# UX Sweep Phase A-F — 단위 테스트 플랜

> 시리즈: **UX Sweep 2026-04-30** Phase A-F 후속 QA
> 본 plan 영역: 6 phase × 28 항목 단위 회귀 spec 매트릭스 + 미작성 12 시나리오 보강
> Pass 1 (mock chromium) 만 다룸. 4 viewport · real-DB · 통합 journey 는 후속 [ux-final-e2e-regression-plan.md](ux-final-e2e-regression-plan.md) 가 담당
> 선행: [A](../ui/ux-sweep-phase-a-trust-legal.md) · [B](../ui/ux-sweep-phase-b-core-blockers.md) · [C](../ui/ux-sweep-phase-c-polish.md) · [D](../ui/ux-sweep-phase-d-a11y.md) · [E](../ui/ux-sweep-phase-e-premium-deferred.md) · [F](../ui/ux-sweep-phase-f-tier-hook.md)

## Context

2026-04-30 자 UX Sweep Phase A · B · C · D · E · F 가 모두 코드 머지 완료 (총 28 구현 항목 — A4·B6·C5·D10·E1·F2). 일부 회귀 spec 은 phase 작업과 동시에 작성되었으나 (`phase-b-ux-sweep.spec.ts`, `phase-c-ux-sweep.spec.ts`, `a11y.spec.ts`, `02-error-boundary.spec.ts`, `03-tier-hook.spec.ts` 등 — 총 25 시나리오), 다음 영역이 미보완:

- **엣지케이스** — A.1 Safari Private localStorage / A.4 `?q=` 빈 문자열 / B.5 false-positive 부정 3건 / B.4 retry 5회 무한루프 가드
- **성능 회귀** — C.3 TimeSlider INP < 200ms / D.7 InlineChart `getComputedStyle` 1회 캐시
- **시각/모바일 회귀** — D.1 reset 무한 throw fallback / D.5 Tally iframe 차단 → mailto fallback / D.8 Header inline JS 부재 / D.9 BottomNav minHeight 60·24·13 / D.10 mouseout fillColor 슬롯 색 race
- **F SSR 가드** — F.1 useTier server component 컴파일 / F.2 FeatureGate import 사용처 0

총 **12 미작성 시나리오** 를 보강해 Phase 별 단위 회귀 베이스라인을 확정한다.

메모리 인용:
- [feedback_react_event_keys_unique](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_react_event_keys_unique.md) — D.6 안정 키 정적 grep
- [feedback_chat_inflight_guard](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_chat_inflight_guard.md) — B.5/B.4 staleness 가드 정합
- [feedback_streaming_diagnose_ttft](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_streaming_diagnose_ttft.md) — C.2 JumpFab 가시성 측정
- [feedback_setpreview_lastcode_race](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_setpreview_lastcode_race.md) — B.1 deselect race 검증
- [feedback_marketscope_sse_format](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_marketscope_sse_format.md) — SSE event 가 data: 안에 임베드 (Pass 1 spec 작성 시 표준 SSE 파서 금지)

## Checklist

### 그룹 1 — Phase A (신뢰/법적, 4 항목)
- [ ] **A.1 기존**: `Ring1-F11-A1` (BetaBanner dismiss + reload 유지) PASS 재현
- [ ] **A.2 기존**: `Ring1-F11-A2` (Footer GitHub 링크 env 분기) PASS 재현
- [ ] **A.3 기존**: `Ring1-F11-A3` (`/terms` · `/privacy` 200 + h1) PASS 재현
- [ ] **A.4 기존**: `Ring2-J01-A4` (Bento deeplink `?q=` 자동전송 1회) PASS 재현
- [ ] **신규 1**: `Ring1-F11-A1-EDGE-PRIVATE` — Safari Private localStorage 거부 graceful (try/catch fallback, 배너 항상 노출)
- [ ] **신규 2**: `Ring2-J01-A4-EDGE-EMPTY` — `?q=` 빈 문자열 → 자동전송 0 + URL `replaceState` scrub
- [ ] **신규 3**: `Ring1-F11-A4-BENTO-ALL6` — 6 Bento cell × cta 전수 검증 (map/chat/compare/recommend/simulation/pdf 각 q 매핑)

