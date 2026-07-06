"""v2 agentic loop — model-driven function-calling + Trust Kernel.

Exposes ``run_agent`` with the SAME signature and SSE event contract as the
legacy PAE ``server.agent.graph.run_agent``, so chat.py can swap between them
with a single dispatch. Events emitted: thinking / tool / tool_end / card /
text / suggestion / done. (greeting + map_cmd are handled in chat.py.)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from server.agent.loop.models import ainvoke_with_fallback, astream_with_fallback
from server.agent.loop.prompts import LOOP_SYSTEM_PROMPT, corrective_instruction
from server.agent.loop.tools_fc import (
    ABSTAIN,
    COMPUTE,
    RESOLVE_DISTRICT,
    card_for_tool,
    execute_fc_tool,
    labels_for_tool,
    tool_schemas,
)
from server.agent.loop.trust import (
    binding_stats,
    find_scale_errors,
    grounded_fallback,
    mask_unbound,
    should_fallback,
)
from server.config import settings

logger = logging.getLogger(__name__)


def _text_of(msg: Any) -> str:
    """Extract plain text from an AIMessage (str or content-block list)."""
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _history_messages(conversation_history: list[dict] | None) -> list:
    out: list = []
    for turn in (conversation_history or [])[-6:]:
        role = turn.get("role")
        content = turn.get("content") or ""
        if not content:
            continue
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role in ("assistant", "ai"):
            out.append(AIMessage(content=content))
    return out


def _system_message(district_code: str, district_name: str, data_quarter: str) -> SystemMessage:
    if district_code:
        ctx = (
            f"\n\n## 현재 컨텍스트\n선택된 상권: {district_name} "
            f"(코드 {district_code}, 분기 {data_quarter}). "
            "이 상권에 대한 질문이면 이 코드를 바로 쓰세요."
        )
    else:
        ctx = (
            "\n\n## 현재 컨텍스트\n선택된 상권이 없습니다. 사용자 메시지에서 상권명을 찾아 "
            "resolve_district 로 코드를 먼저 확보하세요."
        )
    return SystemMessage(content=LOOP_SYSTEM_PROMPT + ctx)


def _proactive_suggestions(called: set[str], district_name: str) -> list[str]:
    if "compare_districts" in called:
        return ["각 상권 추천 업종 알려줘", "유동인구 시간대별로 비교해줘", "리스크가 낮은 곳은?"]
    dn = district_name if district_name and district_name != "미선택" else ""
    if not dn:
        # 선택된 상권이 없는 턴(서울 외 거부·인젝션 방어 등) — "이 상권 ..." 칩은
        # 클릭해도 대상이 없다. 시작용 스타터로 대체.
        return ["강남역 상권 분석해줘", "홍대 어때?", "상권 비교하고 싶어"]
    if "recommend_business" in called:
        return [f"{dn} 매출 시뮬레이션 해줘", f"{dn} 리스크 분석해줘", "비슷한 상권과 비교해줘"]
    if "get_store_history" in called:
        return [f"{dn} 추천 업종 알려줘", f"{dn} 매출 수준은?", "안정적인 업종은 뭐야?"]
    return [f"{dn} 추천 업종 알려줘", f"{dn} 리스크는 어때?", f"{dn} 유동인구 자세히"]


def _chunks(text: str, size: int = 90):
    for i in range(0, len(text), size):
        yield text[i : i + size]


def _is_answer_shaped(text: str) -> bool:
    """교정 턴이 답변 대신 내놓는 메타 발화("...검토하겠습니다")를 걸러낸다.

    실제 재작성이라면 숫자가 남아 있거나, 숫자를 뺐더라도 답변으로 설 만큼의
    분량이 있다. 둘 다 아니면 채택하지 않는다(기존 draft가 still-unbound 검사로
    grounded_fallback 에 떨어진다).
    """
    t = (text or "").strip()
    return bool(t) and (any(c.isdigit() for c in t) or len(t) >= 120)


async def run_agent(
    message: str,
    district_code: str,
    district_name: str,
    data_quarter: str,
    conversation_history: list[dict] | None = None,
    session_id: str = "",
    request_id: str = "",
) -> AsyncGenerator[dict[str, Any], None]:
    """Model-driven loop with Trust Kernel. Yields SSE event dicts."""
    from server.services.langfuse_tracer import (
        attach_summary_observation,
        attach_tool_span,
        build_langchain_metadata,
        build_langchain_tags,
        district_type_for,
        emit_score,
        get_langfuse_handler,
        get_trace_id,
    )
    from server.services.langfuse_tracer import (
        flush as _lf_flush,
    )

    lf_handler = get_langfuse_handler(session_id=session_id, request_id=request_id)
    callbacks = [lf_handler] if lf_handler is not None else None
    lf_trace_id = get_trace_id(lf_handler)
    # Langfuse 활성 시에만 LangChain config 키를 전달 — handler None 이면 빈 dict
    # 로 기존 호출과 바이트 동일 (구 시그니처 fake 를 쓰는 테스트 보호).
    lf_kwargs: dict[str, Any] = (
        {
            "metadata": build_langchain_metadata(lf_handler),
            "tags": build_langchain_tags(),
            "run_name": "marketscope.v2",
        }
        if lf_handler is not None
        else {}
    )

    schemas = tool_schemas()
    messages: list = [
        _system_message(district_code, district_name, data_quarter),
        *_history_messages(conversation_history),
        HumanMessage(content=message),
    ]

    fact_pool: dict[str, dict] = {}
    computed: list[float] = []
    called_tools: set[str] = set()
    abstain_reason: str | None = None
    final_text = ""
    tool_calls_made = 0
    cards_emitted = 0
    started = time.monotonic()
    fact_idx = 0
    resolved_name = ""  # resolve_district 가 찾은 상권명 — suggestion 개인화용
    best_pct = 0  # "응답 작성 중 n%" 단조 clamp — mid-stream 폴백 재시작 시 % 역행 방지
    iteration = -1  # finalize 가 iterations_used 로 참조 — 루프 진입 전 예외 대비
    tool_errors = 0
    trust_corrective = False
    trust_fallback = False
    trust_masked = 0
    final_scored_total = 0
    final_unbound_count = 0
    final_scale_count = 0

    yield {"type": "thinking", "step": "질문 분석 중..."}

    try:
        for iteration in range(settings.agent_loop_max_iterations):
            over_budget = (
                tool_calls_made >= settings.agent_loop_max_tool_calls
                or (time.monotonic() - started) >= settings.agent_loop_wall_clock
            )
            # On the last allowed turn (or over budget) ask for a final answer
            # with no tools so the loop always terminates with prose.
            allow_tools = not over_budget and iteration < settings.agent_loop_max_iterations - 1

            if iteration > 0:
                # 도구 라운드 이후 모델 턴은 수십 초 걸릴 수 있다 — 진행 표시 유지.
                yield {"type": "thinking", "step": "결과 분석 중..."}

            if settings.agent_loop_stream_final:
                # 옵션 B: astream 으로 받되 버퍼링 — 수신 중에는 "응답 작성 중 n%"
                # 진행 이벤트만 방출하고, 본문 텍스트는 Trust 검증 후 일괄 방출.
                ai = None
                last_emit_chars = 0
                async for ev in astream_with_fallback(
                    messages,
                    schemas if allow_tools else None,
                    callbacks=callbacks,
                    timeout=settings.llm_timeout_slow,
                    **lf_kwargs,
                ):
                    if ev["kind"] == "final":
                        ai = ev["message"]
                        continue  # 다음 anext 가 곧바로 StopAsyncIteration — 자연 종료
                    # 도구 턴 서두 텍스트 오인 방지: tool_call 청크 등장 즉시 억제
                    # + 최소 분량 문턱 미달 시 미방출.
                    if ev["tool_call"] or ev["chars"] < settings.agent_loop_progress_min_chars:
                        continue
                    if ev["chars"] - last_emit_chars < settings.agent_loop_progress_interval_chars:
                        continue
                    last_emit_chars = ev["chars"]
                    pct = min(99, ev["chars"] * 100 // settings.agent_loop_expected_answer_chars)
                    if pct > best_pct:
                        best_pct = pct
                        yield {"type": "thinking", "step": f"응답 작성 중... {pct}%"}
                if ai is None:
                    raise RuntimeError("stream ended without a final message")
            else:
                ai = await ainvoke_with_fallback(
                    messages,
                    schemas if allow_tools else None,
                    callbacks=callbacks,
                    timeout=settings.llm_timeout_slow,
                    **lf_kwargs,
                )
            messages.append(ai)

            tool_calls = getattr(ai, "tool_calls", None) or []
            if not tool_calls or not allow_tools:
                final_text = _text_of(ai)
                break

            if iteration == 0:
                yield {"type": "thinking", "step": "데이터 수집 중..."}

            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("args", {}) or {}
                call_id = tc.get("id", "")
                tool_calls_made += 1
                progress, done = labels_for_tool(name)
                yield {"type": "tool", "name": name, "input": args, "progress_label": progress}

                tool_started = time.monotonic()
                result, error = await execute_fc_tool(name, args)
                called_tools.add(name)
                if error:
                    tool_errors += 1
                attach_tool_span(
                    lf_trace_id,
                    name=name,
                    args=args,
                    duration_ms=round((time.monotonic() - tool_started) * 1000, 1),
                    error=error,
                )

                if name == ABSTAIN:
                    abstain_reason = (result or {}).get("reason") or "데이터가 없습니다."
                elif name == RESOLVE_DISTRICT and result and result.get("name"):
                    resolved_name = str(result["name"])
                elif name == COMPUTE and result and "result" in result:
                    try:
                        computed.append(float(result["result"]))
                    except (TypeError, ValueError):
                        pass
                elif result and not error:
                    fact_idx += 1
                    # Store the UNTRUNCATED result: the model's ToolMessage gets
                    # the full payload, so a truncated pool makes values past the
                    # list cap unbindable (Round 3 RC3). The pool never reaches
                    # the LLM — zero token cost.
                    fact_pool[f"{name}#{fact_idx}"] = result
                    card = card_for_tool(name, result)
                    if card:
                        cards_emitted += 1
                        yield {"type": "card", "card_type": card["card_type"], "data": card["data"]}

                yield {"type": "tool_end", "name": name, "done_label": done}

                payload = result if result is not None else {"error": error or "unknown"}
                messages.append(
                    ToolMessage(
                        content=json.dumps(payload, ensure_ascii=False, default=str),
                        tool_call_id=call_id,
                    )
                )

            if abstain_reason is not None:
                break

        # ---- Trust Kernel enforcement -----------------------------------
        if abstain_reason is not None and not final_text:
            final_text = (
                f"요청하신 내용은 확인된 데이터로 답하기 어렵습니다. {abstain_reason} "
                "서울 지역 상권명을 알려주시면 분석해 드리겠습니다."
            )

        # binding_stats 는 find_unbound_numbers 와 동일 경로/동일 unmatched 반환
        # (scored_total 이 덤으로 나옴) — behavior-preserving 계측 치환.
        final_scored_total, unbound = binding_stats(final_text, fact_pool, computed)
        scale_errors = find_scale_errors(final_text, fact_pool, computed)
        final_unbound_count = len(unbound)
        final_scale_count = len(scale_errors)
        if (unbound or scale_errors) and abstain_reason is None:
            trust_corrective = True
            logger.info(
                "trust: %d unbound / %d scale-suspect numbers, corrective pass",
                len(unbound),
                len(scale_errors),
            )
            yield {"type": "thinking", "step": "수치 검증 중..."}
            value_hints = [
                f"'{s.number.raw}' → 도구 확인값 {int(s.expected):,}{s.number.tail or ''}" for s in scale_errors
            ]
            messages.append(
                HumanMessage(content=corrective_instruction([n.raw for n in unbound], value_hints=value_hints or None))
            )
            try:
                # 교정 턴은 prose 전용(도구 없음): 도구를 주면 모델이 도구 호출
                # 서두("...확인하겠습니다")만 텍스트로 남기고, v1은 재루프하지
                # 않으므로 그 메타 발화가 최종 답변으로 유출된다. 재작성은
                # 컨텍스트에 이미 있는 도구 결과만으로 한다.
                ai2 = await ainvoke_with_fallback(
                    messages, None, callbacks=callbacks, timeout=settings.llm_timeout_slow, **lf_kwargs
                )
                corrected = _text_of(ai2)
                if _is_answer_shaped(corrected):
                    final_text = corrected
            except Exception:  # noqa: BLE001
                logger.warning("trust corrective pass failed", exc_info=True)

            # 교정 후 재측정 — 종전의 find_unbound_numbers + binding_stats 이중
            # 계산을 단일 호출로 통합 (동일 반환).
            final_scored_total, still = binding_stats(final_text, fact_pool, computed)
            still_scale = find_scale_errors(final_text, fact_pool, computed)
            final_unbound_count = len(still)
            final_scale_count = len(still_scale)
            if still or still_scale:
                if should_fallback(len(still), final_scored_total):
                    # Entity-mismatch-grade fabrication — 폐기가 맞다.
                    logger.warning(
                        "trust: %d/%d still unbound → deterministic fallback",
                        len(still),
                        final_scored_total,
                    )
                    final_text = grounded_fallback(fact_pool, cards_emitted=cards_emitted > 0)
                    trust_fallback = True
                else:
                    # 소수 잔존 — draft 를 살리고 해당 수치만 마스킹 (Round 3 P1:
                    # 과잉 방어의 가용성 손실 방지).
                    logger.warning(
                        "trust: masking %d unbound + %d scale-suspect, draft preserved",
                        len(still),
                        len(still_scale),
                    )
                    final_text = mask_unbound(final_text, still + [s.number for s in still_scale])
                    trust_masked = len(still) + len(still_scale)

        if not final_text.strip():
            final_text = grounded_fallback(fact_pool, cards_emitted=cards_emitted > 0)
            trust_fallback = True

        for chunk in _chunks(final_text):
            yield {"type": "text", "content": chunk}

        yield {
            "type": "suggestion",
            "questions": _proactive_suggestions(called_tools, district_name or resolved_name),
        }

    except Exception:
        logger.exception("v2 loop execution failed")
        yield {
            "type": "text",
            "content": "죄송합니다. 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        }
    finally:
        # ---- Langfuse finalize (v2 L2) — lf_trace_id None 이면 전부 no-op ----
        if lf_trace_id:
            try:
                elapsed = time.monotonic() - started
                numeric_match_rate = (
                    (final_scored_total - final_unbound_count) / final_scored_total if final_scored_total > 0 else None
                )
                attach_summary_observation(
                    lf_trace_id,
                    name="marketscope.v2.summary",
                    metadata={
                        "district_code": district_code or "anonymous",
                        "district_type": district_type_for(district_code),
                        "district_name": district_name,
                        "resolved_name": resolved_name or None,
                        "data_quarter": data_quarter,
                        "iterations_used": iteration + 1,
                        "tool_calls_made": tool_calls_made,
                        "tool_error_count": tool_errors,
                        "card_count": cards_emitted,
                        "called_tools": sorted(called_tools),
                        "wall_clock_s": round(elapsed, 2),
                        "budget_exhausted": (
                            tool_calls_made >= settings.agent_loop_max_tool_calls
                            or elapsed >= settings.agent_loop_wall_clock
                        ),
                        "abstention_triggered": abstain_reason is not None,
                        "trust_unbound_final": final_unbound_count,
                        "trust_scale_error_count": final_scale_count,
                        "trust_corrective_applied": trust_corrective,
                        "trust_fallback_triggered": trust_fallback,
                        "trust_masked_count": trust_masked,
                        "numeric_match_rate": numeric_match_rate,
                    },
                )
                # score 6종 — numeric_match/tool_error_rate 는 분모 있을 때만
                if numeric_match_rate is not None:
                    emit_score(lf_trace_id, "numeric_match", numeric_match_rate)
                if tool_calls_made > 0:
                    emit_score(lf_trace_id, "tool_error_rate", tool_errors / tool_calls_made)
                emit_score(lf_trace_id, "abstention_triggered", 1.0 if abstain_reason is not None else 0.0)
                emit_score(lf_trace_id, "trust_corrective_applied", 1.0 if trust_corrective else 0.0)
                emit_score(lf_trace_id, "trust_fallback_triggered", 1.0 if trust_fallback else 0.0)
                emit_score(lf_trace_id, "trust_masked_count", float(trust_masked))
            except Exception:
                logger.debug("langfuse v2 summary emit failed", exc_info=True)
        # flush offload — 동기 flush 의 이벤트 루프 블로킹 제거 (best-effort,
        # CancelledError 는 미포착으로 전파 — abort 의미론 보존)
        try:
            await asyncio.to_thread(_lf_flush, lf_handler)
        except Exception:
            logger.debug("langfuse flush offload failed", exc_info=True)

    done_payload: dict[str, Any] = {"type": "done"}
    trace_id = get_trace_id(lf_handler)
    if trace_id:
        done_payload["trace_id"] = trace_id
    yield done_payload
