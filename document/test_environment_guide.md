# MarketScope AI — 테스트 환경 구축 가이드

> **작성일:** 2026-03-22
> **대상:** Phase 6 S3(서비스별 테스트) / S4(E2E 테스트) 실행을 위한 환경 구축
> **전제:** S1(버그 수정) + S2(서비스 분리) 코드 작성 완료, 98개 단위 테스트 PASS

---

## 1. 전체 아키텍처 (Docker Compose 기준)

```
┌──────────────────────────────────────────────────────────────────┐
│                      Host (WSL2 / Linux / macOS)                  │
│                                                                   │
│  ┌─ Infrastructure ──────────────────────────────────────────┐   │
│  │  postgres (PostGIS 15-3.4)    :5432                       │   │
│  │  redis (7-alpine)              :6379                       │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─ Application Services ────────────────────────────────────┐   │
│  │  marketscope-api      :8000   (FastAPI + Uvicorn)         │   │
│  │  marketscope-engine           (Redis Stream → LangGraph)  │   │
│  │  marketscope-pipeline         (APScheduler 8 jobs)        │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─ MCP Servers (9개) ───────────────────────────────────────┐   │
│  │  public_data  :5100    maps         :5101                  │   │
│  │  real_estate  :5102    news         :5103                  │   │
│  │  regulatory   :5104    finance      :5105                  │   │
│  │  database     :5106    google_maps  :5107                  │   │
│  │  naver_maps   :5108                                        │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─ Monitoring (선택사항) ────────────────────────────────────┐   │
│  │  prometheus  :9090    grafana  :3001    loki  :3100        │   │
│  └───────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

**총 14개 서비스** (모니터링 제외)

---

## 2. 사전 요구사항

### 호스트 환경

| 항목 | 최소 요구 | 권장 |
|------|----------|------|
| OS | WSL2 / Linux / macOS | WSL2 Ubuntu 22.04+ |
| Docker | 24.0+ | 최신 |
| Docker Compose | v2.20+ | 최신 |
| RAM | 8GB | 16GB (LLM 에이전트 동시 실행) |
| 디스크 | 10GB | 20GB |

### 확인 명령어

```bash
docker --version          # Docker 24.0+
docker compose version    # v2.20+
```

---

## 3. 환경 변수 설정

### 3.1 .env 파일 생성

```bash
cd marketscope/
cp .env.example .env
```

### 3.2 필수 API 키 (반드시 설정)

| 변수 | 용도 | 발급처 |
|------|------|--------|
| `ANTHROPIC_API_KEY` | Claude 모델 (Commander, Financial, Risk, Critic, Judge) | https://console.anthropic.com |
| `GOOGLE_API_KEY` | Gemini 모델 (Population, Revenue, Competition 등 대부분 에이전트) | https://aistudio.google.com |

> **주의:** 이 두 키 없이는 E2E 분석이 실행 불가합니다.

### 3.3 Docker Compose 환경에서 호스트명 변경

`.env` 파일에서 `localhost` → Docker 서비스명으로 변경:

```env
# ── 인프라 ──
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=marketscope
POSTGRES_USER=marketscope_user
POSTGRES_PASSWORD=marketscope_dev_pw

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# ── LLM API 키 (필수) ──
ANTHROPIC_API_KEY=sk-ant-실제키입력
GOOGLE_API_KEY=AIza-실제키입력

# ── LLM 모델 설정 ──
LLM_MODEL_COMMANDER=claude-sonnet-4-6-20250514
LLM_MODEL_POPULATION=gemini/gemini-2.5-flash
LLM_MODEL_REVENUE=gemini/gemini-2.5-flash
LLM_MODEL_COMPETITION=gemini/gemini-2.5-flash
LLM_MODEL_LOCATION=gemini/gemini-2.5-flash
LLM_MODEL_NARRATIVE=gemini/gemini-2.5-flash
LLM_MODEL_VISUALIZATION=gemini/gemini-2.5-flash

