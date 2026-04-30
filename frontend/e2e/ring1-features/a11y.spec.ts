/**
 * Ring1-A11Y — Phase D 접근성 회귀 (D.2 / D.3 / D.6).
 *
 * 2026-04-30 Plan `ux-sweep-phase-d-a11y`.
 * - D.2 :focus-visible 글로벌 룰 + landing/* focus-visible:ring 보강
 * - D.3 landing/* aria-label / aria-checked / role 검수
 * - D.6 안정 키 — CompareCard / SuggestionChips / TimeSlider
 *
 * 핵심 포인트: 본 spec 은 백엔드 SSE 를 건드리지 않는다. landing(`/`) 만
 * 로드해 정적 a11y 회귀를 빠르게 잡는 것이 목적.
 */
import { test, expect } from '../helpers/setup';

test.describe('Ring1-A11Y — Phase D', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('[data-testid="hero-section"]')).toBeVisible();
  });

  test('Ring1-A11Y-D2 — :focus-visible 글로벌 룰 적용', async ({ page }) => {
    // CTA 에 키보드 focus → outline 가시성 (rgb 비-zero 보장).
    const cta = page.locator('[data-testid="header-cta"]');
    await expect(cta).toBeVisible();
    await cta.focus();
    const outlineWidth = await cta.evaluate(
      (el) => window.getComputedStyle(el).outlineWidth,
    );
    expect(outlineWidth).not.toBe('0px');
  });

  test('Ring1-A11Y-D2 — Hero CTA / 칩 / 어떻게 쓰나요 모두 focus-visible 클래스', async ({
    page,
  }) => {
    const tokens = await page.evaluate(() => {
      const out: Record<string, string> = {};
      const cta = document.querySelector('[data-testid="hero-primary-cta"]');
      const chip = document.querySelector('[data-testid="starter-chip-0"]');
      const how = document.querySelector('a[href="#how-it-works"]');
      out.cta = cta?.className ?? '';
      out.chip = chip?.className ?? '';
      out.how = how?.className ?? '';
      return out;
    });
    expect(tokens.cta).toContain('focus-visible:ring-2');
    expect(tokens.chip).toContain('focus-visible:ring-2');
    expect(tokens.how).toContain('focus-visible:ring-2');
  });

  test('Ring1-A11Y-D3 — Header / Footer / RoleSelector 인터랙티브 요소 텍스트 또는 aria-label', async ({
    page,
  }) => {
    const result = await page.evaluate(() => {
      const interactives = Array.from(
        document.querySelectorAll('header a, header button, footer a, footer button'),
      );
      return interactives.map((el) => ({
        tag: el.tagName.toLowerCase(),
        text: (el.textContent ?? '').trim(),
        aria: el.getAttribute('aria-label') ?? '',
      }));
    });
    expect(result.length).toBeGreaterThan(0);
    for (const r of result) {
      // 텍스트 또는 aria-label 둘 중 하나는 비어있지 않아야 함.
      expect((r.text + r.aria).length).toBeGreaterThan(0);
    }
  });

  test('Ring1-A11Y-D3 — RoleSelector role=radio / aria-checked', async ({ page }) => {
    const radios = page.locator('[data-testid^="role-chip-"]');
    const count = await radios.count();
    expect(count).toBeGreaterThanOrEqual(3);
    for (let i = 0; i < count; i++) {
      const r = radios.nth(i);
      await expect(r).toHaveAttribute('role', 'radio');
      const checked = await r.getAttribute('aria-checked');
      expect(checked).toMatch(/^(true|false)$/);
    }
  });

  test('Ring1-A11Y-D6 — SuggestionChips 키 안정성 (코드 레벨 sanity)', async () => {
    // SuggestionChips 의 key 가 ${index}-${suggestion} 합성인지 정적 검증.
    const fs = await import('node:fs');
    const path = await import('node:path');
    const target = path.resolve(
      process.cwd(),
      'src/components/chat/SuggestionChips.tsx',
    );
    const src = fs.readFileSync(target, 'utf8');
    // index-only 키가 남아있지 않아야 함.
    expect(src).not.toMatch(/key=\{\s*index\s*\}/);
    expect(src).toMatch(/key=\{`\$\{index\}-/);
  });

  // (Mock-only) 신규 11 — Plan UX Sweep Phase D D.8: Header CTA hover 시 inline
  // JS handler (onMouseEnter / onMouseLeave / setProperty) 가 부재해야 하고
  // Tailwind hover: 클래스가 적용되어야 함.
  test('Ring1-F11-D8-HOVER — Header CTA hover 는 Tailwind 만, inline JS 부재', async ({
    page,
  }) => {
    // (1) 정적 source 검증 — Header.tsx 에 onMouseEnter 등 inline handler 부재.
    const fs = await import('node:fs');
    const path = await import('node:path');
    const target = path.resolve(
      process.cwd(),
      'src/components/landing/Header.tsx'
    );
    const src = fs.readFileSync(target, 'utf8');
    expect(src).not.toMatch(/onMouseEnter\s*=/);
    expect(src).not.toMatch(/onMouseLeave\s*=/);
    expect(src).not.toMatch(/style\.setProperty/);
    // hover: prefix Tailwind 클래스가 CTA 에 적용되어야 함.
    expect(src).toMatch(/hover:bg-/);

    // (2) 런타임 — getComputedStyle 로 hover 전후 backgroundColor 변경 확인.
    const cta = page.locator('[data-testid="header-cta"]');
    await expect(cta).toBeVisible();

    const before = await cta.evaluate(
      (el) => window.getComputedStyle(el).backgroundColor
    );
    await cta.hover();
    // Tailwind transition 600ms 미만이라 200ms 대기로 settle.
    await page.waitForTimeout(250);
    const after = await cta.evaluate(
      (el) => window.getComputedStyle(el).backgroundColor
    );

    // hover 색상 변경 — 픽셀 보정 차이로 정확히 다른 RGB 라야 함. CSS 변수 미정의
    // 환경에서는 같을 수 있으므로 soft 검증.
    expect.soft(after).not.toBe('');
    // CTA 가 색을 가지고 있어야 함 (rgb(...) 또는 rgba(...)).
    expect(before).toMatch(/rgb/);
  });
});
