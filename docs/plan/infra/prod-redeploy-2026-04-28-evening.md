# Prod Redeploy — 2026-04-28 저녁 (district-click-race fix)

> 목적: git main `441ef62` (= `7941726` Round 1 + `ba9553f` Round 2 + `441ef62` 검증 자산) 을 프로덕션에 반영. **부수적으로 dev/prod compose project-name 충돌로 인해 prod frontend (`:3200`) 가 stop 된 상태이므로 동시에 복구**.

## 1. Context

### 1.1 현재 장애 상태
- `https://marketscope.robitlabs.co.kr` → **502 Bad Gateway**
- 외부 nginx (`/etc/nginx/sites-enabled/robitlabs`) 가 `marketscope.robitlabs.co.kr → 127.0.0.1:3200` (frontend) + `→ 127.0.0.1:8000` (backend `/api/*`) 로 라우팅하지만, **`:3200` 에 떠있는 컨테이너 없음** (확인: `ss -tlnp | grep 3200` → empty).
- 원인: dev `docker-compose.yml` 과 prod `docker-compose.prod.yml` 이 동일 project name `catchment-area-analysis` 를 공유함. 본 세션에서 dev compose 의 `up -d frontend backend` 를 실행한 결과 prod frontend 컨테이너 (`:3200` mapping) 가 dev 빌드 (`:3000` mapping) 로 교체되었고, `:3000` 은 `robitlabs_home_container` 가 점유 중이라 frontend 가 떠지지 못함 → 결과적으로 `:3200` 도 빈 상태.

### 1.2 적용해야 하는 코드 fix
| Commit | 내용 |
|---|---|
| `7941726` | sendMessage abort+restart, currentRequestId staleness, ChatPanel disabled 분리, backend per-session inflight cancel |
| `ba9553f` | useMapSync 가드 완화, setPreview watchdog 10s, ChatPanel previewError UI |
| `441ef62` | E2E 회귀 자산 4 spec / 12 testcase |

### 1.3 안전장치
- 직전 prod 이미지 보존:
  - frontend: `catchment-area-analysis-frontend:prev-2026-04-24` (`1a5cf08c6567`)
  - backend: `catchment-area-analysis-backend:prev-2026-04-28a` (`63a494302bef`)
- DB/Redis volume (`catchment-area-analysis_postgres-data`, `catchment-area-analysis_redis-data`) 는 변경 없음 — db/redis 컨테이너만 재기동, 데이터 보존.

## 2. Scope

### In-Scope
- ✅ dev compose 잔재 컨테이너 정리 (frontend / backend / migrate / seed / nginx)
- ✅ `.env` (prod credential) 사용한 prod compose 빌드 + 기동
- ✅ live smoke test (curl 11종 + Playwright `f01-preview-real-db.spec.ts`)
- ✅ `fix-verify-fe` 임시 verifier 컨테이너 cleanup
- ✅ 새 prod image 에 `prev-2026-04-28b` tag 부여 (rollback safety)

### Out-of-Scope
- ⛔ DB schema 변경 (alembic head 그대로)
- ⛔ nginx 외부 config 변경
- ⛔ Docker Hub registry push (호스트 로컬 이미지 사용)
- ⛔ 이미지 cache prune

## 3. Design — 단계별 실행 절차

### Pass 1 — 사전 점검 (verify only)
1. `docker ps` — 현재 떠있는 컨테이너 정리 확인
2. `.env` 의 `USE_MOCK=false`, `LLM_PROVIDER=anthropic` 확인 (이미 확인됨)
3. `git log --oneline -3` — 배포할 commit 검증
4. `ss -tlnp | grep -E ':3200|:8000'` — `:3200` 비어있고 `:8000` 점유 상태 확인

### Pass 2 — Prod 빌드 + 배포 (destructive)
1. `fix-verify-fe` 컨테이너 stop + rm (임시 verifier 더 이상 불필요)
2. `.env.dev` 임시 이동 → `predeploy-2026-04-28e.bak` (prod build 시 dev URL 박힘 방지)
3. `docker compose -f docker-compose.prod.yml build frontend backend migrate`
4. `docker compose -f docker-compose.prod.yml up -d` (db/redis volume 그대로, migrate/seed 자동 실행)
5. `.env.dev` 복구
6. ~30s 대기 후 health check

