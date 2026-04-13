# 06. Respond 노드

> 수집된 데이터를 기반으로 최종 응답을 LLM 스트리밍 생성

## 대상 파일

| 파일 | 작업 |
|------|------|
| `server/server/agent/nodes/respond.py` | **신규** — Respond 노드 |
| `server/server/agent/prompts/system.py` | **수정** — Respond 전용 프롬프트로 정리 |

## 의존성

- 01-state-config (AgentState)
- 02-conversation-history (conversation_history)

## TODO

- [ ] `nodes/respond.py` 생성
  - [ ] Respond 프롬프트 구성 (시스템 + 대화이력 + 도구결과 + 사용자 질문)
  - [ ] LLM 스트리밍 응답 (`llm.astream()`)
  - [ ] 텍스트 토큰을 event_queue로 실시간 push
  - [ ] direct 모드 (도구 결과 없이 직접 응답) 처리
  - [ ] `respond_node(state, event_queue) -> dict` 함수
- [ ] `prompts/system.py` 수정
  - [ ] 도구 선택 규칙 제거 (Planner가 담당)
  - [ ] 데이터 해석/응답 생성에 집중하는 프롬프트로 변경
  - [ ] 대화 이력 섹션 추가
  - [ ] 도구 결과 주입 포맷 정의

## 상세 구현

### Respond 프롬프트 구성

```python
def build_respond_prompt(state: AgentState) -> str:
    """Respond 노드용 프롬프트 조립."""
    sections = [RESPOND_SYSTEM_PROMPT]

    # 대화 이력
    if state.get("conversation_history"):
        history_text = format_history_for_respond(state["conversation_history"])
        sections.append(f"## 이전 대화\n{history_text}")

    # 도구 결과 (있을 경우)
    if state.get("tool_results"):
        results_text = format_tool_results(state["tool_results"])
        sections.append(f"## 수집된 데이터\n{results_text}")

    # 도구 에러 (있을 경우)
    if state.get("tool_errors"):
        errors_text = "\n".join(f"- {k}: {v}" for k, v in state["tool_errors"].items())
        sections.append(f"## 데이터 조회 실패\n{errors_text}\n실패한 항목은 언급하지 말고, 확보된 데이터만으로 답변하세요.")

    # Evaluator 제안 (있을 경우)
    if state.get("evaluation") and state["evaluation"].get("proactive_suggestions"):
        suggestions = state["evaluation"]["proactive_suggestions"]
        sections.append(f"## 후속 분석 제안\n자연스럽게 다음 분석을 유도하세요: {suggestions}")

    # 컨텍스트
    sections.append(f"## 현재 컨텍스트\n- 상권: {state['district_name']} ({state['district_code']})\n- 데이터 기준: {state['data_quarter']}")

    return "\n\n".join(sections)
```

### system.py 수정 (Respond 전용)

```python
RESPOND_SYSTEM_PROMPT = """당신은 서울 상권 분석 AI 컨설턴트 '마켓스코프'입니다.

역할:
- 수집된 데이터를 기반으로 사용자 질문에 답변합니다.
- 복잡한 데이터를 이해하기 쉬운 자연어로 해석합니다.
- 창업 준비자, 자영업자에게 실질적인 인사이트를 제공합니다.

규칙:
1. 항상 [수집된 데이터] 섹션의 데이터에 기반하여 답변하세요. 데이터에 없는 내용을 추측하지 마세요.
2. 수치를 언급할 때는 데이터 기준 분기를 함께 안내하세요.
3. 추정 매출은 카드 매출 기반 추정치이며 현금 매출은 미포함임을 안내하세요.
4. 업종 추천/리스크 분석 시 "추정치이며 실제와 다를 수 있습니다" 면책 안내를 포함하세요.
5. 위험 요소가 있으면 솔직하게 안내하세요.
6. 응답은 간결하고 핵심적으로 작성하세요.
7. 한국어로 응답하세요.
8. [이전 대화]가 있으면 맥락을 이어서 답변하세요. 이전에 설명한 내용을 반복하지 마세요.
9. [후속 분석 제안]이 있으면 응답 마지막에 자연스럽게 추가 분석을 유도하세요.
"""
```

### respond_node 함수

