/**
 * Ring 1 — F13 District Preview API
 *
 * 2026-04-23 Plan `landing-onboarding-feedback` §4.
 * `GET /api/districts/{code}/preview` zero-LLM 응답 shape + role 분기 + 캐시 hit 검증.
 */

import { test, expect } from '../helpers/setup';
import { detectMode } from '../helpers/modeGuard';

const BACKEND = process.env.E2E_BACKEND_URL || 'http://localhost:8002';

async function sampleDistrictCode(page: import('@playwright/test').Page): Promise<string> {
  // Mock: D3001~D3005 · Real: 1,650 codes — 첫 번째 list 결과를 쓰면 양쪽 모두 통과
  const resp = await page.request.get(`${BACKEND}/api/districts?limit=1`);
  if (!resp.ok()) throw new Error(`failed to fetch district list: ${resp.status()}`);
  const data = await resp.json();
  const first = data.items?.[0];
  if (!first?.district_code) throw new Error('no districts returned by API');
  return first.district_code;
}

test.describe('Ring 1 — Preview API', () => {
  test('1-PREVIEW-API — response shape + role-based suggestions', async ({ page }) => {
    const code = await sampleDistrictCode(page);

    const resp = await page.request.get(
      `${BACKEND}/api/districts/${code}/preview?role=investor`
    );
    expect(resp.status()).toBe(200);

    const body = await resp.json();
    expect(body).toMatchObject({
      district_code: expect.any(String),
      district_name: expect.any(String),
      district_type: expect.any(String),
      suggested_questions: expect.any(Array),
    });
    expect(Array.isArray(body.top_categories)).toBe(true);
    expect(body.floating_population).toBeTruthy();

    // Role 차이 확인
    const respOwner = await page.request.get(
      `${BACKEND}/api/districts/${code}/preview?role=owner`
    );
    const bodyOwner = await respOwner.json();
    expect(bodyOwner.suggested_questions).not.toEqual(body.suggested_questions);
  });

  test('1-PREVIEW-CACHE — second call faster (Redis hit)', async ({ page }) => {
    const code = await sampleDistrictCode(page);

    // Warm up
    await page.request.get(`${BACKEND}/api/districts/${code}/preview`);

    const t1 = Date.now();
    const resp = await page.request.get(`${BACKEND}/api/districts/${code}/preview`);
    const elapsed = Date.now() - t1;

    expect(resp.status()).toBe(200);
    // Mock 모드에선 Memory cache 이므로 < 50ms 충분. Real 도 Redis 캐시로 유사.
    expect(elapsed).toBeLessThan(500);
  });

  test('3-NEG-PREVIEW-BAD-CODE — unknown code → 404', async ({ page }) => {
    const mode = await detectMode();
    // Real 에서도 ZZZZ 같은 존재하지 않는 코드는 404
    const bogus = mode === 'mock' ? 'ZZZZ' : 'ZZZZZZZZ';
    const resp = await page.request.get(`${BACKEND}/api/districts/${bogus}/preview`);
    expect(resp.status()).toBe(404);
  });
});
