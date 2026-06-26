# 현재 진행 상황

> 최종 갱신: 2026-06-26
> **2026-06-26 S7 coref 수치 날조 fix — Pass 3 라이브 검증 완료 + 죽은 모델 ID fix** ⭐ — 복원 세션에서 잔여 P0(S7 coref, eval Round 2 8.9→5.0 회귀) 마무리. Plan [s7-coref-toolless-fabrication](../plan/fix/s7-coref-toolless-fabrication.md). **Pass 3**(R3-COREF-NUMERIC-01, USE_MOCK=false·1,650상권): `backend-dev` 프로필(`./server:/app` bind-mount + `--reload`)로 미커밋 소스 라이브 반영(기존 backend 이미지 `--no-build` 태그로 SSL 빌드 우회). "홍대랑 성수 비교"→"거기 중 유동인구 더 많은 곳?" 2턴 ×5: **tool 호출률 5/5**(get_floating_population 강제 발화)·정답(홍대 4.11M>성수 1.41M) 5/5·원 날조값(124,386/67,741) 0/5·물리 모순 0/5. S7 회귀 구조적 해소(9.3+ 목표 충족). **근본원인 2건 추가 처리**: (1) `graph.py:74/96` 하드코딩 모델 `claude-sonnet-4-20250514`가 현 키에서 404 은퇴 → anthropic respond 전량 실패 → `claude-sonnet-4-6` 교체(/v1/models 확인, 별건 인프라). (2) 1차 패스에서 respond가 `daily_avg`(실제 분기 시간대 합계인데 필드명이 daily_avg)를 ÷30/÷3로 '일평균' 날조 → 시간대 peak 초과 물리모순 3/5 → `respond.py` `FLOATING_POP_PRESENTATION_RULES` 가드(집계값 그대로 인용·일수 분할 금지·peak는 by_hour 실값만) 추가 → 2차 0/5. **검증**: ruff PASS, 어떤 테스트도 프롬프트·모델문자열 assert 안 함. pytest 재실행은 본 환경(호스트 앱deps 부재+컨테이너 pytest 부재) 불가 — planner.py+test_coref(16)는 prior세션 148 passed, 이번 변경 미접촉. **커밋 2건 main 직접**: `c62bb17`(S7 fix) + `654029a`(모델 fix). Verdict [s7-coref-pass3-2026-06-26/_verdict.md](../qa/runs/s7-coref-pass3-2026-06-26/_verdict.md).
> **2026-06-25 데이터 신뢰성 확보 — 적재 결손 3건 근본수정 + 컬럼내용 검증 게이트 + 적대검증 워크플로우** ⭐ — Plan [data-reliability-2026-06-25](../plan/fix/data-reliability-2026-06-25.md). 2026-06-25 정합성 감사가 surfaced 한 **3개월 잠복 적재결손 3건**(행은 존재하나 컬럼 전량 0/NULL → 기존 행수·FK·boundary 검증을 조용히 통과) 근본수정 + 재발차단. **RC1 worker 19,692행 전량0**: `transformers.py` worker 분기가 resident 접미사(`MAG_POPLTN_CO`) 재사용 → 실 API 키 `MAG_{n}_WRC_POPLTN_CO`/`FAG_{n}` 빌더 분리(live API 1행 dump 로 검증). 재적재 후 worker total_pop **472만**(was 0). **RC2 default_unit_price 100% NULL**: alembic 002 백필이 category 시드 전 실행돼 0행 no-op → `seed_category_metadata.py` INSERT 에 major 기준 객단가(외식12000/서비스25000/소매15000, 기본15000) + `simulation.py` 2차 폴백. NULL **0건**. **RC3 aliases 100% NULL**: source 부재 → `category_aliases.json` 핵심 **32종** 신규 + seed 결합. 32 set/68 NULL(의도). **RC0 게이트**: `runner.py::_validate_data` per-column NULL/all-zero(`bool_and`)/음수 sanity + **비-0 exit**, 행수 quarter-scope(빈 분기 FAIL). 주입 worker=0 → FAIL 재현. **검증**: pytest **132 passed/8 skip** + data-integrity 13(7 unit + 6 `@real`, gate FAIL-injection 포함). ruff PASS. 시드 덤프 재생성(5.6MB). **적대검증 워크플로우**(5 lens→finding별 회의적 검증·16 agent): 11 finding 전건 confirmed → **P1 3건**(alias '학원' 학원 subtype 오라우팅·빈분기 false-pass·게이트 무테스트) + **P2 3건** 즉시 수정, GATE-3(all-constant)·SEED-2(price/major decouple) 는 단일분기 설계·도달불가로 의도적 defer. 코드: `transformers.py`·`seed_category_metadata.py`·`category_aliases.json`(신규)·`simulation.py`·`runner.py`·`p1_api_vs_db.py`·`test_data_integrity.py`(신규)·`ci.yml`.
> **2026-06-21 학습용 ARCHITECTURE-MAP.md 신규 — Mermaid 도식 3종 + 코드 매핑** 🆕 — `docs/learning/ARCHITECTURE-MAP.md` 신규. `crypto_deep_research/docs/ARCHITECTURE-MAP.md` 포맷 차용(Mermaid 도식 + 폴더 책임표 + 설계↔코드 file:line 매핑). **도식 3종**: (1) 시스템 토폴로지 — 프론트(Next.js) ─REST+SSE─ 백엔드(FastAPI) ─Repository─ 데이터(PostGIS/Redis) 색상 경계, (2) 단일 요청 시퀀스 "강남역 알려줘" Plan→Act→Eval→Respond + SSE 9이벤트, (3) PAE 에이전트 내부 그래프(greeting/clarification 단락 포함). **매핑표**: 폴더별 책임(백/프론트 분리) · 4대 학습포인트(SSE/PAE/Repository/지도↔챗 동기화)↔코드 · 흐름노드↔file:line(actor.py:156·chatStore.ts:240·sseParser.ts:10 등 실 grep) · 도구 9종 · 주요 설계결정(월환산/서울밖 3중가드/저점포 floor) · F01~F13 기능↔코드 인덱스. 기존 서술형 코스(00~06) + `architecture/` 스펙과 양끝 링크 연결. 코드 변경 0(문서 only).
> **2026-06-10 Accuracy Eval Round 2 (Item 4) — ISSUE-003 fix 라이브 검증 + S7 coref 수치 날조 신규 P1** ⭐ — P0 백로그 Item 4 실행(003 fix `90937c6` 머지 후 게이트 해제). 스택: 기존 backend 컨테이너(`--reload` + `server` bind-mount)에 003 fix 이미 반영 확인 후 **clean re-import용 `docker compose restart backend`**(Windows/OneDrive bind-mount 파일워치 누락 방지), `USE_MOCK=false`·1,650 상권·`:8000` health 200. 수집: `OUT=docs/qa/runs/eval-round2-2026-06-10 BASE=:8000 run_accuracy_round2.sh`(message-only=entity-linking 검증, 04-24 baseline 보존). **결과 평균 8.0→9.4**(7/8 만점, 전 tool-backed 수치 DB일치). **ISSUE-003 라이브 재현 검증**: 성수동카페거리(편의점 1점포 @₩202M)·성수초등학교(1점포 @₩835M) 추천 #1에서 단일점포 편의점 **제외**(top-5 전부 store_count≥4), S4 건대 #1=편의점 store_count=8 — `_apply_store_floor` 의도대로. DB교차검증 강남1,396억/서울201억/홍대532억/성수221억/건대260억 전부 자릿수 일치. **신규 P1**: S7 coref 후속질문("거기 중 유동인구 더 많은 곳?")이 **tool 0건으로 유동인구 수치 날조**(124,386/67,741 — 카드 실값 411만/141만 무시, "일평균>시간대최고" 물리 모순). W1 abstention 가드가 tool-less 후속질문 수치주장 미포착(003 fix 무관, recommend 외 경로). S7 8.9→5.0 회귀. 권고: 수치 coref 후속질문은 tool 강제호출 or 카드값 인용 강제 + S7 재현율 측정. Verdict [eval-round2-2026-06-10/_verdict.md](../qa/runs/eval-round2-2026-06-10/_verdict.md).
> **2026-06-09 P0 백로그 — ISSUE-003 recommend 저점포수 랭킹 fix + ISSUE-002 Hero H1 줄바꿈 fix** ⭐ — 2026-06-08 QA 디퍼 2건 + 워킹트리 처리. **ISSUE-003 (medium, data accuracy)**: `recommendation.py` 가 점포 1~2개 카테고리를 `per_store_sales`(=monthly/store_count) 아티팩트 + competition 하한(0.01) 증폭으로 score 100 1순위 고정(성수 편의점 월 2억 from 1점포). 댐핑 단독은 ~100x 우위라 수학적으로 불충분 → 스코어링 루프 직후 `_apply_store_floor`(`MIN_RELIABLE_STORES=3`) 파티션, 통과 카테고리 0이면 전체 fallback + `low_confidence` 안내 메시지("점포 표본이 적어(<3개) 참고용 추천"). 루프 내부 미수정(surgical, ~8줄). 회귀 `test_recommendation_scoring.py` 3건 + mock 회귀 10건 = **13 passed**, ruff PASS. **ISSUE-002 (low, cosmetic)**: Hero H1 한글 "데이터로" 단어중간 줄바꿈 → Tailwind `break-keep`(word-break: keep-all). tsc 0 error · lint pre-existing 3 warning만(변경 무관). **워킹트리 chore**: `.gitignore`(+`.gstack/`) + `CLAUDE.md`(+`## Health Stack`) 커밋. 커밋 4건(chore `7fbc118` / 003 fix `90937c6` / 002 fix `7ff871d`). **Item 4 Accuracy Eval Round 2**: 003 fix 가 recommend 품질을 바꾸므로 머지 후 별도 실행 패스로 게이트(미실행, 사용자 트리거). Plan [p0-backlog-2026-06-09](../plan/fix/p0-backlog-2026-06-09.md).
> **2026-06-08 QA(/qa) Standard 풀앱 패스 — out_of_scope/greeting 중복 suggestion fix + 회귀 테스트** ⭐ — Docker 실데이터 스택(frontend :3000 / backend :8000 / PostGIS 1,650 상권 / Redis) 기동 후 브라우저+SSE 검증. 기존 이미지 6주 stale → current source 재빌드(backend+frontend, pip SSL 은 Dockerfile `PIP_TRUSTED_HOST` build-arg 우회). 건강도 **98→99**. **ISSUE-001(medium) fix**: `graph.py` 스트림 말미 fallback suggestion 방출을 `greeting_direct`/`clarification_direct` 모드에서 skip — greeting/clarification 노드가 실행 중 tailored suggestion 을 직접 방출하는데 말미 generic 셋이 한 번 더 방출돼 client replace 로 tailored 를 덮어쓰던 문제(서울 외 거부 응답에 "이 자리 위험하지 않아?" 노출). 회귀 `test_graph_suggestion_emission.py` 2 passed. main 머지 후 **origin push 완료** (`44b9438..eb3e10f`, 4커밋). 검증(SSE): 부산/제주 out_of_scope=suggestion 1회(tailored)·greeting 1회·normal summary 1회(card+evaluator 유지)·회귀 0. 정상 플로우 전수 PASS(F03 요약/F05 비교 멀티상권추출/F07 추천/F13 프리뷰/F06 히트맵/검색 자동완성/privacy·terms/모바일), 콘솔 에러 0·XML leak 0·실수치 월환산 정상. **디퍼 2건**: ISSUE-003(recommend 가 점포 1~2개 카테고리를 점포당매출 아티팩트로 1순위 — 성수 편의점 score100/월2억 from 1점포, accuracy-eval 트랙 권장) · ISSUE-002(랜딩 H1 단어중간 줄바꿈 cosmetic). **환경 플래그(미수정)**: `.env`/`.env.dev` 의 `NEXT_PUBLIC_API_URL=:3000`(프론트포트) → 재빌드 시 chat SSE 버퍼링, `:8000` 권장(QA 중 임시 override). 리포트 `.gstack/qa-reports/qa-report-localhost-2026-06-08.md`.
> **2026-05-07 4 Plan 일괄 Pass 1 — Heatmap Singleflight + Backend pytest 확장 + W1 Type Boost 측정/튜닝 + Langfuse L2 Foundation** ⭐ — 4 P1 Plan ([heatmap-singleflight-reintroduce](../plan/infra/heatmap-singleflight-reintroduce.md) · [backend-pytest-coverage-expansion](../plan/infra/backend-pytest-coverage-expansion.md) · [w1-type-boost-tuning-2026-05-06](../plan/fix/w1-type-boost-tuning-2026-05-06.md) · [langfuse-l2-token-cost-eval](../plan/infra/langfuse-l2-token-cost-eval.md)) 의 Pass 1 일괄 구현. (1) **Heatmap Singleflight** — `services/singleflight.py` 재작성 (per-key Future + asyncio.Lock + leader cancel-shield), `map_data.py::get_heatmap[/all]` 통합, `/metrics` 에 `singleflight_coalesced_total` 노출. 9 testcase PASS (concurrent 50 → fn() 1회, exception propagation, follower-cancel-no-leak). (2) **Backend pytest 확장** — `conftest.py` fixture 5종 (`mock_da` / `memory_cache` / `category_resolver_default` / `app_client` / `mock_district_code`), `test_services_{cache,circuit_breaker,category_resolver}.py` + `test_repos_mock.py` (10 protocol smoke) + `test_routes_health_and_map.py` (lifespan + httpx ASGITransport) — 35 신규 testcase. `pyproject.toml` coverage 설정 + `scripts/run_tests.sh` + `.github/workflows/ci.yml::backend-test` dummy env + coverage XML artifact 통합. (3) **W1 Type Boost 측정** — `tests/data/w1_adversarial_2026-05-06.yaml` 32 case (TM=6/CDST=5/ST=5/CTS=5/BR=6/ABST=5), `scripts/w1_eval.py` (baseline + 4×3 sweep grid), 회귀 가드 `test_adversarial_accuracy_meets_95pct`. **Baseline 96.9% (31/32)**, sweep 12 셀 모두 동일 96.9% — boost/damp 와 무관한 단일 구조적 fail (BR-6, 3-char query × 22-char alias-paren). 현재 (boost=0.15, damp=0.5) 유지 채택. (4) **Langfuse L2 Foundation** — `langfuse_tracer.py::_normalize_usage` (LangChain/Anthropic/Gemini/OpenAI 4 shape 흡수) + `attach_generation_usage` (v3 `start_observation(as_type="generation", usage_details, prompt_name+version metadata)`) + `prompt_version("v1.0.0")` + `_git_sha()` 헬퍼. 12 testcase PASS. 노드 wiring (planner/evaluator/respond) + L2-C eval harness 는 Pass 2/3 으로 분리. **검증**: 전체 backend pytest **120 passed / 8 skipped** (신규 65 + 기존 55, 8 skip = `app_client` fixture host structlog 미설치). ruff PASS. 기존 `test_smoke::langfuse_enabled` host env fail 도 conftest 의 `LANGFUSE_PUBLIC_KEY=""` 로 자동 해결. CI workflow 에 dummy env 주입 + coverage XML artifact.
> **2026-04-30 UX Sweep Phase A-F Plan 2 Pass 1 — 통합 5 journey spec 신규 + 정적 baseline 9 testcase PASS** ⭐ — Plan [ux-final-e2e-regression-plan](../plan/qa/ux-final-e2e-regression-plan.md). Plan 1 verdict ✅ 후속 회차 — `frontend/e2e/ring2-journeys/j06-ux-a2f-integration.spec.ts` 신규 1 파일 (~960 LOC) 에 Phase A→F 횡단 5 journey 1:1 매핑 (J01 onboarding-to-feedback A.4+B.6+F11+F12+F13+D.4 / J02 compare 풀사이클 B.1~B.5 / J03 모바일 첫 진입 C.2+D.2+D.9+B.3 / J04 에러복구+Tally폴백 D.1+D.5+B.4 / J05 a11y 종합 D.2+D.3+D.4+D.6+D.9+WCAG). 각 step 독립 try/catch 로 부분 PASS 가능 (StepCheck[] 누적 + passCount ≥ 임계 시만 fail). 검증: tsc 0 error · next lint 0 warning · dry-list 5 testcase 인식 · 정적 baseline 9 testcase (Ring0-D1 + Ring0-F1 + Ring0-F2) 재현 PASS. Pass 1/2/3 + prod-smoke runtime 은 본 머신 :3001/:8002 점유로 user 수동 트리거 권장. [Verdict](../qa/runs/ux-final-e2e-2026-04-30/summary.md)
> **2026-04-30 UX Sweep Phase A-F Pass 1 — 13 신규 시나리오 작성** ⭐ — Plan [ux-phase-a-f-test-plan](../plan/qa/ux-phase-a-f-test-plan.md). 기존 25 + 신규 13 = 38 시나리오 매트릭스 확정. 변경 9 spec 수정 + 2 spec 신규 + verdict 1: A 엣지 3건 (`A1-EDGE-PRIVATE` Safari Private localStorage / `A4-EDGE-EMPTY` 빈 q scrub / `A4-BENTO-ALL6` 6 cell 매핑) · B 보강 2건 (`B5-FALSE-POS-EXT` negative 3건 추가 / `B4-RETRY-LOOP` 5회 직렬 가드) · C perf 2건 (`C3-PERF` INP < 500ms / `C4-FAILED` 600ms transition) · D 보강 6건 (`D1-RESET-LOOP` self-throw 정적 invariant / `D5-IFRAME-BLOCK` Tally route.abort fallback / `D7-PERF` getComputedStyle 캐시 / `D8-HOVER` Header Tailwind hover / `D9-WCAG258` BottomNav minHeight 60+icon 24+label 13 mobile-iphone / `D10-VISUAL` mouseout styleFor 재계산) · F SSR 2건 (`F1-SSR` no use client / `F2-IMPORT-MAP` import 사용처 0). 검증: tsc 0 error · 정적 회귀 9 testcase PASS (Ring0-D1 + Ring0-F1 + Ring0-F2). Ring1+ 27건은 USE_MOCK e2e stack 필요 (본 머신 :3001/:8002 외부 점유로 user 수동 트리거 권장). [Verdict](../qa/runs/ux-phase-a-f-pass1/summary.md)
> **2026-04-30 UX Sweep Phase F — Tier hook stub (옵션 phase)** — Plan [ux-sweep-phase-f-tier-hook](../plan/ui/ux-sweep-phase-f-tier-hook.md). Phase 2 (OAuth/결제/Tier 게이팅) 머지 시 surface diff 최소화를 위한 hook 자리만 마련. 코드 변경 2 신규 + spec 1 신규: (F.1) `frontend/src/hooks/useTier.ts` — `Tier = 'free' | 'pro' | 'team'` 타입 + `useTier()` 하드코딩 `'free'` 반환 stub. (F.2) `frontend/src/components/common/FeatureGate.tsx` — `'use client'` wrapper, `useTier()` 호출 (grep 표면 유지) 후 children 그대로 렌더 (no-op). spec: `ring0-preflight/03-tier-hook.spec.ts` 신규 — Tier 타입 export + `tier:'free'` 하드코딩 + FeatureGate `<>{children}</>` 정적 invariant 회귀. tsc 0 error · next lint 0 warning. Phase 2 머지 시 본 2 파일 비교 로직만 활성화하면 일괄 게이팅 가능.
> **2026-04-30 UX Sweep Phase E — Premium Deferred (toggle 1건)** — Plan [ux-sweep-phase-e-premium-deferred](../plan/ui/ux-sweep-phase-e-premium-deferred.md). Phase 2 (OAuth/결제/Tier 게이팅) 의존 3건 (E.1 F06 평일/주말 토글 · E.2 F09 What-If UI · E.3 FreeLimitSurvey Premium CTA) 차단 사유 + 선행 요건 명시. 코드 변경은 E.3 임시 결정만 적용 — `FreeLimitSurvey` Premium CTA 블록에 `NEXT_PUBLIC_PREMIUM_CTA_ENABLED` env 게이트 추가 (default off, `'true'` 일 때만 노출), `data-testid="survey-premium-cta"` 부여. spec 보강 1건: `f12-feedback.spec.ts::Ring1-F12-E3` — env off 시 mood ≥ 4 응답에도 CTA 미노출 회귀. tsc 0 error.
> **2026-04-30 UX Sweep Phase D — A11y / 마감** ⭐ — Plan [ux-sweep-phase-d-a11y](../plan/ui/ux-sweep-phase-d-a11y.md). 10 항목 (D.1~D.10) 일괄 구현: (D.1) `app/error.tsx` · `app/loading.tsx` · `app/app/error.tsx` · `app/app/loading.tsx` 4 boundary 신규 — reset+홈 동선 + split-panel skeleton. (D.2) `globals.css` `:focus-visible` 글로벌 룰 + Header/Hero/BetaBanner/Footer focus-visible:ring 보강. (D.4) `FeedbackRow` ack 후 ↩️ 수정 토글 + `useToastStore` 안내. (D.5) `FeedbackModal` iframe 5s timeout fallback (mailto/Kakao). (D.6) `CompareCard`/`SuggestionChips` 안정 키 (`${index}-${value}`). (D.7) `InlineChart` CSS 변수 토큰화 (`useEffect` 1회 read + SSR fallback) + 차트 토큰 5종 light/dark 추가. (D.8) `Header` Tailwind hover 전환 (inline JS 제거). (D.9) `BottomNav` minHeight 60px + 폰트 22→24/12→13 (WCAG 2.5.8 AA). (D.10) `DistrictLayer` mouseout 시 `styleFor` 전체 재계산 (compare 슬롯 색 race 방지). 변경 12 파일 + 신규 spec 2건 (`ring0-preflight/02-error-boundary.spec.ts` · `ring1-features/a11y.spec.ts`). 검증: tsc 0 error · next lint 신규 변경 0 warning (pre-existing 4건만 잔존).
> **2026-04-29 Out-of-Scope (서울 외 지역) 거부 3중 가드 구현** ⭐ — Plan [out-of-scope-handling-2026-04-29](../plan/fix/out-of-scope-handling-2026-04-29.md). 사용자 보고 ("부산/제주 등 서울 외 질문 처리 안 됨") → 3중 가드 설계: (L1) `intents.yaml` `out_of_scope` intent 신규 (광역지명 + 비-서울 시단위 + 부산 동단위 + 제주 동단위 패턴, 한글 word-boundary `(?<![가-힣])...(?![가-힣ㄱ-ㅎㅏ-ㅣ])` 로 substring 오매치 차단). (L2) `planner.py` `_classify_by_rules` 진입 직후 `out_of_scope` 분기 + `_CLARIFICATION_TEMPLATES["out_of_scope"]` 추가, LLM/Tool 호출 0건으로 즉시 clarification_direct 반환. (L3) `entity_matching.py` `STRONG_TOP1_MIN=0.70` 상수 + `chat.py` message-detect 분기에서 score < STRONG_TOP1_MIN 시 거부 (silent wrong-district 가상 비-서울 fuzzy 매치 차단). (L4) `system.py::_BASE_PROMPT` rule 11 + `respond.py::RESPOND_SYSTEM_PROMPT` rule 13 거부 룰 명시. 변경 6 파일 + 신규 unit `test_out_of_scope.py` 21 testcase + Plan 1건. 검증: ruff PASS · **pytest 70/71** (신규 21 + 기존 49, 1 fail = `test_smoke::langfuse_enabled` host env pre-existing) · 회귀 0.

