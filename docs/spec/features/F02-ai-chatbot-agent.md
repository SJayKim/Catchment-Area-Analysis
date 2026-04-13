# F02. AI 챗봇 에이전트 Spec

> LangGraph ReAct Agent + FastAPI SSE 스트리밍 기반 대화형 상권 분석

---

## 1. 개요

| 항목 | 내용 |
|------|------|
| Phase | 1 (MVP) — 핵심 차별점 |
| 의존성 | F01 (상권 선택) |
| 아키텍처 | LangGraph ReAct → FastAPI SSE → Next.js ChatPanel |
| LLM | Claude API (Anthropic) |

## 2. Agent 아키텍처

### 2.1 ReAct 루프

```
START (user query + context)
  │
  ▼
REASON (LLM이 질문 해석, 필요한 Tool 판단)
  │
  ├─ tool_call → ACT (Tool 실행) → OBSERVE (결과 해석) → REASON (반복)
  │
  └─ direct response → END (최종 응답)
```

- 최대 루프 횟수: 5회 (무한루프 방지)
- 세션당 최대 Agent 호출: 20회

### 2.2 상태 정의 (`server/agent/state.py`)

```python
class AgentState(TypedDict):
    messages: list                # 전체 대화 이력
    selected_district_code: str   # 현재 상권코드
    selected_district_name: str   # 상권명
    selected_category_code: str   # 업종코드 (선택)
    tool_calls: list              # 호출한 Tool 목록
    tool_results: list            # Tool 반환값
    iteration_count: int          # ReAct 루프 횟수
    response_type: str            # "text" | "card" | "chart" | "comparison"
    map_commands: list            # 지도 조작 명령
```

### 2.3 그래프 정의 (`server/agent/graph.py`)

```python
from langgraph.graph import StateGraph, END

graph = StateGraph(AgentState)
graph.add_node("reason", reason_node)
graph.add_node("act", act_node)
graph.add_node("observe", observe_node)

graph.add_conditional_edges("reason", should_act, {
    "tool_call": "act",
    "respond": END
})
graph.add_edge("act", "observe")
graph.add_conditional_edges("observe", should_continue, {
    "continue": "reason",
    "respond": END
})

graph.set_entry_point("reason")
agent = graph.compile()
```

## 3. Agent Tools

| Tool | 입력 | 출력 | 사용 기능 |
|------|------|------|-----------|
| `get_floating_population` | 상권코드, 기간 | 시간대/요일/연령/성별 유동인구 | F03, F05, F06 |
| `get_estimated_sales` | 상권코드, 업종코드 | 업종별 추정 매출, 추이 | F03, F04, F09 |
| `get_store_info` | 상권코드, 업종코드 | 점포 수, 개폐업 현황 | F03, F04, F07 |
| `get_population_info` | 상권코드 | 상주/직장인구, 연령/성별 | F03, F07 |
| `get_store_history` | 상권코드 | 과거 업종 이력, 생존기간 | F08 |
| `compare_districts` | 상권코드 2~3개 | 주요 지표 비교표 | F05 |
| `recommend_business` | 상권코드, 조건 | 추천 업종 Top 5 + 근거 | F07 |
| `simulate_revenue` | 상권코드, 업종, 객단가 | 예상 월매출 범위 | F09 |
| `update_map_view` | 상권코드, 레이어 | 지도 하이라이트/히트맵 명령 | F01, F06 |

각 Tool의 구현 상세는 해당 기능 Spec 참조 (F03~F09).

## 4. 시스템 프롬프트 (`server/agent/prompts/system.py`)

```
당신은 서울 상권 분석 AI 컨설턴트입니다.

역할:
- 사용자가 선택한 상권에 대해 데이터 기반 분석을 제공합니다.
- 복잡한 데이터를 이해하기 쉬운 자연어로 해석합니다.
- 창업 준비자, 자영업자에게 실질적인 인사이트를 제공합니다.

규칙:
1. 항상 데이터에 기반하여 답변하세요. 추측을 할 경우 명시하세요.
2. 수치를 언급할 때는 데이터 기준 분기를 함께 안내하세요.
3. 추정 매출은 카드 매출 기반 추정치이며 현금 매출은 미포함임을 안내하세요.
4. 업종 추천 시 반드시 근거 데이터를 제시하세요.
5. 위험 요소가 있으면 솔직하게 안내하세요.
6. 한 번에 최대 2개의 Tool을 호출하세요.
7. 응답은 간결하고 핵심적으로 작성하세요.

현재 컨텍스트:
- 선택된 상권: {district_name} ({district_code})
- 데이터 기준: {data_quarter}
```

## 5. 챗봇 응답 유형

