# 현재 진행 상황

> 최종 갱신: 2026-04-22
> **MVP 운영 READY — Consumer 100/100, 완성도 80/100 (안정성 85 · 효율성 82 · 정확성 74)**
> 프로덕션: `marketscope.robitlabs.co.kr` 라이브 (외부 리버스 프록시 + SSE 스트리밍 정상)
> E2E 회귀: Ring 0~3 전체 그린 (Mock 39/39 · Real 24/24) + Ops OPS-01/02 + L1 Langfuse 7/7
> 관측성 L1: Langfuse trace wiring 완료 (graceful degrade · SSE `done.trace_id`)
> 다음 권장: Accuracy Gap Fix W1~W4 (정확성 74 → 85+). [Plan](../plan/fix/accuracy-gap-fix.md) · Phase 2 착수 전 선행 권장

---

## 전략

**Phase 1A(Mock E2E)** → **Phase 1B(Real Data + UX)** → **Phase 3(확장)** → **Phase 2(Premium)**

| Phase | 범위 | 상태 | 비고 |
|-------|------|------|------|
| 1A | Mock E2E, Card UI, Agent 전체 흐름 | ✅ 완료 | 5개 샘플 상권 |
| 1B | 공공데이터 ETL + 1,650 상권 적재 + 프로덕션 배포 | ✅ 완료 (2026-03-30) | |
| 3 | F06 히트맵 · F09 매출 시뮬레이션 · F10 PDF | ✅ 완료 (2026-04-06) | |
| 2 | OAuth2 · 결제 · Tier 게이팅 · F04 UI | ⏳ 미착수 | Accuracy Gap 선행 권장 |
| Prod | `marketscope.robitlabs.co.kr` 라이브 | ✅ 완료 (2026-04-16) | |

---

## 현재 실행 환경

| 서비스 | 포트 | 모드 |
|--------|-----:|------|
| Next.js 프론트엔드 | 3000 | Real (USE_MOCK=false) |
| FastAPI 백엔드 | 8002 | Real |
| PostGIS (Docker) | 5432 | 1,650 상권 폴리곤 적재 완료 |
| Redis (Docker) | 6379 | 정상 |

| LLM 설정 | 값 |
|----------|-----|
| LLM_PROVIDER | **anthropic** (Claude Sonnet 4) |
| Planner / Respond | Claude Sonnet 4 (TTFT 1.5s) |
| Evaluator | Gemini 2.5 Flash |
| Fallback | gemini-2.5-pro / flash |
| Agent 모드 | PAE (planner-actor-evaluator, max 3 rounds) |
| 관측성 | Langfuse L1 (trace wiring, graceful degrade) |

---

## 현재 서비스 지표

- Mock 상권 5개 (강남역/홍대/건대/명동/서울역) · Real 상권 1,650개
- ETL 적재 (2025Q4): floating_pop 9,888 / estimated_sales 21,333 / stores 75,985 / resident 39,288
- Agent Tool 11종 · Card 타입 5종 · SSE 이벤트 9종
- E2E: 45 시나리오 + 회귀 15 시나리오

---

## 최근 완료 (2026-04-22) — E2E + Ops 회귀 READY + 완성도 평가

### E2E + Ops 회귀 (2차 재실행으로 완전 회복)

**Plan**: `docs/plan/infra/e2e-ops-2026-04-22.md` + `docs/plan/infra/e2e-ops-followup-2026-04-22.md`
**Run**: `docs/qa/runs/e2e-run-2026-04-22.md`

1차 run 에서 47 PASS / 2 FAIL (stale container) / 10 SKIP (e2e stack 빌드 pip SSL 실패). 2차 재실행에서:

- **조치 1** — `server/Dockerfile` pip SSL 우회 build-arg (`PIP_INDEX_URL` / `PIP_TRUSTED_HOST`) + `/etc/pip.conf` 렌더. 기본값 HTTPS 유지로 기존 동작 무변화.
- **조치 2** — dev stack backend 재빌드. 이미지 `2026-04-17 11:02` → **`2026-04-22 11:26`**. `ff9909c` / `3c5f884` 반영. Ring 1 F03 4/4 + F05 5/5 = 9/9 PASS (stale FAIL 회복).
- **조치 3** — E2E 전용 stack (`docker-compose.e2e.yml`) 가동. Windows excluded range 회피로 db 15432 / redis 16379 재할당. ring0 4/4 + ops-endpoints 2/2 + l1-langfuse **7/7** + reg-2026-04-17 **6/6** 전체 PASS.