# ── MCP 서버 URL (Docker 네트워크 내부) ──
MCP_TRANSPORT=sse
MCP_TIMEOUT=30
```

### 3.4 MCP 서버 URL 설정

Docker Compose 내부에서는 컨테이너명으로 통신합니다.
`app/config.py`의 기본값이 `localhost`이므로, Docker 환경에서는 환경변수로 오버라이드 필요:

```env
# docker-compose.yml의 marketscope-api, marketscope-engine 서비스에 추가
MCP_SERVERS='{"public_data":"http://mcp-public-data:5100","maps":"http://mcp-maps:5101","real_estate":"http://mcp-real-estate:5102","news":"http://mcp-news:5103","regulatory":"http://mcp-regulatory:5104","finance":"http://mcp-finance:5105","database":"http://mcp-database:5106","google_maps":"http://mcp-google-maps:5107","naver_maps":"http://mcp-naver-maps:5108"}'
```

> 또는 `docker-compose.yml`의 `environment` 섹션에 직접 추가

### 3.5 데이터 수집 API 키 (선택)

Pipeline 서비스의 데이터 수집에 필요합니다. E2E 분석 테스트 자체는 없어도 동작하지만, 실제 데이터가 없으면 분석 품질이 제한됩니다.

| 변수 | 용도 | 발급처 |
|------|------|--------|
| `DATA_API_SEOUL_OPEN_DATA_KEY` | 서울 생활인구, 지하철, 카드매출 | https://data.seoul.go.kr |
| `DATA_API_PUBLIC_DATA_KEY` | SEMAS 상권분석 (유동인구, 매출, 점포) | https://www.data.go.kr |
| `DATA_API_KAKAO_REST_KEY` | 카카오 지도/검색 | https://developers.kakao.com |
| `DATA_API_NAVER_CLIENT_ID` | 네이버 검색 | https://developers.naver.com |
| `DATA_API_NAVER_CLIENT_SECRET` | 네이버 검색 | https://developers.naver.com |
| `DATA_API_GOOGLE_MAPS_KEY` | Google Maps/Places | https://console.cloud.google.com |

### 3.6 전체 .env 템플릿 (Docker Compose용)

```env
# ── Application ──
APP_NAME=MarketScope AI
APP_ENV=development
APP_DEBUG=true
APP_VERSION=1.0.0
APP_HOST=0.0.0.0
APP_PORT=8000
APP_LOG_LEVEL=DEBUG
APP_SECRET_KEY=your-random-secret-key-at-least-32-chars

# ── LLM (필수) ──
ANTHROPIC_API_KEY=sk-ant-실제키
GOOGLE_API_KEY=AIza-실제키

# ── Database ──
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=marketscope
POSTGRES_USER=marketscope_user
POSTGRES_PASSWORD=marketscope_dev_pw

# ── Redis ──
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# ── MCP ──
MCP_TRANSPORT=sse
MCP_TIMEOUT=30

# ── Analysis ──
ANALYSIS_MAX_PARALLEL_AGENTS=4
ANALYSIS_AGENT_TIMEOUT=60
ANALYSIS_TOTAL_TIMEOUT=300

# ── Data API Keys (선택) ──
DATA_API_SEOUL_OPEN_DATA_KEY=
DATA_API_PUBLIC_DATA_KEY=
DATA_API_KAKAO_REST_KEY=
DATA_API_NAVER_CLIENT_ID=
DATA_API_NAVER_CLIENT_SECRET=
DATA_API_GOOGLE_MAPS_KEY=

# ── Monitoring (선택) ──
LANGFUSE_ENABLED=false

# ── Phase 1 Geo ──
PHASE1_SEOUL_ONLY=true
PHASE1_ALLOWED_DISTRICTS=강남,홍대,이태원,건대,신촌,종로,명동,여의도,성수,잠실
```

---

## 4. 빌드 및 기동

### 4.1 Docker 이미지 빌드

```bash
cd marketscope/
docker compose build
```

> 단일 이미지(`marketscope:latest`)가 빌드되며, 서비스별로 CMD만 다름

### 4.2 인프라 우선 기동

```bash
# 1단계: DB + Redis 먼저 (healthcheck 통과 대기)
docker compose up -d postgres redis
docker compose ps   # healthy 확인
```

### 4.3 DB 마이그레이션

```bash
# 컨테이너 내에서 Alembic 실행
docker compose run --rm marketscope-api alembic upgrade head
```

> 10개 테이블 + PostGIS 확장 생성됨

### 4.4 전체 서비스 기동

```bash
# 2단계: 전체 기동
docker compose up -d

# 상태 확인
docker compose ps
```

### 4.5 기동 확인

```bash
# API 헬스체크
curl http://localhost:8000/api/v1/health

# API readiness (DB, Redis 연결 상태)
curl http://localhost:8000/api/v1/health/ready

# MCP 서버 확인 (9개)
for port in 5100 5101 5102 5103 5104 5105 5106 5107 5108; do
  echo -n "MCP :$port → "
  curl -s http://localhost:$port/health | head -c 50
  echo
done

# Engine 로그 확인
docker compose logs marketscope-engine --tail=20

# Pipeline 로그 확인
docker compose logs marketscope-pipeline --tail=20
```

---

## 5. 포트 사용 현황

| 포트 | 서비스 | 용도 |
|------|--------|------|
| 5432 | postgres | PostgreSQL + PostGIS |
| 6379 | redis | 캐시 + 메시지 브로커 |
| 8000 | marketscope-api | FastAPI REST API |
| 5100 | mcp-public-data | 공공데이터 MCP |
| 5101 | mcp-maps | 지도 MCP |
| 5102 | mcp-real-estate | 부동산 MCP |
| 5103 | mcp-news | 뉴스 MCP |
| 5104 | mcp-regulatory | 규제/인허가 MCP |
| 5105 | mcp-finance | 금융/재무 MCP |
| 5106 | mcp-database | DB 쿼리 MCP |
| 5107 | mcp-google-maps | Google Maps MCP |
| 5108 | mcp-naver-maps | Naver Maps MCP |
| 9090 | prometheus | 메트릭 수집 (선택) |
| 3001 | grafana | 대시보드 (선택) |
| 3100 | loki | 로그 수집 (선택) |

---

## 6. 테스트 실행 가이드

### 6.1 단위 테스트 (Docker 불필요)

컨테이너 내부 또는 로컬 Python 환경에서 실행 가능:

```bash
cd marketscope/
pip install -e ".[dev]"
pytest tests/ -v
# 98개 PASS (약 2.5초)
```

### 6.2 S3: 서비스별 테스트 (Docker 필요)

전체 서비스 기동 후 실행:

```bash
# API 테스트
curl http://localhost:8000/api/v1/health
curl -X POST http://localhost:8000/api/v1/analysis \
  -H "Content-Type: application/json" \
  -d '{"query": "강남역 카페 창업 분석"}'

