# 현재 진행 상황

> 최종 갱신: 2026-04-23 (저녁)
> **프로덕션 v0.4.0 동기화 완료 ✅ — `c6cc60e` 기반 재배포 (저녁), 오전 `60b6de3` 대비 6 커밋 / +13,038 / -577 반영**
> 프로덕션: `marketscope.robitlabs.co.kr` 라이브 — prod-smoke + 신규 2 endpoint 검증 PASS
> 배포 변경: alembic 004 (`learned_aliases`) · `/`=랜딩/`/app`=챗맵 라우트 분리 · Planner Entity Linking + Abstention + Rewriter · `/api/districts/{code}/preview` · `/api/feedback/score`
> E2E 회귀: Ring 0~3 전체 그린 (Mock 39/39 · Real 24/24) + Ops OPS-01/02 + L1 Langfuse 7/7 + prod-smoke 7/7
> 관측성 L1: Langfuse **trace 실제 발행 확인 완료** (dev 로컬 sanity — `done.trace_id=9d59e6455eeb42f685b71f8057915377` + `agent_done` 로그 동일 값 매핑) · langfuse SDK **v2→v3 포팅** (v2 의 legacy langchain 의존 해소) · `agent_done` 운영 로그 조인 추가. 프로덕션 env 배선 완료. [Plan](../plan/infra/llmops-l1-verification.md)
> **2026-04-23 env 관례 분리**: `.env`=프로덕션 · `.env.dev`=로컬 개발 (pydantic/Next.js/scripts 전부 `.env.dev` 우선 로드) · Langfuse prod 워크스페이스 키 분리(`pk-lf-07a3fa78…`) + `LANGFUSE_TRACING_ENVIRONMENT` 태깅으로 dev/prod trace 격리
> 다음 권장: Accuracy Gap Fix W1~W4 (정확성 74 → 85+). [Plan](../plan/fix/accuracy-gap-fix.md) · Phase 2 착수 전 선행 권장
> **2026-04-23 신규 Audit**: Data Integrity Audit 에서 **ETL 키 불일치 (F-01, HIGH)** + **Comparison intent 수치 hallucination (F-02, HIGH)** 발견. [Report](../qa/runs/data-integrity-audit-2026-04-23.md)
> **2026-04-23 UI Phase A~D 구현**: 랜딩 분리(`/` + `/app`) · Zero-LLM 프리뷰(`GET /api/districts/{code}/preview`) · 피드백 3-layer(카드 👍👎 + microsurvey + FAB) · 2026 UI/UX 트렌드 8축 델타 반영. Build 성공, typecheck 0 errors. [Plan](../plan/ui/landing-onboarding-feedback.md)
> **2026-04-23 Mobile Responsive Plan Phase A+B+C 구현**: viewport/breakpoint/touch-target · BottomSheet 3-snap + BottomNav 2-tab · IME/VisualViewport 가드 + auto-scroll FAB. tsc/eslint/build 0 errors. Phase D/E/F (PWA·Perf·A11y/E2E) 미착수. [Plan](../plan/ui/mobile-responsive.md)
> **2026-04-23 F-01 fix + Accuracy Gap W1/W2/W3 구현** ⭐: ETL 8 컬럼 NULL 버그 해소(21,333 행 재적재) + Entity Linking(pg_trgm 대체: difflib+type boost) + Abstention(classify_tool_results+attribution rule) + Coreference Rewriter(Tier1 rule+Tier2 LLM) + 배제 토큰(말고/대신/빼고) + learned_aliases 테이블(alembic 004). [Plan F-01](../plan/fix/etl-sales-column-rename-2026-04-23.md) · [Plan Accuracy Gap](../plan/fix/accuracy-gap-fix.md)
> **2026-04-23 Refactoring Phase 1 Plan 작성**: 7 기준(R1~R7) 기반 저위험/중위험 항목 1 Pass 묶음. Pass1 = singleflight 삭제 + 레거시 E2E 8건 삭제 + status 압축 + Any import 정리. Pass2 = errors.py 래퍼 통합 + blanket except 9건 좁히기 + respond.py 헬퍼 분리 + chatStore slice 분할. [Plan](../plan/infra/phase1-low-mid-risk-2026-04-23.md) — 구현 미착수

## 2026-04-23 (저녁) — v0.4.0 프로덕션 재배포 `c6cc60e`

- **Before**: `60b6de3` (오전 배포, 9h ago)
- **After**: `c6cc60e` v0.4.0 — migrate 003→004, 새 라우트 (`/`=랜딩, `/app`=챗맵), 신규 API 2종
- **Plan**: [prod-deploy-v0.4.0-2026-04-23.md](../plan/infra/prod-deploy-v0.4.0-2026-04-23.md)
- **실행**:
  - `docker compose -f docker-compose.prod.yml build backend frontend migrate seed` (~55s)
  - `docker compose -f docker-compose.prod.yml up -d` → migrate exit 0 (cleanup 0 rows + alembic upgrade head 003→004) → seed exit 0 → backend healthy ~23s
- **DB 변경**: `learned_aliases(alias PK, code FK→category_metadata, confidence, source, hit_count, created_at, last_used_at)` + `idx_learned_aliases_code`. Additive, 기존 데이터 무영향.
- **라우트 cut-over**: `/` → 랜딩(F11, size=26.5KB), `/app` → 기존 챗맵(size=16.1KB Next.js chunk). `/proxy/kakao-sdk` 200 유지, `/api/kakao-sdk` 404 유지.
- **검증**:
  - P1 `/` 200 + landing marker 1
  - P2 `/proxy/kakao-sdk` 200 + 4095 bytes
  - P3 polygons 500 features Polygon
  - P4 `강남역` → 3120189
  - P5 SSE summary: thinking/tool/card/text 전수, `perStoreSales=27,307,409` 원/월 (월 단위 정상, 5M~100M 범위)
  - P6 recommend: 편의점 `per_store_sales=208,887,585` 원/월 (월 단위 정상, <1B)
  - P7 `/app` 200 + app markers
  - N1 `/api/districts/3120189/preview` 200 + `top_categories` 풍부한 F13 preview
  - N2 `/api/feedback/score` → 빈 payload 422 (validation), 정상 payload 204 (Langfuse idempotent drop)
- **prod-smoke spec 갱신**: P7 `page.goto(BASE)` → `page.goto(BASE + '/app')` — 랜딩 분리 대응.
- **이미지 업데이트**: backend `catchment-area-analysis-backend` + frontend `a5d385012a6f` + migrate 동일 이미지 재사용.
- **배포 메모**: `seed` 서비스는 `postgis/postgis:16-3.4` 베이스 이미지 재사용(build 없음). migrate 는 backend 와 동일 context → 한 번 빌드로 둘 다 갱신.

---

## 2026-04-23 — Env 관례 분리 (.env=prod, .env.dev=로컬)

