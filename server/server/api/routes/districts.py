"""District search and detail API routes."""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError

from server.repositories import get_data_access

logger = logging.getLogger(__name__)

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
    try:
        da = get_data_access()
        total, items = await da.districts.list_districts(search, type, limit, offset)
        return DistrictListResponse(
            total=total,
            items=[DistrictSummary(**item) for item in items],
        )
    except OperationalError:
        logger.exception("Database unavailable in list_districts")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable",
        ) from None


@router.get("/districts/{code}", response_model=DistrictDetail)
async def get_district(code: str) -> DistrictDetail:
    """Get district detail including polygon GeoJSON."""
    try:
        da = get_data_access()
        detail = await da.districts.get_district_detail(code)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"District '{code}' not found")
        return DistrictDetail(**detail)
    except HTTPException:
        raise
    except OperationalError:
        logger.exception("Database unavailable in get_district")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable",
        ) from None
