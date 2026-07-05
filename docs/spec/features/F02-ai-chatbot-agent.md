# F02. AI 챗봇 에이전트 Spec

> 기본 실행 경로는 **v2 agentic loop** — 모델주도 function-calling + Trust Kernel (`server/server/agent/loop/`) + FastAPI SSE 스트리밍.
> 레거시 **PAE(Planner-Actor-Evaluator) 그래프**(`agent/graph.py`)는 Mock 폴백 + 롤백 스위치로 유지.
> 상세 루프/Tool 레지스트리는 [../../architecture/agent.md](../../architecture/agent.md) 참조.

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| Phase | 1A(Mock) · 1B(Real) — **완료** (2026-07 v2 agentic loop 전환) |
| Tier | Free (Phase 2에서 Free 일 5회 제한 예정) |
| 의존성 | F01 (상권 선택), D01 (데이터) |
| 아키텍처 | **v2 agentic loop** (LLM function-calling + Trust Kernel) → FastAPI SSE → Next.js ChatPanel |
| LLM | per-invoke fallback chain: `claude-sonnet-4-6` → `gemini-2.5-pro` → `gemini-2.5-flash` (전부 env-overridable) / Mock 프로바이더는 PAE 폴백 |
| 현재 세팅 | `agent_loop_version=v2` (config 기본값) + budget governor `agent_loop_max_iterations=6` · `agent_loop_max_tool_calls=12` · `agent_loop_wall_clock=90s` |

> **디스패치**: `agent/runtime.py::_use_v2()` 가 `agent_loop_version == "v2" and llm_provider != "mock"` 일 때 v2 루프(`agent/loop/engine.py`)를, 그 외에는 PAE 그래프를 선택한다. mock 의 FakeListChatModel 은 tool-call 을 못 하므로 Mock E2E 는 항상 PAE 로 돈다. `AGENT_MODE`(=`agent_mode`, 기본 `"pae"`) 는 디스패치에 사용되지 않는 관측 라벨(`/api/health/detail`, Langfuse metadata)이며 실제 스위치는 `agent_loop_version` 뿐이다.

## 2. 실행 구조

### 2.1 v2 agentic loop (기본 — `agent/loop/engine.py`)

```
 START → [모델 턴] ──(tool_calls 有)──→ 도구 순차 실행 (+card) → ToolMessage append → 다음 턴
             │                          (budget governor: 6턴 / 12콜 / 90s — 마지막 턴은 도구 없이 prose 강제)
             └─(tool_calls 無)──→ 최종 draft
                                       ↓
                        Trust Kernel 검증 (unbound 수치 / ×10·×100 스케일 오기)
                                       ↓ 검출 시 prose 전용 교정 패스 1회
                        text (90자 청크) → suggestion → done
```

- Planner/Evaluator 역할 노드 없이 **LLM 이 도구 스키마 12개(도메인 9종 + 메타 3종, §4)를 직접 호출**한다.
- **Trust Kernel** (`agent/loop/trust.py`): 답변의 모든 수치 주장을 ±5%(`trust_numeric_tolerance=0.05`) 내에서 도구 반환값(또는 `compute` 파생값)에 바인딩 검사. 교정 후에도 잔존 unbound 가 **≥3 이고 전체 스코어 수치의 ≥50%** 일 때만 결정론적 `grounded_fallback`(코드측 라벨 + 도구 값만으로 생성, 카드 발행 시 abstention 금지)으로 전체 대체하고, 그 미만이면 draft 를 보존한 채 해당 수치만 `[미확인]` 으로 마스킹한다.

### 2.2 PAE 그래프 (레거시 — Mock 폴백 + `AGENT_LOOP_VERSION=pae` 롤백 스위치)

```
 START → PLANNER → ┬→ greeting END
                    ├→ ACTOR → EVALUATOR → ┬→ RESPOND → END
                    │                       └→ PLANNER (loop, max 3)
                    └→ RESPOND (fast path)
```

