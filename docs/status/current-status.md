# MarketScope AI — 현재 상태 (Single Source of Truth)

> **마지막 업데이트**: 2026-03-22
> **진행 Phase**: Phase 6 — 버그 수정, 서비스 분리 & E2E 테스트
> **작업 환경**: Docker 컨테이너 내부 (WSL2), Docker-in-Docker 불가

---

## 1. Phase 전체 진행률

| 스프린트 | 상태 | 내용 | 완료일 |
|---------|------|------|--------|
| **S1** | ✅ 완료 | Critical 버그 4건 수정 | 2026-03-22 |
| **S2** | ✅ 완료 | 서비스 분리 + Docker 인프라 + 검증 테스트 | 2026-03-22 |
| **S3** | ⬜ 대기 | 서비스별 테스트 (Docker 환경 필요) | - |
| **S4** | ⬜ 대기 | E2E 테스트 (Docker + API 키 필요) | - |

---

## 2. 완료된 작업 상세

### S1: Critical 버그 수정 ✅

| # | 파일 | 수정 내용 |
|---|------|----------|
| 1 | `app/graph/nodes.py` | debate_check_node: `estimated_revenue` → `estimated_monthly_revenue`, `revenue_range.min_value/max_value` |
| 2 | `app/scheduler/jobs.py` | 6개 job: 파라미터 누락 수정 + `_current_quarter()`, `_prev_month()`, `_get_districts()` 헬퍼 추가 |
| 3 | `app/api/routes/health.py` | `_redis_client` import → `health_check` 함수 import |
| 4 | `app/monitoring/quality_checker.py` | `daily_boarding` → `boarding_total`, `period` → `year,quarter`, `source` → `collector_name` |
| 5 | `app/api/routes/health.py` | `async_session_factory` → `get_session_factory` (S2 검증 중 발견) |

### S2: 서비스 분리 + Docker 인프라 ✅

**설계 결정:** 단일 Docker 이미지 + 다중 엔트리포인트 (코드 변경 최소화)

```
같은 이미지 (marketscope:latest)
├─ CMD ["uvicorn", "app.main:app"]       → marketscope-api     (:8000)
├─ CMD ["python", "-m", "app.engine"]    → marketscope-engine
├─ CMD ["python", "-m", "app.pipeline"]  → marketscope-pipeline
└─ CMD ["python", "-m", "app.mcp_servers.*"] → MCP 서버 9개
```

#### 신규 파일 (8개)

| 파일 | 역할 | LOC |
|------|------|-----|
| `Dockerfile` | 공용 Docker 이미지 (python:3.11-slim) | 26 |
| `.dockerignore` | 빌드 제외 | 15 |
| `app/engine/__init__.py` | Engine 패키지 초기화 | 2 |
| `app/engine/__main__.py` | `python -m app.engine` 진입점 | 8 |
| `app/engine/worker.py` | Redis Stream 소비 → LangGraph 실행 | 131 |
| `app/engine/redis_broker.py` | Redis 기반 서비스간 통신 (Stream/Pub/Sub/Hash) | 225 |
| `app/pipeline/__init__.py` | Pipeline 패키지 초기화 | 2 |
| `app/pipeline/__main__.py` | `python -m app.pipeline` 진입점 | 8 |
| `app/pipeline/main.py` | APScheduler 독립 실행 + graceful shutdown | 46 |

#### 수정 파일 (4개)

| 파일 | 변경 |
|------|------|
| `app/api/routes/analysis.py` | 인메모리(`_analysis_store`, `_analysis_queues`) → Redis 브로커 통신 전면 교체 |
| `app/main.py` | lifespan: broker init/close 추가, MCP Router init 제거 (engine 담당) |
| `docker-compose.yml` | 3개 앱 서비스 추가 (api, engine, pipeline) + Docker 내부 호스트명 환경변수 |
| `pyproject.toml` | `[build-system]` 섹션 추가 (pip install 오류 수정) |

### S2 검증 테스트 ✅

#### 신규 테스트 파일 (4개, 27개 테스트)

| 파일 | 테스트 수 | 커버 대상 |
|------|---------|----------|
| `tests/unit/test_redis_broker.py` | 13 | RedisBroker 전체 메서드 (연결, Stream, Pub/Sub, Hash) |
| `tests/unit/test_analysis_routes.py` | 8 | API 라우트 (POST/GET/SSE + 에러 응답) |
| `tests/unit/test_engine_worker.py` | 4 | EngineWorker (처리 성공/실패, stop) |
| `tests/unit/test_pipeline_main.py` | 2 | 스케줄러 초기화, 8개 job 등록 |

