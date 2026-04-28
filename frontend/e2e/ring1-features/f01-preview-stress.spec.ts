/**
 * Stress / edge-case spec — exercises rare but observable user paths.
 */

import { test, expect } from '@playwright/test';

const A = { code: 'D3001', name: '강남역', lat: 37.4979, lng: 127.0276 };
const B = { code: 'D3002', name: '홍대입구', lat: 37.5563, lng: 126.9237 };

async function selectDistrict(page: import('@playwright/test').Page, d: typeof A, source: 'map' | 'chat' = 'map') {
  await page.evaluate(({ code, name, lat, lng, source }) => {
    const w = window as unknown as {
      __districtStore?: { getState: () => { select: (d: unknown, src: string) => void } };
    };
    w.__districtStore?.getState().select(
      { code, name, type: '발달상권', center: { lat, lng } },
      source
    );
  }, { ...d, source });
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
    };
  });
}

test('chat-origin select then same district map click — preview reappears', async ({ page }) => {
  await page.goto('/app', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => (window as { __chatStore?: unknown }).__chatStore != null,
    { timeout: 15_000 }
  );

  // Map click A — preview A.
  await selectDistrict(page, A, 'map');
  await page.waitForFunction(
    () => (window as { __chatStore?: { getState: () => { preview: { district_code?: string } | null } } })
      .__chatStore?.getState().preview?.district_code === 'D3001',
    { timeout: 10_000 }
  );

  // Simulate the chat sending a map_cmd back (chat-origin select for the same A).
  await selectDistrict(page, A, 'chat');
  // Chat-origin selects do NOT trigger setPreview, so preview stays.
  expect((await getState(page))?.previewCode).toBe('D3001');

  // Now: user clears preview by sending an analysis ...
  await page.evaluate(() => {
    const w = window as unknown as {
      __chatStore?: { getState: () => { sendMessage: (m: string) => Promise<void> } };
    };
    void w.__chatStore?.getState().sendMessage('분석');
  });
  await page.waitForFunction(
    () => (window as { __chatStore?: { getState: () => { isLoading: boolean } } })
      .__chatStore?.getState().isLoading === false,
    { timeout: 60_000 }
  );

  // Preview should be null after analysis.
  expect((await getState(page))?.previewCode).toBeNull();

  // Click the SAME district A again with map source — must re-preview.
  await selectDistrict(page, A, 'map');
  await page.waitForFunction(
    () => (window as { __chatStore?: { getState: () => { preview: { district_code?: string } | null } } })
      .__chatStore?.getState().preview?.district_code === 'D3001',
    { timeout: 10_000 }
  );
  console.log('[final]', await getState(page));
});

test('preview watchdog — error UI appears if backend hangs (forced via abort)', async ({ page }) => {
  await page.goto('/app', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => (window as { __chatStore?: unknown }).__chatStore != null,
    { timeout: 15_000 }
  );

  // Intercept the preview fetch and never respond — simulates backend hang.
  await page.route('**/api/districts/D3002/preview**', async (route) => {
    // Never fulfill — let the watchdog fire.
    await new Promise(() => {});
    await route.continue();
  });

  // Click B (which we've intercepted).
  await selectDistrict(page, B, 'map');

  // Within 12s the watchdog should kick in and previewError should be set.
  await page.waitForFunction(
    () => (window as { __chatStore?: { getState: () => { previewError: string | null } } })
      .__chatStore?.getState().previewError != null,
    { timeout: 15_000 }
  );

  await expect(page.getByTestId('district-preview-error')).toBeVisible({ timeout: 5_000 });
  await expect(page.getByTestId('district-preview-retry')).toBeVisible();
  console.log('[watchdog state]', await getState(page));
});

test('Rapid 5-click thrash settles cleanly on the last click', async ({ page }) => {
  await page.goto('/app', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => (window as { __chatStore?: unknown }).__chatStore != null,
    { timeout: 15_000 }
  );

  const seq = [
    { ...A },
    { ...B },
    { ...A },
    { ...B },
    { code: 'D3003', name: '건대입구', lat: 37.5404, lng: 127.069 },
  ];
  for (const d of seq) {
    await selectDistrict(page, d as typeof A, 'map');
    await page.waitForTimeout(50);
  }

  // Should land on D3003.
  await page.waitForFunction(
    () => (window as { __chatStore?: { getState: () => { preview: { district_code?: string } | null } } })
      .__chatStore?.getState().preview?.district_code === 'D3003',
    { timeout: 12_000 }
  );
  const final = await getState(page);
  expect(final?.previewCode).toBe('D3003');
  expect(final?.previewLoading).toBe(false);
});
