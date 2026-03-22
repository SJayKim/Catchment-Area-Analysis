# Phase 6 S2 상세 실행 계획 — 서비스 분리 & Docker 인프라

> **작성일:** 2026-03-22
> **선행 조건:** S1 버그 수정 완료, 71개 테스트 PASS
> **목표:** 모놀리식 앱을 3개 서비스로 분리하여 Docker Compose로 배포/테스트 가능하게 구성

---

## 현재 상태 분석

### 현재 아키텍처 (모놀리식)

```
[사용자] → POST /api/v1/analysis
              ↓
         [FastAPI app] ← 단일 프로세스
              │
              ├─ BackgroundTasks.add_task(_run_analysis)  ← 인프로세스 실행
              │     ↓
              │  AnalysisService.run_analysis()
              │     ↓
              │  LangGraph app.astream()  ← 20노드 DAG 직접 실행
              │     ↓
              │  MCP Client Router → 9 MCP 서버 (HTTP)
              │
              ├─ _analysis_store: dict (인메모리)  ← 프로세스 종료 시 소실
              └─ _analysis_queues: asyncio.Queue   ← SSE 이벤트 전달
```

**문제점:**
1. API와 분석 엔진이 같은 프로세스 → 분석 중 API 응답 지연
2. 인메모리 상태 → 재시작 시 진행 중 분석 소실
3. 수평 확장 불가 (상태 공유 불가)
4. Dockerfile 미존재 → Docker 빌드/배포 불가

---

## 목표 아키텍처

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

## 핵심 설계 결정

### 1. 단일 Docker 이미지, 다중 엔트리포인트

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

### 2. Redis를 서비스 간 통신 허브로 사용

| 용도 | Redis 자료구조 | Key 패턴 |
|------|-------------|----------|
| 작업 큐 | Stream | `analysis:requests` |
| 진행률 | Pub/Sub | `analysis:progress:{request_id}` |
| 결과 저장 | Hash | `analysis:result:{request_id}` |
| 상태 관리 | Hash | `analysis:status:{request_id}` |

### 3. 기존 코드 최소 변경 원칙

- `app/agents/`, `app/graph/`, `app/models/` → **변경 없음**
- `app/api/routes/analysis.py` → Redis 통신으로 교체
- `app/services/analysis_service.py` → **변경 없음** (engine에서 그대로 사용)
- 신규 파일 4개만 추가

---

## Step별 실행 계획

### Step 1: Dockerfile 작성 (30분)

단일 Dockerfile, 모든 서비스에서 공용.

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**검증:** `docker build -t marketscope:latest .` 성공

### Step 2: Redis 브로커 모듈 신규 작성 (1시간)

`app/engine/redis_broker.py` — API↔Engine 통신 전담 모듈

기능:
- `publish_request(request_id, query, depth)` → Redis Stream XADD
- `consume_requests()` → Redis Stream XREADGROUP (blocking)
- `publish_progress(request_id, event)` → Redis Pub/Sub PUBLISH
- `subscribe_progress(request_id)` → Redis Pub/Sub SUBSCRIBE
- `store_result(request_id, result)` → Redis Hash HSET
- `get_result(request_id)` → Redis Hash HGETALL
- `update_status(request_id, status)` → Redis Hash HSET

### Step 3: Engine Worker 신규 작성 (1시간)

`app/engine/__init__.py` + `app/engine/worker.py`

기능:
- Redis Stream에서 분석 요청 수신 (XREADGROUP, blocking)
- AnalysisService.run_analysis() 호출
- on_progress 콜백 → Redis Pub/Sub로 진행률 발행
- 완료 시 Redis Hash에 결과 저장
- 에러 시 상태를 "failed"로 업데이트

### Step 4: API analysis.py 리팩토링 (1시간)

기존 인메모리 방식 → Redis 통신으로 교체:

