# 현재 진행 상황

> 최종 갱신: 2026-04-24
> **2026-04-24 프로덕션 핫픽스** 🔥 — 어제 env 관례 분리 잔여 설정 3건 수정 (운영 이미지 재빌드 없이 `.env` + frontend 재빌드 + backend 재생성). (1) `NEXT_PUBLIC_API_URL` dev 값(`http://localhost:3000`) baked-in → `https://marketscope.robitlabs.co.kr` 로 복구 (브라우저 `/api/chat` 호출이 사용자 localhost 로 향하던 현상 해소). (2) `LANGFUSE_TRACING_ENVIRONMENT` `development`→`production` (prod trace 가 dev 태그로 저장되던 오염 해소). (3) `LANGFUSE_OTEL_INSECURE=true` 제거 (prod CA 체인 정상, dev-only 우회 불필요). 검증: 신규 chunk `449-e4312e4a97b2d2f9.js` 에 prod URL 박힘 + SSE `done.trace_id=a268eaa891cd5050824cb4bd3e76416b` === `agent_done` 로그.
> **2026-04-24 prod-smoke baked-URL guard 추가** — prod-smoke 에 `P8 real-browser chat round-trip` + `P9 JS bundle dev-URL scan` 2건 추가. 핫픽스 사건이 기존 server-side curl smoke 로 회귀 감지 불가했던 gap 보강. chromium 9/9 PASS (44.6s). [Plan](../plan/infra/prod-baked-url-smoke-2026-04-24.md)
> **Langfuse 비용 갭 fix (2026-04-24)** — Dev 컨테이너 `langfuse==2.60.10` 잔존으로 `from langfuse.langchain import CallbackHandler` import 실패 → `_tracer_valid=False` → dev LLM 호출 전량 미집계. v3 업그레이드 후 `done.trace_id=310fc8bf…` 실 발행 확인. Eval harness `REQUIRE_TRACE=1` preflight 추가. [Plan](../plan/infra/langfuse-cost-coverage-fix-2026-04-24.md)
> ⭐ **User-Journey Sweep (2026-04-24)** — 실사용 패턴 16 journey / 45 turn (UJ1 단일심층 / UJ2 다중전환 / UJ3 3+way 비교 / UJ4 상세보고서). Pass 1 71.3% (9/7) → Pass 2 97.5% (15/1) → **Pass 3 99.1% (16/0 PASS)**. Planner 4 fix: compare-coref history fallback · rule 다중매치 우선순위 (comparison/simulation/risk/recommendation > summary) · "상세 분석 보고서" summary fan-out · "안전 추천" risk→recommendation 교정. [Plan](../plan/qa/user-journey-quality-2026-04-24.md)
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

## 2026-04-24 — User-Journey Quality Sweep (Pass 1 → Pass 3, 16/0 PASS)

### 개요
- **Plan**: [user-journey-quality-2026-04-24.md](../plan/qa/user-journey-quality-2026-04-24.md)
- 기존 107 시나리오 (intent coverage) 와 별개로, **실제 사용자 궤적** (연쇄 질문 / 다중 상권 전환 / 3+way 비교 / 상세 보고서) 16 journey / 45 turn
- Scenarios: `scripts/eval/user_journey_scenarios.py` · runner: `SCENARIO_MODULE` env 로 pack 교체
- Stack: real mode (`USE_MOCK=false`), Claude Sonnet 4, 1,650 상권, compose override volume-mount backend

### 결과
| Pass | Avg | PASS | FAIL | Delta vs 이전 |
|------|----:|-----:|-----:|---|
| Pass 1 (baseline) | 71.3% | 9 | 7 | — |
| Pass 2 (P0+P1+P2) | 97.5% | 15 | 1 | +26.2%p |
| **Pass 3 (+rule 우선순위)** | **99.1%** | **16** | **0** | +1.6%p |

### 적용 Fix (server/server/agent/nodes/planner.py)
- **P0 compare-coref history injection** — `intent == comparison` 이고 `detect_districts_in_message` + session anchor 합이 <2 일 때 최근 6 user turn 의 content 를 재스캔해 최대 3개 code 까지 `referenced_districts` 로 주입. 영향 scenario: UJ2-홍대-성수 / UJ2-잠실-신촌 / UJ4-report-from-compare
- **P1 "안전한 추천" 교정** — `_classify_by_rules` 에서 risk 매치 후 `_RECOMMEND_OVERRIDE` (추천/어떤 업종/가장 좋은 업종) 공존 시 recommendation 로 switch (conf 0.85). UJ1-pub-건대 fix
- **P2 장문 synthesis** — `_LONG_REPORT_TRIGGER` (상세/종합/전체 분석 · 분석 보고서 · 보고서 형태) + 토픽 키워드 3+ 공존 시 summary 강제 분류 → `get_district_summary` 4-tool fan-out. UJ4-long-synthesis fix
- **다중매치 우선순위** — 단일 pattern match 가 아닌 경우 기존에는 `None, 0.4` 로 LLM 분기. 이를 `(comparison, simulation, risk, recommendation, category_analysis) > summary` 우선순위로 교체. summary 의 "알려줘/분석/어때" 가 너무 광범위해 모든 intent 와 충돌하던 근본 문제 해소
- **history fallback guard 완화** — 기존 compare-coref 패턴/empty 조건부 → `len(referenced_districts) < 2` 단일 가드. comparison intent 분기 내부에서만 동작하므로 false positive 위험 낮음

