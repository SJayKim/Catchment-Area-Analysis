# Deployment Architecture

> 개발(docker-compose.yml) / 프로덕션(docker-compose.prod.yml + 외부 Nginx) 두 환경. 운영 배포 절차는 [../ops/production-deployment.md](../ops/production-deployment.md) 참조.

## 1. 환경별 구성

### 1.1 개발 (`docker-compose.yml`)

| 서비스 | 포트 (호스트:컨테이너) | 이미지 | 역할 |
|---|---|---|---|
| `db` | 5432:5432 | postgis/postgis:16-3.4 | PostgreSQL + PostGIS |
| `redis` | 6379:6379 | redis:7-alpine | 캐시 (maxmemory 256MB, allkeys-lru) |
| `backend` | 8002:8000 | local build | FastAPI (uvicorn) |
| `frontend` | 3001:3000 | local build | Next.js standalone |
| `nginx` | 8080:80 | nginx:alpine | 개발용 리버스 프록시 |

모든 서비스 `restart: unless-stopped`, `healthcheck` 정의. 로컬 개발은 `docker compose up -d db redis` 만 띄우고 backend/frontend 는 호스트에서 실행해도 된다.

### 1.2 프로덕션 (`docker-compose.prod.yml`)

| 서비스 | 포트 노출 | 특이점 |
|---|---|---|
| `db` | 미노출 (내부 전용) | 보안상 호스트 포트 차단 |
| `redis` | 미노출 | 동일 |
| `backend` | 8000 | 내부 Docker 네트워크 |
| `frontend` | 3200:3000 | 외부 호스트 nginx 가 접근 |
| `seed` | one-off | pg_restore + `cleanup_alembic.py` 실행 |

**외부 nginx** (호스트 OS): `nginx/external-reverse-proxy.conf.example` 참고. Let's Encrypt 인증서, SSE 버퍼링 비활성, `/api/*` → backend, `/proxy/*` + `/` → frontend 라우팅.

## 2. 네트워크 토폴로지 (프로덕션)

```
  User (HTTPS)
      │
      ▼
┌─────────────────────┐
│  호스트 Nginx         │  marketscope.robitlabs.co.kr
│  (Let's Encrypt)    │  proxy_buffering off (SSE 필수)
└───────┬─────────────┘
        │ 127.0.0.1:3200 (frontend)
        │ 127.0.0.1:8000 (backend, via docker-proxy)
        ▼
┌─────────────────────────────────────────────┐
│  docker network (marketscope_default)       │
│  ┌──────────┐  ┌────────┐  ┌─────────────┐  │
│  │ frontend │→ │ backend│→ │ db / redis  │  │
│  └──────────┘  └────────┘  └─────────────┘  │
└─────────────────────────────────────────────┘
```

- **SSE 경로**: 호스트 nginx → backend 컨테이너. `proxy_buffering off` + `X-Accel-Buffering: no` 필수 (`memory/feedback_sse_buffering.md`).
- **Kakao SDK 프록시**: 프론트엔드 `/proxy/kakao-sdk` 라우트가 백엔드로 가지 않도록 nginx 라우팅 필수.
- **DB/Redis 비노출**: 프로덕션에서는 `docker compose exec db psql …` 로만 접근.

## 3. 환경변수 (요약)

`.env.example` 참고. 필수 항목:

| 변수 | 용도 | 프로덕션 |
|---|---|---|
| `USE_MOCK` | Mock/Real 분기 | `false` |
| `DATABASE_URL` / `DATABASE_URL_SYNC` | PostgreSQL async / sync | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis 접속 | `redis://redis:6379/0` |
| `BACKEND_INTERNAL_URL` | 프론트 → 백엔드 rewrite 대상 | `http://backend:8000` |
| `NEXT_PUBLIC_API_URL` | 브라우저용 (SSE 직접 호출) | `https://marketscope.robitlabs.co.kr` |
| `NEXT_PUBLIC_KAKAO_MAP_KEY` | Kakao SDK (빌드 타임 bake) | 발급 키 |
| `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` | LLM | 필수 |
| `SEOUL_OPENDATA_API_KEY` | ETL | Real 모드에서 필수 |
| `LANGFUSE_*` | 관측 (선택) | 비워두면 비활성 |

`scripts/validate_env.py` 가 빌드/기동 전에 누락 검증.

## 4. 빌드

### Frontend (Dockerfile)

1. builder stage: `npm ci && npm run build` — `NEXT_PUBLIC_*` 값이 이 시점에 bake
2. runner stage: standalone 출력만 복사 → `node server.js`
3. build ARG 가드 — `NEXT_PUBLIC_KAKAO_MAP_KEY` 미주입 시 빌드 실패

### Backend (Dockerfile)

1. Python 3.12 slim
2. `pip install -e ".[dev]"` (`pyproject.toml` 소스 설치)
3. uvicorn --host 0.0.0.0 --port 8000 --workers 2

**pip SSL 우회 build-arg (선택)**: 사내/제한된 네트워크에서 `CERTIFICATE_VERIFY_FAILED` 발생 시:

```bash
docker compose build \
  --build-arg PIP_INDEX_URL=https://pypi.org/simple \
  --build-arg 'PIP_TRUSTED_HOST=pypi.org files.pythonhosted.org' \
  backend
```

기본값은 HTTPS PyPI(기존 동작 유지). build-arg 는 `/etc/pip.conf` 에 렌더되어 pip isolated build subprocess 까지 전파된다. `docker-compose.e2e.yml` 의 migrate/backend 에서도 `${PIP_INDEX_URL}` / `${PIP_TRUSTED_HOST}` 를 그대로 받는다.

## 5. 배포 순서 (프로덕션)

1. `scripts/validate_env.py` — 필수 env 확인
2. `docker compose -f docker-compose.prod.yml build`
3. `docker compose -f docker-compose.prod.yml up -d db redis`
4. `docker compose -f docker-compose.prod.yml run --rm seed` (최초 1회)
5. `docker compose -f docker-compose.prod.yml up -d backend frontend`
6. 호스트 `nginx -s reload` (인증서 갱신 시에도)

상세 runbook: [../ops/production-deployment.md](../ops/production-deployment.md), [../ops/runbook.md](../ops/runbook.md).

## 6. 모니터링 & 로깅

- Docker `json-file` log driver, max-size=50m, max-file=5 (서비스별)
- `/api/health/detail` — DB pool / Redis / session 메트릭
- Langfuse (선택): `LANGFUSE_*` 설정 시 LLM trace
- 향후: Prometheus exporter (backend `/metrics` 엔드포인트 가능성)

## 7. 재해 복구

- DB 백업: `scripts/backup_db.sh` (주기 실행 권장)
- Redis 는 캐시이므로 복구 불필요 (TTL 재적재)
- 세션 스토어는 인메모리 → 서버 재시작 시 유실 (UX 영향 적음)
- 상세 시나리오: [../ops/disaster-recovery.md](../ops/disaster-recovery.md)

## 8. 부하/용량 관측 (계획)

[plan/infra/load-test-plan.md](../plan/infra/load-test-plan.md) — 동시 사용자 환경 검증 인프라 구축 예정. 현재 상한:

- `/api/chat` 10 req/min/IP (slowapi)
- Agent 동시 실행 semaphore=20
- DB pool 10 + overflow 20
- SSE queue 256 events (backpressure)
