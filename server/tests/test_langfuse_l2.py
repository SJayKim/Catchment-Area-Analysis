"""Langfuse L2 — token/cost normalization + prompt_version + graceful degrade.

Plan: docs/plan/infra/langfuse-l2-token-cost-eval.md.

These tests run with Langfuse disabled (no keys → ``_tracer_valid`` evaluates
to "client = None"). They verify that the helpers behave correctly without a
live Langfuse server: input is shaped, output is normalized, and graceful
degrade kicks in for every failure path.
"""

from __future__ import annotations

from server.services.langfuse_tracer import (
    _normalize_usage,
    attach_generation_usage,
    prompt_version,
)

# ---------------------------------------------------------------------------
# _normalize_usage — heterogeneous response shapes
# ---------------------------------------------------------------------------


def test_normalize_langchain_usage_metadata_dict() -> None:
    """LangChain wraps token counts as ``response.usage_metadata`` dict-like."""

    class FakeResp:
        usage_metadata = {"input_tokens": 1024, "output_tokens": 256}

    assert _normalize_usage(FakeResp()) == (1024, 256)


def test_normalize_anthropic_native_usage_attrs() -> None:
    """Anthropic SDK exposes ``response.usage.input_tokens / output_tokens``."""

    class Usage:
        input_tokens = 800
        output_tokens = 200

    class FakeResp:
        usage = Usage()

    assert _normalize_usage(FakeResp()) == (800, 200)


def test_normalize_gemini_prompt_candidates_keys() -> None:
    """Gemini exposes ``prompt_token_count`` / ``candidates_token_count``."""
    payload = {
        "prompt_token_count": 512,
        "candidates_token_count": 128,
    }
    assert _normalize_usage(payload) == (512, 128)


def test_normalize_openai_style_completion_keys() -> None:
    payload = {"prompt_tokens": 100, "completion_tokens": 50}
    assert _normalize_usage(payload) == (100, 50)


def test_normalize_returns_zero_when_no_usage() -> None:
    assert _normalize_usage(None) == (0, 0)
    assert _normalize_usage({}) == (0, 0)
    assert _normalize_usage(object()) == (0, 0)


def test_normalize_handles_partial_data() -> None:
    """Streaming partial — output_tokens=0 must still be preserved."""
    payload = {"input_tokens": 256, "output_tokens": 0}
    assert _normalize_usage(payload) == (256, 0)


# ---------------------------------------------------------------------------
# attach_generation_usage — graceful degrade
# ---------------------------------------------------------------------------


def test_attach_returns_silently_when_trace_id_missing() -> None:
    """No trace_id → no-op (no exception, no log noise)."""
    attach_generation_usage(
        None,
        model="claude-sonnet-4",
        input_tokens=100,
        output_tokens=50,
    )


def test_attach_skips_when_both_token_counts_zero() -> None:
    """0/0 means "no usage to record" — skip silently."""
    attach_generation_usage(
        "trace-xyz",
        model="gemini-2.5-flash",
        input_tokens=0,
        output_tokens=0,
    )


def test_attach_does_not_raise_when_langfuse_disabled() -> None:
    """Disabled (no keys) → silent skip even with valid args."""
    # In the test env, LANGFUSE_PUBLIC_KEY="" so settings.langfuse_enabled is False
    attach_generation_usage(
        "trace-test",
        model="claude-sonnet-4",
        input_tokens=10,
        output_tokens=5,
        prompt_name="planner_intent_classify",
        prompt_version="v1.0.0-abcdef0",
    )


# ---------------------------------------------------------------------------
# prompt_version — git sha helper
# ---------------------------------------------------------------------------


def test_prompt_version_format_is_semver_dash_sha() -> None:
    v = prompt_version("v1.2.3")
    # Format: v1.2.3-<sha7> or v1.2.3-unknown
    parts = v.split("-")
    assert len(parts) == 2
    assert parts[0] == "v1.2.3"
    assert len(parts[1]) >= 6  # sha7 or "unknown"


def test_prompt_version_default_starts_with_v100() -> None:
    assert prompt_version().startswith("v1.0.0-")


def test_prompt_version_distinct_inputs_yield_distinct_outputs() -> None:
    a = prompt_version("v1.0.0")
    b = prompt_version("v1.1.0")
    assert a != b
    assert a.startswith("v1.0.0-")
    assert b.startswith("v1.1.0-")
