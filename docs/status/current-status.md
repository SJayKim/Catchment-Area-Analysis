# 현재 진행 상황

> 최종 갱신: 2026-07-16
> 상세 이력은 git history (`git log --follow docs/status/current-status.md`) + 활성 `docs/plan/` 참조.

---

## 미결 / 블로커 (세션 진입 시 필독)

> **오케스트레이션 Plan (2026-07-16 신규)**: 아래 1~3 + LLM Gateway Pass 3(live)를 `A(서버 블로커 해소)→B(env 수동 적용)→C(로컬 live)→D(prod 카나리아+24h 관찰)` 실행 순서로 묶음 → [pass3-live-activation-2026-07-16.md](../plan/infra/pass3-live-activation-2026-07-16.md). 각 항목 세부는 기존 plan 인용(중복 서술 0).

1. **prod 자동배포 미발화 (push 는 완료)** — 07-07 11:11 push `origin/main=c98ea5d`(ops-hardening `d63a371`+docs 2 + E02/E03 재작성) + CI 5/5 green, 스트리밍 옵션 B `dc11186` 은 07-06 기push. 그러나 **CI green 후 28분간 prod 미반영** — health detail `langfuse` 블록 미등장 + 다운타임 블립 0 = 배포 시도 자체 없음(07-06 미발화와 동일 증상). prod 는 07-04 배포본에 머묾. 서버 진단: `systemctl status marketscope-autodeploy.timer` · `journalctl -u marketscope-autodeploy.service -n 100 --no-pager`(BLOCKED_DIRTY/CI 게이트/freshness 로그) · `cat last-deploy.json` · `git status --short`(서버 워킹트리 dirty 여부) → 해소 후 `bash scripts/deploy/auto_deploy.sh --force`. 롤백 스위치 `AGENT_LOOP_STREAM_FINAL=false`. **별건**: prod `redis_connected=false` 지속 관측 — Redis 컨테이너 상태 확인 필요. 🆕 07-16 docs-only 3커밋 push 로 `origin/main=e3ee692` — 이 tip 이 최신 발화 관찰 대상(소스 무변경이라 freshness 검사는 skip 가 정상).
2. **`.env`/`.env.dev` 수동 diff 미적용** — `TRACING_ENVIRONMENT=production` + `SESSION_SALT` + OTEL 주석. `protect_secrets.py` 훅이 Edit 차단 → 수동 적용 필요([langfuse-ops-hardening](../plan/infra/langfuse-ops-hardening-2026-07-06.md) §수동 적용 diff).
3. **auto-deploy Pass 3** — 2분 폴링 24h 관찰(no-op 부하·API rate) · 수동 배포 세션 전 timer disable 관례화([auto-deploy-on-push](../plan/infra/auto-deploy-on-push.md)).

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
| LLM_PROVIDER | **anthropic** (claude-sonnet-4-6), fallback gemini-2.5-pro/flash |
| Agent 모드 | **v2 agentic loop + Trust Kernel** (`AGENT_LOOP_VERSION=v2`, 롤백=pae) |
| 관측성 | Langfuse L1+L2 (v2 summary/score/tool-span wiring, graceful degrade) |

---

## 현재 서비스 지표

- Mock 상권 5개 · Real 상권 1,650개 · ETL(2025Q4): floating_pop 9,888 / estimated_sales 21,333 / stores 75,985 / resident 39,288 / worker 4,724,265
- Agent Tool 9종 · Card 5종(summary/risk/compare/recommend/simulation) · SSE: v2 7종 + `map_cmd`/greeting(chat.py), PAE +plan/warning · 프론트 SSEEvent 10종
- Backend pytest: 모듈 30 · 최근 실측 2026-07-08 **241 passed / 6 deselected(@real)**(LLM gateway +16) · E2E spec 44파일 · test 선언 188개(ring0~3 + prod-smoke + 레거시, 2026-07-16 실측 — skip 포함)
- 정확도: **Eval R4 평균 10.0 · GATE PASS 4/4**(2026-07-04) → 스트리밍 옵션 B 재판정 fresh 10.0(2026-07-06). 완성도(2026-04-22 85/82/74)는 이후 전항목 해소.

---

## Next Items (우선순위 순)

