# 프로덕션 재배포 — 2026-04-28 (`52ae7db → 04376a4`, 4 커밋)

> `marketscope.robitlabs.co.kr` 운영 컨테이너 4 days old (`2026-04-24T05:34Z`).
> 본 plan 으로 alembic 005 + Langfuse 11차원/6스코어 + 정확성 W1 보강 + 레거시 spec 정리를 라이브에 반영.

## Context

### 현 상태 (preflight 결과)

| 항목 | 값 |
|------|---|
| HEAD | `04376a4` (방금 git pull) |
| 운영 컨테이너 created | `2026-04-24T05:34Z` (4 days) |
| 운영 backend image | `attach_summary_observation`, `emit_score` 헬퍼 **부재** |
| 운영 DB alembic head | **004** (`learned_aliases`) — 005 미적용 |
| `.env` (prod 키) | 존재 |
| `.env.dev` (dev 키) | **존재 ⚠️** — `next.config.mjs:12` 가 우선 로드. **빌드 직전 임시 이동 필수** |
| `.env.e2e` (E2E 전용) | 존재 |
| `docker-compose.override.yml` | 부재 ✅ |
| 외부 nginx | 정상 (`https://marketscope.robitlabs.co.kr` 라이브) |
| 디스크 여유 | 643 GiB ✅ |

### 인입 변경 (4 커밋, 225 파일, +38,390 / -1,519)

| 커밋 | 핵심 |
|------|------|
| `04376a4` | qa raw SSE dump 5 디렉토리 삭제 (-4MB) — 코드 무영향 |
| `1c6f297` | Langfuse trace 11차원 + score 6종 (`langfuse_tracer.py` + `graph.py`) |
| `4a7b386` | P0 6 + Data Trust + Langfuse v3 fix + Round 2 + Refactor Pass 1+2 — `respond.py` 502→280 LOC, `numeric_sanity` evaluator, `XML sanitizer`, `entity_matching` X시장 boost, alembic **005** (estimated_sales COMMENT) |
| `4db6b96` | User-Journey sweep 16 + planner 4건 fix (compare-coref / "안전한 추천"=recommendation / "상세 분석" summary fan-out / rule 다중매치 우선순위) |

### 블로커 / 위험

- 🟢 **alembic 005**: `COMMENT ON COLUMN` only — zero-downtime, 데이터 무영향, downgrade 안전
- 🟡 **frontend lucide-react@^1.9.0** 신규 의존성 — `npm ci` 로 자동 처리
- 🟡 **`.env.dev` baked-in 위험**: `next.config.mjs` 가 dev 우선 로드 → 빌드 직전 `mv .env.dev .env.dev.bak`, 빌드 후 복구. P9 (JS bundle dev-URL scan) 으로 회귀 가드
- 🟡 **Langfuse v3 SDK drift**: 컨테이너에 v2 잔존 시 silent off — `validate_env.py` SDK drift 가드가 빌드 후 통과 확인
- 🟢 **docker-compose.prod.yml / nginx / .env.example**: 변경 없음
- 🟢 **외부 nginx**: 코드 변경 없음, 컨테이너 cut-over 만으로 충분

### 메모리 교훈 참조

- `feedback_env_convention_inverted` — `.env.dev` 가 prod 머신에 있으면 next 빌드 시 dev 값 baked-in
- `feedback_baked_url_dev_leak` — prod-smoke P9 가 JS bundle 내 `localhost` URL 검출
- `feedback_postgis_init_race` — 단, 본 배포는 fresh DB 가 아니라 무관
- `feedback_compose_override_anon_node_modules` — override.yml 부재 확인 완료
- `feedback_langfuse_sdk_drift_silent` — pyproject.toml 의 `langfuse>=3,<4` pin 이 새 이미지에 반영되는지 build log 확인

## Scope

**In Scope**
1. backend / frontend / migrate / seed 4 이미지 clean rebuild
2. `.env.dev` 임시 이동 → frontend 빌드 → 복구
3. alembic 004 → 005 마이그레이션
4. backend / frontend 컨테이너 cut-over (다운타임 < 30s)
5. 라이브 smoke (curl 9 endpoint) + prod-smoke Playwright 28 test
6. ring0~3 E2E (별도 e2e stack) — Pass 까지 hotfix 반복
7. `current-status.md` 갱신 + 커밋

**Out of Scope**
- Phase 2 Premium (OAuth2 / 결제 / Tier 게이팅)
- Langfuse Phase 3+4 (REST ETL, 월간 KPI 마크다운)
- backend pytest CI 인프라 (현재는 호스트에서 수동 실행)
- 외부 nginx config 변경 (변경 없음)

