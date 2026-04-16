# Deployment Root-Cause Fixes — MarketScope AI

## Context

2026-04-16 prod 배포(marketscope.robitlabs.co.kr) 세션에서 6건의 이슈를 **현장 대응**으로 해결했습니다. 각각은 임시 조치였고, 다른 환경/재배포 시 재발합니다. 이 plan은 근본 원인을 제거해 **"docker compose up + nginx reload" 한 번에 정상 기동**되는 상태를 만드는 것이 목표입니다.

### 세션 중 발생했던 문제
1. `alembic upgrade head` 실패 — `alembic_version` 테이블에 `001`+`003` 공존
2. 호스트 포트 80 충돌 — 내장 `nginx` 서비스 vs 호스트 Let's Encrypt nginx
3. `/api/api/chat` 404 — `NEXT_PUBLIC_API_URL=https://.../api`로 `/api` 이중 접미
4. SSE 스트리밍 버퍼링 — 호스트 nginx `proxy_buffering on`(default)
5. 지도 로딩 실패 — `/api/kakao-sdk`가 backend로 라우팅되어 404
6. `.env` 부재로 빌드 → `NEXT_PUBLIC_KAKAO_MAP_KEY` 빈 문자열로 이미지에 baked-in

### 탐색 결과 요약
- Kakao SDK 호출 지점: **단 1곳** — `frontend/src/components/map/MapContainer.tsx:33`
- Alembic chain: 단일 head (`001 → 002 → 003`), migration 정의는 정상. 문제는 **시드 덤프에 stale `001`이 박힌 데이터 잔존**
- `seed` 서비스의 cleanup은 **pg_restore 직후**에만 실행 — 재실행 시 skip되어 cleanup도 skip
- `nginx/nginx.conf`는 내장용으로 이미 `proxy_buffering off` 보유. 외부 nginx용 샘플은 없음
- `frontend/Dockerfile`은 build ARG 검증 없음
- `.env.example`에 `NEXT_PUBLIC_API_URL` 포맷 규칙 미명시

---

## Scope

**근본 해결**(영구) vs **방어적 가드**(재발 방지)를 분리해서 **필수 5건 + 선택 2건**만 반영.

---

## P0 — 필수 (데이터 파이프라인 복원력)

### 1. `alembic_version` cleanup을 migrate **전**으로 이동

**문제**: 현 `seed` 서비스의 cleanup은 `pg_restore` 블록 안에 있어 재실행 시(`COUNT > 0`) skip됨 → 기존 볼륨의 stale row가 영원히 남음 → migrate 실패.

**수정**: `migrate` 서비스의 `command`를 cleanup + upgrade로 묶어 **매번 실행 보장**.

파일: `docker-compose.yml`, `docker-compose.prod.yml`
```yaml
migrate:
  build: { context: ./server, target: runner }
  command: >
    bash -c "
      python -c \"
import psycopg2, os
conn = psycopg2.connect(os.environ['DATABASE_URL_SYNC'])
cur = conn.cursor()
cur.execute(\\\"CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) PRIMARY KEY);\\\")
cur.execute(\\\"DELETE FROM alembic_version WHERE version_num NOT IN (SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1);\\\")
conn.commit()
      \" &&
      alembic upgrade head
    "
  environment:
    DATABASE_URL_SYNC: postgresql://marketscope:devpassword@db:5432/marketscope
  depends_on:
    db: { condition: service_healthy }
```
(server runner 이미지에 `psycopg2-binary`가 이미 있어 추가 설치 불필요 — `server/pyproject.toml` 확인됨)

**Seed 서비스**에서는 cleanup 블록을 그대로 유지(방어) 또는 제거. 유지가 안전.

### 2. `generate_seed.py`에서 `alembic_version` 테이블 제외

**문제**: 시드 덤프 생성 시 `alembic_version` 내용물이 같이 덤프됨 → 복원 시 stale row 재삽입. 근본적으로 이 테이블은 migration 런타임이 관리해야 하므로 dump에 포함되면 안 됨.

**수정**: `scripts/generate_seed.py`의 `pg_dump` 호출에 `--exclude-table=alembic_version` 추가.

파일: `scripts/generate_seed.py`