---

## 2026-06-26 — S7 coref 수치 날조 fix Pass 3 라이브 검증 + 죽은 모델 ID fix

### 개요
- **Plan**: [s7-coref-toolless-fabrication.md](../plan/fix/s7-coref-toolless-fabrication.md) · **Verdict**: [s7-coref-pass3-2026-06-26/_verdict.md](../qa/runs/s7-coref-pass3-2026-06-26/_verdict.md)
- 복원 세션에서 잔여 P0(S7 coref, eval Round 2 8.9→5.0 회귀)를 prior 세션 구현(planner force-plan)의 **라이브 Pass 3**로 마무리. 검증 중 근본원인 2건을 추가 처리.
- ✅ Pass 3 5회 (tool 5/5·정답 5/5·날조 0/5·물리모순 0/5) / ✅ 모델 ID fix / ✅ respond 유동인구 가드 / ✅ 커밋 2건

### Pass 3 라이브 검증 (R3-COREF-NUMERIC-01)
| 항목 | 내용 |
|---|---|
| 환경 | USE_MOCK=false·1,650 상권. `backend-dev` 프로필(`./server:/app` bind-mount + `--reload`)로 미커밋 소스 라이브 반영. 기존 `catchment-area-analysis-backend` 이미지를 `backend-dev`로 태그 후 `--profile dev --no-build` 기동(빌드 SSL 우회) |
| 시나리오 | 동일 session_id 2턴 ×5: ① "홍대랑 성수 비교해줘"(compare 카드) → ② "거기 중 유동인구가 더 많은 곳은 어디야?"(coref) |
| DB GT | 홍대(3120103) 4,106,209 · 성수(3120052) 1,412,369 (floating_population 시간대 합계, 2025Q4). peak 988,851/312,134 |
| 결과 | tool 호출률 **5/5**(get_floating_population 강제) · 정답(홍대) 5/5 · 원 날조값(124,386/67,741) 0/5 · 물리 모순(파생 일평균>peak) 0/5 |

