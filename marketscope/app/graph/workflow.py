"""LangGraph 워크플로우 정의 - MarketScope AI DAG (Phase 2)."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.graph.edges import (
    route_after_debate_check,
    should_continue_after_commander,
    should_run_group2,
    should_run_group3,
    should_skip_reports,
)
from app.graph.nodes import (
    commander_judgment_node,
    commander_plan_node,
    competition_node,
    debate_check_node,
    debate_node,
    financial_node,
    group1_complete_node,
    group2_complete_node,
    group3_complete_node,
    location_node,
    narrative_node,
    population_node,
    real_estate_node,
    regulatory_node,
    report_assembly_node,
    revenue_node,
    risk_node,
    trend_node,
    user_input_node,
    visualization_node,
)
from app.models.state import MarketScopeState


def build_workflow() -> StateGraph:
    """Phase 2 워크플로우 그래프를 구성한다.

    DAG 구조 (병렬 fan-out/fan-in 패턴):
        START
          → user_input (입력 파싱 & 검증)
          → commander_plan
          → [conditional] fan-out Group 1: [population, competition]
          → group1_complete (fan-in)
          → [conditional] fan-out Group 2: [revenue, location] | commander_judgment
          → group2_complete (fan-in)
          → [conditional] fan-out Group 3: [trend, real_estate, regulatory] | financial
          → group3_complete (fan-in)
          → financial (revenue + competition 의존)
          → risk (전체 결과 의존)
          → debate_check (트리거 조건 평가)
          → [conditional] debate | commander_judgment
          → commander_judgment
          → [conditional] report_generation (narrative → visualization) | report_assembly
          → report_assembly
          → END
    """
    workflow = StateGraph(MarketScopeState)

    # ── 노드 등록 ──
    # Entry
    workflow.add_node("user_input", user_input_node)

    # Phase 1
    workflow.add_node("commander_plan", commander_plan_node)
    workflow.add_node("population", population_node)
    workflow.add_node("competition", competition_node)
    workflow.add_node("group1_complete", group1_complete_node)
    workflow.add_node("revenue", revenue_node)
    workflow.add_node("location", location_node)
    workflow.add_node("group2_complete", group2_complete_node)

    # Phase 2 - 에이전트
    workflow.add_node("trend", trend_node)
    workflow.add_node("real_estate", real_estate_node)
    workflow.add_node("regulatory", regulatory_node)
    workflow.add_node("group3_complete", group3_complete_node)
    workflow.add_node("financial", financial_node)
    workflow.add_node("risk", risk_node)

    # Phase 2 - 토론
    workflow.add_node("debate_check", debate_check_node)
    workflow.add_node("debate", debate_node)

    # 판단 + 리포트
    workflow.add_node("commander_judgment", commander_judgment_node)
    workflow.add_node("narrative", narrative_node)
    workflow.add_node("visualization", visualization_node)
    workflow.add_node("report_assembly", report_assembly_node)

    # ── 엣지 연결 ──

    # 0. 시작 → User Input 파싱
    workflow.set_entry_point("user_input")

    # 1. User Input → Commander Planning
    workflow.add_edge("user_input", "commander_plan")

    # 2. Commander → fan-out Group 1 or END (clarification needed)
    workflow.add_conditional_edges(
        "commander_plan",
        should_continue_after_commander,
        {
            "parallel_group_1": ["population", "competition"],
            "end": END,
        },
    )

    # 3. Group 1 fan-in
    workflow.add_edge("population", "group1_complete")
    workflow.add_edge("competition", "group1_complete")

    # 4. Group 1 → fan-out Group 2 or skip to judgment (quick mode)
    workflow.add_conditional_edges(
        "group1_complete",
        should_run_group2,
        {
            "parallel_group_2": ["revenue", "location"],
            "commander_judgment": "commander_judgment",
        },
    )

    # 5. Group 2 fan-in
    workflow.add_edge("revenue", "group2_complete")
    workflow.add_edge("location", "group2_complete")

    # 6. Group 2 → fan-out Group 3 or skip (quick mode)
    workflow.add_conditional_edges(
        "group2_complete",
        should_run_group3,
        {
            "parallel_group_3": ["trend", "real_estate", "regulatory"],
            "financial": "financial",
        },
    )

    # 7. Group 3 fan-in
    workflow.add_edge("trend", "group3_complete")
    workflow.add_edge("real_estate", "group3_complete")
    workflow.add_edge("regulatory", "group3_complete")

    # 8. Group 3 → financial (순차)
    workflow.add_edge("group3_complete", "financial")

    # 9. financial → risk (순차: 재무 결과 기반 리스크 평가)
    workflow.add_edge("financial", "risk")

    # 10. risk → debate_check (트리거 조건 평가)
    workflow.add_edge("risk", "debate_check")

    # 11. debate_check → 조건부 라우팅 (debate | commander_judgment)
    workflow.add_conditional_edges(
        "debate_check",
        route_after_debate_check,
        {
            "debate": "debate",
            "commander_judgment": "commander_judgment",
        },
    )

    # 12. debate → commander_judgment
    workflow.add_edge("debate", "commander_judgment")

    # 12. Judgment → 리포트 생성 조건부
    workflow.add_conditional_edges(
        "commander_judgment",
        should_skip_reports,
        {
            "report_generation": "narrative",
            "report_assembly": "report_assembly",
        },
    )

    # 13. Report Generation: narrative → visualization → assembly
    workflow.add_edge("narrative", "visualization")
    workflow.add_edge("visualization", "report_assembly")

    # 14. Report Assembly → END
    workflow.add_edge("report_assembly", END)

    return workflow


def create_app() -> Any:
    """컴파일된 LangGraph 앱을 반환한다."""
    workflow = build_workflow()
    try:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        return workflow.compile(checkpointer=checkpointer)
    except ImportError:
        return workflow.compile()