| 노드 | 책임 | 파일 |
|---|---|---|
| **Planner** | Intent 분류 (rule→LLM), Tool plan 생성, Entity 추출 | `server/server/agent/nodes/planner.py` |
| **Actor** | 의존성 layer 기반 병렬 Tool 실행, Card 발행 | `agent/nodes/actor.py` |
| **Evaluator** | Tool 결과 충분성 판정 (rule fast path or LLM), suggestion 생성 | `agent/nodes/evaluator.py` |
| **Respond** | 최종 응답 LLM 스트리밍 (토큰 → SSE `text`) | `agent/nodes/respond.py` |

상세 책임·프롬프트·에러 처리는 [architecture/agent.md](../../architecture/agent.md) 참조.

## 3. 상태 (`agent/state.py` — PAE 경로 전용)

v2 루프는 LangGraph state 없이 **메시지 리스트 + fact_pool**(도구 결과 원본 저장, LLM 미전송)로 동작한다. 아래 `AgentState` 는 레거시 PAE 그래프 전용이다.

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

## 4. Agent Tools — 도메인 9종 + v2 메타 3종

### 4.1 도메인 Tool (`@register_tool` 등록 9종 — `agent/tools/registry.py`)

| Tool | Card | 용도 | 관련 기능 |
|---|---|---|---|
| `get_district_summary` | `summary` | 4개 병렬 집계 (유동인구·매출·점포·메타) + 벤치마크 | F03 |
| `get_floating_population` | — (카드 미발행) | 시간대/성별/연령 | F03, F05, F06 |
| `get_estimated_sales` | — (카드 미발행) | 업종별 매출 (분기→월 환산) | F03, F04, F09 |
| `get_store_info` | — (카드 미발행) | 점포수, 개폐업, Top 업종 | F03, F04, F07 |
| `get_store_history` | `risk` | 안정성 / 생존기간 | F08 |
| `get_population_info` | — (카드 미발행) | 상주/직장 인구 | F03, F07 |
| `compare_districts` | `compare` | 2~3 상권 지표 비교 | F05 |
| `recommend_business` | `recommend` | Top 5 + 점수 + 면책 | F07 |
| `simulate_revenue` | `simulation` | p25/avg/p75 범위 + 서울 평균 비교 | F09 |

> `get_district_benchmarks` 는 `@register_tool` 미적용 **내부 헬퍼**(`agent/tools/benchmarks.py`) — `district_summary`/`store_history` 등이 직접 import 해 사용하며 레지스트리에 없다. `estimate_revenue`·`detect_floating_pop_anomaly` 라는 툴은 **코드에 존재하지 않는다** (매출 시뮬레이션의 실명은 `simulate_revenue`, 후자는 tool-name sanitizer 정규식 문자열로만 등장).

### 4.2 v2 메타 Tool (3종 — `agent/loop/tools_fc.py`, 레지스트리 밖 로컬 처리)

| Tool | 입력 | 역할 |
|---|---|---|
| `resolve_district` | `{name}` | 상권명 → 상권 코드 (`detect_district_by_name`), 실패 시 `not_found` |
| `compute` | `{expression}` | AST 기반 안전 산술 (모델 암산 금지) — 결과는 Trust Kernel 바인딩 가능한 fact 로 편입 |
| `abstain` | `{reason}` | "데이터 없음/서울 외" 1급 거부 → 정형 사과문 |

v2 루프가 LLM 에 노출하는 도구 스키마 = 도메인 9종 + 메타 3종 = **12개**. `category_code` 인자는 `_normalize_category` 가 CategoryResolver 로 자동 resolve 한다 ("카페"→CS100010 류).

각 Tool 구현 상세는 해당 기능 Spec(F03~F09) 참조.

## 5. 시스템 프롬프트

- **v2**: `agent/loop/prompts.py::LOOP_SYSTEM_PROMPT` (+ Trust Kernel 교정 패스 `corrective_instruction`)
- **PAE**: `agent/prompts/system.py`

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

