# 10. UX 개선 (동적 제안 / 맥락 해석 / Progressive 분석)

> 상권분석 챗봇 사용자 경험 개선 종합

## 대상 파일

통합 개선 — 03(Planner), 05(Evaluator), 06(Respond) 완성 후 적용

| 파일 | 개선 내용 |
|------|-----------|
| `server/server/agent/nodes/planner.py` | Follow-up 맥락 해석 강화, 모호한 질문 처리 |
| `server/server/agent/nodes/evaluator.py` | 동적 suggestion 맥락 고도화 |
| `server/server/agent/nodes/respond.py` | Progressive 분석 유도, 반복 방지 |
| `server/server/agent/prompts/planner.py` | 맥락 해석 프롬프트 강화 |

## 의존성

- 03~08 모두 완료 후

## TODO

### Follow-up 맥락 해석
- [ ] "거기", "그 지역" → conversation_history에서 last_district 자동 해석
- [ ] "아까 말한 강남역" → history 검색으로 district_code 매칭
- [ ] "홍대랑 비교해줘" → 현재 분석 중인 district + 홍대 자동 조합
- [ ] "그럼 한식은?" → 이전 category_analysis의 district 유지 + category만 변경
- [ ] 짧은 메시지 (<10자) + district 미언급 → session last_district 사용

### Progressive 분석 (점진적 드릴다운)
- [ ] summary 후 → "업종 추천이나 리스크 분석도 확인해 보세요" 유도
- [ ] 높은 폐업률(>8%) 감지 → "리스크 분석으로 위험 업종을 확인해 보세요" 강조
- [ ] recommendation 후 → "1위 업종인 {X}의 상세 매출 분석을 보시겠어요?" 유도
- [ ] risk 후 → "안전한 업종은 무엇인지 추천받아 보세요" 유도

### 모호한 질문 처리
- [ ] 상권 미선택 + 분석 요청 → "어떤 상권을 분석해 드릴까요?"
- [ ] "카페 어때?" (상권 context 없음) → "어떤 상권의 카페를 분석할까요?"
- [ ] 복합 의도 ("카페 매출이랑 리스크") → 우선순위 결정 또는 순차 처리

### 이전 분석 데이터 재활용
- [ ] follow_up 시 이전 라운드 tool_results 확인
- [ ] 동일 district의 이전 결과가 있으면 재조회 안 함
- [ ] category만 변경 시 해당 도구만 재호출

## 상세 구현

### Follow-up 맥락 해석 로직 (planner.py 강화)

```python
async def _resolve_follow_up(
    message: str,
    history: list[dict],
    current_district: str,
) -> dict:
    """Follow-up 질문의 맥락을 해석.

    Returns:
        {
            "district_code": 해석된 상권코드,
            "category": 해석된 업종 (있으면),
            "intent": 실제 의도,
        }
    """
    # 1. "거기", "그 지역" → last district from history
    if re.search(r"(거기|그\s*지역|그\s*상권|그곳)", message):
        for turn in reversed(history):
            if turn.get("district_code"):
                return {
                    "district_code": turn["district_code"],
                    "category": _extract_category(message),
                    "intent": _infer_intent_from_message(message),
                }

    # 2. "아까 말한 {상권명}" → history에서 검색
    name_match = re.search(r"아까.*?([\w가-힣]{2,10})", message)
    if name_match:
        name = name_match.group(1)
        for turn in reversed(history):
            if name in turn.get("content", ""):
                return {
                    "district_code": turn.get("district_code", current_district),
                    "category": _extract_category(message),
                    "intent": _infer_intent_from_message(message),
                }

    # 3. "{상권}랑 비교" → current + mentioned 조합
    compare_match = re.search(r"([\w가-힣]{2,10})(이?랑|하고|과|vs)\s*(비교|대비)", message)
    if compare_match:
        other_name = compare_match.group(1)
        return {
            "district_code": current_district,
            "other_district_name": other_name,  # 별도 해석 필요
            "intent": "comparison",
        }

    # 4. Fallback: current district 유지
    return {
        "district_code": current_district or (history[-1].get("district_code") if history else ""),
        "category": _extract_category(message),
        "intent": _infer_intent_from_message(message),
    }
```

