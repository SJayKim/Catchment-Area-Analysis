"""MemoryCacheService + RedisCacheService graceful degrade regression."""

from __future__ import annotations

import pytest

from server.services.cache import MemoryCacheService, RedisCacheService


@pytest.mark.asyncio
async def test_memory_cache_set_get_roundtrip(memory_cache: MemoryCacheService) -> None:
    assert await memory_cache.get("missing") is None
    await memory_cache.set("k", {"v": 1})
    assert await memory_cache.get("k") == {"v": 1}


@pytest.mark.asyncio
async def test_memory_cache_delete(memory_cache: MemoryCacheService) -> None:
    await memory_cache.set("k", {"v": 1})
    await memory_cache.delete("k")
    assert await memory_cache.get("k") is None


@pytest.mark.asyncio
async def test_memory_cache_flush_by_prefix(memory_cache: MemoryCacheService) -> None:
    await memory_cache.set("heatmap:0:latest", {"x": 0})
    await memory_cache.set("heatmap:1:latest", {"x": 1})
    await memory_cache.set("polygons", {"x": -1})

    n = await memory_cache.flush_by_prefix("heatmap:")
    assert n == 2
    assert await memory_cache.get("heatmap:0:latest") is None
    assert await memory_cache.get("polygons") == {"x": -1}


@pytest.mark.asyncio
async def test_memory_cache_unicode_korean(memory_cache: MemoryCacheService) -> None:
    """Mock fixture / Korean payloads must roundtrip without mojibake."""
    payload = {"district_name": "강남역", "tags": ["카페", "한식"]}
    await memory_cache.set("k", payload)
    assert await memory_cache.get("k") == payload


@pytest.mark.asyncio
async def test_memory_cache_close_clears_all(memory_cache: MemoryCacheService) -> None:
    await memory_cache.set("k", {"v": 1})
    await memory_cache.close()
    assert await memory_cache.get("k") is None


@pytest.mark.asyncio
async def test_redis_cache_unreachable_returns_none_gracefully() -> None:
    """Redis at unreachable URL → all ops degrade to None / no-op."""
    cache = RedisCacheService("redis://127.0.0.1:1/0")
    # Initial connection fails — graceful degrade, no exception
    assert await cache.get("k") is None
    await cache.set("k", {"v": 1})  # silent no-op
    assert await cache.get("k") is None
    await cache.delete("k")  # silent no-op
    assert await cache.flush_by_prefix("p:") == 0
    await cache.close()
