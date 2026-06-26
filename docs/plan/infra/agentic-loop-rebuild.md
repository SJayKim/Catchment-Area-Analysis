# Agentic Loop 전면 개편 — Full Agentic Rebuild

## Context

- 현재 "PAE Agent"는 이름과 달리 **규칙 기반 라우터**다. `planner.py` 가 `intents.yaml` regex 로 intent 분류 → **고정 plan 템플릿** 조회 → `{district_code}` 치환. LLM 은 도구를 고르지 않는다. 9개 tool 의 `@register_tool` `description`(=`fn.__doc__`)은 **어떤 LLM 에도 노출되지 않는** 죽은 문서다.
- 새 질문 형태마다 하드코딩 패치가 누적됐다: `GAP-A`(ambiguity)·`GAP-C/E`(coref rewrite)·`GAP-D`(abstention)·`S7 numeric coref rescue`·`_LONG_REPORT_TRIGGER`·`_RECOMMEND_OVERRIDE`. 8개 템플릿 밖 질문은 구조적으로 답할 수 없다.
- 데이터 접근은 **상권 단위 point lookup 만** 가능. "유동인구 top 10 동네", "프랜차이즈<30% 동네", "A 1위 업종 → 그 업종 강한 다른 동네" 같은 교차·집계·multi-hop 은 불가. `repositories/real/benchmarks.py` 의 percentile 은 아직 mock(TODO).
- 정확성 가드(out_of_scope·abstention·numeric_sanity·XML leak·매출/유동인구 표현 규칙)는 전부 프롬프트 패치 + 사후(post-hoc) 검사. numeric_sanity 는 틀린 수치를 **로깅만** 하고 막지 못한다(S7 날조가 증거).
- **사용자 결정(2026-06-26)**: ① Full agentic rebuild(LLM 주도 tool-use 루프, 통일 schema, 동적 플래닝) ② 우선역량 = 의미/패싯 검색 + multi-hop ③ Tiered 비용(공통질문 빠른 경로, 복잡질문만 깊은 루프). 가드레일/E2E 재구축 수용.
- **claude-api 레퍼런스 대조 완료**: 모델 ID 실존(`claude-opus-4-8`/`claude-haiku-4-5`/`claude-sonnet-4-6`, 날짜접미사 금지) · native tool-use 루프·prompt caching(tool+system)·`thinking:{adaptive}`+`output_config:{effort}`·mid-conversation system(beta `mid-conversation-system-2026-04-07`, 미지원 모델 `<system-reminder>` fallback) 전부 실존. ⚠️ **Opus 4.8 은 `temperature`/`top_p`/`top_k`+`budget_tokens` 제거(400)** — 현 `graph.py` 의 `temperature=0.3` 그대로 이식 불가. thinking 텍스트 기본 omitted → `thinking` SSE 채우려면 `display:"summarized"`. Opus 4.8 은 tool 과소호출 경향 → `description` 에 "이럴 때 호출" trigger 명시가 호출률을 올린다(본 개편 핵심 근거).
- **Memory 참조**:
  - `feedback_marketscope_sse_format` — `event:` 라인 없이 type 이 `data:` JSON 안에 임베드. 신규 emitter 가 이 포맷 유지 필수
  - `feedback_coref_followup_toolless_halluc` / `feedback_comparison_intent_halluc` — tool-less / multi-district 실패 시 수치 날조. 루프의 구조적 abstention+critic 이 대체 가드
  - `feedback_anthropic_model_id_retired_404` — `graph.py` 하드코딩 모델 ID 가 404 (SSE 아닌 컨테이너 로그에만). 신규 `llm_client` 는 `/v1/models` 확인 ID 사용
  - `feedback_respond_tool_use_xml_leak` — Claude Sonnet 의 tool_use XML leak. sanitizer 존치
  - `feedback_sse_hallucination_needs_db_gt` / `feedback_stale_container_vs_source` — 검증 시 DB ground truth 병행 + live inspect
  - `project_sales_quarterly_unit` — `monthly_sales` 는 분기 누적. envelope `units` 로 앵커
  - `feedback_out_of_scope_handling` — out_of_scope 3중 가드. router TRIVIAL 게이트로 이식

## Scope

