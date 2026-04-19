# E2E 회귀 테스트 플랜 — 2026-04-19 (배포 근본해결 + 매출 단위 fix 이후)

## Context

- 최근 main 에 들어간 대규모 변경이 E2E 회귀 없이 커밋만 된 상태 — 커밋 `4dbd598` (Plan A 매출 단위 후속 3곳 + Plan B 배포 근본해결 7건 + 비교모드 다색 하이라이트) 과 `fdd6be8` (하네스 공유 등록) 은 수동 smoke 만 실행됨. 직전 공식 Real 모드 런은 `2026-04-07` (`docs/qa/runs/e2e-run-2026-04-07-real.md`, 41/45 PASS) 로 12일 전이다.
- **프로덕션 (`marketscope.robitlabs.co.kr`) 이 라이브**. 외부 호스트 nginx → `docker-compose.prod.yml` (frontend 3200 / backend 8000, DB·Redis 내부 전용) 로 가동 중. 사용자가 방문 중이므로 테스트 트래픽이 운영 측으로 흘러가면 안 된다 (로그 오염 / LLM 요금 / Langfuse trace 노이즈 / Rate Limit 소진).
- 커밋 `4dbd598` 이 건드린 경로는 모두 재검증 필요:
  - `scripts/cleanup_alembic.py` / `scripts/flush_cache.py` / `scripts/verify_sales_units.py` / `scripts/validate_env.py` (신규 4종)
  - `frontend/src/app/_proxy/kakao-sdk/route.ts` (기존 `/api/kakao-sdk` 제거) → 지도 SDK 로드 경로 변경
  - `agent/tools/estimated_sales.py` / `agent/tools/district_summary.py` / `agent/nodes/respond.py` (매출 키 치환 3곳) → 매출/QoQ 수치 표시 회귀 위험
  - `frontend/src/components/map/DistrictLayer.tsx` → 비교모드 다색 하이라이트 (기존 selected 단색 경로 회귀 위험)
- 기존 E2E 자산: `frontend/e2e/ring{0,1,2,3}-*` 45 시나리오 + `playwright.config.ts` (baseURL `http://localhost:3001`, backend `8002`) + helpers (`modeGuard`, `sseCapture`, `evalPacket`) 존재.

### Memory 참조
- `feedback_sse_buffering.md` — Chat SSE 는 Next.js rewrite 프록시 미사용, 테스트도 `NEXT_PUBLIC_CHAT_API_URL` 을 백엔드 직접 주소로 세팅할 것.
- `feedback_mock_real_pattern.md` — Mock 모드에서 DB/Redis 연결 시도 금지. 테스트 compose 에서도 Mock Ring 1 실행 시 `USE_MOCK=true` 단독 서버 기동 지원.
- `feedback_korean_particles.md` — F05 비교 시나리오 (과/를/이/가 조사) 는 반드시 Ring 1 f05 + Ring 3 negative 양쪽에 케이스 포함.

## Scope

- **In Scope**
  - 격리된 로컬 stack 에서 Ring 0~3 전체 (45 시나리오) 실행 + 신규 회귀 15 시나리오 추가.
  - 운영 배포 (`marketscope.robitlabs.co.kr`) 로의 아웃바운드 요청 전면 차단 및 감사.
  - 커밋 `4dbd598` 변경 경로 4군데 회귀 시나리오.
  - Mock 모드 전체 + Real 모드 핵심 happy-path (F01/F02/F03/F05/F07/F08).
- **Out of Scope**
  - Phase 2 결제/구독/Tier 게이팅 (미구현, 별도 Business 스코프).
  - 서울 열린데이터 API ETL 회귀 (장시간·외부 API 키 의존, 별도 infra 잡).
  - 부하/동시성 테스트 (별도 `docs/plan/infra/load-test-plan.md`).
  - `store_history` 데이터 부재 이슈 (ETL 미실행 상태라 Real 모드 F08 은 design SKIP 유지).

## Design

### D1. 운영 격리 4축