### 그룹 2 — Phase B (핵심 기능 막힘, 6 항목)
- [ ] **B.1~B.6 기존**: `Ring1-F01-B1`, `Ring1-F05-B2`/`B3`, `Ring1-F10-B4`, `Ring3-Negative-B5`, `Ring2-J01-B6` 6건 PASS 재현
- [ ] **신규 4**: `Ring3-Negative-B5-FALSE-POS-EXT` — negative 3건 보강 ("출력 안내", "내보낸 보고서", "PDF 형식 알려") 매칭 X
- [ ] **신규 5**: `Ring1-F10-B4-RETRY-LOOP` — toast retry 5회 연속 → 무한 루프 가드 (재호출 직렬, queue 누적 0)

### 그룹 3 — Phase C (UX polish, 5 항목)
- [ ] **C.1~C.5 기존**: `Ring1-F02-C1`/`C2`/`C4`/`C5`, `Ring1-F06-C3` 5건 PASS 재현
- [ ] **신규 6**: `Ring1-F06-C3-PERF` — TimeSlider 0→23 burst 후 INP < 200ms (Performance.measure) + console warning 0
- [ ] **신규 7**: `Ring1-F02-C4-FAILED` — failed status 도 동일 600ms transition 적용 (jarring 방지)

### 그룹 4 — Phase D (A11y / 마감, 10 항목)
- [ ] **D.1~D.6/D.10 기존**: `Ring0-D1`, `Ring1-A11Y-D2`/`D3`/`D6`, `Ring1-F12-D4`/`D5`, `Ring1-F01-D10` 7건 PASS 재현
- [ ] **신규 8**: `Ring0-D1-RESET-LOOP` — reset() 후 같은 throw 재발생 시 Next 자체 fallback (boundary self-throw 방어)
- [ ] **신규 9**: `Ring1-F12-D5-IFRAME-BLOCK` — `route.abort('failed')` 로 Tally src 차단 → 5s timer 만료 → `[data-testid="feedback-mailto"]` 노출
- [ ] **신규 10**: `Ring1-F02-D7-PERF` — InlineChart re-render 5회 시 `getComputedStyle` 호출 1회로 캐시 (PerformanceObserver longtask)
- [ ] **신규 11**: `Ring1-F11-D8-HOVER` — Header CTA hover 시 inline JS handler 부재 + Tailwind `hover:` 클래스 적용 (정적 source grep + getComputedStyle)
- [ ] **신규 12**: `Ring1-Mobile-D9-WCAG258` — BottomNav minHeight ≥ 60px / icon 24px / label 13px (computedStyle, mobile-iphone viewport)
- [ ] **신규 13**: `Ring1-F01-D10-VISUAL` — compare 슬롯 1 hover→mouseout 후 polygon fillColor 가 슬롯 색 유지 (DistrictLayer.setOptions 회귀)

### 그룹 5 — Phase E (Premium deferred, 1 항목)
- [ ] **E.3 기존**: `Ring1-F12-E3` (Premium CTA hidden when env != 'true') PASS 재현

### 그룹 6 — Phase F (Tier hook stub, 2 항목)
- [ ] **F.1/F.2 기존**: `Ring0-F1` (useTier free 하드코딩), `Ring0-F2` (FeatureGate no-op) 2건 PASS 재현
- [ ] **신규 14**: `Ring0-F1-SSR` — `useTier` import 가 server component 에서 컴파일 오류 미발생 (`tsc --noEmit` smoke + 정적 grep)
- [ ] **신규 15**: `Ring0-F2-IMPORT-MAP` — FeatureGate import 사용처 0 회귀 (Phase 2 머지 전까지 의무)

> **미작성 카운트 = 12 시나리오** (신규 1~3 = A 엣지 / 4·5 = B / 6·7 = C / 8~13 = D / 14·15 = F. 단 신규 7 의 case extension 까지 합쳐 15 작업 항목)

## 재검토 (Self-Review Gate)

- **엣지**:
  - D.5 Tally fallback 의 corp mailto 차단 환경 — kakao 채널 fallback 우선 검토 (기존 `FeedbackFab` 의 `mode='kakao'` 분기 활용); D.1 reset 무한 throw 는 Next 14 자체 가드 의존 — 본 plan 은 1차 fallback 만 검증
  - C.3 INP 측정은 Playwright `Performance.measure` 가 headless 환경에서 idle wait 의 영향을 받음 → `requestAnimationFrame` 30 frame 후 측정으로 안정화
  - D.9 mobile-iphone 단일 project 한정 — Pass 1 chromium 본 grep 에서는 skip (별도 명령으로 실행 명시)

