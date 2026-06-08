# 현재 진행 상황

> 최종 갱신: 2026-06-08
> **2026-06-08 QA(/qa) Standard 풀앱 패스 — out_of_scope/greeting 중복 suggestion fix + 회귀 테스트** ⭐ — Docker 실데이터 스택(frontend :3000 / backend :8000 / PostGIS 1,650 상권 / Redis) 기동 후 브라우저+SSE 검증. 기존 이미지 6주 stale → current source 재빌드(backend+frontend, pip SSL 은 Dockerfile `PIP_TRUSTED_HOST` build-arg 우회). 건강도 **98→99**. **ISSUE-001(medium) fix**: `graph.py` 스트림 말미 fallback suggestion 방출을 `greeting_direct`/`clarification_direct` 모드에서 skip — greeting/clarification 노드가 실행 중 tailored suggestion 을 직접 방출하는데 말미 generic 셋이 한 번 더 방출돼 client replace 로 tailored 를 덮어쓰던 문제(서울 외 거부 응답에 "이 자리 위험하지 않아?" 노출). 회귀 `test_graph_suggestion_emission.py` 2 passed. main 머지 후 **origin push 완료** (`44b9438..eb3e10f`, 4커밋). 검증(SSE): 부산/제주 out_of_scope=suggestion 1회(tailored)·greeting 1회·normal summary 1회(card+evaluator 유지)·회귀 0. 정상 플로우 전수 PASS(F03 요약/F05 비교 멀티상권추출/F07 추천/F13 프리뷰/F06 히트맵/검색 자동완성/privacy·terms/모바일), 콘솔 에러 0·XML leak 0·실수치 월환산 정상. **디퍼 2건**: ISSUE-003(recommend 가 점포 1~2개 카테고리를 점포당매출 아티팩트로 1순위 — 성수 편의점 score100/월2억 from 1점포, accuracy-eval 트랙 권장) · ISSUE-002(랜딩 H1 단어중간 줄바꿈 cosmetic). **환경 플래그(미수정)**: `.env`/`.env.dev` 의 `NEXT_PUBLIC_API_URL=:3000`(프론트포트) → 재빌드 시 chat SSE 버퍼링, `:8000` 권장(QA 중 임시 override). 리포트 `.gstack/qa-reports/qa-report-localhost-2026-06-08.md`.
> **2026-05-07 4 Plan 일괄 Pass 1 — Heatmap Singleflight + Backend pytest 확장 + W1 Type Boost 측정/튜닝 + Langfuse L2 Foundation** ⭐ — 4 P1 Plan ([heatmap-singleflight-reintroduce](../plan/infra/heatmap-singleflight-reintroduce.md) · [backend-pytest-coverage-expansion](../plan/infra/backend-pytest-coverage-expansion.md) · [w1-type-boost-tuning-2026-05-06](../plan/fix/w1-type-boost-tuning-2026-05-06.md) · [langfuse-l2-token-cost-eval](../plan/infra/langfuse-l2-token-cost-eval.md)) 의 Pass 1 일괄 구현. (1) **Heatmap Singleflight** — `services/singleflight.py` 재작성 (per-key Future + asyncio.Lock + leader cancel-shield), `map_data.py::get_heatmap[/all]` 통합, `/metrics` 에 `singleflight_coalesced_total` 노출. 9 testcase PASS (concurrent 50 → fn() 1회, exception propagation, follower-cancel-no-leak). (2) **Backend pytest 확장** — `conftest.py` fixture 5종 (`mock_da` / `memory_cache` / `category_resolver_default` / `app_client` / `mock_district_code`), `test_services_{cache,circuit_breaker,category_resolver}.py` + `test_repos_mock.py` (10 protocol smoke) + `test_routes_health_and_map.py` (lifespan + httpx ASGITransport) — 35 신규 testcase. `pyproject.toml` coverage 설정 + `scripts/run_tests.sh` + `.github/workflows/ci.yml::backend-test` dummy env + coverage XML artifact 통합. (3) **W1 Type Boost 측정** — `tests/data/w1_adversarial_2026-05-06.yaml` 32 case (TM=6/CDST=5/ST=5/CTS=5/BR=6/ABST=5), `scripts/w1_eval.py` (baseline + 4×3 sweep grid), 회귀 가드 `test_adversarial_accuracy_meets_95pct`. **Baseline 96.9% (31/32)**, sweep 12 셀 모두 동일 96.9% — boost/damp 와 무관한 단일 구조적 fail (BR-6, 3-char query × 22-char alias-paren). 현재 (boost=0.15, damp=0.5) 유지 채택. (4) **Langfuse L2 Foundation** — `langfuse_tracer.py::_normalize_usage` (LangChain/Anthropic/Gemini/OpenAI 4 shape 흡수) + `attach_generation_usage` (v3 `start_observation(as_type="generation", usage_details, prompt_name+version metadata)`) + `prompt_version("v1.0.0")` + `_git_sha()` 헬퍼. 12 testcase PASS. 노드 wiring (planner/evaluator/respond) + L2-C eval harness 는 Pass 2/3 으로 분리. **검증**: 전체 backend pytest **120 passed / 8 skipped** (신규 65 + 기존 55, 8 skip = `app_client` fixture host structlog 미설치). ruff PASS. 기존 `test_smoke::langfuse_enabled` host env fail 도 conftest 의 `LANGFUSE_PUBLIC_KEY=""` 로 자동 해결. CI workflow 에 dummy env 주입 + coverage XML artifact.
> **2026-04-30 UX Sweep Phase A-F Plan 2 Pass 1 — 통합 5 journey spec 신규 + 정적 baseline 9 testcase PASS** ⭐ — Plan [ux-final-e2e-regression-plan](../plan/qa/ux-final-e2e-regression-plan.md). Plan 1 verdict ✅ 후속 회차 — `frontend/e2e/ring2-journeys/j06-ux-a2f-integration.spec.ts` 신규 1 파일 (~960 LOC) 에 Phase A→F 횡단 5 journey 1:1 매핑 (J01 onboarding-to-feedback A.4+B.6+F11+F12+F13+D.4 / J02 compare 풀사이클 B.1~B.5 / J03 모바일 첫 진입 C.2+D.2+D.9+B.3 / J04 에러복구+Tally폴백 D.1+D.5+B.4 / J05 a11y 종합 D.2+D.3+D.4+D.6+D.9+WCAG). 각 step 독립 try/catch 로 부분 PASS 가능 (StepCheck[] 누적 + passCount ≥ 임계 시만 fail). 검증: tsc 0 error · next lint 0 warning · dry-list 5 testcase 인식 · 정적 baseline 9 testcase (Ring0-D1 + Ring0-F1 + Ring0-F2) 재현 PASS. Pass 1/2/3 + prod-smoke runtime 은 본 머신 :3001/:8002 점유로 user 수동 트리거 권장. [Verdict](../qa/runs/ux-final-e2e-2026-04-30/summary.md)
> **2026-04-30 UX Sweep Phase A-F Pass 1 — 13 신규 시나리오 작성** ⭐ — Plan [ux-phase-a-f-test-plan](../plan/qa/ux-phase-a-f-test-plan.md). 기존 25 + 신규 13 = 38 시나리오 매트릭스 확정. 변경 9 spec 수정 + 2 spec 신규 + verdict 1: A 엣지 3건 (`A1-EDGE-PRIVATE` Safari Private localStorage / `A4-EDGE-EMPTY` 빈 q scrub / `A4-BENTO-ALL6` 6 cell 매핑) · B 보강 2건 (`B5-FALSE-POS-EXT` negative 3건 추가 / `B4-RETRY-LOOP` 5회 직렬 가드) · C perf 2건 (`C3-PERF` INP < 500ms / `C4-FAILED` 600ms transition) · D 보강 6건 (`D1-RESET-LOOP` self-throw 정적 invariant / `D5-IFRAME-BLOCK` Tally route.abort fallback / `D7-PERF` getComputedStyle 캐시 / `D8-HOVER` Header Tailwind hover / `D9-WCAG258` BottomNav minHeight 60+icon 24+label 13 mobile-iphone / `D10-VISUAL` mouseout styleFor 재계산) · F SSR 2건 (`F1-SSR` no use client / `F2-IMPORT-MAP` import 사용처 0). 검증: tsc 0 error · 정적 회귀 9 testcase PASS (Ring0-D1 + Ring0-F1 + Ring0-F2). Ring1+ 27건은 USE_MOCK e2e stack 필요 (본 머신 :3001/:8002 외부 점유로 user 수동 트리거 권장). [Verdict](../qa/runs/ux-phase-a-f-pass1/summary.md)
> **2026-04-30 UX Sweep Phase F — Tier hook stub (옵션 phase)** — Plan [ux-sweep-phase-f-tier-hook](../plan/ui/ux-sweep-phase-f-tier-hook.md). Phase 2 (OAuth/결제/Tier 게이팅) 머지 시 surface diff 최소화를 위한 hook 자리만 마련. 코드 변경 2 신규 + spec 1 신규: (F.1) `frontend/src/hooks/useTier.ts` — `Tier = 'free' | 'pro' | 'team'` 타입 + `useTier()` 하드코딩 `'free'` 반환 stub. (F.2) `frontend/src/components/common/FeatureGate.tsx` — `'use client'` wrapper, `useTier()` 호출 (grep 표면 유지) 후 children 그대로 렌더 (no-op). spec: `ring0-preflight/03-tier-hook.spec.ts` 신규 — Tier 타입 export + `tier:'free'` 하드코딩 + FeatureGate `<>{children}</>` 정적 invariant 회귀. tsc 0 error · next lint 0 warning. Phase 2 머지 시 본 2 파일 비교 로직만 활성화하면 일괄 게이팅 가능.
> **2026-04-30 UX Sweep Phase E — Premium Deferred (toggle 1건)** — Plan [ux-sweep-phase-e-premium-deferred](../plan/ui/ux-sweep-phase-e-premium-deferred.md). Phase 2 (OAuth/결제/Tier 게이팅) 의존 3건 (E.1 F06 평일/주말 토글 · E.2 F09 What-If UI · E.3 FreeLimitSurvey Premium CTA) 차단 사유 + 선행 요건 명시. 코드 변경은 E.3 임시 결정만 적용 — `FreeLimitSurvey` Premium CTA 블록에 `NEXT_PUBLIC_PREMIUM_CTA_ENABLED` env 게이트 추가 (default off, `'true'` 일 때만 노출), `data-testid="survey-premium-cta"` 부여. spec 보강 1건: `f12-feedback.spec.ts::Ring1-F12-E3` — env off 시 mood ≥ 4 응답에도 CTA 미노출 회귀. tsc 0 error.
> **2026-04-30 UX Sweep Phase D — A11y / 마감** ⭐ — Plan [ux-sweep-phase-d-a11y](../plan/ui/ux-sweep-phase-d-a11y.md). 10 항목 (D.1~D.10) 일괄 구현: (D.1) `app/error.tsx` · `app/loading.tsx` · `app/app/error.tsx` · `app/app/loading.tsx` 4 boundary 신규 — reset+홈 동선 + split-panel skeleton. (D.2) `globals.css` `:focus-visible` 글로벌 룰 + Header/Hero/BetaBanner/Footer focus-visible:ring 보강. (D.4) `FeedbackRow` ack 후 ↩️ 수정 토글 + `useToastStore` 안내. (D.5) `FeedbackModal` iframe 5s timeout fallback (mailto/Kakao). (D.6) `CompareCard`/`SuggestionChips` 안정 키 (`${index}-${value}`). (D.7) `InlineChart` CSS 변수 토큰화 (`useEffect` 1회 read + SSR fallback) + 차트 토큰 5종 light/dark 추가. (D.8) `Header` Tailwind hover 전환 (inline JS 제거). (D.9) `BottomNav` minHeight 60px + 폰트 22→24/12→13 (WCAG 2.5.8 AA). (D.10) `DistrictLayer` mouseout 시 `styleFor` 전체 재계산 (compare 슬롯 색 race 방지). 변경 12 파일 + 신규 spec 2건 (`ring0-preflight/02-error-boundary.spec.ts` · `ring1-features/a11y.spec.ts`). 검증: tsc 0 error · next lint 신규 변경 0 warning (pre-existing 4건만 잔존).
> **2026-04-29 Out-of-Scope (서울 외 지역) 거부 3중 가드 구현** ⭐ — Plan [out-of-scope-handling-2026-04-29](../plan/fix/out-of-scope-handling-2026-04-29.md). 사용자 보고 ("부산/제주 등 서울 외 질문 처리 안 됨") → 3중 가드 설계: (L1) `intents.yaml` `out_of_scope` intent 신규 (광역지명 + 비-서울 시단위 + 부산 동단위 + 제주 동단위 패턴, 한글 word-boundary `(?<![가-힣])...(?![가-힣ㄱ-ㅎㅏ-ㅣ])` 로 substring 오매치 차단). (L2) `planner.py` `_classify_by_rules` 진입 직후 `out_of_scope` 분기 + `_CLARIFICATION_TEMPLATES["out_of_scope"]` 추가, LLM/Tool 호출 0건으로 즉시 clarification_direct 반환. (L3) `entity_matching.py` `STRONG_TOP1_MIN=0.70` 상수 + `chat.py` message-detect 분기에서 score < STRONG_TOP1_MIN 시 거부 (silent wrong-district 가상 비-서울 fuzzy 매치 차단). (L4) `system.py::_BASE_PROMPT` rule 11 + `respond.py::RESPOND_SYSTEM_PROMPT` rule 13 거부 룰 명시. 변경 6 파일 + 신규 unit `test_out_of_scope.py` 21 testcase + Plan 1건. 검증: ruff PASS · **pytest 70/71** (신규 21 + 기존 49, 1 fail = `test_smoke::langfuse_enabled` host env pre-existing) · 회귀 0.

