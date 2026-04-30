# UX Final E2E Regression — 2026-04-30 (Plan 2)

> Plan: [`docs/plan/qa/ux-final-e2e-regression-plan.md`](../../../plan/qa/ux-final-e2e-regression-plan.md)
> 선행 게이트: [`docs/qa/runs/ux-phase-a-f-pass1/summary.md`](../ux-phase-a-f-pass1/summary.md) ✅
>
> 본 회차 범위: **통합 5 journey spec 신규 작성 + tsc 0-error + ESLint 0 + 정적 baseline 9 testcase 재현 PASS** + Pass 1/2/3 + prod-smoke 실행 가이드

## 1. 통합 5 journey spec 작성 완료

| # | Test ID | Spec 파일 | Phase 매핑 | 상태 |
|--:|---|---|---|:--:|
| 1 | `Ring2-UX-A2F-J01` | `e2e/ring2-journeys/j06-ux-a2f-integration.spec.ts:48` | A.4 + B.6 + F11 + F12 + F13 + D.4 | ✅ written |
| 2 | `Ring2-UX-A2F-J02` | `j06-ux-a2f-integration.spec.ts:295` | B.1 + B.2 + B.3 + B.4 + B.5 | ✅ written |
| 3 | `Ring2-UX-A2F-J03` | `j06-ux-a2f-integration.spec.ts:561` | C.2 + D.2 + D.9 + B.3 (mobile-iphone) | ✅ written |
| 4 | `Ring2-UX-A2F-J04` | `j06-ux-a2f-integration.spec.ts:730` | D.1 + D.5 + B.4 | ✅ written |
| 5 | `Ring2-UX-A2F-J05` | `j06-ux-a2f-integration.spec.ts:883` | D.2 + D.3 + D.4 + D.6 + D.9 + WCAG | ✅ written |

> Plan §Scenario 의 신규 5 journey = 1 신규 spec 파일 (`j06-ux-a2f-integration.spec.ts`).
> 각 step 은 독립 try/catch — 한 step fail 이 다음 phase 검증을 차단하지 않음
> (`StepCheck[]` 누적 후 `passCount >= 임계` 일 때만 test failure).

## 2. 빌드 / 타입 회귀

```
$ cd frontend && npx tsc --noEmit -p .
tsc-exit=0  (0 error)

$ npx next lint --file e2e/ring2-journeys/j06-ux-a2f-integration.spec.ts
✔ No ESLint warnings or errors
```

## 3. 정적 baseline 9 testcase 재현 PASS

stack-free 상태에서 file-system + 정적 source-grep 만 회귀하는 9 testcase 전수 통과 (Plan 1 verdict 와 동일):

```
$ ./node_modules/.bin/playwright test --project=chromium \
    ring0-preflight/02-error-boundary.spec.ts \
    ring0-preflight/03-tier-hook.spec.ts --reporter=list

✓  1 [chromium] Ring0-D1 — global error.tsx 컴포넌트 export + reset           (8ms)
✓  2 [chromium] Ring0-D1 — global loading.tsx role=status                      (2ms)
✓  3 [chromium] Ring0-D1 — /app error.tsx reset + 홈 링크                       (2ms)
✓  4 [chromium] Ring0-D1 — /app loading.tsx split-panel skeleton                (2ms)
✓  5 [chromium] Ring0-D1-RESET-LOOP — boundary self-throw 없음 (정적 invariant)  (3ms)
✓  6 [chromium] Ring0-F1 — useTier 하드코딩 free + Tier 타입                    (2ms)
✓  7 [chromium] Ring0-F2 — FeatureGate no-op (children 통과)                    (2ms)
✓  8 [chromium] Ring0-F1-SSR — useTier.ts no 'use client'                       (4ms)
✓  9 [chromium] Ring0-F2-IMPORT-MAP — FeatureGate import 사용처 0               (7ms)

9 passed (1.2s)
```

## 4. j06 dry-list — 5 testcase 인식

