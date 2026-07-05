---
name: Landing Copy & Icon Refresh (De-AI tone)
type: ui
created: 2026-04-24
status: in-progress
---

# Landing Copy & Icon Refresh — "AI 스러움" 제거

> `/` 랜딩의 이모지와 카피가 생성형 AI 템플릿 느낌을 준다는 피드백. 실제 B2B SaaS / 상권분석 서비스 기준으로 아이콘·카피 톤을 재정렬한다.

## 1. Context

### 1-1. 문제 제기

사용자 지적: "현재 이모티콘들이 너무 AI 스러워서" — 즉, **ChatGPT/Notion-AI 기본 템플릿과 구분이 안 되는 시각·언어 톤**.

구체 증상 (2026-04-24 audit):

| 위치 | 요소 | 증상 |
|------|------|------|
| `BentoFeatures.tsx` | 🗺️ 💬 📊 🎯 📈 📄 6종 emoji | OS별 렌더 불일치 + "AI 랜딩 템플릿" 전형 |
| `roles.ts` | 🧑‍🍳 🏢 💡 3종 emoji | 직업 스테레오타입 + 농담조 |
| `roles.ts::DEFAULT_HERO_LEAD` | "서울 1,650개 상권, AI가 읽어드립니다" | "AI가 읽어드립니다" 2인칭 과잉 |
| `roles.ts::owner.heroLead` | "우리 가게 동네, AI가 해석해 드려요" | 동일 패턴 |
| `BentoFeatures::chat` | "자연어로 질문하면 Claude + Gemini가 데이터를 해석해 답합니다" | LLM 브랜드 노출 (유저 관심사 아님) |
| `BentoFeatures::header` | "LLM 무호출 프리뷰부터 PDF 리포트까지" | 기술 용어 표층 |
| `HowItWorks::step02` | "핵심 지표 프리뷰 (Free · LLM 무호출)" | 괄호 내 기술 설명 |
| `Hero::DEFAULT_STARTER_CHIPS` | "매출 시뮬레이션 돌려줘" | 콜로퀄 어미가 반복되어 리듬 단조 |

### 1-2. 레퍼런스 조사 (8종)

| 서비스 | 분야 | 이모지 | 아이콘 | 헤드라인 톤 |
|--------|------|:------:|--------|------------|
| **나이스비즈맵** (m.nicebizmap.co.kr) | 국내 상권분석 | 0 | 선형 stroke + 컬러 포인터 | "믿을 수 있는 상권분석" / "직관적으로 쉽게 파악하세요" — 신뢰·간결 |
| **Placer.ai** | 글로벌 Foot Traffic | 0 | Duotone + 데이터 시각화 | "Measure visitation, benchmark the competition" — 동사 중심 B2B |
| **CARTO** | Geospatial / LI | 0 | Line + brand color | "The Agentic GIS Platform" — 제품 정체성 한 줄 |
| **Linear** | Dev Tool | 0 | 자체 custom mono | 헤드라인 1줄 + 서브 2줄 + CTA 1개 · 미니멀 극단 |
| **Notion** (2026 템플릿) | Prod | emoji 혼용 | 2-3 컬럼 | 벤치마크용 — **emoji 혼용은 Notion 내부 문서 스타일**, SaaS 랜딩은 지양 트렌드 |
| **SEOUL OpenData 광장** | 공공 | 0 | Material stroke | 한국어 공공 서비스 어투 레퍼 |
| **소상공인365** | 정부 플랫폼 | 0 | flat color icon | "상권정보" 기능명 직역 |
| **Shadcn UI 생태계** | 2026 SaaS 디폴트 | 0 | **Lucide** | Lucide 가 2026 SaaS React 사실상 디폴트 (8종 중 6종 채택) |

2026 아이콘 컨센서스 (Muzli / Untitled UI / Glow UI / Hugeicons 정리):

> *"Pick one icon library per project and stick with it. Emoji for SaaS landing has become the tell-tale sign of AI template."*
> *"Structured icon libraries like Lucide are preferred over emoji for SaaS landing pages because they provide visual consistency."*

### 1-3. Memory 참조

- `feedback_react_event_keys_unique.md` — 아이콘 컴포넌트 다회 렌더 시 key 유일성
- `feedback_formatter_strips_unused_imports.md` — lucide icon import 는 사용 지점과 같은 Edit 내에
- `feedback_e2e_user_message_pollution.md` — 이모지 → 아이콘 치환 후 E2E `data-testid` 로 검증 (가시 텍스트 의존 회피)

