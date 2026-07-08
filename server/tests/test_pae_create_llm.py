"""PAE _create_llm — openai all-roles 분기 + de-hardcode 회귀 + mock 불변식.

Plan: docs/plan/infra/llm-gateway-openai-2026-07-08.md (R0-LLMGW-PAE-ROLES, MOCK-INV).

⚠ graph.py 는 ``LLM_PROVIDER = settings.llm_provider`` 를 :21 에서 **모듈 스냅샷**한다.
settings.llm_provider 만 패치하면 무효 — ``graph.LLM_PROVIDER`` 를 직접 패치해야 한다.
"""

from __future__ import annotations

from server.agent import graph
from server.config import settings


def test_openai_all_roles(monkeypatch):
    """provider=openai + 키 → planner/evaluator/respond/default 전부 ChatOpenAI."""
    monkeypatch.setattr(graph, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "o")
    monkeypatch.setattr(settings, "openai_model", "gpt-pae")
    for role in ("planner", "evaluator", "respond", "default"):
        llm = graph._create_llm(role)
        assert type(llm).__name__ == "ChatOpenAI", role
        assert llm.model_name == "gpt-pae", role


def test_openai_empty_key_falls_through(monkeypatch):
    """provider=openai + 키 "" → 크래시 없이 anthropic 분기로 폴스루 (우아한 강등)."""
    monkeypatch.setattr(graph, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "a")
    monkeypatch.setattr(graph, "_anthropic_valid", True)
    planner = graph._create_llm("planner")  # planner-anthropic 선호 분기
    respond = graph._create_llm("respond")  # else(anthropic) 분기
    assert type(planner).__name__ == "ChatAnthropic"
    assert type(respond).__name__ == "ChatAnthropic"


def test_dehardcode_regression(monkeypatch):
    """anthropic_model env 가 planner(:74)·else(:96) 두 분기 모두에 반영."""
    monkeypatch.setattr(graph, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "a")
    monkeypatch.setattr(settings, "anthropic_model", "test-x")
    monkeypatch.setattr(graph, "_anthropic_valid", True)
    planner = graph._create_llm("planner")  # :74 planner 분기
    respond = graph._create_llm("respond")  # :96 else 분기
    assert planner.model == "test-x"
    assert respond.model == "test-x"


def test_mock_invariant(monkeypatch):
    """provider=mock → FakeListChatModel (openai 분기가 mock 을 가로채지 않음)."""
    monkeypatch.setattr(graph, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(settings, "openai_api_key", "o")  # 키 있어도 mock 우선
    llm = graph._create_llm("planner")
    assert type(llm).__name__ == "FakeListChatModel"