| 기존 | 변경 후 |
|------|--------|
| `_analysis_store[id] = {...}` | `redis_broker.update_status(id, "queued")` |
| `BackgroundTasks.add_task(_run_analysis)` | `redis_broker.publish_request(id, query)` |
| `_analysis_queues[id].put(event)` | (engine이 Redis Pub/Sub로 발행) |
| SSE: `queue.get()` | `redis_broker.subscribe_progress(id)` |
| `_analysis_store[id]["result"]` | `redis_broker.get_result(id)` |

### Step 5: Pipeline 진입점 신규 작성 (30분)

`app/pipeline/__init__.py` + `app/pipeline/main.py`

기능:
- APScheduler 시작 (register_all_jobs + start)
- 시그널 핸들러 (SIGTERM/SIGINT → graceful shutdown)
- DB 연결 관리

### Step 6: docker-compose.yml 재구성 (30분)

14개 서비스:
- `postgres` (기존)
- `redis` (기존)
- `marketscope-api` (신규: port 8000)
- `marketscope-engine` (신규: depends_on redis, mcp-*)
- `marketscope-pipeline` (신규: depends_on postgres, redis)
- 9 MCP 서버 (기존, Dockerfile 경로 수정)

### Step 7: 빌드 및 기동 검증 (30분)

```bash
docker-compose build                    # 전체 빌드
docker-compose up -d                    # 전체 기동
docker-compose ps                       # 14개 서비스 상태 확인
docker-compose logs marketscope-api     # API 로그 확인
docker-compose logs marketscope-engine  # Engine 로그 확인
curl http://localhost:8000/health       # API 응답 확인
```

---

## 신규 파일 목록

| 파일 | 역할 | 예상 LOC |
|------|------|---------|
| `Dockerfile` | 공용 Docker 이미지 | ~20 |
| `app/engine/__init__.py` | Engine 패키지 초기화 | ~5 |
| `app/engine/__main__.py` | `python -m app.engine` 진입점 | ~5 |
| `app/engine/worker.py` | Redis Stream 소비자 + LangGraph 실행 | ~120 |
| `app/engine/redis_broker.py` | Redis 통신 모듈 (API/Engine 공용) | ~150 |
| `app/pipeline/__init__.py` | Pipeline 패키지 초기화 | ~5 |
| `app/pipeline/__main__.py` | `python -m app.pipeline` 진입점 | ~5 |
| `app/pipeline/main.py` | 스케줄러 독립 실행 | ~40 |

## 수정 파일 목록

| 파일 | 변경 내용 |
|------|----------|
| `app/api/routes/analysis.py` | 인메모리 → Redis 브로커 통신 |
| `app/main.py` | lifespan에서 engine 관련 초기화 제거 (API 전용화) |
| `docker-compose.yml` | 3개 서비스 추가, MCP Dockerfile 경로 수정 |
| `pyproject.toml` | 빌드 백엔드 추가 (setuptools) |

---

## 의존성 그래프

```
Step 1 (Dockerfile) ──→ Step 6 (docker-compose)
                              ↓
Step 2 (redis_broker) ──→ Step 3 (engine worker)
                    └──→ Step 4 (API 리팩토링) ──→ Step 7 (빌드/검증)
                              ↑
Step 5 (pipeline) ────────────┘
```

병렬 가능: Step 2 + Step 5 동시 진행
순차 필수: Step 2 → Step 3, Step 2 → Step 4

---

## 성공 기준

| 기준 | 측정 방법 |
|------|----------|
| Docker 빌드 성공 | `docker-compose build` exit code 0 |
| 14개 서비스 기동 | `docker-compose ps` 전부 Up/healthy |
| API 응답 | `curl localhost:8000/health` → 200 OK |
| Engine 연결 | Engine 로그에 "Redis Stream 구독 시작" |
| MCP 서버 연결 | 9개 서버 `/health` 응답 |
| 기존 테스트 유지 | `pytest tests/` 71개 PASS |
