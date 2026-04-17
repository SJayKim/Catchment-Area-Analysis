# Plan A + Plan B 로컬 통합 검증 Plan

> 작성일: 2026-04-17
> 목적: 2026-04-17 미커밋 변경(매출 단위 수정 Plan A + 배포 근본해결 Plan B + 비교모드 다색 하이라이트) + 방금 추가한 DistrictLayer 수정을 **로컬 환경**에서 기동-검증-커밋까지 한 번에 수행
> 실운용 도메인 `marketscope.robitlabs.co.kr` 및 `docker-compose.prod.yml` 은 이 plan 범위 밖. **로컬 `docker-compose.yml` + 로컬 `.env` 만 사용**

## Context

### 미커밋 변경 (git status 기준)

| 범주 | 파일 |
|------|------|
| Plan A (sales unit) | `server/server/agent/nodes/respond.py`, `agent/tools/estimated_sales.py`, `agent/tools/district_summary.py`, `scripts/flush_cache.py`(?), `scripts/verify_sales_units.py`(?), `scripts/generate_seed.py` |
| Plan B (deploy root-cause) | `docker-compose.yml`, `docker-compose.prod.yml`, `frontend/Dockerfile`, `frontend/next.config.mjs`, `.env.example`, `.gitignore`, `frontend/src/app/_proxy/`(?), `frontend/src/app/api/kakao-sdk/route.ts`(D), `server/scripts/cleanup_alembic.py`(?), `scripts/validate_env.py`(?), `nginx/external-reverse-proxy.conf.example`(?), `docs/setup/production-deployment.md`(?) |
| 비교모드 (이번 세션) | `frontend/src/components/map/DistrictLayer.tsx`, `frontend/src/components/map/MapContainer.tsx`(무관 경고), `frontend/tsconfig.tsbuildinfo`, `docs/status/current-status.md`, `docs/plan/phase/phase-2-implementation.md`, `docs/spec/checklist.md` |
| 하네스/설정 | `.claude/settings.local.json`, `.claude/agents/`(?), `.claude/hooks/`(?), `.claude/settings.json`(?), `.claude/skills/`(?), `CLAUDE.md` |

### 선행 memory 참조

- `memory/feedback_check_env_before_test.md` — E2E 전 USE_MOCK 환경 확인
- `memory/feedback_python_utf8_windows.md` — Windows Python 스크립트는 `encoding='utf-8'` 강제
- `memory/feedback_jq_unavailable.md` — JSON 파싱은 python 사용
- `memory/feedback_read_large_doc_chunking.md` — 큰 문서는 limit 청크

---

## Scope

### In
- `.env` 로컬 추가 (`NEXT_PUBLIC_API_URL=http://localhost:3000`)
- 4개 신규 스크립트 syntax check + 의도된 동작 확인
- `docker compose up -d db redis` 로 DB/Redis 기동 (기존 `pgdata` 볼륨 유지)
- Alembic head 상태 확인 + (필요 시) `cleanup_alembic.py` 동작 확인
- `verify_sales_units.py` 실행으로 **보문역 슈퍼마켓 월매출** 회귀 확인 (기대: 1~2억/월)
- Backend API smoke (`/api/districts?search=보문`, `/api/map-data/polygons` 최소 검증)
- 변경 묶음 커밋 (user confirmation 후)

### Out
- prod 도메인 / `docker-compose.prod.yml` 작업
- `docker compose down -v` 같은 pgdata 파괴 작업 (기본 스킵. 필요 시 별도 옵션 섹션)
- Frontend 브라우저 E2E (Playwright ring) — 별도 `/e2e-run` 세션
- 신규 기능 추가

---

## Design

### 옵션 A (기본, safe) — 현재 볼륨 유지 검증
현재 `pgdata`에 이미 1,650 districts + 9,888 floating_pop 등 적재됨. 이를 유지하고 API/스크립트 동작만 검증.

