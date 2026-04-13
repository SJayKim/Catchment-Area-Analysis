# 01. State 확장 + Config 설정

> AgentState 타입 확장 및 설정값 추가

## 대상 파일

| 파일 | 작업 |
|------|------|
| `server/server/agent/state.py` | AgentState 확장 (기존 필드 유지, 새 필드 추가) |
| `server/server/config.py` | agent_mode, history, evaluator 설정 추가 |

## TODO

- [ ] `ToolPlanStep` TypedDict 정의
- [ ] `EvaluationResult` TypedDict 정의
- [ ] `AgentState` 확장 (기존 5개 필드 유지 + 새 필드 추가)
- [ ] `config.py`에 agent 관련 설정 추가
- [ ] 기존 코드와 충돌 없는지 확인 (additive only)

## 상세 구현

### state.py 확장

```python
class ToolPlanStep(TypedDict):
    tool_name: str          # "get_district_summary_tool"
    args: dict              # {"district_code": "D3001"}
    reason: str             # "상권 종합 요약 조회"
    depends_on: list[int]   # 의존하는 step 인덱스 (병렬 실행용)

class EvaluationResult(TypedDict):
    sufficient: bool
    missing_info: list[str]
    proactive_suggestions: list[str]
    reasoning: str

class AgentState(TypedDict):
    # [기존 유지]
    messages: Annotated[list[BaseMessage], add_messages]
    district_code: str
    district_name: str
    data_quarter: str
    iteration_count: int

    # [신규 — 대화]
    conversation_history: list[dict]
    session_id: str

    # [신규 — 의도]
    user_intent: str
    intent_confidence: float
    referenced_districts: list[str]
    referenced_category: str | None

    # [신규 — 계획]
    plan: list[ToolPlanStep]
    plan_reasoning: str

    # [신규 — 실행]
    tool_results: dict[str, dict]
    tool_errors: dict[str, str]
    execution_round: int

    # [신규 — 평가]
    evaluation: EvaluationResult | None

    # [신규 — 응답 제어]
    response_mode: str       # "direct" | "tool_assisted"
    card_emissions: list[dict]
```

### config.py 추가 설정

```python
# Agent architecture
agent_mode: str = "react"       # "react" (기존) | "pae" (새 아키텍처)
agent_max_rounds: int = 3       # Planner-Actor-Evaluator 최대 루프 횟수

# Conversation history
max_history_turns: int = 10     # 최대 저장 턴 수
history_content_limit: int = 300  # assistant 응답 truncation 글자 수

# Evaluator
evaluator_skip_simple: bool = True  # 단순 의도는 LLM 평가 건너뜀
```

## Checklist

- [ ] `ToolPlanStep`에 필수 필드 4개(tool_name, args, reason, depends_on) 포함
- [ ] `EvaluationResult`에 필수 필드 4개(sufficient, missing_info, proactive_suggestions, reasoning) 포함
- [ ] `AgentState` 기존 5개 필드(`messages`, `district_code`, `district_name`, `data_quarter`, `iteration_count`) 그대로 유지
- [ ] `AgentState` 새 필드 타입 힌트 정확 (str, list, dict, None 등)
- [ ] `config.py`에 `agent_mode` 기본값 `"react"` (기존 동작 유지)
- [ ] `config.py` 기존 설정(use_mock, database_url 등) 변경 없음
- [ ] Python import 순서 ruff 준수
- [ ] `mypy --strict` 타입 에러 없음

## 시나리오 테스트

### T01-01: AgentState 호환성
```
조건: 기존 graph.py의 create_react_agent 코드가 확장된 state.py를 import
기대: 기존 코드 정상 동작 (새 필드는 Optional이므로 영향 없음)
검증: uvicorn 서버 기동 후 /api/chat 요청 → 기존과 동일한 응답
판정: PASS — 기존 동작 변화 없음 / FAIL — import 에러 또는 동작 변경
```

### T01-02: Config 기본값
```
조건: .env 파일에 agent_mode 미설정
기대: settings.agent_mode == "react", settings.agent_max_rounds == 3
검증: Python shell에서 from server.config import settings; print(settings.agent_mode)
판정: PASS — 기본값 정확 / FAIL — 값 불일치
```

### T01-03: Config 환경변수 오버라이드
```
조건: .env에 AGENT_MODE=pae, AGENT_MAX_ROUNDS=5 설정
기대: settings.agent_mode == "pae", settings.agent_max_rounds == 5
검증: 환경변수 설정 후 Python shell 확인
판정: PASS — 오버라이드 적용 / FAIL — 기본값 유지
```

### T01-04: TypedDict 구조 검증
```
조건: ToolPlanStep, EvaluationResult를 올바른 데이터로 인스턴스 생성
기대: mypy 타입 체크 통과, 잘못된 타입 입력 시 mypy 에러
검증: pytest 테스트에서 올바른/잘못된 데이터로 생성 시도
판정: PASS — 올바른 데이터 OK, 잘못된 데이터 mypy 경고 / FAIL — 타입 체크 미작동
```
