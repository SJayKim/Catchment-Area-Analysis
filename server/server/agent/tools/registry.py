"""Tool registry — centralizes tool metadata (emoji, card type, labels).

Each tool file uses @register_tool to self-register its metadata.
actor.py and graph.py consume the registry instead of maintaining
duplicate mappings.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolMeta:
    """Metadata for a single tool."""

    name: str
    fn: Callable[..., Any]
    card_type: str | None
    progress_label: str
    done_label: str
    description: str
    # Agentic loop (agent_mode="agentic") — additive; ignored by the legacy actor.
    # input_schema: JSON Schema for the Anthropic tools param.
    # llm_description: curated LLM-facing description (vs `description` = fn.__doc__).
    input_schema: dict[str, Any] | None = None
    llm_description: str = ""


_REGISTRY: dict[str, ToolMeta] = {}


def register_tool(
    name: str,
    *,
    emoji: str = "",
    card_type: str | None = None,
    progress_label: str = "",
    done_label: str = "",
    input_schema: dict[str, Any] | None = None,
    llm_description: str = "",
):
    """Decorator that registers a tool function with its metadata."""

    def decorator(fn: Callable) -> Callable:
        _REGISTRY[name] = ToolMeta(
            name=name,
            fn=fn,
            card_type=card_type,
            progress_label=progress_label or f"{name} 실행 중...",
            done_label=done_label or f"{name} 완료",
            description=fn.__doc__ or "",
            input_schema=input_schema,
            llm_description=llm_description,
        )
        return fn

    return decorator


def get_tool_registry() -> dict[str, ToolMeta]:
    """Return the tool registry, discovering tools on first access."""
    if not _REGISTRY:
        _discover_tools()
    return _REGISTRY


def _discover_tools() -> None:
    """Import all tool modules to trigger @register_tool decorators."""
    from server.agent.tools import (  # noqa: F401
        compare_districts,
        district_summary,
        estimated_sales,
        floating_population,
        population_info,
        recommend_business,
        simulate_revenue,
        store_history,
        store_info,
    )
