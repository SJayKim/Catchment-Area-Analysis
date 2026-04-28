/**
 * Mock-stack reproduction of "다른 지역 상권 프리뷰 불러오기 작동안한다".
 *
 * Drives chatStore + districtStore directly through the test harness handles
 * (`__chatStore`, `__districtStore`) since the Kakao map polygon click is
 * unreliable in headless chromium. Focus is on the *store-level* outcome:
 *   • setPreview(B) actually fires after setPreview(A) → user message → ...
 *   • PreviewCard B is eventually rendered (testid `district-preview`).
 */

import { test, expect } from '@playwright/test';

const A = { code: 'D3001', name: '강남역', lat: 37.4979, lng: 127.0276 };
const B = { code: 'D3002', name: '홍대입구', lat: 37.5563, lng: 126.9237 };

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

async function getPreviewCode(page: import('@playwright/test').Page): Promise<string | null> {
  return page.evaluate(() => {
    const w = window as unknown as {
      __chatStore?: { getState: () => { preview: { district_code?: string } | null } };
    };
    return w.__chatStore?.getState().preview?.district_code ?? null;
  });
}

async function waitPreview(
  page: import('@playwright/test').Page,
  code: string,
  timeoutMs = 10_000
) {
  await page.waitForFunction(
    (c) => {
      const w = window as unknown as {
        __chatStore?: { getState: () => { preview: { district_code?: string } | null } };
      };
      return w.__chatStore?.getState().preview?.district_code === c;
    },
    code,
    { timeout: timeoutMs }
  );
}

test('preview switches between districts after AI report', async ({ page }) => {
  page.on('pageerror', (err) => console.log('[pageerror]', err.message));
  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      console.log(`[console.${msg.type()}]`, msg.text());
    }
  });

  await page.goto('/app', { waitUntil: 'domcontentloaded' });

  // Wait until the store handle is exposed.
  await page.waitForFunction(
    () => (window as { __chatStore?: unknown }).__chatStore != null,
    { timeout: 15_000 }
  );

  // 1) Select A → preview A.
  await selectDistrict(page, A);
  await waitPreview(page, A.code);
  expect(await getPreviewCode(page)).toBe(A.code);

  // 2) Trigger sendMessage (drives the user-message + sets preview=null).
  await page.evaluate(() => {
    const w = window as unknown as {
      __chatStore?: { getState: () => { sendMessage: (m: string) => Promise<void> } };
    };
    void w.__chatStore?.getState().sendMessage('강남역 상권 자세히 분석해줘');
  });

  // After sendMessage starts, preview is wiped to null.
  await page.waitForFunction(() => {
    const w = window as unknown as {
      __chatStore?: { getState: () => { preview: unknown; isLoading: boolean } };
    };
    const s = w.__chatStore?.getState();
    return s?.preview === null && s?.isLoading === true;
  }, { timeout: 5_000 });

  // 3) Select B *while the chat stream may still be in-flight*.
  await selectDistrict(page, B);

  // 4) Preview must switch to B within reasonable time.
  await waitPreview(page, B.code, 10_000);
  expect(await getPreviewCode(page)).toBe(B.code);

  // 5) Sanity — PreviewCard DOM is rendered.
  await expect(page.getByTestId('district-preview')).toBeVisible({ timeout: 5_000 });
});

test('clicking the same district again after sendMessage re-shows preview', async ({ page }) => {
  page.on('pageerror', (err) => console.log('[pageerror]', err.message));

  await page.goto('/app', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => (window as { __chatStore?: unknown }).__chatStore != null,
    { timeout: 15_000 }
  );

  await selectDistrict(page, A);
  await waitPreview(page, A.code);

  // Drive a chat round.
  await page.evaluate(() => {
    const w = window as unknown as {
      __chatStore?: { getState: () => { sendMessage: (m: string) => Promise<void> } };
    };
    void w.__chatStore?.getState().sendMessage('강남역 분석');
  });
  // Wait for sendMessage to finish.
  await page.waitForFunction(
    () => {
      const w = window as unknown as {
        __chatStore?: { getState: () => { isLoading: boolean } };
      };
      return w.__chatStore?.getState().isLoading === false;
    },
    { timeout: 30_000 }
  );

  // After analysis, preview is null.
  expect(await getPreviewCode(page)).toBeNull();

  // Click the *same* district again — preview must reappear.
  await selectDistrict(page, A);
  await waitPreview(page, A.code, 10_000);
  expect(await getPreviewCode(page)).toBe(A.code);
});
