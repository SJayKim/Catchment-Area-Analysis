/**
 * Evaluation Packet Builder
 * --------------------------
 * Serializes per-scenario artifacts for fresh-subagent evaluation.
 *
 * Directory layout:
 *   e2e/artifacts/{runId}/{scenarioId}/
 *     ├─ scenario.md
 *     ├─ criteria.md
 *     ├─ screenshot-final.png
 *     ├─ dom.txt
 *     ├─ sse.log              (if captured)
 *     ├─ console.log
 *     ├─ network.json         (request URLs + status)
 *     ├─ timing.json
 *     └─ verdict.json         (subagent output, written later)
 */

import { Page, TestInfo } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

export const RUN_ID = process.env.E2E_RUN_ID || `run-${new Date().toISOString().slice(0, 10)}`;
export const ARTIFACT_ROOT = path.join(__dirname, '..', 'artifacts', RUN_ID);

export interface ScenarioInfo {
  id: string;
  title: string;
  story: string;
  steps: string[];
  mode: 'Mock' | 'Real' | 'Both';
  ring: 0 | 1 | 2 | 3;
  feature?: string;
  criteria: string[];
}

export interface TimingInfo {
  startedAt: number;
  firstSseEventMs?: number;
  firstTextMs?: number;
  totalMs?: number;
  toolNames: string[];
  toolCount: number;
}

export class EvalPacket {
  readonly dir: string;
  readonly scenario: ScenarioInfo;
  readonly timing: TimingInfo;
  readonly consoleEntries: string[] = [];
  readonly networkEntries: { url: string; status: number; method: string }[] = [];

  constructor(scenario: ScenarioInfo) {
    this.scenario = scenario;
    this.dir = path.join(ARTIFACT_ROOT, scenario.id);
    fs.mkdirSync(this.dir, { recursive: true });
    this.timing = { startedAt: Date.now(), toolNames: [], toolCount: 0 };
  }

  attach(page: Page) {
    page.on('console', (msg) => {
      this.consoleEntries.push(`[${msg.type()}] ${msg.text()}`);
    });
    page.on('response', (resp) => {
      const url = resp.url();
      if (url.includes('/api/')) {
        this.networkEntries.push({ url, status: resp.status(), method: resp.request().method() });
      }
    });
  }

  recordToolEvent(toolName: string) {
    if (toolName && !this.timing.toolNames.includes(toolName)) {
      this.timing.toolNames.push(toolName);
    }
    this.timing.toolCount += 1;
  }

  recordFirstSse() {
    if (!this.timing.firstSseEventMs) {
      this.timing.firstSseEventMs = Date.now() - this.timing.startedAt;
    }
  }

  recordFirstText() {
    if (!this.timing.firstTextMs) {
      this.timing.firstTextMs = Date.now() - this.timing.startedAt;
    }
  }

  async finalize(page: Page, opts: { sseLog?: string; verdict?: string } = {}) {
    this.timing.totalMs = Date.now() - this.timing.startedAt;

    // scenario.md
    const scenarioMd = [
      `# ${this.scenario.id} — ${this.scenario.title}`,
      ``,
      `**Ring**: ${this.scenario.ring}  `,
      `**Mode**: ${this.scenario.mode}  `,
      `**Feature**: ${this.scenario.feature || '-'}`,
      ``,
      `## User Story`,
      this.scenario.story,
      ``,
      `## Steps`,
      ...this.scenario.steps.map((s, i) => `${i + 1}. ${s}`),
      ``,
    ].join('\n');
    fs.writeFileSync(path.join(this.dir, 'scenario.md'), scenarioMd);

    // criteria.md
    const criteriaMd = [
      `# PASS Criteria — ${this.scenario.id}`,
      ``,
      `**The evaluator must determine PASS only if ALL criteria below are satisfied.**`,
      ``,
      ...this.scenario.criteria.map((c, i) => `- [ ] **C${i + 1}**: ${c}`),
      ``,
    ].join('\n');
    fs.writeFileSync(path.join(this.dir, 'criteria.md'), criteriaMd);

    // dom.txt
    try {
      const dom = await page.locator('body').innerText({ timeout: 3000 });
      fs.writeFileSync(path.join(this.dir, 'dom.txt'), dom);
    } catch (e) {
      fs.writeFileSync(path.join(this.dir, 'dom.txt'), `[capture failed: ${e}]`);
    }

    // screenshot-final.png
    try {
      await page.screenshot({ path: path.join(this.dir, 'screenshot-final.png'), fullPage: true });
    } catch (e) {
      // ignore
    }

    // console.log
    fs.writeFileSync(path.join(this.dir, 'console.log'), this.consoleEntries.join('\n'));

    // network.json
    fs.writeFileSync(
      path.join(this.dir, 'network.json'),
      JSON.stringify(this.networkEntries, null, 2)
    );

    // sse.log
    if (opts.sseLog !== undefined) {
      fs.writeFileSync(path.join(this.dir, 'sse.log'), opts.sseLog);
    }

    // timing.json
    fs.writeFileSync(path.join(this.dir, 'timing.json'), JSON.stringify(this.timing, null, 2));
  }

  writeAutoVerdict(verdict: { result: 'PASS' | 'FAIL' | 'SKIP'; reason: string; checks: { criterion: string; met: boolean; evidence: string }[] }) {
    fs.writeFileSync(path.join(this.dir, 'auto-verdict.json'), JSON.stringify(verdict, null, 2));
  }
}

export function ensureRunDir() {
  fs.mkdirSync(ARTIFACT_ROOT, { recursive: true });
}
