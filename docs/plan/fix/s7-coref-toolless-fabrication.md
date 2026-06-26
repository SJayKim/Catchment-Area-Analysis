# S7 coref 후속질문 tool-less 수치 날조 fix

## Context

- 2026-06-10 Accuracy Eval Round 2 (Item 4) 에서 S7 회귀 노출 (8.9 → 5.0). S3(홍대 vs 성수 비교) 직후 "거기 중 유동인구가 더 많은 곳은 어디야?" 후속질문에 **tool 0건 / card 0건**으로 응답하며, 직전 compare 카드의 실값(홍대 411만 / 성수 141만)을 인용하지 않고 124,386 / 67,741 을 날조. "일평균 124,386 > 시간대최고 52,179" 물리 모순까지 발생. 방향(홍대>성수)만 정답.
- 근본 원인: coref 후속질문이 planner 에서 plan 없이 `response_mode="direct"` 로 빠지면 Respond LLM 이 history(300자 trim된 텍스트)만으로 답한다. W1 abstention/attribution 가드는 **actor tool 결과 경로만** 커버 — tool-less 경로의 수치 주장은 미포착.
- 접근 결정(2026-06-10 복원 세션): ⓐ **수치 coref 후속질문에 tool 강제 재호출** (DB가 진실) 채택. ⓑ(카드값 인용 강제)는 LLM 준수 의존이라 보조 가드로만 병행.
- 검증 출처: [eval-round2-2026-06-10/_verdict.md](../../qa/runs/eval-round2-2026-06-10/_verdict.md) (S7.sse / S7-pre.sse 캡처 보존)
- **Memory 참조**:
  - `feedback_coref_followup_toolless_halluc.md` — 증상·원인·접근 ⓐ/ⓑ 정리. eval 시 tool_events 카운트 + 카드 payload 대조 필수
  - `feedback_sse_hallucination_needs_db_gt.md` — SSE 캡처만으론 부족, DB ground truth 직접 쿼리 병행
  - `feedback_comparison_intent_halluc.md` — tool error → LLM 일반지식 fallback 시 40~80% 오차 (동일 계열 실패 모드)

## Scope

- **In Scope**:
  - planner 의 direct-mode 진입 전, 수치 데이터 키워드 + coref/history 상권 보유 시 tool plan 강제 생성
  - Respond 시스템 프롬프트에 tool-less 수치 주장 금지 보조 룰 (ⓑ 보조 가드)
  - 단위 회귀 테스트 + S7 시나리오 재측정 (재현율 포함)
- **Out of Scope**:
  - W1 abstention 가드 전면 재설계
  - 세션 카드 payload 를 Respond 컨텍스트에 구조화 주입하는 아키텍처 변경 (별도 Plan 후보)
  - history 저장 포맷 변경 (300자 trim 유지)

## Design

- **접근 (ⓐ 주 + ⓑ 보조)**:
  1. **수치 키워드 → tool 매핑 상수** 신설: `유동인구→get_floating_population`, `매출→get_estimated_sales`, `점포/창업→get_store_info`, `인구→get_population_info`. 한글 키워드 매칭은 단순 substring (out_of_scope 가드처럼 word-boundary 필요한 충돌 토큰 아님 — 재검토 게이트에서 false-positive 점검).
  2. **planner.py**: response_mode 결정(L540) 직전·후 지점에서 다음 조건이 모두 참이면 plan 을 강제 빌드하고 `tool_assisted` 로 승격:
     - `plan` 이 비어 있고 (direct 로 빠질 상황)
     - 메시지에 수치 키워드 매칭 1건 이상
     - `referenced_districts` ≥ 1 (coref anchor 또는 comparison history fallback 으로 채워진 경우 포함). `< 1` 이면 기존 `coref_no_anchor` clarification 경로 유지 — 변경 없음
     - 강제 plan = 매칭된 tool × referenced_districts (≤3, CompareCard cap 과 동일)
  3. **comparison history fallback 재사용**: 현재 L460 history 스캔이 `intent == "comparison"` 게이트 안에 있음. S7 류("거기 **중** 더 많은 곳")는 intent 가 comparison 으로 분류되지 않을 수 있으므로, 수치 coref 분기에서도 동일 history 스캔을 호출할 수 있게 헬퍼로 추출 (기존 comparison 경로 동작 불변 — surgical).
  4. **ⓑ 보조 가드**: `respond.py::RESPOND_SYSTEM_PROMPT` 에 룰 1줄 추가 — "tool 결과가 없는 턴에서는 새로운 수치를 제시하지 말 것. 직전 분석 수치가 필요하면 그 값을 그대로 인용하거나 재분석을 제안할 것."
