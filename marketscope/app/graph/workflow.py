"""LangGraph 워크플로우 정의 - MarketScope AI DAG."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.graph.edges import (
    should_continue_after_commander,
    should_run_group2,
    should_skip_reports,
)
from app.graph.nodes import (
    commander_judgment_node,
    commander_plan_node,
    competition_node,
    group1_complete_node,
    group2_complete_node,
    location_node,
    narrative_node,
    population_node,
    report_assembly_node,
    revenue_node,
    visualization_node,
)
from app.models.state import MarketScopeState


def build_workflow() -> StateGraph:
    """Phase 1 MVP 워크플로우 그래프를 구성한다.

    DAG 구조 (병렬 fan-out/fan-in 패턴):
        START
          → commander_plan
          → [conditional] fan-out to [population, competition] in parallel
          → group1_complete (fan-in barrier)
          → [conditional] fan-out to [revenue, location] in parallel | commander_judgment
          → group2_complete (fan-in barrier)
          → commander_judgment
          → [conditional] report_generation (narrative + visualization) | report_assembly
          → report_assembly
          → END
    """
    workflow = StateGraph(MarketScopeState)

    # ── 노드 등록 ──
    workflow.add_node("commander_plan", commander_plan_node)
    workflow.add_node("population", population_node)
    workflow.add_node("competition", competition_node)
    workflow.add_node("group1_complete", group1_complete_node)
    workflow.add_node("revenue", revenue_node)
    workflow.add_node("location", location_node)
    workflow.add_node("group2_complete", group2_complete_node)
    workflow.add_node("commander_judgment", commander_judgment_node)
    workflow.add_node("narrative", narrative_node)
    workflow.add_node("visualization", visualization_node)
    workflow.add_node("report_assembly", report_assembly_node)

    # ── 엣지 연결 ──

    # 1. 시작 → Commander Planning
    workflow.set_entry_point("commander_plan")

    # 2. Commander → 조건부 분기: fan-out to Group 1 or end
    #    Mapping to a list triggers parallel execution of all listed nodes.
    workflow.add_conditional_edges(
        "commander_plan",
        should_continue_after_commander,
        {
            "parallel_group_1": ["population", "competition"],  # Fan-out: 병렬 실행
            "end": END,
        },
    )

    # 3. Group 1 fan-in: both population and competition → group1_complete
    #    LangGraph waits for ALL incoming edges before running the target node.
    workflow.add_edge("population", "group1_complete")
    workflow.add_edge("competition", "group1_complete")

    # 4. Group 1 완료 → 조건부: fan-out Group 2 or skip to judgment
    workflow.add_conditional_edges(
        "group1_complete",
        should_run_group2,
        {
            "parallel_group_2": ["revenue", "location"],  # Fan-out: 병렬 실행
            "commander_judgment": "commander_judgment",
        },
    )

    # 5. Group 2 fan-in: both revenue and location → group2_complete
    workflow.add_edge("revenue", "group2_complete")
    workflow.add_edge("location", "group2_complete")

    # 6. Group 2 완료 → Commander Judgment
    workflow.add_edge("group2_complete", "commander_judgment")

    # 7. Judgment → 리포트 생성 조건부
    workflow.add_conditional_edges(
        "commander_judgment",
        should_skip_reports,
        {
            "report_generation": "narrative",
            "report_assembly": "report_assembly",
        },
    )

    # 8. Report Generation: narrative → visualization → assembly
    workflow.add_edge("narrative", "visualization")
    workflow.add_edge("visualization", "report_assembly")

    # 9. Report Assembly → END
    workflow.add_edge("report_assembly", END)

    return workflow


def create_app() -> Any:
    """컴파일된 LangGraph 앱을 반환한다."""
    workflow = build_workflow()
    # MemorySaver로 체크포인팅 (개발용)
    try:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        return workflow.compile(checkpointer=checkpointer)
    except ImportError:
        return workflow.compile()
