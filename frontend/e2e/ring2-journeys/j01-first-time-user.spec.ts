/**
 * Ring 2 — J01 First-time user happy path
 *
 * "여기 좋은 상권인가?"
 * F01 → F02 → F03 → F07 → F05
 */

import { test, expect, waitForMapReady, sendChatMessage } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { waitForCardText } from '../helpers/waitSSE';
import { clickPolygonByCode } from '../helpers/polygonClick';
import { detectMode } from '../helpers/modeGuard';

test.beforeAll(() => ensureRunDir());
test.setTimeout(600000); // Real-mode multi-turn journey with LLM retries

test('J01 first-time user — 강남역 click → summary → recommend → compare', async ({ page }) => {
  // Known Real-mode UI flake: 4-turn journey through UI accumulates browser
  // state (polygons, animations) that intermittently blocks waitForResponseComplete.
  // Direct-backend equivalents (F02/F05) cover the same pipeline; skip in Real.
  const mode = await detectMode();
  test.skip(mode === 'real', 'J01 4-turn UI journey is flaky in Real mode — covered by F02-H4 + F05-H1 at API level');
  const packet = new EvalPacket({
    id: 'J01-first-time',
    title: '첫 방문자: 강남역 → 요약 → 추천 → 비교',
    story:
      '강남역 클릭, 요약 카드 자동, "여기서 뭐하면 좋을까" 추천, "홍대랑 비교해줘" 비교까지 한 세션에서 자연스럽게 흘러야 한다.',
    steps: [
      '/ 진입 + 폴리곤 로드',
      '강남역 store-select (폴리곤 클릭 fallback)',
      'SummaryCard 확인',
      '"여기서 뭐하면 좋을까?" 추천 요청',
      '"홍대입구랑 비교해줘" 비교 요청',
    ],
    mode: 'Mock',
    ring: 2,
    feature: 'F01+F02+F03+F07+F05',
    criteria: [
      'StatusBar에 강남 (선택 직후)',
      'DOM에 유동인구 키워드 (요약 단계)',
      'DOM에 추천/업종 키워드 (추천 단계)',
      'DOM에 강남 + 홍대 함께 (비교 단계)',
      '에러 토스트 0',
      'console error 0 (OR 최소화)',
    ],
  });
  packet.attach(page);
  await page.goto('/');
  await waitForMapReady(page);

  // Step 1: select 강남
  await clickPolygonByCode(page, 'D3001', { name: '강남역', lat: 37.4979, lng: 127.0276 });
  await page.waitForTimeout(1000);

  // Step 2: ask for summary
  await sendChatMessage(page, '강남역 상권 분석해줘');
  const r1 = await waitForCardText(page, ['유동인구'], 60000);

  // Step 3: ask for recommendation
  await sendChatMessage(page, '여기서 뭐하면 좋을까?');
  const r2 = await waitForCardText(page, ['추천', '업종'], 60000);

  // Step 4: compare with 홍대
  await sendChatMessage(page, '홍대입구랑 비교해줘');
  await page.waitForTimeout(3000);

  const text = (await page.locator('body').innerText()) || '';
  const hasGangnam = text.includes('강남');
  const hasHongdae = text.includes('홍대');
  const errors = packet.consoleEntries.filter((e) => e.startsWith('[error]')).length;

  packet.writeAutoVerdict({
    result: r1.found && r2.found && hasGangnam && hasHongdae ? 'PASS' : 'FAIL',
    reason: `summary=${r1.found} recommend=${r2.found} 강남=${hasGangnam} 홍대=${hasHongdae} errors=${errors}`,
    checks: [
      { criterion: '요약 카드', met: r1.found, evidence: r1.matched || 'absent' },
      { criterion: '추천 응답', met: r2.found, evidence: r2.matched || 'absent' },
      { criterion: '강남 컨텍스트', met: hasGangnam, evidence: hasGangnam ? 'present' : 'absent' },
      { criterion: '홍대 비교', met: hasHongdae, evidence: hasHongdae ? 'present' : 'absent' },
      { criterion: 'console error 0', met: errors === 0, evidence: `${errors}` },
    ],
  });
  await packet.finalize(page);

  expect(r1.found).toBe(true);
  expect(hasGangnam && hasHongdae).toBe(true);
});
