# F02. AI 챗봇 에이전트 Spec

> 기본 실행 경로는 **v2 agentic loop** — 모델주도 function-calling + Trust Kernel (`server/server/agent/loop/`).
> 레거시 **PAE(Planner-Actor-Evaluator)** 는 Mock 폴백 + `AGENT_LOOP_VERSION=pae` 롤백 스위치로 유지.
> 루프 내부·Trust Kernel·budget governor·PAE 노드·메타툴 상세는 [../../architecture/agent.md](../../architecture/agent.md) 참조.

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| Phase | 1A(Mock) · 1B(Real) — **완료** (2026-07 v2 agentic loop 전환) |
| Tier | Free (Phase 2에서 Free 일 5회 제한 예정) |
| 의존성 | F01 (상권 선택), D01 (데이터) |
| 아키텍처 | **v2 agentic loop** (LLM function-calling + Trust Kernel) → FastAPI SSE → Next.js ChatPanel |
| LLM | per-invoke preferred-first fallback chain: `claude-sonnet-4-6` → `gpt-5.4-mini` → `gemini-2.5-pro` → `gemini-2.5-flash` (전부 env-overridable, `LLM_PROVIDER` 가 선호 프로바이더를 맨 앞으로 승격) / Mock 프로바이더는 PAE 폴백 |
| 현재 세팅 | `agent_loop_version=v2` (config 기본값), budget governor 6턴 / 12콜 / 90s |

## 2. 실행 구조

v2 루프(`agent/loop/engine.py`)는 LLM 이 도구 스키마 12개(도메인 9종 + 메타 3종: resolve_district/compute/abstain)를 function-calling 으로 직접 선택·호출하고, 최종 응답에 Trust Kernel(±5% 수치 바인딩 검증 + 교정 패스 + `[미확인]` 마스킹/grounded_fallback)이 적용된다. PAE 는 Mock 모드 또는 `AGENT_LOOP_VERSION=pae` 롤백 전용. 디스패치 로직, 상태 구조, Trust Kernel 알고리즘, budget governor 전체는 [architecture/agent.md](../../architecture/agent.md) 참조.

## 3. Agent Tools — 도메인 9종

`@register_tool` 등록 9종 (`agent/tools/registry.py`). 메타툴 3종(resolve_district/compute/abstain)은 `agent/loop/tools_fc.py` 로컬 처리 — 스키마 총 12개. 각 Tool 입력/출력 상세는 [architecture/agent.md §5](../../architecture/agent.md) 참조.

| Tool | Card | 관련 기능 |
|---|---|---|
| `get_district_summary` | `summary` | F03 |
| `get_floating_population` | — | F03, F05, F06 |
| `get_estimated_sales` | — | F03, F04, F09 |
| `get_store_info` | — | F03, F04, F07 |
| `get_store_history` | `risk` | F08 |
| `get_population_info` | — | F03, F07 |
| `compare_districts` | `compare` | F05 |
| `recommend_business` | `recommend` | F07 |
| `simulate_revenue` | `simulation` | F09 |

Card 타입 5종: `summary` / `risk` / `compare` / `recommend` / `simulation` — 프론트 `CARD_REGISTRY` 5키와 1:1 일치.

## 4. 시스템 프롬프트 핵심 규칙

파일: `agent/loop/prompts.py::LOOP_SYSTEM_PROMPT` (v2) / `agent/prompts/system.py` (PAE)

1. 데이터 기반 답변, 추측 시 명시
2. 수치 언급 시 데이터 기준 분기 함께 안내
3. 추정 매출은 카드 매출 기반, 현금 매출 미포함 안내
4. 업종 추천 시 반드시 근거 제시
5. 리스크 요소는 솔직하게 안내
6. 응답은 간결하고 핵심적으로
7. 면책 조항: 투자 의사결정은 개인 책임

## 5. SSE 스트리밍

엔드포인트: `POST /api/chat` → `text/event-stream`

```json
{ "message": "강남역에서 카페 하면 어때?", "session_id": "uuid-...", "district_code": "3110032" }
```