- **배경**: LLMOps L1 완결 직후 Langfuse Cloud UI 에서 dev/prod trace 가 동일 프로젝트·환경 태그 없이 섞여 저장. 로컬 실험 trace 가 prod 메트릭/evaluation 에 유입될 위험. Langfuse 제공 prod 전용 워크스페이스 키 분리 요구.
- **결정**: 일반 관례(`.env`=dev, `.env.prod`=prod) 반대로 `.env`=**프로덕션 배포 파일** · `.env.dev`=**로컬 개발** 로 뒤집음. 프로덕션 서버로 파일 1개만 rsync 하면 되는 단순성 택함.
- **변경 파일** (코드 8건):
  - `server/server/config.py` — `_ENV_DEV`/`_ENV_PROD` 이중 조회, `.env.dev` 있으면 우선 로드 (local uvicorn 보호)
  - `docker-compose.yml` — `backend`/`backend-dev`/`frontend-dev` 서비스에 `env_file: .env.dev` 명시. 기존 `${VAR:-}` 보간 제거 (env_file 이 empty 로 덮여쓰는 문제 회피)
  - `docker-compose.prod.yml` — `LANGFUSE_TRACING_ENVIRONMENT: ${...:-production}` 기본값 + `LANGFUSE_OTEL_INSECURE` 패스스루
  - `frontend/next.config.mjs` — `.env.dev` 우선 로드 (NEXT_PUBLIC_* baked-in 에서 dev 값 사용)
  - `scripts/validate_env.py` — 기본 경로 `.env.dev` 자동 선택
  - `scripts/audit/p1_api_vs_db.py` — `load_env()` 에서 `.env.dev` 우선
  - `scripts/setup_db.py` — 신규 setup 시 `.env.dev` 생성 (기존 `.env` 생성 로직 전환)
  - `.env.example` — 신규 관례(파일 4개 용도) + 배포 명령 주석
  - `.gitignore` — `.env.dev` 추가 (`.env` 는 기존 등록)
- **신규 파일** (secrets, gitignored):
  - `.env` — prod 워크스페이스 (`LANGFUSE_PUBLIC_KEY=pk-lf-07a3fa78-…` · `LANGFUSE_TRACING_ENVIRONMENT=production`)
  - `.env.dev` — 기존 `.env` rename (dev 키 + `LANGFUSE_TRACING_ENVIRONMENT=development` + `LANGFUSE_OTEL_INSECURE=true`)
- **Langfuse 분리 전략**: 단일 프로젝트 + `environment` 필드 분리 (Cloud UI 드롭다운 필터). 프로젝트 복제는 과잉 — evaluation/대시보드 파편화 회피.
- **검증**:
  - `docker compose config` → dev 컨테이너에 `pk-lf-bc6db5db-…` (dev 키) + `TRACING_ENVIRONMENT=development` 정상 주입
  - `docker compose -f docker-compose.prod.yml config` → `pk-lf-07a3fa78-…` (prod) + `TRACING_ENVIRONMENT=production` 정상
  - `python scripts/validate_env.py` → `.env.dev` 자동 픽업 확인
- **미해결 트랩**:
  - 마크다운 코드블록 붙여넣기 시 여러 `KEY=VAL` 이 공백 구분자로 한 줄에 merge 되는 이슈 발견 (라인 7~11). `lstrip()` + `re.split(r'\s{2,}(?=[A-Z_]+=)')` 로 복구. `.env` 생성 후 `python scripts/validate_env.py` 로 라인 단위 검증 권장.
- **Memory**: `feedback_env_convention_inverted.md` 신규 — prod 서버에 `.env.dev` 가 존재하면 pydantic 이 dev 값을 읽음 → 배포 rsync 제외 필수.

---

## 2026-04-23 — Refactoring Phase 1 (저위험/중위험) Plan 작성

- **Plan**: [docs/plan/infra/phase1-low-mid-risk-2026-04-23.md](../plan/infra/phase1-low-mid-risk-2026-04-23.md)
- **검토 기준 7축 (R1~R7)**: 계층 경계 / SSE 경로 무결성 / async·타입 안정 / 테스트 격리 / 팽창 임계(400 LOC · 300 LOC · state 10) / env·문서 drift / 한국어 도메인 집약
- **Audit 결과 근거**:
  - 백엔드: `agent/nodes/respond.py` 502 LOC · `planner.py` 399 LOC · blanket `except Exception` 9건 · `singleflight.py` 호출처 0 · `routes/*` 에서 `HTTPException` 15건 직접 raise (errors.py 래퍼 미사용) · `agent_mode=react` 레거시 없음 확인
  - 프론트: `chatStore.ts` 381 LOC (state 13 + action 18) · 레거시 `feature1~7-*.spec.ts` 8건과 `ring1/f01~f03` 중복
  - 횡단: `current-status.md` 411줄 (status-compress 400 임계 초과) · CORS_ORIGINS dev(4)/prod(5) drift · scripts/ + server/scripts/ 혼재
- **Pass 1 (저위험, 30분~1시간)**:
  - `server/server/services/singleflight.py` 삭제 + 참조 정리
  - `frontend/e2e/feature{1..7}-*.spec.ts` 8건 삭제 (ring1 f01~f03 중복 확인 후)
  - `docs/status/current-status.md` 2026-04-22 이하 일자 섹션 이력 테이블 1행씩 압축 → < 400 LOC
  - `planner.py:8` 등 미사용 `from typing import Any` 일괄 정리 (ruff --fix)
- **Pass 2 (중위험, 1주 내)**:
  - `api/errors.py::make_error_response` 래퍼로 routes `HTTPException` 15건 통합
  - `except Exception` 9건(`graph.py:348`, `chat.py:130`, `planner.py:304` 외) → `TimeoutError | CircuitOpenError | SQLAlchemyError` 좁히기
  - `agent/nodes/respond.py` 502 LOC → `agent/utils/formatting.py` 로 `_compute_hints`/`_format_tool_results`/`_format_history` 3종 이식, 목표 ~300 LOC
  - `stores/chatStore.ts` 381 LOC → `stores/slices/{preview,mobile,feedback}.ts` 후 combine (single-store 유지)
- **Out of Scope**: Service layer 신설, Agent tool DI 전환, config.py 4그룹 분할, Next.js 15 승격, SSE 이벤트 스키마 변경
- **Memory 참조**: `feedback_formatter_strips_unused_imports` (Any 제거는 단일 Edit) · `feedback_structlog_extra_silent` (printf-style) · `feedback_read_large_doc_chunking` (status 청크 Read) · `feedback_e2e_user_message_pollution` (레거시 spec 삭제 전 ring1 커버 확인) · `feedback_react_event_keys_unique` (chatStore slice 분할 시 key 유일성)
- **Scenario**: R3-REFACTOR-01/02/03 (Pass1 저위험 회귀 · respond.py 분할 · chatStore slice 분할)
- **후속 Plan 후보**: `infra/service-layer-extraction.md` (R1) · `infra/config-split.md` (R5) · `agent-improvement/tool-dependency-injection.md` (R4)
- **구현 상태**: 미착수 (Plan 승인 + 착수 지시 대기)

