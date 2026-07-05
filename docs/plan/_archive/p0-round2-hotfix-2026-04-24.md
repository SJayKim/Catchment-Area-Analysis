# P0 Round 2 Hotfix — 2026-04-24

> **Context**: [analysis-quality-eval-2026-04-24.md](../../qa/analysis-quality-eval-2026-04-24.md) §4 에서 발견된 4 P0 + 선결 조건(배포 드리프트). Round 2 eval 결과 7.6/10 FAIL 의 1차 원인은 **컨테이너에 W1/W2/W3 코드가 실제로 반영되지 않았고 legacy 코드가 서빙 중** 이었던 배포 드리프트. 그 위에 fix 로직 자체의 결함 3건이 겹쳐 있음.

## 1. Context

### 1.1 배포 드리프트 발견 (선결 조건)

`catchment-area-analysis-backend-1` 컨테이너 상태 검사 결과:

| 검사 | 호스트 | 컨테이너 | 판정 |
|------|-------|---------|------|
| `/app/server/agent/utils/` 디렉토리 | 존재 | **없음** | DRIFT |
| `entity_matching.py` / `rewriter.py` / `abstention.py` | 존재 | **없음** | DRIFT |
| `districts.py::detect_districts_in_message` import | `from server.agent.utils.entity_matching import ...` | legacy (import 없음) | DRIFT |
| `respond.py` | 280 LOC (formatting.py 추출본) | 502 LOC 원본 | DRIFT |

**근거 명령**:
```bash
docker exec catchment-area-analysis-backend-1 sh -c 'find /app -name entity_matching.py'  # (empty)
docker exec catchment-area-analysis-backend-1 ls /app/server/agent/  # utils 없음
```

**결론**: [status](../../status/current-status.md) 의 "컨테이너 W1~W3 docker cp 반영" 은 사실이 아님. legacy 코드(2글자 후보는 exact 매칭만) 로 서빙되고 있었음.
- "홍대 vs 성수 매출 비교" → `_candidate_words` 가 ["홍대","vs","성수"] 추출 ✅
- legacy 는 "홍대" 2글자로 **3순위 contains (`%홍대%`) LIMIT 1** 실행 → `3110285 홍대부중` 첫 매칭
- "성수" 도 contains 시도하지만 `detect_districts_in_message` legacy 는 2글자에 prefix/contains/reverse 모두 스킵 → 0개 반환
- 결과: tool input `district_codes:["3110285"]` 단일

즉 eval 결과는 "W1 type boost 약함" 이 아니라 **"W1 자체가 실행되지 않음"** 이 근본 원인.

### 1.2 W1 fix 자체의 결함 (분석)

배포가 정상이어도 여전히 다음 결함이 남음:

**P0-2 Type boost 약함** — 실측 계산 (현행 `_TYPE_BOOST_PER_RANK=0.05`):

| 후보 | 길이 | prefix sim | type_rank | boost | final |
|------|-----:|-----------:|----------:|------:|------:|
| 홍대부중 (골목) | 4 | 0.55+0.25×(2/4)=**0.675** | 2 | +0.10 | **0.775** |
| 홍대입구역(홍대) (발달) | 9 | 0.55+0.25×(2/9)=0.6056 | 4 | +0.20 | 0.8056 |
| 홍대입구역 3번 (골목) | 8 | 0.55+0.25×(2/8)=0.6125 | 2 | +0.10 | 0.7125 |

현재 수치상 홍대입구역(홍대) 0.8056 > 홍대부중 0.775 로 **미세 차이로는** 발달이 이기긴 함. 하지만:
- CLOSE_DELTA=0.08 → 두 score 차 0.0306 이므로 **ambiguous** 플래그가 뜨긴 함.
- 서울 열린데이터 발달상권 명명 규칙(`실제명(별칭)`) 을 반영한 **괄호-내 exact token 보너스** 가 없음. "홍대입구역(홍대)" 의 괄호 안 "홍대" 가 query 와 완전 일치하는 신호는 가장 강한 확증인데 현행 score 에 반영 0.

**P0-3 Multi-extract**: 
- "홍대 vs 성수 매출 비교" 에서 "성수" 도 후보지만 성수역 (len=3) prefix: 0.55+0.25×(2/3)=0.7167, +0.20=0.9167 → TOP1_MIN 통과 **해야 함**.
- 실제 W1 배포 후 동작은 검증 필요. 선결 조건 해결 후 smoke 로 확인.

