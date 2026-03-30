import { Page, expect } from '@playwright/test';

/** Known mock district centers (from mock_data.py) */
export const DISTRICTS = {
  강남역: { code: 'DISTRICT_001', lat: 37.4979, lng: 127.0276 },
  홍대입구: { code: 'DISTRICT_002', lat: 37.5563, lng: 126.9237 },
  건대입구: { code: 'DISTRICT_003', lat: 37.5404, lng: 127.069 },
  명동: { code: 'DISTRICT_004', lat: 37.5636, lng: 126.986 },
  서울역: { code: 'DISTRICT_005', lat: 37.5547, lng: 126.9706 },
} as const;

/**
 * Wait for the page to be ready (map + polygons loaded).
 */
export async function waitForMapReady(page: Page) {
  // Wait for polygon API response (indicates map loaded and requested data)
  await page.waitForResponse(
    (resp) => resp.url().includes('/api/map-data/polygons') && resp.status() === 200,
    { timeout: 20000 }
  ).catch(() => {
    // polygons might already be loaded or map might not load in headless
  });

  // Give time for polygons to render
  await page.waitForTimeout(2000);
}

/**
 * Send a chat message via the textarea and wait for response.
 */
export async function sendChatMessage(page: Page, text: string) {
  const textarea = page.locator('textarea[placeholder*="물어보세요"]');
  await textarea.fill(text);
  await textarea.press('Enter');

  // Wait for response to complete
  await waitForResponseComplete(page);
}

/**
 * Wait for the AI response to complete (SSE stream done).
 * Checks both the thinking indicator AND textarea disabled state
 * to avoid false-positive "complete" detection.
 */
export async function waitForResponseComplete(page: Page, timeout = 45000) {
  // Wait for SSE stream to start
  await page.waitForTimeout(1000);

  const textarea = page.locator('textarea[placeholder*="물어보세요"]');
  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    const isDisabled = await textarea.isDisabled().catch(() => true);
    const thinkingVisible = await page.locator('.animate-pulse').first().isVisible().catch(() => false);

    // Only consider complete when textarea is enabled AND no thinking indicator
    if (!isDisabled && !thinkingVisible) {
      // Brief settle time, then re-verify
      await page.waitForTimeout(500);
      const stillDisabled = await textarea.isDisabled().catch(() => true);
      const stillThinking = await page.locator('.animate-pulse').first().isVisible().catch(() => false);
      if (!stillDisabled && !stillThinking) break;
    }

    await page.waitForTimeout(500);
  }

  // Extra wait for card rendering
  await page.waitForTimeout(1000);
}

/**
 * Wait for a specific card type to appear in the chat by looking for content patterns.
 */
export async function waitForCard(page: Page, cardType: string, timeout = 30000) {
  const contentPatterns: Record<string, string[]> = {
    summary: ['유동인구', '일평균', 'Top'],
    compare: ['비교', '유동인구', '판정'],
    recommend: ['추천', '점수', '업종'],
    risk: ['안정성', '생존', '리스크'],
  };

  const patterns = contentPatterns[cardType] || [];
  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    for (const pattern of patterns) {
      if (chatText.includes(pattern)) return true;
    }
    await page.waitForTimeout(500);
  }
  return false;
}

/**
 * Get the text shown in the StatusBar.
 * StatusBar is the bottom bar with "데이터 기준:" and "선택: {name}"
 */
export async function getStatusBarText(page: Page): Promise<string> {
  // StatusBar: div.h-8.bg-gray-50 at the bottom
  const statusBar = page.locator('.h-8.bg-gray-50').first();
  const text = await statusBar.textContent({ timeout: 5000 }).catch(() => '');
  return text || '';
}

/**
 * Check that the chat area contains specific text.
 */
export async function chatContainsText(page: Page, text: string): Promise<boolean> {
  const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
  return chatText.includes(text);
}

/**
 * Count user messages (blue bubbles with bg-primary-500).
 */
export async function countUserMessages(page: Page): Promise<number> {
  return await page.locator('.bg-primary-500.text-white').count();
}

/**
 * Wait for a progress step with specific label text to appear.
 */
export async function waitForProgressStep(page: Page, labelText: string, timeout = 15000) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    const chatArea = page.locator('.flex.flex-col.h-full').first();
    const text = await chatArea.textContent().catch(() => '');
    if (text?.includes(labelText)) return true;
    await page.waitForTimeout(300);
  }
  return false;
}

/**
 * Verify progress indicator is no longer visible in DOM.
 */
export async function verifyProgressGone(page: Page, timeout = 15000) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    // Check for in_progress emoji (🟡)
    const chatArea = page.locator('.flex.flex-col.h-full').first();
    const text = await chatArea.textContent().catch(() => '');
    if (!text?.includes('\uD83D\uDFE1')) return true;
    await page.waitForTimeout(300);
  }
  return false;
}