| 축 | 전략 | 구체 구현 |
|---|---|---|
| **네트워크** | 로컬 `127.0.0.1` 만 타겟, 도메인 레벨 차단 | Playwright `context.route('**/marketscope.robitlabs.co.kr/**', r => r.abort('failed'))` 글로벌 훅 추가. `context.route('**/api.langfuse.com/**', r => r.fulfill({status:204}))` 로 telemetry stub. |
| **포트/볼륨** | prod compose 와 포트 겹치지 않게 전용 compose 파일 | `docker-compose.e2e.yml` 신규: frontend `3001`, backend `8002`, db `55432`, redis `56379`. volume `marketscope-e2e-pgdata` 전용 명명. `COMPOSE_PROJECT_NAME=marketscope-e2e`. |
| **LLM/예산** | 실 Anthropic/Google 키 사용 최소화 | `.env.e2e` 에 `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=${E2E_ANTHROPIC_KEY}` 테스트 전용 키(월 $10 상한) 사용. Mock Ring 1 대다수는 intent classifier rule path 로 LLM 호출 skip 가능. Ring 0 에 LLM call budget pre-flight 스크립트 추가. |
| **Env 파일** | 운영 `.env` 로딩 차단 | `scripts/validate_env.py` 실행 시 `ENV_PROFILE=e2e` 가드 → `.env.e2e` 만 로딩, `NEXT_PUBLIC_API_URL=http://localhost:8002` 강제. 운영 `.env` 의 `LANGFUSE_PUBLIC_KEY` 등은 로딩 안 됨. |

### D2. 변경 파일

| 경로 | 역할 | 신규/수정 |
|---|---|---|
| `docker-compose.e2e.yml` | 테스트 전용 stack, prod 포트 미충돌 | 신규 |
| `.env.e2e.example` | 테스트 env 템플릿 (운영 키 절대 미포함) | 신규 |
| `frontend/e2e/helpers/prodGuard.ts` | Playwright context hook — 운영 도메인 요청 abort + 감사 로그 | 신규 |
| `frontend/e2e/helpers/setup.ts` | 모든 test file 에서 `prodGuard` 자동 주입 | 수정 |
| `frontend/e2e/ring1-features/f01-map-selection.spec.ts` | `/api/kakao-sdk` → `/_proxy/kakao-sdk` 경로 assertion 업데이트 | 수정 |
| `frontend/e2e/ring1-features/f03-summary-report.spec.ts` | `_enrich_sales` 키 치환 후 `monthly_sales` 표시 회귀 | 수정 |
| `frontend/e2e/ring1-features/f05-compare.spec.ts` | 비교모드 다색 하이라이트 CSS fill color assertion 3케이스 | 수정 |
| `frontend/e2e/ring3-negative/reg-2026-04-17.spec.ts` | 커밋 4dbd598 회귀 특정 (cleanup_alembic idempotent, validate_env 실패 케이스) | 신규 |
| `scripts/e2e/preflight.sh` | compose up-e2e + migrate + seed 검증 + LLM budget probe | 신규 |
| `scripts/e2e/teardown.sh` | 전용 volume 삭제 (운영 volume 오작동 방지 가드: `docker volume ls` 에서 `marketscope-e2e-` prefix 만 허용) | 신규 |
| `docs/qa/runs/e2e-run-2026-04-19.md` | Run 결과 리포트 | Pass 3 종료 시 작성 |

### D3. 실행 토폴로지

```
Host (Windows/WSL) ─┐
                    │  docker-compose.e2e.yml   (COMPOSE_PROJECT_NAME=marketscope-e2e)
                    │    ├── db       :55432  (volume: marketscope-e2e-pgdata)
                    │    ├── redis    :56379
                    │    ├── migrate  (cleanup_alembic + upgrade head)
                    │    ├── seed     (data/seed/marketscope_seed.dump)
                    │    ├── backend  :8002  (USE_MOCK=false, ENV_PROFILE=e2e)
                    │    └── frontend :3001  (NEXT_PUBLIC_API_URL=http://localhost:8002)
                    │
                    └── Playwright runner
                          ├── prodGuard → abort *.robitlabs.co.kr / *.langfuse.com
                          ├── Ring 0 (infra preflight 4건)
                          ├── Ring 1 (Mock + Real feature 25건)
                          ├── Ring 2 (journey 5건)
                          └── Ring 3 (negative + P0 regression 11건 + 신규 4건)
```

운영 서버 (`marketscope.robitlabs.co.kr`, port 443) 는 테스트 수행 중 유지되며 테스트 어떤 컨테이너도 이 호스트 / prod volume / prod `.env` 를 참조하지 않는다.

## Checklist