**P0-1 XML leak** — Claude Sonnet 4 가 tool 결과 부족 시 "추가 조회 필요" 판단으로 자체 `<tool_use>{...}</tool_use>` XML 을 본문에 생성. MarketScope 파서는 이 XML 을 파싱하지 않고 raw text 로 `MessageList` 에 노출 → UX 오염.
- LLM 행동 이해: Anthropic 모델은 tool_use 포맷을 학습했기 때문에, system prompt 에 "수집된 데이터" 섹션이 부족하면 프롬프트 엔지니어링으로 추가 tool 요청 시뮬레이션을 시도하는 경향.
- Case study: OpenAI 계열도 유사. 해결은 **(a) 시스템 프롬프트에 자연어 마크다운 출력만 허용 명시** + **(b) 스트리밍 chunk 를 필터링해 XML-like token 을 삭제**.

**P0-4 Empty-plan fallback** — 현행 Planner:
```python
# planner.py:359
response_mode = "direct" if intent in ("general", "ambiguous") or not plan else "tool_assisted"
```
- plan 이 empty 면 `direct` → Respond 진입. ABSTENTION 프롬프트가 뜨지만, Respond LLM 이 여전히 대화 히스토리의 수치를 재인용하면서 거절을 충분히 수행하지 않음 (S7 증상).
- 근본 해결: **Planner 에서 clarification 의도를 명시적으로 감지**하고 (coref 감지 O + anchor 복원 X, 또는 exclusion 후 multi 0개), 고정 clarification 텍스트를 SSE 로 직접 방출하고 Respond 스킵.

### 1.3 Memory 교훈

- `feedback_stale_container_vs_source.md` — "최근 fix 와 매칭되는 FAIL 은 code regression 의심 전에 stale image 먼저 확인". 이번 Round 2 실패가 **정확히 이 시나리오**. Plan 에 컨테이너 배포 검증을 선결 Gate 로 명시.
- `feedback_respond_tool_use_xml_leak.md` — 이미 기록된 feedback. 본 Plan 이 해결.
- `feedback_comparison_intent_halluc.md` — multi-district 추출 실패 시 할루시. 본 Plan 의 P0-3 + P0-4 가 해결.

## 2. Scope

**In-scope**:
1. W1/W2/W3 + P0-1~P0-4 fix 를 한 번에 컨테이너에 배포하고 smoke 재실행
2. P0-1 Respond prompt XML 금지 + streaming 중 sanitize
3. P0-2 entity_matching type_boost 상향 + paren-exact bonus
4. P0-3 multi-extract 재검증 (P0-2 fix 효과 포함)
5. P0-4 Planner empty-plan clarification short-circuit

**Out-of-scope**:
- Refactoring Pass 2 잔여 (errors.py 래퍼, chatStore slice)
- Round 3 eval (본 Plan 완료 후 별도)
- W4 Card-level PDF

## 3. Design

### 3.1 선결 — 컨테이너 배포 정합성

**방침**: 호스트 파일을 `docker cp` 로 컨테이너에 복사하되, `find` 로 배포 검증을 수행한 뒤에만 smoke 진행.

```bash
docker cp server/server/agent/utils backend:/app/server/agent/
docker cp server/server/agent/nodes/respond.py backend:/app/server/agent/nodes/
docker cp server/server/agent/nodes/planner.py backend:/app/server/agent/nodes/
docker cp server/server/repositories/real/districts.py backend:/app/server/repositories/real/
docker cp server/server/api/routes/chat.py backend:/app/server/api/routes/
docker compose restart backend
# 검증
docker exec backend python -c "from server.agent.utils.entity_matching import rank_candidates; print('ok')"
```

### 3.2 P0-1: Respond XML leak

**Fix 1 — System prompt 규칙 추가** (`respond.py`):

```text
13. **출력 포맷**: 응답은 **자연어 마크다운만** 허용. 다음 형식은 절대 출력 금지:
    - XML 태그 (`<tool_use>`, `<tool_result>`, `<get_*>`, `<parameter>`, `<invoke>` 등)
    - Tool 호출 JSON ({"name": "...", "input": {...}})
    - 함수 시그니처, 코드 블록으로 감싼 tool call
    데이터가 부족하면 추가 tool 을 "호출 시도" 하지 말고 "해당 데이터가 부족합니다" 라고 자연어로 안내하세요.
```

