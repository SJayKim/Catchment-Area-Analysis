# Langfuse 전체 통계 집계 — 차원 보강 + Score emit + ETL

> 단일 trace drill-down 만 보이는 현 상태에서 cohort/추세 통계까지 자동화. 기존 v3 tracer 파이프라인을 깨지 않고 누락 차원을 메우는 게 목표.

## Context

- 현재 Langfuse v3 SDK 가 dev/prod 양쪽에서 trace 발행 중 (`done.trace_id` 확인). 하지만 **trace 단위 drill-down 만 풍부**하고, cohort 분석(intent별 latency p95, 모델별 비용, 품질 회귀 추세, district_type별 에러율 등)은 사용자/관리자가 UI 에서 손으로 필터링해야 함.
- 근본 원인 3가지:
  - **차원 부족** — Planner 가 결정하는 `user_intent`, `district_code`, `referenced_districts_count`, `response_mode`, `execution_round`, `tool_count` 등이 trace metadata 에 미주입. `astream(config={metadata})` 는 init 시점만이라 Planner 결과 반영 못 함.
  - **품질 score 누락** — `numeric_sanity` evaluator 가 `quality_match_rate` 를 state 에 채우고 SSE `done` 에는 동봉하나 **Langfuse Score API 미호출**. UI 에 회귀 추세가 안 잡힘. 사용자 피드백(`user_feedback` ±1) 만 score 로 등록.
  - **ETL 부재** — Public REST API 로 데이터 끌어와 git-tracked KPI 대시보드를 만드는 스크립트가 없음. Round별 비교/월간 리포트가 수기.
- 기존 파이프라인 충돌 회피 원칙:
  - graceful degrade — Langfuse off / SDK drift / 네트워크 단절 시 영향 0 (`get_client_or_none()` None 반환 패턴 답습).
  - SSE 페이로드 변경 0 — 기존 `done.trace_id` / `done.quality_flags` 그대로 유지. ETL 은 Langfuse API 만 사용.
  - tags/metadata 재배치만 — 기존 tag 5개 (`marketscope.pae`, `provider:{x}`, `mode:{mock|real}`) 유지하면서 추가.
  - `LANGFUSE_TRACING_ENVIRONMENT` (dev/prod 분리) 는 환경변수로 이미 동작 중 — 그대로 활용.
- **Memory 참조**:
  - `feedback_langfuse_v2_langchain1_incompatible.md` — v3 API 사용 강제 (CallbackHandler / score / update_trace 모두 v3 시그니처)
  - `feedback_langfuse_sdk_drift_silent.md` — 컨테이너에 v2 잔존 시 import 실패로 silent off. ETL/score 도입 전 `validate_env.py` 의 SDK drift 가드가 통과하는지 확인 필요
  - `feedback_otlp_http_cert_override.md` — OTEL exporter session.verify monkey-patch 와 충돌 없도록 기존 `_disable_otel_tls_verify` 호출 경로 보존
  - `feedback_env_convention_inverted.md` — `.env`=prod / `.env.dev`=dev. ETL 스크립트도 동일 관례 따라 키 로드
  - `feedback_streaming_diagnose_ttft.md` — Langfuse 호출이 SSE 응답 경로에 동기 차단 못 일으키도록 score/update_trace 는 모두 best-effort + try/except silent

## Scope

- **In Scope**:
  - **Phase 1 — Trace 차원 보강** — graph 종료 시점에 `client.update_trace(trace_id, metadata=..., tags=...)` 호출하여 Planner/Actor/Evaluator 결정값을 trace 에 동봉
  - **Phase 2 — Quality Score emit** — `numeric_match_rate` / `intent_confidence` / `tool_error_rate` / `abstention_triggered` / `ambiguous_disambiguation_needed` / `card_count` 6종 score 등록. 모두 graceful degrade
  - **Phase 3 — REST API ETL 스크립트** — `scripts/observability/aggregate_langfuse.py` (Public API → DuckDB Parquet → 마크다운 리포트). 수동 `python ... --since 7d` 실행 + 월간 cron 권장 옵션
  - **Phase 4 — KPI 대시보드 git-tracked** — `docs/observability/kpi-{YYYY-MM}.md` 자동 생성기. ETL 결과 + Anthropic ↔ Langfuse 비용 갭 모니터
  - 모든 phase 의 단위 검증 + ring0 sanity (Langfuse off / mock / real 3 모드)
