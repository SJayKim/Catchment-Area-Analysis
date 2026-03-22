# MarketScope AI — Phase 6 진행 현황 (2026-03-22)

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

### 문서 작성 ✅

| 파일 | 내용 |
|------|------|
| `document/test_environment_guide.md` | 테스트 환경 구축 가이드 (10개 섹션) |
| `plan/phase/phase6.md` | Phase 6 마스터 계획 |
| `plan/specific_plan/phase6_master_plan.md` | 서비스 분리 상세 설계 |
| `plan/specific_plan/phase6_s2_plan.md` | S2 실행 계획 (7 Step) |
| `plan/specific_plan/phase6_s2_verify_plan.md` | S2 검증 계획 (7 Step) |
| `plan/specific_plan/phase6_checklist.md` | 전체 체크리스트 |

---

## 3. 현재 코드 상태

### 아키텍처 (변경 후)

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

### 파일 구조 (Phase 6 변경분 표시)

```
marketscope/
├── Dockerfile                    # [신규] 공용 Docker 이미지
├── .dockerignore                 # [신규]
├── docker-compose.yml            # [수정] 14개 서비스 (api, engine, pipeline 추가)
├── pyproject.toml                # [수정] build-system 추가
│
├── app/
│   ├── main.py                   # [수정] broker init/close, MCP init 제거
│   │
│   ├── api/routes/
│   │   ├── analysis.py           # [수정] 인메모리 → Redis 브로커
│   │   └── health.py             # [수정] import 오류 2건 수정
│   │
│   ├── engine/                   # [신규] 분석 엔진 패키지
│   │   ├── __init__.py
│   │   ├── __main__.py           #   python -m app.engine
│   │   ├── worker.py             #   EngineWorker (Redis Stream → LangGraph)
│   │   └── redis_broker.py       #   RedisBroker (Stream/Pub/Sub/Hash)
│   │
│   ├── pipeline/                 # [신규] 스케줄러 패키지
│   │   ├── __init__.py
│   │   ├── __main__.py           #   python -m app.pipeline
│   │   └── main.py               #   APScheduler 독립 실행
│   │
│   ├── graph/nodes.py            # [수정] debate_check_node revenue 필드
│   ├── scheduler/jobs.py         # [수정] 6개 job 파라미터 수정
│   └── monitoring/
│       └── quality_checker.py    # [수정] DB 컬럼명 4건
│
├── tests/
│   ├── unit/
│   │   ├── test_redis_broker.py      # [신규] 13개 테스트
│   │   ├── test_analysis_routes.py   # [신규] 8개 테스트
│   │   ├── test_engine_worker.py     # [신규] 4개 테스트
│   │   └── test_pipeline_main.py     # [신규] 2개 테스트
│   └── ...
│
└── document/
    └── test_environment_guide.md # [신규] 테스트 환경 가이드
```

---

## 4. 남은 작업 — S3: 서비스별 테스트

> **전제 조건:** 호스트(WSL2)에서 Docker Compose 기동 필요

### S3-Step1: Docker 빌드 및 인프라 기동

```bash
cd marketscope/
docker compose build
docker compose up -d postgres redis
# healthcheck 통과 대기
docker compose run --rm marketscope-api alembic upgrade head
docker compose up -d
docker compose ps  # 14개 서비스 확인
```

### S3-Step2: API 서비스 테스트

| 테스트 | 명령어 | 기대 결과 |
|--------|--------|----------|
| Health | `curl localhost:8000/api/v1/health` | 200 OK |
| Readiness | `curl localhost:8000/api/v1/health/ready` | DB, Redis 상태 |
| 분석 요청 | `POST /api/v1/analysis` | 202 + request_id |
| Stream 확인 | `curl -N localhost:8000/api/v1/analysis/{id}/stream` | SSE 이벤트 |
| 결과 조회 | `GET /api/v1/analysis/{id}` | status + result |

### S3-Step3: Engine 서비스 테스트

| 테스트 | 확인 방법 | 기대 결과 |
|--------|----------|----------|
| 기동 확인 | `docker compose logs marketscope-engine` | "Redis Stream 구독 시작" |
| Stream 수신 | API에서 분석 요청 후 engine 로그 | "분석 요청 수신: {id}" |
| MCP 연결 | engine 로그 | "MCP Router 초기화 완료" |
| 결과 저장 | `redis-cli GET analysis:result:{id}` | JSON 결과 |

### S3-Step4: MCP 서버 테스트 (9개)

```bash
for port in 5100 5101 5102 5103 5104 5105 5106 5107 5108; do
  echo -n "MCP :$port → "
  curl -s http://localhost:$port/health | head -c 80
  echo
done
```

### S3-Step5: Pipeline 서비스 테스트

| 테스트 | 확인 방법 | 기대 결과 |
|--------|----------|----------|
| 기동 확인 | `docker compose logs marketscope-pipeline` | "스케줄러 시작됨" |
| Job 등록 | pipeline 로그 | "스케줄 등록 완료: 8개 작업" |

---

## 5. 남은 작업 — S4: E2E 테스트

> **전제 조건:** S3 통과 + `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` 설정

### S4-Step1: Happy Path — 강남역 카페 분석

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

### S4-Step2: 에러 시나리오

| 시나리오 | 입력 | 기대 |
|---------|------|------|
| 빈 query | `{"query": "a"}` | 422 Validation Error |
| 없는 ID 조회 | `GET /analysis/fake-id` | 404 ANALYSIS_NOT_FOUND |
| MCP 서버 다운 | `docker compose stop mcp-news` 후 분석 | graceful degradation |

### S4-Step3: 성능 측정

- Standard 분석 소요 시간
- LLM 호출 횟수 / 토큰 사용량
- 분석 1건당 예상 비용

### S4-Step4: 검증 보고서

- E2E 테스트 결과 요약
- 발견된 이슈 및 해결 방안
- 다음 단계 (Phase 7: LightRAG DB 구축) 제안

---

## 6. 알려진 이슈 및 주의사항

| # | 이슈 | 영향 | 대응 |
|---|------|------|------|
| 1 | Docker-in-Docker 불가 | 현 개발 컨테이너에서 docker compose 실행 불가 | 호스트(WSL2) 터미널에서 실행 필요 |
| 2 | `tzdata` 미설치 | APScheduler `Asia/Seoul` 타임존 에러 | Dockerfile에 `tzdata` 추가 또는 UTC 사용 |
| 3 | MCP 서버 내부 URL | Docker 내부에서 localhost → 컨테이너명 | docker-compose.yml에 `MCP_SERVERS` 환경변수 추가 완료 |
| 4 | conftest.py revenue 필드 | `sample_state_with_results` fixture에 구 필드명 잔존 | 테스트에서 직접 override하므로 현재 문제 없음 (정리 권장) |

---

## 7. 참고 문서

| 문서 | 위치 |
|------|------|
| 테스트 환경 가이드 | `document/test_environment_guide.md` |
| Phase 6 마스터 계획 | `plan/phase/phase6.md` |
| S2 실행 계획 | `plan/specific_plan/phase6_s2_plan.md` |
| S2 검증 계획 | `plan/specific_plan/phase6_s2_verify_plan.md` |
| 전체 체크리스트 | `plan/specific_plan/phase6_checklist.md` |
| 이전 구현 현황 (Phase 5까지) | `plan/status/2026-03-21_implementation_status.md` |
