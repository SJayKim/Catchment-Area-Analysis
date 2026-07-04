# Production Deployment — MarketScope AI

호스트(외부) nginx 가 SSL/라우팅을 담당하고 docker-compose 는 frontend/backend만 띄우는 **권장 프로덕션 토폴로지** 가이드.

대상 도메인 예: `marketscope.robitlabs.co.kr`

---

## 1. 필수 준비물

| 항목 | 확인 방법 |
|------|-----------|
| Docker Engine 24+ / Compose v2 | `docker version`, `docker compose version` |
| 호스트 nginx (80/443 바인딩) | `systemctl status nginx` |
| Let's Encrypt 인증서 발급 완료 | `ls /etc/letsencrypt/live/<domain>/` |
| `.env` 파일 (아래 필수 키 모두) | `cat .env` |

### `.env` 필수 키 (빠지면 빌드/기동 실패)

| 키 | 예시 | 누락 시 증상 |
|---|------|-------------|
| `NEXT_PUBLIC_KAKAO_MAP_KEY` | `abc123...` | 지도 SDK 403 → 지도 빈 화면 (현 Dockerfile은 빌드 시점에 fail) |
| `NEXT_PUBLIC_API_URL` | `https://marketscope.example.com` | 프런트 API 호출이 잘못된 도메인으로 감 |
| `GOOGLE_API_KEY` 또는 `ANTHROPIC_API_KEY` | `AIza...` | Agent LLM 호출 실패 → 챗봇 응답 없음 |
| `SEOUL_OPENDATA_API_KEY` | 서울열린데이터 API 키 | Real 데이터 ETL 불가(Mock 모드는 무관) |

> **주의:** `NEXT_PUBLIC_API_URL` 은 반드시 루트 도메인만 (`/api` 경로 금지). 프런트 코드가 `/api` 를 자체 부착한다. 잘못된 값이면 `/api/api/chat` 404 발생 — 재발 방지 가드가 `frontend/Dockerfile` 에 들어있음.

---

## 2. 배포 체크리스트

### 첫 배포

```bash
# 1. 리포지토리 clone, .env 세팅
git clone <repo> && cd Catchment-Area-Analysis
cp .env.example .env
vim .env   # 위 필수 키 모두 채우기

# 2. 환경 사전 검증 (선택)
python scripts/validate_env.py

# 3. 호스트 nginx 설정 복사
sudo cp nginx/external-reverse-proxy.conf.example \
        /etc/nginx/sites-available/marketscope
sudo ln -s /etc/nginx/sites-available/marketscope \
           /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 4. 컨테이너 기동 (prod compose는 nginx 내장 서비스 없음)
docker compose -f docker-compose.prod.yml up -d --build

# 5. Health check
curl -s https://marketscope.robitlabs.co.kr/health
curl -s -I https://marketscope.robitlabs.co.kr/            # → 200
curl -s -o /dev/null -w '%{http_code}\n' \
     https://marketscope.robitlabs.co.kr/proxy/kakao-sdk   # → 200
```

