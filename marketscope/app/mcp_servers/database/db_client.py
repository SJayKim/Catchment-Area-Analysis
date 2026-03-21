"""Database MCP — asyncpg 연결 풀 클라이언트."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger("mcp.database.client")

_pool = None

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False


async def get_pool():
    """asyncpg 커넥션 풀을 반환한다. 최초 호출 시 생성."""
    global _pool
    if _pool is None:
        if not HAS_ASYNCPG:
            raise RuntimeError("asyncpg가 설치되지 않았습니다.")
        dsn = os.environ.get(
            "DATABASE_URL",
            "postgresql://marketscope:marketscope@localhost:5432/marketscope",
        )
        _pool = await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=10)
        logger.info("Database 커넥션 풀 생성 완료")
    return _pool


async def execute_query(query: str, *args: Any) -> list[dict[str, Any]]:
    """SQL 쿼리를 실행하고 결과를 dict 리스트로 반환한다."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(row) for row in rows]


async def execute_scalar(query: str, *args: Any) -> Any:
    """단일 값을 반환하는 쿼리."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


async def close_pool() -> None:
    """커넥션 풀 종료."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database 커넥션 풀 종료")
