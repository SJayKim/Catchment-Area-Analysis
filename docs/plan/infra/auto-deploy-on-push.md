# Auto Deploy on Push — 배포서버 push 자동배포 파이프라인

## Context

- 본 머신이 **프로덕션 배포 서버**(marketscope.robitlabs.co.kr, `docker-compose.prod.yml` 스택)다. 현재 배포는 매번 수동 세션(git pull → 롤백 태그 → build → up → flush → smoke)으로 진행 — 최근 사례 [prod-deploy-2026-07-04](prod-deploy-2026-07-04.md).
- origin/main 에 push 가 도착하면 이 서버가 **자동으로 감지 → CI green 확인 → 재빌드/재기동 → 캐시 flush → smoke → 실패 시 자동 롤백** 하도록 상시 파이프라인을 세팅한다.
- **방식 결정: GitHub → 서버 "폴링(pull) 방식"** (systemd timer + 배포 스크립트).
  - 대안 A) GitHub Actions self-hosted runner: GitHub 워크플로우가 prod 서버에서 임의 코드 실행 — 공격면·러너 유지보수 부담. 기각.
  - 대안 B) webhook 수신 서버: 인바운드 엔드포인트 + 시크릿 검증 데몬 신규 운영 필요. 기각.
  - 채택 C) 폴링: 인바운드 표면 0, 시크릿 불요(공개 API), 구성요소가 스크립트 1개 + systemd unit 2개뿐. push 반영 지연은 폴링 주기(≤2분)로 수용.
- **Memory 참조**:
  - `feedback_pg_restore_dataonly_search_path.md` — DB 롤백 경로가 필요해질 때 복원 문장은 `public.` 한정 + `--single-transaction` 패턴 유지 (본 Plan 의 자동 롤백은 이미지 레벨만 다루고 DB 는 건드리지 않지만, runbook 링크에 명시).
- **Status 기록 교훈** (memory 파일 아닌 current-status 기재분):
  - `stale container vs source` (2026-06-08): 이미지가 소스보다 6주 stale 했던 사례 → 자동배포의 핵심 동기. 배포 성공 판정에 "이미지가 방금 커밋으로 빌드됐는지" 마커 확인 포함.
  - `compose env 블록이 env_file 을 오버라이드 + 호스트 셸 env 흡수` (2026-07-02): 배포 스크립트는 **깨끗한 env 로 compose 실행** (`env -i` 수준의 최소 환경 + `.env` 만) — 호스트 셸 오염이 prod 컨테이너 설정을 뒤집는 사고 차단.
  - `.env.dev 임시 이동 후 빌드` (2026-07-04 런로그): 빌드 시 dev env bake-in 방지 절차를 스크립트에 그대로 코드화.
  - `배포 시 flush_cache.py 필수` (2026-07-03/04): report:* Redis 캐시 포이즈닝 방지 — 스크립트 필수 스텝.

## Scope

- **In Scope**:
  - `scripts/deploy/auto_deploy.sh` — 감지·게이트·배포·검증·롤백 전 과정 단일 스크립트 (수동 단독 실행도 가능)
  - `deploy/systemd/marketscope-autodeploy.service` + `.timer` — 2분 주기 폴링 유닛 (+ 설치 스크립트 or 설치 절차 문서)
  - CI green 게이트: GitHub REST API(`/commits/{sha}/check-runs`, 무인증) 로 push 커밋의 CI 결론 확인
  - 자동 롤백: smoke 실패 시 `prev-auto` 태그 이미지로 재기동
  - 배포 로그: `data/deploy-logs/`(gitignore) 에 run 별 로그 + 최근 상태 파일
  - `docs/ops/production-deployment.md` 에 자동배포 운영 섹션 추가
- **Out of Scope**:
  - DB 마이그레이션/시드 자동 롤백 (기존 migrate init-container 관례 유지 — DB 롤백은 수동 runbook)
  - blue-green / zero-downtime (현행 `up -d --build` 재기동 방식 유지, 수 초 단절 수용)
  - GitHub Actions self-hosted runner, webhook 데몬
  - dev(:3000) / e2e(:8002) 스택 — prod 스택만 대상
  - Slack/메일 알림 (로그 + 상태 파일까지만, 알림은 후속)

## Design

### 흐름

