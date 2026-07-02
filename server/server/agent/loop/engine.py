"""v2 agentic loop — model-driven function-calling + Trust Kernel.

Exposes ``run_agent`` with the SAME signature and SSE event contract as the
legacy PAE ``server.agent.graph.run_agent``, so chat.py can swap between them
with a single dispatch. Events emitted: thinking / tool / tool_end / card /
text / suggestion / done. (greeting + map_cmd are handled in chat.py.)
"""

from __future__ import annotations

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

from server.agent.loop.models import ainvoke_with_fallback
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
from server.agent.loop.trust import find_unbound_numbers, grounded_fallback
from server.agent.nodes.actor import _truncate_result
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
        flush as _lf_flush,
    )
    from server.services.langfuse_tracer import (
        get_langfuse_handler,
        get_trace_id,
    )

    lf_handler = get_langfuse_handler(session_id=session_id, request_id=request_id)
    callbacks = [lf_handler] if lf_handler is not None else None

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
    started = time.monotonic()
    fact_idx = 0
    resolved_name = ""  # resolve_district 가 찾은 상권명 — suggestion 개인화용

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

            ai = await ainvoke_with_fallback(
                messages,
                schemas if allow_tools else None,
                callbacks=callbacks,
                timeout=settings.llm_timeout_slow,
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

                result, error = await execute_fc_tool(name, args)
                called_tools.add(name)

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
                    stored = _truncate_result(result) if isinstance(result, dict) else result
                    fact_pool[f"{name}#{fact_idx}"] = stored
                    card = card_for_tool(name, result)
                    if card:
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

        unbound = find_unbound_numbers(final_text, fact_pool, computed)
        if unbound and abstain_reason is None:
            logger.info("trust: %d unbound numbers, corrective pass", len(unbound))
            yield {"type": "thinking", "step": "수치 검증 중..."}
            messages.append(HumanMessage(content=corrective_instruction([n.raw for n in unbound])))
            try:
                # 교정 턴은 prose 전용(도구 없음): 도구를 주면 모델이 도구 호출
                # 서두("...확인하겠습니다")만 텍스트로 남기고, v1은 재루프하지
                # 않으므로 그 메타 발화가 최종 답변으로 유출된다. 재작성은
                # 컨텍스트에 이미 있는 도구 결과만으로 한다.
                ai2 = await ainvoke_with_fallback(
                    messages, None, callbacks=callbacks, timeout=settings.llm_timeout_slow
                )
                corrected = _text_of(ai2)
                if _is_answer_shaped(corrected):
                    final_text = corrected
            except Exception:  # noqa: BLE001
                logger.warning("trust corrective pass failed", exc_info=True)

            still = find_unbound_numbers(final_text, fact_pool, computed)
            if still:
                logger.warning("trust: %d still unbound → deterministic fallback", len(still))
                final_text = grounded_fallback(fact_pool)

        if not final_text.strip():
            final_text = grounded_fallback(fact_pool)

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
        _lf_flush(lf_handler)

    done_payload: dict[str, Any] = {"type": "done"}
    trace_id = get_trace_id(lf_handler)
    if trace_id:
        done_payload["trace_id"] = trace_id
    yield done_payload
