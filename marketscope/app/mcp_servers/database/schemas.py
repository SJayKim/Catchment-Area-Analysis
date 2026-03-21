"""Database MCP 서버 Pydantic 스키마."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class NearbyStore(BaseModel):
    """근처 점포."""
    store_name: str = ""
    industry_category: str = ""
    address: str = ""
    lat: float = 0.0
    lng: float = 0.0
    distance_m: float = 0.0


class PopulationGrid(BaseModel):
    """격자별 인구 데이터."""
    grid_id: str = ""
    total_population: int = 0
    male_population: int = 0
    female_population: int = 0
    age_groups: dict[str, int] = {}


class RevenueArea(BaseModel):
    """지역별 매출 데이터."""
    area_code: str = ""
    area_name: str = ""
    industry_category: str = ""
    monthly_revenue: int = 0
    store_count: int = 0
    avg_revenue_per_store: int = 0


class CommercialDistrict(BaseModel):
    """상권 정보."""
    district_code: str = ""
    district_name: str = ""
    district_type: str = ""
    total_stores: int = 0
    lat: float = 0.0
    lng: float = 0.0