---

## 2026-06-08 — QA (/qa) Standard 풀앱 패스

### 개요
- **리포트**: `.gstack/qa-reports/qa-report-localhost-2026-06-08.md` (12 스크린샷 + baseline.json)
- ✅ Docker 실데이터 스택 기동 — 기존 이미지 6주 stale → current source 재빌드(backend+frontend). pip SSL(사내 MITM)은 Dockerfile `--build-arg PIP_TRUSTED_HOST` 우회. `NEXT_PUBLIC_API_URL` 은 빌드 시 `:8000` 으로 override(`.env` 값 `:3000` 버그 회피)
- ✅ 건강도 **98 → 99 (Δ+1)**. 콘솔 에러 0 / XML leak 0 / 실수치·월환산 정상
- ✅ ISSUE-001 (medium) fix + 회귀 테스트 main 머지
- 🔧 디퍼 2건 (ISSUE-003 recommend 저점포수 랭킹 · ISSUE-002 H1 줄바꿈)
- ⚠️ 환경(미수정): `.env`/`.env.dev` `NEXT_PUBLIC_API_URL=:3000`(프론트포트) → 재빌드 시 chat SSE 버퍼링, `:8000` 권장

### ISSUE-001 — out_of_scope/greeting 중복 suggestion (✅ fixed)

