# LLMOps L1 Trace 실제 발생 검증 + request_id ↔ trace_id 운영 로그 조인

## Context

- **배경**: Phase L1 (Langfuse trace wiring) 코드는 완료 (커밋 `42b2209`, `3c5f884`, `1986f61`, `ded6cb1`, `ff9909c`). 그러나:
  1. **로컬 `.env` 에 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` 미설정** → 로컬 개발에서는 `langfuse_enabled=False` 로 graceful skip 중. trace 가 실제로 Langfuse Cloud 에 도달하는지 end-to-end 확인된 적 없음.
  2. **프로덕션은 `docker-compose.prod.yml:96-100` 으로 env 배선 완료**, 하지만 cloud 대시보드에 trace 가 채워지는지 sanity check 가 plan/run 로그에 누락.
  3. **운영 로그 ↔ Langfuse trace 양방향 추적 불가** — 사용자가 `done.trace_id` 를 frontend 에서 캡처해도, 백엔드 로그에서는 `request_id` 만 찍히고 Langfuse `trace_id` 는 어디에도 기록되지 않음. 컴플레인 → trace ID 역추적 또는 그 반대가 불가.
- **목적**: 
  - L1 trace 가 실제로 Langfuse 에 기록됨을 1회 명시적 검증 (로컬 + 프로덕션).
  - 백엔드 구조화 로그에 `trace_id` 를 1회 INFO 로 emit 하여 Loki/CloudWatch grep 으로 양방향 매핑 가능하게.
- **Memory 참조** (2026-07-04 정정: 리포 루트 `memory/` 디렉토리 부재로 링크 제거, 교훈 요지만 보존):
  - [[feedback_check_env_before_test]] — 테스트 전 env (USE_MOCK · 키 셋팅) 확인. 본 plan 도 첫 단계에서 `langfuse_enabled` 가 실제로 True 인지 확인하지 않으면 "trace 가 안 잡힌다" 가 키 미설정인지 wiring 버그인지 구분 불가.
  - [[feedback_marketscope_sse_format]] — `event:` 라인 없이 type 이 `data:` JSON 안에 임베드. curl sanity 에서 `data: ` prefix 자르고 `python -m json.tool` 파싱 필요.
  - [[feedback_probe_endpoint_shape_first]] — `done.trace_id` 가 실제로 응답에 포함되는지 source Read 만으로 추정 금지. curl 로 raw shape 직접 확인.
  - [[feedback_stale_container_vs_source]] — 프로덕션 검증 시 backend 컨테이너 재배포 시각이 wiring 커밋(`42b2209` 이후)인지 먼저 확인. 2026-04-23 운영 재배포는 `a5bef97` 기준이므로 OK 지만 향후 plan 적용 시 재확인.

## Scope

- **In Scope**:
  - 로컬 개발 환경에 Langfuse Cloud 무료 프로젝트 생성 + `.env` 키 셋팅 (`.env.example` 은 이미 자리 잡혀 있음, 신규 키 추가 X).
  - 로컬 1회 `curl /api/chat` 으로 trace 발생 확인 + Langfuse Cloud UI 에서 trace 1건 시각 확인.
  - 프로덕션 1회 `done.trace_id` ↔ Langfuse Cloud trace 매핑 확인 (마우스 1회).
  - `server/server/api/routes/chat.py` 에서 `done` 이벤트 emit 직전 또는 직후에 `logger.info("agent_done", extra={"request_id": ..., "trace_id": ..., "session_id": ...})` 1회 출력.
  - `done.trace_id` 가 실제로 frontend 까지 도달하는 raw SSE shape 캡처 → 본 plan 에 stdout 인용.
  - `docs/plan/infra/llmops-platform.md` 또는 status 의 "L1 미검증" 표현 갱신.
- **Out of Scope**:
  - Langfuse self-host 전환 (Cloud 무료 tier 로 충분).
  - L2 (token/cost auto-tracking, prompt registry, eval harness) — 별도 plan 으로 분리.
  - Tool 단위 span 세분화 (현재 LLM 콜은 callback 으로 자동 잡히지만 tool 은 LLM context 내부에 누적). L2 영역.
  - 로그 백엔드(Loki/CloudWatch) 셋업.
  - PII 가드 추가 (이미 `_hash_session()` 으로 session_id 해시 처리, 본 plan 변경 없음).

## Design

### 접근 방식

1. **검증 first, 코드 변경 last** — wiring 이 정상 동작하는지부터 확인하고, 동작 확인 후에만 로그 추가. 동작 안 하면 root cause 부터.
2. **수동 sanity → 자동 회귀** — 1회 수동 curl + cloud UI 확인이 우선. 자동 E2E 는 이미 `frontend/e2e/ring3-negative/l1-langfuse.spec.ts` 7/7 PASS (status doc) — 별도 추가 spec 불필요.
3. **로그 추가는 단일 line** — `done` 이벤트 yield 직후 `logger.info("agent_done", extra={...})` 한 줄. 중복 wiring (Langfuse 핸들러 외부 노출) 회피.

### 변경 파일 목록

| 경로 | 변경 요지 |
|---|---|
| `.env` (untracked, 로컬만) | `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` 3줄 추가. **Git commit 금지**. |
| `server/server/agent/graph.py` | `run_agent()` 에서 `done_payload` yield 직전 `trace_id` 를 `event_queue` 에 별도 시그널로 흘리거나, **(선호)** `request_id` 를 함께 받아 `logger.info` 로 1줄 출력. 단순성 위해 graph.py 안에 logger 직접 호출. |
| `server/server/api/routes/chat.py` | (대안) `done` 이벤트가 yield 될 때 chat.py 의 event_generator 가 자체적으로 `trace_id` 를 추출해 logger 호출. graph.py 변경 회피 가능. **이 옵션 채택** — agent layer 는 SSE-only, 로깅은 API layer 책임 분리 원칙에 부합. |
| `docs/status/current-status.md` | "L1 검증 완료" 줄로 갱신 + Cloud trace URL 1건 인용. |
| `docs/plan/infra/llmops-platform.md` (선택) | `§3.3.1` 의 "검증 미완" 메모를 "검증 완료 (`docs/plan/infra/llmops-l1-verification.md`)" 로 교체. |

### 의존성 / 선행 Plan

- 선행: `docs/plan/infra/llmops-l1-e2e.md` — E2E spec 자체는 이미 작성됨 (7/7 PASS). 본 plan 은 그 위에 "수동 sanity + 운영 로그 join" 을 얹는 보완 작업.
- 후행: `docs/plan/infra/llmops-platform.md` L2 (token/cost) — 본 plan 의 trace 가 실제 채워져야 cost 추적 의미가 있음.
- 코드 의존성:
  - `server/server/services/langfuse_tracer.py:102-119` `get_trace_id()` 가 v2 SDK `.trace_id` / `.last_trace_id` / `get_trace_id()` 메서드 3가지 fallback 보유. 본 plan 은 이 함수만 사용 (handler 직접 접근 X).
  - `server/server/api/middleware.py:22-26` `RequestIdMiddleware` 가 `request.state.request_id` 셋팅. chat.py 에서 이미 `getattr(request.state, "request_id", "")` 로 접근 중 (`chat.py:270`).

### 로그 포맷 (선택안)

```python
# server/server/api/routes/chat.py event_generator() 안, async for event 루프 내부
if event.get("type") == "done":
    logger.info(
        "agent_done",
        extra={
            "request_id": getattr(request.state, "request_id", ""),
            "session_id": session_id,
            "district_code": body.district_code,
            "trace_id": event.get("trace_id"),  # Langfuse 미활성 시 None
        },
    )
