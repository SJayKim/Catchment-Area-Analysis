"""v2 loop 후보 체인 — 선호-우선 파티션 + 키 게이트 + _build openai 계약.

Plan: docs/plan/infra/llm-gateway-openai-2026-07-08.md (R0-LLMGW-CHAIN-*, BUILD-OPENAI).
순수함수라 fake LLM 불요 — settings 를 monkeypatch 하고 체인 순서를 단언한다.
graph.py 와 달리 loop.models 는 settings 를 런타임 참조하므로 settings 패치로 충분.
"""

from __future__ import annotations

import logging

import pytest
from langchain_core.messages import HumanMessage

from server.agent.loop import models
from server.agent.loop.models import (
    ModelCandidate,
    _build,
    _candidate_chain,
    chain_summary,
)
from server.config import settings


@pytest.fixture(autouse=True)
def _reset_warning_flag():
    """per-process 경고 플래그가 테스트 간 누수하지 않도록 리셋."""
    models._chain_warning_logged = False
    yield
    models._chain_warning_logged = False


def _set(monkeypatch, *, anthropic="", openai="", google="", provider):
    monkeypatch.setattr(settings, "anthropic_api_key", anthropic)
    monkeypatch.setattr(settings, "openai_api_key", openai)
    monkeypatch.setattr(settings, "google_api_key", google)
    monkeypatch.setattr(settings, "llm_provider", provider)
    monkeypatch.setattr(settings, "anthropic_model", "claude-x")
    monkeypatch.setattr(settings, "openai_model", "gpt-x")
    monkeypatch.setattr(settings, "gemini_model_pro", "gem-pro")
    monkeypatch.setattr(settings, "gemini_model_flash", "gem-flash")


def _labels(chain):
    return [f"{c.provider}:{c.model_id}" for c in chain]


def test_all_keys_provider_anthropic(monkeypatch):
    _set(monkeypatch, anthropic="a", openai="o", google="g", provider="anthropic")
    assert _labels(_candidate_chain()) == [
        "anthropic:claude-x",
        "openai:gpt-x",
        "gemini:gem-pro",
        "gemini:gem-flash",
    ]


def test_all_keys_provider_openai(monkeypatch):
    _set(monkeypatch, anthropic="a", openai="o", google="g", provider="openai")
    assert _labels(_candidate_chain()) == [
        "openai:gpt-x",
        "anthropic:claude-x",
        "gemini:gem-pro",
        "gemini:gem-flash",
    ]


def test_all_keys_provider_gemini_moves_block(monkeypatch):
    _set(monkeypatch, anthropic="a", openai="o", google="g", provider="gemini")
    # gemini 블록 통째 선두 이동 + pro→flash 내부 순서 유지
    assert _labels(_candidate_chain()) == [
        "gemini:gem-pro",
        "gemini:gem-flash",
        "anthropic:claude-x",
        "openai:gpt-x",
    ]


def test_preferred_key_absent_warns_once(monkeypatch, caplog):
    _set(monkeypatch, anthropic="a", openai="", google="g", provider="openai")
    with caplog.at_level(logging.WARNING, logger="server.agent.loop.models"):
        first = _candidate_chain()
        second = _candidate_chain()
    # openai 키 부재 → 기본 체인(openai 없음), 순서 무변경
    assert _labels(first) == ["anthropic:claude-x", "gemini:gem-pro", "gemini:gem-flash"]
    assert _labels(second) == _labels(first)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1  # per-process 1회
    assert "openai" in warnings[0].getMessage().lower()


def test_unknown_provider_warns_unknown(monkeypatch, caplog):
    _set(monkeypatch, anthropic="a", openai="o", google="g", provider="bogus")
    with caplog.at_level(logging.WARNING, logger="server.agent.loop.models"):
        chain = _candidate_chain()
    # 오타 → 기본 체인 전체 (파티션 없음)
    assert _labels(chain) == [
        "anthropic:claude-x",
        "openai:gpt-x",
        "gemini:gem-pro",
        "gemini:gem-flash",
    ]
    assert "not a known provider" in caplog.records[-1].getMessage().lower()


def test_google_key_only(monkeypatch):
    _set(monkeypatch, anthropic="", openai="", google="g", provider="gemini")
    assert _labels(_candidate_chain()) == ["gemini:gem-pro", "gemini:gem-flash"]


async def test_empty_chain_error_mentions_openai(monkeypatch):
    from server.services.circuit_breaker import CircuitBreaker

    # 세션 공유 breaker 오염 회피 — 갓 만든 CLOSED breaker 주입
    monkeypatch.setattr(
        models,
        "_loop_circuit_breaker",
        CircuitBreaker(failure_threshold=5, recovery_timeout=60.0, name="t"),
    )
    _set(monkeypatch, anthropic="", openai="", google="", provider="anthropic")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await models.ainvoke_with_fallback([HumanMessage(content="hi")], None)


def test_build_openai_contract(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "o")
    llm = _build(ModelCandidate("openai", "gpt-x"))
    assert type(llm).__name__ == "ChatOpenAI"
    assert llm.model_name == "gpt-x"
    assert llm.max_tokens == 4096
    # GPT-5.x 추론형 — temperature 미전달 (400 회피)
    assert "temperature" not in llm.model_fields_set


def test_chain_summary_labels(monkeypatch):
    _set(monkeypatch, anthropic="a", openai="o", google="", provider="anthropic")
    assert chain_summary() == ["anthropic:claude-x", "openai:gpt-x"]
