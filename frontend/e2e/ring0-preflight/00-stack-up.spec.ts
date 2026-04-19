/**
 * Ring 0 — Pre-flight stack health
 *
 * Verifies backend + frontend reachable, mode detection, polygons API smoke.
 * Failures here halt the entire run.
 */

import { test, expect } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { detectMode } from '../helpers/modeGuard';

test.beforeAll(() => ensureRunDir());

const BACKEND = process.env.E2E_BACKEND_URL || 'http://localhost:8002';

test.describe('Ring 0 — Pre-flight', () => {
  test('R0-1 backend health endpoint', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'R0-1-backend-health',
      title: 'Backend /health 200',
      story: '백엔드 헬스체크가 200을 리턴해야 한다 (서비스 가용성 기본).',
      steps: [`fetch ${BACKEND}/health → 200 with body {status:"ok"}`],
      mode: 'Mock',
      ring: 0,
      criteria: [
        '/health 응답이 HTTP 200',
        '응답 body에 status 필드가 ok 값을 포함',
      ],
    });
    packet.attach(page);

    const resp = await page.request.get(`${BACKEND}/health`);
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.status).toBe('ok');

    packet.writeAutoVerdict({
      result: 'PASS',
      reason: '/health responded 200 with status=ok',
      checks: [
        { criterion: 'HTTP 200', met: true, evidence: `status=${resp.status()}` },
        { criterion: 'status=ok', met: body.status === 'ok', evidence: JSON.stringify(body) },
      ],
    });
    await packet.finalize(page);
  });

  test('R0-2 frontend root reachable', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'R0-2-frontend-root',
      title: 'Frontend / 200',
      story: '프론트엔드 루트(/)가 200 HTML을 반환해야 한다.',
      steps: ['GET /', '응답 200 + HTML'],
      mode: 'Mock',
      ring: 0,
      criteria: ['프론트엔드 / 응답 200', 'body에 next.js 마커 (id=__next)'],
    });
    packet.attach(page);
    const resp = await page.goto('/');
    expect(resp?.status()).toBe(200);
    await page.waitForLoadState('domcontentloaded');
    const html = await page.content();
    const hasNext = html.includes('__next') || html.includes('_next');

    packet.writeAutoVerdict({
      result: hasNext ? 'PASS' : 'FAIL',
      reason: hasNext ? 'Next.js marker found' : 'Next.js marker missing',
      checks: [
        { criterion: 'HTTP 200', met: resp?.status() === 200, evidence: `status=${resp?.status()}` },
        { criterion: 'next marker', met: hasNext, evidence: hasNext ? 'present' : 'absent' },
      ],
    });
    await packet.finalize(page);
  });

  test('R0-3 polygons smoke (Mock or Real)', async ({ page }) => {
    // Backend bounds format: sw_lat,sw_lng,ne_lat,ne_lng (lat first)
    // Mock ignores bounds; Real applies ST_MakeEnvelope.
    const bounds = '37.5,126.9,37.6,127.1';
    const packet = new EvalPacket({
      id: 'R0-3-polygons-smoke',
      title: 'Polygons GeoJSON ≥1 feature',
      story: '/api/map-data/polygons가 GeoJSON FeatureCollection을 200으로 리턴해야 한다.',
      steps: [`GET ${BACKEND}/api/map-data/polygons?bounds=${bounds}`],
      mode: 'Mock',
      ring: 0,
      criteria: [
        'HTTP 200',
        'type=FeatureCollection',
        'features 배열 길이 ≥1',
      ],
    });
    packet.attach(page);
    const resp = await page.request.get(
      `${BACKEND}/api/map-data/polygons?bounds=${bounds}`
    );
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(data.type).toBe('FeatureCollection');
    expect(data.features.length).toBeGreaterThanOrEqual(1);

    packet.writeAutoVerdict({
      result: 'PASS',
      reason: `${data.features.length} features returned`,
      checks: [
        { criterion: 'HTTP 200', met: true, evidence: `status=${resp.status()}` },
        { criterion: 'FeatureCollection', met: data.type === 'FeatureCollection', evidence: data.type },
        {
          criterion: 'features ≥1',
          met: data.features.length >= 1,
          evidence: `${data.features.length} features`,
        },
      ],
    });
    await packet.finalize(page);
  });

  test('R0-4 mode detection (Mock vs Real)', async ({ page }) => {
    const mode = await detectMode();
    const packet = new EvalPacket({
      id: 'R0-4-mode-detection',
      title: `Backend mode = ${mode}`,
      story: '백엔드가 Mock 또는 Real 모드 중 어느 것으로 운영되는지 확인.',
      steps: ['/api/districts?search=강남 호출 → district_code 검사'],
      mode: mode === 'mock' ? 'Mock' : 'Real',
      ring: 0,
      criteria: [`backend mode 검출됨 (${mode})`],
    });
    packet.attach(page);
    expect(['mock', 'real']).toContain(mode);
    packet.writeAutoVerdict({
      result: 'PASS',
      reason: `Detected mode: ${mode}`,
      checks: [{ criterion: 'mode detected', met: true, evidence: `mode=${mode}` }],
    });
    await packet.finalize(page);
  });
});
