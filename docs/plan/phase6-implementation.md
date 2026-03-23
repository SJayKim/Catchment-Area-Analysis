# Phase 6 통합 계획 — 버그 수정, 서비스 분리 & E2E 테스트

> **작성일:** 2026-03-22
> **선행 조건:** Phase 5 완료 (기능 테스트 & 버그 수정)
> **목표:** Critical 버그 수정, Docker 배포 기준 서비스 분리, 전체 파이프라인 E2E 테스트
> **상용화를 위한 첫 번째 관문 — "실제로 돌아가는 시스템" 만들기**

---

## 목표

Phase 5까지 코드 완성도는 높지만, **한 번도 end-to-end로 실행된 적이 없다.**
Phase 6의 목표는 세 가지다:

1. **런타임 크래시를 유발하는 Critical 버그 4건 즉시 수정**
2. **모놀리식 `app/`을 Docker 배포 기준으로 서비스 분리** (API / Engine / Pipeline)
3. **실제 분석 요청 → 결과 반환까지 E2E 테스트 수행 및 검증**

---

## 환경 제약

| 항목 | 상태 | 비고 |
|------|------|------|
| Python 3.10+ | ✅ 사용 가능 | 핵심 의존성 설치됨 |
| Docker / Docker Compose | ✅ 사용 가능 | 서비스 분리 및 E2E 테스트 필수 |
| PostgreSQL + PostGIS | ✅ Docker 컨테이너 | docker-compose 정의 완료 |
| Redis 7 | ✅ Docker 컨테이너 | docker-compose 정의 완료 |
| 외부 API 키 | ⚠️ 부분 확보 | Seoul/Kakao/KOSIS/Google 확보, SEMAS/Naver 미확보 |
| LLM API | ✅ Gemini Flash | GOOGLE_API_KEY 확보됨 |

---

## 전체 일정 개요

| 스프린트 | 핵심 목표 | 예상 소요 | 상태 |
|---------|----------|----------|------|
| **S1** | Critical 버그 4건 수정 | 0.5일 | ✅ 완료 |
| **S2** | 서비스 분리 + Dockerfile + docker-compose 재구성 | 2~3일 | ✅ 완료 |
| **S3** | 서비스별 단위/통합 테스트 | 2일 | ⬜ 대기 |
| **S4** | E2E 테스트 (전체 파이프라인 검증) | 2일 | ⬜ 대기 |

### 의존성 그래프

```
S1-1 (debate 필드) ──┐
S1-2 (스케줄러)     ──┤
S1-3 (health)      ──┼──→ S2 (서비스 분리) ──→ S3 (서비스 테스트) ──→ S4 (E2E)
S1-4 (quality)     ──┘
```

---

## S1: Critical 버그 수정 ✅

> 런타임 크래시를 유발하는 4건. 이것 없이는 어떤 테스트도 불가능.

### S1-1: debate_check_node Revenue 필드명 불일치
- **위치:** `app/graph/nodes.py` debate_check_node
- **문제:** `estimated_revenue`, `revenue_lower_bound`, `revenue_upper_bound` 참조
- **실제 모델:** `estimated_monthly_revenue`, `revenue_range.min_value`, `revenue_range.max_value`
- **수정:** 필드명을 RevenueAnalysis 모델에 맞게 변경 ✅

### S1-2: 스케줄러 Collector 호출 파라미터 누락
- **위치:** `app/scheduler/jobs.py` 6개 job 함수
- **문제:** `collect_*()` 메서드를 필수 파라미터 없이 호출 → TypeError
- **수정:** district 목록 순회하며 올바른 파라미터 전달, 헬퍼 함수 추가 ✅

### S1-3: Health 엔드포인트 Redis import 오류
- **위치:** `app/api/routes/health.py`
- **문제:** `from app.cache.redis_client import _redis_client` — 존재하지 않는 변수
- **수정:** `from app.cache.redis_client import health_check` 사용 ✅

### S1-4: Quality Checker 잘못된 DB 컬럼 참조
- **위치:** `app/monitoring/quality_checker.py`
- **문제:** `daily_boarding` → 실제 `boarding_total`, `period` → `year,quarter` 등
- **수정:** ORM 모델 컬럼명에 맞게 4건 수정 ✅

### S1-5: 기존 테스트 확인
- `tests/unit/test_nodes.py` — revenue variance 테스트 필드명 업데이트 ✅
- `pytest tests/` — **71개 테스트 전부 PASS** ✅

---

## S2: 서비스 분리 + Docker 인프라 ✅

### 핵심 설계 결정

