/**
 * Phase D — D.9 BottomNav WCAG 2.5.8 Target Size (AAA 24×24 / AA 44×44).
 *
 * 2026-04-30 Plan `ux-sweep-phase-d-a11y` D.9. mobile-iphone project 한정.
 *
 *   npx playwright test --project=mobile-iphone --grep "Mobile-D9-WCAG258"
 *
 * BottomNav minHeight ≥ 60px / icon 24px / label 13px 회귀.
 */

import { test, expect } from '../helpers/setup';

// (Mock-only) 신규 12 — mobile breakpoint 한정. chromium project 에서 돌면
// BottomNav 가 마운트되지 않아 의미 없음 — explicit skip.
test.describe('Ring1-Mobile-D9 — BottomNav WCAG 2.5.8', () => {
  test('Ring1-Mobile-D9-WCAG258 — minHeight ≥ 60 / icon 24 / label 13', async ({
    page,
    isMobile,
  }, testInfo) => {
    // mobile-iphone 또는 mobile-galaxy project 에서만 실행.
    if (!isMobile && !/mobile/i.test(testInfo.project.name)) {
      test.skip(true, `Project ${testInfo.project.name} is not mobile`);
      return;
    }

    await page.goto('/app');
    // BottomNav 마운트 대기 — useBreakpoint 가 mobile 로 settle 된 후에만 mount.
    const nav = page.locator('nav[role="tablist"]');
    await expect(nav).toBeVisible({ timeout: 8000 });

    // (1) BottomNav tab 버튼 minHeight ≥ 60px.
    const tabs = nav.locator('button[role="tab"]');
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(2);

    for (let i = 0; i < tabCount; i++) {
      const tab = tabs.nth(i);
      const minH = await tab.evaluate(
        (el) => parseFloat((el as HTMLElement).style.minHeight || '0')
      );
      expect.soft(minH, `tab[${i}] minHeight ≥ 60`).toBeGreaterThanOrEqual(60);
    }

    // (2) 아이콘 폰트 크기 24px (BottomNav.tsx text-[24px]).
    const iconSpans = nav.locator('span[aria-hidden="true"]');
    const iconCount = await iconSpans.count();
    expect(iconCount).toBeGreaterThanOrEqual(2);
    const iconFontSizes = await iconSpans.evaluateAll((els) =>
      els.map((el) => parseFloat(window.getComputedStyle(el as HTMLElement).fontSize))
    );
    for (const fs of iconFontSizes) {
      expect.soft(fs, `icon fontSize ≥ 24`).toBeGreaterThanOrEqual(24);
    }

    // (3) 라벨 폰트 크기 13px (text-[13px]).
    // span 두 번째 (icon 다음) 을 고른다 — text 자식이 두 개 있는 구조.
    const labelSpans = nav.locator('button[role="tab"] > span:not([aria-hidden])');
    const labelCount = await labelSpans.count();
    if (labelCount > 0) {
      const labelFontSizes = await labelSpans.evaluateAll((els) =>
        els.map((el) => parseFloat(window.getComputedStyle(el as HTMLElement).fontSize))
      );
      for (const fs of labelFontSizes) {
        expect.soft(fs, `label fontSize ≥ 13`).toBeGreaterThanOrEqual(13);
      }
    }

    // (4) BoundingBox 실제 height — 60px 이상 보장 (paddingBottom env 미지원 시
    // 의도된 minHeight 만 검증).
    const firstTabBox = await tabs.first().boundingBox();
    expect(firstTabBox).not.toBeNull();
    if (firstTabBox) {
      expect.soft(firstTabBox.height, 'first tab boundingBox.height ≥ 60').toBeGreaterThanOrEqual(60);
    }
  });
});
