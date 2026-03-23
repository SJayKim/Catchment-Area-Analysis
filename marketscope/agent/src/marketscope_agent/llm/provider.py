"""LLM Provider 추상 인터페이스."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, Type, runtime_checkable

from pydantic import BaseModel


@dataclass
class LLMResponse:
    """LLM 호출 결과 표준 응답."""
    content: str
    usage: dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0})
    model: str = ""
    latency_ms: float = 0.0


@runtime_checkable
class LLMProvider(Protocol):
    """LLM 프로바이더 프로토콜.

    이 인터페이스를 구현하면 어떤 LLM 백엔드든 교체 가능하다.
    - LiteLLM (기본): litellm_provider.py
    - OpenAI 직접 호출: openai_provider.py (향후)
    - Anthropic 직접 호출: anthropic_provider.py (향후)
    - 로컬 모델: local_provider.py (향후)
    """

    async def completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: int = 120,
        response_format: Optional[Type[BaseModel]] = None,
    ) -> LLMResponse:
        """LLM completion 호출.

        Args:
            model: 모델 식별자 (예: "claude-sonnet-4-6-20250514", "gemini/gemini-2.5-flash")
            messages: [{"role": "system"|"user"|"assistant", "content": str}, ...]
            temperature: 생성 온도 (0.0~2.0)
            max_tokens: 최대 생성 토큰 수
            timeout: 타임아웃 (초)
            response_format: 구조화된 출력용 Pydantic 모델 (지원하는 경우)

        Returns:
            LLMResponse 표준 응답

        Raises:
            Exception: 프로바이더별 에러
        """
        ...
