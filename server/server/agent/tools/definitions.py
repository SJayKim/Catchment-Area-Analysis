"""Build the Anthropic `tools` definitions from the registry + schemas.

Tool defs are emitted sorted by name so the prompt-cache (tools block) stays
stable across requests. Source of truth: TOOL_SCHEMAS for the 9 legacy tools;
a new tool may instead register via register_tool(input_schema=..., llm_description=...).
"""

from __future__ import annotations

from typing import Any

from server.agent.tools.registry import get_tool_registry
from server.agent.tools.schemas import TOOL_SCHEMAS


def build_tool_definitions() -> list[dict[str, Any]]:
    """Return Anthropic tool definitions (name/description/input_schema), sorted by name."""
    reg = get_tool_registry()
    defs: list[dict[str, Any]] = []
    for name in sorted(reg):
        meta = reg[name]
        schema = TOOL_SCHEMAS.get(name)
        input_schema = meta.input_schema or (schema["input_schema"] if schema else None)
        if input_schema is None:
            continue  # tool not yet schema-migrated → not exposed to the LLM
        description = meta.llm_description or (schema["description"] if schema else "") or meta.description
        defs.append({"name": name, "description": description, "input_schema": input_schema})
    return defs
