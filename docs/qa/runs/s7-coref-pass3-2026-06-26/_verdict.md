# S7 coref 수치 날조 fix — Pass 3 라이브 검증 Verdict

> 2026-06-26 · USE_MOCK=false · 1,650 상권 · LLM=anthropic(claude-sonnet-4-6)
> Plan: [s7-coref-toolless-fabrication.md](../../../plan/fix/s7-coref-toolless-fabrication.md)

## 시나리오 (R3-COREF-NUMERIC-01)

2턴, 동일 session_id, ×5 반복:
1. T1: "홍대랑 성수 비교해줘" → compare 카드 (floating_pop 실값 기록)
2. T2: "거기 중 유동인구가 더 많은 곳은 어디야?" → coref 후속질문

## DB Ground Truth (2025Q4, floating_population 시간대 합계)

| 상권 | code | 집계(daily_avg 필드) | 시간대 peak |
|---|---|---|---|
| 홍대입구역 | 3120103 | 4,106,209 (≈411만) | 988,851 |
| 성수역 | 3120052 | 1,412,369 (≈141만) | 312,134 |

정답: 홍대 > 성수 (약 2.9배)

## 결과

| 기준 | 1차 (guard 전) | 2차 (guard 후) |
|---|---|---|
| `get_floating_population` tool 호출률 | 5/5 | **5/5** |
| 정답(홍대) | 5/5 | **5/5** |
| 원래 날조값(124,386/67,741) 재현 | 0/5 | **0/5** |
| 물리 모순(파생 일평균 > 시간대 peak) | **3/5 ❌** | **0/5 ✅** |
| headline 수치 DB 일치 | 5/5 | 5/5 |

직전 eval Round 2 회귀(S7 8.9→5.0)의 **주원인이던 tool-less 전면 날조는 force-plan 분기로 구조적 해소** — 5/5 tool 강제 발화. 재채점 9.3+ 목표 충족.

## 근본원인 2건

### RC1 — S7 일차 회귀: tool-less 수치 날조 (planner, prior 세션 fix)
- follow-up이 district_code 없음 + intent≠comparison → comparison history 스캔 skip → summary plan이 demote 블록에서 빈 plan 강등 → Respond가 trim된 history로 124,386/67,741 날조 (카드 실값 411만/141만 무시).
- **fix**: `planner.py` demote 직후 force-plan 분기 — numeric 키워드 + 빈 plan + history 복구 상권 ≥1 → `get_floating_population` 강제 승격. `_scan_history_districts` 헬퍼 추출(comparison/numeric 공용).

### RC2 — 2차: respond 파생 '일 평균' 오계산 (이번 세션 fix)
- repository가 반환하는 `daily_avg` 필드는 실제로 **분기 시간대 합계**인데 이름이 "daily_avg"라 respond LLM이 "일 평균"으로 라벨 → 4.1M을 ÷30/÷3로 "보정" 날조 → 시간대 peak 초과 물리 모순. 프롬프트 예시("하루 평균 12만 4천명")도 부추김. `peak` 값은 반환 안 됨(`peak_hour`=슬롯 인덱스).
- **fix**: `respond.py` `RESPOND_SYSTEM_PROMPT`에 `FLOATING_POP_PRESENTATION_RULES` 추가 — 집계값 그대로 인용, ÷일수 파생 금지, peak는 `by_hour` 실값 있을 때만 인용. (필드명 변경은 카드/테스트 blast radius로 범위 밖 → follow-up.)

## 부수 인프라 fix
- `graph.py:74/96` 하드코딩 모델 `claude-sonnet-4-20250514` → 현 키에서 404(은퇴) → anthropic provider respond 전량 실패. `claude-sonnet-4-6`(현 키 유효)로 교체. S7과 무관한 별개 breakage이나 Pass 3 선결 조건.

## 검증 환경 메모
- backend: `catchment-area-analysis-backend:latest` 이미지를 `backend-dev`로 태그 후 `--profile dev --no-build` 기동(빌드 SSL 우회) → `./server:/app` bind-mount + `--reload`로 미커밋 소스 라이브 반영.
- ruff check/format PASS (respond.py/graph.py/planner.py). 어떤 테스트도 프롬프트 텍스트·모델 문자열 assert 안 함.
- pytest 재실행은 본 환경(호스트 앱-deps 부재 + 컨테이너 pytest 부재)에서 불가 — planner.py+test_coref(16)는 prior 세션 148 passed, 이번 변경은 그 경로 미접촉.
- raw: `.gstack/s7_pass3_results.json` (gitignore).

## Verdict: ✅ PASS (DONE)
plan 기준 4종(tool 5/5 · DB일치 · 물리모순 0 · 정답 5/5) 전부 충족.

## Follow-up (별건)
- 🔧 `daily_avg` 필드명 정정(`quarter_total` 등) — repository + 카드 + mock parity + 테스트 동반 수정 필요(blast radius). 본 Pass는 프롬프트 가드로 대응.
