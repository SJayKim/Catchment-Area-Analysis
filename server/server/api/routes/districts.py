"""District search and detail API routes."""

import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from server.config import settings

router = APIRouter(prefix="/api", tags=["districts"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class DistrictSummary(BaseModel):
    district_code: str
    district_name: str
    district_type: str
    gu_code: str | None = None
    dong_code: str | None = None
    data_quarter: str
    center_lng: float | None = None
    center_lat: float | None = None


class DistrictListResponse(BaseModel):
    total: int
    items: list[DistrictSummary]


class DistrictDetail(BaseModel):
    district_code: str
    district_name: str
    district_type: str
    gu_code: str | None = None
    dong_code: str | None = None
    data_quarter: str
    center_lng: float | None = None
    center_lat: float | None = None
    polygon: dict | None = None  # GeoJSON geometry


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/districts", response_model=DistrictListResponse)
async def list_districts(
    search: str | None = Query(None, description="상권명 검색 키워드"),
    type: str | None = Query(None, alias="type", description="상권 유형 필터"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> DistrictListResponse:
    """Search / list districts with optional keyword and type filter."""

    if settings.use_mock:
        from server.agent.tools.mock_data import get_mock_district_list
        all_items = get_mock_district_list(search, type)
        total = len(all_items)
        items = all_items[offset:offset + limit]
        return DistrictListResponse(
            total=total,
            items=[DistrictSummary(**item) for item in items],
        )

    from fastapi import Depends
    from geoalchemy2.functions import ST_AsGeoJSON, ST_X, ST_Y
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession

    from server.api.deps import get_db
    from server.models.district import District

    async for db in get_db():
        base_query = select(
            District,
            ST_AsGeoJSON(District.boundary).label("geojson"),
            ST_X(District.center_point).label("cx"),
            ST_Y(District.center_point).label("cy"),
        )

        conditions = []
        if search:
            conditions.append(District.district_name.ilike(f"%{search}%"))
        if type:
            conditions.append(District.district_type == type)

        if conditions:
            base_query = base_query.where(*conditions)

        count_query = select(func.count(District.district_code))
        if conditions:
            count_query = count_query.where(*conditions)
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        query = base_query.order_by(District.district_name).limit(limit).offset(offset)
        result = await db.execute(query)
        rows = result.all()

        items = []
        for row in rows:
            district, geojson_str, cx, cy = row
            items.append(DistrictSummary(
                district_code=district.district_code,
                district_name=district.district_name,
                district_type=district.district_type,
                gu_code=district.gu_code,
                dong_code=district.dong_code,
                data_quarter=district.data_quarter,
                center_lng=cx,
                center_lat=cy,
            ))

        return DistrictListResponse(total=total, items=items)


@router.get("/districts/{code}", response_model=DistrictDetail)
async def get_district(code: str) -> DistrictDetail:
    """Get district detail including polygon GeoJSON."""

    if settings.use_mock:
        from server.agent.tools.mock_data import DISTRICTS
        d = DISTRICTS.get(code)
        if d is None:
            raise HTTPException(status_code=404, detail=f"District '{code}' not found")
        return DistrictDetail(
            district_code=d["code"],
            district_name=d["name"],
            district_type=d["type"],
            data_quarter=d["quarter"],
            center_lng=d["center"]["lng"],
            center_lat=d["center"]["lat"],
            polygon={
                "type": "Polygon",
                "coordinates": [d["polygon"]],
            },
        )

    from fastapi import Depends
    from geoalchemy2.functions import ST_AsGeoJSON, ST_X, ST_Y
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from server.api.deps import get_db
    from server.models.district import District

    async for db in get_db():
        query = select(
            District,
            ST_AsGeoJSON(District.boundary).label("geojson"),
            ST_X(District.center_point).label("cx"),
            ST_Y(District.center_point).label("cy"),
        ).where(District.district_code == code)

        result = await db.execute(query)
        row = result.first()

        if row is None:
            raise HTTPException(status_code=404, detail=f"District '{code}' not found")

        district, geojson_str, cx, cy = row
        polygon = json.loads(geojson_str) if geojson_str else None

        return DistrictDetail(
            district_code=district.district_code,
            district_name=district.district_name,
            district_type=district.district_type,
            gu_code=district.gu_code,
            dong_code=district.dong_code,
            data_quarter=district.data_quarter,
            center_lng=cx,
            center_lat=cy,
            polygon=polygon,
        )