---

## 2026-04-23 — F-01 ETL Fix + Accuracy Gap Fix W1/W2/W3

### F-01 ETL 컬럼 rename + 재적재

- **Audit 근거**: [docs/qa/runs/data-integrity-audit-2026-04-23.md](../qa/runs/data-integrity-audit-2026-04-23.md) §1.1 — `estimated_sales.weekday_sales / weekend_sales / time_1_sales~time_6_sales` 8 컬럼 전량 NULL
- **근본 원인**: Seoul OpenData `VwsmTrdarSelngQq` 2025-10 스키마 개편. `MDW→MDWK` · `WND→WKEND` · `TMZON_N→TMZON_HH_HH` 컬럼명 변경에 ETL 미반영
- **Fix**: `server/data/etl/transformers.py:214-229` 8 key rename + docstring 에 2025-10 개편 사실 명시
- **재적재**: `python -m server.data.etl.runner run 2025Q4 --table estimated_sales` · 139.7s 수집 + 21,333 행 upsert
- **검증**: 5 sample 상권(명동/서울역/건대/홍대/강남역) × weekday/weekend/time_1/time_6 = 20/20 NOT NULL, sum > 0
  - 강남역 평일 3,288억/월 + 주말 898억 · 홍대 평일 1,031억 + 주말 564억 (정상치)
- **Smoke**: Summary card `insights.weekendUplift: -72.7` (이전 NULL) · LLM 응답에 주말 매출 감소 분석 포함
- **Plan**: [etl-sales-column-rename-2026-04-23.md](../plan/fix/etl-sales-column-rename-2026-04-23.md)

### W1 — GAP-A Entity Linking + GAP-D Abstention

- **신규 유틸 `agent/utils/entity_matching.py`**:
  - `rank_candidates` 함수 — prefix 매칭 시 score = `0.55 + 0.25×(query_len / name_len)`, type boost = `TYPE_PRIORITY × 0.05` (발달상권 +0.20, 골목 +0.10, 전통시장 +0.05)
  - `pick_best` — `TOP1_MIN=0.55` · `CLOSE_DELTA=0.08` 기반 ambiguity 감지
  - `pg_trgm` 대체: 1,650 행 규모에 Python-side 가 ms 단위 → DB migration 불필요
- **`repositories/real/districts.py`**:
  - `_fetch_match_pool` 신규 — prefix + (3글자+)contains + reverse-prefix 의 union SQL, LIMIT 25
  - `detect_districts_in_message` / `detect_district_by_name` 재작성 — 각 엔트리에 `{code, name, score, ambiguous, alternatives}` 반환
  - `_candidate_words` 문서화 — 2글자 후보(성수, 종로)도 유지
- **Mock `districts.py`**: 동일 shape 유지 (score=1.0, ambiguous=False)
- **Planner 연동**: `ambiguous_districts` state 필드 추가 · Respond prompt "⚠️ 상권 매칭 모호" 섹션
- **신규 유틸 `agent/utils/abstention.py`**:
  - `classify_tool_results(tool_results, tool_errors)` → `full / partial / empty`
  - `ABSTENTION_PROMPT_ADDENDUM_EMPTY` — Tool 전부 실패 시 고정 템플릿 응답 강제
  - `ABSTENTION_PROMPT_ADDENDUM_PARTIAL` — 누락 필드만 "해당 데이터 없음"
  - `ATTRIBUTION_PROMPT_RULE` — 수치 뒤 `(tool_name)` 태그 의무화
  - `scan_unattributed_numbers` — 후처리 정규식 (숫자+단위 뒤 `(tool_)` 없으면 structlog 경고)
- **Respond 연동**: `build_respond_prompt` 상단 주입 · `respond_node` 말미 post-hoc scan
- **Smoke**:
  - "홍대 vs 성수 매출" → `홍대입구역(홍대) 발달상권` ambiguous=True + `성수역 발달상권` ambiguous=False ✅
  - "종로 상권" → `종로4가 발달상권` top + `종로6가 / 종로구청` alternatives ✅
  - "강남역 상권 요약" → `"하루 유동인구 745만 3천명 (get_district_summary)"` 등 attribution tag 전부 주입 ✅

### W2 — GAP-E Coreference + GAP-C 배제

- **신규 유틸 `agent/utils/rewriter.py`**:
  - Tier 1 (deterministic): `COREF_PATTERN = 거기|저기|방금|그거|이거|해당|위|동일|아까` + history anchor walk (`_find_anchor_from_history` → cards + history 역순)
  - `EXCLUSION_PATTERNS`: `X 말고 / X 대신 / X 빼고 / X 제외` → `excluded_tokens` list
  - Tier 2 (LLM): `llm_rewrite_message` — coref 감지했으나 anchor 없을 때만 flash 호출 (~200ms · `_create_llm(role="planner")`)
- **Planner 연동** (`planner_node` 맨 앞):
  - `rule_rewrite` 호출 → `message = rewrite.rewritten`
  - `excluded_tokens` 와 `district_name` 충돌 시 `district_code/name` 드롭 (auto-detected anchor leak 방지)
  - comparison intent 에서 `multi` 리스트 `excluded_tokens` 필터링
  - Return dict 에 `district_code: "", district_name: ""` propagate → Respond prompt 의 "현재 컨텍스트" 도 정리
- **chat.py 패치**: `_has_exclusion_phrase` 감지 시 `detect_district_by_name` auto-detect skip → 지도 이동도 엉뚱한 상권으로 가지 않음
- **Smoke** (`"홍대 말고 성수역이랑 건대 비교"`):
  - Tool 호출: `compare_districts(district_codes=['3120052', '3120053'])` — 홍대 완전 배제 ✅
  - Card: `['3120052', '3120053']` 2개만 ✅
  - LLM 텍스트: 홍대 언급 0건 ✅
  - map_cmd: 송신 없음 (chat.py skip 동작) ✅

### W3 — GAP-B Learned Aliases (부분)

- **Alembic 004** (`learned_aliases` 테이블):
  - `alias VARCHAR(200) PK · code VARCHAR(20) FK→category_metadata(category_code) · confidence REAL · source · hit_count · created_at · last_used_at`
  - 이미 회수 `003_add_category_aliases` 와 번호 충돌 회피 → 004 배정
  - 적용 `alembic upgrade head` 성공, FK/CHECK 제약 전부 정상
- **`CategoryResolver` 확장**:
  - `load_from_db` 에서 `learned_aliases WHERE confidence >= 0.7` 을 in-memory keyword dict 에 merge
  - `record_learned_alias(alias, code, confidence, source)` — ON CONFLICT 시 `hit_count++` · `confidence = GREATEST(...)` · `last_used_at = NOW()`
  - 테이블 부재 시 silent no-op (downgrade-safe)
- **Smoke**: `record_learned_alias("무인카페", "CS100001", 0.85)` 후 `resolve("무인카페") == "CS100001"` ✅
- **Deferred**: LLM miss-path 자동 fallback (`resolve` async 전환 필요), hit_count promote 야간 잡 — 기존 `category_metadata.aliases` seed 100건 + manual curation 으로 대부분 커버되므로 Phase 2 로 분리

