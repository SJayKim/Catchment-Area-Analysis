"""에이전트 출력 Pydantic 모델."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.common import (
    AgeDistribution,
    DailyValue,
    MoneyRange,
    PermitRequirement,
    PropertyInfo,
    RiskFactor,
    ScenarioResult,
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


# ── Phase 2 에이전트 출력 모델 ──


class TrendAnalysis(BaseModel):
    """트렌드 분석 결과."""
    lifecycle_stage: str = Field(..., description="업종 수명주기 (도입기/성장기/성숙기/쇠퇴기)")
    search_volume_trend: TrendDirection = Field(..., description="검색량 추세")
    search_volume_index: float = Field(..., ge=0.0, le=100.0, description="검색량 지수 (100=최고점)")
    social_buzz_score: float = Field(..., ge=0.0, le=100.0, description="SNS 버즈 점수")
    emerging_keywords: list[str] = Field(default_factory=list, description="신규 떠오르는 키워드")
    declining_keywords: list[str] = Field(default_factory=list, description="하락세 키워드")
    consumer_preference_shift: str = Field(..., description="소비자 선호 변화 요약")
    seasonal_peak_months: list[int] = Field(default_factory=list, description="성수기 월 (1-12)")
    risk_signals: list[str] = Field(default_factory=list, description="위험 신호")
    opportunity_signals: list[str] = Field(default_factory=list, description="기회 신호")
    related_trends: list[str] = Field(default_factory=list, description="연관 트렌드")
    key_insight: str = Field(...)
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class FinancialAnalysis(BaseModel):
    """재무 분석 결과."""
    initial_investment_total: int = Field(..., description="초기 투자 총액 (원)")
    investment_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="투자 항목별 금액 (인테리어, 장비, 보증금, 권리금 등)",
    )
    monthly_operating_cost: int = Field(..., description="월 운영비 (원)")
    operating_cost_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="운영비 항목별 금액 (임대료, 인건비, 재료비, 공과금 등)",
    )
    break_even_months: int = Field(..., description="손익분기 예상 (개월)")
    roi_12m: float = Field(..., description="12개월 ROI (%)")
    roi_24m: float = Field(..., description="24개월 ROI (%)")
    scenarios: list[ScenarioResult] = Field(
        default_factory=list,
        description="시나리오별 분석 (낙관/현실/비관)",
    )
    funding_options: list[str] = Field(default_factory=list, description="활용 가능한 자금 조달 옵션")
    monthly_cash_flow_estimate: int = Field(..., description="예상 월 순이익 (원)")
    key_insight: str = Field(...)
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class RiskAnalysis(BaseModel):
    """리스크 분석 결과."""
    overall_risk_score: float = Field(..., ge=0.0, le=100.0, description="종합 리스크 점수 (0=안전, 100=위험)")
    risk_grade: str = Field(..., description="리스크 등급 (매우낮음/낮음/보통/높음/매우높음)")
    risk_factors: list[RiskFactor] = Field(default_factory=list, description="개별 리스크 요인")
    structural_risks: list[str] = Field(default_factory=list, description="구조적 리스크")
    competitive_risks: list[str] = Field(default_factory=list, description="경쟁 리스크")
    environmental_risks: list[str] = Field(default_factory=list, description="환경적 리스크")
    seasonal_vulnerability: float = Field(..., ge=0.0, le=1.0, description="계절성 취약도")
    exit_difficulty: str = Field(..., description="퇴출 난이도 (쉬움/보통/어려움)")
    risk_mitigation_strategies: list[str] = Field(default_factory=list, description="리스크 완화 전략")
    key_insight: str = Field(...)
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class RealEstateAnalysis(BaseModel):
    """부동산 분석 결과."""
    avg_rent_per_pyeong: int = Field(..., description="평당 월 임대료 (원)")
    rent_trend: TrendDirection = Field(..., description="임대료 추세")
    premium_estimate: int = Field(..., description="예상 권리금 (원)")
    premium_range: MoneyRange = Field(..., description="권리금 범위")
    deposit_estimate: int = Field(..., description="예상 보증금 (원)")
    vacancy_rate: float = Field(..., ge=0.0, le=100.0, description="공실률 (%)")
    vacancy_trend: TrendDirection = Field(..., description="공실률 추세")
    avg_lease_duration_months: int = Field(..., description="평균 임대 기간 (개월)")
    available_properties: list[PropertyInfo] = Field(default_factory=list, description="매물 목록")
    recommended_size_pyeong: float = Field(..., description="업종 권장 면적 (평)")
    key_insight: str = Field(...)
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class RegulatoryAnalysis(BaseModel):
    """규제/인허가 분석 결과."""
    required_permits: list[PermitRequirement] = Field(default_factory=list, description="필요 인허가 목록")
    total_permit_count: int = Field(..., description="필요 인허가 총 개수")
    estimated_total_days: int = Field(..., description="인허가 예상 총 소요일")
    estimated_total_cost: int = Field(..., description="인허가 예상 총 비용 (원)")
    zoning_status: str = Field(..., description="용도지역 적합성 (적합/조건부/부적합)")
    zoning_detail: str = Field(..., description="용도지역 상세")
    health_safety_requirements: list[str] = Field(default_factory=list, description="위생/안전 요건")
    operating_hour_restrictions: Optional[str] = Field(None, description="영업시간 제한")
    special_considerations: list[str] = Field(default_factory=list, description="특별 유의사항")
    key_insight: str = Field(...)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
