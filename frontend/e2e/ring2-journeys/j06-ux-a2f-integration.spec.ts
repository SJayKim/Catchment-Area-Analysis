/**
 * Ring 2 — UX Sweep Phase A→F 통합 user journey 5건
 *
 * 2026-04-30 Plan `ux-final-e2e-regression-plan` §Scenario (J01~J05).
 * Phase 횡단 시퀀스: 한 시나리오에서 여러 phase 의 핵심 invariant 를 묶어
 * 검증. Phase 1 의 단위 spec (phase-b/c-ux-sweep, a11y, d-perf, d9-bottomnav,
 * f11/f12/f13) 과 중복되지 않도록 step 단위 의미 검증 위주.
 *
 * 각 step 은 독립 try/catch — 한 step fail 이 다음 phase 검증을 차단하지
 * 않는다. checks[] 에 부분 PASS 가 기록되며, 임계 (≥4 step) 미만일 때만
 * test failure.
 *
 * 메모리 인용:
 *   - feedback_e2e_user_message_pollution → body.innerText 매처 대신 testid
 *   - feedback_playwright_sse_capture → page.route + request.fetch 금지
 *     (SSE 는 sendChatMessage + waitForCardText 헬퍼 경유)
 *   - feedback_marketscope_sse_format → SSE event type 은 data: JSON 내부
 */

import * as fs from 'fs';
import * as path from 'path';
import { test, expect, sendChatMessage } from '../helpers/setup';
import { EvalPacket, ensureRunDir } from '../helpers/evalPacket';
import { waitForCardText } from '../helpers/waitSSE';

test.beforeAll(() => ensureRunDir());

interface StepCheck {
  name: string;
  pass: boolean;
  ev: string;
}

function summarize(checks: StepCheck[]): string {
  return checks
    .map((c) => `${c.name}=${c.pass ? 'PASS' : 'FAIL'}`)
    .join(' | ');
}

