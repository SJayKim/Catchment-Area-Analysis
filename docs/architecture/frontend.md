# Frontend Architecture

> Next.js 14 (App Router, TypeScript) 기반 단일 페이지. 지도 · 챗 · 카드 UI 3개 서브시스템으로 구성.

## 1. 디렉토리 구조

```
frontend/src/
├── app/
│   ├── layout.tsx           # 루트 레이아웃 (Pretendard + SSR data-theme cookie)
│   ├── page.tsx             # ▶ F11 랜딩 (Header/Hero/Bento/HowItWorks/BetaBanner/Footer)
│   ├── error.tsx            # 글로벌 route boundary (D.1) — reset + 홈 동선
│   ├── loading.tsx          # 글로벌 route loading (D.1) — role=status
│   ├── app/
│   │   ├── page.tsx         # ▶ 분석 앱 (Toolbar + SplitPanel + StatusBar + DeepLinkHandler + Feedback)
│   │   ├── error.tsx        # /app route boundary (D.1) — reset + 홈 링크
│   │   └── loading.tsx      # /app split-panel skeleton (D.1)
│   ├── privacy/page.tsx     # 개인정보 (Phase A — UX Sweep 2026-04-30)
│   ├── terms/page.tsx       # 이용약관 (Phase A)
│   ├── globals.css          # [data-theme='light'|'dark'] 이중 팔레트 + brand tokens + :focus-visible 글로벌 룰 (D.2)
│   └── proxy/
│       └── kakao-sdk/route.ts  # Kakao SDK 서버 프록시 (ORB 회피)
├── components/
│   ├── landing/             # Header, Hero, RoleSelector, HeroVisual, Bento, HowItWorks, BetaBanner, Footer (F11)
│   ├── feedback/            # FeedbackFab, FeedbackModal, FeedbackRow, FreeLimitSurvey, Toast (F12 + Phase B 토스트)
│   ├── layout/              # SplitPanel, Toolbar, StatusBar
│   ├── map/                 # MapContainer, DistrictLayer, HeatmapLayer,
│   │                        # MapControls, TimeSlider
│   ├── chat/                # ChatPanel, MessageList, MessageBubble,
│   │                        # ChatInput, SuggestionChips, PreviewCard (F13),
│   │                        # AgentProgressIndicator, cards/
│   ├── mobile/              # MobileLayout (모바일 조립 래퍼), BottomNav,
│   │                        # BottomSheet, BottomSheetHandle (모바일 viewport)
│   ├── common/              # FeatureGate (Phase F · Tier 게이팅 stub)
│   └── report/              # ReportDocument (PDF)
├── stores/                  # Zustand (chat, district, map, toast)
├── hooks/                   # useChat, useMapSync, useReportExport, useTier, useBreakpoint, useKeyboardInset
├── lib/
│   ├── api.ts               # fetch 래퍼 (fetchDistrictPreview, submitFeedback 포함)
│   ├── sseParser.ts         # SSE 스트림 파서 (async generator)
│   ├── eventHandlers.ts     # SSE event → store dispatch
│   └── types.ts             # 공유 타입 (District / ChatMessage / SSEEvent …)
└── types/
    └── kakao.maps.d.ts      # Kakao Maps SDK ambient 타입 선언
```

## 2. 라우팅 + 페이지 구성

| 라우트 | 역할 |
|---|---|
| `/` | F11 공개 랜딩 (브랜드 + role chip + Bento + 베타 배너). FeedbackFab 노출. |
| `/app` | 분석 앱. `?role=<r>&q=<prefill>` deep link → `chatStore.setRole()` + auto send (300ms). DeepLinkHandler 가 `?q=` 를 history 에서 scrub (B.6). |
| `/privacy` · `/terms` | 정책/약관 (Phase A — Footer 링크). |
| `/proxy/kakao-sdk` | Kakao Map SDK 서버 프록시. |

각 route 마다 `error.tsx` + `loading.tsx` (D.1) — error boundary 가 `reset()` 시그니처 + 홈 동선 제공, loading 은 `role=status` 로 a11y 친화 skeleton.

`/app` 레이아웃:

```
┌─────────────────────────────── Toolbar ────────────────────────────────┐
├──────────────────────── SplitPanel (드래그 30~80%) ────────────────────┤
│   MapContainer (Kakao Map)       │       ChatPanel (SSE streaming)    │
│    ├ DistrictLayer (폴리곤)       │       ├ MessageList                │
│    ├ HeatmapLayer (dynamic)      │       │   ├ PreviewCard (F13)       │
│    ├ MapControls (zoom)          │       │   ├ MessageBubble          │
│    └ TimeSlider (0~23h)          │       │   ├ FeedbackRow (F12 L1)   │
│                                  │       │   └ Card (5종)             │
│                                  │       ├ SuggestionChips            │
│                                  │       └ ChatInput                  │
├──────────────────────────────── StatusBar ─────────────────────────────┤
│                            FeedbackFab (F12 L3) / FreeLimitSurvey (L2) │
└────────────────────────────────────────────────────────────────────────┘
```

