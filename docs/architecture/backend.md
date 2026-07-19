# Backend Architecture

> FastAPI(Python 3.12) 기반 백엔드 서버. Agent 레이어는 [agent.md](agent.md), 데이터 레이어는 [data.md](data.md) 참조.

## 1. 디렉토리 구조

```
server/server/
├── main.py              # FastAPI 앱 + lifespan 초기화
├── config.py            # pydantic-settings (환경변수)
├── logging_config.py    # 구조화 로깅
├── api/
│   ├── routes/
│   │   ├── chat.py      # POST /api/chat (SSE 스트리밍) + GET /api/health/detail
│   │   ├── districts.py # GET /api/districts, /{code}, /{code}/preview
│   │   ├── feedback.py  # POST /api/feedback/score (Langfuse score proxy)
│   │   └── map_data.py  # GET /api/map-data/polygons, /heatmap[/all]
│   ├── deps.py          # FastAPI 의존성 주입
│   ├── middleware.py    # RequestId, SecurityHeaders, global exception handler
│   ├── rate_limiter.py  # slowapi Limiter — 정의만, 라우트 미적용 (§9 참조)
│   └── errors.py        # 에러 응답 스키마
├── middleware/metrics.py  # 인메모리 메트릭 수집 + GET /metrics
├── agent/               # v2 agentic loop (agent/loop/) + 레거시 PAE 그래프 → agent.md 참조
├── data/etl/            # 공공데이터 수집 → data.md 참조
├── repositories/        # Mock/Real 분리 → data.md 참조
├── models/              # SQLAlchemy 모델
└── services/
    ├── cache.py         # Memory/Redis 이중 캐시
    ├── category_resolver.py  # 한국어 키워드→category_code
    ├── circuit_breaker.py    # 3-state async CB
    ├── singleflight.py       # 캐시 미스 동시 요청 병합 (heatmap 라우트 통합)
    └── langfuse_tracer.py    # LLMOps L1 trace wiring (graceful degrade)
```

## 2. 앱 초기화 (`main.py`)

### Lifespan (`main.py::lifespan`)

1. **CacheService**
   - `USE_MOCK=true` → `MemoryCacheService` (in-process dict)
   - `USE_MOCK=false` → `RedisCacheService` (lazy init + exponential backoff 1→2→4→60s, graceful fallback)
2. **DataAccess (Repository Facade)**
   - Mock factory: JSON fixture 기반 10개 repo 번들
   - Real factory: SQLAlchemy `async_sessionmaker` 주입 (pool 10 + overflow 20, pre_ping, recycle 1800s)
3. **CategoryResolver**
   - Mock: 13종 기본값
   - Real: `category_metadata` 테이블에서 `(code, name, aliases)` 로드 후 싱글톤 유지
4. **Shutdown**: `cache.close()` → `engine.dispose()` → Langfuse best-effort flush

> Agent 는 lifespan 초기화 단계가 없다. v2 루프/PAE 그래프 모두 **요청 단위**로 실행되며, 진입점은 `agent/runtime.py::run_agent` — `agent_loop_version == "v2"` 이고 `llm_provider != "mock"` 이면 v2 agentic loop(`agent/loop/engine.py`), 그 외(특히 Mock 모드)는 레거시 PAE 그래프(`agent/graph.py`)로 디스패치한다. 상세는 [agent.md](agent.md).

### 미들웨어 — 등록 순서 vs 실행 순서

`add_middleware` **등록 순서**는 CORS → SecurityHeaders → RequestId → Metrics 이고, Starlette 는 마지막 등록이 최외곽이므로 (`main.py` 주석 "last added = first executed") **요청 관점 실행 순서는 그 역순**이다:

```
 Request
   │
   ▼
 Metrics          ── path/status/latency 집계 (최외곽)
   │
   ▼
 RequestId        ── X-Request-ID 헤더 (인입 값 재사용, 없으면 UUID 생성, 응답에 echo)
   │
   ▼
 SecurityHeaders  ── X-Content-Type-Options=nosniff, X-Frame-Options=DENY, X-XSS-Protection,
   │                 Referrer-Policy=strict-origin-when-cross-origin, Permissions-Policy
   ▼
 CORS             ── allow_origins=settings.cors_origins 화이트리스트
   │                 (기본 localhost:3000/3001, env CORS_ORIGINS 오버라이드) + allow_credentials=True.
   │                 메서드/헤더만 ["*"] — "전체 허용" 아님
   ▼
 Route handler    (응답은 역순으로 통과)
```

