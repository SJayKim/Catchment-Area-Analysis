# UX Sweep — Phase F · Premium 사전작업 (Tier Hook, 옵션)

> 시리즈: **UX Sweep 2026-04-30** (38건 점검 → 6 phase 분할)
> 본 phase 영역: Phase 2 머지 시 surface diff 최소화를 위한 hook 자리만 마련 · 옵션 phase
> 타 phase: [A Quick Wins](ux-sweep-phase-a-trust-legal.md) · [B 핵심 막힘](ux-sweep-phase-b-core-blockers.md) · [C 자연스러움](ux-sweep-phase-c-polish.md) · [D A11y/마감](ux-sweep-phase-d-a11y.md) · [E Premium defer](ux-sweep-phase-e-premium-deferred.md)

## Context

Phase 2 (OAuth/결제/Tier 게이팅) 시작 시 **모든 Premium 기능에 일관된 게이팅 hook 을 박아두는 게 효율적**. 본 phase 는 그 hook 자리만 미리 마련 — 실제 게이팅 호출은 0건, 단지 컴파일 가능한 stub.

가치: Phase 2 머지 시 grep `useTier` 로 wiring 위치 일괄 확인 가능 → surface diff 최소화 + 누락 0.

옵션 phase 이므로 사용자 선택. Phase 2 가 1~2분기 내 진행 예정이면 본 phase 진행 권장. 그렇지 않으면 SKIP.

## Checklist

- [ ] **F.1** `useTier` hook 신규 (하드코딩 `free` 반환) [S]
- [ ] **F.2** `<FeatureGate tier="...">` 래퍼 컴포넌트 신규 (placeholder, 자식 그대로 렌더) [S]

## 변경 사양

### F.1 useTier hook
- 신규: `frontend/src/hooks/useTier.ts`
- 시그니처:
  ```ts
  export type Tier = 'free' | 'pro' | 'team';
  export function useTier(): { tier: Tier; isLoading: boolean } {
    // Phase 2 에서 OAuth 후 실제 값 반환.
    // 현재는 하드코딩 free.
    return { tier: 'free', isLoading: false };
  }
  ```
- 사용 예 (실제 게이팅 0, 미래 surface 만 표시):
  ```tsx
  // F04 업종 심층 카드 컴포넌트 (Phase 2 도입 예정)
  const { tier } = useTier();
  if (tier === 'free') return <UpgradePrompt feature="industry-analysis" />;
  ```

### F.2 FeatureGate 컴포넌트
- 신규: `frontend/src/components/common/FeatureGate.tsx`
- 시그니처:
  ```tsx
  type Props = { tier: Tier; fallback?: React.ReactNode; children: React.ReactNode };
  export function FeatureGate({ tier, fallback = null, children }: Props) {
    const { tier: userTier } = useTier();
    // Phase 2 에서 tier 비교 로직 활성화. 현재는 children 그대로 렌더 (no-op).
    return <>{children}</>;
  }
  ```
- 향후 패턴:
  ```tsx
  <FeatureGate tier="pro" fallback={<UpgradePrompt />}>
    <IndustryAnalysisCard data={...} />
  </FeatureGate>
  ```

## 재검토 (Self-Review Gate)

### 엣지케이스
- **F.1 SSR**: `useTier` 가 hook 이라 client only. 서버 컴포넌트에서 호출 시 컴파일 오류 → 사용처는 `'use client'` 강제.
- **F.2 no-op 의도치 않은 사용**: 현재 children 그대로 렌더이므로 사용해도 동작 변경 0. Phase 2 머지 후 비로소 게이팅 활성. **명시적 주석으로 stub 임을 표시**.

### 메모리 교훈
- 별도 메모리 없음.

### 타 plan 충돌
- `commercialization-plan.md` (Phase 2) 의 게이팅 미들웨어 디자인과 일치 — backend 에서도 `tier` 를 user object 에 attach 후, frontend 가 `/api/me` 응답에서 가져오는 흐름 가정.

## Scenario (E2E Ring Mapping)

| Test ID | Spec | Case |
|---------|------|------|
| `Ring0-F1` | `e2e/ring0-preflight/01-stack-up.spec.ts` 확장 | `useTier` import 컴파일 OK + `tier === 'free'` 항상 |
| `Ring0-F2` | 동상 | `<FeatureGate tier="pro">{X}</FeatureGate>` → `X` 그대로 렌더 (no-op) |

## Pass 반복

- **Pass 1 (happy)**: 위 2 케이스 PASS + typecheck OK.
- **Pass 2 (엣지)**: SSR 사용처에서 컴파일 오류 발생하지 않는지 (서버 컴포넌트에서 import 만 해도 OK).
- **Pass 3 (성능)**: 영향 없음.

## Agent 모델

- 설계: opus
- 구현: sonnet (single-file 2개, 5분)
- 검증: haiku (typecheck only)

## Critical Files

### 신규
- `frontend/src/hooks/useTier.ts` (F.1)
- `frontend/src/components/common/FeatureGate.tsx` (F.2)

### 수정
없음 (사용처 도입은 Phase 2 에서).

### 참조
- `docs/plan/business/commercialization-plan.md` — Phase 2 마스터.

## Rollout

옵션 phase. Phase 2 시작이 1~2분기 내 예정 → 진행 권장. 그 이상 지연 → SKIP (Phase 2 시 한 번에 도입).

머지 순서: F.1 → F.2. 단독 PR 가능, 회귀 risk 0.
