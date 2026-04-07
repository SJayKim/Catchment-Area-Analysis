/**
 * Ring 1 — F07 업종 추천
 */

import { test, expect } from '@playwright/test';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { waitForMapReady, sendChatMessage } from '../helpers/setup';
import { waitForCardText } from '../helpers/waitSSE';

test.beforeAll(() => ensureRunDir());

test.describe('Ring 1 — F07 Recommend', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('F07-H1 강남역 → 업종 추천 Top 5', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F07-H1-recommend',
      title: '"여기서 뭐하면 좋을까?"',
      story: '상권 선택 후 추천 요청 시 RecommendCard에 Top 업종과 점수가 표시되어야 한다.',
      steps: ['"강남역에서 뭐하면 좋을까?" 전송'],
      mode: 'Mock',
      ring: 1,
      feature: 'F07',
      criteria: ['DOM에 추천 키워드', '점수 또는 % 또는 숫자 ≥3개', '면책 안내'],
    });
    packet.attach(page);
    await sendChatMessage(page, '강남역에서 뭐하면 좋을까?');
    const r = await waitForCardText(page, ['추천', '업종'], 60000);
    const text = (await page.locator('body').innerText()) || '';
    const numCount = (text.match(/\d{2,}/g) || []).length;
    const hasDisclaimer = /(참고|면책|추정|주의)/.test(text);
    packet.writeAutoVerdict({
      result: r.found && numCount >= 3 ? 'PASS' : 'FAIL',
      reason: `recommend=${r.found} numCount=${numCount} disclaimer=${hasDisclaimer}`,
      checks: [
        { criterion: '추천/업종 키워드', met: r.found, evidence: r.matched || 'absent' },
        { criterion: '수치 ≥3', met: numCount >= 3, evidence: `${numCount}` },
        { criterion: '면책 안내', met: hasDisclaimer, evidence: hasDisclaimer ? 'present' : 'absent' },
      ],
    });
    expect(r.found).toBe(true);
    await packet.finalize(page);
  });
});