- **In Scope**:
  - `agent_mode="agentic"` 신규 모드: native AsyncAnthropic 수동 tool-use 루프(`agent/loop/`) — `pae` 와 플래그 공존
  - Tool 통일 input_schema + 출력 envelope, `@register_tool` 확장, 9 tool 어댑터 마이그레이션
  - 교차상권 rank/filter/aggregate + 의미/패싯 검색 tool + `AnalyticsRepository`(MV + 실 percentile_cont)
  - 가드 구조화: 자동 abstention 주입 · 수치 critic 재질의 · sanitizer 이전 · out_of_scope router 게이트 · units 앵커
  - Tiered 라우팅(TRIVIAL/SIMPLE/DEEP) + tool-call budget + 모델 tier
  - SSE 9 이벤트 / 5 카드 계약 무변경 보존(프론트 0 변경)
- **Out of Scope**:
  - 프론트엔드 변경(6번째 card type 도입 금지 — rank 결과는 text+compare 카드로 표현)
  - `pae` 경로 동작 변경(byte-identical 보존)
  - `daily_avg` 필드명 자체 정정(repo+카드+mock+테스트 동반 — 별건 follow-up; 본 개편은 envelope 단 LLM 노출만 교정)
  - 세션 저장소 Redis/Postgres 이관 · Phase 2 Premium 게이팅

## Design

### 핵심: native Anthropic SDK 수동 agentic 루프
`graph.py`(LangGraph PAE) 대체. LangChain 은 legacy `pae` + 게이트/Gemini fallback 으로 잔존. 추론 루프는 `anthropic.AsyncAnthropic` 직접 사용. 기존 `asyncio.Queue` producer/consumer(backpressure·90s stall·Langfuse·`chat.py`) 재사용.

**신규 파일 (`server/server/agent/loop/`)**:
- `runner.py::run_agentic(...)` — `graph.run_agent` 과 동일 시그니처. Queue·producer·Langfuse trace/score·말미 `suggestion`+`done`(=`graph.run_agent` SSE-중립 블록 이식)
- `agent_session.py` — observe→think→act 루프(아래 골격)
- `router.py` — TRIVIAL/SIMPLE/DEEP 게이트. out_of_scope·greeting 규칙(0 LLM) 선처리
- `sse_emitter.py` — 루프 이벤트 → 9 SSE 단일 chokepoint(shape 는 `actor.py`/`graph.py` 에서 복사)
- `llm_client.py` — `AsyncAnthropic` 팩토리(`llm_provider=="mock"` 분기, circuit_breaker 재사용, `_anthropic_valid` 가드)
- `guards.py` / `suggestions.py` — 가드 / proactive suggestion(=`evaluator.generate_proactive_suggestions` 이식)

**루프 골격 (`agent_session.py`)**:
```
messages=[{"role":"user","content":rewritten}]; emit thinking("질문 분석 중...")
for step in range(tool_budget):                 # tool_budget 이 agent_max_rounds 대체
    stream = client.messages.create(model=tier.model, system=SYSTEM(cache_control),
        tools=TOOL_DEFS, messages=messages,
        thinking={"type":"adaptive","display":"summarized"},
        output_config={"effort":tier.effort}, stream=True)
    #  text_delta → emit text(sanitized);  tool_use start → emit tool(+plan 첫 배치)
    final = await stream.get_final_message(); messages.append(assistant=final.content)
    if final.stop_reason != "tool_use": break
    results = await gather(execute_tool(tu) for tu in tool_use_blocks)   # 병렬
    for env,tu in results: emit tool_end(tu); (emit card if env.card_type)
    messages.append(user=[tool_result blocks])
final = verify_and_finalize(messages)            # 수치 critic
```
종료: `end_turn`→critic→finalize · 마지막 step `tool_use`→`tool_choice:{none}` 강제 final · 빈 tool 배치→abstention 주입.

**SSE 계약**(`types.ts`/`eventHandlers.ts` 락 확인): 9 이벤트(thinking/plan/tool/tool_end/text/card/map_cmd/suggestion/done) + 5 카드(summary/compare/recommend/risk/simulation). `plan` 은 첫 tool 배치에서 합성(intent=tier 라벨, steps=tool reason), tool 0개면 skip. `card` 는 tool_end 직후 envelope.card_type 기반. `map_cmd` 는 `chat.py` 가 기존대로 방출. **`chat.py` 변경은 1줄**: `run_agent` → `get_runner(settings.agent_mode)`(신규 `agent/__init__.py`).