### 🟡 LLM Gateway — OpenAI GPT 지원 Pass 3 (live 활성화 잔여)
[llm-gateway-openai-2026-07-08.md](../plan/infra/llm-gateway-openai-2026-07-08.md) — Pass 1+2(코드+ops/env/docs) 완료·main merge. **Pass 3(live) 미착수**: 실키 스모크 · 폴백 증명 · Langfuse `provider:openai` cost · PAE 경로 · prod 카나리아. 선행조건 = auto-deploy 발화 회복(미결 §1) + `.env`/`.env.dev` 실키 수동 적용(protect_secrets 훅 차단). **실행 순서**: [pass3-live-activation-2026-07-16.md](../plan/infra/pass3-live-activation-2026-07-16.md) Stage A~D.

### 🟡 Trust 퍼지 톨러런스 충돌 follow-up
[eval-stream-b-2026-07-06/_verdict.md](../qa/runs/eval-stream-b-2026-07-06/_verdict.md) §관찰-1 — "543억"↔총매출 532억(2.07%) ±5% 충돌로 오도출 통과. 큰 자릿수 원화 상대+절대 이중 게이트 or 성별/비율 라벨 바인딩 검토.

### 🟡 Refactoring Phase 1 Pass 2 잔여
[phase1-low-mid-risk-2026-04-23.md](../plan/infra/phase1-low-mid-risk-2026-04-23.md) — `respond.py` 재증식(575 LOC) · `chatStore.ts`(455 LOC) slices 분할 · `except Exception` 좁히기 미착수.

### 🟡 관측성 L2 잔여
[langfuse-l2-token-cost-eval.md](../plan/infra/langfuse-l2-token-cost-eval.md) Pass 2/3 — PAE 노드 generation span + L2-C eval harness · ops-hardening Pass 3(live smoke·eval opt-in·score-config 등록).

### 🟡 Phase 2 — Premium (미착수)
OAuth2 + 결제(Toss/PortOne) · Tier 게이팅(Free 일 5회) · F04 업종 심층 UI · category_aliases 퍼지 검색(pg_trgm).

### 🟢 장기
세션 저장소 Redis/Postgres 이관 · `store_history` 대안 데이터셋 · Docker 이미지 최적화.

---

## 이력 요약

> 상세는 활성 `docs/plan/` · git history · `docs/qa/runs/{eval-round4-2026-07-04, eval-stream-b-2026-07-06}` 참조.

