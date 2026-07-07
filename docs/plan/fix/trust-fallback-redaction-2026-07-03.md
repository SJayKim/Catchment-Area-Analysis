# Plan — Trust Kernel fallback 응답 붕괴 fix (redaction 전환) + S8 스케일 가드 (2026-07-03)

## Context

Eval Round 3 GATE FAIL의 원인 P1/P2 수정 (verdict·R3 plan → git history; gate-fail 분기 → 사용자 1안 확정: fix → S 재측정 → gate 재판정 → 통과 시 배포).

**근본 원인 (코드 확정)**:

1. **RC-A (S2 abstention 오발)**: `engine.py:211`이 fact_pool 키를 `{tool}#{idx}`로 저장하는데 `numeric_sanity._collect_tool_scalars`(L229)는 `candidate_tool != tool_name` 완전일치 비교 → **v2에서 typed scalar 수집 0**. 바인딩은 wildcard leaf로 살아있지만 `grounded_fallback`은 typed 수집에만 의존 → 도구 5회+카드 2장인데 "no-scalars" abstention 분기("죄송합니다...가져오지 못했습니다") 오발. 2차: topCategories 항목 키가 `count`인데 `storeCount/store_count`만 조회.
2. **RC-B (S4 나열 붕괴)**: `engine.py:255-258` — 교정 후 still unbound면 **draft 전체를 grounded_fallback으로 대체**. unbound는 보통 모델이 prose에서 암산한 파생값 2~4개뿐인데 나머지 95% 품질(업종명·해석·시사점)까지 소각. S4 재현 2/2 결정론.
3. **RC-C (S8 10배 오기 통과)**: `match_numbers_to_tools` 원화 floor 10,000,000 → "145만 원"(1.45M)은 채점 제외라 trust gate 무통과.

**설계 (최소 외과 수정)**:

- **전체 대체 → 외과적 redaction**: still unbound 시 unbound 스팬(ExtractedNumber.start/end)이 포함된 **라인만 제거**(마크다운 표 행/불릿 구조 유지). `_is_answer_shaped` + `is_grounded` 재검 통과 시 채택, 아니면 기존 fallback (invariant 불변: 날조 수치는 여전히 절대 못 나감).
- **키 정규화**: `_collect_tool_scalars`에서 `tool_name.split("#", 1)[0]` 비교 (PAE 경로는 plain 키라 no-op). topCategories `count` 키 추가.
- **v2 전용 floor**: `match_numbers_to_tools(thresholds=...)` 옵션 파라미터 신설(기본값 = 현행 dict → PAE 불변), trust.py가 원화 floor 1,000,000 전달 → 145만 류 스케일 오기가 gate에 걸림 → redaction으로 해당 라인 제거.
- **프롬프트 1줄**: LOOP_SYSTEM_PROMPT 출력 절에 만/억 환산 자릿수 검산 규칙 (트리거 빈도 자체를 낮춤).

**메모리 교훈 인용**: `feedback_formatter_strips_unused_imports`(신규 import는 사용 Edit과 동일 Edit에) · `feedback_stale_container_vs_source`(bind-mount여도 restart 후 컨테이너 실값 검증) · `feedback_redis_cache_serves_old_card_text`(재측정 전 flush) · `feedback_bash_cwd_persists_between_calls`(절대경로) · `feedback_python_utf8_windows`(인라인 검증 스크립트 UTF-8) · `feedback_marketscope_sse_format`(data: 임베드 파싱)

**Blast radius**: `match_numbers_to_tools`/`_collect_tool_scalars`/`grounded_fallback` 사용처 = engine.py·trust.py·numeric_sanity.py 3파일 전수 확인. PAE 경로(graph/respond/abstention)는 다른 함수(extract_numbers 등)만 import — 기본값 유지로 불변.

## Scope

- 수정: `server/server/agent/utils/numeric_sanity.py` · `server/server/agent/loop/trust.py` · `server/server/agent/loop/engine.py` · `server/server/agent/loop/prompts.py`
- 신규: `server/tests/test_trust_redaction.py`
- 불변: PAE 경로 전체, 카드/SSE 계약, tools_fc, models

## Checklist