yield {"data": json.dumps(event, ensure_ascii=False, default=str)}
```

- structlog JSON renderer 가 `extra` dict 를 그대로 직렬화 (`logging_config.py:23-26` 참조).
- production 은 `setup_logging(json_output=True)` 로 호출되므로 한 줄 JSON 으로 grep 가능.
- `trace_id=None` 인 경우(Langfuse 비활성)에도 로그 라인은 emit — "Langfuse 꺼졌나" 자체가 운영 시그널이 됨.

## Checklist

- [ ] **C-1** Langfuse Cloud 무료 프로젝트 생성 (https://cloud.langfuse.com → 새 프로젝트 `marketscope-dev`). public/secret 키 발급.
- [ ] **C-2** 로컬 `.env` 에 3줄 추가 — `LANGFUSE_PUBLIC_KEY=pk-lf-...`, `LANGFUSE_SECRET_KEY=sk-lf-...`, `LANGFUSE_HOST=https://cloud.langfuse.com` (host 는 기본값 동일하지만 명시).
- [ ] **C-3** 로컬 백엔드 재기동 (`uvicorn server.main:app --reload --port 8002` 또는 `docker compose restart backend`). 부팅 로그에 `langfuse` import 에러 없는지 확인.
- [ ] **C-4** sanity curl — 강남역 코드(`3120189`)로 1회 chat 호출, raw SSE 응답에서 `done` 이벤트의 `trace_id` 필드 존재 확인.
  ```bash
  curl -N -X POST http://localhost:8002/api/chat \
    -H "Content-Type: application/json" \
    -d '{"message":"강남역 상권 요약","district_code":"3120189"}' \
    | grep -E '"type":\s*"done"'
  ```
  기대: `data: {"type":"done","trace_id":"<UUID>"}` 1줄.
