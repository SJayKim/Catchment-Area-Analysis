"""LLM factory for the v2 loop — provider fallback chain, no hardcoded IDs.

Two structural fixes over graph.py:
  1. Model IDs come from settings (env-overridable), so a retired model ID
     can be hotfixed without a code deploy (the 2026-06 "dead model" class).
  2. A per-invoke fallback chain: if the primary provider 404s / auth-fails /
     times out, the next candidate is tried instead of failing the request.

The circuit breaker is module-level here (same as graph.py). Per-request DI
is a noted follow-up in the design doc, not this slice.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessageChunk, message_chunk_to_message

from server.config import settings
from server.services.circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)

_loop_circuit_breaker = CircuitBreaker(
    failure_threshold=settings.circuit_breaker_failure_threshold,
    recovery_timeout=settings.circuit_breaker_recovery_timeout,
    name="loop_llm",
)


@dataclass
class ModelCandidate:
    provider: str  # "anthropic" | "openai" | "gemini"
    model_id: str


_KNOWN_PROVIDERS = ("anthropic", "openai", "gemini")
# Per-process guard so a misconfigured LLM_PROVIDER logs once, not once per
# invoke (this chain is rebuilt every model turn). Steady-state visibility is
# the health `llm_chain` field's job, not a per-request log line.
_chain_warning_logged = False


def _candidate_chain() -> list[ModelCandidate]:
    """Preferred-first fallback chain for the loop's tool-calling model.

    Base order (key-gated): anthropic → openai → gemini pro → gemini flash.
    Then ``settings.llm_provider`` candidates are stable-partitioned to the
    front, so setting ``LLM_PROVIDER=openai`` promotes GPT to primary without a
    new env var. All IDs from settings → env-overridable (dead-model hotfix).
    """
    global _chain_warning_logged
    chain: list[ModelCandidate] = []
    if settings.anthropic_api_key:
        chain.append(ModelCandidate("anthropic", settings.anthropic_model))
    if settings.openai_api_key:
        chain.append(ModelCandidate("openai", settings.openai_model))
    if settings.google_api_key:
        chain.append(ModelCandidate("gemini", settings.gemini_model_pro))
        chain.append(ModelCandidate("gemini", settings.gemini_model_flash))

    preferred = settings.llm_provider
    front = [c for c in chain if c.provider == preferred]
    if front:
        return front + [c for c in chain if c.provider != preferred]
    # No candidate matched the preferred provider — the key is absent or the
    # value is a typo. Serve the base chain and warn once per process.
    if preferred != "mock" and not _chain_warning_logged:
        _chain_warning_logged = True
        if preferred in _KNOWN_PROVIDERS:
            logger.warning(
                "LLM_PROVIDER=%s but no %s API key is set — using fallback chain %s",
                preferred,
                preferred,
                [f"{c.provider}:{c.model_id}" for c in chain],
            )
        else:
            logger.warning(
                "LLM_PROVIDER=%s is not a known provider %s — using fallback chain %s",
                preferred,
                _KNOWN_PROVIDERS,
                [f"{c.provider}:{c.model_id}" for c in chain],
            )
    return chain


def chain_summary() -> list[str]:
    """``["provider:model_id", ...]`` labels for the current fallback chain.

    Exposed on ``/api/health/detail`` so a deploy can confirm the container
    resolved the expected keys/order in one curl.
    """
    return [f"{c.provider}:{c.model_id}" for c in _candidate_chain()]


def _build(candidate: ModelCandidate):
    if candidate.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=candidate.model_id,
            api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
            max_tokens=4096,
            temperature=0.3,
        )
    if candidate.provider == "openai":
        from langchain_openai import ChatOpenAI

        # No temperature: GPT-5.x reasoning models reject a non-default value
        # (400 error). langchain-openai maps max_tokens → max_completion_tokens.
        return ChatOpenAI(
            model=candidate.model_id,
            api_key=settings.openai_api_key,  # type: ignore[arg-type]
            max_tokens=4096,
        )
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=candidate.model_id,
        google_api_key=settings.google_api_key,  # type: ignore[arg-type]
        temperature=0.3,
        max_output_tokens=4096,
    )


async def ainvoke_with_fallback(
    messages: list,
    tools: list[dict] | None,
    *,
    callbacks: list | None = None,
    timeout: float | None = None,
    metadata: dict | None = None,
    tags: list[str] | None = None,
    run_name: str | None = None,
) -> Any:
    """Invoke the first working model in the fallback chain.

    Binds ``tools`` (OpenAI-function-shaped dicts) when provided so the model
    can emit tool_calls. Raises CircuitOpenError when the breaker is open;
    raises the last provider error if every candidate fails.

    ``metadata``/``tags``/``run_name`` land in the LangChain RunnableConfig
    (client-side only — Langfuse trace enrichment, request body unchanged).
    """
    _loop_circuit_breaker.check()

    chain = _candidate_chain()
    if not chain:
        raise RuntimeError(
            "No LLM provider configured for the v2 loop — set ANTHROPIC_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY"
        )

    config: dict[str, Any] = {}
    if callbacks:
        config["callbacks"] = callbacks
    if metadata:
        config["metadata"] = metadata
    if tags:
        config["tags"] = tags
    if run_name:
        config["run_name"] = run_name

    last_exc: Exception | None = None
    for candidate in chain:
        try:
            llm = _build(candidate)
            bound = llm.bind_tools(tools) if tools else llm
            coro = bound.ainvoke(messages, config=config or None)
            result = await (asyncio.wait_for(coro, timeout) if timeout else coro)
            await _loop_circuit_breaker.record_success()
            return result
        except CircuitOpenError:
            raise
        except Exception as exc:  # noqa: BLE001 — try next provider
            last_exc = exc
            logger.warning(
                "loop model candidate failed (%s/%s): %s — trying next",
                candidate.provider,
                candidate.model_id,
                exc,
            )
            continue

    await _loop_circuit_breaker.record_failure()
    assert last_exc is not None
    raise last_exc


def _chunk_text(chunk: Any) -> str:
    """Extract plain text from an AIMessageChunk (str or content-block list)."""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") in (None, "text", "text_delta"):
                    parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


async def astream_with_fallback(
    messages: list,
    tools: list[dict] | None,
    *,
    callbacks: list | None = None,
    timeout: float | None = None,
    metadata: dict | None = None,
    tags: list[str] | None = None,
    run_name: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream the first working model in the fallback chain, buffering chunks.

    Same fallback/breaker semantics as ``ainvoke_with_fallback`` — a candidate
    that fails BEFORE OR MID-STREAM is dropped (its buffer discarded, never
    shown) and the next one restarts from scratch. Yields:

      {"kind": "delta", "chars": <cumulative text length>, "tool_call": <bool>}
      {"kind": "final", "message": <AIMessage>}   # exactly once, then returns

    Raises CircuitOpenError when the breaker is open; raises the last provider
    error if every candidate fails. CancelledError (client abort) propagates
    without touching the breaker.

    ``metadata``/``tags``/``run_name`` land in the LangChain RunnableConfig
    (client-side only — Langfuse trace enrichment, request body unchanged).
    """
    _loop_circuit_breaker.check()

    chain = _candidate_chain()
    if not chain:
        raise RuntimeError(
            "No LLM provider configured for the v2 loop — set ANTHROPIC_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY"
        )

    config: dict[str, Any] = {}
    if callbacks:
        config["callbacks"] = callbacks
    if metadata:
        config["metadata"] = metadata
    if tags:
        config["tags"] = tags
    if run_name:
        config["run_name"] = run_name

    last_exc: Exception | None = None
    for candidate in chain:
        acc: AIMessageChunk | None = None
        chars = 0
        saw_tool_call = False
        try:
            llm = _build(candidate)
            bound = llm.bind_tools(tools) if tools else llm
            # asyncio.wait_for can't wrap an async iteration — bound the whole
            # stream with asyncio.timeout instead (respond.py pattern).
            async with asyncio.timeout(timeout):
                async for chunk in bound.astream(messages, config=config or None):
                    acc = chunk if acc is None else acc + chunk
                    chars += len(_chunk_text(chunk))
                    saw_tool_call = saw_tool_call or bool(getattr(chunk, "tool_call_chunks", None))
                    yield {"kind": "delta", "chars": chars, "tool_call": saw_tool_call}
            if acc is None:
                raise RuntimeError(f"empty stream from {candidate.provider}/{candidate.model_id}")
            await _loop_circuit_breaker.record_success()
            # Normalize the accumulated chunk (tool_call_chunks → tool_calls)
            # so downstream message history serializes like an ainvoke result.
            yield {"kind": "final", "message": message_chunk_to_message(acc)}
            return
        except CircuitOpenError:
            raise
        except Exception as exc:  # noqa: BLE001 — try next provider (buffer discarded)
            last_exc = exc
            logger.warning(
                "loop stream candidate failed (%s/%s, %d chars buffered): %s — trying next",
                candidate.provider,
                candidate.model_id,
                chars,
                exc,
            )
            continue

    await _loop_circuit_breaker.record_failure()
    assert last_exc is not None
    raise last_exc