- **메모리**:
  - `feedback_react_event_keys_unique` → D.6 안정 키 정적 grep 으로 회귀 (런타임 검증은 phase-c-ux-sweep 의 burst 시나리오로 cover 됨)
  - `feedback_chat_inflight_guard` → B.5/B.4 retry/abort 시 inflight guard 정합 — 이미 `phase-b-ux-sweep.spec.ts::Ring1-F10-B4` 에서 토스트 action 호출 직렬성 검증
  - `feedback_streaming_diagnose_ttft` → C.2 JumpFab 가시성은 30 메시지 주입 후 scrollTop 검증 (TTFT 와 무관)
  - `feedback_marketscope_sse_format` → 본 plan 의 모든 신규 시나리오 는 SSE 캡처 미사용 (정적 / 시각 / a11y 위주). Pass 3 통합 journey 만 `sseCapture.ts::attachSseCapture` 사용 (Plan 2 의무)

- **타 plan 충돌**:
  - `mobile-responsive.md` (Phase A+B+C, 2026-04-23) — BottomSheet snap / IME 가드 / FAB 위치 다룸 → 본 plan 은 D.9 BottomNav 측정값 만 다루므로 영역 비충돌
  - `landing-onboarding-feedback.md` — F11/F12/F13 1차 회귀 → 본 plan 은 A.4 엣지 + D.4/D.5 미세 보강이므로 영역 비충돌
  - 후속 Plan 2 (`ux-final-e2e-regression-plan.md`) 와는 reference-only 관계 (Plan 2 가 본 plan 의 grep 으로 위임)

## Scenario (E2E Ring Mapping)

총 **38 시나리오** = 기존 25 + 신규 13. Phase 별 매트릭스:

| # | Phase | Item | Ring | Test ID | Spec 파일 | 상태 |
|--:|:--|:--|:--:|:--|:--|:--:|
| 1 | A | A.1 dismiss | 1 | `Ring1-F11-A1` | `e2e/ring1-features/f11-landing.spec.ts` | 기존 |
| 2 | A | A.2 GitHub | 1 | `Ring1-F11-A2` | 동상 | 기존 |
| 3 | A | A.3 legal | 1 | `Ring1-F11-A3` | 동상 | 기존 |
| 4 | A | A.4 deeplink | 2 | `Ring2-J01-A4` | `e2e/ring2-journeys/j01-first-time-user.spec.ts` | 기존 |
| 5 | A | A.1 edge Private | 1 | `Ring1-F11-A1-EDGE-PRIVATE` | f11-landing (확장) | 신규 |
| 6 | A | A.4 edge empty q | 2 | `Ring2-J01-A4-EDGE-EMPTY` | j01 (확장) | 신규 |
| 7 | A | A.4 6 Bento all | 1 | `Ring1-F11-A4-BENTO-ALL6` | f11-landing (신규 describe) | 신규 |
| 8 | B | B.1 deselect | 1 | `Ring1-F01-B1` | `e2e/ring1-features/phase-b-ux-sweep.spec.ts` | 기존 |
| 9 | B | B.2 toast 한도 | 1 | `Ring1-F05-B2` | 동상 | 기존 |
| 10 | B | B.3 remove | 1 | `Ring1-F05-B3` | 동상 | 기존 |
| 11 | B | B.4 retry | 1 | `Ring1-F10-B4` | 동상 | 기존 |
| 12 | B | B.5 regex | 3 | `Ring3-Negative-B5` | 동상 | 기존 |
| 13 | B | B.6 scrub | 2 | `Ring2-J01-B6` | 동상 | 기존 |
| 14 | B | B.5 false-pos 3 | 3 | `Ring3-Negative-B5-FALSE-POS-EXT` | phase-b-ux-sweep (확장) | 신규 |
| 15 | B | B.4 retry 5x | 1 | `Ring1-F10-B4-RETRY-LOOP` | 동상 (확장) | 신규 |
| 16 | C | C.1 empty | 1 | `Ring1-F02-C1` | `e2e/ring1-features/phase-c-ux-sweep.spec.ts` | 기존 |
| 17 | C | C.2 JumpFab | 1 | `Ring1-F02-C2` | 동상 | 기존 |
| 18 | C | C.3 rAF | 1 | `Ring1-F06-C3` | 동상 | 기존 |
| 19 | C | C.4 fade | 1 | `Ring1-F02-C4` | 동상 | 기존 |
| 20 | C | C.5 active | 1 | `Ring1-F02-C5` | 동상 | 기존 |
| 21 | C | C.3 perf INP | 1 | `Ring1-F06-C3-PERF` | phase-c-ux-sweep (확장) | 신규 |
| 22 | C | C.4 failed | 1 | `Ring1-F02-C4-FAILED` | 동상 | 신규 |
| 23 | D | D.1 boundary | 0 | `Ring0-D1` | `e2e/ring0-preflight/02-error-boundary.spec.ts` | 기존 |
| 24 | D | D.2/D.3/D.6 | 1 | `Ring1-A11Y-D2/D3/D6` | `e2e/ring1-features/a11y.spec.ts` | 기존 |
| 25 | D | D.4 ack | 1 | `Ring1-F12-D4` | `e2e/ring1-features/f12-feedback.spec.ts` | 기존 |
| 26 | D | D.5 fallback | 1 | `Ring1-F12-D5` | 동상 | 기존 |
| 27 | D | D.10 race | 1 | `Ring1-F01-D10` | `e2e/ring1-features/f01-map-selection.spec.ts` | 기존 |
| 28 | D | D.1 reset loop | 0 | `Ring0-D1-RESET-LOOP` | 02-error-boundary (확장) | 신규 |
| 29 | D | D.5 iframe block | 1 | `Ring1-F12-D5-IFRAME-BLOCK` | f12-feedback (확장) | 신규 |
| 30 | D | D.7 perf | 1 | `Ring1-F02-D7-PERF` | **신규** `e2e/ring1-features/d-perf.spec.ts` | 신규 |
| 31 | D | D.8 hover | 1 | `Ring1-F11-D8-HOVER` | a11y (확장) 또는 f11-landing | 신규 |
| 32 | D | D.9 BottomNav | 1 | `Ring1-Mobile-D9-WCAG258` | **신규** `e2e/ring1-features/d9-bottomnav.spec.ts` (mobile-iphone 한정) | 신규 |
| 33 | D | D.10 visual | 1 | `Ring1-F01-D10-VISUAL` | f01-map-selection (확장) | 신규 |
| 34 | E | E.3 toggle | 1 | `Ring1-F12-E3` | f12-feedback | 기존 |
| 35 | F | F.1 hook | 0 | `Ring0-F1` | `e2e/ring0-preflight/03-tier-hook.spec.ts` | 기존 |
| 36 | F | F.2 gate | 0 | `Ring0-F2` | 동상 | 기존 |
| 37 | F | F.1 SSR | 0 | `Ring0-F1-SSR` | 03-tier-hook (확장) | 신규 |
| 38 | F | F.2 import map | 0 | `Ring0-F2-IMPORT-MAP` | 동상 | 신규 |

### 신규 spec 파일 매핑

| 신규 시나리오 ID | Destination | Action |
|---|---|---|
| `Ring1-F11-A1-EDGE-PRIVATE` | `e2e/ring1-features/f11-landing.spec.ts` | describe `'F11-A-edge'` 추가 |
| `Ring2-J01-A4-EDGE-EMPTY` | `e2e/ring2-journeys/j01-first-time-user.spec.ts` | test 추가 |
| `Ring1-F11-A4-BENTO-ALL6` | `e2e/ring1-features/f11-landing.spec.ts` | describe `'F11-A4-bento-all'` loop test |
| `Ring3-Negative-B5-FALSE-POS-EXT` | `e2e/ring1-features/phase-b-ux-sweep.spec.ts` | 기존 B5 test 안 negative 배열 확장 |
| `Ring1-F10-B4-RETRY-LOOP` | `e2e/ring1-features/phase-b-ux-sweep.spec.ts` | test 추가 |
| `Ring1-F06-C3-PERF` | `e2e/ring1-features/phase-c-ux-sweep.spec.ts` | test 추가 (PerformanceObserver) |
| `Ring1-F02-C4-FAILED` | `e2e/ring1-features/phase-c-ux-sweep.spec.ts` | test 추가 |
| `Ring0-D1-RESET-LOOP` | `e2e/ring0-preflight/02-error-boundary.spec.ts` | test 추가 (정적 grep + boundary self-throw 가정 기록) |
| `Ring1-F12-D5-IFRAME-BLOCK` | `e2e/ring1-features/f12-feedback.spec.ts` | test 추가 (route.abort) |
| `Ring1-F02-D7-PERF` | **신규** `e2e/ring1-features/d-perf.spec.ts` | 파일 신규 (D.7 + 추후 perf 모음) |
| `Ring1-F11-D8-HOVER` | `e2e/ring1-features/a11y.spec.ts` | test 추가 (정적 grep + computedStyle) |
| `Ring1-Mobile-D9-WCAG258` | **신규** `e2e/ring1-features/d9-bottomnav.spec.ts` | 파일 신규, mobile-iphone project 한정 |
| `Ring1-F01-D10-VISUAL` | `e2e/ring1-features/f01-map-selection.spec.ts` | test 추가 (시각 회귀 — fillColor 비교) |
| `Ring0-F1-SSR` | `e2e/ring0-preflight/03-tier-hook.spec.ts` | test 추가 (정적 grep) |
| `Ring0-F2-IMPORT-MAP` | 동상 | test 추가 (정적 grep `FeatureGate` import = 0) |

