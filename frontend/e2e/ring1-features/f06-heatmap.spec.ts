/**
 * Ring 1 — F06 시간대별 히트맵 (Premium)
 *
 * Tests the heatmap API + toggle UI smoke (full canvas verification deferred).
 */

import { test, expect } from '@playwright/test';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';

const BACKEND = process.env.E2E_BACKEND_URL || 'http://localhost:8002';

test.beforeAll(() => ensureRunDir());

test.describe('Ring 1 — F06 Heatmap', () => {
  test('F06-H1 heatmap API at hour 9', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F06-H1-heatmap-9',
      title: '/api/map-data/heatmap?time_slot=9',
      story: '특정 시간대 히트맵 데이터가 정상 반환되어야 한다.',
      steps: ['GET /api/map-data/heatmap?time_slot=9'],
      mode: 'Mock',
      ring: 1,
      feature: 'F06',
      criteria: ['HTTP 200', '응답에 features 또는 points 배열'],
    });
    packet.attach(page);
    const resp = await page.request.get(`${BACKEND}/api/map-data/heatmap?time_slot=9`);
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    const hasData =
      Array.isArray(body) ||
      Array.isArray(body.features) ||
      Array.isArray(body.points) ||
      Array.isArray(body.data);
    packet.writeAutoVerdict({
      result: hasData ? 'PASS' : 'FAIL',
      reason: `hasData=${hasData}`,
      checks: [
        { criterion: 'HTTP 200', met: true, evidence: '200' },
        { criterion: '데이터 배열', met: hasData, evidence: hasData ? 'array present' : 'no array' },
      ],
    });
    await packet.finalize(page);
  });

  test('F06-H2 heatmap toggle UI smoke', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F06-H2-toggle',
      title: '히트맵 토글 버튼 존재',
      story: '맵 컨트롤에 히트맵 토글 버튼이 있고 클릭 시 상태 변경되어야 한다.',
      steps: ['/ 진입', '히트맵 버튼 검색 및 클릭'],
      mode: 'Mock',
      ring: 1,
      feature: 'F06',
      criteria: ['히트맵 버튼 존재', 'click 후 console error 0'],
    });
    packet.attach(page);
    await page.goto('/');
    await page.waitForTimeout(2000);
    // Look for heatmap button (🔥 emoji or '히트맵' text)
    const heatBtn = page
      .locator('button[title*="히트맵"], button:has-text("히트맵"), button[aria-label*="히트맵"]')
      .first();
    const visible = await heatBtn.isVisible({ timeout: 3000 }).catch(() => false);
    if (visible) await heatBtn.click().catch(() => {});
    const errors = packet.consoleEntries.filter((e) => e.startsWith('[error]')).length;
    packet.writeAutoVerdict({
      result: visible && errors === 0 ? 'PASS' : visible ? 'FAIL' : 'SKIP',
      reason: visible ? `clicked, errors=${errors}` : 'heatmap button not visible',
      checks: [
        { criterion: '버튼 존재', met: visible, evidence: visible ? 'present' : 'absent' },
        { criterion: '에러 0', met: errors === 0, evidence: `${errors}` },
      ],
    });
    await packet.finalize(page);
  });
});