**Fix 2 — Streaming sanitizer** (`respond_node`):
- chunk 누적 buffer 에 `<` 가 들어오면 해당 chunk 의 `<` 이후를 보류 (pending)
- pending 에 `>` 가 도달하면: 감싸진 tag 명이 화이트리스트(`br`, `strong`, `em` 등 일반 HTML) 가 아니면 전체 `<...>` 구간 드롭. 포함 여부는 regex `<\/?(tool_use|tool_result|get_[a-z_]+|parameter|invoke|function|antml:)[^>]*>` 로 판별
- 화이트리스트 타이밍: 30 chars 누적 후에도 `>` 미도달이면 전체 flush (tag 아님 판단)

구현은 state machine 기반 class `_XMLTagSanitizer` 로 캡슐화. `astream` 루프에서 `sanitized = sanitizer.feed(content); if sanitized: queue.put(text=sanitized)`. 루프 종료 후 `sanitizer.flush()`.

**Fix 3 — post-hoc 경고 로그**: 최종 `collected_text` 에 여전히 leak 된 pattern 감지 시 `logger.warning("respond_xml_leak_post_sanitize", ...)`. 거의 발생하지 않을 것이지만 관측.

### 3.3 P0-2: entity_matching 강화

`_TYPE_BOOST_PER_RANK` 유지(`0.05`) 하되 다음 **2개 신호 추가**:

```python
# 발달상권 명명 규칙: "실제명(별칭)" — 괄호 안 토큰이 query 와 exact 이면
# "대체 불가" 신호. boost +0.15.
_PAREN_EXACT_BONUS = 0.15
# "XX역(XX)" 와 같이 괄호 앞 본명이 query 와 prefix 매칭되는 경우 +0.05.
_ROOT_PREFIX_BONUS = 0.05
```

`_string_similarity` 또는 `rank_candidates` 에서:
- `re.search(r"\((.+?)\)", name)` 으로 괄호 안 토큰 추출. `parens==query` 면 `+0.15`.
- 괄호 제거 본명 (`name_root = re.sub(r"\([^)]*\)", "", name).strip()`) 이 `query` 와 prefix 매칭이면 `+0.05` 추가.

**재계산 예**:
- 홍대부중 (골목): 0.675 + 0.10 = 0.775 (변경 없음)
- 홍대입구역(홍대) (발달): 0.6056 + 0.20(type) + 0.15(paren-exact) + 0.05(root-prefix=홍대입구역 starts "홍대") = **0.966 (top)** ✅
- 서교동(홍대): 0.5929 + 0.20 + 0.15 + 0(root=서교동 no prefix) = 0.9429

결과: `홍대입구역(홍대)` 가 확정적으로 top, ambiguous 플래그도 해소 (Δ>0.08).

### 3.4 P0-3: multi-extract 재검증

핵심 가설: **P0-2 fix + 배포 정합성 해결만으로 자동 해결**. 별도 코드 변경 불요.

추가 안전장치:
- `detect_districts_in_message` 에 `logger.info` 로 추출 후보/점수 로깅 (session_id, candidates, top scores). DEBUG 아닌 INFO 로 승격해 Langfuse 와 조인.
- Smoke 에서 "홍대 vs 성수 매출 비교" → 추출 결과에 `3120103 홍대입구역(홍대)`, `3120052 성수역` 2건 포함 확인.

### 3.5 P0-4: Planner clarification short-circuit

**설계 원칙**: Respond 까지 가지 말고 Planner 에서 직접 clarification 이벤트를 방출한 뒤 그래프 종료.

추가할 분기 조건:
```python
needs_clarification = False
clarification_reason = None

if rewrite.coref_detected and not rewrite.anchor_district_name and not district_code:
    needs_clarification = True
    clarification_reason = "coref_no_anchor"
elif intent == "comparison" and len(referenced_districts) < 2:
    needs_clarification = True
    clarification_reason = "comparison_under_2"
elif rewrite.excluded_tokens and intent == "comparison" and not referenced_districts:
    needs_clarification = True
    clarification_reason = "exclusion_left_empty"
```

`clarification` intent 인 경우:
- `response_mode = "clarification_direct"`
- `plan = []`
- State 에 `clarification_text`, `clarification_suggestions` 추가

Graph 라우팅 (`graph.py`):
- Planner 에서 `response_mode == "clarification_direct"` 면 Actor/Evaluator/Respond 스킵하고 END.
- chat.py 의 `run_agent` 가 `clarification_text` 를 `text` SSE 이벤트로 방출하고 `suggestions` 방출 후 `done`.

