# UX Sweep Phase A-F — 최종 E2E 회귀 플랜

> 시리즈: **UX Sweep 2026-04-30** Phase A-F 종합 회귀
> 본 plan 영역: 6 phase 28 항목 통합 회귀 (4 viewport · real-DB · 통합 user journey 5건)
> 1회성 sweep — Pass 1/2/3 + prod-smoke 대조
> 선행: ux-phase-a-f-test-plan.md (완료·git history) Pass 1 verdict 가 진입 게이트

## Context

ux-phase-a-f-test-plan.md (완료·git history) (이하 Plan 1) 의 Pass 1 (mock chromium) 통과 후 1회성으로 실행하는 종합 회귀. UX Sweep Phase A-F 의 28 항목이 다음을 보장:

1. **4 viewport 무회귀** — chromium / mobile-iphone / mobile-galaxy / tablet-ipad
2. **real-DB 핵심 journey 5건 + 통합 A→F user journey 5건** 정상 동작
3. **prod-smoke 정합** — 배포 후 6 케이스 + Phase A landing 회귀

Plan 1 의 시나리오는 reference-only 로 다시 열거하지 않고 grep 패턴으로 위임. 본 plan 이 새로 정의하는 것:

- **Pass 1/2/3 환경 매트릭스** (USE_MOCK + viewport project + grep 패턴)
- **통합 user journey 5건** (`Ring2-UX-A2F-J01` ~ `J05`) — Phase 횡단 시나리오
- **Metric 집계 + verdict 기록** 표준

메모리 인용:
- [feedback_compose_override_anon_node_modules](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_compose_override_anon_node_modules.md) — Pass 3 real-DB 진입 전 컨테이너 reload 강제
- [feedback_stale_container_vs_source](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_stale_container_vs_source.md) — 재배포 후 `/api/health/detail` 200 확인
- [feedback_e2e_user_message_pollution](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_e2e_user_message_pollution.md) — `body.innerText` 매처는 user 쿼리도 포함 → 검증 키워드 분리
- [feedback_playwright_sse_capture](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_playwright_sse_capture.md) — Pass 3 SSE 캡처는 `attachSseCapture` 사용, `page.route` + `request.fetch` 금지
- [feedback_marketscope_sse_format](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_marketscope_sse_format.md) — `event:` 라인 없이 type 이 `data:` JSON 안에 임베드

## Checklist

- [ ] **선행 게이트**: Plan 1 verdict ✅ 확인 (`docs/qa/runs/ux-phase-a-f-pass1/summary.md`)
- [ ] **Pass 1**: mock chromium 전수 (Ring 0~3 전체 + UX phase spec 12 신규) → 총 시나리오 수 / PASS rate / FAIL 분류 기록
- [ ] **Pass 2**: mock 4 viewport (chromium / mobile-iphone / mobile-galaxy / tablet-ipad) — 모바일 회귀 핵심 (D.9 BottomNav · B.3 toast 위치 · C.2 JumpFab vs BottomSheet handle · A.4 deeplink mobile)
- [ ] **Pass 3**: real-DB chromium 핵심 journey 5건 + 통합 phase A→F user journey 5건 (`Ring2-UX-A2F-J01~J05`)
- [ ] **prod-smoke 대조** (배포 후): `prod-smoke.spec.ts` 6 케이스 + Phase A landing 회귀 (BetaBanner / Footer / Bento)
- [ ] **Metric 집계**: 총 테스트 수 / PASS rate / FAIL 분류 (P0 실 회귀 / false-fail / noise) / artifact 경로 기록
- [ ] **verdict 기록**: 본 plan 의 Pass 반복 로그 갱신 후 `/status-update` 호출

## 재검토 (Self-Review Gate)

- **엣지**:
  - real-DB Pass 3 가 LLM 호출을 동반하므로 timeout 600s 유지 + flake 재시도 정책 (j01 real mode 기존 skip 패턴 유지) — Plan 1 의 정적 시나리오와 달리 의미 단위 검증으로 한정
  - 통합 J01~J05 는 Phase 횡단이므로 한 시나리오 fail 이 다음 phase 검증 차단 가능 — 각 step 독립 try/catch 로 부분 PASS 기록
  - J03 mobile-real 동시 실행은 BottomSheet IME 오버랩 race 가능성 → mock 한정 유지, real-DB skip 허용
  - prod-smoke Pass 는 외부 도메인 fetch 가 prodGuard 의 의도된 차단 대상 — `prod-smoke.spec.ts` 만 명시적 prodGuard 우회

