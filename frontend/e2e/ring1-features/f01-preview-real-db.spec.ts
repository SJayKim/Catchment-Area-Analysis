/**
 * Real-DB regression of the preview-stuck bug — driven against the rebuilt
 * frontend container (port 3010) that *does* contain the race-condition fix.
 * Backend is real (USE_MOCK=false), so we use real district codes.
 */

import { test, expect } from '@playwright/test';

const A = { code: '3120189', name: '강남역', lat: 37.4979, lng: 127.0276 };
const B = { code: '3110221', name: '의릉', lat: 37.6039, lng: 127.0611 };
const C = { code: '3120240', name: '개롱역', lat: 37.4960, lng: 127.1346 };

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
      currentRequestId: s.currentRequestId,
    };
  });
}

test('A → B → A preview switching against real DB (rebuilt container)', async ({ page }) => {
  await page.goto('/app', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => (window as { __chatStore?: unknown }).__chatStore != null,
    { timeout: 15_000 }
  );

  await selectDistrict(page, A);
  await page.waitForFunction(
    (c) => (window as { __chatStore?: { getState: () => { preview: { district_code?: string } | null } } })
      .__chatStore?.getState().preview?.district_code === c,
    A.code,
    { timeout: 10_000 }
  );
  console.log('[A]', await getState(page));

  await selectDistrict(page, B);
  await page.waitForFunction(
    (c) => (window as { __chatStore?: { getState: () => { preview: { district_code?: string } | null } } })
      .__chatStore?.getState().preview?.district_code === c,
    B.code,
    { timeout: 10_000 }
  );
  console.log('[B]', await getState(page));

  await selectDistrict(page, A);
  await page.waitForFunction(
    (c) => (window as { __chatStore?: { getState: () => { preview: { district_code?: string } | null } } })
      .__chatStore?.getState().preview?.district_code === c,
    A.code,
    { timeout: 10_000 }
  );
  console.log('[A again]', await getState(page));

  expect((await getState(page))?.previewCode).toBe(A.code);
});

test('A → AI 분석 → B preview shows up', async ({ page }) => {
  await page.goto('/app', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => (window as { __chatStore?: unknown }).__chatStore != null,
    { timeout: 15_000 }
  );

  await selectDistrict(page, A);
  await expect(page.getByTestId('district-preview')).toBeVisible({ timeout: 10_000 });
  console.log('[A preview]', await getState(page));

  // Click "AI 분석 보기" — kicks off real LLM stream (which is slow). We
  // don't wait for it; we just want preview B to appear during/after.
  await page.getByTestId('preview-deep-analysis').click();
  await page.waitForFunction(
    () => (window as { __chatStore?: { getState: () => { isLoading: boolean } } })
      .__chatStore?.getState().isLoading === true,
    { timeout: 5_000 }
  );

  // Now click B *while the chat stream is still running*.
  await selectDistrict(page, B);
  await page.waitForFunction(
    (c) => (window as { __chatStore?: { getState: () => { preview: { district_code?: string } | null } } })
      .__chatStore?.getState().preview?.district_code === c,
    B.code,
    { timeout: 12_000 }
  );
  await expect(page.getByTestId('district-preview')).toBeVisible({ timeout: 5_000 });
  console.log('[B preview during in-flight chat]', await getState(page));
});

test('Three rapid clicks A → B → C → preview ends on C', async ({ page }) => {
  await page.goto('/app', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => (window as { __chatStore?: unknown }).__chatStore != null,
    { timeout: 15_000 }
  );

  await selectDistrict(page, A);
  await page.waitForTimeout(80);
  await selectDistrict(page, B);
  await page.waitForTimeout(80);
  await selectDistrict(page, C);

  await page.waitForFunction(
    (c) => (window as { __chatStore?: { getState: () => { preview: { district_code?: string } | null } } })
      .__chatStore?.getState().preview?.district_code === c,
    C.code,
    { timeout: 12_000 }
  );
  expect((await getState(page))?.previewCode).toBe(C.code);
});