**신규 OPS 커버리지** (`frontend/e2e/ring3-negative/ops-endpoints.spec.ts`):
- OPS-01: `/api/health/detail` 11 필수 필드 스키마 (db_pool_* 4 + redis_connected + agent_mode + llm_provider + use_mock + semaphore_* 2 + active_sessions)
- OPS-02: `/metrics` 구조 + warm-up 기록

**최종 Consumer-experience**: **100/100 (READY)**

**memory 신규 2건**:
- `feedback_stale_container_vs_source.md` — E2E FAIL 분류 시 컨테이너 빌드 시각부터 확인
- `feedback_probe_endpoint_shape_first.md` — 스키마 spec 작성 전 실제 응답 probe

### 프로젝트 완성도 평가

| 축 | 점수 | 판정 |
|---|---:|------|
| 안정성 | **85** | 프로덕션 운영 가능 |
| 효율성 | **82** | 비용/레이턴시 양호, 관측성 L2+ 보강 필요 |
| 정확성 | **74** | 주요 시나리오 합격, edge 매핑 + follow-up 약점 |

**안정성 강점**: Circuit Breaker 3-state · Singleflight · SSE heartbeat/stall · slowapi · structlog · LLM 401 세션 플래그 · Redis/Langfuse graceful degrade · SSE 큐 백프레셔 256 · client disconnect 감지 · ETL 매출 단위 verify.
**안정성 약점**: 세션 인메모리 (재시작 시 유실) · `store_history` 실데이터 부재 · backend pytest 부재 · stale container regression 가능성.

**효율성 강점**: Rule-first Planner 50+ 패턴 (Greeting `<1s`) · Evaluator Fast path · History 300자 truncation · Role-based LLM (Respond=Sonnet4 / 기타=flash) — TTFT 25s→1.5s · 이중 캐시 · DB pool 10+20/pre_ping · asyncpg batch 1000 · React.memo 7개 + dynamic import · viewport throttle · Actor DAG `asyncio.gather`.
**효율성 약점**: Langfuse L2+ 미구현 (토큰/비용 측정 불가) · Heatmap preload 24 슬롯 singleflight 미통합.

**정확성 강점**: 2026-04-13 eval S1 9.8 · S2 9.6 · S8 9.7 · 3단 해석법 + 벤치마크 p25/p50/p75 · 할루시네이션 방지 + prompt sanitize · 매출 단위 월 환산 · 한글 조사 strip · multi-district extract · 출처 citation.
**정확성 약점 — 6개 GAP**:

| ID | 상황 | 근본 원인 | 체감 빈도 |
|----|------|----------|:--------:|
| GAP-A | `"홍대 vs 성수"` 1개만 추출 | `_candidate_words` 3글자 이상 제한 | 높음 |
| GAP-B | `"브런치 가게 매출?"` → 재질문 | `category_metadata.aliases` 시드 100건만 적재 | 중간 |
| GAP-C | `"홍대 말고 성수로 비교"` 도치 오추출 | Planner 2-pass 재분석 없음 | 낮음 |
| GAP-D | Tool 실패 시 일반 지식 응답 | Respond 가드레일 후처리 미흡 | 높음 |
| GAP-E | `"거기 중에 2030 높은 데?"` 지시어 해석 실패 | `cards[].data` 참조 X | 높음 |
| GAP-F | `"방금 그 비교 PDF"` → 전체 PDF | F10 messages 스냅샷 방식, 선택형 미지원 | 낮음 |

**해결 로드맵 — [Accuracy Gap Fix Plan](../plan/fix/accuracy-gap-fix.md)**:

| 주 | 대상 GAP | 카테고리 | 대표 사례 |
|----|---------|---------|----------|
| W1 | A, D | Entity Linking + Abstention | Kakao Map · HALT-RAG · pg_trgm 3-stage |
| W2 | C, E | Conversational Query Rewriting | Perplexity · InfoCQR · CHIQ |
| W3 | B | Taxonomy Alias Expansion | Amazon · TaxoAdapt · `learned_aliases` 테이블 |
| W4 | F | Card-level Export UX | Notion AI · Perplexity |

