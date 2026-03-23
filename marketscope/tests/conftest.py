"""Pytest 공통 fixture."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from marketscope_common.config import Settings
from marketscope_common.models.state import create_initial_state


@pytest.fixture
def event_loop():
    """asyncio 이벤트 루프."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Settings 인스턴스 (기본값, .env 로드 없음)."""
    return Settings(
        _env_file=None,
        app_name="MarketScope AI Test",
        app_env="development",
        google_api_key="test-google-key",
        postgres_password="test-pw",
    )


@pytest.fixture
def mock_mcp_client():
    """MCP 클라이언트 AsyncMock."""
    client = AsyncMock()
    client.call_tool = AsyncMock(return_value={"status": "ok", "data": {}})
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_llm_provider():
    """LLM Provider AsyncMock."""
    from marketscope_agent.llm.provider import LLMResponse

    provider = AsyncMock()
    provider.completion = AsyncMock(
        return_value=LLMResponse(
            content='{"summary": "test", "confidence_score": 0.8}',
            model="test-model",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            latency_ms=500.0,
        )
    )
    return provider


@pytest.fixture
def sample_state():
    """기본 State (강남역 카페 분석)."""
    return create_initial_state("test-session-001", "강남역 카페 창업 분석")


@pytest.fixture
def sample_state_with_results(sample_state):
    """에이전트 결과가 포함된 State."""
    sample_state["commander_plan"] = {
        "analysis_mode": "basic",
        "target_location": "강남역",
        "target_industry": "카페",
        "clarification_needed": False,
    }
    sample_state["population_result"] = {
        "confidence_score": 0.75,
        "summary": "유동인구 높음",
    }
    sample_state["competition_result"] = {
        "confidence_score": 0.70,
        "summary": "경쟁 적당",
    }
    sample_state["revenue_result"] = {
        "confidence_score": 0.65,
        "estimated_revenue": 10000000,
        "revenue_lower_bound": 8500000,
        "revenue_upper_bound": 11500000,  # variance = 30% (경계값 이하)
        "summary": "매출 추정",
    }
    sample_state["location_result"] = {
        "confidence_score": 0.80,
        "summary": "교통 편리",
    }
    return sample_state