| 유형 | 트리거 예시 | 응답 형태 | SSE 이벤트 |
|------|------------|-----------|-----------|
| 데이터 조회 | "유동인구 얼마?" | 수치 + 한줄 해석 | `text` |
| 비교 분석 | "강남역이랑 홍대 비교" | 비교 카드 + 요약 | `card` (compare) |
| 추천 | "뭐 하면 좋을까?" | 업종 추천 카드 | `card` (recommend) |
| 시뮬레이션 | "카페 매출 얼마?" | 범위 추정 카드 | `card` (simulation) |
| 리스크 | "이 자리 위험해?" | 리스크 카드 | `card` (risk) |
| 일반 대화 | "고마워" | 텍스트 응답 | `text` |

## 6. SSE 스트리밍 (Backend → Frontend)

### 6.1 API 엔드포인트

```
POST /api/chat
Content-Type: application/json

{
  "message": "강남역에서 카페 하면 어때?",
  "session_id": "uuid-...",
  "district_code": "3110032"
}

Response: text/event-stream
```

### 6.2 SSE 이벤트 타입

| type | data | 설명 |
|------|------|------|
| `thinking` | `{"step": "상권 데이터를 분석하고 있습니다..."}` | 추론 중 표시 |
| `tool` | `{"name": "get_estimated_sales", "input": {...}}` | Tool 호출 알림 |
| `text` | `{"content": "강남역에서..."}` | 텍스트 토큰 스트리밍 |
| `card` | `{"card_type": "summary", "data": {...}}` | Rich Card 데이터 |
| `map_cmd` | `{"action": "highlight", "params": {...}}` | 지도 조작 명령 |
| `suggestion` | `{"questions": ["업종 추천해줘", "홍대랑 비교"]}` | 추천 질문 |
| `done` | `{}` | 응답 완료 |

### 6.3 FastAPI SSE 구현

```python
@router.post("/api/chat")
async def chat(request: ChatRequest):
    async def event_generator():
        async for event in agent.astream(state):
            if event.type == "thinking":
                yield f"data: {json.dumps({'type': 'thinking', ...})}\n\n"
            elif event.type == "tool_call":
                yield f"data: {json.dumps({'type': 'tool', ...})}\n\n"
            elif event.type == "text":
                yield f"data: {json.dumps({'type': 'text', ...})}\n\n"
            # ...
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

## 7. Frontend 구현

### 7.1 관련 컴포넌트

| 컴포넌트 | 파일 | 역할 |
|----------|------|------|
| ChatPanel | `components/chat/ChatPanel.tsx` | 채팅 패널 컨테이너 |
| MessageList | `components/chat/MessageList.tsx` | 메시지 목록 스크롤 |
| MessageBubble | `components/chat/MessageBubble.tsx` | 개별 메시지 (텍스트/카드 분기) |
| ChatInput | `components/chat/ChatInput.tsx` | 입력창 + 전송 버튼 |
| SuggestionChips | `components/chat/SuggestionChips.tsx` | 추천 질문 버튼 |

### 7.2 SSE 클라이언트 (`hooks/useChat.ts`)

```typescript
function useChat() {
  const sendMessage = async (message: string) => {
    const response = await fetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id, district_code }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const events = parseSSE(decoder.decode(value));
      for (const event of events) {
        switch (event.type) {
          case 'text': appendText(event.content); break;
          case 'card': addCard(event.card_type, event.data); break;
          case 'map_cmd': mapStore.executeCommand(event); break;
          case 'suggestion': setSuggestions(event.questions); break;
          case 'thinking': setThinking(event.step); break;
        }
      }
    }
  };
}
```

### 7.3 상권 선택 시 자동 쿼리

지도에서 상권 클릭 → 내부적으로 다음 메시지를 Agent에 전달:
```
"사용자가 {상권명} 상권을 선택했습니다. 기본 요약을 제공해주세요."
```
→ F03 기본 리포트가 자동으로 생성됨

## 8. 대화 세션 관리

- 세션 ID: UUID, 브라우저 `sessionStorage`에 저장
- 대화 이력: `chat_sessions` + `chat_messages` 테이블에 저장
- 컨텍스트 유지: Agent에 최근 10개 메시지 전달
- 상권 전환 시: 새 세션 생성 또는 컨텍스트 리셋 확인

## 9. 에러 처리 및 폴백 전략

### 9.1 에러 유형별 처리

| 에러 상황 | 감지 방법 | 처리 | SSE 이벤트 |
|-----------|----------|------|-----------|
| LLM API 실패 | HTTP 5xx / timeout (30s) | 1회 재시도 → 실패 시 에러 메시지 | `error` |
| LLM API Rate Limit | HTTP 429 | 2초 대기 후 1회 재시도 → 실패 시 에러 메시지 | `error` |
| Tool 실행 실패 (DB 오류) | Tool 함수 내 exception | Agent에 에러 observation 전달 → LLM이 대체 Tool 선택 또는 부분 응답 | `tool` (status: error) |
| Tool 실행 타임아웃 | 10초 초과 | 해당 Tool 스킵, 나머지 결과로 응답 | `tool` (status: timeout) |
| ReAct 루프 5회 도달 | iteration_count ≥ 5 | 수집된 tool_results로 강제 응답 생성 | `text` + `done` |
| 세션 호출 20회 도달 | 세션 카운터 | "분석 한도에 도달했습니다. 새 대화를 시작해주세요" | `error` |
| 상권 데이터 없음 | Tool 반환 결과 empty | "해당 상권의 {항목} 데이터가 아직 없습니다" | `text` |

### 9.2 Tool 실패 시 ReAct 루프 동작

```python
async def observe_node(state: AgentState) -> AgentState:
    """Tool 결과를 해석하고 다음 액션 결정"""

    last_tool = state["tool_calls"][-1]
    last_result = state["tool_results"][-1]

    if last_result["status"] == "error":
        # 에러 정보를 observation으로 LLM에 전달
        state["messages"].append({
            "role": "tool",
            "content": f"[Tool '{last_tool['name']}' 실패: {last_result['error']}] "
                       f"이 데이터 없이 답변하거나, 대체 방법을 시도하세요.",
            "tool_call_id": last_tool["id"]
        })
    elif last_result["status"] == "timeout":
        state["messages"].append({
            "role": "tool",
            "content": f"[Tool '{last_tool['name']}' 응답 시간 초과] "
                       f"이 데이터 없이 가능한 범위에서 답변하세요.",
            "tool_call_id": last_tool["id"]
        })
    else:
        # 정상 결과
        state["messages"].append({
            "role": "tool",
            "content": json.dumps(last_result["data"], ensure_ascii=False),
            "tool_call_id": last_tool["id"]
        })

    return state
