# Deployment Architecture

> 개발(docker-compose.yml) / 프로덕션(docker-compose.prod.yml + 외부 Nginx) 두 환경. 운영 배포 절차는 [../ops/production-deployment.md](../ops/production-deployment.md) 참조.

## 1. 환경별 구성

### 1.1 개발 (`docker-compose.yml`)

compose project 명은 `name: marketscope-dev` 로 명시 (기본 네트워크 자동명 `marketscope-dev_default`).

| 서비스 | 포트 (호스트:컨테이너) | 이미지 | 역할 |
|---|---|---|---|
| `db` | 5432:5432 | postgis/postgis:16-3.4 | PostgreSQL + PostGIS |
| `redis` | 6379:6379 | redis:7-alpine | 캐시 (maxmemory 256MB, allkeys-lru) |
| `migrate` | — (one-off) | local build (`./server`) | `cleanup_alembic.py` → `alembic upgrade head` |
| `seed` | — (one-off) | postgis/postgis:16-3.4 | pg_restore + stale `alembic_version` 정리 (districts 데이터 있으면 skip) |
| `backend` | 8000:8000 | local build | FastAPI (uvicorn), `env_file: .env.dev` |
| `frontend` | 3000:3000 | local build | Next.js standalone |
| `nginx` | 80:80 | nginx:1.25-alpine | 개발용 리버스 프록시 (`nginx/nginx.conf` 마운트) |

이 외 `--profile dev` 전용 서비스 2종: `backend-dev`(`./server` bind-mount + `uvicorn --reload`) / `frontend-dev`(`next dev`). 상시 서비스는 `restart: unless-stopped`, healthcheck 는 db/redis/backend 에 정의. 로컬 개발은 `docker compose up -d db redis` 만 띄우고 backend/frontend 는 호스트에서 실행해도 된다.

> **E2E 전용 포트 (`docker-compose.e2e.yml`)**: 일반 dev stack 과 충돌 없이 병행하기 위해 backend `8002:8000`, frontend `3001:3000` 으로 호스트 포트만 다르게 매핑한다. Playwright `baseURL` 기본값(`http://localhost:3001`)이 이 매핑을 가정한다.

### 1.2 프로덕션 (`docker-compose.prod.yml`)

`name:` 필드가 없어 compose project 명은 리포 디렉터리명 유래(`catchment-area-analysis`) — 이미지/네트워크 prefix 도 동일하며, `scripts/deploy/auto_deploy.sh` 의 `IMAGE_PREFIX` 가 이를 전제한다.

