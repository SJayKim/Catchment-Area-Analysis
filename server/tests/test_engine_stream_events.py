"""v2 루프 옵션 B 이벤트 계약 테스트 — 진행 이벤트 + 버퍼링 일괄 방출.

Plan: docs/plan/infra/v2-stream-final-option-b-2026-07-06.md
고정하는 불변식:
- "응답 작성 중... n%" 진행 이벤트는 % 단조 증가, 도구 턴에서는 억제.
- text 이벤트는 진행 이벤트가 모두 끝난 뒤 일괄 방출 (검증-후-방출 보존).
- Trust 교정 패스는 스트리밍 도입 후에도 그대로 경유한다.
- agent_loop_stream_final=False 롤백 토글 시 기존 ainvoke 경로만 사용.

주의: engine.py 는 모델 함수를 이름으로 로컬 바인딩하므로 monkeypatch 는
반드시 engine 네임스페이스(server.agent.loop.engine.*)를 대상으로 한다.
"""

from __future__ import annotations

import re

from langchain_core.messages import AIMessage

from server.agent.loop import engine as loop_engine
from server.config import settings

# 숫자 없는 prose — Trust 게이트(unbound 검사)를 그대로 통과한다.
PROSE = ("이 상권은 접근성이 좋고 배후 수요가 안정적이며 유동 흐름이 꾸준한 편입니다. " * 8).strip()

CORRECTED = (
    "확인된 도구 데이터만으로 말씀드리면 구체적인 매출 수치는 제시하기 어렵습니다. "
    "다만 상권의 정성적 특성을 보면 접근성과 배후 수요가 안정적인 편이라, "
    "업종 선택과 임차 조건을 함께 검토해 보시길 권합니다. 추정치이며 실제와 다를 수 있습니다."
)


def _delta(chars: int, tool_call: bool = False) -> dict:
    return {"kind": "delta", "chars": chars, "tool_call": tool_call}


def _final(message: AIMessage) -> dict:
    return {"kind": "final", "message": message}


def _make_astream(turns: list[list[dict]]):
    """호출 순서대로 turns[i] 이벤트를 흘리는 fake astream_with_fallback."""
    state = {"calls": 0}

    def fake(messages, tools, *, callbacks=None, timeout=None):
        idx = state["calls"]
        state["calls"] += 1

        async def _gen():
            for ev in turns[idx]:
                yield ev

        return _gen()

    return fake, state


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


def _progress_steps(events: list[dict]) -> list[str]:
    return [e["step"] for e in events if e["type"] == "thinking" and e["step"].startswith("응답 작성 중")]


def _pcts(steps: list[str]) -> list[int]:
    return [int(re.search(r"(\d+)%", s).group(1)) for s in steps]


async def test_final_only_turn_event_order(monkeypatch):
    fake, _ = _make_astream([[_delta(200), _delta(400), _delta(600), _final(AIMessage(content=PROSE))]])
    monkeypatch.setattr(loop_engine, "astream_with_fallback", fake)

    events = await _run_events()

    assert events[0] == {"type": "thinking", "step": "질문 분석 중..."}
    steps = _progress_steps(events)
    pcts = _pcts(steps)
    assert len(steps) == 3
    assert pcts == sorted(pcts) and len(set(pcts)) == len(pcts)  # 단조 + 중복 없음

    types = [e["type"] for e in events]
    first_text = types.index("text")
    last_progress = max(i for i, e in enumerate(events) if e["type"] == "thinking")
    assert last_progress < first_text  # 일괄 방출: text 전에 진행 이벤트 종료

    text = "".join(e["content"] for e in events if e["type"] == "text")
    assert text == PROSE
    assert types[-1] == "done"
    assert "suggestion" in types


