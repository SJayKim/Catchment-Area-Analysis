"""최종 리포트 Pydantic 모델."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from marketscope_common.models.agent_outputs import (
    CompetitionAnalysis,
    LocationAnalysis,
    PopulationAnalysis,
    RevenueAnalysis,
)


class ExecutiveSummary(BaseModel):
    headline: str = Field(...)
    overall_score: float = Field(..., ge=0.0, le=100.0)
    overall_grade: str = Field(...)
    recommendation: str = Field(...)
    key_findings: list[str] = Field(default_factory=list)
    critical_actions: list[str] = Field(default_factory=list)
    summary_paragraph: str = Field(...)


class ScoreBreakdown(BaseModel):
    population_score: float = Field(0.0, ge=0, le=100)
    revenue_score: float = Field(0.0, ge=0, le=100)
    competition_score: float = Field(0.0, ge=0, le=100)
    location_score: float = Field(0.0, ge=0, le=100)


class FinalReport(BaseModel):
    report_id: str = Field(...)
    request_id: str = Field(...)
    generated_at: str = Field(...)
    report_version: str = Field(default="1.0")

    district_name: str = Field(...)
    industry_category: str = Field(...)

    executive_summary: ExecutiveSummary = Field(...)
    score_breakdown: ScoreBreakdown = Field(...)

    population_result: Optional[PopulationAnalysis] = None
    revenue_result: Optional[RevenueAnalysis] = None
    competition_result: Optional[CompetitionAnalysis] = None
    location_result: Optional[LocationAnalysis] = None

    narrative_report: str = Field(...)

    total_execution_time_seconds: float = Field(...)
    total_llm_calls: int = Field(...)
    total_tokens_used: int = Field(...)
