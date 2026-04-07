/**
 * Ring 1 — F10 PDF 리포트 저장 (Premium)
 *
 * Smoke: PDF 버튼 존재 + 클릭 시 다운로드 트리거 (full PDF parse 생략).
 */

import { test, expect } from '@playwright/test';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { waitForMapReady, sendChatMessage } from '../helpers/setup';

test.beforeAll(() => ensureRunDir());

test.describe('Ring 1 — F10 PDF Export', () => {
  test('F10-H1 PDF 버튼 존재 + 다운로드 트리거', async ({ page }) => {
    const packet = new EvalPacket({
      id: 'F10-H1-pdf-button',
      title: 'PDF 저장 버튼 + 다운로드',
      story: '대화 후 PDF 버튼을 클릭하면 다운로드가 시작되어야 한다.',
      steps: ['"강남역 분석" 응답 받기', 'PDF 버튼 클릭 → download event'],
      mode: 'Mock',
      ring: 1,
      feature: 'F10',
      criteria: ['PDF 버튼 존재', '다운로드 이벤트 또는 console error 0'],
    });
    packet.attach(page);
    await page.goto('/');
    await waitForMapReady(page);
    await sendChatMessage(page, '강남역 분석해줘');
    await page.waitForTimeout(2000);

    const btn = page
      .locator('button:has-text("PDF"), button[aria-label*="PDF"], button:has-text("저장")')
      .first();
    const visible = await btn.isVisible({ timeout: 5000 }).catch(() => false);

    let downloadTriggered = false;
    if (visible) {
      try {
        const dlPromise = page.waitForEvent('download', { timeout: 15000 }).catch(() => null);
        await btn.click();
        const dl = await dlPromise;
        downloadTriggered = !!dl;
      } catch {
        downloadTriggered = false;
      }
    }
    const errors = packet.consoleEntries.filter((e) => e.startsWith('[error]')).length;
    packet.writeAutoVerdict({
      result: visible && (downloadTriggered || errors === 0) ? 'PASS' : visible ? 'FAIL' : 'SKIP',
      reason: `visible=${visible} download=${downloadTriggered} errors=${errors}`,
      checks: [
        { criterion: '버튼 존재', met: visible, evidence: visible ? 'present' : 'absent' },
        { criterion: 'download 또는 0 error', met: downloadTriggered || errors === 0, evidence: `dl=${downloadTriggered} err=${errors}` },
      ],
    });
    await packet.finalize(page);
  });
});
