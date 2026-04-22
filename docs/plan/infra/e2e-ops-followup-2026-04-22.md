# E2E + Ops 후속 조치 (backend 재빌드 + e2e stack + teardown) 2026-04-22

> `e2e-ops-2026-04-22.md` run 종료 후 잔여 조치. 2 FAIL(stale container) + 6 SKIP(e2e stack 미가용) 회복 + 문서 일관성 복구.

## Context

- 이전 run 결과: 47 PASS / 2 FAIL / 10 SKIP (Consumer score 92/100, CONDITIONAL READY).
- FAIL 원인: backend 이미지가 2026-04-17 11:02 빌드(`ff9909c` / `3c5f884` 미반영). 코드 회귀 0.
- SKIP 원인:
  - 6 건 — e2e 전용 stack 미가용(`docker-compose.e2e.yml` build 중 `pip install` SSL 실패)
  - 4 건 — Mock/Smoke 전용 design skip (의도됨)
- Memory 참조:
  - `feedback_stale_container_vs_source.md` — 컨테이너 빌드 시각 확인 필수
  - `feedback_probe_endpoint_shape_first.md` — 엔드포인트 스키마 작성 전 probe
  - `feedback_marketscope_sse_format.md` — SSE 포맷 불변 (backend 재빌드 후에도 유지)
  - `feedback_check_env_before_test.md` — Mock(D3001) vs Real(3120189) 전환 시 env 재확인

## Scope

In scope:
- **Backend 컨테이너 재빌드** — Dockerfile 에 pip SSL 우회 build-arg 반영 후 dev stack `backend` 재빌드 + 최신 커밋 적용 확인
- **Ring 1 F03/F05 재실행** — F03-H4 + F05-H4 PASS 확인 (stale container regression 회복)
- **E2E 전용 stack 가동** — `docker-compose.e2e.yml` 이 정상 build 되도록 수정 후 `preflight.sh` 통과
- **SKIP 6건 재실행** — L1-E02~E05 (4건) + reg-2026-04-17 `cleanup_alembic` / `flush_cache` (2건)
- **문서 일관성 갱신** — current-status.md 헤더/결과, e2e-run-2026-04-22.md 재실행 섹션, Dockerfile 변경 사항 반영
- **Teardown** — e2e stack down (사용자 별도 지시 시) 및 로컬 frontend dev server 정리

Out of scope:
- Ring 2 / Ring 3 나머지 재실행 (이전 run 에서 PASS — 회귀 없음)
- Real 모드 확장 (2026-04-21 에 24/24 확인)
- Phase 2 기능 구현

## Design

### D1 — Dockerfile SSL 우회 전략

`pip install` 에서 CERTIFICATE_VERIFY_FAILED 발생. 3가지 후보:

| 옵션 | 장점 | 단점 | 채택 |
|------|------|------|------|
| A) `PIP_INDEX_URL=http://pypi.org/simple` + `--trusted-host` | 제일 빠름, 기존 이미지만 수정 | http 평문(무결성↓) | ✅ 1순위 |
| B) Corporate CA 번들 주입 (`ADD corp-ca.pem`) | 보안 유지 | CA 파일 별도 관리 필요 | ⏸ 보류 |
| C) `--cert /etc/ssl/certs/ca-certificates.crt` | 시스템 CA 재사용 | Python `certifi` 별도 경로라 효과 X | ❌ 기각 |

채택: A + 필요 시 B. Dockerfile 에 build-arg `PIP_INDEX_URL` / `PIP_TRUSTED_HOST` 를 추가해 **보안적 기본값은 PyPI HTTPS 유지**, E2E 재빌드 시에만 HTTP 옵션 on.

구현 스펙:
```dockerfile
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}
RUN pip install --no-cache-dir --prefix=/install .
```

build-arg 미지정 시 현재 동작 동일(HTTPS PyPI). SSL 장애 환경에선:
```
docker compose build --build-arg PIP_INDEX_URL=http://pypi.org/simple \
                     --build-arg PIP_TRUSTED_HOST=pypi.org \
                     backend
```

### D2 — 실행 순서

