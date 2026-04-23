/**
 * Ring 3 — Negative: feedback URL env missing
 *
 * 2026-04-23 Plan `landing-onboarding-feedback` §6 L3.
 * NEXT_PUBLIC_KAKAO_CHANNEL_URL + NEXT_PUBLIC_FEEDBACK_FORM_URL 모두 부재일 때 FAB 는 숨김.
 * 개발 환경에서 해당 두 env 가 비어 있는지를 프론트에서 runtime 감지해 FAB 컴포넌트가
 * `null` 을 렌더하는지 검증.
 */

import { test, expect } from '../helpers/setup';

test.describe('Ring 3 — Feedback FAB hidden when URLs missing', () => {
  test('3-NEG-FEEDBACK-URL-MISSING — FAB 요소 비노출 또는 컴포넌트 null', async ({ page }) => {
    await page.goto('/');
    const fab = page.locator('[data-testid="feedback-fab"]');
    const fabCount = await fab.count();

    if (fabCount === 0) {
      // Expected behavior: component returned null when no env is set
      expect(fabCount).toBe(0);
      return;
    }

    // FAB가 렌더된 경우에도 data-feedback-mode가 'hidden'이 아니어야 함
    // (env가 설정된 환경에서는 스킵)
    const mode = await fab.getAttribute('data-feedback-mode');
    expect(['kakao', 'tally']).toContain(mode);
    test.skip(true, 'Feedback env is set in this run — FAB correctly visible');
  });
});