**미들웨어가 아닌 것** — 아래 2개는 FastAPI exception handler 로 등록되어 미들웨어 체인에 포함되지 않는다:

- **Global exception handler** (`api/middleware.py::register_global_exception_handler`): 스택 미노출, 500 + `{"error": {code, message, request_id}}` (§6)
- **RateLimitExceeded handler** (`api/rate_limiter.py::register_rate_limiter`): 429 + `Retry-After` 헤더. 단, 이를 발동시키는 데코레이터/미들웨어가 등록되어 있지 않아 현재 도달 경로 없음 (§9)

## 3. 환경 설정 (`config.py`)

| 필드 | 기본값 | 설명 |
|---|---|---|
| `use_mock` | `True` | Mock/Real 분기 플래그 |
| `database_url` / `database_url_sync` | — | async + Alembic용 동기 URL |
| `redis_url` | `redis://localhost:6379/0` | Redis 접속. Mock 모드에서 미사용 |
| `seoul_opendata_api_key` / `data_go_kr_api_key` | — | ETL API 키 |
| `llm_provider` | `gemini` | `gemini` / `anthropic` / `openai` / `mock` — 선호 프로바이더를 체인 맨 앞으로 승격 (현 운영 env 는 `anthropic`) |
| `gemini_model_pro` / `gemini_model_flash` | `gemini-2.5-pro` / `2.5-flash` | Gemini 모델 ID — v2 fallback 체인 + PAE 역할별 |
| `anthropic_model` | `claude-sonnet-4-6` | Anthropic 모델 ID (은퇴 모델 hotfix 용 env-오버라이드 가능) |
| `openai_model` | `gpt-5.4-mini` | OpenAI 모델 ID — v2 fallback 체인 2순위(canary) + PAE (openai mode) |
| `agent_loop_version` | `v2` | **현행 런타임 스위치** — `v2`(모델주도 루프 + Trust Kernel) / `pae`(레거시 롤백). mock provider 는 항상 PAE 폴백 |
| `agent_loop_max_iterations` | `6` | v2 budget governor — 모델 턴 상한 (마지막 턴은 도구 없이 prose 강제) |
| `agent_loop_max_tool_calls` | `12` | v2 budget governor — 요청당 도구 실행 총량 |
| `agent_loop_wall_clock` | `90.0s` | v2 budget governor — 경과 시 강제 finalize |
| `trust_numeric_tolerance` | `0.05` | Trust Kernel — 응답 수치↔도구 값 바인딩 허용 오차 (±5%) |
| `agent_max_rounds` | `3` | 레거시 PAE 전용 — planner→actor→evaluator 재진입 상한 |
| `evaluator_skip_simple` | `true` | 레거시 PAE 전용 — 단순 의도는 LLM 평가 생략 (rule path) |
| `llm_timeout_fast` / `llm_timeout_slow` | `15s` / `60s` | fast = PAE planner/evaluator, slow = v2 모델 턴 / PAE respond |
| `tool_execution_timeout` | `15s` | 개별 Tool 실행 타임아웃 (`tool_result_max_chars=8000`) |
| `circuit_breaker_failure_threshold` | `5` | OPEN 전환 실패 횟수 |
| `circuit_breaker_recovery_timeout` | `60s` | HALF_OPEN 재시도 간격 |
| `max_history_turns` / `history_content_limit` | `10` / `300자` | 히스토리 턴 상한 / assistant 응답 truncate |
| `session_max_count` / `session_memory_limit_bytes` | `10000` / `524288` (512KB) | 인메모리 세션 상한 |
| `sse_queue_maxsize` | `256` | SSE 이벤트 큐 상한 (레거시 PAE graph 전용 backpressure) |
| `sse_heartbeat_interval` / `sse_connection_max_duration` | `25s` / `300s` | 프록시 유지 ping / 스트림 최대 지속 |
| `rate_limit_global` / `rate_limit_chat` | `60/minute` / `10/minute` | 정의만 존재, 라우트 미적용 — §9 참조 |
| `chat_message_max_length` | `500` | `/api/chat` message 길이 상한 |
| `langfuse_public_key` / `langfuse_secret_key` | `""` | 둘 다 세팅 시 `langfuse_enabled=True` (property) |
| `langfuse_host` | `https://cloud.langfuse.com` | Self-host 전환 시 덮어쓰기 |
| `langfuse_sampling_rate` | `1.0` | trace 샘플링 비율 (load-test 시 하향) |
| `langfuse_session_salt` | `""` | session_id 해싱 salt (비우면 기동 시 랜덤) |
| `langfuse_otel_insecure` | `False` | OTEL export TLS 검증 비활성 (사내 MITM 환경 전용, prod 기본 False) |

