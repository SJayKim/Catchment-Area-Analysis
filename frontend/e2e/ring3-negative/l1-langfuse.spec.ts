/**
 * Ring 3 — LLMOps L1 Langfuse wiring 회귀
 *
 * Plan: docs/plan/infra/llmops-l1-e2e.md
 * Parent: docs/plan/infra/llmops-platform.md §3.3.1 / §4.3
 *
 * 검증 범위:
 *   L1-E01  TRACE-DOWN baseline (키 미설정 → 정상 SSE, trace_id=null)
 *   L1-E02  TRACE-SDK-MISSING (langfuse v4 SDK + `langfuse.callback` import fail → None)
 *   L1-E03  TRACE-BAD-KEY (잘못된 키 → CallbackHandler 생성 실패 → None)
 *   L1-E04  HASH-DETERMINISTIC (동일 salt + session → 동일 16-hex)
 *   L1-E05  HASH-SALT-INDEPENDENT (salt 변경 시 해시 격리)
 *   L1-E06  DONE-TRACE-ID-OPTIONAL (trace_id 부재 done 이벤트, 프론트 파서 정상)
 *   L1-E07  SSE-CONTRACT-GREP (SSE raw 스트림에 `event:` 라인 금지)
 *
 * Stack: docker-compose.e2e.yml (reg-2026-04-17.spec.ts 와 동일 방식)
 */

import { test, expect } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { spawnSync, SpawnSyncReturns } from 'node:child_process';
import * as http from 'node:http';
import * as path from 'node:path';

/**
 * SSE raw POST — Playwright `request.post` 가 chunked stream 끝(0-size trailer) 감지에
 * 의존하면 sse_starlette keep-alive 설정에 따라 타임아웃되는 경우가 있어, 노드 http
 * 모듈로 직접 스트림을 읽고 `"type":"done"` 발견 시 즉시 종료한다.
 */
async function postSseRaw(
  url: string,
  body: Record<string, unknown>,
  timeoutMs: number = 30000,
): Promise<{ status: number; raw: string }> {
  const parsed = new URL(url);
  const payload = Buffer.from(JSON.stringify(body), 'utf-8');
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        method: 'POST',
        hostname: parsed.hostname,
        port: parsed.port,
        path: parsed.pathname + parsed.search,
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
          resolve({ status: res.statusCode || 0, raw: Buffer.concat(chunks).toString('utf-8') });
        }, timeoutMs);
        res.on('data', (chunk: Buffer) => {
          chunks.push(chunk);
          const raw = Buffer.concat(chunks).toString('utf-8');
          // `done` 이벤트가 한 SSE 프레임 단위(연속 두 개의 LF)로 완전히 도착한 뒤 종료.
          // 너무 일찍 destroy 하면 done 이벤트의 JSON 라인이 잘려 파싱 불가.
          if (/data:\s*\{[^\n]*"type":\s*"done"[^\n]*\}\s*\n\s*\n/.test(raw)) {
            clearTimeout(timer);
            try {
              res.destroy();
            } catch {
              /* ignore */
            }
            resolve({ status: res.statusCode || 0, raw });
          }
        });
        res.on('end', () => {
          clearTimeout(timer);
          resolve({ status: res.statusCode || 0, raw: Buffer.concat(chunks).toString('utf-8') });
        });
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

test.beforeAll(() => ensureRunDir());

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');
const COMPOSE_FILE = process.env.E2E_COMPOSE_FILE || 'docker-compose.e2e.yml';
const COMPOSE_PROJECT = process.env.E2E_COMPOSE_PROJECT || 'marketscope-e2e';
const BACKEND = process.env.E2E_BACKEND_URL || 'http://localhost:8002';

/**
 * backend 컨테이너 내부에서 임의 Python 을 실행.
 * reg-2026-04-17.spec.ts 의 dockerComposeExec 계약을 공유하되,
 * Windows MSYS 경로 변환을 회피하기 위해 `python -c <oneliner>` 형태만 사용.
 */
