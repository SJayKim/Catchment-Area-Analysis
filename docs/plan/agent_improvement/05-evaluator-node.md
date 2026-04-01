# 05. Evaluator 노드

> 도구 결과 충분성 판단 + 동적 후속 제안 생성

## 대상 파일

| 파일 | 작업 |
|------|------|
| `server/server/agent/nodes/evaluator.py` | **신규** — Evaluator 노드 |
| `server/server/agent/prompts/evaluator.py` | **신규** — Evaluator LLM 프롬프트 |

## 의존성

- 01-state-config (AgentState, EvaluationResult, config.evaluator_skip_simple)

## TODO

- [ ] `nodes/evaluator.py` 생성
  - [ ] Fast path: 규칙 기반 충분성 판단 (단순 의도 + 모든 도구 성공)
  - [ ] Slow path: LLM 기반 충분성 판단 (복합 의도 / 실패 있음)
  - [ ] 동적 후속 제안 생성 (`generate_proactive_suggestions`)
  - [ ] `evaluator_node(state: AgentState) -> dict` 함수
- [ ] `prompts/evaluator.py` 작성
  - [ ] 충분성 판단 기준
  - [ ] JSON structured output 스키마

## 상세 구현

### Fast Path (LLM 미사용)

```python
SIMPLE_INTENTS = {"summary", "comparison", "recommendation", "risk"}

def _fast_evaluate(state: AgentState) -> EvaluationResult | None:
    """단순 의도에서 모든 도구 성공 시 LLM 없이 판단."""
    if not settings.evaluator_skip_simple:
        return None
    if state["user_intent"] not in SIMPLE_INTENTS:
        return None
    if state["execution_round"] > 1:
        return None  # 2회차 이상은 LLM 판단

    planned_tools = {step["tool_name"] for step in state["plan"]}
    succeeded_tools = set(state["tool_results"].keys())
    failed_tools = set(state["tool_errors"].keys())

    if planned_tools.issubset(succeeded_tools) and not failed_tools:
        return {
            "sufficient": True,
            "missing_info": [],
            "proactive_suggestions": generate_proactive_suggestions(state),
            "reasoning": "모든 계획된 도구가 성공적으로 완료됨.",
        }

    if planned_tools.issubset(failed_tools):
        return {
            "sufficient": False,  # 전부 실패 → 재시도 또는 에러 응답
            "missing_info": [f"{t} 실패" for t in failed_tools],
            "proactive_suggestions": [],
            "reasoning": "모든 도구가 실패하여 데이터를 가져오지 못함.",
        }

    return None  # 일부 성공/실패 → LLM 판단 필요
```

### Slow Path (LLM 사용)

```python
async def _llm_evaluate(state: AgentState) -> EvaluationResult:
    """LLM으로 도구 결과 충분성 판단."""
    prompt = EVALUATOR_PROMPT.format(
        user_message=state["messages"][-1].content if state["messages"] else "",
        intent=state["user_intent"],
        tool_results_summary=_summarize_results(state["tool_results"]),
        tool_errors=state["tool_errors"],
    )
    # LLM 호출 → JSON 파싱
    # 반환: EvaluationResult
```

### 동적 후속 제안 생성

```python
def generate_proactive_suggestions(state: AgentState) -> list[str]:
    """의도와 결과에 기반한 맥락적 후속 질문."""
    intent = state["user_intent"]
    name = state["district_name"]
    suggestions = []

    if intent == "summary":
        suggestions = [
            f"{name}에서 뭐하면 좋을까?",
            f"{name} 리스크 분석해줘",
            "유동인구 시간대별로 보여줘",
            "다른 상권이랑 비교해줘",
        ]
        # 폐업률 높으면 리스크 강조
        summary = state["tool_results"].get("get_district_summary_tool", {})
        close_rate = summary.get("closeRate", {}).get("current", 0)
        if close_rate > 8.0:
            suggestions[1] = f"⚠ {name} 리스크가 높아 보여요 — 분석해볼까요?"

    elif intent == "comparison":
        suggestions = [
            "어떤 상권이 더 좋을까?",
            "추천 업종은 각각 어때?",
            "리스크도 비교해줘",
        ]

    elif intent == "recommendation":
        rec = state["tool_results"].get("recommend_business_tool", {})
        recs = rec.get("recommendations", [])
        if recs:
            top = recs[0]["category_name"]
            suggestions = [
                f"{top} 상세 분석해줘",
                f"{name} 리스크 확인해줘",
                f"다른 상권에서 {top}은 어때?",
                f"{top} 창업비용 알려줘",
            ]
        else:
            suggestions = [f"{name} 요약해줘", "다른 상권 추천해줘"]

    elif intent == "risk":
        suggestions = [
            f"{name} 추천 업종 알려줘",
            "안전한 업종은 뭐가 있어?",
            f"{name} 요약해줘",
        ]

    elif intent == "category_analysis":
        cat = state.get("referenced_category", "해당 업종")
        suggestions = [
            f"{cat} 리스크 분석해줘",
            f"다른 업종은 어때?",
            f"{name} 전체 요약해줘",
        ]

    else:
        suggestions = [
            "상권 분석해줘",
            "업종 추천해줘",
            "리스크 확인해줘",
        ]

    return suggestions[:4]  # 최대 4개
```

### evaluator_node 함수

