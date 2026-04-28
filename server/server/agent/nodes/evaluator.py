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


def _rule_based_evaluate(state: AgentState) -> EvaluationResult:
    """Deterministic evaluation from tool success/failure state.

    Reused by LLM parse-failure and broad-exception paths so the evaluator
    doesn't silently return sufficient=True on every LLM hiccup.
    """
    planned_tools = [step["tool_name"] for step in (state.get("plan") or [])]
    succeeded = set((state.get("tool_results") or {}).keys())
    failed = set((state.get("tool_errors") or {}).keys())

    # Quality fix (2026-04-24 Pass 2): if any tool returned needs_category=True
    # we must NOT re-plan identically — it will just produce the same error.
    # Stop the loop with sufficient=True so Respond can emit a clarification.
    tool_results = state.get("tool_results") or {}
    for _, data in tool_results.items():
        if isinstance(data, dict) and data.get("needs_category"):
            return EvaluationResult(
                sufficient=True,
                missing_info=[],
                proactive_suggestions=generate_proactive_suggestions(state),
                reasoning="업종 지정 필요 — Respond 에서 clarification 유도.",
            )

    # No plan → nothing to evaluate; respond with whatever we have.
    if not planned_tools:
        return EvaluationResult(
            sufficient=True,
            missing_info=[],
            proactive_suggestions=generate_proactive_suggestions(state),
            reasoning="평가 기준 계획이 없어 수집된 컨텍스트로 응답.",
        )

    all_failed = all(t in failed for t in planned_tools) and bool(failed)
    any_success = any(t in succeeded for t in planned_tools)

    if all_failed:
        return EvaluationResult(
            sufficient=False,
            missing_info=[f"{t} 실패" for t in failed],
            proactive_suggestions=[],
            reasoning="모든 도구 실행이 실패하여 응답을 생성할 데이터가 없음.",
        )

    # Mixed or all-success → sufficient, surface missing tools in missing_info.
    missing_info = [t for t in planned_tools if t not in succeeded]
    return EvaluationResult(
        sufficient=any_success,
        missing_info=missing_info,
        proactive_suggestions=generate_proactive_suggestions(state),
        reasoning=("규칙 기반 평가: 확보된 도구 결과로 응답 진행." if any_success else "수집된 데이터 없음."),
    )


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

    # Same needs_category short-circuit as _rule_based_evaluate.
    tool_results = state.get("tool_results") or {}
    if any(isinstance(d, dict) and d.get("needs_category") for d in tool_results.values()):
        return EvaluationResult(
            sufficient=True,
            missing_info=[],
            proactive_suggestions=generate_proactive_suggestions(state),
            reasoning="업종 지정 필요 — Respond 에서 clarification.",
        )

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
    from server.agent.graph import _create_llm, invoke_llm_with_retry

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
    response = await invoke_llm_with_retry(llm, prompt, timeout=settings.llm_timeout_fast)
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)

    try:
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            return EvaluationResult(
                sufficient=parsed.get("sufficient", True),
                missing_info=parsed.get("missing_info", []),
                proactive_suggestions=[],
                reasoning=parsed.get("reasoning", ""),
            )
    except json.JSONDecodeError:
        logger.warning("Evaluator LLM returned invalid JSON, using rule fallback")

    # Parse failure → deterministic rule-based evaluation instead of
    # optimistic sufficient=True.
    return _rule_based_evaluate(state)


# ---------------------------------------------------------------------------
# Dynamic suggestions
# ---------------------------------------------------------------------------


def _short_name(full: str) -> str:
    """Strip Seoul-opendata 별칭 parens for user-facing suggestions.

    Examples:
        "홍대입구역(홍대)"  → "홍대입구역"
        "건대입구역(건대)"  → "건대입구역"
        "명동(명동거리)"    → "명동"
        "강남역"           → "강남역"
    """
    if not full:
        return full
    idx = full.find("(")
    if idx > 0:
        return full[:idx].strip()
    return full


def generate_proactive_suggestions(state: AgentState) -> list[str]:
    """Context-aware follow-up suggestions based on intent + results."""
    intent = state.get("user_intent", "")
    name = _short_name(state.get("district_name", "여기"))
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
            suggestions[1] = f"{name} 폐업률이 높아요 — 리스크 분석해볼까요?"

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
                "2위 업종은 어때?",
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
    from server.services.circuit_breaker import CircuitOpenError

    # 0. needs_category short-circuit — simulate_revenue (and peers) return
    #    ``{"error": "...", "needs_category": True}`` when the user did not
    #    specify a business category. Looping would just re-run the same tool
    #    with the same null input; instead, hand off to Respond immediately
    #    so it can surface the clarification template.
    tool_results = state.get("tool_results") or {}
    if any(isinstance(d, dict) and d.get("needs_category") for d in tool_results.values()):
        logger.info(
            "evaluator.needs_category short-circuit session=%s round=%s",
            state.get("session_id"),
            state.get("execution_round"),
        )
        return {
            "evaluation": EvaluationResult(
                sufficient=True,
                missing_info=[],
                proactive_suggestions=generate_proactive_suggestions(state),
                reasoning="업종 지정 필요 — Respond 에서 clarification.",
            )
        }

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
    except CircuitOpenError:
        logger.warning("Evaluator skipped: LLM circuit breaker is OPEN, using rule fallback")
        return {"evaluation": _rule_based_evaluate(state)}
    except Exception:
        logger.warning("Evaluator LLM failed, using rule fallback", exc_info=True)
        return {"evaluation": _rule_based_evaluate(state)}