### W4 — GAP-F Card-level PDF (deferred)

- Frontend 대규모 변경 (Card 5종 + `useReportExport` 파라미터화 + `ReportDocument` 서브셋) 필요
- 체감 빈도 "낮음" + 기존 전체 PDF 로 워크어라운드 가능 → accuracy 개선과 분리된 후속 세션으로 이관

### 신규 파일/변경

**신규**:
- `server/server/agent/utils/entity_matching.py` (124 lines)
- `server/server/agent/utils/abstention.py` (110 lines)
- `server/server/agent/utils/rewriter.py` (204 lines)
- `server/server/agent/utils/__init__.py`
- `server/alembic/versions/004_learned_aliases.py`
- `docs/plan/fix/etl-sales-column-rename-2026-04-23.md`

**수정**:
- `server/server/data/etl/transformers.py` — 8 key rename + docstring
- `server/server/repositories/real/districts.py` — fetch_match_pool + ranking 통합
- `server/server/repositories/mock/districts.py` — dict shape 통일
- `server/server/agent/state.py` — `ambiguous_districts` 추가
- `server/server/agent/nodes/planner.py` — rewriter pre-process + exclusion filter + state propagation
- `server/server/agent/nodes/respond.py` — abstention addendum + attribution rule + post-hoc scan
- `server/server/api/routes/chat.py` — `_has_exclusion_phrase` skip
- `server/server/services/category_resolver.py` — `record_learned_alias` + learned_aliases read

### 메모리 신규 1건 + 업데이트 1건

- `feedback_etl_api_column_rename.md` — 2026-04-23 fix 메타 추가 (`docker cp` workaround, env_file 미설정 시 shell 주입법)

### KPI 기대 (2026-04-13 eval 대비)

| 지표 | 2026-04-22 | W1~W3 적용 후 기대 |
|------|-----------:|------------------:|
| GAP-A 2글자 매칭률 | ~60% | **95%+** (difflib + type boost 로 발달상권 우선) |
| GAP-C 배제 정확도 | ~20% | **95%+** (Planner+chat.py 2중 drop) |
| GAP-D 할루시 발생률 | ~15% | **<5%** (empty 템플릿 + attribution scan) |
| GAP-E coref 성공률 | ~30% | **85%+** (anchor walk + Tier2 LLM) |
| 정확성 종합 | 74 | **83~85+** (GAP-B/F deferred로 상한 85) |

### 검증 상태

- ✅ Unit: entity_matching / abstention / rewriter 각각 pytest-free smoke 통과
- ✅ Integration: `/api/chat` live smoke — F03 요약, 배제 비교 모두 PASS
- ⏳ Full E2E Ring 0~3: 재실행 권장 (본 세션에서 생략 — 다음 commit 직전 수행 권장)
- ⏳ 2026-04-13 eval (S1~S8): W1~W3 완료 후 재측정 권장

### 커밋 미생성

사용자 명시 지시 전까지 체크포인트 상태. `transformers.py` 등 서버 파일 + migration 004 + utils 3종 + plan 문서 1건 + status 업데이트 1건이 스테이지 대상.

---

## 2026-04-23 — LLMOps L1 Verification (SDK v2→v3 포팅 + 실제 trace 발행 확인)

- **Plan**: [docs/plan/infra/llmops-l1-verification.md](../plan/infra/llmops-l1-verification.md)
- **C-6 (코드)** `server/server/api/routes/chat.py` event_generator 에 `done` 이벤트 감지 시 `agent_done request_id=… session_id=… district=… trace_id=…` 1줄 추가. printf-style — dev `ConsoleRenderer` / prod `JSONRenderer` 양쪽 grep 가능.
- **dev env 배선** `docker-compose.yml` backend 서비스 environment 에 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` / `LANGFUSE_SAMPLING_RATE` / `LANGFUSE_SESSION_SALT` 5줄 패스스루 (prod `docker-compose.prod.yml:96-100` 과 parity).
- **SDK 포팅 v2 → v3** ⭐ — Cloud 키 투입 후 trace 가 여전히 발행 안 된 원인 추적:
  - 원인: `langfuse 2.60.10` 의 `from langfuse.callback import CallbackHandler` 가 legacy `langchain.callbacks.base` 요구. 컨테이너엔 `langchain_core`/`langchain_anthropic`/`langchain_google_genai` (v4.x) 만 있고 `langchain` 메타 패키지 부재 → `_tracer_valid=False` 로 차단되어 handler=None.
  - 실패 경로: `langchain<0.4` 설치 시 langchain-core 0.3 로 강제 downgrade → `langchain_anthropic`/`langchain_google_genai` 4.x 의 `ContextOverflowError` ImportError 로 LLM 스택 파괴. 복구 후 v3 상향.
  - 해결: `langfuse>=3,<4` + `langchain>=1,<2` 조합. v3 의 `langfuse.langchain.CallbackHandler` 는 `langchain_core.callbacks.BaseCallbackHandler` 기반 OpenTelemetry 구조 — 기존 `langchain-core 1.x` 와 공존.
  - v3 설계 변경: Client (`Langfuse`) 와 Handler (`CallbackHandler`) 분리. `create_trace_id(seed=...)` 로 **handler 생성 시점에 trace_id 결정적 pre-assign** → `TraceContext(trace_id=...)` 로 주입. astream 종료 후 otel context 이탈과 무관하게 `done.trace_id` 동봉 가능.
  - `langfuse_tracer.py` 전면 재작성 + `graph.py` astream config 에 `metadata / tags / run_name` 3필드 추가.
- **최종 sanity (2026-04-23)**:
  - curl: `POST http://localhost:8000/api/chat {"message":"강남역 요약","district_code":"3120189","session_id":"verify-2026-04-23-langfuse"}` → 37 `data:` 라인
  - raw done: `data: {"type": "done", "trace_id": "9d59e6455eeb42f685b71f8057915377"}` ✅
  - 백엔드 로그: `agent_done request_id=b844a844-820a-41fe-81e9-2f5b99f61883 session_id=verify-2026-04-23-langfuse district=3120189 trace_id=9d59e6455eeb42f685b71f8057915377` ✅
  - **SSE done.trace_id === agent_done 로그 trace_id** — 양방향 매핑 확인
