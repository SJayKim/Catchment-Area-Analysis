"""LiteLLM 기반 LLM Provider 구현체."""

from __future__ import annotations

import time
from typing import Any, Optional, Type

import litellm
from pydantic import BaseModel

from marketscope_agent.llm.provider import LLMProvider, LLMResponse
from marketscope_common.logging import get_logger

logger = get_logger("llm.litellm")


class LiteLLMProvider:
    """LiteLLM을 통한 멀티 프로바이더 LLM 호출.

    지원 모델:
    - Anthropic: claude-sonnet-4-6-*, claude-opus-4-6-*
    - Google: gemini/gemini-2.5-flash, gemini/gemini-2.5-pro
    - OpenAI: gpt-4o, gpt-4o-mini (폴백용)
    """

    def __init__(
        self,
        max_retries: int = 3,
        fallback_enabled: bool = True,
        default_timeout: int = 120,
    ) -> None:
        self.max_retries = max_retries
        self.fallback_enabled = fallback_enabled
        self.default_timeout = default_timeout

        # litellm 글로벌 설정
        litellm.num_retries = 0  # 자체 재시도 로직 사용
        litellm.drop_params = True  # 지원하지 않는 파라미터 자동 무시

    async def completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: int = 120,
        response_format: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """LiteLLM을 통해 LLM을 호출한다."""
        effective_timeout = timeout or self.default_timeout

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": effective_timeout,
        }

        if response_format is not None:
            kwargs["response_format"] = response_format

        start_time = time.monotonic()

        response = await litellm.acompletion(**kwargs)

        latency_ms = (time.monotonic() - start_time) * 1000

        content = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        }

        logger.debug(
            "LLM 호출 완료",
            extra={"model": model, "latency_ms": round(latency_ms, 2)},
        )

        return LLMResponse(
            content=content,
            usage=usage,
            model=model,
            latency_ms=latency_ms,
        )
