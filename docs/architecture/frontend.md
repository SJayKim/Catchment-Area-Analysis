# Frontend Architecture

> Next.js 14 (App Router, TypeScript) 기반 단일 페이지. 지도 · 챗 · 카드 UI 3개 서브시스템으로 구성.

## 1. 디렉토리 구조

```
frontend/src/
├── app/
│   ├── layout.tsx           # 루트 레이아웃 (CSS 변수 + Inter font)
│   ├── page.tsx             # 메인 (Toolbar + SplitPanel + StatusBar)
│   ├── globals.css          # 다크 테마 CSS 변수
│   └── proxy/
│       └── kakao-sdk/route.ts  # Kakao SDK 서버 프록시 (ORB 회피)
├── components/
│   ├── layout/              # SplitPanel, Toolbar, StatusBar
│   ├── map/                 # MapContainer, DistrictLayer, HeatmapLayer,
│   │                        # MapControls, TimeSlider
│   ├── chat/                # ChatPanel, MessageList, MessageBubble,
│   │                        # ChatInput, SuggestionChips,
│   │                        # AgentProgressIndicator, cards/
│   └── report/              # ReportDocument (PDF)
├── stores/                  # Zustand (chat, district, map)
├── hooks/                   # useChat, useMapSync, useReportExport
└── lib/
    ├── api.ts               # fetch 래퍼
    ├── sseParser.ts         # SSE 스트림 파서 (async generator)
    ├── eventHandlers.ts     # SSE event → store dispatch
    └── types.ts             # 공유 타입 (District / ChatMessage / SSEEvent …)
```

## 2. 페이지 구성 (`app/page.tsx`)

```
┌─────────────────────────────── Toolbar ────────────────────────────────┐
├──────────────────────── SplitPanel (드래그 30~80%) ────────────────────┤
│   MapContainer (Kakao Map)       │       ChatPanel (SSE streaming)    │
│    ├ DistrictLayer (폴리곤)       │       ├ MessageList                │
│    ├ HeatmapLayer (dynamic)      │       │   ├ MessageBubble          │
│    ├ MapControls (zoom)          │       │   ├ AgentProgressIndicator │
│    └ TimeSlider (0~23h)          │       │   └ Card (5종)             │
│                                  │       ├ SuggestionChips            │
│                                  │       └ ChatInput                  │
├──────────────────────────────── StatusBar ─────────────────────────────┤
└────────────────────────────────────────────────────────────────────────┘
```

`useMapSync` 훅이 `districtStore.selected.source === 'map'` 이면 자동으로 `"상권 요약해줘"` 쿼리를 챗으로 전달한다.

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

## 4. 훅

| 훅 | 용도 |
|---|---|
| `useChat` | 3 store 바인딩, `sendMessage` 콜백이 `map_cmd` 이벤트 처리 |
| `useMapSync` | 지도 클릭 → 자동 요약 쿼리, 챗에서 상권 언급 시 지도 이동 |
| `useReportExport` | `html2canvas` 로 차트 캡처 → `@react-pdf/renderer` 로 PDF 다운로드 |

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

- **CSS 변수**: `--bg-primary` / `--bg-secondary` / `--text-primary` / `--text-secondary` / `--border-color` / `--text-muted` / `--bot-bubble` 등 12종. `app/globals.css` 에 정의.
- **Tailwind**: 유틸리티 클래스 + `tailwind.config.ts` 에 `msgIn` · `stepIn` 키프레임 커스텀.
- **다크 테마 전용**: 라이트 모드 미지원 (CSS 변수가 단일 팔레트).

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
| `@playwright/test` | 1.58 | E2E |

## 10. E2E 테스트

`frontend/playwright.config.ts`: chromium / 1 worker / 60s timeout / 30s expect / retry trace. Base URL `http://localhost:3001`.

`frontend/e2e/` 구조:

```
ring0-preflight/       00-stack-up.spec.ts              (인프라 sanity)
ring1-features/        f01~f10, m01                      (10+1 spec)
ring2-journeys/        j01~j05                           (5 user journey)
ring3-negative/        neg-no-district, neg-prompt-injection,
                        p0-regression, reg-2026-04-17   (4 spec)
helpers/               setup.ts, prodGuard.ts            (SSE 캡처, prod 방지)
```

레거시 `feature1~7-*.spec.ts` 는 Ring 구조로 대체 후 유지 (후속 삭제 대상).

실행: `cd frontend && npm test` (`playwright test`). USE_MOCK preflight 는 `scripts/e2e/` 참조.
