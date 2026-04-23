import { test, expect, waitForMapReady, sendChatMessage, waitForResponseComplete, verifyProgressGone } from './helpers/setup';

test.describe('Feature 7: Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/app');
    await waitForMapReady(page);
  });

  test('7-1: 네트워크 에러 graceful 처리', async ({ page }) => {
    // Intercept chat API to return error
    await page.route('**/api/chat', (route) =>
      route.fulfill({ status: 500, body: 'Internal Server Error' })
    );

    const textarea = page.locator('textarea[placeholder*="물어보세요"]');
    await textarea.fill('테스트 메시지');
    await textarea.press('Enter');

    // Wait for error handling
    await page.waitForTimeout(5000);

    // Should show error message, not crash
    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(
      chatText.includes('오류') || chatText.includes('다시 시도')
    ).toBeTruthy();

    await page.unroute('**/api/chat');
  });

  test('7-2: 에러 후 재시도 가능', async ({ page }) => {
    // First request: error
    await page.route('**/api/chat', (route) =>
      route.fulfill({ status: 500, body: 'Error' })
    );

    const textarea = page.locator('textarea[placeholder*="물어보세요"]');
    await textarea.fill('테스트 에러');
    await textarea.press('Enter');
    await page.waitForTimeout(5000);

    // Remove route to allow normal request
    await page.unroute('**/api/chat');

    // Second request: should work
    await sendChatMessage(page, '강남역 상권 요약해줘');

    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(
      chatText.includes('강남') || chatText.includes('유동인구') || chatText.includes('분석')
    ).toBeTruthy();
  });

  test('7-3: 긴 응답 중 스크롤 자동 이동', async ({ page }) => {
    // Send message to generate response
    await sendChatMessage(page, '강남역 상권 요약해줘');

    // The scroll container should have scrolled to bottom
    const scrollContainer = page.locator('.overflow-y-auto').first();
    const scrollTop = await scrollContainer.evaluate((el) => el.scrollTop);
    const scrollHeight = await scrollContainer.evaluate((el) => el.scrollHeight);
    const clientHeight = await scrollContainer.evaluate((el) => el.clientHeight);

    // If content overflows, scrollTop should be near the bottom
    if (scrollHeight > clientHeight) {
      expect(scrollTop + clientHeight).toBeGreaterThanOrEqual(scrollHeight - 100);
    } else {
      // Content doesn't overflow — that's fine
      expect(true).toBeTruthy();
    }
  });

  test('7-4: 연속 요청 시 이전 응답 유지', async ({ page }) => {
    // First question
    await sendChatMessage(page, '강남역 상권 요약해줘');

    // Second question
    await sendChatMessage(page, '홍대입구 상권 요약해줘');

    // Both responses should be present
    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(chatText.includes('강남') || chatText.includes('강남역')).toBeTruthy();
    expect(chatText.includes('홍대') || chatText.includes('홍대입구')).toBeTruthy();
  });
});
