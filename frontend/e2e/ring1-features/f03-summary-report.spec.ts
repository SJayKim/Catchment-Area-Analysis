/**
 * Ring 1 — F03 상권 기본 리포트 (SummaryCard)
 */

import { test, expect, waitForMapReady, sendChatMessage } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { waitForCardText } from '../helpers/waitSSE';

test.beforeAll(() => ensureRunDir());

test.describe('Ring 1 — F03 Summary Report', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('F03-H1 강남역 요약 → 4 라벨 + 수치', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F03-H1-summary-gangnam',
      title: '강남역 요약 카드 4개 라벨',
      story: '강남역 요약 시 유동인구/매출/점포/Top업종을 한 번에 보여줘야 한다.',
      steps: ['"강남역 분석해줘" 전송', 'card 키워드 4개 검사'],
      mode: 'Mock',
      ring: 1,
      feature: 'F03',
      criteria: ['유동인구 라벨', 'Top 업종', '매출 또는 점포 키워드', '분석 코멘트 ≥30자'],
    });
    packet.attach(page);
    await sendChatMessage(page, '강남역 상권 분석해줘');
    const r1 = await waitForCardText(page, ['유동인구'], 30000);
    const r2 = await waitForCardText(page, ['Top', '업종'], 5000);
    const r3 = await waitForCardText(page, ['매출', '점포'], 5000);
    const text = (await page.locator('body').innerText()) || '';
    const commentLen = text.length;
    packet.writeAutoVerdict({
      result: r1.found && r3.found && commentLen > 100 ? 'PASS' : 'FAIL',
      reason: `유동인구=${r1.found} Top=${r2.found} 매출/점포=${r3.found} text=${commentLen}b`,
      checks: [
        { criterion: '유동인구', met: r1.found, evidence: r1.matched || 'absent' },
        { criterion: 'Top 업종', met: r2.found, evidence: r2.matched || 'absent' },
        { criterion: '매출/점포', met: r3.found, evidence: r3.matched || 'absent' },
      ],
    });
    expect(r1.found).toBe(true);
    await packet.finalize(page);
  });

  test('F03-H2 데이터 출처/기준 분기 명시', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F03-H2-citation',
      title: '데이터 기준 분기 표시',
      story: '응답에 데이터 기준 분기(예: 2025Q3 또는 2025년 3분기)가 표시되어야 한다.',
      steps: ['"강남역 분석" 전송', 'DOM에 분기 표기'],
      mode: 'Mock',
      ring: 1,
      feature: 'F03',
      criteria: ['DOM에 2025 + 분기 키워드 (Q3/Q4/3분기/4분기)'],
    });
    packet.attach(page);
    await sendChatMessage(page, '강남역 분석해줘');
    const r = await waitForCardText(page, ['2025'], 30000);
    const text = (await page.locator('body').innerText()) || '';
    const quarterMatch = /2025.*(Q[34]|[34]분기)/i.test(text);
    packet.writeAutoVerdict({
      result: r.found && quarterMatch ? 'PASS' : 'FAIL',
      reason: `2025 found=${r.found}, quarter pattern=${quarterMatch}`,
      checks: [
        { criterion: '2025 표기', met: r.found, evidence: r.matched || 'absent' },
        { criterion: '분기 패턴', met: quarterMatch, evidence: quarterMatch ? 'matched' : 'no match' },
      ],
    });
    await packet.finalize(page);
  });

  test('F03-H4 monthly_sales 키 회귀 (4dbd598 _enrich_sales 변경)', async ({ page }) => {
    // 2026-04-19: estimated_sales._enrich_sales 가 분기 매출 → 월매출(/3) 변환 후
    // monthly_sales / total_monthly_sales 키로 통일. 분기 단위 노출되면 3배 과표시.
    const packet = new EvalPacket({
      id: 'F03-H4-monthly-sales-key',
      title: 'monthly_sales 키 회귀',
      story: '강남역 요약 응답의 card payload 에 monthly_sales (또는 total_monthly_sales) 키가 있고 값은 월 스케일이어야 한다.',
      steps: ['POST /api/chat — 강남역 분석', 'SSE card 이벤트의 data.monthly_sales 검증'],
      mode: 'Both',
      ring: 1,
      feature: 'F03',
      criteria: ['card payload 에 monthly_sales|total_monthly_sales 키', '값 > 0', '월 스케일 (< 100조)'],
    });
    packet.attach(page);

    const backend = process.env.E2E_BACKEND_URL || 'http://localhost:8002';
    // Mock 은 D3001, Real 은 3120189 처럼 code 가 모드별로 다름. 런타임에 /api/districts
    // 에서 강남역을 검색해 실제 code 를 사용 (mode=Both 이기 때문).
    const districtsResp = await page.request.get(
      `${backend}/api/districts?search=%EA%B0%95%EB%82%A8%EC%97%AD`
    );
    const districtsJson = await districtsResp.json();
    const gangnamItem =
      districtsJson.items?.find((d: { district_name: string }) => d.district_name === '강남역') ??
      districtsJson.items?.[0];
    const districtCode = gangnamItem?.district_code as string | undefined;

    const resp = await page.request.post(`${backend}/api/chat`, {
      data: { message: '강남역 분석해줘', district_code: districtCode },
      headers: { Accept: 'text/event-stream' },
      timeout: 60000,
    });
    const body = await resp.text();

    // MarketScope SSE: 매 줄이 `data: {...}` (event: 라인 없음).
    // card_type=summary 이벤트의 data 블록에서 monthly_sales / monthlySales 추출.
    // CRLF/LF 양쪽 대응 — split 으로 라인 분해 후 직접 JSON.parse.
    const cardLines = body
      .split(/\r?\n/)
      .filter((l) => l.startsWith('data:') && l.includes('"card_type"') && l.includes('summary'));
    const cardMatches = cardLines.map((l) => [l, l.replace(/^data:\s*/, '').trim()] as const);
    let hasMonthlyKey = false;
    let monthlyValue = 0;
    for (const m of cardMatches) {
      try {
        const evt = JSON.parse(m[1]);
        const data = evt?.data || evt;
        const v =
          data?.monthlySales ??
          data?.monthly_sales ??
          data?.total_monthly_sales ??
          data?.totalMonthlySales ??
          data?.sales?.monthly_sales ??
          data?.sales?.total_monthly_sales;
        if (typeof v === 'number' && v > 0) {
          hasMonthlyKey = true;
          monthlyValue = v;
          break;
        }
      } catch {
        /* skip */
      }
    }
    const rangeOk = monthlyValue > 0 && monthlyValue < 1e14;

    packet.writeAutoVerdict({
      result: hasMonthlyKey && rangeOk ? 'PASS' : 'FAIL',
      reason: `hasKey=${hasMonthlyKey} value=${monthlyValue}`,
      checks: [
        { criterion: 'monthly_sales 키', met: hasMonthlyKey, evidence: `${monthlyValue}` },
        { criterion: '월 스케일', met: rangeOk, evidence: `${monthlyValue}` },
      ],
    });
    expect(hasMonthlyKey).toBe(true);
    await packet.finalize(page);
  });

  test('F03-H3 후속 제안 칩 ≥1', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F03-H3-suggestions',
      title: '후속 제안 칩 표시',
      story: '응답 카드 하단에 후속 질문 칩이 표시되어야 한다.',
      steps: ['"강남역 분석" 전송', '클릭 가능한 칩 카운트'],
      mode: 'Mock',
      ring: 1,
      feature: 'F03',
      criteria: ['DOM에 추천/제안 또는 비교 등 후속 키워드'],
    });
    packet.attach(page);
    await sendChatMessage(page, '강남역 분석해줘');
    await page.waitForTimeout(2000);
    const text = (await page.locator('body').innerText()) || '';
    // Suggestion chips contain 추천, 비교, 위험 etc keywords
    const suggestionKeywords = ['비교', '추천', '위험', '뭐', '카페', '시뮬레이션'];
    const hits = suggestionKeywords.filter((k) => text.includes(k)).length;
    packet.writeAutoVerdict({
      result: hits >= 2 ? 'PASS' : 'FAIL',
      reason: `${hits} suggestion keywords matched`,
      checks: [{ criterion: 'suggestion ≥2 keyword', met: hits >= 2, evidence: `${hits} hits` }],
    });
    await packet.finalize(page);
  });
});