- **Out of Scope**:
  - Phase 4+ (Eval harness ↔ Langfuse Datasets 양방향 연동) — 별도 Plan 후보
  - Grafana Tempo / Loki dual-export — over-engineering 판단 (Phase 2 결제 트래픽 진입 시 재검토)
  - 새로운 SSE 이벤트 추가 — `done.quality_match_rate` 가 이미 충분
  - Frontend UI 변경 — observability 는 백오피스 영역
  - Langfuse Cloud Models pricing 자동 등록 — Cloud UI 작업이라 코드 범위 밖 (체크리스트로만 다룸)

## Design

### 변경 파일 목록

| 파일 | 변경 요지 | Phase |
|------|-----------|-------|
| `server/server/services/langfuse_tracer.py` | `update_trace_post_hoc(handler, *, metadata, tags)` + `emit_score(trace_id, name, value, comment?)` 2 헬퍼 추가. 둘 다 graceful degrade. | 1, 2 |
| `server/server/agent/graph.py` | `run_agent` 종료 직전(`finally` 후 `_lf_flush` 전) Planner/Actor/Evaluator 결정값을 모아 `update_trace_post_hoc` 1회 호출. respond 노드에서 capture 한 quality_match_rate 등을 `emit_score` 로 전송. | 1, 2 |
| `server/server/agent/state.py` | `tool_count` / `card_count` / `abstention_triggered` / `ambiguous_disambiguation_needed` 4 필드 추가 (Actor/Evaluator 가 채움) | 1, 2 |
| `server/server/agent/nodes/actor.py` | tool 실행 후 `tool_count` / `tool_error_count` 누적, `card_count` 누적. 기존 `tool_results`/`tool_errors` dict 에서 파생 가능하나 trace 차원으로 명시화. | 1 |
| `server/server/agent/nodes/planner.py` | clarification short-circuit 시 `abstention_triggered=True` 마킹. `ambiguous_districts` 가 비지 않으면 `ambiguous_disambiguation_needed=True`. | 2 |
| `scripts/observability/aggregate_langfuse.py` | 신규. argparse: `--since`, `--out-dir`, `--format {parquet,csv,md}`. Public REST `/api/public/traces` + `/observations` + `/scores` 페이징, DuckDB 로 cohort 쿼리. | 3 |
| `scripts/observability/__init__.py` | 빈 파일 (패키지) | 3 |
| `scripts/observability/queries.sql` | DuckDB SQL 쿼리 모음 — intent별 latency, model 별 token/cost, quality_match_rate 추세, abstention rate 추세, daily error rate. | 3 |
| `scripts/observability/render_kpi_md.py` | DuckDB Parquet → `docs/observability/kpi-{YYYY-MM}.md` 마크다운 리포트 생성기. 표 + 그래프 ASCII (sparkline) + 갭 알람. | 4 |
| `docs/observability/.gitkeep` | 디렉토리 생성 | 4 |
| `docs/observability/README.md` | 운영자 가이드 — 실행 명령, 의존성(`pip install duckdb pandas requests`), env 의존, 트러블슈팅. | 4 |
| `scripts/validate_env.py` | Langfuse Public API key 가 ETL 에 별도로 필요한 경우만 추가 가드 (현재 `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` 로 BasicAuth 가능 — 추가 키 불필요 확인 후 noop) | 3 |
| `docs/ops/runbook.md` | "Langfuse 전체 통계" 섹션 추가 — 월간 KPI 생성 절차 + Cloud Models pricing 재확인 체크리스트. | 4 |

### 차원 / Score 매핑 (누락 없음 명세)

#### Phase 1 — `update_trace_post_hoc` 가 trace 에 attach 하는 metadata 키