### 아티팩트
- `scripts/eval/user_journey_scenarios.py` 16 journey / 45 turn
- `scripts/eval/run_quality_sweep.py` — `SCENARIO_MODULE` env 지원
- `docs/qa/runs/user-journey-2026-04-24/pass{1,2,3}/summary.md` + raw SSE 47 files
- Memory 신규: [Bash cwd 호출 간 지속](../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_bash_cwd_persists_between_calls.md)

### 다음
- 🔧 `docs/status/current-status.md` status-compress 필요 (> 480 LOC)
- 🔧 Accuracy Gap Round 2 (S1~S8) 재측정 이어서 진행

---

## 2026-04-24 — Langfuse 비용 커버리지 fix (Anthropic ↔ Langfuse 갭 원인 규명)

### 배경
- 사용자 문의: Anthropic API key 대시보드 비용 > Langfuse 대시보드 비용. 전수 점검 요청.

### 근본원인
- 🔴 **Dev 컨테이너 Langfuse SDK 드리프트** — `catchment-area-analysis-backend-1` 에 `langfuse==2.60.10` 이 설치돼 있음 (pyproject 은 `langfuse>=3,<4`). 2026-04-23 SDK v2→v3 포팅 시 이미지 재빌드 없이 `docker cp + pip install` 로 수동 패치된 상태에서 일부만 반영돼 stale.
- 코드 경로: `langfuse_tracer.py:178-183` 의 `from langfuse.langchain import CallbackHandler` → `ModuleNotFoundError` → `_tracer_valid=False` 고정 → `get_langfuse_handler()` 100% None → `graph.py:320` callbacks 주입 스킵.
- 증거: `docker logs` `agent_done` 기록 전량 `trace_id=-` placeholder.
- 영향 범위 (dev, 2026-04-24 하루): E2E Quality Sweep Pass 1+2 = 214회 / Trust regression = 30회 / Accuracy eval Round 2 = 8회+ / 로컬 수동 chat 다수 — **전량 Anthropic 과금·Langfuse cost 0**.
- Prod 는 정상: `marketscope.robitlabs.co.kr/api/chat` 분석 호출 `done.trace_id=89ab12176a…` 실값 발행 확인.

### 조치
- ✅ Dev 컨테이너 수동 복구: `docker exec -u root ... pip install --upgrade --trusted-host pypi.org --trusted-host files.pythonhosted.org 'langfuse>=3,<4' 'langchain>=1,<2'` → langfuse 3.14.6, langchain 1.2.15 설치
- ✅ 재시작 후 smoke: `curl /api/chat` 분석 쿼리 → `done.trace_id=310fc8bfd32de178420140bf7bf7bf70` 발행 + 백엔드 로그 `agent_done` 동일 hex 기록 확인
- ✅ Eval harness 가드 추가:
  - `scripts/eval/run_quality_sweep.py` — `REQUIRE_TRACE=1` (default), `preflight_trace()` 가 `/api/chat` 1회 ping 후 trace_id 누락 시 exit 3
  - `scripts/eval/trust_scenarios.py` — 동일 패턴 적용
  - `scripts/validate_env.py` — `importlib.util.find_spec("langfuse.langchain")` 로 SDK drift warning
- ✅ 운영 문서: `docs/ops/runbook.md` Langfuse 섹션 추가 (sanity 3-step + Cloud Models pricing 체크리스트)
- ⚠️ 이미지 재빌드 미완 — `docker compose build backend` 가 SSL MITM 환경에서 build-isolation 서브프로세스가 `setuptools>=75` fetch 실패 (status 2026-04-23 SSL 우회 메모의 재발). Dockerfile 의 `PIP_INDEX_URL` build-arg 가 build isolation 에 전파되지 않음. 별도 fix 필요.

### Langfuse Cloud 사용자 작업 (필수)
- `https://cloud.langfuse.com` → Settings → Models 에서 다음 모델 pricing 등록 확인:
  - `claude-sonnet-4-20250514` (Planner / Respond)
  - `gemini-2.5-pro` (Respond gemini mode)
  - `gemini-2.5-flash` (Planner / Evaluator gemini mode)
- 등록 안 돼 있으면 토큰은 수집되지만 **cost=0** 으로 표시돼 Anthropic 대시보드와 자연히 갭 발생.