#### 1. 단일 Docker 이미지, 다중 엔트리포인트

기존 `app/` 코드베이스를 유지하되, 서비스별 진입점을 분리:

```
같은 이미지 (marketscope:latest)
├─ CMD ["uvicorn", "app.main:app"]          → marketscope-api
├─ CMD ["python", "-m", "app.engine"]       → marketscope-engine
├─ CMD ["python", "-m", "app.pipeline"]     → marketscope-pipeline
└─ CMD ["python", "-m", "app.mcp_servers.*"]→ MCP 서버 (기존)
```

**장점:** import 경로 변경 최소화, 빌드 1회, 이미지 공유
**단점:** 불필요한 의존성 포함 (API에 LangGraph 등) — 추후 멀티스테이지로 최적화

#### 2. Redis를 서비스 간 통신 허브로 사용

| 용도 | Redis 자료구조 | Key 패턴 |
|------|-------------|----------|
| 작업 큐 | Stream | `analysis:requests` |
| 진행률 | Pub/Sub | `analysis:progress:{request_id}` |
| 결과 저장 | Hash | `analysis:result:{request_id}` |
| 상태 관리 | Hash | `analysis:status:{request_id}` |

#### 3. 기존 코드 최소 변경 원칙

- `app/agents/`, `app/graph/`, `app/models/` → **변경 없음**
- `app/api/routes/analysis.py` → Redis 통신으로 교체
- `app/services/analysis_service.py` → **변경 없음** (engine에서 그대로 사용)

### 모놀리식 → 서비스 분리 비교

**변경 전 (모놀리식):**
```
[사용자] → POST /api/v1/analysis
              ↓
         [FastAPI app] ← 단일 프로세스
              ├─ BackgroundTasks.add_task(_run_analysis)  ← 인프로세스 실행
              ├─ _analysis_store: dict (인메모리)  ← 프로세스 종료 시 소실
              └─ _analysis_queues: asyncio.Queue   ← SSE 이벤트 전달
```

**문제점:**
1. API와 분석 엔진이 같은 프로세스 → 분석 중 API 응답 지연
2. 인메모리 상태 → 재시작 시 진행 중 분석 소실
3. 수평 확장 불가 (상태 공유 불가)

**변경 후 (서비스 분리):**
```
┌─────────────────────────────────────────────────┐
│              Docker Compose Network              │
├─────────────────────────────────────────────────┤
│  ┌──────────────┐    Redis Queue    ┌──────────┐│
│  │ marketscope  │ ───────────────→  │ market-  ││
│  │   -api       │ ←─────────────── │ scope    ││
│  │ (FastAPI)    │   Redis Pub/Sub  │ -engine  ││
│  │ Port: 8000   │                   │          ││
│  └──────────────┘                   └────┬─────┘│
│         │                                │      │
│         │ Health Check              MCP Calls   │
│         ▼                                ▼      │
│  ┌──────────────┐              ┌──────────────┐ │
│  │  PostgreSQL   │              │ 9 MCP Servers │ │
│  │  + PostGIS    │              │ (5100~5108)  │ │
│  └──────────────┘              └──────────────┘ │
│  ┌──────────────┐              ┌──────────────┐ │
│  │    Redis      │              │ marketscope  │ │
│  │   (Cache)     │              │  -pipeline   │ │
│  │               │              │ (Scheduler)  │ │
│  └──────────────┘              └──────────────┘ │
└─────────────────────────────────────────────────┘
```

### 서비스 간 통신 프로토콜

#### API → Engine (분석 요청)
```
Redis Stream: "analysis:requests"
Message Format:
{
    "request_id": "uuid",
    "query": "강남역 근처 카페 창업 분석",
    "location": "강남역",
    "industry": "카페",
    "depth": "standard",
    "created_at": "2026-03-22T10:00:00Z"
}
```

#### Engine → API (진행률 업데이트)
```
Redis Pub/Sub Channel: "analysis:progress:{request_id}"
Message Format:
{
    "type": "progress",
    "node": "population",
    "progress_pct": 25,
    "message": "인구 분석 중..."
}
```

#### Engine → API (최종 결과)
```
Redis Hash: "analysis:result:{request_id}"
Fields:
- status: "completed" | "failed"
- result: JSON string (전체 분석 결과)
- completed_at: ISO timestamp
- duration_seconds: float
```

### API analysis.py 리팩토링 요약