| 항목 | 내용 |
|---|---|
| 원인 | `_greeting`/`_clarification` 노드가 실행 중 tailored suggestion 을 직접 방출하나 `final_suggestions`(state) 미설정 → 스트림 말미 fallback 이 generic suggestion 한 번 더 방출 |
| 증상 | client 가 suggestion 을 replace → generic("이 자리 위험하지 않아?"/"카페 하면 어때?", district 선택 가정)이 tailored Seoul-redirect 셋을 덮어씀. 서울 외 거부 UX 훼손 |
| 수정 | `graph.py` 말미 방출을 `final_response_mode in ("greeting_direct","clarification_direct")` 일 때 skip (두 노드는 항상 1회 self-emit → 누락 없음) |
| 검증 | SSE 부산/제주/greeting=1회(tailored)·normal summary=1회(card+evaluator 유지)·회귀 0. UI 확인(tailored 칩만). `test_graph_suggestion_emission.py` 2 passed (컨테이너 pytest 9.0.3/py3.12) |
| 커밋 | c777f49 (fix) · 2d13d22 (test) — main FF 머지, 로컬 3커밋 ahead(미push) |

### 검증 PASS (정상 플로우)
요약 F03 / 비교 F05(멀티상권 추출, hallucination 0) / 추천 F07 / 프리뷰 F13(zero-LLM) / 히트맵 F06(+TimeSlider) / 검색 자동완성 / privacy·terms / 모바일(390×844 BottomNav). out_of_scope 가드(부산/제주) 정상. Redis lazy-init 정상 연결.

