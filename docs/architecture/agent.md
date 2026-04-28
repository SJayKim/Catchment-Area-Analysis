# Agent Architecture — Planner · Actor · Evaluator · Respond

> LangGraph 기반 커스텀 그래프. 기존 `create_react_agent` 블랙박스를 **PAE(Planner-Actor-Evaluator)** 로 전환 완료. ReAct 경로는 레거시이며 기본값은 `agent_mode=pae`.

## 1. 그래프 구조

```
            ┌──────────────────────┐
            │       START          │  (user message + context)
            └──────────┬───────────┘
                       ▼
               ┌──────────────┐
               │   PLANNER    │  intent 분류, plan 생성
               └──────┬───────┘
                      │
        ┌─────────────┼──────────────┐
        ▼             ▼              ▼
   (greeting)     (plan 有)      (fast respond)
     END            │              END
                    ▼
               ┌──────────────┐
               │    ACTOR     │  병렬 Tool 실행 + Card 발행
               └──────┬───────┘
                      ▼
               ┌──────────────┐
     ┌────────▶│  EVALUATOR   │  충분성 판정 + suggestion
     │         └──────┬───────┘
     │                │
     │     ┌──────────┴──────────┐
     │     ▼                     ▼
     └─(insufficient,        (sufficient)
       max 3 rounds)             │
                                 ▼
                         ┌──────────────┐
                         │   RESPOND    │  LLM 스트리밍 최종 응답
                         └──────┬───────┘
                                ▼
                               END
```

| 루프 상한 | 값 | 출처 |
|---|---|---|
| Planner ↔ Evaluator 재진입 | 3회 | `settings.agent_max_rounds` |
| Tool 1회 실행 | 15s | `settings.tool_timeout` |
| LLM fast (planner/evaluator) | 15s | `settings.llm_timeout_fast` |
| LLM slow (respond 스트리밍) | 60s | `settings.llm_timeout_slow` |

## 2. 상태 정의 (`agent/state.py`)

```python
class AgentState(TypedDict, total=False):
    messages: list[BaseMessage]          # 세션 히스토리 (최근 N turn)
    session_id: str
    district_code: str | None
    district_name: str | None
    selected_category_code: str | None
    user_intent: str                     # summary/comparison/recommendation/risk/...
    confidence: float                    # planner 신뢰도
    referenced_districts: list[str]      # "홍대랑 비교" 등에서 추출
    referenced_category: str | None
    plan: list[ToolPlanStep]             # Actor 실행 계획
    tool_calls: list[dict]
    tool_results: list[dict]
    cards: list[dict]                    # Actor 가 발행한 card payload
    suggestions: list[str]
    map_commands: list[dict]
    rounds: int
    response_mode: str                   # "stream" | "fast"
    event_queue: asyncio.Queue           # SSE 이벤트 큐
```

## 3. 노드별 책임

### 3.1 Planner (`agent/nodes/planner.py`)

1. **Intent 분류** (rule-first, LLM-fallback)
   - 규칙: `agent/config/intents.yaml` (50+ 패턴, Greetings/Summary/Comparison/Recommendation/Risk/Category/Simulation/Heatmap/ReportExport)
   - LLM: 신뢰도 낮거나 규칙 매칭 실패 시 Claude Sonnet 4 (`agent/prompts/planner.py`) → Gemini flash fallback
2. **Entity 추출**
   - 복수 상권 (`"강남이랑 홍대"`): 모든 상권명 스캔
   - 업종 (`"카페"`, `"한식"`): `CategoryResolver` 에 위임
3. **Plan 생성**
   - `ToolPlanStep{name, input, depends_on?}` 리스트
   - 의도별 프리셋 (summary → 4 Tool 병렬, comparison → compare_districts 단일, …)

Greeting intent 는 그래프를 건너뛰고 즉시 END (`<1s` 응답).

### 3.2 Actor (`agent/nodes/actor.py`)

1. Plan 을 **의존성 layer** 로 그룹핑 (DAG → 위상 정렬)
2. 한 layer 내 Tool 을 **`asyncio.gather` 병렬 실행**
3. 각 Tool 마다:
   - `tool` SSE 이벤트 발행 (`progress_label`, `icon` 포함)
   - 15s 타임아웃 + 2회 재시도 (transient DB 에러만, fixed 0.5s backoff)
   - 결과 10항목 초과 시 truncate
   - `tool_end` 이벤트 발행
4. `registry` 기반 `card_type` 매핑 → `card` SSE 이벤트
5. 지도 조작이 필요하면 `map_cmd` 이벤트 방출

### 3.3 Evaluator (`agent/nodes/evaluator.py`)

