# 08. Chat API 통합

> chat.py 라우트에서 대화 이력 전달 + 응답 후 이력 저장

## 대상 파일

| 파일 | 작업 |
|------|------|
| `server/server/api/routes/chat.py` | **수정** — history 연동, run_agent 호출 변경 |

## 의존성

- 02-conversation-history (ConversationHistory)
- 07-graph-sse (run_agent 시그니처 변경)

## TODO

- [ ] `_get_session` 반환 구조에 `history: ConversationHistory` 추가
- [ ] `event_generator` 내에서 `run_agent`에 `conversation_history` 전달
- [ ] 응답 완료 후 user 턴 + assistant 턴을 history에 저장
- [ ] 응답 텍스트 수집 메커니즘 (SSE text 이벤트 누적)
- [ ] summary 선발행 로직 — PAE 모드에서는 불필요 (Planner가 처리)
- [ ] 기존 agent_mode="react" 시 동작 변경 없음

## 상세 구현

### 세션 구조 변경

```python
from server.agent.history import ConversationHistory

def _get_session(session_id: str) -> dict:
    now = time.time()
    expired = [k for k, v in _sessions.items() if now - v.get("last_active", 0) > _SESSION_TTL]
    for k in expired:
        del _sessions[k]

    if session_id not in _sessions:
        _sessions[session_id] = {
            "last_district_code": None,
            "last_district_name": None,
            "last_active": now,
            "history": ConversationHistory(
                max_turns=settings.max_history_turns,
                content_limit=settings.history_content_limit,
            ),
        }
    else:
        _sessions[session_id]["last_active"] = now

    return _sessions[session_id]
```

### event_generator 변경

```python
async def event_generator():
    # map_cmd 발행 (기존 유지)
    if district_center:
        yield {"data": json.dumps({...}, ensure_ascii=False)}

    # PAE 모드: summary 선발행 불필요 (Planner가 판단)
    # React 모드: 기존 summary 선발행 유지
    if settings.agent_mode != "pae" and is_summary_request and request.district_code:
        # 기존 summary 선발행 로직...

    collected_text = ""

    try:
        async for event in run_agent(
            message=request.message,
            district_code=request.district_code or "",
            district_name=district_name,
            data_quarter=data_quarter,
            conversation_history=(
                session["history"].get_recent()
                if settings.agent_mode == "pae"
                else None
            ),
        ):
            # text 이벤트 수집 (history 저장용)
            if event.get("type") == "text":
                collected_text += event.get("content", "")

            # suggestion 이벤트에서 동적 제안 추출
            if event.get("type") == "suggestion":
                dynamic_suggestions = event.get("questions", [])

            yield {"data": json.dumps(event, ensure_ascii=False, default=str)}
    except Exception:
        # 기존 에러 처리 유지...

    # 응답 완료 후 history에 저장
    if settings.agent_mode == "pae":
        session["history"].add_turn(
            role="user",
            content=request.message,
            district_code=request.district_code,
            intent=None,  # Planner가 판단한 intent는 SSE에서 추출 가능
        )
        session["history"].add_turn(
            role="assistant",
            content=collected_text,
            district_code=request.district_code,
        )
```

### 제거/변경할 기존 로직

PAE 모드에서 불필요해지는 로직:
- `is_summary_request` 패턴 매칭 → Planner가 담당
- Summary 카드 선발행 → Actor가 담당
- 단, `agent_mode == "react"` 시 기존 로직 100% 유지

## Checklist

- [ ] `_get_session`에 `history: ConversationHistory` 포함
- [ ] `run_agent` 호출 시 `conversation_history` 파라미터 전달 (PAE만)
- [ ] `agent_mode == "react"` 시 `conversation_history=None` 전달
- [ ] text 이벤트 누적하여 `collected_text` 수집
- [ ] 응답 완료 후 user + assistant 턴 history 저장
- [ ] PAE 모드에서 summary 선발행 스킵
- [ ] React 모드에서 기존 summary 선발행 유지
- [ ] 세션 만료 시 history 함께 삭제 (기존 pruning 로직에 포함)
- [ ] map_cmd 발행 로직 변경 없음
- [ ] district 감지 로직 (mock/real) 변경 없음

## 시나리오 테스트

### T08-01: PAE 모드 — 첫 요청
```
조건: agent_mode="pae", session 신규, message="강남역 분석해줘"
기대:
  1. history.get_recent() == [] (빈 이력)
  2. run_agent에 conversation_history=[] 전달
  3. 응답 완료 후 history에 user+assistant 2턴 저장
검증: 세션의 history.turns 길이 == 2
판정: PASS / FAIL
```

### T08-02: PAE 모드 — 두 번째 요청 (멀티턴)
```
조건: 첫 요청 후 두 번째 요청 "카페 어때?"
기대:
  1. history.get_recent()에 이전 2턴 포함
  2. run_agent에 이전 이력 전달
  3. 두 번째 응답 후 history에 총 4턴
검증: 세션 history.turns 길이 == 4
판정: PASS / FAIL
```

### T08-03: React 모드 — 기존 동작 유지
```
조건: agent_mode="react", 동일한 요청
기대:
  1. conversation_history=None 전달
  2. summary 선발행 로직 동작
  3. 기존 SSE 이벤트 순서 동일
검증: 기존 E2E 테스트 결과와 비교
판정: PASS — 변경 없음 / FAIL — 동작 변경
```

### T08-04: 응답 텍스트 수집
```
조건: Agent가 "강남역은 하루 평균 12만명..." 텍스트 생성
기대: collected_text에 전체 텍스트 누적, history에 300자 이내로 저장
검증: history의 assistant 턴 content 길이 <= 303 ("..." 포함)
판정: PASS / FAIL
```

### T08-05: 세션 만료 후 history 초기화
```
조건: 세션 생성 → 31분 경과 → 새 요청
기대: 새 세션 생성, history.turns == [] (빈 이력)
검증: _get_session 후 history 비어있음
판정: PASS / FAIL
```

### T08-06: PAE 모드 — Summary 선발행 스킵
```
조건: agent_mode="pae", message="강남역 분석해줘" (summary 패턴)
기대: event_generator에서 summary 카드 선발행 안 함 (Actor가 emit)
검증: 첫 card 이벤트가 Actor에서 발생
판정: PASS — 선발행 없음 / FAIL — 중복 summary 카드
```