### Tool 통일 schema + envelope
- `tools/registry.py` `ToolMeta` 에 `input_schema: dict` + **LLM-facing `description`**(trigger 조건 명시). `tools/schemas.py`(스키마+한국어 설명) · `tools/definitions.py::build_tool_definitions()`(name 정렬 → prompt-cache 안정). `pae` 는 신규 필드 무시(가산적).
- `tools/envelope.py::ToolEnvelope{data, units, source, quarter, truncated, card_type?, card_data?, error?, needs_category?}` + `llm_view()`(units+quarter 포함 compact JSON). numeric grounding·abstention·card·citation 4 소비자 단일화.
- `tools/adapt.py::to_envelope(name, raw)` — tool 모듈은 현재 dict 그대로 반환, 루프가 wrap. 10항목 truncation(`actor._TRUNCATABLE_KEYS`) 이동. legacy actor 는 raw dict 유지.
- **`daily_avg` 단위버그**: envelope 에서 `quarter_total_pop`(`units` 명시)로 노출, LLM view 에서 오해소지 `daily_avg` 제거 → "하루 평균" 날조 불가. `district_summary._format_population` 문자열 교정. `numeric_sanity._TOOL_SCALAR_FIELDS` 반영.
- **카드 재부착(A안)**: envelope.card_type 있으면 tool_end 직후 `card` 방출(현 actor 동일).

### 신규 search/analyze (선행순서: 3c→3b→3a→multi-hop 자동발현)
- **3c repo+SQL** (`protocols.py` + `real/analytics.py` + mock 쌍): `AnalyticsRepository{rank_districts, search_districts, district_features, percentile_for}`. `DataAccess`+factory 배선(USE_MOCK DB-less 유지). Alembic materialized view `district_features`(1 상권×분기, 기존 sales/stores/floating join, `monthly_sales=SUM/3`·`pop_2030_ratio`·`franchise_ratio` + index). ETL 말미 `REFRESH MATERIALIZED VIEW CONCURRENTLY`. **`percentile_for` 가 실 `percentile_cont` 로 mock benchmarks 대체**(MV 미갱신→빈 envelope→abstain).
- **3b rank/aggregate** (`tools/rank_districts.py`·`aggregate_metric.py`): category 는 `category_resolver`. **6번째 card type 없음** → `card_type=None`, 모델이 text 서술 후 상위 ≤3 을 `compare_districts` 로 기존 compare 카드 렌더.
- **3a 의미/패싯 검색** (`tools/search_districts.py`): MV 위 구조적 facet 필터(임베딩/pg_trgm 아님 — 우선 문구가 수치 facet 으로 분해; 이름 fuzzy 는 `entity_matching` 커버). LLM 이 NL→facet dict 분해(input_schema enum 으로 컬럼 날조 차단). "뜨는/성장"→MV 2분기 QoQ.
- **multi-hop**: 실제 agent 루프이므로 코드 없이 발현 — envelope `llm_view` 가 연쇄 필드(업종코드 등) 노출하면 충분.

### 가드 재anchoring (프롬프트 패치 → 구조화)
- **(a) 자동 abstention**: `guards.classify_evidence(envelopes)` → 전량 empty/error 시 다음 turn 직전 `role:"system"` mid-conversation 메시지로 `ABSTENTION_PROMPT_ADDENDUM_EMPTY` 주입(미지원 모델 `<system-reminder>` fallback).
- **(b) 수치 critic(정확성 핵심)**: `guards.verify_and_finalize` 가 `numeric_sanity.evaluate_response` 를 전체 envelope 합집합 대상으로 확장. match_rate 낮으면(≥4 수치) **1회 교정 재질의**(`role:"system"` 미매칭 수치 + ground-or-drop + `tool_choice:none`). 현 "로깅만" → "done 전 1회 교정".
- **(c) sanitizer**: `_XMLTagSanitizer`/`_ToolTagSanitizer` → `agent/utils/text_sanitizers.py` 이전, 양 경로 공유.
- **(d) out_of_scope**: `router.py` 가 LLM 호출 전 regex+`STRONG_TOP1_MIN` 게이트 → TRIVIAL 즉시 방출(0 LLM/tool). greeting 동일.
- **(e) units 앵커**: 매출 월환산·유동인구 재분할금지를 envelope `units` 문자열로 이동. system 은 "수치의 units 를 따르라" 한 줄.

### Tiered (`config.py` 추가)
`agent_mode`+`"agentic"` · `agentic_gate_model="claude-haiku-4-5"` · `agentic_deep_model="claude-opus-4-8"` · `agentic_simple_effort="low"`/`agentic_deep_effort="high"` · `agentic_tool_budget_simple=2`/`_deep=8`. TRIVIAL(0 LLM, router regex) · SIMPLE(haiku/budget2) · DEEP(opus/effort high/budget8/풀 critic; 옵션 Task Budget). MV tool 은 `services/singleflight` coalesce, tool+system 정렬 후 `cache_control`.

