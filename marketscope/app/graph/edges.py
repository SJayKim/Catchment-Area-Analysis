"""조건부 엣지 로직."""

from __future__ import annotations

from typing import Any, Literal

from app.logging_config import get_logger

logger = get_logger("graph.edges")


def should_continue_after_commander(
    state: dict[str, Any],
) -> str:
    """Commander 계획 후 다음 단계 결정."""
    plan = state.get("commander_plan")
    if not plan:
        return "end"

    if plan.get("clarification_needed"):
        logger.info("edge.decision", edge="should_continue_after_commander", result="end", reason="clarification_needed")
        return "end"  # 명확화 필요 → 사용자에게 반환

    logger.info("edge.decision", edge="should_continue_after_commander", result="parallel_group_1")
    return "parallel_group_1"


def should_run_group2(
    state: dict[str, Any],
) -> str:
    """Group 1 완료 후 Group 2 실행 여부 결정."""
    plan = state.get("commander_plan", {})
    mode = plan.get("analysis_mode", "basic")

    if mode == "quick":
        # quick 모드: Group 1만 실행 후 바로 judgment
        logger.info("edge.decision", edge="should_run_group2", result="commander_judgment", mode=mode)
        return "commander_judgment"

    logger.info("edge.decision", edge="should_run_group2", result="parallel_group_2", mode=mode)
    return "parallel_group_2"


def is_comparison_mode(state: dict[str, Any]) -> str:
    """비교 분석 모드 여부를 판별한다."""
    plan = state.get("commander_plan", {})
    if plan.get("analysis_mode") == "comparison" and plan.get("target_location_secondary"):
        return "comparison"
    return "single"


def should_run_group3(
    state: dict[str, Any],
) -> str:
    """Group 2 완료 후 Group 3 (trend, real_estate, regulatory) 실행 여부."""
    plan = state.get("commander_plan", {})
    mode = plan.get("analysis_mode", "basic")

    if mode == "quick":
        logger.info("edge.decision", edge="should_run_group3", result="financial", mode=mode)
        return "financial"  # quick → Group 3 스킵, financial로

    logger.info("edge.decision", edge="should_run_group3", result="parallel_group_3", mode=mode)
    return "parallel_group_3"


def route_after_debate_check(
    state: dict[str, Any],
) -> str:
    """debate_check 노드 이후 라우팅.

    debate_check_node에서 결정한 debate_decision에 따라 분기한다.
    """
    decision = state.get("debate_decision", "skip")
    if decision == "trigger":
        logger.info("edge.decision", edge="route_after_debate_check", result="debate")
        return "debate"
    logger.info("edge.decision", edge="route_after_debate_check", result="commander_judgment")
    return "commander_judgment"


def should_skip_reports(
    state: dict[str, Any],
) -> str:
    """리포트 생성 여부 결정."""
    if state.get("has_critical_failure"):
        logger.info("edge.decision", edge="should_skip_reports", result="report_assembly", reason="critical_failure")
        return "report_assembly"  # 에러여도 최소한의 리포트 생성

    logger.info("edge.decision", edge="should_skip_reports", result="report_generation")
    return "report_generation"