### Memory 신규
- `feedback_langfuse_sdk_drift_silent.md` — 증상·증거·복구 절차 정리

### 아티팩트
- [Plan](../plan/infra/langfuse-cost-coverage-fix-2026-04-24.md)
- `scripts/eval/run_quality_sweep.py` + `trust_scenarios.py` + `validate_env.py` · `docs/ops/runbook.md`

### 다음 세션
- 🔧 backend 이미지 재빌드 완료 (SSL 우회 재점검) — 수동 pip install 은 컨테이너 재시작 시 유실 위험
- 🔧 Langfuse Cloud Models 등록 확인 (사용자 UI 작업)
- 🔧 prod 컨테이너 `pip show langfuse` 확인 (prod 는 trace_id 발행되므로 v3 추정이나 sanity 필요)

---

## 2026-04-24 — iOS BottomSheet 챗 탭 즉시 닫힘 fix

### 증상
- iOS Safari 에서 BottomNav "💬 챗" 탭을 눌러 시트를 열면 full(90vh)로 올라갔다가 **곧바로 peek/hidden 으로 닫히는** 현상 (사용자 영상 제보)
- 안드로이드/데스크톱 재현 안 됨

### 원인
- `setSnap('full')` 로 시트가 15vh→90vh 로 성장하는 동안 핸들이 손가락 아래로 올라옴 → iOS Safari 가 `setPointerCapture` + `touch-action:none` 조합에서 **합성 pointer 이벤트** 를 핸들에 발사
- `BottomSheetHandle.onPointerDown` 이 이동 0px 탭에서도 `pointerup` → `onDragEnd()` 호출
- `BottomSheet.onDragEnd` 의 `closest` 초기값이 `'hidden'` 이라 `liveVh` 계산이 전환 타이밍에 꼬이면 닫히는 방향으로 편향

### 수정
- ✅ `frontend/src/components/mobile/BottomSheetHandle.tsx` — 6px deadzone + `moved` 플래그. 이동 없는 탭은 `onDragEnd` 스킵
- ✅ `frontend/src/components/mobile/BottomSheet.tsx` — `closest` 초기값 `'hidden'` → 현재 `snap`. useCallback deps 에 `snap` 추가
- ✅ `frontend/e2e/ring1-features/mobile-sheet-open.spec.ts` 신규 — iPhone 12 에뮬레이션 2 시나리오 (챗 탭 후 full 유지 / 핸들 탭 deadzone)
- ✅ `tsc --noEmit` exit 0

### 검증 잔여
- ⚠️ Playwright iPhone 에뮬레이션은 Chromium 엔진이라 Safari WebKit 합성 pointer 100% 재현 불가 — **실기기 iOS Safari 재확인 필요**
- 🔧 스테이징 배포 후 재현 테스트 + 영상 제보자 확인

---

## 2026-04-24 — Data Trust Reliability (Phase A + B)

### 배경
- UI 응답: "종로3가역 월 추정 매출 1,104억 3천만원" 에 대한 사용자 불신 제기
- DB 실측: `SUM(monthly_sales)` 3,313억 (분기누적) / 3 = 1,104억/월 **✅ 계산 정확**
- 벤치마크: 발달상권 p95=492억, 종로3가역은 p95 대비 2.24배 = **상위 5% 수준**. LLM 의 "상위 25%" 라벨은 3분위 해상도 한계
- [Plan](../plan/fix/data-trust-reliability-2026-04-24.md)

### 구현 (Phase A + B)
- ✅ **L1 프롬프트** — `RESPOND_SYSTEM_PROMPT` 에 SALES_NUMBER_PRESENTATION_RULES (절대값+(tool_name) / p95 대비 M배 / 점포당 매출 / 분기→월 환산 출처 명시) 추가
- ✅ **L5 DB guardrail** — Alembic 005 `COMMENT ON estimated_sales.monthly_sales` (SOURCE: THSMON_SELNG_AMT / AGGREGATION: quarterly cumulative / Divide by QUARTER_TO_MONTH_DIVISOR)
- ✅ **L3 numeric_sanity evaluator** — 신규 `server/agent/utils/numeric_sanity.py` (216 LOC)
  - `extract_numbers`: 한국어 수치 파싱 (억/만/천, compound "590만 6천명")
  - `match_numbers_to_tools`: typed + wildcard 재귀 leaf 스캔, ±5% fuzzy
  - `check_benchmark_outliers`: p99×1.5 초과 경고
  - `evaluate_response` → `QualityReport` (flags + match_rate)
  - 유닛 테스트 `server/tests/test_numeric_sanity.py` **6/6 PASS**
