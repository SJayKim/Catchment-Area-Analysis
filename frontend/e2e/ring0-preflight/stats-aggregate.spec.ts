/**
 * Ring 0 — Langfuse aggregate stats 회귀 (Plan langfuse-aggregate-stats-2026-04-28)
 *
 * Phase 1+2 변경이 SSE 페이로드/응답 시간에 영향을 주지 않으면서
 * `done.trace_id` 가 동봉되고 (Langfuse on 시) graceful degrade 가 유지되는지 확인.
 *
 * 검증 범위:
 *   AGG-01  POST /api/chat → SSE done.trace_id 존재 (32-hex)
 *   AGG-02  done.quality_match_rate optional 직렬화 무결
 *   AGG-03  greeting 분기에서도 5xx 없이 정상 종료
 *   AGG-04  SSE raw 에 `event:` 라인 신설 0 (포맷 불변)
 *
 * Stack: dev compose (USE_MOCK 무관, backend=8000). Langfuse on/off 자동 분기 —
 * 키 없으면 trace_id 미동봉이 정상.
 */

import { test, expect } from '../helpers/setup';
import * as http from 'node:http';

const BACKEND = process.env.E2E_BACKEND_URL || 'http://localhost:8000';

interface SseResult {
  status: number;
  raw: string;
  events: Array<Record<string, unknown>>;
  done: Record<string, unknown> | null;
}

async function postSse(
  body: Record<string, unknown>,
  timeoutMs: number = 90_000,
): Promise<SseResult> {
  const url = new URL(`${BACKEND}/api/chat`);
  const payload = Buffer.from(JSON.stringify(body), 'utf-8');

  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        method: 'POST',
        hostname: url.hostname,
        port: url.port,
        path: url.pathname + url.search,
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': payload.length.toString(),
          Accept: 'text/event-stream',
        },
      },
      (res) => {
        const chunks: Buffer[] = [];
        const timer = setTimeout(() => {
          try {
            res.destroy();
          } catch {
            /* ignore */
          }
          finalize();
        }, timeoutMs);

        const finalize = () => {
          clearTimeout(timer);
          const raw = Buffer.concat(chunks).toString('utf-8');
          const events: Array<Record<string, unknown>> = [];
          for (const line of raw.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            try {
              events.push(JSON.parse(line.slice(6)));
            } catch {
              /* skip malformed */
            }
          }
          const done = events.find((e) => e.type === 'done') || null;
          resolve({ status: res.statusCode || 0, raw, events, done });
        };

        res.on('data', (chunk: Buffer) => {
          chunks.push(chunk);
          const raw = Buffer.concat(chunks).toString('utf-8');
          if (/data:\s*\{[^\n]*"type":\s*"done"[^\n]*\}\s*\n\s*\n/.test(raw)) {
            try {
              res.destroy();
            } catch {
              /* ignore */
            }
            finalize();
          }
        });
        res.on('end', finalize);
        res.on('error', (e) => {
          clearTimeout(timer);
          reject(e);
        });
      },
    );
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

test.describe('Ring 0 — Langfuse aggregate stats', () => {
  test('AGG-01 chat SSE round-trip 정상 + done.trace_id 동봉', async () => {
    test.setTimeout(120_000);

    const res = await postSse({
      message: '강남역 분석해줘',
      session_id: 'agg-stats-e2e-1',
      district_code: '3110023',
    });

    expect(res.status).toBe(200);
    expect(res.events.length).toBeGreaterThanOrEqual(5);
    expect(res.done).not.toBeNull();

    // Langfuse 활성/비활성 모두 done 이벤트는 발행. 활성 시 trace_id 가 32-hex.
    const traceId = res.done?.trace_id as string | undefined;
    if (traceId) {
      expect(traceId).toMatch(/^[a-f0-9]{16,64}$/);
    }
  });

  test('AGG-02 done.quality_match_rate 가 number 또는 부재', async () => {
    test.setTimeout(120_000);

    const res = await postSse({
      message: '강남역 분석해줘',
      session_id: 'agg-stats-e2e-2',
      district_code: '3110023',
    });

    expect(res.done).not.toBeNull();
    const qmr = res.done?.quality_match_rate;
    if (qmr !== undefined) {
      expect(typeof qmr).toBe('number');
      expect(qmr).toBeGreaterThanOrEqual(0);
      expect(qmr).toBeLessThanOrEqual(1.0001); // 부동소수 여유
    }
  });

  test('AGG-03 greeting 분기 — 5xx 없이 종료', async () => {
    test.setTimeout(60_000);

    const res = await postSse({
      message: '안녕하세요',
      session_id: 'agg-stats-e2e-greet',
    });

    expect(res.status).toBe(200);
    expect(res.done).not.toBeNull();
    // greeting 은 quality_match_rate 미발행이 정상 (numeric_sanity 미실행)
  });

  test('AGG-04 SSE raw 에 `event:` 라인 신설 0', async () => {
    test.setTimeout(60_000);

    const res = await postSse({
      message: '안녕',
      session_id: 'agg-stats-e2e-fmt',
    });

    expect(/^event:/m.test(res.raw)).toBe(false);
    // data: 라인이 최소 1개 (done 포함)
    expect((res.raw.match(/^data: /gm) || []).length).toBeGreaterThanOrEqual(1);
  });
});
