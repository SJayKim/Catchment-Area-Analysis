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
│   │   ├── chat.py      # POST /api/chat (SSE 스트리밍)
│   │   ├── districts.py # GET /api/districts, /{code}, /{code}/preview
│   │   ├── feedback.py  # POST /api/feedback/score (Langfuse score proxy)
│   │   └── map_data.py  # GET /api/map-data/polygons, /heatmap[/all]
│   ├── deps.py          # FastAPI 의존성 주입
│   ├── middleware.py    # RequestId, SecurityHeaders
│   ├── rate_limiter.py  # slowapi (global 60/min, chat 10/min)
│   └── errors.py        # 에러 응답 스키마
├── middleware/metrics.py  # 인메모리 메트릭 수집
├── agent/               # LangGraph PAE → agent.md 참조
├── data/etl/            # 공공데이터 수집 → data.md 참조
├── repositories/        # Mock/Real 분리 → data.md 참조
├── models/              # SQLAlchemy 모델
└── services/
    ├── cache.py         # Memory/Redis 이중 캐시
    ├── category_resolver.py  # 한국어 키워드→category_code
    ├── circuit_breaker.py    # 3-state async CB
    └── langfuse_tracer.py    # LLMOps L1 trace wiring (graceful degrade)
```

## 2. 앱 초기화 (`main.py`)

### Lifespan (`main.py:91-146`)

1. **CacheService**
   - `USE_MOCK=true` → `MemoryCacheService` (in-process dict)
   - `USE_MOCK=false` → `RedisCacheService` (lazy init + exponential backoff 1→2→4→60s, graceful fallback)
2. **DataAccess (Repository Facade)**
   - Mock factory: JSON fixture 기반 10개 repo 번들
   - Real factory: SQLAlchemy `async_sessionmaker` 주입 (pool 10 + overflow 20, pre_ping, recycle 1800s)
3. **CategoryResolver**
   - Mock: 13종 기본값
   - Real: `category_metadata` 테이블에서 `(code, name, aliases)` 로드 후 싱글톤 유지
4. **Agent Graph**
   - `PAE` 모드: per-request 컴파일 (상태 격리)
   - LLM 프로바이더 인스턴스는 모듈 싱글톤

### Middleware 실행 순서

```
 Request
   │
   ▼
 CORS (전체 허용, MVP)
   │
   ▼
 SecurityHeaders  ── X-Frame-Options=DENY, X-XSS=1, Referrer-Policy=no-referrer, Permissions-Policy
   │
   ▼
 RequestId        ── X-Request-ID 헤더 (UUID, 응답에 echo)
   │
   ▼
 Global Exception ── 스택 미노출, JSON {code, message, request_id}
   │
   ▼
 RateLimiter      ── slowapi, IP key_func, 429 + Retry-After
   │
   ▼
 Metrics          ── path/status/latency 집계
   │
   ▼
 Route handler
```

## 3. 환경 설정 (`config.py`)

| 필드 | 기본값 | 설명 |
|---|---|---|
| `use_mock` | `True` | Mock/Real 분기 플래그 |
| `database_url` / `database_url_sync` | — | async + Alembic용 동기 URL |
| `redis_url` | `redis://localhost:6379/0` | Redis 접속. Mock 모드에서 미사용 |
| `seoul_opendata_api_key` / `data_go_kr_api_key` | — | ETL API 키 |
| `llm_provider` | `gemini` | `gemini` / `anthropic` / `mock` |
| `llm_model_*` | 역할별 | `pro`(respond) / `flash`(planner/evaluator) |
| `agent_mode` | `pae` | 현재 PAE 전용. ReAct 경로는 레거시 |
| `agent_max_rounds` | `3` | planner→actor→evaluator 재진입 상한 |
| `evaluator_skip_simple` | `true` | 단순 의도는 LLM 평가 생략 (rule path) |
| `llm_timeout_fast` / `llm_timeout_slow` | `15s` / `60s` | planner/evaluator / respond |
| `tool_timeout` | `15s` | 개별 Tool 실행 타임아웃 |
| `circuit_breaker_failure_threshold` | `5` | OPEN 전환 실패 횟수 |
| `circuit_breaker_recovery_timeout` | `60s` | HALF_OPEN 재시도 간격 |
| `session_max_count` / `session_memory_limit` | `10000` / `512KB` | 인메모리 세션 상한 |
| `sse_queue_maxsize` | `256` | SSE 이벤트 큐 상한 (backpressure) |
| `sse_heartbeat_interval` | `25s` | 프록시 유지를 위한 주기적 ping |

## 4. API 엔드포인트

