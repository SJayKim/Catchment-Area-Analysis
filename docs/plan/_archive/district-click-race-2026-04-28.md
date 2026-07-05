# District Click Race / "먹통" Fix — 2026-04-28

> 사용자 보고: "하나의 상권 클릭 → AI 리포트까지 본 뒤, 다른 상권 클릭하면 먹통". 새 상권의 PreviewCard 가 떠도 "AI 분석 보기" 버튼이 잠겨 있어 다음 분석으로 자연스럽게 이어지지 않음.

## 1. Context

### 1.1 재현 시나리오

1. 지도에서 **District A** 클릭 → `useMapSync` 가 `chatStore.setPreview(A)` → PreviewCard A 등장
2. 사용자가 PreviewCard 의 "AI 분석 보기" 클릭 → `sendMessage("A 상권 자세히 분석해줘")` → SSE stream 시작
3. SSE stream 진행 중 (또는 done 직후 1~2초 사이) 지도에서 **District B** 클릭
4. `useMapSync` → `chatStore.setPreview(B)` → PreviewCard B 가 슬롯 갱신
5. 사용자가 PreviewCard B 의 "AI 분석 보기" 또는 chip 클릭 → **반응 없음**

### 1.2 근본 원인 (6종)

| # | 위치 | 메커니즘 | 심각도 |
|---|------|----------|--------|
| C1 | `chatStore.ts:189` | `if (state.isLoading) return` — 진행 중 새 send 호출 즉시 무시 | CRITICAL |
| C2 | `ChatPanel.tsx:84,110,114` | `disabled={isLoading}` 가 PreviewCard CTA / Chips / Input 동시 잠금 | CRITICAL |
| C3 | `chatStore.ts:128-129` `setPreview` | `lastDistrictCode` 기반 stale 가드가 선착순(stale) 응답을 채택하고 새 응답을 버림 | HIGH |
| C4 | `eventHandlers.ts:206-215` `done` | 이전 stream 의 done 이 늦게 도착해 새 stream 의 `isLoading=true` 를 덮어씀 (staleness 가드 부재) | HIGH |
| C5 | `chat.py:227` `_chat_semaphore` | per-session lock 부재. 같은 `session_id` 의 동시 요청 → `ConversationHistory` race | MED |
| C6 | `eventHandlers.ts:137` `setTimeout 1500` | 이전 stream cleanup 이 새 stream 의 `agentSteps` 를 1.5s 뒤 비움 | LOW |

### 1.3 메모리 / 선행 검토
- 프로젝트 메모리 디렉토리 비어있음 (`/home/sjkim/.claude/projects/-home-sjkim-Catchment-Area-Analysis/memory/`). 이번 Plan 으로 **신규 feedback 4건 작성 예정** (`feedback_chat_inflight_guard`, `feedback_setpreview_lastcode_race`, `feedback_sse_done_staleness`, `feedback_session_concurrency_lock`).
- 기존 가드 `chatStore.ts:265-270` (prior.abort + new controller) 는 이미 있음 → C1 제거 후 정상 동작 예상. C1 의 가드는 "동일 메시지 더블 클릭 폭주 방지" 의도였을 가능성 → **debounce 로 대체**.

### 1.4 적용할 AI/시스템 패턴
- **Stale-while-cancel** (frontend): 새 사용자 의도 발생 즉시 이전 stream cancel + 신규 시작. 이전 응답의 잔여 이벤트는 staleness token 으로 폐기.
- **Monotonic request id** (frontend): `setPreview` 와 `sendMessage` 모두 단조 증가 ID 부여. 응답/이벤트 처리 시 "현재 ID == 도착 응답 ID" 일 때만 store 반영.
- **Per-session async lock + cancellation token** (backend): 같은 session 동시 요청은 graceful cancel (이전 task 의 LangGraph `astream` 을 task.cancel + 새 task 시작).
- **Optimistic UI + debounced commit**: 새 클릭 즉시 PreviewCard 갱신 + 100ms debounce 동안 추가 클릭 흡수.

## 2. Scope