- [ ] **C-5** Langfuse Cloud UI 에서 해당 trace 열람 — trace_name 이 `marketscope.pae` 인지, planner/respond span 이 들어왔는지 시각 확인. trace URL 을 plan Validation 섹션에 기록.
- [ ] **C-6** `chat.py` event_generator 에 `done` 이벤트 감지 시 `logger.info("agent_done", extra={...})` 1줄 추가 (Design §로그 포맷 참조).
- [ ] **C-7** 백엔드 재기동 + 다시 curl 1회 → 백엔드 stdout 에 `agent_done` 라인이 JSON 으로 emit, `trace_id` 필드가 C-4 의 `done.trace_id` 와 동일한지 확인.
- [ ] **C-8** 프로덕션 sanity (1회만) — `marketscope.robitlabs.co.kr` 에서 한 번 질의 후, Langfuse Cloud 에 trace 도달 확인. 도달하면 trace URL 1건만 plan 에 메모.
- [ ] **C-9** `docs/status/current-status.md` 의 ">관측성 L1: ..." 줄 옆에 `검증 완료 (2026-04-23)` 추가.
- [ ] **C-10** `docs/plan/infra/llmops-platform.md` 가 L1 검증을 미완으로 적시한다면 본 plan 링크로 교체.

## 재검토 (Self-Review Gate)

- [ ] **엣지 케이스**:
  - **Langfuse Cloud 다운/네트워크 단절** — `langfuse_tracer.py:74-77` 가 ImportError/Exception silent skip. `get_trace_id()` 도 None 반환 → `done.trace_id` 미포함, `agent_done` 로그의 `trace_id=None`. 회귀 우려 없음.
  - **샘플링 탈락** (`LANGFUSE_SAMPLING_RATE<1.0`) — `should_sample()` 이 False 면 handler=None → trace_id None. 본 plan 은 검증 단계에서 샘플링 1.0 유지 권장.
  - **`done` 이벤트가 timeout/disconnect 분기에서 yield 됨** (`chat.py:283-303`) — 그 분기는 `{"type":"done"}` 만 yield, `trace_id` 키 없음. 로그는 `trace_id=None` 으로 찍힘 — 이게 곧 "agent timeout 발생" 시그널. 의도된 동작.
  - **`request.state.request_id` 누락** (middleware 미적용) — `getattr(...,"")` 으로 빈 문자열 안전 처리.
  - **재시도 시 trace_id 중복 로그** — chat 재시도는 새 request 라 새 request_id/trace_id. 중복 없음.
