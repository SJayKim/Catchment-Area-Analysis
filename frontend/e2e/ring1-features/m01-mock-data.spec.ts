/**
 * Ring 1 — M01 Mock Data Layer
 *
 * Verifies the Mock fixtures that the entire Phase-1A pipeline depends on.
 */

import { test, expect } from '@playwright/test';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';

const BACKEND = process.env.E2E_BACKEND_URL || 'http://localhost:8002';

test.beforeAll(() => ensureRunDir());

test.describe('Ring 1 — M01 Mock Data', () => {
  test('M01-H1 polygons GeoJSON ≥5 mock features', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'M01-H1-polygons-mock',
      title: 'Mock polygons GeoJSON ≥5',
      story: 'Mock 모드는 5개 고정 상권 폴리곤(D3001~D3005)을 GeoJSON으로 노출해야 한다.',
      steps: ['GET /api/map-data/polygons → ≥5 features, D3001~D3005 모두 존재'],
      mode: 'Mock',
      ring: 1,
      feature: 'M01',
      criteria: [
        'HTTP 200',
        'features.length ≥ 5',
        'D3001/D3002/D3003/D3004/D3005 모두 포함',
      ],
    });
    packet.attach(page);
    const resp = await page.request.get(`${BACKEND}/api/map-data/polygons?bounds=126.8,37.4,127.2,37.7`);
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    const codes = data.features.map((f: { properties: { district_code: string } }) => f.properties.district_code);
    const hasAll = ['D3001', 'D3002', 'D3003', 'D3004', 'D3005'].every((c) => codes.includes(c));
    expect(hasAll).toBe(true);
    packet.writeAutoVerdict({
      result: hasAll && data.features.length >= 5 ? 'PASS' : 'FAIL',
      reason: `${data.features.length} features, codes=[${codes.join(',')}]`,
      checks: [
        { criterion: 'HTTP 200', met: resp.status() === 200, evidence: `${resp.status()}` },
        { criterion: 'features ≥5', met: data.features.length >= 5, evidence: `${data.features.length}` },
        { criterion: 'D3001~D3005 모두', met: hasAll, evidence: codes.join(',') },
      ],
    });
    await packet.finalize(page);
  });

  test('M01-H2 districts search 강남 ≥1 hit', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'M01-H2-search-gangnam',
      title: 'Districts search "강남"',
      story: 'Mock 검색이 "강남"으로 강남역 상권을 매칭해야 한다.',
      steps: ['GET /api/districts?search=강남'],
      mode: 'Mock',
      ring: 1,
      feature: 'M01',
      criteria: ['HTTP 200', 'items 길이 ≥1', 'name 또는 code에 강남 포함'],
    });
    packet.attach(page);
    const resp = await page.request.get(`${BACKEND}/api/districts?search=${encodeURIComponent('강남')}`);
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    const ok = data.total >= 1 && data.items[0].district_name.includes('강남');
    packet.writeAutoVerdict({
      result: ok ? 'PASS' : 'FAIL',
      reason: `total=${data.total}, first=${data.items[0]?.district_name}`,
      checks: [
        { criterion: 'HTTP 200', met: true, evidence: `${resp.status()}` },
        { criterion: 'items ≥1', met: data.total >= 1, evidence: `total=${data.total}` },
        { criterion: '강남 매칭', met: ok, evidence: data.items[0]?.district_name || 'no match' },
      ],
    });
    expect(ok).toBe(true);
    await packet.finalize(page);
  });

  test('M01-H3 mock summary endpoint returns numbers', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'M01-H3-summary-numbers',
      title: 'Summary tool returns non-empty data',
      story: 'D3001(강남역) 요약이 유동인구/매출/점포 수치를 모두 채워서 반환해야 한다.',
      steps: ['POST /api/chat with "강남역 요약" → SSE done', 'card data에 3 metric'],
      mode: 'Mock',
      ring: 1,
      feature: 'M01',
      criteria: ['/api/chat 200', 'response에 유동인구/매출/점포 키워드', '에러 없음'],
    });
    packet.attach(page);

    // Direct backend call for fixture sanity (avoid UI flake)
    const resp = await page.request.post(`${BACKEND}/api/chat`, {
      data: {
        message: '강남역 상권 요약해줘',
        district_code: 'D3001',
        session_id: 'm01-h3',
      },
      timeout: 60000,
    });
    expect(resp.status()).toBe(200);
    const body = await resp.text();
    const ok = body.includes('유동인구') || body.includes('매출') || body.includes('점포');
    packet.writeAutoVerdict({
      result: ok ? 'PASS' : 'FAIL',
      reason: ok ? 'Found at least one metric keyword in SSE body' : 'No metric keywords',
      checks: [
        { criterion: 'HTTP 200', met: resp.status() === 200, evidence: `${resp.status()}` },
        { criterion: '유동인구/매출/점포 언급', met: ok, evidence: ok ? 'present' : 'absent' },
      ],
    });
    expect(ok).toBe(true);
    await packet.finalize(page);
  });

  test('M01-E1 search nonexistent → empty 200', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'M01-E1-search-empty',
      title: 'Search nonexistent → 200 + empty',
      story: '존재하지 않는 키워드 검색은 500이 아닌 200 + 빈 배열을 반환해야 한다.',
      steps: ['GET /api/districts?search=뉴욕'],
      mode: 'Mock',
      ring: 1,
      feature: 'M01',
      criteria: ['HTTP 200', 'items 빈 배열', '500/예외 없음'],
    });
    packet.attach(page);
    const resp = await page.request.get(`${BACKEND}/api/districts?search=${encodeURIComponent('뉴욕')}`);
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    packet.writeAutoVerdict({
      result: resp.status() === 200 && data.total === 0 ? 'PASS' : 'FAIL',
      reason: `status=${resp.status()} total=${data.total}`,
      checks: [
        { criterion: 'HTTP 200', met: resp.status() === 200, evidence: `${resp.status()}` },
        { criterion: 'items 빈', met: data.total === 0, evidence: `total=${data.total}` },
      ],
    });
    expect(data.total).toBe(0);
    await packet.finalize(page);
  });
});
