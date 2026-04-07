/**
 * Backend log capture helper.
 *
 * Backend in this environment runs as a bare process on :8002 (no Docker).
 * We capture per-scenario backend behaviour by polling a sentinel via
 * `/health` and recording the wall-clock window into a file. The actual
 * server-side log lives outside this process; for evaluation we record the
 * scenario time window so a human/subagent can correlate if needed.
 */

import * as fs from 'fs';
import * as path from 'path';

export class BackendLogWindow {
  readonly startedAt: number;
  readonly notes: string[] = [];
  constructor() {
    this.startedAt = Date.now();
  }
  note(msg: string) {
    this.notes.push(`[+${Date.now() - this.startedAt}ms] ${msg}`);
  }
  writeTo(dir: string) {
    const out = [
      `# Backend window for scenario`,
      `started_at_iso: ${new Date(this.startedAt).toISOString()}`,
      `duration_ms: ${Date.now() - this.startedAt}`,
      ``,
      ...this.notes,
    ].join('\n');
    fs.writeFileSync(path.join(dir, 'backend.log'), out);
  }
}
