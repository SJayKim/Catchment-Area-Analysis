# Out-of-Scope Handling — 서울 외 지역 질문 거부

> 카테고리: fix
> 생성일: 2026-04-29
> 담당: sjkim
> 모델: 설계 opus / 구현 sonnet / 검증 haiku
> 상태: ✅ 완료 (2026-07-04 문서 정합성 감사에서 구현 완료 확인 — intents.yaml `out_of_scope` · planner short-circuit · `_CLARIFICATION_TEMPLATES["out_of_scope"]` · `STRONG_TOP1_MIN=0.70` · `test_out_of_scope.py` 전부 현행 코드에 존재)

## Context

### 문제
현재 시스템은 "부산 해운대 상권 알려줘", "제주 분석" 같은 서울 외 지역 질문을 받으면:
1. **명확한 비-서울 지명** → entity 매칭 0건 → ambiguous → clarification (현재 동작 OK, 단 광역지명 거부 메시지 부재)
2. **이름 우연 일치** (가상의 부산 시장명이 서울 전통시장과 W1 fuzzy 매치) → silent wrong-district 분석 응답 (HIGH 위험)
3. **메타 질문** ("서울 외에는?") → respond LLM 자유 응답, 일관성 없음

목표: **명시적 out-of-scope intent + 강한 entity 임계 + system prompt 거부 룰** 3중 가드로 silent 오답 0건 달성.

### 메모리 참조
<!-- 2026-07-04 정합성 감사: 옛 머신(cyon1) auto-memory 절대경로 링크는 현 환경에서 해석 불가 → 평문 전환 (교훈 요지는 보존) -->
- [[feedback_eval_district_code_hardcode]] — DB ground truth + entity linking 검증 패턴
- [[feedback_comparison_intent_halluc]] — entity 매칭 실패 시 LLM 일반지식 fallback 으로 40~80% hallucination
- [[feedback_respond_tool_use_xml_leak]] — LLM 거부 룰 + sanitizer 패턴
- [[project_e2e_port_convention]] — dev=8000/3000, E2E=8002/3001

### 관련 Plan
- [accuracy-gap-fix.md](./accuracy-gap-fix.md) — W1 entity_matching baseline
- [accuracy-gap-eval-round2-2026-04-24.md](./accuracy-gap-eval-round2-2026-04-24.md) — Round 2 P0 #2 multi-district regression
- [data-trust-reliability-2026-04-24.md](./data-trust-reliability-2026-04-24.md) — numeric_sanity Pattern 재사용

### 코드 스폿
- `server/server/agent/config/intents.yaml` — intent 패턴 + plan
- `server/server/agent/nodes/planner.py:38` — `_CLARIFICATION_TEMPLATES` (3종 → 4종 확장)
- `server/server/agent/nodes/planner.py:520` — clarification short-circuit 구간
- `server/server/agent/utils/entity_matching.py` — `TOP1_MIN=0.55`, `pick_best`
- `server/server/agent/prompts/system.py:3` — `_BASE_PROMPT` 역할 정의
- `server/server/agent/nodes/respond.py:229` — `RESPOND_SYSTEM_PROMPT`

---

## Scope

### In-scope
1. `intents.yaml` 에 `out_of_scope` intent 추가 — 광역지명(도/광역시) + 시단위 + 명시적 메타 질문 패턴
2. Planner 에 `out_of_scope` 분기 — LLM 호출 없이 즉시 `clarification_direct` 반환
3. `_CLARIFICATION_TEMPLATES` 에 `out_of_scope` 템플릿 추가 (suggestion 3종)
4. `system.py::_BASE_PROMPT` 에 거부 룰 명시 + `respond.py::RESPOND_SYSTEM_PROMPT` 동일 룰 미러
5. `entity_matching.py` 에 `STRONG_TOP1_MIN=0.70` 추가 — district_code 미선택 + 약한 매치(0.55~0.70) 시 abstention
6. Unit test 4종 신규 (광역지명 / 시단위 / 메타질문 / silent wrong 회귀)

### Out-of-scope (별도 plan)
- F-02 comparison hallucination 추가 fix (별도 plan)
- E2E Playwright spec — backend 변경 후 회귀는 다음 sweep 에 포함
- W1 type_boost 약화 케이스 — Round 3 eval 에서 별도 측정

---

## Design

### 3중 가드 설계

