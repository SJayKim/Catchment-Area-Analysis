"""Map data API routes — polygon and heatmap data for the map layer."""

import json

from fastapi import APIRouter, HTTPException, Query

from server.config import settings

router = APIRouter(prefix="/api/map-data", tags=["map-data"])


@router.get("/polygons")
async def get_polygons(
    bounds: str | None = Query(
        None,
        description="Viewport bounds as 'sw_lat,sw_lng,ne_lat,ne_lng'",
    ),
) -> dict:
    """Return GeoJSON FeatureCollection of district polygons within viewport bounds.

    If `bounds` is not provided, return all polygons (capped at 500).
    """

    if settings.use_mock:
        from server.agent.tools.mock_data import get_mock_geojson
        return get_mock_geojson()

    from geoalchemy2.functions import ST_AsGeoJSON, ST_X, ST_Y
    from sqlalchemy import func, select
    from server.api.deps import get_db
    from server.models.district import District

    async for db in get_db():
        query = select(
            District.district_code,
            District.district_name,
            District.district_type,
            District.data_quarter,
            ST_AsGeoJSON(District.boundary).label("geojson"),
            ST_X(District.center_point).label("cx"),
            ST_Y(District.center_point).label("cy"),
        )

        if bounds:
            parts = bounds.split(",")
            if len(parts) != 4:
                raise HTTPException(
                    status_code=400,
                    detail="bounds must be 'sw_lat,sw_lng,ne_lat,ne_lng'",
                )

            try:
                sw_lat, sw_lng, ne_lat, ne_lng = (float(p.strip()) for p in parts)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="bounds values must be valid numbers",
                )

            envelope = func.ST_MakeEnvelope(sw_lng, sw_lat, ne_lng, ne_lat, 4326)
            query = query.where(func.ST_Intersects(District.boundary, envelope))

        query = query.limit(500)
        result = await db.execute(query)
        rows = result.all()

        features = []
        for row in rows:
            code, name, d_type, quarter, geojson_str, cx, cy = row
            if not geojson_str:
                continue

            geometry = json.loads(geojson_str)
            feature = {
                "type": "Feature",
                "properties": {
                    "district_code": code,
                    "district_name": name,
                    "district_type": d_type,
                    "data_quarter": quarter,
                    "center": [cx, cy] if cx is not None and cy is not None else None,
                },
                "geometry": geometry,
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features,
        }
