# Landing · Onboarding · Feedback Plan

> 작성: 2026-04-23
> 출처: `docs/plan/marketscope_improvement.md` (3개 축 — 랜딩 / 단계별 가이드 / 피드백)
> 카테고리: `ui`
> 상태: 계획 수립 (구현 전)
> 선행: Accuracy Gap Fix W1~W4 (정확성 74→85+) — **동시 진행 가능하나 리소스는 Accuracy 우선**

---

## Context

`docs/plan/marketscope_improvement.md` 의 3개 개선 축을 MarketScope 실제 아키텍처에 맞춰 적용하는 계획.

### 원문 요구사항 요약

1. **랜딩 페이지** — 서비스 정체성/카피/Key Features/브랜드 컬러(Deep Blue · Teal) 노출
2. **단계별 사용 가이드** — 상권 클릭 시 **최소 정보** 먼저, 이후 **예시 질문** 선택/입력 유도
3. **피드백 루프** — 우하단 FAB 로 만족도(별점/이모지) + 주관식 수렴, "베타 무료" 강조

### 현재 상태와의 갭

| 축 | 현 구현 | 갭 |
|---|---|---|
| 랜딩 | 없음. 루트 `/` = 지도+챗 앱 (`app/page.tsx`) | 신규 랜딩 라우트 + 라우팅 이관 필요 |
| 단계별 가이드 | 지도 클릭 → `useMapSync` 가 **즉시** `"{name} 상권 요약해줘"` 자동 쿼리 (`hooks/useMapSync.ts:36-39`) → PAE 전체 실행 (TTFT 1.5s + 카드 6~8종) | **최소 정보 프리뷰 단계 부재**. 사용자가 클릭만 해도 LLM 비용/토큰 소모 |
| 예시 질문 | `SuggestionChips` 는 Evaluator 완료 후에만 노출 (`components/chat/SuggestionChips.tsx`) | **진입 시점** (첫 방문 · 상권 선택 직후) 가이드 chip 부재 |
| 피드백 | 채널 없음 | FAB + 수집 엔드포인트 부재 |
| 브랜드 | 다크 테마 CSS 변수 12종 (`app/globals.css`) 만 존재. 팔레트는 neutral dark | "Deep Blue / Teal" 정체성 토큰 부재 |

### Memory 참조 교훈

- `feedback_next_public_api_url_frontend_port.md` — 새 백엔드 엔드포인트(`/api/feedback`) 도입 시 `NEXT_PUBLIC_API_URL` 이 backend 포트(8002) 를 직접 가리키는지, rewrite 우회 구조를 유지하는지 확인. 빌드 타임 bake-in 주의.
- `feedback_probe_endpoint_shape_first.md` — `/api/feedback` POST body · response shape 은 spec 작성 전 실제로 curl + Pydantic 으로 shape 확정 후 E2E 작성.
- `feedback_e2e_user_message_pollution.md` — 랜딩의 hero 카피 텍스트가 Ring1 body.innerText() 매처에 오염 가능. 랜딩→앱 라우팅 변경 시 기존 spec 의 `page.goto('/')` 모두 재점검.
- `feedback_react_event_keys_unique.md` — 피드백 모달이 여러 번 열리거나 suggestion chip 가이드가 배열 렌더링될 때 `key` 에 인스턴스 id 포함 필수.
- `feedback_marketscope_sse_format.md` — 본 작업은 SSE 스펙 변경 없음. 프리뷰 엔드포인트는 **REST JSON** 로 설계 (Agent 비경유).
- `feedback_stale_container_vs_source.md` — 프론트 route 변경은 Docker next standalone 재빌드 필수. E2E 전 이미지 타임스탬프 확인.

### 전체 파이프라인 관점의 적용 원칙

1. **랜딩 = 프론트 전용** — 백엔드/Agent/DB 건드리지 않음. 순수 Next.js 라우트 분리.
2. **최소 정보 프리뷰 = REST 전용** — PAE Agent 경유 금지. 기존 `get_district_summary` Tool 을 얇게 래핑한 **신규 `/api/districts/{code}/preview`** 엔드포인트 (Tool call 없이 Repository 직접 호출). LLM 토큰 소모 0.
3. **가이드 질문 = 규칙 기반** — `agent/config/intents.yaml` 의 intent 프리셋에서 대표 질문 4~5개를 정적으로 추출해 프론트에 노출 (서버 호출 불필요).
4. **피드백 = MVP 는 외부 툴** — 1차 (이번 Plan) 는 Tally/Google Form 임베드로 DB 마이그레이션 회피. 2차 (성공 시) `/api/feedback` + Alembic 004 + `user_feedback` 테이블.
5. **Accuracy Gap 와 독립** — 파이프라인 중복 수정 없음. W2 (Conversational Query Rewriting) 은 Respond/Planner 수정, 본 Plan 은 라우팅/UI/REST 만.

---

### 2026 UI/UX 트렌드 리서치 델타 (2026-04-23 추가)

> 본 Plan 초안이 가정했던 "product tour · 별점 폼 · 강제 다크 · Framer Motion" 패러다임은 2026 기준 일부 **dated**. 아래 8개 축에서 트렌드 조사 후 기존 설계에 delta 로 반영 ([SaaSUI · SaaSFrame · Chameleon · MDN · Linear changelog · Toss/Kakao 한국 B2C 사례] 종합).

| # | 축 | 기존 Plan 가정 | 2026 델타 (반영) | 출처 패턴 |
|---|---|---|---|---|
| 1 | Onboarding | 랜딩 Hero chip + 앱 진입 시 프리뷰 (단계 가이드) | **Empty state = onboarding**. 튜토리얼 모달 0개. Hero chip 을 **role routing** (소상공인/투자자/창업준비 3-way) 로 확장 → starter prompt 페르소나별로 다름 | Claude.ai · Notion AI · Perplexity Discover |
| 2 | Landing Hero | 정적 텍스트 Hero + chip 4개 | **Live demo in hero** — 축소된 Kakao Map + Card 3종 Framer-loop. "Pretendard Variable" big-type H1 + weight/width animate | Linear · Vercel · Arc |
| 3 | Progressive disclosure | 프리뷰 카드 → chip → LLM | **Zero-LLM preview 를 Free 티어 기본값**으로 승격. `AI 분석 보기` CTA 명시. ghost hint (dotted underline) 로 비교모드 가이드 | Stripe · Linear · Height |
| 4 | Feedback | 우하단 FAB + Tally 폼 | (a) **카드별 👍👎** (Langfuse score 로 바로 배선, 이미 L1 wire 됨) (b) 무료 한도 소진 시 **microsurvey 1문항** (5-emoji scale + B01 검증 문구) (c) 일반 FAB 은 **카카오톡 채널 1:1 문의** 링크 (한국 B2C 응답률 2~3배) | Chameleon · Sprig · Claude.ai · Toss · Kakao for Business |
| 5 | Mobile | 미명시 | **Bottom sheet 패턴** (Airbnb 2026): `<768px` 에서 지도 70vh + chat peek 30vh, swipe-up 시 chat 전체 | Airbnb · OpenTable |
| 6 | Motion | `app/globals.css` `msg-in` · `step-in` keyframe | **View Transitions API** (Next.js 14 공식 지원) + `animation-timeline: scroll()` (JS 없이) + `prefers-reduced-motion` 필수 fallback. Lottie · GSAP 신규 도입 금지 | Interop 2026 · Chrome 2025 release |
| 7 | Dark/Light | landing = light / app = dark 강제 | **앱도 system preference 추적 + 우상단 토글**, 기본값 **light**. 한국 B2C fintech (Toss · Kakao Bank) 모두 light-first. "다크 전용" 은 2026 Korean B2C 에서 **제약**으로 읽힘 | Toss · Kakao Bank 2026 |
| 8 | 디자인 시스템 | Tailwind v3.4 + CSS 변수 12종 | **Tailwind v4 마이그레이션** (config.ts → `@theme`) + 팔레트 **OKLCH** (비교모드 blue/amber/rose) + 카드 `@container` (SplitPanel drag 중 자연스러움) + `.tokens.json` export | W3C DTCG stable v1 · Tailwind v4 · Interop 2026 |

### 델타 반영 범위 결정

- **Phase A~D 안에 녹임**: 1 (role chip), 2 (big-type + Pretendard), 3 (Zero-LLM = 이미 있음, CTA 카피만 재정의), 4 (FAB → 카카오 채널 + 카드 👍👎 추가)
- **Phase E 신설 (본 Plan 에 추가)**: 5 (모바일 bottom sheet), 6 (View Transitions + reduced-motion), 7 (테마 토글)
- **별도 Plan 으로 분리**: 8 (Tailwind v4 + OKLCH 마이그레이션) — 폭이 크고 다른 기능에 영향. 본 Plan 은 **v3.4 기반** 으로 먼저 출시, 이후 `docs/plan/ui/tailwind-v4-oklch-migration.md` 로 분리.

