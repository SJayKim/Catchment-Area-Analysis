/**
 * Ring 2 — J05 PDF stakeholder share
 *
 * "이거 공유해야 해요"
 * F01 → F03 → F05 → F10
 */

import { test, expect, waitForMapReady, sendChatMessage } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';

test.beforeAll(() => ensureRunDir());
test.setTimeout(240000);

test('J05 PDF share — analyze + compare → PDF download', async ({ page }) => {
  const packet = new EvalPacket({
    id: 'J05-pdf',
    title: 'PDF 공유: 분석 + 비교 → PDF 저장',
    story: '강남역 분석 + 홍대 비교 후 PDF 저장 버튼으로 다운로드.',
    steps: ['"강남역 분석"', '"홍대랑 비교"', 'PDF 버튼 클릭'],
    mode: 'Mock',
    ring: 2,
    feature: 'F03+F05+F10',
    criteria: [
      'DOM에 강남 + 홍대',
      'PDF 버튼 존재',
      'click 후 console error 0 또는 download trigger',
    ],
  });
  packet.attach(page);
  await page.goto('/app');
  await waitForMapReady(page);

  await sendChatMessage(page, '강남역 분석해줘');
  await page.waitForTimeout(2000);
  await sendChatMessage(page, '홍대입구랑 비교해줘');
  await page.waitForTimeout(2000);

  const btn = page
    .locator('button:has-text("PDF"), button[aria-label*="PDF"], button:has-text("저장")')
    .first();
  const visible = await btn.isVisible({ timeout: 5000 }).catch(() => false);
  let downloaded = false;
  if (visible) {
    try {
      const dlPromise = page.waitForEvent('download', { timeout: 15000 }).catch(() => null);
      await btn.click();
      const dl = await dlPromise;
      downloaded = !!dl;
    } catch {
      downloaded = false;
    }
  }
  const text = (await page.locator('body').innerText()) || '';
  const hasBoth = text.includes('강남') && text.includes('홍대');
  const errors = packet.consoleEntries.filter((e) => e.startsWith('[error]')).length;
  packet.writeAutoVerdict({
    result: hasBoth && visible && (downloaded || errors === 0) ? 'PASS' : 'FAIL',
    reason: `hasBoth=${hasBoth} button=${visible} download=${downloaded} errors=${errors}`,
    checks: [
      { criterion: '강남+홍대', met: hasBoth, evidence: hasBoth ? 'both' : 'missing' },
      { criterion: 'PDF 버튼', met: visible, evidence: visible ? 'present' : 'absent' },
      {
        criterion: 'download 또는 errors 0',
        met: downloaded || errors === 0,
        evidence: `dl=${downloaded} err=${errors}`,
      },
    ],
  });
  await packet.finalize(page);
  expect(hasBoth).toBe(true);
});
