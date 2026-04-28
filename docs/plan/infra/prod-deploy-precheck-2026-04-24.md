# 프로덕션 배포 전 체크 — 2026-04-24

> v0.4.0 이후 Pass 2 Planner 변경 + W1~W3 Accuracy Gap 반영 이미지 재배포 전 검증.
> 참조: `docs/status/current-status.md` (2026-04-24 Pass 2 / Accuracy Eval Round 2)

## Context

- 이번 세션에서 `planner.py` `ambiguous → clarification` short-circuit + rubric 보정 반영
- `docker-compose.override.yml` 이 dev 전용 (`./server:/app` volume-mount + `--reload`) 인데 `.gitignore` 미등록 (방금 확인)
- 로컬 backend 이미지가 corporate MITM SSL 때문에 `docker cp` 수작업 우회로 빌드됨 — 프로덕션 CI 는 재빌드 가능한지 미검증
- 기존 Playwright 시나리오 중 clarification 경로 (`j03`, `neg-no-district`) 가 Planner 변경 영향권

## Scope

- In: (1) override.yml gitignore, (2) backend 이미지 clean rebuild 가능성 smoke, (3) ring0/1/3 local regression, (4) ruff lint, (5) Langfuse trace_id smoke
- Out: prod-smoke 원격 실행, Phase 2 Premium, Round 3 eval

## Design

### 실행 순서

1. **override.yml 배포 제외** — `.gitignore` 에 `docker-compose.override.yml` 추가 (커밋은 사용자 승인 후)
2. **ruff 린트** — `ruff check server/server/agent/nodes/planner.py server/server/agent/utils/formatting.py`
3. **이미지 재빌드 가능성 smoke** — `docker compose -f docker-compose.yml config` 로 override 제외 구성 dump, `docker compose build backend --dry-run` (Buildx) 로 BuildKit 도달 여부만 확인. MITM 차단 시 CI 환경 위임 메모.
4. **Playwright ring0+1+3 회귀** — `cd frontend && npx playwright test ring0 ring1 ring3 --reporter=line`. USE_MOCK preflight 는 `scripts/e2e/preflight.sh` 로컬 정책 따름.
5. **Langfuse trace_id smoke** — 재빌드 된 backend 컨테이너 한 건 curl → SSE `done.trace_id` 존재 확인.

### 리스크

- MITM 환경에서 `docker compose build` 실패 시 → CI 에게 위임하고 로컬은 skip (경고 기록)
- ring1 의 `f12-feedback` 은 unlimited attempts 로 skip-guard 있음 — precheck 로 조기 skip 허용
- Langfuse otel HTTP SSL 우회는 dev override 전용이라 프로덕션 이미지는 재빌드 후 first-call 에서 검증

## Checklist

