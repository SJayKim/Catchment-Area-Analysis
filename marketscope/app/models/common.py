"""공통 재사용 Pydantic 모델."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TimeSlot(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="시간 (0-23)")
    value: float = Field(..., description="해당 시간대의 측정값")
    label: Optional[str] = Field(None, description="시간대 라벨")


class DayOfWeek(str, Enum):
    MONDAY = "월"
    TUESDAY = "화"
    WEDNESDAY = "수"
    THURSDAY = "목"
    FRIDAY = "금"
    SATURDAY = "토"
    SUNDAY = "일"


class DailyValue(BaseModel):
    day: DayOfWeek = Field(..., description="요일")
    value: float = Field(..., description="해당 요일의 측정값")


class AgeDistribution(BaseModel):
    age_10s: float = Field(0.0, ge=0, le=100)
    age_20s: float = Field(0.0, ge=0, le=100)
    age_30s: float = Field(0.0, ge=0, le=100)
    age_40s: float = Field(0.0, ge=0, le=100)
    age_50s: float = Field(0.0, ge=0, le=100)
    age_60_plus: float = Field(0.0, ge=0, le=100)


class TrendDirection(str, Enum):
    STRONG_UP = "강한상승"
    UP = "상승"
    STABLE = "보합"
    DOWN = "하락"
    STRONG_DOWN = "강한하락"


class MoneyRange(BaseModel):
    min_value: int = Field(..., description="최소 금액 (원)")
    max_value: int = Field(..., description="최대 금액 (원)")
    currency: str = Field(default="KRW")


class ScenarioResult(BaseModel):
    label: str = Field(...)
    monthly_revenue: int = Field(...)
    monthly_profit: int = Field(...)
    break_even_months: int = Field(...)
    roi_12m: float = Field(...)
    probability: float = Field(...)
    assumptions: str = Field(...)


class RiskFactor(BaseModel):
    category: str = Field(...)
    name: str = Field(...)
    description: str = Field(...)
    severity: float = Field(..., ge=1.0, le=5.0)
    probability: float = Field(..., ge=0.0, le=1.0)
    impact_score: float = Field(...)
    mitigation: str = Field(...)


class PropertyInfo(BaseModel):
    address: str = Field(...)
    size_pyeong: float = Field(...)
    floor: str = Field(...)
    monthly_rent: int = Field(...)
    deposit: int = Field(...)
    premium: int = Field(0)
    available_date: Optional[str] = None
    source: Optional[str] = None


class PermitRequirement(BaseModel):
    permit_name: str = Field(...)
    issuing_authority: str = Field(...)
    estimated_days: int = Field(...)
    estimated_cost: int = Field(0)
    required_documents: list[str] = Field(default_factory=list)
    difficulty: str = Field(...)
    notes: Optional[str] = None


class ErrorRecord(BaseModel):
    timestamp: str
    agent_name: str
    error_type: str
    error_message: str
    is_critical: bool = False
    fallback_applied: bool = False
