# 현재 진행 상황

> 최종 갱신: 2026-07-04
> 상세 이력은 git history (`git log --follow docs/status/current-status.md`) + `docs/qa/runs/` + `docs/plan/` 로 복원.

---

## 최근 작업 (2026-07-04)

### v2 프로덕션 배포 완료 ⭐ — Eval R4 GATE PASS 4/4 → prod DB 복구 → 컷오버/스모크 전항목 PASS
- **Plan**: [prod-deploy-2026-07-04](../plan/infra/prod-deploy-2026-07-04.md) · **Verdict**: [eval-round4-2026-07-04/_verdict.md](../qa/runs/eval-round4-2026-07-04/_verdict.md)
- **Trust Kernel P1/P2 근본원인 5건(RC1~RC5) fix**: fact_pool `#N` 접미키 매칭 · `_COMPOUND_RE` "3억 5,000만원" 오파싱 · truncate본↔ToolMessage 불일치 · still-unbound 전체대체 과잉방어(`should_fallback` ≥3 AND ≥50% + `mask_unbound` "[미확인]" + 카드 존재 시 abstention 금지) · 원화 floor 미만 스케일 오기(`find_scale_mismatches`). 신규 `test_trust_kernel_regressions.py` 19케이스, pytest 187 passed.
- **Eval R4**: S2 3.3→10.0 · S4 3.3→10.0 · S8 9.2→10.0, 평균 10.0, 날조 0/8 → GATE PASS 4/4.
- **prod DB 복구**: data-only 단일 트랜잭션(TRUNCATE→COPY→setval), worker_sum 4,724,265 · catmeta 100 · unit_price NULL 0 · aliases 32. 스모크: 외부도메인 200×5 · SSE 3건(직장인구 87,191=DB · 카페→CS100010 시뮬 3,864만=GT) · Anthropic 401/404 0건(2개월 Gemini fallback 해소).

### Deferred 백로그 처리 — daily_avg→quarter_total rename + recommend score 밴드 정규화
- **Plan**: [deferred-backlog-2026-07-04](../plan/fix/deferred-backlog-2026-07-04.md)
- **Item 1** `daily_avg`→`quarter_total` rename: '일평균' 라벨·분할 날조 근원(06-26 S7 물리모순) 근본 정정. 백엔드 10파일 + 프론트 2파일(types.ts `quarterTotal` + `dailyAvg?` deprecated fallback) + 테스트 3건. trust/numeric_sanity 매처는 신규 키 + 구 키 legacy 유지 → **배포 시 `flush_cache.py` 필수**.
- **Item 2** recommend score: min-max 0~100(1위 항상 100.0 고정 오독) → `_band_scores` 순수함수(55~95 유계 밴드, 동점/단일=75.0). mock recommendations.json 재스케일, 회귀 3케이스.
- **Item 3** 스트리밍 재설계 — **설계만, 착수 보류** (eval-gated). 토큰 스트리밍 ↔ Trust Kernel 검증-후-방출 충돌. 옵션 B(astream 버퍼링) 권고.
- **검증**: pytest 190 passed/6 skip · ruff PASS · tsc 0 error.

### 자동배포 파이프라인 Pass 1+2 (C1~C10) 🆕 — auto_deploy.sh + systemd timer 폴링
- **Plan**: [auto-deploy-on-push](../plan/infra/auto-deploy-on-push.md)
- origin/main push 를 2분 폴링 감지 → CI green 게이트 → prev-auto 재태그 → ff merge → 빌드 → healthy 대기 → flush_cache → smoke 4항목 → 실패 시 prev-auto 자동 롤백.
- 신규 4파일: `scripts/deploy/auto_deploy.sh`(flock·`--ff-only`·ERR trap 롤백·`last-deploy.json`) · `install_autodeploy.sh` · systemd `marketscope-autodeploy.{service,timer}`(`TimeoutStartSec=1800`). 안전설계: 본 서버=작업세션 겸용이라 **reset 금지**, 호스트 env 오염 방어.
- **Pass 2 (C9/C10) 완료** — timer 설치 후 라이브 리허설로 결함 3건 발견·즉시 fix: ① 서버발 커밋 no-op 기준 `.last-deployed-sha` 교체(`3fc7d9a`) ② freshness 마커 false-positive → server/·frontend/ diff push 만 검사(`e1d28e4`) ③ 롤백 후 frontend cold-start 가짜 ROLLBACK_FAILED → `wait_frontend`(90s)(`1f5d19b`). C9 자동배포 3회 연속 SUCCESS(4.5분→23초 캐시), C10 smoke 실패 주입 → prev-auto 복귀 ROLLED_BACK 무중단, BLOCKED_DIRTY 2회 검증.
- **다음**: Pass 3 — 2분 폴링 24h 관찰(no-op 부하·API rate) · 수동 배포 세션 전 timer disable 관례.

---

## 현재 실행 환경