**KPI**: 정확성 74 → 85+ / S3 2.6 → 9.0+ / S6 6.1 → 9.0+ / GAP-A 60% → 95%+ / GAP-D 할루시 15% → <3%

---

## 이력 요약 (최근 → 과거)

### 2026-04-21

- **E2E 회귀 Pass 1~3 전체 그린** — Mock 39/39 + Real 24/24. 잔여 FAIL 4건 핫픽스: `/_proxy/` → `/proxy/` rename (Next.js private folder 규칙) · F03-H4 `monthlySales` top-level key · F05-H3/H4 compareList 자동 동기화 · Real `detect_districts_in_message` 2→3글자 제한. 커밋 `3c5f884` / `1986f61` / `ded6cb1` / `ff9909c`.
- **LLMOps L1 Langfuse trace wiring** — `services/langfuse_tracer.py` (salted sha256 session hash, `_tracer_valid` 세션 플래그, graceful degrade) + `graph.py` callbacks 주입 + SSE `done.trace_id` optional + E2E spec `l1-langfuse.spec.ts` 7 test. Plan `llmops-l1-adr-hosting.md` (Langfuse Cloud + SDK `>=2.0,<3.0` 핀).

### 2026-04-19 — v0.3.0 + E2E 회귀 인프라

- 문서 계층화 + 실구현 동기화 (F02 ReAct→PAE / Tool 8→11)
- `docker-compose.e2e.yml` + `env.e2e.example` + `prodGuard` helper + preflight/teardown 스크립트 + 회귀 spec 4종 (F01-H5 kakao-sdk / F03-H4 / F05-H3/H4 / reg-2026-04-17 6-scenario)

### 2026-04-17 — Plan A 매출 단위 + Plan B 배포 근본해결

- **Plan A**: `_enrich_sales` 키 치환 3곳 (`sales` → `monthly_sales`) · `scripts/flush_cache.py` 신설 · `scripts/verify_sales_units.py` 신설
- **Plan B P0~P2 7건**: `alembic_version` cleanup migrate 전 이동 · seed dump 에서 `alembic_version` 제외 · `/api/kakao-sdk` → `/_proxy/kakao-sdk` 네임스페이스 · 외부 nginx 샘플 문서 · `.env.example` 보강 + Dockerfile 가드 · DB/Redis 외부 포트 제거 · `scripts/validate_env.py` 신설
- **비교모드 다색 하이라이트**: `DistrictLayer.tsx` compareList 슬롯 기반 3색 (blue/amber/rose)

### 2026-04-16 — 프로덕션 배포 (marketscope.robitlabs.co.kr)

- 외부 호스트 nginx + Let's Encrypt · `docker-compose.prod.yml` · LLM_PROVIDER=gemini · USE_MOCK=false
- 현장 대응 6건: alembic_version 공존 · 포트 80 충돌 · `/api/api/chat` 404 · SSE 무한로딩 (proxy_buffering) · 지도 미표시 (`/api/kakao-sdk` 404) · env 빌드타임 누락
- 커밋 `5466538`

### 2026-04-14 — 서빙 안정성 Phase 1~10

- 체크리스트 24% → 61% (148/243). 신규 14파일 + 수정 25파일
- Docker 하드닝 · DB/Redis 커넥션 풀 · 미들웨어 (slowapi/request-id/structlog/보안헤더) · SSE heartbeat + stall 감지 · Circuit Breaker + tenacity · 세션 상한 · Frontend React.memo + dynamic import · GitHub Actions + `/metrics` · Nginx + DR 문서

### 2026-04-13 — 분석 품질 Phase 1~3 + SSE 최적화

- **Phase 1 Respond 프롬프트**: 3단 해석법 + 할루시네이션 방지 + few-shot + `_compute_hints()` (6 tool 파생 지표)
- **Phase 2 Tool 보강**: `_enrich_sales/summary/comparison/recommendations/history` winners/insights/risk_flag/saturation
- **Phase 3 벤치마킹**: `benchmarks.py` + `BenchmarkRepository` + mock/real stub · percentile ranking
- **SSE 최적화**: LLM Gemini preview → Claude Sonnet 4. TTFT 25s → 1.5s (17배 개선). Respond 노드 시작 시 thinking 이벤트 emit + `_anthropic_valid` 세션 플래그 + `.env` 키 갱신
- E2E eval: S1 9.8 / S2 9.6 / S8 9.7 PASS. S3 2.6 / S6 6.1 (Agent 파이프라인 이슈, Accuracy Gap 로 이관)