- [ ] **Memory 교훈 반영**:
  - `feedback_check_env_before_test.md` → C-3 에서 `langfuse_enabled` 부팅 확인 명시.
  - `feedback_marketscope_sse_format.md` → C-4 sanity 가 `data:` prefix 그대로 grep (표준 SSE 파서 미사용).
  - `feedback_probe_endpoint_shape_first.md` → C-4 가 raw curl 로 shape 확인 (source Read 추정 금지).
- [ ] **타 Plan / 기존 코드 충돌**:
  - `llmops-l1-e2e.md` 의 `l1-langfuse.spec.ts` 7 spec 이 `done.trace_id` 존재만 검증 — 본 plan 의 `agent_done` 로그 추가가 SSE payload 자체에는 영향 0. spec 영향 없음.
  - `chat.py event_generator` 는 이미 다수의 `logger.warning/exception` 호출 보유 — 추가 1 line 부담 없음.
  - rate_limiter / metrics middleware 가 이미 request_id 를 사용 (`rate_limiter.py:26`, `middleware.py:48`) — 동일한 키 이름 재사용으로 grep alignment 자연스러움.

## Scenario (E2E Ring Mapping)

- **Ring**: **Ring 3 (regression)**. 기존 `l1-langfuse.spec.ts` 와 동일 영역, 회귀 방지가 1차 목표. 신규 spec 추가 X (충분히 커버됨), 기존 spec 의 단언만 1줄 보강.
- **Scenario ID**: `R3-LANGFUSE-LOG-JOIN`
- **사전조건**:
  - `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` 환경변수 셋업 (E2E 환경에서는 `.env.e2e` 활용).
  - `USE_MOCK=true` 가능 (Mock district `D3001` 으로 검증 가능 — Langfuse 는 LLM 호출에 hook, mock/real 무관).
  - 백엔드 stdout 캡처 가능 환경 (docker logs 또는 pytest capfd).
- **실행 단계**:
  1. `frontend/e2e/ring3-negative/l1-langfuse.spec.ts` 의 기존 7 test 1회 통과 확인 (회귀 방지).
  2. 동일 spec 마지막에 1 단언 추가 — `done` 이벤트 캡처 후 `expect(doneEvent.trace_id).toBeTruthy()` (이미 있으면 skip).
  3. 백엔드 stdout 에서 `agent_done` JSON 라인을 `grep` 하여 동일 `trace_id` 추출, frontend 의 `done.trace_id` 와 일치 확인. (선택 — 수동 검증으로 대체 가능)
- **기대 결과**:
  - 7/7 + 신규 단언 PASS.
  - `agent_done` 로그 JSON 의 `trace_id` 가 SSE `done.trace_id` 와 string equal.
  - Langfuse Cloud 에서 동일 `trace_id` 의 trace 검색 가능 (수동, plan Validation 에 URL 인용).

## Pass 반복 (Iteration Plan)

- **Pass 1 — 기본 구현 + 수동 검증** (목표 4시간):
  - C-1~C-5 (Langfuse 키 셋팅 + curl sanity + Cloud UI 확인).
  - C-6~C-7 (logger.info 1줄 추가 + 재검증).
  - C-9 status doc 갱신.
  - 수동 검증 결과 (curl raw 응답 1줄 + Cloud trace URL 1건) 을 본 plan Validation 섹션에 인라인 기록.
- **Pass 2 — 엣지 케이스 보강** (목표 1시간):
  - 샘플링 0.5 로 낮추고 4회 호출 → 약 2회 trace_id 가 None 으로 찍히는지 확인.
  - Langfuse Cloud 키를 의도적으로 invalid 값으로 변경 → handler 생성 실패 후 `_tracer_valid=False` 로 묶이고 이후 호출에서 None 유지되는지 확인.
  - chat timeout 강제 (긴 메시지 + `sse_connection_max_duration` 단축) → `done` 이벤트가 timeout 분기로 가도 `agent_done` 로그가 emit, `trace_id=None` 임을 확인.