| 키 | 출처 | 용도 (Langfuse 필터/groupby) |
|----|------|------------------------------|
| `user_intent` | `state.user_intent` | intent 별 latency p95, success rate |
| `intent_confidence` | `state.intent_confidence` | rule vs LLM intent 분기 추세 |
| `district_code` | `state.district_code` | 핫 상권 cohort. 빈 값이면 "anonymous" |
| `district_type` | district_code → 1글자 prefix (3110/3120/3130/3140) → "발달/골목/전통/관광특구" 매핑 (lookup 테이블) | type 별 분포 |
| `referenced_districts_count` | `len(state.referenced_districts)` | 0/1/2/3+ 분포 (multi-district 사용량) |
| `referenced_category` | `state.referenced_category or "none"` | 업종별 cohort |
| `response_mode` | `state.response_mode` | greeting/clarification/direct/tool_assisted 비율 |
| `execution_round` | `state.execution_round` | planner↔evaluator 루프 회수 분포 |
| `tool_count` | `state.tool_count` | tool 사용량 |
| `tool_error_count` | `len(state.tool_errors)` | error 회수 |
| `card_count` | `state.card_count` | card 발행 회수 |
| `plan_size` | `len(state.plan)` | Planner 가 만든 step 수 |
| `quality_match_rate` | `state.quality_match_rate` | numeric_sanity 합치율 (이미 SSE done 에 포함) |
| `quality_flag_severity_max` | `state.quality_flags` 중 severity 최댓값 | warning/error/info 추세 |

#### Phase 1 — 추가 tags (필터 1급 키)

| tag | 용도 |
|-----|------|
| `intent:{x}` | Langfuse Sessions 뷰에서 intent 필터 |
| `district_type:{x}` | type 별 빠른 cohort |
| `mode:tool_assisted` / `mode:greeting` / `mode:clarification` / `mode:direct` | response_mode 빠른 분기 |
| `quality:warning` 또는 `quality:ok` | quality_flags 존재 여부 (없으면 ok) |

> 기존 tag (`marketscope.pae`, `provider:{x}`, `mode:{mock|real}`) 는 그대로 유지 — `mode:{mock|real}` 와 `mode:tool_assisted` 가 prefix 충돌 안 하는지 검증 필요. 충돌하면 `runtime:{mock|real}` 로 rename.

#### Phase 2 — emit 할 Score 6종

| name | value 타입 | 산출 | Langfuse 활용 |
|------|------------|------|---------------|
| `numeric_match` | float [0.0, 1.0] | `state.quality_match_rate` | 회귀 추세 (`numeric_sanity` evaluator), 이상치 알람 |
| `intent_confidence` | float [0.0, 1.0] | `state.intent_confidence` | rule vs LLM 신뢰도 분포 |
| `tool_error_rate` | float [0.0, 1.0] | `len(tool_errors) / max(tool_count, 1)` | error rate 추세 |
| `abstention_triggered` | float (0 / 1) | clarification short-circuit 발생 시 1 | abstention KPI |
| `ambiguous_disambiguation_needed` | float (0 / 1) | `state.ambiguous_districts` 비어있지 않으면 1 | 모호 쿼리 비율 |
| `quality_severity` | float (0/1/2) | flags 중 max severity (`info`=0, `warning`=1, `error`=2) | 심각도 cohort |

> `user_feedback` (±1) 은 이미 `feedback.py:71` 에서 등록 중. 본 plan 의 6종과 합쳐 총 **7종 score** 가 trace 에 붙음.

#### Phase 3 — ETL 스크립트 데이터 모델

```
DuckDB tables (Parquet roundtrip):
  traces     — id, timestamp, session_hash, user_intent, district_code,
                district_type, response_mode, execution_round, tool_count,
                tool_error_count, card_count, latency_ms, total_tokens,
                input_tokens, output_tokens, total_cost_usd
  observations — trace_id, name (model name), start_time, end_time,
                  input_tokens, output_tokens, total_cost_usd, model
  scores     — trace_id, name, value, timestamp, comment
```

ETL 흐름:
```
Public REST API
  ├─ GET /api/public/traces?fromTimestamp=...&page=...   (BasicAuth: pk:sk)
  ├─ GET /api/public/observations?traceId=...
  └─ GET /api/public/scores?traceId=...
      ↓
  DuckDB COPY → parquet (date partitioned)
      ↓
  queries.sql 실행 → pandas DataFrame
      ↓
  render_kpi_md.py → docs/observability/kpi-2026-04.md
```