### 동적 Suggestion 고도화 (evaluator.py 강화)

```python
def generate_proactive_suggestions(state: AgentState) -> list[str]:
    intent = state["user_intent"]
    name = state["district_name"]
    results = state.get("tool_results", {})

    if intent == "summary":
        suggestions = [f"{name}에서 뭐하면 좋을까?", f"{name} 리스크 분석해줘"]
        # 폐업률 높으면 리스크 우선 제안
        summary = results.get("get_district_summary_tool", {})
        if summary.get("closeRate", {}).get("current", 0) > 8.0:
            suggestions[1] = f"⚠ {name} 폐업률이 높아요 — 리스크 분석해볼까요?"
        suggestions += ["유동인구 시간대별로 보여줘", "다른 상권이랑 비교해줘"]

    elif intent == "recommendation":
        recs = results.get("recommend_business_tool", {}).get("recommendations", [])
        if recs:
            top = recs[0]["category_name"]
            suggestions = [
                f"{top} 상세 분석해줘",
                f"{name} 리스크 확인해줘",
                f"다른 상권에서 {top}은 어때?",
                f"2위 업종은 어때?",
            ]
        else:
            suggestions = [f"{name} 요약해줘", "다른 상권 추천해줘"]

    elif intent == "risk":
        stability = results.get("get_store_history_tool", {}).get("stability", {})
        score = stability.get("score", 50)
        if score and score < 50:
            suggestions = ["안전한 업종 추천해줘", f"{name} 요약해줘", "다른 상권 알아볼까?"]
        else:
            suggestions = [f"{name} 추천 업종 알려줘", "매출 분석해줘", "다른 상권 비교해줘"]

    elif intent == "comparison":
        codes = state.get("referenced_districts", [])
        if len(codes) >= 2:
            suggestions = ["어떤 상권이 더 좋을까?", "추천 업종 각각 비교해줘", "리스크도 비교해줘"]
        else:
            suggestions = ["다른 상권도 비교해줘", f"{name} 요약해줘"]

    elif intent == "category_analysis":
        cat = state.get("referenced_category", "해당 업종")
        suggestions = [f"{cat} 리스크 분석해줘", "다른 업종은 어때?", f"{name} 전체 요약해줘"]

    else:
        suggestions = ["상권 분석해줘", "업종 추천해줘", "리스크 확인해줘"]

    return suggestions[:4]
```

## Checklist

- [ ] Follow-up: "거기"/"그 지역" → last district 해석
- [ ] Follow-up: "아까 말한 {이름}" → history 검색 매칭
- [ ] Follow-up: "{상권}랑 비교" → current + other 조합
- [ ] Follow-up: 짧은 메시지 + district 미언급 → session last_district
- [ ] Follow-up: "그럼 한식은?" → district 유지 + category 변경
- [ ] Progressive: summary 후 리스크/추천 유도
- [ ] Progressive: 높은 폐업률 → 리스크 강조 제안
- [ ] Progressive: recommendation 후 top 업종 상세 유도
- [ ] Progressive: risk 후 안전 업종 추천 유도
- [ ] Ambiguous: 상권 미선택 시 명확화 질문
- [ ] Ambiguous: 복합 의도 우선순위 처리
- [ ] 재활용: follow_up 시 이전 tool_results 확인 → 중복 조회 방지
- [ ] 동적 suggestion: 의도별 + 결과 데이터 기반 4개 생성
- [ ] 동적 suggestion: 폐업률/안정성 점수 기반 조건부 강조

## 시나리오 테스트

### T10-01: Follow-up — "거기서 카페는 어때?"
```
전제: 이전 대화에서 강남역(D3001) 분석 완료
입력: message="거기서 카페는 어때?", district_code=None
기대:
  1. Planner가 "거기" → D3001 해석
  2. intent=category_analysis, district_code=D3001, category=카페
  3. get_estimated_sales + get_store_info 호출 (카페 필터)
  4. 응답이 "강남역 카페" 관련 내용
검증: Planner 출력의 district_code + referenced_category 확인
판정: PASS — 맥락 정확 해석 / FAIL — district 또는 category 오류
```