### 2026-04-08 — F05-H1 fix + Real mode E2E

- `detect_districts_in_message` protocol 신설 (multi-extract, max 5) + Planner comparison multi-extract 호출
- Real mode 45 시나리오 41 PASS / 4 design-skip / **Consumer 100/100 READY**
- 부수 버그 8건 (heatmap 컬럼명 · simulate_revenue category optional · ring0 bounds 형식 · J01 Real UI 플레이크 등)

### 2026-04-07 — E2E QA Run (Mock, 42 시나리오, 94/100)

- 4-ring 전략 helper 구축 (~270 LOC) + 22 spec 파일
- Fresh subagent 평가 4 batches parallel. 35 PASS → React duplicate-key 버그 fix 후 회복
- P0 회귀 6/8 PASS (P0-1 Real-only SKIP / P0-2 env-override SKIP)
- F05-H1 Korean particles 이슈 SOFT FAIL (2026-04-08 에서 해소)

### 2026-04-06 — P0 8건 수정 + E2E QA plan + Phase 3

- **P0 수정 커밋 `d8c0155`**: (1) category_metadata aliases migration · (2) LLM timeout 15s/60s · (3) SSE 큐 백프레셔 256 · (4) client disconnect 감지 · (5) JSON parse 실패 rule fallback · (6) DistrictLayer stale closure · (7) frontend AbortController · (8) prompt sanitize
- **Phase 3 완료**: F09 simulate_revenue + SimulationCard · F06 HeatmapLayer + TimeSlider · F10 PDF (@react-pdf/renderer + html2canvas + Spoqa 폰트)
- **E2E QA plan** (`docs/qa/e2e-qa-test-plan.md` ~500 lines, 10 섹션, M01+F01~F10, 5 journey, 15 failure mode)
- **하드코딩 개선 5건**: Mock JSON 분리 · intents YAML · CategoryResolver 동적 로딩 · `@register_tool` 자동 등록 · SSE label backend 전달
- 지도 폴리곤 CORS 버그 수정 (silent catch → console.warn)

### 2026-04-05 — Docker 통합

- `docker compose up` 원커맨드: db → redis → migrate → seed → backend → frontend
- Multi-stage Dockerfile + `next.config.mjs` standalone + `--profile dev` hot-reload

### 2026-04-04 — QA P0+P1 수정 (8건)

- 종합 QA 194개 테스트 Grade C → B+ 목표 (134/194 → 180/194)
- 3개 Tool 크래시 fix (compare/recommend/risk) · 프롬프트 인젝션 방어 · Frontend 404 rewrite · AGENT_MODE=pae · 인사 단축 + role-based Gemini · 상권 감지 우선순위 + stopword · Redis fallback · asyncio.Lock + Semaphore(20)

### 2026-04-03 — PAE Agent 전환 + 리팩토링

- **PAE 그래프**: `create_react_agent` → Planner-Actor-Evaluator 커스텀. 9 신규 + 6 수정. `asyncio.Queue` 실시간 SSE · Planner 규칙 우선 · Evaluator Fast path · `agent_mode` 플래그 롤백 가능
- **Repository 패턴**: 12 파일 22곳 `if settings.use_mock` → `DataAccess` 파사드 + 7 Protocol + Mock/Real 팩토리. 25 신규 + 20 수정. `tsc --noEmit` 0 errors
- **Frontend 리팩토링**: `SSEEvent` discriminated union · sseParser · eventHandlers registry · chatStore 351→139줄 · Card registry · Kakao Map 타입
- **데이터 출처 citation**: 4 Card footer + `data_sources.py` 레지스트리

### 2026-04-02 — DB 셋업 자동화

- `setup_db.py --quick/--full/--reset` · `generate_seed.py` · Git LFS 시드 덤프 4.9MB · `csv_collector.py` OA-15584 로더