#### Phase 4 — KPI 마크다운 리포트 섹션 (자동 생성 항목)

1. **헤더** — 기간 / 환경 (dev|prod) / trace 총 수
2. **Intent 분포** — intent × count × p50/p95 latency 표
3. **Model 비용** — model × tokens (in/out) × cost USD 표
4. **Quality KPI** — `numeric_match` 평균 + 추세 sparkline (지난 30일)
5. **Error 추세** — `tool_error_rate` 평균 + 90% percentile
6. **Abstention / Disambiguation** — % triggered (모호 쿼리 비율)
7. **User feedback** — 👍/👎 비율
8. **Cost 갭 모니터** — Anthropic Console 입력값(수기 입력 필드) ↔ Langfuse 합산 비용 비교. 갭 > 10% 시 ⚠ 표시 (Cloud Models pricing 미등록 의심)

### 의존성 / 선행 Plan

- 선행 완료: `langfuse-cost-coverage-fix-2026-04-24.md` (SDK v3 drift fix), `llmops-l1-verification.md` (trace_id 발행), `prod-deploy-v0.4.0-2026-04-23.md` (`LANGFUSE_TRACING_ENVIRONMENT` env)
- 외부 의존성:
  - `duckdb` (>=1.0), `pandas` (>=2.2), `requests` — `pyproject.toml` 의 `[project.optional-dependencies] observability` 그룹에 추가 (운영 머신만 설치)
- Langfuse Cloud 사용자 작업 (코드 변경 외):
  - Settings → Models 에서 `claude-sonnet-4-20250514`, `gemini-2.5-pro`, `gemini-2.5-flash` pricing 등록 확인 (status 2026-04-24 메모 재확인). 미등록 시 `cost_usd` 가 0 으로 떨어져 ETL 갭 모니터 알람 발생

## Checklist

### Phase 1 — Trace 차원 보강

- [ ] **P1-1** `state.py` 에 `tool_count: int`, `card_count: int`, `abstention_triggered: bool`, `ambiguous_disambiguation_needed: bool` 4 필드 추가 + 기본값 설정
- [ ] **P1-2** `actor.py` 에서 tool 실행 1건당 `tool_count` 증가, error 시 그대로 `tool_errors` dict push (기존). card 방출 시 `card_count` 증가
- [ ] **P1-3** `planner.py` 의 clarification short-circuit 분기 (3가지: coref-no-anchor / comparison-under-2 / exclusion-left-empty) 모두 `abstention_triggered=True` 세팅. ambiguous_districts non-empty 면 `ambiguous_disambiguation_needed=True`
- [ ] **P1-4** `langfuse_tracer.py::update_trace_post_hoc(handler, *, metadata, tags)` 신규. 내부에서 `_get_client()` + `client.update_trace(trace_id, metadata=..., tags=...)` 호출. 핸들러 None / client None / 예외 시 silent return
- [ ] **P1-5** `langfuse_tracer.py::_district_type(code)` 헬퍼 — district_code 4자리 prefix → 발달/골목/전통/관광특구 매핑. unknown 은 "unknown" 반환
- [ ] **P1-6** `graph.py::run_agent` 의 `finally` 블록에서 `_lf_flush(lf_handler)` 직전에 `update_trace_post_hoc` 1회 호출. final state 의 모든 차원을 metadata 로, intent/district_type/quality 4 tag 를 추가
- [ ] **P1-7** 기존 `mode:{mock|real}` tag 충돌 검증 — 충돌 시 `runtime:{mock|real}` 로 rename + 본 plan 의 신규 tag 는 `flow:{tool_assisted|...}` prefix 사용
- [ ] **P1-8** dev 컨테이너에서 `curl /api/chat` 1회 실행 후 Langfuse UI 에서 trace 의 metadata 에 신규 11 키 + tags 4종 모두 보이는지 수동 확인 (스크린샷 첨부)

### Phase 2 — Quality Score emit

