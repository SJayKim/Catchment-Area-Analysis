# 11. 배포 & 인프라 가이드

> **문서 버전**: 1.0.0
> **최종 수정일**: 2026-03-21
> **상태**: 확정 (Phase 1 MVP 기준)
> **범위**: Docker 기반 로컬 개발환경 및 GCP Cloud Run 프로덕션 배포

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [Dockerfile 설계](#2-dockerfile-설계)
3. [Docker Compose 서비스 구성](#3-docker-compose-서비스-구성)
4. [환경변수 목록](#4-환경변수-목록)
5. [로컬 개발 환경 셋업 절차](#5-로컬-개발-환경-셋업-절차)
6. [GCP Cloud Run 프로덕션 배포 절차](#6-gcp-cloud-run-프로덕션-배포-절차)
7. [Alembic 마이그레이션 전략](#7-alembic-마이그레이션-전략)
8. [볼륨 & 네트워크 구성](#8-볼륨--네트워크-구성)
9. [헬스체크 설정](#9-헬스체크-설정)

---

## 1. 시스템 개요

### 1.1 배포 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Docker Compose Network                       │
│                         (marketscope-net)                           │
│                                                                     │
│  ┌──────────┐  ┌──────────┐                                        │
│  │ postgres │  │  redis   │                                        │
│  │ (PostGIS)│  │ 7-alpine │                                        │
│  │  :5432   │  │  :6379   │                                        │
│  └────┬─────┘  └────┬─────┘                                        │
│       │              │                                              │
│       └──────┬───────┘                                              │
│              │                                                      │
│  ┌───────────▼───────────┐     ┌──────────────────────────────┐    │
│  │      app (FastAPI)    │     │       MCP Servers             │    │
│  │       :8000           │◄───►│  public_data   :5100         │    │
│  │                       │     │  maps          :5101         │    │
│  │  - LangGraph 워크플로우 │     │  real_estate   :5102         │    │
│  │  - REST API           │     │  news          :5103         │    │
│  │  - WebSocket/SSE      │     │  regulatory    :5104         │    │
│  └───────────┬───────────┘     │  finance       :5105         │    │
│              │                 │  database      :5106         │    │
│              │                 │  google_maps   :5107         │    │
│  ┌───────────▼───────────┐     │  naver_maps    :5108         │    │
│  │   Monitoring Stack    │     └──────────────────────────────┘    │
│  │  prometheus  :9090    │                                        │
│  │  grafana     :3001    │                                        │
│  │  loki        :3100    │                                        │
│  └───────────────────────┘                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 서비스 포트 매핑 요약

| 서비스 | 컨테이너 포트 | 호스트 포트 | 프로토콜 | 비고 |
|--------|-------------|-----------|---------|------|
| postgres (PostGIS) | 5432 | 5432 | TCP | PostGIS 15-3.4 |
| redis | 6379 | 6379 | TCP | Redis 7-alpine |
| app (FastAPI) | 8000 | 8000 | HTTP | 메인 애플리케이션 |
| mcp-public-data | 5100 | 5100 | HTTP/SSE | 공공데이터 MCP |
| mcp-maps | 5101 | 5101 | HTTP/SSE | 지도/GIS MCP |
| mcp-real-estate | 5102 | 5102 | HTTP/SSE | 부동산 MCP [Phase 2] |
| mcp-news | 5103 | 5103 | HTTP/SSE | 뉴스/SNS MCP [Phase 2] |
| mcp-regulatory | 5104 | 5104 | HTTP/SSE | 규제/인허가 MCP [Phase 2] |
| mcp-finance | 5105 | 5105 | HTTP/SSE | 금융/대출 MCP [Phase 2] |
| mcp-database | 5106 | 5106 | HTTP/SSE | 데이터베이스 MCP |
| mcp-google-maps | 5107 | 5107 | HTTP/SSE | Google Maps MCP |
| mcp-naver-maps | 5108 | 5108 | HTTP/SSE | Naver Maps MCP |
| prometheus | 9090 | 9090 | HTTP | 메트릭 수집 |
| grafana | 3001 | 3001 | HTTP | 대시보드 |
| loki | 3100 | 3100 | HTTP | 로그 집계 |

### 1.3 기술 스택

| 구분 | 기술 | 버전 |
|------|------|------|
| 런타임 | Python | 3.11 |
| 프레임워크 | FastAPI | 0.115+ |
| 데이터베이스 | PostgreSQL + PostGIS | 15 + 3.4 |
| 캐시 | Redis | 7 (alpine) |
| 컨테이너 | Docker + Docker Compose | 24+ / v2 |
| 오케스트레이션 | LangGraph | 최신 |
| 클라우드 | GCP Cloud Run | v2 |
| CI/CD | GitHub Actions | - |
| 모니터링 | Prometheus + Grafana + Loki | - |

---

## 2. Dockerfile 설계

### 2.1 Multi-stage Build 구조

```dockerfile
# ==============================================================================
# Stage 1: Builder — 의존성 설치 및 wheel 빌드
# ==============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# 시스템 빌드 의존성 설치 (PostGIS 클라이언트 등)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgeos-dev \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# pip 업그레이드 및 wheel 설치
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# pyproject.toml 및 lock 파일 복사 (캐시 레이어 최적화)
COPY pyproject.toml ./
COPY README.md ./

# 의존성 wheel 빌드
RUN pip wheel --no-cache-dir --wheel-dir=/build/wheels -e ".[prod]"

# ==============================================================================
# Stage 2: Production — 최소 런타임 이미지
# ==============================================================================
FROM python:3.11-slim AS production

# 메타데이터 라벨
LABEL maintainer="MarketScope AI Team"
LABEL description="MarketScope AI - 상권 분석 AI 플랫폼"
LABEL version="1.0.0"

# 비root 사용자 생성
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# 런타임 시스템 의존성만 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgeos-c1v5 \
    libproj25 \
    gdal-bin \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Builder에서 wheel 복사 및 설치
COPY --from=builder /build/wheels /tmp/wheels
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheels /tmp/wheels/*.whl && \
    rm -rf /tmp/wheels

# 애플리케이션 소스 복사
COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini ./alembic.ini
COPY ./mcp_servers ./mcp_servers

# 소유권 변경
RUN chown -R appuser:appuser /app

# 비root 사용자로 전환
USER appuser

# 환경변수 기본값
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# 포트 노출
EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# uvicorn 엔트리포인트
ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 2.2 MCP 서버용 Dockerfile

```dockerfile
# ==============================================================================
# MCP Server Dockerfile (공통 템플릿)
# ==============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY pyproject.toml ./
RUN pip wheel --no-cache-dir --wheel-dir=/build/wheels -e ".[mcp]"

FROM python:3.11-slim AS production

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/wheels /tmp/wheels
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheels /tmp/wheels/*.whl && \
    rm -rf /tmp/wheels

COPY ./mcp_servers ./mcp_servers

RUN chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# 포트는 docker-compose에서 서버별로 지정
EXPOSE 5100-5108

ENTRYPOINT ["python", "-m"]
# CMD는 docker-compose에서 오버라이드
CMD ["mcp_servers.public_data.server"]
```

### 2.3 이미지 크기 최적화 전략

| 전략 | 설명 | 절감 효과 |
|------|------|----------|
| Multi-stage build | 빌드 의존성 제거 | ~400MB |
| `--no-install-recommends` | 불필요 패키지 제외 | ~100MB |
| `rm -rf /var/lib/apt/lists/*` | apt 캐시 정리 | ~30MB |
| `--no-cache-dir` (pip) | pip 캐시 제거 | ~50MB |
| python:3.11-slim | 전체 Python 대비 경량 | ~700MB |
| **최종 예상 이미지 크기** | | **~350MB** |

---

## 3. Docker Compose 서비스 구성

### 3.1 전체 `docker-compose.yml`

```yaml
version: "3.9"

# ==============================================================================
# 공유 설정 (YAML Anchors)
# ==============================================================================
x-mcp-common: &mcp-common
  build:
    context: .
    dockerfile: Dockerfile.mcp
  env_file: .env
  networks:
    - marketscope-net
  restart: unless-stopped
  deploy:
    resources:
      limits:
        memory: 512M
        cpus: "0.5"

# ==============================================================================
# 서비스 정의
# ==============================================================================
services:

  # ============================================================================
  # 인프라 서비스
  # ============================================================================

  postgres:
    image: postgis/postgis:15-3.4
    container_name: marketscope-postgres
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-marketscope}
      POSTGRES_USER: ${POSTGRES_USER:-marketscope}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}
      POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=ko_KR.UTF-8"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./docker/initdb:/docker-entrypoint-initdb.d:ro
    networks:
      - marketscope-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-marketscope} -d ${POSTGRES_DB:-marketscope}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: "1.0"

  redis:
    image: redis:7-alpine
    container_name: marketscope-redis
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
      --appendfsync everysec
    volumes:
      - redis-data:/data
    networks:
      - marketscope-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "0.5"

  # ============================================================================
  # MCP 서버 (9개)
  # ============================================================================

  mcp-public-data:
    <<: *mcp-common
    container_name: marketscope-mcp-public-data
    ports:
      - "5100:5100"
    command: ["mcp_servers.public_data.server", "--port", "5100"]
    environment:
      MCP_SERVER_NAME: public_data
      MCP_SERVER_PORT: 5100
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5100/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  mcp-maps:
    <<: *mcp-common
    container_name: marketscope-mcp-maps
    ports:
      - "5101:5101"
    command: ["mcp_servers.maps.server", "--port", "5101"]
    environment:
      MCP_SERVER_NAME: maps
      MCP_SERVER_PORT: 5101
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5101/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  mcp-real-estate:
    <<: *mcp-common
    container_name: marketscope-mcp-real-estate
    ports:
      - "5102:5102"
    command: ["mcp_servers.real_estate.server", "--port", "5102"]
    environment:
      MCP_SERVER_NAME: real_estate
      MCP_SERVER_PORT: 5102
    profiles:
      - phase2
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5102/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  mcp-news:
    <<: *mcp-common
    container_name: marketscope-mcp-news
    ports:
      - "5103:5103"
    command: ["mcp_servers.news.server", "--port", "5103"]
    environment:
      MCP_SERVER_NAME: news
      MCP_SERVER_PORT: 5103
    profiles:
      - phase2
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5103/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  mcp-regulatory:
    <<: *mcp-common
    container_name: marketscope-mcp-regulatory
    ports:
      - "5104:5104"
    command: ["mcp_servers.regulatory.server", "--port", "5104"]
    environment:
      MCP_SERVER_NAME: regulatory
      MCP_SERVER_PORT: 5104
    profiles:
      - phase2
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5104/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  mcp-finance:
    <<: *mcp-common
    container_name: marketscope-mcp-finance
    ports:
      - "5105:5105"
    command: ["mcp_servers.finance.server", "--port", "5105"]
    environment:
      MCP_SERVER_NAME: finance
      MCP_SERVER_PORT: 5105
    profiles:
      - phase2
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5105/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  mcp-database:
    <<: *mcp-common
    container_name: marketscope-mcp-database
    ports:
      - "5106:5106"
    command: ["mcp_servers.database.server", "--port", "5106"]
    environment:
      MCP_SERVER_NAME: database
      MCP_SERVER_PORT: 5106
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5106/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  mcp-google-maps:
    <<: *mcp-common
    container_name: marketscope-mcp-google-maps
    ports:
      - "5107:5107"
    command: ["mcp_servers.google_maps.server", "--port", "5107"]
    environment:
      MCP_SERVER_NAME: google_maps
      MCP_SERVER_PORT: 5107
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5107/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  mcp-naver-maps:
    <<: *mcp-common
    container_name: marketscope-mcp-naver-maps
    ports:
      - "5108:5108"
    command: ["mcp_servers.naver_maps.server", "--port", "5108"]
    environment:
      MCP_SERVER_NAME: naver_maps
      MCP_SERVER_PORT: 5108
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5108/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  # ============================================================================
  # 메인 애플리케이션
  # ============================================================================

  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: marketscope-app
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-marketscope}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-marketscope}
      REDIS_URL: redis://redis:6379/0
      MCP_PUBLIC_DATA_URL: http://mcp-public-data:5100
      MCP_MAPS_URL: http://mcp-maps:5101
      MCP_REAL_ESTATE_URL: http://mcp-real-estate:5102
      MCP_NEWS_URL: http://mcp-news:5103
      MCP_REGULATORY_URL: http://mcp-regulatory:5104
      MCP_FINANCE_URL: http://mcp-finance:5105
      MCP_DATABASE_URL: http://mcp-database:5106
      MCP_GOOGLE_MAPS_URL: http://mcp-google-maps:5107
      MCP_NAVER_MAPS_URL: http://mcp-naver-maps:5108
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      mcp-public-data:
        condition: service_healthy
      mcp-maps:
        condition: service_healthy
      mcp-database:
        condition: service_healthy
    networks:
      - marketscope-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "2.0"

  # ============================================================================
  # 모니터링 스택
  # ============================================================================

  prometheus:
    image: prom/prometheus:latest
    container_name: marketscope-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./docker/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.retention.time=30d"
      - "--web.enable-lifecycle"
    networks:
      - marketscope-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:9090/-/healthy"]
      interval: 30s
      timeout: 10s
      retries: 3

  grafana:
    image: grafana/grafana:latest
    container_name: marketscope-grafana
    ports:
      - "3001:3000"
    environment:
      GF_SECURITY_ADMIN_USER: ${GRAFANA_ADMIN_USER:-admin}
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:-admin}
      GF_USERS_ALLOW_SIGN_UP: "false"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./docker/grafana/provisioning:/etc/grafana/provisioning:ro
    depends_on:
      - prometheus
      - loki
    networks:
      - marketscope-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  loki:
    image: grafana/loki:latest
    container_name: marketscope-loki
    ports:
      - "3100:3100"
    volumes:
      - ./docker/loki/loki-config.yml:/etc/loki/local-config.yaml:ro
      - loki-data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - marketscope-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:3100/ready"]
      interval: 30s
      timeout: 10s
      retries: 3

# ==============================================================================
# 볼륨 정의
# ==============================================================================
volumes:
  postgres-data:
    driver: local
  redis-data:
    driver: local
  prometheus-data:
    driver: local
  grafana-data:
    driver: local
  loki-data:
    driver: local

# ==============================================================================
# 네트워크 정의
# ==============================================================================
networks:
  marketscope-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
```

### 3.2 서비스 의존성 그래프

```
postgres ──────┬──────► mcp-public-data ──┐
               │                          │
               ├──────► mcp-database ─────┤
               │                          │
redis ─────────┤                          ├──► app (:8000)
               │                          │
               │       mcp-maps ──────────┤
               │       mcp-google-maps ───┤
               │       mcp-naver-maps ────┘
               │
               │       [Phase 2]
               ├─ ─ ─► mcp-real-estate
               ├─ ─ ─► mcp-news
               ├─ ─ ─► mcp-regulatory
               └─ ─ ─► mcp-finance

prometheus ──► grafana (:3001)
loki ──────►
```

### 3.3 Phase 별 실행 명령

```bash
# Phase 1 MVP (기본 프로필 — Phase 2 서비스 제외)
docker compose up -d

# Phase 2 전체 (모든 MCP 서버 포함)
docker compose --profile phase2 up -d

# 모니터링 없이 (개발 시)
docker compose up -d postgres redis mcp-public-data mcp-maps mcp-database app

# 특정 서비스만 재빌드
docker compose up -d --build app
```

---

## 4. 환경변수 목록

### 4.1 `.env.example` 템플릿

```env
# ==============================================================================
# MarketScope AI 환경변수 설정
# .env.example → .env 로 복사 후 값 입력
# ==============================================================================

# --- 데이터베이스 (필수) ---
POSTGRES_DB=marketscope
POSTGRES_USER=marketscope
POSTGRES_PASSWORD=                          # 필수: 강력한 비밀번호 입력
DATABASE_URL=postgresql+asyncpg://marketscope:${POSTGRES_PASSWORD}@postgres:5432/marketscope

# --- Redis (필수) ---
REDIS_URL=redis://redis:6379/0

# --- 공공데이터 API 키 (필수) ---
DATA_API_SEOUL_OPEN_DATA_KEY=               # 서울 열린데이터광장 API 인증키
DATA_API_PUBLIC_DATA_KEY=                   # data.go.kr 공공데이터포털 API 인증키

# --- 지도 API 키 (필수) ---
DATA_API_KAKAO_REST_KEY=                    # 카카오 REST API 키
DATA_API_GOOGLE_MAPS_KEY=                   # Google Maps Platform API 키
DATA_API_NAVER_CLIENT_ID=                   # 네이버 클라우드 플랫폼 Client ID
DATA_API_NAVER_CLIENT_SECRET=               # 네이버 클라우드 플랫폼 Client Secret

# --- LLM API 키 (최소 1개 필수) ---
LITELLM_API_KEY=                            # LiteLLM 프록시 키 (사용 시)
OPENAI_API_KEY=                             # OpenAI API 키
ANTHROPIC_API_KEY=                          # Anthropic API 키
GEMINI_API_KEY=                             # Google Gemini API 키

# --- Langfuse 관측성 (선택) ---
LANGFUSE_PUBLIC_KEY=                        # Langfuse Public Key
LANGFUSE_SECRET_KEY=                        # Langfuse Secret Key
LANGFUSE_HOST=https://cloud.langfuse.com   # Langfuse 호스트 URL

# --- 모니터링 (선택) ---
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin

# --- 애플리케이션 설정 (선택) ---
APP_ENV=development                         # development | staging | production
APP_LOG_LEVEL=INFO                          # DEBUG | INFO | WARNING | ERROR
APP_CORS_ORIGINS=http://localhost:3000      # 프론트엔드 origin (콤마 구분)
```

### 4.2 환경변수 분류표

#### 필수 환경변수

| 변수명 | 설명 | 기본값 | 사용 서비스 |
|--------|------|--------|-----------|
| `POSTGRES_PASSWORD` | PostgreSQL 비밀번호 | _(없음, 필수)_ | postgres, app |
| `DATABASE_URL` | DB 접속 URL (asyncpg) | 자동 구성 | app, mcp-database |
| `REDIS_URL` | Redis 접속 URL | `redis://redis:6379/0` | app |
| `DATA_API_SEOUL_OPEN_DATA_KEY` | 서울 열린데이터광장 인증키 | _(없음, 필수)_ | mcp-public-data |
| `DATA_API_PUBLIC_DATA_KEY` | data.go.kr 인증키 | _(없음, 필수)_ | mcp-public-data |
| `DATA_API_KAKAO_REST_KEY` | 카카오 REST API 키 | _(없음, 필수)_ | mcp-maps |
| `DATA_API_GOOGLE_MAPS_KEY` | Google Maps API 키 | _(없음, 필수)_ | mcp-google-maps |
| `DATA_API_NAVER_CLIENT_ID` | 네이버 Client ID | _(없음, 필수)_ | mcp-naver-maps |
| `DATA_API_NAVER_CLIENT_SECRET` | 네이버 Client Secret | _(없음, 필수)_ | mcp-naver-maps |

#### LLM API 키 (최소 1개 필수)

| 변수명 | 설명 | 우선순위 | 비고 |
|--------|------|---------|------|
| `LITELLM_API_KEY` | LiteLLM 프록시 키 | 1순위 | 멀티모델 라우팅 사용 시 |
| `OPENAI_API_KEY` | OpenAI API 키 | 2순위 | GPT-4o 사용 시 |
| `ANTHROPIC_API_KEY` | Anthropic API 키 | 3순위 | Claude 사용 시 |
| `GEMINI_API_KEY` | Google Gemini API 키 | 4순위 | Gemini Pro 사용 시 |

#### 선택 환경변수

| 변수명 | 설명 | 기본값 | 비고 |
|--------|------|--------|------|
| `LANGFUSE_PUBLIC_KEY` | Langfuse Public Key | _(없음)_ | 미설정 시 관측성 비활성 |
| `LANGFUSE_SECRET_KEY` | Langfuse Secret Key | _(없음)_ | 미설정 시 관측성 비활성 |
| `LANGFUSE_HOST` | Langfuse 호스트 URL | `https://cloud.langfuse.com` | 셀프호스팅 시 변경 |
| `APP_ENV` | 실행 환경 | `development` | production에서 디버그 비활성 |
| `APP_LOG_LEVEL` | 로그 레벨 | `INFO` | 개발 시 DEBUG 권장 |
| `APP_CORS_ORIGINS` | CORS 허용 origin | `http://localhost:3000` | 콤마 구분 복수 입력 |
| `GRAFANA_ADMIN_USER` | Grafana 관리자 ID | `admin` | 프로덕션에서 변경 필수 |
| `GRAFANA_ADMIN_PASSWORD` | Grafana 관리자 PW | `admin` | 프로덕션에서 변경 필수 |
| `POSTGRES_DB` | 데이터베이스명 | `marketscope` | |
| `POSTGRES_USER` | DB 사용자명 | `marketscope` | |

---

## 5. 로컬 개발 환경 셋업 절차

### 5.1 사전 요구사항

| 도구 | 최소 버전 | 확인 명령 |
|------|----------|----------|
| Docker Desktop | 24.0+ | `docker --version` |
| Docker Compose | v2.20+ | `docker compose version` |
| Python | 3.11+ | `python --version` |
| Git | 2.30+ | `git --version` |
| uv (권장) | 0.4+ | `uv --version` |

### 5.2 초기 셋업 절차

```bash
# 1. 저장소 클론
git clone https://github.com/your-org/marketscope-ai.git
cd marketscope-ai/marketscope

# 2. 환경변수 파일 설정
cp .env.example .env
# .env 파일을 편집하여 필수 API 키 및 비밀번호 입력

# 3. Docker 이미지 빌드 및 컨테이너 시작
docker compose build
docker compose up -d

# 4. DB 마이그레이션 실행
docker compose exec app alembic upgrade head

# 5. 초기 데이터 시딩 (상권 경계, 행정동 코드 등)
docker compose exec app python -m app.scripts.seed_data

# 6. 서비스 상태 확인
docker compose ps
curl http://localhost:8000/health
```

### 5.3 로컬 개발 모드 (핫 리로드)

개발 시에는 소스 코드를 볼륨 마운트하여 핫 리로드를 활성화한다.

```yaml
# docker-compose.override.yml (로컬 개발 전용, Git 추적 제외)
services:
  app:
    build:
      target: production
    volumes:
      - ./app:/app/app:ro
      - ./mcp_servers:/app/mcp_servers:ro
    command: ["app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
    environment:
      APP_ENV: development
      APP_LOG_LEVEL: DEBUG
```

```bash
# 개발 모드 실행
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

### 5.4 유용한 개발 명령어

```bash
# 로그 실시간 확인
docker compose logs -f app

# 특정 MCP 서버 로그 확인
docker compose logs -f mcp-public-data

# 컨테이너 셸 접속
docker compose exec app bash

# DB 직접 접속
docker compose exec postgres psql -U marketscope -d marketscope

# Redis CLI 접속
docker compose exec redis redis-cli

# 전체 서비스 재시작
docker compose restart

# 전체 정리 (볼륨 포함)
docker compose down -v
```

---

## 6. GCP Cloud Run 프로덕션 배포 절차

### 6.1 GCP 아키텍처 다이어그램

```
┌──────────────────────────────────────────────────────────────┐
│                        GCP Project                           │
│                                                              │
│  ┌─────────────┐                                             │
│  │ Cloud Build  │──── GitHub Webhook (main branch push)      │
│  │ (CI/CD)      │                                            │
│  └──────┬──────┘                                             │
│         │ 이미지 빌드 & 푸시                                   │
│         ▼                                                    │
│  ┌─────────────┐                                             │
│  │  Artifact    │                                             │
│  │  Registry    │                                             │
│  │ (Docker Hub) │                                             │
│  └──────┬──────┘                                             │
│         │ 이미지 배포                                         │
│         ▼                                                    │
│  ┌─────────────────────────────────────────┐                 │
│  │           Cloud Run Services            │                 │
│  │                                         │                 │
│  │  ┌──────────────┐  ┌────────────────┐   │                 │
│  │  │ app (FastAPI) │  │ MCP Servers    │   │                 │
│  │  │  min: 1       │  │ (각각 별도     │   │                 │
│  │  │  max: 10      │  │  Cloud Run     │   │                 │
│  │  │  CPU: 2       │  │  서비스)       │   │                 │
│  │  │  Memory: 2Gi  │  │               │   │                 │
│  │  └──────┬───────┘  └───────┬────────┘   │                 │
│  └─────────┼──────────────────┼────────────┘                 │
│            │                  │                               │
│            ▼                  ▼                               │
│  ┌─────────────┐    ┌──────────────┐                         │
│  │ Cloud SQL    │    │ Memorystore  │                         │
│  │ (PostgreSQL  │    │ (Redis)      │                         │
│  │  + PostGIS)  │    │              │                         │
│  └─────────────┘    └──────────────┘                         │
│                                                              │
│  ┌─────────────┐    ┌──────────────┐                         │
│  │ Secret       │    │ Cloud        │                         │
│  │ Manager      │    │ Monitoring   │                         │
│  └─────────────┘    └──────────────┘                         │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 GCP 리소스 프로비저닝

```bash
# 0. 프로젝트 설정
export PROJECT_ID="marketscope-prod"
export REGION="asia-northeast3"  # 서울 리전
gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION

# 1. API 활성화
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  secretmanager.googleapis.com

# 2. Artifact Registry 저장소 생성
gcloud artifacts repositories create marketscope \
  --repository-format=docker \
  --location=$REGION \
  --description="MarketScope AI Docker images"

# 3. Cloud SQL (PostgreSQL + PostGIS) 인스턴스 생성
gcloud sql instances create marketscope-db \
  --database-version=POSTGRES_15 \
  --tier=db-custom-2-8192 \
  --region=$REGION \
  --storage-size=50GB \
  --storage-auto-increase \
  --database-flags=max_connections=200 \
  --availability-type=regional

# PostGIS 확장 활성화
gcloud sql databases create marketscope --instance=marketscope-db
gcloud sql connect marketscope-db --user=postgres
# SQL> CREATE EXTENSION IF NOT EXISTS postgis;

# 4. Memorystore (Redis) 인스턴스 생성
gcloud redis instances create marketscope-cache \
  --size=1 \
  --region=$REGION \
  --redis-version=redis_7_0 \
  --tier=standard

# 5. Secret Manager에 시크릿 등록
echo -n "YOUR_DB_PASSWORD" | gcloud secrets create db-password --data-file=-
echo -n "YOUR_OPENAI_KEY" | gcloud secrets create openai-api-key --data-file=-
echo -n "YOUR_ANTHROPIC_KEY" | gcloud secrets create anthropic-api-key --data-file=-
# ... 기타 시크릿 동일하게 등록
```

### 6.3 Cloud Build 설정 (`cloudbuild.yaml`)

```yaml
steps:
  # 1. Docker 이미지 빌드
  - name: "gcr.io/cloud-builders/docker"
    args:
      - "build"
      - "-t"
      - "${_REGION}-docker.pkg.dev/${PROJECT_ID}/marketscope/app:${SHORT_SHA}"
      - "-t"
      - "${_REGION}-docker.pkg.dev/${PROJECT_ID}/marketscope/app:latest"
      - "-f"
      - "marketscope/Dockerfile"
      - "marketscope/"

  # 2. Artifact Registry에 푸시
  - name: "gcr.io/cloud-builders/docker"
    args: ["push", "--all-tags", "${_REGION}-docker.pkg.dev/${PROJECT_ID}/marketscope/app"]

  # 3. DB 마이그레이션 실행
  - name: "${_REGION}-docker.pkg.dev/${PROJECT_ID}/marketscope/app:${SHORT_SHA}"
    entrypoint: "alembic"
    args: ["upgrade", "head"]
    secretEnv: ["DATABASE_URL"]

  # 4. Cloud Run 배포
  - name: "gcr.io/cloud-builders/gcloud"
    args:
      - "run"
      - "deploy"
      - "marketscope-app"
      - "--image=${_REGION}-docker.pkg.dev/${PROJECT_ID}/marketscope/app:${SHORT_SHA}"
      - "--region=${_REGION}"
      - "--platform=managed"
      - "--min-instances=1"
      - "--max-instances=10"
      - "--memory=2Gi"
      - "--cpu=2"
      - "--port=8000"
      - "--set-env-vars=APP_ENV=production"
      - "--allow-unauthenticated"

substitutions:
  _REGION: asia-northeast3

availableSecrets:
  secretManager:
    - versionName: projects/${PROJECT_ID}/secrets/db-password/versions/latest
      env: DATABASE_URL

options:
  logging: CLOUD_LOGGING_ONLY

timeout: "1200s"
```

### 6.4 Cloud Run 서비스 배포

```bash
# 메인 애플리케이션 배포
gcloud run deploy marketscope-app \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/marketscope/app:latest \
  --region=$REGION \
  --platform=managed \
  --min-instances=1 \
  --max-instances=10 \
  --memory=2Gi \
  --cpu=2 \
  --port=8000 \
  --set-env-vars="APP_ENV=production,APP_LOG_LEVEL=INFO" \
  --set-secrets="DATABASE_URL=db-url:latest,REDIS_URL=redis-url:latest,OPENAI_API_KEY=openai-api-key:latest" \
  --add-cloudsql-instances=${PROJECT_ID}:${REGION}:marketscope-db \
  --allow-unauthenticated \
  --concurrency=80 \
  --timeout=300

# MCP 서버 배포 (예시: public_data)
gcloud run deploy marketscope-mcp-public-data \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/marketscope/mcp:latest \
  --region=$REGION \
  --platform=managed \
  --min-instances=1 \
  --max-instances=5 \
  --memory=512Mi \
  --cpu=1 \
  --port=5100 \
  --set-env-vars="MCP_SERVER_NAME=public_data,MCP_SERVER_PORT=5100" \
  --set-secrets="DATA_API_SEOUL_OPEN_DATA_KEY=seoul-api-key:latest,DATA_API_PUBLIC_DATA_KEY=public-data-key:latest" \
  --no-allow-unauthenticated \
  --ingress=internal
```

### 6.5 프로덕션 환경 체크리스트

| 항목 | 확인 사항 | 상태 |
|------|----------|------|
| 시크릿 관리 | 모든 API 키를 Secret Manager에 등록 | [ ] |
| Cloud SQL | PostGIS 확장 활성화 확인 | [ ] |
| VPC 커넥터 | Cloud Run ↔ Cloud SQL/Redis 내부 통신 설정 | [ ] |
| 커스텀 도메인 | Cloud Run에 커스텀 도메인 매핑 | [ ] |
| SSL/TLS | 관리형 인증서 자동 프로비저닝 확인 | [ ] |
| IAM | 최소 권한 원칙 적용 (서비스 계정 분리) | [ ] |
| 로깅 | Cloud Logging 통합 확인 | [ ] |
| 알림 | Cloud Monitoring 알림 정책 설정 | [ ] |
| 백업 | Cloud SQL 자동 백업 (일 1회) 활성화 | [ ] |
| 비용 | 예산 알림 설정 (월 $200 임계치) | [ ] |

---

## 7. Alembic 마이그레이션 전략

### 7.1 Alembic 디렉토리 구조

```
marketscope/
├── alembic.ini                    # Alembic 설정 파일
├── alembic/
│   ├── env.py                     # 마이그레이션 환경 설정
│   ├── script.py.mako             # 마이그레이션 스크립트 템플릿
│   └── versions/                  # 마이그레이션 파일들
│       ├── 001_initial_schema.py
│       ├── 002_add_postgis.py
│       ├── 003_create_districts.py
│       └── ...
```

### 7.2 `alembic.ini` 핵심 설정

```ini
[alembic]
script_location = alembic
# sqlalchemy.url은 env.py에서 환경변수로 오버라이드
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[logger_alembic]
level = INFO
handlers =
qualname = alembic
```

### 7.3 `env.py` 비동기 설정

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.config import settings
from app.db.models import Base  # 모든 ORM 모델 import

config = context.config

# 환경변수에서 DATABASE_URL 주입
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """오프라인 모드: SQL 스크립트 생성만 수행."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """비동기 엔진을 사용한 온라인 마이그레이션."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 7.4 마이그레이션 운용 명령어

```bash
# 마이그레이션 파일 자동 생성 (모델 변경 감지)
docker compose exec app alembic revision --autogenerate -m "add_user_table"

# 최신 버전으로 업그레이드
docker compose exec app alembic upgrade head

# 한 단계 업그레이드
docker compose exec app alembic upgrade +1

# 한 단계 다운그레이드
docker compose exec app alembic downgrade -1

# 특정 리비전으로 이동
docker compose exec app alembic upgrade abc123

# 현재 리비전 확인
docker compose exec app alembic current

# 마이그레이션 이력 확인
docker compose exec app alembic history --verbose

# SQL만 출력 (실행하지 않음)
docker compose exec app alembic upgrade head --sql
```

### 7.5 마이그레이션 규칙

| 규칙 | 설명 |
|------|------|
| 네이밍 컨벤션 | `NNN_설명.py` (예: `001_initial_schema.py`) |
| 리뷰 필수 | 자동 생성 파일은 반드시 수동 리뷰 후 커밋 |
| 롤백 가능성 | 모든 `upgrade()`에 대응하는 `downgrade()` 작성 |
| 데이터 마이그레이션 분리 | 스키마 변경과 데이터 변환은 별도 리비전으로 분리 |
| PostGIS 주의 | `geoalchemy2` 컬럼 변경 시 수동 SQL 작성 권장 |
| 프로덕션 배포 순서 | 마이그레이션 실행 -> 애플리케이션 배포 (순차적) |
| CI/CD 통합 | Cloud Build에서 배포 전 자동 마이그레이션 실행 |

### 7.6 PostGIS 전용 마이그레이션 예시

```python
"""002_add_postgis.py - PostGIS 확장 및 공간 인덱스 생성"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


def upgrade() -> None:
    # PostGIS 확장 활성화
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # 상권 경계 테이블에 geometry 컬럼 추가
    op.add_column(
        "districts",
        sa.Column("boundary", Geometry("MULTIPOLYGON", srid=4326), nullable=True),
    )
    op.add_column(
        "districts",
        sa.Column("center_point", Geometry("POINT", srid=4326), nullable=True),
    )

    # 공간 인덱스 생성
    op.create_index(
        "idx_districts_boundary",
        "districts",
        ["boundary"],
        postgresql_using="gist",
    )
    op.create_index(
        "idx_districts_center_point",
        "districts",
        ["center_point"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index("idx_districts_center_point", table_name="districts")
    op.drop_index("idx_districts_boundary", table_name="districts")
    op.drop_column("districts", "center_point")
    op.drop_column("districts", "boundary")
```

---

## 8. 볼륨 & 네트워크 구성

### 8.1 볼륨 설계

| 볼륨 이름 | 마운트 경로 | 용도 | 데이터 영속성 |
|----------|-----------|------|------------|
| `postgres-data` | `/var/lib/postgresql/data` | PostgreSQL 데이터 파일 | 영구 보존 |
| `redis-data` | `/data` | Redis AOF 영속화 파일 | 재시작 시 복원 |
| `prometheus-data` | `/prometheus` | 메트릭 TSDB 데이터 (30일 보존) | 영구 보존 |
| `grafana-data` | `/var/lib/grafana` | 대시보드 설정, 플러그인 | 영구 보존 |
| `loki-data` | `/loki` | 로그 청크 저장소 | 영구 보존 |

### 8.2 바인드 마운트 (설정 파일)

| 호스트 경로 | 컨테이너 경로 | 대상 서비스 | 모드 |
|------------|-------------|-----------|------|
| `./docker/initdb/` | `/docker-entrypoint-initdb.d/` | postgres | `ro` |
| `./docker/prometheus/prometheus.yml` | `/etc/prometheus/prometheus.yml` | prometheus | `ro` |
| `./docker/grafana/provisioning/` | `/etc/grafana/provisioning/` | grafana | `ro` |
| `./docker/loki/loki-config.yml` | `/etc/loki/local-config.yaml` | loki | `ro` |

### 8.3 네트워크 구성

```yaml
networks:
  marketscope-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
```

| 항목 | 설정값 | 설명 |
|------|--------|------|
| 네트워크 이름 | `marketscope-net` | 모든 서비스가 참여하는 단일 브릿지 네트워크 |
| 드라이버 | `bridge` | Docker 기본 브릿지 네트워크 |
| 서브넷 | `172.28.0.0/16` | 충돌 방지를 위한 고정 서브넷 |
| DNS 해석 | 자동 | 서비스명으로 컨테이너 간 통신 (예: `postgres:5432`) |

### 8.4 서비스 간 통신 매트릭스

| 출발 서비스 | 목적 서비스 | 포트 | 프로토콜 | 용도 |
|------------|-----------|------|---------|------|
| app | postgres | 5432 | TCP | DB 쿼리 (asyncpg) |
| app | redis | 6379 | TCP | 캐시, 세션, 큐 |
| app | mcp-* | 5100-5108 | HTTP/SSE | MCP 도구 호출 |
| mcp-public-data | postgres | 5432 | TCP | 수집 데이터 저장 |
| mcp-database | postgres | 5432 | TCP | DB 쿼리 중계 |
| prometheus | app | 8000 | HTTP | `/metrics` 스크래핑 |
| prometheus | mcp-* | 5100-5108 | HTTP | `/metrics` 스크래핑 |
| grafana | prometheus | 9090 | HTTP | 메트릭 쿼리 |
| grafana | loki | 3100 | HTTP | 로그 쿼리 |

---

## 9. 헬스체크 설정

### 9.1 헬스체크 엔드포인트 설계

메인 애플리케이션(`app`)은 3단계 헬스체크 엔드포인트를 제공한다.

#### `/health` (Liveness Probe)

```python
@app.get("/health")
async def health_check():
    """기본 활성 상태 확인. 컨테이너 실행 여부만 판단."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
```

#### `/health/ready` (Readiness Probe)

```python
@app.get("/health/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """서비스 준비 상태 확인. 의존 서비스 연결 상태 포함."""
    checks = {}

    # PostgreSQL 연결 확인
    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = "connected"
    except Exception as e:
        checks["postgres"] = f"error: {str(e)}"

    # Redis 연결 확인
    try:
        await redis.ping()
        checks["redis"] = "connected"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    # MCP 서버 연결 확인 (Phase 1 활성 서버만)
    for name, url in [
        ("mcp_public_data", settings.MCP_PUBLIC_DATA_URL),
        ("mcp_maps", settings.MCP_MAPS_URL),
        ("mcp_database", settings.MCP_DATABASE_URL),
    ]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{url}/health")
                checks[name] = "healthy" if resp.status_code == 200 else "unhealthy"
        except Exception:
            checks[name] = "unreachable"

    all_healthy = all(
        v in ("connected", "healthy") for v in checks.values()
    )

    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
```

#### `/health/startup` (Startup Probe)

```python
@app.get("/health/startup")
async def startup_check():
    """시작 완료 상태 확인. 초기화 완료 여부 판단."""
    return {
        "status": "started",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "timestamp": datetime.utcnow().isoformat(),
    }
```

### 9.2 서비스별 헬스체크 설정 요약

| 서비스 | 방식 | 명령/경로 | interval | timeout | retries | start_period |
|--------|------|----------|----------|---------|---------|-------------|
| postgres | `CMD-SHELL` | `pg_isready -U marketscope` | 10s | 5s | 5 | 30s |
| redis | `CMD` | `redis-cli ping` | 10s | 5s | 5 | 10s |
| app | `CMD` (curl) | `http://localhost:8000/health` | 30s | 10s | 3 | 40s |
| mcp-* (9개) | `CMD` (curl) | `http://localhost:{PORT}/health` | 30s | 10s | 3 | 20s |
| prometheus | `CMD` (wget) | `http://localhost:9090/-/healthy` | 30s | 10s | 3 | - |
| grafana | `CMD` (curl) | `http://localhost:3000/api/health` | 30s | 10s | 3 | - |
| loki | `CMD` (wget) | `http://localhost:3100/ready` | 30s | 10s | 3 | - |

### 9.3 GCP Cloud Run 헬스체크

Cloud Run에서는 Docker HEALTHCHECK 대신 HTTP 헬스체크를 사용한다.

```yaml
# Cloud Run 서비스 YAML
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: marketscope-app
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/startup-cpu-boost: "true"
    spec:
      containers:
        - image: asia-northeast3-docker.pkg.dev/PROJECT_ID/marketscope/app:latest
          ports:
            - containerPort: 8000
          startupProbe:
            httpGet:
              path: /health/startup
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
            failureThreshold: 12
            timeoutSeconds: 5
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            periodSeconds: 30
            timeoutSeconds: 10
            failureThreshold: 3
          resources:
            limits:
              cpu: "2"
              memory: 2Gi
```

### 9.4 Prometheus 메트릭 수집 설정

```yaml
# docker/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "marketscope-app"
    static_configs:
      - targets: ["app:8000"]
    metrics_path: /metrics

  - job_name: "mcp-servers"
    static_configs:
      - targets:
          - "mcp-public-data:5100"
          - "mcp-maps:5101"
          - "mcp-database:5106"
          - "mcp-google-maps:5107"
          - "mcp-naver-maps:5108"
    metrics_path: /metrics

  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]
```

---

> **문서 끝** | MarketScope AI 배포 & 인프라 가이드 v1.0.0