### RC-모델 — graph.py 죽은 모델 ID (✅ fixed, 별건 인프라)
- `graph.py:74`(planner)/`96`(respond·default) 하드코딩 `claude-sonnet-4-20250514`가 현 ANTHROPIC_API_KEY 에서 404(not_found, 은퇴) → anthropic provider respond 전량 graceful-error. `/v1/models` 확인 결과 유효 Sonnet = `claude-sonnet-4-6` 교체. planner 는 rule path 라 우회됐으나 respond 는 항상 LLM → Pass 3 선결조건. 커밋 `654029a`.

### RC-respond — 파생 '일평균' 오계산 (✅ fixed)
- 1차 Pass 3에서 respond가 headline(410만/141만)은 맞게 인용하나 파생 "일 평균"을 ÷30/÷3 불일치로 날조 → 성수 47.1만·홍대 136만 등 시간대 peak 초과(물리 모순 3/5). 근원: repository `get_floating_population` 반환 `daily_avg` 필드가 실제로는 **분기 시간대 합계**인데 이름이 daily_avg → LLM이 "일평균"으로 라벨·분할. peak 값은 반환 안 됨(`peak_hour`=슬롯 인덱스).
- **fix**: `respond.py` `RESPOND_SYSTEM_PROMPT`에 `FLOATING_POP_PRESENTATION_RULES`(집계값 그대로 인용·일수 분할 금지·peak는 by_hour 실값만·비교는 집계값 직접) 추가 → 2차 Pass 3 물리모순 0/5. 필드명 정정은 blast radius(카드/mock/테스트)로 follow-up.

