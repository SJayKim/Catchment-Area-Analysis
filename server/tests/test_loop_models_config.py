"""v2 loop models — Langfuse config(metadata/tags/run_name) 관통 계약.

Plan: docs/plan/infra/langfuse-ops-hardening-2026-07-06.md (Workstream A1).

고정하는 불변식:
- keyword-only metadata/tags/run_name 이 LangChain RunnableConfig 로 전달된다.
- 신규 kwargs 를 생략하면 config 는 종전과 바이트 동일 (None) — 구 시그니처
  fake 를 쓰는 기존 테스트/호출부 보호.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from server.agent.loop import models


class _CapturingLLM:
    """bind_tools/ainvoke/astream 이 받은 config 를 기록하는 fake."""

    def __init__(self, captured: dict) -> None:
        self.captured = captured

    def bind_tools(self, tools):
        self.captured["tools"] = tools
        return self

    async def ainvoke(self, messages, config=None):
        self.captured["config"] = config
        return AIMessage(content="ok")

    async def astream(self, messages, config=None):
        self.captured["config"] = config
        yield AIMessageChunk(content="ok")


def _wire_fake(monkeypatch, captured: dict) -> None:
    monkeypatch.setattr(models, "_candidate_chain", lambda: [models.ModelCandidate("anthropic", "test-model")])
    monkeypatch.setattr(models, "_build", lambda candidate: _CapturingLLM(captured))


async def test_ainvoke_threads_metadata_tags_run_name(monkeypatch) -> None:
    captured: dict = {}
    _wire_fake(monkeypatch, captured)

    result = await models.ainvoke_with_fallback(
        [HumanMessage(content="hi")],
        None,
        metadata={"langfuse_session_id": "abcd"},
        tags=["marketscope.v2"],
        run_name="marketscope.v2",
    )

    assert result.content == "ok"
    assert captured["config"] == {
        "metadata": {"langfuse_session_id": "abcd"},
        "tags": ["marketscope.v2"],
        "run_name": "marketscope.v2",
    }


async def test_astream_threads_metadata_tags_run_name(monkeypatch) -> None:
    captured: dict = {}
    _wire_fake(monkeypatch, captured)

    events = []
    async for ev in models.astream_with_fallback(
        [HumanMessage(content="hi")],
        None,
        metadata={"request_id": "r1"},
        tags=["t1"],
        run_name="marketscope.v2",
    ):
        events.append(ev)

    assert events[-1]["kind"] == "final"
    assert captured["config"] == {
        "metadata": {"request_id": "r1"},
        "tags": ["t1"],
        "run_name": "marketscope.v2",
    }


async def test_omitted_kwargs_keep_config_none(monkeypatch) -> None:
    """신규 kwargs 미지정 시 config 는 종전 그대로 None (기존 경로 무변경)."""
    captured: dict = {}
    _wire_fake(monkeypatch, captured)

    await models.ainvoke_with_fallback([HumanMessage(content="hi")], None)
    assert captured["config"] is None

    captured.clear()
    async for _ in models.astream_with_fallback([HumanMessage(content="hi")], None):
        pass
    assert captured["config"] is None
