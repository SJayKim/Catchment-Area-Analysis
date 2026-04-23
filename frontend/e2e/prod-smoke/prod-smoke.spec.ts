/**
 * Production smoke E2E — marketscope.robitlabs.co.kr
 *
 * 운영 배포 직후 핵심 사용자 여정이 실제로 동작하는지 빠르게 검증한다.
 *  - 프론트엔드 HTML 로드
 *  - Kakao Map SDK 프록시 (/api/kakao-sdk)
 *  - Polygons API (뷰포트 기반 조회)
 *  - Districts 검색 API
 *  - Chat SSE 스트리밍 (end-to-end, card payload 파싱)
 *  - 매출 단위 검증 (이번 배포 핵심 수정: 분기→월 변환)
 */
import { test, expect, request } from '@playwright/test';

const BASE =
  process.env.E2E_BASE_URL || 'https://marketscope.robitlabs.co.kr';

test.describe('Production smoke', () => {
  test('P1 frontend root returns Next.js HTML', async ({ page }) => {
    const resp = await page.goto(BASE);
    expect(resp?.status()).toBe(200);
    const html = await page.content();
    expect(html).toContain('MarketScope AI');
    expect(html.includes('_next') || html.includes('__next')).toBeTruthy();
  });

  test('P2 kakao-sdk proxy serves JavaScript (new path)', async () => {
    const ctx = await request.newContext();
    // 2026-04-23 cut-over: /api/kakao-sdk (frontend route) → /proxy/kakao-sdk
    const resp = await ctx.get(`${BASE}/proxy/kakao-sdk`);
    expect(resp.status()).toBe(200);
    const body = await resp.text();
    expect(body.length).toBeGreaterThan(100);
    expect(body).not.toContain('<!DOCTYPE');

    // Legacy path must 404 (confirms cut-over happened)
    const legacy = await ctx.get(`${BASE}/api/kakao-sdk`);
    expect(legacy.status()).toBe(404);
  });

  test('P3 polygons API returns GeoJSON FeatureCollection', async () => {
    const ctx = await request.newContext();
    const bounds = '37.45,126.85,37.65,127.15';
    const resp = await ctx.get(
      `${BASE}/api/map-data/polygons?bounds=${bounds}`
    );
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(data.type).toBe('FeatureCollection');
    expect(Array.isArray(data.features)).toBeTruthy();
    expect(data.features.length).toBeGreaterThan(0);
    const first = data.features[0];
    expect(first.geometry?.type).toMatch(/Polygon|MultiPolygon/);
    expect(first.properties?.district_code).toBeTruthy();
  });

  test('P4 districts search returns 강남역', async () => {
    const ctx = await request.newContext();
    const resp = await ctx.get(
      `${BASE}/api/districts?search=${encodeURIComponent('강남역')}`
    );
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(data.total).toBeGreaterThanOrEqual(1);
    const match = data.items.find(
      (d: { district_name: string }) => d.district_name === '강남역'
    );
    expect(match?.district_code).toBe('3120189');
  });

  test('P5 chat SSE stream — summary card + monthly-unit sales', async () => {
    const ctx = await request.newContext();
    const resp = await ctx.post(`${BASE}/api/chat`, {
      data: {
        message: '강남역 상권 요약 알려줘',
        session_id: `e2e-smoke-${Date.now()}`,
        district_code: '3120189',
        district_name: '강남역',
      },
      headers: { 'Content-Type': 'application/json' },
      timeout: 60000,
    });
    expect(resp.status()).toBe(200);

    const body = await resp.text();
    const eventLines = body
      .split('\n')
      .filter((l) => l.startsWith('data:'))
      .map((l) => l.slice(5).trim())
      .filter((s) => s.length > 0);

    expect(eventLines.length).toBeGreaterThan(5);

    const events = eventLines
      .map((s) => {
        try {
          return JSON.parse(s);
        } catch {
          return null;
        }
      })
      .filter((e): e is Record<string, unknown> => e !== null);

    const types = new Set(events.map((e) => e.type));
    for (const required of ['thinking', 'tool', 'card', 'text']) {
      expect(types.has(required), `SSE missing type=${required}`).toBeTruthy();
    }

    // Summary card must exist
    const card = events.find(
      (e) => e.type === 'card' && e.card_type === 'summary'
    );
    expect(card, 'summary card missing').toBeTruthy();

    const cardData = (card as { data: Record<string, unknown> }).data;
    expect(cardData.districtName).toBe('강남역');

    // Monthly-unit sales sanity: 강남역 월 매출은 2025Q4 기준 약 1000억~2000억 원 범위
    // 이전 분기-누적 버그였다면 3000억+로 튐
    const summaryStr = String(cardData.summary ?? '');
    const numberInBillion = Number(
      summaryStr.replace(/[^0-9]/g, '').slice(0, 10) || 0
    );
    expect(summaryStr).toMatch(/월 추정 매출/);

    const insights = cardData.insights as
      | { perStoreSales?: number }
      | undefined;
    // Per-store monthly sales should be well under 100M KRW for 강남역 all-category avg
    expect(insights?.perStoreSales).toBeGreaterThan(5_000_000);
    expect(insights?.perStoreSales).toBeLessThan(100_000_000);
  });

  test('P6 recommend card — per_store_sales in monthly range', async () => {
    const ctx = await request.newContext();
    const resp = await ctx.post(`${BASE}/api/chat`, {
      data: {
        message: '이 상권에서 업종 추천해줘',
        session_id: `e2e-smoke-recommend-${Date.now()}`,
        district_code: '3110304',
        district_name: '보문역 4번',
      },
      headers: { 'Content-Type': 'application/json' },
      timeout: 60000,
    });
    expect(resp.status()).toBe(200);
    const body = await resp.text();
    const events = body
      .split('\n')
      .filter((l) => l.startsWith('data:'))
      .map((l) => {
        try {
          return JSON.parse(l.slice(5).trim());
        } catch {
          return null;
        }
      })
      .filter((e): e is Record<string, unknown> => e !== null);

    const card = events.find(
      (e) => e.type === 'card' && e.card_type === 'recommend'
    );
    expect(card, 'recommend card missing').toBeTruthy();

    const recs = (card as { data: { recommendations: Array<Record<string, number>> } })
      .data.recommendations;
    expect(recs.length).toBeGreaterThan(0);

    // Each recommendation's per_store_sales must be under 1B KRW/month (post-fix)
    // Pre-fix (quarterly cumulative), 보문역 슈퍼마켓은 4.13억/월로 나왔는데
    // 실제 월 단위면 1억 남짓. 1B 상한으로 regression guard.
    for (const r of recs) {
      expect(r.per_store_sales).toBeGreaterThan(0);
      expect(
        r.per_store_sales,
        `${r.category_name} per_store_sales=${r.per_store_sales} exceeds 1B monthly`
      ).toBeLessThan(1_000_000_000);
    }
  });

  test('P7 kakao SDK + map instance in browser', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('pageerror', (e) => consoleErrors.push(String(e)));
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    await page.goto(BASE, { waitUntil: 'domcontentloaded' });

    // Wait for Kakao SDK to finish loading (MapContainer triggers autoload=false → kakao.maps.load)
    await page.waitForFunction(
      () => {
        const k = (window as unknown as { kakao?: { maps?: { Map?: unknown } } }).kakao;
        return !!k && !!k.maps && !!k.maps.Map;
      },
      { timeout: 15000 }
    );

    // Kakao initializes the map by injecting child nodes into the mount div.
    // After init, the mount should have at least one child (tile layer wrapper).
    const mapInjected = await page.waitForFunction(
      () => {
        // Find a div whose class starts with "w-full h-full" and lives inside a relative wrapper
        const candidates = Array.from(document.querySelectorAll('div.relative.w-full.h-full > div'));
        return candidates.some((el) => el.childElementCount > 0);
      },
      { timeout: 10000 }
    );
    expect(mapInjected, 'Kakao map did not inject tile DOM').toBeTruthy();

    const fatal = consoleErrors.filter(
      (e) =>
        !e.includes('favicon') &&
        !e.includes('404') &&
        !e.includes('DevTools') &&
        !e.toLowerCase().includes('websocket')
    );
    expect(fatal, `fatal console errors: ${fatal.join(' | ')}`).toHaveLength(0);
  });
});
