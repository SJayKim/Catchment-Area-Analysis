# 운영 재배포 v0.4.0 (2026-04-23 저녁) — `c6cc60e` 동기화

> 같은 날 오전 `a5bef97` → `60b6de3` 재배포 완료 이후, Accuracy Gap W1~W3 + UI A~D(F11 landing/F12 feedback/F13 preview/mobile) + alembic 004 + Langfuse env 확장이 추가로 병합됨.
> 본 plan 은 오전 재배포 시점 HEAD 대비 6 커밋 / 144 파일 / +13,038 / -577 를 프로덕션에 반영한다.

## Context

- **현재 운영**: `60b6de3` (2026-04-23 00:54 KST 빌드, 9h ago)
- **Repo HEAD**: `c6cc60e` v0.4.0 (2026-04-23 저녁)
- **Gap 6 커밋**:
  - `9b966f4` test(server): pytest 부트스트랩 — 영향 無 (CI only)
  - `142e658` ci(docker): frontend build dummy key — 영향 無 (CI only)
  - `4f4bf2d` audit(qa): data integrity audit — 영향 無 (문서)
  - `1d894a6` feat: L1 검증 + Accuracy Gap W1~W3 + UI A~D + Env 분리 — **영향 大**
  - `c6cc60e` chore(release): v0.4.0 — 버전 태깅

### `1d894a6` 운영 영향 분해

| 영역 | 내용 | 운영 영향 |
|------|------|-----------|
| **DB 스키마** | alembic `004_learned_aliases.py` (CREATE TABLE IF NOT EXISTS) | **migrate 필수**. Additive 만 → 기존 데이터 무영향. |
| **Frontend 라우팅** | `/` = 랜딩(F11), `/app` = 기존 챗+맵 | **사용자 가시 변경**. 기존 `/` 북마크는 랜딩 → CTA 클릭으로 `/app` 진입. |
| **신규 API** | `GET /api/districts/{code}/preview` (F13), `POST /api/feedback` (F12) | 신규 엔드포인트, 기존 경로 영향 無. |
| **Agent 로직** | Planner Entity Linking (GAP-A), Abstention (GAP-D), Rewriter (GAP-C/E), learned_aliases (GAP-B) | 응답 품질 향상, 기존 응답 스키마 변경 無. |
| **Env 확장** | `LANGFUSE_TRACING_ENVIRONMENT`(default "production"), `LANGFUSE_OTEL_INSECURE`(default "false") | `.env` 에 **이미 존재 확인**(로컬 로드 완료). |
| **docker-compose.yml** (dev) | `env_file: .env.dev` 로 일괄 이관 | **프로덕션 무관** — prod 는 `docker-compose.prod.yml` 사용. |
| **docker-compose.prod.yml** | `LANGFUSE_TRACING_ENVIRONMENT` / `LANGFUSE_OTEL_INSECURE` 2변수 추가 (이미 커밋됨) | 신규 env 주입만. 나머지 `LANGFUSE_*` 5개는 오전 배포에서 적용됨. |
| **frontend/next.config.mjs** | root env 로더 `.env.dev > .env` 폴백 | **프로덕션에선 `.env` 사용** (컨테이너 `environment:` 우선). |

### `.env` 사전 검증 (완료)
```
LANGFUSE_PUBLIC_KEY=<present>
LANGFUSE_SECRET_KEY=<present>
LANGFUSE_TRACING_ENVIRONMENT=<present>  # production 권장
LANGFUSE_OTEL_INSECURE=<present>        # false 권장
```

### prod-smoke 회귀 대응

`frontend/e2e/prod-smoke/prod-smoke.spec.ts` P7 은 `BASE` (`/`) 에서 Kakao Map DOM 주입을 기대. 본 배포로 `/` = 랜딩(맵 無) 이므로 **`BASE + '/app'` 으로 수정** 필요. P1 (HTML/Next.js 마커) 은 랜딩도 Next.js 렌더라 통과.

### Memory 참조

> (2026-07-04 정정: 아래 auto-memory 파일 링크는 리포 루트 `memory/` 부재로 해석 불가 — 링크 제거, 교훈 요지만 보존.)