### 2026-04-01 — Playwright MCP E2E + SHP 폴리곤 + Real 모드 전환

- 26 시나리오 22 PASS / 4 SOFT FAIL
- OA-15560 SHP → PostGIS 1,650 boundary/center_point 100%
- Real 모드 차단 2건 수정 (시스템 프롬프트 Mock 코드 제거 · chat.py Real 모드 이름→코드 조회)
- floating_population 컬럼명 버그 (`TMZON_00_06_FLPOP_CO`) 수정 + 재적재

### 2026-03-30 ~ 03-31 — Phase 1B 완료

- Agent Progress Indicator (🧠→🔍→📊→✅) + tool_end SSE + icon
- SSE 버퍼링 해결 (Next.js rewrite → 직접 백엔드 호출)
- 다크 테마 (CSS 변수 12종 + bot-bubble + 마크다운 + 스트리밍 커서)
- Card UI 4종 다크 테마 + `.gitignore` 정리
- E2E 32/32 PASS
- ETL 적재 완료 (API 키 발급 + VwsmTrdarFlpopQq/SelngQq/StorQq/WrcPopltnQq + CSV OA-15584)

---

## Next Items (우선순위 순)

### 🟠 Accuracy Gap Fix — Phase 2 착수 전 선행 권장

**Plan**: [docs/plan/fix/accuracy-gap-fix.md](../plan/fix/accuracy-gap-fix.md)

| 주 | 대상 GAP | 기술 카테고리 | 참고 사례 |
|----|---------|-------------|----------|
| W1 | A, D | Entity Linking + Abstention | Kakao Map · Google "abstention paradox" · HALT-RAG |
| W2 | C, E | Conversational Query Rewriting | Perplexity · InfoCQR · CHIQ · SEAL |
| W3 | B | Taxonomy Alias Expansion | Amazon · TaxoAdapt · TELEClass |
| W4 | F | Card-level Export UX | Notion AI · Perplexity |

**근거**: 2026-04-13 eval S3(2.6) · S6(6.1) · S7(8.9) 미달. 종합 정확성 74 → 85+.

### 🟡 관측성 L2+

- Langfuse L2+ (토큰/비용 측정, prompt version, eval harness)
- Heatmap preload singleflight 통합
- backend pytest 인프라

### 🟡 Phase 2 — Premium (미착수)

- OAuth2 인증 + 결제 연동 (Toss Payments / PortOne)
- Tier 게이팅 미들웨어 (Free 일 5회 제한)
- F04 업종 심층 UI (Tool 은 이미 구현)
- category_aliases 퍼지 검색 (pg_trgm)

### 🟢 장기 / 후순위

- 세션 저장소 Redis/Postgres 이관 (재시작 시 유실 제거)
- `store_history` 대안 데이터셋 탐색 (공공 API 미제공)
- frontend/server Docker 이미지 최적화

---

## 참고 문서

| 영역 | 경로 |
|------|------|
| 종합 QA (Grade C 194 테스트) | `docs/qa/qa-summary-report.md` · `qa-detailed-results.md` · `qa-improvements.md` |
| E2E run 로그 | `docs/qa/runs/e2e-run-2026-04-22.md` · `e2e-run-2026-04-19.md` · `e2e-run-2026-04-07.md` · `e2e-run-2026-04-07-real.md` |
| 분석 품질 eval | `docs/qa/analysis-quality-eval-2026-04-13.md` |
| Accuracy Gap Fix | `docs/plan/fix/accuracy-gap-fix.md` |
| 서빙 안정성 체크리스트 | `docs/spec/serving-stability-checklist.md` |
| 아키텍처 overview | `docs/architecture/overview.md` (backend/frontend/agent/data/deployment) |
| 기능 목록 | `docs/spec/feature-list.md` · `features/F01~F10-*.md` |
| LLMOps L1 | `docs/plan/infra/llmops-l1-adr-hosting.md` · `llmops-l1-e2e.md` |
| E2E 회귀 인프라 | `docs/plan/infra/e2e-regression-plan-2026-04-19.md` · `e2e-ops-2026-04-22.md` · `e2e-ops-followup-2026-04-22.md` |

> 2026-04-21 이전 상세 일일 기록은 git history (`git log --follow docs/status/current-status.md`) 로 복원 가능.