```
systemd timer (2분)
  └─ auto_deploy.sh
       1. flock 잠금 (동시 실행 차단, 진행 중이면 즉시 종료)
       2. git fetch origin main
       3. 신규 커밋 없음(HEAD == origin/main) → exit 0 (no-op, 로그 미생성)
       4. 안전 게이트:
          - 워킹트리 dirty 검사 — tracked 변경이 허용목록(.claude/settings.local.json) 외 존재 시 배포 중단 + 상태파일에 BLOCKED_DIRTY 기록
            (본 서버는 작업 세션 겸용 — 미커밋 작업물을 reset 으로 파괴하지 않는다. --ff-only 만 허용)
          - CI 게이트: GitHub check-runs API 로 origin/main tip 의 CI 성공 확인.
            pending → 이번 tick 은 대기(exit 0), failure → BLOCKED_CI 기록 후 해당 SHA 재시도 안 함
       5. 롤백 준비: 현행 이미지 3종(backend/frontend/migrate) → `prev-auto` 재태그
       6. git merge --ff-only origin/main
       7. 빌드: .env.dev 임시 이동 → docker compose -f docker-compose.prod.yml build → .env.dev 원복 (trap 으로 실패 시에도 원복 보장)
       8. up -d → backend healthy 대기 (timeout 180s)
       9. flush_cache.py 실행 (report:* 등 Redis flush)
      10. smoke: :8000/health 200 · :3200 200 · 외부 도메인 `/`(frontend) + `/api/health/detail`(backend) 200 · /api/districts total>0
          (구현 중 정정: 외부 `/health` 는 nginx 라우팅상 404 — backend 루트는 외부 미노출)
      11. 실패 시 자동 롤백: prev-auto 재태그 → up -d --force-recreate → smoke 재확인 → ROLLED_BACK 기록
      12. 성공: last-deploy.json (sha/시각/결과) 갱신 + run 로그 저장
```

### 변경 파일

| 파일 | 변경 요지 |
|---|---|
| `scripts/deploy/auto_deploy.sh` | 신규. 위 1~12 스텝. `bash -euo pipefail`, flock, trap 원복, 최소 env 로 compose 호출 |
| `scripts/deploy/install_autodeploy.sh` | 신규. systemd unit 2개 설치 + `daemon-reload` + `enable --now` (sudo 필요, 사용자 실행) |
| `deploy/systemd/marketscope-autodeploy.service` | 신규. `Type=oneshot`, `User=sjkim`, `WorkingDirectory=/home/sjkim/Catchment-Area-Analysis`, 스크립트 실행 |
| `deploy/systemd/marketscope-autodeploy.timer` | 신규. `OnBootSec=2min`, `OnUnitActiveSec=2min`, `Persistent=true` |
| `.gitignore` | `data/deploy-logs/` 추가 |
| `docs/ops/production-deployment.md` | "자동배포 운영" 섹션 — 활성/비활성(`systemctl disable --now`), 상태 확인, BLOCKED_* 해소법, 수동 배포와의 관계 |

### 의존성 / 선행 Plan

- 선행: [prod-deploy-2026-07-04](prod-deploy-2026-07-04.md) 배포 절차가 golden path — 스크립트는 그 런로그의 코드화.
- **선결 조건**: 현재 로컬 main 이 origin 대비 ahead(미push 커밋 존재, 사용자 push 승인 대기 — status 2026-07-04). 자동배포는 "origin/main = 진실의 원천" 전제이므로 **활성화 전에 push 정리 필수**. 스크립트도 local ahead 상태면 BLOCKED_AHEAD 로 중단하게 방어.
- GitHub API 무인증 rate limit 60req/h — 2분 폴링(30/h) + 커밋 있을 때만 check-runs 호출이라 여유. private 전환 시 `GITHUB_TOKEN` env 지원(옵션 처리).

## Checklist

- [x] C1. `scripts/deploy/auto_deploy.sh` 작성 — flock·fetch·no-op 판정·dirty/ahead 가드 (+BLOCKED_BRANCH 가드 추가)
- [x] C2. CI 게이트 함수 — check-runs API 파싱 (green/pending/failure/api-error 4분기), 실패 SHA 캐시(`blocked-shas.txt`)로 재시도 방지. jq 표현식 synthetic 5케이스 + live API green 검증
- [x] C3. 빌드/기동 스텝 — `.env.dev` 이동+trap EXIT 원복, prev-auto 재태그, healthy 대기(180s) + stale-image 마커(Created ≥ deploy start)
- [x] C4. flush + smoke 4항목 + 실패 시 자동 롤백 경로 (`set -E` + ERR trap → rollback, 롤백 후 smoke 재확인, ROLLBACK_FAILED 구분)
- [x] C5. 로그/상태 — `data/deploy-logs/deploy-<ts>-<sha>.log` + `last-deploy.json`, `.gitignore` 갱신 (+`.env.dev.autodeploy-moved` 잔존물도 ignore)
- [x] C6. systemd unit 2개 + `install_autodeploy.sh` 작성 (`TimeoutStartSec=1800` — oneshot 기본 90s 로는 빌드 중 강제종료). `systemd-analyze verify` PASS
- [x] C7. `docs/ops/production-deployment.md` §6 자동배포 섹션 추가 (result 7종 해소표 포함)
- [x] C8. 드라이런: 수동 1회 실행 no-op exit 0 · 로그 미생성 · flock 동시실행 차단 · smoke 4항목 라이브 개별 PASS · dirty 필터/date 파싱 단위 검증
- [ ] C9. 실배포 리허설: 무해 커밋(문서 touch) push → timer 경유 자동배포 성공 확인 — **선행: 사용자 `sudo bash scripts/deploy/install_autodeploy.sh`** (본 커밋 push 자체가 첫 리허설 트리거가 됨)
- [ ] C10. 롤백 리허설: smoke 강제 실패 주입(예: 임시로 잘못된 헬스 URL) → prev-auto 복귀 확인 후 원복

