# Agent Architecture — v2 Agentic Loop + Trust Kernel

> 현행 기본 실행 경로는 **v2 모델주도 function-calling 루프 + Trust Kernel** (`server/server/agent/loop/`). 레거시 **PAE(Planner-Actor-Evaluator) 그래프**(`agent/graph.py`)는 삭제되지 않은 현행 코드지만 **Mock 폴백 + 롤백 스위치 전용**이다 (§8). 두 경로는 동일한 `run_agent` 시그니처·SSE 계약으로 스왑 가능하다.

## 1. 디스패치 (`agent/runtime.py`)

```python
def _use_v2() -> bool:
    return settings.agent_loop_version == "v2" and settings.llm_provider != "mock"
```

- **단일 진입점**: `agent/runtime.py::run_agent` — chat.py 는 이 함수만 import.
- `_use_v2()` True → `agent/loop/engine.py::run_agent` (v2 루프) / False → `agent/graph.py::run_agent` (레거시 PAE).
- **`agent_loop_version` 기본값 = `"v2"`** (config.py, env `AGENT_LOOP_VERSION`). `"pae"` 로 내리면 롤백.
- **mock 프로바이더는 항상 PAE 폴백** — mock 의 FakeListChatModel 이 tool-call 을 못 하므로 Mock E2E 는 PAE 경로로 돈다.
- 관측 필드 `agent_mode`(`/api/health/detail` 응답·Langfuse trace 메타데이터)는 `runtime.py::effective_loop_version()` 이 반환하는 **실효 서빙 루프**(`v2`|`pae`, mock 폴백 반영)를 보고한다. 구 설정 `agent_mode` 는 제거됨 (2026-07-05).

## 2. v2 루프 구조 (`agent/loop/engine.py`)

```
 START  (user message + 선택 상권 컨텍스트)
   │   SystemMessage(LOOP_SYSTEM_PROMPT + 컨텍스트) + 히스토리 최근 6턴 + HumanMessage
   ▼
 ┌────────────── 모델 턴 (budget governor 내 반복) ──────────────┐
 │  ainvoke_with_fallback(messages, tool_schemas | None)         │
 │    ├─ tool_calls 없음 (또는 마지막 턴) → 최종 prose ──────────┼──▶ Trust Kernel (§3)
 │    └─ tool_calls 있음 → 순차(직렬) 실행                        │
 │         `tool` → execute_fc_tool → (card 매핑 시 `card`)       │
 │         → `tool_end` + ToolMessage + fact_pool 축적            │
 │         abstain 호출 시 해당 라운드 후 즉시 break               │
 └────────────────────────────────────────────────────────────────┘
   ▼
 Trust Kernel 집행 → `text`(90자 청크) → `suggestion` → `done`(+trace_id)
```

- 마지막 허용 턴(또는 budget 초과)은 **도구 없이 prose 강제** — 루프가 항상 텍스트로 종결.
- 도구 결과는 `fact_pool` 에 **절단 없이 원본 저장** (pool 은 LLM 미전송 — 토큰 비용 0, Trust Kernel 바인딩 전용).
- PAE actor 의 `asyncio.gather` 병렬과 달리 v2 는 한 모델 턴의 tool_calls 를 **순차 실행**한다 (모델이 한 턴에 여러 도구를 요청하는 방식으로 병렬성 확보).

### Budget governor (PAE `agent_max_rounds` 대체)

| config 필드 | 기본값 | 의미 |
|---|---|---|
| `agent_loop_max_iterations` | 6 | 모델 턴 상한 (초과 직전 턴 = 강제 finalize) |
| `agent_loop_max_tool_calls` | 12 | 요청당 도구 실행 총량 |
| `agent_loop_wall_clock` | 90.0s | 경과 시 강제 finalize |
| `llm_timeout_slow` | 60s | 모델 턴 1회 타임아웃 |

### 메타툴 3종 (`agent/loop/tools_fc.py` — 도메인 레지스트리 밖에서 로컬 처리)