1. **Dockerfile 수정** (server/Dockerfile)
2. **dev stack `backend` 재빌드** — `docker compose build backend` → `docker compose up -d backend`
3. **커밋 반영 확인** — container 내부에서 `python -c "from server.repositories.real.districts import detect_districts_in_message; ..."` 로 F05-H4 의 multi-detect 로직 확인 + `/api/districts/D3001` 응답에 `monthly_sales` 키 존재 확인
4. **F03/F05 재실행** — `npx playwright test ring1-features/f03 ring1-features/f05 --reporter=list`
5. **E2E stack preflight** — `bash scripts/e2e/preflight.sh` (내부적으로 동일 build-arg 사용)
6. **SKIP 6건 재실행** — `npx playwright test ring3-negative/reg-2026-04-17 ring3-negative/l1-langfuse --reporter=list`
7. **문서 갱신**
8. **Teardown** — 사용자 지시 확인 후 `docker compose -f docker-compose.e2e.yml down`

### D3 — 문서 일관성 범위

| 대상 | 갱신 내용 |
|------|---------|
| `docs/status/current-status.md` | 상단 헤더 47/2/10 → 최종 결과로 업데이트. "완료 항목 (2026-04-22)" 섹션에 followup 결과 append |
| `docs/qa/runs/e2e-run-2026-04-22.md` | 재실행 결과(FAIL → PASS / SKIP → PASS) 추가 섹션 |
| `docs/architecture/deployment.md` | Dockerfile build-arg 추가 사실 반영 (SSL 우회 가이드) |
| `.env.example` | 변경 없음 (환경변수가 아닌 build-arg 라서) |
| `docs/plan/infra/e2e-ops-followup-2026-04-22.md` | 본 문서 — 결과 섹션 채움 |

### D4 — 재검토 (Self-Review Gate)

- **엣지케이스 1**: dev stack `backend` 재빌드 시 기존 컨테이너가 있는데 compose up 시 state 꼬임 가능 → `docker compose up -d --force-recreate backend` 사용
- **엣지케이스 2**: e2e stack 과 dev stack 이 동일 Dockerfile 사용 → 재빌드 1회로 양쪽 적용 확인
- **엣지케이스 3**: HTTP PyPI 로 설치 후 이미지가 build 성공해도 package hash 변조 위험 → `pip install` 자체가 아직 signature 검증 하지 않으므로 원래부터 HTTPS 만이 방어선. 이 조치는 **SSL 장애 환경 한시적** 용도임을 주석에 명시
- **엣지케이스 4**: 이전 run 에서 OPS-01 이 `use_mock === true` 가드 제거된 상태로 PASS. e2e stack 은 Mock 모드라 다시 PASS 예상. 회귀 확인
- **메모리 교훈 충돌 여부**: `feedback_stale_container_vs_source.md` 와 정합 — 본 plan 이 바로 그 교훈 적용 사례
- **다른 plan 충돌**: `llmops-l1-e2e.md` 의 L1-E02~E05 는 backend python REPL 사용. e2e stack 가동 시 의존성 자동 충족

### D5 — Pass 반복 전략

- **Pass 1**: Dockerfile fix + dev backend 재빌드 + F03/F05 재실행 → 기본 FAIL 회복 확인
- **Pass 2**: e2e stack 가동 + SKIP 6건 재실행 → 커버리지 회복
- **Pass 3** (optional, 사용자 지시 시): Ring 0~3 전체 재실행으로 최종 baseline 확정

FAIL 발생 시 Dockerfile 추가 수정(CA 주입) 또는 e2e stack 별도 분석.

### D6 — Agent 모델 선택

- 설계: 이미 사용자와 정렬 — 추가 opus 불필요
- 구현: sonnet (현 assistant)
- 검증: haiku 대신 Playwright 자동 verdict + python 직접 probe 로 대체

## Checklist

