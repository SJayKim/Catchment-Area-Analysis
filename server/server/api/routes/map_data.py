"""Map data API routes — polygon and heatmap data for the map layer."""

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from server.api.errors import raise_db_unavailable
from server.repositories import get_data_access
from server.services.cache import get_cache_service
from server.services.singleflight import get_singleflight

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/map-data", tags=["map-data"])


@router.get("/polygons")
async def get_polygons(
    bounds: str | None = Query(
        None,
        description="Viewport bounds as 'sw_lat,sw_lng,ne_lat,ne_lng'",
    ),
) -> dict:
    """Return GeoJSON FeatureCollection of district polygons within viewport bounds."""
    if bounds:
        parts = bounds.split(",")
        if len(parts) != 4:
            raise HTTPException(
                status_code=400,
                detail="bounds must be 'sw_lat,sw_lng,ne_lat,ne_lng'",
            )
        try:
            [float(p.strip()) for p in parts]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="bounds values must be valid numbers",
            ) from None

    try:
        da = get_data_access()
        data = await da.districts.get_polygons_geojson(bounds)
        return JSONResponse(
            content=data,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except OperationalError:
        logger.exception("Database unavailable in get_polygons")
        raise_db_unavailable()


@router.get("/heatmap")
async def get_heatmap(
    time_slot: int = Query(..., ge=0, le=23, description="Hour of day (0-23)"),
    quarter: str | None = Query(None, description="Data quarter (e.g. 2025Q4)"),
) -> dict:
    """Return heatmap point data for a specific time slot."""
    cache = get_cache_service()
    cache_key = f"heatmap:{time_slot}:{quarter or 'latest'}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    async def _load() -> dict:
        da = get_data_access()
        result = await da.heatmap.get_heatmap_data(time_slot, quarter)
        if result.get("points"):
            await cache.set(cache_key, result, ttl=86400)
        return result

    try:
        result = await get_singleflight().do(cache_key, _load)
        return JSONResponse(
            content=result,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except OperationalError:
        logger.exception("Database unavailable in get_heatmap")
        raise_db_unavailable()


@router.get("/heatmap/all")
async def get_heatmap_all(
    quarter: str | None = Query(None, description="Data quarter (e.g. 2025Q4)"),
):
    """Return all 24 hours of heatmap data for client-side preloading."""
    cache = get_cache_service()
    cache_key = f"heatmap:all:{quarter or 'latest'}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return JSONResponse(
            content=cached,
            headers={"Cache-Control": "public, max-age=86400"},
        )

    async def _load() -> dict:
        da = get_data_access()
        result = await da.heatmap.get_heatmap_all(quarter)
        if result.get("slots"):
            await cache.set(cache_key, result, ttl=86400)
        return result

    try:
        result = await get_singleflight().do(cache_key, _load)
        return JSONResponse(
            content=result,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except OperationalError:
        logger.exception("Database unavailable in get_heatmap_all")
        raise_db_unavailable()
