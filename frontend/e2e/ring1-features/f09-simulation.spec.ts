/**
 * Ring 1 — F09 매출 시뮬레이션 (Premium)
 */

import { test, expect } from '@playwright/test';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { waitForMapReady, sendChatMessage } from '../helpers/setup';
import { waitForCardText } from '../helpers/waitSSE';

test.beforeAll(() => ensureRunDir());

test.describe('Ring 1 — F09 Simulation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('F09-H1 "강남역 카페 월 매출 얼마나?"', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F09-H1-simulation',
      title: '카페 매출 시뮬레이션',
      story: '매출 시뮬레이션 요청 시 SimulationCard에 분위수 수치와 가정/면책이 표시되어야 한다.',
      steps: ['"강남역에서 카페 월 매출 얼마나?" 전송'],
      mode: 'Mock',
      ring: 1,
      feature: 'F09',
      criteria: ['DOM에 매출/시뮬레이션/예상 키워드', '수치 ≥3', '면책 안내'],
    });
    packet.attach(page);
    await sendChatMessage(page, '강남역에서 카페 월 매출 얼마나 나올까?');
    await waitForCardText(page, ['매출', '시뮬레이션', '예상', '범위'], 60000);
    const text = (await page.locator('body').innerText()) || '';
    const numCount = (text.match(/\d{2,}/g) || []).length;
    const hasDisclaimer = /(면책|참고|추정|주의)/.test(text);
    packet.writeAutoVerdict({
      result: numCount >= 3 ? 'PASS' : 'FAIL',
      reason: `numCount=${numCount} disclaimer=${hasDisclaimer}`,
      checks: [
        { criterion: '수치 ≥3', met: numCount >= 3, evidence: `${numCount}` },
        { criterion: '면책', met: hasDisclaimer, evidence: hasDisclaimer ? 'present' : 'absent' },
      ],
    });
    await packet.finalize(page);
  });
});