- [ ] C1 `numeric_sanity._collect_tool_scalars` — `#idx` 접미사 정규화 + topCategories `count` 키
- [ ] C2 `numeric_sanity.match_numbers_to_tools` — `thresholds` 옵션 파라미터 (기본 현행)
- [ ] C3 `trust.py` — `_V2_UNIT_FLOORS`(원 1M) 전달 + `redact_unbound(text, unbound)` 신규
- [ ] C4 `engine.py` — still-unbound 분기를 redaction-first로 교체 (fallback은 degenerate 시만)
- [ ] C5 `prompts.py` — 만/억 환산 검산 1줄
- [ ] C6 unit 테스트 9케이스 (redaction 3 · 키fix 3 · floor 3) — 컨테이너 실행
- [ ] C7 ruff check/format PASS
- [ ] C8 e2e backend restart → 컨테이너 실값으로 새 코드 반영 검증
- [ ] C9 flush → S1~S8 + S7-run2 전체 재수집 (R3.1) → 파싱·채점·gate 재판정
- [ ] C10 gate PASS 시 R3 plan Item 2 (E~J) 진행 / FAIL 시 정지·보고

## 재검토 (Self-Review Gate)

- **동일 도구 다회 호출 키 충돌?** `#idx` 정규화는 비교 시점만 — pool 키 자체는 유일 유지, 병합 없음.
- **PAE 회귀?** thresholds 기본값 = 기존 dict 리터럴 그대로, split은 plain 키에 no-op. `test_numeric_sanity.py` 6케이스로 확인.
- **redaction이 표 헤더/구분행 제거?** 헤더에 대형 수치 없음(라벨 행). 데이터 행 제거는 표 구조 유지.
- **redaction 공회전?** 채택 조건 = `_is_answer_shaped` AND `is_grounded` 재검 — 실패 시 기존 fallback (동작 후퇴 없음).
- **floor 1M 오탐?** R3 만점 답변 전수 스캔: ≥100만원 표기(1,396억/532억/3,864만/1,615만/550억/4,600만...)는 전부 도구 leaf ±5% 내 — 오탐 0. 27,641원/54,082원/12,000원류는 <1M이라 비채점 유지.
- **교정 패스 유지?** 유지 — redaction은 교정 실패 후의 3차 방어. 순서: draft → 교정(LLM) → redaction(결정론) → fallback(결정론).

## Scenario (E2E Ring Mapping)

| ID | 시나리오 | 기대 |
|---|---|---|
| R3-TRUST-KEYFIX-01 | S2 "서울역 상권 분석" | abstention 미출력, 리포트 또는 redacted 리포트 |
| R3-TRUST-REDACT-01 | S4 "건대 창업 추천 업종?" (결정론 재현) | 무라벨 나열 미출력, 업종명 포함 리포트(unbound 라인만 제거 가능) |
| R3-SCALE-GUARD-01 | S8 "홍대 말고 성수역이랑 건대 비교" | "145만" 류 10배 축소 표기 없음 (정확 표기 또는 해당 라인 제거) |
| 회귀 | S1/S3/S5/S6/S7(+run2) | R3 만점 유지, trust 로그 오발 0 |

## Pass 반복

- **Pass 1 (unit)**: C6 9케이스 + 기존 test_numeric_sanity 6 + test_v2_loop_qa_regressions 전체 — 컨테이너 pytest(부재 시 인라인 assert)
- **Pass 2 (라이브 스팟)**: restart 후 S2/S4/S8 단건 재현 — fallback 미발동 or redaction 채택 로그 확인
- **Pass 3 (풀 재측정)**: R3.1 전체 수집(`OUT=docs/qa/runs/eval-round3.1-2026-07-03`) → 채점 → gate 4항목 재판정 → verdict 갱신

## Agent 모델 선택

설계·구현·검증 = 본 세션 직접 (blast radius 3파일, 위임 오버헤드 > 이득). 재측정 수집은 기존 스크립트 재사용.

## Validation

- ruff check/format PASS
- unit: 신규 9 + 기존 무회귀
- 라이브: gate 4항목 (평균 ≥9.0 · R2 이상 · 날조 0 · S7 ≥9.3)

## Metadata

- 날짜: 2026-07-03 · 카테고리: fix · 선행: eval-round3 verdict · 후속: R3 plan Item 2 (gate PASS 시)
