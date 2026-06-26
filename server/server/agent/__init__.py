"""Agent package — SSE runner dispatch.

`get_runner(mode)` selects the streaming agent implementation by `agent_mode`:
- "pae"     → LangGraph Planner-Actor-Evaluator (`graph.run_agent`)
- "agentic" → native AsyncAnthropic tool-use loop (`loop.runner.run_agentic`, wired in P2)

Both share the same call signature and yield the same 9-event SSE dict stream,
so `chat.py` dispatches through here without knowing which is active.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import Any


def get_runner(mode: str) -> Callable[..., AsyncGenerator[dict[str, Any], None]]:
    """Return the streaming agent runner for the given agent_mode."""
    if mode == "agentic":
        from server.agent.loop.runner import run_agentic  # wired in P2

        return run_agentic

    from server.agent.graph import run_agent

    return run_agent