> env 파일 로딩: `.env.dev` 존재 시 우선, 아니면 `.env` (`config.py` 상단). Docker 는 compose `environment:` 블록 주입이라 file 로딩과 무관.

## 4. API 엔드포인트

| Method | Path | 요청 | 응답 | 비고 |
|---|---|---|---|---|
| GET | `/health` | — | `{status}` | Liveness |
| GET | `/api/health/detail` | — | DB pool / Redis / sessions / `agent_mode`(실효 루프 v2\|pae) / `agent_loop_version` / `llm_provider` / `llm_chain`(현 체인의 `provider:model_id` 리스트 — 키/순서 1-curl 확인) / `langfuse`(enabled·tracer_valid·client_initialized·sampling_rate — 무음사망 가시화) | Readiness |
| POST | `/api/chat` | `{message(≤500), session_id?, district_code?}` | `text/event-stream` | SSE — 이벤트 집합은 아래 표 (경로별 상이) |
| GET | `/api/districts` | `search?`, `type?`, `limit`, `offset` | `{total, items[]}` | 한글 조사 strip |
| GET | `/api/districts/{code}` | — | District + polygon | GeoJSON. 없으면 404 |
| GET | `/api/map-data/polygons` | `bounds?` | GeoJSON FeatureCollection | 뷰포트 필터, Cache-Control 24h |
| GET | `/api/map-data/heatmap` | `time_slot=0..23`(필수), `quarter?` | `{points[]}` | Redis cache 24h + singleflight |
| GET | `/api/map-data/heatmap/all` | `quarter?` | `{slots: {0..23: [...]}}` | 프리로드 + singleflight |
| GET | `/api/districts/{code}/preview` | `role?` | `DistrictPreview` JSON | F13 — LLM 무호출, Redis 24h |
| POST | `/api/feedback/score` | `{trace_id, value, reason?, comment?}` | 202/204 | F12 L1 — Langfuse score proxy, trace_id 멱등(24h) |
| GET | `/metrics` | — | `{sse_active_connections, singleflight_coalesced_total, langfuse_trace_missing_total, request_counts[], latency[]}` | 운영 관측 (p50/p95/p99/avg ms, 인메모리). `langfuse_trace_missing_total` = enabled 인데 done 에 trace_id 없던 요청 수 |

### `/api/chat` SSE 이벤트

방출 집합은 **실행 경로에 따라 다르다** (진입점 `agent/runtime.py::run_agent`, [agent.md](agent.md) 참조):

| type | v2 루프 (기본) | PAE (레거시/Mock) | chat.py 계층 | payload 예시 |
|---|---|---|---|---|
| `thinking` | O | O | — | `{step}` |
| `plan` | **X** | O — planner 완료 시 | — | `{intent, steps[]}` |
| `tool` / `tool_end` | O (도구 직렬 실행) | O (actor 병렬 실행) | — | `{name, input, progress_label}` / `{name, done_label}` |
| `card` | O | O | — | `{card_type, data}` |
| `text` | O (90자 청크) | O (respond 토큰 스트림) | greeting 단축 / 타임아웃·오류 종결 시 | `{content}` |
| `suggestion` | O | O | greeting 단축 시 | `{questions[]}` |
| `warning` | **X** | O — respond numeric_sanity 위반 시 1회 | — | `{rules, match_rate}` |
| `map_cmd` | X | X | **O — 유일 방출처** (에이전트 실행 전 1회) | `{action:"move", params:{lat,lng,zoom}, district_code, district_name, district_type}` |
| `done` | O (+`trace_id?`) | O (+`trace_id?`, `quality_flags?`, `quality_match_rate?`) | greeting / 타임아웃 / 오류 종결 | `{}` + 부가 payload |