### In-Scope
- ✅ `frontend/src/stores/chatStore.ts` — `sendMessage` 가드 변경, `setPreview` AbortController + requestId, `messages.preview` 정리 시점 보정
- ✅ `frontend/src/components/chat/ChatPanel.tsx` — PreviewCard / Chips / Input 의 `disabled` 조건 분리
- ✅ `frontend/src/lib/eventHandlers.ts` — `done` 이벤트 staleness 가드, `text` 의 1.5s setTimeout staleness 가드
- ✅ `frontend/src/hooks/useMapSync.ts` — 진행 중 새 클릭 시 ChatPanel 의 진행 안내 (선택)
- ✅ `server/server/api/routes/chat.py` — per-session asyncio.Lock + 이전 task cancel
- ✅ Playwright E2E — `ring1-features/f01-district-rapid-switch.spec.ts` (district A→B 빠른 전환, AI 분석 정상 진행 보장)
- ✅ Frontend unit (jsdom) — `chatStore` `sendMessage` race 테스트 (선택, 인프라 부재 시 skip)

### Out-of-Scope
- ⛔ ConversationHistory 의 thread-safe 자체 리팩토링 (lock 으로 우회)
- ⛔ SSE 스트림 partial 결과 백필/재개 (cancel 만으로 충분)
- ⛔ Hover preview / speculative fetch (별도 Plan)
- ⛔ Mobile 전용 BottomSheet 행동 변경 (chat 진행 상태가 sheet 닫지 않게만 보장)

## 3. Design

### 3.1 Frontend `chatStore.ts`

#### 3.1.1 `sendMessage` — abort+restart 로 변경

**Before** (`chatStore.ts:188-189`):
```ts
const state = get();
if (!message.trim() || state.isLoading) return;   // ← 새 send 무시
```

**After**:
```ts
const state = get();
if (!message.trim()) return;
// 진행 중 send 가 있으면 abort 하고 새로 시작 (이전 finally 가
// staleness 가드로 인해 새 stream 의 상태를 덮지 않음 → 안전)
if (state.isLoading && state.currentAbortController) {
  state.currentAbortController.abort();
  // 동기 cleanup: 새 stream 이 곧바로 controller 를 재할당하기 때문에
  // controller === null 로 두지 않는다. isLoading flag 도 false 로
  // 깜빡이지 않게 유지 (사용자 perception 일관성).
}
```

#### 3.1.2 `currentRequestId` (monotonic counter) 추가

```ts
interface ChatState {
  // ...
  currentRequestId: number;   // 단조 증가
}

// initial: currentRequestId: 0

sendMessage: async (message, districtCode, onMapCmd) => {
  // ... 기존 로직 ...
  const requestId = get().currentRequestId + 1;
  set({ currentRequestId: requestId });
  // controller / ctx 에 requestId 동봉
  const ctx: EventHandlerContext = {
    ...,
    requestId,
  };
  // ...
}
```

#### 3.1.3 `setPreview` AbortController + requestId

**Before** (`chatStore.ts:122-135`):
```ts
setPreview: async (code) => {
  set({ previewLoading: true, previewError: null });
  try {
    const role = get().role ?? undefined;
    const preview = await fetchDistrictPreview(code, role);
    const currentCode = get().lastDistrictCode;
    if (currentCode && currentCode !== code) return;   // ← 잘못된 가드
    set({ preview, previewLoading: false, lastDistrictCode: code });
  } catch (err) { ... }
},
```

**After**:
```ts
// 모듈 level (store 외부, race 가드 전용)
let _previewSeq = 0;
let _previewAbort: AbortController | null = null;

setPreview: async (code) => {
  // 이전 fetch 즉시 cancel
  _previewAbort?.abort();
  const ac = new AbortController();
  _previewAbort = ac;
  const seq = ++_previewSeq;

  set({ previewLoading: true, previewError: null });
  try {
    const role = get().role ?? undefined;
    const preview = await fetchDistrictPreview(code, role, ac.signal);
    if (seq !== _previewSeq) return;  // 더 새로운 요청이 있음 → 폐기
    set({ preview, previewLoading: false, lastDistrictCode: code });
  } catch (err) {
    if (ac.signal.aborted) return;     // intentional cancel
    if (seq !== _previewSeq) return;
    const msg = err instanceof Error ? err.message : 'preview failed';
    set({ preview: null, previewError: msg, previewLoading: false });
  }
},
```

