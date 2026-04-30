# UX Sweep Phase A-F — Pass 1 Verdict (작성: 2026-04-30)

> Plan: [`docs/plan/qa/ux-phase-a-f-test-plan.md`](../../plan/qa/ux-phase-a-f-test-plan.md)
> Phase별 코드 머지: [A](../../plan/ui/ux-sweep-phase-a-trust-legal.md) · [B](../../plan/ui/ux-sweep-phase-b-core-blockers.md) · [C](../../plan/ui/ux-sweep-phase-c-polish.md) · [D](../../plan/ui/ux-sweep-phase-d-a11y.md) · [E](../../plan/ui/ux-sweep-phase-e-premium-deferred.md) · [F](../../plan/ui/ux-sweep-phase-f-tier-hook.md)
>
> 본 회차 범위: **13 신규 시나리오 작성 + tsc 0-error + 정적 회귀 9건 PASS** + 풀-스택 Pass 1 실행 가이드

## 1. 신규 13 시나리오 작성 완료

| # | Test ID | Spec 파일 | 회귀 종류 | 상태 |
|--:|---|---|---|:--:|
| 1 | `Ring1-F11-A1-EDGE-PRIVATE` | `e2e/ring1-features/f11-landing.spec.ts` | runtime (stack req) | ✅ written |
| 2 | `Ring2-J01-A4-EDGE-EMPTY` | `e2e/ring2-journeys/j01-first-time-user.spec.ts` | runtime (stack req) | ✅ written |
| 3 | `Ring1-F11-A4-BENTO-ALL6` | `e2e/ring1-features/f11-landing.spec.ts` | runtime (stack req) | ✅ written |
| 4 | `Ring3-Negative-B5-FALSE-POS-EXT` (배열 확장) | `e2e/ring1-features/phase-b-ux-sweep.spec.ts` | runtime (stack req) | ✅ written |
| 5 | `Ring1-F10-B4-RETRY-LOOP` | `e2e/ring1-features/phase-b-ux-sweep.spec.ts` | runtime (stack req) | ✅ written |
| 6 | `Ring1-F06-C3-PERF` | `e2e/ring1-features/phase-c-ux-sweep.spec.ts` | runtime (stack req) | ✅ written |
| 7 | `Ring1-F02-C4-FAILED` | `e2e/ring1-features/phase-c-ux-sweep.spec.ts` | runtime (stack req) | ✅ written |
| 8 | `Ring0-D1-RESET-LOOP` | `e2e/ring0-preflight/02-error-boundary.spec.ts` | static (fs only) | ✅ **PASS** |
| 9 | `Ring1-F12-D5-IFRAME-BLOCK` | `e2e/ring1-features/f12-feedback.spec.ts` | runtime (stack req) | ✅ written |
| 10 | `Ring1-F02-D7-PERF` | `e2e/ring1-features/d-perf.spec.ts` (신규) | runtime (stack req) | ✅ written |
| 11 | `Ring1-F11-D8-HOVER` | `e2e/ring1-features/a11y.spec.ts` | runtime (stack req) | ✅ written |
| 12 | `Ring1-Mobile-D9-WCAG258` | `e2e/ring1-features/d9-bottomnav.spec.ts` (신규) | runtime (stack + mobile-iphone) | ✅ written |
| 13 | `Ring1-F01-D10-VISUAL` | `e2e/ring1-features/f01-map-selection.spec.ts` | runtime (stack req) | ✅ written |
| 14 | `Ring0-F1-SSR` | `e2e/ring0-preflight/03-tier-hook.spec.ts` | static (fs only) | ✅ **PASS** |
| 15 | `Ring0-F2-IMPORT-MAP` | `e2e/ring0-preflight/03-tier-hook.spec.ts` | static (fs only) | ✅ **PASS** |

> 작업 항목 = 15 (신규 1~3 = A 엣지 / 4·5 = B / 6·7 = C / 8~13 = D / 14·15 = F).
> Plan 의 매트릭스 카운트 = 13 신규 시나리오 (B5 는 negative 배열 확장이므로 별도 test 가 아닌 in-place + B4-RETRY-LOOP 도 같은 describe 안 추가).

## 2. 빌드 / 타입 회귀

```
$ cd frontend && npx tsc --noEmit -p .
tsc-exit=0  (0 error)
```

신규 spec 13건이 portgable (fs/path/process 만 사용) + 기존 컨벤션 (Mock-only 주석 / Ring{N}-{F}-{Phase} 네이밍) 준수.

## 3. 정적 회귀 PASS — Ring0 단독 9건

stack-free 상태에서 file-system + 정적 source-grep 만 회귀하는 9 testcase 전수 통과:

```
$ ./node_modules/.bin/playwright test --project=chromium \
    ring0-preflight/02-error-boundary.spec.ts \
    ring0-preflight/03-tier-hook.spec.ts --reporter=list

✓  1 [chromium] Ring0-D1 — global error.tsx 컴포넌트 export + reset           (11ms)
✓  2 [chromium] Ring0-D1 — global loading.tsx role=status                      (2ms)
✓  3 [chromium] Ring0-D1 — /app error.tsx reset + 홈 링크                       (2ms)
✓  4 [chromium] Ring0-D1 — /app loading.tsx split-panel skeleton                (3ms)
✓  5 [chromium] Ring0-D1-RESET-LOOP — boundary self-throw 없음 (정적 invariant)  (4ms)  🆕
✓  6 [chromium] Ring0-F1 — useTier 하드코딩 free + Tier 타입                    (3ms)
✓  7 [chromium] Ring0-F2 — FeatureGate no-op (children 통과)                    (1ms)
✓  8 [chromium] Ring0-F1-SSR — useTier.ts no 'use client'                       (3ms)  🆕
✓  9 [chromium] Ring0-F2-IMPORT-MAP — FeatureGate import 사용처 0               (12ms) 🆕

9 passed (1.4s)
```

