"""Unit tests for out-of-scope (서울 외 지역) handling.

Plan: docs/plan/fix/out-of-scope-handling-2026-04-29.md

3중 가드 검증:
1. intents.yaml::out_of_scope 패턴
2. planner_node 의 short-circuit clarification
3. entity_matching::STRONG_TOP1_MIN 상수 존재
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from server.agent.config.intent_loader import load_intent_config
from server.agent.nodes.planner import _CLARIFICATION_TEMPLATES, planner_node
from server.agent.utils.entity_matching import STRONG_TOP1_MIN, TOP1_MIN

# ---------------------------------------------------------------------------
# Layer 1 — intents.yaml pattern
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message,should_match",
    [
        # Out-of-scope: metropolitan names
        ("부산 해운대 상권 알려줘", True),
        ("제주도 분석해줘", True),
        ("경기도 분당 신도시 분석", True),
        ("대구 동성로 vs 강남 비교", True),
        ("인천 송도 추천", True),
        ("광주광역시 매출 어때?", True),
        ("서귀포 카페 추천", True),
        ("수원 영통 분석", True),
        # In-scope: Seoul districts
        ("강남역 요약", False),
        ("홍대 vs 성수 비교", False),
        ("명동 창업 추천", False),
        # Substring traps — must NOT match
        ("부산물 시장 분석", False),  # "부산" in "부산물" — lookahead guards
        ("광주리 만드는 곳", False),  # "광주" in "광주리"
        ("경기침체 영향", False),  # "경기" in "경기침체"
        ("구로구 분석", False),  # 서울 구로구 — must not match
    ],
)
def test_out_of_scope_pattern_coverage(message: str, should_match: bool) -> None:
    """Pattern matches obvious metro/city names but avoids common substring traps."""
    config = load_intent_config()
    pattern = config.patterns.get("out_of_scope")
    assert pattern is not None, "out_of_scope intent not loaded from intents.yaml"
    actual = bool(pattern.search(message))
    assert actual == should_match, f"pattern.search({message!r}) → {actual}, expected {should_match}"


# ---------------------------------------------------------------------------
# Layer 2 — planner_node short-circuit
# ---------------------------------------------------------------------------


def _make_state(message: str, **overrides: object) -> dict:
    base: dict = {
        "messages": [HumanMessage(content=message)],
        "session_id": "test-out-of-scope",
        "district_code": "",
        "district_name": "",
        "conversation_history": [],
        "execution_round": 0,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_metropolitan_query_returns_clarification() -> None:
    """'부산 해운대 알려줘' → out_of_scope clarification (LLM/Tool 0건)."""
    out = await planner_node(_make_state("부산 해운대 알려줘"))
    assert out["user_intent"] == "clarification"
    assert out["response_mode"] == "clarification_direct"
    assert out["plan"] == []
    assert "clarification_text" in out
    assert "서울" in out["clarification_text"]
    assert "1,650" in out["clarification_text"]
    assert isinstance(out["clarification_suggestions"], list)
    assert len(out["clarification_suggestions"]) >= 2


@pytest.mark.asyncio
async def test_mixed_query_routes_to_out_of_scope() -> None:
    """'제주 vs 강남 비교' → out_of_scope wins over comparison."""
    out = await planner_node(_make_state("제주 vs 강남 비교"))
    assert out["user_intent"] == "clarification"
    assert out["response_mode"] == "clarification_direct"
    # Out-of-scope short-circuit must drop comparison plan entirely.
    assert out["plan"] == []
    assert out["plan_reasoning"].startswith("clarification: out_of_scope")


@pytest.mark.asyncio
async def test_city_level_query_routes_to_out_of_scope() -> None:
    """'분당 신도시 분석' → out_of_scope (경기 city)."""
    out = await planner_node(_make_state("분당 신도시 분석"))
    assert out["user_intent"] == "clarification"
    assert out["plan"] == []
    assert "서울" in out["clarification_text"]


@pytest.mark.asyncio
async def test_seoul_query_does_not_clarify_as_oos() -> None:
    """Sanity: a Seoul-only query MUST NOT route to out_of_scope."""
    out = await planner_node(_make_state("강남역 요약", district_code="3120010", district_name="강남역"))
    # Either summary or another non-clarification intent — but never out_of_scope
    if out.get("user_intent") == "clarification":
        # If it does clarify, it must be for a non-OOS reason (e.g. coref)
        assert "out_of_scope" not in out.get("plan_reasoning", "")


# ---------------------------------------------------------------------------
# Layer 3 — entity_matching threshold constant
# ---------------------------------------------------------------------------


def test_strong_top1_min_above_top1_min() -> None:
    """STRONG_TOP1_MIN must be strictly higher than TOP1_MIN to add value."""
    assert STRONG_TOP1_MIN > TOP1_MIN
    # Sanity: empirical floor — too high causes false negatives on legitimate queries
    assert 0.65 <= STRONG_TOP1_MIN <= 0.80


def test_clarification_template_has_out_of_scope_key() -> None:
    """`out_of_scope` template must exist with text + suggestions."""
    tmpl = _CLARIFICATION_TEMPLATES.get("out_of_scope")
    assert tmpl is not None
    assert "서울" in tmpl["text"]
    assert "1,650" in tmpl["text"]
    assert isinstance(tmpl["suggestions"], list)
    assert len(tmpl["suggestions"]) >= 2
