"""Proactive suggestions for the agentic loop — reuses the PAE evaluator logic.

Wraps `evaluator.generate_proactive_suggestions` with a synthesized state dict so
the agentic and PAE paths emit identical per-intent suggestion sets.
"""

from __future__ import annotations

from typing import Any

from server.agent.nodes.evaluator import generate_proactive_suggestions


def build_suggestions(
    *,
    intent: str,
    district_name: str | None,
    tool_results: dict[str, Any],
    referenced_category: str | None = None,
) -> list[str]:
    state: dict[str, Any] = {
        "user_intent": intent,
        "district_name": district_name or "여기",
        "tool_results": tool_results or {},
        "referenced_category": referenced_category,
    }
    return generate_proactive_suggestions(state)  # type: ignore[arg-type]
