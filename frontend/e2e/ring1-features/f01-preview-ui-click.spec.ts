/**
 * UI-driven reproduction: actual PreviewCard / ChatInput clicks (not direct
 * store calls) to mirror what the user is doing in the browser.
 */

import { test, expect } from '@playwright/test';

const A = { code: 'D3001', name: '강남역', lat: 37.4979, lng: 127.0276 };
const B = { code: 'D3002', name: '홍대입구', lat: 37.5563, lng: 126.9237 };
const C = { code: 'D3003', name: '건대입구', lat: 37.5404, lng: 127.069 };

async function selectDistrict(page: import('@playwright/test').Page, d: typeof A) {
  await page.evaluate(({ code, name, lat, lng }) => {
    const w = window as unknown as {
      __districtStore?: { getState: () => { select: (d: unknown, src: string) => void } };
    };
    w.__districtStore?.getState().select(
      { code, name, type: '발달상권', center: { lat, lng } },
      'map'
    );
  }, d);
}

async function getState(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const w = window as unknown as {
      __chatStore?: { getState: () => Record<string, unknown> };
    };
    const s = w.__chatStore?.getState();
    if (!s) return null;
    return {
      previewCode: (s.preview as { district_code?: string } | null)?.district_code ?? null,
      previewLoading: s.previewLoading,
      previewError: s.previewError,
      isLoading: s.isLoading,
      currentRequestId: s.currentRequestId,
      messageCount: (s.messages as unknown[] | undefined)?.length ?? 0,
    };
  });
}

test('UI flow: A→AI→B→AI works end-to-end', async ({ page }) => {
  page.on('pageerror', (err) => console.log('[pageerror]', err.message));

  await page.goto('/app', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => (window as { __chatStore?: unknown }).__chatStore != null,
    { timeout: 15_000 }
  );

  // 1) Select A.
  await selectDistrict(page, A);
  await expect(page.getByTestId('district-preview')).toBeVisible({ timeout: 10_000 });
  console.log('[after A select]', await getState(page));

  // 2) Click "AI 분석 보기" on A's preview.
  await page.getByTestId('preview-deep-analysis').click();
  // Should kick off a stream — isLoading true.
  await page.waitForFunction(
    () => (window as { __chatStore?: { getState: () => { isLoading: boolean } } })
      .__chatStore?.getState().isLoading === true,
    { timeout: 5_000 }
  );
  console.log('[after A AI click]', await getState(page));

  // 3) Select B *while* the chat stream is in-flight.
  await selectDistrict(page, B);

  // Preview must switch to B even though chat is still streaming.
  await page.waitForFunction(() => {
    const s = (window as { __chatStore?: { getState: () => { preview: { district_code?: string } | null } } })
      .__chatStore?.getState();
    return s?.preview?.district_code === 'D3002';
  }, { timeout: 10_000 });
  console.log('[after B select]', await getState(page));
  await expect(page.getByTestId('district-preview')).toBeVisible({ timeout: 5_000 });

  // 4) Click "AI 분석 보기" on B's preview *while A might still be settling*.
  await page.getByTestId('preview-deep-analysis').click();
  // Should pre-empt and start a new request — currentRequestId increments.
  await page.waitForFunction(() => {
    const s = (window as { __chatStore?: { getState: () => { currentRequestId: number; isLoading: boolean } } })
      .__chatStore?.getState();
    return s != null && s.isLoading === true && s.currentRequestId >= 2;
  }, { timeout: 5_000 });
  console.log('[after B AI click]', await getState(page));

  // Wait for B's stream to end.
  await page.waitForFunction(() => {
    const s = (window as { __chatStore?: { getState: () => { isLoading: boolean } } })
      .__chatStore?.getState();
    return s?.isLoading === false;
  }, { timeout: 60_000 });

  const final = await getState(page);
  console.log('[final]', final);
  expect(final?.isLoading).toBe(false);
  expect((final?.messageCount as number) ?? 0).toBeGreaterThanOrEqual(2);
});

test('Three rapid clicks A → B → C show C preview', async ({ page }) => {
  page.on('pageerror', (err) => console.log('[pageerror]', err.message));

  await page.goto('/app', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => (window as { __chatStore?: unknown }).__chatStore != null,
    { timeout: 15_000 }
  );

  // Three rapid clicks within ~100ms each.
  await selectDistrict(page, A);
  await page.waitForTimeout(80);
  await selectDistrict(page, B);
  await page.waitForTimeout(80);
  await selectDistrict(page, C);

  // Preview must end on C.
  await page.waitForFunction(() => {
    const s = (window as { __chatStore?: { getState: () => { preview: { district_code?: string } | null } } })
      .__chatStore?.getState();
    return s?.preview?.district_code === 'D3003';
  }, { timeout: 12_000 });
  console.log('[final state]', await getState(page));
});

test('Preview reappears when same district is clicked after AI analysis', async ({ page }) => {
  page.on('pageerror', (err) => console.log('[pageerror]', err.message));

  await page.goto('/app', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => (window as { __chatStore?: unknown }).__chatStore != null,
    { timeout: 15_000 }
  );

  await selectDistrict(page, A);
  await expect(page.getByTestId('district-preview')).toBeVisible({ timeout: 10_000 });
  await page.getByTestId('preview-deep-analysis').click();

  // Wait for stream to fully end.
  await page.waitForFunction(() => {
    const s = (window as { __chatStore?: { getState: () => { isLoading: boolean } } })
      .__chatStore?.getState();
    return s?.isLoading === false;
  }, { timeout: 60_000 });

  // Preview is null after sendMessage.
  const mid = await getState(page);
  expect(mid?.previewCode).toBeNull();

  // Click the SAME district A again — preview must come back.
  await selectDistrict(page, A);
  await page.waitForFunction(() => {
    const s = (window as { __chatStore?: { getState: () => { preview: { district_code?: string } | null } } })
      .__chatStore?.getState();
    return s?.preview?.district_code === 'D3001';
  }, { timeout: 10_000 });
  console.log('[final]', await getState(page));
});

test('ChatInput while in-flight — does not freeze, second message goes through', async ({ page }) => {
  page.on('pageerror', (err) => console.log('[pageerror]', err.message));

  await page.goto('/app', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => (window as { __chatStore?: unknown }).__chatStore != null,
    { timeout: 15_000 }
  );

  await selectDistrict(page, A);
  await expect(page.getByTestId('district-preview')).toBeVisible({ timeout: 10_000 });

  const textarea = page.locator('textarea[placeholder*="물어보세요"]');
  await textarea.fill('첫 번째 질문');
  await textarea.press('Enter');

  await page.waitForFunction(
    () => (window as { __chatStore?: { getState: () => { isLoading: boolean } } })
      .__chatStore?.getState().isLoading === true,
    { timeout: 5_000 }
  );

  // While in-flight, send a 2nd message.
  await textarea.fill('두 번째 질문');
  await textarea.press('Enter');

  // requestId should be at least 2.
  await page.waitForFunction(
    () => (window as { __chatStore?: { getState: () => { currentRequestId: number } } })
      .__chatStore?.getState().currentRequestId >= 2,
    { timeout: 5_000 }
  );

  // Wait for the 2nd stream to settle.
  await page.waitForFunction(
    () => (window as { __chatStore?: { getState: () => { isLoading: boolean } } })
      .__chatStore?.getState().isLoading === false,
    { timeout: 60_000 }
  );
});
