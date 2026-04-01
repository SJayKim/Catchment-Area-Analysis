# 07. Graph 조립 + SSE 스트리밍

> 4개 노드를 StateGraph로 연결 + run_agent SSE 스트리밍 재작성

## 대상 파일

| 파일 | 작업 |
|------|------|
| `server/server/agent/graph.py` | **대폭 수정** — 커스텀 StateGraph + run_agent 재작성 |

## 의존성

- 01~06 (모든 노드 + State + Config)

## TODO

- [ ] `build_pae_graph()` 함수 구현 — StateGraph 조립
- [ ] 라우팅 함수 구현 (`route_after_planner`, `route_after_evaluator`)
- [ ] `run_agent()` 재작성 — asyncio.Queue 기반 SSE 스트리밍
- [ ] 기존 `create_agent()` + `run_agent()` 보존 (agent_mode="react" 호환)
- [ ] `agent_mode` 분기 처리
- [ ] 기존 `TOOLS`, `_TOOL_EMOJI`, `_TOOL_CARD_MAP` 상수 Actor로 이관 확인

## 상세 구현

### StateGraph 조립

```python
from langgraph.graph import StateGraph, END
from server.agent.state import AgentState
from server.agent.nodes.planner import planner_node
from server.agent.nodes.actor import actor_node
from server.agent.nodes.evaluator import evaluator_node
from server.agent.nodes.respond import respond_node

def build_pae_graph():
    """Planner-Actor-Evaluator 커스텀 그래프 빌드."""
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("actor", actor_node)
    graph.add_node("evaluator", evaluator_node)
    graph.add_node("respond", respond_node)

    graph.set_entry_point("planner")

    graph.add_conditional_edges("planner", route_after_planner,
        {"actor": "actor", "respond": "respond"})

    graph.add_edge("actor", "evaluator")

    graph.add_conditional_edges("evaluator", route_after_evaluator,
        {"respond": "respond", "planner": "planner"})

    graph.add_edge("respond", END)

    return graph.compile()


def route_after_planner(state: AgentState) -> str:
    if state.get("response_mode") == "direct" or not state.get("plan"):
        return "respond"
    return "actor"


def route_after_evaluator(state: AgentState) -> str:
    evaluation = state.get("evaluation")
    if not evaluation or evaluation["sufficient"]:
        return "respond"
    if state.get("execution_round", 0) >= settings.agent_max_rounds:
        return "respond"
    return "planner"
```

### run_agent (Queue 기반 스트리밍)

핵심 설계: `graph.astream(stream_mode="updates")`는 노드 완료 후에만 yield 하므로, 노드 내부의 실시간 이벤트(tool 진행, text 토큰)를 전달하려면 **asyncio.Queue** 필요.

```python
async def run_agent_pae(
    message: str,
    district_code: str,
    district_name: str,
    data_quarter: str,
    conversation_history: list[dict] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """PAE 에이전트 실행 + SSE 이벤트 스트리밍."""

    event_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    initial_state: AgentState = {
        "messages": [HumanMessage(content=message)],
        "conversation_history": conversation_history or [],
        "district_code": district_code,
        "district_name": district_name,
        "data_quarter": data_quarter,
        "session_id": "",
        "user_intent": "",
        "intent_confidence": 0.0,
        "referenced_districts": [],
        "referenced_category": None,
        "plan": [],
        "plan_reasoning": "",
        "tool_results": {},
        "tool_errors": {},
        "execution_round": 0,
        "evaluation": None,
        "response_mode": "tool_assisted",
        "card_emissions": [],
    }

    graph = build_pae_graph()

    async def _run_graph():
        """그래프 실행 태스크. event_queue에 이벤트 push."""
        try:
            # Planner thinking
            await event_queue.put({"type": "thinking", "step": "질문 분석 중...", "icon": "🧠"})

            async for update in graph.astream(initial_state, stream_mode="updates"):
                for node_name, state_update in update.items():
                    if node_name == "planner":
                        plan = state_update.get("plan", [])
                        if plan:
                            steps = [s["reason"] for s in plan]
                            await event_queue.put({
                                "type": "plan",
                                "intent": state_update.get("user_intent", ""),
                                "steps": steps,
                            })

                    elif node_name == "actor":
                        # Actor의 tool/tool_end는 노드 내부에서 직접 queue에 push
                        # 여기서는 card_emissions만 처리
                        for card in state_update.get("card_emissions", []):
                            await event_queue.put({
                                "type": "card",
                                "card_type": card["card_type"],
                                "data": card["data"],
                            })

                    elif node_name == "evaluator":
                        ev = state_update.get("evaluation", {})
                        if not ev.get("sufficient", True):
                            await event_queue.put({
                                "type": "thinking",
                                "step": "추가 데이터 수집 중...",
                                "icon": "🔍",
                            })

                    elif node_name == "respond":
                        # Text 토큰은 respond 노드 내부에서 직접 queue에 push
                        pass

        except Exception:
            logger.exception("PAE agent execution failed")
            await event_queue.put({
                "type": "text",
                "content": "죄송합니다. 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            })
        finally:
            await event_queue.put(None)  # Sentinel

    # 그래프를 백그라운드 태스크로 실행
    task = asyncio.create_task(_run_graph())

    # Queue에서 이벤트를 꺼내면서 yield
    try:
        while True:
            event = await event_queue.get()
            if event is None:  # Sentinel
                break
            yield event
    finally:
        if not task.done():
            task.cancel()

    # 마지막에 suggestion + done
    # (suggestion은 evaluator의 proactive_suggestions 사용)
    yield {
        "type": "suggestion",
        "questions": ["여기서 뭐하면 좋을까?", "리스크 분석해줘", "다른 상권 비교해줘", "유동인구 상세"],
    }
    yield {"type": "done"}
```

