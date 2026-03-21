"""조건부 엣지 로직."""

from __future__ import annotations

from typing import Any, Literal


def should_continue_after_commander(
    state: dict[str, Any],
) -> str:
    """Commander 계획 후 다음 단계 결정."""
    plan = state.get("commander_plan")
    if not plan:
        return "end"

    if plan.get("clarification_needed"):
        return "end"  # 명확화 필요 → 사용자에게 반환

    return "parallel_group_1"


def should_run_group2(
    state: dict[str, Any],
) -> str:
    """Group 1 완료 후 Group 2 실행 여부 결정."""
    plan = state.get("commander_plan", {})
    mode = plan.get("analysis_mode", "basic")

    if mode == "quick":
        # quick 모드: Group 1만 실행 후 바로 judgment
        return "commander_judgment"

    return "parallel_group_2"


def is_comparison_mode(state: dict[str, Any]) -> str:
    """비교 분석 모드 여부를 판별한다."""
    plan = state.get("commander_plan", {})
    if plan.get("analysis_mode") == "comparison" and plan.get("target_location_secondary"):
        return "comparison"
    return "single"


def should_skip_reports(
    state: dict[str, Any],
) -> str:
    """리포트 생성 여부 결정."""
    if state.get("has_critical_failure"):
        return "report_assembly"  # 에러여도 최소한의 리포트 생성

    return "report_generation"