## 재검토 (Self-Review Gate)

- [x] **엣지: 워킹트리 dirty** — 본 서버는 Claude 작업 세션 겸용. `reset --hard` 절대 금지, `--ff-only` + dirty 시 BLOCKED. 허용목록은 `.claude/settings.local.json` 1개만. (untracked 는 ff merge 에 무해라 통과 — 충돌 시 merge 실패→롤백 경로가 안전망)
- [x] **엣지: local ahead** — 서버에서 직접 커밋한 미push 분기 존재 시 ff 불가 → BLOCKED_AHEAD (자동 push 는 하지 않음, 사용자 판단).
- [x] **엣지: 빌드 중 timer 재발화** — flock(-n, 즉시 skip) + timer `OnUnitActiveSec`(직전 종료 기준) 2중 보장. 동시실행 차단 실측 확인.
- [x] **엣지: .env.dev 원복 누락** — trap EXIT 로 무조건 원복 (2026-07-04 수동 절차의 실수 여지 제거). 잔존물 `.env.dev.autodeploy-moved` 는 gitignore.
- [x] **엣지: 호스트 셸 env 오염** — systemd 실행이라 대화 셸 오염과 무관하지만, 스크립트 내부에서도 USE_MOCK/AGENT_LOOP_VERSION 등 위험 변수 unset 후 compose 호출.
- [x] **엣지: CI pending 장기화** — failure 아니면 매 tick 재확인만 (배포 안 함), 별도 timeout 없음. API 오류(network)도 pending 취급.
- [x] **Memory 교훈**: flush 필수 / stale-image 마커 / env bake-in — Design 에 반영됨.
- [x] **타 Plan 충돌**: e2e 스택(:8002)·dev 스택과 compose project 분리 완료(`marketscope-dev`) → 자동배포는 prod project 만 조작. 스트리밍 재설계(deferred) 등 코드 Plan 과 무충돌.
- [x] **엣지 (구현 중 발견): systemd oneshot 기본 timeout 90s** — 빌드가 그보다 길어 강제종료 → `TimeoutStartSec=1800`.
- [x] **엣지 (구현 중 발견): 함수 내부 실패의 ERR trap 미전파** — `set -e` 만으로는 함수 안 실패가 롤백을 건너뜀 → `set -E`(errtrace) 필수.

## Scenario (E2E Ring Mapping)

- **Ring**: 0 (infra) — 앱 기능이 아닌 배포 인프라. 기존 Playwright ring 스펙 추가 없음(스크립트/유닛 레벨 검증).
- **Scenario ID**: `R0-DEPLOY-AUTOPUSH-01` (정상 자동배포) / `R0-DEPLOY-AUTOPUSH-02` (smoke 실패 자동 롤백) / `R0-DEPLOY-AUTOPUSH-03` (dirty/ahead/CI-fail 차단)
- **사전조건**: origin/main 과 로컬 main 동기화(미push 커밋 정리), prod 스택 healthy, timer enable.
- **실행 단계**: 무해 커밋 push → ≤2분 내 timer 발화 → 로그 tail.
- **기대 결과**: `last-deploy.json` 에 신규 SHA + SUCCESS, 외부 도메인 200, `docker inspect` 이미지 생성시각이 배포 시각과 일치, 롤백 시나리오에서는 prev-auto 이미지로 서비스 지속.

## Pass 반복 (Iteration Plan)

- **Pass 1 (기본)**: C1~C8 — 스크립트+유닛 작성, no-op 드라이런.
- **Pass 2 (엣지)**: C9~C10 + 차단 3종(BLOCKED_DIRTY/AHEAD/CI) 강제 재현.
- **Pass 3 (성능/회귀)**: 2분 폴링 24h 관찰 — no-op tick 부하(2s 내 종료·로그 무증가), GitHub API rate 여유, prod-smoke(Chromium 계열) 재실행으로 서비스 회귀 0 확인.
- 각 Pass 후 해당 Scenario 재실행, Fail → 수정 → 재실행.

## Agent 모델 선택

- **설계**: opus — 롤백/게이트 순서 등 실패모드 추론 필요 (본 Plan)
- **구현**: sonnet — bash/systemd 는 스펙이 명확
- **검증**: haiku — Scenario Pass/Fail 판정 + 로그 파싱
- 근거: 표준 관례. 파괴 리스크(prod 재기동·이미지 태그)가 있는 스크립트라 설계 단계에 실패모드 열거를 집중 배치.

## Validation

- 수동: `bash scripts/deploy/auto_deploy.sh` 단독 실행 (no-op / 강제 배포 `--force` 플래그) · `systemctl status marketscope-autodeploy.timer` · `cat data/deploy-logs/last-deploy.json`
- smoke 자동 검증은 스크립트 내장 (health·외부 도메인·districts count)
- `/e2e-run 0` — 자동배포 이후 스택 sanity (ring0 preflight)
- 서비스 회귀: `cd frontend && npx playwright test prod-smoke --project=chromium`

## Metadata

- 작성일: 2026-07-04
- 작성자: Claude Code (plan-new skill)