### 재배포 (기존 볼륨 유지)

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
# migrate 서비스의 cleanup_alembic 이 stale 버전 row 를 자동 제거
```

### 완전 초기화

```bash
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d --build
# seed 서비스가 data/seed/marketscope_seed.dump 복원
```

---

## 3. 외부 nginx 필수 설정 포인트

`nginx/external-reverse-proxy.conf.example` 참조. 직접 작성 시 반드시 포함해야 하는 항목:

| 위치 | 설정 | 이유 |
|------|------|------|
| `location /api/chat` | `proxy_buffering off` | SSE 스트리밍 — 버퍼링 켜져 있으면 첫 토큰 지연 |
| `location /api/chat` | `proxy_read_timeout 300s` | Agent 응답 5분까지 허용 |
| `location /api/chat` | `chunked_transfer_encoding on` | SSE chunked 전송 유지 |
| `location /api/` | proxy_pass → backend:8000 | Next.js `/api/*` 가 아닌 FastAPI 로 라우팅 |
| `location /` | proxy_pass → frontend:3200 | `/proxy/kakao-sdk` 도 여기 포함 |

> **히스토리:** 과거 `/api/kakao-sdk` 는 Next.js server route였지만 `/api/*` 네임스페이스 겹침으로 매 배포마다 exact-match exception 필요. 현재 `/proxy/kakao-sdk` 로 분리 — 외부 nginx 설정이 단순해짐.

---

## 4. 포트 정책

| 서비스 | 외부 노출 | 내부 포트 |
|--------|-----------|-----------|
| frontend | `:3200` → 3000 | 3000 |
| backend | `:8000` → 8000 | 8000 |
| db (PostgreSQL) | **없음** (docker network 전용) | 5432 |
| redis | **없음** (docker network 전용) | 6379 |

디버깅용 psql/redis-cli 접속이 필요하면 `docker compose exec db psql -U marketscope` 처럼 exec 를 쓸 것. `ports:` 재개방은 금지(공격면 증가).

---

## 5. 트러블슈팅

| 증상 | 확인 | 해결 |
|------|------|------|
| `/api/chat` 첫 응답 5~10초 지연 | `curl -sN -X POST ...` 로 이벤트 타임라인 | 외부 nginx `proxy_buffering off` 누락 점검 |
| 지도 빈 화면 | 브라우저 Network `proxy/kakao-sdk` | 200 인지 확인, 빌드 시 `NEXT_PUBLIC_KAKAO_MAP_KEY` 전달 여부 |
| `/api/api/chat` 404 | Network 탭 URL | `.env` `NEXT_PUBLIC_API_URL` 끝에 `/api` 붙어있음 → 제거 후 재빌드 |
| alembic "Multiple head revisions" | `docker compose logs migrate` | `cleanup_alembic.py` 실행 여부 — 커스텀 command 변경됐는지 확인 |
| seed 서비스 skip 후 데이터 없음 | `docker compose exec db psql ... -c "SELECT COUNT(*) FROM districts;"` | `down -v` 로 볼륨 완전 초기화 후 재기동 |

---

## 6. 자동배포 (auto deploy on push)

origin/main push 를 systemd timer(2분 폴링)가 감지해 자동 배포한다. 설계: [plan/infra/auto-deploy-on-push.md](../plan/infra/auto-deploy-on-push.md).

```
timer(2min) → scripts/deploy/auto_deploy.sh
  fetch → 신규 커밋 없으면 no-op → dirty/ahead 가드 → CI green 게이트(check-runs API)
  → prev-auto 재태그 → ff merge → build(.env.dev 임시이동) → up -d → healthy 대기
  → flush_cache.py → smoke 4항목 → 실패 시 prev-auto 자동 롤백
```

### 활성화 / 비활성화

```bash
sudo bash scripts/deploy/install_autodeploy.sh                  # 설치 + enable --now
sudo systemctl disable --now marketscope-autodeploy.timer       # 중지 (수동 배포 세션 전 권장)
systemctl list-timers marketscope-autodeploy.timer              # 다음 발화 확인
```

### 상태 확인

```bash
cat data/deploy-logs/last-deploy.json        # 최근 결과 {result, sha, detail, ts, log}
ls -t data/deploy-logs/deploy-*.log | head   # run 별 로그 (no-op tick 은 로그 미생성)
journalctl -u marketscope-autodeploy.service -n 50   # no-op/차단 tick 포함 전체
bash scripts/deploy/auto_deploy.sh           # 수동 1회 실행 (신규 커밋 없으면 no-op)
bash scripts/deploy/auto_deploy.sh --force   # 현 origin/main tip 강제 재배포
```

### `result` 값과 해소법

| result | 의미 | 해소 |
|---|---|---|
| `SUCCESS` | 배포 + smoke 통과 | — |
| `BLOCKED_DIRTY` | 허용목록(`.claude/settings.local.json`) 외 tracked 변경 존재 | 커밋/스태시 정리. 스크립트는 절대 reset 하지 않음 |
| `BLOCKED_AHEAD` | 서버 로컬 커밋이 origin 보다 ahead | 수동 push 후 다음 tick 에 자동 재개 |
| `BLOCKED_CI` | 해당 SHA 의 check-runs failure. 같은 SHA 재시도 안 함 | CI fix 커밋 push (새 SHA 는 자동 재개). 강제는 `--force` |
| `BLOCKED_BRANCH` | HEAD 가 main 이 아님 | `git switch main` |
| `ROLLED_BACK` | 배포 실패 → `prev-auto` 이미지 복귀 + smoke OK | run 로그에서 실패 스텝 확인 후 fix push |
| `ROLLBACK_FAILED` | 롤백 후에도 smoke 실패 | **수동 개입 필수** — §5 트러블슈팅 + [disaster-recovery.md](disaster-recovery.md) |

### 수동 배포와의 관계

- 수동 배포 세션(대규모 마이그레이션·DB 복구 동반) 전에는 timer 를 **disable** 하고, 끝나면 다시 enable. flock 이 겹침을 막지만 수동 작업 중 자동 배포가 끼어드는 것 자체를 피하는 게 안전.
- DB 마이그레이션/시드는 기존 migrate init-container 관례 그대로 (자동 롤백은 이미지 레벨만). DB 롤백은 수동 runbook — 복원 문장은 `public.` 한정 + `--single-transaction` 패턴 유지.
- CI 게이트는 GitHub 무인증 API(60 req/h) 사용 — private 전환 시 서비스 env 에 `GITHUB_TOKEN` 추가.

---

## 7. 보안 체크

- [ ] 호스트 nginx 가 HTTPS 강제 (`return 301 https://...`)
- [ ] DB/Redis 포트 외부 노출 없음
- [ ] `.env` 는 git ignored (`grep -F '.env' .gitignore`)
- [ ] LLM API 키는 서버 환경변수에만 (클라이언트 번들 금지)

---

*작성일: 2026-04-17*