## Design

### 배포 순서

```
[ Pass 1 — 코드 회귀 ]
  1. backend pytest 신규 5종 + 기존 — host or 임시 컨테이너
  2. ruff check server/

[ Pass 2 — 빌드 + 마이그레이션 ]
  3. .env.dev → .env.dev.predeploy.bak 임시 이동
  4. docker compose -f docker-compose.prod.yml build backend frontend migrate seed
  5. .env.dev 복구
  6. docker compose -f docker-compose.prod.yml run --rm migrate (alembic upgrade head → 005)

[ Pass 3 — Cut-over + 라이브 검증 ]
  7. docker compose -f docker-compose.prod.yml up -d backend frontend
  8. backend healthcheck pass 대기 (~20s)
  9. live smoke 9 endpoint (P1~P9)
  10. prod-smoke Playwright 28 test (chromium + 3 mobile viewport)

[ Pass 4 — Ring 0~3 회귀 ]
  11. e2e stack 기동 (docker-compose.e2e.yml)
  12. ring0 + ring1 + ring2 + ring3 chromium 전수
  13. FAIL 발생 시 hotfix → 재실행 (반복)

[ Pass 5 — 기록 ]
  14. status-update 2026-04-28 섹션
  15. 커밋 (settings.local.json + status + plan)
```

### 다운타임 분석

- backend 재시작: ~10s (uvicorn graceful shutdown + healthcheck)
- frontend 재시작: ~5s (Next standalone)
- `up -d` 는 stop → start 직렬이므로 **총 다운타임 ~15s**
- 외부 nginx 는 backend 5xx 시 502 반환 — 이는 cut-over 의 자연스러운 일부

### 롤백 전략

- alembic 005 = COMMENT only → `alembic downgrade 004` 즉시 가능
- 컨테이너 롤백: 이전 image tag 보존 (현재는 latest 만 사용 — 빌드 전 `docker tag` 로 `prev` snapshot 확보)

## Checklist

### Phase 0 — Plan + 사전 회귀 (host)

- [ ] **C0-1** Plan 문서 작성 (이 문서)
- [ ] **C0-2** `cd server && python -m pytest server/tests -q --tb=short` — 신규 5종 + 기존 = 22+ test PASS
- [ ] **C0-3** `cd server && ruff check server/` All passed
- [ ] **C0-4** 이전 backend 이미지 snapshot tag — `docker tag catchment-area-analysis-backend catchment-area-analysis-backend:prev-2026-04-24`
- [ ] **C0-5** 이전 frontend 이미지 snapshot tag — 동일

### Phase 1 — Build (downtime 0)

- [ ] **C1-1** `mv .env.dev .env.dev.predeploy-2026-04-28.bak`
- [ ] **C1-2** `docker compose -f docker-compose.prod.yml build backend frontend migrate seed --pull=false` (cache 활용)
- [ ] **C1-3** `mv .env.dev.predeploy-2026-04-28.bak .env.dev` (즉시 복구)
- [ ] **C1-4** `docker images | grep catchment-area-analysis` — 새 이미지 IMAGE ID 가 4 days 전 ID 와 다른지 확인
- [ ] **C1-5** validate_env Langfuse SDK drift 가드 pass — `docker run --rm catchment-area-analysis-backend python /app/scripts/validate_env.py` (env 마운트 없이도 import 가드는 동작)

### Phase 2 — Migrate (zero-downtime)

- [ ] **C2-1** `docker compose -f docker-compose.prod.yml run --rm migrate` — `cleanup_alembic.py && alembic upgrade head` exit 0
- [ ] **C2-2** DB 검증: `docker exec catchment-area-analysis-db-1 psql -U $POSTGRES_USER -d marketscope -c "SELECT version_num FROM alembic_version"` → `005`
- [ ] **C2-3** COMMENT 검증: `pg_catalog.col_description` 으로 `estimated_sales.monthly_sales` COMMENT 존재 확인

### Phase 3 — Cut-over

- [ ] **C3-1** `docker compose -f docker-compose.prod.yml up -d backend frontend` — 컨테이너 교체
- [ ] **C3-2** Loop until `curl -sf http://localhost:8000/health` 200 — backend healthy 대기
- [ ] **C3-3** `curl -sf http://localhost:3200/` 200 — frontend healthy 대기
- [ ] **C3-4** 신규 헬퍼 반영 검증: `docker exec ...backend-1 python -c "from server.services import langfuse_tracer as t; assert hasattr(t, 'attach_summary_observation') and hasattr(t, 'emit_score'); print('OK')"`