`useMapSync` 는 지도 클릭 시 LLM 호출 없이 `chatStore.setPreview(code)` 로 REST 프리뷰만 호출.
사용자가 PreviewCard 의 chip 이나 "AI 분석 보기" 를 눌러야 에이전트 풀 파이프라인(v2 agentic loop, Mock 모드는 PAE 폴백)으로 진입 (F13).

## 3. Zustand Store

### `chatStore.ts`

| state | 타입 | 용도 |
|---|---|---|
| `messages` | `ChatMessage[]` | user/assistant/card 메시지 |
| `isLoading` / `isThinking` | `boolean` | 로딩 인디케이터 |
| `sessionId` | `string` (UUID) | 서버 세션 키 |
| `agentSteps` | `AgentStep[]` | thinking→plan→tool 진행 표시 (plan 은 PAE 경로 전용 이벤트) |
| `suggestions` | `string[]` | 추천 질문 |
| `lastDistrictCode` | `string \| null` | 마지막 전송 상권 코드 |
| `currentAbortController` / `currentRequestId` | `AbortController \| null` / `number` | 취소 제어 + monotonic requestId (stale SSE 이벤트 drop) |
| `role` | `'owner' \| 'investor' \| 'founder' \| null` | F11 역할 온보딩 (deep link `?role=`) |
| `preview` / `previewLoading` / `previewError` | `DistrictPreview \| null` / `boolean` / `string \| null` | F13 zero-LLM 프리뷰 (module-private seq + AbortController race 가드, 10s watchdog) |
| `messageCount` | `number` | 세션 내 발화 카운트 |
| `lastTraceId` / `feedbackByTrace` | `string \| null` / `Record<string, 'up'\|'down'>` | F12 L1 피드백 (trace 당 1회 제한) |
| `mobileTab` / `sheetSnap` / `unreadCount` | `'map'\|'chat'` / `'hidden'\|'peek'\|'half'\|'full'` / `number` | 모바일 내비 서브시스템 (BottomNav/BottomSheet) |

주요 action: `sendMessage(msg, districtCode?, onMapCmd?)` → `/api/chat` 직접 호출(Next rewrite 우회), `sseParser.ts` + `eventHandlers.ts` 로 이벤트 dispatch. 최대 2회 재시도 (1s → 2s backoff, 4xx·Abort 는 재시도 안 함). SSE 스트림은 이벤트마다 리셋되는 **120s idle 타이머**로 abort. 모바일에서는 전송 시 `mobileTab='chat'` + `sheetSnap='full'` 승격.

PDF 요청은 서버로 보내기 전에 로컬에서 감지한다 — 통합 `PDF_PATTERNS` regex + false-positive 가드(≤30자, "뭐/알려/설명" 등 질문 키워드 차단) 매치 시 서버 미전송으로 `marketscope:generate-pdf` CustomEvent 만 발행.

### `districtStore.ts`

| state | 용도 |
|---|---|
| `selected: District \| null` | 현재 선택 상권. `District` = `{code, name, type, center, polygon?, dataQuarter?}` (`lib/types.ts`) |
| `selectSource: 'map' \| 'chat' \| null` | 선택 출처 — `selected` 내장 프로퍼티가 아닌 **별도 top-level 필드** |
| `isCompareMode` / `compareList (max 3)` | F05 비교 모드. `addToCompare` 는 3개 초과 시 toastStore warning 후 거부, 중복 code 무시 |
| `hoveredCode` | 호버 하이라이트 |

Playwright 디버깅용으로 `window.__districtStore` 노출 (chat/map/toast 포함 4개 스토어 모두 `window.__*Store` 동일 패턴).

### `mapStore.ts`

| state | 기본값 | 용도 |
|---|---|---|
| `center {lat, lng}` | 서울 (37.5665, 126.9780) | 지도 중심 |
| `zoom` | 11 | 초기 축척 |
| `activeLayers` | `['polygon']` | 활성 레이어 토글 |
| `heatmapEnabled` / `heatmapTimeSlot` | `false` / `12` | F06 히트맵 |
| `heatmapPlaying` | `false` | TimeSlider 자동 재생/정지 |
| `heatmapData` / `heatmapLoading` | `null` / `false` | 프리로드된 전 슬롯 |

### `toastStore.ts` (Phase B)

| state | 용도 |
|---|---|
| `toasts: Toast[]` | 활성 토스트 큐 (4s `info/success/warning`, 7s `error`) |
| `show(message, level?, options?)` | 토스트 발사. `options.actionLabel` + `onAction` 으로 retry 액션 (B.4) |
| `dismiss(id)` / `clear()` | 개별/전체 제거 |