### 검증
- ✅ ruff check/format PASS (planner.py/respond.py/graph.py). 어떤 테스트도 프롬프트 텍스트·모델 문자열 assert 안 함(test_langfuse_l2 `claude-sonnet-4` 는 self-contained 리터럴).
- ⚠️ pytest 재실행은 본 환경(호스트 앱-deps 부재 + 컨테이너 pytest 부재)에서 불가 — planner.py + test_coref_numeric_followup.py(16)는 prior 세션 **148 passed**, 이번 변경(모델 문자열·프롬프트 텍스트)은 그 경로 미접촉.

### 커밋 (main 직접, 프로젝트 관례)
- `c62bb17` fix(agent): S7 coref 수치 날조 — planner force-plan + respond 유동인구 가드 (planner.py·respond.py·test_coref_numeric_followup.py·plan·verdict)
- `654029a` fix(agent): 죽은 모델 ID claude-sonnet-4-20250514 → claude-sonnet-4-6 (graph.py)
- 제외: `.claude/settings.local.json`(기존 drift) · `docs/architecture/tech-stack-rationale.md`(무관)

### 다음 (선택)
- 🔧 `daily_avg` 필드명 정정(`quarter_total` 등) — repository + 카드 + mock parity + 테스트 동반(별건 follow-up)
- 🔧 검증용 `backend-dev`+redis 컨테이너 기동 상태 — 불필요 시 `docker compose --profile dev down`
- 🔧 origin/main push (커밋 2건 미push)

---

## 2026-06-25 — 데이터 신뢰성 확보 (적재 결손 3건 + 검증 게이트)

### 개요
- **Plan**: [data-reliability-2026-06-25.md](../plan/fix/data-reliability-2026-06-25.md)
- 2026-06-25 정합성 감사가 발견한 **3개월 잠복 적재결손 3건** 근본수정(Part A) + **컬럼내용 검증 게이트**로 재발차단(Part B). 세 결손 모두 "행은 존재하나 컬럼 전량 0/NULL" 이라 기존 행수·FK·boundary 검증을 조용히 통과했다.
- ✅ Pass 1(C1~C5 수정·재적재) / ✅ Pass 2(C6~C9 게이트·회귀·CI) / ✅ Pass 3(C10 시드재생성·C11 문서) / ✅ 적대검증 워크플로우(11 finding→P1·P2 수정)