### 6.2 이벤트 타입 (경로별 방출 집합이 다름)

| type | payload | v2 | PAE | 발생 시점 |
|---|---|:-:|:-:|---|
| `thinking` | `{step}` | O | O | 질문 분석 / 데이터 수집 / 결과 분석 / 수치 검증 |
| `plan` | `{intent, steps[]}` | ✗ | O | **PAE 전용** — Planner 완료 |
| `tool` | `{name, input, progress_label}` | O | O | Tool 호출 직전 |
| `tool_end` | `{name, done_label}` | O | O | Tool 종료 |
| `text` | `{content}` | O | O | v2: 검증 후 90자 청크 / PAE: Respond 토큰 |
| `card` | `{card_type, data}` (`data.dataSources[]` 포함) | O | O | card_type 매핑 Tool 성공 시 |
| `suggestion` | `{questions[]}` | O | O | 추천 질문 |
| `warning` | — | ✗ | O | **PAE 전용** — respond numeric_sanity 품질 플래그 |
| `map_cmd` | `{action, params}` | chat.py | chat.py | **`api/routes/chat.py` 가 유일 방출처** — 에이전트 실행 전 1회 |
| `done` | `{trace_id?}` | O | O | 스트림 종료 |

- **v2 기본 경로 방출 = `thinking / tool / tool_end / card / text / suggestion / done` 7종**.
- greeting 단축 응답(`text`+`suggestion`+`done`)과 `map_cmd` 는 두 경로 공통으로 `chat.py` 계층이 에이전트 밖에서 방출한다.

### 6.3 구현

`server/server/api/routes/chat.py`
- `sse_starlette.EventSourceResponse` 사용
- `event_queue: asyncio.Queue(maxsize=256)` backpressure 는 **PAE 그래프 전용** — v2 루프는 async generator 로 직접 yield
- 25s 주기 heartbeat (프록시 유지)
- 최대 지속 시간 5분 (`sse_connection_max_duration=300s`), 클라이언트 disconnect 시 graceful 종료

## 7. Frontend 구현

| 컴포넌트 | 파일 | 역할 |
|---|---|---|
| ChatPanel | `components/chat/ChatPanel.tsx` | 컨테이너 (MessageList + SuggestionChips + ChatInput) |
| MessageList | `components/chat/MessageList.tsx` | 스크롤 + 메시지 렌더링 |
| MessageBubble | `components/chat/MessageBubble.tsx` | 텍스트 / 카드 분기 + react-markdown |
| AgentProgressIndicator | `components/chat/AgentProgressIndicator.tsx` | thinking→tool 진행 표시 (plan 은 PAE 경로만) |
| ChatInput | `components/chat/ChatInput.tsx` | 자연어 입력 |
| SuggestionChips | `components/chat/SuggestionChips.tsx` | 추천 질문 버튼 |

SSE 파서는 `lib/sseParser.ts` (async generator), 이벤트 dispatch 는 `lib/eventHandlers.ts` 참조.

### 지도 클릭 → Zero-LLM 프리뷰 (F13)

지도 클릭은 **챗 자동 전송을 하지 않는다**. `useMapSync` 훅이 map-origin 선택 시 `chatStore.setPreview(code)` 로 REST `GET /api/districts/{code}/preview`(LLM 무호출, Redis 24h 캐시)를 호출해 PreviewCard 를 렌더링하고, 사용자가 추천 질문 chip 또는 "AI 분석 보기"를 눌러야 에이전트 풀파이프에 진입한다. (2026-04-23 이전의 `"상권 요약해줘"` 자동 전송은 제거됨 — [F13](F13-district-preview.md) 참조.)

## 8. 세션 관리

