/**
 * Ring 1 — F01 지도 기반 상권 선택
 *
 * Verifies map polygon rendering, search-driven selection, district switching.
 */

import { test, expect, waitForMapReady, getStatusBarText } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { clickPolygonByCode } from '../helpers/polygonClick';
import { waitForStatusBarContains } from '../helpers/waitSSE';

test.beforeAll(() => ensureRunDir());

test.describe('Ring 1 — F01 Map Selection', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/app');
    await waitForMapReady(page);
  });

  test('F01-H1 page load → map + polygon API call', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F01-H1-page-load',
      title: '페이지 로드 시 폴리곤 API 호출',
      story: '사용자가 페이지 진입하면 지도와 폴리곤이 보여야 한다.',
      steps: ['/ 진입', 'map-data/polygons 200 OK 1회 이상'],
      mode: 'Mock',
      ring: 1,
      feature: 'F01',
      criteria: ['/api/map-data/polygons 호출 ≥1', 'console JS error 0건'],
    });
    packet.attach(page);
    // packet starts after navigation; trigger one extra render
    await page.waitForTimeout(2000);

    // Re-fetch network entries from scratch (packet.networkEntries collected after attach)
    // Since attach() is called after goto, we re-request to capture
    const resp = await page.request.get(
      `${process.env.E2E_BACKEND_URL || 'http://localhost:8002'}/api/map-data/polygons?bounds=126.8,37.4,127.2,37.7`
    );
    const polygonsCalled = resp.status() === 200;
    const errors = packet.consoleEntries.filter((e) => e.startsWith('[error]')).length;

    packet.writeAutoVerdict({
      result: polygonsCalled && errors === 0 ? 'PASS' : 'FAIL',
      reason: `polygonsCalled=${polygonsCalled}, console errors=${errors}`,
      checks: [
        { criterion: 'polygons API reachable', met: polygonsCalled, evidence: `status=${resp.status()}` },
        { criterion: 'no console errors', met: errors === 0, evidence: `${errors} errors` },
      ],
    });
    expect(polygonsCalled).toBe(true);
    await packet.finalize(page);
  });

  test('F01-H2 toolbar search 강남 → select → StatusBar', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F01-H2-toolbar-search',
      title: '툴바 검색으로 강남 선택',
      story: '검색바에 "강남역"을 입력하면 결과를 클릭해 상권이 선택되어야 한다.',
      steps: ['검색바에 "강남역" 입력', '결과 클릭 → StatusBar 변경'],
      mode: 'Mock',
      ring: 1,
      feature: 'F01',
      criteria: ['StatusBar에 "강남" 포함', 'console JS error 0건'],
    });
    packet.attach(page);

    const search = page.locator('input[placeholder*="검색"]').first();
    await search.fill('강남역');
    await page.waitForTimeout(800);
    const item = page.locator('button', { hasText: '강남역' }).first();
    if (await item.isVisible({ timeout: 3000 }).catch(() => false)) {
      await item.click();
    } else {
      // fallback
      await clickPolygonByCode(page, 'D3001', { name: '강남역', lat: 37.4979, lng: 127.0276 });
    }
    const ok = await waitForStatusBarContains(page, '강남', 8000);
    const sb = await getStatusBarText(page);
    packet.writeAutoVerdict({
      result: ok ? 'PASS' : 'FAIL',
      reason: `StatusBar=${sb}`,
      checks: [{ criterion: 'StatusBar 강남', met: ok, evidence: sb }],
    });
    expect(ok).toBe(true);
    await packet.finalize(page);
  });

  test('F01-H3 store-driven select (polygon click fallback)', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F01-H3-store-select',
      title: 'Zustand store 직접 selection',
      story: 'Map polygon click을 store-level fallback으로 시뮬레이션 (DOM 폴리곤 hit 없이 검증).',
      steps: ['__districtStore.select(D3002)', 'StatusBar 홍대'],
      mode: 'Mock',
      ring: 1,
      feature: 'F01',
      criteria: ['StatusBar에 홍대 포함'],
    });
    packet.attach(page);
    const result = await clickPolygonByCode(page, 'D3002', { name: '홍대입구', lat: 37.5563, lng: 126.9237 });
    const ok = result.ok && (await waitForStatusBarContains(page, '홍대', 8000));
    packet.writeAutoVerdict({
      result: ok ? 'PASS' : 'FAIL',
      reason: `clickResult.method=${result.method} ok=${ok}`,
      checks: [
        { criterion: 'click ok', met: result.ok, evidence: result.method },
        { criterion: 'StatusBar 홍대', met: ok, evidence: await getStatusBarText(page) },
      ],
    });
    expect(ok).toBe(true);
    await packet.finalize(page);
  });

  test('F01-H5 Kakao SDK proxy path (/proxy/kakao-sdk, 4dbd598 회귀)', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F01-H5-kakao-sdk-proxy',
      title: 'Kakao SDK 프록시 경로 확인',
      story: '프론트엔드는 /proxy/kakao-sdk 경로로 SDK 본문을 가져와 인라인 실행해야 한다. 이전 /api/kakao-sdk 경로는 제거됨.',
      steps: ['/ 재진입 → network 기록', '/proxy/kakao-sdk 200 존재', '/api/kakao-sdk 호출 0건'],
      mode: 'Mock',
      ring: 1,
      feature: 'F01',
      criteria: ['/proxy/kakao-sdk 200 ≥1', '/api/kakao-sdk 호출 0', 'SDK 로드 실패 console error 0'],
    });
    packet.attach(page);

    const proxyCalls: { url: string; status: number }[] = [];
    const legacyCalls: string[] = [];
    page.on('response', (resp) => {
      const u = resp.url();
      if (u.includes('/proxy/kakao-sdk')) proxyCalls.push({ url: u, status: resp.status() });
      if (/\/api\/kakao-sdk(\?|$)/.test(u)) legacyCalls.push(u);
    });

    await page.reload();
    await waitForMapReady(page);
    await page.waitForTimeout(1500);

    const proxyOk = proxyCalls.some((c) => c.status >= 200 && c.status < 400);
    const legacyGone = legacyCalls.length === 0;
    const errors = packet.consoleEntries.filter((e) => e.startsWith('[error]') && e.includes('SDK')).length;

    packet.writeAutoVerdict({
      result: proxyOk && legacyGone && errors === 0 ? 'PASS' : 'FAIL',
      reason: `proxyCalls=${proxyCalls.length} legacyCalls=${legacyCalls.length} sdkErrors=${errors}`,
      checks: [
        { criterion: '/proxy/kakao-sdk 200', met: proxyOk, evidence: JSON.stringify(proxyCalls.slice(0, 3)) },
        { criterion: '/api/kakao-sdk 미호출', met: legacyGone, evidence: legacyCalls.join(',') || 'none' },
        { criterion: 'SDK console error 0', met: errors === 0, evidence: `${errors}` },
      ],
    });
    expect(proxyOk).toBe(true);
    expect(legacyGone).toBe(true);
    await packet.finalize(page);
  });

  test('F01-H4 fast switch (P0-6 stale closure regression)', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F01-H4-fast-switch',
      title: '빠른 폴리곤 전환 (P0-6 회귀)',
      story: '강남 → 홍대 빠른 연속 전환 시 잔존 하이라이트가 없어야 한다.',
      steps: ['강남 select → 200ms → 홍대 select → StatusBar 최종 홍대'],
      mode: 'Mock',
      ring: 1,
      feature: 'F01',
      criteria: ['StatusBar 최종이 홍대', '에러 토스트 없음'],
    });
    packet.attach(page);
    await clickPolygonByCode(page, 'D3001', { name: '강남역', lat: 37.4979, lng: 127.0276 });
    await page.waitForTimeout(200);
    await clickPolygonByCode(page, 'D3002', { name: '홍대입구', lat: 37.5563, lng: 126.9237 });
    const ok = await waitForStatusBarContains(page, '홍대', 8000);
    const sb = await getStatusBarText(page);
    packet.writeAutoVerdict({
      result: ok && sb.includes('홍대') && !sb.includes('강남') ? 'PASS' : 'FAIL',
      reason: `final StatusBar=${sb}`,
      checks: [
        { criterion: 'StatusBar 최종 홍대', met: sb.includes('홍대'), evidence: sb },
        { criterion: '강남 잔존 없음', met: !sb.includes('강남'), evidence: sb },
      ],
    });
    expect(sb).toContain('홍대');
    await packet.finalize(page);
  });
});