## Pass 반복

본 plan 은 **Pass 1 단일 통과 기준** 만 정의. 후속 multi-viewport · real-DB · 통합 journey 는 Plan 2 가 담당.

### Pass 1 — Mock chromium 전수

- **환경**: `USE_MOCK=true`, baseURL `http://localhost:3001`, project `chromium`, workers=1, retries=0, timeout 60s
- **명령**:
  ```bash
  cd frontend && \
  npx playwright test --project=chromium \
    --grep "(F11|F01|F02|F05|F06|F10|F12|A11Y|Phase B|Phase C|D-PERF|Tier-Hook|Error-Boundary|UX-A2F)"

  # D.9 단독 (mobile-iphone)
  npx playwright test --project=mobile-iphone \
    --grep "Mobile-D9-WCAG258"
  ```

- **PASS 기준**:
  - 기존 25 + 신규 13 = **38 시나리오 0 FAIL**
  - console error/warning 누적 ≤ 5 (전 시나리오 합산)
  - Phase 별 a11y 차원: D.2 outline non-zero / D.3 aria coverage 100% / D.6 key 안정성 정적 grep 0 hit
  - D.7 perf: re-render 5회 시 `getComputedStyle` 호출 = 1 (cache hit 4)
  - D.9 mobile-iphone single project 통과

- **FAIL 시 처리**:
  1. 단일 spec 격리 → atomic edit (sonnet) → 재실행
  2. 3회 fail 시 Plan 2 진입 보류 + 회피 케이스 별도 plan 분리
  3. flake 의심 시 trace.zip + screenshot artifact 보존 → root cause 분석 후 재실행

- **artifact 저장**: `docs/qa/runs/ux-phase-a-f-pass1/` (summary.md + screenshots/)

## Agent 모델

| 단계 | 모델 | 이유 |
|---|---|---|
| 본 Plan 설계 | Opus | 38 시나리오 매트릭스 + 기존 spec 인벤토리 통합 정밀도 |
| 구현 (12 신규 시나리오) | Sonnet | 단일 spec atomic edit · 표준 Playwright 패턴 |
| 검증 / Pass 1 실행 | Haiku | 체크리스트 기반 grep + verdict 기록 |

## Metadata

- **선행 plan**: `docs/plan/ui/ux-sweep-phase-{a,b,c,d,e,f}-*.md` (6 phase 코드 머지 완료)
- **후속 plan**: `docs/plan/qa/ux-final-e2e-regression-plan.md` (Plan 2 — Pass 1 verdict 가 진입 게이트)
- **USE_MOCK preflight**: 각 신규 spec 상단 주석에 `(Mock-only)` 명시 (기존 컨벤션 유지)
- **Spec naming 컨벤션**: `Ring{N}-{FCODE}-{Phase letter+number}` 그대로
- **Helpers**: `setup.ts` (`gotoApp`, `waitForMapReady`, `sendChatMessage`, `waitForCompareList`) / `prodGuard.ts` (자동 설치) / `waitSSE.ts` (`waitForChatIdle`) / `sseCapture.ts` (Pass 1 미사용 — 정적/시각/a11y 위주)
- **Playwright config**: `frontend/playwright.config.ts` 수정 없음 (기존 4 project 그대로)
- **artifact 저장 경로**: `docs/qa/runs/ux-phase-a-f-pass1/summary.md`