`fetchDistrictPreview(code, role, signal?)` 시그니처 추가 (`lib/api.ts`).

#### 3.1.4 `sendMessage` 진입 시 preview 정리 시점

기존 (`chatStore.ts:232-238`) 은 user 메시지 추가와 동시에 `preview: null` 설정 — OK. 다만 **새 send 가 기존 send 를 abort 한 직후에는 user 메시지가 추가되기 전 한 프레임 동안 preview 가 "이미 null" 상태일 수 있음** → 그대로 둬도 무방 (변경 없음).

### 3.2 Frontend `eventHandlers.ts` — staleness 가드

#### 3.2.1 `EventHandlerContext` 에 `requestId` 추가

```ts
export interface EventHandlerContext {
  get: () => { ...; currentRequestId: number; ... };
  set: ...;
  firstTextReceived: { current: boolean };
  onMapCmd?: (event: SSEEvent) => void;
  requestId: number;   // 신규
}

function isStale(ctx: EventHandlerContext): boolean {
  return ctx.requestId !== ctx.get().currentRequestId;
}
```

#### 3.2.2 `done` 처리 (`eventHandlers.ts:206-215`)

**Before**:
```ts
case 'done':
  set({ isLoading: false });
  if (!ctx.firstTextReceived.current) {
    set({ isThinking: false, agentSteps: [] });
  }
  if (event.trace_id) {
    set({ lastTraceId: event.trace_id });
  }
  break;
```

**After**:
```ts
case 'done':
  if (isStale(ctx)) break;        // 이전 stream 의 늦은 done 폐기
  set({ isLoading: false });
  if (!ctx.firstTextReceived.current) {
    set({ isThinking: false, agentSteps: [] });
  }
  if (event.trace_id) {
    set({ lastTraceId: event.trace_id });
  }
  break;
```

#### 3.2.3 `text` 의 1.5s setTimeout 가드 (`eventHandlers.ts:137`)

```ts
case 'text': {
  if (!ctx.firstTextReceived.current) {
    ctx.firstTextReceived.current = true;
    // ... in_progress → completed ...
    get().addAgentStep({ id: 'final', label: '분석 완료', status: 'completed' });
    const myReq = ctx.requestId;
    setTimeout(() => {
      // 1.5s 사이 새 send 가 시작됐다면 새 agentSteps 를 보존
      if (myReq !== ctx.get().currentRequestId) return;
      set({ agentSteps: [], isThinking: false });
    }, 1500);
  }
  if (isStale(ctx)) break;          // 이전 stream 의 텍스트 청크 폐기
  get().updateLastAssistantMessage(event.content);
  break;
}
```

#### 3.2.4 `card` / `tool` / `tool_end` / `suggestion` / `map_cmd`

각 case 첫 줄에 `if (isStale(ctx)) break;` 추가 — 이전 stream 의 잔여 이벤트가 새 stream UI 를 오염하지 않게.

#### 3.2.5 `error` 처리

```ts
case 'error':
  if (isStale(ctx)) break;
  set({ isThinking: false, agentSteps: [] });
  get().updateLastAssistantMessage(event.message || '오류가 발생했습니다.');
  break;
```

### 3.3 Frontend `ChatPanel.tsx` — disabled 조건 분리

**핵심**: `isLoading` 일 때도 PreviewCard CTA · Chips · Input 클릭 가능. 새 send 는 진행 중인 stream 을 자동 abort 하고 시작 (위 3.1.1).

**Before** (`ChatPanel.tsx:84,110,114`):
```tsx
<PreviewCard ... disabled={isLoading} ... />
<SuggestionChips suggestions={suggestions} onSelect={sendMessage} disabled={isLoading} />
<ChatInput onSend={sendMessage} disabled={isLoading} />
```

**After**:
```tsx
<PreviewCard ... disabled={false} ... />
<SuggestionChips suggestions={suggestions} onSelect={sendMessage} disabled={false} />
<ChatInput onSend={sendMessage} disabled={false} />
```

