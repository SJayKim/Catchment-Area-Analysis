# Langfuse Ops Hardening — v2 L2 wiring + 무음사망 가시화 + eval 관측 opt-in

> 작성: 2026-07-06 · 선행: [langfuse-l2-token-cost-eval.md](langfuse-l2-token-cost-eval.md) (L2 Foundation) · [langfuse-aggregate-stats-2026-04-28.md](../_archive/langfuse-aggregate-stats-2026-04-28.md) (PAE 11차원/6스코어)

## Context

Langfuse 감사(2026-07-06 세션)에서 확인된 사실: **v2 agentic loop(현행 prod 기본 경로)는 CallbackHandler만 주입하고 그 외 wiring이 전무하다.** 그 결과:

- **P1 — 관측 깊이 후퇴**: prod 트레이스가 "ChatAnthropic" 이름으로 session/metadata/tags/summary/score/tool-span 없이 쌓임. PAE 는 11차원 metadata + 6 score 를 동봉하는데 v2 는 0종.
- **P2 — 무음 사망 미감지**: `_tracer_valid=False` 로 tracing 이 조용히 꺼져도 어떤 지표에도 드러나지 않음 (`agent_done trace_id=-` 로그가 유일한 흔적).
- **P3 — eval/e2e 트래픽 완전 미관측**: `docker-compose.e2e.yml` 이 Langfuse 키를 하드코딩 `""` 로 고정 — eval LLM 지출이 어디에도 안 잡힘.
- **P4 — 잠재 결함**: ① `Langfuse(sample_rate=...)` + `should_sample()` **이중 샘플링** — done 이벤트에 trace_id 를 동봉했는데 SDK 가 trace 를 드랍하는 고아 발생 가능 ② 동기 `flush()` 가 SSE 응답 경로 블로킹 ③ prod `.env` 의 `LANGFUSE_TRACING_ENVIRONMENT=development` 오기 + salt 미설정(재시작 시 세션 해시 분절).

**사용자 결정**: ① eval 관측 = compose **opt-in 파라미터화**(`${E2E_LANGFUSE_*:-}`, 기본 off 유지 — e2e 계약 보존, eval 세션만 dev 프로젝트 키 + `environment=e2e` 로 export) ② 실행 범위 = Plan 문서 + **Pass 1 구현까지** (e2e 회귀·live smoke 는 Pass 2/3).

**Memory 참조**: `feedback_langfuse_sdk_drift_silent`(무음사망 — 모든 LLM 호출이 과금되는데 Langfuse 0건, `agent_done trace_id=-` 로만 드러남 → Workstream B 의 직접 근거) · `feedback_langfuse_v3_no_update_trace`(update_trace 부재 — 0-duration `start_observation` 우회 패턴 답습) · `feedback_env_convention_inverted`(`.env`=prod / `.env.dev`=로컬 — D 의 파일별 값 결정 근거) · `feedback_compose_env_block_overrides_env_file`(compose environment 블록이 호스트 셸을 읽음 — `${E2E_LANGFUSE_*:-}` 는 의도된 활용) · `feedback_langfuse_otel_insecure_partial`(OTEL insecure 는 score/observation REST 미적용 — prod 복사 금지 주석 근거) · `project_e2e_port_convention`(dev 8000 / e2e 8002).

## Scope

- **In**: v2 engine L2 wiring(A) · tracer 신규 helper + tag 동적화(A2) · health/metrics 무음사망 가시화(B) · 이중 샘플링 제거 + flush offload(C) · compose/env 파일(D) · 신규 pytest 4파일 18건(E) · 문서 sync
- **Out**: PAE 노드 내부 wiring(planner/evaluator/respond generation span — L2 Plan Pass 2 잔여), L2-C eval harness, score-config 콘솔 등록(런북 문서화만), per-request CircuitBreaker DI, e2e 회귀 실행(Pass 2) · live smoke(Pass 3)

## Design