- ✅ **Respond/graph 통합** — `respond_node` post-hoc scan → `quality_flags` 반환. Graph 가 SSE `warning` 이벤트 (severity=warning) + `done.quality_flags` + `done.quality_match_rate` 발행. `state.py` `quality_flags` / `quality_match_rate` 필드 추가
- ✅ **L4 Trust regression harness** — `scripts/eval/trust_scenarios.py` + DB ground truth 비교 (5 상권)
- ⏸️ **L2 벤치마크 병렬 호출** — defer to Pass 3 (summary intent 는 이미 district_summary 내장, comparison/recommend 추가 호출은 TTFT 영향 측정 필요)

### Pass 1 결과 — 25/30 (↑ from Pass 0 21/25)

| 상권 | Pass 0 | Pass 1 | 비고 |
|---|:---:|:---:|---|
| 종로3가역 | 5/5 ✅ | **6/6 ✅** | 수치 정확, L3 warning 부재 체크 통과 |
| 강남역 | 5/5 ✅ | 5/6 ❌ | store_count 자연 변동 (카테고리별만 언급) |
| 망원시장 | 5/5 ✅ | **6/6 ✅** | — |
| 남대문시장(자유상가) | 3/5 ❌ | 4/6 ❌ | Planner mismatch 지속 |
| 명동 관광특구 | 3/5 ❌ | 4/6 ❌ | Planner mismatch 지속 |

### L3 의 한계 — 중요 인사이트
- **Planner 가 "남대문시장" → `삼익패션타운(남대문시장)` 로 잘못 resolve** 한 뒤 Tool 이 그 잘못된 code 로 데이터 fetch → Respond 는 그 데이터를 충실히 인용 → 응답 ↔ tool_results 가 **내부적으로 일치**하므로 `tool_mismatch_ratio_high` 미발동
- L3 실효 범위: (1) Tool 과 동떨어진 수치 할루시, (2) 벤치마크 p99 초과 outlier, (3) Langfuse 로 품질 추세 관측
- L3 범위 밖: Planner 수준 entity mismatch → **W1 `entity_matching.py` 재점검 별도 Plan 필요**

### 아티팩트
- [Plan](../plan/fix/data-trust-reliability-2026-04-24.md)
- [Trust eval summary](../qa/runs/trust-eval-2026-04-24/summary.md) · [per-district](../qa/runs/trust-eval-2026-04-24/per-district.md)
- `server/agent/utils/numeric_sanity.py` · `server/tests/test_numeric_sanity.py` · `server/alembic/versions/005_estimated_sales_column_comment.py` · `scripts/eval/trust_scenarios.py`

### 다음 세션 P0
- 🔧 W1 entity_matching 재점검: "남대문시장" 같이 여러 상권명에 prefix 포함된 케이스 ambiguity 감지 상향
- 🔧 (강남역 케이스) LLM 응답에서 총 store_count 명시 유도 — 프롬프트 규칙 추가 검토

---

## 2026-04-24 — E2E 품질 Sweep 107 시나리오 (Pass 1 → Pass 2)

### 개요
- **Plan**: [e2e-quality-improvement-2026-04-24.md](../plan/qa/e2e-quality-improvement-2026-04-24.md)
- **Harness**: `scripts/eval/run_quality_sweep.py` + `scripts/eval/scenarios.py` 107 시나리오 (A35/B12/C8/D10/E12/F10/G8/H6/I6)
- **Stack**: real mode (`USE_MOCK=false`), Claude Sonnet 4, 1,650 상권. backend 는 compose override 로 `./server:/app` volume-mount + `uvicorn --reload`.

### 결과
| Pass | Avg | PASS (≥80%) | FAIL | XML leak |
|------|----:|------------:|-----:|---------:|
| Pass 1 (baseline) | 96.1% | 97 | 10 | 0 |
| **Pass 2 (재측정)** | **96.4%** | **98** | **9** | **0** |
| Delta | +0.3 | +1 | -1 | — |

> `done.trace_id` 는 Pass 2 에서 Langfuse OpenTelemetry 모듈 부재로 None. rubric 재집계 시 trace_id 체크 제외.

### Agent 품질 Fix (Pass 1 → Pass 2 사이)
- ✅ **Planner `ambiguous → clarification` short-circuit** (`server/server/agent/nodes/planner.py:437-466`) — district_code+referenced_districts 모두 비면 Respond 로 넘기지 않고 고정 clarification 발행. Pass 1 에서 발견된 `(recommend_business)` 가짜 attribution 할루시 (tool 호출 0건) 차단.
- ✅ **scripts/eval/scenarios.py rubric 보정 6건** — simulation tool 이름 alias 허용 / coref substring / D-typo-2·E-coref-그업종·I-greeting graceful 완화 / G-switch 계열 text-level 검증.
- ✅ W1~W3 (entity_matching paren+type boost / abstention / rewriter coref·exclusion) regression 0 확인.