- **Pass 3 — 프로덕션 회귀** (목표 30분):
  - C-8 프로덕션 sanity 1회.
  - prod-smoke 7/7 (이미 PASS) 재실행 후 백엔드 로그에서 `agent_done` 7건 emit 확인.
  - status doc final commit.
- **Fail 시 루프**:
  - Pass 1 에서 trace 미발생 → `langfuse_tracer.py:80-91` CallbackHandler 생성자 인자 mismatch (v2 SDK 변경 가능성) 의심 → SDK 버전 핀 확인 (`pyproject.toml` `langfuse` extra).
  - Pass 1 에서 `agent_done` 로그 누락 → structlog formatter 가 `extra` dict 를 무시하는지 확인 (`logging_config.py:35-37`).

## Agent 모델 선택

- **설계 (이 plan 작성)**: opus — wiring 코드 이해 + graceful degrade 분기 + 로그 라인 위치 결정에 multi-file 추론 필요.
- **구현 (Pass 1 코드 변경)**: sonnet — `chat.py` event_generator 안의 1줄 추가 + status doc 1줄 갱신. 명확한 스펙.
- **검증 (Pass 1~3 sanity)**: haiku — curl 응답 grep, 로그 라인 grep, PASS/FAIL 판정. 단순 비교.
- **근거**: 본 plan 의 코드 변경량은 ~5 LOC. 복잡도는 "동작 확인 + 로그 1줄" 수준이라 sonnet/haiku 분리만으로 충분.

## Validation

### 수동 검증 스텝

1. **로컬 sanity (Pass 1)**:
   ```bash
   # 백엔드 부팅 후
   curl -N -X POST http://localhost:8002/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message":"강남역 요약","district_code":"3120189","session_id":"verify-2026-04-23"}' \
     | tee /tmp/chat-sanity.txt
   grep '"trace_id"' /tmp/chat-sanity.txt
   ```
   기대: `data: {"type":"done","trace_id":"abc123..."}` 1줄.

2. **Langfuse Cloud UI 확인**:
   - https://cloud.langfuse.com → `marketscope-dev` 프로젝트 → Traces → 방금 생성된 trace 클릭.
   - `trace_name = marketscope.pae`, metadata 에 `request_id`/`llm_provider`/`agent_mode`/`use_mock` 4개 키 보임.
   - planner / respond span 들이 timeline 에 표시.
   - **본 plan 의 Pass 1 완료 표시는 trace URL 1건을 아래 [기록] 섹션에 인용**.

3. **로그 join 확인** (C-6 적용 후):
   ```bash
   docker compose logs backend --since 10s | grep agent_done
   ```
   기대: JSON 1줄 `{"event":"agent_done","request_id":"...","session_id":"...","district_code":"...","trace_id":"abc123..."}`. `trace_id` 가 1번 단계의 `done.trace_id` 와 동일.

4. **프로덕션 sanity (Pass 3)**: 동일 절차를 `https://marketscope.robitlabs.co.kr` 대상으로 1회. 백엔드 로그는 `ssh prod && docker compose logs backend --since 10s | grep agent_done`.

### 자동 검증

- `cd frontend && npx playwright test ring3-negative/l1-langfuse.spec.ts` — 기존 7 test PASS 유지.
- (선택) `/e2e-run 3` — Ring 3 전체 회귀.

### [기록] (Pass 별로 채움)

- **Pass 1-a baseline (Langfuse 키 없음)** — 2026-04-23:
  - curl: `curl -N -X POST http://localhost:8000/api/chat ... --data-binary @scripts/.sanity_body.json` (바디: `{"message":"강남역 요약","district_code":"3120189","session_id":"verify-2026-04-23"}`). 포트는 plan 원문 `:8002` (호스트 uvicorn) 대신 docker compose backend 기본 `:8000`.
  - raw done: `data: {"type": "done"}` (Langfuse 비활성 → `trace_id` 키 미포함, 설계 의도한 graceful degrade)
  - 백엔드 로그: `agent_done request_id=0acd4abe-... session_id=verify-2026-04-23 district=3120189 trace_id=-`
