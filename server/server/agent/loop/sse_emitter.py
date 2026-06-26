"""SSE event builders — single chokepoint for the 9-event contract.

Shapes copied verbatim from the legacy actor.py / graph.py emitters so the
frontend (types.ts / eventHandlers.ts) sees an identical stream regardless of
agent_mode. No `icon` key — actor.py never emits one.
"""

from __future__ import annotations

from typing import Any


def thinking(step: str) -> dict[str, Any]:
    return {"type": "thinking", "step": step}


def plan(intent: str, steps: list[str]) -> dict[str, Any]:
    return {"type": "plan", "intent": intent, "steps": steps}


def tool(name: str, tool_input: dict[str, Any], progress_label: str | None) -> dict[str, Any]:
    return {"type": "tool", "name": name, "input": tool_input, "progress_label": progress_label}


def tool_end(name: str, done_label: str | None) -> dict[str, Any]:
    return {"type": "tool_end", "name": name, "done_label": done_label}


def text(content: str) -> dict[str, Any]:
    return {"type": "text", "content": content}


def card(card_type: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"type": "card", "card_type": card_type, "data": data}


def suggestion(questions: list[str]) -> dict[str, Any]:
    return {"type": "suggestion", "questions": questions}


# Note: `map_cmd` is emitted by chat.py (identically for both runners) before the
# runner starts, so the loop never builds it — no builder here to avoid a partial-
# shape trap (chat.py's map_cmd carries district_code/name/type that eventHandlers reads).
