/**
 * Ring 2 — J02 Comparison shopper
 *
 * "A vs B vs C 중 어디?"
 * F01 → F05 → F04 → F09
 */

import { test, expect, waitForMapReady, sendChatMessage } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';

test.beforeAll(() => ensureRunDir());
test.setTimeout(300000);

test('J02 comparison shopper — 3-way compare → cafe analysis → simulation', async ({ page }) => {
  const packet = new EvalPacket({
    id: 'J02-comparison',
    title: '비교 쇼퍼: 3개 비교 → 카페 분석 → 시뮬레이션',
    story: '강남/홍대/건대를 비교한 후 카페 적합성을 묻고 매출 시뮬레이션까지 유도.',
    steps: [
      '"강남역, 홍대입구, 건대입구 비교해줘"',
      '"거기서 카페 하면 어때?"',
      '"강남역 카페 월 매출 얼마나 나올까?"',
    ],
    mode: 'Mock',
    ring: 2,
    feature: 'F05+F04+F09',
    criteria: [
      'DOM에 강남+홍대+건대 모두 (비교)',
      'DOM에 카페 키워드 (분석)',
      'DOM에 매출/시뮬 키워드 + 수치',
      'console error 0',
    ],
  });
  packet.attach(page);
  await page.goto('/');
  await waitForMapReady(page);

  await sendChatMessage(page, '강남역, 홍대입구, 건대입구를 비교해줘');
  await page.waitForTimeout(2000);
  await sendChatMessage(page, '거기서 카페 하면 어때?');
  await page.waitForTimeout(2000);
  await sendChatMessage(page, '강남역 카페 월 매출 얼마나 나올까?');
  await page.waitForTimeout(2000);

  const text = (await page.locator('body').innerText()) || '';
  const all3 = ['강남', '홍대', '건대'].every((n) => text.includes(n));
  const hasCafe = text.includes('카페') || text.includes('커피');
  const hasSales = /매출|시뮬|예상|범위/.test(text);
  const numCount = (text.match(/\d{2,}/g) || []).length;
  const errors = packet.consoleEntries.filter((e) => e.startsWith('[error]')).length;

  packet.writeAutoVerdict({
    result: all3 && hasCafe && hasSales && numCount >= 5 ? 'PASS' : 'FAIL',
    reason: `all3=${all3} cafe=${hasCafe} sales=${hasSales} nums=${numCount} errors=${errors}`,
    checks: [
      { criterion: '3 상권 모두', met: all3, evidence: all3 ? 'present' : 'missing' },
      { criterion: '카페 분석', met: hasCafe, evidence: hasCafe ? 'present' : 'absent' },
      { criterion: '매출 시뮬', met: hasSales, evidence: hasSales ? 'present' : 'absent' },
      { criterion: '수치 ≥5', met: numCount >= 5, evidence: `${numCount}` },
    ],
  });
  await packet.finalize(page);
  expect(all3).toBe(true);
});