| 결정 | 내용 | 근거 |
|---|---|---|
| lf_kwargs 조건부 전달 | engine 이 `metadata/tags/run_name` 을 **handler 존재 시에만** LLM 호출 kwargs 로 전달 (`**lf_kwargs`, None 이면 빈 dict) | `test_engine_stream_events.py` fake 5건이 구 시그니처 — 무조건 전달 시 TypeError. handler None 이면 기존 호출과 바이트 동일 |
| models.py 시그니처 | `ainvoke/astream_with_fallback` 에 keyword-only `metadata/tags/run_name` 추가, 값 있을 때만 config 키 세팅 | graph.py `astream_config` 검증된 패턴 이식. config 는 클라이언트측 전용 — Anthropic request body 불변(prompt-cache 무영향) |
| summary name | `attach_summary_observation(name=...)` 파라미터화, **default `marketscope.pae.summary` 유지** | `test_langfuse_aggregate.py:64` 가 default 이름 assert, graph.py 호출부 무변경 |
| tool span | 신규 `attach_tool_span` — `as_type="tool"` 0-duration span, **tool 결과 본문 미탑재** | fact_pool untruncated 원본은 ToolMessage 에 이미 존재 — 중복 탑재는 페이로드 낭비 |
| tag 동적화 | `build_langchain_tags()` 하드코딩 `marketscope.pae` → `f"marketscope.{effective_loop_version()}"` | mock/PAE 경로에서는 기존값 그대로 (e2e 계약 무변경) |
| Trust 계측 | `find_unbound_numbers` → `binding_stats` 치환(동일 unmatched 반환 — behavior-preserving) + 이중 계산 제거, `trust_*` 플래그 축적 | 코드 경로 동일, 계측만 추가. F401 import 정리 |
| score 6종 (v2) | `numeric_match`((scored−unbound)/scored, scored>0) · `tool_error_rate`(calls>0) · `abstention_triggered`(항상) · `trust_corrective_applied` · `trust_fallback_triggered` · `trust_masked_count` | 앞 3종은 PAE 와 이름 공유(의미 동일), loop 구분은 tag/`agent_mode` metadata |
| 샘플링 단일 게이트 | `Langfuse(sample_rate=...)` kwarg 삭제 — `should_sample()` 만 유지 | 이중 샘플링 = done trace_id 고아. handler 생성 자체를 막는 게이트가 상류 |
| flush offload | `_lf_flush` → `await asyncio.to_thread(...)` (engine + graph 양쪽) | 동기 flush 의 SSE 블로킹 제거. async generator finally 내 await 합법, CancelledError 는 미포착(abort 의미론 보존) |
| 무음사망 가시화 | health detail `langfuse` 블록 + `/metrics` `langfuse_trace_missing_total` + agent_done 직후 카운터 | enabled 인데 trace_id 없음 = 무음사망 시그널. e2e 는 keys off → enabled=False → 오염 없음 |
| eval 관측 | compose `${E2E_LANGFUSE_*:-}` 기본 empty | L1-E01/E06 (trace_id null 계약) 보존, eval 때만 export opt-in |

**v2 summary metadata (~19키)**: district_code(`or "anonymous"`) / district_type(`district_type_for`) / district_name / resolved_name / data_quarter / iterations_used / tool_calls_made / tool_error_count / card_count / called_tools(sorted) / wall_clock_s / budget_exhausted / abstention_triggered / trust_unbound_final / trust_scale_error_count / trust_corrective_applied / trust_fallback_triggered / trust_masked_count / numeric_match_rate

## Checklist

- [x] C1 `langfuse_tracer.py`: `sample_rate` kwarg 삭제(주석 근거) · `build_langchain_tags` 동적화 · `attach_summary_observation(name=)` · 신규 `attach_tool_span` · 신규 `status()`
- [x] C2 `models.py`: `ainvoke/astream_with_fallback` keyword-only `metadata/tags/run_name` + config 관통
- [x] C3 `engine.py`: lf_kwargs 조건부 전달(3 call site) · tool loop duration+error 계측+span · Trust 블록 `binding_stats` 치환+플래그 · finalize summary(19키)+score 6종 · flush offload · `iteration=-1` 사전 초기화
- [x] C4 `graph.py`: flush offload 1블록 / `chat.py`: health detail `langfuse` 블록 + trace_missing 카운터 hook / `metrics.py`: 카운터+getter+JSON 키
- [x] C5 compose/env: `docker-compose.e2e.yml` `${E2E_LANGFUSE_*:-}` ✅ · `.env.example` 주석 교정 ✅ · ⚠ `.env`(environment=production+salt+OTEL 주석)/`.env.dev`(salt) 는 `protect_secrets.py` PreToolUse 훅이 차단 — **수동 적용 필요** (아래 §수동 적용 diff)
- [x] C6 신규 테스트 4파일: `test_loop_models_config.py`(3) · `test_langfuse_ops.py`(7) · `test_v2_loop_langfuse.py`(5) · `test_metrics_langfuse.py`(3)
- [x] V1 `ruff check .` + `ruff format --check .`(151 files) + `pytest -m "not real"` — **225 passed / 6 deselected(@real), 수집 231** (structlog·slowapi 로컬 env 드리프트 복구로 app_client 스킵 0)
- [x] V2 기존 계약 회귀: `test_langfuse_aggregate`(10) · `test_langfuse_l2`(12) · `test_engine_stream_events`(5) · `test_v2_loop_qa_regressions`(12) 전건 green (전체 스위트에 포함 실행)
- [x] C7 문서 sync: `agent.md` §9 · `backend.md` §4/§8 · `deployment.md` §3/§7 · `ops/runbook.md`(무음사망 3단 진단 + 샘플링 단일 게이트 + score-config 절차) · `status/current-status.md`