### RC1 — 직장인구(worker) 19,692행 전량 0 (✅ fixed)
| 항목 | 내용 |
|---|---|
| 원인 | `data/etl/transformers.py::transform_resident_pop` worker 분기가 resident 접미사(`MAG_POPLTN_CO`/`FAG_POPLTN_CO`) 재사용 → `AGRDE_10_MAG_POPLTN_CO` 등 worker API 에 없는 키 조회 → 전부 None→0 |
| 수정 | worker 분기에서 `MAG_{n}_WRC_POPLTN_CO`/`FAG_{n}_WRC_POPLTN_CO`(n=age_prefix−`AGRDE_`) 빌더 분리. resident 분기 무변경 + "API path dormant(CSV)" 주석. **live API 1행 dump 로 키 사전검증**([[feedback_etl_api_column_rename]]) |
| 검증 | 단위: 12행, Σ=`TOT_WRC_POPLTN_CO`. 재적재(`runner run 2025Q4 --table resident_pop`, 19,692행) 후 worker `bool_and(population=0)=f`, total_pop **4,724,265** |

### RC2 — `default_unit_price` 100% NULL (✅ fixed)
| 항목 | 내용 |
|---|---|
| 원인 | alembic 002 백필 `UPDATE ... WHERE major_category=...` 이 category_metadata 시드(stores 적재 후) **전에** 실행돼 0행 no-op. 이후 `seed_category_metadata.py` INSERT 가 컬럼 누락 → 영구 NULL |
| 수정 | `_UNIT_PRICES`(외식12000/서비스25000/소매15000)+`_DEFAULT_UNIT_PRICE=15000` 공유, INSERT/ON CONFLICT 에 `default_unit_price` 포함. 2차 방어선 `repositories/real/simulation.py::get_default_unit_price` NULL→major 기본값 폴백 |
| 검증 | 재시드 후 NULL **0건**. 분포 12000×10/25000×10/15000×80. `@real` 테스트가 major↔price 일치 검증 |

### RC3 — `aliases` 100% NULL (✅ fixed)
| 항목 | 내용 |
|---|---|
| 원인 | source of truth 부재 + seed INSERT 누락 |
| 수정 | `data/etl/category_aliases.json` 핵심 **32종**(콜로키얼: 스벅·편의점·약국·부동산·피시방 등) 신규 + seed 에 콤마조인 결합. 나머지 NULL 은 의도(카테고리명+learned_aliases+LLM 위임) |
| 검증 | 재시드 후 32 set/68 NULL. resolver 가 카페→CS100010·편의점→CS300002·부동산→CS200033 정확 매칭 |

### RC0 — 컬럼내용 검증 게이트 (✅)
- `runner.py::_validate_data` → 테스트 가능한 `_collect_validation_checks(conn, quarter)` 로 분리. per-column NULL 비율, all-zero(`bool_and`, NULL-safe `COALESCE`), 음수 sanity, **비-0 exit**. 행수 체크는 **quarter-scope**(빈 분기 false-pass 차단).
- `scripts/audit/p1_api_vs_db.py` `--strict` exit code(API↔DB 불일치 게이팅).

### 적대검증 워크플로우 (11 finding 전건 confirmed)
5 lens(rc1-worker/gate-logic/seed-idempotency/test-coverage/plan-conformance) × finding별 회의적 검증, 16 agent. **rc1-worker lens 0 finding**(핵심 수정 무결).
- **P1 수정**: SEED-1(alias `학원` 이 외국어/예술/컴퓨터학원 name 의 substring → resolver naive 매칭이 모든 학원 subtype 을 CS200001 로 오라우팅) — `학원` 제거, subtype 정상 복구 검증 / GATE-1(행수 미-scope → `validate <빈분기>` false-pass) — 4 시계열 테이블 quarter-scope, `validate 2026Q1` FAIL(exit1) / TC-1(게이트 무테스트) — `@real` gate FAIL-injection 테스트(롤백 트랜잭션)로 R3-VALIDATE-GATE 코드화.
- **P2 수정**: GATE-2(floating_pop all-zero NULL-unsafe → `COALESCE`) / TC-2(RC2 단위테스트 동어반복 → seed 결과 `@real` 검증) / PC-1(잉여 noqa 제거).
- **의도적 defer**: GATE-3(all-constant `count(distinct)=1` 은 단일분기 설계와 충돌 → false-FAIL) / SEED-2(price↔major decouple 은 category_name 안정성상 도달불가) / PC-3(`settings.local.json` 은 본 작업 무관 기존 drift).

### 검증 종합
- `ruff check` PASS · pytest **132 passed / 8 skipped**(기존 structlog skip) · data-integrity 13 테스트(7 unit CI-safe + 6 `@pytest.mark.real`, gate FAIL-injection 포함) · CI `backend-test` 는 `-m "not real"` 로 DB 테스트 deselect.
- `runner validate 2025Q4` ALL PASS / `2026Q1`(빈 분기) FAIL / worker=0 주입시 FAIL 재현.
- 시드 덤프 `data/seed/marketscope_seed.dump` 재생성(5.26→5.6MB, 정정 데이터 반영, TOC 검증). **fresh compose 복원 재검증은 live DB 파괴적이라 미실행 — 클린 세션 권장**.

### Memory 신규
- `feedback_rich_table_bracket_markup` — rich.Table 셀의 `[worker]` 동적 라벨이 스타일 markup 으로 파싱돼 증발(게이트 행 식별 불가) → `(..)`/`:` 사용.

### 다음 (선택)
- 🔧 커밋(미수행 — 사용자 확인 대기): 코드 8파일 + 신규 2 + 시드 덤프(LFS). `settings.local.json`(기존 drift) 은 스테이징 제외 권장.
- 🔧 fresh `docker compose up` 로 시드 복원 end-to-end 재검증(클린 세션).
- 🔧 2026Q1 분기 갱신 시 전 테이블 동시 적재(별도 사이클) — 게이트가 누락 분기를 FAIL 로 잡음.

---

## 2026-06-09 — P0 백로그 (ISSUE-003 / ISSUE-002 / 워킹트리)

### 개요
- **Plan**: [p0-backlog-2026-06-09.md](../plan/fix/p0-backlog-2026-06-09.md)
- 2026-06-08 QA 디퍼 2건(ISSUE-003 / ISSUE-002) fix + 워킹트리 chore 정리. 커밋 4건 main 직접(프로젝트 관례).
- ✅ ISSUE-003 (medium, data accuracy) fix + 회귀 테스트 / ✅ ISSUE-002 (low, cosmetic) fix / ✅ 워킹트리 chore 커밋
- 🔧 Item 4 Accuracy Eval Round 2 — 003 fix 머지 후 별도 실행 패스로 게이트(미실행, 사용자 트리거)

### ISSUE-003 — recommend_business 저점포수 랭킹 아티팩트 (✅ fixed)