### 1-4. 타 Plan 충돌

- `landing-onboarding-feedback.md` (Phase A 완료) — 현재 랜딩 구조를 생성한 Plan. 본 Plan 은 그 위 **비파괴적 refinement**. 컴포넌트 구조·testid·라우팅·번들 분리 전부 보존.
- `mobile-responsive.md` (Phase A~C 완료) — BentoFeatures 셀 크기·터치타깃에 영향 없음.

## 2. Scope

### In Scope

- `frontend/src/components/landing/BentoFeatures.tsx` — 6 cell emoji → Lucide icon + 카피 재작성
- `frontend/src/components/landing/roles.ts` — 3 role icon(emoji→Lucide) + heroLead/heroSub/starterChips 재작성 + DEFAULT_* 재작성
- `frontend/src/components/landing/RoleSelector.tsx` — `<span aria-hidden>{r.icon}</span>` → `<Icon />` 렌더
- `frontend/src/components/landing/HowItWorks.tsx` — step02 "LLM 무호출" 괄호 제거, step03 카피 다듬기
- `frontend/package.json` — `lucide-react` 신규 추가 (tree-shakable, 현재 deps 14 → 15)

### Out of Scope

- Header `<span>` 브랜드 마크 (이모지 아님, 이미 SVG-like — 유지)
- Hero primary CTA `→` arrow character (일반 문자, 유지)
- HeroVisual (SVG placeholder — 별도 디자인 Plan)
- FeedbackFab / Footer — 이모지 없음
- `/app` 내부 카드 UI, 챗봇 메시지 이모지 (본 Plan 외)
- 라이트/다크 테마 팔레트 변경
- Lucide 외 아이콘 라이브러리 (Phosphor, Heroicons) 평가 — Shadcn 생태계 정합성 이유로 Lucide 고정

## 3. Design

### 3-1. 아이콘 교체 기준

| 기준 | 규칙 |
|------|------|
| 라이브러리 | `lucide-react` 단일. Shadcn/Tailwind 생태계 정합 + tree-shakable (per-icon import) |
| 크기 | Bento cell 아이콘 = 20px (기존 w-10 h-10 배경 박스 내 중앙 정렬) / RoleSelector = 16px |
| stroke | `strokeWidth={1.75}` — Lucide 기본 2 보다 약간 얇게, 한국어 타이포 무게와 균형 |
| 색상 | `currentColor` — 기존 cell accent 토큰 (`ACCENT_MAP`) 그대로 재활용 |
| 접근성 | 이모지와 달리 `<Icon aria-hidden />` 명시 + title 은 별도 `<h3>` 텍스트에서 제공 |
| 번들 | per-icon import (`import { Map } from 'lucide-react'`) — 전체 라이브러리 0KB 포함, 개별 ~1KB |

### 3-2. 아이콘 매핑

| 기존 emoji | 교체 Lucide | 의미 검증 |
|:----------:|:-----------:|-----------|
| 🗺️ (Bento map) | `Map` | 지도 레이어 — 1:1 |
| 💬 (Bento chat) | `MessagesSquare` | 대화형 리포트 — `MessageCircle` 은 단일 버블이라 "대화" 뉘앙스 약함 |
| 📊 (Bento compare) | `Columns3` | 2~3 컬럼 비교 — `BarChart3` 는 단순 차트, 비교 뉘앙스 약함 |
| 🎯 (Bento recommend) | `Target` | 업종 추천 정확도 — 1:1 |
| 📈 (Bento simulation) | `TrendingUp` | p25/p75 범위 상승 추세 |
| 📄 (Bento PDF) | `FileText` | PDF 리포트 — `FileDown` 도 후보나 "저장" 뉘앙스 편중 |
| 🧑‍🍳 (Role owner) | `Store` | 소상공인 = 매장 운영자 — 직업 아이콘 대신 **객체 아이콘** (스테레오타입 회피) |
| 🏢 (Role investor) | `LineChart` | 투자자 = 데이터 분석 — 건물 아이콘은 부동산 편중 |
| 💡 (Role founder) | `Sparkle` | 창업 준비 = 시작/아이디어 — `Lightbulb` 은 이모지와 동일 개념이라 차별화 약함 |

### 3-3. 카피 재작성 기준