- **v2 기본 방출 7종**: `thinking / tool / tool_end / card / text / suggestion / done`
- **최종 응답 스트리밍(옵션 B)**: 본문 `text` 는 Trust 검증 후 일괄 방출하되 작성 중 진행률을 `thinking`("응답 작성 중... n%")으로 표시 — 신규 이벤트 타입 없음, 롤백 `AGENT_LOOP_STREAM_FINAL=false`. 상세: [architecture/agent.md §2](../../architecture/agent.md)
- **PAE 추가 2종**: `plan`(Planner 완료) · `warning`(respond numeric_sanity 경고)
- **`map_cmd`·greeting 단축**(`text`+`suggestion`+`done`): `api/routes/chat.py` 가 에이전트 밖에서 방출
- 프론트 `SSEEvent` 유니온: 위에 `error` 포함 **10종**
- 이벤트 payload 전체 계약은 [architecture/backend.md §4](../../architecture/backend.md) 참조

## 6. Frontend 구현

| 컴포넌트 | 파일 | 역할 |
|---|---|---|
| ChatPanel | `components/chat/ChatPanel.tsx` | 컨테이너 (MessageList + SuggestionChips + ChatInput) |
| MessageList | `components/chat/MessageList.tsx` | 스크롤 + 메시지 렌더링 |
| MessageBubble | `components/chat/MessageBubble.tsx` | 텍스트 / 카드 분기 + react-markdown |
| AgentProgressIndicator | `components/chat/AgentProgressIndicator.tsx` | thinking→tool 진행 표시 (plan 은 PAE 경로만) |
| ChatInput | `components/chat/ChatInput.tsx` | 자연어 입력 |
| SuggestionChips | `components/chat/SuggestionChips.tsx` | 추천 질문 버튼 |

SSE 파서: `lib/sseParser.ts` (async generator) · 이벤트 dispatch: `lib/eventHandlers.ts`

### 지도 클릭 → Zero-LLM 프리뷰 (F13)

지도 클릭은 챗 자동 전송을 하지 않는다. `useMapSync` 훅이 `chatStore.setPreview(code)` 로 `GET /api/districts/{code}/preview`(LLM 무호출, Redis 24h 캐시)를 호출해 PreviewCard 를 렌더링하고, 사용자가 추천 질문 chip 또는 "AI 분석 보기"를 눌러야 에이전트 풀 파이프에 진입한다. ([F13](F13-district-preview.md) 참조)

## 7. 세션 관리

- 세션 ID: UUID — 프론트 `chatStore` 생성, 요청마다 전달
- 히스토리: `max_history_turns=10`, assistant 응답 300자 trim 저장. v2 는 최근 6턴만 프롬프트 주입
- TTL: 30분 / 10,000 세션 상한 / 512KB per session

## 8. 에러 처리

| 상황 | 처리 |
|---|---|
| LLM 타임아웃 (모델 턴 60s) | per-invoke preferred-first fallback chain (claude → gpt → gemini pro → flash), 전 후보 실패 시 사과 `text` + `done` |
| Circuit Breaker OPEN | 5회 실패 → OPEN 60s → HALF_OPEN 재시도 |
| Tool 에러 (v2) | `ToolMessage` 로 모델에 전달, 모델이 재시도/우회 판단 |
| 예산 상한 (v2) | 6턴/12콜/90s — 마지막 허용 턴은 prose 강제 finalize |
| Round 상한 (PAE) | `agent_max_rounds=3` 후 Respond 진입 |
| 레이트리밋 | `rate_limit_chat`(10/min)은 정의만, 라우트 미적용 (전역 60/min 만 유효) |

## 9. 관측 (Langfuse)

- `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` 둘 다 설정 시 활성화
- v2 루프 wiring 완료: `ainvoke_with_fallback` 에 콜백 주입, `done` 이벤트에 `trace_id` 동봉
- 피드백 스코어: `POST /api/feedback/score` → Langfuse score proxy (F12 L1)

## 10. 수용 기준

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