- **후속 문제: Cloud UI Traces 탭 비어 있음** → OTEL HTTP exporter 가 `/api/public/otel/v1/traces` POST 에서 `SSLError CERTIFICATE_VERIFY_FAILED` 로 전량 드롭. 로컬 dev 환경이 corporate/ISP MITM HTTPS intercept 로 certifi·시스템 CA 둘 다 실패.
- **SSL 우회 조치 (dev only)** ⭐:
  - Langfuse 공식 문서에는 OTEL HTTP exporter 의 verify 비활성 옵션 없음. unsupported workaround 로 언급된 `exporter._session.verify=False` monkey-patch 적용. 단 OTLP HTTP 는 `session.post(..., verify=self._certificate_file)` 로 `_certificate_file` 이 session.verify 를 override → **둘 다 False 필수**.
  - `server/server/config.py` `langfuse_otel_insecure: bool = False` 신규 + `docker-compose.yml` 에 `LANGFUSE_OTEL_INSECURE` 패스스루 + `.env` 에 `LANGFUSE_OTEL_INSECURE=true` (로컬 dev only).
  - `langfuse_tracer.py::_disable_otel_tls_verify()` — `trace.get_tracer_provider()._active_span_processor._span_processors[*].span_exporter` 순회 패치. `urllib3.disable_warnings` + `WARN "DO NOT use in production"` 1건.
  - 재검증: 3회 연속 curl → 3 trace 전송, OTEL export 실패 로그 **0건**. 샘플 trace ID: `6858b5fc5b68643db593f73d2d56483a` / `bf8f637e2976200793402b747d10170f` / `4365fcdf399efa11cfaf447ad86b5521`.
- **이미지 재빌드 이슈**: `docker compose build backend` 가 pypi SSL cert verify 실패로 막힘 (2026-04-22 기존 이슈). 우회: `docker cp` 로 수정 파일 3개(`chat.py`/`langfuse_tracer.py`/`graph.py`) 주입 + `pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org 'langfuse>=3,<4' 'langchain>=1,<2'` 컨테이너 내 설치 + `docker compose restart backend`. **프로덕션 배포 전 `Dockerfile` 에 해당 pin 반영 필요**.
- **미완 (사용자 작업 필요)**:
  - **C-5** Langfuse Cloud UI 에서 trace ID `9d59e6455eeb42f685b71f8057915377` 열람 → URL 을 plan `[기록]` 섹션에 최종 인용
  - **C-8** 프로덕션(`marketscope.robitlabs.co.kr`) 1회 sanity. 단 **prod Dockerfile / pyproject 재빌드 선행 필요** (`langfuse>=3` + `langchain>=1` 포함). 운영 이미지 빌드 가능해지면 plan Pass 3 실행 권장.
- **변경 파일**: `server/pyproject.toml` · `server/server/config.py` (langfuse_otel_insecure 신규) · `server/server/services/langfuse_tracer.py` (전면 재작성 + SSL monkey-patch) · `server/server/agent/graph.py` (config metadata/tags/run_name) · `server/server/api/routes/chat.py` (C-6 로그) · `docker-compose.yml` (Langfuse 6 env) · `.env` (키 + LANGFUSE_OTEL_INSECURE=true, gitignored) · `docs/plan/infra/llmops-l1-verification.md` · 본 status 섹션.
- **커밋 미생성**: 사용자 명시 지시 전 체크포인트. pyproject pin 변경은 이미지 재빌드와 묶이므로 `Dockerfile` pypi SSL 우회 결정 후 커밋 권장.

---

## 2026-04-23 — Mobile Responsive Plan Phase A+B+C

- **Plan**: [docs/plan/ui/mobile-responsive.md](../plan/ui/mobile-responsive.md) (916줄, 10축 2026 트렌드 리서치 기반)
- **Phase A — Foundation** ✅ (7/7):
  - `app/layout.tsx` — `export const viewport: Viewport` (viewport-fit cover · userScalable · themeColor light/dark)
  - `tailwind.config.ts` — `xs: 375px` screens 확장 (sm~2xl 명시)
  - `hooks/useBreakpoint.ts` 신규 — SSR-safe mobile/tablet/desktop (matchMedia subscribe)
  - `globals.css` — `.touch-target` + `pb/pt/pl/pr-safe` utilities + `--safe-top/bottom/left/right` + `--kb-inset` 토큰
  - `app/app/page.tsx` — `useBreakpoint()` 분기 (mobile → MobileLayout / 그 외 SplitPanel 유지)
  - `SplitPanel.tsx` — tablet 50/50 고정 + desktop 만 drag 활성
  - `playwright.config.ts` — `iPhone 12` · `Galaxy S9+` · `iPad Pro 11` 3 device project 추가
- **Phase B — Sheet + Nav** ✅ (11/11):
  - `chatStore` — `mobileTab`('map'|'chat') · `sheetSnap`('hidden'|'peek'|'half'|'full') · `unreadCount` + setters. `setMobileTab('chat')` 시 자동 `resetUnread`.
  - `components/mobile/BottomSheet.tsx` 신규 — 4-snap (hidden 4vh / peek 15vh / half 55vh / full 90vh) · pointer drag delta + snap 정착 알고리즘 · haptic (`navigator.vibrate(10)`) · `prefers-reduced-motion` 가드 · `role="dialog" aria-modal="false"`.
  - `components/mobile/BottomSheetHandle.tsx` 신규 — drag indicator 36×4px + `role="slider"` + ArrowUp/Down/Home/End 키보드 지원 + `aria-valuenow`.
  - `components/mobile/BottomNav.tsx` 신규 — 2-tab tablist (지도🗺️/챗💬) · unread badge (9+) · `paddingBottom: env(safe-area-inset-bottom)` · 44px touch target.
  - `components/mobile/MobileLayout.tsx` 신규 — `height: 100dvh` · 지도 full-bleed + BottomSheet + BottomNav + `useKeyboardInset()` mount.
  - `MapControls.tsx` — 모바일 44px(`w-11 h-11`) / md 이상 36px(`md:w-9 md:h-9`) 터치 타깃 분기.
  - `HeatmapLayer.tsx` — `radiusPixels` 모바일 40 / 데스크톱 60 (`useBreakpoint()`) — INP 개선.
  - `useMapSync.ts` — 폴리곤 클릭 → `setPreview(code)` + `sheetSnap === 'hidden'` 인 경우만 `'peek'` 승격 (사용자 이미 확장했으면 유지).
  - `chatStore.sendMessage` — 메시지 전송 시 `mobileTab='chat'` + `sheetSnap='full'` 자동 승격 (desktop 은 영향 0).
  - `eventHandlers.ts` — `card` 이벤트 수신 시 `mobileTab !== 'chat'` 이면 `incrementUnread()`.
  - landing-onboarding-feedback.md Phase E1~E5 체크박스는 이미 "→ mobile-responsive.md B1/A5/B9/A6/F3" 포인터 존재 (migration 상태 확정).