| 기준 | Before 패턴 | After 규칙 |
|------|------------|----------|
| **AI 인격화 제거** | "AI가 해석해 드려요" | 행위 주체를 AI → 데이터/상권/지표로 이동 |
| **LLM 브랜드 숨김** | "Claude + Gemini가 데이터를 해석" | 공급자 명 삭제 — 유저는 결과만 소비 |
| **기술 용어 숨김** | "LLM 무호출 프리뷰" | "클릭만으로 미리보기" 등 결과 중심 |
| **동사 우선** | "~돌려줘 / ~보여줘" 일색 | 일부는 명사구 ("강남 vs 성수 매출 비교") — 리듬 분리 |
| **신뢰 어휘** | "3초 안에 요약" (과장 부담) | "유동인구·매출·업종 한 장으로" (측정 가능) |
| **한국어 상권 용어** | — | 나이스비즈맵 레퍼 채택 — "유동인구/점포밀집도/골목단위" 친숙 어휘 |

### 3-4. Before / After (핵심만)

#### DEFAULT_HERO_LEAD
- Before: `서울 1,650개 상권, AI가 읽어드립니다`
- After: `서울 1,650개 상권, 데이터로 읽다`
- 근거: Placer.ai "Measure ... benchmark" 동사 중심 + 나이스비즈맵 "믿을 수 있는" 명사 응축

#### DEFAULT_HERO_SUB
- Before: `클릭 한 번이면 해당 상권의 유동인구·매출·업종을 3초 안에 요약해드려요.`
- After: `지도 위 상권을 선택하면 유동인구·매출·업종 구성을 한 장의 리포트로 확인합니다.`

#### Bento chat
- Before: `대화형 AI 리포트 / 자연어로 질문하면 Claude + Gemini가 데이터를 해석해 답합니다.`
- After: `대화형 리포트 / 질문을 던지면 필요한 지표를 골라 근거와 함께 답합니다.`

#### Bento section header
- Before: `LLM 무호출 프리뷰부터 PDF 리포트까지. 클릭만으로 이어집니다.`
- After: `지도 클릭에서 시작해, 비교·추천·시뮬레이션·PDF까지 한 흐름으로 이어집니다.`

#### HowItWorks step02
- Before: `핵심 지표 프리뷰 (Free · LLM 무호출)` / `지역 유형, 주요 업종 Top 3, 유동인구 추이를 즉시 확인하세요.`
- After: `상권 프리뷰 바로 보기` / `지역 유형·주요 업종 Top 3·유동인구 추이가 즉시 카드로 나타납니다.`

#### Role owner (hero copy)
- Before: `우리 가게 동네, AI가 해석해 드려요 / 유동인구·매출·경쟁 점포를 3초 안에 한 장으로 요약해드립니다.`
- After: `우리 동네 상권, 숫자로 이해하기 / 유동인구·매출·경쟁 점포를 한 장으로 정리해 드립니다.`

#### Role investor (hero copy)
- Before: `상권 데이터로 결정하세요 / 2~3 상권을 한 화면에서 비교하고 유망 업종을 점수화해 드립니다.`
- After: `데이터로 의사결정하는 상권 탐색 / 2~3 상권을 나란히 비교하고 유망 업종을 점수로 확인합니다.`

#### Role founder (hero copy)
- Before: `어디서 뭘 시작할까? / 예산·업종·지역 조합으로 월 매출 범위를 시뮬레이션해 드립니다.`
- After: `어디서 시작할지, 수치로 고르기 / 예산·업종·지역 조합으로 월 매출 범위를 시뮬레이션합니다.`

#### Starter chips — 리듬 개선

DEFAULT:
- Before: `['강남역 상권 요약해줘', '홍대랑 건대 비교해줘', '이 동네 유망 업종 알려줘', '매출 시뮬레이션 돌려줘']`
- After: `['강남역 상권 요약', '홍대 vs 건대 비교', '유망 업종 Top 5', '월 매출 시뮬레이션']`

owner / investor / founder 각 5개 chip 도 동일 기준(명사구 + 일부 동사)으로 다듬음 — §3-5 상세표.

### 3-5. 카피 전문 (roles.ts)