| Method | Path | 요청 | 응답 | 비고 |
|---|---|---|---|---|
| GET | `/health` | — | `{status}` | Liveness |
| GET | `/api/health/detail` | — | DB pool / Redis / sessions | Readiness |
| POST | `/api/chat` | `{message, session_id?, district_code?}` | `text/event-stream` | SSE 9 이벤트 |
| GET | `/api/districts` | `search?`, `type?`, pagination | JSON list | 한글 조사 strip |
| GET | `/api/districts/{code}` | — | District + polygon | GeoJSON |
| GET | `/api/map-data/polygons` | `bounds?` | GeoJSON FeatureCollection | 뷰포트 필터 |
| GET | `/api/map-data/heatmap` | `time_slot=0..23`, `quarter?` | `{points[]}` | Redis cache 24h |
| GET | `/api/map-data/heatmap/all` | `quarter?` | `{slots: {0..23: [...]}}` | 프리로드 |
| GET | `/api/districts/{code}/preview` | `role?` | `DistrictPreview` JSON | F13 — LLM 무호출, Redis 24h |
| POST | `/api/feedback/score` | `{trace_id, value, reason?, comment?}` | 202/204 | F12 L1 — Langfuse score proxy |

### `/api/chat` SSE 이벤트

| type | payload 예시 | 발생 시점 |
|---|---|---|
| `thinking` | `{step, icon}` | Planner/Actor 전환 |
| `plan` | `{intent, steps[]}` | Planner 완료 |
| `tool` | `{name, input, progress_label, icon}` | Tool 호출 직전 |
| `tool_end` | `{name, done_label, icon}` | Tool 종료 |
| `card` | `{card_type, data, dataSources[]}` | Actor가 카드 발행 |
| `text` | `{content}` | Respond LLM 토큰 스트림 |
| `suggestion` | `{questions[]}` | Evaluator 추천 질문 |
| `map_cmd` | `{action, params}` | Actor가 지도 조작 요청 |
| `done` | `{}` | 세션 종료 |

## 5. 서비스 레이어

### Cache (`services/cache.py`)

- **인터페이스**: `get/set/delete/clear` (async)
- **MemoryCacheService**: in-process dict + JSON 직렬화. 개발/Mock용.
- **RedisCacheService**: 연결 실패 시 점진적 재시도(1→2→4→60s) 후에도 실패하면 함수 호출마다 예외 없이 `None` 반환(graceful degradation). 20 커넥션 풀 / 3s timeout.
- 기본 TTL: 24h. 키 규약: `report:{district_code}:{quarter}`, `heatmap:{quarter}:{slot}`.

### Circuit Breaker (`services/circuit_breaker.py`)

- 3-state async: CLOSED → OPEN → HALF_OPEN → CLOSED
- 프로토콜: `check()` → 호출 → `record_success()` / `record_failure()`
- 실패 임계 5회, 회복 60초. LLM 호출 래핑에 사용.

### Category Resolver (`services/category_resolver.py`)

- 한국어 키워드(예: `"카페"`, `"한식"`) → `category_code` 매핑
- Mock: 13개 하드코딩
- Real: `category_metadata(code, name, aliases[])` 로드 후 역 인덱스 구축 (싱글톤)

## 6. 에러/로깅 규약

- **JSON 에러 응답**: `{code: str, message: str, request_id: str}`
- **에러 코드**: `INTERNAL_ERROR`, `RATE_LIMITED`, `INVALID_INPUT`, `UPSTREAM_TIMEOUT`
- **로깅**: `request_id`, `session_id`, `user_intent` 필드 포함. 스택 트레이스는 서버 로그에만, 응답에는 미노출.

## 7. 세션 관리

- 인메모리 세션 저장소 (`session_max_count=10000`, 메모리 상한 512KB/세션)
- TTL 30분, 60초 주기로 만료 세션 prune
- 대화 히스토리 `history_max_turns=10` (초과분 FIFO 제거)
- 세션 재시작 시 유실 — 프로덕션에서는 Redis 또는 Postgres 이관 고려 대상 (현재 out of scope)

## 8. 테스트

- **Backend pytest**: `server/tests/` (단편 → conftest + core 5 모듈 확장, 2026-05-07).
  현재 107 passed, 8 skipped (full dev deps 시 unblock). Plan: [backend-pytest-coverage-expansion.md](../plan/infra/backend-pytest-coverage-expansion.md).
  주요 파일: `conftest.py` (fixture 5종) · `test_services_{cache,circuit_breaker,category_resolver}.py` · `test_repos_mock.py` (10 protocol) · `test_routes_health_and_map.py` (lifespan + httpx ASGITransport) · `test_singleflight.py` (9 testcase).
  CI: `.github/workflows/ci.yml::backend-test` (USE_MOCK 강제, dummy env, `--cov-report=xml` artifact).
- **E2E (Playwright)**: `frontend/e2e/ring{0,1,2,3}-*` → 백엔드 SSE 규약까지 커버
- **수동 smoke**: `scripts/verify_sales_units.py`, `server/scripts/flush_cache.py` 등 운영 스크립트

## 9. 레이트/쿼터

- 전역 60 req/min, `/api/chat` 10 req/min (IP 기반 slowapi)
- 세션별 Agent 최대 라운드 3, Tool 1회 타임아웃 15s
- Free/Premium Tier 게이팅은 미구현 → Phase 2 (`plan/business/commercialization-plan.md`)