- **메모리**:
  - `feedback_compose_override_anon_node_modules` → Pass 3 진입 전 `docker compose restart frontend backend` 강제, anonymous volume 함정 회피
  - `feedback_stale_container_vs_source` → real-DB Pass 3 시작 시 `/api/health/detail` 200 + 컨테이너 SHA 검증
  - `feedback_e2e_user_message_pollution` → 통합 journey 의 SSE 검증은 `body.innerText` 가 아닌 `[data-testid]` locator 또는 `attachSseCapture` events 배열 직접 검사
  - `feedback_playwright_sse_capture` → J01/J02/J04 의 SSE 검증 모두 `attachSseCapture` 사용
  - `feedback_marketscope_sse_format` → SSE event type 은 `data: {"type":...}` JSON 내부 추출

- **타 plan 충돌**:
  - Plan 1 과 시나리오 중복 시 본 plan 은 reference-only (grep `Ring1-` 으로 일괄 위임)
  - `prod-baked-url-smoke-2026-04-24.md` (prod-smoke 정합 plan) 와는 baseURL 분기로 비충돌
  - `load-test.md` 는 별도 부하 시나리오, 본 plan 영역 외

## Scenario (E2E Ring Mapping)

총 시나리오 = Plan 1 의 38 + 통합 5 journey = **43 시나리오** (재실행 grep 단위는 Pass 별 다름).

### Pass × Ring × Project 매트릭스

| Pass | Ring | Scope | Spec 묶음 | 신규 ID |
|---|:--:|---|---|---|
| 1 | 0 | preflight | `00-stack-up`, `02-error-boundary`, `03-tier-hook`, `stats-aggregate` | — (Plan 1 reference) |
| 1 | 1 | features | `f01~f12` + `a11y` + `phase-b-ux-sweep` + `phase-c-ux-sweep` + `d-perf` + `d9-bottomnav` | — |
| 1 | 2 | journeys | `j01~j05` | — |
| 1 | 3 | negative | `p0-regression`, `neg-*`, `l1-langfuse` | — |
| 2 | 1 | viewport mobile-iphone | 동일 + D.9 / B.3 toast 위치 / C.2 JumpFab | — |
| 2 | 1 | viewport mobile-galaxy | 동상 | — |
| 2 | 1 | viewport tablet-ipad | 동상 | — |
| 3 | 2 | real-DB | `j01 / j02 / j03 / j04 / j05` (real mode 만 PASS) | — |
| 3 | 2 | UX A→F integration | **신규 5건** | `Ring2-UX-A2F-J01`/`J02`/`J03`/`J04`/`J05` |
| smoke | prod | prod-smoke | `prod-smoke.spec.ts` + Phase A landing 회귀 | — |

### 통합 user journey 5건 (신규 — `Ring2-UX-A2F-J01~J05`)

| ID | 제목 | Phase 매핑 | 시나리오 outline |
|---|---|---|---|
| `Ring2-UX-A2F-J01` | 신규 사용자 onboarding-to-feedback | A.4 + B.6 + F11 + F12 + F13 + D.4 | 랜딩 진입 → role(owner) 선택 → Bento "AI 분석" 클릭 → /app deeplink → URL `?q=` scrub 검증 (B.6) → SummaryCard preview (F13) → "강남역 분석해줘" SSE done → FeedbackRow 👍 클릭 (F12) → ack → "수정" 토글 (D.4) |
| `Ring2-UX-A2F-J02` | 비교 모드 풀 사이클 | B.1 + B.2 + B.3 + B.4 + B.5 | 강남 클릭 → 다시 클릭 deselect (B.1) → compareMode ON → 강남/홍대/건대/명동 4클릭 → toast (B.2) + length=3 → CompareCard × 클릭 → toast + length=2 (B.3) → "PDF 출력해줘" 매치 (B.5) → 의도적 throw (B.4) → retry toast → 재시도 클릭 |
| `Ring2-UX-A2F-J03` | 모바일 첫 진입 (iPhone 12) | C.2 + D.2 + D.9 + B.3 | mobile-iphone viewport, BottomSheet 챗 노출 → BottomNav minHeight 60px / 24px / 13px (D.9) → Tab 키 순회 focus-visible (D.2) → 30메시지 주입 → JumpFab 가시 (C.2) → BottomSheet handle 과 미충돌 + safe-area-inset-bottom 가산 |
| `Ring2-UX-A2F-J04` | 에러 복구 + Tally 폴백 | D.1 + D.5 + B.4 | /app 진입 → throw 의도 시뮬 → app/error.tsx 노출 (`data-testid="app-route-error"`) → reset() → 정상 복구 → Feedback FAB → Tally iframe `route.abort` → 5s 타이머 → mailto fallback (D.5) → PDF 호출 throw → retry toast (B.4) |
| `Ring2-UX-A2F-J05` | a11y 종합 (키보드 only + reduced-motion) | D.2 + D.3 + D.4 + D.6 + D.9 + WCAG | `prefers-reduced-motion: reduce` 강제 → keyboard only 탐색: Tab 순회 모든 인터랙티브 outline non-zero (WCAG 2.1.1 / 2.4.7) → ARIA: `role=radio`/`aria-checked` (RoleSelector, 4.1.2) / `aria-label` (Footer/Header) / `role=status` (loading) / 안정 키 (D.6 정적 grep) / FeedbackRow ack 토글 (D.4) / BottomNav size (2.5.8) |