### 디퍼 (사용자 결정 대기)
- **ISSUE-003 (medium, data accuracy)**: `recommend_business` 가 점포수 1~2개 카테고리를 점포당매출 아티팩트로 1순위 랭크 (성수동 편의점 score 100 / 월 2억 from 1점포). 점포수 floor(예 <3) damp/제외 권장 — [accuracy-gap-fix](../plan/fix/accuracy-gap-fix.md) 트랙.
- **ISSUE-002 (low, cosmetic)**: 랜딩 H1 "데이터로" 단어중간 줄바꿈 → `word-break: keep-all` 권장.

### 다음 P0
- ✅ origin/main push 완료 (`44b9438..eb3e10f`, 4커밋 — origin↔local 동기화)
- 🔧 `.env`/`.env.dev` `NEXT_PUBLIC_API_URL` → `:8000` 교정
- 🔧 ISSUE-003 accuracy-eval 트랙 반영 / ISSUE-002 cosmetic

---

## 2026-04-30 — UX Sweep Phase A-F Pass 1

### 개요
- **Plan**: [ux-phase-a-f-test-plan.md](../plan/qa/ux-phase-a-f-test-plan.md)
- ✅ 13 신규 시나리오 작성 — Phase A·B·C·D·F 6 phase × 28 항목 단위 회귀 매트릭스 확정 (기존 25 + 신규 13 = 38 시나리오)
- ✅ tsc 0 error · 정적 회귀 9 testcase PASS (Ring0-D1 + Ring0-F1 + Ring0-F2)
- 🔧 Ring1+ 27 시나리오는 USE_MOCK e2e stack 필요 — 본 머신 `:3001` (Vite) + `:8002` (외부 FastAPI) 점유로 user 수동 트리거 권장
- ✅ Verdict: [ux-phase-a-f-pass1/summary.md](../qa/runs/ux-phase-a-f-pass1/summary.md)

### 변경 (11 파일)

| # | 파일 | 신규 시나리오 |
|---|------|------|
| 1 | `e2e/ring0-preflight/02-error-boundary.spec.ts` | 🆕 `Ring0-D1-RESET-LOOP` |
| 2 | `e2e/ring0-preflight/03-tier-hook.spec.ts` | 🆕 `Ring0-F1-SSR` + `Ring0-F2-IMPORT-MAP` |
| 3 | `e2e/ring1-features/a11y.spec.ts` | 🆕 `Ring1-F11-D8-HOVER` |
| 4 | `e2e/ring1-features/d-perf.spec.ts` (신규) | 🆕 `Ring1-F02-D7-PERF` |
| 5 | `e2e/ring1-features/d9-bottomnav.spec.ts` (신규, mobile-iphone) | 🆕 `Ring1-Mobile-D9-WCAG258` |
| 6 | `e2e/ring1-features/f01-map-selection.spec.ts` | 🆕 `Ring1-F01-D10-VISUAL` |
| 7 | `e2e/ring1-features/f11-landing.spec.ts` | 🆕 `Ring1-F11-A1-EDGE-PRIVATE` + `Ring1-F11-A4-BENTO-ALL6` |
| 8 | `e2e/ring1-features/f12-feedback.spec.ts` | 🆕 `Ring1-F12-D5-IFRAME-BLOCK` |
| 9 | `e2e/ring1-features/phase-b-ux-sweep.spec.ts` | 🆕 `Ring3-Negative-B5-FALSE-POS-EXT` (배열 +3) + `Ring1-F10-B4-RETRY-LOOP` |
| 10 | `e2e/ring1-features/phase-c-ux-sweep.spec.ts` | 🆕 `Ring1-F06-C3-PERF` + `Ring1-F02-C4-FAILED` |
| 11 | `e2e/ring2-journeys/j01-first-time-user.spec.ts` | 🆕 `Ring2-J01-A4-EDGE-EMPTY` |

### 정적 회귀 PASS (stack-free, 9 testcase)

```
✓ Ring0-D1 — 4 boundary 컴포넌트 / role=status / split-panel skeleton  (4 testcase)
✓ Ring0-D1-RESET-LOOP — boundary self-throw 없음 (정적 invariant)         🆕
✓ Ring0-F1 — useTier 하드코딩 free + Tier 타입 export
✓ Ring0-F2 — FeatureGate no-op (children 통과)
✓ Ring0-F1-SSR — useTier.ts no 'use client' (server-component-friendly)   🆕
✓ Ring0-F2-IMPORT-MAP — FeatureGate import 사용처 0 (Phase 2 머지 전)     🆕

9 passed (1.4s)
```

### 다음 P0
- 🔧 user 수동 Pass 1 트리거 (e2e stack 격리 가능한 머신/세션)
- 🔧 chromium 38 시나리오 PASS 확인 후 → Plan 2 ([ux-final-e2e-regression-plan](../plan/qa/ux-final-e2e-regression-plan.md)) 진입 게이트
- 🔧 mobile-iphone D9 단독 실행 검증
- 🔧 D.7 perf invariant — production CI 머신에서 INP < 200ms 재측정

---

### 추가 — Plan 2 Pass 1 (통합 5 journey 신규)

