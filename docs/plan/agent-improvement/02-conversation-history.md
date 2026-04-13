# 02. 대화 이력 관리

> 멀티턴 대화를 위한 세션별 대화 이력 저장/조회/Truncation

## 대상 파일

| 파일 | 작업 |
|------|------|
| `server/server/agent/history.py` | **신규** — ConversationHistory 클래스 |
| `server/server/api/routes/chat.py` | **수정** — 세션 저장 구조 확장, history 주입 |

## 의존성

- 01-state-config (AgentState.conversation_history 필드, config 설정)

## TODO

- [ ] `history.py` 파일 생성
- [ ] `ConversationHistory` 클래스 구현
  - [ ] `add_turn(role, content, district_code, intent, tool_results_keys)` 메서드
  - [ ] `get_recent(max_turns)` 메서드 — 최근 N턴 반환
  - [ ] `format_for_planner()` 메서드 — Planner 프롬프트용 압축 포맷
  - [ ] `truncate()` 메서드 — 최대 턴 수 초과 시 오래된 턴 삭제
- [ ] assistant 응답 저장 시 `history_content_limit` (300자) truncation 적용
- [ ] `chat.py` 세션 구조 확장 (`_sessions`에 `history` 필드 추가)
- [ ] `chat.py`에서 요청 시 history 조회 → `run_agent`에 전달
- [ ] `chat.py`에서 응답 완료 후 user/assistant 턴 history에 저장

## 상세 구현

### history.py

```python
class ConversationHistory:
    """세션별 대화 이력 관리."""

    def __init__(self, max_turns: int = 10, content_limit: int = 300):
        self.max_turns = max_turns
        self.content_limit = content_limit
        self.turns: list[dict] = []

    def add_turn(
        self,
        role: str,           # "user" | "assistant"
        content: str,
        district_code: str | None = None,
        intent: str | None = None,
        tool_results_keys: list[str] | None = None,
    ) -> None:
        """턴 추가. assistant 응답은 content_limit로 truncation."""
        truncated = content
        if role == "assistant" and len(content) > self.content_limit:
            truncated = content[:self.content_limit] + "..."

        self.turns.append({
            "role": role,
            "content": truncated,
            "district_code": district_code,
            "intent": intent,
            "tool_results_keys": tool_results_keys or [],
            "timestamp": datetime.utcnow().isoformat(),
        })
        self._truncate()

    def get_recent(self, max_turns: int | None = None) -> list[dict]:
        """최근 N턴 반환."""
        n = max_turns or self.max_turns
        return self.turns[-n:]

    def format_for_planner(self) -> str:
        """Planner 프롬프트에 주입할 압축 포맷."""
        lines = []
        for t in self.turns:
            if t["role"] == "user":
                district = f"({t['district_code']})" if t["district_code"] else ""
                intent = t.get("intent", "")
                tools = ",".join(t.get("tool_results_keys", []))
                tools_str = f" tools:[{tools}]" if tools else ""
                lines.append(f'[User] {district} "{t["content"]}" → {intent}{tools_str}')
            else:
                lines.append(f'[AI] "{t["content"]}"')
        return "\n".join(lines)

    def get_last_district(self) -> str | None:
        """이력에서 가장 최근 district_code 반환."""
        for t in reversed(self.turns):
            if t.get("district_code"):
                return t["district_code"]
        return None

    def _truncate(self) -> None:
        """max_turns 초과 시 오래된 턴 삭제."""
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]
```

### chat.py 세션 구조 변경

기존:
```python
_sessions[session_id] = {
    "last_district_code": None,
    "last_district_name": None,
    "last_active": now,
}
```

변경:
```python
_sessions[session_id] = {
    "last_district_code": None,
    "last_district_name": None,
    "last_active": now,
    "history": ConversationHistory(
        max_turns=settings.max_history_turns,
        content_limit=settings.history_content_limit,
    ),
}
```

### chat.py 흐름 변경

1. 요청 수신 시: `session["history"].get_recent()` → `run_agent(..., conversation_history=...)`
2. 응답 완료 후: `session["history"].add_turn("user", request.message, ...)` + `session["history"].add_turn("assistant", collected_response, ...)`

## Checklist

- [ ] `ConversationHistory` 클래스가 독립적으로 동작 (외부 의존성 없음)
- [ ] `add_turn` 호출 시 assistant 응답이 300자로 truncation됨
- [ ] `get_recent(5)` 호출 시 최근 5턴만 반환
- [ ] `format_for_planner()` 출력이 `[User]`/`[AI]` 형식
- [ ] `_truncate()`가 max_turns 초과 시 오래된 턴 삭제
- [ ] `get_last_district()` 가 역순 탐색으로 최근 district_code 반환
- [ ] `chat.py`에서 기존 `_sessions` 호환성 유지 (기존 필드 그대로)
- [ ] `chat.py`에서 `agent_mode == "react"` 시 history 저장은 하되 `run_agent`에는 미전달 (기존 동작 유지)
- [ ] 세션 TTL (30분) 만료 시 history도 함께 삭제

## 시나리오 테스트

### T02-01: 턴 추가 + Truncation
```
조건: ConversationHistory(max_turns=4, content_limit=10)에 6턴 추가
기대: turns에 최근 4턴만 남아있음, assistant 응답은 10자+"..."
검증:
  h = ConversationHistory(max_turns=4, content_limit=10)
  h.add_turn("user", "강남역 분석해줘", "D3001", "summary")
  h.add_turn("assistant", "강남역은 하루 평균 12만명의 유동인구가 방문하는 발달상권입니다")
  h.add_turn("user", "카페 어때?", "D3001", "category_analysis")
  h.add_turn("assistant", "카페 업종은 경쟁이 치열합니다")
  h.add_turn("user", "홍대는?", "D3002", "summary")
  h.add_turn("assistant", "홍대입구는 젊은층이 많은 상권입니다")
  assert len(h.turns) == 4
  assert h.turns[0]["content"] == "카페 어때?"  # 첫 2턴 삭제됨
  assert h.turns[1]["content"] == "카페 업종은 경..."  # 10자 + "..."
판정: PASS / FAIL
```

### T02-02: Planner 포맷 출력
```
조건: 2턴(user+assistant) 추가 후 format_for_planner() 호출
기대:
  [User] (D3001) "강남역 분석해줘" → summary tools:[get_district_summary_tool]
  [AI] "강남역은 하루 평균 12만명..."
검증: 문자열 포맷 일치 확인
판정: PASS — 포맷 일치 / FAIL — 형식 불일치
```

### T02-03: get_last_district 역순 탐색
```
조건: D3001 → D3002 순서로 턴 추가
기대: get_last_district() == "D3002"
검증: 직접 호출 확인
판정: PASS / FAIL
```

### T02-04: chat.py 세션 호환성
```
조건: agent_mode="react" 상태에서 /api/chat 요청
기대: 기존과 동일한 SSE 응답 (history 저장은 되지만 agent에 미전달)
검증: curl -X POST /api/chat → 기존 이벤트 순서 동일
판정: PASS — 기존 동작 100% 유지 / FAIL — 응답 변경
```

### T02-05: 세션 만료 시 이력 삭제
```
조건: 세션 생성 후 31분 경과, 새 요청 수신
기대: 이전 세션의 history가 삭제되고 새 세션 생성
검증: _get_session 호출 후 history.turns == []
판정: PASS / FAIL
```
