"""LangGraph 공유 상태 정의."""

from __future__ import annotations

import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph.message import add_messages

from app.models.agent_outputs import (
    CompetitionAnalysis,
    FinancialAnalysis,
    LocationAnalysis,
    PopulationAnalysis,
    RealEstateAnalysis,
    RegulatoryAnalysis,
    RevenueAnalysis,
    RiskAnalysis,
    TrendAnalysis,
)
from app.models.debate import DebateResult


class CommanderPlan(TypedDict):
    """Commander 에이전트가 수립한 실행 계획."""
    analysis_mode: str
    target_location: str
    target_location_secondary: Optional[str]
    target_industry: str
    agents_to_run: list[str]
    agents_to_skip: list[str]
    force_debate: bool
    priority_focus: list[str]
    user_constraints: dict[str, Any]
    estimated_duration_seconds: int
    clarification_needed: bool
    clarification_message: Optional[str]


class FinalJudgment(TypedDict):
    """Commander 에이전트의 최종 판단."""
    overall_score: float
    overall_grade: str
    recommendation: str
    executive_summary: str
    key_findings: list[str]
    critical_actions: list[str]
    score_breakdown: dict[str, float]


class NodeExecution(TypedDict):
    """노드 실행 메타데이터."""
    node_id: str
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_seconds: Optional[float]
    llm_model_used: Optional[str]
    token_usage: Optional[dict[str, int]]
    error_message: Optional[str]
    retry_count: int


class VisualizationOutput(TypedDict):
    """시각화 에이전트 출력."""
    chart_configs: list[dict[str, Any]]
    map_config: Optional[dict[str, Any]]
    summary_cards: list[dict[str, Any]]


class NarrativeOutput(TypedDict):
    """내러티브 에이전트 출력."""
    executive_summary: str
    detailed_sections: list[dict[str, str]]
    recommendations: list[str]
    risk_warnings: list[str]


class MarketScopeState(TypedDict):
    """MarketScope AI LangGraph 메인 State."""
    # Session metadata
    session_id: str
    created_at: str
    updated_at: str

    # User input
    user_input: str
    messages: Annotated[list, add_messages]

    # Commander plan
    commander_plan: Optional[CommanderPlan]
    final_judgment: Optional[FinalJudgment]

    # Phase 1 agent results
    population_result: Optional[PopulationAnalysis]
    competition_result: Optional[CompetitionAnalysis]
    revenue_result: Optional[RevenueAnalysis]
    location_result: Optional[LocationAnalysis]

    # Phase 2 agent results
    trend_result: Optional[TrendAnalysis]
    financial_result: Optional[FinancialAnalysis]
    risk_result: Optional[RiskAnalysis]
    real_estate_result: Optional[RealEstateAnalysis]
    regulatory_result: Optional[RegulatoryAnalysis]

    # Debate
    debate_decision: Optional[str]  # "trigger" | "skip"
    debate_trigger_reasons: Annotated[list[str], operator.add]
    debate_result: Optional[DebateResult]

    # Report outputs
    visualization_output: Optional[VisualizationOutput]
    narrative_output: Optional[NarrativeOutput]
    final_report: Optional[dict[str, Any]]

    # Execution tracking
    node_executions: Annotated[list[NodeExecution], operator.add]
    current_phase: int
    progress_pct: float

    # Errors
    errors: Annotated[list[dict[str, Any]], operator.add]
    has_critical_failure: bool

    # Comparison mode
    secondary_population_result: Optional[PopulationAnalysis]
    secondary_competition_result: Optional[CompetitionAnalysis]
    secondary_revenue_result: Optional[RevenueAnalysis]
    secondary_location_result: Optional[LocationAnalysis]
    comparison_summary: Optional[dict[str, Any]]


def create_initial_state(session_id: str, user_input: str) -> MarketScopeState:
    now = datetime.now(timezone.utc).isoformat()
    return MarketScopeState(
        session_id=session_id,
        created_at=now,
        updated_at=now,
        user_input=user_input,
        messages=[],
        commander_plan=None,
        final_judgment=None,
        # Phase 1
        population_result=None,
        competition_result=None,
        revenue_result=None,
        location_result=None,
        # Phase 2
        trend_result=None,
        financial_result=None,
        risk_result=None,
        real_estate_result=None,
        regulatory_result=None,
        debate_decision=None,
        debate_trigger_reasons=[],
        debate_result=None,
        # Report
        visualization_output=None,
        narrative_output=None,
        final_report=None,
        node_executions=[],
        current_phase=0,
        progress_pct=0.0,
        errors=[],
        has_critical_failure=False,
        secondary_population_result=None,
        secondary_competition_result=None,
        secondary_revenue_result=None,
        secondary_location_result=None,
        comparison_summary=None,
    )