| 항목 | 내용 |
|---|---|
| 원인 | `repositories/real/recommendation.py:153` `raw_score = (per_store_sales * age_match * (1-close_rate)) / max(competition, 0.01)`. 점포 1개면 `per_store_sales`(=monthly/store_count)가 카테고리 전체매출(월 2억)로 잡히고, `competition`(=store_count/total) 하한 0.01 로 희소 카테고리 ×100 증폭 → 정규화 후 score 100 1순위 고정 |
| 수정 | 모듈 상수 `MIN_RELIABLE_STORES=3` + 순수함수 `_apply_store_floor` 추가. 스코어링 루프 직후(L181) `filtered, low_confidence = _apply_store_floor(raw_scores)` 로 `store_count < 3` 카테고리 제외. 통과 카테고리 0이면(작은 골목상권) 전체 fallback + `low_confidence=True`. 결과 dict 에 안내 메시지("점포 표본이 적어(<3개) 참고용 추천입니다") |
| 범위 | 루프 내부(per-category 계산) 미수정 — 플로어는 루프 직후 파티션. ~8줄. Mock 레포는 fixture 기반이라 공식 미사용 → 변경 불필요 |
| 검증 | `tests/test_recommendation_scoring.py` 신규 3건(단일점포 제외 + 전부미달 fallback + 상수 sanity) + `test_repos_mock.py` 회귀 10건 = **13 passed**. ruff/format PASS. `_apply_store_floor` 는 신규 함수라 fix 없으면 import 자체 실패(회귀 가드 성립) |
| 커밋 | `90937c6` |

### ISSUE-002 — Hero H1 줄바꿈 (✅ fixed)

| 항목 | 내용 |
|---|---|
| 원인 | `components/landing/Hero.tsx:75` `<h1>` 에 word-break 없음 → 한글 "데이터로" 단어중간 줄바꿈. codebase 전체 break-keep 사용처 0 |
| 수정 | className 에 Tailwind `break-keep`(word-break: keep-all) 추가. 기본/investor 카피 양쪽 커버 |
| 검증 | tsc 0 error · next lint pre-existing 3 warning(DistrictLayer/MapContainer, 변경 무관)만 |
| 커밋 | `7ff871d` |

### 워킹트리 chore (✅)
- `.gitignore` +`.gstack/` · `CLAUDE.md` +`## Health Stack` (이전 세션 산출물) → chore 커밋 `7fbc118` 로 먼저 클린 후 fix 진행.

### 다음 P0
- 🔧 Item 4 Accuracy Eval Round 2 — `scripts/eval/run_accuracy_round2.sh`(BASE=:8000) → S1~S8 SSE 수집, S4(건대 추천)는 003 fix 후 1순위가 점포 ≥3 인지 확인. current source 재빌드 필수(`feedback_stale_container_vs_source`). 사용자 트리거.
- 🔧 origin/main push (커밋 4건 미push)
- 🔧 `.env`/`.env.dev` `NEXT_PUBLIC_API_URL` → `:8000` 교정(직전 세션 임시 override만)

---

## 2026-06-08 — QA (/qa) Standard 풀앱 패스

### 개요
- **리포트**: `.gstack/qa-reports/qa-report-localhost-2026-06-08.md` (12 스크린샷 + baseline.json)
- ✅ Docker 실데이터 스택 기동 — 기존 이미지 6주 stale → current source 재빌드(backend+frontend). pip SSL(사내 MITM)은 Dockerfile `--build-arg PIP_TRUSTED_HOST` 우회. `NEXT_PUBLIC_API_URL` 은 빌드 시 `:8000` 으로 override(`.env` 값 `:3000` 버그 회피)
- ✅ 건강도 **98 → 99 (Δ+1)**. 콘솔 에러 0 / XML leak 0 / 실수치·월환산 정상
- ✅ ISSUE-001 (medium) fix + 회귀 테스트 main 머지
- 🔧 디퍼 2건 (ISSUE-003 recommend 저점포수 랭킹 · ISSUE-002 H1 줄바꿈)
- ⚠️ 환경(미수정): `.env`/`.env.dev` `NEXT_PUBLIC_API_URL=:3000`(프론트포트) → 재빌드 시 chat SSE 버퍼링, `:8000` 권장

### ISSUE-001 — out_of_scope/greeting 중복 suggestion (✅ fixed)

| 항목 | 내용 |
|---|---|
| 원인 | `_greeting`/`_clarification` 노드가 실행 중 tailored suggestion 을 직접 방출하나 `final_suggestions`(state) 미설정 → 스트림 말미 fallback 이 generic suggestion 한 번 더 방출 |
| 증상 | client 가 suggestion 을 replace → generic("이 자리 위험하지 않아?"/"카페 하면 어때?", district 선택 가정)이 tailored Seoul-redirect 셋을 덮어씀. 서울 외 거부 UX 훼손 |
| 수정 | `graph.py` 말미 방출을 `final_response_mode in ("greeting_direct","clarification_direct")` 일 때 skip (두 노드는 항상 1회 self-emit → 누락 없음) |
| 검증 | SSE 부산/제주/greeting=1회(tailored)·normal summary=1회(card+evaluator 유지)·회귀 0. UI 확인(tailored 칩만). `test_graph_suggestion_emission.py` 2 passed (컨테이너 pytest 9.0.3/py3.12) |
| 커밋 | c777f49 (fix) · 2d13d22 (test) — main FF 머지, 로컬 3커밋 ahead(미push) |

### 검증 PASS (정상 플로우)
요약 F03 / 비교 F05(멀티상권 추출, hallucination 0) / 추천 F07 / 프리뷰 F13(zero-LLM) / 히트맵 F06(+TimeSlider) / 검색 자동완성 / privacy·terms / 모바일(390×844 BottomNav). out_of_scope 가드(부산/제주) 정상. Redis lazy-init 정상 연결.

### 디퍼 (사용자 결정 대기)
- **ISSUE-003 (medium, data accuracy)**: `recommend_business` 가 점포수 1~2개 카테고리를 점포당매출 아티팩트로 1순위 랭크 (성수동 편의점 score 100 / 월 2억 from 1점포). 점포수 floor(예 <3) damp/제외 권장 — [accuracy-gap-fix](../plan/fix/accuracy-gap-fix.md) 트랙.
- **ISSUE-002 (low, cosmetic)**: 랜딩 H1 "데이터로" 단어중간 줄바꿈 → `word-break: keep-all` 권장.

### 다음 P0
- ✅ origin/main push 완료 (`44b9438..eb3e10f`, 4커밋 — origin↔local 동기화)
- 🔧 `.env`/`.env.dev` `NEXT_PUBLIC_API_URL` → `:8000` 교정
- 🔧 ISSUE-003 accuracy-eval 트랙 반영 / ISSUE-002 cosmetic

---

## 전략

Phase 1A(Mock E2E) → Phase 1B(Real Data + UX) → Phase 3(확장) → Phase 2(Premium)

| Phase | 범위 | 상태 |
|-------|------|------|
| 1A | Mock E2E, Card UI, Agent 전체 흐름 | ✅ 완료 |
| 1B | 공공데이터 ETL + 1,650 상권 적재 + 프로덕션 배포 | ✅ 완료 (2026-03-30) |
| 3 | F06 히트맵 · F09 매출 시뮬레이션 · F10 PDF | ✅ 완료 (2026-04-06) |
| Prod | `marketscope.robitlabs.co.kr` 라이브 | ✅ 완료 (2026-04-16) |
| 2 | OAuth2 · 결제 · Tier 게이팅 · F04 UI | ⏳ 미착수 (Accuracy Gap 선행 권장) |

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
| LLM_PROVIDER | **anthropic** (Claude Sonnet 4) |
| Planner / Respond | Claude Sonnet 4 (TTFT 1.5s) |
| Evaluator | Gemini 2.5 Flash |
| Fallback | gemini-2.5-pro / flash |
| Agent 모드 | PAE (max 3 rounds) |
| 관측성 | Langfuse L1 (trace wiring, graceful degrade) |

