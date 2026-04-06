"""Planner node — intent classification + tool plan generation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from server.agent.config.intent_loader import load_intent_config
from server.agent.prompts.planner import PLANNER_CLASSIFICATION_PROMPT
from server.agent.state import AgentState, ToolPlanStep

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _classify_by_rules(message: str) -> tuple[str | None, float]:
    """Fast rule-based intent classification. Returns (intent, confidence)."""
    config = load_intent_config()

    # Follow-up markers → need LLM
    if config.follow_up_markers.search(message):
        return "follow_up", 0.5

    # Non-summary overrides first
    if config.non_summary_overrides.search(message):
        # Find which specific intent matches
        for intent, pattern in config.patterns.items():
            if intent == "summary":
                continue
            if pattern.search(message):
                return intent, 0.9
        return None, 0.0

    # Single-pattern match
    matched: list[str] = []
    for intent, pattern in config.patterns.items():
        if pattern.search(message):
            matched.append(intent)

    if len(matched) == 1:
        return matched[0], 0.9
    if len(matched) > 1:
        return None, 0.4  # ambiguous → LLM

    return None, 0.0  # no match → LLM


def _extract_category(message: str) -> str | None:
    """Extract category_code from message keywords."""
    from server.services.category_resolver import get_category_resolver

    return get_category_resolver().resolve(message)


def _extract_category_name(message: str) -> str | None:
    """Extract the category keyword itself for display."""
    from server.services.category_resolver import get_category_resolver

    return get_category_resolver().resolve_name(message)


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
    config = load_intent_config()
    templates = config.plans.get(intent, [])
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
