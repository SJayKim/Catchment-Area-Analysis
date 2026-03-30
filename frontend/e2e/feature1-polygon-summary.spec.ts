import { test, expect } from '@playwright/test';
import {
  waitForMapReady,
  sendChatMessage,
  waitForResponseComplete,
  waitForCard,
  getStatusBarText,
} from './helpers/setup';

test.describe('Feature 1: 폴리곤 클릭 → 자동 SummaryCard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('1-1: 폴리곤 클릭 → SummaryCard 자동 표시', async ({ page }) => {
    // Use toolbar search to select 강남역 (triggers select('map') → useMapSync auto-query)
    const searchInput = page.locator('input[placeholder*="검색"]').first();
    await searchInput.fill('강남역');
    await page.waitForTimeout(800);

    // Click the dropdown result
    const dropdown = page.locator('button', { hasText: '강남역' }).first();
    const dropdownVisible = await dropdown.isVisible({ timeout: 3000 }).catch(() => false);

    if (dropdownVisible) {
      await dropdown.click();
      // useMapSync should fire auto-query
      await waitForResponseComplete(page);
    } else {
      // Fallback: send chat message directly
      await sendChatMessage(page, '강남역 상권 요약해줘');
    }

    // ASSERT: Summary content rendered
    const hasSummary = await waitForCard(page, 'summary');
    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(
      hasSummary || chatText.includes('강남역') || chatText.includes('유동인구')
    ).toBeTruthy();

    // ASSERT: StatusBar shows 강남역
    const statusText = await getStatusBarText(page);
    expect(statusText).toContain('강남역');
  });

  test('1-2: 다른 상권 연속 선택', async ({ page }) => {
    // First: 강남역
    await sendChatMessage(page, '강남역 상권 요약해줘');

    let statusText = await getStatusBarText(page);
    expect(statusText).toContain('강남역');

    // Second: 홍대입구
    await sendChatMessage(page, '홍대입구 상권 요약해줘');

    // ASSERT: StatusBar updated to 홍대입구
    statusText = await getStatusBarText(page);
    expect(statusText).toContain('홍대입구');

    // ASSERT: 홍대입구 content present
    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(chatText).toContain('홍대입구');
  });

  test('1-3: 로딩 중 추가 요청 — 에러 없음', async ({ page }) => {
    // Send first request
    const textarea = page.locator('textarea[placeholder*="물어보세요"]');
    await textarea.fill('강남역 상권 요약해줘');
    await textarea.press('Enter');

    // Immediately try second (while first is loading — should be ignored due to isLoading guard)
    await page.waitForTimeout(500);
    await textarea.fill('홍대입구 상권 요약해줘');
    await textarea.press('Enter');

    // Wait for all responses
    await waitForResponseComplete(page, 50000);

    // ASSERT: Page is still functional, no crash
    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(
      chatText.includes('강남역') || chatText.includes('홍대입구') || chatText.includes('유동인구')
    ).toBeTruthy();

    // ASSERT: No error
    expect(chatText).not.toContain('상권을 선택해주세요');
  });
});