### 신규 spec 파일 매핑

- **신규 1 파일**: `frontend/e2e/ring2-journeys/j06-ux-a2f-integration.spec.ts` — J01~J05 단일 파일에 통합

## Pass 반복

### Pass 1 — Mock chromium 전수

- **환경**: `USE_MOCK=true`, baseURL `http://localhost:3001`, project `chromium`, workers=1, retries=0, timeout 60s
- **사전 조건**: Plan 1 Pass 1 verdict ✅
- **명령**:
  ```bash
  cd frontend && \
  npx playwright test --project=chromium \
    --grep "(Ring0|Ring1|Ring2-J|Ring3|Phase B|Phase C|A11Y|UX-A2F)"
  ```
- **통과 기준**: PASS rate ≥ 95% / FAIL ≤ 5건 / 모두 P0 아님 (rubric noise 또는 known-skip)

### Pass 2 — Mock 4 viewport (모바일 회귀 핵심)

- **환경**: `USE_MOCK=true`, projects `mobile-iphone` + `mobile-galaxy` + `tablet-ipad`, viewport 별 의미 있는 spec 만 grep 한정
- **사전 조건**: Pass 1 verdict ✅
- **명령**:
  ```bash
  cd frontend && \
  npx playwright test --project=mobile-iphone --grep "D9|B-UX|A4|J03|JumpFab" && \
  npx playwright test --project=mobile-galaxy --grep "D9|B-UX|J03" && \
  npx playwright test --project=tablet-ipad --grep "Phase B|Phase C|A4|D2"
  ```
- **통과 기준**:
  - D.9 (BottomNav minHeight ≥ 60) iphone+galaxy PASS
  - B.3 toast 가 iphone safe-area 와 미충돌
  - C.2 JumpFab 위치 mobile-iphone 에서 BottomSheet handle 과 ≥ 8px 간격
  - A.4 deeplink mobile 자동전송 1회 (B.6 scrub 정합)

### Pass 3 — Real-DB chromium 핵심 + 통합 journey

- **환경**: `USE_MOCK=false`, `LLM_PROVIDER=anthropic`, baseURL `:3001`, project `chromium`, timeout 600s
- **사전 조건**:
  - `docker compose restart frontend backend` (anonymous volume 회피)
  - `curl -fsS http://localhost:8000/api/health/detail | jq '.use_mock'` → `false` 확인
  - 컨테이너 SHA 검증: `docker inspect marketscope-frontend | jq '.[0].Image'` 가 직전 빌드와 일치
- **명령**:
  ```bash
  cd frontend && \
  USE_MOCK=false npx playwright test --project=chromium \
    --grep "(F02-H4|F05-H1|F10-H1|J02|J03|J04|J05|UX-A2F-J0[1-5])"
  ```
  > UX-A2F-J03 모바일은 viewport project 와 real-DB 동시 실행 시 flake — Mock 한정 유지 (J03 real-DB SKIP 허용)
- **통과 기준**:
  - real-DB 핵심 5 journey PASS (F02-H4 / F05-H1 / F10-H1 / j02-real / j04-real)
  - 통합 5 journey 4건 PASS (J03 mobile-real 은 SKIP 허용)
  - SSE done 100% (timeout 만료 0)
  - XML leak 0 (`(get_*\)`/`(recommend_*\)` 등 raw tool 함수명 grep 결과 0)
  - prodGuard hit 0 (`docs/qa/runs/.../prod-hit-log.jsonl` empty)

