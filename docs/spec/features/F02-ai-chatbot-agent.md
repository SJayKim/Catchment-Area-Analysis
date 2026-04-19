# F02. AI 챗봇 에이전트 Spec

> LangGraph 기반 커스텀 **Planner-Actor-Evaluator-Respond** 그래프 + FastAPI SSE 스트리밍.
> 상세 그래프/Tool 레지스트리는 [../../architecture/agent.md](../../architecture/agent.md) 참조.

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| Phase | 1A(Mock) · 1B(Real) — **완료** |
| Tier | Free (Phase 2에서 Free 일 5회 제한 예정) |
| 의존성 | F01 (상권 선택), D01 (데이터) |
| 아키텍처 | **PAE 그래프** → FastAPI SSE → Next.js ChatPanel |
| LLM | Claude Sonnet 4 (planner) / Gemini pro·flash (역할별) / Mock |
| 현재 세팅 | `agent_mode=pae`, `agent_max_rounds=3` |

## 2. Agent 그래프 구조

```
 START → PLANNER → ┬→ greeting END
                    ├→ ACTOR → EVALUATOR → ┬→ RESPOND → END
                    │                       └→ PLANNER (loop, max 3)
                    └→ RESPOND (fast path)
```

| 노드 | 책임 | 파일 |
|---|---|---|
| **Planner** | Intent 분류 (rule→LLM), Tool plan 생성, Entity 추출 | `server/server/agent/nodes/planner.py` |
| **Actor** | 의존성 layer 기반 병렬 Tool 실행, Card 발행, map_cmd | `agent/nodes/actor.py` |
| **Evaluator** | Tool 결과 충분성 판정 (rule fast path or LLM), suggestion 생성 | `agent/nodes/evaluator.py` |
| **Respond** | 최종 응답 LLM 스트리밍 (토큰 → SSE `text`) | `agent/nodes/respond.py` |

상세 책임·프롬프트·에러 처리는 [architecture/agent.md §3](../../architecture/agent.md) 참조.

## 3. 상태 (`agent/state.py`)

```python
class AgentState(TypedDict, total=False):
    messages: list[BaseMessage]
    session_id: str
    district_code: str | None
    district_name: str | None
    selected_category_code: str | None
    user_intent: str           # summary/comparison/recommendation/risk/category/simulation/heatmap/greeting
    confidence: float
    referenced_districts: list[str]
    referenced_category: str | None
    plan: list[ToolPlanStep]
    tool_calls: list[dict]
    tool_results: list[dict]
    cards: list[dict]
    suggestions: list[str]
    map_commands: list[dict]
    rounds: int
    event_queue: asyncio.Queue  # SSE 이벤트 큐
```

## 4. Agent Tools (11종)

| Tool | Card | 용도 | 관련 기능 |
|---|---|---|---|
| `get_district_summary` | summary | 4 Tool 병렬 집계 | F03 |
| `get_floating_population` | population | 시간대/성별/연령 | F03, F05, F06 |
| `get_estimated_sales` | sales | 업종별 매출 (분기→월 환산) | F03, F04, F09 |
| `get_store_info` | store | 점포수, 개폐업, Top 업종 | F03, F04, F07 |
| `get_store_history` | history | 안정성 / 생존기간 | F08 |
| `get_population_info` | population | 상주/직장 인구 | F03, F07 |
| `compare_districts` | comparison | 2~3 상권 지표 비교 | F05 |
| `recommend_business` | recommend | Top 5 + 점수 + 면책 | F07 |
| `estimate_revenue` | revenue | p25/avg/p75 범위 | F09 |
| `get_district_benchmarks` | benchmark | 유형별 통계 | 벤치마킹 |
| `detect_floating_pop_anomaly` | anomaly | 통계적 이상 감지 | 리스크 감지 |

각 Tool 구현 상세는 해당 기능 Spec(F03~F09) 참조.

## 5. 시스템 프롬프트 (`agent/prompts/system.py`)

핵심 규칙:
1. 데이터 기반 답변, 추측 시 명시
2. 수치 언급 시 데이터 기준 분기 함께 안내
3. **추정 매출**은 카드 매출 기반, 현금 매출 미포함 안내
4. 업종 추천 시 반드시 근거 제시
5. 리스크 요소는 솔직하게 안내
6. 응답은 간결하고 핵심적으로
7. 면책 조항: 투자 의사결정은 개인 책임

## 6. SSE 스트리밍

### 6.1 엔드포인트

```
POST /api/chat
Content-Type: application/json

{
  "message": "강남역에서 카페 하면 어때?",
  "session_id": "uuid-...",      // 선택, 없으면 서버 생성
  "district_code": "3110032"     // 선택
}

Response: text/event-stream
```

