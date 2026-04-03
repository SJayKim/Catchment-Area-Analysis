"""Cache service — Memory and Redis implementations."""

from __future__ import annotations

import json
from typing import Protocol


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
    """Redis-backed cache for real mode."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            from redis.asyncio import Redis
            self._redis = Redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    async def get(self, key: str) -> dict | None:
        redis = await self._get_redis()
        data = await redis.get(key)
        return json.loads(data) if data else None

    async def set(self, key: str, value: dict, ttl: int = 86400) -> None:
        redis = await self._get_redis()
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        await redis.set(key, serialized, ex=ttl)

    async def delete(self, key: str) -> None:
        redis = await self._get_redis()
        await redis.delete(key)

    async def flush_by_prefix(self, prefix: str) -> int:
        redis = await self._get_redis()
        cursor, count = b"0", 0
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=f"{prefix}*", count=100)
            if keys:
                await redis.delete(*keys)
                count += len(keys)
            if cursor == 0:
                break
        return count

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
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


# Backward compatibility — legacy singleton used by existing code during migration
cache_service = MemoryCacheService()
