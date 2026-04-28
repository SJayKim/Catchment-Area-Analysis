# 현재 진행 상황

> 최종 갱신: 2026-04-28
> **2026-04-28 프로덕션 재배포 (`52ae7db → 04376a4`, 4 커밋) + Tool 함수명 노출 fix** ⭐ — Plan [prod-deploy-2026-04-28](../plan/infra/prod-deploy-2026-04-28.md). 4 days old prod 컨테이너 (alembic 004) 에서 alembic 005 (estimated_sales COMMENT) + Langfuse 11차원/6스코어 + W1 entity_matching X시장 boost + planner clarification 3종 + numeric_sanity evaluator + respond.py 502→280 LOC + lucide-react 신규 의존성 반영. **추가 핫픽스**: LLM 응답에 raw 함수명 (`(get_district_summary)`) 노출 사용자 보고 → `ATTRIBUTION_PROMPT_RULE` 자연어 출처 표기 강제 + `_ToolTagSanitizer` 11종 tool 이름 stream-level 가드 + RESPOND rule 13 정정 + 잉여 `scan_unattributed_numbers` 호출 제거. 라이브 검증: prod-smoke 30/30 PASS (4 viewport) · ring0 stack-up 7/9 (R0-2/LANDING 은 prodGuard 의도 차단) · stats-aggregate 4/4 PASS · live SSE raw tool name leak **0건**.
> **2026-04-28 Langfuse 전체 통계 집계 Plan + Phase 1+2 구현** ⭐ — Plan [langfuse-aggregate-stats-2026-04-28](../plan/infra/langfuse-aggregate-stats-2026-04-28.md). v3 tracer 에 `district_type_for` / `attach_summary_observation` (start_observation 우회) / `emit_score` 헬퍼 + graph finally 에서 11 차원 metadata + 6 score emit. 신규 unit 10/10 + Playwright stats-aggregate 16/16 PASS. SSE `done.trace_id` 동봉 + `agent_done` 로그 매핑 정상. dev MITM SSL 갭은 graceful degrade 로 swallow (prod 영향 0). Phase 3+4 (REST ETL + 월간 KPI 마크다운) 은 별도 세션.
> **2026-04-27 P0 우선순위 6건** — Plan [p0-priority-2026-04-27](../plan/fix/p0-priority-2026-04-27.md). (1) W1 entity_matching 보강: "X시장" 쿼리 → 전통시장 +0.15 boost · paren alias-only 매치 dampen. unit 6/6. (2) RESPOND XML leak `_XMLTagSanitizer` + 프롬프트 rule 13 unit 6/6. (3) Planner empty-plan clarification 3종 unit 4/4. (4) Eval district_code 하드코딩 제거 + drift guard. (5) status-compress 517→383 LOC. (6) Refactor Pass 2: `api/errors.py` `raise_db_unavailable / raise_not_found` 헬퍼 적용. ruff/tsc/pytest 22/22 PASS.
> **프로덕션 v0.4.0 동기화 완료 ✅ — `c6cc60e` 기반 재배포 (저녁), 오전 `60b6de3` 대비 6 커밋 / +13,038 / -577 반영**
> 프로덕션: `marketscope.robitlabs.co.kr` 라이브 — prod-smoke 28/28 + 신규 2 endpoint 검증 PASS
> 배포 변경: alembic 004 (`learned_aliases`) · `/`=랜딩/`/app`=챗맵 라우트 분리 · Planner Entity Linking + Abstention + Rewriter · `/api/districts/{code}/preview` · `/api/feedback/score`
> **E2E 회귀 (2026-04-23 저녁)**: Pass 1 = 106 test · 94 PASS · 4 FAIL (전부 test infra) · 8 SKIP → **Pass 2 hotfix 후 4 spec + 1 component 수정으로 FAIL 0** (ring0~3 chromium 66/66 + prod-smoke 28/28). ops 5종 전수 PASS. [Run log](../qa/runs/e2e-run-2026-04-23-full.md) · [Hotfix plan](../plan/qa/e2e-spec-hotfix-2026-04-23.md)
> E2E 회귀: Ring 0~3 전체 그린 (Mock 39/39 · Real 24/24) + Ops OPS-01/02 + L1 Langfuse 7/7 + prod-smoke 7/7
> 관측성 L1: Langfuse **trace 실제 발행 확인 완료** (dev 로컬 sanity — `done.trace_id=9d59e6455eeb42f685b71f8057915377` + `agent_done` 로그 동일 값 매핑) · langfuse SDK **v2→v3 포팅** (v2 의 legacy langchain 의존 해소) · `agent_done` 운영 로그 조인 추가. 프로덕션 env 배선 완료. [Plan](../plan/infra/llmops-l1-verification.md)
> **2026-04-23 env 관례 분리**: `.env`=프로덕션 · `.env.dev`=로컬 개발 (pydantic/Next.js/scripts 전부 `.env.dev` 우선 로드) · Langfuse prod 워크스페이스 키 분리(`pk-lf-07a3fa78…`) + `LANGFUSE_TRACING_ENVIRONMENT` 태깅으로 dev/prod trace 격리
> 다음 권장: (1) W1 entity_matching 재점검 · (2) Accuracy Gap KPI 재측정 (S1~S8 eval Round 2) · (3) Refactoring Phase 1 Pass 2 · (4) status-compress 필요 (> 480 LOC) · Phase 2 착수 전 선행 권장
> **2026-04-23 신규 Audit**: Data Integrity Audit 에서 **ETL 키 불일치 (F-01, HIGH)** + **Comparison intent 수치 hallucination (F-02, HIGH)** 발견. [Report](../qa/runs/data-integrity-audit-2026-04-23.md)
> **2026-04-23 UI Phase A~D 구현**: 랜딩 분리(`/` + `/app`) · Zero-LLM 프리뷰(`GET /api/districts/{code}/preview`) · 피드백 3-layer(카드 👍👎 + microsurvey + FAB) · 2026 UI/UX 트렌드 8축 델타 반영. Build 성공, typecheck 0 errors. [Plan](../plan/ui/landing-onboarding-feedback.md)
> **2026-04-23 Mobile Responsive Plan Phase A+B+C 구현**: viewport/breakpoint/touch-target · BottomSheet 3-snap + BottomNav 2-tab · IME/VisualViewport 가드 + auto-scroll FAB. tsc/eslint/build 0 errors. Phase D/E/F (PWA·Perf·A11y/E2E) 미착수. [Plan](../plan/ui/mobile-responsive.md)
> **2026-04-23 F-01 fix + Accuracy Gap W1/W2/W3 구현** ⭐: ETL 8 컬럼 NULL 버그 해소(21,333 행 재적재) + Entity Linking(pg_trgm 대체: difflib+type boost) + Abstention(classify_tool_results+attribution rule) + Coreference Rewriter(Tier1 rule+Tier2 LLM) + 배제 토큰(말고/대신/빼고) + learned_aliases 테이블(alembic 004). [Plan F-01](../plan/fix/etl-sales-column-rename-2026-04-23.md) · [Plan Accuracy Gap](../plan/fix/accuracy-gap-fix.md)
> **2026-04-23 Refactoring Phase 1 Plan 작성**: 7 기준(R1~R7) 기반 저위험/중위험 항목 1 Pass 묶음. Pass1 = singleflight 삭제 + 레거시 E2E 8건 삭제 + status 압축 + Any import 정리. Pass2 = errors.py 래퍼 통합 + blanket except 9건 좁히기 + respond.py 헬퍼 분리 + chatStore slice 분할. [Plan](../plan/infra/phase1-low-mid-risk-2026-04-23.md) — 구현 미착수