```
User message ("부산 해운대 알려줘")
    │
    ▼
[Layer 1] intents.yaml::out_of_scope
    pattern = "(부산|대구|인천|광주|대전|울산|세종|제주|경기|강원|충청|전라|경상)"
    → intent="out_of_scope", confidence=0.95
    │
    ▼
[Layer 2] planner.py: out_of_scope short-circuit
    → 즉시 clarification_direct (LLM 호출 0건, ~1ms)
    → user 에게 "서울시 1,650개 상권만 지원합니다" 안내
    │
    ▼ (Layer 1/2 우회 실패 시 — 가상 비-서울 시장명 등)
[Layer 3] entity_matching: STRONG_TOP1_MIN=0.70
    district_code 미선택 + 매치 score < 0.70 → referenced_districts 비우기
    → ambiguous → clarification (district_missing)
    │
    ▼ (모든 가드 우회 시 — 실수로 LLM 호출됨)
[Layer 4] respond.py: RESPOND_SYSTEM_PROMPT 거부 룰
    "서울 외 지역에 대한 분석 요청은 정중히 거절하세요"
```

### 패턴 설계 — out_of_scope

```yaml
out_of_scope:
  # 우선순위: greeting 다음, 다른 모든 intent 보다 먼저
  pattern: >-
    (부산|대구|인천|광주|대전|울산|세종|제주|경기|강원|충청남?|충청북?|전라남?|전라북?|경상남?|경상북?
    |해운대|광안리|서면|기장|대명|중구|동구|서구|남구|북구
    |수원|성남|용인|안양|부천|평촌|일산|분당|판교|동탄|광교
    |강릉|속초|춘천|원주
    |청주|천안|아산|세종|논산|공주
    |전주|군산|익산|순천|여수
    |창원|마산|김해|진주|포항|경주|안동
    |서귀포|애월|함덕)
  flags: IGNORECASE
  plan: []
```

> ⚠ 광역지명만 토큰으로 사용 (서울에 같은 동/구명이 있을 수 있어 시단위는 제한적). 부산/제주/경기 등 17개 광역지자체 중 서울 외 16개 + 주요 부산 동(해운대/광안리/서면) + 경기 주요 신도시(분당/판교/동탄/광교) + 제주(서귀포/애월/함덕) 보강.

> ⚠ Order matters — `intents.yaml` 에서 greeting 다음, comparison/summary 보다 먼저 위치. 그래야 "부산 vs 강남 비교" 같은 mixed query 도 out_of_scope 로 라우팅.

### Clarification 템플릿

```python
"out_of_scope": {
    "text": (
        "현재 마켓스코프는 **서울시 1,650개 상권**만 지원합니다. "
        "서울 외 지역 (부산, 인천, 경기 등) 데이터는 아직 제공하지 않습니다. "
        "서울 상권에 대해 알려드릴까요?"
    ),
    "suggestions": [
        "강남역 상권 요약",
        "홍대 vs 성수 비교",
        "명동 창업 추천 업종",
    ],
}
```

### entity_matching 가드

```python
# entity_matching.py
STRONG_TOP1_MIN = 0.70  # district_code 미선택 시 적용
TOP1_MIN = 0.55         # 기존 — 이름 명시 + 컨텍스트 있음

def pick_best(candidates, *, strong: bool = False):
    floor = STRONG_TOP1_MIN if strong else TOP1_MIN
    ...
```

planner 에서 호출 시:
```python
# planner.py 라인 374 부근
multi = await get_data_access().districts.detect_districts_in_message(message)
# 새 로직: district_code 미선택 + 가장 높은 매치 score < STRONG_TOP1_MIN 이면 drop
if not district_code and multi:
    weak_only = all(m.get("score", 0) < STRONG_TOP1_MIN for m in multi)
    if weak_only:
        logger.info("planner.entity-match-weak dropping refs=%s scores below %.2f",
                    [m["code"] for m in multi], STRONG_TOP1_MIN)
        multi = []
```

> 단, repository 의 `detect_districts_in_message` 응답 dict 에 `score` 키가 이미 있음(라인 200~). 호출자에서 필터링하는 게 데이터 레이어 변경 0.

### system prompt 거부 룰 (라인 추가)

```text
11. **서비스 범위**: 서울시 1,650개 상권에 한정합니다. 부산/대구/인천/광주/대전/울산/
    세종/제주/경기/강원/충청/전라/경상 등 서울 외 지역에 대한 분석 요청은 정중히 거절하고
    서울 상권을 안내하세요. 가상의 데이터를 만들어 답변하지 마세요.
```

---

## Checklist (원자적, 검증 가능)

### Pass 1 — 기본 (out-of-scope 명시 거부)