```ts
// DEFAULT
heroLead  = '서울 1,650개 상권, 데이터로 읽다'
heroSub   = '지도 위 상권을 선택하면 유동인구·매출·업종 구성을 한 장의 리포트로 확인합니다.'
chips     = ['강남역 상권 요약', '홍대 vs 건대 비교', '유망 업종 Top 5', '월 매출 시뮬레이션']

// owner
heroLead  = '우리 동네 상권, 숫자로 이해하기'
heroSub   = '유동인구·매출·경쟁 점포를 한 장으로 정리해 드립니다.'
chips     = ['홍대 카페 매출 추이', '시간대별 유동인구', '인근 유사 상권 비교', '이 상권의 주요 리스크', '프랜차이즈 비중']

// investor
heroLead  = '데이터로 의사결정하는 상권 탐색'
heroSub   = '2~3 상권을 나란히 비교하고 유망 업종을 점수로 확인합니다.'
chips     = ['강남 vs 성수 유동인구', '홍대 vs 건대입구 매출', '최고 기대 업종 Top 5', '시간대별 히트맵', '상권 안정성 점수']

// founder
heroLead  = '어디서 시작할지, 수치로 고르기'
heroSub   = '예산·업종·지역 조합으로 월 매출 범위를 시뮬레이션합니다.'
chips     = ['예산 5천만원 창업 후보', '홍대 카페 월 매출 추정', '유망 업종 추천', '신규 점포 생존율 상위', '매출 시뮬레이션']
```

### 3-6. 컴포넌트 변경 요약

1. `BentoFeatures.tsx` — `Cell.emoji: string` → `Cell.Icon: LucideIcon`, JSX `{cell.emoji}` → `<cell.Icon size={20} strokeWidth={1.75} />`
2. `roles.ts` — `icon: string` → `Icon: LucideIcon`, default + 3 role 전체 카피 교체
3. `RoleSelector.tsx` — `<span aria-hidden>{r.icon}</span>` → `<r.Icon size={16} strokeWidth={1.75} aria-hidden />`
4. `HowItWorks.tsx` — STEPS 텍스트만 교체
5. `BentoFeatures.tsx` 섹션 헤더 · 6 cell title/desc 전수 교체

## 4. Checklist · Self-Review · Scenario · Pass

### 4-1. Checklist (원자 단위)

- [ ] `cd frontend && npm install lucide-react --save`
- [ ] `BentoFeatures.tsx`: `import { Map, MessagesSquare, Columns3, Target, TrendingUp, FileText, type LucideIcon } from 'lucide-react'`
- [ ] `BentoFeatures.tsx`: `interface Cell { ... Icon: LucideIcon; ... }`, emoji 필드 제거
- [ ] `BentoFeatures.tsx`: CELLS 6행 재작성 (icon + title + desc)
- [ ] `BentoFeatures.tsx`: 섹션 헤더 h2/p 카피 교체
- [ ] `BentoFeatures.tsx`: JSX 아이콘 박스 `{cell.emoji}` → `<cell.Icon size={20} strokeWidth={1.75} />`
- [ ] `roles.ts`: `import { Store, LineChart, Sparkle, type LucideIcon } from 'lucide-react'`
- [ ] `roles.ts::RoleMeta`: `icon: string` → `Icon: LucideIcon`
- [ ] `roles.ts`: owner/investor/founder 3 role — Icon + heroLead + heroSub + starterChips 전수 교체
- [ ] `roles.ts`: DEFAULT_HERO_LEAD / DEFAULT_HERO_SUB / DEFAULT_STARTER_CHIPS 교체
- [ ] `RoleSelector.tsx`: `<span>{r.icon}</span>` → `<r.Icon size={16} strokeWidth={1.75} aria-hidden />`
- [ ] `HowItWorks.tsx`: STEPS[1].title, STEPS[1].desc, STEPS[2].title 다듬기
- [ ] `npx tsc --noEmit` → 0 errors
- [ ] `npx eslint` changed files → 0 errors
- [ ] `npm run build` → 성공 + `/` First Load 변화 <+2KB

### 4-2. 재검토 (Self-Review Gate)

| 엣지케이스 | 대응 |
|-----------|------|
| Lucide icon 이름 오타 → type error | TS 가 잡음. 빌드로 검증 |
| SSR hydration mismatch (`suppressHydrationWarning={!hydrated}`) | Hero 는 이미 가드 있음. RoleSelector 리렌더만 영향 — 이모지든 아이콘이든 동일. 리스크 0 |
| E2E spec 에서 emoji 텍스트로 matching? | `ring1/f11-landing.spec.ts` 확인 필요. testid 기반이면 무영향 |
| "AI" 완전 삭제? | 금지 — F12 `FeedbackFab` · HowItWorks step03 `"AI 분석 보기"` · BetaBanner 는 남김 (메뉴/버튼 레이블). 금지 대상은 "AI가 ~해드려요" 인격화 구문 |
| Bento cell accent 컬러 6종 유지? | 유지. `ACCENT_MAP` 그대로, 아이콘은 `color: ACCENT` 로 stroke 색만 받음 |
| Bundle size 증가? | Lucide per-icon ~1KB gzip × 9 icon ≈ 9KB gzip. 200KB 예산 내 |
| 모바일에서 아이콘 픽셀 hinting? | 20px stroke=1.75 는 1x/2x 모두 선명. Lucide 표준 24px 의 스케일 다운 문제 없음 (공식 가이드) |
| 한국어 어휘 "의사결정하는" 자연스러운가? | 나이스비즈맵 "의사결정" 사용 전례 — 자연스러움 확인 |

