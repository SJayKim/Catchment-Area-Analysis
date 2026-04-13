# 03. Planner 노드

> 사용자 의도 분류 + 도구 실행 계획 생성

## 대상 파일

| 파일 | 작업 |
|------|------|
| `server/server/agent/nodes/__init__.py` | **신규** — 패키지 init |
| `server/server/agent/nodes/planner.py` | **신규** — Planner 노드 구현 |
| `server/server/agent/prompts/planner.py` | **신규** — Planner 전용 프롬프트 |

## 의존성

- 01-state-config (AgentState, ToolPlanStep)
- 02-conversation-history (format_for_planner)

## TODO

- [ ] `nodes/__init__.py` 생성
- [ ] `nodes/planner.py` 구현
  - [ ] 규칙 기반 의도 분류 (`INTENT_PATTERNS` 정규식)
  - [ ] Follow-up 감지 (`FOLLOW_UP_MARKERS`)
  - [ ] LLM 의도 분류 (모호한 경우, structured JSON output)
  - [ ] 의도 → 도구 계획 매핑 (`INTENT_TO_PLAN`)
  - [ ] Follow-up 시 이전 tool_results 확인 → 부족분만 계획
  - [ ] `planner_node(state: AgentState) -> dict` 함수
- [ ] `prompts/planner.py` 작성
  - [ ] 도구 카탈로그 (이름 + 1줄 설명 + 파라미터, ~400 토큰)
  - [ ] 의도 분류 가이드
  - [ ] JSON structured output 스키마
  - [ ] conversation_history 삽입 포맷

## 상세 구현

### 의도 분류 — 3단계 파이프라인

**Step 1: 규칙 기반 사전 필터 (LLM 미사용)**

```python
INTENT_PATTERNS = {
    "comparison": re.compile(r"(비교|vs|대비|차이)"),
    "recommendation": re.compile(r"(추천|뭐.*하면|어떤.*업종|창업|아이템)"),
    "risk": re.compile(r"(위험|리스크|폐업|안전|생존|실패)"),
    "category_analysis": re.compile(r"(카페|한식|커피|치킨|편의점|음식점|미용|병원|약국)"),
    "summary": re.compile(r"(요약|분석|알려줘|어때|보여줘|정보|현황|상권을?\s*선택)"),
}

FOLLOW_UP_MARKERS = re.compile(r"(그러면|그럼|그래서|그리고|또|거기|아까|방금|그\s*상권|그\s*지역)")

NON_SUMMARY_OVERRIDES = re.compile(
    r"(비교|추천|뭐.*하면|위험|리스크|폐업|히트맵|시뮬|카페|한식|커피|치킨)"
)
```

규칙:
1. `FOLLOW_UP_MARKERS` 매칭 → `follow_up` (LLM 해석 필요)
2. `NON_SUMMARY_OVERRIDES` 매칭 → summary가 아닌 specific intent
3. 단일 패턴 매칭 → 해당 intent (confidence=0.9)
4. 다중 패턴 또는 미매칭 → LLM에 위임

**Step 2: LLM 의도 분류 (모호한 경우만)**

```python
async def _classify_with_llm(
    message: str,
    history_text: str,
    district_code: str,
) -> dict:
    """LLM으로 의도 분류 + 맥락 해석. Structured JSON output."""
    prompt = PLANNER_CLASSIFICATION_PROMPT.format(
        message=message,
        history=history_text,
        district_code=district_code,
    )
    # LLM 호출 → JSON 파싱
    # 반환: {"intent": "...", "confidence": 0.85, "referenced_districts": [...], "referenced_category": ...}
```

**Step 3: 도구 계획 생성 (하드코딩 매핑)**