| 서비스 | 포트 노출 | 특이점 |
|---|---|---|
| `db` | 미노출 (내부 전용) | 보안상 호스트 포트 차단 |
| `redis` | 미노출 | 동일 |
| `migrate` | one-off | `cleanup_alembic.py` → `alembic upgrade head` (db healthy 후 실행) |
| `seed` | one-off | pg_restore + stale `alembic_version` 정리 psql (districts 데이터 있으면 skip) |
| `backend` | 8000 | 내부 Docker 네트워크. migrate → seed 완료 후 기동 |
| `frontend` | 3200:3000 | 외부 호스트 nginx 가 접근 |

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
┌──────────────────────────────────────────────────┐
│  docker network (catchment-area-analysis_default)│
│  ┌──────────┐  ┌────────┐  ┌─────────────┐       │
│  │ frontend │→ │ backend│→ │ db / redis  │       │
│  └──────────┘  └────────┘  └─────────────┘       │
└──────────────────────────────────────────────────┘
```

> 네트워크명은 compose project 명에서 유래: prod = `catchment-area-analysis_default`, dev = `marketscope-dev_default`.

- **SSE 경로**: 호스트 nginx → backend 컨테이너. `proxy_buffering off` + `X-Accel-Buffering: no` 필수 — 프록시 버퍼링 시 SSE 토큰이 뭉쳐 도착해 스트리밍이 깨진다 (교훈 [[feedback_sse_buffering]]).
- **Kakao SDK 프록시**: 프론트엔드 `/proxy/kakao-sdk` 라우트가 백엔드로 가지 않도록 nginx 라우팅 필수.
- **DB/Redis 비노출**: 프로덕션에서는 `docker compose exec db psql …` 로만 접근.

## 3. 환경변수 (요약)

`.env.example` 참고 (파일 관례: `.env`=prod · `.env.dev`=로컬 dev, config.py 우선 로드 · `.env.e2e`=E2E). 주요 항목:

| 변수 | 용도 | 프로덕션 |
|---|---|---|
| `USE_MOCK` | Mock/Real 분기 | `false` |
| `DATABASE_URL` / `DATABASE_URL_SYNC` | PostgreSQL async / sync | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis 접속 | `redis://redis:6379/0` |
| `AGENT_LOOP_VERSION` | **Agent 아키텍처 스위치** — `v2`(모델주도 루프 + Trust Kernel, config 기본값) / `pae`(레거시 롤백). mock 프로바이더는 항상 PAE 폴백 | `v2` (`.env` 에 명시) |
| `LLM_PROVIDER` | `gemini`(코드 기본값) / `anthropic` / `mock` | `anthropic` (현 운영) |
| `BACKEND_INTERNAL_URL` | 프론트 → 백엔드 rewrite 대상. **compose 파일이 `http://backend:8000` 하드코딩 주입** — `.env.example` 에는 없음 | `http://backend:8000` |
| `NEXT_PUBLIC_API_URL` | 브라우저용 (SSE 직접 호출). `/api` 로 끝나면 빌드 실패 가드 | `https://marketscope.robitlabs.co.kr` |
| `NEXT_PUBLIC_KAKAO_MAP_KEY` | Kakao SDK (빌드 타임 bake) | 발급 키 |
| `NEXT_PUBLIC_REPO_URL` | 랜딩 푸터 GitHub 링크 (선택, Phase A) | 비워두면 li 미렌더 |
| `NEXT_PUBLIC_CONTACT_EMAIL` | 푸터 mailto: 링크 (선택, Phase A) | 비워두면 "문의" 미노출 |
| `NEXT_PUBLIC_KAKAO_CHANNEL_URL` | F12 FeedbackFab kakao 모드 우선 (선택) | 둘 중 하나만 있어도 FAB 노출 |
| `NEXT_PUBLIC_FEEDBACK_FORM_URL` | F12 FeedbackFab tally 모드 폴백 (선택) | (위와 동일) |
| `NEXT_PUBLIC_PREMIUM_CTA_ENABLED` | Phase E.3 — `'true'` 일 때만 FreeLimitSurvey Premium CTA 노출 | default off |
| `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` | LLM | 필수 |
| `SEOUL_OPENDATA_API_KEY` | ETL | Real 모드에서 필수 |
| `LANGFUSE_*` | 관측 (선택) | 비워두면 비활성. `LANGFUSE_TRACING_ENVIRONMENT` 관례: `.env`=production / `.env.dev`=development / e2e=`e2e`. `LANGFUSE_SESSION_SALT` 는 고정값 필수(비우면 재시작마다 세션 해시 분절). `LANGFUSE_OTEL_INSECURE=true` 는 로컬 MITM 전용 — **prod 서버 복사 금지** |
| `E2E_LANGFUSE_{PUBLIC_KEY,SECRET_KEY,HOST,TRACING_ENVIRONMENT}` | e2e/eval 트래픽 관측 **opt-in** — `docker-compose.e2e.yml` 이 `${E2E_LANGFUSE_*:-}` 로 주입 | 기본 empty = 관측 off (e2e trace_id null 계약 보존). eval 세션만 dev 프로젝트 키 export, environment 기본 `e2e` |

`scripts/validate_env.py` 가 빌드/기동 전에 누락 검증.