### 수동 적용 diff (.env / .env.dev — 훅 보호로 자동 수정 불가)

```diff
# .env (prod 프로파일)
-LANGFUSE_TRACING_ENVIRONMENT=development
+LANGFUSE_TRACING_ENVIRONMENT=production
+# 세션 해시 salt — 고정값이어야 재시작 후에도 같은 세션이 같은 해시로 묶임
+LANGFUSE_SESSION_SALT=b229b91fc5d3575e4488c272eb9ed09a
 # Corporate/ISP MITM — OTEL HTTPS verify skip (dev only)
+# ⚠ 프로덕션 서버로 이 줄 복사 금지 — TLS 검증이 꺼진 채 운영된다
 LANGFUSE_OTEL_INSECURE=true

# .env.dev (로컬)
 LANGFUSE_TRACING_ENVIRONMENT=development
+LANGFUSE_SESSION_SALT=f967fecff0191c5d935e23642c47d131
```

## 재검토 (Self-Review Gate)

- [x] 엣지: `test_engine_stream_events` fake 구 시그니처 → lf_kwargs 조건부 (테스트 env 는 conftest keys="" → handler 항상 None → 빈 kwargs)
- [x] 엣지: `test_langfuse_aggregate.py:64` summary name assert → `name=` default 유지
- [x] 엣지: e2e L1-E01/E06 trace_id null 계약 → compose 기본값 empty 유지
- [x] 엣지: to_thread flush 중 CancelledError → `except Exception` 미포착으로 전파(abort 의미론), 스레드는 완주 + lifespan `shutdown()` 백스톱
- [x] 엣지: `iteration` 미정의 NameError (max_iterations=0 또는 루프 전 예외) → `-1` 사전 초기화
- [x] Memory: `feedback_langfuse_sdk_drift_silent`(B 전체 근거) · `feedback_env_convention_inverted`(.env=prod) · `feedback_compose_env_block_overrides_env_file`(호스트 export 활용) · `feedback_langfuse_otel_insecure_partial`(prod 복사 금지) 반영
- [x] 충돌: [v2-stream-final-option-b](v2-stream-final-option-b-2026-07-06.md) 산출물(astream 버퍼링) 위에 kwargs 만 추가 — 스트리밍 분기/Trust 게이트 의미론 무접촉. PAE 변경은 flush 1블록뿐
- [x] prompt-cache: metadata/tags/run_name 은 LangChain config(클라이언트측) — Anthropic request body 불변
- [x] 이중 샘플링 제거 부작용: rate<1.0 에서 이전엔 (rate²) 로 과소 수집 — 제거 후 의도대로 rate¹. done trace_id 고아 소멸

## Scenario (E2E Ring Mapping)

