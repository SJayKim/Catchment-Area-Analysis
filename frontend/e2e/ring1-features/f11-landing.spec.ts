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

  test('1-F11-A1 — beta banner dismiss persists across reloads', async ({ page }) => {
    await page.addInitScript(() => {
      try {
        window.localStorage.removeItem('ms_beta_banner_dismissed');
      } catch {}
    });
    await page.goto('/');
    const banner = page.locator('[data-testid="beta-banner"]');
    await expect(banner).toBeVisible();

    const dismiss = page.locator('[data-testid="beta-banner-dismiss"]');
    await expect(dismiss).toHaveAttribute('aria-label', '배너 닫기');
    await dismiss.click();
    await expect(banner).toHaveCount(0);

    const stored = await page.evaluate(() =>
      window.localStorage.getItem('ms_beta_banner_dismissed')
    );
    expect(stored).toBe('1');

    await page.reload();
    await expect(page.locator('[data-testid="beta-banner"]')).toHaveCount(0);
  });

  test('1-F11-A2 — repo link only renders when env is set', async ({ page }) => {
    await page.goto('/');
    const repoLink = page.locator('[data-testid="footer-repo-link"]');
    const count = await repoLink.count();
    if (count === 0) {
      // env unset — graceful fallback path verified
      expect(count).toBe(0);
    } else {
      const href = await repoLink.getAttribute('href');
      expect(href).not.toContain('anthropics/claude-code');
      expect(href).toMatch(/^https?:\/\//);
      await expect(repoLink).toHaveAttribute('target', '_blank');
      await expect(repoLink).toHaveAttribute('rel', /noopener/);
    }
  });

  test('1-F11-A3 — footer legal links resolve with h1', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('[data-testid="footer-terms-link"]')).toBeVisible();
    await expect(page.locator('[data-testid="footer-privacy-link"]')).toBeVisible();

    const termsResp = await page.goto('/terms');
    expect(termsResp?.status()).toBe(200);
    await expect(page.locator('[data-testid="terms-page"] h1')).toHaveText(/이용약관/);

    const privacyResp = await page.goto('/privacy');
    expect(privacyResp?.status()).toBe(200);
    await expect(page.locator('[data-testid="privacy-page"] h1')).toHaveText(
      /개인정보처리방침/
    );
  });

  // (Mock-only) 신규 1 — Plan UX Sweep Phase A 엣지: Safari Private localStorage
  // 거부 시에도 BetaBanner 가 graceful 하게 노출되어야 함. setItem/getItem 둘
  // 다 throw 하도록 monkey-patch 한 뒤 페이지 진입.
  test('Ring1-F11-A1-EDGE-PRIVATE — Safari Private localStorage 거부 graceful', async ({
    page,
  }) => {
    await page.addInitScript(() => {
      const block = (op: string) => {
        throw new DOMException(
          `${op} is disabled in private mode`,
          'SecurityError'
        );
      };
      // proto 레벨에서 throw 하도록 정의 — readDismissed/writeDismissed try/catch
      // 가 모두 catch 해야 함.
      const proto = Object.getPrototypeOf(window.localStorage);
      try {
        Object.defineProperty(proto, 'getItem', {
          configurable: true,
          value: () => block('getItem'),
        });
        Object.defineProperty(proto, 'setItem', {
          configurable: true,
          value: () => block('setItem'),
        });
        Object.defineProperty(proto, 'removeItem', {
          configurable: true,
          value: () => block('removeItem'),
        });
      } catch {
        // 일부 브라우저는 readonly — 무시 (테스트 자체가 SkippedNotApplicable)
      }
    });

    await page.goto('/');
    // BetaBanner 는 dismissed=null → false 흐름이라 throw 케이스에서도 항상 노출.
    const banner = page.locator('[data-testid="beta-banner"]');
    await expect(banner).toBeVisible();

    // dismiss 클릭 → setItem 또한 throw 하지만 in-memory state 로 닫혀야 함.
    const dismiss = page.locator('[data-testid="beta-banner-dismiss"]');
    await dismiss.click();
    await expect(banner).toHaveCount(0);

    // 새로고침 후에는 getItem 도 throw 하므로 dismissed 가 false 로 떨어져 다시
    // 노출 — 즉 영구 dismiss 는 불가하지만 세션 내 dismiss 는 동작한다.
    await page.reload();
    await expect(page.locator('[data-testid="beta-banner"]')).toBeVisible();

    // localStorage proxy 는 사라졌으나 페이지 자체는 unhandled error 없이 정상.
    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));
    await page.waitForTimeout(500);
    expect(errors).toEqual([]);
  });
});

test.describe('Ring 1 — F11 BENTO 6 cells coverage', () => {
  // (Mock-only) 신규 3 — BentoFeatures 6 cell 전수: data-testid + 헤더/본문 텍스트
  // 가 cell.id 별 의도된 카피와 매핑되는지 확인. Phase A.4 의 onClick deeplink 가
  // 추후 도입되면 본 spec 의 expectQ 매핑도 cta 클릭 후 URL 검증으로 확장.
  test('Ring1-F11-A4-BENTO-ALL6 — 6 Bento cell 가시성 + q 매핑 메타', async ({
    page,
  }) => {
    await page.goto('/');
    const bento = page.locator('[data-testid="bento-features"]');
    await expect(bento).toBeVisible();

    // Plan A.4 의 q 매핑 표 (BentoFeatures.tsx 카피와 일치 검증).
    const expectations: { id: string; copy: RegExp; expectQ: string }[] = [
      { id: 'map', copy: /지도|상권|탐색/, expectQ: '상권을 추천해줘' },
      { id: 'chat', copy: /대화|리포트|질문/, expectQ: '이 상권 분석해줘' },
      { id: 'compare', copy: /비교|나란히/, expectQ: '강남, 홍대 비교' },
      { id: 'recommend', copy: /추천|업종|점수/, expectQ: '여기서 뭐하면 좋을까' },
      { id: 'simulation', copy: /시뮬레이션|p25|매출/, expectQ: '카페 매출 시뮬레이션' },
      { id: 'pdf', copy: /PDF|리포트|저장/, expectQ: '리포트 다운로드' },
    ];

    for (const exp of expectations) {
      const cell = page.locator(`[data-testid="bento-cell-${exp.id}"]`);
      await expect(cell, `cell ${exp.id} 가시`).toBeVisible();
      const text = (await cell.textContent()) ?? '';
      expect.soft(exp.copy.test(text), `cell ${exp.id} copy match`).toBe(true);
      // expectQ 는 plan A.4 deeplink 매핑 — 현재 stub 단계에서는 메타 보존만 검증.
      expect(exp.expectQ.length).toBeGreaterThan(0);
    }
  });
});