> ⚠ compose 의 `environment:` 블록은 `env_file` 값과 **호스트 셸 env** 를 모두 오버라이드한다 — 배포 셸에서 `USE_MOCK`/`AGENT_LOOP_VERSION` 등이 export 돼 있으면 조용히 다른 모드로 기동될 수 있다 (교훈 [[feedback_compose_env_block_overrides_env_file]]). `auto_deploy.sh` 는 이를 위해 실행 초기에 관련 env 19종을 unset 한다.

## 4. 빌드

### Frontend (Dockerfile — deps → builder → runner)

1. builder stage: `npm ci && npm run build` — `NEXT_PUBLIC_*` 값이 이 시점에 bake
2. runner stage: standalone 출력만 복사 → `node server.js` (USER node)
3. build ARG 가드 2종 — `NEXT_PUBLIC_KAKAO_MAP_KEY` 미주입 시 빌드 실패, `NEXT_PUBLIC_API_URL` 이 `/api` 로 끝나면 빌드 실패

### Backend (Dockerfile — builder → runner)

1. Python 3.12 slim multi-stage
2. builder: `pip install --no-cache-dir --prefix=/install .` — 일반 소스 설치. (`pip install -e ".[dev]"` editable + dev extras 는 프로덕션 이미지가 아닌 **CI/로컬 개발 전용** — dev 의존성은 이미지에 미포함)
3. runner: `CMD uvicorn server.main:app --host 0.0.0.0 --port 8000` — `--workers` 플래그 없음 (**단일 워커**), 비루트 `appuser` 실행

**pip SSL 우회 build-arg (선택)**: 사내/제한된 네트워크에서 `CERTIFICATE_VERIFY_FAILED` 발생 시:

```bash
docker compose build \
  --build-arg PIP_INDEX_URL=https://pypi.org/simple \
  --build-arg 'PIP_TRUSTED_HOST=pypi.org files.pythonhosted.org' \
  backend
```

기본값은 HTTPS PyPI(기존 동작 유지). build-arg 는 `/etc/pip.conf` 에 렌더되어 pip isolated build subprocess 까지 전파된다. `docker-compose.e2e.yml` 의 migrate/backend 에서도 `${PIP_INDEX_URL}` / `${PIP_TRUSTED_HOST}` 를 그대로 받는다.

## 5. 배포 (프로덕션)

### 5.1 자동배포 (기본 경로)

origin/main push 를 **systemd timer 폴링(2분)** 이 감지해 자동 배포한다:

```
deploy/systemd/marketscope-autodeploy.timer (OnUnitActiveSec=2min)
  → marketscope-autodeploy.service (oneshot, TimeoutStartSec=1800)
    → scripts/deploy/auto_deploy.sh
       flock → fetch → no-op 판정 → 가드(branch/dirty/ahead — reset 절대 안 함)
       → CI green 게이트(GitHub check-runs API) → prev-auto 재태그 → ff merge
       → build(.env.dev 임시 이동) → up -d → healthy 대기 → flush_cache.py
       → smoke → 실패 시 prev-auto 자동 롤백
```

설치는 `sudo bash scripts/deploy/install_autodeploy.sh`, 상태는 `data/deploy-logs/last-deploy.json`. result 값 해소표·활성/비활성 커맨드 등 운영 상세는 [../ops/production-deployment.md](../ops/production-deployment.md) §6 참조.

### 5.2 수동 배포 순서

수동 배포 세션 전에는 자동배포 timer 를 disable 권장 (위 ops 문서 참조).

1. `scripts/validate_env.py` — 필수 env 확인
2. `.env.dev` 가 있으면 빌드 전 임시 이동 (프론트 빌드 bake-in 방지)
3. `docker compose -f docker-compose.prod.yml build`
4. `docker compose -f docker-compose.prod.yml up -d` — 의존 체인(db/redis → migrate → seed → backend → frontend)이 자동 순서 실행. seed 는 데이터 있으면 skip
5. `docker compose -f docker-compose.prod.yml exec -T backend python scripts/flush_cache.py` — report 계열 캐시 포이즈닝 방지 (**배포 필수 스텝**)
6. smoke: `:8000/health` · `:3200` · 외부 도메인 `/`(frontend) + `/api/health/detail`(backend — 외부에서 backend 루트 `/health` 는 미노출) · `/api/districts?limit=1` total>0
7. 호스트 `nginx -s reload` (nginx 설정/인증서 변경 시)