```
1. .env NEXT_PUBLIC_API_URL 추가
2. validate_env.py 실행 → 가드 동작 확인
3. python -m py_compile 4종 스크립트
4. docker compose up -d db redis
5. alembic current 확인
6. python scripts/flush_cache.py (기존 stale 값 제거)
7. 로컬 uvicorn 또는 docker backend 기동
8. verify_sales_units.py 실행 → 보문역 결과 assertion
9. curl /api/districts?search=보문 smoke
10. (user ack) git commit
```

### 옵션 B (선택, full rebuild) — pgdata 재생성으로 migrate cleanup 검증
Plan B P0-1 `cleanup_alembic.py` 가 기존 볼륨 시나리오에서 동작함을 재현하려면 `alembic_version` 다중 row 상태를 인위 주입.

```
1. alembic_version 에 `001` row 강제 INSERT (mock stale state)
2. docker compose restart migrate — 기존이면 fail
3. cleanup_alembic.py 실행 → stale 제거
4. alembic upgrade head 통과 확인
```

옵션 A 완주 후 user 승인 시만 옵션 B 수행. 기본은 A 만으로 Pass 판정.

---

## Checklist

### Phase 0 — 준비
- [ ] `NEXT_PUBLIC_API_URL=http://localhost:3000` 를 `.env` 에 추가 (이미 있으면 값만 확인)
- [ ] `python scripts/validate_env.py` 실행 → 0 exit
- [ ] `python -m py_compile scripts/flush_cache.py scripts/verify_sales_units.py scripts/validate_env.py server/scripts/cleanup_alembic.py` → 0 exit

### Phase 1 — DB/Redis 기동
- [ ] `docker compose up -d db redis` 성공
- [ ] `docker compose ps` 로 두 서비스 healthy
- [ ] Postgres 접속 smoke (`docker compose exec db psql -U marketscope -c "SELECT count(*) FROM districts"`) — 1650 가정

### Phase 2 — Cache flush
- [ ] `python scripts/flush_cache.py` 실행 → 5 prefix 삭제 카운트 출력
- [ ] redis-cli 로 `KEYS sales:*` 0 건 확인

### Phase 3 — 매출 단위 회귀 검증
- [ ] `python scripts/verify_sales_units.py` 실행
- [ ] 보문역 슈퍼마켓 점포당 월매출이 **3억/월 미만** (assertion 통과)
- [ ] `computed.qoq_growth_pct` 또는 `insights.qoqGrowth` 값이 0이 아님 (Phase A 키 버그 수정 효과 확인)

### Phase 4 — Backend API smoke
- [ ] backend 기동 (`uvicorn server.main:app --reload --port 8000` 또는 docker)
- [ ] `curl 'http://localhost:8000/api/districts?search=보문'` → `보문` 포함 1건 이상 반환
- [ ] `/health` 200 OK

### Phase 5 — Frontend build 회귀
- [ ] `cd frontend && npx tsc --noEmit` → 0 exit (이미 통과)
- [ ] `npm run build` → 성공 (이미 통과)

### Phase 6 — 커밋 (user confirmation 필수)
- [ ] 변경 묶음 논리 단위로 분할:
  1. Plan A (매출 단위 수정) — `agent/tools/*.py`, `agent/nodes/respond.py`, `scripts/flush_cache.py`, `scripts/verify_sales_units.py`
  2. Plan B (deploy root-cause) — `docker-compose*.yml`, `frontend/Dockerfile`, `frontend/next.config.mjs`, `frontend/src/app/_proxy/`, `api/kakao-sdk/` 삭제, `server/scripts/cleanup_alembic.py`, `scripts/generate_seed.py`, `scripts/validate_env.py`, `nginx/`, `docs/setup/production-deployment.md`, `.env.example`, `.gitignore`
  3. 비교모드 다색 하이라이트 — `frontend/src/components/map/DistrictLayer.tsx`, `docs/status/current-status.md`, `docs/plan/phase/phase-2-implementation.md`, `docs/spec/checklist.md`, `docs/plan/fix/integration-verification-local.md` (이 plan 자체)
