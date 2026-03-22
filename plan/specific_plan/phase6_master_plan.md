# Phase 6 Master Plan — 버그 수정, 서비스 분리 & E2E 테스트

> **작성일:** 2026-03-22
> **목표:** 상용화를 위한 첫 번째 관문 — "실제로 돌아가는 시스템" 만들기

---

## 서비스 분리 상세 설계

### 현재 구조 (모놀리식)

```
marketscope/app/
├── main.py              ← FastAPI 앱 (모든 기능 집중)
├── api/                 ← HTTP 라우트
├── agents/              ← 15개 에이전트
├── graph/               ← LangGraph DAG
├── services/            ← 분석 서비스
├── tools/               ← MCP Client
├── llm/                 ← LLM Provider
├── models/              ← 데이터 모델
├── collectors/          ← 데이터 수집
├── preprocessors/       ← 전처리
├── scheduler/           ← APScheduler
├── cache/               ← Redis
├── db/                  ← PostgreSQL ORM
├── memory/              ← LightRAG (stub)
├── monitoring/          ← Prometheus/Langfuse
└── mcp_servers/         ← 9개 MCP 서버 (이미 분리됨)
```

### 목표 구조 (서비스 분리)

```
marketscope/
├── services/
│   ├── api/                      ← marketscope-api 서비스
│   │   ├── Dockerfile
│   │   ├── main.py               ← FastAPI 앱 (API 전용)
│   │   ├── routes/
│   │   │   ├── analysis.py       ← POST/GET/SSE 엔드포인트
│   │   │   └── health.py         ← Health check
│   │   ├── redis_store.py        ← Redis 기반 분석 상태 관리
│   │   └── deps.py               ← FastAPI 의존성
│   │
│   ├── engine/                   ← marketscope-engine 서비스
│   │   ├── Dockerfile
│   │   ├── main.py               ← Engine 워커 (Redis Queue 수신)
│   │   ├── agents/               ← 15개 에이전트 (이동)
│   │   ├── graph/                ← LangGraph DAG (이동)
│   │   ├── tools/                ← MCP Client Router (이동)
│   │   ├── llm/                  ← LLM Provider (이동)
│   │   └── models/               ← 상태/출력 모델 (이동)
│   │
│   └── pipeline/                 ← marketscope-pipeline 서비스
│       ├── Dockerfile
│       ├── main.py               ← 스케줄러 시작점
│       ├── collectors/           ← 데이터 수집기 (이동)
│       ├── preprocessors/        ← 전처리기 (이동)
│       ├── scheduler/            ← APScheduler (이동)
│       └── db/                   ← ORM 모델 (이동)
│
├── shared/                       ← 공유 라이브러리
│   ├── config.py                 ← 설정 (공통)
│   ├── constants.py              ← 상수 (공통)
│   ├── exceptions.py             ← 예외 (공통)
│   ├── cache/                    ← Redis 클라이언트 (공통)
│   ├── models/                   ← Pydantic 모델 (공통)
│   ├── monitoring/               ← 메트릭/로깅 (공통)
│   └── logging_config.py         ← structlog 설정 (공통)
│
├── mcp_servers/                  ← 9개 MCP 서버 (기존 유지)
│   ├── public_data/
│   ├── maps/
│   ├── real_estate/
│   ├── news/
│   ├── regulatory/
│   ├── finance/
│   ├── database/
│   ├── google_maps/
│   └── naver_maps/
│
├── tests/
│   ├── unit/                     ← 기존 단위 테스트
│   ├── integration/              ← 기존 통합 테스트
│   └── e2e/                      ← 신규 E2E 테스트
│       ├── conftest.py
│       ├── test_happy_path.py
│       └── test_error_scenarios.py
│
├── docker-compose.yml            ← 전체 서비스 (14개)
├── docker-compose.test.yml       ← 테스트용 오버라이드
└── Makefile                      ← 빌드/테스트 편의 명령
```

---

## 서비스 간 통신 프로토콜

### API → Engine (분석 요청)

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

### Engine → API (진행률 업데이트)

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

### Engine → API (최종 결과)

```
Redis Hash: "analysis:result:{request_id}"

Fields:
- status: "completed" | "failed"
- result: JSON string (전체 분석 결과)
- completed_at: ISO timestamp
- duration_seconds: float
```

---

## Sprint 상세 계획

### S1: Critical 버그 수정 (0.5일)