---

## 2026-04-28 — 프로덕션 재배포 + Tool 함수명 노출 fix

### 개요
- **Plan**: [prod-deploy-2026-04-28.md](../plan/infra/prod-deploy-2026-04-28.md)
- 운영 컨테이너 4 days old (`2026-04-24T05:34Z`, alembic 004) → 04376a4 동기화. alembic 005 + Langfuse 11차원/6스코어 + W1 보강 + 신규 planner 4건 + 매출 단위 가드 + lucide-react 1건 적용.

### Pass 1 — 사전 회귀 (host venv)
- backend pytest **34/35 PASS** (1 fail = `test_settings_loads_with_mock_defaults` env-dep 사전 알려진 케이스 — host에 Langfuse 키 존재로 langfuse_enabled=True 평가)
- ruff `server/` All checks passed
- 이전 image snapshot tag — `prev-2026-04-24` 3종 (rollback safety)

### Pass 2 — Build + Migrate
- `.env.dev` 임시 이동(`predeploy-2026-04-28.bak`) → 4 image build → 즉시 복구
- 신규 IMAGE IDs: backend `63a494302bef` · frontend `e8921f344424` · migrate `caf17802568b`
- Frontend baked-URL 검증: `https://marketscope.robitlabs.co.kr` 정상 박힘 (P9 가드 통과)
- alembic 004 → 005 (`estimated_sales.monthly_sales COMMENT`) — zero-downtime, idempotent. `cleanup_alembic + upgrade head` exit 0
- 신규 헬퍼 import 검증: `attach_summary_observation`, `emit_score`, `district_type_for` 모두 `True`
- Langfuse v3 (`langfuse.langchain.CallbackHandler`) import OK

