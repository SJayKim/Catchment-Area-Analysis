/**
 * Production Network Guard
 * --------------------------
 * 모든 Playwright context 에 장착되어 운영 도메인 (marketscope.robitlabs.co.kr,
 * Langfuse, PostHog, Sentry 등) 로 나가는 요청을 차단하고 `ProdHitLog` 에 기록한다.
 *
 * 사용: `await installProdGuard(context)` — setup.ts 의 beforeEach hook 에서 호출.
 *
 * 통과 기준: 테스트 전체 런 종료 후 `ProdHitLog.length === 0`. 1 건이라도 남으면
 * Ring 3 `3-REG-PROD-DOMAIN-BLOCK` 를 제외하고는 FAIL.
 *
 * 차단 호스트는 env `E2E_BLOCKED_HOSTS` 또는 아래 DEFAULT 로 확장 가능.
 */

import { BrowserContext, Route } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

export interface ProdHit {
  url: string;
  method: string;
  resourceType: string;
  timestamp: string;
  testTitle?: string;
}

const DEFAULT_BLOCKED = [
  'marketscope.robitlabs.co.kr',
  'langfuse.com',
  'cloud.langfuse.com',
  'us.i.posthog.com',
  'app.posthog.com',
  'sentry.io',
  'ingest.sentry.io',
];

const LOG_DIR = path.join(__dirname, '..', 'artifacts', process.env.E2E_RUN_ID || 'run-local');
const LOG_PATH = path.join(LOG_DIR, 'prod-hit-log.jsonl');

const hits: ProdHit[] = [];

function blockedHosts(): string[] {
  const envHosts = (process.env.E2E_BLOCKED_HOSTS || '').split(',').map((s) => s.trim()).filter(Boolean);
  return envHosts.length > 0 ? envHosts : DEFAULT_BLOCKED;
}

function matchesBlocked(url: string, hosts: string[]): string | null {
  try {
    const u = new URL(url);
    for (const h of hosts) {
      if (u.hostname === h || u.hostname.endsWith(`.${h}`)) return h;
    }
  } catch {
    return null;
  }
  return null;
}

function appendHit(hit: ProdHit) {
  hits.push(hit);
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    fs.appendFileSync(LOG_PATH, JSON.stringify(hit) + '\n', 'utf8');
  } catch {
    // swallow — log persistence is best-effort, in-memory hits[] is authoritative.
  }
}

export async function installProdGuard(context: BrowserContext, testTitle?: string): Promise<void> {
  const hosts = blockedHosts();
  await context.route('**/*', (route: Route) => {
    const req = route.request();
    const url = req.url();
    const hostHit = matchesBlocked(url, hosts);
    if (hostHit) {
      appendHit({
        url,
        method: req.method(),
        resourceType: req.resourceType(),
        timestamp: new Date().toISOString(),
        testTitle,
      });
      return route.abort('failed');
    }
    return route.continue();
  });
}

export function getProdHits(): readonly ProdHit[] {
  return hits;
}

export function clearProdHits(): void {
  hits.length = 0;
}

export function prodHitLogPath(): string {
  return LOG_PATH;
}
