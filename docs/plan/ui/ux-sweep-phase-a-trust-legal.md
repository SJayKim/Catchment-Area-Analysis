# UX Sweep — Phase A · 신뢰/법적 Quick Wins

> 시리즈: **UX Sweep 2026-04-30** (38건 점검 → 6 phase 분할)
> 본 phase 영역: 랜딩 (Footer / BetaBanner / Bento) · 예상 1~2h
> 타 phase: [B 핵심 막힘](ux-sweep-phase-b-core-blockers.md) · [C 자연스러움](ux-sweep-phase-c-polish.md) · [D A11y/마감](ux-sweep-phase-d-a11y.md) · [E Premium defer](ux-sweep-phase-e-premium-deferred.md) · [F Tier hook](ux-sweep-phase-f-tier-hook.md)

## Context

직전 38건 UX 점검 결과 중 **첫 인상에서 "버려진 서비스"로 보이게 만드는 4건**. 사용자 신뢰 회복을 1순위로 가장 빠르게 머지 가능한 묶음으로 구성. 회귀 위험은 랜딩 영역에 局所화되어 최저.

- 메모리 참조: `feature-list.md` F11(Landing) 의 "법적 페이지 링크" 항목 → A.3 가 spec 을 실제 구현으로 채움.
- 인접 plan: `landing-onboarding-feedback.md` 와 영역 중복 — 본 plan 은 dismiss/링크 정정만, onboarding 영역은 그대로 유지.

## Checklist

- [ ] **A.1** BetaBanner 닫기 + localStorage 영구 dismiss [S]
- [ ] **A.2** Footer GitHub 링크 정정 (`anthropics/claude-code` → `NEXT_PUBLIC_REPO_URL` 환경변수 + fallback null) [S]
- [ ] **A.3** Footer 약관/개인정보/문의 섹션 + `/terms`·`/privacy` placeholder 페이지 [M]
- [ ] **A.4** Bento 6개 카드 onClick → `?role=&q=` deeplink [M] _(B.6 머지 후)_

## 변경 사양

### A.1 BetaBanner dismiss
- 파일: `frontend/src/components/landing/BetaBanner.tsx` (현 36 LOC)
- `useState` + `useEffect` 추가. mount 시 `localStorage.getItem('ms_beta_banner_dismissed')` 체크.
- 초기 `isOpen` 은 `null`(불확정), `useEffect` 에서만 결정 → hydration mismatch 회피.
- 우상단 버튼 24×24, `lucide-react` X 아이콘, `aria-label="배너 닫기"`.

### A.2 GitHub 링크
- 파일: `frontend/src/components/landing/Footer.tsx:78`
- 변경: `process.env.NEXT_PUBLIC_REPO_URL` 사용. 환경변수 없으면 `<li>` 자체 미렌더.

### A.3 법적 링크 + placeholder
- 파일: `Footer.tsx` + 신규 `app/terms/page.tsx`, `app/privacy/page.tsx`
- "법적" 섹션 추가 또는 "지원" 안에 합치기. `이용약관 → /terms`, `개인정보처리방침 → /privacy`, `문의 → mailto:` (또는 기존 `feedbackHref`).
- placeholder 페이지: 50자 본문 + "초안 — 외부 변호사 검토 전" 라벨.

### A.4 Bento deeplink
- 파일: `frontend/src/components/landing/BentoFeatures.tsx:99-129`
- `<article>` → `<Link href>` + `role="link"`. 각 cell 에 `cta: { q?: string; anchor?: string }` 필드 추가.
  - map → `?q=상권을 추천해줘` / chat → `?q=이 상권 분석해줘` / compare → `?q=강남, 홍대 비교` / recommend → `?q=여기서 뭐하면 좋을까` / simulation → `?q=카페 매출 시뮬레이션` / pdf → `?q=리포트 다운로드` (B.5 의존).
- **선행 의존: B.6** (deeplink history scrub). 미준수 시 새로고침 자동 재전송.

## 재검토 (Self-Review Gate)

### 엣지케이스
- **Safari Private mode** localStorage 차단 → try/catch graceful, banner 항상 노출.
- **SSR hydration**: A.1 의 `null → false → true` 3-state 로 mismatch 회피.
- **A.4 머지 순서**: B.6 미머지 상태에서 A.4 만 들어가면 새로고침 시 자동 재전송 → 항상 `B.6 → A.4` 강제.
- **placeholder 법적 본문**: 외부 변호사 검토 전이라는 사실을 페이지 헤더에 명시. SEO `noindex` 권장.

### 메모리 교훈
- `chatStore.ts` 의 `?q=` 처리 흐름은 이미 staleness 가드된 sendMessage 와 정합. A.4 는 라우팅만, 추가 race 없음.
- 인접 `landing-copy-icon-refresh.md` 와 충돌 없음 (본 plan 은 카드 cta 만, 카피/아이콘은 별 plan).

### 타 plan 충돌
- `landing-onboarding-feedback.md` 의 BetaBanner 가 onboarding 시리즈에 포함될 가능성 → 본 phase 는 dismiss 만 추가. onboarding 컴포넌트 신설 시 둘 다 살림.

## Scenario (E2E Ring Mapping)

| Test ID | Spec | Case |
|---------|------|------|
| `Ring1-F11-A1` | `e2e/ring1-features/f11-landing.spec.ts` | 배너 표시 → x 클릭 → 사라짐 → 새로고침 후에도 dismiss 유지 |
| `Ring1-F11-A2` | 동상 | env 없음 → li 미노출 / env 있음 → 새 탭 link `target="_blank"` |
| `Ring1-F11-A3` | 동상 | footer 링크 클릭 → `/terms`·`/privacy` 200 + h1 존재 |
| `Ring2-J01-A4` | `e2e/ring2-journeys/j01-first-time-user.spec.ts` | Bento "AI 분석" 카드 클릭 → URL `?q=` → 자동 송신 1회 → 새로고침 시 0회 (B.6 검증 포함) |

## Pass 반복

- **Pass 1 (happy path)**: 위 Ring1+2 spec 4개 PASS.
- **Pass 2 (엣지)**: Safari Private localStorage 차단 시뮬레이션 / `?q=` 빈 문자열 / Bento 모든 6개 cta.
- **Pass 3 (성능)**: 랜딩 LCP ≥ 베이스라인 -10% 회귀 시 fail. lucide X 아이콘 추가로 번들 영향 확인.

## Agent 모델

- 설계: opus (본 plan)
- 구현: sonnet (per item, 30~60분 단위 atomic edit)
- 검증: haiku (typecheck/lint + ring1+2 spec)

## Critical Files

### 신규
- `frontend/src/app/terms/page.tsx`
- `frontend/src/app/privacy/page.tsx`

### 수정
- `frontend/src/components/landing/BetaBanner.tsx` (A.1)
- `frontend/src/components/landing/Footer.tsx` (A.2, A.3)
- `frontend/src/components/landing/BentoFeatures.tsx` (A.4)
- `frontend/.env.example` 또는 README — `NEXT_PUBLIC_REPO_URL` 문서화

### 참조
- `frontend/src/app/app/page.tsx:47-55` (`DeepLinkHandler` — A.4 가 의존)
- `docs/spec/features/F11-landing.md`

## Rollout 머지 순서

A.2 → A.1 → A.3 → (B.6 머지 확인 후) A.4