- 세션 ID: UUID — 프론트 `chatStore` 가 생성해 요청마다 전달, 서버는 인메모리 세션 키로 사용
- 히스토리: `max_history_turns=10`, assistant 응답은 300자(`history_content_limit`)로 trim 후 저장. **v2 루프는 그중 최근 6턴만 프롬프트에 주입**
- TTL: 30분, 60초 주기 prune, 최대 10,000 세션 / 512KB per session (`session_memory_limit_bytes`)
- 대화 컨텍스트: v2 는 히스토리를 프롬프트에 직접 포함하고 `resolve_district` 로 상권을 재해석. PAE 는 Planner 가 `referenced_districts` / `referenced_category` 활용 ("거기서 카페는?" 가능)

## 9. 에러 처리

| 상황 | 감지 | 처리 | SSE |
|---|---|---|---|
| LLM 타임아웃 | 모델 턴당 `llm_timeout_slow=60s` | per-invoke fallback chain 다음 후보 (claude → gemini pro → flash) | 전 후보 실패 시 사과 `text` + `done` |
| LLM 연속 실패 | Circuit Breaker 임계 5회 | OPEN 60s, HALF_OPEN 재시도 | `text` (degraded) |
| Tool 실행 에러 (v2) | `execute_fc_tool` 이 `(result, error)` 반환 | 에러 payload 를 ToolMessage 로 모델에 전달 — 모델이 재시도/우회 판단 | `tool_end` |
| Tool 타임아웃/재시도 (PAE) | `tool_execution_timeout=15s` | Actor 가 transient 에러 2회 재시도, 실패 시 부분 응답 | `tool_end` |
| 레이트리밋 | config `rate_limit_chat`(10/min)은 **정의만 존재, chat 라우트 데코레이터 미적용** (전역 60/min 만 유효) — 적용 여부는 별도 결정 대기 | — | — |
| 예산 상한 (v2) | `agent_loop_max_iterations=6` / `agent_loop_max_tool_calls=12` / `agent_loop_wall_clock=90s` | 마지막 허용 턴은 도구 없이 prose 강제 finalize | 정상 `text` + `done` |
| Round 상한 (PAE) | `rounds ≥ agent_max_rounds(3)` | 수집된 결과로 Respond 진입 | 정상 `text` + `done` |
| Agent 동시 초과 | semaphore 20 (`chat.py`) | 대기 후 진행 (fairness) | — |

## 10. 관측 (Langfuse)

- `.env` 의 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` 둘 다 설정 시 활성화 (`settings.langfuse_enabled`)
- **wiring 완료**: v2 루프가 `get_langfuse_handler()` 콜백을 `ainvoke_with_fallback` 에 주입하고, `done` 이벤트에 `trace_id` 를 동봉한다 (`agent/loop/engine.py`). 미설정 시 graceful degrade (no-op)
- 피드백 스코어: `POST /api/feedback/score` 가 `trace_id` 기반 Langfuse score proxy (F12 L1)

## 11. 수용 기준

- [x] 자연어 입력 → LLM 이 적절한 Tool 을 직접 선택·호출 (v2 function-calling / PAE 경로는 Planner plan)
- [x] SSE 스트리밍 실시간 표시 (v2 7종 이벤트 + chat.py 계층 `map_cmd`·greeting 단축)
- [x] AgentProgressIndicator 에 thinking / tool 단계 표시 (plan 은 PAE 경로만)
- [x] 카드·텍스트 포맷팅 정확 (card registry 5종: summary/compare/recommend/risk/simulation)
- [x] 대화 컨텍스트 유지 (follow-up 가능, v2 최근 6턴)
- [x] 지도 클릭 시 Zero-LLM 프리뷰 (`useMapSync` → F13 PreviewCard, 자동 챗 전송 없음)
- [x] `map_cmd` → 지도 반영 (chat.py 방출)
- [x] 종결 보장 — v2 budget governor (6턴/12콜/90s) / PAE Evaluator 재진입 최대 3회
- [x] Trust Kernel — 수치 바인딩 검증 + 교정 패스 + `[미확인]` 마스킹/grounded_fallback
- [x] Langfuse 콜백 주입 (v2 루프 wiring 완료, trace_id SSE 동봉)