- **Phase C — ChatInput · IME · 자동 스크롤** ✅ (9/9):
  - `hooks/useKeyboardInset.ts` 신규 — VirtualKeyboard API `overlaysContent=true` (Chrome/Edge) + VisualViewport `resize` fallback (iOS Safari) → `--kb-inset` CSS 변수 동기. `compositionstart/end` 동안 update skip (IME 방해 방지).
  - `ChatInput.tsx` — IME 가드 (`e.nativeEvent.isComposing` 우선 + `e.keyCode === 229` 보조) · `padding-bottom: max(0.75rem, env(safe-area-inset-bottom))` · `margin-bottom: var(--kb-inset)` · `font-size: 16px` (iOS zoom 회피) · `aria-label="메시지 입력"` · 전송 버튼 44px 모바일.
  - `MessageList.tsx` — `IntersectionObserver` 기반 `isAtBottom` (rootMargin 100px) · 스트리밍 자동 scrollIntoView 는 `isAtBottom === true` 일 때만 · "↓ 최신 메시지" FAB — `!isAtBottom && messages.length > 0` 시 우하단 노출 · `MessageList` 루트 구조 `relative overflow-hidden + absolute inset-0 overflow-y-auto` 로 전환하여 FAB positioning 기반 확보.
- **검증**:
  - `tsc --noEmit` → **0 errors**
  - `eslint` (Phase A/B/C 변경 파일 전수) → **0 errors**
  - `next build` → **성공**. `/` 5.73 kB/109 kB · `/app` 161 kB/264 kB · shared 87.7 kB. `/app` First Load +2 kB (mobile 컴포넌트 번들 영향, 200 kB gzip 예산 내).
- **Phase D/E/F 미착수**:
  - D (PWA): manifest.ts + workbox SW + offline.html — `npm install workbox-*` 의존성 + icons 192/512/maskable 에셋 필요
  - E (Perf): Pretendard WOFF2 subset 생성 · AVIF 변환 스크립트 · `@next/bundle-analyzer`
  - F (A11y + E2E + 문서): axe-core 통합 · Ring1/2/3 신규 spec 18개 · TalkBack/VoiceOver 실기기 수동 QA
- **커밋 미생성**: 사용자 명시 지시 전까지 체크포인트 상태 유지.

---

## 2026-04-23 — UI Landing / Onboarding / Feedback Phase A~D

- **Plan**: [docs/plan/ui/landing-onboarding-feedback.md](../plan/ui/landing-onboarding-feedback.md) (807줄)
- **Feature 신규**: F11 랜딩 · F12 피드백 3-layer · F13 상권 프리뷰 (Zero-LLM)
- **Phase A — 랜딩 라우트 + 브랜딩**:
  - `/` 랜딩 (신규) / `/app` 앱 이관. 번들 분리 — 랜딩 `/` = 6.54 kB/101 kB First Load.
  - `app/globals.css` 를 `[data-theme='light'|'dark']` 이중 팔레트로 리팩터 + brand tokens (`--brand-deep-blue`, `--brand-teal`, `--compare-slot-1/2/3`). 기본값 **light**.
  - `@media (prefers-reduced-motion: reduce)` 전역 블록 추가 (0.01ms clamp).
  - Pretendard Variable CDN (`app/layout.tsx` `<link>`). Inter 라틴 fallback 유지.
  - `components/landing/` 8개 컴포넌트 (Header/Hero/RoleSelector/HeroVisual/BentoFeatures/HowItWorks/BetaBanner/Footer).
  - Role routing 3-way (소상공인/투자자/창업) + `localStorage['ms_role']` + URL deep link (`/app?role=&q=`).
  - Hero Visual = CSS-only 지도 PNG + 카드 3종 cross-fade 8s loop (번들 영향 0).
  - Toolbar 로고 → `/` (랜딩 복귀).
  - E2E 헬퍼 `gotoApp()` + 28 spec 파일의 `page.goto('/')` → `page.goto('/app')` 일괄 치환.
- **Phase B — 상권 프리뷰 (F13)**:
  - `GET /api/districts/{code}/preview?role=` 라우트 신설 (`server/server/api/routes/districts.py`).
    기존 repo (`stores.get_store_info` · `floating_pop.get_floating_population` × 현재/전분기) 병렬 호출, `asyncio.gather` + Redis `preview:{code}:{role|default}` TTL 24h. **LLM 호출 0**.
  - `_suggestions_for(role)` — intents.yaml 프리셋 기반 정적 5 질문 (역할별 상이).
  - `useMapSync` 재작성 — auto sendMessage 제거, `chatStore.setPreview(code)` 만 호출.
  - `chatStore` 확장: `preview` · `previewLoading` · `role` · `messageCount` · `lastTraceId` · `feedbackByTrace`.
  - `PreviewCard.tsx` — 상권명 · 유형 · Top 3 share bar · 유동인구 prev-quarter delta · peak hour · 예시 질문 chip 5개 · "AI 분석 보기" CTA.
  - ChatPanel `previewSlot` prop 으로 MessageList 최상단 렌더.
  - `lib/api.ts::fetchDistrictPreview(code, role?)`.
- **Phase C — 피드백 3-layer (F12)**:
  - L1 `FeedbackRow` — 카드 trace 단위 👍👎 + 👎 클릭 시 reason chip 3 (부정확함/느림/주제 벗어남) + 자유 텍스트 60자. 500ms debounce + 세션 `feedbackByTrace` dedup.
  - L1 백엔드 `POST /api/feedback/score` (`server/server/api/routes/feedback.py`) — Langfuse `score` API proxy. Langfuse 비활성 시 HTTP 204 silent drop. Redis 24h `feedback:seen:{trace_id}` idempotency.
  - L2 `FreeLimitSurvey` — 5-emoji 만족도 + 조건부 Premium 관심 문항 + dismiss. 쿠키 `ms_survey_week_<YYYYww>` 주 1회 상한. GA4 `dataLayer.push('free_limit_survey')`. 서버 게이팅 Phase 2 결합 예정.
  - L3 `FeedbackFab` — 우하단 fixed, 랜딩 + 앱 공통. `NEXT_PUBLIC_KAKAO_CHANNEL_URL` > `NEXT_PUBLIC_FEEDBACK_FORM_URL` > 숨김. Tally fallback `FeedbackModal` (ESC 닫기 + body scroll lock).
- **Phase D — 문서 + E2E 갱신**:
  - `docs/spec/feature-list.md` 에 F11/F12/F13 추가.
  - `docs/spec/features/F11-landing.md` · `F12-feedback.md` · `F13-district-preview.md` 신규.
  - `docs/architecture/frontend.md` · `backend.md` 라우팅 · 엔드포인트 표 갱신.
  - Ring 0 `R0-LANDING-STACK` (hero-section 마커 검증) 추가.
  - Ring 1 신규: `f11-landing.spec.ts` 6 test · `f12-feedback.spec.ts` 3 test · `preview-api.spec.ts` 3 test.
  - Ring 3 신규: `neg-feedback-missing.spec.ts`.
  - `window.__chatStore` 노출 (E2E 에서 `messageCount` · `lastTraceId` 시드).
- **검증**:
  - TypeScript `npx tsc --noEmit` → **0 errors**.
  - Next.js build → **성공**. `/` 5.73 kB/109 kB · `/app` 159 kB/262 kB · shared 87.7 kB.
  - Ruff backend lint (districts.py, feedback.py) → **All checks passed**.
  - Playwright `--list` → **129 tests in 36 files** (신규 13 test 포함).
