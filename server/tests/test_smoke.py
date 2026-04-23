"""Smoke tests — verify the package imports and core primitives work.

These are intentionally lightweight (no DB/Redis/LLM) so they run under
USE_MOCK=true in CI. They bootstrap the pytest infrastructure and catch
basic import/regression failures until the dedicated test suites land.
"""

from __future__ import annotations

import pytest


def test_settings_loads_with_mock_defaults() -> None:
    from server.config import Settings

    settings = Settings(use_mock=True)

    assert settings.use_mock is True
    assert settings.agent_mode == "pae"
    assert settings.agent_max_rounds >= 1
    assert settings.langfuse_enabled is False


def test_tool_registry_discovers_tools() -> None:
    from server.agent.tools.registry import get_tool_registry

    registry = get_tool_registry()

    assert "get_district_summary" in registry
    assert "compare_districts" in registry
    assert registry["get_district_summary"].card_type is not None


@pytest.mark.asyncio
async def test_memory_cache_roundtrip() -> None:
    from server.services.cache import MemoryCacheService

    cache = MemoryCacheService()

    assert await cache.get("missing") is None

    await cache.set("k", {"v": 1})
    assert await cache.get("k") == {"v": 1}

    await cache.delete("k")
    assert await cache.get("k") is None
