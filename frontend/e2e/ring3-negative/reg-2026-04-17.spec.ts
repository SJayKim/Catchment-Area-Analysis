/**
 * Ring 3 — Regression (2026-04-17 base)
 *
 * 커밋 4dbd598 (Plan B 배포 근본해결 7건) 이후 추가된 회귀 케이스.
 * - cleanup_alembic idempotent (2회 실행해도 exit 0)
 * - validate_env.py 누락 env 실패 케이스
 * - flush_cache.py 5 prefix 삭제 로깅
 * - /api/kakao-sdk 404 + /proxy/kakao-sdk 200
 * - PROD-DOMAIN-BLOCK: prodGuard 가 운영 도메인 호출 abort
 * - SALES-UNIT-GREP: 분기 매출 → 월매출 치환 흔적 (회귀 탐지)
 */

import { test, expect } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { getProdHits, clearProdHits, prodHitLogPath } from '../helpers/prodGuard';
import { spawnSync, SpawnSyncReturns } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';

test.beforeAll(() => ensureRunDir());

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');
const PY = process.env.E2E_PYTHON || 'python';
const COMPOSE_FILE = process.env.E2E_COMPOSE_FILE || 'docker-compose.e2e.yml';
const COMPOSE_PROJECT = process.env.E2E_COMPOSE_PROJECT || 'marketscope-e2e';

// 호스트에 psycopg2/redis 모듈을 설치하지 않아도 되도록, Python 스크립트는
// backend 컨테이너에서 실행한다. 컨테이너는 실제 마이그레이션/캐시가 돌아가는
// 환경과 동일해서 의존성/경로 정합성도 자연스럽게 검증된다.
function dockerComposeExec(
  service: string,
  cmd: string[],
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
    service,
    ...cmd,
  ];
  return spawnSync('docker', args, {
    cwd: REPO_ROOT,
    encoding: 'utf8',
    timeout: timeoutMs,
  });
}

function dockerUnavailableReason(r: SpawnSyncReturns<string>): string | null {
  if (r.error && (r.error as NodeJS.ErrnoException).code === 'ENOENT') {
    return 'docker CLI not found on PATH';
  }
  if (r.status === null) return 'docker exec timed out or failed to spawn';
  const stderr = (r.stderr || '').toLowerCase();
  if (stderr.includes('no configuration file provided')) {
    return 'docker compose file not found';
  }
  if (stderr.includes('not running') || stderr.includes('no such container')) {
    return 'e2e stack service not running';
  }
  if (stderr.includes('error response from daemon')) {
    return 'docker daemon unreachable';
  }
  if (stderr.includes('cannot connect to the docker daemon')) {
    return 'docker daemon unreachable';
  }
  return null;
}

