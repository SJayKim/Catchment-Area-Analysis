/**
 * Ring 1 — F04 업종별 심층 분석 (Premium)
 *
 * Phase 2 기능 — happy path만 검증.
 */

import { test, expect } from '@playwright/test';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { waitForMapReady, sendChatMessage, waitForResponseComplete } from '../helpers/setup';
import { waitForCardText } from '../helpers/waitSSE';

test.beforeAll(() => ensureRunDir());

test.describe('Ring 1 — F04 Category Deep Analysis', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('F04-H1 "강남역 카페 어때?" → 카페 + 수치 응답', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F04-H1-cafe',
      title: '강남역 카페 분석',
      story: '특정 업종 분석 요청 시 해당 업종 키워드와 수치를 답변에 포함해야 한다.',
      steps: ['"강남역에서 카페 하면 어때?" 전송'],
      mode: 'Mock',
      ring: 1,
      feature: 'F04',
      criteria: ['DOM에 카페 키워드', 'DOM에 숫자 또는 수치 표현'],
    });
    packet.attach(page);
    await sendChatMessage(page, '강남역에서 카페 하면 어때?');
    const r = await waitForCardText(page, ['카페', '커피'], 60000);
    const text = (await page.locator('body').innerText()) || '';
    const hasNumber = /\d{2,}/.test(text);
    packet.writeAutoVerdict({
      result: r.found && hasNumber ? 'PASS' : 'FAIL',
      reason: `cafe keyword=${r.found}, has number=${hasNumber}`,
      checks: [
        { criterion: '카페 키워드', met: r.found, evidence: r.matched || 'absent' },
        { criterion: '수치', met: hasNumber, evidence: hasNumber ? 'has' : 'absent' },
      ],
    });
    expect(r.found).toBe(true);
    await packet.finalize(page);
  });

  test('F04-E1 없는 업종 → 정중한 폴백', async ({ page }) => {
    test.setTimeout(120000);
    const packet = new EvalPacket({
      id: 'F04-E1-unknown-category',
      title: '없는 업종 ("우주선 매장")',
      story: '존재하지 않는 업종을 물어도 크래시 없이 응답해야 한다.',
      steps: ['"강남역에서 우주선 매장 하면 어때?" 전송'],
      mode: 'Mock',
      ring: 1,
      feature: 'F04',
      criteria: ['응답 완료', 'console error 0', 'textarea 재활성'],
    });
    packet.attach(page);
    await sendChatMessage(page, '강남역에서 우주선 매장 하면 어때?');
    await waitForResponseComplete(page, 90000);
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