| ID | Ring | 내용 | 기대 |
|---|---|---|---|
| `R0-LF-AGG` | Ring 0 (stats-aggregate) | 기존 Langfuse 11차원/6score 회귀 재실행 (mock/PAE 경로) | 기존 assert 전건 green — tag `marketscope.pae` (effective=pae) · summary name default 불변 |
| `R3-LF-L1` | Ring 3 (l1-langfuse) | keys off 기본 스택에서 trace_id null 계약 | L1-E01/E06 green — done 에 trace_id 없음 유지 |
| `R1-LF-V2SMOKE` | Ring 1 | dev 키 + live LLM 기동 → SSE done trace_id → langfuse-cli 로 trace 조회 | trace name=`marketscope.v2` · tags · session · tool span ≥1 · summary(19키) · score 6종 · health detail `langfuse.enabled=true` |
| `R1-LF-EVALOPT` | Ring 1 | `E2E_LANGFUSE_*` export 후 e2e 스택 재기동 → SSE 1건 | e2e 트래픽이 dev 프로젝트 `environment=e2e` 로 수집 |

> Pass 1 은 pytest 단위/통합 18건으로 커버. Ring 시나리오는 Pass 2/3 범위.

## Pass 반복

- **Pass 1 (기본 — 이번 실행 범위)**: C1~C7 + V1/V2 green
- **Pass 2 (엣지/회귀)**: `R0-LF-AGG` + `R3-LF-L1` e2e 재실행 (keys 기본 off 계약 green) — ✅ **2026-07-07 실행: 9 passed** (AGG-01~04 전건 + L1-E01/E04/E05/E06/E07). 게이트 항목(AGG 전건·L1-E01/E06) green, done trace_id null 계약 유지, health detail `langfuse` 블록 라이브 확인. **L1-E02/E03 FAIL 은 사전결함** — "v4 SDK import fail → handler None" 전제가 SDK v2→v3 포팅(2026-04-24) 이후 소멸(v3 는 fake key 로도 `LangchainCallbackHandler` 생성, 컨테이너 프로브 확증). 본 변경 diff 는 None-경로 무접촉 → 회귀 아님, 스펙 v3 의미론 재작성은 follow-up. 참고: `.env.e2e` `LLM_PROVIDER=anthropic` 라 실효 경로는 pae 아닌 **v2**(prod 동형) — keys-off 계약은 경로 무관 green · **→ ✅ 07-07 스펙 v3 재작성 완료**: E02=`sys.modules` 포이즈닝(패키지 부재 시뮬, None+valid False), E03=`TRACE-BAD-KEY-LAZY`(lazy-init 계약 핀 — handler 생성+trace_id 사전배정+client_initialized True), l1-langfuse **7/7 green**
- **Pass 3 (live 실측)**: `R1-LF-V2SMOKE`(dev 키 기동 → health detail langfuse 블록 → langfuse-cli 로 trace/score/span 확인) + `R1-LF-EVALOPT`(eval opt-in 스모크) + score-config 콘솔 등록(user_feedback)

## Agent 모델 선택

- 설계: opus 급 (완료 — 감사 세션 + 본 문서)
- 구현: sonnet 급 (스펙 확정 — 본 세션 수행)
- 검증: pytest/ruff exit code 판정, live smoke 는 langfuse-cli + 사람 확인

## Validation

| 단계 | 명령/방법 | 기준 |
|---|---|---|
| V1 | `cd server && ruff check . && ruff format --check . && pytest -m "not real"` | all pass, 수집 에러 0 |
| V1-표적 | `pytest tests/test_loop_models_config.py tests/test_langfuse_ops.py tests/test_v2_loop_langfuse.py tests/test_metrics_langfuse.py -v` | 신규 18건 green |
| V2-회귀 | `pytest tests/test_langfuse_aggregate.py tests/test_langfuse_l2.py tests/test_engine_stream_events.py tests/test_v2_loop_qa_regressions.py -v` | 기존 계약 green |
| Pass 3 | dev 키 기동 → `/api/health/detail` → SSE → `langfuse-cli` trace 조회 | `langfuse` 블록 4키 · trace `marketscope.v2` · score 6종 |

## Metadata

- 변경 파일: `server/server/services/langfuse_tracer.py` · `server/server/agent/loop/models.py` · `server/server/agent/loop/engine.py` · `server/server/agent/graph.py` · `server/server/api/routes/chat.py` · `server/server/middleware/metrics.py` · `docker-compose.e2e.yml` · `.env`(untracked) · `.env.dev`(untracked) · `.env.example` · 신규 테스트 4파일 · 문서 5파일
- Deferred(follow-up): PAE 노드 generation span wiring(L2 Plan Pass 2) · L2-C eval harness · score-config 콘솔 등록 실행 · per-request breaker DI