```python
async def respond_node(
    state: AgentState,
    event_queue: asyncio.Queue | None = None,
) -> dict:
    """수집된 데이터 기반 최종 응답 생성 (LLM 스트리밍)."""
    llm = _create_llm()
    prompt = build_respond_prompt(state)
    user_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=user_message),
    ]

    collected_text = ""

    async for chunk in llm.astream(messages):
        content = chunk.content
        if isinstance(content, str) and content:
            collected_text += content
            if event_queue:
                await event_queue.put({"type": "text", "content": content})
        elif isinstance(content, list):
            for block in content:
                text = block.get("text", "") if isinstance(block, dict) else str(block)
                if text:
                    collected_text += text
                    if event_queue:
                        await event_queue.put({"type": "text", "content": text})

    return {"collected_response": collected_text}
```

### direct 모드 처리

`response_mode == "direct"` 일 때 (도구 호출 없이 직접 응답):
- `tool_results` 없이 프롬프트 구성
- 일반 대화 / 명확화 질문 생성

## Checklist

- [ ] `build_respond_prompt`에 시스템 프롬프트 + 이력 + 결과 + 에러 + 제안 + 컨텍스트 모두 포함
- [ ] 도구 결과가 없을 때 (direct 모드) 정상 동작
- [ ] 도구 에러가 있을 때 "실패 항목은 언급하지 말 것" 지시 포함
- [ ] `llm.astream()`으로 토큰 단위 스트리밍
- [ ] 각 토큰을 event_queue에 push (SSE text 이벤트)
- [ ] event_queue가 None이면 push 생략 (단위 테스트용)
- [ ] collected_text에 전체 응답 누적 (history 저장용)
- [ ] system.py에서 도구 선택 규칙 제거 (Planner 담당)
- [ ] system.py에 "이전 대화 맥락 이어서 답변" 규칙 추가
- [ ] system.py에 "후속 분석 유도" 규칙 추가
- [ ] conversation_history가 빈 경우 해당 섹션 미포함

## 시나리오 테스트

### T06-01: Tool-Assisted 응답 — Summary
```
조건: response_mode="tool_assisted",
      tool_results={"get_district_summary_tool": {districtName: "강남역", summary: "...", ...}}
기대: LLM이 summary 데이터를 기반으로 자연어 응답 생성
      응답에 "강남역", 유동인구, 매출 관련 내용 포함
      event_queue에 text 이벤트 다수
검증: respond_node 호출, collected_text에 핵심 키워드 포함 확인
판정: PASS — 데이터 기반 응답 / FAIL — 데이터 미반영
```

### T06-02: Direct 응답 — 일반 대화
```
조건: response_mode="direct", tool_results={}, user_message="안녕하세요"
기대: 도구 결과 없이 인사 응답 생성
검증: collected_text가 비어있지 않음, 도구 관련 언급 없음
판정: PASS — 자연스러운 인사 / FAIL — 도구 언급 또는 에러
```

### T06-03: Direct 응답 — Ambiguous 명확화
```
조건: intent="ambiguous", response_mode="direct", district_code=""
기대: "어떤 상권을 분석해 드릴까요?" 류의 명확화 질문 생성
검증: collected_text에 질문 형태 포함
판정: PASS — 명확화 질문 / FAIL — 무의미한 응답
```

### T06-04: 에러 있는 응답
```
조건: tool_results={"get_estimated_sales_tool": {data}},
      tool_errors={"get_store_info_tool": "timeout"}
기대: 매출 데이터만 언급, 점포 현황 미언급 (실패 항목 숨김)
검증: collected_text에 점포/store 관련 내용 없음
판정: PASS — 실패 항목 미언급 / FAIL — 실패 언급
```

### T06-05: 스트리밍 이벤트 순서
```
조건: event_queue 전달, respond_node 실행
기대: 큐에 {"type": "text", "content": "..."} 이벤트가 다수 push
      모든 이벤트의 content를 이어붙이면 collected_text와 동일
검증: 큐에서 모든 이벤트 수집 → content 합산 == collected_text
판정: PASS — 일치 / FAIL — 불일치
```

### T06-06: 대화 이력 맥락 유지
```
조건: conversation_history=[{user: "강남역 분석해줘"}, {assistant: "강남역은 12만명..."}]
      user_message="거기서 카페는 어때?"
기대: 응답이 "강남역"을 다시 설명하지 않고 카페 분석으로 바로 진행
검증: collected_text에 "이전에 말씀드린" 등 맥락 연결 표현 또는 반복 없음
판정: PASS — 맥락 이어짐 / FAIL — 처음부터 재설명
```

### T06-07: 후속 분석 유도
```
조건: evaluation.proactive_suggestions=["리스크 분석해줘", "업종 추천해줘"]
기대: 응답 마지막에 후속 분석을 자연스럽게 유도하는 문장
검증: collected_text 마지막 부분에 추가 분석 유도 표현
판정: PASS — 유도 표현 있음 / FAIL — 유도 없음
```
