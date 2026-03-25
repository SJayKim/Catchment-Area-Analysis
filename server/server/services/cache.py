import json

from server.config import settings


class CacheService:
    """Redis caching wrapper with in-memory fallback for mock mode."""

    def __init__(self) -> None:
        self._redis = None
        self._memory: dict[str, str] = {}

    async def get_redis(self):
        if settings.use_mock:
            return None
        if self._redis is None:
            from redis.asyncio import Redis
            self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def get(self, key: str) -> dict | None:
        """Get cached value by key. Returns None if not found."""
        if settings.use_mock:
            data = self._memory.get(key)
            return json.loads(data) if data else None
        redis = await self.get_redis()
        data = await redis.get(key)
        return json.loads(data) if data else None

    async def set(self, key: str, value: dict, ttl: int = 86400) -> None:
        """Set a value in cache with TTL (default 24h)."""
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        if settings.use_mock:
            self._memory[key] = serialized
            return
        redis = await self.get_redis()
        await redis.set(key, serialized, ex=ttl)

    async def delete(self, key: str) -> None:
        """Delete a cached key."""
        if settings.use_mock:
            self._memory.pop(key, None)
            return
        redis = await self.get_redis()
        await redis.delete(key)

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None


cache_service = CacheService()
