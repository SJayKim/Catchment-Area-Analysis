"""Real benchmark repository — DB percentile queries with caching."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server.services.cache import get_cache_service


class RealBenchmarkRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_benchmarks(self, district_type: str) -> dict:
        cache = get_cache_service()
        cache_key = f"benchmarks:{district_type}"
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

        # TODO: Implement real DB percentile_cont() queries when Phase 1B data is loaded.
        # For now, fall back to the mock hardcoded benchmarks.
        from server.repositories.mock.benchmarks import MockBenchmarkRepository

        result = await MockBenchmarkRepository().get_benchmarks(district_type)
        await cache.set(cache_key, result, ttl=86400)
        return result
