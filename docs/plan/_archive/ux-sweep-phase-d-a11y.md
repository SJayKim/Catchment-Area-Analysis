# UX Sweep — Phase D · A11y / 마감

> 시리즈: **UX Sweep 2026-04-30** (38건 점검 → 6 phase 분할)
> 본 phase 영역: 접근성 + 라우트 boundary + key 안정화 + 변수화 등 10건 · 예상 3~4h
> 타 phase: [A Quick Wins](ux-sweep-phase-a-trust-legal.md) · [B 핵심 막힘](ux-sweep-phase-b-core-blockers.md) · [C 자연스러움](ux-sweep-phase-c-polish.md) · [E Premium defer](ux-sweep-phase-e-premium-deferred.md) · [F Tier hook](ux-sweep-phase-f-tier-hook.md)

## Context

A11y 와 마감 품질 10건. 핵심: **error.tsx / loading.tsx 라우트 boundary 부재** (D.1) — 네트워크 오류 시 사용자에게 freeze 처럼 보이는 가장 큰 신뢰 저하 요인. 그 외 focus-visible / aria-label / FeedbackRow 토글 / Tally fallback / key 안정화 / InlineChart CSS 변수 / Header hover Tailwind / BottomNav 폰트 / DistrictLayer hover 잔상.

D.1 단독 머지 권장 (영향도 가장 큼). 나머지는 묶어서 한 번에 가능.

## Checklist

