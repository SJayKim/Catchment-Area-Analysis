"""에이전트 출력 Pydantic 모델 (Phase 1 활성 에이전트)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.common import (
    AgeDistribution,
    DailyValue,
    MoneyRange,
    TimeSlot,
    TrendDirection,
)


class PopulationAnalysis(BaseModel):
    """유동인구 분석 결과."""
    total_floating_population: int = Field(..., description="일평균 총 유동인구 (명)")
    floating_by_time: list[TimeSlot] = Field(default_factory=list)
    floating_by_day: list[DailyValue] = Field(default_factory=list)
    resident_population: int = Field(..., description="거주 인구 (명)")
    worker_population: int = Field(..., description="직장인 인구 (명)")
    age_distribution: AgeDistribution = Field(...)
    gender_ratio: float = Field(..., ge=0.0, le=100.0, description="남성 비율 (%)")
    population_trend: TrendDirection = Field(...)
    trend_rate: float = Field(..., description="전년 대비 증감률 (%)")
    peak_times: list[str] = Field(default_factory=list)
    key_insight: str = Field(...)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    data_freshness: str = Field(...)


class RevenueAnalysis(BaseModel):
    """매출 분석 결과."""
    area_total_revenue: int = Field(..., description="상권 전체 월 총매출 (원)")
    target_industry_revenue: int = Field(..., description="타겟 업종 월 총매출 (원)")
    revenue_per_store: int = Field(..., description="점포당 월 평균 매출 (원)")
    revenue_trend: TrendDirection = Field(...)
    seasonal_pattern: list[DailyValue] = Field(default_factory=list)
    avg_ticket_price: int = Field(..., description="평균 결제 단가 (원)")
    estimated_monthly_revenue: int = Field(..., description="신규 점포 예상 월 매출 (원)")
    revenue_range: MoneyRange = Field(...)
    top_performing_industries: list[str] = Field(default_factory=list)
    key_insight: str = Field(...)
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class CompetitionAnalysis(BaseModel):
    """경쟁 분석 결과."""
    total_competitors: int = Field(...)
    direct_competitors: int = Field(...)
    indirect_competitors: int = Field(...)
    saturation_index: float = Field(..., ge=0.0, description="포화 지수 (1.0=평균)")
    opening_rate_12m: float = Field(..., ge=0.0, description="12개월 개업률 (%)")
    closing_rate_12m: float = Field(..., ge=0.0, description="12개월 폐업률 (%)")
    avg_business_duration: float = Field(..., description="평균 영업 기간 (개월)")
    market_share_top5: float = Field(..., ge=0.0, le=100.0)
    differentiation_opportunities: list[str] = Field(default_factory=list)
    competitive_threat_level: str = Field(...)
    key_insight: str = Field(...)
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class LocationAnalysis(BaseModel):
    """입지 분석 결과."""
    accessibility_score: float = Field(..., ge=0.0, le=100.0)
    nearest_subway: str = Field(...)
    bus_routes_within_300m: int = Field(..., ge=0)
    parking_availability: str = Field(...)
    visibility_score: float = Field(..., ge=0.0, le=100.0)
    foot_traffic_quality: str = Field(...)
    anchor_facilities: list[str] = Field(default_factory=list)
    nearby_development: list[str] = Field(default_factory=list)
    floor_recommendation: str = Field(...)
    location_grade: str = Field(...)
    key_insight: str = Field(...)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