**변경/신규 파일 요약**: `agent/loop/*`(신규 7) · `agent/__init__.py`(get_runner) · `api/routes/chat.py`(1줄) · `config.py` · `agent/tools/{registry,schemas,definitions,envelope,adapt,rank_districts,aggregate_metric,search_districts}.py` · `repositories/{protocols, real/analytics, mock/analytics, data_access}.py` · `alembic/versions/xxxx_district_features_mv.py` · `agent/utils/{text_sanitizers,numeric_sanity}.py` · `data/etl/runner.py`(MV refresh).

## Checklist

- [ ] **P0**: `agent/__init__.py::get_runner(mode)` + `chat.py` 1줄 교체 + `config.py` `agentic_*`/`"agentic"`. `pae` 경로 byte-identical 회귀 0
- [ ] **P1**: `tools/{envelope,schemas,adapt,definitions}.py` + `ToolMeta`(input_schema/LLM description) 확장. 9 tool 어댑터. `daily_avg`→`quarter_total_pop`(adapter+summary 문자열+numeric_sanity). 단위테스트(envelope shape/units/truncation/card_type)
- [ ] **P2**: `loop/{runner,agent_session,router,sse_emitter,llm_client,guards,suggestions}.py`. `mock` provider canned tool_use 우선. `types.ts` 대조 SSE parity(9 이벤트 키 일치)
- [ ] **P3**: `AnalyticsRepository`+`real/analytics.py`+mock+`DataAccess`. Alembic `district_features` MV + index. `percentile_for`→benchmarks 대체. `rank_districts`/`aggregate_metric`/`search_districts`. ETL refresh 단계
- [ ] **P4**: abstention mid-conv 주입 · critic 재질의 · sanitizer 이전 · out_of_scope router 게이트 · units 앵커. numeric_sanity 다-envelope 확장
- [ ] **P5**: prod 1인스턴스 `agentic` cutover. ring0~3 + 43 시나리오 `agentic` 모드 재실행(고정-plan assert → "≥1 grounded tool + DB 일치"). PAE 고정-plan 테스트 4종 재표현
- [ ] `cd server && ruff check --fix . && ruff format .` PASS · `cd frontend && npx tsc --noEmit` 0 error(프론트 무변경 확인)
- [ ] backend pytest 전체 회귀 0 (신규 P1~P4 단위 + 기존 132 baseline)

## 재검토 (Self-Review Gate)

- [ ] **엣지**: SSE `plan` 합성 — LLM 이 tool 0개로 직답(SIMPLE)할 때 `plan` skip 이 프론트 agentStep 표시를 깨지 않는지(`eventHandlers.plan` 은 intent+steps 만 필요)
- [ ] **엣지**: `compare` 카드 — rank 결과를 `compare_districts` 로 렌더 시 `data.district_codes`+`data.districts` shape 유지(eventHandlers 가 compareList 동기화에 사용)
- [ ] **엣지**: prompt-cache 무효화 — tool 목록 비정렬/모델 교체/system 변동 시 cache miss. tool name 정렬·tier별 모델 고정·system frozen 확인(`feedback` 없음, claude-api prompt-caching 규칙)
- [ ] **엣지**: mid-conversation system 미지원 시 `<system-reminder>` fallback 경로 — Gemini 게이트/Anthropic 양쪽 테스트
- [ ] **엣지**: MV staleness — refresh 전 빈 MV → rank/search 빈 envelope → abstain(false 수치 아님) 확인. ETL 주입 worker=0 류 재발 방지(`project_data_integrity_2026-06-25` 게이트와 정합)
- [ ] **엣지**: Opus 4.8 tool 과소호출 — `description` trigger 문구 없을 때 SIMPLE 이 tool 0개로 직답해 환각하는지. trigger 명시 + DEEP 강제경로 점검
- [ ] **Memory 교훈**: SSE 캡처+DB GT 병행(`feedback_sse_hallucination_needs_db_gt`) · 컨테이너 live inspect(`feedback_stale_container_vs_source`) · `temperature` 제거 미반영 시 400(claude-api) · `NEXT_PUBLIC_API_URL` :8000 (`feedback_next_public_api_url_frontend_port`)
- [ ] **타 Plan 충돌**: out_of_scope(2026-04-29) 가드는 router TRIVIAL 로 이식 — 동작 동등성 유지 · `langfuse-l2-token-cost-eval` 의 trace wiring 과 runner Langfuse 블록 정합 · data-reliability 게이트(`runner._validate_data`)는 MV 신뢰 전제