```python
INTENT_TO_PLAN: dict[str, list[dict]] = {
    "summary": [
        {"tool_name": "get_district_summary_tool",
         "args_keys": ["district_code"],
         "reason": "상권 종합 요약 조회"}
    ],
    "comparison": [
        {"tool_name": "compare_districts_tool",
         "args_keys": ["district_codes"],  # referenced_districts 사용
         "reason": "상권 비교 분석"}
    ],
    "recommendation": [
        {"tool_name": "recommend_business_tool",
         "args_keys": ["district_code", "budget?", "preference?"],
         "reason": "업종 추천 분석"}
    ],
    "risk": [
        {"tool_name": "get_store_history_tool",
         "args_keys": ["district_code"],
         "reason": "점포 이력/리스크 분석"}
    ],
    "category_analysis": [
        {"tool_name": "get_estimated_sales_tool",
         "args_keys": ["district_code", "category_code"],
         "reason": "업종별 매출 조회",
         "depends_on": []},
        {"tool_name": "get_store_info_tool",
         "args_keys": ["district_code", "category_code"],
         "reason": "업종별 점포 현황 조회",
         "depends_on": []},  # 병렬 실행 가능
    ],
    "general": [],      # 도구 불필요
    "ambiguous": [],     # 명확화 질문으로 직접 응답
}
```

### planner_node 함수

```python
async def planner_node(state: AgentState) -> dict:
    message = state["messages"][-1].content
    history = state.get("conversation_history", [])

    # 1. 규칙 기반 분류
    intent, confidence = _classify_by_rules(message)

    # 2. follow_up 또는 모호 → LLM 분류
    if intent in ("follow_up", None) or confidence < 0.7:
        llm_result = await _classify_with_llm(message, format_history(history), state["district_code"])
        intent = llm_result["intent"]
        confidence = llm_result["confidence"]
        # 맥락 해석 결과 반영
        referenced_districts = llm_result.get("referenced_districts", [state["district_code"]])
        referenced_category = llm_result.get("referenced_category")
    else:
        referenced_districts = [state["district_code"]]
        referenced_category = _extract_category(message)  # 규칙 기반 카테고리 추출

    # 3. 계획 생성
    plan = _build_plan(intent, state["district_code"], referenced_districts, referenced_category)

    # 4. response_mode 결정
    response_mode = "direct" if intent in ("general", "ambiguous") or not plan else "tool_assisted"

    return {
        "user_intent": intent,
        "intent_confidence": confidence,
        "referenced_districts": referenced_districts,
        "referenced_category": referenced_category,
        "plan": plan,
        "plan_reasoning": f"의도: {intent}, 계획: {len(plan)}개 도구 호출",
        "response_mode": response_mode,
        "execution_round": state.get("execution_round", 0) + 1,
    }
```

### Planner 프롬프트 (prompts/planner.py)

```python
PLANNER_CLASSIFICATION_PROMPT = """사용자의 질문을 분석하여 의도와 맥락을 파악하세요.

## 도구 카탈로그
| 도구 | 설명 | 파라미터 |
|------|------|----------|
| get_district_summary_tool | 상권 종합 요약 | district_code |
| get_floating_population_tool | 유동인구 상세 | district_code, quarter? |
| get_estimated_sales_tool | 추정 매출 상세 | district_code, category_code? |
| get_store_info_tool | 점포 현황 | district_code, category_code? |
| get_population_info_tool | 상주/직장인구 | district_code |
| compare_districts_tool | 상권 비교 (2~3개) | district_codes[] |
| recommend_business_tool | 업종 추천 Top5 | district_code, budget?, preference? |
| get_store_history_tool | 리스크 분석 | district_code |

## 의도 유형
summary, comparison, recommendation, risk, category_analysis, follow_up, general, ambiguous

## 대화 이력
{history}

## 현재 컨텍스트
선택 상권: {district_code}

## 사용자 질문
{message}

## 출력 (JSON)
{{
  "intent": "...",
  "confidence": 0.0~1.0,
  "referenced_districts": ["district_code", ...],
  "referenced_category": "카테고리명 or null"
}}
"""
```

## Checklist

