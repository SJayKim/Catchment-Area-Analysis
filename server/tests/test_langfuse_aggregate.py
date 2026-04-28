"""Tests for langfuse_tracer aggregate-stats helpers (Plan
langfuse-aggregate-stats-2026-04-28).

Covers:
- district_type_for prefix mapping (4 types + unknown)
- attach_summary_observation graceful degrade (None client / no trace_id / exception)
- emit_score graceful degrade
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from server.services import langfuse_tracer as tr


def test_district_type_for_known_prefixes():
    assert tr.district_type_for("3110023") == "발달상권"
    assert tr.district_type_for("3120189") == "골목상권"
    assert tr.district_type_for("3130001") == "전통시장"
    assert tr.district_type_for("3140001") == "관광특구"


def test_district_type_for_unknown_or_empty():
    assert tr.district_type_for("") == "unknown"
    assert tr.district_type_for(None) == "unknown"
    assert tr.district_type_for("9999999") == "unknown"
    assert tr.district_type_for("D3001") == "unknown"  # mock id


def test_attach_summary_observation_skips_when_no_trace_id():
    # Should not raise, no client interaction
    tr.attach_summary_observation(None, metadata={"foo": "bar"})
    tr.attach_summary_observation("", metadata={"foo": "bar"})


def test_attach_summary_observation_skips_when_client_none():
    with patch.object(tr, "_get_client", return_value=None):
        # Should silently skip
        tr.attach_summary_observation("trace-id-1", metadata={"foo": "bar"})


def test_attach_summary_observation_calls_start_observation():
    fake_span = MagicMock()
    fake_client = MagicMock()
    fake_client.start_observation.return_value = fake_span

    with patch.object(tr, "_get_client", return_value=fake_client):
        with patch.object(tr, "_tracer_valid", True):
            tr.attach_summary_observation(
                "trace-abc",
                metadata={"intent": "summary", "tool_count": 4, "missing": None},
                output={"text_len": 100},
            )

    assert fake_client.start_observation.called
    call_kwargs = fake_client.start_observation.call_args.kwargs
    # None values should be stripped from metadata
    assert "missing" not in call_kwargs["metadata"]
    assert call_kwargs["metadata"]["intent"] == "summary"
    assert call_kwargs["metadata"]["tool_count"] == 4
    assert call_kwargs["name"] == "marketscope.pae.summary"
    assert call_kwargs["as_type"] == "agent"
    # span.end() should be called even after start
    fake_span.end.assert_called_once()


def test_attach_summary_observation_swallows_exceptions():
    fake_client = MagicMock()
    fake_client.start_observation.side_effect = RuntimeError("boom")

    with patch.object(tr, "_get_client", return_value=fake_client):
        with patch.object(tr, "_tracer_valid", True):
            # Should NOT raise
            tr.attach_summary_observation("trace-x", metadata={"x": 1})


def test_emit_score_skips_when_no_trace_id():
    tr.emit_score(None, "numeric_match", 0.9)
    tr.emit_score("", "numeric_match", 0.9)


def test_emit_score_calls_create_score():
    fake_client = MagicMock()
    fake_client.create_score = MagicMock()
    # ensure score fallback is not picked when create_score exists
    delattr_target = getattr(fake_client, "score", None)
    if delattr_target is not None:
        del fake_client.score

    with patch.object(tr, "_get_client", return_value=fake_client):
        with patch.object(tr, "_tracer_valid", True):
            tr.emit_score("trace-Y", "numeric_match", 0.85, comment="ok")

    fake_client.create_score.assert_called_once()
    kwargs = fake_client.create_score.call_args.kwargs
    assert kwargs["trace_id"] == "trace-Y"
    assert kwargs["name"] == "numeric_match"
    assert kwargs["value"] == 0.85
    assert kwargs["comment"] == "ok"


def test_emit_score_swallows_exceptions():
    fake_client = MagicMock()
    fake_client.create_score.side_effect = ConnectionError("offline")

    with patch.object(tr, "_get_client", return_value=fake_client):
        with patch.object(tr, "_tracer_valid", True):
            # Should NOT raise
            tr.emit_score("trace-Z", "abstention_triggered", 1.0)


def test_emit_score_when_tracer_invalidated():
    fake_client = MagicMock()
    with patch.object(tr, "_get_client", return_value=fake_client):
        with patch.object(tr, "_tracer_valid", False):
            tr.emit_score("trace-W", "numeric_match", 0.5)
    fake_client.create_score.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