### Pass 3 — Cut-over + Live Smoke (curl 11종)
- backend healthy ~20s + frontend started
- P1 / 랜딩 200 (data-theme=light + MarketScope) · P2 /proxy/kakao-sdk 200 (4095 bytes)
- P3 polygons (no-bounds 500 features / bounds 90 features) · P4 강남역 → `3120189`
- P5 SSE 강남역 요약 — `perStoreSales=27,307,409 원/월` 정상 + done.trace_id 동봉 + attribution `(get_district_summary)` (1차 동작 — 후속 fix 대상)
- P6 SSE 보문역 편의점 — recommend `per_store_sales` 5건 모두 < 1B/월 (32M~201M)
- P7 /app 200 (data-testid=toolbar-logo + statusbar)
- P8 /api/districts/3120189/preview top_categories 3종
- P9 feedback/score: empty=422 / valid `value="up"` → 204 (schema 신규 변경 — int → up/down 문자열)
- P10 clarification "이 지역 요약" → tool 0건 + suggestion 2건 + done.trace_id ✅
- P11 done.trace_id Langfuse L1 정상

### Pass 4 — Playwright 회귀
- **prod-smoke 30/30 PASS** (chromium 9/9 + iphone/galaxy 14/14 + ipad 7/7, 6 skip는 P8/P9 chromium-only 의도)
- ring0-preflight: 5 PASS (R0-1 backend health · R0-3 polygons · R0-4 mode · stats-aggregate AGG-01~04 신규 Langfuse 11차원/6스코어 회귀) · 2 expected fail (R0-2/R0-LANDING은 `helpers/prodGuard.ts`의 의도된 prod 도메인 fetch 차단)
- ring1~3 mock-fixture spec은 prod 머신에 별도 e2e stack(`docker-compose.e2e.yml`) 부재로 라이브 prod 부적합 — dev/staging 머신에서 별도 실행 권장

### 추가 핫픽스 — LLM 응답 raw 함수명 노출
- **사용자 보고**: P5 SSE 응답 텍스트에 `유동인구: 하루 평균 81만 5천명 (get_district_summary)` 같이 raw 함수명 그대로 노출
- **근본 원인**: `agent/utils/abstention.py::ATTRIBUTION_PROMPT_RULE` 가 LLM에게 수치 옆에 `(tool_name)` 표기를 의무화 (W1 hallucination 가드 의도). 그러나 `numeric_sanity` evaluator (data-trust-reliability-2026-04-24) 가 이미 attribution tag 없이도 entity mismatch 까지 잡는 더 정확한 검증을 수행 → attribution tag 는 잉여 + UX 손상
- **수정 (4 파일)**:
  - `abstention.py` — `ATTRIBUTION_PROMPT_RULE` 을 "raw 함수명 사용자 노출 금지 + 자연어 출처 표기" 로 재작성. 11 tool 이름 명시 금지 목록. `ABSTENTION_PROMPT_ADDENDUM_EMPTY` 의 attribution tag 예시도 정정
  - `agent/nodes/respond.py` — `_ToolTagSanitizer` 신규 (97 LOC). chunk-aware stream filter, `_TOOL_NAME_INNER` 정규식이 `get_*` / `compare_*` / `recommend_*` / `estimate_*` / `simulate_*` / `detect_*` 11개 tool 매칭. `(자본금 부족)` 같은 일반 한국어 괄호는 보존. `_emit` chain = XML sanitiser → ToolTag sanitiser → SSE
  - `respond.py::RESPOND_SYSTEM_PROMPT` rule 13 — `(수치 출처 표기 (tool_name) 은 일반 괄호 표기이므로 허용됩니다.)` → "**도구 함수명 노출 금지** — 출처는 자연어로만 표기"
  - `respond.py` — `scan_unattributed_numbers` 호출 제거 (잉여 telemetry, numeric_sanity 가 더 정확)
  - 신규 `tool_sanitizer.dropped_count > 0` 시 `respond_tool_tag_stripped` 로그 (LLM relapse 추적)