| 서비스 | 포트 | 모드 |
|--------|-----:|------|
| Next.js 프론트엔드 | 3000 | Real (USE_MOCK=false) |
| FastAPI 백엔드 | 8000 | Real |
| PostGIS (Docker) | 5432 | 1,650 상권 폴리곤 적재 완료 |
| Redis (Docker) | 6379 | 정상 |

| LLM 설정 | 값 |
|----------|-----|
| LLM_PROVIDER | **anthropic** (claude-sonnet-4-6) |
| Loop | Claude Sonnet (function-calling), fallback gemini-2.5-pro/flash |
| Agent 모드 | **v2 agentic loop + Trust Kernel** (`AGENT_LOOP_VERSION=v2`, 롤백 스위치=pae) |
| 관측성 | Langfuse L1 (trace wiring, graceful degrade) |

---

## 현재 서비스 지표

- Mock 상권 5개 · Real 상권 1,650개
- ETL 적재 (2025Q4): floating_pop 9,888 / estimated_sales 21,333 / stores 75,985 / resident 39,288 / worker total 4,724,265
- Agent Tool 9종 · Card 타입 5종(summary/risk/compare/recommend/simulation)
- SSE 이벤트: v2 루프 7종(thinking/tool/tool_end/card/text/suggestion/done) + `map_cmd`/greeting 단축은 chat.py, PAE(legacy) 경로는 plan/warning 추가 · 프론트 SSEEvent 유니온 10종(`error` 포함)
- Backend pytest: 테스트 모듈 22 · 최근 실측 2026-07-04 **190 passed / 6 skipped**(`@pytest.mark.real` DB 통합 6)
- E2E(Playwright): spec 44파일 · ring0~3 + prod-smoke. 최근 실측 2026-07-02 Mock 131 passed / 25 failed(loop 무관 사전결함) / 8 skip

> 완성도 평가(2026-04-22 스냅샷 안정성85/효율82/정확74)는 이후 해소: backend pytest·Langfuse L2·Heatmap singleflight = 2026-05-07 완료, 정확성 = Eval Round 4(평균 10.0, GATE PASS 4/4, 2026-07-04) 재측정 완료.

---

## Next Items (우선순위 순)

### 🟠 자동배포 파이프라인 Pass 3 (24h 관찰)
**Plan**: [auto-deploy-on-push.md](../plan/infra/auto-deploy-on-push.md)
- C9/C10 완료(자동배포 3회 SUCCESS · 롤백 무중단 검증) → Pass 3 잔여: 2분 폴링 24h 관찰(no-op 부하·API rate) · 수동 배포 세션 전 timer disable 관례화

### 🟡 스트리밍 재설계 (eval-gated, 설계만 완료)
**Plan**: [deferred-backlog-2026-07-04.md](../plan/fix/deferred-backlog-2026-07-04.md) Item 3
- v2 루프는 검증-후-방출(비스트리밍). 옵션 B(astream 버퍼링 + 진행 세분화) 권고안 기록됨
- 착수 게이트: eval 스택 가용 + S1~S8 평균 ≥9.0 · 날조 0 재판정

### 🟡 Refactoring Phase 1 Pass 2 — 잔여분
**Plan**: [phase1-low-mid-risk-2026-04-23.md](../plan/infra/phase1-low-mid-risk-2026-04-23.md)
- ✅ `api/errors.py` 래퍼 · ✅ `respond.py`→`agent/utils/formatting.py` 분할
- 🔧 `agent/nodes/respond.py` 재증식(575 LOC) · `stores/chatStore.ts`(455 LOC) slices 분할 미착수 · `except Exception` 좁히기

### 🟡 관측성 L2 잔여
- Langfuse L2 Foundation 구현 완료(2026-05-07) — **노드 wiring(planner/evaluator/respond) + L2-C eval harness 미착수** (Plan [langfuse-l2-token-cost-eval.md](../plan/infra/langfuse-l2-token-cost-eval.md) Pass 2/3)

### 🟡 Phase 2 — Premium (미착수)
- OAuth2 + 결제(Toss/PortOne) · Tier 게이팅 미들웨어(Free 일 5회) · F04 업종 심층 UI · category_aliases 퍼지 검색(pg_trgm)

### 🟢 장기 / 후순위
- 세션 저장소 Redis/Postgres 이관 · `store_history` 대안 데이터셋 · Docker 이미지 최적화

---

## 이력 요약

> 상세는 각 Plan / `docs/qa/runs/` / git history 참조.