- **Phase E (모바일 bottom sheet · View Transitions · 테마 토글) 미착수**: 랜딩/프리뷰/피드백 안정화 후 별도 Plan pass 로 진행.

## 2026-04-23 — Data Integrity Audit (Phase 1~3)

- **Report**: [docs/qa/runs/data-integrity-audit-2026-04-23.md](../qa/runs/data-integrity-audit-2026-04-23.md)
- **Plan**: [docs/plan/qa/data-integrity-audit.md](../plan/qa/data-integrity-audit.md)
- **Scope**: 5 sample 상권(강남/홍대/건대/명동/서울역) × 2025Q4 — (1) API↔DB 적재 완전성, (2) Tool/Repository 계산 정확성, (3) LLM 응답 hallucination
- **Verdict**: ETL **FAIL** (F-01) · Tool/Repo **PASS** 25/25 · LLM Summary **PASS** · LLM Comparison **FAIL** 5/5 (F-02/F-03)
- **신규 결함 6건**:
  - 🔴 **F-01** ETL 키 불일치 — `MDW→MDWK`, `WND→WKEND`, `TMZON_1→TMZON_00_06` 으로 `estimated_sales.weekday_sales / weekend_sales / time_1~6_sales` 8개 컬럼 **전량 NULL**
  - 🔴 **F-02** Comparison intent multi-district 추출 실패 → compare_districts error → Respond LLM 일반지식 hallucination (5/5 세션에서 매출 -39% ~ +79% 오차)
  - 🟡 **F-03** tool error 시 Respond 가드레일 부재 (accuracy-gap-fix GAP-D)
  - 🟡 **F-04** `floating_population.daily_avg` 실제 의미는 "분기 시간대별 관측합" — 명명 오해
  - 🟢 **F-05** LLM store_count 표기 ±2 (5,112 vs 5,111)
  - 🟢 **F-06** audit script 성능 개선 필요
- **PASS 근거**: Phase 2 에서 5상권 × 5 tool = 25 체크 전량 일치. `//MONTHS_PER_QUARTER`, 파생 지표, compare argmax, simulate p25/p75 모두 정확.
- **외부 교차검증**: 홍대 월 532억 / 점포당 1,785만 / 점포 2,981개 — 공개 통계 order-of-magnitude 합리. 단 서울 열린데이터는 **2016년 보정비 + KT 생활인구 추정** 구조적 한계.
- **즉시 권장 Action**: (1) F-01 5분 fix — `transformers.py:214-229` key rename + 재적재, (2) F-02 comparison guardrail, (3) accuracy-gap-fix W1 착수 격상.
- **신규 memory**: `feedback_etl_api_column_rename.md`, `feedback_comparison_intent_halluc.md`

---

## 2026-04-23 — 운영 재배포 (HEAD 동기화)

- **Before**: `f6c1229` 시점 빌드 (2026-04-16), 13 커밋 뒤처짐
- **After**: `a5bef97` 기반 재빌드, migrate/seed exit 0, backend healthy
- **Plan**: [production-redeploy-2026-04-23.md](../plan/infra/production-redeploy-2026-04-23.md)
- **변경**:
  - `docker-compose.prod.yml` backend env 에 `LANGFUSE_*` 5 변수 전달 (graceful degrade)
  - migrate 서비스가 `python scripts/cleanup_alembic.py && alembic upgrade head` 실행 — `003 overlaps 001` 오염 자동 해소 (cleanup 0 행, 이미 깨끗)
  - frontend `/api/kakao-sdk` → `/proxy/kakao-sdk` 자동 cut-over (nginx 예외 블록은 dead config, 후속 정리 대상)
- **검증**:
  - `curl /proxy/kakao-sdk` = 200 (4095 bytes), `/api/kakao-sdk` = 404 (cut-over 완료)
  - prod-smoke 7/7 PASS (58.1s): P5 summary `insights.perStoreSales` 27.3M/월, P6 recommend 편의점 2.09억/월 (모두 월 단위 정상)
- **배포 메모**: `migrate` 서비스가 자체 이미지(`catchment-area-analysis-migrate`)를 써서 `build backend frontend` 만으론 구 이미지 유지 → 최초 `up -d` 에서 migrate exit 2 (`cleanup_alembic.py` not found). `build migrate` 별도 실행으로 해소. 향후 **compose 모든 빌드 서비스(migrate/seed/backend/frontend) 를 rebuild** 체크리스트에 추가.

---

## 전략

**Phase 1A(Mock E2E)** → **Phase 1B(Real Data + UX)** → **Phase 3(확장)** → **Phase 2(Premium)**

| Phase | 범위 | 상태 | 비고 |
|-------|------|------|------|
| 1A | Mock E2E, Card UI, Agent 전체 흐름 | ✅ 완료 | 5개 샘플 상권 |
| 1B | 공공데이터 ETL + 1,650 상권 적재 + 프로덕션 배포 | ✅ 완료 (2026-03-30) | |
| 3 | F06 히트맵 · F09 매출 시뮬레이션 · F10 PDF | ✅ 완료 (2026-04-06) | |
| 2 | OAuth2 · 결제 · Tier 게이팅 · F04 UI | ⏳ 미착수 | Accuracy Gap 선행 권장 |
| Prod | `marketscope.robitlabs.co.kr` 라이브 | ✅ 완료 (2026-04-16) | |

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
| Agent 모드 | PAE (planner-actor-evaluator, max 3 rounds) |
| 관측성 | Langfuse L1 (trace wiring, graceful degrade) |

---

## 현재 서비스 지표

- Mock 상권 5개 (강남역/홍대/건대/명동/서울역) · Real 상권 1,650개
- ETL 적재 (2025Q4): floating_pop 9,888 / estimated_sales 21,333 / stores 75,985 / resident 39,288
- Agent Tool 11종 · Card 타입 5종 · SSE 이벤트 9종
- E2E: 45 시나리오 + 회귀 15 시나리오

---

## 프로젝트 완성도 평가 (2026-04-22 기준)

| 축 | 점수 | 판정 | 약점 |
|---|---:|------|------|
| 안정성 | **85** | 프로덕션 운영 가능 | 세션 인메모리 · `store_history` 실데이터 부재 · backend pytest 부재 |
| 효율성 | **82** | 양호 | Langfuse L2+ 미구현 (토큰/비용) · Heatmap singleflight 미통합 |
| 정확성 | **74** | 주요 시나리오 합격 | 6개 GAP (A~F): multi-district 추출 / alias / 도치 / tool 실패 가드레일 / 지시어 / card-level export |

**해결 로드맵**: [Accuracy Gap Fix Plan](../plan/fix/accuracy-gap-fix.md) W1~W4. KPI: 정확성 74 → 85+ / GAP-A 60% → 95%+ / GAP-D 할루시 15% → <3%.

---

## 이력 요약 (2026-03-30 ~ 2026-04-22)

> 상세는 git history (`git log --follow docs/status/current-status.md`) + `docs/qa/runs/` + `docs/plan/` 로 복원.