### 4-3. Scenario (E2E Ring Mapping)

- **R0-LANDING-STACK**: 기존 `landing-page` testid 렌더 유지 — 영향 없음
- **R1-F11-BENTO-ICON**: `bento-cell-<id>` 셀 6개 모두 아이콘 SVG `<svg>` 렌더 확인 (기존 spec 에 `[data-testid^="bento-cell-"]` count === 6 있으면 PASS 유지)
- **R1-F11-ROLE-CHIP**: `role-chip-<id>` 클릭 시 chatStore.role 세팅 (기존 spec 그대로)
- **R3-REG-NO-AI-TONE** (신규, 선택): `page.content()` 로 "AI가 해석" / "Claude + Gemini" / "LLM 무호출" 텍스트가 **없음** 을 확인 — regression guard

### 4-4. Pass 계획

- **Pass 1 (기본)**: §4-1 체크리스트 전부 그린. `npm run build` + `tsc` PASS
- **Pass 2 (엣지)**: 기존 E2E spec 재실행 (`ring1/f11-landing.spec.ts` 우선) — 텍스트 의존 matcher 있으면 testid 로 수정
- **Pass 3 (성능 — 선택)**: 번들 사이즈 비교 (`.next/analyze` 또는 build output 의 First Load 값)

### 4-5. Agent 모델 선택

- 설계 (본 Plan 작성 완료): **Opus 4.7** (현재 세션)
- 구현: **Opus 4.7** (auto mode, 동일 세션 이어서 진행)
- 검증: **Opus 4.7** — tsc/eslint/build 자동 실행

## 5. Validation

### 5-1. 빌드

```bash
cd frontend
npm install lucide-react --save
npx tsc --noEmit
npx next build
```

**합격 기준**:
- tsc 0 errors
- next build 성공
- `/` First Load JS 가 현재 109KB 대비 +3KB 이내

### 5-2. 수동 QA

- `/` 접속 → Bento 6 cell 모두 Lucide 아이콘 렌더 (이모지 글리프 없음)
- Role chip 3종 — Store / LineChart / Sparkle 아이콘
- Role 클릭 → Hero headline/sub/chip 변경 정상
- Starter chip 클릭 → `/app?role=&q=` deep link 이동
- Ctrl+U 로 HTML 소스 grep: "AI가", "Claude", "Gemini", "LLM" — **0건**
- Dark mode 토글 시 아이콘 색상 자동 반영 (currentColor)

### 5-3. 회귀 방지

- testid `landing-page` / `hero-section` / `bento-cell-*` / `role-chip-*` / `starter-chip-*` / `beta-banner` / `how-it-works` / `footer-feedback-link` 전수 보존
- Header `data-testid="header-cta"` 텍스트 "시작하기" 유지
- `mobileTab` / `sheetSnap` 등 chatStore slice 무영향

## 6. Metadata

- **Created**: 2026-04-24 (Opus 4.7 · 1M context)
- **Author**: sjkim + Claude Code
- **Related**:
  - [landing-onboarding-feedback.md](landing-onboarding-feedback.md) (Phase A 완료 — 본 Plan 이 수정 대상)
  - [mobile-responsive.md](mobile-responsive.md) (독립)
- **References**:
  - 나이스비즈맵 (m.nicebizmap.co.kr) — 국내 상권분석 레퍼
  - Placer.ai — 글로벌 Foot Traffic 레퍼
  - Linear / CARTO — 미니멀 SaaS 타이포 레퍼
  - Lucide Icons 2026 — Shadcn 생태계 사실상 디폴트
  - Hugeicons / Muzli / Untitled UI "icon library comparison 2026"
- **Memory 신규 후보** (구현 후 판단):
  - `feedback_landing_avoid_ai_persona_copy.md` — "AI가 ~해드려요" 인격화 어미는 SaaS B2B 톤 훼손, 데이터·지표 주체로 rephrase
  - `feedback_landing_lucide_default.md` — Bento/role 류 SaaS 랜딩은 Lucide 단일 라이브러리 + per-icon import 기본값