**이후 작업**: 로컬 clean DB에서 `setup_db.py --full` 실행 → `generate_seed.py` 재실행 → 새 덤프 커밋(Git LFS). 이 덤프는 어떤 환경에 복원해도 alembic이 스스로 초기화.

---

## P1 — 필수 (배포 구성 일관성)

### 3. `/api/kakao-sdk` → `/_proxy/kakao-sdk`로 이동 (네임스페이스 분리)

**문제**: `/api/*` 네임스페이스가 **backend API**와 **Next.js server route**를 동시에 사용 → 외부 프록시에서 경로 예외처리 필요.

**수정**:
- `frontend/src/app/api/kakao-sdk/route.ts` → `frontend/src/app/_proxy/kakao-sdk/route.ts`로 이동
- `frontend/src/components/map/MapContainer.tsx:33`의 `fetch('/api/kakao-sdk')` → `fetch('/_proxy/kakao-sdk')`

호출 지점이 **단 1곳**이라 변경 비용 최소. 이후 외부 nginx는 `location /api/` 하나로 backend 라우팅 — 예외 불필요.

### 4. 외부 리버스 프록시 샘플 설정 + 배포 문서

**문제**: SSE `proxy_buffering off`는 외부 nginx 몫인데, 리포지토리에 가이드 없음.

**수정**: 신규 파일 생성
- `nginx/external-reverse-proxy.conf.example` — marketscope.robitlabs.co.kr 블록 샘플 (현재 호스트 nginx에 반영된 내용)
- `docs/setup/production-deployment.md` — 배포 체크리스트:
  - 호스트 nginx 존재 시 `docker-compose.prod.yml` 사용 (내장 nginx 없음)
  - 외부 nginx `/api/` 블록에 `proxy_buffering off`, `proxy_read_timeout 300s`, `chunked_transfer_encoding on` **필수**
  - `.env` 필수 키 리스트 + 누락 시 증상

### 5. `.env.example` 규칙 + `frontend/Dockerfile` 빌드 ARG 검증

**문제**:
- `NEXT_PUBLIC_API_URL` 포맷(`/api` 포함 금지) 문서 없음 → 외부 배포용 compose에 `.../api`로 하드코딩된 사례 발생
- `.env` 없이 빌드 → build-time env가 **빈 문자열로 이미지에 baked-in**되어 재빌드 전까지 복구 불가

**수정 A** — `.env.example` 주석 추가:
```bash
# 프론트엔드 API base URL — 루트 도메인만 (슬래시/api 절대 금지)
# 올바른 예: https://marketscope.example.com
# 잘못된 예: https://marketscope.example.com/api  ← 프론트 코드가 /api를 자체 추가함
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**수정 B** — `frontend/Dockerfile` builder 스테이지에 가드:
```dockerfile
ARG NEXT_PUBLIC_KAKAO_MAP_KEY
ARG NEXT_PUBLIC_API_URL
RUN test -n "$NEXT_PUBLIC_KAKAO_MAP_KEY" || (echo "ERROR: NEXT_PUBLIC_KAKAO_MAP_KEY build arg required" >&2; exit 1)
RUN echo "$NEXT_PUBLIC_API_URL" | grep -qv '/api$' || (echo "ERROR: NEXT_PUBLIC_API_URL must not end with /api" >&2; exit 1)
```

---

## P2 — 선택 (운영 편의)

### 6. `docker-compose.prod.yml`에서 DB/Redis 포트 외부 노출 제거

**현 상태**: `5432`, `6379`를 `0.0.0.0`으로 바인딩 → 내부 전용인데 외부 공격면 증가.

**수정**: `ports: ["5432:5432"]` → 삭제 (서비스 간 통신은 Docker network로 충분). 디버깅 필요 시 `docker exec` 또는 override 파일.

### 7. `scripts/validate_env.py` (런타임 전 env 검증 스크립트)

**수정**: 신규 스크립트로 필수 키 존재/포맷 체크. CI 및 로컬 기동 전 훅. Dockerfile 가드와 중복되지만 빠른 피드백 제공.

---

## 파일 변경 요약

| 우선순위 | 파일 | 변경 |
|---------|------|------|
| P0-1 | `docker-compose.yml`, `docker-compose.prod.yml` | `migrate` command에 cleanup 추가 |
| P0-2 | `scripts/generate_seed.py` | `--exclude-table=alembic_version` |
| P0-2 | `data/seed/marketscope_seed.dump` | 재생성 후 커밋 (Git LFS) |
| P1-3 | `frontend/src/app/_proxy/kakao-sdk/route.ts` | `api/kakao-sdk/route.ts`에서 이동(신규 경로) |
| P1-3 | `frontend/src/app/api/kakao-sdk/` | 디렉토리 삭제 |
| P1-3 | `frontend/src/components/map/MapContainer.tsx` | L33 fetch URL 변경 |
| P1-4 | `nginx/external-reverse-proxy.conf.example` | 신규 |
| P1-4 | `docs/setup/production-deployment.md` | 신규 |
| P1-5 | `.env.example` | `NEXT_PUBLIC_API_URL` 주석 + 규칙 |
| P1-5 | `frontend/Dockerfile` | ARG 검증 RUN 추가 |
| P2-6 | `docker-compose.prod.yml` | DB/Redis `ports:` 제거 |
| P2-7 | `scripts/validate_env.py` | 신규 |

---

## Verification

### 단위 검증 (각 항목 적용 후)

**P0-1 cleanup ordering**:
```bash
# 시뮬레이션: alembic_version에 stale row 강제 삽입 후 재기동
docker exec catchment-area-analysis-db-1 psql -U marketscope -d marketscope \
  -c "INSERT INTO alembic_version VALUES ('001'), ('002');"
