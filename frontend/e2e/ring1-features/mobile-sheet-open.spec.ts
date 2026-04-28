import { test, expect, devices } from '@playwright/test';

// 회귀: iOS Safari 에서 BottomNav "챗" 탭을 눌러 시트를 full 로 올렸을 때
// BottomSheetHandle 의 합성 pointer 이벤트로 onDragEnd 가 발동돼 시트가
// 즉시 peek/hidden 으로 닫히던 버그 (2026-04-24).

test.use({ ...devices['iPhone 12'] });

test('BottomNav 챗 탭 → 시트 full 유지 (iOS 회귀)', async ({ page }) => {
  await page.goto('/app');
  // 모바일 레이아웃 보장
  await expect(page.locator('[data-layout="mobile"]')).toBeVisible();

  const chatTab = page.getByRole('tab', { name: '챗' });
  await chatTab.tap();

  const snap = async () =>
    page.evaluate(() => {
      const w = window as unknown as {
        __chatStore?: { getState: () => { sheetSnap: string } };
      };
      if (w.__chatStore) return w.__chatStore.getState().sheetSnap;
      return (
        (document.querySelector('[role="slider"]') as HTMLElement | null)
          ?.getAttribute('aria-valuetext') ?? null
      );
    });

  // 탭 직후 full
  await expect.poll(snap, { timeout: 2000 }).toBe('full');

  // 220ms 애니메이션 + iOS 합성 이벤트 여유까지 대기 후에도 full 유지
  await page.waitForTimeout(600);
  expect(await snap()).toBe('full');
});

test('핸들 작은 탭(deadzone) 은 시트 스냅을 바꾸지 않는다', async ({ page }) => {
  await page.goto('/app');
  await expect(page.locator('[data-layout="mobile"]')).toBeVisible();

  await page.getByRole('tab', { name: '챗' }).tap();
  await page.waitForTimeout(400);

  const handle = page.getByRole('slider', { name: '시트 높이 조절' });
  await handle.tap();
  await page.waitForTimeout(300);

  const valueText = await handle.getAttribute('aria-valuetext');
  expect(valueText).toBe('full');
});
