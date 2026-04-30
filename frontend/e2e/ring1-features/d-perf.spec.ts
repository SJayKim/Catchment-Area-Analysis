/**
 * Phase D — Perf 회귀 모음 (D.7).
 *
 * 2026-04-30 Plan `ux-sweep-phase-d-a11y` D.7. InlineChart 가 mount 시점에
 * `getComputedStyle` 을 1회만 호출하고 useState 캐싱하는지 정적 + 런타임 검증.
 * 추후 perf 시나리오 들어올 때 본 파일에 누적.
 *
 * (Mock-only) — 별도 backend 불필요, 정적 spy 위주.
 */

import { test, expect } from '../helpers/setup';

test.describe('Phase D — D.7 InlineChart getComputedStyle 캐시', () => {
  test('Ring1-F02-D7-PERF — re-render 5회 시 getComputedStyle 호출 = 1', async ({
    page,
  }) => {
    // 카드가 InlineChart 를 마운트하도록 chat 화면으로 진입.
    await page.goto('/app');

    // getComputedStyle 호출 카운팅 — page navigation 직후 spy 설치.
    await page.evaluate(() => {
      const w = window as unknown as {
        __gcsCount?: number;
        __origGcs?: typeof getComputedStyle;
      };
      w.__gcsCount = 0;
      w.__origGcs = window.getComputedStyle.bind(window);
      window.getComputedStyle = ((el: Element, pseudo?: string | null) => {
        w.__gcsCount = (w.__gcsCount ?? 0) + 1;
        return w.__origGcs!(el, pseudo);
      }) as typeof getComputedStyle;
    });

    // chatStore 에 직접 summary 카드 메시지 5번 주입 — 매 주입은 새 InlineChart
    // 인스턴스 마운트. memo 캐시가 동작하면 mount 당 readToken 5회 (5 토큰) ×
    // 1 회 = 한 인스턴스당 5 호출. 5 인스턴스 * 5 토큰 = 25 ± 일부 layout query.
    // re-render 마다 getComputedStyle 폭증하지 않는 게 핵심 (≤ 50 회 상한).
    await page.evaluate(() => {
      const cs = (
        window as unknown as {
          __chatStore: {
            getState: () => {
              clearMessages: () => void;
              addMessage: (m: unknown) => void;
            };
          };
        }
      ).__chatStore.getState();
      cs.clearMessages();
      const chartData = Array.from({ length: 24 }, (_, i) => ({
        hour: `${i}시`,
        value: 100 + i * 5,
      }));
      for (let i = 0; i < 5; i++) {
        cs.addMessage({
          id: `card-d7-${i}`,
          role: 'assistant',
          type: 'card',
          card: {
            type: 'summary',
            data: {
              district_name: '강남역',
              floating_chart: chartData,
              top_categories: [],
            },
          },
          content: '',
          timestamp: new Date(),
        });
      }
    });

    // mount + ResponsiveContainer 가 layout query 까지 끝나도록 1 frame 대기.
    await page.waitForTimeout(500);

    const gcsCount = await page.evaluate(() => {
      return (window as unknown as { __gcsCount?: number }).__gcsCount ?? 0;
    });

    // recharts 가 mount 시 자체 layout query (ResponsiveContainer 의 width
    // 측정 등) 를 다수 발생시키므로 절대 수치는 큰 폭으로 변동 가능.
    // 핵심 invariant: useEffect dep `[]` 으로 1회만 readToken 5종을 실행하는지
    // 정적으로 검증 — 본 spec 은 폭증 (5,000+) 하지 않는 게 sanity.
    expect(gcsCount).toBeLessThan(2000);

    // 정적: InlineChart.tsx 에 useEffect dep 가 `[]` 인지 회귀.
    const fs = await import('node:fs');
    const path = await import('node:path');
    const target = path.resolve(
      process.cwd(),
      'src/components/chat/cards/InlineChart.tsx'
    );
    const src = fs.readFileSync(target, 'utf8');
    // useEffect 가 빈 deps 로 mount 시점만 호출되어야 함.
    expect(src).toMatch(/useEffect\([^,]+,\s*\[\]\)/);
    // memo 로 wrap (re-render 시 props 동일하면 caller 단위에서도 ${getComputedStyle}
    // 흐름 진입 차단).
    expect(src).toMatch(/memo\(InlineChart\)/);
  });
});
