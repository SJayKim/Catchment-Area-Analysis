"""Shared pytest fixtures — Plan: docs/plan/infra/backend-pytest-coverage-expansion.md.

USE_MOCK is forced to ``true`` for this whole test session so import-time
side effects (Anthropic/Gemini SDK key validation, DB pool init) stay quiet.
Tests that need a real DB use the ``@pytest.mark.real`` marker (currently
unused — placeholder for future integration tests).
"""

from __future__ import annotations

import os

# Must run before server.* imports
os.environ.setdefault("USE_MOCK", "true")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
# Dummy keys so config.py doesn't validate against live services
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-dummy")
os.environ.setdefault("GOOGLE_API_KEY", "test-dummy")
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "")
os.environ.setdefault("SEOUL_OPENDATA_API_KEY", "test-dummy")

import pytest
import pytest_asyncio


@pytest.fixture
def mock_district_code() -> str:
    """Stable Mock district code (강남역). Avoids hard-coding throughout tests."""
    return "D3001"


@pytest.fixture
def mock_da():
    """Fresh Mock DataAccess instance per test."""
    from server.repositories.mock.factory import build_mock_data_access

    return build_mock_data_access()


@pytest.fixture
def memory_cache():
    """Fresh in-process Memory cache per test."""
    from server.services.cache import MemoryCacheService

    return MemoryCacheService()


@pytest.fixture
def category_resolver_default():
    """CategoryResolver pre-loaded with built-in Korean keyword defaults."""
    from server.services.category_resolver import CategoryResolver

    r = CategoryResolver()
    r.load_defaults()
    return r


@pytest_asyncio.fixture
async def app_client():
    """httpx AsyncClient bound to the FastAPI app via ASGI transport.

    Manually drives FastAPI lifespan (cache + DataAccess + CategoryResolver
    init in mock mode) before the client yields, since ASGITransport does
    not run lifespan automatically.

    Skips when optional deps (structlog, slowapi, etc.) are missing — this
    keeps the lightweight unit suite (cache/CB/resolver/repos/sanitizers)
    runnable without ``pip install -e ".[dev]"``.
    """
    try:
        from httpx import ASGITransport, AsyncClient

        from server.main import app
    except ModuleNotFoundError as e:
        pytest.skip(f"app_client requires full server deps (missing: {e.name})")

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
