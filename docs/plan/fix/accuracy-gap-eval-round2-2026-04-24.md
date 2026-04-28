# Accuracy Gap Eval Round 2 — W1~W3 적용 후 KPI 재측정 (2026-04-24)

## Context

2026-04-13 Round 1 에서 S1~S8 8 시나리오 평균 8.0/10 (FAIL). S3(비교)=2.6, S6(시뮬레이션)=6.1, S7(후속질문)=8.9 가 기준치 9.0 미달. 이는 정확성 축 74/100 의 근거.

2026-04-23 에 [accuracy-gap-fix.md](./accuracy-gap-fix.md) W1~W3 구현 완료:
- **W1 (GAP-A/D)**: Entity Linking (`entity_matching.py` — difflib + type boost) + Abstention (`abstention.py` — classify_tool_results + attribution rule + post-hoc scan)
- **W2 (GAP-C/E)**: Coreference Rewriter (`rewriter.py` — Tier1 rule + Tier2 LLM) + 배제 토큰 (`말고/대신/빼고`)
- **W3 (GAP-B, 부분)**: `learned_aliases` 테이블 (alembic 004) + `CategoryResolver.record_learned_alias`

본 Plan 의 목표는 **Round 1 rubric 동일 기준으로 Round 2 재측정** → 정확성 74→85+ 달성 여부 검증.

### 관련 메모리

- `feedback_check_env_before_test.md` — USE_MOCK 상태 확인 후 eval (Real 모드 district_code 사용 필수)
- `feedback_marketscope_sse_format.md` — SSE 이벤트가 `data:` 안에 type 임베드, 표준 파서 금지
- `feedback_sse_hallucination_needs_db_gt.md` — tool_end 에 result 부재, accuracy 검증에 DB 직접 쿼리 병행
- `feedback_stale_container_vs_source.md` — 최신 W1~W3 코드 반영된 컨테이너 확인

## Scope

### In Scope

- S1~S8 8 시나리오 curl 스트리밍 + 결과 캡쳐
- Round 1 동일 rubric (Depth / Context / Derived / Structure / Actionable / Accuracy 6축, 각 2점, 합 12점 → 10점 환산)
- 측정 대상 KPI:
  - 종합 정확성 74 → **85+**
  - S3 비교 2.6 → **9.0+**
  - S6 시뮬레이션 6.1 → **9.0+**
  - S7 후속질문 8.9 → **9.3+**
  - GAP-A 2글자 매칭 ~60% → **95%+**
  - GAP-D 할루시 ~15% → **<3%**
- DB ground truth 교차검증 (5 sample 상권 × 주요 지표)

### Out of Scope

- W4 (Card-level PDF UX) — deferred
- Rewriter LLM Tier2 의 p95 지연 측정 (별도 성능 Plan)
- Round 3 (W2/W3 잔여분 완료 후 별도 세션)

### 가정

- Real 모드 (USE_MOCK=false), Mock 은 회귀 보장만
- dev 환경 `.env.dev` 사용, prod trace 오염 없음
- backend 컨테이너는 2026-04-23 W1~W3 반영 이미지

## Design

### 시나리오 정의 (Round 1 과 동일 세트)

| ID | 의도 | 입력 | 주 검증 GAP |
|----|------|------|:-----------:|
| S1 | 기본 요약 | `"강남역 상권 요약해줘"` | — (regression baseline) |
| S2 | 기본 요약 | `"서울역 상권 분석"` | — |
| S3 | 상권 비교 | `"홍대 vs 성수 매출 비교"` | A |
| S4 | 업종 추천 | `"건대 창업 추천 업종?"` | — |
| S5 | 리스크 분석 | `"명동 창업 리스크는?"` | — |
| S6 | 매출 시뮬레이션 | `"강남역에서 카페 차리면 매출 얼마?"` | — |
| S7 | 후속 질문 | S3 후 `"거기 중에 유동인구 더 많은 곳?"` | E |
| S8 | 엣지케이스 (배제) | `"홍대 말고 성수역이랑 건대 비교"` | C |

**district_code 매핑** (Real):
- 강남역 = `3120189`, 서울역 = `3110023`, 홍대입구역 = `3120050`, 성수역 = `3120052`, 건대입구 = `3120053`, 명동 = `3110010`

### Rubric (Round 1 복제)

| 축 | 0점 | 1점 | 2점 |
|---|-----|-----|-----|
| **Depth** | 표면적 답변 | 기본 지표 나열 | 해석+분석 포함 |
| **Context** | 컨텍스트 무시 | 일부 반영 | 전체 반영 |
| **Derived** | 원시수치만 | 파생지표 일부 | 비율/차이/트렌드 도출 |
| **Structure** | 평문 | 부분 구조화 | 섹션+리스트+강조 |
| **Actionable** | 관찰만 | 간접 제안 | 구체적 액션 권고 |
| **Accuracy** | 확인불가 주장 多 | 일부 attribution | 전 수치 attribution + DB 일치 |

합계 12점 → **10점 환산** (`score * 10 / 12`). 9.0+ PASS.

### Eval 스크립트 설계

