/**
 * Ring 1 — F08 점포 이력/리스크 분석
 */

import { test, expect, waitForMapReady, sendChatMessage } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { waitForCardText } from '../helpers/waitSSE';

test.beforeAll(() => ensureRunDir());

test.describe('Ring 1 — F08 Risk Analysis', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('F08-H1 "강남역 위험해?" → 리스크 카드', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F08-H1-risk',
      title: '"이 자리 위험해?"',
      story: '리스크 분석 요청 시 RiskCard에 안정성/생존 키워드와 폐업률 등이 표시되어야 한다.',
      steps: ['"강남역 위험해?" 전송'],
      mode: 'Mock',
      ring: 1,
      feature: 'F08',
      criteria: ['DOM에 안정성/생존/리스크 중 하나', '폐업률 또는 위험도 수치'],
    });
    packet.attach(page);
    await sendChatMessage(page, '강남역 이 자리 위험해?');
    const r = await waitForCardText(page, ['안정성', '생존', '리스크', '위험'], 60000);
    const text = (await page.locator('body').innerText()) || '';
    const hasNum = /\d{1,2}\.?\d*\s*%/.test(text) || /\d{2,}/.test(text);
    packet.writeAutoVerdict({
      result: r.found && hasNum ? 'PASS' : 'FAIL',
      reason: `keyword=${r.found} num=${hasNum}`,
      checks: [
        { criterion: '리스크 키워드', met: r.found, evidence: r.matched || 'absent' },
        { criterion: '수치', met: hasNum, evidence: hasNum ? 'present' : 'absent' },
      ],
    });
    expect(r.found).toBe(true);
    await packet.finalize(page);
  });
});