---

## 현재 서비스 지표

- Mock 상권 5개 · Real 상권 1,650개
- ETL 적재 (2025Q4): floating_pop 9,888 / estimated_sales 21,333 / stores 75,985 / resident 39,288
- Agent Tool 9종 · Card 타입 5종 · SSE 이벤트 9종
- E2E: ring0~3 78 test (66 PASS / 0 FAIL / 12 SKIP) + prod-smoke 28/28

---

## 프로젝트 완성도 평가 (2026-04-22 기준, W1~W3 반영 전)

| 축 | 점수 | 판정 | 약점 |
|---|---:|------|------|
| 안정성 | **85** | 프로덕션 운영 가능 | 세션 인메모리 · `store_history` 실데이터 부재 · backend pytest 부재 |
| 효율성 | **82** | 양호 | Langfuse L2+ 미구현 · Heatmap singleflight 미통합 |
| 정확성 | **74** | 주요 시나리오 합격 | 6 GAP (A~F) — W1~W3 적용 후 재측정 대기 |

**로드맵**: [Accuracy Gap Fix](../plan/fix/accuracy-gap-fix.md) W1~W4 · [Eval Round 2](../plan/fix/accuracy-gap-eval-round2-2026-04-24.md) — 목표 74 → 85+.

---

## 이력 요약 (2026-03-30 ~ 2026-04-30)

> 상세는 git history (`git log --follow docs/status/current-status.md`) + `docs/qa/runs/` + `docs/plan/` 로 복원.

| 날짜 | 주요 내용 |
|------|----------|
| 2026-04-30 | UX Sweep Phase A-F Pass 1 — 13 신규 e2e 시나리오(기존 25+13=38) + 통합 5 journey(j06) 신규. 정적 회귀 9 testcase PASS · tsc 0. Ring1+ runtime 은 user 수동(:3001/:8002 점유). [Plan](../plan/qa/ux-phase-a-f-test-plan.md) · [Plan2](../plan/qa/ux-final-e2e-regression-plan.md) |
| 2026-04-29 | Out-of-Scope(서울 외) 거부 3중 가드 — out_of_scope intent + STRONG_TOP1_MIN(0.70) + system/respond prompt rule. 한글 word-boundary 로 substring trap(부산물/광주리) 차단. ruff PASS · pytest 70/71. [Plan](../plan/fix/out-of-scope-handling-2026-04-29.md) |
| 2026-04-28 (저녁) | Prod 재배포 — district-click-race fix 라이브 적용. dev/prod compose project name 충돌로 `:3200` stop → 502 → A 방식 destructive 4 Pass. frontend `46815639...` + backend `6be3098215b9` healthy. P1~P9 ALL PASS · Playwright real-DB 3/3 · prev-2026-04-28b tag. [Plan](../plan/infra/prod-redeploy-2026-04-28-evening.md) |
| 2026-04-28 | District click race / "먹통" fix — 6 근본 원인 (sendMessage isLoading return / ChatPanel disabled / setPreview lastDistrictCode race / SSE late-done / per-session lock 부재 / 1.5s setTimeout). Stale-while-cancel + Monotonic requestId + AbortController + Per-session async cancellation. ruff/tsc/pytest 49/50 · memory 4건 신규. [Plan](../plan/fix/district-click-race-2026-04-28.md) |
| 2026-04-28 | 프로덕션 재배포 (`52ae7db → 04376a4`) + Tool 함수명 노출 fix. alembic 005 + Langfuse 11차원/6스코어 + W1 X시장 boost + planner clarification + numeric_sanity + respond.py 502→280 LOC. ATTRIBUTION_PROMPT_RULE + `_ToolTagSanitizer` 11종 가드. prod-smoke 30/30 · live raw tool name leak 0건. [Plan](../plan/infra/prod-deploy-2026-04-28.md) |
| 2026-04-28 | Langfuse 전체 통계 집계 Phase 1+2 — v3 tracer 에 `district_type_for` / `attach_summary_observation` (start_observation 우회) / `emit_score`. graph finally 에서 11 차원 metadata + 6 score emit. unit 10/10 + Playwright stats-aggregate 16/16 PASS. [Plan](../plan/infra/langfuse-aggregate-stats-2026-04-28.md) |
| 2026-04-27 | P0 우선순위 6건 — W1 entity_matching X시장 boost + paren-alias dampen, RESPOND XML leak `_XMLTagSanitizer` (rule 13), Planner empty-plan clarification 3종, Eval district_code 하드코딩 제거 + drift guard, status-compress 517→383, Refactor Pass 2 `api/errors.py` 헬퍼. ruff/tsc/pytest 22/22 PASS. [Plan](../plan/fix/p0-priority-2026-04-27.md) |
| 2026-04-24 | User-Journey Sweep 16 journey/45 turn — Pass1 71.3% → **Pass3 99.1% (16/0 PASS)**. Planner 4 fix (compare-coref history fallback · rule 다중매치 우선순위 · 장문 synthesis summary fan-out · risk→recommendation 교정). [Plan](../plan/qa/user-journey-quality-2026-04-24.md) |
| 2026-04-24 | Langfuse 비용 커버리지 fix — dev 컨테이너 `langfuse==2.60.10` stale → v3 업그레이드 후 `done.trace_id=310fc8bf…` 실 발행. Eval harness `REQUIRE_TRACE=1` preflight + `validate_env.py` SDK drift 가드. [Plan](../plan/infra/langfuse-cost-coverage-fix-2026-04-24.md) |
| 2026-04-24 | Data Trust Reliability Phase A+B — `numeric_sanity` evaluator (216 LOC, 6/6 unit) + alembic 005 컬럼 코멘트 + RESPOND SALES_PRESENTATION_RULES 프롬프트 + trust eval 25/30 (5 상권). L3 한계: Planner entity mismatch 는 W1 별도 Plan. [Plan](../plan/fix/data-trust-reliability-2026-04-24.md) |
| 2026-04-24 | E2E 품질 Sweep 107 시나리오 — Pass 1 96.1% (10 FAIL) → Pass 2 96.4% (9 FAIL). Planner ambiguous→clarification short-circuit + `scenarios.py` rubric 보정 6건. [Plan](../plan/qa/e2e-quality-improvement-2026-04-24.md) |
| 2026-04-24 | Refactoring Pass 1+2 + Accuracy Eval Round 2 — `singleflight.py`/레거시 spec 7건 삭제, `respond.py` 502→280 LOC (`utils/formatting.py` 분할). Round 2 평균 7.6/10 FAIL — XML leak / W1 type boost 약화 / multi-district regression / coref empty-plan 4 P0 신규. [Plan](../plan/fix/accuracy-gap-eval-round2-2026-04-24.md) |
| 2026-04-24 (iOS) | BottomSheet 챗 탭 즉시 닫힘 fix — `BottomSheetHandle` 6px deadzone + `moved` 플래그, `BottomSheet.onDragEnd` `closest` 초기값을 현재 `snap`으로. iPhone E2E spec 신규. |
| 2026-04-23 (저녁) | E2E Pass 2 hotfix — FAIL 0 달성 (StatusBar testid · waitSSE · f12 skip-guard · reg python3 · F01-H3 timeout). v0.4.0 재배포 `c6cc60e` — learned_aliases 004 · 라우트 분리 (`/` 랜딩 / `/app` 챗맵) · P1~P7+N1~N2 전수 PASS. |
| 2026-04-23 | F-01 ETL fix (21,333 행 재적재, 8 컬럼 NULL 해소) + Accuracy Gap W1/W2/W3 구현 (entity_matching/abstention/rewriter utils + learned_aliases 004). LLMOps L1 SDK v2→v3 포팅, trace 발행 확인. Env 관례 분리 (`.env`=prod · `.env.dev`=dev). UI Landing/Feedback/Preview Phase A~D. Mobile Responsive Phase A+B+C. Data Integrity Audit. Refactoring Phase 1 Plan 작성. |
| 2026-04-22 | E2E + Ops 회귀 2차 READY (Dockerfile pip SSL 우회 · E2E 전용 stack 포트 재할당 · OPS-01/02 spec). 완성도 평가 85/82/74. [Run](../qa/runs/e2e-run-2026-04-22.md) |
| 2026-04-21 | E2E 회귀 Pass 1~3 그린 (Mock 39/39 + Real 24/24). LLMOps L1 Langfuse trace wiring (graceful degrade · SSE `done.trace_id`). |
| 2026-04-19 | v0.3.0 — 문서 계층화 · `docker-compose.e2e.yml` + `prodGuard` · 회귀 spec 4종. |
| 2026-04-17 | 매출 단위 fix (`_enrich_sales` sales→monthly_sales). 배포 근본해결 7건. 비교모드 다색 하이라이트. |
| 2026-04-16 | **프로덕션 런치** (marketscope.robitlabs.co.kr). 외부 nginx + LE · `docker-compose.prod.yml`. |
| 2026-04-14 | 서빙 안정성 Phase 1~10. 체크리스트 24% → 61%. Docker 하드닝 · DB/Redis 풀 · SSE heartbeat · Circuit Breaker · `/metrics` · DR. |
| 2026-04-13 | 분석 품질 Phase 1~3 (3단 해석법 · Tool enrich · 벤치마크). SSE 최적화 — TTFT 25s→1.5s. E2E eval S1 9.8 / S2 9.6 / S3 2.6 / S6 6.1 / S7 8.9 / S8 9.7 (평균 8.0). |
| 2026-04-08 | F05-H1 fix — `detect_districts_in_message` multi-extract. Real 45 시나리오 41 PASS. |
| 2026-04-07 | E2E QA Run (Mock 42 시나리오 94/100). 4-ring helper + 22 spec. React duplicate-key fix. |
| 2026-04-06 | P0 8건 수정 (`d8c0155`) — category aliases · LLM timeout · SSE 백프레셔 · AbortController. Phase 3 완료 (F06/F09/F10). |
| 2026-04-05 | Docker 통합. `docker compose up` 원커맨드 · Multi-stage + standalone · `--profile dev`. |
| 2026-04-04 | QA P0+P1 8건 (Tool 크래시 · 인젝션 방어 · Redis fallback · Semaphore(20)). |
| 2026-04-03 | PAE Agent 전환. Repository 패턴 (`DataAccess` + 7 Protocol). Frontend 리팩토링. 데이터 출처 citation. |
| 2026-04-02 | DB 셋업 자동화 — `setup_db.py --quick/full/reset` · seed 덤프 LFS · OA-15584 CSV 로더. |
| 2026-04-01 | Playwright E2E 26 시나리오 22 PASS · SHP→PostGIS 1,650 적재 · Real 모드 전환. |
| 2026-03-30~31 | **Phase 1B 완료** — Agent Progress Indicator · SSE 버퍼링 해결 · 다크 테마 · ETL 적재 · E2E 32/32. |

