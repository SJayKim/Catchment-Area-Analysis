"""Evaluator node — judge tool result sufficiency + generate suggestions."""

from __future__ import annotations

import json
import logging
import re

from server.agent.prompts.evaluator import EVALUATOR_PROMPT
from server.agent.state import AgentState, EvaluationResult
from server.config import settings

logger = logging.getLogger(__name__)

SIMPLE_INTENTS = {"summary", "comparison", "recommendation", "risk"}


# ---------------------------------------------------------------------------
# Fast path (no LLM)
# ---------------------------------------------------------------------------


def _fast_evaluate(state: AgentState) -> EvaluationResult | None:
    """Rule-based sufficiency check for simple, first-round intents."""
    if not settings.evaluator_skip_simple:
        return None
    if state.get("user_intent") not in SIMPLE_INTENTS:
        return None
    if (state.get("execution_round") or 0) > 1:
        return None

    planned_tools = {step["tool_name"] for step in (state.get("plan") or [])}
    succeeded_tools = set((state.get("tool_results") or {}).keys())
    failed_tools = set((state.get("tool_errors") or {}).keys())

    if planned_tools and planned_tools.issubset(succeeded_tools) and not failed_tools:
        return EvaluationResult(
            sufficient=True,
            missing_info=[],
            proactive_suggestions=generate_proactive_suggestions(state),
            reasoning="모든 계획된 도구가 성공적으로 완료됨.",
        )

    if planned_tools and planned_tools.issubset(failed_tools):
        return EvaluationResult(
            sufficient=False,
            missing_info=[f"{t} 실패" for t in failed_tools],
            proactive_suggestions=[],
            reasoning="모든 도구가 실패하여 데이터를 가져오지 못함.",
        )

    return None  # mixed → slow path


# ---------------------------------------------------------------------------
# Slow path (LLM)
# ---------------------------------------------------------------------------


def _summarize_results(tool_results: dict[str, dict]) -> str:
    """Compact summary of tool results for the evaluator prompt."""
    parts: list[str] = []
    for name, data in tool_results.items():
        keys = list(data.keys())[:8]
        parts.append(f"- {name}: keys={keys}")
    return "\n".join(parts) or "(없음)"


async def _llm_evaluate(state: AgentState) -> EvaluationResult:
    """Use LLM to judge sufficiency for complex cases."""
    from server.agent.graph import _create_llm

    user_message = ""
    for msg in reversed(state.get("messages") or []):
        if hasattr(msg, "type") and msg.type == "human":
            user_message = msg.content
            break

    prompt = EVALUATOR_PROMPT.format(
        user_message=user_message,
        intent=state.get("user_intent", ""),
        tool_results_summary=_summarize_results(state.get("tool_results") or {}),
        tool_errors=state.get("tool_errors") or {},
    )

    llm = _create_llm(role="evaluator")
    response = await llm.ainvoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in content
        )

    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match:
        parsed = json.loads(json_match.group())
        return EvaluationResult(
            sufficient=parsed.get("sufficient", True),
            missing_info=parsed.get("missing_info", []),
            proactive_suggestions=[],
            reasoning=parsed.get("reasoning", ""),
        )

    # Parse failure → assume sufficient
    return EvaluationResult(
        sufficient=True,
        missing_info=[],
        proactive_suggestions=[],
        reasoning="LLM 응답 파싱 실패 — 기본값으로 진행.",
    )


# ---------------------------------------------------------------------------
# Dynamic suggestions
# ---------------------------------------------------------------------------


def generate_proactive_suggestions(state: AgentState) -> list[str]:
    """Context-aware follow-up suggestions based on intent + results."""
    intent = state.get("user_intent", "")
    name = state.get("district_name", "여기")
    results = state.get("tool_results") or {}

    suggestions: list[str]

    if intent == "summary":
        suggestions = [
            f"{name}에서 뭐하면 좋을까?",
            f"{name} 리스크 분석해줘",
            "유동인구 시간대별로 보여줘",
            "다른 상권이랑 비교해줘",
        ]
        summary = results.get("get_district_summary", {})
        close_rate = summary.get("closeRate", {}).get("current", 0)
        if close_rate and close_rate > 8.0:
            suggestions[1] = f"⚠ {name} 폐업률이 높아요 — 리스크 분석해볼까요?"

    elif intent == "comparison":
        suggestions = [
            "어떤 상권이 더 좋을까?",
            "추천 업종은 각각 어때?",
            "리스크도 비교해줘",
        ]

    elif intent == "recommendation":
        rec = results.get("recommend_business", {})
        recs = rec.get("recommendations", [])
        if recs:
            top = recs[0].get("category_name", "1위 업종")
            suggestions = [
                f"{top} 상세 분석해줘",
                f"{name} 리스크 확인해줘",
                f"다른 상권에서 {top}은 어때?",
                f"2위 업종은 어때?",
            ]
        else:
            suggestions = [f"{name} 요약해줘", "다른 상권 추천해줘"]

    elif intent == "risk":
        stability = results.get("get_store_history", {}).get("stability", {})
        score = stability.get("score", 50)
        if score is not None and score < 50:
            suggestions = ["안전한 업종 추천해줘", f"{name} 요약해줘", "다른 상권 알아볼까?"]
        else:
            suggestions = [f"{name} 추천 업종 알려줘", "매출 분석해줘", "다른 상권 비교해줘"]

    elif intent == "category_analysis":
        cat = state.get("referenced_category") or "해당 업종"
        suggestions = [f"{cat} 리스크 분석해줘", "다른 업종은 어때?", f"{name} 전체 요약해줘"]

    else:
        suggestions = ["상권 분석해줘", "업종 추천해줘", "리스크 확인해줘"]

    return suggestions[:4]


# ---------------------------------------------------------------------------
# Evaluator node
# ---------------------------------------------------------------------------


async def evaluator_node(state: AgentState) -> dict:
    """Judge tool result sufficiency. Fast path first, LLM if needed."""
    # 1. Fast path
    fast_result = _fast_evaluate(state)
    if fast_result is not None:
        return {"evaluation": fast_result}

    # 2. Slow path (LLM)
    try:
        llm_result = await _llm_evaluate(state)
        if llm_result["sufficient"]:
            llm_result = EvaluationResult(
                sufficient=True,
                missing_info=llm_result["missing_info"],
                proactive_suggestions=generate_proactive_suggestions(state),
                reasoning=llm_result["reasoning"],
            )
        return {"evaluation": llm_result}
    except Exception:
        logger.warning("Evaluator LLM failed, assuming sufficient", exc_info=True)
        return {
            "evaluation": EvaluationResult(
                sufficient=True,
                missing_info=[],
                proactive_suggestions=generate_proactive_suggestions(state),
                reasoning="Evaluator 오류 — 수집된 데이터로 응답 진행.",
            )
        }
