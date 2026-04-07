/**
 * Ring 1 — F03 상권 기본 리포트 (SummaryCard)
 */

import { test, expect } from '@playwright/test';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { waitForMapReady, sendChatMessage } from '../helpers/setup';
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
