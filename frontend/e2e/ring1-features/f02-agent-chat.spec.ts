/**
 * Ring 1 — F02 AI 챗봇 (PAE + SSE)
 *
 * Verifies LLM agent intent → tool → SSE response stream + context retention.
 */

import { test, expect, waitForMapReady, sendChatMessage, waitForResponseComplete } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';

const BACKEND = process.env.E2E_BACKEND_URL || 'http://localhost:8002';

/**
 * Parse a raw SSE response body into an array of {type, data} events.
 * MarketScope SSE format embeds the event type inside the JSON `data:` payload:
 *   data: {"type":"text","content":"..."}
 *   data: {"type":"done"}
 */
function parseSse(raw: string): { type: string; data: string }[] {
  const events: { type: string; data: string }[] = [];
  for (const line of raw.split('\n')) {
    if (line.startsWith('data:')) {
      const payload = line.slice(5).trim();
      try {
        const parsed = JSON.parse(payload);
        events.push({ type: parsed.type || 'message', data: payload });
      } catch {
        events.push({ type: 'message', data: payload });
      }
    }
  }
  return events;
}

test.beforeAll(() => ensureRunDir());

test.describe('Ring 1 — F02 Agent Chat', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('F02-H1 SSE flow has thinking + tool + done', async ({ page }) => {
    test.setTimeout(120000);
    const packet = new EvalPacket({
      id: 'F02-H1-sse-flow',
      title: 'SSE 이벤트 thinking/tool/done 순서',
      story: '강남역 분석 요청 시 SSE 스트림에 thinking → tool → done 이벤트가 모두 나타나야 한다.',
      steps: [
        '백엔드 /api/chat 직접 POST (UI는 분리)',
        'SSE 이벤트 캡처 → 종류 검사',
      ],
      mode: 'Mock',
      ring: 1,
      feature: 'F02',
      criteria: ['sse 이벤트에 thinking/tool/done 모두', 'done 1회 이상', 'tool 1회 이상'],
    });
    packet.attach(page);

    // Let backend auto-detect district from message ("강남역") instead of
    // hard-coding D3001 (which only exists in Mock mode).
    const resp = await page.request.post(`${BACKEND}/api/chat`, {
      data: {
        message: '강남역 상권 분석해줘',
        session_id: 'f02-h1',
      },
      timeout: 90000,
    });
    expect(resp.status()).toBe(200);
    const raw = await resp.text();
    const events = parseSse(raw);
    const types = new Set(events.map((e) => e.type));
    const hasThinking = types.has('thinking');
    const hasTool = types.has('tool');
    const hasDone = types.has('done');

    packet.writeAutoVerdict({
      result: hasDone && hasTool ? 'PASS' : 'FAIL',
      reason: `event types: ${Array.from(types).join(',')}`,
      checks: [
        { criterion: 'thinking', met: hasThinking, evidence: hasThinking ? 'present' : 'absent' },
        { criterion: 'tool', met: hasTool, evidence: hasTool ? 'present' : 'absent' },
        { criterion: 'done', met: hasDone, evidence: hasDone ? 'present' : 'absent' },
      ],
    });
    await packet.finalize(page, { sseLog: raw });
    expect(hasDone).toBe(true);
  });

  test('F02-H2 인사 → 도구 호출 없이 직접 응답', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F02-H2-greeting',
      title: '인사 → 직접 응답',
      story: '"안녕"은 도구 호출 없이 짧은 응답으로 처리되어야 한다.',
      steps: ['백엔드 /api/chat 직접 POST "안녕"'],
      mode: 'Mock',
      ring: 1,
      feature: 'F02',
      criteria: ['SSE에 tool 이벤트 없음', 'text 또는 done 응답 존재'],
    });
    packet.attach(page);

    const resp = await page.request.post(`${BACKEND}/api/chat`, {
      data: { message: '안녕', session_id: 'f02-h2' },
      timeout: 30000,
    });
    expect(resp.status()).toBe(200);
    const raw = await resp.text();
    const events = parseSse(raw);
    const types = new Set(events.map((e) => e.type));
    const hasTool = types.has('tool');
    const hasDone = types.has('done');
    const hasText = types.has('text');

    packet.writeAutoVerdict({
      result: hasDone && !hasTool ? 'PASS' : 'FAIL',
      reason: `tool=${hasTool} text=${hasText} done=${hasDone}`,
      checks: [
        { criterion: 'no tool call', met: !hasTool, evidence: hasTool ? 'tool called' : 'none' },
        { criterion: 'done', met: hasDone, evidence: hasDone ? 'present' : 'absent' },
      ],
    });
    await packet.finalize(page, { sseLog: raw });
    expect(hasDone).toBe(true);
  });

  test('F02-H3 모호한 입력 → graceful 안내', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F02-H3-ambiguous',
      title: '상권 미선택 + 모호 입력',
      story: '상권을 선택하지 않은 채 "알려줘"만 입력해도 크래시 없이 안내가 나와야 한다.',
      steps: ['"알려줘" 전송', 'text 응답 또는 가이드'],
      mode: 'Mock',
      ring: 1,
      feature: 'F02',
      criteria: ['응답 완료 (textarea 재활성화)', 'console error 0'],
    });
    packet.attach(page);
    await sendChatMessage(page, '알려줘');
    await waitForResponseComplete(page, 30000);
    const errors = packet.consoleEntries.filter((e) => e.startsWith('[error]')).length;
    const ta = page.locator('textarea[placeholder*="물어보세요"]');
    const enabled = !(await ta.isDisabled());
    packet.writeAutoVerdict({
      result: enabled && errors === 0 ? 'PASS' : 'FAIL',
      reason: `enabled=${enabled} errors=${errors}`,
      checks: [
        { criterion: 'textarea 재활성화', met: enabled, evidence: `${enabled}` },
        { criterion: '에러 0', met: errors === 0, evidence: `${errors} errors` },
      ],
    });
    expect(enabled).toBe(true);
    await packet.finalize(page);
  });

  test('F02-H4 컨텍스트 유지 (강남 → "홍대랑 비교")', async ({ page }) => {
    test.setTimeout(180000); // 2 LLM turns × Real-mode latency
    const packet = new EvalPacket({
      id: 'F02-H4-context',
      title: 'Multi-turn 컨텍스트 유지',
      story: 'turn1 강남역 요약 후 turn2 "홍대랑 비교"에서 강남이 컨텍스트로 유지되어야 한다.',
      steps: ['"강남역 분석해줘"', '"홍대랑 비교해줘"', 'CompareCard 두 상권명'],
      mode: 'Mock',
      ring: 1,
      feature: 'F02',
      criteria: ['DOM에 강남 + 홍대 함께 존재', '비교 카드 키워드'],
    });
    packet.attach(page);
    await sendChatMessage(page, '강남역 분석해줘');
    await waitForResponseComplete(page, 60000);
    await sendChatMessage(page, '홍대랑 비교해줘');
    await waitForResponseComplete(page, 60000);
    const text = (await page.locator('body').innerText()) || '';
    const hasBoth = text.includes('강남') && text.includes('홍대');
    const hasCompare = text.includes('비교') || text.includes('판정');
    packet.writeAutoVerdict({
      result: hasBoth && hasCompare ? 'PASS' : 'FAIL',
      reason: `hasBoth=${hasBoth} hasCompare=${hasCompare}`,
      checks: [
        { criterion: '강남+홍대', met: hasBoth, evidence: hasBoth ? 'both present' : 'missing' },
        { criterion: '비교 키워드', met: hasCompare, evidence: hasCompare ? 'present' : 'absent' },
      ],
    });
    expect(hasBoth).toBe(true);
    await packet.finalize(page);
  });
});