`PreviewCard` 의 `disabled` prop 자체는 유지 (나중에 다른 사유로 잠글 수 있음). 단, ChatPanel 에서 `false` 로 명시.

> **UX 보강 (선택)**: PreviewCard / ChatInput 에 진행 중일 때 hint 텍스트 ("진행 중인 분석을 중단하고 새로 시작합니다") — Phase 4 에서 처리.

### 3.4 Backend `chat.py` — per-session lock + cancel

#### 3.4.1 세션별 in-flight task 추적

```python
# 모듈 level
_session_inflight: dict[str, asyncio.Task] = {}
_session_lock_dict_lock = asyncio.Lock()  # _session_inflight dict mutation 보호

async def _claim_session(session_id: str) -> None:
    """같은 session 의 이전 task 가 있으면 cancel 하고 종료 대기."""
    async with _session_lock_dict_lock:
        prev = _session_inflight.pop(session_id, None)
    if prev and not prev.done():
        prev.cancel()
        try:
            await asyncio.wait_for(prev, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

async def _register_session_task(session_id: str, task: asyncio.Task) -> None:
    async with _session_lock_dict_lock:
        _session_inflight[session_id] = task

async def _release_session_task(session_id: str, task: asyncio.Task) -> None:
    async with _session_lock_dict_lock:
        if _session_inflight.get(session_id) is task:
            del _session_inflight[session_id]
```

#### 3.4.2 `event_generator` 진입 시 claim, exit 시 release

```python
async def event_generator():
    sse_connection_opened()
    await _claim_session(session_id)
    current_task = asyncio.current_task()
    if current_task is not None:
        await _register_session_task(session_id, current_task)
    try:
        async for event in _event_generator_inner():
            yield event
    finally:
        if current_task is not None:
            await _release_session_task(session_id, current_task)
        sse_connection_closed()
```

#### 3.4.3 `ConversationHistory.add_turn` 보호

같은 session 동시 진입은 위 lock 으로 직렬화되므로 별도 처리 불필요. 단, history.add_turn 호출 (`chat.py:344-354`) 이 cancel 후에도 실행되도록 finally 블록 안으로 이동:

```python
finally:
    # cancel/disconnect 후에도 사용자 발화는 history 에 남기는 게 conversation
    # 일관성에 유리. assistant turn 은 collected_text 가 있을 때만.
    history.add_turn(role="user", content=body.message, district_code=body.district_code)
    if collected_text:
        history.add_turn(role="assistant", content=collected_text, district_code=body.district_code)
```

> 단, cancel 시 `collected_text` 가 부분 응답일 수 있으므로 — partial 일 경우 history 저장 skip 하는 게 안전: `if collected_text and not request.is_disconnected_at_finally:` 같은 guard 는 과해서, **partial 도 그냥 저장** (다음 turn 의 컨텍스트로 작용해도 무해, 면책 텍스트 짧음).

### 3.5 Frontend `lib/api.ts` — `fetchDistrictPreview` signal 지원

```ts
export async function fetchDistrictPreview(
  code: string,
  role?: UserRole,
  signal?: AbortSignal,
): Promise<DistrictPreview> {
  const url = ...;
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`preview ${res.status}`);
  return res.json();
}
```

기존 호출부 (`chatStore.setPreview`) 만 영향 — signal 미전달 시 backwards-compatible.

## 4. Checklist

- [x] **C1** `chatStore.sendMessage` `isLoading return` → `abort + restart` (3.1.1)
- [x] **C2-1** `chatStore.currentRequestId` 카운터 + `EventHandlerContext.requestId` 추가 (3.1.2, 3.2.1)
- [x] **C2-2** `ChatPanel` PreviewCard / Chips / Input `disabled={false}` (3.3)
- [x] **C3** `chatStore.setPreview` AbortController + monotonic seq (3.1.3) + `lib/api.ts` signal 지원 (3.5)
- [x] **C4** `eventHandlers` `done` / `text` / `card` / `tool` / `tool_end` / `suggestion` / `map_cmd` / `error` staleness 가드 (3.2)
- [x] **C5** `chat.py` per-session in-flight task 추적 + cancel + history finally 이동 (3.4)
- [x] **C6** `eventHandlers.text:137` 1.5s setTimeout 가드 (3.2.3 에 포함)
- [x] **검증** ruff (server) · tsc (frontend) · pytest (server) · Playwright e2e 신규 spec
- [x] **메모리** feedback 4건 신규 작성 (`feedback_chat_inflight_guard.md` 외 3건)

