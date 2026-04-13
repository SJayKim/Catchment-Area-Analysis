"""Actor node — executes tool plan without LLM calls."""

from __future__ import annotations

import asyncio
import logging

from server.agent.state import AgentState, ToolPlanStep
from server.agent.tools.data_sources import get_sources_for_tool
from server.agent.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependency layer grouping
# ---------------------------------------------------------------------------


def group_by_dependencies(plan: list[ToolPlanStep]) -> list[list[ToolPlanStep]]:
    """Split plan steps into layers that can execute in parallel."""
    if not plan:
        return []

    layers: list[list[ToolPlanStep]] = []
    resolved: set[int] = set()

    while len(resolved) < len(plan):
        current_layer: list[ToolPlanStep] = []
        for i, step in enumerate(plan):
            if i in resolved:
                continue
            if all(dep in resolved for dep in step["depends_on"]):
                current_layer.append(step)

        if not current_layer:
            # Circular dependency safety: flush remaining
            for i, step in enumerate(plan):
                if i not in resolved:
                    current_layer.append(step)
            resolved.update(range(len(plan)))
        else:
            for step in current_layer:
                resolved.add(plan.index(step))

        layers.append(current_layer)

    return layers


# ---------------------------------------------------------------------------
# Single tool execution
# ---------------------------------------------------------------------------


async def execute_tool(step: ToolPlanStep) -> tuple[str, dict | None, str | None]:
    """Execute one tool. Returns (tool_name, result_dict, error_str)."""
    reg = get_tool_registry()
    meta = reg.get(step["tool_name"])
    if not meta:
        return step["tool_name"], None, f"Unknown tool: {step['tool_name']}"

    try:
        # Filter out None args
        args = {k: v for k, v in step["args"].items() if v is not None}
        result = await meta.fn(**args)

        if isinstance(result, dict) and "error" in result:
            return step["tool_name"], result, result["error"]
        return step["tool_name"], result, None
    except Exception as exc:
        logger.warning("Tool %s failed: %s", step["tool_name"], exc, exc_info=True)
        return step["tool_name"], None, str(exc)


# ---------------------------------------------------------------------------
# Actor node
# ---------------------------------------------------------------------------


async def actor_node(
    state: AgentState,
    event_queue: asyncio.Queue | None = None,
) -> dict:
    """Execute all planned tools. No LLM calls."""
    reg = get_tool_registry()
    tool_results: dict[str, dict] = dict(state.get("tool_results") or {})
    tool_errors: dict[str, str] = dict(state.get("tool_errors") or {})
    card_emissions: list[dict] = list(state.get("card_emissions") or [])

    layers = group_by_dependencies(state.get("plan") or [])

    for layer in layers:
        # Emit tool-start events
        for step in layer:
            meta = reg.get(step["tool_name"])
            if event_queue:
                await event_queue.put(
                    {
                        "type": "tool",
                        "name": step["tool_name"],
                        "input": step["args"],
                                                "progress_label": meta.progress_label if meta else None,
                    }
                )

        # Parallel execution within layer
        results = await asyncio.gather(
            *[execute_tool(step) for step in layer],
            return_exceptions=True,
        )

        for step, result in zip(layer, results):
            if isinstance(result, BaseException):
                tool_errors[step["tool_name"]] = str(result)
                name = step["tool_name"]
                data = None
            else:
                name, data, error = result
                if error:
                    tool_errors[name] = error
                if data:
                    tool_results[name] = data

            meta = reg.get(step["tool_name"])
            # tool_end event
            if event_queue:
                await event_queue.put(
                    {
                        "type": "tool_end",
                        "name": step["tool_name"],
                                                "done_label": meta.done_label if meta else None,
                    }
                )

            # Card emission (skip if tool returned an error)
            card_type = meta.card_type if meta else None
            if card_type and step["tool_name"] in tool_results:
                card_data = tool_results[step["tool_name"]]
                if "error" not in card_data:
                    card_copy = dict(card_data)
                    sources = get_sources_for_tool(step["tool_name"])
                    if sources:
                        card_copy["dataSources"] = sources
                    card_emissions.append({"card_type": card_type, "data": card_copy})

    return {
        "tool_results": tool_results,
        "tool_errors": tool_errors,
        "card_emissions": card_emissions,
    }
