"""v2 engine Langfuse L2 wiring — summary/score/tool-span/flush 방출 계약.

Plan: docs/plan/infra/langfuse-ops-hardening-2026-07-06.md (Workstream A3).

고정하는 불변식:
- handler None(테스트 env 기본)이면 LLM 호출 kwargs 가 종전과 동일 — 구 시그니처
  fake 로도 돌아가고 tracer 부속(summary/score/span)은 일절 호출되지 않는다.
- handler 존재 시 summary(name=marketscope.v2.summary) + score 6종 + flush,
  tool 실행마다 tool span, 교정/abstain 경로는 해당 플래그 score 로 드러난다.

주의: engine 은 tracer 함수를 run_agent 호출 시점에 import 하므로 monkeypatch 는
server.services.langfuse_tracer 모듈 속성을 대상으로 한다 (LLM 함수는
test_engine_stream_events 관례대로 engine 네임스페이스).
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

import server.services.langfuse_tracer as tr
from server.agent.loop import engine as loop_engine

# 숫자 없는 prose — Trust 게이트(unbound 검사)를 그대로 통과한다.
PROSE = ("이 상권은 접근성이 좋고 배후 수요가 안정적이며 유동 흐름이 꾸준한 편입니다. " * 8).strip()

CORRECTED = (
    "확인된 도구 데이터만으로 말씀드리면 구체적인 매출 수치는 제시하기 어렵습니다. "
    "다만 상권의 정성적 특성을 보면 접근성과 배후 수요가 안정적인 편이라, "
    "업종 선택과 임차 조건을 함께 검토해 보시길 권합니다. 추정치이며 실제와 다를 수 있습니다."
)

# test_trust_kernel_regressions 검증 완료 쌍 — 확실히 바인딩된다 (147억 = 1.47e10).
BOUND_FACT = {"monthlySales": 14_700_000_000}
BOUND_TEXT = "이 상권의 월 매출은 147억원 규모로 확인됩니다."
FABRICATED_TEXT = "이 상권의 월 매출은 999억원입니다."


class DummyHandler:
    _ms_trace_id = "trace-v2-test"
    _ms_session_hash = "hash-abcd"
    _ms_request_id = "req-1"


def _final_turns(*messages: AIMessage):
    """호출 순서대로 final message 1개씩 내보내는 신 시그니처 fake astream."""
    state = {"calls": 0}

    def fake(msgs, tools, *, callbacks=None, timeout=None, metadata=None, tags=None, run_name=None):
        idx = state["calls"]
        state["calls"] += 1
        state["run_name"] = run_name

        async def _gen():
            yield {"kind": "final", "message": messages[idx]}

        return _gen()

    return fake, state


def _spy_tracer(monkeypatch) -> dict:
    """tracer 부속 4종 spy — engine 이 call-time import 로 집는다."""
    calls: dict = {"summary": [], "scores": [], "tool_spans": [], "flush": []}
    monkeypatch.setattr(tr, "attach_summary_observation", lambda trace_id, **k: calls["summary"].append((trace_id, k)))
    monkeypatch.setattr(tr, "emit_score", lambda trace_id, name, value, **k: calls["scores"].append((name, value)))
    monkeypatch.setattr(tr, "attach_tool_span", lambda trace_id, **k: calls["tool_spans"].append((trace_id, k)))
    monkeypatch.setattr(tr, "flush", lambda handler: calls["flush"].append(handler))
    return calls


def _enable_handler(monkeypatch) -> None:
    monkeypatch.setattr(tr, "get_langfuse_handler", lambda **k: DummyHandler())


async def _run_events() -> list[dict]:
    events = []
    async for ev in loop_engine.run_agent(
        message="강남역 분석해줘",
        district_code="3110001",
        district_name="강남역",
        data_quarter="2025Q4",
    ):
        events.append(ev)
    return events


def _score_map(calls: dict) -> dict:
    return dict(calls["scores"])


async def test_handler_none_keeps_legacy_signature_and_skips_tracer(monkeypatch):
    """keys 미설정(기본) — 구 시그니처 fake 로 동작 + tracer 부속 무호출."""
    calls = _spy_tracer(monkeypatch)

    def fake_astream(msgs, tools, *, callbacks=None, timeout=None):  # 구 시그니처
        async def _gen():
            yield {"kind": "final", "message": AIMessage(content=PROSE)}

        return _gen()

    monkeypatch.setattr(loop_engine, "astream_with_fallback", fake_astream)

    events = await _run_events()

    assert events[-1]["type"] == "done"
    assert "trace_id" not in events[-1]
    assert calls["summary"] == [] and calls["scores"] == [] and calls["tool_spans"] == []
    # flush 는 handler=None 로도 best-effort 호출된다 (no-op)
    assert calls["flush"] == [None]


async def test_handler_present_emits_summary_six_scores_and_flush(monkeypatch):
    calls = _spy_tracer(monkeypatch)
    _enable_handler(monkeypatch)

    tool_turn = AIMessage(
        content="",
        tool_calls=[{"name": "get_district_summary", "args": {"district_code": "3110001"}, "id": "c1"}],
    )
    fake, state = _final_turns(tool_turn, AIMessage(content=BOUND_TEXT))
    monkeypatch.setattr(loop_engine, "astream_with_fallback", fake)

    async def fake_exec(name, args):
        return (BOUND_FACT, None)

    monkeypatch.setattr(loop_engine, "execute_fc_tool", fake_exec)
    monkeypatch.setattr(loop_engine, "card_for_tool", lambda name, result: None)

    events = await _run_events()

    # done 에 trace_id 동봉 + LLM 호출에 run_name 관통
    assert events[-1] == {"type": "done", "trace_id": "trace-v2-test"}
    assert state["run_name"] == "marketscope.v2"

    # summary — v2 이름 + 핵심 metadata 키
    assert len(calls["summary"]) == 1
    trace_id, kwargs = calls["summary"][0]
    assert trace_id == "trace-v2-test"
    assert kwargs["name"] == "marketscope.v2.summary"
    md = kwargs["metadata"]
    assert md["district_code"] == "3110001"
    assert md["district_type"] == "발달상권"
    assert md["iterations_used"] == 2
    assert md["tool_calls_made"] == 1
    assert md["tool_error_count"] == 0
    assert md["called_tools"] == ["get_district_summary"]
    assert md["numeric_match_rate"] == 1.0
    assert md["trust_fallback_triggered"] is False

    # score 6종 전부 — 바인딩 성공 케이스 값
    scores = _score_map(calls)
    assert scores == {
        "numeric_match": 1.0,
        "tool_error_rate": 0.0,
        "abstention_triggered": 0.0,
        "trust_corrective_applied": 0.0,
        "trust_fallback_triggered": 0.0,
        "trust_masked_count": 0.0,
    }

    # tool span 1건 + flush offload
    assert len(calls["tool_spans"]) == 1
    assert len(calls["flush"]) == 1


async def test_tool_error_records_span_error_and_rate(monkeypatch):
    calls = _spy_tracer(monkeypatch)
    _enable_handler(monkeypatch)

    tool_turn = AIMessage(
        content="",
        tool_calls=[{"name": "get_store_info", "args": {"district_code": "3110001"}, "id": "c1"}],
    )
    fake, _ = _final_turns(tool_turn, AIMessage(content=PROSE))
    monkeypatch.setattr(loop_engine, "astream_with_fallback", fake)

    async def fake_exec(name, args):
        return (None, "connection refused")

    monkeypatch.setattr(loop_engine, "execute_fc_tool", fake_exec)

    await _run_events()

    assert len(calls["tool_spans"]) == 1
    _trace_id, span_kwargs = calls["tool_spans"][0]
    assert span_kwargs["name"] == "get_store_info"
    assert span_kwargs["error"] == "connection refused"
    assert span_kwargs["duration_ms"] is not None

    scores = _score_map(calls)
    assert scores["tool_error_rate"] == 1.0
    summary_md = calls["summary"][0][1]["metadata"]
    assert summary_md["tool_error_count"] == 1


async def test_abstain_path_scores_abstention(monkeypatch):
    calls = _spy_tracer(monkeypatch)
    _enable_handler(monkeypatch)

    abstain_turn = AIMessage(
        content="",
        tool_calls=[{"name": "abstain", "args": {"reason": "서울 외 지역"}, "id": "c1"}],
    )
    fake, _ = _final_turns(abstain_turn)
    monkeypatch.setattr(loop_engine, "astream_with_fallback", fake)

    async def fake_exec(name, args):
        return ({"reason": "서울 외 지역은 분석할 수 없습니다."}, None)

    monkeypatch.setattr(loop_engine, "execute_fc_tool", fake_exec)

    events = await _run_events()

    text = "".join(e["content"] for e in events if e["type"] == "text")
    assert "서울 외 지역은 분석할 수 없습니다." in text
    scores = _score_map(calls)
    assert scores["abstention_triggered"] == 1.0
    assert calls["summary"][0][1]["metadata"]["abstention_triggered"] is True


async def test_corrective_path_scores_trust_corrective(monkeypatch):
    calls = _spy_tracer(monkeypatch)
    _enable_handler(monkeypatch)

    fake, _ = _final_turns(AIMessage(content=FABRICATED_TEXT))
    monkeypatch.setattr(loop_engine, "astream_with_fallback", fake)

    async def fake_ainvoke(msgs, tools, *, callbacks=None, timeout=None, metadata=None, tags=None, run_name=None):
        assert tools is None  # 교정 턴은 prose 전용
        return AIMessage(content=CORRECTED)

    monkeypatch.setattr(loop_engine, "ainvoke_with_fallback", fake_ainvoke)

    events = await _run_events()

    assert {"type": "thinking", "step": "수치 검증 중..."} in events
    scores = _score_map(calls)
    assert scores["trust_corrective_applied"] == 1.0
    assert scores["trust_fallback_triggered"] == 0.0
    md = calls["summary"][0][1]["metadata"]
    assert md["trust_corrective_applied"] is True
    # 교정문(숫자 0개) 채택 → 재측정 scored=0 → numeric_match 미방출
    assert "numeric_match" not in scores