### Phase 4 — Live Smoke (curl)

- [ ] **C4-1 P1** `curl https://marketscope.robitlabs.co.kr/` → 200 + `data-theme="light"` + `MarketScope` 마커
- [ ] **C4-2 P2** `curl /proxy/kakao-sdk` → 200 + bytes > 1000
- [ ] **C4-3 P3** `curl /api/map-data/polygons?bounds=...` → GeoJSON FeatureCollection
- [ ] **C4-4 P4** `curl /api/districts?search=강남역` → 3120189
- [ ] **C4-5 P5** `curl -N -X POST /api/chat` (강남역 요약) → SSE thinking/tool/card/text/done.trace_id, perStoreSales 5M~100M/월 범위
- [ ] **C4-6 P6** `curl -N -X POST /api/chat` (보문역 편의점 추천) → SSE recommend, per_store_sales < 1B/월
- [ ] **C4-7 P7** `curl /app` → 200 + app 마커
- [ ] **C4-8 P8** `curl /api/districts/3120189/preview` → top_categories 풍부한 F13 응답
- [ ] **C4-9 P9** `curl -X POST /api/feedback/score` 빈 payload → 422 / 정상 payload → 204
- [ ] **C4-10 P10 (신규)** `curl -N -X POST /api/chat` (clarification: "이 지역 요약") → tool 0건 + suggestion + done
- [ ] **C4-11 P11 (신규)** `curl -N -X POST /api/chat` 응답 SSE done.trace_id 발행 확인 (Langfuse L1 정상)

### Phase 5 — prod-smoke Playwright (28 test)

- [ ] **C5-1** `cd frontend && npx playwright test prod-smoke --project=chromium --project=mobile-iphone --project=mobile-galaxy --project=tablet-ipad --reporter=line`
- [ ] **C5-2** P8 baked-URL real-browser chat round-trip PASS — 새 frontend bundle 이 prod URL 만 호출
- [ ] **C5-3** P9 JS bundle dev-URL scan PASS — bundle chunk 에서 `localhost` 0건

### Phase 6 — Ring 0~3 회귀 (e2e stack)

- [ ] **C6-1** e2e stack 기동: `docker compose -f docker-compose.e2e.yml up -d` + USE_MOCK preflight
- [ ] **C6-2** `npx playwright test ring0-preflight --reporter=line` — 5/5 PASS (00-stack-up + stats-aggregate 4 신규)
- [ ] **C6-3** `npx playwright test ring1-features --reporter=line` — f01~f13 + m01 PASS (mobile-sheet-open 신규 포함)
- [ ] **C6-4** `npx playwright test ring2-journeys --reporter=line` — j01~j05 PASS
- [ ] **C6-5** `npx playwright test ring3-negative --reporter=line` — neg-* + p0-regression + reg-2026-04-17 PASS
- [ ] **C6-6** FAIL 발생 시 → 진단 → spec or product hotfix → 재실행 (Pass 까지 반복, 최대 3 라운드)

### Phase 7 — 기록

- [ ] **C7-1** `docs/qa/runs/prod-deploy-2026-04-28.md` 신규 (run log)
- [ ] **C7-2** `docs/status/current-status.md` 2026-04-28 섹션 추가 (status-update skill)
- [ ] **C7-3** 커밋: `feat(deploy): 2026-04-28 prod 재배포 — alembic 005 + Langfuse 11차원/6스코어 + W1 보강`

## 재검토 (Self-Review Gate)

### 엣지 케이스

- **`.env.dev` 임시 이동 사이에 외부 트래픽 영향 0** — 빌드는 컨테이너 외부에서 이뤄지고, 운영 컨테이너는 그대로 유지 (cut-over 는 빌드 후)
- **alembic 005 가 idempotent 하지 않은 경우**: `COMMENT ON COLUMN ... IS '...'` 는 PostgreSQL 에서 idempotent — 같은 값으로 재실행해도 OK
- **migrate 컨테이너가 `cleanup_alembic.py` 없는 이미지인 경우**: `4a7b386` 이전 prod 이미지에 `cleanup_alembic.py` 존재 (이전 production-redeploy-2026-04-23 plan 에서 추가됨). 새 이미지 빌드로 자동 갱신.
- **frontend lucide-react 의 peer dependency 충돌**: `package-lock.json` 에 이미 lock 됨. `npm ci` 로 안전.
- **Langfuse OTEL TLS verify**: prod 환경에서는 `.env` 에 `LANGFUSE_OTEL_INSECURE` 미설정 → 정상 SSL 검증. dev 머신 MITM 우회 코드는 프로덕션 영향 0.
- **다운타임 중 사용자 SSE 세션**: backend 재시작 시 진행 중 SSE 는 끊김. 사용자는 retry (chatStore 의 2회 재시도) 로 복구. 단발성 끊김 허용.
- **이전 컨테이너 image tag 미보존 시 롤백 어려움**: C0-4/C0-5 로 `prev-2026-04-24` 태그 명시.

