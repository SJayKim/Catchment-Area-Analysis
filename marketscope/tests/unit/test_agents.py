"""에이전트 단위 테스트."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.base import BaseAgent
from app.exceptions import LLMCallError, MCPToolCallError
from app.llm.provider import LLMResponse


@pytest.mark.asyncio
class TestBaseAgentCallTool:
    async def test_call_tool_success(self, mock_settings, mock_mcp_client):
        """MCP 도구 호출 성공 케이스."""
        from app.agents.population import PopulationAgent

        agent = PopulationAgent(
            settings=mock_settings,
            mcp_client=mock_mcp_client,
        )
        result = await agent.call_tool("maps.geocode", {"address": "강남역"})
        mock_mcp_client.call_tool.assert_called_once_with("maps.geocode", {"address": "강남역"})
        assert result == {"status": "ok", "data": {}}

    async def test_call_tool_no_client_returns_empty(self, mock_settings):
        """MCP 클라이언트 없을 때 빈 dict 반환."""
        from app.agents.population import PopulationAgent

        agent = PopulationAgent(settings=mock_settings, mcp_client=None)
        result = await agent.call_tool("maps.geocode", {"address": "강남역"})
        assert result == {}

    async def test_call_tool_timeout(self, mock_settings, mock_mcp_client):
        """MCP 타임아웃 시 MCPToolCallError."""
        from app.agents.population import PopulationAgent

        mock_mcp_client.call_tool = AsyncMock(side_effect=asyncio.TimeoutError)
        agent = PopulationAgent(
            settings=mock_settings,
            mcp_client=mock_mcp_client,
        )
        with pytest.raises(MCPToolCallError):
            await agent.call_tool("maps.geocode", {"address": "강남역"}, timeout=1)

    async def test_call_tool_exception(self, mock_settings, mock_mcp_client):
        """MCP 일반 에러 시 MCPToolCallError."""
        from app.agents.population import PopulationAgent

        mock_mcp_client.call_tool = AsyncMock(side_effect=ConnectionError("refused"))
        agent = PopulationAgent(
            settings=mock_settings,
            mcp_client=mock_mcp_client,
        )
        with pytest.raises(MCPToolCallError):
            await agent.call_tool("maps.geocode", {"address": "강남역"})


@pytest.mark.asyncio
class TestBaseAgentCallLLM:
    async def test_call_llm_success(self, mock_settings, mock_llm_provider):
        """LLM 호출 성공 케이스."""
        from app.agents.population import PopulationAgent

        agent = PopulationAgent(
            settings=mock_settings,
            mcp_client=None,
            llm_provider=mock_llm_provider,
        )
        result = await agent.call_llm(
            system_prompt="You are an analyst.",
            user_prompt="Analyze population.",
        )
        assert result["content"] is not None
        assert result["model"] == "test-model"
        assert result["latency_ms"] == 500.0

    async def test_call_llm_retry_on_failure(self, mock_settings):
        """LLM 첫 호출 실패 → 재시도 → 성공."""
        from app.agents.population import PopulationAgent

        provider = AsyncMock()
        provider.completion = AsyncMock(
            side_effect=[
                Exception("temporary error"),
                LLMResponse(
                    content="success",
                    model="test-model",
                    usage={"prompt_tokens": 10, "completion_tokens": 5},
                    latency_ms=100.0,
                ),
            ]
        )
        agent = PopulationAgent(
            settings=mock_settings,
            mcp_client=None,
            llm_provider=provider,
        )
        agent.retry_base_delay = 0.01  # 테스트 빠르게

        result = await agent.call_llm(
            system_prompt="test",
            user_prompt="test",
        )
        assert result["content"] == "success"
        assert provider.completion.call_count == 2

    async def test_call_llm_all_retries_fail(self, mock_settings):
        """LLM 모든 재시도 실패 → LLMCallError."""
        from app.agents.population import PopulationAgent

        provider = AsyncMock()
        provider.completion = AsyncMock(side_effect=Exception("persistent error"))
        agent = PopulationAgent(
            settings=mock_settings,
            mcp_client=None,
            llm_provider=provider,
        )
        agent.max_retries = 1
        agent.retry_base_delay = 0.01

        with pytest.raises(LLMCallError):
            await agent.call_llm(system_prompt="test", user_prompt="test")
        # max_retries=1 → 총 2번 시도
        assert provider.completion.call_count == 2


@pytest.mark.asyncio
class TestBaseAgentCallToolsParallel:
    async def test_parallel_success(self, mock_settings, mock_mcp_client):
        """병렬 도구 호출 성공."""
        from app.agents.population import PopulationAgent

        call_count = 0

        async def fake_call_tool(name, args):
            nonlocal call_count
            call_count += 1
            return {"tool": name, "idx": call_count}

        mock_mcp_client.call_tool = fake_call_tool
        agent = PopulationAgent(
            settings=mock_settings,
            mcp_client=mock_mcp_client,
        )
        results = await agent.call_tools_parallel([
            {"tool_name": "public_data.get_a", "arguments": {}},
            {"tool_name": "public_data.get_b", "arguments": {}},
            {"tool_name": "public_data.get_c", "arguments": {}},
        ])
        assert len(results) == 3
        assert all("_error" not in r for r in results)

    async def test_parallel_partial_failure(self, mock_settings, mock_mcp_client):
        """병렬 호출 중 일부 실패 → 에러 dict 포함."""
        from app.agents.population import PopulationAgent

        call_idx = 0

        async def flaky_call_tool(name, args):
            nonlocal call_idx
            call_idx += 1
            if call_idx == 2:
                raise ConnectionError("server down")
            return {"tool": name}

        mock_mcp_client.call_tool = flaky_call_tool
        agent = PopulationAgent(
            settings=mock_settings,
            mcp_client=mock_mcp_client,
        )
        results = await agent.call_tools_parallel([
            {"tool_name": "tool_a", "arguments": {}},
            {"tool_name": "tool_b", "arguments": {}},
            {"tool_name": "tool_c", "arguments": {}},
        ])
        assert len(results) == 3
        # 2번째가 실패
        errors = [r for r in results if "_error" in r]
        assert len(errors) == 1


class TestConfidenceCalculation:
    def test_perfect_scores(self, mock_settings):
        from app.agents.population import PopulationAgent

        agent = PopulationAgent(settings=mock_settings, mcp_client=None)
        score = agent.calculate_confidence(
            data_completeness=1.0,
            data_freshness=1.0,
            source_count=5,
            cross_validation_score=1.0,
        )
        assert score == 1.0

    def test_zero_scores(self, mock_settings):
        from app.agents.population import PopulationAgent

        agent = PopulationAgent(settings=mock_settings, mcp_client=None)
        score = agent.calculate_confidence(
            data_completeness=0.0,
            data_freshness=0.0,
            source_count=0,
            cross_validation_score=0.0,
        )
        assert score == 0.0

    def test_clamped_to_range(self, mock_settings):
        from app.agents.population import PopulationAgent

        agent = PopulationAgent(settings=mock_settings, mcp_client=None)
        score = agent.calculate_confidence(
            data_completeness=1.5,
            data_freshness=1.5,
            source_count=100,
            cross_validation_score=1.5,
        )
        assert score <= 1.0