### Pass 2 잔여 FAIL 9건 분류
- **P1 multi-turn 결합 이슈 3건** — `E-coref-위`, `F-drill-summary-to-compare`, `G-switch-intent`. history anchor 를 comparison intent 에 주입하지 못함.
- **P2 rubric 과엄격 4건** — `E-coref-compare-then-pick` (strict threshold 3), `E-coref-summary-then-risk`, `E-coref-동일` (card_names category_analysis payload), `C-unknown-district` (clarification 거절 키워드 미포함).
- **P2 clarification 템플릿 결함 1건** — `C-exclusion-soft` 에서 clarification 예시 문구에 "강남역 요약" 이 포함되어 must_not_contain 걸림. 중립 예시로 교체 필요.
- **P2 intent 미등록 1건** — `A-other-heatmap-pop` "유동인구 높은 곳" top-N 쿼리. 후속 intent 추가 대상.

### 아티팩트
- [Plan + Pass 로그](../plan/qa/e2e-quality-improvement-2026-04-24.md)
- [Pass 1 summary](../qa/runs/quality-sweep-2026-04-24/pass1/summary.md) · [fail-details](../qa/runs/quality-sweep-2026-04-24/pass1/fail-details.md)
- [Pass 2 summary](../qa/runs/quality-sweep-2026-04-24/pass2/summary.md) · [fail-details](../qa/runs/quality-sweep-2026-04-24/pass2/fail-details.md)
- raw SSE 214 files under `pass1/raw/` + `pass2/raw/`
- Memory 신규: [compose override anonymous node_modules 함정](../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_compose_override_anon_node_modules.md)

### 다음
- 🔧 multi-turn comparison coref (E-위, F-summary-to-compare) 를 위한 rewriter history-anchor-for-comparison 주입
- 🔧 top-N 쿼리 intent (`A-other-heatmap-pop` 류) 등록
- 🔧 clarification 예시 문구 중립화 (`강남역 요약` → 일반형)
- ⚠️ 컨테이너 volume-mount 모드에서 Langfuse disabled — 프로덕션 이미지 재빌드 시 `opentelemetry` 의존성 포함 확인

---

## 2026-04-24 — Refactoring Phase 1 Pass 1+2 + Accuracy Eval Round 2

### Refactoring Pass 1 (저위험 일괄) ✅
- **Plan**: [phase1-low-mid-risk-2026-04-23.md](../plan/infra/phase1-low-mid-risk-2026-04-23.md)
- `server/server/services/singleflight.py` 삭제 (호출처 0)
- `frontend/e2e/feature{1..7}-*.spec.ts` 7건 삭제 — ring1/f01~f03 커버리지 대조 후
- `docs/architecture/backend.md` Singleflight 섹션/도식 제거
- `docs/status/current-status.md` 532 → 279 LOC 압축
- `ruff check server/` All checks passed · `tsc --noEmit` 0 errors · `playwright --list` = 388 tests / 29 files

### Refactoring Pass 2 — respond.py 분할 ✅
- **신규 `server/server/agent/utils/formatting.py`** (216 LOC) — `_compute_hints` / `_format_tool_results` / `_format_history` 3 헬퍼 이식
- `respond.py` **502 → 280 LOC** (목표 ≤300 달성)
- signature 동일 유지, import 만 전환. `ruff check` All passed. smoke 통과 (compute_hints 샘플 호출)
- Pass 2 잔여 (errors.py 래퍼 / except 좁히기 / chatStore slice 분할) 은 다음 세션

### Accuracy Eval Round 2 — W1~W3 KPI 재측정 ⚠️
- **Plan**: [accuracy-gap-eval-round2-2026-04-24.md](../plan/fix/accuracy-gap-eval-round2-2026-04-24.md)
- **Report**: [analysis-quality-eval-2026-04-24.md](../qa/analysis-quality-eval-2026-04-24.md)
- **Verdict**: 전체 평균 **7.6/10 FAIL** (Round 1 8.0 대비 -0.4, 목표 85+ 미달)

| 시나리오 | Round 1 | Round 2 | Delta | 판정 |
|---------|---:|---:|---:|:---:|
| S1 강남 요약 | 9.8 | 9.2 | -0.6 | PASS |
| S2 서울역 | 9.6 | 7.9 | -1.7 | FAIL* |
| S3 홍대 vs 성수 | 2.6 | 7.9 | **+5.3** | FAIL (9.0 미달) |
| S4 건대 추천 | 8.9 | 9.2 | +0.3 | PASS |
| S5 명동 리스크 | 8.4 | 6.7 | -1.7 | FAIL* |
| S6 강남 카페 시뮬 | 6.1 | 9.2 | **+3.1** | PASS |
| S7 후속질문 coref | 8.9 | 5.4 | **-3.5** | FAIL |
| S8 배제 토큰 | — | 5.0 | — | FAIL (신규) |

> * S2/S5 는 eval 설계자 district_code 오매핑 — 서울역=3120043 (투입 3110023=서울대병원), 명동=3120028 (투입 3110010=평창동서측). 시스템 회귀 아님.

