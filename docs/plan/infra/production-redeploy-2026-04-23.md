# 운영 재배포 2026-04-23 — HEAD `a5bef97` 동기화

> 운영 `marketscope.robitlabs.co.kr` 이 `f6c1229` 시점 빌드로 14 커밋 뒤처져 있음.
> 본 plan 은 13 커밋 누락분을 프로덕션에 반영하되, nginx 경로 rename(`/api/kakao-sdk`→`/proxy/kakao-sdk`)
> 에 따른 호스트 설정 변경까지 포함한다.

## Context

- **현재 운영**: `f6c1229` (2026-04-16 22:45 KST 빌드)
- **Repo HEAD**: `a5bef97` (2026-04-23 작성)
- **Gap**: 13 커밋 / 156 파일 / +3,754 / -817
- **회귀 가드**: `frontend/e2e/prod-smoke/*.spec.ts` P1~P7 (작업 `42f17ff`에서 도입)

### 누락 커밋 영향도

| 커밋 | 성격 | 운영 영향 | 근거 |
|------|------|----------|------|
| `4dbd598` Plan A 매출 단위 후속 + Plan B 배포 근본해결 + 비교모드 다색 | fix/feat | **크다** | `_enrich_sales` 키 버그 3곳, `/api/kakao-sdk`→`/proxy/kakao-sdk` rename, 비교모드 다색 하이라이트 |
| `b7400d7` 격리된 E2E 회귀 인프라 (Pass 0) | infra | 작다 | E2E 전용 stack |
| `ded682d` 문서 재편 v0.3.0 | docs | 없음 | |
| `dc91327` E2E Pass 0 status | docs | 없음 | |
| `3c5f884` Pass 1 잔여 FAIL 3건 처리 | fix | **있다** | `/proxy/` rename, F03 monthlySales, F05 compareList 동기화 |
| `1986f61` cleanup_alembic/flush_cache docker exec 전환 | refactor | 없다 | 테스트 헬퍼만 |
| `ded6cb1` P0-7 timeout 180s | fix | E2E only | |
| `ff9909c` F03-H4 district_code 런타임 resolve | fix | **있다** | Mock/Real district 검색 |
| `277e427` Pass 1~3 그린 status | docs | 없음 | |
| `42b2209` L1 Langfuse trace wiring | feat | **있다** | 관찰성(옵션) |
| `bcea688` 2026-04-22 stale container 후속 회복 | fix | 인프라 | |
| `42f17ff` prod-smoke spec | test | 없음 | |
| `4983fa9` status 요약 + accuracy-gap-fix plan + validate_env 가드 | docs/fix | 작다 | validate_env 스크립트 추가 |

### 실증 (재배포 전)

```
GET https://marketscope.robitlabs.co.kr/api/kakao-sdk    → 200   (구 경로, 여전히 동작)
GET https://marketscope.robitlabs.co.kr/_proxy/kakao-sdk → 404   (신 경로, 미배포)
```

## Scope

In scope:
- **호스트 nginx** — `/etc/nginx/sites-enabled/robitlabs` 내 marketscope 블록에서 `location = /api/kakao-sdk` 예외 제거. frontend 코드가 `/proxy/kakao-sdk`로 이동했으므로 기본 `/`→frontend 라우팅으로 충분.
- **docker-compose.prod.yml** — backend `environment` 에 `LANGFUSE_*` 변수 5종 전달 (`.env` 는 이미 설정됨, 컨테이너에 미전파 상태).
- **백엔드 + 프런트 재빌드** — 소스 변경 156 파일 반영.
- **롤아웃** — `compose up -d` 로 recreate. migrate/seed 는 depends_on 자동 실행 (003 head 상태 유지, 스키마 변경 없음).
- **회귀 검증** — `frontend/e2e/prod-smoke` 7/7 통과 + `/proxy/kakao-sdk` 경로 정상 추가 확인.
- **문서** — `current-status.md` 헤더/타임라인, 본 plan 완료 체크.

Out of scope:
- Phase 2 기능 (OAuth/결제/Tier gating)
- DB 스키마 변경 (alembic 003 head 유지)
- 매출 단위 추가 회귀 (`4983fa9` 의 accuracy-gap-fix plan 은 다음 이터레이션)