async def test_tool_turn_suppresses_progress(monkeypatch):
    tool_msg = AIMessage(
        content="",
        tool_calls=[{"name": "resolve_district", "args": {"name": "홍대"}, "id": "c1"}],
    )
    fake, _ = _make_astream(
        [
            [_delta(30), _delta(45, tool_call=True), _final(tool_msg)],
            [_delta(300), _final(AIMessage(content=PROSE))],
        ]
    )
    monkeypatch.setattr(loop_engine, "astream_with_fallback", fake)

    async def fake_exec(name, args):
        return ({"code": "3120103", "name": "홍대"}, None)

    monkeypatch.setattr(loop_engine, "execute_fc_tool", fake_exec)
    monkeypatch.setattr(loop_engine, "card_for_tool", lambda name, result: None)

    events = await _run_events()

    types = [e["type"] for e in events]
    assert "tool" in types and "tool_end" in types
    # 도구 턴(1턴차)에서는 진행 이벤트 0건 — 첫 진행 이벤트는 tool_end 이후.
    steps = _progress_steps(events)
    assert len(steps) == 1  # 2턴차 chars=300 1건만
    first_progress = next(i for i, e in enumerate(events) if e["type"] == "thinking" and "응답 작성 중" in e["step"])
    assert first_progress > types.index("tool_end")
    assert {"type": "thinking", "step": "데이터 수집 중..."} in events
    assert {"type": "thinking", "step": "결과 분석 중..."} in events


async def test_trust_corrective_path_still_runs(monkeypatch):
    # fact 없이 수치 주장 → unbound → 교정 패스(ainvoke, prose 전용) 경유.
    fabricated = AIMessage(content="이 상권의 월 매출은 999억원입니다.")
    fake, _ = _make_astream([[_delta(200), _final(fabricated)]])
    monkeypatch.setattr(loop_engine, "astream_with_fallback", fake)

    calls = {"ainvoke": 0, "tools": "sentinel"}

    async def fake_ainvoke(messages, tools, *, callbacks=None, timeout=None):
        calls["ainvoke"] += 1
        calls["tools"] = tools
        return AIMessage(content=CORRECTED)

    monkeypatch.setattr(loop_engine, "ainvoke_with_fallback", fake_ainvoke)

    assert len(CORRECTED) >= 120  # _is_answer_shaped 전제 (숫자 없는 교정문)
    events = await _run_events()

    assert {"type": "thinking", "step": "수치 검증 중..."} in events
    assert calls["ainvoke"] == 1
    assert calls["tools"] is None  # 교정 턴은 prose 전용(도구 없음)
    text = "".join(e["content"] for e in events if e["type"] == "text")
    assert text == CORRECTED


async def test_stream_toggle_off_uses_ainvoke(monkeypatch):
    monkeypatch.setattr(settings, "agent_loop_stream_final", False)
    called = {"astream": False}

    def fake_astream(*args, **kwargs):
        called["astream"] = True

        async def _gen():
            yield _final(AIMessage(content="unexpected"))

        return _gen()

    async def fake_ainvoke(messages, tools, *, callbacks=None, timeout=None):
        return AIMessage(content=PROSE)

    monkeypatch.setattr(loop_engine, "astream_with_fallback", fake_astream)
    monkeypatch.setattr(loop_engine, "ainvoke_with_fallback", fake_ainvoke)

    events = await _run_events()

    assert called["astream"] is False
    assert _progress_steps(events) == []
    text = "".join(e["content"] for e in events if e["type"] == "text")
    assert text == PROSE


async def test_progress_throttle_caps_events(monkeypatch):
    # 10자 단위 미세 delta 60건 → interval(80자)·min(120자) 스로틀로 7건만.
    deltas = [_delta(c) for c in range(10, 601, 10)]
    fake, _ = _make_astream([[*deltas, _final(AIMessage(content=PROSE))]])
    monkeypatch.setattr(loop_engine, "astream_with_fallback", fake)

    events = await _run_events()

    pcts = _pcts(_progress_steps(events))
    assert len(pcts) == 7  # chars 120/200/280/360/440/520/600
    assert pcts == sorted(pcts) and len(set(pcts)) == len(pcts)