| 날짜 | 주요 내용 |
|------|----------|
| 2026-07-16 | **Docs-코드 동기화 + Learning 전면 개정 + 07-관측 신설** — 07-05 이후 코드 4건(옵션 B·ops-hardening·E02/E03 v3·LLM Gateway) 문서 드리프트 전수 해소: architecture 6 + spec 2 + ops 2 + qa 2 + server/CLAUDE + .env.example(옵션 B 4종 표·prod compose passthrough 부재 명시·e2e 44파일·188선언·모듈 30/수집 247). learning 00~06+MAP 개정(옵션 B §6·openai 4단 체인·라인 재실측) + **07-관측-품질기록실 신설**(summary 19키·score 6종·무음사망 가시화). 완료 plan 2건(docs-diet·trust-fallback-redaction) 게이트 통과 삭제 — redaction 설계는 R4 mask_unbound 로 대체 반영 확인. docs-only. ✅ 3커밋(`00410e9`·`d1f8f76`·`e3ee692`) **origin/main push 완료** — CI green 예상(docs-only), auto-deploy 발화 여부는 미결 §1 관찰 대상. [docs-code-sync-2026-07-16.md](../plan/infra/docs-code-sync-2026-07-16.md) |
| 2026-07-16 | **Pass 3 Live 활성화 통합 오케스트레이션 Plan 신규** — 미결 3건(auto-deploy 미발화 · `.env`/`.env.dev` 수동 diff · auto-deploy Pass 3) + LLM Gateway Pass 3(live)를 `A(서버 블로커 해소)→B(env 적용)→C(로컬 live)→D(prod 카나리아+24h 관찰)` 단일 실행 사슬로 묶음. 세부는 기존 3개 plan(llm-gateway·auto-deploy·ops-hardening) 라인 앵커 인용(중복 0)·env diff 2블록만 재게시. docs-only·코드 변경 0. 블로커 자체 무변동(실행은 후속 세션). [pass3-live-activation-2026-07-16.md](../plan/infra/pass3-live-activation-2026-07-16.md) |
| 2026-07-09 | LLM Gateway 문서 sync 잔여분 — Pass 2 가 놓친 문서 3건(`deployment.md` env 표 · `quickstart.md` · `learning/ARCHITECTURE-MAP.md`) 코드 실값 대조 보강(`LLM_PROVIDER`+openai·모델 ID passthrough 4종·§7 health `llm_chain`·체인 openai(`gpt-5.4-mini`) 누락 교정). `6ab8b5a` → main push, docs-only behavior-neutral. Pass 3(live) 블로커 무변동. |
| 2026-07-08 | LLM Gateway OpenAI 지원 Pass 1+2 — `LLM_PROVIDER` 선호-우선 체인(v2) + openai 프로바이더(v2 loop + PAE) + PAE 모델 ID de-hardcode + health `llm_chain` + ops/env/compose/docs sync. pytest 241 green · ruff clean. `feat/llm-gateway-openai` → main merge(PR). Pass 3(live)는 auto-deploy 블로커 선행. |
| 2026-07-07 | Langfuse Ops Hardening Pass 2 — e2e 회귀 9 passed(R0-LF-AGG 4/4 · R3-LF-L1) + E02/E03 v3 의미론 재작성(l1-langfuse 7/7). `c98ea5d` 까지 push + CI green — **auto_deploy 미발화 재확인**(28분 미반영, 블로커 §1). |
| 2026-07-06 | v2 스트리밍 옵션 B(astream 버퍼링 + "응답 작성 중 n%" 진행 이벤트, Trust 의미론 무변경) → Eval GATE PASS 4/4 평균 10.0. + Langfuse ops-hardening Pass 1(v2 L2 wiring: summary 19키/score 6종/tool span + 무음사망 가시화). pytest 225. |
| 2026-07-04 | **v2 프로덕션 배포** — Eval R4 GATE PASS 4/4(평균 10.0·날조 0) + Trust Kernel RC1~RC5 fix + prod DB 복구(worker 4,724,265). Deferred 백로그(daily_avg→quarter_total rename·recommend 밴드) + 자동배포 파이프라인 Pass 1+2(auto_deploy.sh + systemd timer). |
| 2026-07-02~03 | Eval Round 3 GATE FAIL 2/4(평균 8.2, P1 fallback 붕괴·P2 S8 스케일 → R4 해소) · v2→main 머지 · /qa v2 Real 첫 검증(날조 0/10, 건강도 99). |
| 2026-06-25~26 | S7 coref 수치 날조 fix Pass 3(죽은 모델 ID `claude-sonnet-4-6` 교체) · 데이터 신뢰성 적재 결손 3건 근본수정 + 적대검증. |
| 2026-06-08~10 | Accuracy Eval Round 2 평균 8.0→9.4 · P0 백로그(recommend store floor) · out_of_scope/greeting suggestion fix. |
| 2026-05-07 | 4 Plan Pass 1 — Heatmap singleflight 재도입 + backend pytest 확장 + W1 boost + Langfuse L2 Foundation. |
| 2026-04-27~30 | UX Sweep Phase A-F Pass 1(13 e2e + j06) · Out-of-Scope 3중 가드 · Prod 재배포(district-click-race) · Tool 함수명 노출 fix · P0 우선순위 6건. |
| 2026-04-23~24 | F-01 ETL fix(21,333 재적재) + Accuracy Gap W1/W2/W3 · User-Journey Sweep(99.1%) · numeric_sanity · LLMOps L1 v3 포팅 · v0.4.0 재배포. |
| 2026-04-16~22 | **프로덕션 런치**(marketscope.robitlabs.co.kr) — 외부 nginx + LE · prod compose · 문서 계층화 · E2E 회귀 Pass 1~3 · LLMOps L1 wiring. |
| 2026-04-03~14 | PAE Agent 전환 · Repository 패턴 · Phase 3(F06/F09/F10) · Docker 통합 · 분석 품질 Phase 1~3 · SSE TTFT 25s→1.5s · 서빙 안정성 Phase 1~10(Circuit Breaker · /metrics · DR). |
| 2026-03-30~04-02 | **Phase 1B 완료** — SHP→PostGIS 1,650 적재 · Real 전환 · ETL · E2E 32/32. |

---

## 참고 문서

| 영역 | 경로 |
|------|------|
| 종합 QA | `docs/qa/README.md` · `docs/qa/test-plan.md` · 최근 로그 `docs/qa/runs/` |
| 분석 품질 eval | `eval-round4-2026-07-04/`(GATE PASS 4/4) · `eval-stream-b-2026-07-06/`(최신 스트리밍) |
| 아키텍처 | `docs/architecture/overview.md` (+ backend/frontend/agent/data/deployment) |
| 기능 목록 | `docs/spec/feature-list.md` · `features/F01~F13-*.md` |
| 배포/운영 | `docs/ops/` (runbook · disaster-recovery · production-deployment) |