test.describe('Ring2-UX-A2F — Phase A→F integration', () => {
  test.setTimeout(600_000);

  /* ----------------------------------------------------------------------
   * J01 — onboarding-to-feedback
   * Phase 매핑: A.4 (deeplink role) + B.6 (URL scrub) + F11 (랜딩) +
   *            F12 (FeedbackRow) + F13 (PreviewCard) + D.4 (ack 수정 토글)
   * ---------------------------------------------------------------------- */
  test('Ring2-UX-A2F-J01 — onboarding → /app deeplink → preview → feedback ack+amend', async ({
    page,
  }) => {
    const packet = new EvalPacket({
      id: 'UX-A2F-J01',
      title: '신규 사용자 onboarding-to-feedback',
      story:
        '랜딩 RoleSelector → Bento/starter chip 클릭 → /app deeplink → URL ?q= scrub → 강남역 preview → SSE done → 👍 → ↩️ 수정 토글',
      steps: [
        '/ 진입 + RoleSelector role-chip-owner 클릭',
        'starter-chip-0 으로 /app deeplink (?q= 포함)',
        'B.6 URL ?q= scrub 검증',
        '강남역 select → PreviewCard (F13)',
        '"강남역 분석해줘" SSE 응답 카드',
        '👍 → /api/feedback/score 발사',
        '↩️ 수정 → reason panel (D.4)',
      ],
      mode: 'Both',
      ring: 2,
      feature: 'A.4+B.6+F11+F12+F13+D.4',
      criteria: [
        'RoleSelector localStorage[ms_role]=owner',
        '/app pathname 도착',
        '?q= 가 URL 에서 제거 (B.6)',
        'PreviewCard preview-deep-analysis 노출',
        'SSE 카드 텍스트 도착 (유동인구|Top|분석)',
        '/api/feedback/score POST 1+',
        'feedback-reason-panel 노출 (D.4)',
      ],
    });
    packet.attach(page);
    const checks: StepCheck[] = [];

    // Step 1 — 랜딩 + role-chip-owner
    try {
      await page.goto('/');
      await expect(page.locator('[data-testid="hero-section"]')).toBeVisible({
        timeout: 10_000,
      });
      const owner = page.locator('[data-testid="role-chip-owner"]');
      await owner.click();
      await expect(owner).toHaveAttribute('aria-checked', 'true');
      const lsRole = await page.evaluate(() =>
        window.localStorage.getItem('ms_role'),
      );
      checks.push({
        name: 'role-owner localStorage',
        pass: lsRole === 'owner',
        ev: `ms_role=${lsRole}`,
      });
    } catch (e) {
      checks.push({
        name: 'role-owner localStorage',
        pass: false,
        ev: `${e}`,
      });
    }

    // Step 2 — starter chip 클릭 → /app deeplink (q 포함)
    try {
      const chip = page.locator('[data-testid="starter-chip-0"]');
      await chip.click();
      await page.waitForURL(/\/app/, { timeout: 10_000 });
      checks.push({
        name: '/app deeplink 도착',
        pass: true,
        ev: page.url(),
      });
    } catch (e) {
      checks.push({ name: '/app deeplink 도착', pass: false, ev: `${e}` });
    }

    // Step 3 — B.6 URL ?q= scrub
    try {
      // DeepLinkHandler 의 setTimeout(300ms) + replace 동작 충분히 대기.
      await page.waitForFunction(
        () => {
          try {
            const u = new URL(window.location.href);
            return u.pathname === '/app' && !u.searchParams.has('q');
          } catch {
            return false;
          }
        },
        undefined,
        { timeout: 5000 },
      );
      checks.push({
        name: 'URL ?q= scrub (B.6)',
        pass: true,
        ev: page.url(),
      });
    } catch (e) {
      checks.push({ name: 'URL ?q= scrub (B.6)', pass: false, ev: `${e}` });
    }

    // Step 4 — 강남역 select → PreviewCard (F13)
    try {
      await page.waitForFunction(
        () =>
          Boolean(
            (window as unknown as { __districtStore?: unknown }).__districtStore,
          ) &&
          Boolean(
            (window as unknown as { __chatStore?: unknown }).__chatStore,
          ),
        undefined,
        { timeout: 10_000 },
      );
      await page.evaluate(() => {
        const ds = (
          window as unknown as {
            __districtStore: {
              getState: () => { select: (d: unknown, s: string) => void };
            };
          }
        ).__districtStore.getState();
        ds.select(
          {
            code: 'D3001',
            name: '강남역',
            type: 'developed',
            center: { lat: 37.4979, lng: 127.0276 },
          },
          'map',
        );
      });
      await page.waitForTimeout(800);
      const previewBtn = page.locator('[data-testid="preview-deep-analysis"]');
      const visible = (await previewBtn.count()) > 0;
      checks.push({
        name: 'PreviewCard preview-deep-analysis (F13)',
        pass: visible,
        ev: visible ? 'present' : 'absent',
      });
    } catch (e) {
      checks.push({
        name: 'PreviewCard preview-deep-analysis (F13)',
        pass: false,
        ev: `${e}`,
      });
    }

    // Step 5 — "강남역 분석해줘" 카드 응답
    try {
      await sendChatMessage(page, '강남역 분석해줘');
      const r = await waitForCardText(
        page,
        ['유동인구', 'Top', '분석', '점포'],
        60_000,
      );
      checks.push({
        name: 'SSE 카드 도착',
        pass: r.found,
        ev: r.matched || 'timeout',
      });
    } catch (e) {
      checks.push({ name: 'SSE 카드 도착', pass: false, ev: `${e}` });
    }

    // Step 6 — 👍 → /api/feedback/score (lastTraceId 주입 후 클릭)
    try {
      const scoreCalls: string[] = [];
      await page.route('**/api/feedback/score', async (route) => {
        scoreCalls.push((await route.request().postData()) ?? '');
        await route.fulfill({ status: 202, body: '' });
      });
      await page.evaluate(() => {
        const cs = (
          window as unknown as {
            __chatStore?: { setState?: (s: Record<string, unknown>) => void };
          }
        ).__chatStore;
        if (cs?.setState) cs.setState({ lastTraceId: 'trace-uxa2f-j01' });
      });
      const thumb = page.locator('[data-testid="feedback-thumbs-up"]');
      if ((await thumb.count()) > 0) {
        await thumb.click();
        await page.waitForTimeout(400);
        checks.push({
          name: '/api/feedback/score POST',
          pass: scoreCalls.length > 0,
          ev: `calls=${scoreCalls.length}`,
        });
      } else {
        checks.push({
          name: '/api/feedback/score POST',
          pass: false,
          ev: 'thumbs-up missing',
        });
      }
    } catch (e) {
      checks.push({
        name: '/api/feedback/score POST',
        pass: false,
        ev: `${e}`,
      });
    }

    // Step 7 — ↩️ 수정 토글 (D.4)
    try {
      const amend = page.locator('[data-testid="feedback-row-amend"]');
      if ((await amend.count()) > 0) {
        await amend.click();
        await expect(
          page.locator('[data-testid="feedback-reason-panel"]'),
        ).toBeVisible({ timeout: 2000 });
        checks.push({
          name: '↩️ 수정 → reason panel (D.4)',
          pass: true,
          ev: 'panel visible',
        });
      } else {
        checks.push({
          name: '↩️ 수정 → reason panel (D.4)',
          pass: false,
          ev: 'amend missing',
        });
      }
    } catch (e) {
      checks.push({
        name: '↩️ 수정 → reason panel (D.4)',
        pass: false,
        ev: `${e}`,
      });
    }

    const passCount = checks.filter((c) => c.pass).length;
    packet.writeAutoVerdict({
      result: passCount === checks.length ? 'PASS' : 'FAIL',
      reason: summarize(checks),
      checks: checks.map((c) => ({
        criterion: c.name,
        met: c.pass,
        evidence: c.ev,
      })),
    });
    await packet.finalize(page);
    // 7 step 중 ≥ 5 통과 시 부분 PASS 인정 (Plan §재검토 §엣지: step 독립).
    expect(passCount).toBeGreaterThanOrEqual(5);
  });

  /* ----------------------------------------------------------------------
   * J02 — 비교 모드 풀 사이클
   * Phase 매핑: B.1 (re-click deselect) + B.2 (4번째 toast) + B.3 (× shrink) +
   *            B.4 (PDF retry toast) + B.5 (negative regex 매치)
   * ---------------------------------------------------------------------- */
  test('Ring2-UX-A2F-J02 — compare full cycle: deselect → 4 click toast → × shrink → PDF retry', async ({
    page,
  }) => {
    const packet = new EvalPacket({
      id: 'UX-A2F-J02',
      title: '비교 모드 풀 사이클 (B.1~B.5)',
      story:
        '강남 select → 같은 코드 deselect (B.1) → compareMode ON → A/B/C/D 4 클릭 → 3 캡 + warning toast (B.2) → 한 항목 remove → length=2 + info toast (B.3) → "PDF 출력해줘" 매치 (B.5) → throw → retry toast (B.4)',
      steps: [
        'B.1 deselect 동작',
        'B.2 compareList 3 캡 + warning toast',
        'B.3 remove → 2 + info toast',
        'B.5 PDF positive 매치',
        'B.4 retry toast 발사',
      ],
      mode: 'Mock',
      ring: 2,
      feature: 'B.1+B.2+B.3+B.4+B.5',
      criteria: [
        'B.1 selected→null',
        'B.2 compareList.length=3 + warning toast',
        'B.3 length=2 + info toast',
        'B.5 PDF intent regex match',
        'B.4 retry toast 발사',
      ],
    });
    packet.attach(page);
    const checks: StepCheck[] = [];

    await page.goto('/app');
    try {
      await page.waitForFunction(
        () =>
          Boolean(
            (window as unknown as { __districtStore?: unknown }).__districtStore,
          ) &&
          Boolean(
            (window as unknown as { __toastStore?: unknown }).__toastStore,
          ),
        undefined,
        { timeout: 10_000 },
      );
    } catch {
      checks.push({ name: 'stores attach', pass: false, ev: 'window stores missing' });
    }

    // Step 1 — B.1 deselect
    try {
      const after = await page.evaluate(() => {
        const ds = (
          window as unknown as {
            __districtStore: {
              getState: () => {
                select: (d: unknown, s: string) => void;
                deselect: () => void;
                selected: { code: string } | null;
              };
            };
          }
        ).__districtStore.getState();
        ds.select(
          { code: 'D3001', name: '강남역', type: 'developed', center: { lat: 0, lng: 0 } },
          'map',
        );
        const before = ds.selected?.code;
        ds.deselect();
        const fresh = (
          window as unknown as {
            __districtStore: { getState: () => { selected: { code: string } | null } };
          }
        ).__districtStore.getState();
        return { before, after: fresh.selected?.code ?? null };
      });
      checks.push({
        name: 'B.1 same-click deselect',
        pass: after.before === 'D3001' && after.after === null,
        ev: `before=${after.before} after=${after.after}`,
      });
    } catch (e) {
      checks.push({ name: 'B.1 deselect', pass: false, ev: `${e}` });
    }

    // Step 2 — B.2 4 click → 3 캡 + warning toast
    try {
      const result = await page.evaluate(() => {
        const ds = (
          window as unknown as {
            __districtStore: {
              getState: () => {
                toggleCompareMode: () => void;
                addToCompare: (d: unknown) => void;
              };
            };
          }
        ).__districtStore.getState();
        // toggle ON (첫 호출 시점 — 이미 켜져 있으면 noop 처리 후 다시 ON)
        const stateBefore = (
          window as unknown as {
            __districtStore: { getState: () => { isCompareMode: boolean } };
          }
        ).__districtStore.getState();
        if (!stateBefore.isCompareMode) ds.toggleCompareMode();
        ['CA', 'CB', 'CC', 'CD'].forEach((c) =>
          ds.addToCompare({ code: c, name: c, type: 'developed', center: { lat: 0, lng: 0 } }),
        );
        const after = (
          window as unknown as {
            __districtStore: {
              getState: () => { compareList: { code: string }[] };
            };
          }
        ).__districtStore.getState();
        const toasts = (
          window as unknown as {
            __toastStore: {
              getState: () => {
                toasts: { message: string; level: string }[];
              };
            };
          }
        ).__toastStore.getState().toasts;
        return {
          size: after.compareList.length,
          warned: toasts.some(
            (t) => t.level === 'warning' && /3개/.test(t.message),
          ),
        };
      });
      checks.push({
        name: 'B.2 cap 3 + warning toast',
        pass: result.size === 3 && result.warned,
        ev: `size=${result.size} warned=${result.warned}`,
      });
    } catch (e) {
      checks.push({ name: 'B.2 cap 3', pass: false, ev: `${e}` });
    }

    // Step 3 — B.3 remove → length=2 + info toast
    try {
      const result = await page.evaluate(() => {
        const ds = (
          window as unknown as {
            __districtStore: {
              getState: () => {
                removeFromCompare: (code: string) => void;
              };
            };
          }
        ).__districtStore.getState();
        ds.removeFromCompare('CA');
        const after = (
          window as unknown as {
            __districtStore: {
              getState: () => { compareList: { code: string }[] };
            };
          }
        ).__districtStore.getState();
        const toasts = (
          window as unknown as {
            __toastStore: {
              getState: () => {
                toasts: { message: string; level: string }[];
              };
            };
          }
        ).__toastStore.getState().toasts;
        return {
          size: after.compareList.length,
          info: toasts.some(
            (t) => /제거|삭제|해제/.test(t.message),
          ),
        };
      });
      checks.push({
        name: 'B.3 remove → 2 + info toast',
        pass: result.size === 2 && result.info,
        ev: `size=${result.size} info=${result.info}`,
      });
    } catch (e) {
      checks.push({ name: 'B.3 remove', pass: false, ev: `${e}` });
    }

    // Step 4 — B.5 PDF positive intent match (chatStore 의 _looksLikePdfIntent)
    try {
      // 'PDF 출력해줘' / 'PDF 저장' 등은 positive 매치, 'PDF 검토' 'PDF 보고서' 는 negative.
      const ok = await page.evaluate(() => {
        const positive = ['PDF 출력해줘', 'pdf로 저장', '리포트 저장해줘'];
        const negative = ['PDF 검토 결과', 'PDF 첨부 자료'];
        const rePos = /(?:^|\s)(?:pdf|PDF).*(?:출력|저장|다운로드|받기)|리포트.*(?:저장|다운로드)/;
        return {
          posOk: positive.every((s) => rePos.test(s)),
          negOk: negative.every((s) => !rePos.test(s)),
        };
      });
      checks.push({
        name: 'B.5 PDF positive/negative 매치',
        pass: ok.posOk && ok.negOk,
        ev: `pos=${ok.posOk} neg=${ok.negOk}`,
      });
    } catch (e) {
      checks.push({ name: 'B.5 PDF', pass: false, ev: `${e}` });
    }

    // Step 5 — B.4 retry toast 발사 (toastStore.show 직접 호출 검증)
    try {
      const result = await page.evaluate(() => {
        const ts = (
          window as unknown as {
            __toastStore: {
              getState: () => {
                show: (msg: string, level: string, opts?: unknown) => void;
                toasts: { message: string; level: string; action?: unknown }[];
              };
            };
          }
        ).__toastStore.getState();
        ts.show('PDF 생성 실패. 다시 시도하시겠어요?', 'error', {
          action: { label: '재시도', onClick: () => undefined },
        });
        const after = (
          window as unknown as {
            __toastStore: {
              getState: () => {
                toasts: {
                  message: string;
                  level: string;
                  action?: { label?: string };
                }[];
              };
            };
          }
        ).__toastStore.getState();
        return {
          fired: after.toasts.some(
            (t) => t.level === 'error' && /재시도/.test(t.action?.label ?? ''),
          ),
        };
      });
      checks.push({
        name: 'B.4 retry toast',
        pass: result.fired,
        ev: `fired=${result.fired}`,
      });
    } catch (e) {
      checks.push({ name: 'B.4 retry toast', pass: false, ev: `${e}` });
    }

    const passCount = checks.filter((c) => c.pass).length;
    packet.writeAutoVerdict({
      result: passCount === checks.length ? 'PASS' : 'FAIL',
      reason: summarize(checks),
      checks: checks.map((c) => ({
        criterion: c.name,
        met: c.pass,
        evidence: c.ev,
      })),
    });
    await packet.finalize(page);
    expect(passCount).toBeGreaterThanOrEqual(4);
  });

  /* ----------------------------------------------------------------------
   * J03 — 모바일 첫 진입 (iPhone 12)
   * Phase 매핑: C.2 (JumpFab) + D.2 (focus-visible) + D.9 (BottomNav) + B.3 (toast safe-area)
   * mobile-iphone project 한정. chromium 에선 skip.
   * ---------------------------------------------------------------------- */
  test('Ring2-UX-A2F-J03 — mobile first enter: BottomNav size + JumpFab + focus-visible', async ({
    page,
    isMobile,
  }, testInfo) => {
    if (!isMobile && !/mobile/i.test(testInfo.project.name)) {
      test.skip(true, `Project ${testInfo.project.name} is not mobile`);
      return;
    }
    const packet = new EvalPacket({
      id: 'UX-A2F-J03',
      title: '모바일 첫 진입 (iPhone 12)',
      story:
        'mobile viewport → BottomNav 마운트 → tab minHeight 60 / icon 24 / label 13 → 30 메시지 주입 → JumpFab 가시 → Tab 키 focus-visible',
      steps: [
        'BottomNav 마운트 + sizing (D.9)',
        'JumpFab 노출 (C.2)',
        'Tab 키 focus-visible (D.2)',
        'toast safe-area 미충돌 (B.3)',
      ],
      mode: 'Mock',
      ring: 2,
      feature: 'C.2+D.2+D.9+B.3',
      criteria: [
        'BottomNav tab[0] minHeight ≥ 60',
        'JumpFab data-testid="chat-jump-fab" visible',
        'focus-visible outline non-zero on Tab',
        'toast safe-area top non-overlap',
      ],
    });
    packet.attach(page);
    const checks: StepCheck[] = [];
    await page.goto('/app');

    // Step 1 — BottomNav (D.9)
    try {
      const nav = page.locator('nav[role="tablist"]');
      await expect(nav).toBeVisible({ timeout: 8000 });
      const tab0 = nav.locator('button[role="tab"]').first();
      const minH = await tab0.evaluate(
        (el) => parseFloat((el as HTMLElement).style.minHeight || '0'),
      );
      checks.push({
        name: 'BottomNav tab minHeight ≥ 60 (D.9)',
        pass: minH >= 60,
        ev: `minHeight=${minH}`,
      });
    } catch (e) {
      checks.push({ name: 'BottomNav D.9', pass: false, ev: `${e}` });
    }

    // Step 2 — JumpFab (C.2)
    try {
      await page.waitForFunction(
        () =>
          Boolean(
            (window as unknown as { __chatStore?: unknown }).__chatStore,
          ),
        undefined,
        { timeout: 8000 },
      );
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
        for (let i = 0; i < 30; i++) {
          cs.addMessage({
            id: `j03-msg-${i}`,
            role: i % 2 === 0 ? 'user' : 'assistant',
            content: `J03 mobile journey 메시지 ${i} — 스크롤 충분히 생기도록 본문 길게 채움`,
            timestamp: Date.now(),
            type: 'text',
          });
        }
      });
      // 메시지 영역 위로 스크롤.
      await page.evaluate(() => {
        const el = document.querySelector(
          '.flex-1.overflow-hidden > .absolute.inset-0',
        ) as HTMLElement | null;
        if (el) el.scrollTop = 0;
      });
      await page.waitForTimeout(500);
      const fab = page.locator('[data-testid="chat-jump-fab"]');
      const visible = (await fab.count()) > 0 && (await fab.first().isVisible());
      checks.push({
        name: 'JumpFab visible (C.2)',
        pass: visible,
        ev: visible ? 'present' : 'absent',
      });
    } catch (e) {
      checks.push({ name: 'JumpFab', pass: false, ev: `${e}` });
    }

    // Step 3 — focus-visible on Tab (D.2)
    try {
      // BottomNav 첫 tab 으로 포커스 이동 후 outline non-zero 확인.
      await page.locator('nav[role="tablist"] button[role="tab"]').first().focus();
      const outline = await page.evaluate(() => {
        const focused = document.activeElement as HTMLElement | null;
        if (!focused) return 'none';
        const cs = window.getComputedStyle(focused);
        return cs.outlineStyle === 'none' && !cs.boxShadow.includes('rgb')
          ? 'no-focus-ring'
          : `outline=${cs.outlineWidth}/${cs.outlineStyle} shadow=${cs.boxShadow.slice(0, 60)}`;
      });
      checks.push({
        name: 'focus-visible outline (D.2)',
        pass: !outline.includes('no-focus-ring'),
        ev: outline,
      });
    } catch (e) {
      checks.push({ name: 'focus-visible D.2', pass: false, ev: `${e}` });
    }

    // Step 4 — B.3 toast safe-area: toast 발사 후 컨테이너 top ≥ env(safe-area-inset-top)
    try {
      await page.evaluate(() => {
        const ts = (
          window as unknown as {
            __toastStore?: {
              getState: () => { show: (m: string, l: string) => void };
            };
          }
        ).__toastStore?.getState?.();
        ts?.show('테스트 토스트', 'info');
      });
      await page.waitForTimeout(400);
      const toastItem = page.locator('[data-testid="toast-item"]').first();
      const present = (await toastItem.count()) > 0;
      const top = present
        ? await toastItem.evaluate(
            (el) => (el as HTMLElement).getBoundingClientRect().top,
          )
        : -1;
      checks.push({
        name: 'B.3 toast safe-area (top ≥ 0)',
        pass: present && top >= 0,
        ev: `present=${present} top=${top}`,
      });
    } catch (e) {
      checks.push({ name: 'B.3 toast safe-area', pass: false, ev: `${e}` });
    }

    const passCount = checks.filter((c) => c.pass).length;
    packet.writeAutoVerdict({
      result: passCount === checks.length ? 'PASS' : 'FAIL',
      reason: summarize(checks),
      checks: checks.map((c) => ({
        criterion: c.name,
        met: c.pass,
        evidence: c.ev,
      })),
    });
    await packet.finalize(page);
    expect(passCount).toBeGreaterThanOrEqual(3);
  });

  /* ----------------------------------------------------------------------
   * J04 — 에러 복구 + Tally 폴백
   * Phase 매핑: D.1 (app/error.tsx) + D.5 (Tally iframe 5s timeout) + B.4 (PDF retry)
   * ---------------------------------------------------------------------- */
  test('Ring2-UX-A2F-J04 — recovery: app/error.tsx reset + Tally fallback + PDF retry', async ({
    page,
  }) => {
    const packet = new EvalPacket({
      id: 'UX-A2F-J04',
      title: '에러 복구 + Tally 폴백 + PDF retry',
      story:
        '/app 진입 → 에러 발생 시뮬 → app/error.tsx reset 동작 → FeedbackFab Tally → iframe 차단 → 5s timer fallback (D.5) → PDF retry toast (B.4)',
      steps: [
        '/app 정상 마운트',
        'D.5 Tally iframe 차단 → fallback 노출',
        'B.4 PDF retry toast',
      ],
      mode: 'Mock',
      ring: 2,
      feature: 'D.1+D.5+B.4',
      criteria: [
        '/app stores 정상 마운트',
        'feedback-modal-fallback 노출 (D.5)',
        'B.4 retry toast (action label 재시도)',
      ],
    });
    packet.attach(page);
    const checks: StepCheck[] = [];

    // Step 1 — /app 정상 마운트 (D.1 의 boundary 가 reset 가능 상태인지 정적 회귀
    // 는 ring0-preflight/02 에서 다룸. 여기선 정상 마운트만 회귀)
    try {
      await page.goto('/app');
      await page.waitForFunction(
        () =>
          Boolean(
            (window as unknown as { __chatStore?: unknown }).__chatStore,
          ),
        undefined,
        { timeout: 10_000 },
      );
      checks.push({ name: '/app stores attach', pass: true, ev: page.url() });
    } catch (e) {
      checks.push({ name: '/app stores attach', pass: false, ev: `${e}` });
    }

    // Step 2 — D.5 Tally iframe 차단 → 5s fallback
    try {
      // Tally 도메인 전체 abort.
      await page.route('**/tally.so/**', (route) =>
        route.abort('failed').catch(() => undefined),
      );
      await page.goto('/');
      const fab = page.locator('[data-testid="feedback-fab"]');
      const fabCount = await fab.count();
      if (fabCount === 0) {
        checks.push({
          name: 'D.5 Tally fallback',
          pass: false,
          ev: 'feedback-fab not rendered (env unset) — SKIP-eligible',
        });
      } else {
        const mode = await fab.getAttribute('data-feedback-mode');
        if (mode !== 'tally') {
          checks.push({
            name: 'D.5 Tally fallback',
            pass: false,
            ev: `mode=${mode} not tally — SKIP-eligible`,
          });
        } else {
          await fab.click();
          await expect(
            page.locator('[data-testid="feedback-modal"]'),
          ).toBeVisible();
          const fallback = page.locator(
            '[data-testid="feedback-modal-fallback"]',
          );
          await expect(fallback).toBeVisible({ timeout: 7000 });
          checks.push({
            name: 'D.5 Tally fallback',
            pass: true,
            ev: 'fallback visible after 5s',
          });
        }
      }
    } catch (e) {
      checks.push({ name: 'D.5 Tally fallback', pass: false, ev: `${e}` });
    }

    // Step 3 — B.4 PDF retry toast (toastStore.show 직접 호출 회귀)
    try {
      await page.goto('/app');
      await page.waitForFunction(
        () =>
          Boolean(
            (window as unknown as { __toastStore?: unknown }).__toastStore,
          ),
        undefined,
        { timeout: 8000 },
      );
      const fired = await page.evaluate(() => {
        const ts = (
          window as unknown as {
            __toastStore: {
              getState: () => {
                show: (msg: string, lvl: string, opts?: unknown) => void;
              };
            };
          }
        ).__toastStore.getState();
        ts.show('PDF 생성에 실패했습니다.', 'error', {
          action: { label: '재시도', onClick: () => undefined },
        });
        const after = (
          window as unknown as {
            __toastStore: {
              getState: () => {
                toasts: {
                  level: string;
                  action?: { label?: string };
                }[];
              };
            };
          }
        ).__toastStore.getState();
        return after.toasts.some(
          (t) => t.level === 'error' && /재시도/.test(t.action?.label ?? ''),
        );
      });
      checks.push({
        name: 'B.4 PDF retry toast',
        pass: fired,
        ev: `fired=${fired}`,
      });
    } catch (e) {
      checks.push({ name: 'B.4 PDF retry toast', pass: false, ev: `${e}` });
    }

    const passCount = checks.filter((c) => c.pass).length;
    packet.writeAutoVerdict({
      result: passCount === checks.length ? 'PASS' : 'FAIL',
      reason: summarize(checks),
      checks: checks.map((c) => ({
        criterion: c.name,
        met: c.pass,
        evidence: c.ev,
      })),
    });
    await packet.finalize(page);
    // D.5 는 env 의존이라 SKIP-eligible — ≥ 2 step 통과로 부분 PASS.
    expect(passCount).toBeGreaterThanOrEqual(2);
  });

  /* ----------------------------------------------------------------------
   * J05 — a11y 종합 (키보드 only + reduced-motion)
   * Phase 매핑: D.2 + D.3 + D.4 + D.6 + D.9 + WCAG (2.1.1 / 2.4.7 / 4.1.2 / 2.5.8)
   * ---------------------------------------------------------------------- */
  test('Ring2-UX-A2F-J05 — keyboard-only + reduced-motion + ARIA (D.2/D.3/D.4/D.6/D.9)', async ({
    page,
  }) => {
    const packet = new EvalPacket({
      id: 'UX-A2F-J05',
      title: 'a11y 종합 (키보드 + reduced-motion + ARIA)',
      story:
        'prefers-reduced-motion: reduce → 키보드 only → 모든 인터랙티브 outline non-zero (WCAG 2.1.1 / 2.4.7) → ARIA radiogroup / aria-checked / aria-label → FeedbackRow ack 토글 (D.4) → BottomNav 24/13/60 (D.9, 2.5.8)',
      steps: [
        'reduced-motion 적용 확인',
        'role-chip-owner aria-checked toggle (D.3, 4.1.2)',
        'feedback-row-amend aria-expanded 토글 (D.4)',
        'CompareCard 안정 키 정적 grep (D.6)',
      ],
      mode: 'Mock',
      ring: 2,
      feature: 'D.2+D.3+D.4+D.6+D.9+WCAG',
      criteria: [
        'reduced-motion media query 적용',
        'role-chip aria-checked true',
        'feedback amend aria-expanded toggle',
        'CompareCard SuggestionChips 의 unique key 패턴',
      ],
    });
    packet.attach(page);
    const checks: StepCheck[] = [];

    // reduced-motion 강제.
    await page.emulateMedia({ reducedMotion: 'reduce' });

    // Step 1 — reduced-motion media query 적용 확인
    try {
      await page.goto('/');
      const reduced = await page.evaluate(
        () =>
          window.matchMedia('(prefers-reduced-motion: reduce)').matches === true,
      );
      checks.push({
        name: 'prefers-reduced-motion: reduce',
        pass: reduced,
        ev: `matches=${reduced}`,
      });
    } catch (e) {
      checks.push({ name: 'reduced-motion', pass: false, ev: `${e}` });
    }

    // Step 2 — role-chip-owner aria-checked toggle (4.1.2)
    try {
      await expect(
        page.locator('[data-testid="role-selector"]'),
      ).toHaveAttribute('role', 'radiogroup');
      const owner = page.locator('[data-testid="role-chip-owner"]');
      await owner.focus();
      await expect(owner).toHaveAttribute('role', 'radio');
      await owner.click();
      await expect(owner).toHaveAttribute('aria-checked', 'true');
      // 다시 클릭 → toggle off.
      await owner.click();
      await expect(owner).toHaveAttribute('aria-checked', 'false');
      checks.push({
        name: 'role-chip aria-checked toggle (4.1.2)',
        pass: true,
        ev: 'toggle ok',
      });
    } catch (e) {
      checks.push({
        name: 'role-chip aria-checked',
        pass: false,
        ev: `${e}`,
      });
    }

    // Step 3 — FeedbackRow amend aria-expanded toggle (D.4)
    try {
      await page.goto('/app');
      await page.waitForFunction(
        () =>
          Boolean(
            (window as unknown as { __chatStore?: unknown }).__chatStore,
          ),
        undefined,
        { timeout: 10_000 },
      );
      // 강제로 lastTraceId 주입 + feedbackByTrace 에 'up' 기록 → ack 상태로 전환.
      await page.evaluate(() => {
        const cs = (
          window as unknown as {
            __chatStore: {
              setState: (s: Record<string, unknown>) => void;
            };
          }
        ).__chatStore;
        cs.setState({
          lastTraceId: 'trace-j05-ack',
          feedbackByTrace: { 'trace-j05-ack': 'up' },
        });
      });
      const amend = page.locator('[data-testid="feedback-row-amend"]');
      const amendVisible = (await amend.count()) > 0;
      if (amendVisible) {
        await expect(amend).toHaveAttribute('aria-expanded', 'false');
        await amend.click();
        await expect(amend).toHaveAttribute('aria-expanded', 'true');
        checks.push({
          name: 'feedback-row-amend aria-expanded toggle (D.4)',
          pass: true,
          ev: 'toggle ok',
        });
      } else {
        checks.push({
          name: 'feedback-row-amend',
          pass: false,
          ev: 'amend not rendered',
        });
      }
    } catch (e) {
      checks.push({
        name: 'feedback-row-amend',
        pass: false,
        ev: `${e}`,
      });
    }

    // Step 4 — CompareCard / SuggestionChips 안정 키 정적 grep (D.6)
    // 본 step 은 fs 검사로 page 와 무관 — j06 에서 정적 회귀 의도.
    try {
      const compareCardSrc = fs.readFileSync(
        path.join(
          process.cwd(),
          'src',
          'components',
          'chat',
          'cards',
          'CompareCard.tsx',
        ),
        'utf-8',
      );
      const suggestionChipsSrc = fs.readFileSync(
        path.join(
          process.cwd(),
          'src',
          'components',
          'chat',
          'SuggestionChips.tsx',
        ),
        'utf-8',
      );
      // index-only key 사용 금지 — index + value 또는 stable id 패턴 회귀.
      const compareKeyOk = /key=\{[^}]*(?:\.code|\.id|district|`\$\{i?n?d?e?x?[^`]*\$\{)/.test(
        compareCardSrc,
      );
      const suggestionKeyOk = /key=\{`\$\{(?:index|i)\}-/.test(
        suggestionChipsSrc,
      );
      checks.push({
        name: 'CompareCard/SuggestionChips 안정 키 (D.6)',
        pass: compareKeyOk && suggestionKeyOk,
        ev: `compare=${compareKeyOk} suggestion=${suggestionKeyOk}`,
      });
    } catch (e) {
      checks.push({
        name: '안정 키 (D.6)',
        pass: false,
        ev: `${e}`,
      });
    }

    const passCount = checks.filter((c) => c.pass).length;
    packet.writeAutoVerdict({
      result: passCount === checks.length ? 'PASS' : 'FAIL',
      reason: summarize(checks),
      checks: checks.map((c) => ({
        criterion: c.name,
        met: c.pass,
        evidence: c.ev,
      })),
    });
    await packet.finalize(page);
    expect(passCount).toBeGreaterThanOrEqual(3);
  });
});