# Engine 연결 확인
docker compose logs marketscope-engine | grep "Redis Stream"

# MCP 서버 확인
curl http://localhost:5100/health
curl http://localhost:5105/health
```

### 6.3 S4: E2E 테스트 (Docker + API 키 필수)

```bash
# 1. 분석 요청
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/analysis \
  -H "Content-Type: application/json" \
  -d '{"query": "강남역 카페 창업 분석", "depth": "standard"}')
echo $RESPONSE

# request_id 추출
REQUEST_ID=$(echo $RESPONSE | python -c "import sys,json; print(json.load(sys.stdin)['request_id'])")

# 2. SSE 스트리밍 (진행률 실시간 확인)
curl -N http://localhost:8000/api/v1/analysis/$REQUEST_ID/stream

# 3. 결과 조회
curl http://localhost:8000/api/v1/analysis/$REQUEST_ID
```

**E2E 성공 기준:**
- `POST` → 202 Accepted + `request_id` 반환
- SSE 스트림에 `processing` → 각 에이전트 진행률 → `done` 순서로 이벤트 수신
- `GET` → `status: completed` + `result` 객체에 분석 결과 포함
- 소요 시간: standard 기준 120초 이내

---

## 7. 서비스 간 통신 흐름

```
사용자 → POST /api/v1/analysis
           │
    [marketscope-api]
           │ Redis Stream XADD "analysis:requests"
           ▼
    [Redis]
           │ XREADGROUP (blocking)
           ▼
    [marketscope-engine]
           │ AnalysisService.run_analysis()
           │   └─ LangGraph DAG (20노드)
           │       └─ MCP Client → 9개 MCP 서버 (HTTP)
           │
           │ Redis Pub/Sub PUBLISH "analysis:progress:{id}"
           ▼
    [Redis]
           │ SUBSCRIBE
           ▼
    [marketscope-api] → SSE 스트리밍 → 사용자

    완료 시: Redis Hash SET "analysis:result:{id}"
```

---

## 8. 트러블슈팅

### 서비스가 기동하지 않을 때

```bash
# 전체 로그 확인
docker compose logs --tail=50

# 특정 서비스 로그
docker compose logs marketscope-api --tail=30
docker compose logs marketscope-engine --tail=30
```

### DB 연결 실패

```bash
# postgres healthcheck 확인
docker compose exec postgres pg_isready -U marketscope_user -d marketscope

# .env의 POSTGRES_HOST가 'postgres'인지 확인 (localhost 아님)
```

### Redis 연결 실패

```bash
# redis healthcheck 확인
docker compose exec redis redis-cli ping

# .env의 REDIS_HOST가 'redis'인지 확인
```

### MCP 서버 연결 실패

```bash
# Engine 로그에서 MCP 연결 확인
docker compose logs marketscope-engine | grep -i "mcp"

# MCP 서버 URL이 Docker 내부 호스트명인지 확인
# localhost → mcp-public-data, mcp-maps 등
```

### LLM 호출 실패

```bash
# API 키 확인
docker compose exec marketscope-engine env | grep -E "ANTHROPIC|GOOGLE"

# litellm 로그
docker compose logs marketscope-engine | grep -i "litellm\|llm\|api_key"
```

### 모니터링 스택 추가 (선택)

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
# Grafana: http://localhost:3001 (admin/admin)
# Prometheus: http://localhost:9090
```

---

## 9. 서비스 중지/정리

```bash
# 전체 중지
docker compose down

# 볼륨 포함 정리 (DB 데이터 삭제됨)
docker compose down -v

# 이미지까지 삭제
docker compose down -v --rmi all
```

---

## 10. 체크리스트 — 환경 구축 완료 확인

```
[ ] Docker / Docker Compose 설치 확인
[ ] .env 파일 생성 (ANTHROPIC_API_KEY, GOOGLE_API_KEY 설정)
[ ] .env에서 POSTGRES_HOST=postgres, REDIS_HOST=redis 확인
[ ] docker compose build 성공
[ ] docker compose up -d postgres redis → healthy
[ ] alembic upgrade head 성공 (10개 테이블 생성)
[ ] docker compose up -d (전체 14개 서비스)
[ ] curl localhost:8000/api/v1/health → 200 OK
[ ] MCP 서버 9개 /health 응답 확인
[ ] Engine 로그에 "Redis Stream 구독" 확인
```
