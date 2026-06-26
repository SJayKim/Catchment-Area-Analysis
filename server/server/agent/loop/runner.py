"""Agentic SSE runner — mirrors graph.run_agent's queue/sentinel/Langfuse shell.

`run_agentic` has the identical signature + 9-event SSE contract as
graph.run_agent so chat.py drives it unchanged via get_runner("agentic"). The
producer task drives the tool-use loop (or a 0-LLM TRIVIAL reply) and pushes
events to a bounded queue; the consumer yields them with a 90s per-event stall
guard; the final `suggestion` + `done` are yielded directly after the queue
drains (suggestion skipped for greeting/clarification, matching the PAE guard).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from server.config import settings
from server.services.langfuse_tracer import (
    attach_summary_observation,
    district_type_for,
    emit_score,
    get_langfuse_handler,
    get_trace_id,
)
from server.services.langfuse_tracer import (
    flush as _lf_flush,
)

from . import router
from . import sse_emitter as sse
from .agent_session import run_loop as run_session

logger = logging.getLogger(__name__)

_SUGGESTION_SKIP_MODES = ("greeting_direct", "clarification_direct")
_ERROR_TEXT = "죄송합니다. 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."


async def run_agentic(
    message: str,
    district_code: str,
    district_name: str,
    data_quarter: str,
    conversation_history: list[dict] | None = None,
    session_id: str = "",
    request_id: str = "",
) -> AsyncGenerator[dict[str, Any], None]:
    """Agentic tool-use runner. Same signature/contract as graph.run_agent."""
    event_queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=settings.sse_queue_maxsize)
    lf_handler = get_langfuse_handler(session_id=session_id, request_id=request_id)
    trace_id = get_trace_id(lf_handler)
    route = router.classify(message, district_code)

    agg: dict[str, Any] = {
        "final_suggestions": [],
        "final_quality_flags": [],
        "final_quality_match_rate": None,
        "final_response_mode": route.response_mode,
        "final_intent": route.intent,
        "tool_results_count": 0,
        "tool_errors_count": 0,
        "card_count": 0,
    }

    async def _run_loop() -> None:
        try:
            if route.tier == "TRIVIAL":
                await event_queue.put(sse.thinking("질문 분석 중..."))
                await event_queue.put(sse.text(route.text))
                await event_queue.put(sse.suggestion(route.suggestions))
            else:
                result = await run_session(
                    message=message,
                    district_code=district_code,
                    district_name=district_name,
                    data_quarter=data_quarter,
                    conversation_history=conversation_history,
                    route=route,
                    emit=event_queue.put,
                    trace_id=trace_id,
                )
                agg.update(result)
        except Exception:
            logger.exception("agentic agent execution failed")
            await event_queue.put(sse.text(_ERROR_TEXT))
        finally:
            await event_queue.put(None)

    task = asyncio.create_task(_run_loop())
    try:
        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=90.0)
            except TimeoutError:
                logger.warning("Agentic event queue stalled for 90s, forcing done")
                break
            if event is None:
                break
            yield event
    finally:
        if not task.done():
            task.cancel()
        if trace_id:
            try:
                attach_summary_observation(
                    trace_id,
                    metadata={
                        "agent_mode": "agentic",
                        "tier": route.tier,
                        "intent": agg.get("final_intent"),
                        "district_type": district_type_for(district_code),
                        "tool_results_count": agg.get("tool_results_count", 0),
                        "tool_errors_count": agg.get("tool_errors_count", 0),
                        "card_count": agg.get("card_count", 0),
                    },
                )
                if agg.get("final_quality_match_rate") is not None:
                    emit_score(trace_id, "numeric_match", float(agg["final_quality_match_rate"]))
            except Exception:
                logger.debug("agentic langfuse aggregate emit failed", exc_info=True)
        _lf_flush(lf_handler)

    if agg.get("final_response_mode") not in _SUGGESTION_SKIP_MODES:
        dn = district_name if district_name and district_name != "미선택" else "여기"
        suggestions = agg.get("final_suggestions") or [
            f"{dn}에서 뭐하면 좋을까?",
            "이 자리 위험하지 않아?",
            "카페 하면 어때?",
            "유동인구 자세히 알려줘",
        ]
        yield sse.suggestion(suggestions)

    done_payload: dict[str, Any] = {"type": "done"}
    if trace_id:
        done_payload["trace_id"] = trace_id
    if agg.get("final_quality_flags"):
        done_payload["quality_flags"] = agg["final_quality_flags"]
    if agg.get("final_quality_match_rate") is not None:
        done_payload["quality_match_rate"] = agg["final_quality_match_rate"]
    yield done_payload