- **변경 파일**:
  - `server/server/agent/nodes/planner.py` : 수치 키워드 상수 + 강제 plan 승격 분기 + history 스캔 헬퍼 추출
  - `server/server/agent/nodes/respond.py` : RESPOND_SYSTEM_PROMPT 룰 1건 추가
  - `server/tests/test_coref_numeric_followup.py` : 신규 단위 테스트
- **의존성 / 선행 Plan**: 없음. ISSUE-003 fix(`90937c6`)와 독립 경로. [accuracy-gap-fix.md](accuracy-gap-fix.md) GAP-D 잔여분에 해당.

## Checklist

- [x] 수치 키워드 → tool 매핑 상수 정의 (planner.py 모듈 레벨, 4 tool / 6 keyword) — `_NUMERIC_FOLLOWUP_TOOLS` + `_numeric_tools_for`. 바레 "인구" 오버랩 회피 위해 "유동"/"상주"/"직장" 매칭
- [x] history 상권 스캔 로직 헬퍼 함수로 추출 (`_scan_history_districts`), comparison 경로 회귀 없음 확인 (동작 동일 리팩터 — 동일 스캔/`>=2` 가드/할당)
- [x] direct-mode 직전 강제 plan 승격 분기 구현 — demote 블록(L546-552) 직후, `numeric_tools and not plan` + history 스캔 결과 1건 이상 → tool_assisted 승격
- [x] referenced_districts 0건 시 기존 clarification 경로 그대로인지 확인 — history 스캔도 0건이면 force branch skip → clarification (test ③)
- [x] RESPOND_SYSTEM_PROMPT 보조 룰 추가 — rule 11 에 "이번 턴 신규 데이터 없으면 새 수치 금지" 1문장 추가(번호 체계 유지)
- [x] 단위 테스트: ① 강제 plan(floating×2) ② 수치 키워드 없는 coref → clarification 유지 ③ anchor 0건 → clarification ④ 키워드→tool 매핑(파라미터 10건) + `_scan_history_districts` 3건 = **16 testcase**
- [x] `cd server && ruff check --fix . && ruff format .` PASS
- [x] 기존 pytest 전체 회귀 0 — **148 passed / 8 skipped**(기준선 132 + 신규 16, real 6 deselected)

## 재검토 (Self-Review Gate)

- [ ] **엣지**: 수치 키워드가 일반 문장에 우연히 포함되는 false-positive (예: "매출 말고 분위기 어때?") — 강제 plan 이 생겨도 tool 결과가 추가 컨텍스트일 뿐 답변 품질 저하인지 확인. 비용(tool 1~3회, LLM 0회 추가)은 수용 가능
- [ ] **엣지**: referenced_districts 가 history 6턴 스캔으로 3개 초과 매칭 시 cap 동작
- [ ] **엣지**: USE_MOCK=true 에서 detect_districts_in_message mock 동작 (mock repo 5상권 한정)
- [ ] **Memory 교훈**: SSE 캡처 + DB ground truth 병행 검증 (`feedback_sse_hallucination_needs_db_gt`) / eval 은 message-only 전송 (`feedback_eval_district_code_hardcode`) / 컨테이너 반영은 docker exec 로 live inspect (`feedback_stale_container_vs_source`)
- [ ] **타 Plan 충돌**: out-of-scope 가드(2026-04-29)의 clarification 분기보다 뒤에서 동작 — out_of_scope intent 는 planner 진입 직후 short-circuit 이므로 충돌 없음. ISSUE-001 suggestion emission fix 와 무관 경로

## Scenario (E2E Ring Mapping)