### 신규 발견 (P0)
- **🔴 Respond LLM `<tool_use>` XML leak** (S3, S8) — Claude Sonnet 4 가 tool 결과 부족 시 응답 본문에 `<tool_use>...</tool_result>` XML 출력. `RESPOND_SYSTEM_PROMPT` 에 금지 규칙 필요
- **🔴 W1 type boost 약함** — "홍대" → `홍대부중(골목상권)` top 매칭. 기대 `홍대입구역(홍대) 발달상권`. `rank_candidates` 의 type_priority 가중치 상향 필요
- **🔴 W1 multi-district regression** — `detect_districts_in_message("홍대 vs 성수")` 가 1 code 만 반환 → S3 core 깨짐
- **🔴 W2 coref + exclusion 실전 경로** — S7 (거기), S8 (홍대 말고) 에서 tool plan empty → Respond 할루시. Planner 가 empty plan 시 clarification fallback 필요

### 개선 영역 (긍정)
- **S3 +5.3** — Round 1 일반지식 할루시 → Round 2 Tool 결과 기반 수치 (DB 일치)
- **S6 +3.1** — `simulate_revenue` + SimulationCard 정상
- **S5 abstention 완벽** — 잘못된 input 에도 수치 할루시 0

### 메모리 신규 2건
- `feedback_respond_tool_use_xml_leak.md`
- `feedback_eval_district_code_hardcode.md`

### 다음 세션 P0
1. `RESPOND_SYSTEM_PROMPT` XML/tag leak 금지 규칙 추가
2. `entity_matching.py` type_priority 가중치 상향 (0.20 → 0.35)
3. Planner empty-plan clarification fallback
4. eval 시나리오 district_code 하드코딩 제거 → entity linking 검증 Round 3

---

## 2026-04-23 (저녁, Pass 2) — E2E Spec Hotfix → PASS 100%

- **Plan**: [e2e-spec-hotfix-2026-04-23.md](../plan/qa/e2e-spec-hotfix-2026-04-23.md)
- **변경 (5 spec + 1 component)**:
  - `StatusBar.tsx` `data-testid="statusbar"` 추가 (Tailwind `.h-8` 셀렉터 5곳 충돌 근본 해소)
  - `waitSSE.ts` / `setup.ts` / `p0-regression.spec.ts` 세 곳 `.h-8` → `[data-testid="statusbar"]`
  - `f12-feedback.spec.ts` `fab.count()===0` precheck 로 skip-guard 보강 (unlimited `getAttribute` timeout 회피)
  - `reg-2026-04-17.spec.ts` `PY` 기본값 `'python'` → `'python3'` (Playwright jammy 이미지)
  - `f01-map-selection.spec.ts` F01-H3 waitForStatusBarContains 8s → 15s
- **결과**: ring0~3 78 test **66 PASS / 0 FAIL / 12 SKIP** (이전 Pass 1 대비 FAIL 4건 소거). prod-smoke 7/7 재확인 — StatusBar HTML attribute 추가 영향 없음.
- **Memory 후보**: 셀렉터 충돌 (h-8), Playwright 이미지 python 미존재, `locator.getAttribute` unlimited wait.

---

## 2026-04-23 (저녁) — v0.4.0 프로덕션 재배포 `c6cc60e`

- **Plan**: [prod-deploy-v0.4.0-2026-04-23.md](../plan/infra/prod-deploy-v0.4.0-2026-04-23.md)
- **Before / After**: `60b6de3` (오전) → `c6cc60e` (저녁), 6 커밋 / +13,038 / -577
- **DB 변경**: `learned_aliases(alias PK, code FK→category_metadata, confidence, source, hit_count, created_at, last_used_at)` + `idx_learned_aliases_code`. Additive, 기존 데이터 무영향.
- **라우트 cut-over**: `/` → 랜딩(F11, 26.5KB), `/app` → 기존 챗맵(16.1KB chunk). `/proxy/kakao-sdk` 200, `/api/kakao-sdk` 404 (cut-over 완료).
- **검증 (P1~P7 + N1~N2)**:
  - P5 summary `perStoreSales=27,307,409` 원/월 (월 단위 정상)
  - P6 recommend 편의점 `per_store_sales=208,887,585` 원/월 (<1B)
  - N1 `/api/districts/3120189/preview` 200 + top_categories
  - N2 `/api/feedback/score` → 빈 payload 422 · 정상 payload 204 (Langfuse idempotent)
- **E2E 회귀 결과**: Pass 1 = 106 test · 94 PASS · 4 FAIL (전부 test infra) · 8 SKIP → Pass 2 hotfix 후 FAIL 0 (위 섹션).
- **배포 메모**: `seed` 는 base image 재사용(build 불필요). migrate 는 backend 와 동일 context → `build backend frontend migrate seed` 전체 지정 필수 (이전 단일 backend build 로는 migrate stale 이슈).