- [ ] **D.1** `app/error.tsx`, `app/loading.tsx`, `app/app/error.tsx`, `app/app/loading.tsx` 신규 [M]
- [ ] **D.2** `globals.css` `:focus-visible` ring + landing/* 의 `focus:outline-none` → `focus-visible:ring-2` [S]
- [ ] **D.3** landing/* aria-label 누락 검수 + 보강 [S]
- [ ] **D.4** FeedbackRow 토글 가능 (ack 옆 "↩️ 수정" 버튼 → reason 재오픈) [M]
- [ ] **D.5** FeedbackModal Tally iframe `onError` + 5s 타임아웃 → mailto fallback [S]
- [ ] **D.6** `key={idx}` → 안정 키 (CompareCard/SuggestionChips/TimeSlider 등) [S]
- [ ] **D.7** InlineChart 색상 CSS 변수화 (`getComputedStyle` 1회 resolve) [S]
- [ ] **D.8** Header 인라인 `onMouseEnter` → Tailwind `hover:` 클래스 [S]
- [ ] **D.9** BottomNav 이모지 22→24px, 라벨 12→13px, minHeight 56→60 [S]
- [ ] **D.10** DistrictLayer `mouseout` 시 `polygon.setOptions(styleFor(code))` 재적용 (compare 슬롯 색 reset race) [S]

## 변경 사양

### D.1 라우트 boundary
- 신규 파일 4개 (Next.js 14 표준):
  - `frontend/src/app/error.tsx` — global, `'use client'`, `({ error, reset }) => JSX` + reset 버튼 + 메인 링크.
  - `frontend/src/app/loading.tsx` — global skeleton.
  - `frontend/src/app/app/error.tsx` — `/app` 라우트.
  - `frontend/src/app/app/loading.tsx` — 지도 grey skeleton + 챗 dot loader.
- error 시그니처: `function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void })`.

### D.2 focus-visible
- `globals.css`:
  ```css
  :focus-visible { outline: 2px solid var(--brand-deep-blue); outline-offset: 2px; }
  ```
- 기존 `focus:outline-none` 인 곳 → `focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500`.
- 대상: `landing/Header.tsx`, `Footer.tsx`, `BentoFeatures.tsx`, `Hero.tsx`, `BetaBanner.tsx`.

### D.3 aria-label
- 검수 대상: `landing/*` 일괄. 텍스트 없는 `<a>`/`<button>`.
- 현재 검수 결과 대부분 갖춤 — 0~2건 보강 예상.

### D.4 FeedbackRow 토글
- 파일: `frontend/src/components/feedback/FeedbackRow.tsx:31-55`
- ack 옆 "↩️ 수정" 버튼. 클릭 → reason input 패널 재오픈.
- 백엔드는 첫 값 idempotent 유지 → 토스트 "추가 의견은 댓글로 남겨주세요" 안내 (B.2 토스트 의존).

### D.5 Tally fallback
- 파일: `frontend/src/components/feedback/FeedbackModal.tsx:65-70`
- `<iframe onError>` + 5s 타임아웃 (`useEffect` setTimeout) → 폴백 UI: "이메일로 보내기" mailto 링크.

### D.6 안정 키
- 파일: `CompareCard.tsx:120`, `SuggestionChips.tsx:21`, `TimeSlider.tsx:101`, 그 외
- 데이터 unique 필드 사용. 없으면 `${idx}-${value}` 합성.

### D.7 InlineChart CSS 변수
- 파일: `frontend/src/components/chat/cards/InlineChart.tsx:40,45,57,67,72,84` + `globals.css`
- 하드코딩 `#334155`/`#94a3b8`/`#1e293b`/`#f8fafc` → `var(--chart-grid)`/`--chart-axis`/`--chart-tooltip-bg`/`--chart-tooltip-text`.
- Recharts 가 raw value 받음 → `getComputedStyle(document.documentElement).getPropertyValue('--chart-grid')` 컴포넌트 mount 시 1회 resolve, useMemo 캐싱.

### D.8 Header hover Tailwind
- 파일: `frontend/src/components/landing/Header.tsx:35-40`
- `onMouseEnter`/`Leave` 제거 → `hover:bg-[var(--brand-deep-blue-hover)]` 클래스.

### D.9 BottomNav 폰트
- 파일: `frontend/src/components/mobile/BottomNav.tsx:50-53`
- 이모지 `text-[22px]` → `text-[24px]`, 라벨 `text-[12px]` → `text-[13px]`, minHeight 56 → 60.

### D.10 hover 잔상
- 파일: `frontend/src/components/map/DistrictLayer.tsx:114-132`
- `mouseout` 핸들러 안에서 `polygon.setOptions(styleFor(feature.code))` 재호출 — compare 슬롯 색이 default 로 reset 되는 race 방지.

## 재검토 (Self-Review Gate)

### 엣지케이스
- **D.1 reset 무한 루프**: error 자체에서 throw 발생 시 → Next 가 자동 fallback 함. 추가 가드 불필요.
- **D.2 focus-visible 브라우저 호환**: 모든 modern 브라우저 지원. IE 미고려.
- **D.4 + B.2 의존**: D.4 토스트가 B.2 toastStore 필요 → 머지 순서.
- **D.5 mailto 차단 환경** (corp): mailto 이외에 chat 채널 link fallback 도 검토.
- **D.7 다크 팔레트만 정의**: 라이트 팔레트가 globals.css 에 정의되면 자동 추종. 현재는 단일 다크 팔레트만 있음.
- **D.10 compare 슬롯 색 + selected**: `styleFor` 가 selected/compare/default 분기 일관 처리.

### 메모리 교훈
- `feedback_react_event_keys_unique.md` — `tool-${name}` 같은 type-only id 는 같은 도구 다회 호출 시 duplicate-key. D.6 안정 키 정리에 반영.

### 타 plan 충돌
- `mobile-responsive.md` 와 D.9 BottomNav 폰트 — microscale 만, 큰 리팩토링은 mobile plan 위임.
- `landing-copy-icon-refresh.md` 와 D.2/D.3 — 영역 일부 중복 가능. 카피/아이콘은 별 plan, focus/aria 는 본 plan.

## Scenario (E2E Ring Mapping)

| Test ID | Spec | Case |
|---------|------|------|
| `Ring0-D1` | `e2e/ring0-preflight/02-error-boundary.spec.ts` (신규) | 의도적 throw → error.tsx 렌더 + reset 클릭 시 정상 복구 |
| `Ring1-A11Y-D2` | `e2e/ring1-features/a11y.spec.ts` (신규) | Tab 순회 → 모든 인터랙티브 요소에 가시 outline |
| `Ring1-A11Y-D3` | 동상 | axe-core Lighthouse a11y 점수 ≥ 95 |
| `Ring1-F12-D4` | `e2e/ring1-features/f12-feedback.spec.ts` | 👍 클릭 → ack → "수정" 클릭 → reason 패널 재오픈 |
| `Ring1-F12-D5` | 동상 | iframe src 차단 → 5s 후 mailto 폴백 노출 |
| `Ring1-F01-D10` | `e2e/ring1-features/f01-map-selection.spec.ts` | compare 슬롯 1 hover → mouseout → 슬롯 1 색 유지 |

## Pass 반복

- **Pass 1 (happy)**: 위 6 케이스 + key 경고 0건 (React DevTools).
- **Pass 2 (엣지)**: D.1 reset 후 다시 throw / D.5 mailto 차단 환경 / D.10 compare 슬롯 + 같은 polygon hover.
- **Pass 3 (성능)**: D.7 `getComputedStyle` 1회 cost 측정 / D.1 loading skeleton paint 시점.

## Agent 모델

- 설계: opus
- 구현: sonnet (D.1 단독, 나머지 묶음)
- 검증: haiku + Lighthouse a11y

## Critical Files

### 신규
- `frontend/src/app/error.tsx` (D.1)
- `frontend/src/app/loading.tsx` (D.1)
- `frontend/src/app/app/error.tsx` (D.1)
- `frontend/src/app/app/loading.tsx` (D.1)
- `frontend/e2e/ring0-preflight/02-error-boundary.spec.ts` (D.1)
- `frontend/e2e/ring1-features/a11y.spec.ts` (D.2/D.3)

### 수정
- `frontend/src/app/globals.css` (D.2, D.7)
- `frontend/src/components/landing/Header.tsx` (D.2, D.8)
- `frontend/src/components/landing/Footer.tsx` (D.2)
- `frontend/src/components/landing/BentoFeatures.tsx` (D.2)
- `frontend/src/components/landing/Hero.tsx` (D.2)
- `frontend/src/components/landing/BetaBanner.tsx` (D.2)
- `frontend/src/components/feedback/FeedbackRow.tsx` (D.4)
- `frontend/src/components/feedback/FeedbackModal.tsx` (D.5)
- `frontend/src/components/chat/cards/CompareCard.tsx` (D.6)
- `frontend/src/components/chat/SuggestionChips.tsx` (D.6)
- `frontend/src/components/map/TimeSlider.tsx` (D.6)
- `frontend/src/components/chat/cards/InlineChart.tsx` (D.7)
- `frontend/src/components/mobile/BottomNav.tsx` (D.9)
- `frontend/src/components/map/DistrictLayer.tsx` (D.10)

### 참조
- `frontend/src/stores/toastStore.ts` (D.4 의존, B.2 에서 도입)

## Rollout 머지 순서

D.1 (단독, 영향 큼) → D.6/D.10 (저위험) → D.7/D.8/D.9 (visual) → D.2/D.3 (a11y 묶음) → D.4/D.5 (B.2 토스트 머지 후)
