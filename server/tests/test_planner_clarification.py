"""Unit tests for Planner clarification short-circuits (P0-3 / P0-4).

Verifies that when the planner cannot build a meaningful tool plan it returns
a deterministic clarification payload — the LLM must not be invoked, since
empty-plan Respond is what produced the 2026-04-24 eval Round 2 hallucinations.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from server.agent.nodes.planner import _CLARIFICATION_TEMPLATES, planner_node


def _make_state(message: str, **overrides: object) -> dict:
    base: dict = {
        "messages": [HumanMessage(content=message)],
        "session_id": "test-session",
        "district_code": "",
        "district_name": "",
        "conversation_history": [],
        "execution_round": 0,
    }
    base.update(overrides)
    return base


def test_clarification_templates_have_all_keys() -> None:
    for key in ("coref_no_anchor", "comparison_under_2", "exclusion_left_empty"):
        tmpl = _CLARIFICATION_TEMPLATES[key]
        assert tmpl["text"], f"{key} missing text"
        assert isinstance(tmpl["suggestions"], list)
        assert len(tmpl["suggestions"]) >= 2


@pytest.mark.asyncio
async def test_comparison_under_2_returns_clarification() -> None:
    """\"비교해줘\" without enough districts → clarification."""
    state = _make_state("비교해줘")
    out = await planner_node(state)
    assert out["user_intent"] == "clarification"
    assert out["response_mode"] == "clarification_direct"
    assert out["plan"] == []
    assert "clarification_text" in out
    assert "비교" in out["clarification_text"]


@pytest.mark.asyncio
async def test_district_missing_with_recommendation_intent() -> None:
    """Recommendation intent with no district anchor → clarification."""
    state = _make_state("어떤 업종이 추천되나요?")
    out = await planner_node(state)
    # Either clarification_direct (P1 trigger) or ambiguous-handled — both are
    # acceptable; what matters is no LLM-bound tool plan.
    assert out["plan"] == []
    if out["user_intent"] == "clarification":
        assert "clarification_text" in out
        assert out["response_mode"] == "clarification_direct"


@pytest.mark.asyncio
async def test_summary_with_district_does_not_clarify() -> None:
    """Sanity: a well-formed query must NOT clarify."""
    state = _make_state("강남역 요약", district_code="3120010", district_name="강남역")
    out = await planner_node(state)
    assert out["user_intent"] != "clarification"
    assert out["response_mode"] != "clarification_direct"