- [ ] 규칙 기반 분류가 8가지 의도 모두 커버
- [ ] `follow_up` 감지 시 LLM에 conversation_history 전달
- [ ] LLM 호출은 모호한 경우에만 (규칙 확정 시 미호출 → 토큰 절약)
- [ ] `INTENT_TO_PLAN` 매핑이 모든 의도 타입 커버
- [ ] `category_analysis`의 2개 도구가 `depends_on: []` (병렬 가능)
- [ ] `comparison` 시 `referenced_districts`에 2~3개 코드 필수
- [ ] `general`/`ambiguous` → `response_mode="direct"`, plan 비어있음
- [ ] `execution_round` 증가 로직 포함
- [ ] Planner 프롬프트가 ~400 토큰 이내 (도구 카탈로그 포함)
- [ ] LLM JSON 파싱 실패 시 fallback 처리 (규칙 기반 재분류)
- [ ] 카테고리 추출: "카페" → category_code 매핑 로직 존재

## 시나리오 테스트

### T03-01: 규칙 기반 — Summary 의도
```
입력: message="강남역 분석해줘", district_code="D3001"
기대: intent="summary", confidence>=0.9, plan=[get_district_summary_tool], response_mode="tool_assisted"
검증: planner_node 직접 호출, LLM 미호출 확인
판정: PASS — intent 정확 + LLM 미호출 / FAIL
```

### T03-02: 규칙 기반 — Comparison 의도
```
입력: message="홍대랑 비교해줘", district_code="D3001"
기대: intent="comparison", plan=[compare_districts_tool], referenced_districts에 D3001+D3002 포함
검증: planner_node 호출 (홍대 → D3002 매핑 필요하므로 LLM 호출 가능)
판정: PASS — 2개 district 포함 / FAIL — district 누락
```

### T03-03: 규칙 기반 — Recommendation 의도
```
입력: message="여기서 뭐하면 좋을까?", district_code="D3001"
기대: intent="recommendation", plan=[recommend_business_tool]
판정: PASS / FAIL
```

### T03-04: 규칙 기반 — Risk 의도
```
입력: message="이 자리 위험하지 않아?", district_code="D3001"
기대: intent="risk", plan=[get_store_history_tool]
판정: PASS / FAIL
```

### T03-05: 규칙 기반 — Category Analysis 의도
```
입력: message="카페 매출 분석해줘", district_code="D3001"
기대: intent="category_analysis", plan에 get_estimated_sales_tool + get_store_info_tool 2개
      referenced_category에 카페 관련 값
판정: PASS — 2개 도구 + 카테고리 추출 / FAIL
```

### T03-06: Follow-up 감지 + LLM 맥락 해석
```
입력: message="거기서 카페는 어때?"
      conversation_history=[{user: "강남역 분석해줘", district_code: "D3001"}]
기대: intent="category_analysis" or "follow_up",
      district_code="D3001" (이전 맥락에서 해석),
      referenced_category="카페"
검증: LLM 호출 발생 확인, 맥락 해석 정확
판정: PASS — 이전 상권 + 카페 정확 해석 / FAIL — 맥락 유실
```

### T03-07: General 의도 (도구 불필요)
```
입력: message="안녕하세요", district_code=""
기대: intent="general", plan=[], response_mode="direct"
검증: planner_node 호출, 도구 계획 없음
판정: PASS — direct 응답 모드 / FAIL — 불필요한 도구 계획
```

### T03-08: Ambiguous 의도
```
입력: message="어떻게 하면 될까요?", district_code="" (상권 미선택)
기대: intent="ambiguous", response_mode="direct"
검증: plan이 비어있고 명확화 질문으로 응답 유도
판정: PASS / FAIL
```

### T03-09: LLM 실패 시 Fallback
```
조건: LLM API 타임아웃 또는 JSON 파싱 실패
기대: 규칙 기반 재분류로 fallback, 에러 미노출
검증: LLM mock으로 에러 주입 후 planner_node 호출
판정: PASS — graceful fallback / FAIL — 예외 전파
```

### T03-10: 2회차 Planner (Evaluator 루프백)
```
조건: execution_round=1, evaluator가 missing_info=["유동인구 상세"] 반환
기대: planner가 get_floating_population_tool 추가 계획, execution_round=2
검증: 이전 tool_results와 중복되지 않는 도구만 계획
판정: PASS — 중복 없이 부족분만 추가 / FAIL — 중복 계획
```