| 기존 | 변경 후 |
|------|--------|
| `_analysis_store[id] = {...}` | `redis_broker.update_status(id, "queued")` |
| `BackgroundTasks.add_task(_run_analysis)` | `redis_broker.publish_request(id, query)` |
| `_analysis_queues[id].put(event)` | (engine이 Redis Pub/Sub로 발행) |
| SSE: `queue.get()` | `redis_broker.subscribe_progress(id)` |
| `_analysis_store[id]["result"]` | `redis_broker.get_result(id)` |

### S2 실행 Step별 상세

| Step | 작업 | 산출물 | 상태 |
|------|------|--------|------|
| Step 1 | Dockerfile 작성 | `Dockerfile`, `.dockerignore`, `pyproject.toml` 수정 | ✅ |
| Step 2 | Redis 브로커 모듈 | `app/engine/redis_broker.py` (225 LOC) | ✅ |
| Step 3 | Engine Worker | `app/engine/worker.py` (131 LOC) | ✅ |
| Step 4 | API 리팩토링 | `app/api/routes/analysis.py`, `app/main.py` 수정 | ✅ |
| Step 5 | Pipeline 진입점 | `app/pipeline/main.py` (46 LOC) | ✅ |
| Step 6 | docker-compose 재구성 | 14개 서비스 (api, engine, pipeline 추가) | ✅ |
| Step 7 | 빌드/검증 | Docker 빌드 전 코드 검증 | ✅ |

### S2 검증 계획 및 결과

Docker 빌드 전 코드 품질 확보를 위한 검증:

| 기준 | 측정 | 결과 |
|------|------|------|
| Import 오류 0건 | 4개 모듈 python -c import 성공 | ✅ 4/4 |
| 발견 버그 수정 | health.py `async_session_factory` → `get_session_factory` | ✅ |
| 신규 테스트 PASS | 27개 신규 테스트 전부 PASS | ✅ 27/27 |
| 기존 테스트 유지 | 71개 기존 테스트 PASS | ✅ 71/71 |
| 총 테스트 수 | **98개 PASS** (2.41s) | ✅ |

---

## S3: 서비스별 테스트 ⬜

> **전제 조건:** 호스트(WSL2)에서 Docker Compose 기동 필요

### Step 12: Docker 빌드 및 인프라 기동

```bash
cd marketscope/
docker compose build
docker compose up -d postgres redis
# healthcheck 통과 대기
docker compose run --rm marketscope-api alembic upgrade head
docker compose up -d
docker compose ps  # 14개 서비스 확인
```

### Step 13: API 서비스 테스트

| 테스트 | 명령어 | 기대 결과 |
|--------|--------|----------|
| Health | `curl localhost:8000/api/v1/health` | 200 OK |
| Readiness | `curl localhost:8000/api/v1/health/ready` | DB, Redis 상태 |
| 분석 요청 | `POST /api/v1/analysis` | 202 + request_id |
| Stream 확인 | `curl -N localhost:8000/api/v1/analysis/{id}/stream` | SSE 이벤트 |
| 결과 조회 | `GET /api/v1/analysis/{id}` | status + result |

### Step 14: Engine 서비스 테스트

| 테스트 | 확인 방법 | 기대 결과 |
|--------|----------|----------|
| 기동 확인 | `docker compose logs marketscope-engine` | "Redis Stream 구독 시작" |
| Stream 수신 | API에서 분석 요청 후 engine 로그 | "분석 요청 수신: {id}" |
| MCP 연결 | engine 로그 | "MCP Router 초기화 완료" |
| 결과 저장 | `redis-cli GET analysis:result:{id}` | JSON 결과 |

### Step 15: MCP 서버 테스트 (9개)

```bash
for port in 5100 5101 5102 5103 5104 5105 5106 5107 5108; do
  echo -n "MCP :$port → "
  curl -s http://localhost:$port/health | head -c 80
  echo
done
```

### Step 16: Pipeline 서비스 테스트

| 테스트 | 확인 방법 | 기대 결과 |
|--------|----------|----------|
| 기동 확인 | `docker compose logs marketscope-pipeline` | "스케줄러 시작됨" |
| Job 등록 | pipeline 로그 | "스케줄 등록 완료: 8개 작업" |

---

## S4: E2E 테스트 ⬜

> **전제 조건:** S3 통과 + `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` 설정

### Step 17: Happy Path — 강남역 카페 분석

```bash
# 요청
curl -s -X POST http://localhost:8000/api/v1/analysis \
  -H "Content-Type: application/json" \
  -d '{"query": "강남역 카페 창업 분석", "depth": "standard"}'

# SSE 스트리밍
curl -N http://localhost:8000/api/v1/analysis/{request_id}/stream

# 결과
curl http://localhost:8000/api/v1/analysis/{request_id}
```