- 요약: **v2 = 7종**(thinking/tool/tool_end/card/text/suggestion/done), **PAE = 9종**(+plan, +warning). `map_cmd` 와 greeting 단축 응답(text+suggestion+done)은 두 루프 공통으로 `chat.py` 가 에이전트 밖에서 방출한다.
- 프론트 `SSEEvent` 유니온(`frontend/src/lib/types.ts`)은 여기에 `error` 리터럴을 더한 10종을 정의하되 `warning` 은 미정의 — PAE warning 이벤트는 프론트 파서에서 무시된다.
- 스트림 가드: 최대 지속 `sse_connection_max_duration`(300s) + heartbeat ping 25s + 매 이벤트 client-disconnect 체크.

## 5. 서비스 레이어

### Cache (`services/cache.py`)

- **인터페이스**: `get / set / delete / flush_by_prefix / close` (async) — `clear` 메서드는 없음
- **MemoryCacheService**: in-process dict + JSON 직렬화. 개발/Mock용.
- **RedisCacheService**: 연결 실패 시 점진적 재시도(1→2→4→60s) 후에도 실패하면 함수 호출마다 예외 없이 `None` 반환(graceful degradation). 20 커넥션 풀 / 3s timeout.
- 기본 TTL: 24h. 주요 키 규약(실측): `heatmap:{time_slot}:{quarter|latest}` · `heatmap:all:{quarter|latest}` · `preview:{code}:{role|default}` · `summary:{district_code}` · `fp:` `sales:` `store:` `pop:` `history:` `compare:` `recommend:` `simulation:` · `feedback:seen:{trace_id}` — 전수 표는 [data.md](data.md) 참조.
- 배포 시 flush: `server/scripts/flush_cache.py` (DEFAULT_PREFIXES = `sales:` `compare:` `recommend:` `simulation:` `summary:`).

### Singleflight (`services/singleflight.py`)

- per-key Future + `asyncio.Lock` — 캐시 미스 시 동일 키 동시 요청을 leader 1회 호출로 병합 (leader cancel-shield 포함)
- `map_data.py::get_heatmap[/all]` 에 통합. 병합 횟수는 `/metrics` 의 `singleflight_coalesced_total` 로 노출.

### Circuit Breaker (`services/circuit_breaker.py`)

- 3-state async: CLOSED → OPEN → HALF_OPEN → CLOSED
- 프로토콜: `check()` → 호출 → `record_success()` / `record_failure()`
- 실패 임계 5회, 회복 60초. LLM 호출 래핑에 사용 (v2 fallback 체인 `loop_llm` / PAE `llm`).

### Category Resolver (`services/category_resolver.py`)

- 한국어 키워드(예: `"카페"`, `"한식"`) → `category_code` 매핑 (case-insensitive substring 매칭)
- Mock: 13개 하드코딩
- Real: `category_metadata(code, name, aliases)` + `learned_aliases`(confidence ≥ 0.7) 로드 후 역 인덱스 구축 (싱글톤)

## 6. 에러/로깅 규약

- **표준 에러 응답** (global exception 500 / rate-limit 429): `{"error": {"code": str, "message": str, "request_id": str}}` — `"error"` 키 아래 **중첩** 구조
- **에러 코드 상수** (`api/errors.py`): `RATE_LIMITED` · `VALIDATION_ERROR` · `NOT_FOUND` · `INTERNAL_ERROR` · `SERVICE_UNAVAILABLE`
- **라우트 레벨 4xx/503** 은 FastAPI `HTTPException` 기본 형태 `{"detail": "..."}` — `raise_db_unavailable()`(503) / `raise_not_found()`(404) 헬퍼 사용. 표준 포맷과 공존하므로 클라이언트는 두 형태 모두 처리.
- **로깅**: `request_id`, `session_id`, `user_intent` 필드 포함. 스택 트레이스는 서버 로그에만, 응답에는 미노출.

## 7. 세션 관리

