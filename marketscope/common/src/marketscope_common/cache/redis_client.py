"""Redis 캐시 클라이언트 — async Redis + cached_call 헬퍼.

캐시 키 패턴: {server}:{tool}:{params_hash}
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable, Coroutine

import redis.asyncio as aioredis

from marketscope_common.config import get_settings

logger = logging.getLogger("cache.redis")

_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Redis 연결 풀 싱글턴."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return _pool


async def close_redis() -> None:
    """Redis 연결 종료."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


def _make_cache_key(server: str, tool: str, params: dict[str, Any]) -> str:
    """캐시 키 생성: {server}:{tool}:{params_hash}."""
    sorted_params = json.dumps(params, sort_keys=True, default=str)
    params_hash = hashlib.sha256(sorted_params.encode()).hexdigest()[:16]
    return f"{server}:{tool}:{params_hash}"


async def cached_call(
    server: str,
    tool: str,
    params: dict[str, Any],
    fetch_fn: Callable[[], Coroutine[Any, Any, dict]],
    ttl: int | None = None,
) -> dict:
    """캐시가 있으면 반환, 없으면 fetch_fn 실행 후 캐시 저장.

    Args:
        server: MCP 서버 이름 (예: "public_data", "maps")
        tool: 도구 이름 (예: "get_floating_population")
        params: 도구 파라미터 (캐시 키 생성에 사용)
        fetch_fn: 캐시 미스 시 호출할 비동기 함수
        ttl: 캐시 TTL (초). None이면 설정값 사용.
    """
    if ttl is None:
        ttl = get_settings().redis_cache_ttl

    key = _make_cache_key(server, tool, params)

    try:
        r = await get_redis()
        cached = await r.get(key)
        if cached is not None:
            logger.debug("캐시 HIT: %s", key)
            return json.loads(cached)
    except Exception:
        logger.warning("Redis 접근 실패, fallback으로 직접 호출", exc_info=True)

    # 캐시 미스 → 실제 호출
    logger.debug("캐시 MISS: %s", key)
    result = await fetch_fn()

    try:
        r = await get_redis()
        await r.set(key, json.dumps(result, default=str), ex=ttl)
    except Exception:
        logger.warning("Redis 캐시 저장 실패", exc_info=True)

    return result


async def invalidate(server: str, tool: str, params: dict[str, Any]) -> bool:
    """특정 캐시 키 무효화."""
    key = _make_cache_key(server, tool, params)
    try:
        r = await get_redis()
        deleted = await r.delete(key)
        return deleted > 0
    except Exception:
        logger.warning("캐시 무효화 실패: %s", key)
        return False


async def invalidate_pattern(pattern: str) -> int:
    """패턴 매칭 키 일괄 무효화 (예: "public_data:*")."""
    try:
        r = await get_redis()
        count = 0
        async for key in r.scan_iter(match=pattern, count=100):
            await r.delete(key)
            count += 1
        return count
    except Exception:
        logger.warning("패턴 캐시 무효화 실패: %s", pattern)
        return 0


async def health_check() -> dict:
    """Redis 상태 확인."""
    try:
        r = await get_redis()
        pong = await r.ping()
        info = await r.info(section="memory")
        return {
            "status": "ok",
            "ping": pong,
            "used_memory_human": info.get("used_memory_human", "unknown"),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