---

## 2026-04-23 — F-01 ETL Fix + Accuracy Gap Fix W1/W2/W3

### F-01 ETL 컬럼 rename + 재적재
- **Audit 근거**: [data-integrity-audit-2026-04-23.md](../qa/runs/data-integrity-audit-2026-04-23.md) §1.1 — `estimated_sales.weekday_sales / weekend_sales / time_1_sales~time_6_sales` 8 컬럼 전량 NULL
- **원인**: Seoul OpenData `VwsmTrdarSelngQq` 2025-10 스키마 개편. `MDW→MDWK · WND→WKEND · TMZON_N→TMZON_HH_HH` 컬럼명 변경에 ETL 미반영
- **Fix**: `server/data/etl/transformers.py:214-229` 8 key rename + docstring 갱신
- **재적재**: `python -m server.data.etl.runner run 2025Q4 --table estimated_sales` · 139.7s 수집 + 21,333 행 upsert
- **검증**: 5 sample 상권 × weekday/weekend/time_1/time_6 = 20/20 NOT NULL, sum > 0. 강남역 평일 3,288억/월 + 주말 898억 (정상치)
- **Plan**: [etl-sales-column-rename-2026-04-23.md](../plan/fix/etl-sales-column-rename-2026-04-23.md)

### W1 — GAP-A Entity Linking + GAP-D Abstention
- **신규 `agent/utils/entity_matching.py`**:
  - `rank_candidates` — prefix 시 score = `0.55 + 0.25×(query_len/name_len)`, type boost (발달상권 +0.20 / 골목 +0.10 / 전통시장 +0.05)
  - `pick_best` — `TOP1_MIN=0.55` · `CLOSE_DELTA=0.08` ambiguity 감지
  - `pg_trgm` 대체: 1,650 행에 Python-side difflib 가 ms 단위 → DB migration 불필요
- **`repositories/real/districts.py`** `_fetch_match_pool` 신규 (prefix + 3글자+contains + reverse-prefix union, LIMIT 25) · `detect_districts_in_message` 재작성 (각 엔트리 `{code, name, score, ambiguous, alternatives}`)
- **신규 `agent/utils/abstention.py`**:
  - `classify_tool_results(tool_results, tool_errors)` → `full / partial / empty`
  - `ABSTENTION_PROMPT_ADDENDUM_EMPTY` — Tool 전부 실패 시 고정 템플릿 강제
  - `ATTRIBUTION_PROMPT_RULE` — 수치 뒤 `(tool_name)` 태그 의무화
  - `scan_unattributed_numbers` — 후처리 정규식 (숫자+단위 뒤 `(tool_)` 없으면 warning)
- **Respond 연동**: `build_respond_prompt` 상단 주입 · `respond_node` 말미 post-hoc scan
- **Smoke**: "홍대 vs 성수 매출" → 홍대입구역(홍대) `ambiguous=True`, 성수역 `ambiguous=False` · "강남역 요약" → 전 수치 attribution tag 주입 ✅

### W2 — GAP-E Coreference + GAP-C 배제
- **신규 `agent/utils/rewriter.py`**:
  - Tier 1 rule: `COREF_PATTERN = 거기|저기|방금|그거|이거|해당|위|동일|아까` + history anchor walk (cards + history 역순)
  - `EXCLUSION_PATTERNS`: `X 말고 / X 대신 / X 빼고 / X 제외` → `excluded_tokens`
  - Tier 2 LLM: `llm_rewrite_message` — coref 감지했으나 anchor 없을 때만 flash 호출 (~200ms)
- **Planner 연동**: `planner_node` 맨 앞 `rule_rewrite` · `excluded_tokens` 와 `district_name` 충돌 시 `district_code/name` 드롭 · comparison intent 에서 `multi` 리스트 `excluded_tokens` 필터
- **chat.py**: `_has_exclusion_phrase` 감지 시 `detect_district_by_name` auto-detect skip
- **Smoke** ("홍대 말고 성수역이랑 건대 비교"): Tool 호출 `compare_districts(['3120052','3120053'])` · Card 2개만 · LLM 텍스트 홍대 언급 0건 · map_cmd 없음 ✅

### W3 — GAP-B Learned Aliases (부분)
- **Alembic 004** `learned_aliases` 테이블: `alias PK · code FK→category_metadata · confidence · source · hit_count · timestamps`. 003 충돌 회피로 004 배정. `alembic upgrade head` 정상.
- **`CategoryResolver` 확장**: `load_from_db` 가 `WHERE confidence >= 0.7` merge · `record_learned_alias(alias, code, confidence, source)` ON CONFLICT 증가 · 테이블 부재 시 silent no-op
- **Deferred**: LLM miss-path 자동 fallback (`resolve` async 전환 필요), `hit_count ≥ 5` promote 잡 — Phase 2 로 분리

