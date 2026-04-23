/**
 * Ring 1 — F11 Landing
 *
 * 2026-04-23 Plan `landing-onboarding-feedback` §2.
 * 랜딩 페이지(/) 의 Hero · RoleSelector · Bento · BetaBanner · HeroVisual 확인.
 */

import { test, expect } from '../helpers/setup';

test.describe('Ring 1 — F11 Landing', () => {
  test('1-F11-HERO — hero headline + CTA + Pretendard font', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const heroSection = page.locator('[data-testid="hero-section"]');
    await expect(heroSection).toBeVisible();

    const headline = page.locator('[data-testid="hero-headline"]');
    await expect(headline).toBeVisible();
    const text = (await headline.textContent()) ?? '';
    expect(text.length).toBeGreaterThan(10);

    const primaryCta = page.locator('[data-testid="hero-primary-cta"]');
    await expect(primaryCta).toBeVisible();

    // Pretendard font should load (checked via font-family chain)
    const fontFamily = await page.evaluate(
      () => getComputedStyle(document.body).fontFamily
    );
    expect(fontFamily).toMatch(/Pretendard/i);
  });

  test('1-F11-ROLE — role chip swaps hero copy + persists in localStorage', async ({ page }) => {
    await page.goto('/');
    const investor = page.locator('[data-testid="role-chip-investor"]');
    await investor.click();

    // aria-checked toggled
    await expect(investor).toHaveAttribute('aria-checked', 'true');

    // localStorage persists the role
    const stored = await page.evaluate(() => window.localStorage.getItem('ms_role'));
    expect(stored).toBe('investor');

    // Hero copy swaps — starter chips should contain the investor-specific phrasing
    const chips = page.locator('[data-testid="starter-chips"]');
    const chipsText = (await chips.textContent()) ?? '';
    expect(chipsText).toMatch(/비교|투자|매출/);
  });

  test('1-F11-CHIP-PREFILL — starter chip navigates to /app with q= + role=', async ({ page }) => {
    await page.goto('/');

    // Select a role first so it propagates to the URL
    await page.locator('[data-testid="role-chip-owner"]').click();

    const chip = page.locator('[data-testid="starter-chip-0"]');
    const chipText = (await chip.textContent())?.trim() ?? '';
    await chip.click();

    await page.waitForURL(/\/app\?/, { timeout: 5000 });
    const url = new URL(page.url());
    expect(url.pathname).toBe('/app');
    expect(url.searchParams.get('role')).toBe('owner');
    const q = url.searchParams.get('q') ?? '';
    expect(q.length).toBeGreaterThan(0);
    expect(chipText).toContain(q.slice(0, 5));
  });

  test('1-F11-BENTO — 6 cells rendered with data-testid', async ({ page }) => {
    await page.goto('/');
    const bento = page.locator('[data-testid="bento-features"]');
    await expect(bento).toBeVisible();
    const cellIds = ['map', 'chat', 'compare', 'recommend', 'simulation', 'pdf'];
    for (const id of cellIds) {
      await expect(page.locator(`[data-testid="bento-cell-${id}"]`)).toBeVisible();
    }
  });

  test('1-F11-BETA-BANNER — beta banner visible with free messaging', async ({ page }) => {
    await page.goto('/');
    const banner = page.locator('[data-testid="beta-banner"]');
    await expect(banner).toBeVisible();
    const text = (await banner.textContent()) ?? '';
    expect(text).toMatch(/베타|무료/);
  });

  test('1-F11-HERO-VISUAL — cross-fade frames rendered', async ({ page }) => {
    await page.goto('/');
    const visual = page.locator('[data-testid="hero-visual"]');
    await expect(visual).toBeVisible();
    const frameCount = await visual.locator('.hero-frame').count();
    expect(frameCount).toBeGreaterThanOrEqual(2);
  });
});