```
$ ./node_modules/.bin/playwright test --project=chromium --list \
    e2e/ring2-journeys/j06-ux-a2f-integration.spec.ts

[chromium] Ring2-UX-A2F-J01 — onboarding → /app deeplink → preview → feedback ack+amend
[chromium] Ring2-UX-A2F-J02 — compare full cycle: deselect → 4 click toast → × shrink → PDF retry
[chromium] Ring2-UX-A2F-J03 — mobile first enter: BottomNav size + JumpFab + focus-visible
[chromium] Ring2-UX-A2F-J04 — recovery: app/error.tsx reset + Tally fallback + PDF retry
[chromium] Ring2-UX-A2F-J05 — keyboard-only + reduced-motion + ARIA (D.2/D.3/D.4/D.6/D.9)

Total: 5 tests in 1 file
```

> Plan 매트릭스: 본 plan §Scenario 의 통합 5 journey = j06 의 5 testcase 1:1 매핑.

## 5. 잔여 Pass 1/2/3 + prod-smoke — runtime 실행 보류 (stack 점유)

### 5.1 환경 conflict 보고 (Plan 1 verdict 와 동일)

본 작업 머신의 `:3001` / `:8002` 포트는 다른 프로젝트 (PID 26264 — Vite + 외부 FastAPI) 가 점유 중:

```
$ netstat -ano | grep -E ':(3001|8002) '
TCP    127.0.0.1:3001    LISTENING       26264   (Vite — 다른 프로젝트)
TCP    127.0.0.1:8002    LISTENING       26264   (AI URL Smishing Monitor — 다른 프로젝트)
```

`docker-compose.e2e.yml` 가 `:3001/:8002/:15432/:16379` 격리. Auto mode 제약상 **다른 프로젝트 강제 종료 불가**. Pass 1/2/3 + prod-smoke 의 runtime 회귀는 별도 dev 머신 또는 user 의 수동 트리거 필요.

### 5.2 Pass 1 — Mock chromium 전수

`docker-compose.e2e.yml` 가 격리 stack 제공. 다른 :3001/:8002 점유자 종료 후:

```bash
# 1) preflight
bash scripts/e2e/preflight.sh

# 2) e2e stack 기동
COMPOSE_PROJECT_NAME=marketscope-e2e \
  docker compose -f docker-compose.e2e.yml up -d --wait

# 3) ready 확인
curl -s http://localhost:3001/ | head -c 80
curl -s http://localhost:8002/health
curl -s "http://localhost:8002/api/districts?limit=1"

# 4) Pass 1 실행 (Plan §Pass 1 명령)
cd frontend && \
  npx playwright test --project=chromium \
    --grep "(Ring0|Ring1|Ring2-J|Ring3|Phase B|Phase C|A11Y|UX-A2F)"
```

**PASS 기준**: 38 (Plan 1 매트릭스) + 5 (j06 신규) = 43 시나리오, FAIL ≤ 5 (모두 P0 아님).

### 5.3 Pass 2 — Mock 4 viewport (모바일 회귀)

```bash
cd frontend && \
  npx playwright test --project=mobile-iphone --grep "D9|B-UX|A4|J03|JumpFab" && \
  npx playwright test --project=mobile-galaxy  --grep "D9|B-UX|J03" && \
  npx playwright test --project=tablet-ipad    --grep "Phase B|Phase C|A4|D2"
```

**PASS 기준**:
- D.9 (BottomNav minHeight ≥ 60) iphone+galaxy PASS
- B.3 toast iphone safe-area 미충돌
- C.2 JumpFab BottomSheet handle ≥ 8px 간격
- A.4 deeplink mobile 자동전송 1회

### 5.4 Pass 3 — Real-DB chromium 핵심 + 통합 journey

```bash
docker compose restart frontend backend  # anonymous volume 회피 (memory: feedback_compose_override_anon_node_modules)
curl -fsS http://localhost:8000/api/health/detail | jq '.use_mock'  # false 확인

cd frontend && \
  USE_MOCK=false npx playwright test --project=chromium \
    --grep "(F02-H4|F05-H1|F10-H1|J02|J03|J04|J05|UX-A2F-J0[1-5])"
```

