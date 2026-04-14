"""Cache service — Memory and Redis implementations."""

from __future__ import annotations

import json
import logging
import time
from typing import Protocol

logger = logging.getLogger(__name__)


class CacheService(Protocol):
    """Cache service interface."""

    async def get(self, key: str) -> dict | None: ...
    async def set(self, key: str, value: dict, ttl: int = 86400) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def flush_by_prefix(self, prefix: str) -> int: ...
    async def close(self) -> None: ...


class MemoryCacheService:
    """In-memory cache for mock mode — no external dependencies."""

    def __init__(self) -> None:
        self._memory: dict[str, str] = {}

    async def get(self, key: str) -> dict | None:
        data = self._memory.get(key)
        return json.loads(data) if data else None

    async def set(self, key: str, value: dict, ttl: int = 86400) -> None:
        self._memory[key] = json.dumps(value, ensure_ascii=False, default=str)

    async def delete(self, key: str) -> None:
        self._memory.pop(key, None)

    async def flush_by_prefix(self, prefix: str) -> int:
        keys_to_delete = [k for k in self._memory if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._memory[k]
        return len(keys_to_delete)

    async def close(self) -> None:
        self._memory.clear()


class RedisCacheService:
    """Redis-backed cache — graceful degradation with exponential backoff."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis = None
        # Exponential backoff for reconnection
        self._last_fail_time: float = 0.0
        self._backoff_seconds: float = 1.0
        self._max_backoff: float = 60.0

    async def _get_redis(self):
        if self._redis is not None:
            return self._redis

        # Exponential backoff: skip reconnection if too soon after last failure
        now = time.monotonic()
        if self._last_fail_time > 0 and (now - self._last_fail_time) < self._backoff_seconds:
            return None

        try:
            from redis.asyncio import Redis
            self._redis = Redis.from_url(
                self._redis_url, decode_responses=True,
                socket_connect_timeout=3, socket_timeout=3,
                max_connections=20,
            )
            await self._redis.ping()
            # Success — reset backoff
            self._backoff_seconds = 1.0
            self._last_fail_time = 0.0
        except Exception:
            logger.warning("Redis connection failed — cache disabled", exc_info=True)
            self._redis = None
            self._last_fail_time = time.monotonic()
            self._backoff_seconds = min(self._backoff_seconds * 2, self._max_backoff)
            return None
        return self._redis

    def _on_error(self, operation: str, key: str = "") -> None:
        """Common error handling: log, reset connection, update backoff."""
        logger.warning("Redis %s failed for key=%s", operation, key)
        self._redis = None
        self._last_fail_time = time.monotonic()
        self._backoff_seconds = min(self._backoff_seconds * 2, self._max_backoff)

    async def get(self, key: str) -> dict | None:
        try:
            redis = await self._get_redis()
            if redis is None:
                return None
            data = await redis.get(key)
            return json.loads(data) if data else None
        except Exception:
            self._on_error("GET", key)
            return None

    async def set(self, key: str, value: dict, ttl: int = 86400) -> None:
        try:
            redis = await self._get_redis()
            if redis is None:
                return
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            await redis.set(key, serialized, ex=ttl)
        except Exception:
            self._on_error("SET", key)

    async def delete(self, key: str) -> None:
        try:
            redis = await self._get_redis()
            if redis is None:
                return
            await redis.delete(key)
        except Exception:
            self._on_error("DELETE", key)

    async def flush_by_prefix(self, prefix: str) -> int:
        try:
            redis = await self._get_redis()
            if redis is None:
                return 0
            cursor, count = b"0", 0
            while True:
                cursor, keys = await redis.scan(cursor=cursor, match=f"{prefix}*", count=100)
                if keys:
                    await redis.delete(*keys)
                    count += len(keys)
                if cursor == 0:
                    break
            return count
        except Exception:
            self._on_error("FLUSH", prefix)
            return 0

    async def close(self) -> None:
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None


# ---------------------------------------------------------------------------
# Module-level accessors
# ---------------------------------------------------------------------------

_cache_service: MemoryCacheService | RedisCacheService | None = None


def get_cache_service() -> MemoryCacheService | RedisCacheService:
    """Return the global cache service. Raises if not initialized."""
    if _cache_service is None:
        raise RuntimeError("CacheService not initialized. Call set_cache_service() first.")
    return _cache_service


def set_cache_service(cs: MemoryCacheService | RedisCacheService) -> None:
    """Set the global cache service (called once at startup)."""
    global _cache_service
    _cache_service = cs
