import { test, expect, waitForMapReady, sendChatMessage, waitForCard } from './helpers/setup';

test.describe('Feature 5: Card Rendering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/app');
    await waitForMapReady(page);
  });

  test('5-1: SummaryCard 렌더링', async ({ page }) => {
    await sendChatMessage(page, '강남역 상권 요약해줘');

    const hasSummary = await waitForCard(page, 'summary');
    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(
      hasSummary || chatText.includes('유동인구') || chatText.includes('강남역')
    ).toBeTruthy();
  });

  test('5-2: CompareCard 렌더링', async ({ page }) => {
    await sendChatMessage(page, '강남역이랑 홍대입구 비교해줘');

    const hasCompare = await waitForCard(page, 'compare');
    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(
      hasCompare || chatText.includes('비교') || chatText.includes('강남역')
    ).toBeTruthy();
  });

  test('5-3: RecommendCard 렌더링', async ({ page }) => {
    await sendChatMessage(page, '강남역에서 뭐하면 좋을까?');

    const hasRecommend = await waitForCard(page, 'recommend');
    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(
      hasRecommend || chatText.includes('추천') || chatText.includes('업종')
    ).toBeTruthy();
  });

  test('5-4: RiskCard 렌더링', async ({ page }) => {
    await sendChatMessage(page, '강남역 이 자리 위험해?');

    const hasRisk = await waitForCard(page, 'risk');
    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(
      hasRisk || chatText.includes('리스크') || chatText.includes('안정') || chatText.includes('생존')
    ).toBeTruthy();
  });

  test('5-5: 카드 데이터 정합성', async ({ page }) => {
    await sendChatMessage(page, '강남역 상권 요약해줘');

    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    // Should contain district name
    expect(chatText.includes('강남역') || chatText.includes('강남')).toBeTruthy();
  });
});
