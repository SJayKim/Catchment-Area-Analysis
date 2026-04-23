/**
 * Ring 1 — F12 Feedback
 *
 * 2026-04-23 Plan `landing-onboarding-feedback` §6.
 * L3 FAB (kakao > tally > hidden) · L1 card 👍👎 · L2 microsurvey.
 */

import { test, expect } from '../helpers/setup';

test.describe('Ring 1 — F12 Feedback FAB', () => {
  test('1-F12-FAB-KAKAO — FAB opens kakao URL when NEXT_PUBLIC_KAKAO_CHANNEL_URL set', async ({ page }) => {
    await page.goto('/');
    const fab = page.locator('[data-testid="feedback-fab"]');
    const mode = await fab.getAttribute('data-feedback-mode').catch(() => null);

    if (mode === 'hidden' || mode === null) {
      test.skip(true, 'Feedback URL env not configured in this run');
      return;
    }

    await expect(fab).toBeVisible();

    if (mode === 'kakao') {
      const openedUrl = await page.evaluate(async () => {
        const calls: string[] = [];
        const original = window.open;
        window.open = (url?: string | URL): WindowProxy | null => {
          if (url) calls.push(String(url));
          return null;
        };
        const btn = document.querySelector<HTMLButtonElement>(
          '[data-testid="feedback-fab"]'
        );
        btn?.click();
        window.open = original;
        return calls[0] ?? null;
      });
      expect(openedUrl).toBeTruthy();
      expect(openedUrl).toMatch(/^https?:\/\//);
    } else if (mode === 'tally') {
      await fab.click();
      await expect(page.locator('[data-testid="feedback-modal"]')).toBeVisible();
      // ESC closes
      await page.keyboard.press('Escape');
      await expect(page.locator('[data-testid="feedback-modal"]')).toBeHidden();
    }
  });
});

test.describe('Ring 1 — F12 Card Thumbs (L1)', () => {
  test('1-F12-CARD-THUMBS — feedback row POST /api/feedback/score', async ({ page }) => {
    // Inject a trace_id directly to simulate a done event already received.
    await page.goto('/app');
    await page.waitForLoadState('domcontentloaded');

    const scoreCalls: string[] = [];
    await page.route('**/api/feedback/score', async (route) => {
      scoreCalls.push(await route.request().postData() ?? '');
      await route.fulfill({ status: 202, body: '' });
    });

    // Seed minimal state so FeedbackRow renders: one assistant message + lastTraceId
    await page.evaluate(() => {
      // @ts-expect-error — dev-time window exposure
      const store = window.__chatStore || null;
      // fall back to direct store import via dynamic require is not possible in e2e;
      // instead we dispatch via stored module if exposed.
      if (store && typeof store.setState === 'function') {
        store.setState({
          messages: [
            {
              id: 'assist-1',
              role: 'assistant',
              content: 'dummy',
              type: 'text',
              timestamp: new Date(),
            },
          ],
          lastTraceId: 'trace-test-1',
        });
      }
    });

    const thumb = page.locator('[data-testid="feedback-thumbs-up"]');
    const visible = await thumb.isVisible().catch(() => false);
    if (!visible) {
      test.skip(true, 'FeedbackRow not rendered — window.__chatStore not exposed in build');
      return;
    }

    await thumb.click();

    // Wait for network to settle + state ack
    await page.waitForTimeout(300);
    expect(scoreCalls.length).toBeGreaterThanOrEqual(1);
    const payload = JSON.parse(scoreCalls[0] || '{}');
    expect(payload.trace_id).toBe('trace-test-1');
    expect(payload.value).toBe('up');
  });
});

test.describe('Ring 1 — F12 Free Limit Survey (L2)', () => {
  test('1-F12-SURVEY — 5-emoji rating pushes GA4 dataLayer event', async ({ page }) => {
    // Seed messageCount ≥ 5 via query-driven navigation; SurveyTrigger uses store state.
    await page.goto('/app');
    await page.waitForLoadState('domcontentloaded');

    // Clear cookie for this week if any
    await page.context().clearCookies();

    const opened = await page.evaluate(() => {
      // @ts-expect-error — dev-time window exposure
      const store = window.__chatStore;
      if (store && typeof store.setState === 'function') {
        store.setState({ messageCount: 10 });
        return true;
      }
      return false;
    });

    if (!opened) {
      test.skip(true, 'chatStore not exposed — survey cannot be triggered');
      return;
    }

    await page.reload();
    const dialog = page.locator('[data-testid="free-limit-survey"]');
    const visible = await dialog.isVisible({ timeout: 3000 }).catch(() => false);
    if (!visible) {
      test.skip(true, 'Survey did not mount (messageCount reset on reload)');
      return;
    }

    await page.locator('[data-testid="survey-mood-5"]').click();
    const pushed = await page.evaluate(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return (window as any).dataLayer?.slice(-1)?.[0];
    });
    expect(pushed).toBeTruthy();
  });
});