- [[feedback_stale_container_vs_source]] — 배포 후 FAIL 시 컨테이너 빌드 시각부터 확인.
- [[feedback_probe_endpoint_shape_first]] — 신규 `/api/districts/{code}/preview`, `/api/feedback` 스키마는 실호출로 확인.
- (앞 plan `production-redeploy-2026-04-23.md`) — compose 가 쓰는 이미지 4종(backend/frontend/migrate/seed) 모두 rebuild 필요.

## Scope

**In scope**:
- prod-smoke P7 spec 을 `/app` 으로 정정 (회귀 방지)
- `docker compose -f docker-compose.prod.yml build backend frontend migrate seed`
- `docker compose -f docker-compose.prod.yml up -d` → migrate 003→004 + seed 재실행 + backend/frontend 재기동
- prod-smoke 7/7 + 신규 엔드포인트 2종 (`/api/districts/3120189/preview`, `/api/feedback` POST) 재확인
- `docs/status/current-status.md` v0.4.0 배포 섹션 추가

**Out of scope**:
- Phase 2 기능 (OAuth/결제/Tier gating)
- 외부 호스트 nginx 수정 (`/`→3200, `/api/`→8000 는 이미 커버; 경로 추가 없음)
- Accuracy Gap Fix W4 (Card-level Export) — 별도 plan

## Design

### D1 — 롤아웃 순서

1. **Phase A**: plan 문서 작성 + prod-smoke P7 패치 (로컬 커밋 전)
2. **Phase B**: 이미지 4종 rebuild → `up -d` → migrate/seed exit 0 → backend healthy (~20s)
3. **Phase C**: prod-smoke 7/7 + 신규 API probe → FAIL 시 롤백 결정
4. **Phase D**: status 갱신 → 단일 커밋 + push

### D2 — alembic 004 안전성

`CREATE TABLE IF NOT EXISTS learned_aliases` + `idx_learned_aliases_code`. FK 는 `category_metadata(category_code)` ON DELETE CASCADE. 기존 테이블/인덱스/데이터 건드리지 않음. 실패 가능 시나리오:
- `category_metadata` 부재 → FK 생성 실패. 오전 003 head 확인됨 → 존재 보장.
- 동일 이름 테이블이 이미 존재 → `IF NOT EXISTS` 로 skip.

### D3 — 롤백 플랜

| 실패 지점 | 조치 |
|----------|-----|
| migrate exit != 0 | `docker compose stop backend` + 오전 이미지 태그(`catchment-area-analysis-backend` SHA `6017d07`) 로 복귀. DB 는 트랜잭션 롤백으로 원상. |
| backend unhealthy | 오전 frontend/backend 이미지 태그로 `docker tag ...:latest` 후 `up -d` |
| prod-smoke P5/P6 매출 단위 회귀 | 복귀 + 원인 분석 (오전 배포에선 통과 → `monthly_sales` enrich 경로 회귀 가능성) |
| 랜딩에서 `/app` 진입 실패 | frontend 이미지만 오전 태그로 복귀 (`/app` 라우트 문제 가능성) |

### D4 — 호스트 nginx

`/` 과 `/app` 은 둘 다 frontend(3200)로 가는 기본 분기에 매칭. `/api/*` 은 backend(8000). 신규 `/api/districts/{code}/preview`, `/api/feedback` 모두 기본 규칙 흡수. **수정 불필요**.

## Checklist

### Phase A — 코드 정리 (blast radius 극소)
- [ ] 본 plan 파일 작성
- [ ] `frontend/e2e/prod-smoke/prod-smoke.spec.ts` P7: `page.goto(BASE)` → `page.goto(BASE + '/app')`

### Phase B — 빌드 + 롤아웃
- [ ] `docker compose -f docker-compose.prod.yml build backend frontend migrate seed`
- [ ] `docker compose -f docker-compose.prod.yml up -d`
- [ ] migrate 컨테이너 exit 0 (cleanup 0 rows + alembic 003→004)
- [ ] seed 컨테이너 exit 0
- [ ] backend healthcheck PASS (~20s)
- [ ] frontend 기동 확인 (log: `Ready in ...`)