#### 테스트 결과

```
전체: 98개 PASS (2.41s)
  ├─ 기존: 71개 (변경 없음)
  └─ 신규: 27개
```

---

## 3. 현재 아키텍처

```
[사용자] → POST /api/v1/analysis
              ↓
    ┌─ marketscope-api (FastAPI) ─────────────────┐
    │  1. 요청 검증                                │
    │  2. Redis Stream "analysis:requests"에 발행   │
    │  3. Redis Pub/Sub 구독 → SSE 스트리밍         │
    │  4. Redis Hash에서 결과 조회                   │
    └─────────────────────────────────────────────┘
              │ Redis Stream                Redis Pub/Sub ↑
              ▼                                          │
    ┌─ marketscope-engine (Worker) ───────────────┐     │
    │  1. Redis Stream에서 작업 수신                │     │
    │  2. LangGraph DAG 실행 (20노드)              │     │
    │  3. MCP Client Router → 9 MCP 서버           │     │
    │  4. 진행률 → Redis Pub/Sub 발행 ─────────────┼─────┘
    │  5. 최종 결과 → Redis Hash 저장               │
    └─────────────────────────────────────────────┘

    ┌─ marketscope-pipeline (Scheduler) ──────────┐
    │  APScheduler 8개 job (독립 실행)              │
    │  → Collector → PostgreSQL 직접 저장           │
    └─────────────────────────────────────────────┘

    ┌─ 9 MCP 서버 (기존 유지) ────────────────────┐
    │  5100~5108 포트, 각자 독립 실행               │
    └─────────────────────────────────────────────┘
```

---

## 4. 코드베이스 요약

| 영역 | 파일 수 | 비고 |
|------|--------|------|
| agents/ | 15 | Commander + 4분석(P1) + 5분석(P2) + 2리포트 + 3토론 |
| graph/ | 4 | 20노드 DAG, 조건분기 6개 |
| mcp_servers/ | 9종 | public_data(8), maps(7), real_estate(4), news(3), regulatory(3), finance(6), database(5), google_maps(5), naver_maps(5) |
| engine/ | 3 | Redis Stream Worker + Broker |
| pipeline/ | 3 | APScheduler 독립 실행 |
| tests/ | 98개 PASS | unit(92) + integration(6) |

---

## 5. 남은 작업 — S3: 서비스별 테스트

> **전제 조건:** 호스트(WSL2)에서 Docker Compose 기동 필요

### S3 체크리스트

- [ ] **Step 12: API 서비스 테스트**
  - [ ] `GET /health` → 200 OK
  - [ ] `GET /health/ready` → DB, Redis 상태 확인
  - [ ] `POST /api/v1/analysis` → 202 Accepted + request_id
  - [ ] Redis Stream에 메시지 발행 확인
  - [ ] `GET /api/v1/analysis/{id}` → 상태 조회
  - [ ] `GET /api/v1/analysis/{id}/stream` → SSE 연결 유지

- [ ] **Step 13: Engine 서비스 테스트**
  - [ ] LangGraph DAG 빌드 (20노드) 확인
  - [ ] Redis Stream에서 작업 수신 확인
  - [ ] MCP 서버 연결 확인 (health check)
  - [ ] 단일 에이전트 실행 → 결과 반환
  - [ ] 분석 완료 → Redis Hash에 결과 저장 확인

- [ ] **Step 14: MCP 서버 테스트 (9개)**
  - [ ] public_data (5100) — `/health` 응답
  - [ ] maps (5101) — `/health` 응답
  - [ ] real_estate (5102) — `/health` 응답
  - [ ] news (5103) — `/health` 응답
  - [ ] regulatory (5104) — `/health` 응답
  - [ ] finance (5105) — `/health` 응답
  - [ ] database (5106) — `/health` 응답 (postgres 의존)
  - [ ] google_maps (5107) — `/health` 응답
  - [ ] naver_maps (5108) — `/health` 응답

- [ ] **Step 15: Pipeline 서비스 테스트**
  - [ ] 스케줄러 job 등록 확인 (8개)
  - [ ] Collector 단위 실행 (dry-run)

