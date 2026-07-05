"""Agent runtime dispatch — selects the v2 model-driven loop or the legacy
PAE graph, preserving a single ``run_agent`` entry point for chat.py.

v2 requires a real LLM provider (the mock FakeListChatModel can't tool-call),
so mock mode always falls back to PAE — keeping mock e2e tests green.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from server.config import settings


def _use_v2() -> bool:
    return settings.agent_loop_version == "v2" and settings.llm_provider != "mock"


def effective_loop_version() -> str:
    """The loop actually serving requests ("v2" | "pae").

    Differs from ``settings.agent_loop_version`` when the mock provider
    forces the PAE fallback — observability must report this value, not
    the raw setting.
    """
    return "v2" if _use_v2() else "pae"


async def run_agent(*args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
    if _use_v2():
        from server.agent.loop.engine import run_agent as _impl
    else:
        from server.agent.graph import run_agent as _impl
    async for event in _impl(*args, **kwargs):
        yield event
