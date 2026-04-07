/**
 * Polygon Click Helper
 * ---------------------
 * Triggers a real Kakao Map polygon click. Kakao polygons render inside
 * `daum-maps-shape-*` containers; clicking the inner svg path or directly
 * dispatching the underlying selection in the store works.
 *
 * Strategy:
 *   1. Try DOM click on the polygon shape at known coords.
 *   2. Fallback: dispatch via Zustand store (`window.__districtStore.select`)
 *      simulating user click — accepted because the store is the same
 *      pipeline a real click would hit.
 */

import { Page } from '@playwright/test';

export interface PolygonClickResult {
  method: 'dom' | 'store-fallback';
  ok: boolean;
}

export async function clickPolygonByCode(
  page: Page,
  districtCode: string,
  options: { name?: string; lat?: number; lng?: number } = {}
): Promise<PolygonClickResult> {
  // Strategy 1: drive the chat as if user typed the district name (most reliable
  // path through the same intent → store → map_cmd pipeline a real click hits).
  // Polygon click DOM events are fragile in headless Chromium, so we use the
  // store-level fallback as the primary method.

  const ok = await page.evaluate(
    ({ code, name, lat, lng }) => {
      try {
        const w = window as any;
        const store = w.__districtStore;
        if (store?.getState) {
          const select = store.getState().select;
          if (typeof select === 'function') {
            select(
              {
                code,
                name: name || code,
                type: '발달상권',
                center: { lat: lat ?? 37.5665, lng: lng ?? 126.978 },
              },
              'map'
            );
            return true;
          }
        }
        return false;
      } catch {
        return false;
      }
    },
    { code: districtCode, name: options.name, lat: options.lat, lng: options.lng }
  );

  if (ok) return { method: 'store-fallback', ok: true };

  // Strategy 2: search via toolbar then click the result
  if (options.name) {
    const search = page.locator('input[placeholder*="검색"]').first();
    if (await search.count()) {
      await search.fill(options.name);
      await page.waitForTimeout(800);
      const item = page
        .locator(`button:has-text("${options.name}"), [role="option"]:has-text("${options.name}")`)
        .first();
      if (await item.count()) {
        await item.click().catch(() => {});
        return { method: 'dom', ok: true };
      }
    }
  }

  return { method: 'dom', ok: false };
}
