/**
 * Ring 3 — Negative: 상권 미선택 상태에서 분석 요청
 */

import { test, expect } from '@playwright/test';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { waitForMapReady, sendChatMessage } from '../helpers/setup';

test.beforeAll(() => ensureRunDir());

test('NEG-1 no district selected → graceful guide', async ({ page }) => {
  const packet = new EvalPacket({
    id: 'NEG-1-no-district',
    title: '상권 미선택 + 분석 요청',
    story: '아무 상권도 선택하지 않은 채 "분석해줘"만 입력해도 안내가 나와야 한다.',
    steps: ['"분석해줘" 전송 (상권 명시 없음)'],
    mode: 'Mock',
    ring: 3,
    feature: 'NEG',
    criteria: ['textarea 재활성화', 'console error 0', '응답 텍스트 존재'],
  });
  packet.attach(page);
  await page.goto('/');
  await waitForMapReady(page);
  await sendChatMessage(page, '분석해줘');
  await page.waitForTimeout(2000);
  const ta = page.locator('textarea[placeholder*="물어보세요"]');
  const enabled = !(await ta.isDisabled());
  const text = (await page.locator('body').innerText()) || '';
  const hasGuide = /(상권|선택|어디|지역)/.test(text);
  const errors = packet.consoleEntries.filter((e) => e.startsWith('[error]')).length;
  packet.writeAutoVerdict({
    result: enabled && hasGuide && errors === 0 ? 'PASS' : 'FAIL',
    reason: `enabled=${enabled} guide=${hasGuide} errors=${errors}`,
    checks: [
      { criterion: 'textarea 재활성', met: enabled, evidence: `${enabled}` },
      { criterion: '안내 텍스트', met: hasGuide, evidence: hasGuide ? 'present' : 'absent' },
      { criterion: 'errors 0', met: errors === 0, evidence: `${errors}` },
    ],
  });
  await packet.finalize(page);
  expect(enabled).toBe(true);
});