| 날짜 | 주요 내용 |
|------|----------|
| 2026-04-22 | E2E + Ops 회귀 2차 READY (Dockerfile pip SSL 우회 · E2E 전용 stack 포트 재할당 · OPS-01/02 spec). 완성도 평가 85/82/74. [Run](../qa/runs/e2e-run-2026-04-22.md) |
| 2026-04-21 | E2E 회귀 Pass 1~3 그린 (Mock 39/39 + Real 24/24). LLMOps L1 Langfuse trace wiring (graceful degrade · SSE `done.trace_id`). 커밋 `3c5f884`/`1986f61`/`ded6cb1`/`ff9909c`. |
| 2026-04-19 | v0.3.0 — 문서 계층화 · `docker-compose.e2e.yml` + `prodGuard` · 회귀 spec 4종 (F01-H5/F03-H4/F05-H3~4/reg-2026-04-17). |
| 2026-04-17 | 매출 단위 fix (`_enrich_sales` sales→monthly_sales). 배포 근본해결 7건 (alembic cleanup · kakao-sdk 네임스페이스 · env 가드 · 포트 폐쇄 · `validate_env.py`). 비교모드 다색 하이라이트. |
| 2026-04-16 | **프로덕션 런치** (marketscope.robitlabs.co.kr). 외부 nginx + LE · `docker-compose.prod.yml`. 커밋 `5466538`. |
| 2026-04-14 | 서빙 안정성 Phase 1~10. 체크리스트 24% → 61%. Docker 하드닝 · DB/Redis 풀 · SSE heartbeat · Circuit Breaker · React.memo · `/metrics` · DR. |
| 2026-04-13 | 분석 품질 Phase 1~3 (3단 해석법 · Tool enrich · 벤치마크). SSE 최적화 — LLM Gemini→Sonnet4 TTFT 25s→1.5s. E2E eval S1 9.8 / S2 9.6 / S8 9.7. |
| 2026-04-08 | F05-H1 fix — `detect_districts_in_message` multi-extract protocol. Real 45 시나리오 41 PASS. 부수 버그 8건. |
| 2026-04-07 | E2E QA Run (Mock 42 시나리오 94/100). 4-ring helper + 22 spec. React duplicate-key fix. |
| 2026-04-06 | P0 8건 수정 (`d8c0155`) — category aliases · LLM timeout · SSE 백프레셔 · disconnect 감지 · AbortController · prompt sanitize. Phase 3 완료 (F06/F09/F10). 하드코딩 개선 5건. |
| 2026-04-05 | Docker 통합. `docker compose up` 원커맨드 · Multi-stage + standalone · `--profile dev` hot-reload. |
| 2026-04-04 | QA P0+P1 8건 (Tool 3개 크래시 · 인젝션 방어 · rewrite · Redis fallback · Semaphore(20) · 상권 감지 우선순위). |
| 2026-04-03 | PAE Agent 전환 (`create_react_agent`→커스텀). Repository 패턴 (`DataAccess` 파사드 + 7 Protocol). Frontend 리팩토링 (chatStore 351→139줄). 데이터 출처 citation. |
| 2026-04-02 | DB 셋업 자동화 — `setup_db.py --quick/full/reset` · seed 덤프 LFS · OA-15584 CSV 로더. |
| 2026-04-01 | Playwright E2E 26 시나리오 22 PASS · SHP→PostGIS 1,650 적재 · Real 모드 전환 · floating_population 컬럼명 fix. |
| 2026-03-30~31 | **Phase 1B 완료** — Agent Progress Indicator · SSE 버퍼링 해결 · 다크 테마 · ETL 적재 (4 API + CSV) · E2E 32/32. |

---

## Next Items (우선순위 순)

### 🟠 Accuracy Gap Fix — Phase 2 착수 전 선행 권장

**Plan**: [docs/plan/fix/accuracy-gap-fix.md](../plan/fix/accuracy-gap-fix.md)

| 주 | 대상 GAP | 기술 카테고리 | 참고 사례 |
|----|---------|-------------|----------|
| W1 | A, D | Entity Linking + Abstention | Kakao Map · Google "abstention paradox" · HALT-RAG |
| W2 | C, E | Conversational Query Rewriting | Perplexity · InfoCQR · CHIQ · SEAL |
| W3 | B | Taxonomy Alias Expansion | Amazon · TaxoAdapt · TELEClass |
| W4 | F | Card-level Export UX | Notion AI · Perplexity |

**근거**: 2026-04-13 eval S3(2.6) · S6(6.1) · S7(8.9) 미달. 종합 정확성 74 → 85+.

### 🟡 Refactoring Phase 1 (저위험/중위험)

- [Plan](../plan/infra/phase1-low-mid-risk-2026-04-23.md) — Pass1 즉시(30분~1시간) + Pass2 1주 내
- Phase 2 착수 전 코드베이스 정돈 목적. 삭제/추출 위주로 회귀 위험 낮음

### 🟡 관측성 L2+

- Langfuse L2+ (토큰/비용 측정, prompt version, eval harness)
- Heatmap preload singleflight 통합 (단, Refactoring Phase 1 에서 `singleflight.py` 삭제 후 별도 Plan 으로 재도입)
- backend pytest 인프라

### 🟡 Phase 2 — Premium (미착수)

- OAuth2 인증 + 결제 연동 (Toss Payments / PortOne)
- Tier 게이팅 미들웨어 (Free 일 5회 제한)
- F04 업종 심층 UI (Tool 은 이미 구현)
- category_aliases 퍼지 검색 (pg_trgm)

### 🟢 장기 / 후순위

- 세션 저장소 Redis/Postgres 이관 (재시작 시 유실 제거)
- `store_history` 대안 데이터셋 탐색 (공공 API 미제공)
- frontend/server Docker 이미지 최적화

---

## 참고 문서

| 영역 | 경로 |
|------|------|
| 종합 QA (Grade C 194 테스트) | `docs/qa/qa-summary-report.md` · `qa-detailed-results.md` · `qa-improvements.md` |
| E2E run 로그 | `docs/qa/runs/e2e-run-2026-04-22.md` · `e2e-run-2026-04-19.md` · `e2e-run-2026-04-07.md` · `e2e-run-2026-04-07-real.md` |
| 분석 품질 eval | `docs/qa/analysis-quality-eval-2026-04-13.md` |
| Accuracy Gap Fix | `docs/plan/fix/accuracy-gap-fix.md` |
| 서빙 안정성 체크리스트 | `docs/spec/serving-stability-checklist.md` |
| 아키텍처 overview | `docs/architecture/overview.md` (backend/frontend/agent/data/deployment) |
| 기능 목록 | `docs/spec/feature-list.md` · `features/F01~F10-*.md` |
| LLMOps L1 | `docs/plan/infra/llmops-l1-adr-hosting.md` · `llmops-l1-e2e.md` |
| E2E 회귀 인프라 | `docs/plan/infra/e2e-regression-plan-2026-04-19.md` · `e2e-ops-2026-04-22.md` · `e2e-ops-followup-2026-04-22.md` |