- **Pass 1-b Langfuse 키 투입 + v3 포팅 (trace 실제 발행)** — 2026-04-23:
  - **SDK 호환성 이슈 발견**: langfuse 2.60.10 의 `from langfuse.callback import CallbackHandler` 가 legacy `langchain.callbacks.base` 요구. 컨테이너엔 `langchain_core` / `langchain_anthropic` / `langchain_google_genai` 만 있고 `langchain` 메타패키지 부재 → ImportError → `_tracer_valid=False` 로 차단.
  - **조사 경로**:
    1. `pip install langchain==0.3.x` 시도 → `langchain-core` 0.3 로 강제 downgrade, `langchain_anthropic`/`langchain_google_genai` 가 `ContextOverflowError` 로 ImportError (LLM 스택 파괴)
    2. 복구 후 `pip install 'langfuse>=3,<4'` + `pip install 'langchain>=1,<2'` 조합 테스트 — `langfuse.langchain` 소스 보면 `if langchain.__version__.startswith("1"): ... from langchain_core.callbacks import BaseCallbackHandler` 로 분기, modern 스택과 공존 가능 ✅
  - **`langfuse_tracer.py` v3 포팅** — v3 는 Client 와 Handler 분리 구조:
    - `Langfuse` client 싱글톤 (`_client`) lazy init — env 자동 픽업 또는 명시적 `public_key/secret_key/host/sample_rate` 주입
    - `Langfuse.create_trace_id(seed=...)` 로 결정적 pre-assign → `CallbackHandler(trace_context=TraceContext(trace_id=...))` 로 handler 생성 시점에 이미 trace_id 결정됨 (astream 종료 후 otel context 이탈에 안전)
    - handler 에 `_ms_trace_id` / `_ms_session_hash` / `_ms_request_id` 부착 → `get_trace_id()` 가 이것을 우선 반환
    - 신규 `build_langchain_metadata(handler)` → graph.py 의 `astream(config={..., metadata: ..., tags: ['marketscope.pae'], run_name: 'marketscope.pae'})` 로 전달해 Langfuse UI 의 session/llm_provider/agent_mode/use_mock/request_id 필터링 가능
  - **`graph.py`**: `astream_config` 에 `metadata` / `tags` / `run_name` 3필드 추가 (기존 `callbacks` 만 있었음)
  - **`pyproject.toml`**: `langfuse>=2.0,<3.0` → `langfuse>=3,<4` + `"langchain>=1,<2"` 새 라인 추가
  - 재검증 curl (session_id="verify-2026-04-23-langfuse"):
    - raw done: `data: {"type": "done", "trace_id": "9d59e6455eeb42f685b71f8057915377"}` ✅
    - 백엔드 로그: `agent_done request_id=b844a844-820a-41fe-81e9-2f5b99f61883 session_id=verify-2026-04-23-langfuse district=3120189 trace_id=9d59e6455eeb42f685b71f8057915377` ✅
    - **SSE done.trace_id === agent_done 로그 trace_id** — 운영 로그 ↔ Langfuse trace 양방향 매핑 확보
  - **⚠ Pass 1-b 후속 문제**: trace_id 는 SSE / 로그에 찍히는데 Cloud UI 의 Traces 탭이 비어 있음. 백엔드 로그 grep → OTEL HTTP exporter 가 `/api/public/otel/v1/traces` POST 시 `SSLError CERTIFICATE_VERIFY_FAILED` 로 전량 드롭 중. 로컬 dev 환경이 corporate/ISP MITM HTTPS intercept 이라 certifi 번들·시스템 CA 번들 모두 Langfuse cert 체인을 검증 못함.
