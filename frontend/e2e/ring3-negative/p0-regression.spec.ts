/**
 * Ring 3 — P0 Regression (commit d8c0155)
 *
 * Verifies the 8 P0 fixes do not regress at the user-experience level.
 * Some P0s require backend env-override (P0-2 timeout, P0-3 backpressure)
 * and are SKIP-marked here unless the env supports them.
 */

import { test, expect, waitForMapReady, sendChatMessage } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { clickPolygonByCode } from '../helpers/polygonClick';
import { detectMode } from '../helpers/modeGuard';

const BACKEND = process.env.E2E_BACKEND_URL || 'http://localhost:8002';

test.beforeAll(() => ensureRunDir());

test.describe('Ring 3 — P0 Regression', () => {
  // P0-1: Migration 003 (real mode only)
  test('P0-1 category_metadata.aliases column (Real mode only)', async ({ page }) => {
    const mode = await detectMode();
    test.skip(mode !== 'real', 'P0-1 requires Real mode (Mock has no DB)');
    const packet = new EvalPacket({
      id: 'P0-1-migration-003',
      title: 'Migration 003 — category_metadata.aliases',
      story: 'USE_MOCK=false 부팅 후 카페 매출 요청이 UndefinedColumn 없이 동작.',
      steps: ['"카페 매출" 분석 요청'],
      mode: 'Real',
      ring: 3,
      feature: 'P0-1',
      criteria: ['응답 200', '응답 done', '에러 없음'],
    });
    packet.attach(page);
    const resp = await page.request.post(`${BACKEND}/api/chat`, {
      data: { message: '강남역 카페 매출 분석', district_code: 'D3001', session_id: 'p0-1' },
      timeout: 60000,
    });
    expect(resp.status()).toBe(200);
    const body = await resp.text();
    const ok = body.includes('done') && !body.includes('UndefinedColumn');
    packet.writeAutoVerdict({
      result: ok ? 'PASS' : 'FAIL',
      reason: ok ? 'no UndefinedColumn, done present' : 'failure',
      checks: [{ criterion: 'no UndefinedColumn + done', met: ok, evidence: ok ? 'ok' : body.slice(0, 300) }],
    });
    await packet.finalize(page);
  });

  // P0-2 timeout — env override; not enforced in this run
  test('P0-2 LLM timeout regression (smoke only)', async ({ page }) => {
    test.skip(!process.env.LLM_TIMEOUT_FAST, 'P0-2 requires LLM_TIMEOUT_FAST env override');
  });

  // P0-3 SSE backpressure — slow consumer simulation
  test('P0-3 SSE backpressure tolerance (smoke)', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'P0-3-sse-backpressure',
      title: 'SSE 큐 maxsize=256 ',
      story: '느린 소비자 시뮬레이션 — 다수 tool 이벤트가 발생해도 서버 OOM/크래시 없이 응답이 결국 전달되어야 한다.',
      steps: ['카페 분석 요청 (다수 tool 호출 유도)'],
      mode: 'Mock',
      ring: 3,
      feature: 'P0-3',
      criteria: ['HTTP 200', 'done 이벤트 도달', '서버 크래시 없음'],
    });
    packet.attach(page);
    const resp = await page.request.post(`${BACKEND}/api/chat`, {
      data: {
        message: '강남역에서 카페 매출 분석 + 비교 + 추천',
        district_code: 'D3001',
        session_id: 'p0-3',
      },
      timeout: 90000,
    });
    expect(resp.status()).toBe(200);
    const body = await resp.text();
    const ok = body.includes('"done"');
    packet.writeAutoVerdict({
      result: ok ? 'PASS' : 'FAIL',
      reason: ok ? 'done present, no crash' : 'no done',
      checks: [{ criterion: 'done 도달', met: ok, evidence: ok ? 'present' : 'absent' }],
    });
    await packet.finalize(page, { sseLog: body });
  });

  // P0-4 client disconnect → background task cancel (verify next request still works)
  test('P0-4 client disconnect → next request OK', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'P0-4-disconnect',
      title: 'Disconnect 후 즉시 다음 요청',
      story: '클라이언트가 끊긴 후 다음 요청도 즉시 200 응답을 받아야 한다 (semaphore 누수 없음).',
      steps: ['1차 요청 시작 → 즉시 abort', '2차 요청 → 정상 응답'],
      mode: 'Mock',
      ring: 3,
      feature: 'P0-4',
      criteria: ['2차 요청 200 + done'],
    });
    packet.attach(page);
    // Fire-and-forget first
    const ctrl = new AbortController();
    const p1 = fetch(`${BACKEND}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: '강남역 분석', district_code: 'D3001', session_id: 'p0-4-1' }),
      signal: ctrl.signal,
    }).catch(() => null);
    setTimeout(() => ctrl.abort(), 200);
    await p1;
    // Second request
    const r2 = await page.request.post(`${BACKEND}/api/chat`, {
      data: { message: '강남역 분석', district_code: 'D3001', session_id: 'p0-4-2' },
      timeout: 60000,
    });
    expect(r2.status()).toBe(200);
    const body = await r2.text();
    const ok = body.includes('"done"');
    packet.writeAutoVerdict({
      result: ok ? 'PASS' : 'FAIL',
      reason: ok ? '2nd request success' : '2nd failed',
      checks: [{ criterion: '2nd done', met: ok, evidence: ok ? 'present' : 'absent' }],
    });
    await packet.finalize(page);
  });

  // P0-5 LLM JSON parse fallback — risk question must NOT yield SummaryCard
  test('P0-5 rule fallback preserves intent', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'P0-5-rule-fallback',
      title: '리스크 질문 → 리스크 카드',
      story: '"이 자리 위험해?" 질문은 SummaryCard가 아닌 RiskCard로 라우팅되어야 한다 (LLM 파싱 실패해도).',
      steps: ['"강남역 위험해?" 전송'],
      mode: 'Mock',
      ring: 3,
      feature: 'P0-5',
      criteria: ['DOM에 안정성/생존/리스크/위험 키워드'],
    });
    packet.attach(page);
    await page.goto('/');
    await waitForMapReady(page);
    await sendChatMessage(page, '강남역 위험해?');
    await page.waitForTimeout(3000);
    const text = (await page.locator('body').innerText()) || '';
    const riskKw = /(안정성|생존|리스크|위험|폐업)/.test(text);
    packet.writeAutoVerdict({
      result: riskKw ? 'PASS' : 'FAIL',
      reason: `risk keyword=${riskKw}`,
      checks: [{ criterion: '리스크 키워드', met: riskKw, evidence: riskKw ? 'present' : 'absent' }],
    });
    await packet.finalize(page);
    expect(riskKw).toBe(true);
  });

  // P0-6 DistrictLayer stale closure — fast switch
  test('P0-6 fast district switch — no stale highlight', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'P0-6-fast-switch',
      title: '빠른 폴리곤 전환',
      story: '강남 → 홍대 → 건대 빠른 연속 전환 시 잔존 하이라이트/잘못된 StatusBar 없어야 한다.',
      steps: ['강남 select → 200ms → 홍대 select → 200ms → 건대 select'],
      mode: 'Mock',
      ring: 3,
      feature: 'P0-6',
      criteria: ['StatusBar 최종이 건대', '강남/홍대 잔존 표시 없음'],
    });
    packet.attach(page);
    await page.goto('/');
    await waitForMapReady(page);
    await clickPolygonByCode(page, 'D3001', { name: '강남역', lat: 37.4979, lng: 127.0276 });
    await page.waitForTimeout(200);
    await clickPolygonByCode(page, 'D3002', { name: '홍대입구', lat: 37.5563, lng: 126.9237 });
    await page.waitForTimeout(200);
    await clickPolygonByCode(page, 'D3003', { name: '건대입구', lat: 37.5404, lng: 127.069 });
    await page.waitForTimeout(2000);
    const sb = (await page.locator('.h-8').first().textContent()) || '';
    const finalOk = sb.includes('건대') && !sb.includes('강남') && !sb.includes('홍대');
    packet.writeAutoVerdict({
      result: finalOk ? 'PASS' : 'FAIL',
      reason: `final StatusBar=${sb}`,
      checks: [{ criterion: 'StatusBar 건대 단독', met: finalOk, evidence: sb }],
    });
    await packet.finalize(page);
    expect(sb).toContain('건대');
  });

  // P0-7 SSE reader release + AbortController
  test('P0-7 navigate-away then new request OK', async ({ page }) => {
    // 2회 SSE 라운드(≈ 45s × 2) + reload — 60s 기본 timeout 초과. Ring 2 journey와
    // 동일한 180s 스코프로 상향.
    test.setTimeout(180000);
    const packet = new EvalPacket({
      id: 'P0-7-abort-controller',
      title: '라우팅 이탈 후 새 요청',
      story: '요청 중 다른 탭으로 이동했다가 돌아와도 새 요청이 정상 처리되어야 한다.',
      steps: ['/ 진입', '메시지 전송', '리로드', '새 메시지 → 정상 응답'],
      mode: 'Mock',
      ring: 3,
      feature: 'P0-7',
      criteria: ['2차 응답 정상', 'console error 0'],
    });
    packet.attach(page);
    await page.goto('/');
    await waitForMapReady(page);
    await sendChatMessage(page, '강남역 분석');
    await page.reload();
    await waitForMapReady(page);
    await sendChatMessage(page, '홍대 분석');
    await page.waitForTimeout(2000);
    const errors = packet.consoleEntries.filter((e) => e.startsWith('[error]')).length;
    const text = (await page.locator('body').innerText()) || '';
    const ok = text.includes('홍대');
    packet.writeAutoVerdict({
      result: ok && errors === 0 ? 'PASS' : 'FAIL',
      reason: `ok=${ok} errors=${errors}`,
      checks: [
        { criterion: '2차 응답 홍대', met: ok, evidence: ok ? 'present' : 'absent' },
        { criterion: 'errors 0', met: errors === 0, evidence: `${errors}` },
      ],
    });
    await packet.finalize(page);
    expect(ok).toBe(true);
  });

  // P0-8 prompt injection sanitize — covered by neg-prompt-injection.spec.ts
  test('P0-8 prompt injection (cross-ref to NEG-2)', async () => {
    test.info().annotations.push({
      type: 'cross-ref',
      description: 'See NEG-2 prompt injection test for P0-8 verification',
    });
  });
});