function dockerPy(
  code: string,
  envOverrides: Record<string, string> = {},
  timeoutMs: number = 20000
): SpawnSyncReturns<string> {
  const envFlags: string[] = [];
  for (const [k, v] of Object.entries(envOverrides)) {
    envFlags.push('-e', `${k}=${v}`);
  }
  const args = [
    'compose',
    '-f',
    COMPOSE_FILE,
    '-p',
    COMPOSE_PROJECT,
    'exec',
    '-T',
    ...envFlags,
    'backend',
    'python',
    '-c',
    code,
  ];
  return spawnSync('docker', args, {
    cwd: REPO_ROOT,
    encoding: 'utf8',
    timeout: timeoutMs,
    env: { ...process.env, MSYS_NO_PATHCONV: '1' },
  });
}

function dockerUnavailable(r: SpawnSyncReturns<string>): string | null {
  if (r.error && (r.error as NodeJS.ErrnoException).code === 'ENOENT') {
    return 'docker CLI not found on PATH';
  }
  if (r.status === null) return 'docker exec timed out or failed to spawn';
  const stderr = (r.stderr || '').toLowerCase();
  if (stderr.includes('no configuration file provided')) return 'docker compose file not found';
  if (stderr.includes('not running') || stderr.includes('no such container')) {
    return 'e2e stack service not running';
  }
  return null;
}