- **Plan**: [ux-final-e2e-regression-plan.md](../plan/qa/ux-final-e2e-regression-plan.md)
- ✅ 통합 5 journey spec 신규 — `frontend/e2e/ring2-journeys/j06-ux-a2f-integration.spec.ts` 1 파일 (~960 LOC, 5 testcase)
  - `Ring2-UX-A2F-J01` — onboarding-to-feedback (A.4 + B.6 + F11 + F12 + F13 + D.4)
  - `Ring2-UX-A2F-J02` — compare 풀사이클 (B.1 + B.2 + B.3 + B.4 + B.5)
  - `Ring2-UX-A2F-J03` — 모바일 첫 진입 (C.2 + D.2 + D.9 + B.3, mobile-iphone)
  - `Ring2-UX-A2F-J04` — 에러복구+Tally 폴백 (D.1 + D.5 + B.4)
  - `Ring2-UX-A2F-J05` — a11y 종합 (D.2 + D.3 + D.4 + D.6 + D.9 + WCAG)
- ✅ tsc 0 error · next lint 0 warning · dry-list 5 testcase 인식
- ✅ 정적 baseline 재현 9 testcase PASS (Ring0-D1 + Ring0-F1 + Ring0-F2)
- ⚠️ Pass 1/2/3 + prod-smoke runtime 보류 — 본 머신 :3001/:8002 점유 (PID 26264 다른 프로젝트)
- ✅ Verdict: [ux-final-e2e-2026-04-30/summary.md](../qa/runs/ux-final-e2e-2026-04-30/summary.md)
- 🔧 다음 액션 — user 수동 Pass 1 트리거 → 38(Plan 1) + 5(j06) = 43 시나리오 chromium 전수 PASS → Pass 2 mobile viewport → Pass 3 real-DB → prod-smoke

---

## 2026-04-29 — Out-of-Scope (서울 외 지역) 거부 3중 가드

### 개요
- **Plan**: [out-of-scope-handling-2026-04-29.md](../plan/fix/out-of-scope-handling-2026-04-29.md)
- 사용자 보고: "현재 서비스에서 서울 외의 상권 질문이 들어오면 어떻게 처리하지?" → audit 결과 명시적 거부 룰 부재. 4 가지 보강 여지 (intents.yaml / system prompt / numeric_sanity / W1 type boost) 중 1·2·3 구현. 4번 (W1 type boost 약화) 은 Round 3 eval 에서 별도 측정.

### 변경 (6 파일 + 1 신규 + 1 Plan)
| # | 파일 | 변경 |
|---|------|------|
| 1 | `agent/config/intents.yaml` | greeting 직후 `out_of_scope` intent 추가. 광역(부산/대구/인천/광주/대전/울산/세종/제주/경기/강원/충청/전라/경상) + 부산 동(해운대/광안리) + 경기 시(수원/성남/용인/안양/부천/일산/분당/판교/동탄) + 강원/충청/전라/경상 주요 시 + 제주(서귀포/애월). word-boundary `(?<![가-힣])...(?![가-힣ㄱ-ㅎㅏ-ㅣ])` |
| 2 | `agent/nodes/planner.py` | `_classify_by_rules` 진입 직후 `out_of_scope` 우선 분기 (다른 모든 intent 보다 먼저, confidence 0.95). `_CLARIFICATION_TEMPLATES["out_of_scope"]` 4번째 키 추가. `planner_node` 에 short-circuit (LLM/Tool 0건, ~1ms 응답) |
| 3 | `agent/utils/entity_matching.py` | `STRONG_TOP1_MIN = 0.70` 상수 신규 (TOP1_MIN 0.55 보다 strict) |
| 4 | `api/routes/chat.py` | message-detect 분기에서 `det_score < STRONG_TOP1_MIN` 거부. body.district_code 미선택 + fuzzy 약한 매치 시 silent wrong-district 차단 |
| 5 | `agent/nodes/respond.py` | `RESPOND_SYSTEM_PROMPT` rule 13 신규 (서비스 범위 명시 + 가상 수치 금지). 기존 rule 13(출력 포맷) → 14 |
| 6 | `agent/prompts/system.py` | `_BASE_PROMPT` rule 11 추가 (서울 외 정중 거절) |
| 7 | `tests/test_out_of_scope.py` | 신규 — 21 testcase (pattern coverage 16 + planner short-circuit 4 + 상수/템플릿 sanity 1 + control 1) |
| 8 | `docs/plan/fix/out-of-scope-handling-2026-04-29.md` | 신규 — 5섹션 Plan |

### 3중 가드 설계
```
User: "부산 해운대 알려줘"
   ↓
[L1] intents.yaml::out_of_scope (regex)
   → intent="out_of_scope", confidence=0.95
   ↓
[L2] planner.py: short-circuit
   → LLM/Tool 0건, clarification_direct 즉시 반환
   ↓ (L1/L2 우회 — 가상 비-서울 시장명 등)
[L3] entity_matching::STRONG_TOP1_MIN=0.70
   → 약한 매치 거부 → ambiguous → clarification (district_missing)
   ↓ (모든 가드 우회)
[L4] respond.py::RESPOND_SYSTEM_PROMPT rule 13
   → "서울시 1,650개 상권만 지원" 자연어 거절
```

### Clarification 응답
> "현재 마켓스코프는 **서울시 1,650개 상권**만 지원합니다. 서울 외 지역(부산·인천·경기 등)의 상권 데이터는 아직 제공하지 않습니다. 서울 상권에 대해 알려드릴까요?"
>
> Suggestions: ["강남역 상권 요약", "홍대 vs 성수 비교", "명동 창업 추천 업종"]

