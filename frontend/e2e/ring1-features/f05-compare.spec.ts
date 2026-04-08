/**
 * Ring 1 — F05 상권 비교
 */

import { test, expect } from '@playwright/test';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { waitForMapReady, sendChatMessage, waitForResponseComplete } from '../helpers/setup';
import { waitForCardText } from '../helpers/waitSSE';

test.beforeAll(() => ensureRunDir());

test.describe('Ring 1 — F05 Compare', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('F05-H1 강남 vs 홍대 비교', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F05-H1-2-way',
      title: '2개 상권 비교',
      story: '두 상권을 비교 요청 시 CompareCard에 두 상권 모두 표시되고 판정 코멘트가 나와야 한다.',
      steps: ['"강남역과 홍대입구 비교해줘" 전송'],
      mode: 'Mock',
      ring: 1,
      feature: 'F05',
      criteria: ['DOM에 강남 + 홍대', '비교 또는 판정 키워드', '수치 ≥3개'],
    });
    packet.attach(page);
    await sendChatMessage(page, '강남역과 홍대입구를 비교해줘');
    await waitForCardText(page, ['비교', '판정'], 60000);
    const text = (await page.locator('body').innerText()) || '';
    const hasBoth = text.includes('강남') && text.includes('홍대');
    const numCount = (text.match(/\d{2,}/g) || []).length;
    packet.writeAutoVerdict({
      result: hasBoth && numCount >= 3 ? 'PASS' : 'FAIL',
      reason: `hasBoth=${hasBoth} numCount=${numCount}`,
      checks: [
        { criterion: '두 상권명', met: hasBoth, evidence: hasBoth ? 'both' : 'missing' },
        { criterion: '수치 ≥3', met: numCount >= 3, evidence: `${numCount}` },
      ],
    });
    expect(hasBoth).toBe(true);
    await packet.finalize(page);
  });

  test('F05-H2 강남/홍대/건대 3개 비교', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F05-H2-3-way',
      title: '3개 상권 비교',
      story: '최대 허용 개수 비교 (3개) 정상 처리.',
      steps: ['"강남역, 홍대입구, 건대입구 비교해줘" 전송'],
      mode: 'Mock',
      ring: 1,
      feature: 'F05',
      criteria: ['DOM에 강남 + 홍대 + 건대 모두', 'console error 0'],
    });
    packet.attach(page);
    await sendChatMessage(page, '강남역, 홍대입구, 건대입구 비교해줘');
    await page.waitForTimeout(3000);
    const text = (await page.locator('body').innerText()) || '';
    const allThree = ['강남', '홍대', '건대'].every((n) => text.includes(n));
    packet.writeAutoVerdict({
      result: allThree ? 'PASS' : 'FAIL',
      reason: `all3=${allThree}`,
      checks: [{ criterion: '3 상권명', met: allThree, evidence: allThree ? 'all present' : 'missing' }],
    });
    expect(allThree).toBe(true);
    await packet.finalize(page);
  });

  test('F05-E1 4개 비교 → 안내 메시지', async ({ page }) => {
    test.setTimeout(180000); // Real-mode 4-way compare can be slow
    const packet = new EvalPacket({
      id: 'F05-E1-over-3',
      title: '4개 상권 비교 거부 또는 제한',
      story: '4개 비교를 요청해도 크래시 없이 안내가 나와야 한다.',
      steps: ['"강남역, 홍대, 건대, 명동 비교해줘" 전송'],
      mode: 'Mock',
      ring: 1,
      feature: 'F05',
      criteria: ['응답 완료', 'console error 0'],
    });
    packet.attach(page);
    await sendChatMessage(page, '강남역, 홍대입구, 건대입구, 명동 비교해줘');
    await waitForResponseComplete(page, 120000);
    const errors = packet.consoleEntries.filter((e) => e.startsWith('[error]')).length;
    const ta = page.locator('textarea[placeholder*="물어보세요"]');
    const enabled = !(await ta.isDisabled());
    packet.writeAutoVerdict({
      result: enabled && errors === 0 ? 'PASS' : 'FAIL',
      reason: `enabled=${enabled} errors=${errors}`,
      checks: [
        { criterion: '재활성화', met: enabled, evidence: `${enabled}` },
        { criterion: '에러 0', met: errors === 0, evidence: `${errors}` },
      ],
    });
    expect(enabled).toBe(true);
    await packet.finalize(page);
  });
});
