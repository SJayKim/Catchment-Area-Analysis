"""astream_with_fallback 단위 테스트 — 옵션 B 스트리밍 (buffering + fallback parity).

Plan: docs/plan/infra/v2-stream-final-option-b-2026-07-06.md
계약: delta(chars 단조/tool_call 플래그) → final(AIMessage) 1회.
폴백/breaker 의미론은 ainvoke_with_fallback 과 동일해야 한다 —
첫 청크 전 실패·mid-stream 실패 모두 버퍼 폐기 후 다음 후보,
클라이언트 abort(GeneratorExit/CancelledError)는 breaker 를 건드리지 않는다.
"""

from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import AIMessageChunk

from server.agent.loop import models as loop_models
from server.agent.loop.models import ModelCandidate, astream_with_fallback
from server.services.circuit_breaker import CircuitBreaker, CircuitState


class _FakeStreamLLM:
    """astream 이 주어진 청크를 흘리다 지정 지점에서 실패/지연하는 fake."""

    def __init__(
        self,
        chunks: list | None = None,
        exc: Exception | None = None,
        fail_after: int | None = None,
        delay_per_chunk: float = 0.0,
    ):
        self.chunks = chunks or []
        self.exc = exc
        self.fail_after = fail_after  # None + exc → 첫 청크 전 실패
        self.delay_per_chunk = delay_per_chunk
        self.stream_started = False

    def bind_tools(self, tools):
        return self

    async def astream(self, messages, config=None):
        self.stream_started = True
        if self.exc is not None and self.fail_after is None:
            raise self.exc
        for i, chunk in enumerate(self.chunks):
            if self.delay_per_chunk:
                await asyncio.sleep(self.delay_per_chunk)
            yield chunk
            if self.fail_after is not None and i + 1 >= self.fail_after:
                raise self.exc or RuntimeError("mid-stream boom")


@pytest.fixture
def fresh_breaker(monkeypatch):
    cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0, name="test_loop_llm")
    monkeypatch.setattr(loop_models, "_loop_circuit_breaker", cb)
    return cb


def _patch_chain(monkeypatch, llms: list[_FakeStreamLLM]) -> None:
    candidates = [ModelCandidate("fake", f"model-{i}") for i in range(len(llms))]
    mapping = dict(zip((c.model_id for c in candidates), llms, strict=True))
    monkeypatch.setattr(loop_models, "_candidate_chain", lambda: candidates)
    monkeypatch.setattr(loop_models, "_build", lambda c: mapping[c.model_id])


async def _drain(gen) -> tuple[list[dict], dict]:
    deltas: list[dict] = []
    final: dict | None = None
    async for ev in gen:
        if ev["kind"] == "delta":
            deltas.append(ev)
        else:
            final = ev
    assert final is not None, "stream ended without a final event"
    return deltas, final


def _tc_chunk(name, args, call_id, index=0):
    return {"name": name, "args": args, "id": call_id, "index": index, "type": "tool_call_chunk"}


async def test_happy_path_text_stream(monkeypatch, fresh_breaker):
    llm = _FakeStreamLLM(chunks=[AIMessageChunk(content=t) for t in ["서울", " 상권", " 분석"]])
    _patch_chain(monkeypatch, [llm])

    deltas, final = await _drain(astream_with_fallback([], None))

    chars = [d["chars"] for d in deltas]
    assert chars == sorted(chars) and chars[-1] == len("서울 상권 분석")
    assert all(d["tool_call"] is False for d in deltas)
    assert final["message"].content == "서울 상권 분석"
    assert not getattr(final["message"], "tool_calls", [])
    assert fresh_breaker.state == CircuitState.CLOSED


async def test_tool_call_chunks_assembled(monkeypatch, fresh_breaker):
    # Anthropic 형: partial_json 이 두 청크로 분할 → `+` 병합으로 완성돼야 한다.
    llm = _FakeStreamLLM(
        chunks=[
            AIMessageChunk(content="", tool_call_chunks=[_tc_chunk("resolve_district", '{"na', "c1")]),
            AIMessageChunk(content="", tool_call_chunks=[_tc_chunk(None, 'me": "홍대"}', None)]),
        ]
    )
    _patch_chain(monkeypatch, [llm])

    deltas, final = await _drain(astream_with_fallback([], None))

    assert all(d["tool_call"] is True for d in deltas)
    tool_calls = final["message"].tool_calls
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "resolve_district"
    assert tool_calls[0]["args"] == {"name": "홍대"}