- **단위 테스트** `server/tests/test_tool_tag_sanitizer.py` 신규 11/11 PASS — simple/backticked/quoted tool tag · chunk boundary split (open paren / inside name) · 한국어 괄호 보존 · 영어 일반 괄호 보존 · 다중 tag · 미완 paren overflow flush · empty input · compare/estimate 등
- **회귀 검증**: backend cache rebuild 11s → up -d backend → live SSE `강남역 요약` 재실행. 응답 7,498 bytes · text 이벤트 30+개 · raw tool name pattern (`\(get_*\)|\(recommend_*\)|\(compare_*\)|\(estimate_*\)|\(simulate_*\)|\(detect_*\)`) **0건** ✅. 답변 자연도 향상 — 수치 옆 노이즈 사라짐
- **prod-smoke chromium 9/9 재확인 PASS** — backend 재빌드 사이드이펙트 0

### 참조 메모리 / 후속
- 메모리 활용: `feedback_respond_tool_use_xml_leak` (sanitizer 패턴 재사용) · `feedback_env_convention_inverted` (.env.dev 임시 이동 자동화 후보)
- 운영 권장: 일정 기간 `respond_tool_tag_stripped count` 모니터 → 0 유지 시 prompt rule 만으로 충분, > 0 지속 시 prompt 추가 강화 또는 fewshot 추가
- 후속 P0: ring1~3 mock stack 을 prod 머신에 별도 셋업 (`docker-compose.e2e.yml` 작성 — 격리된 backend port + USE_MOCK=true) — 라이브 회귀 자동화 가능

---

## 2026-04-27 — P0 우선순위 6건 (Plan p0-priority-2026-04-27)

### 개요
- **Plan**: [p0-priority-2026-04-27.md](../plan/fix/p0-priority-2026-04-27.md)
- 2026-04-24 Round 2 eval 후속 P0 6건 + 위생 작업. unit-test 우선, 프로덕션 영향 0.

### 변경 / 결과

| # | 영역 | 변경 | 검증 |
|---|------|------|------|
| 1 | W1 entity_matching | `_market_type_boost` 신규 ("X시장" → 전통시장 +0.15) · paren alias-only 매치 damp (`_PAREN_ALIAS_ONLY_DAMP=0.5`) | `tests/test_entity_matching.py` 6/6 PASS |
| 2 | Respond XML leak | (이전 변경분) `_XMLTagSanitizer` + 프롬프트 rule 13 | `tests/test_xml_sanitizer.py` 6/6 PASS |
| 3 | Planner clarification | (이전 변경분) `_CLARIFICATION_TEMPLATES` 3종 + 4 트리거 경로 | `tests/test_planner_clarification.py` 4/4 PASS |
| 4 | Eval district_code 하드코딩 | `run_accuracy_round2.sh` `WITH_CODES=0` default · `verify_district_codes.py` drift guard · `trust_scenarios.verify_target_codes()` | 코드 import OK |
| 5 | status-compress | 04-23 5섹션 + iOS BottomSheet 섹션 → 이력 테이블 1행씩 | 517 → 383 LOC |
| 6 | Refactor Pass 2 (부분) | `api/errors.py` `raise_db_unavailable / raise_not_found` (`-> NoReturn`) · districts.py 3건 + map_data.py 3건 적용 | ruff All passed |

### Pass 2 잔여 (defer)
- `chatStore.ts` (381 LOC) slice 분할 — 36 consumer 영향 + 슬라이스 typing 복잡도 대비 cosmetic 가치 낮음
- `except Exception` 9건 좁히기 — Plan 의 핵심 4 파일은 후속 세션
- routes 의 `HTTPException` validation 패턴 통합 — 4xx 본문은 그대로 두는 게 가독성 우수

### 메모리 활용
- [feedback_eval_district_code_hardcode](../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_eval_district_code_hardcode.md) — DB drift guard 설계
- [feedback_respond_tool_use_xml_leak](../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_respond_tool_use_xml_leak.md) — sanitizer 검증 angle
- [feedback_formatter_strips_unused_imports](../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_formatter_strips_unused_imports.md) — `raise_not_found` 추가 import 가 1차 ruff F821 → 같은 Edit 안에서 import+사용 묶어 해소

### 다음 P0
- 🔧 Accuracy Eval Round 3 — district_code 미동봉 모드로 W1 entity_matching 신규 boost 회귀
- 🔧 chatStore slice 분할 (필요 시 별도 Plan)
- 🔧 backend pytest 인프라 — `tests/` 4 파일 모인 김에 fixture/conftest 정비

---