## Design

### D1 — nginx 경로 정리 전략

**현재 (운영)**:
```nginx
location = /api/kakao-sdk { proxy_pass http://127.0.0.1:3200; }
location /api/            { proxy_pass http://127.0.0.1:8000; ... }
location /                { proxy_pass http://127.0.0.1:3200; }
```

**변경 후**:
```nginx
# `location = /api/kakao-sdk` 블록 제거
location /api/ { proxy_pass http://127.0.0.1:8000; ... }
location /     { proxy_pass http://127.0.0.1:3200; }   # /proxy/kakao-sdk 자연 매칭
```

**왜 제거만?** 신 경로 `/proxy/kakao-sdk` 는 `location /` 기본 분기로 frontend(3200)에 프록시되므로 별도 예외 불필요. 구 경로 `/api/kakao-sdk` 는 더 이상 frontend 에 존재하지 않으므로 `/api/` 기본 규칙을 타고 backend(8000)로 가면 404 를 반환하게 되지만, 레거시 부트스트랩이 있는 구버전 HTML 캐시가 브라우저에 남아있을 가능성을 고려해 **임시로** 양 경로 모두 호환되도록 유지할 수도 있음. 본 plan 은 **깔끔 cut-over** 선택 — 캐시 TTL(만료/Ctrl+F5)에 의존.

### D2 — Langfuse env 전달

`docker-compose.prod.yml` backend service:
```yaml
environment:
  ...
  LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY:-}
  LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY:-}
  LANGFUSE_HOST: ${LANGFUSE_HOST:-https://cloud.langfuse.com}
  LANGFUSE_SAMPLING_RATE: ${LANGFUSE_SAMPLING_RATE:-1.0}
  LANGFUSE_SESSION_SALT: ${LANGFUSE_SESSION_SALT:-}
```

graceful degrade — 키 비어도 서비스 계속 동작.

### D3 — 롤아웃 순서

1. Plan 문서 커밋 (이 문서)
2. compose.prod.yml 편집 + 커밋
3. 호스트 nginx 수정 + reload
4. `docker compose -f docker-compose.prod.yml build backend frontend`
5. `docker compose -f docker-compose.prod.yml up -d`
6. migrate/seed exit 0 + backend healthy 확인
7. Smoke E2E (7 + 추가 1건) 실행
8. status 업데이트 + 전부 푸시

롤백: `docker compose up -d` 는 이전 이미지 태그가 사라지지 않는 한 언제든 `docker tag <old-sha> catchment-area-analysis-backend:latest && up -d` 로 원복. 본 plan 은 롤백 시 nginx 도 `location = /api/kakao-sdk { ... }` 복원 필요.

## Checklist

### Phase A — Plan + 설정 (blast radius 작음)
- [x] 본 plan 파일 작성
- [x] `docker-compose.prod.yml` 에 Langfuse env 5 변수 추가
- [~] 호스트 nginx 에서 `location = /api/kakao-sdk` 삭제 — **deferred**.
  - 재검토 결과 frontend 라우트 rename 만으로 cut-over 자동 성립:
    - `/proxy/kakao-sdk` 는 nginx `location /` 기본 분기로 frontend 3200 → **200 OK**
    - `/api/kakao-sdk` 는 nginx `location = /api/kakao-sdk` 예외로 여전히 3200 으로 가지만 frontend 에 라우트가 없어 **404** (예상된 cut-over 결과)
  - nginx 예외 블록은 dead config 로 남음 → 후속 plan 으로 분리 (정리 자체가 서비스 영향 無).

### Phase B — 재빌드 + 롤아웃
- [x] backend 이미지 재빌드 (`6017d078295b`)
- [x] frontend 이미지 재빌드 (`98289821dd37`)
- [x] migrate 이미지 재빌드 (`16123a3b11e8`) — 누락으로 인한 첫 시도 exit 2 후 별도 실행
- [x] `docker compose up -d` 실행
- [x] migrate 컨테이너 exit 0 확인 (cleanup_alembic: 0 rows removed → alembic upgrade head)
- [x] seed 컨테이너 exit 0 확인
- [x] backend healthcheck PASS (~18s)