비교 모드 cap (B.2), CompareCard remove (B.3), PDF retry (B.4) 등 상호작용 confirm 채널. `window.__toastStore` 로 디버깅 가능.

## 4. 훅

| 훅 | 용도 |
|---|---|
| `useChat` | 3 store 바인딩, `sendMessage` 콜백이 `map_cmd` 이벤트 처리 |
| `useMapSync` | 지도 클릭(map-origin) → `setView` 센터링 + zero-LLM `chatStore.setPreview(code)` 프리뷰만 발사 (자동 요약 쿼리는 2026-04-23 제거). 챗발(chat-origin) 선택은 SSE `map_cmd` 경로가 별도 처리 (`useChat` 콜백) |
| `useReportExport` | `html2canvas` 로 차트 캡처 → `@react-pdf/renderer` 로 PDF 다운로드. 실패 시 `toastStore` 로 재시도 액션 발사 (B.4) |
| `useTier` | Phase F stub — 현재 하드코딩 `'free'` 반환, Phase 2 OAuth/결제 머지 시 `/api/me` 응답 라이브 wiring |
| `useBreakpoint` | viewport breakpoint 감지 (mobile/tablet/desktop) — BottomNav/BottomSheet mount 분기 |
| `useKeyboardInset` | iOS Safari `visualViewport` 추적 — IME 오픈 시 BottomSheet/ChatInput 위치 보정 |

## 5. SSE 파서

### `lib/sseParser.ts`

- `ReadableStreamDefaultReader` 를 `async generator` 로 래핑
- UTF-8 decode → line split → `data: {json}` parse (`[DONE]` sentinel · JSON 파싱 실패 라인은 무시)
- 30초 무활동 시 `Promise.race` 타임아웃이 `{done: true}` 를 resolve → **throw 없이 generator 정상 종료** (실제 스트림 abort 는 chatStore 의 이벤트마다 리셋되는 120s idle 타이머가 담당)
- `finally` 에서 `reader.releaseLock()`

### `lib/eventHandlers.ts`

SSE `type` → store action 매핑. `SSEEvent` 유니온(`lib/types.ts`)은 **10종** (`error` 포함)이며 `handleSSEEvent` 가 10종 전부 처리한다. 진입 직후 `requestId` staleness 가드로 이전(중단된) 스트림의 잔여 이벤트는 silent drop.

| type | 처리 |
|---|---|
| `thinking` | 첫 이벤트 → `thinking` step 추가. 이후 이벤트 → `response` step 생성 후 **라벨 실시간 갱신**(`updateAgentStepStatus('response', 'in_progress', step)`) — v2 옵션 B 진행 이벤트("응답 작성 중... n%")가 이 갱신으로 표시된다 |
| `plan` | 이전 thinking 완료 + plan step 추가 (PAE 경로 전용 — v2 루프는 `plan` 미방출) |
| `tool` / `tool_end` | progress 라벨 + 종료 마킹 |
| `text` | 마지막 assistant 메시지에 append. 첫 수신 시 in_progress step 일괄 완료 + 1.5s 후 `agentSteps` 클리어 |
| `card` | 새 메시지로 카드 추가. 모바일 지도탭이면 `incrementUnread()`, compare 카드는 compareList 자동 동기화 |
| `suggestion` | `chatStore.suggestions` 교체 |
| `map_cmd` | 콜백으로 mapStore/districtStore 갱신 (방출처는 백엔드 `chat.py` 계층 유일) |
| `done` | `isLoading=false`, `trace_id` → `lastTraceId` (F12 피드백) |
| `error` | `isThinking=false` + `agentSteps` 클리어 + 오류 메시지를 마지막 assistant 메시지로 append |

## 6. Card UI

`components/chat/cards/registry.ts` 가 `card_type → Component` 매핑을 소유:

| card_type | 컴포넌트 | 주요 차트 |
|---|---|---|
| `summary` | SummaryCard | 시간대별 유동인구 바 차트 + Top 5 업종 |
| `compare` | CompareCard | 2~3 상권 지표 그리드 + AI 의견 |
| `recommend` | RecommendCard | ScoreBar + 추천 근거 + 면책 |
| `risk` | RiskCard | 안정성 게이지 + 업종별 생존기간 |
| `simulation` | SimulationCard | p25/avg/p75 범위 + 서울 평균 비교 |

공통: `InlineChart` (Recharts 래퍼), `SourcesCitation` (기관·라이선스 표시).

## 7. 스타일링