- [x] server/Dockerfile 에 `ARG PIP_INDEX_URL` / `ARG PIP_TRUSTED_HOST` 추가 (기본 HTTPS 유지)
- [x] dev stack backend 재빌드 — HTTPS + `trusted-host` 조합으로 빌드 성공 (처음 시도한 `http://pypi.org/simple` 은 pypi.org 가 HTTP 리다이렉트 미지원이라 실패)
- [x] `docker compose up -d --force-recreate backend` → healthy 확인 (CreatedAt: 2026-04-22 11:26)
- [x] container 내부 probe — `monthlySales` 키 + multi-detect 로직 확인 (Redis `summary:*` 캐시 선 플러시 필요)
- [x] F03 + F05 재실행 — **F03 4/4 + F05 5/5 = 9/9 PASS** (이전 FAIL 2건 회복)
- [x] e2e stack preflight 통과 — 포트 55432 Windows excluded range 회피로 15432/16379 로 변경
- [x] L1 7/7 + reg-2026-04-17 6/6 + Ring 0 4/4 + OPS 2/2 = **19/19 PASS**
- [x] current-status.md 헤더 + 완료 항목 갱신
- [x] e2e-run-2026-04-22.md 2차 재실행 섹션 append
- [x] docs/architecture/deployment.md 에 build-arg 가이드 추가
- [ ] (사용자 지시 시) teardown 수행

## 결과

**Consumer-experience score**: 92 → **100/100**. **판정: READY**

| 항목 | 1차 run | 2차 재실행 |
|------|--------|-----------|
| Ring 1 F03/F05 (9 test) | 7 PASS / 2 FAIL | **9 PASS** |
| Ring 3 L1 (7 test) | 3 PASS / 4 SKIP | **7 PASS** |
| Ring 3 reg (6 test) | 4 PASS / 2 SKIP | **6 PASS** |
| Ring 0 (4 test) | 4 PASS | 4 PASS (재확인) |
| OPS-01/02 (2 test) | 2 PASS | 2 PASS (재확인) |
| **stale FAIL** | 2 | 0 |
| **infra SKIP** | 6 | 0 |

### 예상 외 발견

- **pip HTTP 리다이렉트 미지원**: 최초 가설(`http://pypi.org/simple`) 은 pypi.org 가 HTTP→HTTPS 리다이렉트를 안 받으므로 바로 실패. 대신 HTTPS 유지 + `trusted-host` 로 SSL 검증만 skip 하는 방식으로 해결.
- **Windows excluded port range**: db:55432 / redis:56379 가 Windows Hyper-V reserved range(55015-55614) 에 포함되어 바인딩 실패. `netsh interface ipv4 show excludedportrange protocol=tcp` 로 확인 후 15432 / 16379 로 이동.
- **Redis 캐시 stale**: backend 재빌드 후에도 summary card 에 `monthlySales` 키가 없었음 → `summary:*` 4개 키를 flush 한 뒤 회복. (향후 rebuild 시 운영 스크립트로 flush 자동화 검토)

## Scenario (E2E Ring Mapping)

| Ring | Scenario ID | 역할 |
|------|------------|------|
| 1 | F03-H4 | monthly_sales 키 회복 (backend 재빌드 검증) |
| 1 | F05-H4 | 한글 조사 과/를 multi-detect 회복 |
| 3 | L1-E02 | Langfuse v4 SDK import fail → handler None |
| 3 | L1-E03 | 잘못된 키 + 생성자 실패 → `_tracer_valid=False` |
| 3 | L1-E04 | `_hash_session` 결정성 + ascii/한글 |
| 3 | L1-E05 | salt 교체 시 해시 변화 |
| 3 | REG-CLEANUP-ALEMBIC | alembic_version 중복 정리 스크립트 |
| 3 | REG-FLUSH-CACHE | flush_cache.py 5 prefix |

## Validation

- Playwright exit code 0 + 각 시나리오 `autoVerdict.result === 'PASS'`
- `docker ps --format '{{.Names}}\t{{.CreatedAt}}'` 에서 backend CreatedAt 이 오늘 날짜로 갱신
- `docker compose -f docker-compose.e2e.yml ps` 에서 전 서비스 healthy
- 문서 4건 갱신 완료 + git status 에 따른 untracked/modified 구분 명시

## Metadata

- 작성: 2026-04-22
- 기준 커밋: `42b2209` + 후속 fix (아직 미커밋)
- 산출물: 본 plan / Dockerfile diff / current-status 갱신 / run report 2차 섹션