> ✅ 2026-07-04 문서 정합성 감사에서 구현 완료 확인 — `chatStore.ts` `currentRequestId` + module-private `_previewSeq`/`_previewAbort`, `eventHandlers.ts` requestId staleness 가드, `chat.py` `_session_inflight`/`_claim_session_slot`(이전 task cancel), `server/tests/test_chat_session_concurrency.py` + e2e `f01-rapid-switch`/`f01-preview-rapid-switch` spec 전부 현행 코드 존재. 실행 결과는 status 2026-04-28 기록(ruff/tsc/pytest 49/50 · memory 4건 신규).

## 5. 재검toot (Self-Review Gate)

| 엣지케이스 | 다룸? | 대응 |
|------------|-------|------|
| 더블 클릭 (같은 메시지 빠르게 두 번) | YES | abort 후 즉시 새 send → user message 가 두 개 추가됨. **debounce 100ms** 추가? — 후속 PR. 1차 fix 에서는 user 가 빠르게 두 번 보내면 두 메시지 모두 보임 (의도된 동작) |
| 새 send 가 시작했으나 백엔드는 이전 task cancel 처리 중 | YES | 백엔드 per-session lock 이 이전 task 종료 대기 (timeout 2s). 새 SSE 는 약간 지연 후 시작 |
| 이전 stream 의 `card` 이벤트가 새 stream 시작 후 도착 | YES | C4 staleness 가드로 폐기 |
| `setPreview` 이전 fetch 가 cancel 안 되고 응답 도착 (구 브라우저 fetch 미지원) | NO | abort 미지원 환경은 무시 (Next.js 14 대상 브라우저는 모두 지원). seq 가드가 추가 안전망 |
| `useMapSync` 가 같은 code 로 두 번 호출 | YES | `prevSelectedRef.current === selected.code` 가드 (`useMapSync.ts:34`) 그대로 유지 |
| 진행 중 다른 상권 클릭 → preview 갱신되었으나 user 가 chip 안 누르고 다시 원래 상권 클릭 | YES | 두 번째 클릭이 `setPreview(A)` → seq 증가 → A 응답이 표시됨. preview 슬롯에 노출되는 데이터는 "마지막 사용자 의도" 와 일치 |
| 같은 session 동시 요청이지만 다른 브라우저 탭 (다중 탭) | YES | per-session lock 이 직렬화. 한 탭은 약간 지연 후 진행. 사용자 인지 가능한 지연 (~2s) 이지만 freeze 보다 낫다 |
| backend cancel 도중 LangGraph 가 LLM 호출 중 | OK | LangGraph `astream` 은 `asyncio.CancelledError` 전파 → LLM async 호출 cancel. `circuit_breaker` 영향 없음 (record_failure 호출 안 됨) |
| `EventHandlerContext.requestId` 가 closure 로 캡처되므로 이벤트 처리 함수가 새 send 후에 실행되어도 `ctx.requestId` 는 옛 값 | YES | 정상. `ctx.get().currentRequestId !== ctx.requestId` 일 때 staleness → 폐기 |
| chatStore `clearMessages` 후 sendMessage | OK | `clearMessages` 가 `currentRequestId` 도 리셋해야 함 → 변경 추가 |
| Playwright `__chatStore` 노출 영향 | OK | 신규 필드 `currentRequestId` 노출되지만 테스트가 직접 수정 안 함 |