- **Pass 1-c SSL 우회 + Cloud export 성공** — 2026-04-23:
  - 조사 경로:
    1. `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` 환경변수 주입 → **효과 없음**. `urllib.request` 기본 context 에서는 200 OK 지만 `requests` session 레벨에서는 실패 (CA 번들 차이).
    2. `certifi` 최신판(`2026.04.22`) 업그레이드 → **실패 유지**.
    3. Langfuse 공식 문서 조회 (langfuse skill) — `OTEL_EXPORTER_OTLP_TRACES_CERTIFICATE` 는 cert 경로만 받음(자체 해결 안 됨). `httpx_client=httpx.Client(verify=False)` 는 non-tracing 전용. **공식 "insecure" 옵션 없음**. 문서에 언급된 unsupported workaround: exporter session `.verify=False` monkey-patch.
    4. OTLP HTTP exporter source 확인 → `session.post(..., verify=self._certificate_file)` — `_certificate_file` 이 session.verify 를 override. **둘 다 False 로 세팅 필수**.
  - **최종 조치**:
    - `server/server/config.py`: `langfuse_otel_insecure: bool = False` 신규 필드 (env `LANGFUSE_OTEL_INSECURE`).
    - `server/server/services/langfuse_tracer.py`: `_disable_otel_tls_verify()` 내부 helper — `trace.get_tracer_provider()._active_span_processor._span_processors[*].span_exporter` 순회해 `_certificate_file = False` + `_session.verify = False` 를 모두 세팅. `urllib3.disable_warnings(InsecureRequestWarning)` + WARN 로그("DO NOT use in production") 1건. `_get_client()` 가 client 초기화 직후 `settings.langfuse_otel_insecure=True` 인 경우에만 호출.
    - `docker-compose.yml`: backend env 에 `LANGFUSE_OTEL_INSECURE: ${LANGFUSE_OTEL_INSECURE:-false}` 패스스루 (prod 는 false 기본). `.env` 에 `LANGFUSE_OTEL_INSECURE=true` 추가 (로컬 dev 전용).
  - 재검증 (session_id="verify-2026-04-23-otel-insecure"):
    - 3회 연속 curl → 3 trace 전송 성공. **OTEL export 실패 로그 0건** (이전엔 curl 1회당 SSLError 3회+ 발생).
    - Pass 1-c 확인용 trace ID 후보 (**어느 하나라도 Cloud UI 에 뜨면 PASS**):
      - `6858b5fc5b68643db593f73d2d56483a`
      - `bf8f637e2976200793402b747d10170f`
      - `4365fcdf399efa11cfaf447ad86b5521`
    - Cloud UI 에서 marketscope-dev 프로젝트 → Traces → 위 ID 중 아무거나 검색 → trace name `marketscope.pae`, tags `marketscope.pae` / `provider:anthropic` / `mode:real`, metadata `langfuse_session_id/request_id/llm_provider/agent_mode/use_mock`, planner/actor/evaluator/respond span 트리 기대.
  - **보안 주의**: `LANGFUSE_OTEL_INSECURE=true` 는 MITM 환경에서만 opt-in. 프로덕션 `docker-compose.prod.yml` 은 false 유지 — prod 네트워크에서는 기본 cert 검증이 성공해야 함.
- **Pass 2 엣지 (샘플링/invalid 키/timeout)**: deferred — 별도 수동 검증 세션에서 `LANGFUSE_SAMPLING_RATE=0.5` + 4회 호출, invalid 키, sse_connection_max_duration 단축 3 패턴 실행 권장
- **Pass 3 프로덕션 trace URL**: pending — 사용자가 `marketscope.robitlabs.co.kr` 1회 질의 후 Cloud UI 에서 trace URL 1건 인용

## Metadata

- 작성일: 2026-04-23
- 작성자: Claude Code (plan-new skill)
- 카테고리: infra
- 관련 커밋: `42b2209` (L1 wiring), `a5bef97` (운영 재배포)
- 관련 문서:
  - [llmops-l1-adr-hosting.md](./llmops-l1-adr-hosting.md) — Langfuse Cloud vs Self-host 결정
  - [llmops-l1-e2e.md](./llmops-l1-e2e.md) — E2E spec 7건
  - [llmops-platform.md](./llmops-platform.md) — L1~L3 전체 로드맵