| 날짜 | 주요 내용 |
|------|----------|
| 2026-07-03 | Accuracy Eval Round 3(v2 Real) GATE FAIL 2/4(평균 8.2) → P1 Trust Kernel fallback 붕괴 + P2 S8 스케일 오기 발견(07-04 R4 에서 해소). v2→main 머지 완료(결과 트리 = v2 tip byte-동일). |
| 2026-07-02 | /qa v2 Real 최초 품질검증 — 날조 0/10 GT 전수일치, 건강도 90→99, HIGH 2 fix(trust 교정턴 메타발화 가드 · simulate category resolve). v2 E2E 마무리 — S9-5 fix + PAE baseline로 v2 회귀 0 실증(근본원인=compose env 오설정). |
| 2026-06-26 | S7 coref 수치 날조 fix Pass 3(tool 5/5·날조 0/5) + 죽은 모델 ID `claude-sonnet-4-20250514`→`claude-sonnet-4-6`. [Plan](../plan/fix/s7-coref-toolless-fabrication.md) |
| 2026-06-25 | 데이터 신뢰성 — 적재 결손 3건(worker 전량0·unit_price NULL·aliases NULL) 근본수정 + 컬럼내용 검증 게이트 + 적대검증 워크플로우(11 finding). [Plan](../plan/fix/data-reliability-2026-06-25.md) |
| 2026-06-10 | Accuracy Eval Round 2 평균 8.0→9.4 + ISSUE-003 라이브 검증 + S7 coref P1 발견. [Verdict](../qa/runs/eval-round2-2026-06-10/_verdict.md) |
| 2026-06-09 | P0 백로그 — recommend 저점포수 floor(`_apply_store_floor` MIN_RELIABLE_STORES=3) + Hero H1 break-keep. [Plan](../plan/fix/p0-backlog-2026-06-09.md) |
| 2026-06-08 | QA 풀앱 패스 건강도 98→99 — out_of_scope/greeting 중복 suggestion fix(`graph.py`). |
| 2026-05-07 | 4 Plan Pass 1 — Heatmap singleflight 재도입 + backend pytest 확장(35 신규) + W1 boost 측정(baseline 96.9%) + Langfuse L2 Foundation. |
| 2026-04-30 | UX Sweep Phase A-F Pass 1 — 13 신규 e2e + 통합 5 journey(j06). [Plan](../plan/qa/ux-phase-a-f-test-plan.md) |
| 2026-04-29 | Out-of-Scope(서울 외) 거부 3중 가드 — out_of_scope intent + STRONG_TOP1_MIN(0.70) + prompt rule. [Plan](../plan/fix/out-of-scope-handling-2026-04-29.md) |
| 2026-04-28 | Prod 재배포(district-click-race fix) · Tool 함수명 노출 fix(alembic 005 + Langfuse 11차원/6스코어 + `_ToolTagSanitizer`) · Langfuse 통계 집계 Phase 1+2. |
| 2026-04-27 | P0 우선순위 6건 — W1 entity_matching boost · RESPOND XML leak `_XMLTagSanitizer` · Planner empty-plan clarification · Eval drift guard. [Plan](../plan/fix/p0-priority-2026-04-27.md) |
| 2026-04-24 | User-Journey Sweep(Pass3 99.1%) · Data Trust `numeric_sanity` · E2E 품질 Sweep 107 · Refactoring Pass1+2 · Langfuse 비용 커버리지 fix(SDK v2→v3). |
| 2026-04-23 | F-01 ETL fix(21,333 행 재적재) + Accuracy Gap W1/W2/W3(entity_matching/abstention/rewriter + learned_aliases 004) · LLMOps L1 v3 포팅 · v0.4.0 재배포(라우트 `/` `/app` 분리). |
| 2026-04-21~22 | E2E 회귀 Pass 1~3 그린(Mock 39 + Real 24) · LLMOps L1 trace wiring · 완성도 평가 85/82/74. |
| 2026-04-16~19 | **프로덕션 런치**(marketscope.robitlabs.co.kr) — 외부 nginx + LE · `docker-compose.prod.yml` · 문서 계층화 · 매출 단위 fix. |
| 2026-04-13~14 | 분석 품질 Phase 1~3(3단 해석법) · SSE TTFT 25s→1.5s · 서빙 안정성 Phase 1~10(Circuit Breaker · `/metrics` · DR). |
| 2026-04-03~08 | PAE Agent 전환 · Repository 패턴 · Phase 3 완료(F06/F09/F10) · Docker 통합 · QA P0 다수. |
| 2026-03-30~04-02 | **Phase 1B 완료** — SHP→PostGIS 1,650 적재 · Real 모드 전환 · DB 셋업 자동화 · ETL 적재 · E2E 32/32. |

---

## 참고 문서

| 영역 | 경로 |
|------|------|
| 종합 QA | `docs/qa/README.md` · `docs/qa/test-plan.md` · 최근 로그 `docs/qa/runs/` |
| 분석 품질 eval | `docs/qa/runs/eval-round4-2026-07-04/` (최신 — GATE PASS 4/4) · `eval-round3-2026-07-03/` · `eval-round2-2026-06-10/` |
| 아키텍처 | `docs/architecture/overview.md` (backend/frontend/agent/data/deployment) |
| 기능 목록 | `docs/spec/feature-list.md` · `features/F01~F13-*.md` |
| 배포/운영 | `docs/ops/` (runbook · disaster-recovery · production-deployment) |