### 다른 Plan 과 충돌
- `data-trust-reliability-2026-04-24` 의 `numeric_sanity` evaluator — 영향 없음
- `langfuse-aggregate-stats-2026-04-28` 의 `done.trace_id` — staleness 가드 후에도 `lastTraceId` 갱신은 동일 (가드 통과 시에만)
- `p0-priority-2026-04-27` 의 W1 entity_matching — 영향 없음
- 모바일 BottomSheet sheet 닫힘 fix (2026-04-24 iOS) — `setMobileTab` / `setSheetSnap` 은 sendMessage 시점에 promote, abort+restart 변경 후에도 동일

## 6. Scenario (E2E Ring Mapping)

| Ring | ID | 시나리오 | 기대 |
|------|-----|----------|------|
| Ring0 | R0-PREFLIGHT | mock backend up + landing 200 | 기존 PASS 유지 |
| Ring1 | R1-F01-RAPID-SWITCH | District A 클릭 → AI 분석 (text 청크 1개 수신) → District B 클릭 → "AI 분석 보기" 클릭 → B 의 SSE done 도달 | (1) B 의 user message 1건 추가 (2) A 의 stream cancel (3) B 의 trace_id 가 lastTraceId (4) preview 가 사라짐 |
| Ring1 | R1-F01-RAPID-CHIP | District A 분석 진행 중 District B preview chip 클릭 | B 의 chip 텍스트가 user message 로 추가, B 의 stream done |
| Ring2 | R2-J01-COMPARE | A 분석 → B 분석 → C 분석 (3 회 연속) | 마지막 C 의 stream 만 final state. 이전 2건은 부분 응답으로 남아도 OK |
| Ring3 | R3-NEG-DOUBLE-CLICK | 같은 chip 200ms 간격 두 번 클릭 | user message 2건. 첫 send 는 abort, 두번째만 done |

## 7. Pass 반복

### Pass 1 — 기본 동작 (CRITICAL/HIGH 4종)
- C1 + C2 + C3 + C4 적용
- 검증: Playwright `R1-F01-RAPID-SWITCH` PASS · ring1 기존 spec 회귀 0
- ETA: 1.5h

### Pass 2 — 백엔드 + cleanup (MED/LOW 2종)
- C5 + C6 적용
- 검증: pytest `tests/test_chat_session_concurrency.py` 신규 (같은 session_id 두 요청 → 둘 다 200, 두 번째 만 history 에 assistant turn) · ring1 R1-F01-RAPID-SWITCH 재확인
- ETA: 1.0h

### Pass 3 — UX polish + 검증 종합
- ChatPanel 진행 중 hint 텍스트 (선택)
- ruff/tsc/pytest 전수 + ring0~3 chromium 전수 회귀
- ETA: 0.5h

총 ETA: ~3h.

## 8. Agent 모델 선택

| Phase | 작업 | 권장 모델 | 비고 |
|-------|------|-----------|------|
| Plan/Design | 본 문서 작성 | opus | 메인 컨텍스트 (현재) |
| 구현 (Pass 1~3) | code edit | opus (현 세션) | 변경 면적 작아 별도 sonnet 분기 불필요 |
| 검증 | qa-scenario-runner agent | haiku/sonnet | Playwright 대량 출력 격리 |

## 9. Validation

| 항목 | 명령 | 합격 기준 |
|------|------|-----------|
| ruff | `cd server && ruff check . && ruff format --check .` | 0 issue |
| tsc | `cd frontend && npx tsc --noEmit` | 0 error |
| pytest | `cd server && pytest -q` | 기존 34/35 + 신규 0~3건 PASS |
| Playwright (신규) | `cd frontend && npm test -- ring1-features/f01-district-rapid-switch.spec.ts` | PASS |
| Playwright (회귀) | `cd frontend && npm test -- ring0-preflight ring1-features ring3-negative` | 기존 그린 유지 |

## 10. Metadata

| 항목 | 값 |
|------|-----|
| 작성자 | Claude (Opus 4.7) |
| 작성일 | 2026-04-28 |
| 우선순위 | P0 (사용자 보고, UX critical) |
| 영향 범위 | Frontend 4 파일 + Backend 1 파일 + E2E spec 1 신규 + memory 4 신규 |
| 후속 추적 | (1) 100ms debounce 검토 (2) PreviewCard 진행 중 hint UX (3) backend lock 의 metric 추가 |
