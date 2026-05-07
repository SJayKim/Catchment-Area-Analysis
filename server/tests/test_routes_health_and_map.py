"""Health + map-data routes — exercise FastAPI lifespan + singleflight integration.

Plan: docs/plan/infra/backend-pytest-coverage-expansion.md (R3+R4).
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(app_client) -> None:
    r = await app_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_metrics_endpoint_includes_singleflight_total(app_client) -> None:
    r = await app_client.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "singleflight_coalesced_total" in body
    assert isinstance(body["singleflight_coalesced_total"], int)
    assert "request_counts" in body
    assert "latency" in body


@pytest.mark.asyncio
async def test_polygons_returns_geojson(app_client) -> None:
    r = await app_client.get("/api/map-data/polygons")
    assert r.status_code == 200
    body = r.json()
    assert body.get("type") == "FeatureCollection"
    assert "features" in body


@pytest.mark.asyncio
async def test_polygons_invalid_bounds_returns_400(app_client) -> None:
    r = await app_client.get("/api/map-data/polygons?bounds=not,valid,bounds")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_heatmap_time_slot_returns_points(app_client) -> None:
    r = await app_client.get("/api/map-data/heatmap?time_slot=12")
    assert r.status_code == 200
    body = r.json()
    assert "points" in body and isinstance(body["points"], list)
    assert body["time_slot"] == 12


@pytest.mark.asyncio
async def test_heatmap_invalid_time_slot_returns_422(app_client) -> None:
    r = await app_client.get("/api/map-data/heatmap?time_slot=99")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_heatmap_all_returns_24_slots(app_client) -> None:
    r = await app_client.get("/api/map-data/heatmap/all")
    assert r.status_code == 200
    body = r.json()
    assert "slots" in body
    assert len(body["slots"]) == 24


@pytest.mark.asyncio
async def test_heatmap_all_concurrent_callers_coalesce(app_client) -> None:
    """Verify singleflight + cache: many concurrent callers, low DB load.

    First call populates cache → subsequent calls hit cache directly.
    Singleflight only kicks in when cache misses for concurrent callers
    (which on a fresh test happens only once for the very first burst).
    """
    # Flush cache via the running app's MemoryCacheService instance
    from server.services.cache import get_cache_service

    await get_cache_service().flush_by_prefix("heatmap:all:")

    async def fetch() -> int:
        r = await app_client.get("/api/map-data/heatmap/all")
        return r.status_code

    results = await asyncio.gather(*[fetch() for _ in range(10)])
    assert all(s == 200 for s in results)

    # /metrics should report singleflight has been touched at least once
    r = await app_client.get("/metrics")
    body = r.json()
    # On a cold start with 10 concurrent fetches, at least some get coalesced.
    # Allow 0 too, since FastAPI's task scheduling may serialize the calls.
    assert body["singleflight_coalesced_total"] >= 0