- **CSS 변수**: `--bg-primary` / `--bg-secondary` / `--text-primary` / `--text-secondary` / `--border-color` / `--text-muted` / `--bot-bubble` + 차트 토큰 5종 (D.7). `app/globals.css` 에 light/dark 이중 팔레트.
- **`:focus-visible` 글로벌 룰** (D.2): 모든 인터랙티브 요소에 outline ring (WCAG 2.4.7 보강).
- **Tailwind**: 유틸리티 클래스 + `tailwind.config.ts` 에 `msgIn` · `stepIn` 키프레임 커스텀.
- **`prefers-reduced-motion`**: globals.css 에서 motion-reduce 감지 (D.3 a11y).
- **테마**: light/dark 이중 팔레트 (data-theme cookie 기반 SSR).

## 8. Next.js 설정 (`next.config.mjs`)

- `output: 'standalone'` (Docker 프로덕션 빌드)
- `rewrites()`: `/api/*` → `BACKEND_INTERNAL_URL` (컨테이너 간 내부 네트워크)
- `NEXT_PUBLIC_KAKAO_MAP_KEY`, `NEXT_PUBLIC_API_URL` 은 빌드 타임에 bake
- Chat API는 rewrite 미사용 — `NEXT_PUBLIC_API_URL` 로 직접 호출(버퍼링 방지)

## 9. 주요 의존성

| 패키지 | 버전 | 용도 |
|---|---|---|
| `next` | 14.2.21 | 프레임워크 |
| `react` / `react-dom` | 18.3.1 | — |
| `zustand` | 5.0 | 상태 관리 |
| `recharts` | 2.15 | 차트 |
| `deck.gl` (core/layers/react/aggregation) | 9.2 | 히트맵 |
| `@react-pdf/renderer` | 4.3 | PDF |
| `html2canvas` | 1.4 | 차트 → 이미지 |
| `react-markdown` + `remark-gfm` | 10.1 / 4.0 | AI 응답 마크다운 |
| `tailwindcss` | 3.4 | 스타일 |
| `lucide-react` | 1.9 | 랜딩 아이콘 세트 (per-icon import) |
| `@playwright/test` | 1.58 | E2E |

## 10. E2E 테스트

`frontend/playwright.config.ts`: 4 project (chromium / mobile-iphone / mobile-galaxy / tablet-ipad) / 1 worker / 60s timeout / 30s expect / retries 0 (trace 는 `on-first-retry` 설정이나 retries 0 이라 사실상 비활성). Base URL `E2E_BASE_URL || http://localhost:3001`.

`frontend/e2e/` 구조 — spec 44파일 · test 선언 188개 (ring0 4파일·18 / ring1 25파일·99 / ring2 6파일·13 / ring3 7파일·35 + prod-smoke 1파일·11 + 레거시 루트 1파일·12, 2026-07-16 실측 — skip 선언 포함):

```
ring0-preflight/       00-stack-up                      (인프라 sanity)
                        02-error-boundary               (D.1 4 boundary 정적 회귀)
                        03-tier-hook                    (F.1 + F.2 useTier/FeatureGate stub)
                        stats-aggregate                 (Langfuse 11 차원/6 score 회귀)
ring1-features/        f01~f10, m01                     (기능별 핵심)
                        f11-landing, f12-feedback       (UX F11/F12)
                        a11y                            (D.2/D.4/D.6 ARIA 회귀)
                        d-perf                          (D.7 perf invariant)
                        d9-bottomnav                    (D.9 WCAG 2.5.8, mobile-iphone)
                        phase-b-ux-sweep                (B.1~B.6)
                        phase-c-ux-sweep                (C.1~C.5)
                        preview-api, mobile-sheet-open  (F13 + 모바일)
ring2-journeys/        j01~j05                          (5 user journey)
                        j06-ux-a2f-integration          (UX-A2F-J01~J05 통합 5 journey)
ring3-negative/        neg-no-district, neg-prompt-injection,
                        ops-endpoints, l1-langfuse,
                        neg-feedback-missing,
                        p0-regression, reg-2026-04-17
prod-smoke/            prod-smoke.spec.ts               (외부 도메인 smoke, prodGuard 우회)
(e2e 루트)             phase3-scenario.spec.ts          (레거시 Phase 3 시나리오 — ring 미배치,
                                                         testDir='./e2e' 라 수집 대상)
helpers/               setup.ts, prodGuard.ts, sseCapture.ts,
                       waitSSE.ts, polygonClick.ts, modeGuard.ts,
                       evalPacket.ts, backendLogs.ts
```

실행: `cd frontend && npm run test:e2e` (= `playwright test`. **`test` 스크립트는 없으므로 `npm test` 는 실패** — 링별 실행은 `npm run test:e2e:ring0`~`ring3`). USE_MOCK preflight 는 `scripts/e2e/` 참조. 회귀 매트릭스 + 통합 journey 는 [`docs/plan/qa/ux-final-e2e-regression-plan.md`](../plan/qa/ux-final-e2e-regression-plan.md) 참조.