docker compose -f docker-compose.prod.yml up -d migrate
docker compose -f docker-compose.prod.yml logs migrate | grep -i "overlaps\|error"  # → 0 lines
```

**P0-2 seed dump regeneration**:
```bash
python scripts/generate_seed.py
pg_restore --list data/seed/marketscope_seed.dump | grep -i alembic_version  # → 0 lines
```

**P1-3 kakao-sdk 이동**:
```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3200/_proxy/kakao-sdk  # → 200
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3200/api/kakao-sdk      # → 404 (정상)
# 브라우저 하드 리로드 → 지도 렌더 확인
```

**P1-4 외부 프록시 SSE**:
```bash
curl -s -N -X POST https://marketscope.robitlabs.co.kr/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"강남역 분석","session_id":"verify-sse"}' | head -10
# → "data: {type: thinking}" 이벤트가 1초 이내 첫 도달
```

**P1-5 Dockerfile 가드**:
```bash
# 의도적으로 키 비우고 빌드 → 실패해야 정상
NEXT_PUBLIC_KAKAO_MAP_KEY= docker compose -f docker-compose.prod.yml build frontend
# → "ERROR: NEXT_PUBLIC_KAKAO_MAP_KEY build arg required" 로 exit 1
```

### 통합 E2E (clean slate)
```bash
# 1. 볼륨 완전 초기화
docker compose -f docker-compose.prod.yml down -v
# 2. .env 로부터 시작
docker compose -f docker-compose.prod.yml up -d --build
# 3. 모든 서비스 healthy 확인
docker compose -f docker-compose.prod.yml ps | grep -c healthy  # → 2 이상 (db, backend)
# 4. 브라우저에서 marketscope.robitlabs.co.kr 접속:
#    - 지도 로드
#    - 폴리곤 클릭 → SummaryCard 실시간 스트리밍
#    - 채팅 "강남역 분석해줘" → thinking/tool/text 이벤트 단계별 표시
# 5. 재기동 (볼륨 유지) 후 재검증
docker compose -f docker-compose.prod.yml restart
```

---

## Out of Scope

- 호스트 nginx 설정(`/etc/nginx/sites-available/robitlabs`) 자동화 — 서버별 운영 영역이라 리포지토리 외부 유지. 샘플만 `nginx/external-reverse-proxy.conf.example`로 제공.
- `NEXT_PUBLIC_*` 런타임 주입 전환 — 재빌드 없이 키 교체 가능하지만 Next.js 14 App Router에서 구현 비용이 큼. 현재 빌드타임 + ARG 검증으로 충분.
- 시크릿 관리(Vault 등) — 현 `.env` 파일 방식 유지.