| 툴 | 입력 | 역할 |
|---|---|---|
| `resolve_district` | `{name}` | 상권명 → 코드 (`detect_district_by_name`). 상권 미선택 일반질의를 가능케 하는 generality 표면. 성공 시 상권명이 suggestion 개인화에 사용됨 |
| `compute` | `{expression}` | AST 기반 안전 산술 평가기 (`eval()` 미사용, `+ - * / ** %` + 단항). 모델 암산 금지 — 결과값은 `computed` 리스트로 들어가 **바인딩 가능한 fact** 가 됨 |
| `abstain` | `{reason}` | "데이터 없음 / 서울 외" 1급 거부. engine 이 reason 을 채택해 정형 사과문 생성 |

- **도구 스키마 총 12개** = 도메인 9종(§5) + 메타 3종. OpenAI-function 형태 — Anthropic·Gemini 양쪽 `bind_tools` 호환.
- **category_code 정규화**: `execute_fc_tool` 이 `category_code` 인자가 `^CS\d+$` 형태가 아니면 CategoryResolver 로 resolve ("카페"→CS100010류), 실패 시 원값 유지.
- **교정 턴 메타발화 가드**: `_is_answer_shaped(text)` — 숫자 포함 or 120자 이상일 때만 교정 결과 채택 ("...검토하겠습니다" 류 유출 차단).

## 3. Trust Kernel (`agent/loop/trust.py` + engine.py 집행부)

- **불변식**: 답변의 모든 수치 주장은 도구 반환값(또는 compute 파생값)에 `trust_numeric_tolerance`(기본 **0.05 = ±5%**) 이내로 바인딩되어야 한다. 모델이 기억으로 만든 숫자는 매칭 fact 가 없어 *unbound* 로 검출된다 — 구조적 anti-fabrication 보장.
- 기반: `agent/utils/numeric_sanity.py` 의 한국어 숫자 추출(조/억/천만/… 복합 단위) + `match_numbers_to_tools` 재사용. 작은 수(순위·%·소량 카운트)는 스코어링 임계로 필터.

**집행 흐름** (단계적 — 과잉 방어의 가용성 손실 방지):

1. `find_unbound_numbers` + `find_scale_errors` 로 최종 prose 검사.
2. 검출 시 (abstain 아님) → `thinking "수치 검증 중..."` 방출 + `corrective_instruction`(unbound raw 최대 8개 + 스케일 교정 value_hints 최대 5개) 을 붙여 **prose 전용(도구 없음) 교정 재호출** 1회 → `_is_answer_shaped` 통과 시만 채택.
3. 재검사 후 잔존 시 `should_fallback(unbound, scored_total)` 판정 = **잔존 unbound ≥ 3 AND 전체 스코어 수치의 ≥ 50%** 일 때만:
   - True → `grounded_fallback`: fact_pool 을 코드측 고정 라벨로 평탄화한 결정론적 전체 대체(최대 10줄, 모델 산출물 0%). 라벨 스칼라가 없으면 — **카드가 이미 발행된 경우 abstention 금지**("핵심 지표는 위 카드에…"), 아니면 abstention 문구.
   - False → `mask_unbound`: draft 보존 + 해당 수치만 `"[미확인]"` 치환 + 각주 1회.
4. 최종 텍스트가 공백이면 `grounded_fallback`.

- **스케일 오기 검출**: "145만 원" ↔ 도구값 14,503,839원 같은 ×10/×100 자릿수 오기를 동일 unit typed scalar 와 매칭해 검출, 교정 프롬프트에 정확값 힌트로 전달.

## 4. LLM 체인 (`agent/loop/models.py`)

v2 는 **역할별 모델 분리가 없다** — 단일 tool-calling 모델을 per-invoke fallback chain 으로 호출:

| 순서 | provider / model | 조건 |
|---|---|---|
| 1 | anthropic / `settings.anthropic_model` (기본 `claude-sonnet-4-6`) | ANTHROPIC_API_KEY 존재 시 (tool_use 정확도 우선) |
| 2 | gemini / `settings.gemini_model_pro` (기본 `gemini-2.5-pro`) | GOOGLE_API_KEY 존재 시 |
| 3 | gemini / `settings.gemini_model_flash` (기본 `gemini-2.5-flash`) | 〃 |

- 모델 ID 는 전부 settings 유래(env-overridable) — 하드코딩 ID 은퇴 사고(2026-06 dead model) 재발 방지 설계.
- 파라미터: temperature 0.3, max tokens 4096. 실패 시 다음 후보로 진행, 전 후보 실패 시 마지막 예외 re-raise.
- 모듈 레벨 CircuitBreaker `"loop_llm"` (실패 임계 5회 / 회복 60s — `circuit_breaker_*` settings 주입).
- 기본 `llm_provider` 는 config 상 `"gemini"` 이나, 체인은 **키 존재 기준**이라 Anthropic 키가 있으면 Claude 가 1순위다 (현 운영 환경은 `.env` 로 anthropic 사용).

## 5. Tool 레지스트리 (`agent/tools/registry.py`)

`@register_tool(name, *, emoji, card_type=None, progress_label, done_label)` 로 자체 등록. `card_type` 미지정 = 카드 미발행 (LLM 컨텍스트 전용).

| Tool | 입력 | 출력 | Card | 사용 기능 |
|---|---|---|---|---|
| `get_district_summary` | district_code | 4개 병렬 집계 (유동인구·매출·점포 + district meta) | `summary` | F03 |
| `get_floating_population` | district_code, quarter? | 시간대/성별/연령 | — (카드 없음) | F03, F05, F06 |
| `get_estimated_sales` | district_code, category? | 분기매출 → 월 환산 | — (카드 없음) | F03, F04, F09 |
| `get_store_info` | district_code, category? | 점포수 / 개폐업 / 프랜차이즈 | — (카드 없음) | F03, F04, F07 |
| `get_store_history` | district_code | 안정성 스코어 / 생존기간 | `risk` | F08 |
| `get_population_info` | district_code | 상주/직장 인구 | — (카드 없음) | F03, F07 |
| `compare_districts` | district_codes[2..3] | 지표 비교 + winners | `compare` | F05 |
| `recommend_business` | district_code, budget?, preference? | Top 5 + 55~95 밴드 점수 + 면책 | `recommend` | F07 |
| `simulate_revenue` | district_code, category, unit_price? | p25/avg/p75 + 서울 비교 | `simulation` | F09 |

- 발행되는 card_type 은 정확히 **5종** = `summary` / `risk` / `compare` / `recommend` / `simulation` — 프론트 `CARD_REGISTRY` 5키와 1:1 일치.
- **내부 헬퍼 (등록 X)**: `get_district_benchmarks(district_type)` — `district_summary` / `store_history` / `numeric_sanity` 가 직접 import. 레지스트리에 없으므로 모델이 단독 호출할 수 없다.

> ⚠ 매출 단위 주의: `estimated_sales.monthly_sales` DB 컬럼은 서울 열린데이터 `THSMON_SELNG_AMT` = **분기 누적(원)**. Repository 에서 `// MONTHS_PER_QUARTER` 로 **월 환산** 후 응답.
> ⚠ 유동인구 집계 필드는 `quarter_total`(분기 시간대 합계) — '일평균' 아님. 카드 키는 `quarterTotal` (구 `dailyAvg` 는 legacy fallback 만 잔존).

## 6. SSE 이벤트 계약 (경로별 방출 집합)