### prod-smoke 대조 (배포 후)

- **환경**: `E2E_BASE_URL=https://marketscope.robitlabs.co.kr`, project `chromium`
- **사전 조건**: Pass 1/2/3 PASS + 프로덕션 배포 완료
- **명령**:
  ```bash
  cd frontend && \
  E2E_BASE_URL=https://marketscope.robitlabs.co.kr \
  npx playwright test prod-smoke --project=chromium \
    --grep "F11|BetaBanner|Footer|Bento"
  ```
- **통과 기준**: 기존 6 케이스 + Phase A landing 회귀 = ALL PASS

### FAIL 분류 + 처리

| 분류 | 대응 |
|---|---|
| **P0 실 회귀** | 즉시 hotfix plan 분리 (`docs/plan/fix/`) — 본 plan 은 verdict FAIL 기록 후 종료 |
| **false-fail** (rubric noise) | 시나리오 보정 → 재실행 1회 |
| **noise** (flake / 외부 의존 timeout) | retry 1회 → 재 fail 시 known-flake 로 verdict 기록 (skip 허용) |

### Metric 집계

`docs/qa/runs/ux-final-e2e-2026-04-30/summary.md` 에 다음을 기록:

```markdown
# UX Final E2E Regression — 2026-04-30

## Pass 1 (Mock chromium 전수)
- 총 시나리오: NN
- PASS: NN (NN%)
- FAIL: NN (P0 X / false X / noise X)
- 실행 시간: NN min

## Pass 2 (Mock 4 viewport)
- 총 시나리오 (3 project 합산): NN
- ...

## Pass 3 (Real-DB + 통합 J01~J05)
- 총 시나리오: 9 (real 5 + 통합 4 + J03 mobile-real SKIP)
- ...

## prod-smoke
- 총 시나리오: 6 + N
- ...

## verdict
- ✅ ALL PASS / ⚠️ PARTIAL / ❌ FAIL
- Phase A-F 통합 회귀 베이스라인 확정 — 다음 회귀 sweep 까지 지속
```

## Agent 모델

| 단계 | 모델 | 이유 |
|---|---|---|
| 본 Plan 설계 | Opus | 통합 viewport / real-DB / journey 매트릭스 1회성 설계 |
| 통합 5 journey spec 구현 | Sonnet | 표준 spec 패턴 + Phase 횡단 step 조합 |
| Pass 1/2/3 실행 + verdict | Haiku | 체크리스트 기반 grep / artifact 정리 |
| 최종 점검 | Haiku | 누락 ID grep / 통과 기준 합산 / status-update |

## Metadata

- **선행 plan**: ux-phase-a-f-test-plan.md (완료·git history) (Plan 1) — Pass 1 verdict 가 본 plan 진입 게이트
- **메모리 활용**: `feedback_compose_override_anon_node_modules` / `feedback_stale_container_vs_source` / `feedback_e2e_user_message_pollution` / `feedback_playwright_sse_capture` / `feedback_marketscope_sse_format`
- **prod-smoke 정합 plan**: `docs/plan/infra/prod-baked-url-smoke-2026-04-24.md`
- **artifact 저장 경로**: `docs/qa/runs/ux-final-e2e-2026-04-30/pass{1,2,3}/summary.md` + `screenshots/` + `prod-hit-log.jsonl`
- **Spec naming 컨벤션 추가**: 통합 journey 는 `Ring2-UX-A2F-J0N` (N=1~5)
- **신규 spec 파일**: `frontend/e2e/ring2-journeys/j06-ux-a2f-integration.spec.ts` (J01~J05 단일 파일)
- **후속 plan**:
  - 본 Plan PASS → `/status-update` 만 호출 (신규 plan 분리 X)
  - 본 Plan Pass 3 에서 P0 회귀 발견 시 → `docs/plan/fix/<area>-fix-2026-XX.md` 분리
- **Helpers**: Plan 1 과 동일 (`setup.ts` + `prodGuard.ts` 자동 / `sseCapture.ts` Pass 3 사용)
- **Playwright config**: 수정 없음
- **prod 도메인**: `marketscope.robitlabs.co.kr` (prod-smoke 만 baseURL 변경)