- [ ] **P2-1** `langfuse_tracer.py::emit_score(trace_id, name, value, *, comment=None)` 신규. `client.score(trace_id=..., name=..., value=..., comment=...)` + best-effort flush. 예외 silent
- [ ] **P2-2** `graph.py::run_agent` 의 finally 블록 (P1-6 직후) 에서 6종 score 일괄 emit. trace_id None 이면 skip
- [ ] **P2-3** numeric_match 는 `final_quality_match_rate` 가 None 이 아닐 때만 emit (greeting/clarification 분기에서는 미발행)
- [ ] **P2-4** `quality_severity` 산출 로직 — `final_quality_flags` 의 severity 문자열 → 0/1/2 매핑 dict
- [ ] **P2-5** `tool_error_rate` 0/0 회피 — `tool_count == 0` 이면 score 미발행 (greeting 분기 등)
- [ ] **P2-6** dev 에서 score emit 후 Langfuse UI Scores 탭에서 신규 6종 + 기존 `user_feedback` = 총 7종이 보이는지 확인

### Phase 3 — REST API ETL 스크립트

- [ ] **P3-1** `pyproject.toml` `[project.optional-dependencies].observability = ["duckdb>=1.0", "pandas>=2.2", "requests>=2.31"]` 추가
- [ ] **P3-2** `scripts/observability/__init__.py` (빈 파일)
- [ ] **P3-3** `scripts/observability/aggregate_langfuse.py` 신규
  - argparse: `--since {7d|30d|YYYY-MM-DD}`, `--out-dir docs/observability/data`, `--env {dev|prod}`
  - `.env` / `.env.dev` 자동 선택 (config.py 와 동일 관례)
  - BasicAuth (public_key, secret_key) 로 `https://cloud.langfuse.com/api/public/*` 호출
  - rate-limit (Cloud free tier 100 req/min) 회피 — 페이지 100건 단위 + sleep 0.6s
  - DuckDB 로 traces / observations / scores 3 테이블 만들고 parquet 로 export
- [ ] **P3-4** `scripts/observability/queries.sql` — 8개 쿼리 (intent latency, model cost, quality 추세, error rate, abstention rate, district_type 분포, daily volume, env split)
- [ ] **P3-5** `--dry-run` 모드 — 첫 페이지만 fetch, 출력 schema 만 검증
- [ ] **P3-6** dev 환경에서 `python scripts/observability/aggregate_langfuse.py --since 1d --env dev --dry-run` 동작 확인

### Phase 4 — KPI 마크다운 자동 생성

- [ ] **P4-1** `scripts/observability/render_kpi_md.py` 신규 — Parquet 읽고 마크다운 표 8섹션 + sparkline (`▁▂▃▄▅▆▇█` 8단계) 생성
- [ ] **P4-2** Cost gap 모니터 — Anthropic Console 입력은 `--anthropic-cost-usd 12.34` 옵션으로 받음. Langfuse 합산 대비 갭 > 10% 시 ⚠
- [ ] **P4-3** `docs/observability/README.md` 신규 — 실행 명령, 의존성, 트러블슈팅. Langfuse Cloud Models pricing 등록 체크리스트
- [ ] **P4-4** `docs/observability/kpi-2026-04.md` 첫 샘플 생성 (수동 실행)
- [ ] **P4-5** `docs/ops/runbook.md` "월간 통계 생성" 섹션 추가 (3 step)

### 위생 작업

- [ ] **H-1** `docs/status/current-status.md` 에 Plan 링크 + 다음 P0 갱신
- [ ] **H-2** `MEMORY.md` 새 feedback 추가 — `feedback_langfuse_update_trace_post_hoc.md` (init metadata 만으로는 Planner 차원 못 잡으니 finally 에서 update_trace 필수)

## 재검토 (Self-Review Gate)

### 엣지 케이스

- **trace_id 가 None 인 분기 전수 점검**
  - Langfuse off (`langfuse_enabled=False`) → handler None → `update_trace_post_hoc` 도 None 가드
  - 샘플링 탈락 → handler None → 동일
  - graph 도중 예외 → finally 에서 trace_id 는 살아 있으나 state 가 partial. metadata 에 None 키가 섞이면 Langfuse UI 가 boolean false 처리 — `None` 인 키는 dict 에서 제거 후 update
- **greeting / clarification 분기**
  - tool_count=0, plan_size=0, quality_match_rate None — 일부 score skip 필요 (P2-3, P2-5)
  - response_mode tag 는 항상 emit (`greeting_direct` / `clarification_direct` 도 cohort)