| 이벤트 | v2 engine | PAE graph | chat.py (양 경로 공통) |
|---|---|---|---|
| `thinking` / `tool` / `tool_end` / `card` / `text` / `suggestion` / `done` | O (7종) | O | greeting 정규식 단축 시 `text`+`suggestion`+`done` 직접 방출 |
| `plan` | **X** | O (planner plan 有 시) | X |
| `warning` | **X** | O (respond numeric_sanity 경고 시 1회) | X |
| `map_cmd` | X | X | **O — 유일한 방출처** (district 해석 성공 시 에이전트 실행 전 1회) |
| `done` 부가 payload | `trace_id` | `trace_id` + `quality_flags` + `quality_match_rate` | — |

- v2 의 `thinking` 은 "질문 분석 → 데이터 수집 → 결과 분석 → (필요 시) 수치 검증" 진행 표시를 겸한다 (비스트리밍 침묵 구간 완화).
- 프론트 `SSEEvent` 유니온은 위에 더해 클라이언트 전용 `error` 를 포함해 10종.

## 7. 세션 / 히스토리 (`agent/history.py` + chat.py 세션 저장소)

- config: `max_history_turns=10` / `history_content_limit=300` (assistant 응답 300자 truncate 후 저장 — 토큰 비용 절감).
- 인메모리 세션 저장소 (chat.py): TTL 30분, `session_max_count=10000`, 세션당 `session_memory_limit_bytes=512KB`, 초과 시 oldest evict.
- **v2 루프는 히스토리 중 최근 6턴만** 프롬프트에 넣는다 (chat.py 가 10턴을 넘겨도 engine 이 재절단).
- chat.py 상권 자동감지: 명시 코드 없을 때 `detect_district_by_name` + `STRONG_TOP1_MIN`(≥0.70) 게이트 + 제외어("말고/대신/빼고/제외") 필터, 미스 시 세션 last_district 폴백 — "거기서 카페는?" 같은 follow-up 지원.

## 8. 레거시 — PAE 그래프 (`agent/graph.py`, Mock 폴백 / 롤백 스위치 전용)

> `AGENT_LOOP_VERSION=pae` 또는 `llm_provider=mock` 일 때만 실행된다. Mock E2E 는 항상 이 경로로 돈다. 세부는 코드 참조 — 여기서는 요약만 유지.

- **구조**: LangGraph 커스텀 그래프 `PLANNER → ACTOR → EVALUATOR → RESPOND`. greeting / clarification 은 그래프 초입에서 단락(direct 응답). Evaluator `insufficient` 시 Planner 재진입, 상한 `agent_max_rounds=3`.
- **Planner** (`agent/nodes/planner.py`): rule-first intent 분류 — `agent/config/intents.yaml` 의 **8개 intent** (greeting / out_of_scope(서울 외 거부) / simulation / comparison / risk / recommendation / category_analysis / summary, intent 당 정규식 1개 + `non_summary_overrides`·`follow_up_markers` 보조 패턴). 규칙 미스 시 LLM fallback. 복수 상권·업종 entity 추출(CategoryResolver 위임), 의도별 Tool plan 프리셋 생성.
- **Actor** (`agent/nodes/actor.py`): plan 을 의존성 layer 로 위상 정렬 후 layer 내 **`asyncio.gather` 병렬 실행**. Tool 1회 `asyncio.timeout(settings.tool_execution_timeout)`(15s) + transient DB 에러만 2회 재시도(fixed 0.5s). card_type 매핑 시 `card` 이벤트 발행.
- **Evaluator** (`agent/nodes/evaluator.py`): `evaluator_skip_simple=true` 면 단순 케이스 rule 판정, 아니면 flash LLM 으로 충분성 판정 + suggestion 생성. LLM 타임아웃 `llm_timeout_fast`(15s).
- **Respond** (`agent/nodes/respond.py`): 최종 응답 토큰 스트리밍 + post-hoc `numeric_sanity` 검사(경고 시 `warning` 이벤트). Tool 이름 누출 sanitizer 포함.
- **역할별 모델** (`graph.py::_create_llm`): planner 는 Anthropic 키 유효 시 `claude-sonnet-4-6`(하드코딩), gemini provider 에서 respond/default → `gemini_model_pro`, planner/evaluator → `gemini_model_flash`. tenacity 2회 재시도 + 지수 백오프 1~4s + CircuitBreaker `"llm"`.
- **상태** (`agent/state.py::AgentState`): 주요 필드 = `user_intent` / `intent_confidence` / `referenced_districts` / `plan: list[ToolPlanStep]` / `tool_results: dict[str, dict]` / `execution_round` / `card_emissions` / `response_mode`(`"direct" | "tool_assisted" | "clarification_direct" | "greeting_direct"`) / `quality_flags`. SSE 큐는 상태 밖(graph.py)에서 관리 (`sse_queue_maxsize=256`).

