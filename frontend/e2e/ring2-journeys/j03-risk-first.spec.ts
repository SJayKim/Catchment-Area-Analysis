/**
 * Ring 2 — J03 Risk-first owner
 *
 * "내 저축 날리지 않을까?"
 * F01 → F08 → F07 → F03
 */

import { test, expect, waitForMapReady, sendChatMessage } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { waitForCardText } from '../helpers/waitSSE';

test.beforeAll(() => ensureRunDir());
test.setTimeout(300000);

test('J03 risk-first — 건대 risk → recommend safer → confirm summary', async ({ page }) => {
  const packet = new EvalPacket({
    id: 'J03-risk-first',
    title: '리스크 우선: 건대 위험 → 안전 추천 → 요약',
    story: '건대입구에서 위험성을 먼저 묻고 안전한 업종 추천을 받은 후 요약으로 컨펌.',
    steps: [
      '"건대입구 위험해?" 리스크',
      '"그럼 뭐하면 덜 위험해?" 추천',
      '"건대입구 분석해줘" 요약',
    ],
    mode: 'Mock',
    ring: 2,
    feature: 'F08+F07+F03',
    criteria: [
      'DOM에 안정성/생존/리스크/위험 키워드',
      'DOM에 추천/업종 키워드',
      'DOM에 유동인구 키워드',
      '에러 0',
    ],
  });
  packet.attach(page);
  await page.goto('/app');
  await waitForMapReady(page);

  await sendChatMessage(page, '건대입구 위험해?');
  const r1 = await waitForCardText(page, ['안정성', '생존', '리스크', '위험'], 60000);

  await sendChatMessage(page, '그럼 뭐하면 덜 위험해?');
  const r2 = await waitForCardText(page, ['추천', '업종'], 60000);

  await sendChatMessage(page, '건대입구 분석해줘');
  const r3 = await waitForCardText(page, ['유동인구'], 60000);

  const errors = packet.consoleEntries.filter((e) => e.startsWith('[error]')).length;
  packet.writeAutoVerdict({
    result: r1.found && r2.found && r3.found ? 'PASS' : 'FAIL',
    reason: `risk=${r1.found} recommend=${r2.found} summary=${r3.found} errors=${errors}`,
    checks: [
      { criterion: '리스크 키워드', met: r1.found, evidence: r1.matched || 'absent' },
      { criterion: '추천 응답', met: r2.found, evidence: r2.matched || 'absent' },
      { criterion: '요약 응답', met: r3.found, evidence: r3.matched || 'absent' },
      { criterion: 'errors 0', met: errors === 0, evidence: `${errors}` },
    ],
  });
  await packet.finalize(page);
  expect(r1.found).toBe(true);
});