**`scripts/eval/run_accuracy_round2.sh`** (신규 or 기존 참고):

```bash
#!/bin/bash
set -euo pipefail
BASE="${BASE:-http://localhost:8002}"
SESSION="eval-round2-$(date +%s)"
OUT="docs/qa/runs/analysis-quality-eval-2026-04-24-raw"
mkdir -p "$OUT"

scenario() {
  local id=$1 msg=$2 code=${3:-}
  local payload
  if [[ -n "$code" ]]; then
    payload=$(printf '{"message":"%s","session_id":"%s","district_code":"%s"}' "$msg" "$SESSION" "$code")
  else
    payload=$(printf '{"message":"%s","session_id":"%s"}' "$msg" "$SESSION")
  fi
  curl -sN -X POST "$BASE/api/chat" \
    -H "Content-Type: application/json" -H "Accept: text/event-stream" \
    -d "$payload" > "$OUT/$id.sse"
}

scenario S1 "강남역 상권 요약해줘" 3120189
scenario S2 "서울역 상권 분석" 3110023
scenario S3 "홍대 vs 성수 매출 비교"
scenario S4 "건대 창업 추천 업종?" 3120053
scenario S5 "명동 창업 리스크는?" 3110010
scenario S6 "강남역에서 카페 차리면 매출 얼마?" 3120189
# S7 은 S3 세션 이어서
SESSION_S7="$SESSION-s7" \
  && curl -sN -X POST "$BASE/api/chat" -H "Content-Type: application/json" \
       -d '{"message":"홍대 vs 성수 매출 비교","session_id":"'$SESSION_S7'"}' > "$OUT/S7-pre.sse" \
  && curl -sN -X POST "$BASE/api/chat" -H "Content-Type: application/json" \
       -d '{"message":"거기 중에 유동인구 더 많은 곳?","session_id":"'$SESSION_S7'"}' > "$OUT/S7.sse"
scenario S8 "홍대 말고 성수역이랑 건대 비교"
```

**후처리**: `python scripts/eval/extract_sse.py $OUT/*.sse` 로 text/card/tool_end 를 markdown 테이블화.

### Ground Truth 쿼리

5 sample district × 핵심 지표 직접 DB 추출 (accuracy 축 채점용):

```sql
-- S1/S2/S5/S6: 단일 상권 지표
SELECT d.district_code, d.district_name,
       (SELECT SUM(total_pop)/COUNT(DISTINCT time_slot)
          FROM floating_population
         WHERE district_code=d.district_code AND quarter='2025Q4') AS daily_avg_pop,
       (SELECT SUM(monthly_sales)/3
          FROM estimated_sales
         WHERE district_code=d.district_code AND quarter='2025Q4') AS monthly_sales_total
  FROM districts d
 WHERE d.district_code IN ('3120189','3110023','3120050','3120052','3120053','3110010');
```

```sql
-- S3/S8: 비교 대상 매출 순위
SELECT district_code, SUM(monthly_sales)/3 AS monthly_won
  FROM estimated_sales WHERE quarter='2025Q4'
  AND district_code IN ('3120050','3120052','3120053')
  GROUP BY district_code;
```

## Checklist

### Pass 1 (스택 기동 + S1~S8 수집)

- [ ] `docker compose config | grep USE_MOCK` → `false` 확인 (.env.dev 확인)
- [ ] `docker compose up -d` (`db`, `redis`, `backend`, `frontend`)
- [ ] `curl http://localhost:8002/health` 200
- [ ] `scripts/eval/run_accuracy_round2.sh` 실행 → 8 raw SSE 파일 생성
- [ ] `psql ... -f scripts/eval/ground_truth.sql > ground_truth.tsv` 추출

### Pass 2 (수동 채점)

- [ ] S1~S8 각 raw SSE 에서 text 조합 + card data 추출 → `analysis-quality-eval-2026-04-24.md` 에 시나리오별 블록 작성
- [ ] rubric 6축 × 0/1/1.5/2 점수 할당 (Round 1 portal 참조)
- [ ] Accuracy 축: DB ground truth 대비 LLM 수치 편차 ±10% 이내 = 2점
- [ ] 할루시 카운트: `(tool_name)` attribution 없는 숫자+단위 정규식 매칭

### Pass 3 (비교 리포트)

- [ ] Round 1 대비 변화 표 (시나리오별 점수 delta)
- [ ] KPI 테이블 업데이트 (종합 정확성 / S3/S6/S7 / GAP-A / GAP-D)
- [ ] `docs/status/current-status.md` 에 Round 2 결과 1 섹션 추가
- [ ] PASS/FAIL 판정 — 전체 평균 9.0+ 이면 정확성 축 85+ 로 reclassify

## 재검토 (Self-Review Gate)