## Scenario (E2E Ring Mapping)

- **Ring 0 (preflight)** `R0-AGENTIC-BOOT` — `USE_MOCK=1`·`llm_provider=mock`·`agent_mode=agentic` 부팅, DB 연결 0 으로 greeting/summary/compare 동작
- **Ring 1 (feature)** `R1-AGENTIC-SSE-PARITY` — 질문군별 `/api/chat` SSE 9 type 전수 + `types.ts` 키 일치(thinking/plan/tool/tool_end/text/card/suggestion/done). 5 카드 렌더
- **Ring 1** `R1-SEARCH-RANK` — "유동인구 많은 동네 top 5"·"프랜차이즈 낮고 폐업률 낮은 동네" → `rank_districts`/`search_districts` 호출 + 결과 DB MV 대조
- **Ring 2 (journey)** `R2-MULTIHOP` — "강남 1위 업종 알려줘 → 그 업종 강한 다른 동네 → 비교" 3턴 단일세션 → tool 연쇄(`get_store_info`→`rank_districts`→`compare_districts`), 최종 compare 카드
- **Ring 3 (negative)** `R3-NUMERIC-GROUNDING` — 전 수치 인용이 envelope/DB 와 자릿수 일치, 데이터 없는 질의는 abstain, S7 coref 후속질문 tool 강제 + 날조 0
- **Ring 3** `R3-OUT-OF-SCOPE` — 부산/제주 → router TRIVIAL 거부(0 LLM/tool), tailored suggestion 1회

## Pass 반복 (Iteration Plan)

- **Pass 1 (기본)**: P0~P2 — 플래그 seam + envelope/schema + 루프(mock provider). `R0-AGENTIC-BOOT` + `R1-AGENTIC-SSE-PARITY` 정적 PASS, pytest 회귀 0
- **Pass 2 (역량+엣지)**: P3~P4 — search/analyze + 가드. `R1-SEARCH-RANK`·`R2-MULTIHOP`·`R3-NUMERIC-GROUNDING`·`R3-OUT-OF-SCOPE`. critic 재질의·abstention·units 앵커 엣지 케이스
- **Pass 3 (성능+cutover)**: P5 — Real 스택 `agentic` 라이브, tier별 토큰·TTFT vs PAE baseline(Langfuse), 43 시나리오 재실행. Fail→수정→재실행 루프
- 각 Pass 후 Scenario 재실행, Fail 시 수정→재실행

## Agent 모델 선택

- **설계**: opus — 루프 종료조건·SSE 합성·가드 재anchoring·MV 스키마가 다수 기존 모듈과 상호작용, 심층 추론 필요
- **구현**: sonnet — Design 이 파일·시그니처 수준으로 확정(어댑터/envelope/tool 은 기계적), 단 native SDK 루프·prompt-cache 배치는 opus 리뷰 1회 권장
- **검증**: haiku — SSE type 카운트·수치 DB 일치·tool 호출 유무 Pass-Fail 은 기계적
- 위험도는 P2 루프(SSE 계약 drift)·P3 MV(데이터 정합)에 집중 → 두 Phase 만 opus 페어리뷰

## Validation

- **수동**: `agent_mode=agentic` 로 `docker compose restart backend` 후 curl SSE — `feedback_qa_browse_unstable_use_sse` 관례대로 browse 미사용. `feedback_stale_container_vs_source` 대로 `docker exec find` 로 소스 반영 확인
- **DB ground truth**: `docker exec ...-db-1 psql -U marketscope` 로 MV(`district_features`) + 원 테이블 대조, 인용 수치 자릿수 일치(`feedback_sse_hallucination_needs_db_gt`)
- **자동**: backend pytest(P1~P4 단위 + 기존). `cd frontend && npx tsc --noEmit`(프론트 0 변경 증명). E2E 는 `npm test` 를 `agent_mode=agentic` 로 — ring0~3 + 43 시나리오
- **비용/지연**: Langfuse `model_request_end.model_usage` 로 tier별 토큰·TTFT vs PAE baseline. `NEXT_PUBLIC_API_URL=:8000` 확인

## Metadata

- 작성일: 2026-06-26
- 작성자: Claude Code (plan mode → docs/plan 이관)
- 분류: infra (아키텍처 전면 개편, 고위험 — 플래그 뒤 단계 cutover)
- 선행/병행: `langfuse-l2-token-cost-eval`(trace wiring) · `heatmap-singleflight-reintroduce`(singleflight 재사용) · `data-reliability-2026-06-25`(MV 신뢰 전제 게이트)