### 6.2 이벤트 타입 (9종)

| type | payload | 발생 시점 |
|---|---|---|
| `thinking` | `{step, icon}` | 노드 전환 |
| `plan` | `{intent, steps[]}` | Planner 완료 |
| `tool` | `{name, input, progress_label, icon}` | Tool 호출 직전 |
| `tool_end` | `{name, done_label, icon}` | Tool 종료 |
| `text` | `{content}` | Respond 토큰 |
| `card` | `{card_type, data, dataSources[]}` | Actor 카드 발행 |
| `suggestion` | `{questions[]}` | Evaluator 추천 질문 |
| `map_cmd` | `{action, params}` | 지도 조작 |
| `done` | `{}` | 세션 종료 |

### 6.3 구현

`server/server/api/routes/chat.py`
- `sse_starlette.EventSourceResponse` 사용
- `event_queue: asyncio.Queue(maxsize=256)` 로 backpressure
- 25s 주기 heartbeat (프록시 유지)
- 최대 지속 시간 5분, 클라이언트 disconnect 시 graceful 종료

## 7. Frontend 구현

| 컴포넌트 | 파일 | 역할 |
|---|---|---|
| ChatPanel | `components/chat/ChatPanel.tsx` | 컨테이너 (MessageList + SuggestionChips + ChatInput) |
| MessageList | `components/chat/MessageList.tsx` | 스크롤 + 메시지 렌더링 |
| MessageBubble | `components/chat/MessageBubble.tsx` | 텍스트 / 카드 분기 + react-markdown |
| AgentProgressIndicator | `components/chat/AgentProgressIndicator.tsx` | thinking→plan→tool 진행 표시 |
| ChatInput | `components/chat/ChatInput.tsx` | 자연어 입력 |
| SuggestionChips | `components/chat/SuggestionChips.tsx` | 추천 질문 버튼 |

SSE 파서는 `lib/sseParser.ts` (async generator), 이벤트 dispatch 는 `lib/eventHandlers.ts` 참조.

### 지도 클릭 → 자동 요약

`useMapSync` 훅이 `districtStore.selected.source === 'map'` 일 때 챗에 `"상권 요약해줘"` 쿼리 자동 전송 → Planner 가 summary intent 로 분류 → F03 카드 생성.

## 8. 세션 관리

- 세션 ID: UUID, 브라우저 `sessionStorage` + 서버 인메모리
- 히스토리: `history_max_turns=10`, 응답은 300자로 trim 후 저장
- TTL: 30분, 60초 주기 prune, 최대 10,000 세션 / 512KB per session
- 대화 컨텍스트는 Planner 가 `referenced_districts` / `referenced_category` 로 활용 ("거기서 카페는?" 가능)

## 9. 에러 처리

| 상황 | 감지 | 처리 | SSE |
|---|---|---|---|
| LLM 타임아웃 | fast 15s / slow 60s | 2회 재시도 + 지수 백오프 | `error` 또는 degraded `text` |
| LLM 연속 실패 | Circuit Breaker 임계 5회 | OPEN 60s, HALF_OPEN 재시도 | `text` (degraded) |
| Tool 타임아웃 | 15s | 스킵 후 부분 응답 | `tool_end` (status=timeout) |
| Tool 실행 에러 | transient → 2x 재시도 | 실패 시 Evaluator 가 부분 응답 | `tool_end` (status=error) |
| 세션 rate limit | slowapi 10/min (IP) | 429 + Retry-After | HTTP 에러 |
| 세션 Round 상한 | `rounds ≥ 3` | 수집된 결과로 Respond 진입 | 정상 `text` + `done` |
| Agent 동시 초과 | semaphore 20 | 대기 후 진행 (fairness) | — |

## 10. 관측 (Langfuse)

- `.env` 의 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` 설정 시 활성화
- 현재: 환경변수만 준비, graph callback 주입 wiring 향후 계획
- 추적 예정: Planner 분류 정확도, Tool latency, 토큰 비용

## 11. 수용 기준

- [x] 자연어 입력 → Planner 가 적절한 Tool plan 생성
- [x] SSE 스트리밍 (9 이벤트) 실시간 표시
- [x] AgentProgressIndicator 에 thinking / plan / tool 단계 표시
- [x] 카드·텍스트 포맷팅 정확 (card registry 5종)
- [x] 대화 컨텍스트 유지 (follow-up 가능)
- [x] 지도 클릭 시 자동 요약 (`useMapSync`)
- [x] `map_cmd` → 지도 반영
- [x] Evaluator 재진입 최대 3회
- [ ] Langfuse 콜백 주입 (wiring 대기)