---

## 6. 남은 작업 — S4: E2E 테스트

> **전제 조건:** S3 통과 + `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` 설정

- [ ] **Step 16: 전체 인프라 기동** — `docker-compose up -d`, 14개 서비스 healthy 확인
- [ ] **Step 17: Happy Path** — 강남역 카페 분석 요청 → SSE 스트리밍 → 결과 조회
  - 성공 기준: population/competition/revenue/location 결과 + final_judgment + narrative, 120초 이내
- [ ] **Step 18: 에러 시나리오** — 빈 query(422), 없는 ID(404), MCP 다운(graceful degradation)
- [ ] **Step 19: 성능 측정** — 소요 시간, LLM 호출 횟수/토큰, 분석 1건당 비용
- [ ] **Step 20: 검증 보고서** — E2E 결과 요약, 이슈, Phase 7 제안

---

## 7. 알려진 이슈 및 주의사항

| # | 이슈 | 영향 | 대응 |
|---|------|------|------|
| 1 | Docker-in-Docker 불가 | 현 개발 컨테이너에서 docker compose 실행 불가 | 호스트(WSL2) 터미널에서 실행 필요 |
| 2 | `tzdata` 미설치 | APScheduler `Asia/Seoul` 타임존 에러 | Dockerfile에 `tzdata` 추가 또는 UTC 사용 |
| 3 | MCP 서버 내부 URL | Docker 내부에서 localhost → 컨테이너명 | docker-compose.yml에 `MCP_SERVERS` 환경변수 추가 완료 |
| 4 | conftest.py revenue 필드 | `sample_state_with_results` fixture에 구 필드명 잔존 | 테스트에서 직접 override하므로 현재 문제 없음 (정리 권장) |

---

## 8. Master Checklist (전체 구현 현황)

### Step 1: Project Foundation (spec 00) ✅
- [x] 디렉토리 구조 생성
- [x] pyproject.toml, .env.example
- [x] config.py (Settings)
- [x] constants.py, exceptions.py, logging_config.py
- [x] models/ (common, agent_outputs, state, report, debate)
- [x] agents/base.py (BaseAgent)

### Step 2: MCP Client & Tools (spec 05) ✅
- [x] tools/mcp_client.py
- [x] tools/registry.py

### Step 3: Memory Stubs (spec 06 - minimal) ✅
- [x] memory/reme_client.py (stub)
- [x] memory/lightrag_client.py (stub)

### Step 4: Commander Agent (spec 02) ✅
- [x] agents/commander.py (planning + judgment)

### Step 5: Specialist Agents (spec 03) ✅
- [x] agents/population.py
- [x] agents/revenue.py
- [x] agents/competition.py
- [x] agents/location.py

### Step 6: Report Agents (spec 10) ✅
- [x] agents/narrative.py
- [x] agents/visualization.py

### Step 7: LangGraph Orchestration (spec 01) ✅
- [x] graph/workflow.py (StateGraph + DAG)
- [x] graph/nodes.py (9개 노드 함수)
- [x] graph/edges.py (조건부 라우팅)

### Step 8: API Endpoints (spec 08) ✅
- [x] main.py (FastAPI app + CORS + lifespan)
- [x] api/routes/analysis.py (POST, GET, SSE stream)
- [x] api/routes/health.py
- [x] api/deps.py
- [x] services/analysis_service.py

### Step 9: DB Layer (spec 07 - minimal) ✅
- [x] db/session.py (stub)
- [x] db/models.py (stub)
- [x] db/repositories.py (stub)

### 검증 결과 ✅
- [x] 전체 import 테스트 통과
- [x] LangGraph 그래프 빌드 성공 (20개 노드)
- [x] FastAPI 서버 부팅 성공 (8개 라우트)
- [x] 전체 테스트 98개 PASS (2.41s)

---

## 9. 참고 문서

| 문서 | 위치 |
|------|------|
| 테스트 환경 가이드 | `document/test_environment_guide.md` |
| Phase 6 통합 계획 | `docs/plan/phase6_plan.md` |
| 전체 로드맵 | `docs/plan/roadmap.md` |
| 설계 문서 (21개) | `document/specs/` |
| 이전 구현 현황 (Phase 5까지) | `plan/status/2026-03-21_implementation_status.md` |