- 인메모리 세션 저장소 (`session_max_count=10000`, 세션당 `session_memory_limit_bytes=512KB`)
- TTL 30분, 60초 주기로 만료 세션 prune. 동시성: 세마포어 20(`_MAX_CONCURRENT_CHATS`) + per-session in-flight 선점 취소
- 대화 히스토리 `max_history_turns=10` (초과분 FIFO 제거, assistant 응답은 `history_content_limit=300자` truncate). **v2 루프는 그중 최근 6턴만 프롬프트에 사용**
- 세션 재시작 시 유실 — 프로덕션에서는 Redis 또는 Postgres 이관 고려 대상 (현재 out of scope)

## 8. 테스트

- **Backend pytest**: `server/tests/` — **테스트 모듈 30개 · 수집 247케이스** (이 중 `@pytest.mark.real` DB 통합 6케이스). 최근 실측 2026-07-08: **241 passed / 6 deselected(@real)**.
  주요 파일: `conftest.py`(fixture 5종, `USE_MOCK=true`·`LLM_PROVIDER=mock` 강제) · `test_services_{cache,circuit_breaker,category_resolver}.py` · `test_repos_mock.py`(10 protocol) · `test_routes_health_and_map.py`(lifespan + httpx ASGITransport) · `test_singleflight.py`(9) · **`test_trust_kernel_regressions.py`(23)** · **`test_v2_loop_qa_regressions.py`(12)** · `test_loop_models_stream.py`(8) + `test_engine_stream_events.py`(5) (스트리밍 옵션 B) · `test_loop_models_chain.py`(9) + `test_pae_create_llm.py`(4) (LLM Gateway openai) · `test_loop_models_config.py`(3) + `test_langfuse_ops.py`(7) + `test_v2_loop_langfuse.py`(5) + `test_metrics_langfuse.py`(3) (Langfuse ops-hardening) · `test_langfuse_l2.py`(12) + `test_langfuse_aggregate.py`(10) · `test_data_integrity.py`(13 = unit 7 + `@real` 6) · `test_tool_tag_sanitizer.py`(11) + `test_xml_sanitizer.py`(6) · `test_entity_matching.py`(7) · `test_coref_numeric_followup.py`(7) · `test_out_of_scope.py`(7) · `test_numeric_sanity.py`(6) · `test_recommendation_scoring.py`(6) · `test_planner_clarification.py`(4) · `test_chat_session_concurrency.py`(4) · `test_smoke.py`(3) · `test_graph_suggestion_emission.py`(2).
  CI: `.github/workflows/ci.yml::backend-test` — `pytest -m "not real"` + `--cov=server`(coverage XML artifact), dummy env 주입. `@real` 6케이스는 로컬 opt-in.
- **E2E (Playwright)**: `frontend/e2e/` — spec 44파일 · test 선언 188개 (ring0 4파일·18 / ring1 25파일·99 / ring2 6파일·13 / ring3 7파일·35 = ring0~3 소계 42파일·165 + prod-smoke 1파일·11(active 9 + skip 2) + 레거시 루트 phase3-scenario 1파일·12). 산정: `test(`/`test.skip(`/`test.fixme(` 선언 수 기준 (2026-07-16 실측). 실행 `cd frontend && npm run test:e2e`. 백엔드 SSE 규약까지 커버.
- **수동 smoke**: `scripts/verify_sales_units.py`, `server/scripts/flush_cache.py` 등 운영 스크립트

## 9. 레이트/쿼터

- **레이트리밋**: config `rate_limit_chat`("10/minute") 은 정의만 되어 있고 chat 라우트에 `@limiter.limit` 데코레이터 미적용(전역 60/min 만 유효) — 적용 여부는 별도 결정 대기. 429 핸들러(+`Retry-After`)는 등록되어 있음.
- **Agent 예산 (v2 기본)**: budget governor — 모델 턴 6회(`agent_loop_max_iterations`) / 도구 호출 12회(`agent_loop_max_tool_calls`) / wall clock 90s(`agent_loop_wall_clock`). Tool 1회 타임아웃 15s(`tool_execution_timeout`). 레거시 PAE 는 `agent_max_rounds=3`.
- **동시성**: `/api/chat` 동시 스트림 세마포어 20 + SSE 스트림 최대 지속 300s.
- Free/Premium Tier 게이팅은 미구현 → Phase 2 (`plan/business/commercialization-plan.md`)
