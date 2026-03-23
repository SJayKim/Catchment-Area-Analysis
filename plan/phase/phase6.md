# Phase 6 구현 계획 — 버그 수정, 서비스 분리 & E2E 테스트

> **작성일:** 2026-03-22
> **선행 조건:** Phase 5 완료 (기능 테스트 & 버그 수정)
> **목표:** Critical 버그 수정, Docker 배포 기준 서비스 분리, 전체 파이프라인 E2E 테스트

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

| 스프린트 | 핵심 목표 | 예상 소요 |
|---------|----------|----------|
| **S1** | Critical 버그 4건 수정 | 0.5일 |
| **S2** | 서비스 분리 + Dockerfile + docker-compose 재구성 | 2~3일 |
| **S3** | 서비스별 단위/통합 테스트 | 2일 |
| **S4** | E2E 테스트 (전체 파이프라인 검증) | 2일 |

---

## S1: Critical 버그 수정

> 런타임 크래시를 유발하는 4건. 이것 없이는 어떤 테스트도 불가능.

### S1-1: debate_check_node Revenue 필드명 불일치

- **위치:** `app/graph/nodes.py` debate_check_node
- **문제:** `estimated_revenue`, `revenue_lower_bound`, `revenue_upper_bound` 참조
- **실제 모델:** `estimated_monthly_revenue`, `revenue_range.min_value`, `revenue_range.max_value`
- **수정:** 필드명을 RevenueAnalysis 모델에 맞게 변경

### S1-2: 스케줄러 Collector 호출 파라미터 누락

- **위치:** `app/scheduler/jobs.py` 6개 job 함수
- **문제:** `collect_*()` 메서드를 필수 파라미터 없이 호출 → TypeError
- **수정:** 스케줄러 job에서 district 목록 순회하며 올바른 파라미터 전달

### S1-3: Health 엔드포인트 Redis import 오류

- **위치:** `app/api/routes/health.py` line 126
- **문제:** `from app.cache.redis_client import _redis_client` — 존재하지 않는 변수
- **수정:** `from app.cache.redis_client import health_check` 사용

### S1-4: Quality Checker 잘못된 DB 컬럼 참조

- **위치:** `app/monitoring/quality_checker.py`
- **문제:** `daily_boarding` → 실제 `boarding_total` 또는 `daily_avg_boarding`
- **수정:** ORM 모델 컬럼명에 맞게 수정

---

## S2: 서비스 분리 + Docker 인프라

> 모놀리식 `app/`을 3개 서비스로 분리하여 독립 배포/테스트 가능하게 구성.

### 서비스 아키텍처