### 2026 델타 반영 시 핵심 리스크 재평가

| 리스크 | 원인 | 완화 |
|---|---|---|
| **R-1. 다크 강제로 B2C 이탈** | 소상공인·투자자는 주간 사무실/카페 환경 → 가독성 · 신뢰감 light 우위 | Phase E1 에서 테마 토글 도입. 기본값 light. CSS 변수 기반이라 추가 비용 작음 |
| **R-2. Live demo hero 의 번들 비대** | Kakao Map SDK 를 랜딩에 로드하면 LCP 저하 | 실제 Map 대신 **정적 PNG + CSS transform animate** 로 fake-demo. 지도는 `/app` 진입 시에만 실 로드 (기존 원칙 1 보존) |
| **R-3. 👍👎 스팸 / 오클릭** | Langfuse score 가 노이즈로 오염 | debounce 500ms + 세션당 카드별 1회 제한 + 음수 응답 시 자유 텍스트 1줄 선택 입력 |
| **R-4. 무료 한도 microsurvey 이탈** | 차단 화면 + 설문 = 이중 차단 | microsurvey 는 dismiss 가능 (X 버튼) + 쿠키로 주 1회 상한 |
| **R-5. View Transitions API Safari 호환** | Safari < 18 미지원 | progressive enhancement — 미지원 브라우저는 instant swap. 기능 회귀 없음 |

---

## Scope

### In

- 랜딩 라우트 분리 (`/` 랜딩 / `/app` 또는 `/analysis` 앱)
- 브랜드 토큰 확장 (Deep Blue 1색 + Teal accent) — 기존 다크 테마 보존
- 최소 정보 프리뷰 카드 (`PreviewCard`) + 프리뷰 REST 엔드포인트
- 가이드 질문 chip (랜딩 Hero 섹션 + 상권 선택 직후 2곳)
- `useMapSync` 개편: 자동 쿼리 OFF → 사용자 confirm 후 발사
- 피드백 FAB (카카오톡 채널 1:1 문의 링크 기반, MVP) + Tally fallback
- `feature-list.md` 에 F11(랜딩) · F12(피드백) 신규 항목 추가
- Ring1 F01/F02 spec 재점검 (`page.goto('/')` → `page.goto('/app')` 대체)
- **(델타 1) Role routing** — 랜딩 Hero 에 3-way 선택 (소상공인 / 투자자 / 창업 준비) → starter chip 세트 분기
- **(델타 2) Big-type Hero + Pretendard Variable** — Hero H1 font-weight scroll-driven animate, 한글 variable font 적용
- **(델타 2) Live demo hero** — 실 Map 아닌 정적 PNG + CSS transform loop 로 지도+카드 애니메이션 연출
- **(델타 3) Free 티어 = Zero-LLM preview 기본값** — `"AI 분석 보기"` CTA 카피 명시. B01 비즈니스 모델 티어와 정합
- **(델타 4) 카드별 👍👎 inline feedback** — Langfuse L1 score 배선 (`trace_id` 이미 SSE `done` 이벤트로 수신 중)
- **(델타 4) 무료 한도 소진 microsurvey** — 5-emoji scale + Premium 관심 문항 (dismiss 가능, 주 1회 상한)
- **(델타 5) 모바일 bottom sheet** — `<768px` 에서 SplitPanel → 지도 70vh + chat peek 30vh
- **(델타 6) View Transitions API + `prefers-reduced-motion`** — 카드 reveal stagger + reduced-motion fallback
- **(델타 7) 테마 토글** — 앱 우상단 light/dark/system 토글, 기본값 **light**. CSS 변수 light 팔레트 신설

### Out

- 백엔드 `/api/feedback` + DB 마이그레이션 (2차 Plan 으로 분리)
- OAuth2 / 회원가입 (Phase 2 상용화 Plan 에 이미 존재)
- 다국어 i18n (한국어 고정)
- Accuracy Gap Fix 의 GAP-A~F 수정 (별도 Plan)
- **Tailwind v4 + OKLCH 마이그레이션** — 별도 Plan `docs/plan/ui/tailwind-v4-oklch-migration.md` 로 분리 (폭이 큼)
- **GSAP / Lottie 신규 도입** — Framer Motion + CSS 로 충분, 번들 비대 회피
- **Shake-to-feedback / 웹 haptic** — 웹 한계 + 소상공인 혼란 리스크
- **shadcn/ui 전면 rewrite** — 수제 Tailwind 컴포넌트 충분, 신규 컴포넌트만 shadcn 스타일

---

## Design

### 1. 라우팅 구조

```
Next.js App Router
├── app/
│   ├── layout.tsx           # 루트 (기존 유지, <html> · <body> · CSS 변수)
│   ├── page.tsx             # ▶ 변경: 랜딩 페이지 (Hero + Features + CTA + Feedback FAB)
│   ├── app/
│   │   └── page.tsx         # ▶ 신규: 실제 분석 앱 (기존 page.tsx 내용 이관)
│   ├── globals.css          # ▶ 변경: brand token 추가 (--brand-deep-blue, --brand-teal)
│   └── proxy/               # 기존 유지
```

대안 A (채택): `/app` 세그먼트로 앱 이동.
대안 B: `/` 유지 + `?intro=1` 쿼리로 모달 오버레이. → 기각. 공유 URL 의미가 모호.

### 2. 랜딩 페이지 구성

> **(델타 1·2 반영)** Role routing 3-way + Big-type + Live demo PNG loop + Bento feature grid.

```
┌───────────────────────────────────────────────────────────┐
│  Header: MarketScope 로고 · 테마 토글 ⚪⚫ · "시작하기" CTA│
├───────────────────────────────────────────────────────────┤
│  Hero Section (Big-type · Pretendard Variable)            │
│   H1 (대형·weight scroll animate):                         │
│     "서울 1,650개 상권, AI가 읽어드립니다"                  │
│   Sub: "클릭 한 번이면 해당 상권의 유동인구·매출·업종을     │
│         3초 안에 요약해드려요."                             │
│                                                           │
│   [어떤 역할이신가요?] role chip 3개                       │
│     🧑‍🍳 소상공인    🏢 투자자    💡 창업 준비                │
│   └ 선택 시 아래 starter chip + Hero 카피 페르소나별 스왑   │
│                                                           │
│   Starter chip 4~5개 (role 별 달라짐)                      │
│     ex. 소상공인: "우리 동네 홍대 카페 매출 어때?"          │
│          투자자  : "강남 vs 성수 유동인구 비교"             │
│          창업   : "월 5천만원 투자로 열기 좋은 업종"        │
│   └ 클릭 → `/app?role=<r>&q=<prefill>` navigation          │
│                                                           │
│   Hero Visual (live-look demo, 실 Map 아님):              │
│     정적 PNG 지도 + Framer CSS transform 으로 폴리곤 펄스 │
│     → SummaryCard / CompareCard PNG 3개 교차 fade-in loop│
│     (8s 주기, `prefers-reduced-motion` → instant)        │
├───────────────────────────────────────────────────────────┤
│  Bento Key Features (6 cell, CSS Grid 3x2 / 모바일 1x6)   │
│   ① 지도 기반 탐색   (Map PNG)                             │
│   ② 대화형 AI 리포트 (Summary card thumb)                  │
│   ③ 2~3 상권 비교   (Compare card thumb)                   │
│   ④ 업종 추천       (Recommend card thumb)                 │
│   ⑤ 매출 시뮬레이션 (Simulation card thumb)                │
│   ⑥ PDF 리포트      (PDF thumb)                            │
│   └ 각 셀 hover 시 **실제 기능 동작을 재현** 하는          │
│      micro-interaction (loop PNG/SVG)                     │
├───────────────────────────────────────────────────────────┤
│  How It Works (3 step, 세로 진행 인디케이터)               │
│   1) 지도에서 상권 클릭                                    │
│   2) **LLM 호출 없이** 즉시 핵심 지표 프리뷰 (Free)         │
│   3) "AI 분석 보기" → 심층 분석 카드 수신                   │
├───────────────────────────────────────────────────────────┤
│  Beta 안내 배너 ("베타 기간 무료. 피드백 주신 분께 감사")   │
├───────────────────────────────────────────────────────────┤
│  Footer: 데이터 출처 · 면책 · 카카오톡 1:1 문의 · 깃허브    │
└───────────────────────────────────────────────────────────┘

FAB (우하단 고정, 랜딩/앱 공통): 💬 카카오톡 1:1 문의
  └ NEXT_PUBLIC_KAKAO_CHANNEL_URL (없으면 Tally fallback)
```

