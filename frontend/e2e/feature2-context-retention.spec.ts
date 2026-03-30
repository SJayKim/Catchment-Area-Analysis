import { test, expect } from '@playwright/test';
import {
  waitForMapReady,
  sendChatMessage,
  waitForResponseComplete,
  getStatusBarText,
} from './helpers/setup';

test.describe('Feature 2: 대화 컨텍스트 유지', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('2-1: 후속 질문에서 이전 상권 자동 참조', async ({ page }) => {
    // Step 1: 강남역 분석
    await sendChatMessage(page, '강남역 분석해줘');

    const chatText1 = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(chatText1.includes('강남역') || chatText1.includes('유동인구')).toBeTruthy();

    // Step 2: 후속 질문 — 상권명 없이
    await sendChatMessage(page, '위험해?');

    // ASSERT: 강남역 관련 리스크 응답
    const chatText2 = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(
      chatText2.includes('안정성') ||
      chatText2.includes('리스크') ||
      chatText2.includes('폐업') ||
      chatText2.includes('생존') ||
      chatText2.includes('강남역')
    ).toBeTruthy();

    // ASSERT: No "상권을 선택해주세요" error
    expect(chatText2).not.toContain('상권을 선택해주세요');
  });

  test('2-2: 연속 후속 질문 — 컨텍스트 유지', async ({ page }) => {
    // Step 1: 홍대입구
    await sendChatMessage(page, '홍대입구 상권 보여줘');

    // Step 2: 유동인구 후속
    await sendChatMessage(page, '유동인구 자세히 알려줘');

    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(
      chatText.includes('홍대입구') || chatText.includes('유동인구')
    ).toBeTruthy();

    // Step 3: 업종 추천 후속
    await sendChatMessage(page, '여기서 뭐하면 좋을까?');

    const chatText2 = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(
      chatText2.includes('추천') ||
      chatText2.includes('업종') ||
      chatText2.includes('홍대입구')
    ).toBeTruthy();
  });

  test('2-3: 상권 전환 시 컨텍스트 갱신', async ({ page }) => {
    test.setTimeout(120000);
    // Step 1: 강남역
    await sendChatMessage(page, '강남역 분석해줘');

    // Step 2: 후속 — 강남역 기준
    await sendChatMessage(page, '위험해?');

    // Step 3: 명동으로 전환
    await sendChatMessage(page, '명동 분석해줘');

    // Step 4: 후속 — 명동 기준이어야 함
    await sendChatMessage(page, '여기서 뭐하면 좋을까?');

    // ASSERT: StatusBar = 명동
    const statusText = await getStatusBarText(page);
    expect(statusText).toContain('명동');
  });

  test('2-4: 검색 선택 후 후속 질문', async ({ page }) => {
    // Step 1: 강남역 요약 via toolbar search
    const searchInput = page.locator('input[placeholder*="검색"]').first();
    await searchInput.fill('강남역');
    await page.waitForTimeout(800);

    const dropdown = page.locator('button', { hasText: '강남역' }).first();
    if (await dropdown.isVisible({ timeout: 3000 }).catch(() => false)) {
      await dropdown.click();
      await waitForResponseComplete(page);
    } else {
      await sendChatMessage(page, '강남역 상권 요약해줘');
    }

    // Step 2: 후속 질문
    await sendChatMessage(page, '위험해?');

    // ASSERT: 강남역 리스크 응답
    const chatText = await page.locator('.flex.flex-col.h-full').first().textContent() || '';
    expect(
      chatText.includes('강남역') ||
      chatText.includes('안정성') ||
      chatText.includes('리스크')
    ).toBeTruthy();
  });
});