**성공 기준:**
- population_result, competition_result, revenue_result, location_result 존재
- final_judgment: score (0-100), grade, recommendation
- narrative_output: 텍스트 리포트
- 소요 시간: 120초 이내

### Step 18: 에러 시나리오

| 시나리오 | 입력 | 기대 |
|---------|------|------|
| 빈 query | `{"query": "a"}` | 422 Validation Error |
| 없는 ID 조회 | `GET /analysis/fake-id` | 404 ANALYSIS_NOT_FOUND |
| MCP 서버 다운 | `docker compose stop mcp-news` 후 분석 | graceful degradation |

### Step 19: 성능 측정

- Standard 분석 소요 시간
- LLM 호출 횟수 / 토큰 사용량
- 분석 1건당 예상 비용

### Step 20: 검증 보고서

- E2E 테스트 결과 요약
- 발견된 이슈 및 해결 방안
- 다음 단계 (Phase 7: LightRAG DB 구축) 제안

---

## 리스크 및 대응

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| Docker-in-Docker 불가 | 확정 | 높음 | 호스트(WSL2) 터미널에서 실행 |
| `tzdata` 미설치 | 높음 | 중간 | Dockerfile에 `tzdata` 추가 또는 UTC 사용 |
| MCP 서버 외부 API 장애 | 중간 | 높음 | stub/fallback 데이터로 E2E 테스트 우선 |
| LLM 비용 초과 | 낮음 | 중간 | Quick 모드 (4 에이전트)로 테스트 |
| Redis 통신 지연 | 낮음 | 낮음 | 타임아웃 설정 + 재시도 로직 |

---

## 성공 기준

| 기준 | 목표 | 현황 |
|------|------|------|
| Critical 버그 | 4건 전부 수정, 기존 71개 테스트 통과 유지 | ✅ |
| S2 코드 검증 | 98개 테스트 PASS | ✅ |
| Docker 빌드 | `docker-compose build` 성공 | ⬜ S3 |
| 서비스 기동 | 14개 서비스 전부 healthy | ⬜ S3 |
| E2E Happy Path | "강남역 카페" 분석 요청 → 최종 리포트 반환 | ⬜ S4 |
| 분석 소요 시간 | Standard 모드 기준 120초 이내 | ⬜ S4 |
| 결과 품질 | 4개 Phase 1 에이전트 결과 + 점수/등급/추천 포함 | ⬜ S4 |

---

## 파일 변경 요약 (S1+S2 완료분)

### 신규 파일 (8개)

| 파일 | 역할 | LOC |
|------|------|-----|
| `Dockerfile` | 공용 Docker 이미지 (python:3.11-slim) | 26 |
| `.dockerignore` | 빌드 제외 | 15 |
| `app/engine/__init__.py` | Engine 패키지 초기화 | 2 |
| `app/engine/__main__.py` | `python -m app.engine` 진입점 | 8 |
| `app/engine/worker.py` | EngineWorker (Redis Stream → LangGraph) | 131 |
| `app/engine/redis_broker.py` | RedisBroker (Stream/Pub/Sub/Hash) | 225 |
| `app/pipeline/__init__.py` | Pipeline 패키지 초기화 | 2 |
| `app/pipeline/__main__.py` | `python -m app.pipeline` 진입점 | 8 |
| `app/pipeline/main.py` | APScheduler 독립 실행 | 46 |

### 수정 파일 (7개)

| 파일 | 변경 내용 |
|------|----------|
| `app/graph/nodes.py` | debate_check_node revenue 필드명 수정 |
| `app/scheduler/jobs.py` | 6개 job 파라미터 수정 + 헬퍼 함수 |
| `app/api/routes/health.py` | import 오류 2건 수정 |
| `app/monitoring/quality_checker.py` | DB 컬럼명 4건 수정 |
| `app/api/routes/analysis.py` | 인메모리 → Redis 브로커 통신 |
| `app/main.py` | lifespan: broker init/close 추가, MCP Router init 제거 |
| `docker-compose.yml` | 3개 앱 서비스 추가 |
| `pyproject.toml` | `[build-system]` 섹션 추가 |

### 신규 테스트 파일 (4개, 27개 테스트)

| 파일 | 테스트 수 | 커버 대상 |
|------|---------|----------|
| `tests/unit/test_redis_broker.py` | 13 | RedisBroker 전체 메서드 |
| `tests/unit/test_analysis_routes.py` | 8 | API 라우트 |
| `tests/unit/test_engine_worker.py` | 4 | EngineWorker |
| `tests/unit/test_pipeline_main.py` | 2 | 스케줄러 초기화 |
