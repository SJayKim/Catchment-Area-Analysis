"""Map data API routes — polygon and heatmap data for the map layer."""

from fastapi import APIRouter, HTTPException, Query

from server.repositories import get_data_access

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
            raise HTTPException(status_code=400, detail="bounds must be 'sw_lat,sw_lng,ne_lat,ne_lng'")
        try:
            [float(p.strip()) for p in parts]
        except ValueError:
            raise HTTPException(status_code=400, detail="bounds values must be valid numbers")

    da = get_data_access()
    return await da.districts.get_polygons_geojson(bounds)
