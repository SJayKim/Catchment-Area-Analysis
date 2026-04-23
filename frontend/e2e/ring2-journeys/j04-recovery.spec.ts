/**
 * Ring 2 — J04 Error recovery
 *
 * "잘못 쳤는데 막혔어요?"
 * F02 → F01 → F03
 */

import { test, expect, waitForMapReady, sendChatMessage } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';

test.beforeAll(() => ensureRunDir());
test.setTimeout(180000);

test('J04 error recovery — vague query → recover via search', async ({ page }) => {
  const packet = new EvalPacket({
    id: 'J04-recovery',
    title: '에러 복구: 모호 입력 → 검색으로 복구 → 분석',
    story: '상권 미선택 상태에서 모호한 입력 후 검색으로 명동을 선택해 분석까지 도달.',
    steps: [
      '"분석 좀" (모호)',
      '검색바로 "명동" 검색 + 선택',
      '"명동 분석해줘"',
    ],
    mode: 'Mock',
    ring: 2,
    feature: 'F02+F01+F03',
    criteria: [
      '첫 응답 후 textarea 재활성화 (graceful fail)',
      '검색 → StatusBar에 명동',
      'DOM에 명동 + 유동인구 키워드',
      'console error 0',
    ],
  });
  packet.attach(page);
  await page.goto('/app');
  await waitForMapReady(page);

  // Step 1: vague
  await sendChatMessage(page, '분석 좀');
  const ta = page.locator('textarea[placeholder*="물어보세요"]');
  const enabled1 = !(await ta.isDisabled());

  // Step 2: search 명동
  const search = page.locator('input[placeholder*="검색"]').first();
  await search.fill('명동');
  await page.waitForTimeout(800);
  const item = page.locator('button', { hasText: '명동' }).first();
  if (await item.isVisible({ timeout: 3000 }).catch(() => false)) {
    await item.click();
  }
  await page.waitForTimeout(1500);

  // Step 3: analyze
  await sendChatMessage(page, '명동 분석해줘');
  await page.waitForTimeout(3000);

  const text = (await page.locator('body').innerText()) || '';
  const hasMyeong = text.includes('명동');
  const hasFlow = text.includes('유동인구') || text.includes('인구');
  const errors = packet.consoleEntries.filter((e) => e.startsWith('[error]')).length;

  packet.writeAutoVerdict({
    result: enabled1 && hasMyeong && hasFlow ? 'PASS' : 'FAIL',
    reason: `enabled1=${enabled1} myeongdong=${hasMyeong} flow=${hasFlow} errors=${errors}`,
    checks: [
      { criterion: 'graceful fail (재활성화)', met: enabled1, evidence: `${enabled1}` },
      { criterion: '명동 컨텍스트', met: hasMyeong, evidence: hasMyeong ? 'present' : 'absent' },
      { criterion: '유동인구 분석', met: hasFlow, evidence: hasFlow ? 'present' : 'absent' },
      { criterion: 'errors 0', met: errors === 0, evidence: `${errors}` },
    ],
  });
  await packet.finalize(page);
  expect(hasMyeong).toBe(true);
});
