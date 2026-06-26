"""LLM provider for the agentic loop — native AsyncAnthropic + offline mock.

The mock provider (use_mock / llm_provider=="mock") returns canned tool_use →
final-text turns so the loop + SSE contract are testable with no network. The real
provider wraps anthropic.AsyncAnthropic.messages.stream with Opus-4.8 params
(adaptive thinking, output_config.effort; no temperature/top_p/top_k).

Both providers expose the same `stream(...)` contract: an async context manager
yielding `content_block_delta` events (with `.delta.type`/`.delta.text`) and an
`await stream.get_final_message()` returning an object with `.content` (blocks with
`.type`/`.id`/`.name`/`.input`/`.text`), `.stop_reason`, and `.usage`.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from server.config import settings
from server.services.circuit_breaker import CircuitBreaker

_cb = CircuitBreaker(
    failure_threshold=settings.circuit_breaker_failure_threshold,
    recovery_timeout=settings.circuit_breaker_recovery_timeout,
    name="agentic-llm",
)


def get_circuit_breaker() -> CircuitBreaker:
    return _cb


def get_provider():
    if settings.use_mock or settings.llm_provider == "mock":
        return _MockProvider()
    return _AnthropicProvider()


def _supports_effort(model: str) -> bool:
    """Adaptive thinking + output_config.effort: Opus 4.5+, Sonnet 4.6, Fable 5.

    Haiku 4.5 and Sonnet 4.5 reject both (400) — the gate tier (claude-haiku-4-5)
    must NOT send them.
    """
    m = model.lower()
    return "haiku" not in m and "sonnet-4-5" not in m


class _AnthropicProvider:
    def __init__(self) -> None:
        import anthropic  # lazy — only the real path needs the native SDK

        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    def stream(self, *, model, max_tokens, system, tools, messages, effort):
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "tools": tools,
            "messages": messages,
        }
        if _supports_effort(model):
            kwargs["thinking"] = {"type": "adaptive", "display": "summarized"}
            kwargs["output_config"] = {"effort": effort}
        return self._client.messages.stream(**kwargs)


# --- Offline mock --------------------------------------------------------------

_MOCK_FINAL_TEXT = "분석 결과를 정리하면, 해당 상권은 유동인구와 매출 지표가 양호합니다. (샘플 응답)"
_MOCK_TEXT_PIECES = (
    "분석 결과를 정리하면, ",
    "해당 상권은 유동인구와 매출 지표가 양호합니다. ",
    "(샘플 응답)",
)


class _MockProvider:
    def stream(self, *, model, max_tokens, system, tools, messages, effort):
        return _MockStream(messages=messages, tools=tools)


class _MockStream:
    """Deterministic two-turn mock: round 1 calls a tool, round 2 answers."""

    def __init__(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> None:
        self._messages = messages
        self._tools = tools or []

    async def __aenter__(self) -> _MockStream:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    def _last_is_tool_result(self) -> bool:
        if not self._messages:
            return False
        content = self._messages[-1].get("content")
        return isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content
        )

    def _decide(self) -> tuple[str, str | None]:
        names = [t["name"] for t in self._tools]
        if self._last_is_tool_result() or not names:
            return "end_turn", None
        target = "get_district_summary" if "get_district_summary" in names else names[0]
        return "tool_use", target

    def _district_code(self) -> str:
        for m in self._messages:
            content = m.get("content")
            if isinstance(content, str) and "코드:" in content:
                try:
                    return content.split("코드:", 1)[1].split(")", 1)[0].strip()
                except IndexError:
                    return ""
        return ""

    async def __aiter__(self):
        stop, _ = self._decide()
        if stop == "end_turn":
            for piece in _MOCK_TEXT_PIECES:
                yield SimpleNamespace(
                    type="content_block_delta",
                    delta=SimpleNamespace(type="text_delta", text=piece),
                )

    async def get_final_message(self) -> SimpleNamespace:
        stop, target = self._decide()
        usage = SimpleNamespace(input_tokens=0, output_tokens=0)
        if stop == "tool_use":
            block = SimpleNamespace(
                type="tool_use",
                id="toolu_mock_1",
                name=target,
                input={"district_code": self._district_code()},
            )
            return SimpleNamespace(content=[block], stop_reason="tool_use", usage=usage)
        block = SimpleNamespace(type="text", text=_MOCK_FINAL_TEXT)
        return SimpleNamespace(content=[block], stop_reason="end_turn", usage=usage)