- [ ] `.claude/*` 하네스 변경은 별도 커밋 또는 stash (사용자 지시)

## 재검토 (Self-Review Gate)

- 엣지 케이스: `flush_cache.py` 가 Redis 없을 때 graceful 처리하는가 → 스크립트 내부 fallback 확인 필요
- 엣지 케이스: `verify_sales_units.py` 가 USE_MOCK=true 일 때 어떻게 동작? → `.env` 현재 USE_MOCK=false 이므로 비관련 but 스크립트는 가드 있어야
- memory 교훈: UTF-8 파일 I/O, Windows print 인코딩 — 스크립트 모두 `encoding='utf-8'` 사용하는지 code review 필요
- 타 plan 충돌: `sales-unit-conversion-fix.md` 가 이 검증의 원본 plan. 이 plan 은 그 뒤에 붙는 "로컬 수행 절차". 충돌 없음

## Scenario (E2E Ring Mapping)

| Scenario ID | Ring | 사전조건 | 실행 | 기대 결과 |
|-------------|------|----------|------|-----------|
| V-ENV-01 | 0 | `.env` 존재 | `validate_env.py` | exit 0, 누락 키 없음 |
| V-SCRIPT-02 | 0 | - | 4종 `py_compile` | exit 0 |
| V-DB-03 | 0 | docker 설치됨 | `compose up -d db redis` | 2 컨테이너 healthy |
| V-SALES-04 | 1 | DB seed 적재됨 | `verify_sales_units.py` | 보문역 슈퍼마켓 < 3억/월, QoQ 0 아님 |
| V-API-05 | 1 | backend up | `curl /api/districts?search=보문` | 1+ row |
| V-BUILD-06 | 1 | - | `tsc --noEmit + npm run build` | 0 errors |
| V-OPT-B-07 | 2 | user 승인 | alembic stale row + cleanup | migrate 성공 |

## Pass 반복

- Pass 1 (기본): Phase 0~5 전부 통과 → Pass. 실패 항목 1개 → 해당 항목만 Edit/fix → 재실행
- Pass 2 (엣지): Redis down 시 flush_cache graceful; USE_MOCK 토글 시 verify 스크립트 friendly skip
- Pass 3 (성능): verify_sales_units 전체 실행 < 30s

실패 시 해당 파일만 수정 후 해당 Phase 재실행. 전체 롤백 불필요 (코드 변경 없으면 git reset 없이 retry).

## Agent 모델 선택

- 설계(이 plan 작성): opus
- 실행(스크립트/bash): sonnet/haiku — 이 세션 자체가 수행
- 검증 리뷰(선택): `code-reviewer` subagent — 스크립트 4종 검토 (ruff line 100, UTF-8)

---

## Validation 합격 기준

| 조건 | 기준 |
|------|------|
| Phase 0~5 전부 PASS | ✅ 로컬 통합 검증 완료 |
| 보문역 슈퍼마켓 월매출 | **< 3억/월** (plan A 효과 재현) |
| QoQ 성장률 | **≠ 0** (키 버그 수정 확인) |
| tsc + build | 0 errors |
| Backend API smoke | 200 OK, 결과 1건 이상 |

전부 만족 시 커밋 단계로 진행 가능.

---

## Metadata

- 작성일: 2026-04-17
- 작성자: Claude Opus 4.7 (auto session)
- 원본 Plan: `docs/plan/fix/sales-unit-conversion-fix.md`, `docs/plan/fix/deployment-root-cause-fixes.md`, `docs/plan/phase/phase-2-implementation.md`
- 실행 환경: 로컬 only (prod 도메인 `marketscope.robitlabs.co.kr` 작업 금지)
