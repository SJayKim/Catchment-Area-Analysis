'use client';

import type { ReactNode } from 'react';
import { useTier, type Tier } from '@/hooks/useTier';

/**
 * F.2 — Tier 게이팅 wrapper stub (Phase F · UX Sweep 2026-04-30).
 *
 * Phase 2 머지 시 본 컴포넌트의 비교 로직만 활성화하면 모든 Premium 카드/패널
 * surface 가 일괄 게이팅된다. 현재는 children 그대로 렌더 (no-op).
 *
 * 향후 패턴:
 *   <FeatureGate tier="pro" fallback={<UpgradePrompt />}>
 *     <IndustryAnalysisCard data={...} />
 *   </FeatureGate>
 *
 * Phase 2 활성화 시 변경 지점은 본 파일 한 곳 — useTier 비교 후 fallback 렌더.
 */

interface Props {
  tier: Tier;
  fallback?: ReactNode;
  children: ReactNode;
}

export function FeatureGate({ tier: _required, fallback: _fallback, children }: Props) {
  // Phase 2 에서 활성화 — 현재는 stub 으로 children 그대로 렌더.
  // 의도적으로 useTier 를 호출해 hook 사용처 표면을 grep 으로 추적 가능하게 유지.
  useTier();
  return <>{children}</>;
}
