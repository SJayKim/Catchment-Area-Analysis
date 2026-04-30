/**
 * F.1 — Tier hook stub (Phase F · UX Sweep 2026-04-30).
 *
 * Phase 2 (OAuth/결제/Tier 게이팅) 머지 시 surface diff 최소화를 위해 미리
 * 박아두는 hook 자리. 현재는 하드코딩 `'free'` 반환 — 실제 게이팅 호출 0건.
 *
 * Phase 2 에서 `/api/me` 응답을 SWR 또는 Zustand 로 가져와 실제 tier 값 반환
 * 하도록 교체할 예정. 그 시점까지 모든 사용처는 `tier === 'free'` 분기만 받음.
 *
 * 사용처는 `'use client'` 컴포넌트로 강제 (React hook 규칙).
 */

export type Tier = 'free' | 'pro' | 'team';

export interface TierState {
  tier: Tier;
  isLoading: boolean;
}

export function useTier(): TierState {
  return { tier: 'free', isLoading: false };
}
