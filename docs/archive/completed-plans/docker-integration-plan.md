# Docker 통합 정비 계획

## Context

현재 Docker 인프라가 개발 편의용으로만 구성되어 있어 `docker compose up` 한 줄로 전체 서비스를 올릴 수 없음. Dockerfile은 dev 모드만 지원하고, .dockerignore 없이 전체 파일을 복사하며, 서비스 간 네트워킹(localhost vs service name) 문제로 컨테이너 내부에서 DB/Redis 연결이 실패함. 이를 정비하여 **어떤 환경에서든 `docker compose up` 한 줄로 동작**하게 만드는 것이 목표.

---

## 수정 파일 목록 (8개)

| # | 파일 | 작업 |
|---|------|------|
| 1 | `frontend/.dockerignore` | **신규** |
| 2 | `server/.dockerignore` | **신규** |
| 3 | `frontend/Dockerfile` | **재작성** — multi-stage (deps → build → runner) |
| 4 | `server/Dockerfile` | **재작성** — multi-stage (deps → runner) |
| 5 | `docker-compose.yml` | **재작성** — 프로필(dev/prod), env 전략, health check |
| 6 | `frontend/next.config.mjs` | **수정** — `output: 'standalone'` 추가 |
| 7 | `server/server/config.py` | **수정** — env_file 경로 존재 여부 체크 |
| 8 | `.env.example` | **수정** — Docker 환경 설명 추가 |

---

## 1. `.dockerignore` 파일 (신규 2개)

### `frontend/.dockerignore`
```
node_modules
.next
.env*
*.md
test-results
playwright-report
```

### `server/.dockerignore`
```
__pycache__
*.egg-info
.env*
*.md
data/shp
data/csv
data/seed
alembic/versions/__pycache__
```

**효과**: 빌드 컨텍스트 대폭 축소 (frontend ~400MB → ~5MB)

---

