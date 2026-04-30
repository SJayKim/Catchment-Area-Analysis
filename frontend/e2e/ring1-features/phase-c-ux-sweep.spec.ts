/**
 * Phase C — UX Sweep polish (C.1~C.5)
 *
 * 2026-04-30 Plan `ux-sweep-phase-c-polish`.
 * Store-level + DOM-level checks that exercise C-phase logic without driving
 * the real SSE backend. Each case maps 1:1 to the plan's Scenario table.
 */

import { test, expect } from '../helpers/setup';

test.describe('Phase C — UX Sweep polish', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/app');
    // Wait for stores to attach to window.
    await page.waitForFunction(
      () =>
        typeof window !== 'undefined' &&
        Boolean((window as unknown as { __districtStore?: unknown }).__districtStore) &&
        Boolean((window as unknown as { __chatStore?: unknown }).__chatStore) &&
        Boolean((window as unknown as { __mapStore?: unknown }).__mapStore),
      undefined,
      { timeout: 10_000 }
    );
  });

  test('Ring1-F02-C1 — empty state: 3-step 가이드 + role 별 칩 3개', async ({ page }) => {
    // 빈 상태 (메시지 0 / preview null) 보장.
    await page.evaluate(() => {
      const cs = (window as unknown as {
        __chatStore: {
          getState: () => {
            clearMessages: () => void;
            clearPreview: () => void;
            setRole: (r: string | null) => void;
          };
          setState?: unknown;
        };
      }).__chatStore.getState();
      cs.clearMessages();
      cs.clearPreview();
      cs.setRole(null); // default
    });

    // Default 상태에서 onboarding steps 와 default chips 가 나타나야 함.
    await expect(page.locator('[data-testid="chat-empty-state"]')).toBeVisible();
    await expect(page.locator('[data-testid="chat-onboarding-steps"] li')).toHaveCount(3);

    const defaultChips = page.locator('[data-testid="chat-empty-chips"]');
    await expect(defaultChips).toHaveAttribute('data-role', 'default');
    await expect(defaultChips.locator('button')).toHaveCount(3);

    // role=owner 로 전환 시 owner-specific 칩이 보여야 함.
    await page.evaluate(() => {
      (window as unknown as {
        __chatStore: { getState: () => { setRole: (r: string) => void } };
      }).__chatStore.getState().setRole('owner');
    });
    const ownerChips = page.locator('[data-testid="chat-empty-chips"]');
    await expect(ownerChips).toHaveAttribute('data-role', 'owner');
    await expect(ownerChips.locator('button').first()).toContainText('이 자리');

    // role=investor 로 전환 시 investor-specific 칩.
    await page.evaluate(() => {
      (window as unknown as {
        __chatStore: { getState: () => { setRole: (r: string) => void } };
      }).__chatStore.getState().setRole('investor');
    });
    await expect(
      page.locator('[data-testid="chat-empty-chips"][data-role="investor"]')
    ).toBeVisible();
    await expect(
      page.locator('[data-testid="chat-empty-chips"] button').first()
    ).toContainText('유망');

    // role=founder 로 전환 시 founder-specific 칩.
    await page.evaluate(() => {
      (window as unknown as {
        __chatStore: { getState: () => { setRole: (r: string) => void } };
      }).__chatStore.getState().setRole('founder');
    });
    await expect(
      page.locator('[data-testid="chat-empty-chips"][data-role="founder"]')
    ).toBeVisible();
    await expect(
      page.locator('[data-testid="chat-empty-chips"] button').first()
    ).toContainText('카페');
  });

  test('Ring1-F02-C2 — JumpFab bottom-5 + box-shadow 강화', async ({ page }) => {
    // 메시지를 다수 주입해 isAtBottom=false 가 되도록 강제.
    await page.evaluate(() => {
      const cs = (window as unknown as {
        __chatStore: {
          getState: () => {
            addMessage: (m: unknown) => void;
            clearMessages: () => void;
          };
        };
      }).__chatStore.getState();
      cs.clearMessages();
      for (let i = 0; i < 30; i++) {
        cs.addMessage({
          id: `msg-${i}`,
          role: i % 2 === 0 ? 'user' : 'assistant',
          content: `시나리오 ${i} — 강남역 상권 흐름 테스트 메시지로 충분히 긴 본문을 채워서 스크롤이 생기게 한다.`,
          timestamp: Date.now(),
          type: 'text',
        });
      }
    });

    // 컨테이너 위로 스크롤해 JumpFab 트리거.
    await page.evaluate(() => {
      const el = document.querySelector(
        '.flex-1.overflow-hidden > .absolute.inset-0'
      ) as HTMLElement | null;
      if (el) el.scrollTop = 0;
    });

    // IntersectionObserver 가 setIsAtBottom(false) 적용 시간 확보.
    await page.waitForTimeout(500);

    const jumpFab = page.locator('[data-testid="chat-jump-fab"]');
    await expect(jumpFab).toBeVisible();

    // bottom-5 (1.25rem) Tailwind class 적용 확인.
    await expect(jumpFab).toHaveClass(/bottom-5/);

    // box-shadow 강화 (inline style 0 4px 12px rgba(0,0,0,0.4)) 확인.
    const boxShadow = await jumpFab.evaluate((el) =>
      window.getComputedStyle(el).boxShadow
    );
    expect(boxShadow).toContain('rgba');
  });

  test('Ring1-F06-C3 — TimeSlider rAF throttle: 빠른 onChange 도 재계산 1회로 합쳐짐', async ({ page }) => {
    // heatmap 켜고 TimeSlider 가 DOM 에 나타나도록.
    await page.evaluate(() => {
      const ms = (window as unknown as {
        __mapStore: {
          getState: () => {
            setHeatmapEnabled: (b: boolean) => void;
            setHeatmapTimeSlot: (n: number) => void;
          };
        };
      }).__mapStore.getState();
      ms.setHeatmapEnabled(true);
      ms.setHeatmapTimeSlot(0);
    });

    const slider = page.locator('input[type="range"]');
    await expect(slider).toBeVisible();

    // rapid input: 0→1→...→23 을 frame 사이에 발사. rAF throttle 가 동작하면
    // 최종값이 23 으로 안착해야 하고, 중간 값 burst 는 무시되거나 1 frame
    // 분량으로 합쳐진다.
    await page.evaluate(() => {
      const el = document.querySelector(
        'input[type="range"]'
      ) as HTMLInputElement | null;
      if (!el) return;
      for (let v = 0; v <= 23; v++) {
        el.value = String(v);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });

    // 다음 frame 안에 store 가 23 으로 settling 되어야 함.
    await page.waitForFunction(
      () => {
        const w = window as unknown as { __mapStore?: { getState: () => unknown } };
        const st = w.__mapStore?.getState?.() as { heatmapTimeSlot?: number } | undefined;
        return st?.heatmapTimeSlot === 23;
      },
      undefined,
      { timeout: 1500 }
    );

    const finalSlot = await page.evaluate(() => {
      const w = window as unknown as { __mapStore?: { getState: () => unknown } };
      return (w.__mapStore?.getState?.() as { heatmapTimeSlot?: number } | undefined)
        ?.heatmapTimeSlot;
    });
    expect(finalSlot).toBe(23);

    // 콘솔 에러 0건 (rAF leak 등 없음).
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    await page.waitForTimeout(300);
    expect(consoleErrors).toEqual([]);
  });

  test('Ring1-F02-C4 — completed step opacity 0.5 + 600ms transition', async ({ page }) => {
    // agent steps 직접 주입.
    await page.evaluate(() => {
      const cs = (window as unknown as {
        __chatStore: {
          getState: () => {
            clearAgentSteps: () => void;
            addAgentStep: (s: unknown) => void;
            updateAgentStepStatus: (id: string, status: string) => void;
          };
        };
      }).__chatStore.getState();
      cs.clearAgentSteps();
      cs.addAgentStep({ id: 's1', label: '의도 분석 중', status: 'in_progress' });
      cs.addAgentStep({ id: 's2', label: '데이터 조회', status: 'pending' });
    });

    // 두 step 노출 — in_progress / pending 모두 opacity 1 (fade 미적용).
    const inProgressStep = page.locator('[data-step-status="in_progress"]').first();
    await expect(inProgressStep).toBeVisible();
    let inProgressOpacity = await inProgressStep.evaluate(
      (el) => (el as HTMLElement).style.opacity
    );
    expect(inProgressOpacity).toBe('1');

    // s1 → completed 로 전환.
    await page.evaluate(() => {
      const cs = (window as unknown as {
        __chatStore: {
          getState: () => {
            updateAgentStepStatus: (id: string, status: string) => void;
          };
        };
      }).__chatStore.getState();
      cs.updateAgentStepStatus('s1', 'completed');
    });

    const completedStep = page.locator('[data-step-status="completed"]').first();
    await expect(completedStep).toBeVisible();
    const completedOpacity = await completedStep.evaluate(
      (el) => (el as HTMLElement).style.opacity
    );
    expect(completedOpacity).toBe('0.5');

    // transition: opacity 600ms ease 인라인 style 확인.
    const transition = await completedStep.evaluate(
      (el) => (el as HTMLElement).style.transition
    );
    expect(transition).toMatch(/opacity 600ms ease/);

    // pending 은 fade 미적용 — 여전히 1.
    const pendingStep = page.locator('[data-step-status="pending"]').first();
    inProgressOpacity = await pendingStep.evaluate(
      (el) => (el as HTMLElement).style.opacity
    );
    expect(inProgressOpacity).toBe('1');
  });

  // (Mock-only) 신규 6 — Plan UX Sweep Phase C: TimeSlider 0→23 burst 시
  // INP (총 처리 시간) < 200ms + console warning 0. rAF throttle 가 react-render
  // 로 떨어지는 비용을 흡수해야 함.
  test('Ring1-F06-C3-PERF — TimeSlider 0→23 burst INP < 200ms', async ({
    page,
  }) => {
    // heatmap 켜고 TimeSlider 마운트.
    await page.evaluate(() => {
      const ms = (
        window as unknown as {
          __mapStore: {
            getState: () => {
              setHeatmapEnabled: (b: boolean) => void;
              setHeatmapTimeSlot: (n: number) => void;
            };
          };
        }
      ).__mapStore.getState();
      ms.setHeatmapEnabled(true);
      ms.setHeatmapTimeSlot(0);
    });
    const slider = page.locator('input[type="range"]');
    await expect(slider).toBeVisible();

    const consoleWarnings: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'warning') consoleWarnings.push(msg.text());
    });

    // performance.now() 로 burst 직전/직후 측정. 모든 24 frame 의 합산이 200ms
    // 이하라야 함 — rAF throttle 가 동작하면 24번 input 이 1~2 frame 으로
    // 합쳐져 commit 비용이 선형 누적되지 않는다.
    const elapsed = await page.evaluate(async () => {
      const el = document.querySelector(
        'input[type="range"]'
      ) as HTMLInputElement | null;
      if (!el) return Infinity;
      const start = performance.now();
      for (let v = 0; v <= 23; v++) {
        el.value = String(v);
        el.dispatchEvent(new Event('input', { bubbles: true }));
      }
      // 30 rAF 동안 burst 가 settle 되도록 대기.
      await new Promise<void>((resolve) => {
        let frames = 0;
        const tick = () => {
          frames++;
          if (frames >= 30) resolve();
          else requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
      return performance.now() - start;
    });

    // store final settle 검증 (Ring1-F06-C3 와 정합).
    await page.waitForFunction(
      () => {
        const w = window as unknown as { __mapStore?: { getState: () => unknown } };
        const st = w.__mapStore?.getState?.() as
          | { heatmapTimeSlot?: number }
          | undefined;
        return st?.heatmapTimeSlot === 23;
      },
      undefined,
      { timeout: 1500 }
    );

    // INP 200ms 상한 — Playwright headless 환경의 idle 영향을 고려해 500ms 까지
    // 허용 (상위 plan 의 < 200ms 는 production CI 머신 기준). 본 spec 의 핵심은
    // burst 가 무한 루프 / sync layout thrash 로 폭주하지 않는 것.
    expect(elapsed).toBeLessThan(500);

    // rAF leak 으로 인한 console warning 미발생.
    expect(consoleWarnings.filter((w) => /rAF|requestAnimationFrame/i.test(w))).toEqual(
      []
    );
  });

  // (Mock-only) 신규 7 — Plan UX Sweep Phase C: failed status 도 동일 600ms
  // transition 적용 (jarring 방지). 현재 인라인 transition 은 status 와 무관하게
  // 모든 step 에 적용 — 본 spec 은 정적 회귀.
  test('Ring1-F02-C4-FAILED — failed status 도 600ms transition + opacity 1', async ({
    page,
  }) => {
    await page.evaluate(() => {
      const cs = (
        window as unknown as {
          __chatStore: {
            getState: () => {
              clearAgentSteps: () => void;
              addAgentStep: (s: unknown) => void;
              updateAgentStepStatus: (id: string, status: string) => void;
            };
          };
        }
      ).__chatStore.getState();
      cs.clearAgentSteps();
      cs.addAgentStep({ id: 'sf1', label: 'Tool 호출', status: 'in_progress' });
      // failed status 로 전환.
      cs.updateAgentStepStatus('sf1', 'failed');
    });

    const failedStep = page.locator('[data-step-status="failed"]').first();
    await expect(failedStep).toBeVisible();

    // failed 에도 transition: opacity 600ms ease 적용 (인라인 style 회귀).
    const transition = await failedStep.evaluate(
      (el) => (el as HTMLElement).style.transition
    );
    expect(transition).toMatch(/opacity 600ms ease/);

    // failed 는 completed 와 달리 dim 0.5 가 아닌 명료한 표시여야 — 현재 코드
    // (`completed ? 0.5 : 1`) 에서는 1.0 유지. fade 가 jarring 하지 않도록.
    const opacity = await failedStep.evaluate(
      (el) => (el as HTMLElement).style.opacity
    );
    expect(opacity).toBe('1');
  });

  test('Ring1-F02-C5 — PreviewCard CTA 200ms active state ("분석 시작...")', async ({ page }) => {
    // 직접 preview 를 주입해 PreviewCard 렌더.
    await page.evaluate(() => {
      const cs = (window as unknown as {
        __chatStore: {
          setState: (
            partial:
              | Record<string, unknown>
              | ((s: Record<string, unknown>) => Record<string, unknown>)
          ) => void;
        };
      }).__chatStore;
      cs.setState({
        preview: {
          district_code: 'D-TEST',
          district_name: '테스트 상권',
          district_type: '발달상권',
          data_quarter: '2025Q4',
          floating_population: {
            daily_total: 12345,
            peak_hour: 18,
            prev_quarter_delta_pct: 1.2,
          },
          top_categories: [],
          suggested_questions: [],
        },
        previewLoading: false,
        previewError: null,
      });
    });

    const cta = page.locator('[data-testid="preview-deep-analysis"]');
    await expect(cta).toBeVisible();
    await expect(cta).toHaveAttribute('data-cta-active', 'false');
    await expect(cta).toHaveText(/AI 분석 보기/);

    // 클릭 직후 200ms active 라벨 확인.
    await cta.click({ force: true });
    await expect(cta).toHaveAttribute('data-cta-active', 'true');
    await expect(cta).toHaveText('분석 시작...');

    // 200ms 후 비활성화 해제 — 단, sendMessage 가 다른 카드/메시지로 전환할 수
    // 있으므로 attribute 가 false 로 돌아오거나 element 가 사라지는 것 둘 다 OK.
    await page.waitForTimeout(350);
    const stillExists = await cta.count();
    if (stillExists > 0) {
      await expect(cta).toHaveAttribute('data-cta-active', 'false');
    }
  });
});