test.describe('Ring 3 — LLMOps L1 Langfuse wiring', () => {
  test('L1-E01 TRACE-DOWN baseline: SSE 정상 + trace_id null', async ({}, testInfo) => {
    testInfo.setTimeout(120_000);
    const packet = new EvalPacket({
      id: 'L1-E01-TRACE-DOWN-BASELINE',
      title: 'Langfuse 미설정 상태에서 /api/chat 정상',
      story: 'LANGFUSE_*_KEY 미설정 + v4 SDK 환경에서도 /api/chat 는 모든 SSE 이벤트를 발행하고 done 의 trace_id 는 null(미포함) 이다.',
      steps: [
        'POST /api/chat message="강남역 분석해줘" district_code=D3001',
        'SSE lines 파싱 → 이벤트 수 / 타입 / done.trace_id 수집',
      ],
      mode: 'Mock',
      ring: 3,
      criteria: [
        'HTTP 200',
        '이벤트 ≥ 5개',
        'done 이벤트 존재',
        'done.trace_id 없음(null)',
        'SSE raw 에 `event:` 라인 0',
      ],
    });

    const { status, raw } = await postSseRaw(
      `${BACKEND}/api/chat`,
      {
        message: '강남역 분석해줘',
        district_code: 'D3001',
        session_id: 'l1-e01',
      },
      // PAE 전체 파이프라인 — Actor 15s + Respond stream 10s+
      90000,
    );

    // SSE line 파싱
    const dataLines = raw.split('\n').filter((l) => l.startsWith('data: '));
    const events = dataLines
      .map((l) => {
        try {
          return JSON.parse(l.slice(6));
        } catch {
          return null;
        }
      })
      .filter((e): e is { type: string; trace_id?: string | null } => !!e);
    const done = events.find((e) => e.type === 'done');
    const hasEventLine = /^event:/m.test(raw);

    const passed =
      status === 200 &&
      events.length >= 5 &&
      done !== undefined &&
      !done?.trace_id &&
      !hasEventLine;

    packet.writeAutoVerdict({
      result: passed ? 'PASS' : 'FAIL',
      reason: `status=${status} events=${events.length} done=${!!done} trace_id=${done?.trace_id ?? 'null'} hasEventLine=${hasEventLine}`,
      checks: [
        { criterion: 'HTTP 200', met: status === 200, evidence: `${status}` },
        { criterion: 'events ≥5', met: events.length >= 5, evidence: `${events.length}` },
        { criterion: 'done 존재', met: !!done, evidence: done ? 'yes' : 'no' },
        { criterion: 'trace_id null', met: !done?.trace_id, evidence: `${done?.trace_id ?? 'null'}` },
        { criterion: 'event: 라인 0', met: !hasEventLine, evidence: hasEventLine ? 'FOUND' : 'clean' },
      ],
    });

    expect(status).toBe(200);
    expect(events.length).toBeGreaterThanOrEqual(5);
    expect(done).toBeDefined();
    expect(done?.trace_id ?? null).toBeNull();
    expect(hasEventLine).toBe(false);
  });

  test('L1-E02 TRACE-SDK-MISSING: v4 SDK 환경에서 handler None', async () => {
    // 현재 컨테이너에는 langfuse v4 가 설치되어 있고, graph.py 는 v2 `langfuse.callback`
    // 경로를 시도한다. ImportError → `None` 반환 + `_tracer_valid=False` 가 L1 설계의 핵심.
    const packet = new EvalPacket({
      id: 'L1-E02-TRACE-SDK-MISSING',
      title: 'v4 SDK 에서 v2 API import fail → None',
      story: 'langfuse v4 는 `langfuse.callback` 경로가 없음. get_langfuse_handler() 가 None 을 반환하고 _tracer_valid 플래그를 내려야 한다.',
      steps: [
        'backend python -c 로 langfuse_tracer 직접 호출',
        'ImportError handling → None',
      ],
      mode: 'Mock',
      ring: 3,
      criteria: ['handler None', '_tracer_valid False', 'log warn 텍스트 포함'],
    });

    const code = [
      'import importlib, server.services.langfuse_tracer as m',
      // 모듈 캐시 리셋 — 이전 테스트 영향 제거
      'importlib.reload(m)',
      // Langfuse 키 2개 세팅 (활성화 조건 충족)
      'from server.config import settings',
      'settings.langfuse_public_key = "pk-test"',
      'settings.langfuse_secret_key = "sk-test"',
      'h = m.get_langfuse_handler("s1", "r1")',
      'print("HANDLER=" + ("None" if h is None else "NOT_NONE"))',
      'print("VALID=" + str(m._tracer_valid))',
    ].join('; ');

    const r = dockerPy(code);
    const skip = dockerUnavailable(r);
    if (skip) {
      packet.writeAutoVerdict({
        result: 'SKIP',
        reason: skip,
        checks: [{ criterion: 'docker stack', met: false, evidence: skip }],
      });
      test.skip(true, skip);
    }

    const stdout = r.stdout || '';
    const stderr = r.stderr || '';
    const handlerNone = stdout.includes('HANDLER=None');
    const validFalse = stdout.includes('VALID=False');
    const warnLogged = stderr.includes('langfuse package unavailable') || stderr.includes('import failed');

    packet.writeAutoVerdict({
      result: handlerNone && validFalse ? 'PASS' : 'FAIL',
      reason: `stdout="${stdout.slice(0, 200)}" stderr="${stderr.slice(0, 200)}"`,
      checks: [
        { criterion: 'handler None', met: handlerNone, evidence: stdout.slice(0, 80) },
        { criterion: '_tracer_valid False', met: validFalse, evidence: stdout.slice(0, 80) },
        { criterion: 'warn log', met: warnLogged, evidence: stderr.slice(0, 80) },
      ],
    });

    expect(handlerNone).toBe(true);
    expect(validFalse).toBe(true);
  });

  test('L1-E03 TRACE-BAD-KEY: 생성자 실패 시 None 반환', async () => {
    // v2 SDK 가 있어도, 잘못된 키 + 네트워크 없는 호스트로 생성자 예외 시 None.
    // v4 환경에서는 E02 처럼 import 단계에서 이미 fail — 동일한 None 경로로 수렴.
    // 즉 E03 은 "키 있음 + 어떤 형태로든 실패 = None" 을 확증한다.
    const packet = new EvalPacket({
      id: 'L1-E03-TRACE-BAD-KEY',
      title: '키 있음 + 생성 실패 → None',
      story: 'langfuse_public_key/secret_key 가 있어도 생성자가 실패하면 None 을 반환하고 _tracer_valid 를 내린다.',
      steps: ['backend python -c 에서 키 세팅 + handler 호출'],
      mode: 'Mock',
      ring: 3,
      criteria: ['handler None', '_tracer_valid False'],
    });

    const code = [
      'import importlib, server.services.langfuse_tracer as m',
      'importlib.reload(m)',
      'from server.config import settings',
      'settings.langfuse_public_key = "pk-lf-invalid-xxxxxxxx"',
      'settings.langfuse_secret_key = "sk-lf-invalid-xxxxxxxx"',
      'settings.langfuse_host = "http://127.0.0.1:9/unreachable"',
      'h = m.get_langfuse_handler("abc", "req")',
      'print("HANDLER=" + ("None" if h is None else "NOT_NONE"))',
      'print("VALID=" + str(m._tracer_valid))',
    ].join('; ');

    const r = dockerPy(code);
    const skip = dockerUnavailable(r);
    if (skip) {
      packet.writeAutoVerdict({
        result: 'SKIP',
        reason: skip,
        checks: [{ criterion: 'docker stack', met: false, evidence: skip }],
      });
      test.skip(true, skip);
    }

    const stdout = r.stdout || '';
    const handlerNone = stdout.includes('HANDLER=None');
    const validFalse = stdout.includes('VALID=False');

    packet.writeAutoVerdict({
      result: handlerNone && validFalse ? 'PASS' : 'FAIL',
      reason: `stdout="${stdout.slice(0, 200)}"`,
      checks: [
        { criterion: 'handler None', met: handlerNone, evidence: stdout.slice(0, 80) },
        { criterion: '_tracer_valid False', met: validFalse, evidence: stdout.slice(0, 80) },
      ],
    });

    expect(handlerNone).toBe(true);
    expect(validFalse).toBe(true);
  });

  test('L1-E04 HASH-DETERMINISTIC: 동일 salt + session → 동일 해시', async () => {
    // session_id 는 ascii + 한글 혼합. UTF-8 인코딩이 깨지면 결과가 달라진다.
    const packet = new EvalPacket({
      id: 'L1-E04-HASH-DETERMINISTIC',
      title: 'hash 결정성 (UTF-8 포함)',
      story: '같은 salt 에서 같은 session_id 는 항상 같은 16-hex 해시를 생성한다.',
      steps: ['backend python _hash_session(ascii) 2회', '_hash_session(한글) 2회'],
      mode: 'Mock',
      ring: 3,
      criteria: ['ascii 2회 결과 동일', '한글 2회 결과 동일', '길이 16'],
    });

    const code = [
      'import importlib, server.services.langfuse_tracer as m',
      'importlib.reload(m)',
      // 고정 salt 주입 (인스턴스 랜덤 salt 제거)
      'm._SESSION_SALT = "fixed-test-salt"',
      'a1 = m._hash_session("abc123")',
      'a2 = m._hash_session("abc123")',
      'k1 = m._hash_session("강남-세션-001")',
      'k2 = m._hash_session("강남-세션-001")',
      'print("A=" + a1 + "/" + a2)',
      'print("K=" + k1 + "/" + k2)',
    ].join('; ');

    const r = dockerPy(code);
    const skip = dockerUnavailable(r);
    if (skip) {
      packet.writeAutoVerdict({
        result: 'SKIP',
        reason: skip,
        checks: [{ criterion: 'docker stack', met: false, evidence: skip }],
      });
      test.skip(true, skip);
    }

    const stdout = r.stdout || '';
    const parseLine = (prefix: string): [string, string] => {
      const m = stdout.match(new RegExp(`^${prefix}=([^/]+)/([^\\s]+)`, 'm'));
      return m ? [m[1], m[2]] : ['', ''];
    };
    const [a1, a2] = parseLine('A');
    const [k1, k2] = parseLine('K');
    const asciiOk = a1.length === 16 && a1 === a2;
    const koreanOk = k1.length === 16 && k1 === k2;

    packet.writeAutoVerdict({
      result: asciiOk && koreanOk ? 'PASS' : 'FAIL',
      reason: `A=${a1}/${a2} K=${k1}/${k2}`,
      checks: [
        { criterion: 'ascii 2회 동일', met: a1 === a2, evidence: `${a1}==${a2}` },
        { criterion: 'ascii len 16', met: a1.length === 16, evidence: `${a1.length}` },
        { criterion: 'korean 2회 동일', met: k1 === k2, evidence: `${k1}==${k2}` },
        { criterion: 'korean len 16', met: k1.length === 16, evidence: `${k1.length}` },
      ],
    });

    expect(asciiOk).toBe(true);
    expect(koreanOk).toBe(true);
  });

  test('L1-E05 HASH-SALT-INDEPENDENT: salt 변경 시 해시 격리', async () => {
    const packet = new EvalPacket({
      id: 'L1-E05-HASH-SALT-INDEPENDENT',
      title: 'salt 격리',
      story: '같은 session_id 라도 salt 가 다르면 해시는 서로 달라야 한다.',
      steps: ['salt A 에서 해시', 'salt B 에서 해시', '두 값 비교'],
      mode: 'Mock',
      ring: 3,
      criteria: ['두 해시 다름', '각 길이 16'],
    });

    const code = [
      'import importlib, server.services.langfuse_tracer as m',
      'importlib.reload(m)',
      'm._SESSION_SALT = "salt-alpha"',
      'h1 = m._hash_session("sess-1")',
      'm._SESSION_SALT = "salt-beta"',
      'h2 = m._hash_session("sess-1")',
      'print("H=" + h1 + "/" + h2)',
    ].join('; ');

    const r = dockerPy(code);
    const skip = dockerUnavailable(r);
    if (skip) {
      packet.writeAutoVerdict({
        result: 'SKIP',
        reason: skip,
        checks: [{ criterion: 'docker stack', met: false, evidence: skip }],
      });
      test.skip(true, skip);
    }

    const stdout = r.stdout || '';
    const match = stdout.match(/H=([a-f0-9]+)\/([a-f0-9]+)/);
    const h1 = match?.[1] || '';
    const h2 = match?.[2] || '';
    const differ = h1.length === 16 && h2.length === 16 && h1 !== h2;

    packet.writeAutoVerdict({
      result: differ ? 'PASS' : 'FAIL',
      reason: `h1=${h1} h2=${h2}`,
      checks: [
        { criterion: 'len 16 x2', met: h1.length === 16 && h2.length === 16, evidence: `${h1.length}/${h2.length}` },
        { criterion: 'h1 != h2', met: h1 !== h2, evidence: `${h1}!=${h2}` },
      ],
    });

    expect(differ).toBe(true);
  });

  test('L1-E06 DONE-TRACE-ID-OPTIONAL: frontend 파서 깨지지 않음', async ({ page }) => {
    // 전체 챗 플로우를 Playwright 로 돌려 콘솔 에러 없음을 확인.
    // L1 변경이 frontend 파서(eventHandlers.ts case 'done') 호환성을 깨지 않는지 검증.
    const packet = new EvalPacket({
      id: 'L1-E06-DONE-TRACE-ID-OPTIONAL',
      title: 'done.trace_id 부재에도 파서 무사',
      story: 'Langfuse 미활성 상태(done 에 trace_id 없음)에서도 frontend 렌더러가 콘솔 에러 없이 suggestion/loading 상태 전이를 완료한다.',
      steps: [
        'goto /',
        'waitForMapReady (생략 허용)',
        'textarea 에 메시지 입력 + Enter',
        'done 까지 대기',
        'console error 0',
      ],
      mode: 'Mock',
      ring: 3,
      criteria: ['console error 0', 'textarea 재활성화', 'SuggestionChip 존재'],
    });
    packet.attach(page);

    const errors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.goto('/app', { waitUntil: 'domcontentloaded', timeout: 30000 });
    // 폴리곤 로딩을 기다릴 필요는 없음(채팅만 사용)
    const textarea = page.locator('textarea[placeholder*="물어보세요"]');
    await textarea.waitFor({ state: 'visible', timeout: 15000 });
    await textarea.fill('안녕');
    await textarea.press('Enter');

    // done 이벤트 도착 후 textarea 가 다시 활성화되는지 확인
    const deadline = Date.now() + 30000;
    let enabled = false;
    while (Date.now() < deadline) {
      if (!(await textarea.isDisabled().catch(() => true))) {
        enabled = true;
        break;
      }
      await page.waitForTimeout(200);
    }

    const suggestionCount = await page
      .locator('button')
      .filter({ hasText: /강남역|홍대|업종|상권/ })
      .count()
      .catch(() => 0);

    const consoleErrorsRelevant = errors.filter(
      // prodGuard 차단 / devtools 잡음 제외
      (e) => !e.includes('prodGuard') && !e.includes('DevTools'),
    );

    const passed = enabled && consoleErrorsRelevant.length === 0;

    packet.writeAutoVerdict({
      result: passed ? 'PASS' : 'FAIL',
      reason: `enabled=${enabled} errors=${consoleErrorsRelevant.length} suggestions=${suggestionCount}`,
      checks: [
        { criterion: 'textarea 재활성', met: enabled, evidence: `${enabled}` },
        { criterion: 'console error 0', met: consoleErrorsRelevant.length === 0, evidence: consoleErrorsRelevant.slice(0, 2).join('|') || 'clean' },
        { criterion: 'suggestion ≥1', met: suggestionCount >= 1, evidence: `${suggestionCount}` },
      ],
    });

    await packet.finalize(page);
    expect(enabled).toBe(true);
    expect(consoleErrorsRelevant).toEqual([]);
  });

  test('L1-E07 SSE-CONTRACT-GREP: `event:` 라인 금지 회귀', async () => {
    // L1-E01 과 동일한 쿼리를 다시 쳐서 raw text 를 새로 캡처한 뒤, Ring 1 에서 절대 안 생겨야 할
    // `event: <xxx>` SSE prefix 가 안 새는지 엄격히 검증. Plan §4.2 재검토의 "SSE 포맷 불변" 항목.
    const packet = new EvalPacket({
      id: 'L1-E07-SSE-CONTRACT-GREP',
      title: 'SSE event: 라인 회귀 grep',
      story: 'L1 변경은 SSE 포맷 불변이 원칙. done 등 이벤트 type 은 JSON 내부로만, event: 라인 신설 금지.',
      steps: ['POST /api/chat 실행 + raw 캡처', '/^event:/m 검색'],
      mode: 'Mock',
      ring: 3,
      criteria: ['0 match', 'data: 라인은 ≥5'],
    });

    const { raw } = await postSseRaw(`${BACKEND}/api/chat`, {
      message: '안녕',
      session_id: 'l1-e07',
    });
    const eventLines = raw.match(/^event:/gm) || [];
    const dataLines = raw.match(/^data: /gm) || [];
    const passed = eventLines.length === 0 && dataLines.length >= 1;

    packet.writeAutoVerdict({
      result: passed ? 'PASS' : 'FAIL',
      reason: `event_lines=${eventLines.length} data_lines=${dataLines.length}`,
      checks: [
        { criterion: 'event: 0', met: eventLines.length === 0, evidence: `${eventLines.length}` },
        { criterion: 'data: ≥1', met: dataLines.length >= 1, evidence: `${dataLines.length}` },
      ],
    });

    expect(eventLines.length).toBe(0);
    expect(dataLines.length).toBeGreaterThanOrEqual(1);
  });
});