**Clarification 템플릿 3종**:

```python
CLARIFICATION_TEMPLATES = {
    "coref_no_anchor": {
        "text": "이전에 분석했던 상권이 없어 '거기' 가 어디인지 특정하기 어려워요. 비교하실 상권 이름을 직접 알려주시겠어요? (예: '강남역 vs 홍대입구역 유동인구 비교')",
        "suggestions": ["강남역 상권 요약", "홍대 vs 성수 비교", "건대 창업 추천 업종"],
    },
    "comparison_under_2": {
        "text": "비교를 위해서는 최소 2개의 상권이 필요해요. 두 상권을 모두 알려주시겠어요? (예: '강남역이랑 홍대입구역 매출 비교')",
        "suggestions": ["강남역 vs 홍대 매출", "성수역 vs 건대 유동인구", "명동 vs 서울역 비교"],
    },
    "exclusion_left_empty": {
        "text": "'{excluded}' 을 제외하고 나니 비교할 상권이 없어요. 분석하실 상권 2개를 다시 알려주세요.",
        "suggestions": ["성수역이랑 건대 비교", "강남역 vs 서울역", "홍대 vs 성수"],
    },
}
```

**왜 Respond 스킵이 안전한가**: abstention 프롬프트만으로는 Claude 가 priors 로 답변하는 것을 100% 막지 못함(S7 증거). Fixed-text clarification 은 deterministic 하고 사용자에게 재질문 흐름을 명확히 전달.

## 4. Checklist

### Phase 0 — 선결 (배포 정합성)
- [ ] 호스트 코드 fix 완료 (Phase 1~4)
- [ ] `docker cp` 로 W1/W2/W3 + P0 fix 를 컨테이너 반영
- [ ] `docker compose restart backend`
- [ ] `docker exec backend python -c "from server.agent.utils.entity_matching import rank_candidates"` 성공
- [ ] `/api/health/detail` 200 OK + `use_mock=false`

### Phase 1 — P0-1 Respond XML leak
- [ ] `respond.py:RESPOND_SYSTEM_PROMPT` 에 규칙 13 추가
- [ ] `respond.py` 에 `_XMLTagSanitizer` state-machine 클래스 추가
- [ ] `respond_node` 의 `async for chunk` 루프에서 sanitizer 통과 후 `text` 이벤트 방출
- [ ] 스트림 종료 후 `sanitizer.flush()` + post-hoc leak 감지 logger.warning

### Phase 2 — P0-2 Entity matching 강화
- [ ] `entity_matching.py:_string_similarity` 에 paren/root 분석 helper 함수 추가
- [ ] `rank_candidates` 에서 `_PAREN_EXACT_BONUS` + `_ROOT_PREFIX_BONUS` 적용
- [ ] unit-smoke: "홍대" → `홍대입구역(홍대) 0.96+` top, `홍대부중 0.775`, Δ>0.08 → ambiguous=False

### Phase 3 — P0-3 multi-extract 검증
- [ ] `detect_districts_in_message` 에 INFO 로깅 추가 (candidates + top scores)
- [ ] smoke: "홍대 vs 성수 매출 비교" → 2건 추출 (3120103 홍대입구역(홍대), 3120052 성수역)

### Phase 4 — P0-4 Planner clarification
- [ ] `agent/prompts/clarification.py` (또는 planner.py 내부) 에 `CLARIFICATION_TEMPLATES` 3종 정의
- [ ] `planner_node` 말미에 needs_clarification 분기 추가
- [ ] `AgentState` 에 `clarification_text`, `clarification_suggestions` 추가
- [ ] `graph.py` 에서 `response_mode == "clarification_direct"` 분기 → Actor/Respond 스킵하고 END 로
- [ ] `chat.py` `run_agent` (또는 state mutator) 에서 clarification 이벤트 방출

### Phase 5 — 검증
- [ ] `ruff check server/` PASS
- [ ] 컨테이너 재배포 + smoke S3/S7/S8 3건 수집 → SSE 파서로 할루시 / tool_codes / XML leak 지표 확인
- [ ] Memory 갱신 (`feedback_stale_container_vs_source.md` 는 이미 존재 — status 에 새 feedback 등록)

## 5. 재검토 (Self-Review Gate)