- [ ] 1. `docker-compose.e2e.yml` 작성 — 포트 `55432 / 56379 / 8002 / 3001`, volume `marketscope-e2e-pgdata`, healthcheck 포함.
- [ ] 2. `.env.e2e.example` 작성 — `USE_MOCK=true` 기본, `NEXT_PUBLIC_API_URL=http://localhost:8002`, telemetry 전부 비활성.
- [ ] 3. `frontend/e2e/helpers/prodGuard.ts` 작성 — 운영 도메인 리스트 (`marketscope.robitlabs.co.kr`, `langfuse.com`, `us.i.posthog.com`) 전부 abort + `ProdHitLog` 직렬화.
- [ ] 4. `setup.ts` 에 `prodGuard` 자동 주입 hook 추가 + 기존 32 spec 회귀 없음 확인 (`npm test -- --list` dry-run).
- [ ] 5. `scripts/e2e/preflight.sh` 작성 — `COMPOSE_PROJECT_NAME` 가드, prod compose 충돌 탐지, migrate 종료코드 체크.
- [ ] 6. `scripts/e2e/teardown.sh` 작성 — volume 이름 prefix 가드 (`marketscope-e2e-` 외 삭제 거부).
- [ ] 7. Pass 1 — Ring 0 (4) + Mock Ring 1 (11) 실행. 기존 41 pass baseline 재현.
- [ ] 8. 신규 회귀 spec 3종 (`f01` kakao-sdk / `f03` sales unit / `f05` 다색) 수정/검증.
- [ ] 9. 신규 `reg-2026-04-17.spec.ts` — cleanup_alembic idempotent (2회 실행), validate_env missing env 실패 케이스, flush_cache 5 prefix 삭제 검증.
- [ ] 10. Pass 2 — Real 모드 happy-path (F01/F02/F03/F05/F07/F08 6건). `store_history` blocker 는 design SKIP 명시.
- [ ] 11. Pass 3 — Ring 2 (5 journey) + Ring 3 (11 negative + 4 신규) 실행.
- [ ] 12. `docs/qa/runs/e2e-run-2026-04-19.md` 리포트 작성 — Ring × Mode 매트릭스, `ProdHitLog` 0건 assertion 명시.
- [ ] 13. `/status-update` 로 진행 반영.

## 재검토 (Self-Review Gate)

- [ ] **엣지 케이스**
  - (a) 개발자가 `docker-compose.yml` 을 이미 up 한 상태에서 e2e 실행 → 포트 충돌 → preflight 가 `docker ps --filter "name=marketscope-"` 로 감지 후 abort.
  - (b) 운영 `.env` 가 리포 루트에 존재 → `ENV_PROFILE=e2e` 미설정 시 백엔드가 실수로 운영 키 로딩 → `validate_env.py` 에서 `NEXT_PUBLIC_API_URL` 이 `localhost` 미포함이면 즉시 exit 1.
  - (c) Playwright 가 실수로 `baseURL` 을 운영으로 설정 → `prodGuard` 에서 첫 네트워크 요청시 abort + test fail + `ProdHitLog` 에 기록.
  - (d) 테스트 중 LLM 타임아웃 → circuit breaker + tenacity 재시도 (Phase 6 구현) 경로로 graceful, Real 시나리오는 fixture response mode 활용.
- [ ] **Memory 교훈 반영**
  - SSE 버퍼링: `f02` / `f06` 스트리밍 spec 에서 `NEXT_PUBLIC_CHAT_API_URL=http://localhost:8002` 직접 사용 확인.
  - Mock/Real 패턴: Mock 전용 시나리오는 `requireMode('mock')` 가드.
  - Korean particles: f05 / neg 양쪽에 과/를/이/가/랑 5 케이스.
- [ ] **타 Plan 충돌**
  - `docs/plan/infra/load-test-plan.md` 와 포트 겹치지 않음 (load test 는 prod compose 타겟).
  - `docs/plan/fix/deployment-root-cause-fixes.md` Phase 완료와 시나리오 매칭 (cleanup_alembic / validate_env / `_proxy/kakao-sdk` 전부 reg spec 으로 커버).

## Scenario (E2E Ring Mapping)

### Ring 0 — Pre-flight (Hard stop)

| Scenario ID | 사전조건 | 실행 단계 | 기대 결과 |
|---|---|---|---|
| `0-INFRA-COMPOSE` | `docker-compose.e2e.yml` up 완료 | `docker compose -p marketscope-e2e ps` | 4 services running & healthy |
| `0-INFRA-PORT-COLLIDE` | prod compose 는 다른 네임스페이스 | port 3200 / 8000 점유 상태에서 e2e up | 충돌 없이 3001 / 8002 로 바인딩 |
| `0-INFRA-ENV-GUARD` | `.env.e2e` 세팅 | `python scripts/validate_env.py --profile e2e` | exit 0, `NEXT_PUBLIC_API_URL=http://localhost:8002` 확인 |
| `0-INFRA-PROD-REACH` | 운영 도메인 DNS 는 정상 해석 | Playwright 세션에서 `fetch('https://marketscope.robitlabs.co.kr/health')` | `prodGuard` 가 abort, `ProdHitLog.length === 1` + test PASS (차단 자체가 성공 조건) |