### Phase C — 회귀 검증
- [ ] 로컬 `curl /health` = 200
- [ ] 외부 `/` = 200 + 랜딩 HTML (`data-testid="landing-page"` 또는 "MarketScope AI")
- [ ] 외부 `/app` = 200 + Toolbar/Map HTML
- [ ] 외부 `/proxy/kakao-sdk` = 200 + JS
- [ ] 외부 `/api/districts/3120189/preview` = 200 + 스키마 (JSON)
- [ ] 외부 `/api/feedback` POST = 2xx (빈 payload 거절 허용, 스키마 검증 통과면 OK)
- [ ] `npx playwright test e2e/prod-smoke/` = 7/7 PASS (P7 수정 반영)

### Phase D — 문서 + 푸시
- [ ] `current-status.md` v0.4.0 배포 섹션 + 헤더 최종 갱신일
- [ ] plan 파일 + prod-smoke 수정 + status → 단일 커밋
- [ ] `git push origin main`

## Self-Review Gate

| 엣지케이스 | 대응 |
|-----------|------|
| 구버전 HTML 캐시 → 기존 `/` = 챗 UI 로 기억, 배포 후 `/` = 랜딩에 당황 | 랜딩 Hero CTA 가 `/app` 로 이동. 사용자 불편 1클릭으로 해소. |
| 랜딩 `FeedbackFab` 가 `/api/feedback` 호출 → DB insert 전 FK 오류 | feedback 테이블은 본 배포 이전 migration(003)로 존재 여부 확인 필요. 만약 없다면 migration plan 필요. |
| alembic 004 실행 중 backend 기동 → `learned_aliases` 미존재 SELECT | compose `depends_on: migrate: service_completed_successfully` 로 gating. 오전 배포에서 검증됨. |
| Langfuse 키 없이 prod 재기동 | `langfuse_enabled()` False → degrade. `.env` 에 키 확인됨. |
| Planner Entity Linking 신규 경로 → 응답 지연 | pg_trgm 의존하지만 mock fallback 있음. prod-smoke P5/P6 TTFT 가 회귀 가드. |
| Kakao Map SDK 캐시 만료 이슈 | P7 이 실제 `window.kakao.maps.Map` DOM 주입을 검증 → 회귀 감지 가능. |

## Scenario — E2E Ring Mapping

| Ring | 시나리오 | 도구 | 기대 |
|------|---------|------|------|
| R0-1 | backend `/health` | curl | 200 `{"status":"ok"}` |
| R0-2 | 외부 `/` 랜딩 | curl | 200 + `MarketScope AI` + 랜딩 마커 |
| R0-3 | 외부 `/app` 챗맵 | curl | 200 + Toolbar DOM |
| R1-P1 | frontend root HTML | Playwright | `MarketScope AI` |
| R1-P2 | `/proxy/kakao-sdk` | Playwright | 200 + 100+ bytes JS |
| R1-P3 | polygons FeatureCollection | Playwright | features ≥ 1 |
| R1-P4 | districts 검색 `강남역` | Playwright | code=3120189 |
| R1-P5 | SSE summary (월 단위) | Playwright | perStoreSales 5M~100M |
| R1-P6 | recommend per_store_sales < 1B | Playwright | 전 추천 < 1B |
| R1-P7 | `/app` Kakao map 주입 | Playwright | `window.kakao.maps.Map` + tile DOM |
| R1-N1 | `/api/districts/3120189/preview` | curl | 200 + `{district_name, ...}` |
| R1-N2 | `/api/feedback` POST | curl | 2xx (스키마 OK) or 4xx (validation) — 500 금지 |

## Pass 반복

- **Pass 1 (기본)**: Phase A→D 1회. 기대 PASS 7/7 prod-smoke + 2/2 신규 endpoint.
- **Pass 2 (엣지)**: 실패 시 migrate 재실행 / 이미지 stale 재빌드 / nginx reload. 발생 없으면 skip.
- **Pass 3 (성능)**: 이번 배포는 기능 병합. TTFT/latency 회귀는 prod-smoke P5 내부 이벤트 수/카드 데이터로 1차 확인. 정식 load-test 는 별도.

## Agent 모델 선택

- 설계: 본 plan (Opus)
- 구현: compose build/up, prod-smoke 수정 (Sonnet 충분, 현재 Opus 유지)
- 검증: Playwright prod-smoke 재사용 (별도 agent 불요)

---

*작성: 2026-04-23 / 실행 대상: `origin/main c6cc60e` (v0.4.0)*
