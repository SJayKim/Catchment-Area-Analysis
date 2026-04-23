# F11 — 랜딩 · 역할 온보딩

> 공개 랜딩 페이지(`/`) + role-based starter prompts 로 신규 방문자를 앱(`/app`)으로 유도.

## 1. 배경

`app/page.tsx` 가 기존에는 지도+챗 앱을 바로 띄웠다. 신규 방문자는 서비스 가치 제안 없이
거대한 도구만 맞닥뜨리는 상황이었다. 2026-04-23 Plan `docs/plan/ui/landing-onboarding-feedback.md`
에서 랜딩 분리가 결정됨.

## 2. 라우팅

```
/        → 랜딩 페이지 (Header · Hero · BentoFeatures · HowItWorks · BetaBanner · Footer)
/app     → 분석 앱 (기존 Home). `?role=<r>&q=<prefill>` deep link 지원
```

E2E 회귀: `page.goto('/')` 는 모두 `page.goto('/app')` 로 이관. 랜딩 고유 검증은
`ring1-features/f11-landing.spec.ts` 에서 `/` 로 고루.

## 3. 주요 컴포넌트 (`frontend/src/components/landing/`)

| 파일 | 책임 |
|---|---|
| `Header.tsx` | 상단 고정 네비 + "시작하기" CTA → `/app` |
| `Hero.tsx` | Big-type H1 + RoleSelector + starter chip + 2개 CTA |
| `RoleSelector.tsx` | 소상공인/투자자/창업 3-way radiogroup, `localStorage['ms_role']` 영속 |
| `HeroVisual.tsx` | CSS-only 지도 + 카드 3종 cross-fade (8s loop, PNG 의존 0) |
| `BentoFeatures.tsx` | 6 cell feature 그리드 |
| `HowItWorks.tsx` | 3단계 (지도 클릭 → 프리뷰 → AI 분석) 진행 인디케이터 |
| `BetaBanner.tsx` | 베타 무료 안내 + CTA |
| `Footer.tsx` | 데이터 출처 · 면책 · 피드백 링크 (env 기반) |
| `roles.ts` | `ROLES` 맵 — 역할별 Hero 카피 + starter chip 프리셋 |

## 4. Role routing

역할 선택 시:

1. `localStorage['ms_role']` 저장
2. Hero H1/Sub/starter chip 동적 스왑
3. starter chip 클릭 → `/app?role=<r>&q=<prefill>` navigation
4. `/app` 의 `DeepLinkHandler` (`app/app/page.tsx`) 가 URL params → `chatStore.setRole()` + prefill
   을 auto-send 로 전달 (300ms delay)

## 5. 브랜드 토큰

`app/globals.css` 에 `[data-theme='light'|'dark']` 이중 팔레트 + brand tokens:

- `--brand-deep-blue` / `--brand-deep-blue-hover`
- `--brand-teal` / `--brand-teal-hover`
- `--compare-slot-1/2/3` (DistrictLayer 연동, F05)
- 기본값 **light** (한국 B2C 관례). `prefers-color-scheme` 로 dark 자동 추적
  (명시 토글은 Phase E 에서 추가 예정).

## 6. 폰트

`app/layout.tsx` 에서 Pretendard Variable 공식 CDN (jsdelivr) 을 `<link>` 로 프리로드.
Inter 는 라틴 fallback 으로만 유지.

## 7. 접근성

- RoleSelector: `role="radiogroup"` + `role="radio"` + `aria-checked`
- Hero CTA 는 `button` 또는 `<a>` 로 적절히 분리
- 전역 `@media (prefers-reduced-motion: reduce)` 에서 모든 `animation-duration` → `0.01ms` clamp

## 8. 완료 조건 (Plan Ring1 F11 시나리오)

- `1-F11-HERO` — Hero H1/Sub/CTA + Deep Blue · Teal computed style + Pretendard 로드
- `1-F11-ROLE` — role chip 3 way + Hero 카피 스왑 + `localStorage['ms_role']`
- `1-F11-CHIP-PREFILL` — chip 클릭 → `/app?role=...&q=...` + auto send
- `1-F11-BENTO` — 6 cell `data-testid="bento-cell-*"`
- `1-F11-BETA-BANNER` — 베타 무료 문구
- `1-F11-HERO-VISUAL` — hero-frame cross-fade 정상, reduced-motion 시 정지

## 9. Out of scope (별도 Plan)

- 테마 토글 UI (Phase E)
- Tailwind v4 + OKLCH (별도 `tailwind-v4-oklch-migration.md`)
- 모바일 bottom sheet (Phase E)