### Ring 1 — Feature 회귀 (Mock 기본, Real 은 별도 프로파일)

| Scenario ID | Mode | 목적 | 기대 결과 |
|---|---|---|---|
| `1-F01-KAKAO-SDK-PROXY` | Mock | `/_proxy/kakao-sdk` 새 경로로 SDK 로드 | script tag src 가 `/_proxy/kakao-sdk` 포함, 지도 init 성공 |
| `1-F01-POLYGON-CLICK` | Mock | 폴리곤 클릭 → SummaryCard | 기존 `feature1` spec 회귀 없음 |
| `1-F02-SSE-STREAM` | Mock | thinking→tool→text→done 순서 | 5 초 이내 텍스트 첫 토큰 도달 |
| `1-F03-SALES-MONTHLY` | Real | `estimated_sales._enrich_sales` 키 수정 회귀 | SummaryCard 월매출 수치 = DB 값 / 3 (분기→월), QoQ growth 비율 `null` 아님 |
| `1-F03-MOCK-PARITY` | Mock | Mock 응답도 `monthly_sales` 키 사용 | 카드 필드 `monthlySales` 렌더 |
| `1-F04-CATEGORY` | Mock | 업종 심층 분석 Tool 호출 경로 | `get_estimated_sales(category=...)` 실제 호출 trace |
| `1-F05-COMPARE-MULTI-COLOR` | Mock | 비교모드 3상권 다색 | DOM `path[data-district-code]` 3개가 각 팔레트 색(fill blue/amber/rose) |
| `1-F05-KOREAN-PARTICLES` | Mock | `강남역과 홍대입구를 비교해줘` | `compare_districts` 호출 args 에 2 code |
| `1-F06-HEATMAP` | Mock | deck.gl HeatmapLayer 프리로드 | 시간 슬라이더 24 frame 모두 200ms 이내 |
| `1-F07-RECOMMEND` | Real | 추천 Top 5 업종 모두 포함 | 응답 리스트 길이 ≥ 5 |
| `1-F08-RISK` | Mock | 리스크 카드 (store_history Real 은 SKIP) | 응답 `closeRate` 필드 존재 |
| `1-F09-SIMULATION` | Mock | 매출 시뮬레이션 p25/p75 | 범위 값 p25 < p50 < p75 |
| `1-F10-PDF` | Mock | PDF 다운로드 | 파일 크기 > 50KB, 한글 폰트 embed |
| `1-M01-MOCK-DATA` | Mock | 5 상권 고정 코드 | `D3001~D3005` 전부 응답 |
| `1-SCRIPT-CLEANUP-ALEMBIC` | Real | `scripts/cleanup_alembic.py` | 2 회 실행해도 idempotent (exit 0 양회) |
| `1-SCRIPT-FLUSH-CACHE` | Real | `scripts/flush_cache.py` | 5 prefix (sales/compare/recommend/simulation/summary) 삭제 카운트 로깅 |
| `1-SCRIPT-VERIFY-SALES` | Real | `scripts/verify_sales_units.py` | 보문역 슈퍼마켓 점포당 월매출 1.3억 ~ 1.5억 range |

### Ring 2 — Journeys

| Scenario ID | 실행 단계 | 기대 결과 |
|---|---|---|
| `2-J01-FIRSTUSER` | 지도 로드 → 검색 → 클릭 → 요약 | 총 SLA 8 초 이내 |
| `2-J02-COMPARE` | 상권 A 선택 → "B 랑 비교" → CompareCard | 다색 강조 + CompareCard 승자 표시 |
| `2-J03-RISK` | 상권 선택 → "이 자리 위험?" → RiskCard → 추천 | 후속 질문 컨텍스트 유지 |
| `2-J04-RECOVERY` | LLM timeout 1 회 → 재시도 → 응답 | 사용자 UI 끊김 없음, progress 지속 |
| `2-J05-PDF-STAKEHOLDER` | 대화 5 턴 → "PDF 로 저장" | 5 초 이내 다운로드 |

### Ring 3 — Negative & Regression