### 타 Plan 충돌

- ✅ `prod-deploy-precheck-2026-04-24.md` 의 GO 조건 4개 모두 충족
- ✅ `production-redeploy-2026-04-23.md` 와 동일한 빌드 순서 (backend → frontend → migrate → seed)
- ✅ `langfuse-aggregate-stats-2026-04-28.md` 의 Phase 1+2 가 본 배포에 포함 (Phase 3+4 는 별도)
- ✅ `prod-baked-url-smoke-2026-04-24.md` 의 P8/P9 가드를 본 배포 검증에 활용

## Scenario (E2E Ring Mapping)

| Ring | ID | 케이스 |
|---|---|---|
| 0 | `R0-DEPLOY-STACK-UP` | docker compose ps 전수 healthy |
| 0 | `R0-LF-AGG-01..04` | Langfuse 11차원 + 6 score (stats-aggregate.spec.ts) |
| 1 | `R1-F01..F11` | 기능 회귀 (지도/Agent/요약/비교/추천/리스크/시뮬/PDF/랜딩/피드백/프리뷰) |
| 1 | `R1-M01-MOBILE-SHEET` | BottomSheet iOS 즉시 닫힘 fix 회귀 |
| 2 | `R2-J01..J05` | 5 사용자 여정 |
| 3 | `R3-NEG-NO-DISTRICT` | clarification 분기 (planner fix 검증) |
| 3 | `R3-P0-REG` | 매출 단위 + StatusBar testid |
| 3 | `R3-REG-2026-04-17` | 매출 단위 회귀 (월 환산) |
| 3 | `R3-PROD-SMOKE-P8` | baked-URL real-browser chat |
| 3 | `R3-PROD-SMOKE-P9` | JS bundle dev-URL scan |

## Pass 반복

### Pass 1 — 사전 회귀 + 빌드 + 마이그레이션
- C0-1 ~ C2-3 (Plan + pytest + ruff + image tag + build + env restore + migrate)
- 실패 시: ruff/pytest 수정 또는 alembic downgrade

### Pass 2 — Cut-over + Live Smoke
- C3-1 ~ C4-11 (cut-over + healthcheck + curl 11종)
- 실패 시: 컨테이너 로그 확인, `prev-2026-04-24` 태그로 롤백

### Pass 3 — Playwright prod-smoke
- C5-1 ~ C5-3
- 실패 시: spec or env 문제 → hotfix → 재실행

### Pass 4 — Ring 0~3
- C6-1 ~ C6-6
- 실패 시: spec or product 분석 → hotfix → 재실행 (최대 3 라운드)

### Pass 5 — 기록
- C7-1 ~ C7-3

## Agent 모델 선택

- 설계 (본 plan): opus
- 구현 (cut-over + 검증): sonnet (다수의 docker / curl / playwright 호출, 명확한 스펙)
- 검증 (Pass 판정): haiku (run log 비교)

## Validation

### 자동 검증

- ✅ backend pytest 22+ PASS
- ✅ ruff All passed
- ✅ docker images 새 ID
- ✅ alembic head=005
- ✅ live curl 11/11 200 + 정합 페이로드
- ✅ prod-smoke 28/28 PASS (chromium + 3 mobile)
- ✅ ring0~3 chromium 전수 PASS

### 수동 검증

- 외부 nginx 로 https://marketscope.robitlabs.co.kr 페치 — 랜딩 / 분석 / 챗 SSE 정상
- Langfuse Cloud UI 에서 신규 trace 확인 (intent/district_type/quality 차원, score 7종)

## Metadata

- 작성일: 2026-04-28
- 작성자: Claude (opus)
- 카테고리: infra
- 선행 Plan: `prod-deploy-precheck-2026-04-24.md` · `prod-deploy-v0.4.0-2026-04-23.md` · `langfuse-aggregate-stats-2026-04-28.md`
- 후속 Plan 후보: Langfuse Phase 3 (REST ETL) · Phase 4 (월간 KPI 마크다운)
- 영향 범위: 백엔드 + 프론트 + DB COMMENT. SSE 페이로드 무변경. nginx/외부 LB 무변경.
