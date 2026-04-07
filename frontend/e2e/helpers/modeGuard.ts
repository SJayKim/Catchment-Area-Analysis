/**
 * Mode Guard
 * -----------
 * Detects whether the running backend is in Mock or Real mode by probing
 * `/api/districts?search=강남`. Returns 'mock' if D3001/D300x or 5-district
 * total, otherwise 'real'.
 *
 * Tests can call `requireMode('mock')` or `requireMode('real')` to skip
 * scenarios that don't apply.
 */

import { test } from '@playwright/test';

export type Mode = 'mock' | 'real';

let cachedMode: Mode | null = null;

export async function detectMode(): Promise<Mode> {
  if (cachedMode) return cachedMode;
  const baseUrl = process.env.E2E_BACKEND_URL || 'http://localhost:8002';
  try {
    const resp = await fetch(`${baseUrl}/api/districts?search=${encodeURIComponent('강남')}`);
    if (!resp.ok) return (cachedMode = 'real'); // assume real on error
    const data = await resp.json();
    const first = data?.items?.[0];
    if (first?.district_code?.startsWith('D300')) {
      cachedMode = 'mock';
    } else {
      cachedMode = 'real';
    }
  } catch {
    cachedMode = 'mock';
  }
  return cachedMode;
}

export async function requireMode(required: Mode) {
  const actual = await detectMode();
  test.skip(actual !== required, `Requires ${required} mode, but backend is in ${actual} mode`);
}

export async function getMode(): Promise<Mode> {
  return detectMode();
}
