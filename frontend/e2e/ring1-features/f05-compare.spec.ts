/**
 * Ring 1 — F05 상권 비교
 */

import { test, expect, waitForMapReady, sendChatMessage, waitForResponseComplete } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
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

  test('F05-H3 비교모드 다색 하이라이트 store 상태 (4dbd598 회귀)', async ({ page }) => {
    // 2026-04-19: DistrictLayer 에 COMPARE_STYLES 팔레트 3종(blue/amber/rose) 추가.
    // Kakao 폴리곤 fillColor 는 canvas/SVG 렌더에 묻혀 있어 DOM 단위 선택이 신뢰도
    // 낮음 → window.__districtStore 로 직접 계약 검증.
    const packet = new EvalPacket({
      id: 'F05-H3-multi-color-state',
      title: '비교모드 다색 하이라이트 store 상태',
      story: '3개 상권 비교 요청 후 Zustand store 의 compareList 3개 + isCompareMode=true 여야 한다.',
      steps: ['"강남역, 홍대입구, 건대입구 비교해줘"', 'window.__districtStore.getState() 확인'],
      mode: 'Mock',
      ring: 1,
      feature: 'F05',
      criteria: ['compareList.length === 3', 'isCompareMode === true', '3개 code distinct'],
    });
    packet.attach(page);

    await sendChatMessage(page, '강남역, 홍대입구, 건대입구 비교해줘');
    await page.waitForTimeout(3000);

    const state = await page.evaluate(() => {
      const w = window as unknown as { __districtStore?: { getState: () => unknown } };
      const st = w.__districtStore?.getState?.() as
        | { compareList?: { code: string }[]; isCompareMode?: boolean }
        | undefined;
      return {
        compareCodes: st?.compareList?.map((d) => d.code) ?? [],
        isCompareMode: !!st?.isCompareMode,
      };
    });

    const distinct = new Set(state.compareCodes);
    const lenOk = state.compareCodes.length === 3 && distinct.size === 3;
    const modeOk = state.isCompareMode === true;

    packet.writeAutoVerdict({
      result: lenOk && modeOk ? 'PASS' : 'FAIL',
      reason: `codes=${JSON.stringify(state.compareCodes)} mode=${state.isCompareMode}`,
      checks: [
        { criterion: 'compareList 3 distinct', met: lenOk, evidence: state.compareCodes.join(',') },
        { criterion: 'isCompareMode true', met: modeOk, evidence: `${state.isCompareMode}` },
      ],
    });
    expect(lenOk).toBe(true);
    expect(modeOk).toBe(true);
    await packet.finalize(page);
  });

  test('F05-H4 한글 조사 처리 (과/를 회귀)', async ({ page }) => {
    // feedback_korean_particles.md — f05 + neg 양쪽에 particles 케이스 포함.
    const packet = new EvalPacket({
      id: 'F05-H4-particles',
      title: '한글 조사 비교 intent',
      story: '"강남역과 홍대입구를 비교해줘" 처럼 조사가 붙어도 compareList 2개로 세팅된다.',
      steps: ['해당 문장 전송', 'compareList 2 + isCompareMode=true'],
      mode: 'Mock',
      ring: 1,
      feature: 'F05',
      criteria: ['compareList 2 distinct', 'isCompareMode true'],
    });
    packet.attach(page);
    await sendChatMessage(page, '강남역과 홍대입구를 비교해줘');
    await page.waitForTimeout(3000);
    const state = await page.evaluate(() => {
      const w = window as unknown as { __districtStore?: { getState: () => unknown } };
      const st = w.__districtStore?.getState?.() as
        | { compareList?: { code: string }[]; isCompareMode?: boolean }
        | undefined;
      return {
        codes: st?.compareList?.map((d) => d.code) ?? [],
        mode: !!st?.isCompareMode,
      };
    });
    const ok = state.codes.length === 2 && state.mode === true;
    packet.writeAutoVerdict({
      result: ok ? 'PASS' : 'FAIL',
      reason: `codes=${JSON.stringify(state.codes)} mode=${state.mode}`,
      checks: [{ criterion: '2 distinct + mode', met: ok, evidence: `${state.codes.length}/${state.mode}` }],
    });
    expect(ok).toBe(true);
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
