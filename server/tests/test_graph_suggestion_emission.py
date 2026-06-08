"""Regression: graph stream emits exactly one suggestion event per response.

Regression: ISSUE-001 — out_of_scope/greeting 중복 suggestion 이벤트
Found by /qa on 2026-06-08
Report: .gstack/qa-reports/qa-report-localhost-2026-06-08.md

Bug: greeting/clarification 노드는 실행 중 tailored suggestion 이벤트를 직접
방출하지만 final_suggestions(state) 를 채우지 않아, 스트림 말미 fallback 이
generic suggestion 을 한 번 더 방출했다. 클라이언트가 suggestion 을 교체
(replace)하므로 generic 이 tailored 를 덮어써, 서울 외 지역 거부 응답에
"이 자리 위험하지 않아?" 같은 부적절한 follow-up 이 노출됐다.

out_of_scope/greeting 경로는 planner 규칙 short-circuit 으로 LLM/Tool 0건이라
외부 의존 없이 run_agent 를 끝까지 구동할 수 있다.
"""

from __future__ import annotations

import pytest

from server.agent.graph import run_agent


async def _collect(message: str) -> list[dict]:
    events: list[dict] = []
    async for ev in run_agent(message, "", "", "2025Q4"):
        events.append(ev)
    return events


@pytest.mark.asyncio
async def test_out_of_scope_emits_single_tailored_suggestion() -> None:
    """서울 외 지역 거부 시 suggestion 이벤트는 정확히 1회, tailored 셋이어야 한다."""
    events = await _collect("부산 해운대 상권 알려줘")
    sugg = [e for e in events if e.get("type") == "suggestion"]
    assert len(sugg) == 1, f"expected 1 suggestion event, got {len(sugg)}: {[s.get('questions') for s in sugg]}"

    questions = sugg[0]["questions"]
    # tailored Seoul-redirect 셋 — 서울 상권명을 포함
    assert any(("강남" in q) or ("홍대" in q) or ("명동" in q) or ("성수" in q) for q in questions), questions
    # generic district follow-up 이 tailored 를 덮어쓰지 않아야 한다
    assert not any("이 자리 위험" in q for q in questions), questions

    # out_of_scope 는 Tool/Card 0건 (short-circuit)
    assert not any(e.get("type") == "card" for e in events)


@pytest.mark.asyncio
async def test_greeting_emits_single_suggestion() -> None:
    """인사 응답도 suggestion 이벤트는 정확히 1회여야 한다 (동일 중복 버그 경로)."""
    events = await _collect("안녕하세요")
    sugg = [e for e in events if e.get("type") == "suggestion"]
    assert len(sugg) == 1, f"expected 1 suggestion event, got {len(sugg)}: {[s.get('questions') for s in sugg]}"
    assert not any(e.get("type") == "card" for e in events)