### W4 — GAP-F Card-level PDF (deferred)
- Frontend 대규모 변경 (Card 5종 + `useReportExport` 파라미터화 + `ReportDocument` 서브셋) 필요. 체감 빈도 "낮음" + 전체 PDF 워크어라운드 가능 → 후속 세션.

### KPI 기대 (2026-04-13 eval 대비)

| 지표 | 2026-04-22 | W1~W3 적용 후 기대 |
|------|-----------:|------------------:|
| GAP-A 2글자 매칭률 | ~60% | **95%+** (difflib + type boost) |
| GAP-C 배제 정확도 | ~20% | **95%+** (Planner+chat.py 2중 drop) |
| GAP-D 할루시 발생률 | ~15% | **<5%** (empty 템플릿 + attribution scan) |
| GAP-E coref 성공률 | ~30% | **85%+** (anchor walk + Tier2 LLM) |
| 정확성 종합 | 74 | **83~85+** (GAP-B/F deferred 로 상한 85) |

### 검증 상태
- ✅ Unit: entity_matching / abstention / rewriter 각각 smoke 통과
- ✅ Integration: `/api/chat` live smoke — F03 요약, 배제 비교 모두 PASS
- ⏳ Full E2E Ring 0~3: Pass 2 hotfix 에서 검증 완료
- ⏳ 2026-04-13 eval (S1~S8) 재측정: **2026-04-24 Round 2 Plan 작성**, 실행 대기

---

## 2026-04-23 — LLMOps L1 Verification

- **Plan**: [llmops-l1-verification.md](../plan/infra/llmops-l1-verification.md)
- `chat.py` event_generator 에 `agent_done request_id=… session_id=… trace_id=…` 1줄 추가 (printf-style)
- **SDK v2→v3 포팅**: `langfuse>=3` + `langchain>=1` 조합. v2 의 `from langfuse.callback import CallbackHandler` 가 legacy `langchain.callbacks.base` 요구 → `_tracer_valid=False` 차단. v3 의 `langfuse.langchain.CallbackHandler` 는 `langchain_core.callbacks` 기반 OTel 구조.
- **dev env 배선**: `docker-compose.yml` backend 에 LANGFUSE 5 env 패스스루 (prod 와 parity)
- `create_trace_id(seed=...)` 로 handler 생성 시점에 trace_id pre-assign → `TraceContext` 로 주입. astream 종료 후 otel context 이탈과 무관하게 `done.trace_id` 동봉 가능.
- **최종 sanity (2026-04-23 dev)**: SSE `done.trace_id=9d59e6455eeb…` 와 백엔드 로그 `agent_done trace_id=9d59e6455eeb…` 매핑 확인 ✅
- **SSL 우회 (dev only)**: corporate MITM 환경에서 `/api/public/otel/v1/traces` POST SSL cert verify 실패 → `_session.verify=False` + `_certificate_file=False` monkey-patch (OTLP HTTP 는 `_certificate_file` 이 `session.verify` override → 둘 다 필요). `LANGFUSE_OTEL_INSECURE` env 플래그 추가.
- **이미지 재빌드 이슈**: `docker compose build backend` 가 pypi SSL 실패 → `docker cp` + 컨테이너 내 `pip install --trusted-host` 로 우회. 프로덕션 배포 전 Dockerfile pin 반영 필요.
- **미완**: Cloud UI 실제 trace 열람 (C-5) · 프로덕션 sanity (C-8) — 운영 이미지 재빌드 선행 필요.

---

## 2026-04-23 — Env 관례 분리 (.env=prod · .env.dev=dev)

- **배경**: Langfuse Cloud UI 에서 dev/prod trace 혼입. 관례 반대로 `.env`=**프로덕션 배포 파일** · `.env.dev`=**로컬 개발** 로 뒤집음 (prod 서버로 파일 1개만 rsync 하면 되는 단순성).
- **변경 파일** (8건): `server/config.py`, `docker-compose.yml`/`docker-compose.prod.yml`, `frontend/next.config.mjs`, `scripts/validate_env.py`, `scripts/audit/p1_api_vs_db.py`, `scripts/setup_db.py`, `.env.example`, `.gitignore`
- **Langfuse 분리**: 단일 프로젝트 + `LANGFUSE_TRACING_ENVIRONMENT` 필드 (Cloud UI 드롭다운 필터). Prod 워크스페이스 키 별도 (`pk-lf-07a3fa78…`)
- **Memory**: `feedback_env_convention_inverted.md` — prod 서버에 `.env.dev` 가 존재하면 pydantic 이 dev 값을 읽음 → 배포 rsync 제외 필수

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
| FastAPI 백엔드 | 8002 | Real |
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
- Agent Tool 11종 · Card 타입 5종 · SSE 이벤트 9종
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