test.describe('Ring 3 — Regression 2026-04-17', () => {
  test('3-REG-CLEANUP-ALEMBIC idempotent (2회 실행 exit 0)', async () => {
    // backend 컨테이너에서 실행 — 실제 migrate 컨테이너와 동일한 의존성/네트워크
    // 환경(/app/scripts/cleanup_alembic.py, DATABASE_URL_SYNC 주입, psycopg2 포함).
    const packet = new EvalPacket({
      id: '3-REG-CLEANUP-ALEMBIC',
      title: 'cleanup_alembic idempotent',
      story: '마이그레이션 init 컨테이너에서 매 기동 실행해도 exit 0 이어야 한다.',
      steps: ['docker exec backend python scripts/cleanup_alembic.py 2회', '두 번 모두 exit 0'],
      mode: 'Real',
      ring: 3,
      criteria: ['1회차 exit 0', '2회차 exit 0', 'stale rows removed 로그'],
    });

    const runs = [0, 1].map(() =>
      dockerComposeExec('backend', ['python', 'scripts/cleanup_alembic.py'])
    );

    const unavailable = dockerUnavailableReason(runs[0]);
    if (unavailable) {
      packet.writeAutoVerdict({
        result: 'SKIP',
        reason: `${unavailable} (stderr="${runs[0].stderr?.slice(0, 200)}")`,
        checks: [{ criterion: 'docker stack available', met: false, evidence: unavailable }],
      });
      test.skip(true, unavailable);
    }

    const statuses = runs.map((r) => r.status);
    const bothZero = statuses.every((s) => s === 0);
    const logged = runs[0].stdout?.includes('stale rows removed') ?? false;

    packet.writeAutoVerdict({
      result: bothZero ? 'PASS' : 'FAIL',
      reason: `runs=${statuses.join(',')} firstStdout="${runs[0].stdout?.slice(0, 200)}" firstStderr="${runs[0].stderr?.slice(0, 200)}"`,
      checks: [
        { criterion: '1회차 exit 0', met: statuses[0] === 0, evidence: `${statuses[0]}` },
        { criterion: '2회차 exit 0', met: statuses[1] === 0, evidence: `${statuses[1]}` },
        { criterion: '로그 출력', met: logged, evidence: runs[0].stdout?.slice(0, 80) || '' },
      ],
    });
    expect(bothZero).toBe(true);
  });

  test('3-REG-VALIDATE-ENV-FAIL 누락 env 감지', async () => {
    const packet = new EvalPacket({
      id: '3-REG-VALIDATE-ENV-FAIL',
      title: 'validate_env.py missing key',
      story: 'NEXT_PUBLIC_API_URL 이 빠진 임시 env 에 대해 validate_env.py 가 exit 1 + stderr 로 필드명 보고.',
      steps: ['임시 broken.env 생성', 'python scripts/validate_env.py broken.env'],
      mode: 'Real',
      ring: 3,
      criteria: ['exit 1', 'stderr 에 NEXT_PUBLIC_API_URL 포함'],
    });

    const tmpEnv = path.join(REPO_ROOT, '.e2e-tmp-broken.env');
    fs.writeFileSync(
      tmpEnv,
      'NEXT_PUBLIC_KAKAO_MAP_KEY=validkey\n' +
        'GOOGLE_API_KEY=validkey\n' +
        'USE_MOCK=true\n',
      'utf8'
    );
    try {
      const r = spawnSync(PY, ['scripts/validate_env.py', tmpEnv], {
        cwd: REPO_ROOT,
        encoding: 'utf8',
        timeout: 10000,
      });
      const exit1 = r.status === 1;
      const stderrHasKey = (r.stderr || '').includes('NEXT_PUBLIC_API_URL');
      packet.writeAutoVerdict({
        result: exit1 && stderrHasKey ? 'PASS' : 'FAIL',
        reason: `exit=${r.status} stderr="${(r.stderr || '').slice(0, 200)}"`,
        checks: [
          { criterion: 'exit 1', met: exit1, evidence: `${r.status}` },
          { criterion: 'stderr mentions key', met: stderrHasKey, evidence: 'NEXT_PUBLIC_API_URL' },
        ],
      });
      expect(exit1).toBe(true);
      expect(stderrHasKey).toBe(true);
    } finally {
      try { fs.unlinkSync(tmpEnv); } catch { /* ignore */ }
    }
  });

  test('3-REG-FLUSH-CACHE 5 prefix 삭제', async () => {
    // backend 컨테이너 내부에서 Real 모드로 실행 — /app/scripts/flush_cache.py
    // (server/scripts/ → 컨테이너 COPY 결과) + redis 모듈 + REDIS_URL 이 이미
    // 준비된 환경. 호스트 의존성 0.
    const packet = new EvalPacket({
      id: '3-REG-FLUSH-CACHE',
      title: 'flush_cache.py 5 prefix 로그',
      story: 'docker exec backend python scripts/flush_cache.py 실행 시 sales:/compare:/recommend:/simulation:/summary: 5 prefix 가 각각 로깅되어야 한다.',
      steps: ['docker exec backend python scripts/flush_cache.py', 'stdout 에 5 prefix 각 존재'],
      mode: 'Real',
      ring: 3,
      criteria: ['exit 0', '5 prefix 라인 존재', '[flush_cache] Total removed: 포함'],
    });

    const r = dockerComposeExec(
      'backend',
      ['python', 'scripts/flush_cache.py'],
      { USE_MOCK: 'false' }
    );

    const unavailable = dockerUnavailableReason(r);
    if (unavailable) {
      packet.writeAutoVerdict({
        result: 'SKIP',
        reason: `${unavailable} (stderr="${r.stderr?.slice(0, 200)}")`,
        checks: [{ criterion: 'docker stack available', met: false, evidence: unavailable }],
      });
      test.skip(true, unavailable);
    }

    const prefixes = ['sales:', 'compare:', 'recommend:', 'simulation:', 'summary:'];
    const out = r.stdout || '';
    const hits = prefixes.filter((p) => out.includes(p));
    const totalLogged = out.includes('Total removed');
    const exitOk = r.status === 0;

    packet.writeAutoVerdict({
      result: exitOk && hits.length === 5 && totalLogged ? 'PASS' : 'FAIL',
      reason: `exit=${r.status} hits=${hits.length}/5 stderr="${(r.stderr || '').slice(0, 150)}"`,
      checks: [
        { criterion: 'exit 0', met: exitOk, evidence: `${r.status}` },
        { criterion: '5 prefix', met: hits.length === 5, evidence: hits.join(',') },
        { criterion: 'Total removed 로깅', met: totalLogged, evidence: totalLogged ? 'ok' : 'missing' },
      ],
    });
    expect(exitOk).toBe(true);
    expect(hits.length).toBe(5);
  });

  test('3-REG-KAKAO-SDK-ROUTE /proxy vs /api 경로', async ({ request }) => {
    const packet = new EvalPacket({
      id: '3-REG-KAKAO-SDK-ROUTE',
      title: 'Kakao SDK 경로 이동 (4dbd598)',
      story: '/proxy/kakao-sdk 는 200, 이전 /api/kakao-sdk 는 404 (이동 완료).',
      steps: ['GET /proxy/kakao-sdk → 200', 'GET /api/kakao-sdk → 404'],
      mode: 'Mock',
      ring: 3,
      criteria: ['proxy 200', 'legacy 404'],
    });

    const frontend = process.env.E2E_BASE_URL || 'http://localhost:3001';
    const proxy = await request.get(`${frontend}/proxy/kakao-sdk`, { timeout: 10000 });
    const legacy = await request.get(`${frontend}/api/kakao-sdk`, {
      timeout: 10000,
      failOnStatusCode: false,
    });

    const proxyOk = proxy.status() >= 200 && proxy.status() < 400;
    const legacyGone = legacy.status() === 404;

    packet.writeAutoVerdict({
      result: proxyOk && legacyGone ? 'PASS' : 'FAIL',
      reason: `proxy=${proxy.status()} legacy=${legacy.status()}`,
      checks: [
        { criterion: '/proxy 200', met: proxyOk, evidence: `${proxy.status()}` },
        { criterion: '/api/kakao-sdk 404', met: legacyGone, evidence: `${legacy.status()}` },
      ],
    });
    expect(proxyOk).toBe(true);
    expect(legacyGone).toBe(true);
  });

  test('3-REG-PROD-DOMAIN-BLOCK 운영 도메인 접근 차단', async ({ page }) => {
    // prodGuard 가 동작하는지 확인하는 자기-검증 테스트.
    const packet = new EvalPacket({
      id: '3-REG-PROD-DOMAIN-BLOCK',
      title: '운영 도메인 접근 차단',
      story: 'Playwright context 에서 marketscope.robitlabs.co.kr 로 fetch 를 시도하면 prodGuard 가 abort 하고 ProdHitLog 에 1 건이 남는다.',
      steps: ['clear hits', 'fetch(prod URL)', 'hits.length === 1'],
      mode: 'Both',
      ring: 3,
      criteria: ['fetch 실패', 'ProdHitLog 1건 증가'],
    });
    packet.attach(page);

    const before = getProdHits().length;
    clearProdHits();
    const baseBefore = before; // unused but kept for trace

    await page.goto('/');
    const fetchResult = await page.evaluate(async () => {
      try {
        const r = await fetch('https://marketscope.robitlabs.co.kr/health');
        return { ok: r.ok, status: r.status };
      } catch (e) {
        return { ok: false, status: -1, err: (e as Error).message };
      }
    });

    const hits = getProdHits();
    const abortedClient = fetchResult.ok === false;
    const hitLogged = hits.length >= 1;

    packet.writeAutoVerdict({
      result: abortedClient && hitLogged ? 'PASS' : 'FAIL',
      reason: `clientFail=${abortedClient} hits=${hits.length} (baseline ${baseBefore}) log=${prodHitLogPath()}`,
      checks: [
        { criterion: 'fetch 실패', met: abortedClient, evidence: JSON.stringify(fetchResult) },
        { criterion: 'ProdHitLog ≥1', met: hitLogged, evidence: `${hits.length}` },
      ],
    });
    expect(abortedClient).toBe(true);
    expect(hitLogged).toBe(true);
    // 차단 자체가 성공 조건 — 테스트 종료 전 hits 를 비워 전체 런 sanity 를 오염시키지 않음.
    clearProdHits();
    await packet.finalize(page);
  });

  test('3-REG-SALES-UNIT-GREP 분기 매출 키 회귀', async () => {
    // server/ 전체에서 quarterly 매출을 sales 키로 직접 노출하는 회귀 패턴이 남아있지 않은지 확인.
    // 4dbd598 이전: response['sales'] = quarterly_sales  (잘못된 분기 매출 단위)
    // 이후: monthly_sales 키 + /3 변환.
    const packet = new EvalPacket({
      id: '3-REG-SALES-UNIT-GREP',
      title: '분기 매출 키 회귀 grep',
      story: 'server/ 코드에 quarterly 매출을 sales 키로 직접 반환하는 회귀 패턴이 없어야 한다.',
      steps: ['server/ 재귀 scan', 'pattern: quarterly.*[\'\"]sales[\'\"] = 금지'],
      mode: 'Real',
      ring: 3,
      criteria: ['0 match'],
    });

    const serverDir = path.join(REPO_ROOT, 'server');
    const badPattern = /quarterly[A-Za-z_0-9]*\s*\[\s*["']sales["']\s*\]\s*=/;

    const matches: { file: string; line: number; text: string }[] = [];
    const stack: string[] = [serverDir];
    while (stack.length > 0) {
      const dir = stack.pop()!;
      let entries: fs.Dirent[] = [];
      try {
        entries = fs.readdirSync(dir, { withFileTypes: true });
      } catch {
        continue;
      }
      for (const e of entries) {
        if (e.name === '__pycache__' || e.name === '.venv' || e.name === 'node_modules') continue;
        const full = path.join(dir, e.name);
        if (e.isDirectory()) {
          stack.push(full);
        } else if (e.isFile() && e.name.endsWith('.py')) {
          const src = fs.readFileSync(full, 'utf8').split('\n');
          src.forEach((line, idx) => {
            if (badPattern.test(line)) {
              matches.push({ file: path.relative(REPO_ROOT, full), line: idx + 1, text: line.trim().slice(0, 120) });
            }
          });
        }
      }
    }
    const clean = matches.length === 0;
    packet.writeAutoVerdict({
      result: clean ? 'PASS' : 'FAIL',
      reason: `matches=${matches.length}`,
      checks: [{ criterion: '0 match', met: clean, evidence: matches.slice(0, 5).map((m) => `${m.file}:${m.line}`).join('; ') || 'clean' }],
    });
    expect(clean).toBe(true);
  });
});