- [x] `agent/config/intents.yaml` 에 `out_of_scope` intent 추가 (greeting 직후, comparison 앞)
- [x] `non_summary_overrides` 패턴에 영향 없는지 확인 — 광역지명 토큰이 우연히 매칭되지 않도록
- [x] `agent/nodes/planner.py::_CLARIFICATION_TEMPLATES` 에 `out_of_scope` 키 추가
- [x] `planner_node` 에서 rule 분류 직후 `intent == "out_of_scope"` 분기 추가 → 즉시 clarification 반환
- [x] `agent/prompts/system.py::_BASE_PROMPT` rule 11 추가
- [x] `agent/nodes/respond.py::RESPOND_SYSTEM_PROMPT` 동일 룰 미러
- [x] `server/tests/test_out_of_scope.py` 신규 — 4 케이스 (실제 구현은 7 함수 / parametrize 포함 21 케이스)
  - [x] "부산 해운대 상권 알려줘" → out_of_scope clarification
  - [x] "제주 vs 강남 비교" → out_of_scope clarification (mixed)
  - [x] "분당 신도시 분석" → out_of_scope clarification
  - [x] "강남역 요약" (제어군) → out_of_scope 으로 분류되지 않음

### Pass 2 — 엣지 (silent wrong-district)

- [x] `agent/utils/entity_matching.py` 에 `STRONG_TOP1_MIN = 0.70` 상수 추가
- [x] `planner.py` 의 `detect_districts_in_message` 호출 후 weak match 필터링 (최종 구현은 `api/routes/chat.py` message-detect 분기에서 `score < STRONG_TOP1_MIN` 거부로 위치 확정)
- [x] `server/tests/test_entity_matching.py` 에 `STRONG_TOP1_MIN` 시나리오 추가 (실제 수록 위치는 `test_out_of_scope.py` — `STRONG_TOP1_MIN > TOP1_MIN` + 0.65~0.80 범위 가드)

### Pass 3 — 검증 (regression + 성능)

- [x] `ruff check server/` All passed
- [x] `pytest server/tests/` — 기존 49 + 신규 5+ PASS, 회귀 0 (test_smoke env-dep 1건 제외) — 실측 70/71 (신규 21 + 기존 49)
- [x] manual smoke (Mock 모드, USE_MOCK=true): backend `:8000` 띄워 curl 4종
  - "부산 해운대 알려줘" → out_of_scope text
  - "제주 vs 강남" → out_of_scope text
  - "강남역 요약" → 정상 summary 카드
  - "비교해줘" (district 없음) → comparison_under_2 clarification (회귀 0)
- [x] `docs/status/current-status.md` 갱신 (`/status-update`)
- [ ] memory `feedback_out_of_scope_handling.md` 신규 + MEMORY.md 인덱스 추가 (2026-07-04 감사: 현 머신 auto-memory 에 해당 파일 부재 — 미확인)

> ✅ 2026-07-04 문서 정합성 감사에서 구현 완료 확인: `intents.yaml:18 out_of_scope` · `planner.py` `_CLARIFICATION_TEMPLATES["out_of_scope"]` + `intent == "out_of_scope"` short-circuit(`clarification_direct`) · `entity_matching.py STRONG_TOP1_MIN = 0.70`(적용부는 chat.py message-detect 분기) · `test_out_of_scope.py` 7 함수(21 케이스). 실행 결과는 status 2026-04-29 기록(ruff PASS · pytest 70/71 · 회귀 0).

---

## 재검토 (Self-Review Gate)

### 엣지 케이스
- ✅ "강남역 부근 부산 횟집" 같이 서울 상권 + 비-서울 단어 혼재 → out_of_scope 우선 분류 (false positive 위험). **결정**: 광역지명 토큰이 있으면 out_of_scope 우선. 사용자가 의도한 게 명확하지 않으니 거부 안내가 안전.
- ✅ "부산물" / "광주리" / "경상도식" 등 형태소 충돌 → 패턴에 `\b` 또는 `(?:^|[\s,!?.])` 가드. 단순 alternation 은 부산물 매치. **결정**: word-boundary 추가.
- ✅ 서울 안의 "구로" / "광주" / "대구식당" 같은 토큰 → 서울 상권명에 광역지명 substring 가능. **결정**: 광역지명 단독 토큰만 매치 (예: `\b부산\b`, `\b광주(?!시?\s*[가-힣]*역)\b`). 다만 한국어는 띄어쓰기 부재가 흔하므로 보수적 패턴 + manual smoke 검증.
- ✅ "서울 외에 다른 지역도 가능?" 메타 질문 → out_of_scope 패턴 미매치 → 일반 ambiguous → respond LLM 이 역할 인지로 거부. **결정**: 별도 패턴 불필요, system prompt 룰로 충분.