### Phase C — 회귀 검증
- [x] 로컬 backend `/health` = 200
- [x] 외부 `/proxy/kakao-sdk` = 200 (4095 bytes)
- [x] 외부 `/api/kakao-sdk` = 404 (cut-over 완료)
- [x] prod-smoke 스펙 7/7 PASS (58.1s)
- [x] 매출 단위 monthly 검증: P5 `perStoreSales` 27.3M / P6 편의점 2.09억 (월 단위 정상)

### Phase D — 문서 + 푸시
- [x] `current-status.md` 에 2026-04-23 재배포 섹션 추가
- [ ] Plan 파일 + compose 변경 + status 를 단일 커밋
- [ ] origin/main push

## Self-Review Gate

| 엣지케이스 | 대응 |
|-----------|------|
| 사용자 브라우저가 구버전 HTML 캐시 → `/api/kakao-sdk` 요청 → 404 | Ctrl+F5 / 30분 TTL. 영향 미미 (지도 첫 로드 실패 → 새로고침). |
| nginx reload 실패 | `nginx -t` 선행, 실패 시 원본 백업에서 복구 (`cp /etc/nginx/sites-enabled/robitlabs /tmp/robitlabs.bak.2026-04-23`) |
| migrate 재실패 (alembic_version 오염) | 이미 2026-04-22 에 검증됨, 스키마 변경 無 → exit 0 기대. 실패 시 별도 수동 cleanup. |
| Langfuse 키 미설정 | `langfuse_enabled()` = False → graceful degrade (경고 로그만) |
| 비교모드 다색 하이라이트 런타임 오류 | DistrictLayer 수정됨. smoke E2E 에선 비교 시나리오 미포함 (후속 확장) |
| SSE TTFT 회귀 | Claude Sonnet 4 LLM_PROVIDER 유지 (`.env` 기준). prod-smoke P5 에서 SSE 이벤트 수 + 텍스트 도달 검증 |

## Scenario — E2E Ring Mapping

| Ring | 시나리오 | 도구 | 기대 |
|------|---------|------|------|
| R0-1 | 백엔드 `/health` 200 | curl | 200 + `{"status":"ok"}` |
| R0-2 | 프론트엔드 `/` 200 | curl | 200 + Next.js HTML |
| R0-3 | 경로 cut-over | curl | `/proxy/kakao-sdk`=200, `/api/kakao-sdk`=404 |
| R1-P1 | Next.js HTML | Playwright | `MarketScope AI` 텍스트 |
| R1-P2 | `/proxy/kakao-sdk` JS 반환 | Playwright | 200 + 100+ bytes + JS |
| R1-P3 | polygons FeatureCollection | Playwright | features ≥ 1 |
| R1-P4 | districts 검색 `강남역` | Playwright | code=3120189 |
| R1-P5 | SSE summary card (월 단위) | Playwright | thinking/tool/card/text 전수 + perStoreSales 5M~100M |
| R1-P6 | recommend card (월 단위) | Playwright | per_store_sales < 1B |
| R1-P7 | Kakao 맵 DOM 주입 | Playwright | `window.kakao.maps.Map` + 맵 타일 렌더 |

**P2 의 대상 경로는 `/proxy/kakao-sdk` 로 교체** (이번 재배포 검증 포인트).

## Pass 반복

- **Pass 1 (기본)**: Phase A→B→C 1회. 기대 PASS 7/7.
- **Pass 2 (엣지)**: (예외 발생 시) migrate 재실패 / SSE 타임아웃 / Langfuse import 실패. 발생 없으면 skip.
- **Pass 3 (성능)**: 생략 (이번 재배포는 feature/fix 병합이지 성능 변경 아님).

## Agent 모델 선택

- 설계: 이 plan 작성 (Opus)
- 구현: nginx 편집 / compose 편집 / 롤아웃 실행 (Sonnet 가능하지만 현재 세션 Opus 유지)
- 검증: prod-smoke 실행 (기존 스펙 재사용, 별도 agent 불요)

---

*작성: 2026-04-23 / 실행 대상: `origin/main a5bef97`*
