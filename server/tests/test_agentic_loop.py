"""Agentic loop (agent_mode="agentic") — router + offline SSE-parity tests (P2).

Runs fully offline: USE_MOCK forces the mock LLM provider (canned tool_use →
final text), and the global data access is swapped to the mock repos so
execute_tool hits mock fixtures. Asserts the 9-event SSE contract the frontend
(types.ts / eventHandlers.ts) depends on.
"""

from __future__ import annotations

import pytest

from server.agent.loop import router
from server.agent.loop.runner import run_agentic

# --- router (pure, no async) ---------------------------------------------------


def test_router_greeting_is_trivial():
    d = router.classify("안녕하세요", None)
    assert d.tier == "TRIVIAL"
    assert d.response_mode == "greeting_direct"
    assert d.suggestions


def test_router_out_of_scope_is_trivial():
    d = router.classify("부산 해운대 상권 알려줘", None)
    assert d.tier == "TRIVIAL"
    assert d.response_mode == "clarification_direct"
    assert "서울" in d.text


def test_router_comparison_is_deep():
    d = router.classify("강남이랑 홍대 비교해줘", None)
    assert d.tier == "DEEP"
    assert d.intent == "comparison"


def test_router_summary_is_simple():
    d = router.classify("강남역 요약해줘", "D3001")
    assert d.tier == "SIMPLE"
    assert d.intent == "summary"


# --- end-to-end SSE parity (mock provider + mock repos) ------------------------


@pytest.fixture
def _agentic_env():
    """Swap the global DataAccess + CacheService to mocks (tool wrappers use the globals)."""
    import server.repositories as repos
    from server.repositories.mock.factory import build_mock_data_access
    from server.services import cache as cache_mod
    from server.services.cache import MemoryCacheService

    prev_da = repos._data_access
    prev_cache = cache_mod._cache_service
    repos.set_data_access(build_mock_data_access())
    cache_mod.set_cache_service(MemoryCacheService())
    yield
    repos._data_access = prev_da
    cache_mod._cache_service = prev_cache


async def _collect(gen) -> list[dict]:
    return [event async for event in gen]


async def test_agentic_greeting_stream(_agentic_env):
    events = await _collect(run_agentic("안녕하세요", "", "", "2025Q4"))
    types = [e["type"] for e in events]
    assert types[0] == "thinking"  # leading thinking for PAE parity
    text_event = next(e for e in events if e["type"] == "text")
    assert "마켓스코프" in text_event["content"]
    assert "suggestion" in types
    assert "tool" not in types  # greeting is 0-LLM, 0-tool
    assert types[-1] == "done"
    assert sum(t == "done" for t in types) == 1


async def test_agentic_out_of_scope_stream(_agentic_env):
    events = await _collect(run_agentic("부산 해운대 상권 분석해줘", "", "", "2025Q4"))
    types = [e["type"] for e in events]
    text_event = next(e for e in events if e["type"] == "text")
    assert "서울" in text_event["content"]
    assert "tool" not in types  # 0-LLM, 0-tool TRIVIAL path
    assert types[-1] == "done"


async def test_agentic_summary_sse_9_event_parity(_agentic_env):
    events = await _collect(run_agentic("강남역 요약해줘", "D3001", "강남역", "2025Q4"))
    types = [e["type"] for e in events]

    assert types[0] == "thinking"
    for required in ("plan", "tool", "tool_end", "card", "text", "suggestion"):
        assert required in types, f"missing SSE event: {required}"
    assert types[-1] == "done"
    assert sum(t == "done" for t in types) == 1

    # card shape (frozen frontend contract): top-level card_type + data dict
    card = next(e for e in events if e["type"] == "card")
    assert card["card_type"] == "summary"
    assert isinstance(card["data"], dict)

    # plan shape: intent + steps
    plan = next(e for e in events if e["type"] == "plan")
    assert "intent" in plan
    assert isinstance(plan["steps"], list)

    # tool event shape: name + input + progress_label (no icon)
    tool_evt = next(e for e in events if e["type"] == "tool")
    assert set(tool_evt) == {"type", "name", "input", "progress_label"}


async def test_agentic_done_always_present_and_single(_agentic_env):
    events = await _collect(run_agentic("강남역 요약해줘", "D3001", "강남역", "2025Q4"))
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