## 2. `frontend/Dockerfile` — multi-stage 재작성

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_KAKAO_MAP_KEY
ENV NEXT_PUBLIC_KAKAO_MAP_KEY=$NEXT_PUBLIC_KAKAO_MAP_KEY
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public 2>/dev/null || true
EXPOSE 3000
CMD ["node", "server.js"]
```

- `deps` → `builder` → `runner` 3단계
- `NEXT_PUBLIC_KAKAO_MAP_KEY`는 build-time ARG로 번들에 인라인
- `NEXT_PUBLIC_API_URL`은 build-time에 넣지 않음 → 클라이언트는 상대경로 `/api/*` 사용 → Next.js 서버가 runtime env로 rewrite
- standalone output으로 `node_modules` 없이 `server.js` 단독 실행

---

## 3. `server/Dockerfile` — multi-stage 재작성

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc g++ && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runner
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
COPY . .
EXPOSE 8000
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- builder에서 컴파일 의존성(gcc) 설치 + pip install
- runner에는 런타임 라이브러리(libpq5)만 → 이미지 경량화
- `--reload` 제거 (prod 모드)

---

## 4. `docker-compose.yml` — 프로필 + env 전략

핵심 설계:
- **기본(프로필 없음)**: prod 모드 — 빌드된 이미지, health check, 자동 마이그레이션
- **`--profile dev`**: dev 모드 — 볼륨 마운트, hot-reload, 기존 로컬 개발과 동일

```yaml
services:
  db:
    image: postgis/postgis:16-3.4
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: marketscope
      POSTGRES_USER: marketscope
      POSTGRES_PASSWORD: devpassword
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U marketscope"]
      interval: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5

  # --- 마이그레이션 (init container, 실행 후 종료) ---
  migrate:
    build: { context: ./server, target: runner }
    command: alembic upgrade head
    environment:
      DATABASE_URL_SYNC: postgresql://marketscope:devpassword@db:5432/marketscope
    depends_on:
      db: { condition: service_healthy }

  # --- Production 서비스 ---
  backend:
    build: { context: ./server, target: runner }
    ports: ["8000:8000"]
    environment:
      USE_MOCK: "false"
      DATABASE_URL: postgresql+asyncpg://marketscope:devpassword@db:5432/marketscope
      DATABASE_URL_SYNC: postgresql://marketscope:devpassword@db:5432/marketscope
      REDIS_URL: redis://redis:6379/0
      CORS_ORIGINS: '["http://localhost:3000","http://frontend:3000"]'
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
      GOOGLE_API_KEY: ${GOOGLE_API_KEY:-}
      AGENT_MODE: ${AGENT_MODE:-pae}
      LLM_PROVIDER: ${LLM_PROVIDER:-gemini}
    depends_on:
      db: { condition: service_healthy }
      redis: { condition: service_healthy }
      migrate: { condition: service_completed_successfully }
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      target: runner
      args:
        NEXT_PUBLIC_KAKAO_MAP_KEY: ${NEXT_PUBLIC_KAKAO_MAP_KEY:-}
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://backend:8000
      NEXT_PUBLIC_KAKAO_MAP_KEY: ${NEXT_PUBLIC_KAKAO_MAP_KEY:-}
    depends_on:
      backend: { condition: service_healthy }

  # --- Dev 프로필 (docker compose --profile dev up) ---
  backend-dev:
    profiles: [dev]
    build: { context: ./server }
    command: uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
    ports: ["8000:8000"]
    volumes: [./server:/app]
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://marketscope:devpassword@db:5432/marketscope
      REDIS_URL: redis://redis:6379/0
    depends_on:
      db: { condition: service_healthy }
      redis: { condition: service_healthy }

  frontend-dev:
    profiles: [dev]
    build: { context: ./frontend, target: deps }
    command: npx next dev --port 3000
    ports: ["3000:3000"]
    volumes: [./frontend:/app, /app/node_modules]
    environment:
      NEXT_PUBLIC_KAKAO_MAP_KEY: ${NEXT_PUBLIC_KAKAO_MAP_KEY:-}
      NEXT_PUBLIC_API_URL: http://backend-dev:8000
    depends_on: [backend-dev]

volumes:
  pgdata:
```

### env 전략 — localhost vs service name

| 환경 | DB 호스트 | Redis 호스트 | 설정 위치 |
|------|-----------|-------------|----------|
| 로컬 하이브리드 | `localhost` | `localhost` | root `.env` |
| Docker 전체 | `db` | `redis` | `docker-compose.yml` environment |

docker-compose의 `environment:`가 `.env` 파일보다 우선 → localhost URL을 service name으로 자동 오버라이드.

---

## 5. `frontend/next.config.mjs` 수정

`output: 'standalone'` 추가 (standalone 모드는 `next build` 시에만 영향, `next dev`에 영향 없음):

```javascript
const nextConfig = {
  output: 'standalone',  // Docker production 빌드용
  env: { ... },
  async rewrites() { ... },
};
```

---

## 6. `server/server/config.py` 수정

Docker 내부에서 `.env` 파일 경로가 존재하지 않을 때 graceful하게 처리:

```python
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

class Settings(BaseSettings):
    model_config = {
        "env_file": str(_ENV_FILE) if _ENV_FILE.exists() else None,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }
```

---

## 7. `.env.example` 수정

Docker 환경 설명 + 누락 변수 추가:

```
# [env 로딩 구조]
# - 로컬 개발: root .env → backend(pydantic) + frontend(dotenv in next.config)
# - Docker: docker-compose.yml environment 섹션이 service name으로 오버라이드
# → .env의 localhost URL은 수정 불필요, Docker가 자동 처리

GOOGLE_API_KEY=your_google_api_key_here
AGENT_MODE=pae
LLM_PROVIDER=gemini
```

---

## 실행 순서

1. `.dockerignore` 2개 생성
2. `next.config.mjs`에 `output: 'standalone'` 추가
3. `config.py` env_file 존재 체크 추가
4. `frontend/Dockerfile` 재작성
5. `server/Dockerfile` 재작성
6. `docker-compose.yml` 재작성
7. `.env.example` 업데이트
8. 검증

---

## 검증 계획

### Test 1: Production 모드 전체 기동
```bash
docker compose up --build
curl http://localhost:8000/health        # → {"status": "ok"}
curl http://localhost:3000               # → HTML 페이지
# 브라우저: 카카오맵 + 채팅 동작 확인
```

### Test 2: Playwright E2E
```bash
node -e "..." # 카카오맵 로딩, 폴리곤 표시, 에러 없음 확인
```

### Test 3: 로컬 하이브리드 회귀
```bash
docker compose up db redis
cd server && uvicorn server.main:app --port 8002 --reload
cd frontend && npx next dev --port 3000
# 기존과 동일하게 동작 확인
```

### Test 4: Clean slate (신규 개발자 시뮬레이션)
```bash
# .env.example → .env 복사 + API 키 설정
docker compose up --build
# 추가 설정 없이 동작 확인
```
