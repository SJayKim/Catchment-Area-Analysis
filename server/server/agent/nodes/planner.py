"""Planner node — intent classification + tool plan generation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from server.agent.config.intent_loader import load_intent_config
from server.agent.prompts.planner import PLANNER_CLASSIFICATION_PROMPT
from server.agent.prompts.system import sanitize_prompt_value
from server.agent.state import AgentState, ToolPlanStep
from server.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _matches_excluded(name: str, excluded_tokens: list[str]) -> bool:
    """Return True when a district name should be dropped due to an exclusion
    token surfaced by the rewriter (``"홍대 말고 성수"`` → excludes "홍대")."""
    if not name or not excluded_tokens:
        return False
    for token in excluded_tokens:
        if not token:
            continue
        if token in name or name in token:
            return True
    return False


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


def _rule_fallback_result(message: str, district_code: str) -> dict:
    """Rule-based fallback shared by LLM failure/parse-fail paths.

    Reuses _classify_by_rules so LLM timeouts/parse errors don't silently
    degrade to "summary" for every query (e.g. risk / comparison).
    """
    rule_intent, rule_conf = _classify_by_rules(message)
    intent = rule_intent or "general"
    return {
        "intent": intent,
        "confidence": rule_conf if rule_intent else 0.4,
        "referenced_districts": [district_code] if district_code else [],
        "referenced_category": None,
    }


async def _classify_with_llm(
    message: str,
    history_text: str,
    district_code: str,
    district_name: str,
) -> dict:
    """LLM-based intent classification for ambiguous cases."""
    from server.agent.graph import _create_llm, invoke_llm_with_retry
    from server.services.circuit_breaker import CircuitOpenError

    prompt = PLANNER_CLASSIFICATION_PROMPT.format(
        message=sanitize_prompt_value(message),
        history=history_text or "(없음)",
        district_code=sanitize_prompt_value(district_code or "(미선택)"),
        district_name=sanitize_prompt_value(district_name or "(미선택)"),
    )

    llm = _create_llm(role="planner")
    try:
        response = await invoke_llm_with_retry(llm, prompt, timeout=settings.llm_timeout_fast)
        content = response.content if hasattr(response, "content") else str(response)
        if isinstance(content, list):
            content = "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
        # Extract JSON from response
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        logger.warning("LLM classification returned no JSON, using rule fallback")
    except CircuitOpenError:
        logger.warning("LLM circuit breaker is OPEN, using rule fallback for planner")
    except TimeoutError:
        logger.warning(
            "LLM classification timed out after %.1fs, using rule fallback",
            settings.llm_timeout_fast,
        )
    except Exception as exc:
        logger.warning("LLM classification failed, falling back to rules", exc_info=True)
        # Disable Anthropic for future calls if the key is invalid
        if "AuthenticationError" in type(exc).__name__ or "authentication" in str(exc).lower():
            import server.agent.graph as _graph_mod

            _graph_mod._anthropic_valid = False
            logger.warning("Anthropic API key invalid — disabled for this session")

    return _rule_fallback_result(message, district_code)


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

    # GAP-E / GAP-C: pre-Planner rewrite. Rule-first so the happy path is free.
    # Falls back to a Gemini flash rewrite (~200ms) only when coreference
    # tokens remain unresolved.
    from server.agent.utils.rewriter import (
        llm_rewrite_message,
        rule_rewrite,
    )

    rewrite = rule_rewrite(
        message,
        history=history,
        current_district_code=district_code or None,
        current_district_name=district_name or None,
    )
    if rewrite.needs_llm_fallback:
        try:
            from server.agent.history import ConversationHistory

            h = ConversationHistory()
            h.turns = list(history)
            history_text = h.format_for_planner() if history else ""
        except Exception:
            history_text = ""
        llm_rw = await llm_rewrite_message(
            message=message,
            history_text=history_text,
            district_name=district_name,
        )
        if llm_rw:
            rewrite.rewritten = llm_rw["rewritten"]
            if llm_rw.get("anchor_district_name"):
                rewrite.anchor_district_name = llm_rw["anchor_district_name"]
            if llm_rw.get("anchor_category"):
                rewrite.anchor_category = llm_rw["anchor_category"]

    if rewrite.rewritten != message or rewrite.excluded_tokens:
        logger.info(
            "planner.rewrite session=%s raw=%r → %r (anchor=%s, excluded=%s)",
            state.get("session_id"),
            message,
            rewrite.rewritten,
            rewrite.anchor_district_name,
            rewrite.excluded_tokens,
        )
    message = rewrite.rewritten

    # GAP-C: if the pre-selected district (usually auto-detected by chat.py
    # from the *original* message) collides with an exclusion token, drop it.
    # Without this, "홍대 말고 성수로" auto-picks "홍대입구역(홍대)" upstream and
    # the comparison still ends up with 홍대 ∪ 성수.
    if rewrite.excluded_tokens and _matches_excluded(district_name, rewrite.excluded_tokens):
        logger.info(
            "planner.exclude-anchor dropping auto-detected district %s (%s)",
            district_code,
            district_name,
        )
        district_code = ""
        district_name = ""

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

    # For comparison, run a deterministic multi-district extraction over the
    # message. The rule classifier returns confidence 0.9 (skips LLM), so the
    # initial referenced_districts only contains the explicitly selected one.
    # detect_districts_in_message scans every district name in the message
    # (with Korean particle stripping + stopwords), enabling queries like
    # "강남역과 홍대입구를 비교해줘" to populate both codes.
    ambiguous_districts: list[dict] = []
    if intent == "comparison":
        try:
            from server.repositories import get_data_access

            multi = await get_data_access().districts.detect_districts_in_message(message)
        except Exception:
            logger.warning("detect_districts_in_message failed", exc_info=True)
            multi = []

        # GAP-C: honour rewriter-detected exclusion tokens ("홍대 말고 성수"). We
        # drop any candidate whose matched name contains (or is contained by)
        # the excluded token.
        if rewrite.excluded_tokens:
            before = len(multi)
            multi = [m for m in multi if not _matches_excluded(m.get("name", ""), rewrite.excluded_tokens)]
            if len(multi) != before:
                logger.info(
                    "planner.exclude session=%s dropped=%d via tokens=%s",
                    state.get("session_id"),
                    before - len(multi),
                    rewrite.excluded_tokens,
                )

        if multi:
            multi_codes = [m["code"] for m in multi]
            # Priority: explicit selection first, then message-discovered
            if district_code and district_code not in multi_codes:
                multi_codes.insert(0, district_code)
            referenced_districts = multi_codes[:3]  # CompareCard caps at 3

            # GAP-A: capture ambiguous entries so Actor can emit a choice card.
            ambiguous_districts = [
                {
                    "top": {"code": m["code"], "name": m.get("name"), "score": m.get("score")},
                    "alternatives": m.get("alternatives") or [],
                }
                for m in multi
                if m.get("ambiguous")
            ]
        elif len(referenced_districts) < 2 and district_code:
            if district_code not in referenced_districts:
                referenced_districts.insert(0, district_code)

    # 3. Greeting → skip entire agent pipeline (no LLM call needed)
    if intent == "greeting":
        return {
            "user_intent": "greeting",
            "intent_confidence": 1.0,
            "referenced_districts": [],
            "referenced_category": None,
            "plan": [],
            "plan_reasoning": "인사 → Agent 파이프라인 스킵",
            "response_mode": "greeting_direct",
            "execution_round": 0,
        }

    # 4. Build plan
    plan = _build_plan(intent, district_code, referenced_districts, referenced_category)

    # 5. Determine response mode
    response_mode = "direct" if intent in ("general", "ambiguous") or not plan else "tool_assisted"

    # If no district selected and tool-assisted → ambiguous. Comparison is
    # exempt when the planner already discovered 2+ districts from the
    # message (e.g. GAP-C "홍대 말고 성수역이랑 건대 비교" — the map pre-selection
    # is dropped but the comparison targets are well-defined).
    if response_mode == "tool_assisted" and not district_code:
        if intent == "comparison" and len(referenced_districts) >= 2:
            pass  # plan is valid without an explicit map-selected district
        else:
            intent = "ambiguous"
            plan = []
            response_mode = "direct"

    logger.info(
        "planner.final session=%s intent=%s district=%s refs=%s plan_size=%d mode=%s",
        state.get("session_id"),
        intent,
        district_code,
        referenced_districts,
        len(plan),
        response_mode,
    )
    # Propagate excludeAnchor drops so Respond-side context does not leak the
    # pre-selected district back into the prompt ("## 현재 컨텍스트 - 상권: 홍대
    # (홍대입구역)").
    out: dict = {
        "user_intent": intent,
        "intent_confidence": confidence,
        "referenced_districts": referenced_districts,
        "referenced_category": referenced_category,
        "ambiguous_districts": ambiguous_districts,
        "plan": plan,
        "plan_reasoning": f"의도: {intent}, 계획: {len(plan)}개 도구 호출",
        "response_mode": response_mode,
        "execution_round": (state.get("execution_round") or 0) + 1,
    }
    if not district_code and state.get("district_code"):
        out["district_code"] = ""
        out["district_name"] = ""
    return out