- **multi-round (planner ↔ evaluator)**
  - `execution_round` 가 마지막 값으로 덮어씌워짐 — 의도된 동작 (라운드 횟수 = 마지막 값). `tool_count` 도 누적.
- **astream 도중 client disconnect**
  - `chat.py:300` 에서 `request.is_disconnected()` early return. graph task 는 cancel — finally 의 `update_trace_post_hoc` 호출 가능 여부 확인 필요. 안전하게 `try/except` 한 번 더 wrap.
- **score value 범위 일탈**
  - `quality_match_rate` 가 1.0 초과 / 0 이하 가능성? `numeric_sanity.py` 가 [0,1] 보장하는지 확인
- **Langfuse update_trace 가 v3 에서 deprecated 되었는지**
  - SDK v3 docs 확인 필요. 대체로 `client.update_current_trace()` (context 기반) 와 `client.api.trace.update(trace_id=..., body=...)` (REST wrapper) 둘 중 하나. 후자가 graph 종료 후 context 빠진 시점에도 안전.
- **Langfuse Cloud rate limit (100 req/min)**
  - ETL 에서만 영향. Plan 내 P3-3 의 sleep 0.6s 로 대응.
- **OTEL TLS verify monkey-patch 와 update_trace HTTPS 호출 충돌**
  - `update_trace` 는 OTEL exporter 가 아니라 HTTP API 직호출. `_disable_otel_tls_verify` 와 무관. 다만 사내 MITM 환경에서는 별도 SSL 우회 필요할 수 있어 `_get_client()` 시점 verify 동작 확인.

### Memory 교훈 반영

- ✅ `feedback_langfuse_v2_langchain1_incompatible` — v3 API (`client.score`, `client.api.trace.update`) 만 사용
- ✅ `feedback_langfuse_sdk_drift_silent` — `validate_env.py` 의 `find_spec("langfuse.langchain")` 가드가 통과한 환경에서만 ETL 실행 (사전 체크)
- ✅ `feedback_otlp_http_cert_override` — OTEL exporter 와 별도 경로라 영향 없음을 명시
- ✅ `feedback_env_convention_inverted` — ETL 스크립트도 `.env.dev` 우선 로드 (config.py 동일 관례)
- ✅ `feedback_streaming_diagnose_ttft` — finally 블록의 `update_trace` / `emit_score` 호출이 SSE 응답에 차단 일으키지 않도록 graph task 종료 후로 시점 잡음
- ✅ `feedback_stale_container_vs_source` — Phase 1+2 배포 후 `docker exec ... grep update_trace_post_hoc` 로 컨테이너 내부 source 반영 확인 단계 추가

### 타 Plan / 기존 코드 충돌

- ⚠️ `feedback.py:71` 의 `client.score(trace_id=..., name="user_feedback", value=±1)` 와 Phase 2 의 `emit_score` 는 **동일 v3 시그니처**. 헬퍼 만들면 `feedback.py` 도 마이그레이션 검토 (선택 — 기능 동등이라 미수정 시 영향 0)
- ⚠️ `langfuse-cost-coverage-fix-2026-04-24.md` 의 `validate_env.py` SDK drift 가드는 그대로 유지. ETL 스크립트도 진입 시 동일 가드 사용 권장
- ⚠️ `e2e-quality-improvement-2026-04-24.md` 의 sweep harness 가 `/api/chat` 호출 → trace 발행. Phase 1 적용 후 sweep 실행 시 Langfuse trace volume 이 1회 실행 = 100+ traces. dev workspace 무료 tier (50k obs/월) 빠르게 소진 가능 → `langfuse_sampling_rate=0.1` 적용 가이드 runbook 에 추가
- ✅ `chat.py:308-317` 의 `agent_done` 로그 포맷 그대로 유지 — Phase 1 의 trace 차원 보강과 무관

## Scenario (E2E Ring Mapping)