### Pass 3 — Live Smoke Verification (curl + Playwright)
| # | 검증 | 합격 기준 |
|---|------|-----------|
| P1 | `curl http://127.0.0.1:3200` | 200 + `data-theme=light` |
| P2 | `curl http://127.0.0.1:8000/health` | `{"status":"ok"}` |
| P3 | `curl https://marketscope.robitlabs.co.kr` | 200 (외부 nginx 통과) |
| P4 | `curl https://marketscope.robitlabs.co.kr/api/health/detail` | `use_mock=false`, `llm_provider=anthropic` |
| P5 | `curl https://marketscope.robitlabs.co.kr/api/districts?limit=3` | 1650 상권 정상 |
| P6 | `curl https://marketscope.robitlabs.co.kr/api/districts/3120189/preview` | 강남역 preview JSON |
| P7 | Playwright `f01-preview-real-db.spec.ts` (E2E_BASE_URL=https://marketscope.robitlabs.co.kr) | 3/3 PASS |
| P8 | `docker exec frontend grep -l currentRequestId /app/.next/server/chunks/*.js` | ≥1 (fix baked-in) |
| P9 | SSE chat `/api/chat` curl mini round | `done.trace_id` 포함 |

### Pass 4 — Rollback Safety + Cleanup
1. 새 prod image 에 `prev-2026-04-28b` tag 부여
2. `docker images | head -10` — tag 확인
3. (선택) 정상 확인 후 신규 e2e spec dir `/tmp/pw-results` 청소

### 롤백 절차 (만약 Pass 3 실패 시)
```bash
docker tag catchment-area-analysis-frontend:prev-2026-04-24 catchment-area-analysis-frontend:latest
docker tag catchment-area-analysis-backend:prev-2026-04-28a catchment-area-analysis-backend:latest
docker compose -f docker-compose.prod.yml up -d
```
직전 정상 동작 image 로 즉시 복귀.

## 4. Checklist

- [ ] **Pass 1** 사전 점검 4건
- [ ] **Pass 2-1** fix-verify-fe stop + rm
- [ ] **Pass 2-2** .env.dev 임시 이동
- [ ] **Pass 2-3** prod compose build (frontend + backend + migrate)
- [ ] **Pass 2-4** prod compose up -d
- [ ] **Pass 2-5** .env.dev 복구
- [ ] **Pass 3** live smoke P1~P9
- [ ] **Pass 4** prev-2026-04-28b tag 부여
- [ ] commit + push (status 업데이트)

## 5. 재검토 (Self-Review Gate)

| 엣지케이스 | 다룸? | 대응 |
|------------|-------|------|
| `:3000` 점유 중 robitlabs_home_container | YES | prod compose 의 frontend 는 `:3200` mapping 이라 영향 없음 |
| migrate 실패 (alembic head mismatch) | YES | 이전 배포에서 이미 alembic 005 적용. 재실행 시 idempotent |
| .env.dev 복구 누락 | YES | 명시적 mv + 검증 |
| ANTHROPIC API 키 만료 | NO | 이전 prod 정상 동작했으니 유효 가정 |
| Playwright real-DB spec 의 district code | YES | `3120189`, `3110221`, `3120240` — real DB 에 존재 확인됨 |
| nginx (외부) 캐시 / 502 cache | YES | systemd reload 가능 (필요시) |
| 빌드 시간이 오래 걸려 prod 다운타임 길어짐 | YES | build 는 image build 일 뿐 — up -d 시점만 짧은 컨테이너 교체 (~10s). 이미 :3200 비어있으므로 추가 다운타임 0 |

## 6. Scenario (E2E Ring Mapping)

| Ring | ID | 시나리오 | 기대 |
|------|-----|----------|------|
| Ring0 | R0-PROD-HEALTH | `/api/health/detail` 응답 | `use_mock=false`, `llm_provider=anthropic` |
| Ring1 | R1-PREVIEW-RAPID-SWITCH | `f01-preview-real-db::A→B→A` | preview 단조 갱신 |
| Ring1 | R1-PREVIEW-AI-INTERRUPT | `f01-preview-real-db::A→AI→B` | preview B 가 진행 중 chat 도중 정상 표시 |
| Ring1 | R1-PREVIEW-3-RAPID | `f01-preview-real-db::A→B→C` | preview C |
| Ring0 | R0-FIX-BAKED | `grep currentRequestId` in `/app/.next` | ≥1 hit |

## 7. Pass 반복

- **Pass 1** (사전 점검) — 1분
- **Pass 2** (build + 기동) — 약 3-5분 (frontend standalone 빌드 시간이 가장 길음)
- **Pass 3** (live smoke) — 2-3분
- **Pass 4** (cleanup + tag) — 30s

총 ETA: ~10분.

## 8. Agent 모델 선택

| Phase | 작업 | 모델 |
|-------|------|------|
| Plan/Design | 본 문서 | opus (현재) |
| Build / 검증 | bash + curl + playwright | opus (현재) |

## 9. Validation

| 항목 | 명령 | 기대 |
|------|------|------|
| `:3200` health | `curl -sS http://127.0.0.1:3200 -o /dev/null -w "%{http_code}\n"` | 200 |
| `:8000` health | `curl -sS http://127.0.0.1:8000/health` | `{"status":"ok"}` |
| 외부 도메인 | `curl -sS https://marketscope.robitlabs.co.kr -o /dev/null -w "%{http_code}\n"` | 200 |
| fix baked | `docker exec catchment-area-analysis-frontend-1 sh -c 'grep -rl currentRequestId /app/.next 2>/dev/null \| wc -l'` | ≥1 |
| 회귀 | `playwright test e2e/ring1-features/f01-preview-real-db.spec.ts --project=chromium` against prod URL | 3/3 PASS |

## 10. Metadata

| 항목 | 값 |
|------|-----|
| 작성자 | Claude (Opus 4.7) |
| 작성일 | 2026-04-28 (저녁, KST) |
| 우선순위 | P0 (prod 502 라이브 장애) |
| 영향 범위 | prod frontend / backend / migrate (db/redis 데이터 보존) |
| 롤백 안전 | prev-2026-04-24 (fe) + prev-2026-04-28a (be) |