### T10-02: Follow-up — "아까 말한 강남역"
```
전제: 3턴 전에 강남역 분석, 이후 홍대 분석
입력: message="아까 말한 강남역은 리스크가 어때?"
기대: district_code=D3001 (현재 홍대가 아닌 강남역으로 해석)
판정: PASS — 강남역 정확 / FAIL — 홍대로 잘못 해석
```

### T10-03: Follow-up — "홍대랑 비교해줘"
```
전제: 강남역(D3001) 분석 중
입력: message="홍대랑 비교해줘"
기대: intent=comparison, referenced_districts=[D3001, D3002]
판정: PASS — 2개 상권 조합 / FAIL — 1개만 또는 잘못된 조합
```

### T10-04: Follow-up — "그럼 한식은?"
```
전제: "카페 분석해줘" 후
입력: message="그럼 한식은?"
기대: district 유지 + category=한식, intent=category_analysis
판정: PASS — district 유지 + category 변경 / FAIL
```

### T10-05: Progressive — Summary 후 높은 폐업률
```
전제: summary 결과의 closeRate.current=12.5
기대: suggestion에 "⚠ {name} 폐업률이 높아요" 포함
검증: suggestion 이벤트 내용 확인
판정: PASS — 리스크 강조 / FAIL — 일반 제안
```

### T10-06: Progressive — Recommendation 후 Top 업종 드릴다운
```
전제: recommendation 결과의 top 업종 = "커피전문점"
기대: suggestion에 "커피전문점 상세 분석해줘" 포함
판정: PASS — 업종명 반영 / FAIL
```

### T10-07: Ambiguous — 상권 미선택
```
입력: message="분석해줘", district_code=None, history=[]
기대: intent=ambiguous, response_mode="direct"
      응답: "어떤 상권을 분석해 드릴까요? 지도에서 선택하거나 이름을 알려주세요."
판정: PASS — 명확화 질문 / FAIL — 에러 또는 빈 응답
```

### T10-08: 데이터 재활용 — 동일 상권 재조회 방지
```
전제: D3001 summary 완료 (tool_results에 get_district_summary_tool 존재)
입력: message="강남역 유동인구 상세 알려줘"
기대: get_floating_population_tool만 호출 (summary 재호출 안 함)
검증: Actor의 plan에 1개 도구만 포함
판정: PASS — 1개만 호출 / FAIL — 중복 호출
```

### T10-09: 복합 의도 처리
```
입력: message="카페 매출이랑 리스크 같이 알려줘"
기대: plan에 get_estimated_sales + get_store_info + get_store_history 포함
      또는 우선순위에 따라 하나 먼저 처리 후 후속 제안
판정: PASS — 복합 처리 또는 순차 유도 / FAIL — 일부만 처리
```

### T10-10: 멀티턴 종합 시나리오 (5턴)
```
시나리오:
  1. "강남역 분석해줘" → summary card + 텍스트 응답
  2. "거기서 뭐하면 좋을까?" → recommendation card
  3. "카페 상세 분석해줘" → category_analysis 텍스트
  4. "홍대랑 비교해줘" → comparison card (강남역 vs 홍대)
  5. "홍대 리스크는?" → risk card

기대:
  - 각 턴에서 정확한 intent 분류
  - 맥락 유지 (2번: "거기" → 강남역, 4번: 현재 강남역 + 홍대, 5번: 홍대)
  - 각 턴의 올바른 카드/텍스트 응답
  - suggestion이 매 턴마다 맥락적으로 변경
  - 이전 데이터 불필요한 재조회 없음

검증: 5턴 순차 실행, 각 턴의 intent + card_type + district 확인
판정: PASS — 5/5 턴 정확 / FAIL — 1턴이라도 오류
```
