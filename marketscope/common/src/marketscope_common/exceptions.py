"""MarketScope AI 커스텀 예외 클래스."""

from __future__ import annotations

from typing import Any, Optional


class MarketScopeError(Exception):
    """MarketScope AI 기본 예외."""
    def __init__(self, message: str = "", **kwargs: Any) -> None:
        self.message = message
        self.details = kwargs
        super().__init__(message)


class AgentExecutionError(MarketScopeError):
    """에이전트 실행 중 발생하는 에러."""
    def __init__(
        self,
        agent_name: str,
        message: str = "",
        original_error: Optional[Exception] = None,
        is_critical: bool = False,
    ) -> None:
        self.agent_name = agent_name
        self.original_error = original_error
        self.is_critical = is_critical
        super().__init__(f"[{agent_name}] {message}")


class AgentTimeoutError(MarketScopeError):
    """에이전트 타임아웃."""
    def __init__(self, agent_name: str, timeout_seconds: int) -> None:
        self.agent_name = agent_name
        self.timeout_seconds = timeout_seconds
        super().__init__(f"[{agent_name}] {timeout_seconds}초 타임아웃 초과")


class LLMCallError(MarketScopeError):
    """LLM 호출 실패."""
    def __init__(
        self,
        agent_name: str,
        model: str,
        original_error: Optional[Exception] = None,
        attempts: int = 0,
    ) -> None:
        self.agent_name = agent_name
        self.model = model
        self.original_error = original_error
        self.attempts = attempts
        super().__init__(f"[{agent_name}] LLM({model}) 호출 실패 ({attempts}회 시도)")


class DataCollectionError(MarketScopeError):
    """MCP/외부 데이터 수집 실패."""
    def __init__(
        self,
        agent_name: str,
        source: str,
        message: str = "",
        original_error: Optional[Exception] = None,
    ) -> None:
        self.agent_name = agent_name
        self.source = source
        self.original_error = original_error
        super().__init__(f"[{agent_name}] 데이터 수집 실패 ({source}): {message}")


class MCPToolCallError(MarketScopeError):
    """MCP 도구 호출 실패."""
    def __init__(
        self,
        agent_name: str,
        tool_name: str,
        message: str = "",
        original_error: Optional[Exception] = None,
    ) -> None:
        self.agent_name = agent_name
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f"[{agent_name}] MCP 도구 '{tool_name}' 호출 실패: {message}")


class OutputParsingError(MarketScopeError):
    """LLM 출력 파싱 실패."""
    def __init__(
        self,
        agent_name: str,
        model_class: str,
        raw_content: str = "",
    ) -> None:
        self.agent_name = agent_name
        self.model_class = model_class
        self.raw_content = raw_content
        super().__init__(f"[{agent_name}] {model_class} 파싱 실패")


class AnalysisNotFoundError(MarketScopeError):
    """분석 결과를 찾을 수 없음."""
    pass


class RateLimitExceededError(MarketScopeError):
    """요율 제한 초과."""
    pass
