/**
 * Wait helpers for SSE-driven UI states.
 *
 * Reduces reliance on `waitForTimeout` heuristics by polling on actual
 * UI signals (textarea state, card content, status bar, etc).
 */

import { Page } from '@playwright/test';

export async function waitForChatIdle(page: Page, timeoutMs = 45000) {
  const textarea = page.locator('textarea[placeholder*="물어보세요"]');
  const deadline = Date.now() + timeoutMs;
  let stableSince = 0;
  while (Date.now() < deadline) {
    const disabled = await textarea.isDisabled().catch(() => true);
    const thinking = await page.locator('.animate-pulse').first().isVisible().catch(() => false);
    if (!disabled && !thinking) {
      if (stableSince === 0) stableSince = Date.now();
      if (Date.now() - stableSince > 600) return true;
    } else {
      stableSince = 0;
    }
    await page.waitForTimeout(150);
  }
  return false;
}

export async function waitForCardText(
  page: Page,
  patterns: string[],
  timeoutMs = 30000
): Promise<{ found: boolean; matched?: string }> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const text = (await page.locator('body').innerText().catch(() => '')) || '';
    for (const pat of patterns) {
      if (text.includes(pat)) return { found: true, matched: pat };
    }
    await page.waitForTimeout(300);
  }
  return { found: false };
}

export async function waitForStatusBarContains(page: Page, needle: string, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const sb = await page.locator('.h-8').first().textContent().catch(() => '');
    if (sb && sb.includes(needle)) return true;
    await page.waitForTimeout(200);
  }
  return false;
}