async def test_midstream_failure_falls_back(monkeypatch, fresh_breaker):
    bad = _FakeStreamLLM(
        chunks=[AIMessageChunk(content="절반쯤 " * 10)],
        exc=RuntimeError("provider died mid-stream"),
        fail_after=1,
    )
    good = _FakeStreamLLM(chunks=[AIMessageChunk(content="후보2의 온전한 답변")])
    _patch_chain(monkeypatch, [bad, good])

    deltas, final = await _drain(astream_with_fallback([], None))

    # 후보1의 버퍼는 폐기 — final 은 후보2 텍스트만.
    assert final["message"].content == "후보2의 온전한 답변"
    # 재시작으로 chars 가 리셋된 delta 가 관찰된다 (전체 단조가 아님).
    chars = [d["chars"] for d in deltas]
    assert chars[-1] == len("후보2의 온전한 답변") < max(chars)
    assert fresh_breaker.state == CircuitState.CLOSED


async def test_prefirst_chunk_failure_falls_back(monkeypatch, fresh_breaker):
    bad = _FakeStreamLLM(exc=RuntimeError("401 dead key"))
    good = _FakeStreamLLM(chunks=[AIMessageChunk(content="ok")])
    _patch_chain(monkeypatch, [bad, good])

    deltas, final = await _drain(astream_with_fallback([], None))

    assert bad.stream_started
    assert final["message"].content == "ok"


async def test_all_candidates_fail_raises_last(monkeypatch, fresh_breaker):
    _patch_chain(
        monkeypatch,
        [_FakeStreamLLM(exc=RuntimeError("first")), _FakeStreamLLM(exc=RuntimeError("second"))],
    )

    with pytest.raises(RuntimeError, match="second"):
        async for _ in astream_with_fallback([], None):
            pass
    # 전 후보 소진 시 record_failure 1회 — ainvoke parity.
    assert fresh_breaker._failure_count == 1


async def test_timeout_moves_to_next_candidate(monkeypatch, fresh_breaker):
    slow = _FakeStreamLLM(chunks=[AIMessageChunk(content="느림")], delay_per_chunk=0.5)
    fast = _FakeStreamLLM(chunks=[AIMessageChunk(content="빠른 후보")])
    _patch_chain(monkeypatch, [slow, fast])

    deltas, final = await _drain(astream_with_fallback([], None, timeout=0.05))

    assert final["message"].content == "빠른 후보"


async def test_openai_style_split_args_tool_call(monkeypatch, fresh_breaker):
    # OpenAI 형: 같은 index 로 args 가 여러 청크에 분할 도착 → `+` 병합으로 완성.
    llm = _FakeStreamLLM(
        chunks=[
            AIMessageChunk(
                content="",
                tool_call_chunks=[_tc_chunk("get_estimated_sales", '{"district', "call_1", index=0)],
            ),
            AIMessageChunk(
                content="",
                tool_call_chunks=[_tc_chunk(None, '_code": "D1"}', None, index=0)],
            ),
        ]
    )
    _patch_chain(monkeypatch, [llm])

    deltas, final = await _drain(astream_with_fallback([], None))

    assert all(d["tool_call"] is True for d in deltas)
    tool_calls = final["message"].tool_calls
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "get_estimated_sales"
    assert tool_calls[0]["args"] == {"district_code": "D1"}


async def test_gemini_style_single_chunk_tool_call(monkeypatch, fresh_breaker):
    # Gemini 형: 완결 tool_call 이 단일 청크로 도착해도 동일하게 조립.
    llm = _FakeStreamLLM(
        chunks=[
            AIMessageChunk(
                content="",
                tool_call_chunks=[_tc_chunk("compute", '{"expression": "1+2"}', "g1")],
            )
        ]
    )
    _patch_chain(monkeypatch, [llm])

    _deltas, final = await _drain(astream_with_fallback([], None))

    assert final["message"].tool_calls[0]["args"] == {"expression": "1+2"}


async def test_client_abort_does_not_trip_breaker(monkeypatch, fresh_breaker):
    llm = _FakeStreamLLM(chunks=[AIMessageChunk(content="가" * 50) for _ in range(5)])
    _patch_chain(monkeypatch, [llm])

    gen = astream_with_fallback([], None)
    first = await anext(gen)
    assert first["kind"] == "delta"
    # 프론트 abort → uvicorn 이 generator 를 닫는다. GeneratorExit 는
    # except Exception 에 잡히지 않아야 하고 breaker 도 무기록이어야 한다.
    await gen.aclose()
    assert fresh_breaker._failure_count == 0
    assert fresh_breaker.state == CircuitState.CLOSED