- [ ] `.gitignore` 에 `docker-compose.override.yml` 추가 + 재확인 `git check-ignore` exit=0
- [ ] `ruff check` planner.py + formatting.py + utils/* 전체 pass
- [ ] `docker compose config` (override 없이) 파싱 OK
- [ ] Playwright ring0 (1 spec) PASS
- [ ] Playwright ring1 핵심 (f01/f02/f03/f05/f11) PASS
- [ ] Playwright ring3 (neg-no-district, p0-regression) PASS
- [ ] 배포 go/no-go 판정 기록

## 재검토 (Self-Review Gate)

- Memory 교훈 — `feedback_compose_override_anon_node_modules.md` 재확인 (override 를 prod 에 풀어두면 volume-mount 로 fresh-empty node_modules)
- 타 Plan 충돌 — `prod-deploy-v0.4.0-2026-04-23.md` 의 "full rebuild order" 재사용 (backend → frontend → migrate → seed)
- 엣지케이스 — override 가 tracked 로 승격되어 있으면 `.gitignore` 만으론 부족 → `git rm --cached` 필요 (현재 `??` untracked 이므로 ignore 만으로 충분)

## Scenario (E2E Ring Mapping)

| Ring | ID | 케이스 |
|---|---|---|
| 0 | `00-stack-up` | 기동 sanity |
| 1 | `f01-map-selection` | 지도 선택 + StatusBar testid |
| 1 | `f02-agent-chat` | PAE + SSE |
| 1 | `f03-summary-report` | Summary card + attribution |
| 1 | `f05-compare` | 다중 상권 (rewriter 배제 회귀) |
| 1 | `f11-landing` | `/` 랜딩 라우트 |
| 3 | `neg-no-district` | clarification (planner fallback 회귀) |
| 3 | `p0-regression` | StatusBar testid + 매출 단위 |

Pass/Fail 는 아래 Pass 반복 섹션에 기록.

## Pass 반복

### Pass 1 (2026-04-24 실행)

| 체크 | 결과 | 증거 |
|---|---|---|
| `.gitignore` override.yml 등록 | ✅ PASS | `git check-ignore` exit=0 |
| ruff check (planner/formatting/utils/respond/evaluator) | ✅ PASS | All checks passed |
| docker compose config (base + prod) | ✅ PASS | config 파싱 OK · merged prod 에 `./server:/app`, `--reload` 부재 |
| Playwright ring0 | ✅ 5/5 PASS | `npx playwright test ring0 --project=chromium` |
| Playwright ring3 (neg-no-district, neg-prompt-injection, p0-regression) | ✅ 9 PASS / 1 skip | P0-1 real-only skip (USE_MOCK dev) |
| Playwright ring1 (f01,f02,f03,f05,f11) | ⚠️ 22 PASS / 2 FAIL (F05-H3, F05-H4) | 조사 — frontend dev 서버가 `.env.local` 의 `:8002` 고정 → backend(:8000) 미도달 (테스트 인프라 오설정) |
| Backend direct smoke (clarify/3-way/exclude) | ✅ PASS | clarify → tool 0건 · 3-way → `[3120189,3120103,3120053]` · exclude → 홍대 drop `[3120052,3120053]` |

**판정**: F05-H3/H4 는 planner 회귀 아님 — Playwright 가 stale `npm run dev` (`NEXT_PUBLIC_API_URL=http://localhost:8002` build-time bake-in) 를 사용해 fetch 실패. backend `/api/chat` 직접 호출 smoke 로 W1/W2 + ambiguous short-circuit 전부 정상 확인.

### Pass 2 (필요 시)
- 프론트 dev 서버 env 교정 후 F05-H3/H4 재실행 — deploy 선결 조건은 아님 (프로덕션 이미지는 빌드 타임 env 사용)

## Agent 모델 선택
- 설계: opus (현재 세션)
- 실행: 직접 (짧은 smoke, subagent 불필요)

## Validation

- ✅ ruff clean
- ✅ docker compose config clean
- ✅ `.gitignore` override 등록
- ✅ ring0 5/5 · ring3 9/9 (skip 1) · ring1 backend 회귀 없음
- ⚠️ ring1 F05-H3/H4 = 로컬 dev env 문제 (배포 블로커 아님)

## 배포 go/no-go 판정

**GO (조건부)** — 아래 항목은 프로덕션 CI/운영자 책임:

1. **이미지 빌드**: CI 환경(MITM 없음)에서 `docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend frontend migrate seed` 성공 확인 후 push
2. **배포 머신 `.env.dev` 부재 확인**: prod 서버에 `.env` 만 있어야 함 (pydantic 이 `.env.dev` 를 우선 로드하는 버그 회피). `ls /opt/marketscope/.env*` 로 사전 점검
3. **`docker-compose.override.yml` 부재 확인**: prod 서버에 해당 파일 없어야 함. 있으면 즉시 `rm`. (.gitignore 등록으로 git 경로 배포는 차단, 수동 rsync 만 주의)
4. **배포 직후 smoke**:
   - `curl $PROD/api/health/detail` 200
   - `curl -N $PROD/api/chat` clarification 경로 (`이 지역 요약`) → tool 0건 + suggestion + done
   - `curl -N $PROD/api/chat` comparison 경로 (`강남역과 홍대입구를 비교해줘`) → `compare_districts` 2 codes
   - `done.trace_id` 발행 확인 (Langfuse L1)

## Metadata

- Created: 2026-04-24
- Owner: cyon1
- Status: Pass 1 완료 · GO (조건부)