**PASS 기준**:
- real-DB 핵심 5 journey PASS (F02-H4 / F05-H1 / F10-H1 / j02-real / j04-real)
- 통합 5 journey 4건 PASS (J03 mobile-real SKIP 허용)
- SSE done 100% (timeout 만료 0)
- XML leak 0 (`(get_*\)` / `(recommend_*\)` raw tool name grep 0)
- prodGuard hit 0

### 5.5 prod-smoke 대조 (배포 후)

```bash
cd frontend && \
  E2E_BASE_URL=https://marketscope.robitlabs.co.kr \
  npx playwright test prod-smoke --project=chromium \
    --grep "F11|BetaBanner|Footer|Bento"
```

**PASS 기준**: 기존 6 케이스 + Phase A landing 회귀 = ALL PASS.

## 6. FAIL 분류 + 처리 (Plan §FAIL 분류 인용)

| 분류 | 대응 |
|---|---|
| **P0 실 회귀** | 즉시 hotfix plan 분리 (`docs/plan/fix/`) — 본 plan verdict FAIL 기록 후 종료 |
| **false-fail** (rubric noise) | 시나리오 보정 → 재실행 1회 |
| **noise** (flake / 외부 의존 timeout) | retry 1회 → 재 fail 시 known-flake (skip 허용) |

## 7. verdict (본 회차)

- ✅ **PARTIAL PASS — 정적 baseline + spec 신규**
  - 통합 5 journey spec 작성 완료
  - tsc 0 / ESLint 0 / 정적 9 testcase 재현 PASS
  - j06 dry-list 5 testcase 인식
- ⏳ **Pass 1/2/3 + prod-smoke runtime — 보류**
  - 본 머신 :3001/:8002 점유로 user 수동 트리거 권장
  - 위 §5 명령 그대로 실행 후 본 verdict 갱신

## 8. 다음 회차 후속 액션

- 🔧 user Pass 1 수동 트리거 → 38+5=43 시나리오 chromium 전수 PASS 확인
- 🔧 Pass 2 mobile-iphone / mobile-galaxy / tablet-ipad 회귀
- 🔧 `docker compose restart frontend backend` 후 Pass 3 real-DB
- 🔧 본 verdict §7 갱신 → ALL PASS 시 `/status-update` 호출
- 🔧 P0 회귀 발견 시 → `docs/plan/fix/<area>-fix-2026-XX.md` 분리

## 9. 변경 파일 (2 파일)

```
A  frontend/e2e/ring2-journeys/j06-ux-a2f-integration.spec.ts   (+ ~960 lines, J01~J05 통합)
A  docs/qa/runs/ux-final-e2e-2026-04-30/summary.md              (본 verdict)
```

> 추정: +960 LOC / -0 (1 spec 신규 + 1 verdict 신규)

## 10. 참조

- 선행 plan: [`ux-phase-a-f-test-plan.md`](../../../plan/qa/ux-phase-a-f-test-plan.md) (Plan 1)
- 본 plan: [`ux-final-e2e-regression-plan.md`](../../../plan/qa/ux-final-e2e-regression-plan.md) (Plan 2)
- Phase 코드 머지: [A](../../../plan/ui/ux-sweep-phase-a-trust-legal.md) · [B](../../../plan/ui/ux-sweep-phase-b-core-blockers.md) · [C](../../../plan/ui/ux-sweep-phase-c-polish.md) · [D](../../../plan/ui/ux-sweep-phase-d-a11y.md) · [E](../../../plan/ui/ux-sweep-phase-e-premium-deferred.md) · [F](../../../plan/ui/ux-sweep-phase-f-tier-hook.md)
- Plan 1 verdict: [`ux-phase-a-f-pass1/summary.md`](../ux-phase-a-f-pass1/summary.md)
- 메모리: `feedback_compose_override_anon_node_modules` · `feedback_stale_container_vs_source` · `feedback_e2e_user_message_pollution` · `feedback_playwright_sse_capture` · `feedback_marketscope_sse_format`