### agent_mode 분기

```python
async def run_agent(
    message: str,
    district_code: str,
    district_name: str,
    data_quarter: str,
    conversation_history: list[dict] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """통합 진입점. agent_mode에 따라 분기."""
    if settings.agent_mode == "pae":
        async for event in run_agent_pae(
            message, district_code, district_name, data_quarter, conversation_history
        ):
            yield event
    else:
        # 기존 ReAct agent (conversation_history 무시)
        async for event in run_agent_react(
            message, district_code, district_name, data_quarter
        ):
            yield event
```

기존 `run_agent` 코드를 `run_agent_react`으로 rename하여 보존.

## Checklist

- [ ] `build_pae_graph()` — 4개 노드 등록, entry_point=planner
- [ ] Planner → Actor (도구 있음) / Respond (직접 응답) 조건부 엣지
- [ ] Actor → Evaluator 고정 엣지
- [ ] Evaluator → Respond (충분) / Planner (부족, max 3회) 조건부 엣지
- [ ] Respond → END 고정 엣지
- [ ] `route_after_planner` — response_mode="direct" or plan 비어있음 → "respond"
- [ ] `route_after_evaluator` — sufficient or round >= max → "respond"
- [ ] `run_agent_pae` — asyncio.Queue 기반 이벤트 스트리밍
- [ ] `run_agent_pae` — 백그라운드 task로 그래프 실행
- [ ] `run_agent_pae` — sentinel(None) 수신 시 루프 종료
- [ ] `run_agent_pae` — exception 시 에러 텍스트 emit
- [ ] `run_agent` — agent_mode 분기 (react / pae)
- [ ] 기존 `run_agent_react` 코드 100% 보존
- [ ] event_queue가 Actor/Respond 노드에 전달되는 메커니즘 구현
- [ ] suggestion 이벤트에 evaluator의 proactive_suggestions 반영

## 시나리오 테스트

### T07-01: 그래프 — Summary 흐름 (Planner → Actor → Evaluator → Respond)
```
조건: message="강남역 분석해줘", district_code="D3001", agent_mode="pae"
기대: SSE 이벤트 순서:
  1. thinking (질문 분석 중)
  2. plan (intent=summary, steps=["상권 요약 조회"])
  3. tool (get_district_summary_tool)
  4. tool_end (get_district_summary_tool)
  5. card (summary)
  6. text (응답 토큰들...)
  7. suggestion (동적 제안)
  8. done
검증: run_agent로 모든 이벤트 수집 후 순서 확인
판정: PASS — 순서 정확 / FAIL — 순서 불일치 또는 누락
```

### T07-02: 그래프 — Direct 응답 (Planner → Respond)
```
조건: message="안녕하세요", agent_mode="pae"
기대: SSE 이벤트 순서:
  1. thinking
  2. text (인사 응답)
  3. suggestion
  4. done
  (tool, card 이벤트 없음)
검증: tool/card 이벤트 미발생 확인
판정: PASS — 도구 미호출 + 직접 응답 / FAIL
```

### T07-03: 그래프 — Evaluator 루프백
```
조건: Evaluator가 sufficient=False 반환하도록 mock 설정, max_rounds=2
기대:
  1. Planner(1회) → Actor → Evaluator(insufficient)
  2. Planner(2회) → Actor → Evaluator(sufficient)
  3. Respond
  SSE에 thinking 이벤트가 "추가 데이터 수집 중..." 포함
검증: execution_round가 2까지 증가, 최종 응답 정상
판정: PASS — 루프 1회 + 최종 응답 / FAIL
```

### T07-04: 그래프 — max_rounds 강제 종료
```
조건: Evaluator가 항상 sufficient=False, max_rounds=3
기대: 3회 루프 후 강제 Respond, done 이벤트
검증: execution_round == 3에서 respond로 이동
판정: PASS — 3회에서 종료 / FAIL — 무한 루프
```

### T07-05: agent_mode="react" 호환
```
조건: agent_mode="react", message="강남역 분석해줘"
기대: 기존 ReAct agent와 동일한 SSE 이벤트 (변경 없음)
검증: 기존 E2E 테스트와 동일한 결과
판정: PASS — 기존 동작 100% 유지 / FAIL
```

### T07-06: 에러 시 graceful 처리
```
조건: Planner에서 예외 발생 (LLM 연결 실패 등)
기대: text 이벤트로 에러 메시지 emit + done 이벤트
      프론트엔드에서 정상 렌더링
검증: run_agent에서 에러 이벤트 수신 확인
판정: PASS — 에러 메시지 + done / FAIL — 스트림 중단
```

### T07-07: Queue 기반 실시간 스트리밍
```
조건: Actor에서 2개 도구 순차 실행
기대: 첫 tool 이벤트가 그래프 완료 전에 yield됨 (실시간)
검증: 이벤트 수신 시각과 그래프 완료 시각 비교
판정: PASS — 실시간 스트리밍 / FAIL — 그래프 완료 후 일괄 yield
```