## 9. 관측 (Langfuse)

- `.env` 에 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` 설정 시 활성화 (둘 다 필요).
- **양 경로 모두 L2 wiring 완료** (2026-07-06 ops-hardening): 콜백 + `metadata`(session hash/request_id/agent_mode) + `tags`(`marketscope.{v2|pae}` — `effective_loop_version()` 동적) + `run_name` 을 전 LLM 호출에 전달. v2 는 `engine.py` 의 `lf_kwargs` **조건부** 전달(handler None 이면 빈 dict — 기존 호출과 동일), PAE 는 `graph.py` 가 `astream` config 에 주입. `done` 이벤트에 `trace_id` 동봉 → 프론트 FeedbackRow 가 `/api/feedback/score` 로 score proxy (F12 L1).
- **v2 trace 동봉물** (`engine.py` finalize, `lf_trace_id` 없으면 전부 no-op): 도구 실행마다 `attach_tool_span`(as_type=tool, args/duration_ms/error — 결과 본문 미탑재) · 종료 시 `attach_summary_observation(name="marketscope.v2.summary")` 19키 metadata(iterations/tool_calls/trust_* 플래그/numeric_match_rate 등) · **score 6종** = `numeric_match`(scored>0 시) / `tool_error_rate`(calls>0 시) / `abstention_triggered` / `trust_corrective_applied` / `trust_fallback_triggered` / `trust_masked_count`. 앞 3종은 PAE 와 이름 공유. PAE summary 는 기존 `marketscope.pae.summary` 유지.
- **샘플링 단일 게이트**: `should_sample()` 만 적용 — SDK `sample_rate` 는 이중 샘플링(done 에 trace_id 를 동봉했는데 SDK 가 trace 를 드랍하는 고아)을 만들어 제거 (`langfuse_tracer.py::_get_client`).
- **flush offload**: 양 경로 모두 `await asyncio.to_thread(_lf_flush, ...)` — 동기 flush 의 이벤트 루프 블로킹 제거.
- 실패/비활성 시 handler=None 으로 graceful degrade (trace 없이 정상 동작). 무음사망 가시화: `/api/health/detail` `langfuse` 블록(enabled/tracer_valid/client_initialized/sampling_rate) + `/metrics` `langfuse_trace_missing_total` — 진단 절차는 [ops/runbook.md](../ops/runbook.md) 참조.

## 10. 확장 포인트

- **새 Tool 추가**: `agent/tools/<name>.py` 작성 → `@register_tool` 데코레이터 → v2 용 스키마를 `agent/loop/tools_fc.py::tool_schemas()` 에 추가 (PAE 경로도 쓰려면 `intents.yaml` plan 프리셋에 매핑).
- **새 Intent (PAE 전용)**: `agent/config/intents.yaml` 에 패턴 + Tool plan 프리셋 추가. v2 는 intent 분류가 없고 모델이 도구를 직접 선택한다.
- **LLM 교체**: `settings.llm_provider` + `anthropic_model` / `gemini_model_pro` / `gemini_model_flash` env 오버라이드. v2 체인 순서는 `loop/models.py::_candidate_chain`.
- **롤백**: `AGENT_LOOP_VERSION=pae` — 코드 배포 없이 레거시 그래프로 전환.