- **Fast path (rule)**: `evaluator_skip_simple=true` 이고 1 round + 전체 성공/실패 일관 시 LLM 생략
- **Slow path (LLM)**: Gemini flash 로 Tool 결과 충분성 + 누락 판단 → `sufficient | insufficient`
- `suggestion` 생성: intent 별 프롬프트 (`agent/prompts/evaluator.py`)
- `insufficient` 시 `rounds++` 후 Planner 로 복귀 (max 3)

### 3.4 Respond (`agent/nodes/respond.py`)

- Gemini pro (또는 Claude Sonnet) 로 최종 응답 **스트리밍**
- 토큰 청크를 `event_queue` 에 `text` 이벤트로 push
- 시스템 프롬프트 (`agent/prompts/system.py`): 한국어 상권 분석 컨설턴트 역할, 해석 가이드, 면책 조항
- Tool 결과는 요약된 형태로 컨텍스트에 주입 (raw dict 전달 시 토큰 낭비)

## 4. Tool 레지스트리 (`agent/tools/registry.py`)

`@register_tool(name, card_type, progress_label, done_label, description)` 로 자체 등록.

| Tool | 입력 | 출력 | Card | 사용 기능 |
|---|---|---|---|---|
| `get_district_summary` | district_code | 4 Tool 병렬 집계 | `summary` | F03 |
| `get_floating_population` | district_code, quarter? | 시간대/성별/연령 | `population` | F03, F05, F06 |
| `get_estimated_sales` | district_code, category? | 분기매출 → 월 환산 | `sales` | F03, F04, F09 |
| `get_store_info` | district_code, category? | 점포수 / 개폐업 / 프랜차이즈 | `store` | F03, F04, F07 |
| `get_store_history` | district_code | 안정성 스코어 / 생존기간 | `history` | F08 |
| `get_population_info` | district_code | 상주/직장 인구 | `population` | F03, F07 |
| `compare_districts` | district_codes[2..3], category? | 지표 비교 + AI 의견 | `comparison` | F05 |
| `recommend_business` | district_code, budget? | Top 5 + 점수 + 면책 | `recommend` | F07 |
| `simulate_revenue` | district_code, category, unit_price? | p25/avg/p75 + 서울 비교 | `simulation` | F09 |

> **내부 헬퍼 (등록 X)**: `get_district_benchmarks(district_type)` — `district_summary` / `store_history` / `numeric_sanity` 가 직접 import 해 사용. `@register_tool` 으로 등록되지 않으므로 Planner plan 에 단독으로 등장하지 않는다.

> ⚠ 매출 단위 주의: `estimated_sales.monthly_sales` DB 컬럼은 서울 열린데이터 `THSMON_SELNG_AMT` = **분기 누적(원)**. Repository 에서 `// MONTHS_PER_QUARTER` 로 **월 환산** 후 응답. `_enrich_sales` 키 불일치 버그는 2026-04-17 fix 완료.

## 5. 세션 히스토리 (`agent/history.py`)

- 세션당 최근 `history_max_turns=10` turn 유지
- 응답 텍스트는 `history_truncate_responses=300자` 로 trim 후 저장 (토큰 비용 절감)
- 인메모리 저장소, TTL 30분 (서버 재시작 시 유실)
- Planner 는 히스토리의 `referenced_districts` 를 우선 참조 ("거기서 카페는?" 같은 follow-up 가능)

## 6. LLM 프로바이더 전환

| 역할 | 기본 | Fallback |
|---|---|---|
| Planner | Claude Sonnet 4 (tool_use 정확도) | Gemini flash |
| Evaluator | Gemini flash (저비용) | — |
| Respond | Gemini pro (한국어 스트리밍) | Claude Sonnet |

- `_anthropic_valid` 플래그로 Anthropic 키 유효성 가드
- 2회 재시도 + 1~4s 지수 백오프
- Circuit Breaker 로 연속 실패 시 OPEN → degraded 응답

## 7. 관측 (Langfuse)

- `.env` 에 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` 설정 시 활성화
- 현재 graph 실행에 callback 주입 wiring 은 향후 계획 ([plan/business/commercialization-plan.md](../plan/business/commercialization-plan.md) 에서 Observability 항목)

## 8. 확장 포인트

- **새 Tool 추가**: `agent/tools/<name>.py` 작성 → `@register_tool` 데코레이터 → Planner intents.yaml 에 매핑
- **새 Intent**: `agent/config/intents.yaml` 에 패턴 + Tool plan 프리셋 추가
- **LLM 교체**: `settings.llm_provider` + 역할별 model 필드 수정
