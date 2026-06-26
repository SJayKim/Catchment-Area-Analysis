"""LangGraph agent for MarketScope AI — Planner-Actor-Evaluator (PAE) architecture."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from langchain_core.messages import HumanMessage
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from server.config import settings
from server.services.circuit_breaker import CircuitBreaker, CircuitOpenError

LLM_PROVIDER = settings.llm_provider

logger = logging.getLogger(__name__)

# Flag to skip Anthropic after first auth failure (avoids repeated 401 roundtrips)
_anthropic_valid = True

# Module-level circuit breaker for all LLM calls
_llm_circuit_breaker = CircuitBreaker(
    failure_threshold=settings.circuit_breaker_failure_threshold,
    recovery_timeout=settings.circuit_breaker_recovery_timeout,
    name="llm",
)


def _create_llm(role: str = "default"):
    """Create the LLM instance based on configured provider and role.

    Role-based model selection (Gemini):
      - "respond", "default" → gemini-2.5-pro  (user-facing, quality matters)
      - "planner", "evaluator" → gemini-2.5-flash  (internal, speed matters)

    Provider "mock" returns a FakeListChatModel for load testing (no API cost).
    """
    if LLM_PROVIDER == "mock":
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        # Planner expects JSON with intent/plan; other roles get plain Korean text
        if role in ("planner",):
            responses = [
                '{"intent": "summary", "confidence": 0.95, '
                '"plan": [{"tool": "district_summary", "input": {"district_code": "%(district_code)s"}, "depends_on": []}], '
                '"direct_response": false, "reasoning": "상권 요약 요청"}'
            ]
        elif role in ("evaluator",):
            responses = ['{"sufficient": true, "reasoning": "모든 도구 결과가 정상 반환됨", "missing": []}']
        else:
            responses = [
                "강남역 상권은 서울 주요 상권 중 하나입니다. "
                "일평균 유동인구는 약 100만 명이며, 피크 시간대는 18시입니다. "
                "주요 업종은 한식, 커피, 편의점 순이고, "
                "최근 분기 추정 매출은 약 500억 원입니다. "
                "폐업률은 5.2%로 서울 평균 대비 양호한 수준입니다.",
            ]

        return FakeListChatModel(responses=responses, sleep=0.02)

    # Planner uses Anthropic Claude Sonnet for superior intent classification.
    # Guarded by _anthropic_valid flag to avoid retrying a known-bad key.
    if role == "planner" and settings.anthropic_api_key and _anthropic_valid:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
            max_tokens=4096,
            temperature=0.3,
        )

    if LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        pro_roles = {"respond", "default"}
        model = settings.gemini_model_pro if role in pro_roles else settings.gemini_model_flash

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,  # type: ignore[arg-type]
            temperature=0.3,
            max_output_tokens=4096,
        )
    else:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
            max_tokens=4096,
            temperature=0.3,
        )


# ===================================================================
# LLM retry wrapper (circuit breaker + tenacity)
# ===================================================================


async def invoke_llm_with_retry(llm, prompt, *, timeout: float | None = None):
    """Invoke LLM with circuit breaker + automatic retry.

    Combines:
      1. Circuit breaker — fast-fail when LLM is consistently down
      2. Tenacity retry  — 2 attempts, exponential backoff 1-4s

    Raises CircuitOpenError if circuit is open.
    Raises the underlying LLM error after retries are exhausted.
    """

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_not_exception_type(CircuitOpenError),
        reraise=True,
    )
    async def _attempt():
        _llm_circuit_breaker.check()  # raises CircuitOpenError immediately
        try:
            if timeout is not None:
                result = await asyncio.wait_for(llm.ainvoke(prompt), timeout=timeout)
            else:
                result = await llm.ainvoke(prompt)
            await _llm_circuit_breaker.record_success()
            return result
        except CircuitOpenError:
            raise  # don't record CB errors as failures
        except Exception:
            await _llm_circuit_breaker.record_failure()
            raise

    return await _attempt()


# ===================================================================
# PAE agent (Planner-Actor-Evaluator)
# ===================================================================


def _build_pae_graph(event_queue: asyncio.Queue):
    """Build a fresh PAE StateGraph with closures over event_queue."""
    from langgraph.graph import END, StateGraph

    from server.agent.nodes.actor import actor_node
    from server.agent.nodes.evaluator import evaluator_node
    from server.agent.nodes.planner import planner_node
    from server.agent.nodes.respond import respond_node
    from server.agent.state import AgentState

    async def _planner(state: AgentState) -> dict:
        return await planner_node(state)

    async def _greeting(state: AgentState) -> dict:
        """Emit greeting response directly — no LLM call needed."""
        await event_queue.put(
            {
                "type": "text",
                "content": "안녕하세요! 서울 상권 분석 AI 마켓스코프입니다.\n"
                "지도에서 상권을 선택하시거나, 분석할 상권명을 알려주세요!",
            }
        )
        await event_queue.put(
            {
                "type": "suggestion",
                "questions": ["강남역 상권 분석해줘", "홍대 어때?", "업종 추천해줘", "상권 비교하고 싶어"],
            }
        )
        return {"final_response": "안녕하세요! 서울 상권 분석 AI 마켓스코프입니다."}

    async def _clarification(state: AgentState) -> dict:
        """P0-4: deterministic clarification when Planner flagged an empty-plan
        coreference/exclusion/comparison-under-2 case. Emits fixed text +
        suggestions and skips LLM."""
        text = state.get("clarification_text") or (
            "질문을 조금 더 구체적으로 알려주시겠어요? 분석할 상권 이름을 직접 언급해 주세요."
        )
        suggestions = state.get("clarification_suggestions") or [
            "강남역 상권 분석",
            "홍대 vs 성수 비교",
            "건대 창업 추천 업종",
        ]
        await event_queue.put({"type": "text", "content": text})
        await event_queue.put({"type": "suggestion", "questions": suggestions})
        return {"final_response": text}

    async def _actor(state: AgentState) -> dict:
        return await actor_node(state, event_queue)

    async def _evaluator(state: AgentState) -> dict:
        return await evaluator_node(state)

    async def _respond(state: AgentState) -> dict:
        return await respond_node(state, event_queue)

    def route_after_planner(state) -> str:
        if state.get("response_mode") == "greeting_direct":
            return "greeting"
        if state.get("response_mode") == "clarification_direct":
            return "clarification"
        if state.get("response_mode") == "direct" or not state.get("plan"):
            return "respond"
        return "actor"

    def route_after_evaluator(state) -> str:
        evaluation = state.get("evaluation")
        if not evaluation or evaluation["sufficient"]:
            return "respond"
        if (state.get("execution_round") or 0) >= settings.agent_max_rounds:
            return "respond"
        return "planner"

    graph = StateGraph(AgentState)
    graph.add_node("planner", _planner)
    graph.add_node("greeting", _greeting)
    graph.add_node("clarification", _clarification)
    graph.add_node("actor", _actor)
    graph.add_node("evaluator", _evaluator)
    graph.add_node("respond", _respond)

    graph.set_entry_point("planner")
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "actor": "actor",
            "respond": "respond",
            "greeting": "greeting",
            "clarification": "clarification",
        },
    )
    graph.add_edge("greeting", END)
    graph.add_edge("clarification", END)
    graph.add_edge("actor", "evaluator")
    graph.add_conditional_edges("evaluator", route_after_evaluator, {"respond": "respond", "planner": "planner"})
    graph.add_edge("respond", END)

    return graph.compile()


async def run_agent(
    message: str,
    district_code: str,
    district_name: str,
    data_quarter: str,
    conversation_history: list[dict] | None = None,
    session_id: str = "",
    request_id: str = "",
) -> AsyncGenerator[dict[str, Any], None]:
    """PAE agent — asyncio.Queue based real-time SSE streaming.

    `session_id` / `request_id` 는 Langfuse trace 메타데이터로 전달.
    Langfuse 비활성/실패 시 handler=None → 기존 경로와 동일.
    """
    from server.agent.state import AgentState
    from server.services.langfuse_tracer import (
        build_langchain_metadata,
        build_langchain_tags,
        get_langfuse_handler,
        get_trace_id,
    )
    from server.services.langfuse_tracer import (
        flush as _lf_flush,
    )

    lf_tags = build_langchain_tags()

    # Bounded queue so a slow/disconnected SSE consumer naturally blocks the
    # LLM/tool producers (backpressure) instead of growing memory unbounded.
    event_queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=settings.sse_queue_maxsize)

    # Langfuse callback (best-effort). None 이면 trace 없이 진행.
    lf_handler = get_langfuse_handler(session_id=session_id, request_id=request_id)
    lf_metadata = build_langchain_metadata(lf_handler)

    initial_state: AgentState = {  # type: ignore[typeddict-item]
        "messages": [HumanMessage(content=message)],
        "conversation_history": conversation_history or [],
        "district_code": district_code,
        "district_name": district_name,
        "data_quarter": data_quarter,
        "session_id": "",
        "user_intent": "",
        "intent_confidence": 0.0,
        "referenced_districts": [],
        "referenced_category": None,
        "plan": [],
        "plan_reasoning": "",
        "tool_results": {},
        "tool_errors": {},
        "execution_round": 0,
        "evaluation": None,
        "response_mode": "tool_assisted",
        "card_emissions": [],
        "iteration_count": 0,
    }

    compiled = _build_pae_graph(event_queue)

    # Store suggestions from evaluator for the final yield
    final_suggestions: list[str] = []
    final_quality_flags: list[dict] = []
    final_quality_match_rate: float | None = None
    # Aggregate-stats dimensions captured during astream (Plan
    # langfuse-aggregate-stats-2026-04-28 §Phase1). All derived from existing
    # state — no new state fields required.
    final_intent: str = ""
    final_intent_confidence: float = 0.0
    final_response_mode: str = "tool_assisted"
    final_execution_round: int = 0
    final_plan_size: int = 0
    final_referenced_count: int = 0
    final_referenced_category: str | None = None
    final_ambiguous_count: int = 0
    final_tool_results_count: int = 0
    final_tool_errors_count: int = 0
    final_card_count: int = 0

    async def _run_graph():
        nonlocal final_suggestions, final_quality_flags, final_quality_match_rate
        nonlocal final_intent, final_intent_confidence, final_response_mode
        nonlocal final_execution_round, final_plan_size, final_referenced_count
        nonlocal final_referenced_category, final_ambiguous_count
        nonlocal final_tool_results_count, final_tool_errors_count, final_card_count
        emitted_card_count = 0  # track to avoid re-emitting accumulated cards

        try:
            await event_queue.put({"type": "thinking", "step": "질문 분석 중..."})

            astream_config: dict[str, Any] = {}
            if lf_handler is not None:
                astream_config["callbacks"] = [lf_handler]
                astream_config["metadata"] = lf_metadata
                astream_config["tags"] = lf_tags
                astream_config["run_name"] = "marketscope.pae"

            async for update in compiled.astream(
                initial_state,
                config=astream_config or None,
                stream_mode="updates",
            ):
                for node_name, state_update in update.items():
                    if node_name == "planner":
                        plan = state_update.get("plan", [])
                        intent = state_update.get("user_intent", "")
                        if intent:
                            final_intent = intent
                        conf = state_update.get("intent_confidence")
                        if conf is not None:
                            final_intent_confidence = float(conf)
                        rm = state_update.get("response_mode")
                        if rm:
                            final_response_mode = rm
                        if plan is not None:
                            final_plan_size = len(plan)
                        ref = state_update.get("referenced_districts") or []
                        final_referenced_count = len(ref)
                        cat = state_update.get("referenced_category")
                        if cat is not None:
                            final_referenced_category = cat
                        amb = state_update.get("ambiguous_districts") or []
                        if amb:
                            final_ambiguous_count = len(amb)
                        if plan:
                            steps = [s["reason"] for s in plan]
                            await event_queue.put(
                                {
                                    "type": "plan",
                                    "intent": intent,
                                    "steps": steps,
                                }
                            )

                    elif node_name == "actor":
                        # Only emit NEW cards (actor accumulates across rounds)
                        all_cards = state_update.get("card_emissions", [])
                        new_cards = all_cards[emitted_card_count:]
                        emitted_card_count = len(all_cards)
                        for card in new_cards:
                            await event_queue.put(
                                {
                                    "type": "card",
                                    "card_type": card["card_type"],
                                    "data": card["data"],
                                }
                            )
                        final_card_count = len(all_cards)
                        tr = state_update.get("tool_results") or {}
                        final_tool_results_count = len(tr)
                        te = state_update.get("tool_errors") or {}
                        final_tool_errors_count = len(te)
                        rd = state_update.get("execution_round")
                        if rd is not None:
                            final_execution_round = int(rd)

                    elif node_name == "evaluator":
                        ev = state_update.get("evaluation") or {}
                        if not ev.get("sufficient", True):
                            await event_queue.put(
                                {
                                    "type": "thinking",
                                    "step": "추가 데이터 수집 중...",
                                }
                            )
                        # Capture suggestions
                        sug = ev.get("proactive_suggestions", [])
                        if sug:
                            final_suggestions[:] = sug

                    elif node_name == "respond":
                        # L3: capture quality_flags from numeric_sanity evaluator
                        qf = state_update.get("quality_flags") or []
                        if qf:
                            final_quality_flags = qf
                        qmr = state_update.get("quality_match_rate")
                        if qmr is not None:
                            final_quality_match_rate = qmr

                    elif node_name in ("greeting", "clarification"):
                        final_response_mode = "greeting_direct" if node_name == "greeting" else "clarification_direct"

        except Exception:
            logger.exception("PAE agent execution failed")
            await event_queue.put(
                {
                    "type": "text",
                    "content": "죄송합니다. 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                }
            )
        finally:
            await event_queue.put(None)  # sentinel

    task = asyncio.create_task(_run_graph())

    try:
        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=90.0)
            except TimeoutError:
                logger.warning("Agent event queue stalled for 90s, forcing done")
                break
            if event is None:
                break
            yield event
    finally:
        if not task.done():
            task.cancel()

        # Aggregate-stats: trace 차원 보강 + score emit (Plan
        # langfuse-aggregate-stats-2026-04-28). flush 보다 먼저 호출해야
        # 동봉 span/score 가 같은 배치에 묶여 단일 round-trip 으로 송신됨.
        trace_id = get_trace_id(lf_handler)
        if trace_id:
            from server.services.langfuse_tracer import (
                attach_summary_observation,
                district_type_for,
                emit_score,
            )

            try:
                tools_attempted = final_tool_results_count + final_tool_errors_count
                tool_error_rate = final_tool_errors_count / tools_attempted if tools_attempted > 0 else None
                quality_severity_max = _max_quality_severity(final_quality_flags)
                summary_metadata = {
                    "user_intent": final_intent or "unknown",
                    "intent_confidence": final_intent_confidence,
                    "district_code": district_code or "anonymous",
                    "district_type": district_type_for(district_code),
                    "referenced_districts_count": final_referenced_count,
                    "referenced_category": final_referenced_category or "none",
                    "response_mode": final_response_mode,
                    "execution_round": final_execution_round,
                    "tool_count": tools_attempted,
                    "tool_error_count": final_tool_errors_count,
                    "card_count": final_card_count,
                    "plan_size": final_plan_size,
                    "quality_match_rate": final_quality_match_rate,
                    "quality_flag_severity_max": quality_severity_max,
                    "abstention_triggered": (final_response_mode == "clarification_direct"),
                    "ambiguous_disambiguation_needed": final_ambiguous_count > 0,
                }
                attach_summary_observation(trace_id, metadata=summary_metadata)

                # 6 score emits — None 분기는 helper 가 silent skip
                if final_quality_match_rate is not None:
                    emit_score(trace_id, "numeric_match", final_quality_match_rate)
                if final_intent_confidence > 0:
                    emit_score(trace_id, "intent_confidence", final_intent_confidence)
                if tool_error_rate is not None:
                    emit_score(trace_id, "tool_error_rate", tool_error_rate)
                emit_score(
                    trace_id,
                    "abstention_triggered",
                    1.0 if final_response_mode == "clarification_direct" else 0.0,
                )
                emit_score(
                    trace_id,
                    "ambiguous_disambiguation_needed",
                    1.0 if final_ambiguous_count > 0 else 0.0,
                )
                if quality_severity_max is not None:
                    emit_score(trace_id, "quality_severity", float(quality_severity_max))
            except Exception:
                logger.debug("langfuse aggregate stats emit failed", exc_info=True)

        # best-effort flush — 예외 삼킴
        _lf_flush(lf_handler)

    # Suggestion + done (trace_id 는 Langfuse 활성 시에만 포함)
    # greeting/clarification 노드는 실행 중 자체 tailored suggestion 을 이미 방출한다.
    # 이 경우 말미 fallback 방출을 건너뛴다 — 중복 이벤트로 generic suggestion 이
    # tailored 를 덮어쓰는 문제(out_of_scope 등) 방지.
    if final_response_mode not in ("greeting_direct", "clarification_direct"):
        dn = district_name if district_name and district_name != "미선택" else "여기"
        suggestions = final_suggestions or [
            f"{dn}에서 뭐하면 좋을까?",
            "이 자리 위험하지 않아?",
            "카페 하면 어때?",
            "유동인구 자세히 알려줘",
        ]
        yield {"type": "suggestion", "questions": suggestions}

    done_payload: dict[str, Any] = {"type": "done"}
    if trace_id:
        done_payload["trace_id"] = trace_id
    if final_quality_flags:
        done_payload["quality_flags"] = final_quality_flags
    if final_quality_match_rate is not None:
        done_payload["quality_match_rate"] = final_quality_match_rate
    yield done_payload


_QUALITY_SEVERITY_MAP = {"info": 0, "warning": 1, "error": 2}


def _max_quality_severity(flags: list[dict] | None) -> int | None:
    """quality_flags 중 max severity (info=0, warning=1, error=2). 없으면 None."""
    if not flags:
        return None
    levels = [_QUALITY_SEVERITY_MAP.get(str(f.get("severity", "info")).lower(), 0) for f in flags]
    return max(levels) if levels else None