| Step | 작업 | 파일 | 예상 시간 |
|------|------|------|----------|
| S1-1 | debate_check revenue 필드명 수정 | `app/graph/nodes.py` | 15분 |
| S1-2 | 스케줄러 job 파라미터 수정 | `app/scheduler/jobs.py` | 30분 |
| S1-3 | health.py Redis import 수정 | `app/api/routes/health.py` | 10분 |
| S1-4 | quality_checker 컬럼명 수정 | `app/monitoring/quality_checker.py` | 15분 |
| S1-5 | 기존 71개 테스트 통과 확인 | `pytest tests/` | 10분 |

### S2: 서비스 분리 + Docker (2~3일)

| Step | 작업 | 산출물 | 예상 시간 |
|------|------|--------|----------|
| S2-1 | shared/ 공유 모듈 추출 | `shared/` 디렉토리 | 3시간 |
| S2-2 | API 서비스 분리 | `services/api/` | 3시간 |
| S2-3 | Engine 서비스 분리 | `services/engine/` | 4시간 |
| S2-4 | Pipeline 서비스 분리 | `services/pipeline/` | 2시간 |
| S2-5 | Redis 기반 서비스 간 통신 구현 | `redis_store.py`, engine `main.py` | 3시간 |
| S2-6 | Dockerfile 4개 작성 | `Dockerfile.*` | 2시간 |
| S2-7 | docker-compose.yml 재구성 | `docker-compose.yml` | 2시간 |
| S2-8 | `docker-compose build` 성공 확인 | 빌드 로그 | 1시간 |
| S2-9 | `docker-compose up` 전체 서비스 기동 확인 | 14개 서비스 healthy | 1시간 |

### S3: 서비스별 테스트 (2일)

| Step | 작업 | 검증 항목 | 예상 시간 |
|------|------|----------|----------|
| S3-1 | API 서비스 테스트 | health, POST, GET, SSE | 3시간 |
| S3-2 | Engine 서비스 테스트 | DAG 빌드, 에이전트 실행 | 4시간 |
| S3-3 | MCP 서버 테스트 (9개) | health, tool call | 3시간 |
| S3-4 | Pipeline 서비스 테스트 | migration, collector | 2시간 |
| S3-5 | 서비스 간 통신 테스트 | Redis Stream/Pub/Sub | 2시간 |

### S4: E2E 테스트 (2일)

| Step | 작업 | 검증 항목 | 예상 시간 |
|------|------|----------|----------|
| S4-1 | 인프라 기동 + 전체 healthy 확인 | 14개 서비스 | 1시간 |
| S4-2 | Happy Path: 강남역 카페 분석 | 결과 반환 | 2시간 |
| S4-3 | Happy Path: 홍대 음식점 분석 | 결과 반환 | 1시간 |
| S4-4 | 결과 품질 검증 | 점수/등급/추천 | 2시간 |
| S4-5 | 에러 시나리오 테스트 | MCP 다운, 타임아웃 | 2시간 |
| S4-6 | 성능 측정 | 소요 시간, LLM 호출 횟수, 비용 | 2시간 |
| S4-7 | 검증 보고서 작성 | 최종 결과 문서화 | 1시간 |

---

## 리스크 및 대응

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| 서비스 분리 시 import 순환 참조 | 높음 | 중간 | shared/ 모듈로 공통 코드 추출 |
| MCP 서버 외부 API 장애 | 중간 | 높음 | stub/fallback 데이터로 E2E 테스트 우선 |
| LLM 비용 초과 | 낮음 | 중간 | Quick 모드 (4 에이전트)로 테스트 |
| Redis 통신 지연 | 낮음 | 낮음 | 타임아웃 설정 + 재시도 로직 |
| Docker 빌드 실패 | 중간 | 높음 | 단계별 빌드 검증 |

---

## 추가 고려사항

### 서비스 분리 원칙

1. **shared/ 모듈**: config, models, exceptions 등 모든 서비스가 참조하는 코드
2. **순환 참조 금지**: shared → (어떤 서비스도 import 안 함)
3. **서비스 독립성**: 각 서비스는 자체 `main.py`로 독립 실행 가능
4. **환경변수 분리**: 각 서비스는 필요한 환경변수만 사용

### 테스트 전략

1. **S3 (서비스 테스트)**: 각 서비스를 개별 Docker 컨테이너로 올려서 테스트
2. **S4 (E2E 테스트)**: 전체 docker-compose로 올려서 curl/httpx로 테스트
3. **Mock 전략**: MCP 서버의 외부 API는 가능하면 실제 호출, 불가능하면 mock
