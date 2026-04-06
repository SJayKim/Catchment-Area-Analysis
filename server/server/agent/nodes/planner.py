"""Planner node — intent classification + tool plan generation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from server.agent.prompts.planner import PLANNER_CLASSIFICATION_PROMPT
from server.agent.state import AgentState, ToolPlanStep

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rule-based intent patterns
# ---------------------------------------------------------------------------

INTENT_PATTERNS: dict[str, re.Pattern[str]] = {
    "greeting": re.compile(r"^(안녕|하이|헬로|hi|hello|반갑|감사|고마워|ㅎㅇ)", re.IGNORECASE),
    "simulation": re.compile(r"(시뮬���이션|매출.*예상|매출.*얼마|매출.*시뮬|얼마.*벌|수익.*예상|장사.*되|매출.*전망|열면.*매출|하면.*매출)"),
    "comparison": re.compile(r"(비교|vs|대비|차이)"),
    "recommendation": re.compile(r"(추천|뭐.*하면|어떤.*업종|창업|아이���)"),
    "risk": re.compile(r"(위험|리스크|폐업|안전|생존|실패)"),
    "category_analysis": re.compile(
        r"(카페|한식|���피|치킨|편의점|음식점|미용|병원|약국|중식|일식|양식|분식|주점|제과)"
    ),
    "summary": re.compile(r"(요약|분석|알려���|어때|보여줘|정보|현황|상권을?\s*선택)"),
}

FOLLOW_UP_MARKERS = re.compile(
    r"(그러면|그럼|그래서|그리고|또|거기|아까|방금|그\s*상권|그\s*지역|그곳)"
)

NON_SUMMARY_OVERRIDES = re.compile(
    r"(비교|추천|뭐.*하면|위험|리스크|폐업|히트맵|시뮬|매출.*예상|매출.*얼마|얼마.*벌|카페|한식|커피|치킨|편의점)"
)

# Map Korean category keywords → category_code (best-effort)
_CATEGORY_KEYWORDS: dict[str, str] = {
    "카페": "CS100001",
    "커피": "CS100001",
    "한식": "CS200001",
    "중식": "CS200002",
    "일식": "CS200003",
    "양식": "CS200004",
    "분식": "CS200006",
    "치킨": "CS200010",
    "편의점": "CS300001",
    "미용": "CS400001",
    "약국": "CS500001",
    "주점": "CS200009",
    "제과": "CS200014",
}

# ---------------------------------------------------------------------------
# Intent → tool plan mapping
# ---------------------------------------------------------------------------

INTENT_TO_PLAN: dict[str, list[dict[str, Any]]] = {
    "summary": [
        {"tool_name": "get_district_summary", "args_template": {"district_code": "{district_code}"}, "reason": "상권 종합 요약 조회", "depends_on": []},
    ],
    "comparison": [
        {"tool_name": "compare_districts", "args_template": {"district_codes": "{referenced_districts}"}, "reason": "상권 비교 분석", "depends_on": []},
    ],
    "recommendation": [
        {"tool_name": "recommend_business", "args_template": {"district_code": "{district_code}"}, "reason": "업종 추천 분석", "depends_on": []},
    ],
    "risk": [
        {"tool_name": "get_store_history", "args_template": {"district_code": "{district_code}"}, "reason": "점포 이력/리스크 분석", "depends_on": []},
    ],
    "category_analysis": [
        {"tool_name": "get_estimated_sales", "args_template": {"district_code": "{district_code}", "category_code": "{category_code}"}, "reason": "업종별 매출 조회", "depends_on": []},
        {"tool_name": "get_store_info", "args_template": {"district_code": "{district_code}", "category_code": "{category_code}"}, "reason": "업종별 점포 현황 조회", "depends_on": []},
    ],
    "simulation": [
        {"tool_name": "simulate_revenue", "args_template": {"district_code": "{district_code}", "category_code": "{category_code}"}, "reason": "매출 시뮬레이션", "depends_on": []},
    ],
    "greeting": [],  # 도구 불필요
    "general": [],
    "ambiguous": [],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _classify_by_rules(message: str) -> tuple[str | None, float]:
    """Fast rule-based intent classification. Returns (intent, confidence)."""
    # Follow-up markers → need LLM
    if FOLLOW_UP_MARKERS.search(message):
        return "follow_up", 0.5

    # Non-summary overrides first
    if NON_SUMMARY_OVERRIDES.search(message):
        # Find which specific intent matches
        for intent, pattern in INTENT_PATTERNS.items():
            if intent == "summary":
                continue
            if pattern.search(message):
                return intent, 0.9
        return None, 0.0

    # Single-pattern match
    matched: list[str] = []
    for intent, pattern in INTENT_PATTERNS.items():
        if pattern.search(message):
            matched.append(intent)

    if len(matched) == 1:
        return matched[0], 0.9
    if len(matched) > 1:
        return None, 0.4  # ambiguous → LLM

    return None, 0.0  # no match → LLM


def _extract_category(message: str) -> str | None:
    """Extract category_code from message keywords."""
    for keyword, code in _CATEGORY_KEYWORDS.items():
        if keyword in message:
            return code
    return None


def _extract_category_name(message: str) -> str | None:
    """Extract the category keyword itself for display."""
    for keyword in _CATEGORY_KEYWORDS:
        if keyword in message:
            return keyword
    return None


async def _classify_with_llm(
    message: str,
    history_text: str,
    district_code: str,
    district_name: str,
) -> dict:
    """LLM-based intent classification for ambiguous cases."""
    from server.agent.graph import _create_llm

    prompt = PLANNER_CLASSIFICATION_PROMPT.format(
        message=message,
        history=history_text or "(없음)",
        district_code=district_code or "(미선택)",
        district_name=district_name or "(미선택)",
    )

    llm = _create_llm(role="planner")
    try:
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        if isinstance(content, list):
            content = "".join(
                b.get("text", "") if isinstance(b, dict) else str(b) for b in content
            )
        # Extract JSON from response
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception:
        logger.warning("LLM classification failed, falling back to rules", exc_info=True)

    # Fallback
    return {"intent": "summary", "confidence": 0.5, "referenced_districts": [district_code], "referenced_category": None}


def _build_plan(
    intent: str,
    district_code: str,
    referenced_districts: list[str],
    category_code: str | None,
) -> list[ToolPlanStep]:
    """Generate ToolPlanStep list from intent."""
    templates = INTENT_TO_PLAN.get(intent, [])
    plan: list[ToolPlanStep] = []

    for tmpl in templates:
        args: dict[str, Any] = {}
        for key, val in tmpl["args_template"].items():
            if val == "{district_code}":
                args[key] = district_code
            elif val == "{referenced_districts}":
                args[key] = referenced_districts
            elif val == "{category_code}":
                args[key] = category_code
            else:
                args[key] = val

        plan.append(
            ToolPlanStep(
                tool_name=tmpl["tool_name"],
                args=args,
                reason=tmpl["reason"],
                depends_on=list(tmpl.get("depends_on", [])),
            )
        )

    return plan


# ---------------------------------------------------------------------------
# Planner node (entry point)
# ---------------------------------------------------------------------------


async def planner_node(state: AgentState) -> dict:
    """Classify user intent and generate a tool execution plan."""
    # Extract latest user message
    message = ""
    for msg in reversed(state["messages"]):
        if hasattr(msg, "type") and msg.type == "human":
            message = msg.content
            break
        if hasattr(msg, "role") and msg.role == "user":
            message = msg.content
            break
    if not message:
        message = str(state["messages"][-1].content) if state["messages"] else ""

    history = state.get("conversation_history") or []
    district_code = state.get("district_code", "")
    district_name = state.get("district_name", "")

    # 1. Rule-based classification
    intent, confidence = _classify_by_rules(message)

    referenced_districts: list[str] = [district_code] if district_code else []
    referenced_category = _extract_category(message)

    # 2. LLM classification for follow_up / ambiguous / low confidence
    if intent in ("follow_up", None) or confidence < 0.7:
        history_text = ""
        if history:
            from server.agent.history import ConversationHistory

            h = ConversationHistory()
            h.turns = list(history)
            history_text = h.format_for_planner()

        llm_result = await _classify_with_llm(message, history_text, district_code, district_name)
        intent = llm_result.get("intent", intent or "summary")
        confidence = llm_result.get("confidence", 0.7)
        llm_districts = llm_result.get("referenced_districts") or []
        if llm_districts:
            referenced_districts = llm_districts
        if llm_result.get("referenced_category"):
            referenced_category = llm_result["referenced_category"]

    # Ensure we have at least the current district
    if not referenced_districts and district_code:
        referenced_districts = [district_code]

    # For comparison, ensure at least 2 districts
    if intent == "comparison" and len(referenced_districts) < 2 and district_code:
        if district_code not in referenced_districts:
            referenced_districts.insert(0, district_code)

    # 3. Build plan
    plan = _build_plan(intent, district_code, referenced_districts, referenced_category)

    # 4. Determine response mode
    response_mode = "direct" if intent in ("general", "ambiguous") or not plan else "tool_assisted"

    # If no district selected and tool-assisted → ambiguous
    if response_mode == "tool_assisted" and not district_code:
        intent = "ambiguous"
        plan = []
        response_mode = "direct"

    return {
        "user_intent": intent,
        "intent_confidence": confidence,
        "referenced_districts": referenced_districts,
        "referenced_category": referenced_category,
        "plan": plan,
        "plan_reasoning": f"의도: {intent}, 계획: {len(plan)}개 도구 호출",
        "response_mode": response_mode,
        "execution_round": (state.get("execution_round") or 0) + 1,
    }