```

### 9.3 ReAct 루프 초과 시 강제 응답 생성

```python
async def should_continue(state: AgentState) -> str:
    """루프 계속/종료 판단"""
    if state["iteration_count"] >= 5:
        # 수집된 결과가 있으면 강제 응답 생성
        if any(r["status"] == "success" for r in state["tool_results"]):
            # 성공한 Tool 결과만으로 부분 응답 생성
            state["messages"].append({
                "role": "system",
                "content": "루프 한도에 도달했습니다. 현재까지 수집된 데이터로 답변을 생성하세요. "
                           "부족한 부분은 '추가 분석이 필요합니다'로 안내하세요."
            })
        return "respond"
    return "continue"
```

### 9.4 부분 응답 예시

```
🔍 강남역 카페 분석 (2025년 4분기 기준)

강남역에 카페가 72개 있어서 경쟁이 꽤 치열합니다 (상권 내 점포 비율 13.8%).

⚠ 매출 데이터를 불러오지 못해 매출 분석은 제외되었습니다.
유동인구 중 20~30대가 63%로, 카페 타겟과 잘 맞습니다.

💡 매출 정보가 필요하시면 "카페 매출 알려줘"로 다시 질문해주세요.
```

### 9.5 프론트엔드 에러 표시

```typescript
// SSE error 이벤트 수신 시
case 'error':
  addMessage({
    role: 'assistant',
    type: 'error',
    content: event.message,        // "잠시 후 다시 시도해주세요"
    retryable: event.retryable,    // true → 재시도 버튼 표시
  });
  break;
```

## 10. Langfuse 통합

```python
from langfuse.callback import CallbackHandler

langfuse_handler = CallbackHandler(...)
result = agent.invoke(state, config={"callbacks": [langfuse_handler]})
```

추적 항목:
- ReAct 루프별 reasoning/tool_call/observation
- Tool별 latency, 성공/실패율
- 토큰 사용량, 비용
- 사용자 질문 유형 분류

## 11. 수용 기준

- [ ] 자연어 입력 → Agent가 적절한 Tool을 선택하여 호출한다
- [ ] SSE 스트리밍으로 응답이 실시간 표시된다
- [ ] thinking 상태가 UI에 표시된다
- [ ] Tool 결과가 적절한 카드/텍스트로 포맷팅된다
- [ ] 대화 컨텍스트가 유지된다 (이전 대화 참조 가능)
- [ ] 상권 선택 시 자동으로 기본 요약이 생성된다
- [ ] 지도 조작 명령(map_cmd)이 실제 지도에 반영된다
- [ ] ReAct 루프가 5회 이내로 제한된다
- [ ] Langfuse에서 Agent 호출 트레이스가 확인된다

---

*작성일: 2026-03-24*
