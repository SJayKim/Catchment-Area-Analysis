"""BaseAgent 추상 클래스 - 모든 에이전트의 공통 기반."""

from __future__ import annotations

import asyncio
import json
import re
import traceback
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Generic, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.constants import ConfidenceLevel
from app.exceptions import (
    AgentExecutionError,
    LLMCallError,
    MCPToolCallError,
    OutputParsingError,
)
from app.llm.provider import LLMProvider, LLMResponse
from app.logging_config import get_agent_logger

T = TypeVar("T", bound=BaseModel)

# result 필드명 커스텀 매핑 (agent_name → state 필드명)
_RESULT_FIELD_MAP: dict[str, str] = {
    "narrative": "narrative_output",
    "visualization": "visualization_output",
}


def _get_default_provider() -> LLMProvider:
    """기본 LLM Provider를 생성한다. 지연 임포트로 순환 참조 방지."""
    from app.llm.litellm_provider import LiteLLMProvider
    return LiteLLMProvider()


class BaseAgent(ABC, Generic[T]):
    """모든 MarketScope AI 에이전트의 추상 기본 클래스.

    LLM Provider는 주입 가능하여 litellm 외 다른 프로바이더로 교체 가능하다.
    """

    agent_name: str = ""
    agent_description: str = ""
    output_model: Type[T]
    llm_role: str = "analysis"
    max_retries: int = 2
    retry_base_delay: float = 1.0
    required_state_fields: list[str] = []

    def __init__(
        self,
        settings: Optional[Settings] = None,
        mcp_client: Optional[Any] = None,
        llm_provider: Optional[LLMProvider] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.mcp_client = mcp_client
        self.llm_provider = llm_provider or _get_default_provider()
        self.logger = get_agent_logger(self.agent_name)
        self._llm_model = self.settings.llm.get_model_for_agent(self.agent_name)
        self._temperature = self.settings.llm.get_temperature_for_role(self.llm_role)

    # ── 서브클래스 필수 구현 ──

    @abstractmethod
    async def execute(self, state: dict[str, Any]) -> T:
        ...

    @abstractmethod
    def build_system_prompt(self, state: dict[str, Any]) -> str:
        ...

    @abstractmethod
    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        ...

    # ── LLM 호출 (Provider 경유) ──

    async def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Type[BaseModel]] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """LLM Provider를 통해 LLM을 호출한다. 재시도 로직 내장."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        effective_temperature = temperature if temperature is not None else self._temperature
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                llm_response: LLMResponse = await self.llm_provider.completion(
                    model=self._llm_model,
                    messages=messages,
                    temperature=effective_temperature,
                    max_tokens=max_tokens,
                    timeout=self.settings.litellm_timeout,
                    response_format=response_format,
                )

                parsed = None
                if response_format is not None and llm_response.content:
                    parsed = self._parse_structured_output(llm_response.content, response_format)

                self.logger.info(
                    "LLM 호출 성공",
                    extra={
                        "model": self._llm_model,
                        "attempt": attempt + 1,
                        "latency_ms": round(llm_response.latency_ms, 2),
                    },
                )
                return {
                    "content": llm_response.content,
                    "parsed": parsed,
                    "usage": llm_response.usage,
                    "model": llm_response.model,
                    "latency_ms": llm_response.latency_ms,
                }

            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"LLM 호출 실패 (시도 {attempt + 1}/{self.max_retries + 1})",
                    extra={"error": str(e), "model": self._llm_model},
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_base_delay * (2 ** attempt))

        raise LLMCallError(
            agent_name=self.agent_name,
            model=self._llm_model,
            original_error=last_error,
            attempts=self.max_retries + 1,
        )

    # ── 구조화된 출력 파싱 ──

    def _parse_structured_output(
        self, raw_content: str, model_class: Type[BaseModel]
    ) -> BaseModel:
        """LLM 응답을 Pydantic 모델로 파싱. 3단계 전략."""
        strategies = [
            ("json_block", lambda: self._extract_json_block(raw_content)),
            ("full_text", lambda: json.loads(raw_content)),
            ("brace_extract", lambda: self._extract_json_brace(raw_content)),
        ]

        for strategy_name, extractor in strategies:
            try:
                data = extractor()
                if data is not None:
                    result = model_class.model_validate(data)
                    self.logger.debug(f"파싱 성공: strategy={strategy_name}")
                    return result
            except (json.JSONDecodeError, ValidationError, TypeError):
                continue

        raise OutputParsingError(
            agent_name=self.agent_name,
            model_class=model_class.__name__,
            raw_content=raw_content[:500],
        )

    @staticmethod
    def _extract_json_block(text: str) -> Optional[dict]:
        match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
        return json.loads(match.group(1)) if match else None

    @staticmethod
    def _extract_json_brace(text: str) -> Optional[dict]:
        match = re.search(r"\{[\s\S]*\}", text)
        return json.loads(match.group(0)) if match else None

    # ── MCP 도구 호출 ──

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: Optional[int] = None,
    ) -> dict[str, Any]:
        if self.mcp_client is None:
            self.logger.warning(f"MCP 클라이언트 미설정, 빈 결과 반환: {tool_name}")
            return {}

        effective_timeout = timeout or self.settings.mcp_timeout
        try:
            result = await asyncio.wait_for(
                self.mcp_client.call_tool(tool_name, arguments),
                timeout=effective_timeout,
            )
            self.logger.info(f"MCP 도구 호출 성공: {tool_name}")
            return result
        except asyncio.TimeoutError:
            raise MCPToolCallError(
                agent_name=self.agent_name,
                tool_name=tool_name,
                message=f"타임아웃 ({effective_timeout}초)",
            )
        except Exception as e:
            raise MCPToolCallError(
                agent_name=self.agent_name,
                tool_name=tool_name,
                message=str(e),
                original_error=e,
            )

    async def call_tools_parallel(
        self, tool_calls: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """여러 MCP 도구를 병렬 호출. 개별 실패 시 에러 dict 반환."""
        semaphore = asyncio.Semaphore(self.settings.mcp_max_concurrent_tools)

        async def _call(tc: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                try:
                    return await self.call_tool(tc["tool_name"], tc["arguments"])
                except MCPToolCallError as e:
                    self.logger.warning(f"병렬 도구 호출 실패: {tc['tool_name']}")
                    return {"_error": str(e), "_tool_name": tc["tool_name"]}

        return await asyncio.gather(*[_call(tc) for tc in tool_calls])

    # ── 신뢰도 ──

    def calculate_confidence(
        self,
        data_completeness: float,
        data_freshness: float,
        source_count: int,
        cross_validation_score: float = 0.0,
    ) -> float:
        source_score = min(source_count / 5.0, 1.0)
        confidence = (
            data_completeness * 0.30
            + data_freshness * 0.25
            + source_score * 0.20
            + cross_validation_score * 0.25
        )
        return round(min(max(confidence, 0.0), 1.0), 4)

    def classify_confidence(self, score: float) -> ConfidenceLevel:
        if score >= 0.85:
            return ConfidenceLevel.VERY_HIGH
        elif score >= 0.70:
            return ConfidenceLevel.HIGH
        elif score >= 0.55:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.40:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.VERY_LOW

    # ── 실행 메타데이터 ──

    def create_node_execution(
        self, status: str, started_at: str, error_message: Optional[str] = None,
        token_usage: Optional[dict[str, int]] = None, retry_count: int = 0,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        started = datetime.fromisoformat(started_at)
        duration = (now - started).total_seconds()
        return {
            "node_id": self.agent_name,
            "status": status,
            "started_at": started_at,
            "completed_at": now.isoformat(),
            "duration_seconds": round(duration, 3),
            "llm_model_used": self._llm_model,
            "token_usage": token_usage,
            "error_message": error_message,
            "retry_count": retry_count,
        }

    def _get_result_field(self) -> str:
        """에이전트 결과를 저장할 state 필드명을 결정한다."""
        return _RESULT_FIELD_MAP.get(self.agent_name, f"{self.agent_name}_result")

    # ── LangGraph 노드 래퍼 ──

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """LangGraph 노드 함수로 사용되는 통일된 실행 래퍼.

        모든 에이전트(narrative, visualization 포함)가 이 메서드를 공유한다.
        결과는 Pydantic → dict 변환하여 State 타입 일관성을 보장한다.
        """
        execution_start = datetime.now(timezone.utc).isoformat()
        state_update: dict[str, Any] = {}
        result_field = self._get_result_field()

        self.logger.info(f"에이전트 실행 시작: {self.agent_name}")

        try:
            result = await asyncio.wait_for(
                self.execute(state),
                timeout=self.settings.analysis_agent_timeout,
            )

            # Pydantic 모델 → dict 변환 (State 타입 일관성)
            if isinstance(result, BaseModel):
                state_update[result_field] = result.model_dump()
            else:
                state_update[result_field] = result

            state_update["node_executions"] = [
                self.create_node_execution(
                    "completed", execution_start,
                    token_usage={"prompt_tokens": 0, "completion_tokens": 0},
                )
            ]
            self.logger.info(f"에이전트 실행 완료: {self.agent_name}")

        except asyncio.TimeoutError:
            error_msg = f"{self.agent_name} 타임아웃 ({self.settings.analysis_agent_timeout}초)"
            self.logger.error(error_msg)
            state_update[result_field] = None
            state_update["node_executions"] = [
                self.create_node_execution("failed", execution_start, error_message=error_msg)
            ]
            state_update["errors"] = [{"agent": self.agent_name, "error": error_msg}]

        except Exception as e:
            error_msg = f"{self.agent_name} 실행 에러: {str(e)}"
            self.logger.error(error_msg, extra={"traceback": traceback.format_exc()})
            state_update[result_field] = None
            state_update["node_executions"] = [
                self.create_node_execution("failed", execution_start, error_message=error_msg)
            ]
            state_update["errors"] = [{"agent": self.agent_name, "error": error_msg}]

        return state_update