```
┌─────────────────────────────────────────────────┐
│              Docker Compose Network              │
├─────────────────────────────────────────────────┤
│                                                  │
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

### S2-1: 서비스 분리 설계

**marketscope-api** (API Gateway):
- `app/api/` — HTTP 라우트, SSE 스트리밍
- `app/main.py` — FastAPI 앱 (단순화)
- 분석 상태 저장소를 in-memory → Redis로 이전
- 분석 요청을 Redis Queue로 engine에 전달

**marketscope-engine** (분석 엔진):
- `app/agents/` — 15개 에이전트
- `app/graph/` — LangGraph DAG (20노드)
- `app/tools/` — MCP Client Router
- `app/llm/` — LLM Provider
- `app/models/` — 상태/출력 모델
- Redis Queue에서 작업 수신, 결과를 Redis로 발행

**marketscope-pipeline** (데이터 파이프라인):
- `app/collectors/` — 데이터 수집기
- `app/preprocessors/` — 전처리기
- `app/scheduler/` — APScheduler 8개 job
- `app/db/` — ORM 모델, Repository
- `app/monitoring/quality_checker.py` — 데이터 품질 체크

### S2-2: Dockerfile 작성

- `Dockerfile.api` — API 서비스용
- `Dockerfile.engine` — 분석 엔진용
- `Dockerfile.mcp` — MCP 서버 공용 (기존 9개 서버)
- `Dockerfile.pipeline` — 데이터 파이프라인용
- 공통 base image 활용 (Python 3.11-slim)

### S2-3: docker-compose.yml 재구성

- 기존 11개 서비스 → 14개 서비스로 확장
- 서비스 간 의존성 (depends_on + healthcheck) 명시
- 네트워크 분리: `frontend`, `backend`, `data`
- 볼륨 관리: DB 데이터, Redis 데이터, 로그

### S2-4: Redis 기반 서비스 간 통신

- 분석 요청: API → Redis Stream → Engine
- 진행률 업데이트: Engine → Redis Pub/Sub → API (SSE)
- 분석 결과: Engine → Redis Hash → API
- 기존 in-memory `_analysis_store` 제거

---

## S3: 서비스별 테스트

> 각 서비스가 독립적으로 동작하는지 검증.

### S3-1: API 서비스 테스트

- Health 엔드포인트 (`/health`, `/health/ready`) 정상 응답
- 분석 요청 제출 → Redis Queue에 메시지 발행 확인
- SSE 스트리밍 연결 유지 및 heartbeat 확인
- 분석 결과 조회 (Redis에서 읽기)

### S3-2: Engine 서비스 테스트

- LangGraph DAG 빌드 검증 (20노드)
- 단일 에이전트 실행 테스트 (MCP mock)
- 전체 워크플로우 실행 (MCP mock → 결과 반환)
- Redis Queue에서 작업 수신 → 처리 → 결과 발행

### S3-3: MCP 서버 테스트

- 각 서버 `/health` 응답 확인 (9개)
- 주요 도구 호출 테스트 (실제 API 키 필요한 서버)
- 도구 목록 조회 (`/tools/list`)

### S3-4: Pipeline 서비스 테스트

- DB 마이그레이션 (Alembic upgrade)
- Collector 단위 테스트 (API mock)
- 스케줄러 job 등록 확인

---

## S4: E2E 테스트

> 실제 사용자 시나리오: 질문 입력 → 분석 실행 → 결과 확인.

### S4-1: 인프라 기동 및 검증

```bash
docker-compose up -d
# 모든 서비스 healthy 확인
docker-compose ps
```

### S4-2: Happy Path 테스트

```bash
# 1. 분석 요청
curl -X POST http://localhost:8000/api/v1/analysis \
  -H "Content-Type: application/json" \
  -d '{"query": "강남역 근처 카페 창업 분석해줘"}'

# 2. SSE 스트리밍으로 진행률 확인
curl -N http://localhost:8000/api/v1/analysis/{request_id}/stream

# 3. 결과 조회
curl http://localhost:8000/api/v1/analysis/{request_id}
```

### S4-3: 결과 품질 검증

- 전체 파이프라인 소요 시간 측정
- 에이전트별 결과 존재 여부 (population, competition, revenue, location)
- confidence_score 범위 (0.0~1.0)
- final_judgment 점수/등급/추천 존재 여부
- narrative 리포트 텍스트 품질

### S4-4: 에러 시나리오 테스트

- 잘못된 location 입력 시 graceful 처리
- MCP 서버 일부 다운 시 fallback 동작
- LLM 타임아웃 시 재시도 로직

---

## 파일 변경 요약

| 파일 | 변경 사항 |
|------|----------|
| `app/graph/nodes.py` | debate_check_node revenue 필드명 수정 |
| `app/scheduler/jobs.py` | 6개 job 파라미터 수정 |
| `app/api/routes/health.py` | Redis import 수정 |
| `app/monitoring/quality_checker.py` | DB 컬럼명 수정 |
| `Dockerfile.api` | 신규 생성 |
| `Dockerfile.engine` | 신규 생성 |
| `Dockerfile.mcp` | 신규 생성 |
| `Dockerfile.pipeline` | 신규 생성 |
| `docker-compose.yml` | 서비스 재구성 (14개) |
| `app/main.py` | API 전용으로 단순화 |
| `app/services/analysis_service.py` | Redis Queue 통신으로 변경 |
| `tests/e2e/` | 신규 생성 (E2E 테스트) |

---

## 의존성 그래프

```
S1-1 (debate 필드) ──┐
S1-2 (스케줄러)     ──┤
S1-3 (health)      ──┼──→ S2 (서비스 분리) ──→ S3 (서비스 테스트) ──→ S4 (E2E)
S1-4 (quality)     ──┘
```

---

## 성공 기준

| 기준 | 목표 |
|------|------|
| Critical 버그 | 4건 전부 수정, 기존 71개 테스트 통과 유지 |
| Docker 빌드 | `docker-compose build` 성공 |
| 서비스 기동 | 14개 서비스 전부 healthy |
| E2E Happy Path | "강남역 카페" 분석 요청 → 최종 리포트 반환 |
| 분석 소요 시간 | Standard 모드 기준 120초 이내 |
| 결과 품질 | 4개 Phase 1 에이전트 결과 + 점수/등급/추천 포함 |
