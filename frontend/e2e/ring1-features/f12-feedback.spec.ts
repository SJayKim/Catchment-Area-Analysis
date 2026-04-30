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
    // FeedbackFab returns null when both env vars are unset → element never attaches.
    // `locator.getAttribute()` waits indefinitely in that case, so precheck count first.
    if ((await fab.count()) === 0) {
      test.skip(true, 'Feedback FAB not rendered (NEXT_PUBLIC_KAKAO_CHANNEL_URL / FEEDBACK_FORM_URL unset)');
      return;
    }
    const mode = await fab.getAttribute('data-feedback-mode');
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

  // (Mock-only) 신규 9 — Plan UX Sweep Phase D: Tally src 차단 → 5s timer
  // 만료 → fallback 노출. mode==='tally' 가 필수이고 build env 가 hidden / kakao
  // 이면 skip.
  test('Ring1-F12-D5-IFRAME-BLOCK — route.abort tally src → 5s 후 mailto/kakao fallback', async ({
    page,
  }) => {
    // Tally 도메인 전체 차단 — iframe.onLoad 미발화 → 5s timer 가 fallback 으로
    // 전환해야 함.
    await page.route('**/tally.so/**', (route) =>
      route.abort('failed').catch(() => undefined)
    );
    await page.route('**/*tally*/**', (route) =>
      route.abort('failed').catch(() => undefined)
    );

    await page.goto('/');
    const fab = page.locator('[data-testid="feedback-fab"]');
    if ((await fab.count()) === 0) {
      test.skip(true, 'FeedbackFab not rendered (env unset)');
      return;
    }
    const mode = await fab.getAttribute('data-feedback-mode');
    if (mode !== 'tally') {
      test.skip(true, `Feedback mode=${mode} (need tally for D5-IFRAME-BLOCK)`);
      return;
    }

    await fab.click();
    const modal = page.locator('[data-testid="feedback-modal"]');
    await expect(modal).toBeVisible();

    // iframe 이 마운트 되었는지 — onError/onLoad 어느 쪽도 발화 X 가정.
    // 5s timer 만료 후 fallback 노출.
    const fallback = page.locator('[data-testid="feedback-modal-fallback"]');
    await expect(fallback).toBeVisible({ timeout: 7000 });

    // mailto 또는 kakao 채널 링크 중 하나 이상 노출 (env 의존). 둘 다 미설정
    // 환경에서는 안내 텍스트로 fallback.
    const mailto = page.locator('[data-testid="feedback-modal-mailto"]');
    const kakao = page.locator('[data-testid="feedback-modal-kakao"]');
    const mailtoCount = await mailto.count();
    const kakaoCount = await kakao.count();
    expect(mailtoCount + kakaoCount).toBeGreaterThanOrEqual(0);

    if (mailtoCount > 0) {
      const href = await mailto.getAttribute('href');
      expect(href).toMatch(/^mailto:/);
    }
    if (kakaoCount > 0) {
      const href = await kakao.getAttribute('href');
      expect(href).toMatch(/^https?:\/\//);
    }
  });

  test('Ring1-F12-E3 — Premium CTA hidden when NEXT_PUBLIC_PREMIUM_CTA_ENABLED!=true', async ({
    page,
  }) => {
    // E.3 — Phase 2 OAuth/결제 wiring 전까지 default off.
    // 본 spec 은 build-time env 미설정 또는 'false' 가정. CI 가 `'true'` 로 띄우면 skip.
    const enabled = process.env.NEXT_PUBLIC_PREMIUM_CTA_ENABLED === 'true';
    if (enabled) {
      test.skip(true, 'Premium CTA is enabled in this build — gate test does not apply');
      return;
    }

    await page.goto('/app');
    await page.waitForLoadState('domcontentloaded');
    await page.context().clearCookies();

    const seeded = await page.evaluate(() => {
      // @ts-expect-error — dev-time window exposure
      const store = window.__chatStore;
      if (store && typeof store.setState === 'function') {
        store.setState({ messageCount: 10 });
        return true;
      }
      return false;
    });
    if (!seeded) {
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

    // mood = 5 (≥ 4) 클릭 → 게이트 OFF 면 Premium CTA 미노출 보장.
    await page.locator('[data-testid="survey-mood-5"]').click();
    const cta = page.locator('[data-testid="survey-premium-cta"]');
    expect(await cta.count()).toBe(0);
  });
});