**엣지케이스**:
- XML sanitizer 가 정상 HTML (`<strong>`, `<br>`) 을 삭제하지 않는지 → 화이트리스트 기반 판별. 현 respond.py 는 markdown 출력이라 HTML 이 거의 없음, 하지만 `<...>` 꼴 강조가 등장할 수 있으므로 화이트리스트 `br|strong|em|code|b|i|u` 만 통과.
- Paren-exact bonus 가 "XX역(XX)" 만 아니라 "XX(일부)" 일반 케이스에 과잉 적용? → query 와 괄호 안이 exact 일 때만. 예: query="홍대", name="상수역(홍대)" → bonus 적용. 이는 의도된 동작 (서울 열린데이터가 발달상권 별칭을 괄호로 관리).
- Clarification 무한 루프: 사용자가 여전히 애매한 질문 재전송 시 반복. → clarification 도 session history 에 저장되지만, 이후 사용자가 "강남역 vs 홍대" 로 재질의하면 정상 흐름. 시스템 정상.

**타 Plan 충돌**: 
- [accuracy-gap-fix.md](accuracy-gap-fix.md) W1~W3 이 전제. 본 Plan 은 그 fix 들의 실제 배포 + 2차 조정.
- [phase1-low-mid-risk-2026-04-23.md](../infra/phase1-low-mid-risk-2026-04-23.md) Pass 2 의 `respond.py` 분할과 함께 충돌 없음 (formatting.py 는 건드리지 않음).

**메모리 교훈 반영**:
- `feedback_stale_container_vs_source.md` — Phase 0 에 `docker exec find` 검증 의무화
- `feedback_respond_tool_use_xml_leak.md` — Phase 1 이 본체
- `feedback_eval_district_code_hardcode.md` — 본 Plan 과는 별도. Round 3 eval 재설계 시 반영 예정

## 6. Scenario (E2E Ring Mapping)

배포 검증 후 수동 smoke 만 수행 (E2E ring 재실행은 Refactor Pass 2 이후 묶음 예정).

| ID | message | district_code | 기대 |
|---|--------|:--:|------|
| P0-S3 | "홍대 vs 성수 매출 비교" | (none) | tool input `district_codes` 에 `3120103`, `3120052` 포함. `cards` non-empty. 응답에 `<tool_use>` 없음 |
| P0-S7 | (S7-pre 후) "거기 중에 유동인구 더 많은 곳?" | (none) | P0-S3 히스토리 anchor 가 복원되어 `compare_districts` 재실행 OR clarification fallback |
| P0-S8 | "홍대 말고 성수역이랑 건대 비교" | (none) | district_codes=[3120052, 3120053]. "홍대" 단어 응답 미포함. XML 없음 |
| P0-S3-XML | "홍대 vs 성수 매출 비교" | (none) | 응답 본문 `<tool_use>` / `<get_*>` 패턴 0회 |

## 7. Pass 반복

- **Pass 1 (본 세션)**: 기본 구현 + Phase 0 배포 + P0-S3/S7/S8 smoke. Fail 시 로그 원인 파악 후 수정.
- **Pass 2 (후속)**: Refactor Pass 2 완료 후 Round 3 eval 전체 (S1~S8) 재측정. 목표 8.5/10.
- **Pass 3 (후속)**: KPI 85+ 달성 전까지 프롬프트 microtuning.

## 8. Agent 모델 선택

- 설계 (본 Plan 작성): Opus
- 구현: Sonnet (기존 컨벤션)
- 검증 smoke: 현 Opus 세션에서 직접 curl

## 9. Validation

- ruff check server/ 0 errors
- 컨테이너 배포 후 `docker exec backend python -c "from server.agent.utils.entity_matching import rank_candidates; print('ok')"` 출력 `ok`
- P0-S3 SSE 에 `"district_codes": ["3120103", "3120052"]` 또는 동등 포함
- P0-S3 응답 텍스트에 `<tool_use>` / `</tool_result>` / `<get_district` regex 매치 0
- P0-S8 응답 텍스트에 `홍대` 단어 미포함
- P0-S7 응답에 tools=0 이면서도 할루시 수치("만명" 등) 0 — clarification fallback 정상

## 10. Metadata

- 작성: 2026-04-24, Claude Opus 4.7
- 시작점: Round 2 eval 7.6/10 FAIL + 배포 드리프트 발견
- 완료 목표: 본 세션 내 Pass 1 smoke PASS
- 선행: W1~W3 (accuracy-gap-fix.md) — 본 Plan 은 해당 fix 의 실제 배포 + 조정
- 후행: Round 3 eval Plan