**대안 검토**:
- Hero 에 실 Kakao Map SDK 로드 → **기각** (R-2 랜딩 LCP 저하). 정적 PNG + CSS animate 채택.
- Hero chip 을 AI 가 동적 생성 (personalization) → **기각** (LLM 비용 0 원칙 위배). `intents.yaml` 정적 세트 + role 분기.

### 3. 브랜드 토큰 (CSS 변수 확장 · **델타 7 반영**)

> 랜딩만 라이트가 아니라 **앱도 light/dark 양방향** + system preference 추적. 기본값 **light**. Tailwind v3.4 CSS 변수 기반이라 v4 마이그레이션 전에도 가능.

`app/globals.css` (기존 변수 삭제 금지, light 팔레트 신설 + `[data-theme]` attribute 토글):

```css
:root,
[data-theme='light'] {
  /* 라이트 팔레트 (기본값, 한국 B2C fintech 관례) */
  --bg-primary: #FFFFFF;
  --bg-secondary: #F8FAFC;
  --bg-tertiary: #F1F5F9;
  --text-primary: #0F172A;
  --text-secondary: #475569;
  --text-muted: #64748B;
  --border-color: #E2E8F0;
  --bot-bubble: #F1F5F9;
  --user-bubble: #0B3D91;

  /* brand tokens (공통) */
  --brand-deep-blue: #0B3D91;      /* primary CTA, user bubble */
  --brand-teal: #14B8A6;            /* accent, link, highlight */
  --brand-deep-blue-hover: #0A3480;
  --brand-teal-hover: #0F9488;

  /* 비교모드 3색 (기존 DistrictLayer 유지) */
  --compare-slot-1: #3B82F6;
  --compare-slot-2: #F59E0B;
  --compare-slot-3: #F43F5E;
}

[data-theme='dark'] {
  /* 기존 다크 팔레트 그대로 (2026-04-23 현재 값 보존) */
  --bg-primary: #0F172A;
  --bg-secondary: #1E293B;
  --bg-tertiary: #283548;
  --text-primary: #F8FAFC;
  --text-secondary: #94A3B8;
  --text-muted: #64748B;
  --border-color: #334155;
  --bot-bubble: #1E293B;
  --user-bubble: #3B82F6;
  /* brand tokens 동일 */
}

/* system preference 자동 추적 (data-theme 미지정 시) */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme]) {
    color-scheme: dark;
    /* dark 변수 복사 */
  }
}

/* 감소 모션 (델타 6) */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

**폰트 (델타 2)**: `app/layout.tsx` 에 **Pretendard Variable** next/font import (한글 big-type 안전). 기존 Inter 는 라틴 fallback 으로만 유지.

**OKLCH 참고**: 본 Plan 은 v3.4 기반 hex 유지 (마이그레이션 비용 관리). 별도 Plan `docs/plan/ui/tailwind-v4-oklch-migration.md` 에서 위 hex 를 OKLCH 로 재매핑 (다크↔라이트 전환 시 채도 보존 목적).

**테마 토글 동작**: 우상단 토글 클릭 → `document.documentElement.setAttribute('data-theme', ...)` + `localStorage['theme']` 저장. 3-state: `light` / `dark` / `system`.

### 4. 단계별 공개 — 프리뷰 파이프라인

#### 현재 흐름 (문제)

```
지도 클릭 → districtStore.select() → useMapSync
           ↓
     chatStore.sendMessage("홍대 상권 요약해줘", code)
           ↓
     POST /api/chat (SSE) → PAE full run (6~8 Tool)
           ↓
     Card 5~6종 발행 (유동인구/매출/점포/추천/…)

문제: 사용자가 **탐색 의도** 인지, **분석 의도** 인지 구분 없이 모든 클릭이 풀파이프 소모.
```

#### 신규 흐름

```
지도 클릭 → districtStore.select()
           ↓
     ┌─────────────────────────────┐
     │  PreviewCard (챗 패널 최상단) │   ← REST GET /api/districts/{code}/preview
     │  ┌─────────────────────────┐│    (Agent 비경유, ~100ms)
     │  │ 지역명 · 유형 · 동 정보   ││
     │  │ 주요 업종 Top 3 (점유율) ││
     │  │ 유동인구: 전분기 대비 +x%│
     │  │ [이 상권 더 알아보기] btn││
     │  └─────────────────────────┘│
     │  예시 질문 chip 5개          │
     │  (또는 직접 입력)             │
     └─────────────────────────────┘
           ↓ (사용자 클릭/입력 시에만)
     chatStore.sendMessage(...) → PAE run
```

#### 신규 엔드포인트 `GET /api/districts/{code}/preview`

```yaml
response:
  district_code: str
  district_name: str
  district_type: str                # 상주/발달/관광/골목
  gu: str
  dong: str
  top_categories:                    # max 3
    - { code, name, share_pct }      # stores 테이블 + category_metadata join
  floating_population_trend:
    current_quarter: int             # 해당 상권 일평균
    prev_quarter_delta_pct: float    # 전분기 대비 % (양/음)
  suggested_questions:               # intents.yaml 에서 4~5개 추출
    - "이 지역 어떤 업종이 잘 될까?"
    - "비슷한 상권이랑 비교해줘"
    - "매출 시뮬레이션 해줘"
    - "이 상권의 리스크는?"
    - "시간대별 유동인구 패턴 알려줘"
```

- **구현 위치**: `server/server/api/routes/districts.py` 에 라우트 추가
- **Repository 직접 호출**: `DataAccess.stores.get_top_categories(district_code, limit=3)` + `DataAccess.floating_population.get_quarter_trend(district_code)` — 기존 repo 에 메서드 없으면 최소 확장
- **캐시**: Redis key `preview:{district_code}` TTL 24h (기존 `report:` 캐시 규약 준수)
- **LLM 호출 금지** — 비용 0 보장
- **Mock 지원**: `mock/` 구현체에 JSON fixture 확장

### 5. 가이드 질문 추출 전략

`agent/config/intents.yaml` 에 정의된 intent 프리셋에서 대표 질문을 추출.

```python
# server/server/api/routes/districts.py 프리뷰 핸들러 내부
SUGGESTED_QUESTIONS_TEMPLATES = [
    ("comparison", "비슷한 상권이랑 비교해줘"),
    ("recommendation", "어떤 업종이 유망할까?"),
    ("simulation", "월 매출 시뮬레이션해줘"),
    ("risk", "이 상권의 리스크는?"),
    ("heatmap", "시간대별 유동인구 보여줘"),
]
```

Frontend 는 이 문자열을 `SuggestionChips` 컴포넌트로 렌더.

### 6. 피드백 — 3-layer 모델 (**델타 4 반영**)

> 기존 "FAB 단일 채널" 에서 **L1 inline · L2 microsurvey · L3 FAB** 3단으로 확장.
> 한국 B2C 자료 기준 카카오톡 채널 > 웹 폼 (응답률 2~3배), 별점 < 5-emoji, 이메일 요구 = 즉사.

#### L1 — 카드별 inline `👍 👎` (Claude.ai · Perplexity 패턴)

- **위치**: 각 Card footer, `SourcesCitation` 옆
- **구성**: `👍 👎` 아이콘 버튼 2개 + (👎 클릭 시) 선택형 chip 3개 ("부정확함" / "느림" / "주제 벗어남") + 자유 텍스트 1줄 (optional, 60자 제한)
- **데이터 경로**: `trace_id` 는 SSE `done` 이벤트에서 이미 수신 중. **Langfuse score API** (`tracer.score(trace_id, name='user_feedback', value=1 or -1)`) 로 직접 배선 → DB 변경 없음
- **스팸 가드 (R-3)**: debounce 500ms · 세션당 카드별 1회 제한 · 동일 `trace_id` 중복 전송 시 서버 무시
- **컴포넌트**: `components/chat/cards/FeedbackRow.tsx` 신규 → 5 Card 공통 사용

#### L2 — 무료 한도 소진 microsurvey (Free tier 전환 신호 수집)

> Phase 2 상용화 착수 전 **B01 비즈니스 모델 검증용**. 일 5회 제한은 Phase 2 에서 도입 예정이므로, 본 Plan 에서는 **UI + 쿠키 상한만 준비** 하고 서버 게이팅은 Phase 2 에 결합.

- **트리거**: `chatStore.messageCount >= DAILY_FREE_LIMIT` 조건 (현재 enforcement 없음, UI만 구현)
- **노출 조건**: 쿠키 `ms_survey_week_<yyyyww>` 부재 시 (주 1회 상한)
- **문항 1** (필수): `"방금 받은 분석, 얼마나 도움이 됐나요?"` → 5-emoji (😡😞😐🙂😍)
- **문항 2** (선택, 문항1 🙂/😍 응답 시만): `"Premium 요금(월 ₩9,900)에 관심 있으신가요?"` → 네/아니오/나중에
- **Dismiss**: X 버튼으로 닫힘, 쿠키 기록 → 주 1회 재노출
- **데이터 경로**: `window.dataLayer` GA4 이벤트만 발사 (백엔드 수정 0) → 후속 2차 Plan 에서 `/api/feedback` 이관

#### L3 — FAB (일반 의견, 랜딩/앱 공통)

- **위치**: 우하단 고정, `z-index: 50`, 모바일에서는 Chat 입력창과 충돌 회피 (아래 9 섹션)
- **클릭 동작**:
  - `NEXT_PUBLIC_KAKAO_CHANNEL_URL` 존재 → 카카오톡 채널 1:1 문의로 신탭 오픈 (한국 B2C 기본 채널)
  - 부재 → Tally.so iframe 모달 fallback (`NEXT_PUBLIC_FEEDBACK_FORM_URL`)
  - 둘 다 부재 → FAB **숨김** (개발 환경 오노출 방지, R 2-EDGE-1 회귀)
- **컴포넌트**:

```
frontend/src/components/feedback/
├── FeedbackFab.tsx           # 우하단 고정, 카카오 > Tally > 숨김 분기
├── FeedbackModal.tsx         # Tally iframe fallback, ESC 닫기 + focus trap
├── FeedbackRow.tsx           # L1 카드 footer 👍👎
└── FreeLimitSurvey.tsx       # L2 microsurvey 모달
```

- **환경 변수**:
  - `NEXT_PUBLIC_KAKAO_CHANNEL_URL` (신규 · 1순위)
  - `NEXT_PUBLIC_FEEDBACK_FORM_URL` (기존 · 2순위)

**DB 마이그레이션 없음.** Langfuse L1 은 이미 배선됨. GA4 이벤트 키만 신설.

2차 Plan 에서 자체 구현 이관 (`/api/feedback` + Alembic 004, `user_feedback` 테이블 · microsurvey 응답 집계용).

### 7. `useMapSync` 개편

```typescript
// 현재 (hooks/useMapSync.ts:36)
useChatStore.getState().sendMessage(`${selected.name} 상권 요약해줘`, selected.code);

