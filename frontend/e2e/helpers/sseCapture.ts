/**
 * SSE Capture Helper
 * -------------------
 * Tees `/api/chat` SSE stream into a buffer + dispatches per-event callbacks.
 *
 * Usage:
 *   const sse = await attachSseCapture(page, evalPacket);
 *   await sendChatMessage(page, '강남역 분석');
 *   await sse.waitForEvent('done', 30000);
 *   const log = sse.getLog();
 */

import { Page } from '@playwright/test';
import { EvalPacket } from './evalPacket';

export interface SseCapture {
  getLog(): string;
  events: { type: string; data: string; ts: number }[];
  waitForEvent(eventType: string, timeoutMs?: number): Promise<boolean>;
  hasEvent(eventType: string): boolean;
  detach(): void;
}

export async function attachSseCapture(page: Page, packet?: EvalPacket): Promise<SseCapture> {
  const events: { type: string; data: string; ts: number }[] = [];
  const buffer: string[] = [];
  let lastEventType = '';
  const startTs = Date.now();

  // Intercept /api/chat at network level so we can tee the body.
  const handler = async (route: any) => {
    const request = route.request();
    try {
      const response = await page.request.fetch(request, { timeout: 60000 });
      const body = await response.body();
      const text = body.toString('utf-8');
      buffer.push(text);

      // Parse SSE events from accumulated buffer.
      // MarketScope SSE format: data: {"type":"...","content":"..."}
      // (event type embedded in JSON, not on a separate `event:` line)
      const lines = text.split('\n');
      for (const line of lines) {
        if (line.startsWith('data:')) {
          const dataPart = line.slice(5).trim();
          const ts = Date.now() - startTs;
          let evType = 'message';
          let parsed: any = null;
          try {
            parsed = JSON.parse(dataPart);
            evType = parsed?.type || 'message';
          } catch {}
          events.push({ type: evType, data: dataPart, ts });
          if (packet) {
            packet.recordFirstSse();
            if ((evType === 'tool' || evType === 'tool_end') && parsed?.name) {
              packet.recordToolEvent(parsed.name);
            }
            if (evType === 'text') {
              packet.recordFirstText();
            }
          }
        }
      }
      // Suppress unused warning
      void lastEventType;

      await route.fulfill({
        status: response.status(),
        headers: response.headers(),
        body,
      });
    } catch (err) {
      await route.continue();
    }
  };

  await page.route('**/api/chat', handler);

  return {
    events,
    getLog() {
      return buffer.join('');
    },
    hasEvent(eventType: string) {
      return events.some((e) => e.type === eventType);
    },
    async waitForEvent(eventType: string, timeoutMs = 30000) {
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        if (events.some((e) => e.type === eventType)) return true;
        await new Promise((r) => setTimeout(r, 200));
      }
      return false;
    },
    detach() {
      page.unroute('**/api/chat', handler).catch(() => {});
    },
  };
}