- **Ring**: 0 (infra) — 새 SSE 이벤트/카드/페이지 추가 없음. backend lifecycle + Langfuse off/on 분기만 검증
- **Scenario ID**:
  - `0-LF-AGG-01-dimensions` — `/api/chat` 1 회 → Langfuse UI trace metadata 에 11 키 + tags 4종
  - `0-LF-AGG-02-scores` — 동일 trace 의 Scores 탭에 6 종 + user_feedback (총 7종)
  - `0-LF-AGG-03-greeting-skip` — "안녕하세요" 인사 → greeting_direct, score 일부 skip 확인 (numeric_match, tool_error_rate 미발행)
  - `0-LF-AGG-04-clarification-abstention` — 모호 쿼리 ("거기는?") → abstention_triggered=1, response_mode=clarification_direct
  - `0-LF-AGG-05-langfuse-off` — `LANGFUSE_PUBLIC_KEY=""` 로 재기동 후 chat → 5xx 0건, agent_done log trace_id=- 정상
  - `0-LF-AGG-06-etl-dryrun` — `aggregate_langfuse.py --since 1d --dry-run` exit 0 + schema dump
  - `0-LF-AGG-07-kpi-render` — `render_kpi_md.py` 실행 → `kpi-2026-04.md` 생성, 8 섹션 채워짐
- **사전조건**:
  - dev: `.env.dev` 에 LANGFUSE_PUBLIC_KEY/SECRET_KEY 유효, `validate_env.py` SDK drift 가드 통과
  - 실 1,650 상권 ETL 적재 상태
- **실행 단계**:
  1. backend 재시작 (Phase 1+2 적용 코드 반영)
  2. `curl -N /api/chat` 4 종 (intent별 summary/comparison/clarification/greeting)
  3. Langfuse UI 에서 traces 4건 확인 (metadata 11 키, tags 4종, scores 7종)
  4. `LANGFUSE_PUBLIC_KEY=""` 로 환경변수 unset 후 backend 재시작 → curl 1회 → 정상 응답 + agent_done trace_id=-
  5. ETL dry-run + KPI render
- **기대 결과**:
  - Langfuse UI 에서 intent 별 latency p95 cohort 차트가 곧바로 그려짐
  - Scores 탭에 numeric_match 시계열 분포 확인 가능
  - `kpi-2026-04.md` 가 git diff 에 새 파일로 출력
  - off 모드에서 `/api/chat` 5xx / SSE 끊김 0건

## Pass 반복 (Iteration Plan)

### Pass 1 — 기본 구현

1. Phase 1 (P1-1 ~ P1-8): state 필드 추가 + actor/planner 마킹 + tracer 헬퍼 + graph 통합
2. ruff/mypy/pytest 회귀: `server/tests/test_*.py` 22 + 신규 1 (test_update_trace_post_hoc) → 23/23 PASS
3. Scenario 0-LF-AGG-01, 03, 05 수동 검증

### Pass 2 — 엣지 케이스 + Score

1. Phase 2 (P2-1 ~ P2-6): 6종 score emit + 분기별 skip
2. Edge:
   - astream 예외 분기에서도 update_trace 호출되는지 확인 (try/except wrap)
   - clarification/greeting 시 score 일부 skip
   - quality_match_rate=None 분기
3. Scenario 0-LF-AGG-02, 04 수동 검증
4. dev 1일 운영 후 Langfuse UI 에서 신규 차원 분포 sanity check (intent 분포, abstention rate, district_type 분포)

### Pass 3 — ETL + KPI 자동화

1. Phase 3+4 (P3-1 ~ P4-5): ETL 스크립트 + KPI 마크다운
2. dev 환경 1주일치 데이터 (`--since 7d`) 로 first run → kpi-2026-04.md 생성
3. Cloud Models pricing 미등록 시 cost gap 알람 발동 확인
4. Scenario 0-LF-AGG-06, 07 수동 검증
5. runbook 섹션 + status 갱신

### Pass 4 (조건부) — 회귀 / 성능

1. e2e-quality-sweep 1회 실행 후 Langfuse trace 100+ 발행 확인 (sampling 0.1 토글 검증)
2. Phase 1 의 `update_trace_post_hoc` 호출이 SSE 응답 latency p95 에 미치는 영향 측정 (목표: < 50ms 추가)
3. ETL 페이지네이션 rate-limit 한도 내 정상 종료 확인 (1주일치 trace 약 1k 건 가정 → 10 페이지 × 0.6s = 6s)

