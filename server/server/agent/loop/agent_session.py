"""Agentic observe→think→act loop (native AsyncAnthropic tool-use).

Drives the manual tool-use loop for SIMPLE/DEEP tiers, pushing the 9-event SSE
stream via `emit`. Reuses the PAE tool registry / execute_tool (timeout+retry),
the P1 envelope layer (units anchor + card_data), the respond-node sanitizers,
and the numeric-sanity guard. Tool results are surfaced to the LLM via
envelope.llm_view() (daily_avg→quarter_total_pop relabel; never the raw dict).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from server.agent.nodes.actor import execute_tool
from server.agent.nodes.respond import (
    RESPOND_SYSTEM_PROMPT,
    _ToolTagSanitizer,
    _XMLTagSanitizer,
)
from server.agent.tools.adapt import to_envelope
from server.agent.tools.definitions import build_tool_definitions
from server.agent.tools.registry import get_tool_registry
from server.agent.utils.abstention import ATTRIBUTION_PROMPT_RULE
from server.agent.utils.formatting import _format_history
from server.config import settings
from server.services.circuit_breaker import CircuitOpenError
from server.services.langfuse_tracer import attach_generation_usage

from . import guards
from . import sse_emitter as sse
from .llm_client import get_circuit_breaker, get_provider
from .suggestions import build_suggestions

logger = logging.getLogger(__name__)

_AGENTIC_TOOL_ADDENDUM = "\n".join(
    [
        "## 도구 사용 (에이전트 모드)",
        "- 데이터가 필요하면 반드시 제공된 도구를 호출하세요. 추측하지 말고 도구를 사용하세요.",
        (
            "- 각 도구 결과의 `units` 필드는 수치의 단위와 집계 의미(예: 분기 합계, 월 환산)를 명시합니다. "
            "반드시 그 의미대로 인용하고 임의로 나누거나 변형하지 마세요."
        ),
        "- 비교 질문이면 각 상권에 대해 필요한 도구를 호출해 실제 수치로 비교하세요.",
        "- 충분한 데이터를 모았으면 도구 호출을 멈추고 한국어로 최종 분석을 작성하세요.",
    ]
)

# Frozen system prompt → stable prefix for prompt caching (cache_control breakpoint).
_STABLE_SYSTEM = "\n\n".join([RESPOND_SYSTEM_PROMPT, ATTRIBUTION_PROMPT_RULE, _AGENTIC_TOOL_ADDENDUM])

_CB_OPEN_TEXT = "일시적으로 분석이 어렵습니다. 잠시 후 다시 시도해주세요."

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]


async def run_loop(
    *,
    message: str,
    district_code: str,
    district_name: str,
    data_quarter: str,
    conversation_history: list[dict] | None,
    route,
    emit: EmitFn,
    trace_id: str | None,
) -> dict[str, Any]:
    """Run the tool-use loop, emitting SSE events. Returns the run aggregate."""
    tier = route.tier
    model = settings.agentic_deep_model if tier == "DEEP" else settings.agentic_gate_model
    effort = settings.agentic_deep_effort if tier == "DEEP" else settings.agentic_simple_effort
    budget = settings.agentic_tool_budget_deep if tier == "DEEP" else settings.agentic_tool_budget_simple
    max_tokens = 16000 if tier == "DEEP" else 8000

    provider = get_provider()
    cb = get_circuit_breaker()
    reg = get_tool_registry()
    tool_defs = build_tool_definitions()
    system = [{"type": "text", "text": _STABLE_SYSTEM, "cache_control": {"type": "ephemeral"}}]

    parts: list[str] = []
    if conversation_history:
        parts.append("## 이전 대화\n" + _format_history(conversation_history))
    parts.append(
        f"## 현재 컨텍스트\n- 선택 상권: {district_name or '미선택'} (코드: {district_code or '없음'})\n"
        f"- 데이터 분기: {data_quarter or '최신'}"
    )
    parts.append("## 질문\n" + message)
    messages: list[dict[str, Any]] = [{"role": "user", "content": "\n\n".join(parts)}]

    await emit(sse.thinking("질문 분석 중..."))

    xml_san = _XMLTagSanitizer()
    tool_san = _ToolTagSanitizer()
    collected_text = ""
    tool_results: dict[str, Any] = {}
    tool_errors: dict[str, Any] = {}
    plan_emitted = False
    card_count = 0

    async def _emit_text(raw: str) -> None:
        nonlocal collected_text
        safe_xml = xml_san.feed(raw)
        if not safe_xml:
            return
        safe = tool_san.feed(safe_xml)
        if not safe:
            return
        collected_text += safe
        await emit(sse.text(safe))

    async def _turn(tools_arg: list[dict[str, Any]]):
        """Run one streaming turn. Returns the final message, or None on circuit-open/timeout."""
        try:
            cb.check()
        except CircuitOpenError:
            await _emit_text(_CB_OPEN_TEXT)
            return None
        try:
            async with asyncio.timeout(settings.llm_timeout_slow):
                async with provider.stream(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    tools=tools_arg,
                    messages=messages,
                    effort=effort,
                ) as stream:
                    async for event in stream:
                        if getattr(event, "type", None) == "content_block_delta":
                            delta = getattr(event, "delta", None)
                            if delta is not None and getattr(delta, "type", None) == "text_delta":
                                await _emit_text(delta.text)
                    final = await stream.get_final_message()
            await cb.record_success()
        except TimeoutError:
            await cb.record_failure()
            logger.warning("agentic LLM turn timed out after %ss", settings.llm_timeout_slow)
            await _emit_text("(응답이 지연되어 일부만 표시합니다.)")
            return None
        except Exception as exc:
            # Deterministic client errors (4xx) are not transient — don't trip the breaker.
            status = getattr(exc, "status_code", None)
            if status is None or status >= 500:
                await cb.record_failure()
            logger.exception("agentic LLM turn failed")
            raise

        usage = getattr(final, "usage", None)
        if trace_id and usage is not None:
            try:
                attach_generation_usage(
                    trace_id,
                    model=model,
                    input_tokens=getattr(usage, "input_tokens", 0) or 0,
                    output_tokens=getattr(usage, "output_tokens", 0) or 0,
                )
            except Exception:
                logger.debug("agentic usage attach failed", exc_info=True)
        return final

    final = None
    for _round in range(budget):
        final = await _turn(tool_defs)
        if final is None:
            break  # circuit-open / timeout — notice already emitted

        messages.append({"role": "assistant", "content": final.content})
        tool_uses = [b for b in final.content if getattr(b, "type", None) == "tool_use"]
        if getattr(final, "stop_reason", None) != "tool_use" or not tool_uses:
            break

        if not plan_emitted:
            steps = [(reg.get(b.name).progress_label if reg.get(b.name) else b.name) for b in tool_uses]
            await emit(sse.plan(route.intent, steps))
            plan_emitted = True

        for b in tool_uses:
            meta = reg.get(b.name)
            await emit(sse.tool(b.name, dict(b.input), meta.progress_label if meta else None))

        steps = [{"tool_name": b.name, "args": dict(b.input)} for b in tool_uses]
        results = await asyncio.gather(*[execute_tool(s) for s in steps], return_exceptions=True)

        tool_result_blocks: list[dict[str, Any]] = []
        for b, res in zip(tool_uses, results, strict=True):
            meta = reg.get(b.name)
            if isinstance(res, BaseException):
                env = to_envelope(b.name, {"error": str(res)})
            else:
                _name, raw, err = res
                env = to_envelope(b.name, raw if raw is not None else {"error": err or "도구 실행 실패"})
            await emit(sse.tool_end(b.name, meta.done_label if meta else None))
            if env.error:
                tool_errors[b.name] = env.error
            else:
                tool_results[b.name] = env.data
                if env.card_type and env.card_data is not None:
                    await emit(sse.card(env.card_type, env.card_data))
                    card_count += 1
            tool_result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": json.dumps(env.llm_view(), ensure_ascii=False),
                    "is_error": env.error is not None,
                }
            )
        messages.append({"role": "user", "content": tool_result_blocks})

    # Budget exhausted while still mid-tool-use → force a final no-tools turn so the
    # user always gets a synthesized answer (and chat.py persists the turn).
    if final is not None and getattr(final, "stop_reason", None) == "tool_use":
        await _turn([])

    # Flush sanitizer tails (xml flush piped through tool sanitizer, then tool flush).
    tail = tool_san.feed(xml_san.flush())
    if tail:
        collected_text += tail
        await emit(sse.text(tail))
    tail2 = tool_san.flush()
    if tail2:
        collected_text += tail2
        await emit(sse.text(tail2))

    quality_flags, match_rate, warning = guards.verify_numeric(collected_text, tool_results)
    if warning:
        await emit(warning)

    suggestions = build_suggestions(intent=route.intent, district_name=district_name, tool_results=tool_results)

    return {
        "final_suggestions": suggestions,
        "final_quality_flags": quality_flags,
        "final_quality_match_rate": match_rate,
        "final_intent": route.intent,
        "card_count": card_count,
        "tool_results_count": len(tool_results),
        "tool_errors_count": len(tool_errors),
        "collected_text": collected_text,
    }