상세 runbook: [../ops/production-deployment.md](../ops/production-deployment.md), [../ops/runbook.md](../ops/runbook.md).

## 6. CI 파이프라인 (`.github/workflows/ci.yml`)

push·PR(main) 마다 5개 잡이 실행된다. 자동배포의 **CI green 게이트**가 이 check-runs 결과를 조회해 실패 SHA 배포를 차단한다.

| 잡 | 내용 |
|---|---|
| `backend-lint` | `ruff check server/` + `ruff format --check server/` |
| `frontend-lint` | `npm ci` → `npx next lint` → `npx tsc --noEmit` |
| `backend-test` | `pytest -v -m "not real" --cov=server` (dummy env: USE_MOCK=true·LLM_PROVIDER=mock) + coverage XML artifact. `@pytest.mark.real` DB 통합 6케이스는 deselect — 로컬 opt-in |
| `docker-build` | backend/frontend 이미지 빌드 검증 (KAKAO key dummy build-arg) |
| `security-audit` | pip-audit + npm audit (`\|\| true` 비차단) |

Playwright E2E 실행 잡은 CI 에 **없음** — E2E 는 로컬 `cd frontend && npm test` 수동 실행.

## 7. 모니터링 & 로깅

- Docker `json-file` log driver, max-size=50m, max-file=5 (서비스별)
- `/api/health/detail` — DB pool / Redis / session 메트릭 + `langfuse` 블록(enabled/tracer_valid/client_initialized/sampling_rate)
- `/metrics` — SSE 게이지 / singleflight / `langfuse_trace_missing_total`(무음사망 카운터) / 경로별 latency (인메모리 집계)
- Langfuse (선택): `LANGFUSE_*` 설정 시 LLM trace — 무음사망 진단 플레이북은 [ops/runbook.md](../ops/runbook.md) 참조
- 자동배포 로그: journal(`marketscope-autodeploy.service`) + `data/deploy-logs/`
- 향후: Prometheus exporter 연동

## 8. 재해 복구

- DB 백업: `scripts/backup_db.sh` (주기 실행 권장)
- Redis 는 캐시이므로 복구 불필요 (TTL 재적재)
- 세션 스토어는 인메모리 → 서버 재시작 시 유실 (UX 영향 적음)
- 배포 실패 시 이미지 레벨 롤백은 auto_deploy 가 `prev-auto` 태그로 자동 수행 — DB 롤백은 수동 runbook
- 상세 시나리오: [../ops/disaster-recovery.md](../ops/disaster-recovery.md)

## 9. 부하 테스트 & 용량 상한

**loadtest/ 스택 구현 완료**: `locustfile.py`(SSE chat 부하) + `scenarios/` 8종(`a_basic_summary` ~ `h_redis_failure`: ramp / mixed intent / greeting 단축 / semaphore 포화 / spike / 세션 격리 / mid-stream disconnect / Redis 장애) + `run_all_tests.py` + `sse_client.py`. 실행 전제: `USE_MOCK=true LLM_PROVIDER=mock` backend `:8002`, `pip install -e ".[loadtest]"`. 사용법은 [loadtest/README.md](../../loadtest/README.md).

현재 상한:

- 레이트리밋: config 에 `rate_limit_global`(60/min)·`rate_limit_chat`(10/min) 정의 — 단, `rate_limit_chat` 은 chat 라우트에 데코레이터 미적용(전역 60/min 만 유효). 적용 여부는 별도 결정 대기
- Agent 동시 실행 semaphore=20 (`chat.py::_MAX_CONCURRENT_CHATS`)
- DB pool 10 + overflow 20
- SSE queue 256 events (backpressure — PAE 경로의 이벤트 큐, v2 루프는 큐 미사용)