| Scenario ID | 목적 | 기대 결과 |
|---|---|---|
| `3-NEG-NO-DISTRICT` | 상권 미선택 상태 질의 | "상권을 선택해주세요" 안내 |
| `3-NEG-PROMPT-INJECT` | 시스템 프롬프트 노출 시도 | refusal, 도구 미호출 |
| `3-P0-REGRESSION-11` | 기존 11 개 P0 fix 전부 | 모두 PASS |
| `3-REG-PROD-DOMAIN-BLOCK` | 테스트 중 운영 도메인 접근 시도 | `ProdHitLog` 1 건 기록, 테스트는 차단 성공으로 PASS |
| `3-REG-VALIDATE-ENV-FAIL` | `.env` 에서 `NEXT_PUBLIC_API_URL` 제거 | `validate_env.py` exit 1, stderr 에 필드명 |
| `3-REG-SALES-UNIT-GREP` | `grep -rn 'quarterly.*\.get("sales"' server/` | 0 match (회귀 없음) |
| `3-REG-KAKAO-SDK-404-GONE` | `/api/kakao-sdk` 경로 | 404 (이동 완료) & `/_proxy/kakao-sdk` 200 |

## Pass 반복 (Iteration Plan)

- **Pass 1 — Mock E2E baseline + 격리 인프라 확정**
  - D1/D2 변경 적용 → Ring 0 (4) + Mock Ring 1 (11) + Ring 3 (3 regression).
  - Fail 시 prodGuard / preflight 수정 → 재실행.
  - 종료 기준: 기존 32 spec + 신규 3 spec 전부 PASS, `ProdHitLog` 0 건.
- **Pass 2 — Real 모드 happy-path + 매출 단위 회귀**
  - Real compose 전환 (`USE_MOCK=false`), seed dump 복원 후 Ring 1 Real 6 + Ring 2 J02/J03 + Ring 3 REG.
  - Fail 시 root-cause → 커밋 별 bisect (4dbd598 / f6c1229) → fix → 재실행.
  - 종료 기준: Real happy-path 6 건 PASS, `verify_sales_units.py` 값 보고 범위 내.
- **Pass 3 — 전체 매트릭스 + 리포트**
  - Ring 0~3 전수 실행 (Mock + Real) → `docs/qa/runs/e2e-run-2026-04-19.md` 작성.
  - Consumer-experience score ≥ 95/100 목표 (2026-04-07 런 100/100 기준 회귀 방지).
  - Fail 시 Pass 2 로 회귀 루프.

## Agent 모델 선택

- **설계**: `opus` — 격리 토폴로지, prodGuard 설계, LLM budget 전략 모두 판단 트레이드오프 (보안 vs 실제 유사성 vs 비용) 포함 → 심층 추론 필요.
- **구현**: `sonnet` — compose YAML / env / helper 작성은 스펙 명확, Claude Sonnet 4.6 급 코드 작성으로 충분.
- **검증**: `haiku` — Pass/Fail 판정은 artifact (sse.log / ProdHitLog / verdict.json) 스캔 수준이라 경량 모델로 충분. `qa-scenario-runner` subagent 사용.
- 근거: CLAUDE.md 의 3-tier 원칙 준수. 단 Ring 2 journey 평가는 fresh general-purpose subagent 로 bias 차단 (기존 `docs/qa/e2e-qa-test-plan.md` A.3 Evaluator loop 계승).

## Validation

- 수동 검증
  1. `cp .env.e2e.example .env.e2e` → `ANTHROPIC_API_KEY` 테스트 키 입력.
  2. `bash scripts/e2e/preflight.sh` → 4 services healthy, `ProdHitLog` sanity probe OK.
  3. `cd frontend && E2E_BASE_URL=http://localhost:3001 E2E_BACKEND_URL=http://localhost:8002 npm test` — Playwright 전체 실행.
  4. `bash scripts/e2e/teardown.sh` → volume prefix 가드로 운영 volume 건드리지 않음 확인.
  5. `docs/qa/runs/e2e-run-2026-04-19.md` 작성 (Pass/Fail 매트릭스 + ProdHitLog 첨부).
- 자동 검증
  - `/e2e-run 0` → preflight 통과 후 `/e2e-run 1|2|3` 순차 실행 (기존 skill 재사용).
  - GitHub Actions `ci.yml` 에 `e2e-mock` job 추가 (Ring 0 + Mock Ring 1 만, Real 은 수동).

## Metadata

- 작성일: 2026-04-19
- 작성자: Claude Code (plan-new skill 수동 적용)
- 선행 Plan: `docs/plan/fix/deployment-root-cause-fixes.md`, `docs/plan/fix/sales-unit-conversion-fix.md`
- 관련 문서: `docs/qa/e2e-qa-test-plan.md`, `docs/qa/runs/e2e-run-2026-04-07-real.md`
- 예상 작업량: Pass 1 ≈ 3h, Pass 2 ≈ 2h, Pass 3 ≈ 4h (총 ~9h)