- [ ] **엣지케이스**: S3/S8 은 district_code 미제공 → Planner 의 multi-district 추출 로직이 검증 대상. "홍대 vs 성수" 에 `ambiguous=True` 유지되는지
- [ ] **엣지케이스**: S7 의 session 재사용 — `messages` history 10 turn 이 유지되는지. rewriter anchor walk 가 S3 의 cards 를 참조하는지
- [ ] **엣지케이스**: S8 의 `excluded_tokens=["홍대"]` 가 실제로 compare_districts input 에서 제거되는지 (2026-04-23 smoke 재확인)
- [ ] **Memory 교훈**: `feedback_sse_hallucination_needs_db_gt.md` — tool_end payload 에 result 없음. card data + DB 직접 쿼리로 보강 필수
- [ ] **Memory 교훈**: `feedback_marketscope_sse_format.md` — `event:` 라인 없는 SSE. `grep '^data:' | jq` 로 파싱
- [ ] **타 Plan 충돌**: [phase1-low-mid-risk-2026-04-23.md](../infra/phase1-low-mid-risk-2026-04-23.md) Pass 1 의 singleflight 삭제 · 레거시 spec 삭제는 eval 스택과 무관 (백엔드 SSE 계약 불변)
- [ ] **타 Plan 충돌**: Refactoring Pass 2 의 respond.py 분할은 **eval 완료 후** 진행 (스트리밍 경로 회귀 위험). 본 Plan 은 Pass 2 전에 baseline 확보 필수

## Scenario (E2E Ring Mapping)

- **Ring**: 2 (user journey) — S1~S8 은 실제 사용자 대화 시나리오

| Ring | ID | 시나리오 | 기대 결과 |
|------|----|---------|----------|
| 2 | R2-EVAL-S1 | 기본 요약 강남역 | SummaryCard + 월매출 수치 매칭 |
| 2 | R2-EVAL-S2 | 기본 요약 서울역 | SummaryCard + 주말/평일 대비 |
| 2 | R2-EVAL-S3 | 비교 홍대 vs 성수 | CompareCard 2개 상권 + ambiguous 경고 유지 |
| 2 | R2-EVAL-S4 | 업종 추천 건대 | RecommendCard Top 5 전체 서술 |
| 2 | R2-EVAL-S5 | 리스크 명동 | RiskCard + 안정성 스코어 |
| 2 | R2-EVAL-S6 | 시뮬레이션 강남역 카페 | SimulationCard p25/avg/p75 |
| 2 | R2-EVAL-S7 | 후속질문 coreference | rewriter 활성, anchor district 참조 |
| 2 | R2-EVAL-S8 | 배제 토큰 | 홍대 언급 0건, compare 2개만 |

## Pass 반복

- **Pass 1 (기본)**: 8 시나리오 raw 수집 + ground truth 쿼리. Fail 시 stack 재기동 + USE_MOCK 재확인
- **Pass 2 (엣지)**: S3/S8 ambiguous/exclusion 동작 smoke + DB 교차검증
- **Pass 3 (성능)**: Rewriter LLM 호출 횟수 집계, attribution scan 위반 카운트, 평균 TTFT 기록
- Fail → 코드 수정은 본 Plan scope 밖. 결과만 기록하고 `accuracy-gap-fix.md` W3 잔여/W4 로 이관

## Agent 모델 선택

- **설계**: opus (본 Plan)
- **실행 (raw 수집)**: haiku (curl + bash 루프)
- **채점**: opus (LLM 텍스트 분석 + rubric 점수 할당)
- **리포트**: sonnet (markdown 작성)

근거: 채점에 도메인 판단 + 숫자 교차검증 필요 → opus. 실행은 deterministic script → haiku.

## Validation

### 수동 검증

1. 8 SSE 파일 모두 `done` 이벤트 도달 + 0 timeout
2. S3 응답에 `홍대입구역` + `성수역` 2개 명시
3. S8 응답에 `홍대` 언급 0회, `성수역` + `건대입구` 만 등장
4. S6 응답에 `p25`/`평균`/`p75` 3 구간 언급
5. Round 2 평균 ≥ 9.0 → 정확성 축 85 reclassify 근거

### 자동 검증

- `grep -c "(get_[a-z_]*)" $OUT/*.sse` — attribution tag 카운트 ≥ 5/시나리오
- `grep -E '\d+[만억원명%][^(]*$'` — unattributed 숫자 위반 0 기대
- 각 card_type 이 `data` 이벤트에 정확히 1회 등장 (Ring 2 smoke)

### 산출물

- `docs/qa/runs/analysis-quality-eval-2026-04-24-raw/S{1..8}.sse` (raw)
- `docs/qa/analysis-quality-eval-2026-04-24.md` (채점 + 비교표)
- `docs/status/current-status.md` 2026-04-24 섹션 (KPI update)
- 메모리 신규 (있다면): `feedback_accuracy_round2_*.md`

## Metadata

- 작성자: Claude Opus 4.7
- 작성일: 2026-04-24
- 선행 Plan: [accuracy-gap-fix.md](./accuracy-gap-fix.md) W1~W3 완료, [etl-sales-column-rename-2026-04-23.md](./etl-sales-column-rename-2026-04-23.md) 완료
- 후행 연계: Refactoring Phase 1 Pass 2 (respond.py 분할) — 본 eval 의 baseline SSE 를 회귀 비교 기준으로 재사용