## 2026-04-28 — Langfuse 전체 통계 집계 Plan + Phase 1+2 구현

### 개요
- **Plan**: [langfuse-aggregate-stats-2026-04-28](../plan/infra/langfuse-aggregate-stats-2026-04-28.md)
- 단일 trace drill-down 만 보이는 현 Langfuse 상태에서 cohort/추세 통계까지 자동화. 기존 v3 tracer 파이프라인 깨지 않고 누락 차원/Score 메우는 게 목표.

### 변경 (3 파일 + 2 신규)
| # | 파일 | 변경 |
|---|------|------|
| 1 | `server/services/langfuse_tracer.py` | `district_type_for` (4 prefix 매핑) · `attach_summary_observation` (v3 `start_observation` 우회) · `emit_score` 헬퍼. 모두 graceful degrade |
| 2 | `server/agent/graph.py` | astream 루프에서 11 차원 capture (intent/confidence/response_mode/exec_round/plan_size/refs/category/ambiguous/tool_results/tool_errors/cards). finally 에서 attach + 6 score emit |
| 3 | `server/tests/test_langfuse_aggregate.py` | 신규 — 10 testcase (district_type_for / attach / emit graceful degrade 전수) |
| 4 | `frontend/e2e/ring0-preflight/stats-aggregate.spec.ts` | 신규 — 4 spec (AGG-01 trace_id 동봉 / AGG-02 quality_match_rate / AGG-03 greeting / AGG-04 SSE 포맷 불변) |
| 5 | `docs/plan/infra/langfuse-aggregate-stats-2026-04-28.md` | 신규 — 4 Phase Plan (차원 보강 / Score / REST ETL / KPI 마크다운) |

### Phase 1 — Trace 차원 보강 (`update_trace_post_hoc` 우회)
v3 SDK 에 `update_trace` 가 없어 동일 `trace_id` 의 0-duration `start_observation(as_type="agent")` 으로 metadata 동봉. CallbackHandler 가 만든 langchain spans 와 같은 trace 에 묶여 UI 의 trace-level 필터/groupby 에 반영.

### Phase 2 — Quality Score 6종 emit
`numeric_match` / `intent_confidence` / `tool_error_rate` / `abstention_triggered` / `ambiguous_disambiguation_needed` / `quality_severity`. 기존 `user_feedback` (±1) 과 합쳐 trace 당 최대 7종 score.

### 검증
- ✅ ruff (graph + tracer) — All checks passed
- ✅ pytest 신규 — **10/10 PASS**
- ✅ pytest 전체 — 34/35 (test_smoke 1건 env-dep pre-existing)
- ✅ Playwright stats-aggregate — **16/16 PASS** (chromium + iphone + galaxy + ipad × 4 spec)
- ✅ chat smoke — `done.trace_id=333172da75de77c7421a7db37c7dec64` SSE 동봉 + `agent_done` 로그 동일
- ✅ F02-H3/H4 chat 회귀 (frontend 경유) PASS

### 발견된 환경 이슈 (P1 follow-up)
- ⚠️ `LANGFUSE_OTEL_INSECURE=true` 부분 패치 — OTEL exporter 만 verify 우회, `create_score`/`start_observation` 의 httpx client 는 SSL 그대로. dev MITM 환경에서 `Unexpected error occurred` SDK 노이즈. graceful degrade 가 swallow → SSE / agent_done 영향 0. prod 정상 SSL 이라 영향 없음.

### Memory 신규 2건
- `feedback_langfuse_v3_no_update_trace.md` — `update_trace` 없음, `start_observation` 우회 패턴
- `feedback_langfuse_otel_insecure_partial.md` — `LANGFUSE_OTEL_INSECURE` 가 REST 호출엔 미적용

### 다음 P0
- 🔧 Phase 3 — REST API ETL 스크립트 (`scripts/observability/aggregate_langfuse.py`)
- 🔧 Phase 4 — 월간 KPI 마크다운 자동 생성 (`docs/observability/kpi-{YYYY-MM}.md`)
- 🔧 prod 배포 후 Langfuse UI 에서 신규 11 차원 + 6 score 가시성 확인
- 🔧 dev SSL gap 해소 (REQUESTS_CA_BUNDLE 또는 SDK httpx transport 패치) — 선택적

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

## 이력 요약 (2026-03-30 ~ 2026-04-23)

> 상세는 git history (`git log --follow docs/status/current-status.md`) + `docs/qa/runs/` + `docs/plan/` 로 복원.

| 날짜 | 주요 내용 |
|------|----------|
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
