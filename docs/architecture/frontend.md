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
│   ├── mobile/              # BottomNav, BottomSheet (모바일 viewport)
│   ├── common/              # FeatureGate (Phase F · Tier 게이팅 stub)
│   └── report/              # ReportDocument (PDF)
├── stores/                  # Zustand (chat, district, map, toast)
├── hooks/                   # useChat, useMapSync, useReportExport, useTier, useBreakpoint, useKeyboardInset
└── lib/
    ├── api.ts               # fetch 래퍼 (fetchDistrictPreview, submitFeedback 포함)
    ├── sseParser.ts         # SSE 스트림 파서 (async generator)
    ├── eventHandlers.ts     # SSE event → store dispatch
    └── types.ts             # 공유 타입 (District / ChatMessage / SSEEvent …)
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
사용자가 PreviewCard 의 chip 이나 "AI 분석 보기" 를 눌러야 PAE 풀파이프로 진입 (F13).

## 3. Zustand Store

### `chatStore.ts`

| state | 타입 | 용도 |
|---|---|---|
| `messages` | `ChatMessage[]` | user/assistant/card 메시지 |
| `isLoading` / `isThinking` | `boolean` | 로딩 인디케이터 |
| `sessionId` | `string` (UUID) | 서버 세션 키 |
| `agentSteps` | `AgentStep[]` | thinking→plan→tool 진행 표시 |
| `suggestions` | `string[]` | 추천 질문 |
| `currentAbortController` | `AbortController \| null` | 취소 제어 |

주요 action: `sendMessage(msg, districtCode?, onMapCmd?)` → `/api/chat` 직접 호출(Next rewrite 우회), `sseParser.ts` + `eventHandlers.ts` 로 이벤트 dispatch. 최대 2회 재시도 (1s → 2s backoff).

PDF 요청(`/pdf/i` 또는 `리포트.*저장/i`)은 서버 보내기 전에 로컬에서 감지해 `marketscope:generate-pdf` CustomEvent를 발행한다.

### `districtStore.ts`

| state | 용도 |
|---|---|
| `selected: { code, name, polygon, source: 'map'\|'chat' } \| null` | 현재 선택 상권 |
| `isCompareMode` / `compareList (max 3)` | F05 비교 모드 |
| `hoveredCode` | 호버 하이라이트 |

Playwright 디버깅용으로 `window.__districtStore` 노출.

### `mapStore.ts`

| state | 기본값 | 용도 |
|---|---|---|
| `center {lat, lng}` | 서울 (37.5665, 126.9780) | 지도 중심 |
| `zoom` | 11 | 초기 축척 |
| `activeLayers` | `['districts']` | 활성 레이어 토글 |
| `heatmapEnabled` / `heatmapTimeSlot` | `false` / `12` | F06 히트맵 |
| `heatmapData` / `heatmapLoading` | — | 프리로드된 전 슬롯 |

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
| `useMapSync` | 지도 클릭 → 자동 요약 쿼리, 챗에서 상권 언급 시 지도 이동 |
| `useReportExport` | `html2canvas` 로 차트 캡처 → `@react-pdf/renderer` 로 PDF 다운로드. 실패 시 `toastStore` 로 재시도 액션 발사 (B.4) |
| `useTier` | Phase F stub — 현재 하드코딩 `'free'` 반환, Phase 2 OAuth/결제 머지 시 `/api/me` 응답 라이브 wiring |
| `useBreakpoint` | viewport breakpoint 감지 (mobile/tablet/desktop) — BottomNav/BottomSheet mount 분기 |
| `useKeyboardInset` | iOS Safari `visualViewport` 추적 — IME 오픈 시 BottomSheet/ChatInput 위치 보정 |

## 5. SSE 파서

### `lib/sseParser.ts`

- `ReadableStreamDefaultReader` 를 `async generator` 로 래핑
- UTF-8 decode → line split → `data: {json}` parse
- 30초 무활동 시 타임아웃 throw
- `finally` 에서 `reader.releaseLock()`

### `lib/eventHandlers.ts`

SSE `type` → store action 매핑:

| type | 처리 |
|---|---|
| `thinking` | `agentSteps` 에 thinking 추가 |
| `plan` | 이전 thinking 완료 + plan step 추가 |
| `tool` / `tool_end` | progress 라벨 + 종료 마킹 |
| `text` | 마지막 assistant 메시지에 append |
| `card` | 새 메시지로 카드 추가 |
| `suggestion` | `chatStore.suggestions` 교체 |
| `map_cmd` | 콜백으로 mapStore/districtStore 갱신 |
| `done` | `isLoading=false`, `agentSteps` fade-out |

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

`frontend/playwright.config.ts`: 4 project (chromium / mobile-iphone / mobile-galaxy / tablet-ipad) / 1 worker / 60s timeout / 30s expect / retry trace. Base URL `http://localhost:3001`.

`frontend/e2e/` 구조 (2026-04-30 UX Sweep 기준):

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
helpers/               setup.ts, prodGuard.ts, sseCapture.ts,
                       waitSSE.ts, polygonClick.ts, modeGuard.ts,
                       evalPacket.ts, backendLogs.ts
```

실행: `cd frontend && npm test` (`playwright test`). USE_MOCK preflight 는 `scripts/e2e/` 참조. 회귀 매트릭스 + 통합 journey 는 [`docs/plan/qa/ux-final-e2e-regression-plan.md`](../plan/qa/ux-final-e2e-regression-plan.md) 참조.