## Agent 모델 선택

- **설계 (Plan 작성, 본 문서)**: opus — Langfuse v3 API 시그니처 / state 차원 매핑 / ETL 데이터 모델 설계가 다층 추론 필요
- **구현 (Phase 1+2 코드)**: sonnet — 헬퍼 함수 + state 필드 추가 + finally 통합. 명확한 스펙
- **구현 (Phase 3+4 ETL)**: sonnet — 스크립트 작성, REST API 페이징 패턴 답습
- **검증 (수동 sanity + Pass 판정)**: haiku — Langfuse UI 스크린샷 비교, KPI 표 정합성 체크

## Validation

### 자동 검증

- `pytest server/tests/test_langfuse_tracer.py` (신규) — `update_trace_post_hoc` / `emit_score` graceful degrade 4 케이스
- `pytest server/tests/test_state_dimensions.py` (신규) — state 필드 default 값 + planner/actor 마킹
- ruff `server/` All passed
- `npm run typecheck` (frontend 무영향 — 회귀 가드)
- `playwright e2e ring0-preflight/00-stack-up.spec.ts` 그린

### 수동 검증

1. **Phase 1 sanity** — dev backend 재시작 → `curl -N /api/chat -d '{"message":"강남역 분석", ...}'` → Langfuse UI Traces → 최신 trace 클릭 → metadata 패널에 11 키 다 있음 + tags 에 `intent:summary`, `district_type:발달`, `flow:tool_assisted`, `quality:ok` 4종 있음
2. **Phase 2 score** — 동일 trace → Scores 탭 → 6종 score (numeric_match=1.0, intent_confidence=0.85, tool_error_rate=0.0, abstention_triggered=0, ambiguous_disambiguation_needed=0, quality_severity=0)
3. **Phase 3 ETL** — `python scripts/observability/aggregate_langfuse.py --since 1d --env dev --dry-run` exit 0 + schema dump
4. **Phase 4 KPI** — `python scripts/observability/render_kpi_md.py --month 2026-04 --env dev` → `docs/observability/kpi-2026-04-dev.md` 생성, 8 섹션 채워짐
5. **graceful degrade** — `LANGFUSE_PUBLIC_KEY=""` env 로 backend 재기동 → `curl /api/chat` 5xx 0건, log `agent_done ... trace_id=-`
6. **prod-smoke 회귀** — `npm test --grep prod-smoke` 28/28 PASS (P8/P9 baked-URL 가드 포함)

### KPI 검증 (Plan 효과)

- ✅ Langfuse UI 에서 intent × latency 차트가 1 click 으로 그려짐 (이전: 수기 필터)
- ✅ `numeric_match` score 의 7일 평균 추세선이 보임 (이전: trace 단건만)
- ✅ git-tracked `docs/observability/kpi-{YYYY-MM}.md` 가 월간 KPI 스냅샷으로 누적
- ✅ Anthropic 비용 ↔ Langfuse 비용 갭이 < 10% (Cloud Models pricing 정상 등록 시)
- ✅ ETL 1회 < 30s (1주일치 dev trace 약 1k 건 기준)

## Metadata

- 작성일: 2026-04-28
- 작성자: Claude Code (plan-new skill, opus)
- 카테고리: infra
- 선행 Plan:
  - `docs/plan/infra/llmops-l1-verification.md` (trace_id 발행 검증 완료)
  - `docs/plan/infra/langfuse-cost-coverage-fix-2026-04-24.md` (SDK v3 drift fix)
  - `docs/plan/infra/prod-deploy-v0.4.0-2026-04-23.md` (`LANGFUSE_TRACING_ENVIRONMENT` env 배선)
- 후속 Plan 후보:
  - Eval harness ↔ Langfuse Datasets 양방향 연동 (Round별 cohort 비교)
  - Self-host Langfuse 마이그레이션 (Cloud free tier 50k obs/월 한계 도달 시)
- 영향 범위: 백엔드 (graph/tracer/state/actor/planner 5 파일) + 신규 스크립트 디렉토리 (`scripts/observability/`) + 신규 문서 디렉토리 (`docs/observability/`). Frontend / DB schema 무변경. SSE 페이로드 무변경.