- **Ring**: 3 (negative/regression) — hallucination 방지 회귀 케이스
- **Scenario ID**: `R3-COREF-NUMERIC-01`
- **사전조건**: Real 스택 (USE_MOCK=false, PostGIS 1,650 상권, backend :8000 health 200). 세션 1개로 2턴 연속 전송
- **실행 단계**:
  1. POST `/api/chat` — "홍대랑 성수 비교해줘" (S3 동일) → compare 카드의 `floating_pop` 실값 기록
  2. 동일 session_id 로 — "거기 중 유동인구가 더 많은 곳은 어디야?" (S7 동일)
  3. SSE 이벤트에서 `tool` 이벤트 카운트 + 응답 텍스트 수치 추출
- **기대 결과**:
  - 2턴째 `tool` 이벤트 ≥ 1 (`get_floating_population`)
  - 응답 수치가 DB `floating_population` 합계와 자릿수 일치 (±환산 오차)
  - 방향(홍대 > 성수) 정답 유지, 물리 모순(일평균 > 시간대최고) 0건

## Pass 반복 (Iteration Plan)

- ✅ **Pass 1 (기본)**: 키워드 상수 + 강제 plan 분기 + 단위 테스트 → pytest 통과 (2026-06-26, 16 testcase)
- ✅ **Pass 2 (엣지)**: false-positive 키워드(거기 어때/추천) / anchor 0건 / 3상권 cap / USE_MOCK mock-DA fixture 보강 + RESPOND 보조 룰 (Pass 1 과 동시 구현)
- ✅ **Pass 3 (회귀 + 재현율)** — *완료 (2026-06-26)*: `R3-COREF-NUMERIC-01` 라이브 5회 반복 → tool 호출률 **5/5** · 정답(홍대) **5/5** · 원 날조값(124,386/67,741) **0/5** · 물리 모순 **0/5**. Verdict [qa/runs/s7-coref-pass3-2026-06-26/_verdict.md](../../qa/runs/s7-coref-pass3-2026-06-26/_verdict.md). 검증 중 2건 추가 처리: (a) `graph.py` 하드코딩 모델 `claude-sonnet-4-20250514`(현 키 404 은퇴) → `claude-sonnet-4-6` — anthropic respond 전량 실패 차단 (별건 인프라). (b) `respond.py` 1차 패스에서 파생 '일평균' 오계산(물리 모순 3/5) 발견 → `FLOATING_POP_PRESENTATION_RULES` 가드 추가 후 2차 패스 0/5. 검증 환경: `backend-dev` 프로필(`./server:/app` bind-mount + `--reload`)로 미커밋 소스 라이브 반영 (이미지 재빌드 SSL 회피용 `--no-build` 태그).
- 각 Pass 후 Scenario 재실행, Fail 시 수정→재실행 루프

## Agent 모델 선택

- **설계**: opus — planner 분기 삽입 지점이 기존 clarification/ambiguous 분기 5곳과 상호작용하므로 심층 추론 필요
- **구현**: sonnet — Design 의 조건·매핑이 명세 수준으로 확정됨
- **검증**: haiku — tool 이벤트 카운트 / 수치 일치 Pass-Fail 판정은 기계적
- 근거: 위험도는 planner 분기 순서(out_of_scope → greeting → clarification → 강제승격 → ambiguous)에 집중, 구현 자체는 ~40줄

## Validation

- 수동: `docker compose restart backend` 후 (Windows/OneDrive bind-mount 파일워치 누락 방지) curl SSE 2턴 시나리오 1회 육안 확인 — `feedback_qa_browse_unstable_use_sse` 관례대로 browse 미사용
- DB ground truth: `docker exec catchment-area-analysis-db-1 psql -U marketscope` 로 홍대(3120103)/성수(3120052) floating_population 합계 추출 후 응답 대조
- 자동: `cd server && pytest tests/test_coref_numeric_followup.py -v` + 전체 pytest. E2E 는 Pass 3 의 5회 반복 스크립트로 갈음 (`/e2e-run 3` 은 기존 ring3 회귀 확인용)

## Metadata

- 작성일: 2026-06-10
- 작성자: Claude Code (plan-new skill)