```python
async def evaluator_node(state: AgentState) -> dict:
    """도구 결과 충분성 판단. Fast path 우선, 필요 시 LLM."""
    # 1. Fast path 시도
    fast_result = _fast_evaluate(state)
    if fast_result is not None:
        return {"evaluation": fast_result}

    # 2. Slow path (LLM)
    try:
        llm_result = await _llm_evaluate(state)
        # proactive_suggestions 보강
        if llm_result["sufficient"]:
            llm_result["proactive_suggestions"] = generate_proactive_suggestions(state)
        return {"evaluation": llm_result}
    except Exception:
        # Evaluator 실패 시 기본값: sufficient=True
        return {
            "evaluation": {
                "sufficient": True,
                "missing_info": [],
                "proactive_suggestions": generate_proactive_suggestions(state),
                "reasoning": "Evaluator 오류 — 수집된 데이터로 응답 진행.",
            }
        }
```

### Evaluator 프롬프트 (prompts/evaluator.py)

```python
EVALUATOR_PROMPT = """도구 실행 결과가 사용자 질문에 답하기에 충분한지 판단하세요.

## 사용자 질문
{user_message}

## 의도
{intent}

## 도구 결과 요약
{tool_results_summary}

## 도구 에러
{tool_errors}

## 판단 기준
- 사용자 질문에 답변할 수 있는 핵심 데이터가 있는가?
- 에러가 있다면 답변 품질에 치명적인가?
- 추가 도구 호출로 보완할 수 있는 부분이 있는가?

## 출력 (JSON)
{{
  "sufficient": true/false,
  "missing_info": ["부족한 정보 목록"],
  "reasoning": "판단 근거"
}}
"""
```

## Checklist

- [ ] Fast path: `SIMPLE_INTENTS` (summary, comparison, recommendation, risk) 커버
- [ ] Fast path: 모든 도구 성공 → `sufficient=True` (LLM 미호출)
- [ ] Fast path: 모든 도구 실패 → `sufficient=False` (LLM 미호출)
- [ ] Fast path: 일부 성공/실패 → None 반환 (Slow path로 이동)
- [ ] Fast path: `execution_round > 1` → None 반환 (LLM 판단 강제)
- [ ] Slow path: LLM 호출로 structured JSON 파싱
- [ ] Slow path: LLM 실패 시 `sufficient=True` 기본값 (graceful fallback)
- [ ] `generate_proactive_suggestions` — 의도별 맥락적 제안 생성
- [ ] `generate_proactive_suggestions` — 최대 4개 반환
- [ ] 폐업률 높을 때 리스크 제안 강조 (summary 결과 기반)
- [ ] recommendation 결과에서 top 업종 추출하여 제안에 반영
- [ ] `evaluator_skip_simple` config false → 항상 LLM 호출
- [ ] `_summarize_results` — tool_results를 간결하게 요약 (프롬프트 토큰 절약)

## 시나리오 테스트

### T05-01: Fast Path — 단순 의도 + 전체 성공
```
조건: intent="summary", plan=[get_district_summary_tool],
      tool_results={"get_district_summary_tool": {valid data}}, tool_errors={}
기대: sufficient=True, LLM 미호출, proactive_suggestions 4개
검증: evaluator_node 호출, LLM mock으로 호출 여부 확인
판정: PASS — sufficient + LLM 미호출 / FAIL
```

### T05-02: Fast Path — 전체 실패
```
조건: intent="summary", plan=[get_district_summary_tool],
      tool_results={}, tool_errors={"get_district_summary_tool": "timeout"}
기대: sufficient=False, missing_info에 실패 도구 포함
판정: PASS / FAIL
```

### T05-03: Slow Path — 복합 의도
```
조건: intent="category_analysis", tool_results에 sales는 있고 store_info는 에러
기대: LLM 호출 발생, sufficient 판단 (LLM이 결정)
검증: LLM mock으로 호출 확인
판정: PASS — LLM 호출 발생 / FAIL — Fast path로 처리됨
```

### T05-04: Slow Path — 2회차 루프
```
조건: intent="summary", execution_round=2 (이미 1회 루프)
기대: Fast path 스킵 → LLM 호출
검증: execution_round > 1이면 항상 Slow path
판정: PASS / FAIL
```

### T05-05: LLM 실패 Fallback
```
조건: Slow path에서 LLM 타임아웃
기대: sufficient=True 기본값, 에러 미전파
검증: evaluator_node 호출 후 정상 반환 확인
판정: PASS — graceful fallback / FAIL — 예외 전파
```

### T05-06: 동적 제안 — Summary 의도 + 높은 폐업률
```
조건: intent="summary", tool_results의 closeRate.current=12.5
기대: suggestions에 리스크 관련 강조 제안 포함 ("⚠")
검증: proactive_suggestions 내용 확인
판정: PASS — 리스크 강조 있음 / FAIL — 일반 제안만
```

### T05-07: 동적 제안 — Recommendation 의도 + Top 업종
```
조건: intent="recommendation", tool_results에 top 업종 "커피전문점"
기대: suggestions에 "커피전문점 상세 분석해줘" 포함
검증: proactive_suggestions에 업종명 포함 확인
판정: PASS — 업종명 반영 / FAIL — 일반 제안
```

### T05-08: evaluator_skip_simple=False
```
조건: config에서 evaluator_skip_simple=False, intent="summary", 전체 성공
기대: Fast path 스킵 → LLM 호출 (항상)
검증: LLM mock 호출 확인
판정: PASS — LLM 강제 호출 / FAIL — Fast path 사용
```
