/**
 * Ring 3 — Ops endpoints
 *
 * `/api/health/detail` (DB pool / Redis / session 상태) 와 `/metrics` (요청 카운트 / latency 분위수 / SSE 활성 연결) 엔드포인트의
 * 스키마와 최소 의미를 확인한다. 운영 모니터링 표면의 회귀 방지.
 *
 * 참조:
 *  - server/server/api/routes/chat.py:94  (/api/health/detail)
 *  - server/server/middleware/metrics.py:141 (/metrics)
 */

import { test, expect } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';

const BACKEND = process.env.E2E_BACKEND_URL || 'http://localhost:8002';

test.beforeAll(() => ensureRunDir());

test.describe('Ring 3 — Ops endpoints', () => {
  test('OPS-01-HEALTH-DETAIL /api/health/detail 스키마', async ({ request }) => {
    const packet = new EvalPacket({
      id: 'OPS-01-HEALTH-DETAIL',
      title: '/api/health/detail 스키마',
      story:
        '운영 모니터링 대시보드가 DB pool / Redis / session / agent mode 를 이 엔드포인트로 조회한다. 필드 누락 시 대시보드가 깨지므로 스키마 회귀 방지.',
      steps: [
        'GET /api/health/detail',
        '필수 필드 존재 + 타입 검증',
        'use_mock === true (e2e stack)',
      ],
      mode: 'Mock',
      ring: 3,
      criteria: [
        'HTTP 200',
        '필수 필드 11개 존재',
        'db_pool_* 숫자형',
        'redis_connected boolean',
        'use_mock boolean',
      ],
    });

    const resp = await request.get(`${BACKEND}/api/health/detail`, { timeout: 10000 });
    const status = resp.status();
    const body = await resp.json().catch(() => ({}));

    const required = [
      'db_pool_size',
      'db_pool_checkedout',
      'db_pool_overflow',
      'db_pool_checkedin',
      'redis_connected',
      'agent_mode',
      'llm_provider',
      'use_mock',
      'semaphore_available',
      'semaphore_max',
      'active_sessions',
    ];
    const missing = required.filter((k) => !(k in body));

    const poolNumeric = ['db_pool_size', 'db_pool_checkedout', 'db_pool_overflow', 'db_pool_checkedin']
      .every((k) => typeof body[k] === 'number');
    const redisBool = typeof body.redis_connected === 'boolean';
    const mockBool = typeof body.use_mock === 'boolean';
    const agentModeStr = typeof body.agent_mode === 'string' && body.agent_mode.length > 0;
    const providerStr = typeof body.llm_provider === 'string' && body.llm_provider.length > 0;

    const ok = status === 200 && missing.length === 0 && poolNumeric && redisBool && mockBool && agentModeStr && providerStr;

    packet.writeAutoVerdict({
      result: ok ? 'PASS' : 'FAIL',
      reason: `status=${status} missing=[${missing.join(',')}] poolNumeric=${poolNumeric} redisBool=${redisBool} mode=${body.use_mock ? 'Mock' : 'Real'} agent=${body.agent_mode} provider=${body.llm_provider}`,
      checks: [
        { criterion: 'HTTP 200', met: status === 200, evidence: `${status}` },
        { criterion: '필수 11 필드', met: missing.length === 0, evidence: missing.length === 0 ? 'all present' : `missing=${missing.join(',')}` },
        { criterion: 'db_pool_* 숫자형', met: poolNumeric, evidence: `${poolNumeric}` },
        { criterion: 'redis_connected bool', met: redisBool, evidence: `${typeof body.redis_connected}` },
        { criterion: 'use_mock bool', met: mockBool, evidence: `${typeof body.use_mock}=${body.use_mock}` },
        { criterion: 'agent_mode 문자열', met: agentModeStr, evidence: `${body.agent_mode}` },
        { criterion: 'llm_provider 문자열', met: providerStr, evidence: `${body.llm_provider}` },
      ],
    });

    expect(status).toBe(200);
    expect(missing).toEqual([]);
    expect(poolNumeric).toBe(true);
    expect(redisBool).toBe(true);
    expect(mockBool).toBe(true);
  });

  test('OPS-02-METRICS /metrics 스키마 + 기록된 샘플', async ({ request }) => {
    const packet = new EvalPacket({
      id: 'OPS-02-METRICS',
      title: '/metrics 응답 구조 + 최소 샘플',
      story:
        '운영 메트릭 수집 파이프라인이 이 JSON 을 parse 한다. 선행 /health warm-up 으로 최소 1 샘플 보장 후 request_summary / latency_summary / sse_active_connections 확인.',
      steps: [
        'warm-up: GET /health 2회 + GET /api/districts?search=강남 1회',
        'GET /metrics',
        '최상위 필드 + 배열 shape 검증',
      ],
      mode: 'Mock',
      ring: 3,
      criteria: [
        'HTTP 200',
        'request_counts 배열',
        'latency 배열',
        'sse_active_connections 숫자',
        'warm-up 호출 기록됨',
      ],
    });

    // warm-up 으로 metrics 에 최소 1 샘플 확보
    await request.get(`${BACKEND}/health`, { timeout: 5000 });
    await request.get(`${BACKEND}/health`, { timeout: 5000 });
    await request.get(`${BACKEND}/api/districts?search=${encodeURIComponent('강남')}`, { timeout: 5000 });

    const resp = await request.get(`${BACKEND}/metrics`, { timeout: 10000 });
    const status = resp.status();
    const body = await resp.json().catch(() => ({}));

    const hasReqCounts = Array.isArray(body.request_counts);
    const hasLatency = Array.isArray(body.latency);
    const hasSseCount = typeof body.sse_active_connections === 'number';
    const warmUpRecorded = hasReqCounts
      && (body.request_counts as Array<{ path?: string; method?: string; count?: number }>)
        .some((r) => typeof r.path === 'string' && r.method === 'GET' && typeof r.count === 'number' && r.count >= 1);

    const latencyShape = hasLatency
      && (body.latency as Array<Record<string, unknown>>).every((row) =>
        typeof row.method === 'string'
        && typeof row.path === 'string'
        && typeof row.samples === 'number'
        && typeof row.p50_ms === 'number'
        && typeof row.p95_ms === 'number'
        && typeof row.p99_ms === 'number'
        && typeof row.avg_ms === 'number'
      );

    const ok = status === 200 && hasReqCounts && hasLatency && hasSseCount && warmUpRecorded && latencyShape;

    packet.writeAutoVerdict({
      result: ok ? 'PASS' : 'FAIL',
      reason: `status=${status} reqLen=${hasReqCounts ? body.request_counts.length : 'n/a'} latLen=${hasLatency ? body.latency.length : 'n/a'} sseConn=${body.sse_active_connections} warm=${warmUpRecorded}`,
      checks: [
        { criterion: 'HTTP 200', met: status === 200, evidence: `${status}` },
        { criterion: 'request_counts 배열', met: hasReqCounts, evidence: `${Array.isArray(body.request_counts)}` },
        { criterion: 'latency 배열', met: hasLatency, evidence: `${Array.isArray(body.latency)}` },
        { criterion: 'sse_active_connections number', met: hasSseCount, evidence: `${typeof body.sse_active_connections}` },
        { criterion: 'warm-up 호출 기록됨', met: warmUpRecorded, evidence: warmUpRecorded ? 'ok' : JSON.stringify(body.request_counts ?? {}).slice(0, 200) },
        { criterion: 'latency row shape', met: latencyShape, evidence: `${latencyShape}` },
      ],
    });

    expect(status).toBe(200);
    expect(hasReqCounts).toBe(true);
    expect(hasLatency).toBe(true);
    expect(hasSseCount).toBe(true);
    expect(warmUpRecorded).toBe(true);
  });
});
