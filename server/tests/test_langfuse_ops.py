"""langfuse_tracer ops-hardening helpers — tool span / summary name / 샘플링 단일 게이트 / status.

Plan: docs/plan/infra/langfuse-ops-hardening-2026-07-06.md (Workstream A2 + C).

기존 test_langfuse_aggregate.py 스타일 답습 — client 는 patch.object(tr, ...) 로
주입, 전 경로 graceful degrade (예외가 SSE 응답 경로로 새지 않음).
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

from server.config import settings
from server.services import langfuse_tracer as tr


def test_attach_tool_span_calls_start_observation():
    fake_span = MagicMock()
    fake_client = MagicMock()
    fake_client.start_observation.return_value = fake_span

    with patch.object(tr, "_get_client", return_value=fake_client):
        with patch.object(tr, "_tracer_valid", True):
            tr.attach_tool_span(
                "trace-abc",
                name="get_district_summary",
                args={"district_code": "D3001"},
                duration_ms=12.5,
                error=None,
            )

    assert fake_client.start_observation.called
    kwargs = fake_client.start_observation.call_args.kwargs
    assert kwargs["name"] == "get_district_summary"
    assert kwargs["as_type"] == "tool"
    assert kwargs["input"] == {"district_code": "D3001"}
    # None 값(error)은 metadata 에서 제거
    assert kwargs["metadata"] == {"duration_ms": 12.5}
    fake_span.end.assert_called_once()


def test_attach_tool_span_skips_without_trace_id_or_client():
    fake_client = MagicMock()
    # trace_id 없음 → client 접근 전 no-op
    tr.attach_tool_span(None, name="get_store_info")
    tr.attach_tool_span("", name="get_store_info")
    # client None → silent skip
    with patch.object(tr, "_get_client", return_value=None):
        tr.attach_tool_span("trace-1", name="get_store_info")
    fake_client.start_observation.assert_not_called()


def test_attach_tool_span_swallows_exceptions():
    fake_client = MagicMock()
    fake_client.start_observation.side_effect = RuntimeError("boom")
    with patch.object(tr, "_get_client", return_value=fake_client):
        with patch.object(tr, "_tracer_valid", True):
            # 예외가 밖으로 새면 SSE 응답 경로가 죽는다 — raise 금지
            tr.attach_tool_span("trace-x", name="compute", error="tool failed")


def test_attach_summary_observation_custom_name():
    """v2 는 name="marketscope.v2.summary" 로 호출 (default 는 PAE 계약 유지)."""
    fake_span = MagicMock()
    fake_client = MagicMock()
    fake_client.start_observation.return_value = fake_span

    with patch.object(tr, "_get_client", return_value=fake_client):
        with patch.object(tr, "_tracer_valid", True):
            tr.attach_summary_observation(
                "trace-v2",
                metadata={"tool_calls_made": 2},
                name="marketscope.v2.summary",
            )

    kwargs = fake_client.start_observation.call_args.kwargs
    assert kwargs["name"] == "marketscope.v2.summary"
    assert kwargs["as_type"] == "agent"


def test_client_init_has_no_sample_rate(monkeypatch):
    """샘플링은 should_sample() 단일 게이트 — SDK sample_rate 이중 적용 금지."""
    captured: dict = {}

    class FakeLangfuse:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_mod = types.ModuleType("langfuse")
    fake_mod.Langfuse = FakeLangfuse  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langfuse", fake_mod)
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-test")
    monkeypatch.setattr(tr, "_client", None)
    monkeypatch.setattr(tr, "_tracer_valid", True)

    client = tr._get_client()

    assert client is not None
    assert "sample_rate" not in captured
    assert captured.keys() == {"public_key", "secret_key", "host"}


def test_should_sample_boundaries(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_sampling_rate", 1.0)
    assert tr.should_sample() is True
    monkeypatch.setattr(settings, "langfuse_sampling_rate", 0.0)
    assert tr.should_sample() is False


def test_status_reports_four_keys():
    s = tr.status()
    assert set(s.keys()) == {"enabled", "tracer_valid", "client_initialized", "sampling_rate"}
    # 테스트 env 는 keys="" → disabled
    assert s["enabled"] is False
    assert isinstance(s["tracer_valid"], bool)
    assert isinstance(s["sampling_rate"], float)