### 검증
- ✅ ruff (server/) — All checks passed
- ✅ pytest **70/71 PASS** (신규 21 + 기존 49). 1 fail = `test_smoke::langfuse_enabled` host env pre-existing (변경 무관)
- ✅ Pattern coverage: 부산/제주/경기/대구/인천/광주광역시/서귀포/수원 8 케이스 → True. 강남역/홍대/명동 3 케이스 → False (제어군). substring trap 4 (부산물/광주리/경기침체/구로구) → False ✓
- 🔧 Manual smoke + Playwright E2E spec 은 다음 sweep 에 포함 (backend pytest 우선)

### Memory 신규 1건
- `feedback_out_of_scope_handling.md` — 서울 외 거부 3중 가드 패턴 + STRONG_TOP1_MIN 임계 근거

### 후속 P0
- 🔧 W1 type boost 약화 케이스 — Round 3 eval 에서 별도 측정 (Plan p0-priority-2026-04-27 의 #1 보강)
- 🔧 Playwright E2E spec — `r3-neg-out-of-scope.spec.ts` 작성
- 🔧 Manual smoke (USE_MOCK=true backend) — curl 4 케이스 검증
- 🔧 prod 배포 (다음 배포 사이클)

---


## 전략

Phase 1A(Mock E2E) → Phase 1B(Real Data + UX) → Phase 3(확장) → Phase 2(Premium)

| Phase | 범위 | 상태 |
|-------|------|------|
| 1A | Mock E2E, Card UI, Agent 전체 흐름 | ✅ 완료 |
| 1B | 공공데이터 ETL + 1,650 상권 적재 + 프로덕션 배포 | ✅ 완료 (2026-03-30) |
| 3 | F06 히트맵 · F09 매출 시뮬레이션 · F10 PDF | ✅ 완료 (2026-04-06) |
| Prod | `marketscope.robitlabs.co.kr` 라이브 | ✅ 완료 (2026-04-16) |
| 2 | OAuth2 · 결제 · Tier 게이팅 · F04 UI | ⏳ 미착수 (Accuracy Gap 선행 권장) |

---

## 현재 실행 환경

| 서비스 | 포트 | 모드 |
|--------|-----:|------|
| Next.js 프론트엔드 | 3000 | Real (USE_MOCK=false) |
| FastAPI 백엔드 | 8000 | Real |
| PostGIS (Docker) | 5432 | 1,650 상권 폴리곤 적재 완료 |
| Redis (Docker) | 6379 | 정상 |

| LLM 설정 | 값 |
|----------|-----|
| LLM_PROVIDER | **anthropic** (Claude Sonnet 4) |
| Planner / Respond | Claude Sonnet 4 (TTFT 1.5s) |
| Evaluator | Gemini 2.5 Flash |
| Fallback | gemini-2.5-pro / flash |
| Agent 모드 | PAE (max 3 rounds) |
| 관측성 | Langfuse L1 (trace wiring, graceful degrade) |

---

## 현재 서비스 지표

- Mock 상권 5개 · Real 상권 1,650개
- ETL 적재 (2025Q4): floating_pop 9,888 / estimated_sales 21,333 / stores 75,985 / resident 39,288
- Agent Tool 9종 · Card 타입 5종 · SSE 이벤트 9종
- E2E: ring0~3 78 test (66 PASS / 0 FAIL / 12 SKIP) + prod-smoke 28/28

---

## 프로젝트 완성도 평가 (2026-04-22 기준, W1~W3 반영 전)

| 축 | 점수 | 판정 | 약점 |
|---|---:|------|------|
| 안정성 | **85** | 프로덕션 운영 가능 | 세션 인메모리 · `store_history` 실데이터 부재 · backend pytest 부재 |
| 효율성 | **82** | 양호 | Langfuse L2+ 미구현 · Heatmap singleflight 미통합 |
| 정확성 | **74** | 주요 시나리오 합격 | 6 GAP (A~F) — W1~W3 적용 후 재측정 대기 |

**로드맵**: [Accuracy Gap Fix](../plan/fix/accuracy-gap-fix.md) W1~W4 · [Eval Round 2](../plan/fix/accuracy-gap-eval-round2-2026-04-24.md) — 목표 74 → 85+.

---

## 이력 요약 (2026-03-30 ~ 2026-04-28)

> 상세는 git history (`git log --follow docs/status/current-status.md`) + `docs/qa/runs/` + `docs/plan/` 로 복원.

| 날짜 | 주요 내용 |
|------|----------|
| 2026-04-28 (저녁) | Prod 재배포 — district-click-race fix 라이브 적용. dev/prod compose project name 충돌로 `:3200` stop → 502 → A 방식 destructive 4 Pass. frontend `46815639...` + backend `6be3098215b9` healthy. P1~P9 ALL PASS · Playwright real-DB 3/3 · prev-2026-04-28b tag. [Plan](../plan/infra/prod-redeploy-2026-04-28-evening.md) |
| 2026-04-28 | District click race / "먹통" fix — 6 근본 원인 (sendMessage isLoading return / ChatPanel disabled / setPreview lastDistrictCode race / SSE late-done / per-session lock 부재 / 1.5s setTimeout). Stale-while-cancel + Monotonic requestId + AbortController + Per-session async cancellation. ruff/tsc/pytest 49/50 · memory 4건 신규. [Plan](../plan/fix/district-click-race-2026-04-28.md) |
| 2026-04-28 | 프로덕션 재배포 (`52ae7db → 04376a4`) + Tool 함수명 노출 fix. alembic 005 + Langfuse 11차원/6스코어 + W1 X시장 boost + planner clarification + numeric_sanity + respond.py 502→280 LOC. ATTRIBUTION_PROMPT_RULE + `_ToolTagSanitizer` 11종 가드. prod-smoke 30/30 · live raw tool name leak 0건. [Plan](../plan/infra/prod-deploy-2026-04-28.md) |
| 2026-04-28 | Langfuse 전체 통계 집계 Phase 1+2 — v3 tracer 에 `district_type_for` / `attach_summary_observation` (start_observation 우회) / `emit_score`. graph finally 에서 11 차원 metadata + 6 score emit. unit 10/10 + Playwright stats-aggregate 16/16 PASS. [Plan](../plan/infra/langfuse-aggregate-stats-2026-04-28.md) |
| 2026-04-27 | P0 우선순위 6건 — W1 entity_matching X시장 boost + paren-alias dampen, RESPOND XML leak `_XMLTagSanitizer` (rule 13), Planner empty-plan clarification 3종, Eval district_code 하드코딩 제거 + drift guard, status-compress 517→383, Refactor Pass 2 `api/errors.py` 헬퍼. ruff/tsc/pytest 22/22 PASS. [Plan](../plan/fix/p0-priority-2026-04-27.md) |
| 2026-04-24 | User-Journey Sweep 16 journey/45 turn — Pass1 71.3% → **Pass3 99.1% (16/0 PASS)**. Planner 4 fix (compare-coref history fallback · rule 다중매치 우선순위 · 장문 synthesis summary fan-out · risk→recommendation 교정). [Plan](../plan/qa/user-journey-quality-2026-04-24.md) |
| 2026-04-24 | Langfuse 비용 커버리지 fix — dev 컨테이너 `langfuse==2.60.10` stale → v3 업그레이드 후 `done.trace_id=310fc8bf…` 실 발행. Eval harness `REQUIRE_TRACE=1` preflight + `validate_env.py` SDK drift 가드. [Plan](../plan/infra/langfuse-cost-coverage-fix-2026-04-24.md) |
| 2026-04-24 | Data Trust Reliability Phase A+B — `numeric_sanity` evaluator (216 LOC, 6/6 unit) + alembic 005 컬럼 코멘트 + RESPOND SALES_PRESENTATION_RULES 프롬프트 + trust eval 25/30 (5 상권). L3 한계: Planner entity mismatch 는 W1 별도 Plan. [Plan](../plan/fix/data-trust-reliability-2026-04-24.md) |
| 2026-04-24 | E2E 품질 Sweep 107 시나리오 — Pass 1 96.1% (10 FAIL) → Pass 2 96.4% (9 FAIL). Planner ambiguous→clarification short-circuit + `scenarios.py` rubric 보정 6건. [Plan](../plan/qa/e2e-quality-improvement-2026-04-24.md) |
| 2026-04-24 | Refactoring Pass 1+2 + Accuracy Eval Round 2 — `singleflight.py`/레거시 spec 7건 삭제, `respond.py` 502→280 LOC (`utils/formatting.py` 분할). Round 2 평균 7.6/10 FAIL — XML leak / W1 type boost 약화 / multi-district regression / coref empty-plan 4 P0 신규. [Plan](../plan/fix/accuracy-gap-eval-round2-2026-04-24.md) |
| 2026-04-24 (iOS) | BottomSheet 챗 탭 즉시 닫힘 fix — `BottomSheetHandle` 6px deadzone + `moved` 플래그, `BottomSheet.onDragEnd` `closest` 초기값을 현재 `snap`으로. iPhone E2E spec 신규. |
| 2026-04-23 (저녁) | E2E Pass 2 hotfix — FAIL 0 달성 (StatusBar testid · waitSSE · f12 skip-guard · reg python3 · F01-H3 timeout). v0.4.0 재배포 `c6cc60e` — learned_aliases 004 · 라우트 분리 (`/` 랜딩 / `/app` 챗맵) · P1~P7+N1~N2 전수 PASS. |
| 2026-04-23 | F-01 ETL fix (21,333 행 재적재, 8 컬럼 NULL 해소) + Accuracy Gap W1/W2/W3 구현 (entity_matching/abstention/rewriter utils + learned_aliases 004). LLMOps L1 SDK v2→v3 포팅, trace 발행 확인. Env 관례 분리 (`.env`=prod · `.env.dev`=dev). UI Landing/Feedback/Preview Phase A~D. Mobile Responsive Phase A+B+C. Data Integrity Audit. Refactoring Phase 1 Plan 작성. |
| 2026-04-22 | E2E + Ops 회귀 2차 READY (Dockerfile pip SSL 우회 · E2E 전용 stack 포트 재할당 · OPS-01/02 spec). 완성도 평가 85/82/74. [Run](../qa/runs/e2e-run-2026-04-22.md) |
| 2026-04-21 | E2E 회귀 Pass 1~3 그린 (Mock 39/39 + Real 24/24). LLMOps L1 Langfuse trace wiring (graceful degrade · SSE `done.trace_id`). |
| 2026-04-19 | v0.3.0 — 문서 계층화 · `docker-compose.e2e.yml` + `prodGuard` · 회귀 spec 4종. |
| 2026-04-17 | 매출 단위 fix (`_enrich_sales` sales→monthly_sales). 배포 근본해결 7건. 비교모드 다색 하이라이트. |
| 2026-04-16 | **프로덕션 런치** (marketscope.robitlabs.co.kr). 외부 nginx + LE · `docker-compose.prod.yml`. |
| 2026-04-14 | 서빙 안정성 Phase 1~10. 체크리스트 24% → 61%. Docker 하드닝 · DB/Redis 풀 · SSE heartbeat · Circuit Breaker · `/metrics` · DR. |
| 2026-04-13 | 분석 품질 Phase 1~3 (3단 해석법 · Tool enrich · 벤치마크). SSE 최적화 — TTFT 25s→1.5s. E2E eval S1 9.8 / S2 9.6 / S3 2.6 / S6 6.1 / S7 8.9 / S8 9.7 (평균 8.0). |
| 2026-04-08 | F05-H1 fix — `detect_districts_in_message` multi-extract. Real 45 시나리오 41 PASS. |
| 2026-04-07 | E2E QA Run (Mock 42 시나리오 94/100). 4-ring helper + 22 spec. React duplicate-key fix. |
| 2026-04-06 | P0 8건 수정 (`d8c0155`) — category aliases · LLM timeout · SSE 백프레셔 · AbortController. Phase 3 완료 (F06/F09/F10). |
| 2026-04-05 | Docker 통합. `docker compose up` 원커맨드 · Multi-stage + standalone · `--profile dev`. |
| 2026-04-04 | QA P0+P1 8건 (Tool 크래시 · 인젝션 방어 · Redis fallback · Semaphore(20)). |
| 2026-04-03 | PAE Agent 전환. Repository 패턴 (`DataAccess` + 7 Protocol). Frontend 리팩토링. 데이터 출처 citation. |
| 2026-04-02 | DB 셋업 자동화 — `setup_db.py --quick/full/reset` · seed 덤프 LFS · OA-15584 CSV 로더. |
| 2026-04-01 | Playwright E2E 26 시나리오 22 PASS · SHP→PostGIS 1,650 적재 · Real 모드 전환. |
| 2026-03-30~31 | **Phase 1B 완료** — Agent Progress Indicator · SSE 버퍼링 해결 · 다크 테마 · ETL 적재 · E2E 32/32. |

---

## Next Items (우선순위 순)

### 🟠 Accuracy Eval Round 2 — W1~W3 KPI 재측정

**Plan**: [accuracy-gap-eval-round2-2026-04-24.md](../plan/fix/accuracy-gap-eval-round2-2026-04-24.md)

- S1~S8 curl SSE 수집 + DB ground truth 교차검증
- Round 1 (2026-04-13) 대비 변화 기록 · KPI 테이블 업데이트
- Refactoring Pass 2 (respond.py 분할) 전에 baseline 확보

### 🟡 Refactoring Phase 1 Pass 2 (중위험)

**Plan**: [phase1-low-mid-risk-2026-04-23.md](../plan/infra/phase1-low-mid-risk-2026-04-23.md)

- `server/server/api/errors.py::make_error_response` 래퍼로 routes `HTTPException` 15건 통합
- `except Exception` 9건 → 구체 exception tuple 좁히기
- `agent/nodes/respond.py` 502 LOC → `agent/utils/formatting.py` 3종 이식, 목표 ~300 LOC
- `stores/chatStore.ts` 381 LOC → `stores/slices/{preview,mobile,feedback}.ts` 분할

### 🟡 관측성 L2+

- Langfuse L2+ (토큰/비용 측정, prompt version, eval harness)
- Heatmap preload singleflight 통합 (Pass 1 에서 `singleflight.py` 삭제 후 별도 Plan 으로 재도입)
- backend pytest 인프라

### 🟡 Phase 2 — Premium (미착수)

- OAuth2 + 결제 (Toss Payments / PortOne)
- Tier 게이팅 미들웨어 (Free 일 5회)
- F04 업종 심층 UI
- category_aliases 퍼지 검색 (pg_trgm)

### 🟢 장기 / 후순위

- 세션 저장소 Redis/Postgres 이관
- `store_history` 대안 데이터셋
- Docker 이미지 최적화

---

## 참고 문서

| 영역 | 경로 |
|------|------|
| 종합 QA | `docs/qa/qa-summary-report.md` · `qa-detailed-results.md` · `qa-improvements.md` |
| E2E run | `docs/qa/runs/e2e-run-2026-04-23-full.md` · `e2e-run-2026-04-22.md` · `e2e-run-2026-04-19.md` |
| 분석 품질 eval | `docs/qa/analysis-quality-eval-2026-04-13.md` (Round 1) · `analysis-quality-eval-2026-04-24.md` (Round 2, 대기) |
| Accuracy Gap | `docs/plan/fix/accuracy-gap-fix.md` · `accuracy-gap-eval-round2-2026-04-24.md` |
| Refactoring | `docs/plan/infra/phase1-low-mid-risk-2026-04-23.md` |
| 서빙 안정성 체크리스트 | `docs/spec/serving-stability-checklist.md` |
| 아키텍처 overview | `docs/architecture/overview.md` (backend/frontend/agent/data/deployment) |
| 기능 목록 | `docs/spec/feature-list.md` · `features/F01~F13-*.md` |
| LLMOps L1 | `docs/plan/infra/llmops-l1-adr-hosting.md` · `llmops-l1-verification.md` |
| E2E 회귀 인프라 | `docs/plan/infra/e2e-regression-plan-2026-04-19.md` · `e2e-ops-2026-04-22.md` |