// 개편 후
useChatStore.getState().setPreview(selected.code);   // 프리뷰 페치만
// sendMessage 는 사용자가 chip 클릭/입력 시에만 발사
```

`chatStore` 에 `preview: DistrictPreview | null` 상태 + `setPreview(code)` action 추가.

---

### 8. Motion / Micro-interaction (**델타 6 반영**)

> Framer Motion 신규 의존 0, 번들 비대 회피. CSS + 표준 API 만 사용.

#### 카드 reveal stagger

- SSE `card` 이벤트로 추가된 `MessageBubble` 컨테이너에 `style={{animationDelay: '${idx*90}ms'}}` 적용
- `@keyframes msg-in` (기존) 재사용, stagger 만 추가
- 5~8 카드가 자연스럽게 순차 등장

#### View Transitions API (Next.js 14 공식)

- 비교모드 진입/해제 · 랜딩 → `/app` 라우팅 · PreviewCard → 분석 카드 전환에 적용
- Next.js 14 `experimental.viewTransition` 플래그 (`next.config.mjs`) 활성화 + `<Link>` 에 `unstable_ViewTransition` wrapper
- **Safari < 18 progressive enhancement**: 미지원 브라우저는 기본 Next navigation (무애니메이션) → 기능 회귀 0 (R-5)
- 카드 cross-fade 는 CSS `view-transition-name: card-<trace_id>` 로 매칭

#### `prefers-reduced-motion` 필수 (접근성)

- `globals.css` 에 전역 media query (섹션 3 브랜드 토큰 블록에 포함)
- 모든 animation/transition duration 을 0.01ms 로 클램프
- 비교모드 morph · 카드 stagger · Hero weight animate 모두 skip

#### Scroll-driven hero typography (랜딩 전용)

- `animation-timeline: scroll()` (CSS, Chromium/Firefox 2026 안정)
- Hero H1 `font-variation-settings: 'wght'` 를 scroll progress 로 400→900 변화
- Fallback: 스크롤 기반 미지원 브라우저는 정적 weight 700 고정

**배제 목록**: Lottie (JSON 용량 + 지하/3G 체감 저하) · GSAP (번들 ~30KB · CSS 로 충분) · 웹 haptic (소상공인 실수 트리거 리스크)

---

### 9. 모바일 Bottom Sheet (**델타 5 반영**)

> `<768px` 에서 현재 SplitPanel 은 지도가 너무 작아져 사용 불가. Airbnb 2026 패턴 채택.

#### 레이아웃 분기

| breakpoint | 레이아웃 |
|---|---|
| `≥1024px` | 현재 SplitPanel (30~80% drag) 유지 |
| `768~1023px` | SplitPanel 고정 50/50 (drag 비활성, 지도 우선) |
| `<768px` | **Bottom sheet**: 지도 전체화면 + chat 을 하단 시트로 (peek 30vh → swipe-up 으로 95vh) |

#### 구현

- `components/layout/MobileBottomSheet.tsx` 신규 — `framer-motion` 없이 CSS `scroll-snap-type: y mandatory` + 3-snap point (peek / half / full)
- `window.matchMedia('(max-width: 768px)')` 로 SplitPanel ↔ BottomSheet 분기. `useEffect` SSR hydration 주의
- 지도 클릭 → PreviewCard 가 sheet 에 들어오며 자동으로 half 로 snap
- FAB (L3 피드백): 모바일에서는 sheet 상단 drag handle 옆 아이콘으로 이동 — Chat 입력창과 겹침 방지 (기존 엣지케이스 5 해소)

#### 검증

- Playwright `iPhone 12` device emulation + snap point 전환 확인
- `touch-action: pan-y` 명시해 지도 pan 과 sheet swipe 충돌 방지

---

### 10. 테마 토글 (**델타 7 반영**)

> 앱도 system preference 자동 추적 + 사용자 토글. 기본값 light (한국 B2C).

#### 동작

1. **초기값 결정 (layout.tsx 서버측)**:
   - Cookie `theme` 우선 (`light` / `dark` / `system`)
   - 없으면 `system` → `<html>` 에 `data-theme` 미지정 → CSS `@media (prefers-color-scheme)` 가 처리
   - 없으면 기본 `light`
2. **런타임 토글**: 우상단 아이콘 버튼 클릭 → 3-state 순환 (`☀️ light` → `🌙 dark` → `🖥️ system`)
3. **저장**: `document.cookie = 'theme=...; path=/; max-age=31536000'` (1y)
4. **FOUC 방지**: `layout.tsx` 에서 cookie 읽어 `<html data-theme="...">` SSR 렌더

#### 컴포넌트

- `components/layout/ThemeToggle.tsx` 신규 — `Toolbar` 우측에 배치 (기존 Toolbar 는 좌 로고 · 우 CTA 2슬롯, 우측에 추가 1슬롯)
- 접근성: `aria-pressed` · 3-state 시 `aria-label="테마: 시스템 기본"` 등 현재 상태 음성 안내

#### 랜딩 페이지

- 랜딩도 동일 토글 노출 (header 내). **기본 light** 는 유지하되 사용자 선택 존중.
- H3 Hero Visual PNG 는 light/dark 2종 각각 준비 (`hero-demo-light.png` / `hero-demo-dark.png`)

---

## Checklist

### Phase A — 랜딩 라우트 + 브랜딩

- [ ] A1. `app/app/page.tsx` 생성 후 기존 `app/page.tsx` 내용 이관
- [ ] A2. `app/page.tsx` 를 랜딩으로 재작성 (Hero / Bento Features / How / Beta banner / Footer)
- [ ] A3. `globals.css` 를 `[data-theme='light'|'dark']` attribute 기반 이중 팔레트로 리팩터링 — brand tokens (Deep Blue · Teal) + 비교모드 3색 + compare-slot 토큰 명시. 기존 변수 값은 `[data-theme='dark']` 에 보존 (델타 7 선행 조건)
- [ ] A4. Landing 전용 컴포넌트 `components/landing/{Header,Hero,RoleSelector,HeroVisual,BentoFeatures,HowItWorks,BetaBanner,Footer}.tsx` (델타 1·2 반영)
- [ ] A5. Toolbar 로고 클릭 → `/` (랜딩) 이동
- [ ] A6. 랜딩 Hero chip 4~5개 클릭 시 `/app?role=<r>&q=<prefill>` 로 이동 후 `chatStore.sendMessage` 자동 발사
- [ ] A7. Playwright `baseURL` 변경 없이 기존 Ring1/2 spec 의 `page.goto('/')` 를 `page.goto('/app')` 로 일괄 치환 (helper `gotoApp()` 도입)
- [ ] **A8. (델타 1) Role routing** — `RoleSelector` 3-way chip (소상공인 / 투자자 / 창업 준비) → 선택 시 Hero 카피 · starter chip · CTA 문구 스왑. 선택 상태는 `localStorage['role']` 보존
- [ ] **A9. (델타 2) Pretendard Variable** — `app/layout.tsx` 에 `next/font/google` 또는 self-host Pretendard 1.3.9 weight 100-900 + italic. Inter 는 라틴 fallback 유지
- [ ] **A10. (델타 2) Hero Visual PNG loop** — 정적 지도 PNG (light/dark 2종) + SummaryCard/CompareCard/RecommendCard thumbnail 3장 cross-fade 8s loop. `prefers-reduced-motion` 시 첫 프레임만 표시
- [ ] **A11. (델타 2) Bento Features 6 cell** — CSS Grid `grid-template-columns: repeat(3, 1fr)` (모바일 1fr) · 각 셀에 기능 미리보기 이미지 + hover micro-interaction

### Phase B — 단계별 프리뷰 파이프라인

- [ ] B1. `server/server/repositories/protocols.py` 에 `DistrictPreviewRepository` 프로토콜 추가 (기존 repo 재사용 가능 여부 먼저 점검)
- [ ] B2. `mock/` · `real/` 에서 `get_preview(code)` 구현
- [ ] B3. `api/routes/districts.py` 에 `GET /api/districts/{code}/preview` 라우트 추가
- [ ] B4. Redis 캐시 (`preview:{code}`, TTL 24h)
- [ ] B5. 응답 shape curl + Pydantic 으로 probe 후 스펙 확정 (memory: `probe_endpoint_shape_first`)
- [ ] B6. `suggested_questions` 생성 헬퍼 함수 — `intents.yaml` 프리셋 × `role` 쿼리 파라미터 기반 분기 (델타 1 연계)
- [ ] B7. Frontend `lib/api.ts` 에 `fetchDistrictPreview(code, role?)` 추가
- [ ] B8. `chatStore.preview` 상태 + `setPreview(code)` action · `chatStore.role` 상태 (`'owner'|'investor'|'founder'|null`) 추가
- [ ] B9. `components/chat/PreviewCard.tsx` 신규 + `MessageList` 최상단 렌더. **CTA 카피 "AI 분석 보기"** 명시 (델타 3 Free 티어 원칙)
- [ ] B10. `useMapSync` 개편 — auto sendMessage 제거, `setPreview(code)` 호출로 전환
- [ ] B11. `SuggestionChips` 재사용: PreviewCard 내부에 `questions` prop 전달
- [ ] B12. "AI 분석 보기" 버튼 → `sendMessage("{name} 상권 자세히 분석해줘", code)` 풀파이프 진입
- [ ] **B13. (델타 1) `/app?role=<r>` deep link** — 첫 진입 시 URL 파싱 → `chatStore.setRole()` → PreviewCard · SuggestionChips 가 role 별 질문 세트 노출

### Phase C — 피드백 3-layer (**델타 4 반영**)

#### C-L1 카드별 inline 👍👎

- [ ] C1. `components/chat/cards/FeedbackRow.tsx` 신규 — `👍 👎` · 👎 시 선택 chip 3개 + 자유 텍스트 1줄
- [ ] C2. `chatStore.lastTraceId` 상태 + SSE `done.trace_id` 수신 시 업데이트 (이미 L1 Langfuse 배선됨)
- [ ] C3. `lib/api.ts::scoreFeedback(traceId, value, reason?)` — POST `/api/langfuse/score` 경유 (신규 얇은 프록시 라우트, DB 변경 0)
- [ ] C4. 5 Card 컴포넌트 footer 에 `FeedbackRow` 공통 삽입 (Summary/Compare/Recommend/Risk/Simulation)
- [ ] C5. 스팸 가드 — debounce 500ms + 세션 Map 으로 trace_id 당 1회 제한

#### C-L2 무료 한도 microsurvey (UI + 쿠키 상한만, 서버 게이팅 Phase 2)

- [ ] C6. `components/feedback/FreeLimitSurvey.tsx` — 5-emoji scale + 조건부 Premium 문항 + dismiss
- [ ] C7. 쿠키 `ms_survey_week_<yyyyww>` 기록 + 주 1회 상한
- [ ] C8. GA4 `dataLayer.push({event: 'free_limit_survey', mood, premium_interest})` 이벤트 발사 (backend 수정 0)
- [ ] C9. 트리거 조건 `chatStore.messageCount >= DAILY_FREE_LIMIT` 명시 (Phase 2 서버 enforcement 결합 예정)

#### C-L3 FAB (카카오 채널 1순위)

- [ ] C10. `.env.example` 에 `NEXT_PUBLIC_KAKAO_CHANNEL_URL` (1순위) + `NEXT_PUBLIC_FEEDBACK_FORM_URL` (2순위) 둘 다 추가
- [ ] C11. `components/feedback/FeedbackFab.tsx` — 카카오 > Tally > 숨김 분기, 우하단 고정, 랜딩/앱 공통
- [ ] C12. `FeedbackModal.tsx` — Tally fallback, iframe + ESC + focus trap
- [ ] C13. 베타 안내 문구 (`"베타 기간 무료. 의견이 서비스를 만듭니다."`)
- [ ] C14. 랜딩 Footer 에 동일 폼 링크 (FAB 미노출 환경 대응)
- [ ] C15. 모바일에서 FAB 이 ChatInput 과 겹치지 않도록 `<768px` 에서 Bottom sheet 상단 drag handle 옆으로 이동 (Phase E 와 연계)

### Phase D — 문서/E2E 갱신

- [ ] D1. `docs/spec/feature-list.md` 에 F11(랜딩) · F12(피드백 수집) 신규 행
- [ ] D2. `docs/spec/features/F11-landing.md` · `F12-feedback.md` 최소 스펙 (~100줄)
- [ ] D3. `docs/architecture/frontend.md` 라우팅 표 갱신 (`/` 랜딩 / `/app` 앱) + Pretendard · 테마 토글 · Bottom sheet 항목
- [ ] D4. `docs/architecture/backend.md` API 엔드포인트 표에 `/api/districts/{code}/preview` + `/api/langfuse/score` 행 추가
- [ ] D5. Ring1 `f11-landing.spec.ts` 신규 (Hero · RoleSelector · chip · Bento · BetaBanner)
- [ ] D6. Ring1 `f12-feedback.spec.ts` 신규 (FAB 분기 · 카카오 URL 경로 · Tally fallback)
- [ ] D7. Ring1 `f01-map-selection.spec.ts` 회귀: 지도 클릭 후 **즉시 SSE 쿼리 발사 안 함** + PreviewCard 노출 검증
- [ ] D8. Ring2 `j01-first-time-user.spec.ts` 업데이트: 랜딩 → role chip → CTA → 앱 → 프리뷰 → chip → 분석 흐름
- [ ] D9. `docs/status/current-status.md` 에 Phase 완료 기록 (델타 8 축 요약 포함)

### Phase E — 2026 트렌드 델타 (델타 5·6·7 전용)

> Phase A~D 의 inline 델타(1·2·3·4) 와 분리해 별도 Phase. 랜딩/프리뷰가 안정화된 뒤 추가 가능하여 리스크 격리.

#### E-모바일 Bottom Sheet (델타 5) — **→ `docs/plan/ui/mobile-responsive.md` Phase B 에 흡수**

> 2026-04-23: 모바일 대응이 10축(레이아웃/제스처/키보드/PWA/오프라인/a11y/성능/입력/피드백/네비) 전반의 구조적 작업임이 확인되어 별도 Plan (`mobile-responsive.md`) 으로 승격. 아래 체크는 참조로만 유지, 실제 구현·검증은 해당 Plan 의 Phase B + A 에서 진행.

- [ ] E1. `components/mobile/BottomSheet.tsx` 신규 — 3-snap (peek 15vh / half 55vh / full 90vh) · **→ mobile-responsive.md B1**
- [ ] E2. `app/app/page.tsx` 에서 `useBreakpoint()` 분기 → MobileLayout ↔ SplitPanel 스왑 · **→ mobile-responsive.md A5**
- [ ] E3. 지도 `touch-action` 명시 + sheet drag 충돌 회피 · **→ mobile-responsive.md B9**
- [ ] E4. 768~1023px tablet SplitPanel 50/50 고정 · **→ mobile-responsive.md A6**
- [ ] E5. FeedbackFab 모바일 위치 분기 · **→ mobile-responsive.md F3 (상호 확인)**

#### E-Motion (델타 6)

- [ ] E6. `globals.css` 에 `@media (prefers-reduced-motion: reduce)` 블록 — animation/transition duration 0.01ms clamp
- [ ] E7. 카드 stagger — `MessageList` 에서 `style={{animationDelay: '${idx*90}ms'}}` 주입
- [ ] E8. Next.js 14 View Transitions 활성화 — `next.config.mjs` `experimental.viewTransition: true` + 비교모드 morph · 라우팅 cross-fade
- [ ] E9. Safari < 18 progressive enhancement 테스트 — 지원 미흡 시 기본 navigation fallback 자동
- [ ] E10. Hero H1 `animation-timeline: scroll()` 로 font-weight 400→900 scroll 연동. 스크롤 미지원 브라우저는 `wght: 700` 정적

#### E-Theme Toggle (델타 7)

- [ ] E11. `components/layout/ThemeToggle.tsx` 신규 — 3-state 순환 (`light` / `dark` / `system`), `aria-pressed` + 음성 안내
- [ ] E12. `app/layout.tsx` SSR 에서 `cookies()` 로 `theme` 읽어 `<html data-theme="...">` 초기값 렌더 (FOUC 방지)
- [ ] E13. Toolbar 우측에 ThemeToggle 슬롯 + 랜딩 Header 에도 동일 배치
- [ ] E14. `hero-demo-light.png` · `hero-demo-dark.png` 2종 에셋 준비 + `next/image` 조건부 로딩 (`<picture>`)
- [ ] E15. Cookie `theme` max-age 1y · SameSite=Lax. 로그인 연동 전까지 서버 세션 미사용
- [ ] E16. 기존 MessageBubble · Card · deck.gl heatmap color 모두 `data-theme='light'` 에서 가독성 재점검 (palette 재매핑)

---

## 재검토 (Self-Review Gate)

### 엣지케이스

1. **랜딩에서 Kakao Map SDK 미로딩** — 랜딩은 지도 불필요. `MapContainer` dynamic import 가 `/app` 에서만 트리거되는지 확인. 번들 분석 필요.
2. **`/app?role=...&q=...` deep link SSR 이슈** — `chatStore` 는 client-only. `useEffect` 에서 searchParams 읽어 dispatch. 첫 렌더 flash 주의. `role` 은 서버측 `cookies()` 로 초기값 복원.
3. **프리뷰 페치 실패** — Repository 예외 시 `PreviewCard` 에 fallback ("데이터 로딩 실패, 직접 질문해보세요" + suggested_questions 만 정적으로 표시). Circuit Breaker 대상 아님 (LLM 무관).
4. **지도 클릭 연속 (debounce)** — `setPreview` 150ms debounce. 기존 `useMapSync` 의 `prevSelectedRef` 로직 유지.
5. **모바일 FAB ↔ ChatInput 충돌** — FAB 가 ChatInput 전송 버튼 위에 겹침. 델타 5 Bottom sheet 전환 시 sheet drag handle 옆으로 이동 (Phase E5).
6. **피드백 URL 미설정** — `NEXT_PUBLIC_KAKAO_CHANNEL_URL` + `NEXT_PUBLIC_FEEDBACK_FORM_URL` 둘 다 부재 시 FAB 숨김 (개발 환경 오노출 방지).
7. **"AI 분석 보기" 더블 클릭** — 기존 `isLoading` 가드 + `currentAbortController` 체크 재사용.
8. **랜딩 SEO** — `/app` 이 no-index, 랜딩만 index. `robots.txt` + `<head> meta` 갱신. Pretendard Variable `rel="preload"` + `font-display: swap`.
9. **(델타 1) 잘못된 role 파라미터** — `/app?role=admin` 등 예상치 못한 값 → `chatStore.setRole(null)` 로 기본 세트 폴백, 경고 없이 무시.
10. **(델타 2) Hero Visual PNG 과도한 크기** — 4K 스크린샷 그대로 쓰면 LCP 저하. WebP + max-width 1200px + `loading="eager"` 제약.
11. **(델타 4) Langfuse score API 실패** — `/api/langfuse/score` 에서 `_tracer_valid=false` 시 HTTP 204 로 silently drop. 프론트엔드는 UX 변경 없이 낙관적 업데이트 유지.
12. **(델타 4) microsurvey 를 XHR 차단 환경 (광고 차단기)** — GA4 dataLayer 가 블록되면 UI 는 성공 상태로 마감 (ACK 필요 없음). 서버 영향 0.
13. **(델타 5) 한글 IME 입력 중 sheet swipe 간섭** — Bottom sheet `drag handle` 영역만 swipe 인식, ChatInput textarea 는 `touch-action: auto` 명시해 IME 조립 과정 보호.
14. **(델타 6) View Transitions + dynamic import 충돌** — `/app` 진입 시 MapContainer dynamic chunk 로딩이 VT 전에 완료되지 않으면 빈 transition. `startViewTransition` 전 `await` preload.
15. **(델타 7) 테마 토글 + deck.gl heatmap color** — light 모드에서 기존 heatmap 팔레트(어두운 배경 전제) 는 판독 불가. `activeLayers` 에 theme-aware color range 전달.
16. **(델타 7) cookie 없이 iframe 임베드 환경** — 3P cookie 블록 브라우저에서는 `theme` 쿠키가 저장 안 됨. `localStorage` 백업.

### 메모리 교훈 매칭

| 교훈 | 적용 지점 |
|---|---|
| `feedback_next_public_api_url_frontend_port.md` | B3 프리뷰 엔드포인트는 SSE 아니므로 rewrite 경유 OK. 하지만 일관성 위해 `/api/chat` 과 동일한 직접 호출 검토. |
| `feedback_probe_endpoint_shape_first.md` | B5 명시 — Pydantic 스키마 확정 전 curl probe. |
| `feedback_e2e_user_message_pollution.md` | D7/D8 — user 쿼리 키워드(`"요약해줘"`) 와 검증 키워드 분리. 랜딩 Hero 카피("상권", "분석") 가 assert 에 들어가면 오탐. |
| `feedback_react_event_keys_unique.md` | Phase C 피드백 모달의 별점 버튼 배열 렌더, Phase B suggested_questions chip 배열 모두 `key` 는 `${idx}-${text.slice(0,8)}` 같은 복합. |
| `feedback_marketscope_sse_format.md` | 프리뷰 엔드포인트는 REST JSON 만, SSE 아님 (명시). |
| `feedback_stale_container_vs_source.md` | D E2E 전 `docker compose build frontend` 후 이미지 타임스탬프 확인. |
| `feedback_check_env_before_test.md` | D 실행 전 USE_MOCK 상태 확인 (Mock: D3001~D3005 / Real: 1650개) — 프리뷰도 동일 제약. |

### 타 Plan 과의 충돌

| 충돌 후보 | 평가 |
|---|---|
| `accuracy-gap-fix.md` W1 (Entity Linking + Abstention) | **충돌 없음**. W1 은 Planner/Respond 수정, 본 Plan 은 라우팅/REST. 공통 touch point 없음. |
| `accuracy-gap-fix.md` W2 (Conversational Query Rewriting) | **충돌 없음**. W2 는 대화 히스토리 rewrite, 본 Plan 은 첫 진입 UX. 단, "AI 분석 보기" 클릭이 히스토리에 어떻게 쌓일지 W2 와 조정 필요. |
| `commercialization-plan.md` (Phase 2 Premium) | **보완 관계**. 피드백 FAB → 자체 구현 이관 시 Tier 게이팅 인증 흐름과 결합 가능. **델타 4 L2 microsurvey** 트리거(`DAILY_FREE_LIMIT`) 는 Phase 2 서버 게이팅과 반드시 결합. |
| `llmops-platform.md` | **경미**. 프리뷰 엔드포인트는 Langfuse trace 미대상 (LLM 무관). **델타 4 L1 카드 👍👎** 는 Langfuse `score` API 경유 — 기존 L1 trace_id wiring 와 정합. |
| `e2e-ops-followup-2026-04-22.md` | **영향 있음**. Ring1 `f01~f10` spec 의 `page.goto('/')` 전체 치환 + 모바일 device spec 추가. helper `gotoApp()` 도입. |
| **(신규) `tailwind-v4-oklch-migration.md`** | **후속 Plan**. 본 Plan 은 v3.4 hex 기반으로 먼저 출시, 이후 OKLCH 재매핑. `[data-theme]` attribute 구조는 v4 `@theme` 문법과 호환되게 설계. |
| **(신규) `pwa-offline.md` (가칭)** | **없음, 경계만 명시**. 본 Plan 은 PWA/offline 미포함. 모바일 bottom sheet 는 웹만. 향후 PWA 도입 시 haptic/shake 재검토. |

### 보류/미결 의사결정

- **D1 랜딩을 라이트로 할지 다크로 할지** — 현재 계획: 라이트. 이유: 랜딩은 일반 대중 (소상공인/투자자), 앱은 데이터 분석 화면. 재논의 가능.
- **피드백 2차 (자체 `/api/feedback`) 타이밍** — Phase C MVP 3개월 운영 후 데이터량 보고 결정. 별도 Plan.
- **랜딩을 `/` 로 유지할지 `/welcome` 으로 할지** — `/` 유지 (SEO/브랜딩 우선). 대신 분석 앱은 `/app`.

---

## Scenario (E2E Ring Mapping)

포맷: `<RING>-<FEATURE>-<CASE>` (CLAUDE.md 규약).

### Ring 0 (Preflight)

| ID | 검증 | 스크립트 |
|---|---|---|
| 0-LANDING-STACK | `/` 에 랜딩 마운트, `/app` 에 분석 앱 마운트 — 200 OK 각각 | 기존 `00-stack-up.spec.ts` 확장 |

### Ring 1 (Features)

| ID | 검증 | 파일 |
|---|---|---|
| 1-F11-HERO | Hero H1/Sub/CTA 렌더 + Deep Blue · Teal 토큰 computed style + Pretendard 폰트 로딩 | `f11-landing.spec.ts` |
| 1-F11-ROLE | RoleSelector 3-way chip 클릭 → Hero 카피 + starter chip 스왑 + `localStorage['role']` 저장 (델타 1) | 동 |
| 1-F11-CHIP-PREFILL | Hero chip 클릭 → `/app?role=...&q=...` navigation + ChatInput prefill + 자동 send | 동 |
| 1-F11-BENTO | Bento 6 cell 렌더 + 각 셀 `data-testid` 존재 + hover 클래스 토글 (델타 2) | 동 |
| 1-F11-BETA-BANNER | 베타 무료 배너 텍스트 존재 | 동 |
| 1-F11-HERO-VISUAL | Hero Visual `<img>` 2종 (light/dark) src 존재 + `prefers-reduced-motion: reduce` 시 animation `paused` | 동 |
| 1-F12-FAB-KAKAO | `NEXT_PUBLIC_KAKAO_CHANNEL_URL` 설정 → FAB 클릭 시 해당 URL 로 window.open (델타 4) | `f12-feedback.spec.ts` |
| 1-F12-FAB-TALLY-FALLBACK | KAKAO URL 미설정 + TALLY URL 설정 → Tally iframe 모달 열림 | 동 |
| 1-F12-CARD-THUMBS | SummaryCard 하단 👍 클릭 → `/api/langfuse/score` POST 200 + 동일 trace_id 재클릭 시 서버 무시 | 동 |
| 1-F12-SURVEY | `FreeLimitSurvey` 강제 노출 (test hook) → 5-emoji 응답 → GA4 dataLayer push 이벤트 검증 | 동 |
| 1-F01-PREVIEW-FIRST | 지도 클릭 시 SSE POST `/api/chat` 호출 **없음** + PreviewCard 노출 (`data-testid="district-preview"`) + "AI 분석 보기" CTA 문구 | `f01-map-selection.spec.ts` 회귀 |
| 1-F01-PREVIEW-CHIP | PreviewCard suggested chip 클릭 → `/api/chat` SSE 발사 | 동 |
| 1-F01-PREVIEW-DEEP | "AI 분석 보기" → 풀파이프 실행 + 다수 카드 수신 | 동 |
| 1-PREVIEW-API | `GET /api/districts/D3001/preview?role=owner` 200 + shape 검증 (district_code/top_categories/suggested_questions role 별 차이) | `preview-api.spec.ts` |
| 1-PREVIEW-CACHE | 동일 code 2회 호출 시 2번째 latency <20ms (Redis hit) | 동 |
| 1-THEME-TOGGLE | 토글 클릭 → `data-theme` 순환 (light→dark→system) + cookie `theme` max-age 1y (델타 7) | `theme-toggle.spec.ts` |
| 1-THEME-SSR | cookie `theme=dark` 설정 + reload → `<html data-theme="dark">` SSR 렌더 (FOUC 없음) | 동 |

### Ring 2 (Journeys)

| ID | 검증 | 파일 |
|---|---|---|
| 2-J01-FIRST-TIME | 랜딩 → role chip → CTA → 앱 → 지도 클릭 → 프리뷰 → chip → 분석 카드 수신 | `j01-first-time-user.spec.ts` 개편 |
| 2-J02-COMPARISON | 랜딩 투자자 role → chip "비교" → `/app?role=investor&q=...` → 자동 비교 흐름 | `j02-comparison-shopper.spec.ts` 연장 |
| 2-J06-FEEDBACK | 임의 journey 완료 후 카드 👎 클릭 → reason chip 선택 → Langfuse score POST → FAB 카카오 링크 별탭 | `j06-feedback-loop.spec.ts` 신규 |
| 2-J07-MOBILE | iPhone 12 device — 랜딩 → CTA → 앱 → bottom sheet peek → swipe-up → 전체 chat → 지도 클릭 시 sheet half snap (델타 5) | `j07-mobile-journey.spec.ts` 신규 |

### Ring 3 (Negative)

| ID | 검증 | 파일 |
|---|---|---|
| 3-NEG-PREVIEW-BAD-CODE | `/api/districts/ZZZZ/preview` → 404 | `neg-preview-invalid.spec.ts` |
| 3-NEG-FEEDBACK-URL-MISSING | KAKAO + TALLY URL 모두 빈 상태에서 FAB 숨김 | `neg-feedback-missing.spec.ts` |
| 3-NEG-LANDING-DEEPLINK | `/app?q=<매우긴프롬프트>` (1000자+) → 챗 입력 방어 + 정상 send | `neg-landing-deeplink.spec.ts` |
| 3-NEG-ROLE-INVALID | `/app?role=hacker` → 무시 + 기본 질문 세트 (델타 1) | 동 |
| 3-NEG-CARD-SPAM | 동일 trace_id 👍 3회 클릭 → 서버 첫 1건만 저장 + 2·3회 는 HTTP 204 or 무반응 (델타 4 스팸 가드) | `neg-feedback-spam.spec.ts` |
| 3-NEG-VT-SAFARI | `userAgent` Safari 17 override → View Transitions 미지원 시 기본 navigation (애니메이션 없음) + 기능 회귀 0 (델타 6) | `neg-view-transitions-fallback.spec.ts` |

---

## Pass 반복

### Pass 1 — 기본 동작

**목표**: 해피패스. 주요 커밋 단위 = Phase A/B/C/D/E 끝날 때마다.

- [ ] Pass 1-A (랜딩): Ring0-LANDING-STACK + Ring1 F11 6건 (HERO/ROLE/CHIP/BENTO/BETA/HERO-VISUAL) + Ring1 F01 회귀 3건 전체 PASS
- [ ] Pass 1-B (프리뷰): Ring1 PREVIEW-API/CACHE + Ring2 J01 PASS
- [ ] Pass 1-C (피드백): Ring1 F12 4건 (FAB-KAKAO/FAB-TALLY/CARD-THUMBS/SURVEY) + Ring2 J06 PASS
- [ ] Pass 1-D (문서/E2E 갱신): D1~D9 체크리스트 전부 커밋 + Ring1~3 전체 green
- [ ] **Pass 1-E (트렌드 델타)**: Ring2 J07 모바일 + Ring1 THEME-TOGGLE/SSR + Ring3 NEG-VT-SAFARI PASS

Fail → 로컬 수정 → `docker compose build frontend` (memory: stale container) → 재실행.

### Pass 2 — 엣지

- [ ] Pass 2-EDGE-1: 프리뷰 API timeout / Redis down → fallback 동작 (정적 suggested_questions 만 렌더)
- [ ] Pass 2-EDGE-2: `/app?q=` 매우 긴 문자열 · XSS payload → 프론트 sanitize + backend prompt sanitize (기존 `prompt sanitize` 2026-04-06 P0 회귀 확인)
- [ ] Pass 2-EDGE-3: 모바일 뷰 (iPhone 12 Playwright device) → FAB 위치 · PreviewCard 스크롤 가능 · Bottom sheet 3-snap 전환 자연스러움
- [ ] Pass 2-EDGE-4: 랜딩 SEO meta (`robots`, `og:image`) lighthouse > 90
- [ ] Pass 2-EDGE-5: `USE_MOCK=true` 와 `false` 양쪽에서 프리뷰 응답 동일 shape (Mock fixture 확장 필수)
- [ ] **Pass 2-EDGE-6 (델타 6): `prefers-reduced-motion: reduce`** 에뮬레이션 — 카드 stagger · Hero weight animate · Hero Visual loop 모두 정지, 기능 회귀 0
- [ ] **Pass 2-EDGE-7 (델타 7): 테마 토글** — light ↔ dark ↔ system 3-state 순환 · 모든 Card 가독성 검증 (contrast ≥ WCAG AA) · heatmap deck.gl color palette light 모드 판독 가능
- [ ] **Pass 2-EDGE-8 (델타 4): 스팸 가드** — 카드 👍👎 500ms debounce 내 3번 클릭 시 1회만 전송 + 세션 Map trace_id 중복 차단 확인
- [ ] **Pass 2-EDGE-9 (델타 1): role chip 쿠키 복귀** — role 선택 후 새 탭 `/` 진입 시 chip 사전 선택 상태 복원 (localStorage persist)
- [ ] **Pass 2-EDGE-10 (델타 2): Pretendard 로드 실패** — `Content-Security-Policy` 또는 네트워크 차단 조건에서 Inter fallback 로 한글 가독 유지 확인

Fail → 수정 → Pass 1 회귀 재실행 포함.

### Pass 3 — 성능

- [ ] Pass 3-PERF-1: 프리뷰 P95 latency < 150ms (Redis hit 시 < 30ms)
- [ ] Pass 3-PERF-2: 랜딩 페이지 Lighthouse Performance > 85, LCP < 2.5s, CLS < 0.05
- [ ] Pass 3-PERF-3: `/app` 번들 사이즈 — 랜딩 이관 후 app 번들 15% 이상 감소 확인 (dynamic import 검증)
- [ ] Pass 3-PERF-4: PAE Tool 호출 감소율 — 지도 클릭 10회 중 "AI 분석 보기" 클릭률 측정 (운영 지표, 베타 1주)
- [ ] **Pass 3-PERF-5 (델타 2): Pretendard Variable** `font-display: swap` + subset (`KR`) — TTFT 기준 FOIT 0 (swap 확인)
- [ ] **Pass 3-PERF-6 (델타 2): Hero Visual PNG** 총 크기 < 200KB 각 (WebP 권장) + `loading="eager"` + width/height 명시로 CLS 방지
- [ ] **Pass 3-PERF-7 (델타 6): View Transitions** 활성 시 비교모드 진입 JS blocking time 증가 < 20ms (Chrome DevTools performance trace)
- [ ] **Pass 3-PERF-8 (델타 5): 모바일 bottom sheet** `<768px` scroll-snap 60fps 유지 (iPhone 12 emulation 기준)

Fail → 최적화 (번들 분석 · 이미지 lazy · Redis warming · WebP 변환 · font subset) → Pass 2 회귀.

---

## Agent 모델 선택

CLAUDE.md Plan 규약에 따라 역할별 모델 분리.

| 단계 | 추천 서브에이전트 | 모델 | 이유 |
|---|---|---|---|
| 설계 · ADR 검토 · 라우팅 대안 비교 | 주 대화 (Claude Opus) | opus | 아키텍처 trade-off 판단 |
| Landing 컴포넌트 구현 · 프리뷰 API 구현 | `Explore` + `frontend-specialist` (또는 sonnet 직접) | sonnet | 기계적 CRUD · React JSX |
| E2E spec 작성/실행 | `qa-scenario-runner` | haiku | Playwright 결과 대량 출력 메인 컨텍스트에서 격리 |
| DB/Repository 변경 검증 | `db-validator` | haiku | USE_MOCK · alembic head · preview fixture 존재 확인 |
| 코드 리뷰 | `code-reviewer` | haiku | ruff/SSE/React key 기계 점검 |

---

## Validation

### 완료 조건 (Definition of Done)

1. ✅ Ring 0/1/2/3 전체 신규 · 회귀 spec PASS (Mock + Real 양쪽)
2. ✅ 지도 클릭 당 `/api/chat` 호출 0건 (프리뷰만 발사) — 네트워크 로그로 증빙
3. ✅ 프리뷰 P95 < 150ms / Lighthouse Performance > 85 / CLS < 0.05
4. ✅ `docs/spec/features/F11,F12` · `docs/architecture/frontend.md` · `backend.md` 갱신
5. ✅ `docs/status/current-status.md` 에 서비스 지표 행 추가 (랜딩 · 프리뷰 · 피드백 · 테마 토글 · 모바일)
6. ✅ Feedback — 카드 👍👎 1건 이상 Langfuse score 확인 + FAB 경로 kakao 또는 Tally 1회 이상
7. ✅ 번들 분석 리포트 — `/app` 번들 크기 변화 기록
8. ✅ **(델타 1) Role routing** — 3 role × 5 starter chip = 15개 질문이 `intents.yaml` mapping 으로 커버되는지 수동 QA
9. ✅ **(델타 6) `prefers-reduced-motion`** 사용자 시나리오 WCAG 2.2 AA 적합
10. ✅ **(델타 7) 테마 토글** — light 모드에서 모든 5 Card 타입 contrast AA 통과 (axe-core) + heatmap palette 판독 가능
11. ✅ **(델타 5) 모바일 bottom sheet** — iPhone 12 · Galaxy S21 2종 실제 기기 1회 이상 수동 QA

### 운영 지표 (Beta 1주 관찰)

- 랜딩 CTA 클릭률 (/ → /app) — 목표 35%+
- Role chip 선택률 (랜딩 방문자 중 1개 이상 선택, 목표 50%+)
- 지도 클릭 대비 "AI 분석 보기" 버튼 클릭률 (목표 30%+ — 너무 낮으면 프리뷰 정보 부족, 너무 높으면 프리뷰 무용)
- 프리뷰 Redis cache hit rate (목표 60%+)
- 카드 👍 rate (긍정 비율, 목표 65%+) + 👎 reason top-3 카테고리
- 피드백 L3 수집량 (카카오 채널 DM + Tally 합산, 목표 주간 5건+)
- 테마 토글 사용률 (`cookie theme != default` 비율, 선택권 활용도 지표)
- 모바일 `<768px` 세션 비중 + bottom sheet full snap 도달률

---

## Metadata

- **작성자**: sjkim (Claude Opus 4.7 보조)
- **작성일**: 2026-04-23
- **갱신 이력**:
  - 2026-04-23 초안
  - **2026-04-23 델타 8축 트렌드 반영** (onboarding / hero / progressive / feedback / mobile / motion / theme / tokens) — Phase E 신설 · Scope 재분류
- **소요 추정**: Phase A 3d + Phase B 3d + Phase C 2d + Phase D 1d + **Phase E 3d** = **약 1.5주 ~ 2주**
  - 기존 1주 대비 +0.5~1주 증가 (모바일 bottom sheet · theme 토글 · Pretendard 튜닝 · View Transitions fallback 포함)
- **선행 의존**: 없음 (Accuracy Gap Fix 와 병렬 가능, 리소스는 Accuracy 우선)
- **후속 Plan**:
  - `docs/plan/ui/feedback-self-hosted.md` (C 의 2차 — `/api/feedback` + Alembic 004 + `user_feedback` 테이블)
  - `docs/plan/ui/tailwind-v4-oklch-migration.md` (델타 8 — 본 Plan 의 hex 를 OKLCH 로 재매핑, 별도 분리)
  - `docs/plan/business/commercialization-plan.md` 와 브랜드 토큰 · microsurvey 문항 일치 확인
- **Ring 회귀 영향**: Ring1 F01 / Ring2 J01~J02 spec 개편 필수 · Ring2 J07 모바일 신규
- **Rollback 전략**:
  - 라우팅 변경 (Phase A): 커밋 단위 git revert
  - 프리뷰 엔드포인트 (Phase B): feature flag `NEXT_PUBLIC_ENABLE_PREVIEW=false` → 기존 `useMapSync` 자동 쿼리 경로 복원
  - 피드백 (Phase C): `NEXT_PUBLIC_KAKAO_CHANNEL_URL` + `NEXT_PUBLIC_FEEDBACK_FORM_URL` 둘 다 비우면 FAB 자동 숨김. L1 카드 👍👎 는 `NEXT_PUBLIC_ENABLE_CARD_FEEDBACK=false` 로 OFF
  - 델타 5/6/7 (Phase E): `NEXT_PUBLIC_ENABLE_THEME_TOGGLE` · `NEXT_PUBLIC_ENABLE_BOTTOM_SHEET` · `NEXT_PUBLIC_ENABLE_VIEW_TRANSITIONS` 각 flag 로 개별 OFF
- **참고 (2026 트렌드 리서치 출처)**: SaaSUI · SaaSFrame · Chameleon · MDN View Transitions · Next.js 14 view-transitions docs · Interop 2026 · Toss/Kakao 한국 B2C 사례 · Linear 2026-03 UI refresh · Claude.ai / Perplexity / Notion AI 패턴
