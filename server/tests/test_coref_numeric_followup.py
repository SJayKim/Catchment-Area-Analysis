"""Unit tests for the S7 numeric-coref fabrication fix.

Plan: docs/plan/fix/s7-coref-toolless-fabrication.md

Regression: a numeric follow-up after a comparison ("거기 중 유동인구가 더 많은
곳은?") used to fall through to Respond with an empty plan, where the LLM
fabricated numbers from trimmed history text. The fix forces a DB re-fetch
(approach ⓐ) for districts recoverable from recent history.

Mock districts (conftest forces USE_MOCK=true):
    D3001 강남역 / D3002 홍대입구 / D3003 건대입구 / D3004 명동 / D3005 서울역
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

import server.agent.nodes.planner as planner
from server.agent.nodes.planner import _numeric_tools_for, planner_node


@pytest.fixture(autouse=True)
def _mock_data_access():
    """Register the global Mock DataAccess so planner_node's history scan +
    detect_districts_in_message resolve against the 5-district mock fixtures."""
    import server.repositories as repos
    from server.repositories.mock.factory import build_mock_data_access

    prev = repos._data_access
    repos.set_data_access(build_mock_data_access())
    try:
        yield
    finally:
        repos._data_access = prev


# ---------------------------------------------------------------------------
# _numeric_tools_for — pure keyword → tool mapping (checklist ④)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message,expected",
    [
        ("유동인구가 더 많은 곳은?", ["get_floating_population"]),
        ("매출 알려줘", ["get_estimated_sales"]),
        ("점포 수는?", ["get_store_info"]),
        ("창업하기 좋은 곳", ["get_store_info"]),
        ("상주인구 비교", ["get_population_info"]),
        ("직장인구는?", ["get_population_info"]),
        # No numeric keyword → empty (existing behavior preserved)
        ("거기 분위기 어때?", []),
        ("그냥 추천해줘", []),
        # Multi-keyword → de-duplicated, declaration order
        ("유동인구랑 매출 둘 다", ["get_floating_population", "get_estimated_sales"]),
        # "유동인구" must NOT also trigger bare-인구 → population
        ("유동인구만", ["get_floating_population"]),
    ],
)
def test_numeric_tools_for(message: str, expected: list[str]) -> None:
    assert _numeric_tools_for(message) == expected


# ---------------------------------------------------------------------------
# _scan_history_districts — recover elided districts from recent turns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_history_recovers_districts() -> None:
    history = [
        {"role": "user", "content": "홍대입구 요약"},
        {"role": "assistant", "content": "홍대입구는 ..."},
        {"role": "user", "content": "건대입구는 어때?"},
    ]
    codes = await planner._scan_history_districts(history, [])
    assert set(codes) == {"D3002", "D3003"}


@pytest.mark.asyncio
async def test_scan_history_keeps_seed_and_caps_at_3() -> None:
    history = [
        {"role": "user", "content": "홍대입구 요약"},
        {"role": "user", "content": "건대입구 매출"},
        {"role": "user", "content": "명동 점포"},
        {"role": "user", "content": "서울역 유동인구"},
    ]
    codes = await planner._scan_history_districts(history, ["D3001"])
    assert codes[0] == "D3001"  # seed preserved first
    assert len(codes) == 3  # CompareCard cap
    assert len(set(codes)) == 3  # no duplicates
    assert all(c.startswith("D300") for c in codes)


@pytest.mark.asyncio
async def test_scan_history_empty_returns_seed() -> None:
    assert await planner._scan_history_districts([], []) == []


# ---------------------------------------------------------------------------
# planner_node integration — force-plan branch
# ---------------------------------------------------------------------------


def _make_state(message: str, **overrides: object) -> dict:
    base: dict = {
        "messages": [HumanMessage(content=message)],
        "session_id": "test-coref-numeric",
        "district_code": "",
        "district_name": "",
        "conversation_history": [],
        "execution_round": 0,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_numeric_coref_forces_tool_replan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Checklist ①: numeric coref + 2 history districts → forced floating plan.

    Pin the rule classifier to summary so the test isolates the new force
    branch from intents.yaml classification (covered elsewhere).
    """
    monkeypatch.setattr(planner, "_classify_by_rules", lambda _m: ("summary", 0.95))
    out = await planner_node(
        _make_state(
            "유동인구가 더 많은 곳은 어디야?",
            conversation_history=[
                {"role": "user", "content": "홍대입구 vs 건대입구 비교해줘"},
            ],
        )
    )
    assert out["response_mode"] == "tool_assisted"
    tool_names = [step["tool_name"] for step in out["plan"]]
    assert tool_names, "expected forced plan, got empty"
    assert all(t == "get_floating_population" for t in tool_names)
    assert set(out["referenced_districts"]) == {"D3002", "D3003"}
    # one floating-population call per recovered district
    assert len(out["plan"]) == 2
    assert out["user_intent"] != "clarification"


@pytest.mark.asyncio
async def test_non_numeric_coref_keeps_existing_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checklist ②: no numeric keyword → no forced plan (clarification path)."""
    monkeypatch.setattr(planner, "_classify_by_rules", lambda _m: ("summary", 0.95))
    out = await planner_node(
        _make_state(
            "거기 어때?",
            conversation_history=[
                {"role": "user", "content": "홍대입구 vs 건대입구 비교해줘"},
            ],
        )
    )
    # Falls to clarification — the force branch must NOT fabricate a plan.
    assert out["user_intent"] == "clarification"
    assert out["plan"] == []


@pytest.mark.asyncio
async def test_numeric_coref_without_anchor_clarifies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checklist ③: numeric keyword but no recoverable district → clarification."""
    monkeypatch.setattr(planner, "_classify_by_rules", lambda _m: ("summary", 0.95))
    out = await planner_node(_make_state("유동인구가 더 많은 곳은 어디야?"))
    assert out["user_intent"] == "clarification"
    assert out["plan"] == []