### 메모리 교훈 충돌
- `feedback_eval_district_code_hardcode` — DB ground truth 검증 권장. **적용**: STRONG_TOP1_MIN 도입 이유 = 가상 매치 silent wrong-district 차단 (DB 가 없는 부산명도 0 점수 보장).
- `feedback_formatter_strips_unused_imports` — 새 import 와 사용 지점 같은 Edit 에 묶기. **적용**: STRONG_TOP1_MIN 정의 + 사용 같은 commit.

### 타 Plan 충돌
- ✅ `accuracy-gap-fix.md` W1 — entity_matching 의 TOP1_MIN/CLOSE_DELTA 보존. STRONG_TOP1_MIN 은 별도 상수 (additive).
- ✅ `data-trust-reliability-2026-04-24.md` numeric_sanity — entity mismatch ratio 검출은 그대로. out_of_scope 단축은 그 *전*에 짧게 끝남.
- ✅ `p0-priority-2026-04-27.md` clarification 3종 — 4번째 키 추가만, 기존 키 영향 0.

---

## Scenario (E2E Ring Mapping)

| Ring | Feature | Case ID | 시나리오 |
|---|---|---|---|
| Ring1 | F02 (Agent) | `R1-F02-OOS-METRO` | "부산 해운대 알려줘" → out_of_scope clarification + 3 suggestion chips |
| Ring1 | F02 (Agent) | `R1-F02-OOS-MIXED` | "제주 vs 강남 비교" → out_of_scope (mixed query) |
| Ring1 | F02 (Agent) | `R1-F02-OOS-CITY` | "분당 신도시 분석" → out_of_scope |
| Ring3 | Negative | `R3-NEG-OOS-WEAK` | district_code 미선택 + 약한 매치 가상명 → ambiguous (silent wrong 회귀) |
| Ring3 | Negative | `R3-NEG-OOS-CONTROL` | "강남역 요약" → 정상 summary (false positive 회귀) |

> Backend pytest 우선, Playwright spec 은 다음 sweep 에 포함 (E2E preflight stack 부재로 본 Plan 에선 backend unit + manual smoke 만).

---

## Pass 반복

### Pass 1 — 기본 동작
**목표**: out_of_scope 명시 거부 4 케이스 PASS.
**Fail 시**: pattern 좁히기 / 우선순위 재배치 → 재실행.

### Pass 2 — 엣지 (silent wrong-district)
**목표**: STRONG_TOP1_MIN 가드로 약한 매치 abstention.
**Fail 시**: 임계치 조정 (0.65~0.75 범위 탐색) → 재실행.

### Pass 3 — 회귀 + 성능
**목표**: 기존 49 unit + 신규 5+ ALL PASS, ruff clean, manual smoke 4 케이스 OK.
**Fail 시**: 회귀 발생 시 root cause 찾아 fix, 단순 임계치 조정으로 회피 금지.

---

## Agent 모델 선택

- 설계 (본 Plan): **opus 4.7** (현재 세션, 패턴 우선순위 + 엣지 케이스 reasoning)
- 구현 (intents.yaml + planner.py + system.py + entity_matching.py): **sonnet 4.6** (구체적 코드 변경, 패턴 매칭)
- 검증 (pytest + ruff + smoke): **haiku 4.5** (mechanical execution)

> Auto mode 이므로 단일 세션에서 일괄 진행 — 모델 전환 명시는 trace 용이성 목적.

---

## Validation

### Acceptance Criteria
1. Backend pytest **신규 4+ test 100% PASS**
2. Backend pytest **기존 49 회귀 0** (test_smoke 1건 env-dep 제외)
3. ruff `server/` **All checks passed**
4. Manual curl 4 케이스 **out_of_scope text 노출 + tool 호출 0건**
5. silent wrong-district 시나리오 **약한 매치 시 abstention 동작**

### KPI
- LLM 호출 비용: out_of_scope 0건 (현재는 ambiguous → respond LLM 1회 호출 ~$0.001/req)
- 응답 시간: out_of_scope < 50ms (현재 ambiguous ~2s)

---

## Metadata

- 생성: 2026-04-29
- 마지막 업데이트: 2026-07-04 (문서 정합성 감사 — 체크리스트/상태 실태 반영)
- 상태: ✅ 완료 (2026-07-04 문서 정합성 감사에서 구현 완료 확인)
- 관련 commit: (구현 후 추가)
- 참조 메모리: 4건 (Context 섹션 참조)