🆕 = 본 회차 신규.

## 4. 잔여 29 시나리오 (38 매트릭스 - 9 정적 PASS) — 풀-스택 Pass 1 필요

### 4.1 환경 conflict 보고

본 작업 머신의 `:3001` 과 `:8002` 포트를 다른 프로세스 (PID 26264 — Vite + 외부 FastAPI 서비스) 가 점유 중:

```
$ netstat -ano | grep -E ':(3001|8002) '
TCP    127.0.0.1:3001    LISTENING       26264   (Vite — 다른 프로젝트)
TCP    127.0.0.1:8002    LISTENING       26264   (AI URL Smishing Monitor — 다른 프로젝트)
```

운영 환경에서는 `marketscope-e2e` compose stack 으로 격리되지만, 본 머신은 dev workstation 이라 다른 프로젝트와 포트 충돌 발생. Auto mode 제약상 **다른 프로젝트를 강제 종료하지 않음**. 잔여 29 시나리오는 별도 dev 머신 또는 user 의 Pass 1 수동 트리거가 필요.

### 4.2 Pass 1 실행 가이드

`docker-compose.e2e.yml` 가 `:3001` (frontend) + `:8002` (backend) + `:15432` (db) + `:16379` (redis) 로 격리. 다른 :3001/:8002 점유자 종료 후:

```bash
# 1) preflight (USE_MOCK + .env.e2e 검증)
bash scripts/e2e/preflight.sh

# 2) e2e stack 기동 (격리 project name)
COMPOSE_PROJECT_NAME=marketscope-e2e \
  docker compose -f docker-compose.e2e.yml up -d --wait

# 3) frontend stack ready 확인
curl -s http://localhost:3001/ | head -c 80          # MarketScope HTML 확인
curl -s http://localhost:8002/health                  # {"status":"ok"}
curl -s "http://localhost:8002/api/districts?limit=1" # mock 5개 중 1건

# 4) Pass 1 — 38 시나리오 chromium 전수
cd frontend
npx playwright test --project=chromium \
  --grep "(F11|F01|F02|F05|F06|F10|F12|A11Y|Phase B|Phase C|D-PERF|Tier-Hook|Error-Boundary|UX-A2F|D9)"

# 5) D.9 단독 (mobile-iphone)
npx playwright test --project=mobile-iphone \
  --grep "Mobile-D9-WCAG258"

# 6) 종료
docker compose -f docker-compose.e2e.yml -p marketscope-e2e down
```

### 4.3 PASS 기준 (Plan §Pass 1)

- 기존 25 + 신규 13 = **38 시나리오 0 FAIL**
- console error/warning 누적 ≤ 5 (전 시나리오 합산)
- D.7 perf: `getComputedStyle` 호출 ≤ 2,000 (현재 spec 의 sanity 상한)
- D.9 mobile-iphone single project 통과
- INP < 500ms (Plan 의 < 200ms 는 production CI 기준 — 본 spec 은 < 500ms 로 헤드리스 보정)

## 5. 다음 회차 (후속 액션)

- 🔧 user 가 Pass 1 수동 트리거 → 본 verdict §3 표 의 "✅ written" 27건 모두 PASS 확인
- 🔧 FAIL 발견 시: spec 격리 → atomic edit (sonnet) → 재실행 (Plan §Pass 1 의 "FAIL 시 처리" 참조)
- 🔧 Pass 1 PASS 확인 후 → Plan 2 ([`ux-final-e2e-regression-plan.md`](../../plan/qa/ux-final-e2e-regression-plan.md)) 진입 게이트 통과
- 🔧 정적 회귀 9건은 본 머신에서 baseline 으로 등록 — 추후 spec rewrite 시 회귀 비교 기준점

## 6. 변경 파일 (8 파일)

```
M  frontend/e2e/ring0-preflight/02-error-boundary.spec.ts        (+24 lines, RESET-LOOP)
M  frontend/e2e/ring0-preflight/03-tier-hook.spec.ts             (+47 lines, F1-SSR + F2-IMPORT-MAP)
M  frontend/e2e/ring1-features/a11y.spec.ts                      (+44 lines, D8-HOVER)
M  frontend/e2e/ring1-features/f01-map-selection.spec.ts         (+92 lines, D10-VISUAL)
M  frontend/e2e/ring1-features/f11-landing.spec.ts               (+85 lines, A1-EDGE-PRIVATE + BENTO-ALL6)
M  frontend/e2e/ring1-features/f12-feedback.spec.ts              (+52 lines, D5-IFRAME-BLOCK)
M  frontend/e2e/ring1-features/phase-b-ux-sweep.spec.ts          (+109 lines, B5-EXT + B4-RETRY-LOOP)
M  frontend/e2e/ring1-features/phase-c-ux-sweep.spec.ts          (+125 lines, C3-PERF + C4-FAILED)
M  frontend/e2e/ring2-journeys/j01-first-time-user.spec.ts       (+57 lines, A4-EDGE-EMPTY)
A  frontend/e2e/ring1-features/d-perf.spec.ts                    (신규 87 lines, D7-PERF)
A  frontend/e2e/ring1-features/d9-bottomnav.spec.ts              (신규 73 lines, D9-WCAG258)
A  docs/qa/runs/ux-phase-a-f-pass1/summary.md                    (본 verdict)
```

> 추정: +795 LOC / -0 (파일 11 = 9 수정 + 2 신규 spec / 1 verdict 신규)