---

## Next Items (우선순위 순)

### 🟠 Accuracy Eval Round 2 — W1~W3 KPI 재측정

**Plan**: [accuracy-gap-eval-round2-2026-04-24.md](../plan/fix/accuracy-gap-eval-round2-2026-04-24.md)

- S1~S8 curl SSE 수집 + DB ground truth 교차검증
- Round 1 (2026-04-13) 대비 변화 기록 · KPI 테이블 업데이트
- Refactoring Pass 2 (respond.py 분할) 전에 baseline 확보

### 🟡 Refactoring Phase 1 Pass 2 (중위험)

**Plan**: [phase1-low-mid-risk-2026-04-23.md](../plan/infra/phase1-low-mid-risk-2026-04-23.md)

- `server/server/api/errors.py::make_error_response` 래퍼로 routes `HTTPException` 15건 통합
- `except Exception` 9건 → 구체 exception tuple 좁히기
- `agent/nodes/respond.py` 502 LOC → `agent/utils/formatting.py` 3종 이식, 목표 ~300 LOC
- `stores/chatStore.ts` 381 LOC → `stores/slices/{preview,mobile,feedback}.ts` 분할

### 🟡 관측성 L2+

- Langfuse L2+ (토큰/비용 측정, prompt version, eval harness)
- Heatmap preload singleflight 통합 (Pass 1 에서 `singleflight.py` 삭제 후 별도 Plan 으로 재도입)
- backend pytest 인프라

### 🟡 Phase 2 — Premium (미착수)

- OAuth2 + 결제 (Toss Payments / PortOne)
- Tier 게이팅 미들웨어 (Free 일 5회)
- F04 업종 심층 UI
- category_aliases 퍼지 검색 (pg_trgm)

### 🟢 장기 / 후순위

- 세션 저장소 Redis/Postgres 이관
- `store_history` 대안 데이터셋
- Docker 이미지 최적화

---

## 참고 문서

| 영역 | 경로 |
|------|------|
| 종합 QA | `docs/qa/qa-summary-report.md` · `qa-detailed-results.md` · `qa-improvements.md` |
| E2E run | `docs/qa/runs/e2e-run-2026-04-23-full.md` · `e2e-run-2026-04-22.md` · `e2e-run-2026-04-19.md` |
| 분석 품질 eval | `docs/qa/analysis-quality-eval-2026-04-13.md` (Round 1) · `analysis-quality-eval-2026-04-24.md` (Round 2, 대기) |
| Accuracy Gap | `docs/plan/fix/accuracy-gap-fix.md` · `accuracy-gap-eval-round2-2026-04-24.md` |
| Refactoring | `docs/plan/infra/phase1-low-mid-risk-2026-04-23.md` |
| 서빙 안정성 체크리스트 | `docs/spec/serving-stability-checklist.md` |
| 아키텍처 overview | `docs/architecture/overview.md` (backend/frontend/agent/data/deployment) |
| 기능 목록 | `docs/spec/feature-list.md` · `features/F01~F13-*.md` |
| LLMOps L1 | `docs/plan/infra/llmops-l1-adr-hosting.md` · `llmops-l1-verification.md` |
| E2E 회귀 인프라 | `docs/plan/infra/e2e-regression-plan-2026-04-19.md` · `e2e-ops-2026-04-22.md` |
