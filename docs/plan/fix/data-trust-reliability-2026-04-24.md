# 데이터 신뢰성 강화 — 2026-04-24

> "종로3가역 월매출 1,104억" 류의 정답이지만 불신 유발 응답을 근본 해소.
> Parent accuracy gap fix W1~W4 (entity_matching / abstention / rewriter / learned_aliases) 완료 후속.

## Context

### 근본 원인 분석 (2026-04-24 종로3가역 케이스)

UI 응답: **"월 추정 매출 1,104억 3천만원 (발달상권 중 상위 25%)"**.
사용자 불신 이유 = "수치가 상식 대비 과도하게 큼".

DB 실측 대조 (동일 세션 2026-04-24):

| 지표 | DB 값 | UI 값 | 판정 |
|---|---|---|---|
| `SUM(monthly_sales)` 2025Q4 | 331,319,763,982 원 (분기 누적) | — | — |
| Repository 환산 ( `/3` ) | 110,439,921,327 원 (월) | **110,439,921,327 원** (= 1,104억) | ✅ 정확 |
| `SUM(store_count)` | 4,123 | 4,125 | ✅ 근사 일치 (2 오차는 데이터 refresh 시점) |
| `CS300017` 점포 | 1,925 | 1,925 (46.7%) | ✅ |

**결론**: 수치 계산·환산은 전부 정확. `estimated_sales.monthly_sales` 컬럼은 열린데이터 `THSMON_SELNG_AMT` (분기 누적, 원) 를 그대로 저장하고 Repository `/_enrich_sales` 에서 `// 3` 환산. CLAUDE.md 도 이 함정을 경고 중.

### 진짜 문제 — 컨텍스트 부재

벤치마크 쿼리 결과 (2025Q4, 1,565 상권 집계):

| 상권 유형 | n | 월매출 평균 | p50 | p75 | p95 | max |
|---|---|---|---|---|---|---|
| 골목상권 | 1,030 | 13억 | 7억 | 18억 | 47억 | 177억 |
| 관광특구 | 6 | 857억 | 693억 | 1,172억 | 1,662억 | 1,793억 |
| 발달상권 | 249 | 200억 | 116억 | 210억 | 492억 | **4,205억** |
| 전통시장 | 280 | 46억 | 16억 | 48억 | 163억 | 672억 |

종로3가역 1,104억/월 = 발달상권 **p95(492억) 대비 2.24배, max(4,205억) 대비 26%**. "상위 25%" 보다는 "**상위 5% 수준**" 표기가 정확.
LLM 응답의 "상위 25%" 라벨은 Tool 이 제공하는 `get_district_benchmarks` quartile 결과에 의존하는데, **분위 기반 라벨이 p95 이상 구간을 모두 하나의 "상위 25%" 로 뭉뚱그리고 있음**.

### 구조적 3 원인 (재발 가능성 순)

1. **컬럼명과 의미 불일치** — `monthly_sales` 가 실제 **분기 누적** 을 저장. 향후 ETL 변경자가 컬럼명만 보고 추가 환산 누락/중복 위험. 2026-04-17 이미 `_enrich_sales` 키 불일치 fix 이력.
2. **분위 해석이 저해상도** — 3분위 (하위 25% / 중위 / 상위 25%) 라벨만 제공. p95 이상 초고액 상권(`max=4,205억` 급)을 상위 25% 라벨로 흡수 → LLM 이 "평범한 상위권" 으로 소통.
3. **출처 근거 post-hoc 만 존재, numeric 정합성 검증 부재** — 현재 `scan_unattributed_numbers` (`abstention.py`) 는 `(tool_name)` 누락만 탐지. **수치 크기 sanity / DB ground truth 교차 검증 부재**.

## Scope

### In
- Layer 1 — **Prompt**: Respond/Compare/Summary 시스템 프롬프트에 "p95 대비 배율 / 점포당 매출 우선 / 분기누적→월 환산 명시" 규칙 강제
- Layer 2 — **Benchmarks 자동 병렬**: intent ∈ {summary, recommendation, comparison, risk, simulation} 일 때 `get_district_benchmarks` 를 Planner DAG 에 항상 포함 (현재 선택적 호출)
- Layer 3 — **Numeric Sanity Evaluator**: 신규 `agent/utils/numeric_sanity.py` + `respond_node` post-hoc. 응답에서 수치 N개 추출 → tool_results 값과 fuzzy 매칭 + 벤치마크 범위 내인지 판정. 벗어나면 SSE `warning` 이벤트 발행 + `done.quality_flags` 동봉
- Layer 4 — **Trust Regression**: `scripts/eval/trust_scenarios.py` 5 상권 eval harness + DB ground truth 자동 대조
- Layer 5 — **문서/코드 guardrail**: `estimated_sales` 테이블 DDL 에 column comment `"SOURCE: THSMON_SELNG_AMT, UNIT: KRW, AGGREGATION: quarterly cumulative"` 추가 + Alembic migration. Repository 에 `QUARTER_TO_MONTH_DIVISOR = 3` 상수화 + assertion

### Out
- 컬럼 rename `monthly_sales → quarterly_sales_raw_krw` (breaking change, Phase 2 에서 pg view 로 soft-migrate 권장)
- pg_trgm / Learned aliases DB 쿼리 튜닝 (별도 Plan)
- Premium tier 게이팅

## Design

### Layer 1 — Prompt rules (최소 변경, 최대 효과)

`agent/prompts/system.py` 에 아래 규칙 블록 추가:

```
[SALES_NUMBER_PRESENTATION_RULES]
- 월 매출 총액을 언급할 때 반드시 3가지를 한 문단에 담아라:
  (1) 절대값 + 출처 `(tool_name)`
  (2) 해당 상권 유형(발달/골목/관광/전통) 내 분위 컨텍스트 — "p95(N억) 대비 M배" 형식 권장
  (3) **점포당 월 매출** — 실제 사업자 체감 수치
- 분기 누적 원시값을 실수로 "월 매출" 로 말하지 말 것. 출처는 항상 `estimated_sales.monthly_sales / 3` 환산된 값.
- "상위 25%" 같은 quartile 라벨보다 "p95 대비 M배" 가 더 정확하면 후자를 우선.
```

### Layer 2 — Planner preset

`agent/config/intents.yaml` 의 summary/recommendation/comparison/risk intent 프리셋에 `get_district_benchmarks` 를 **병렬 step** 으로 추가. 현재 `recommend_business` 만 벤치마크 참조.

### Layer 3 — Numeric Sanity Evaluator

```
agent/utils/numeric_sanity.py
├── extract_numbers(text) -> list[ExtractedNumber]
│     # "1,104억", "2,679만원", "590만 6천명" 류 한국어 수치 파싱
│     # 단위 정규화: 억/만/천 → 원 scalar
├── match_against_tools(numbers, tool_results) -> list[MatchResult]
│     # fuzzy ±5% 매칭, 매칭 실패 시 hallucination 후보
├── check_benchmark_range(numbers, benchmarks, district_type) -> list[RangeFlag]
│     # p99 초과 or p1 미만 → outlier flag
└── evaluate_response(text, tool_results, benchmarks) -> QualityReport
      # 최종 quality_flags: list[{severity, rule, evidence}]
```

`respond_node` 종료 직후 실행, 결과를 `event_queue` 에 `warning` 이벤트(새 타입) + `done.quality_flags` 로 발행. Frontend 는 optional (기존 SSE parser 는 미지 type 무시).

### Layer 4 — Trust Regression harness

```
scripts/eval/trust_scenarios.py
- 5 타겟 상권: 종로3가역(발달, 시계·귀금속 특화), 남대문시장(전통), 강남역(발달), 망원시장(골목), 명동(관광특구)
- 각 상권마다:
  1) curl SSE 수집 → 응답 텍스트 + card data 파싱
  2) DB ground truth 재조회 (monthly_sales, store_count, close_rate, floating_pop)
  3) 응답 수치 vs DB 대조: 모든 수치가 ±5% 이내면 PASS
  4) 벤치마크 컨텍스트 포함 여부 (p95 대비 표현) 체크
  5) 출처 tag 포함 여부
- 출력: docs/qa/runs/trust-eval-<date>/{summary.md, per-district.md, raw/}
```

### Layer 5 — DB guardrail

```sql
-- alembic/versions/005_estimated_sales_column_comment.py
COMMENT ON COLUMN estimated_sales.monthly_sales IS
  'SOURCE: Seoul OpenData THSMON_SELNG_AMT; UNIT: KRW; AGGREGATION: quarterly cumulative. Divide by 3 for monthly estimate. See _enrich_sales.';
```

```python
# repositories/real/estimated_sales.py
QUARTER_TO_MONTH_DIVISOR = 3  # docs/plan/fix/data-trust-reliability-2026-04-24.md

def _enrich_sales(row):
    raw_quarterly = row.monthly_sales  # column name is legacy; value is quarterly cumulative
    monthly = raw_quarterly // QUARTER_TO_MONTH_DIVISOR
    assert monthly >= 0, f"negative monthly sales: {row}"
    return {..., "monthly_sales": monthly}
```

## Checklist

### Phase A — Immediate (Pass 1, 1 session)
- [ ] Layer 1 프롬프트 규칙 추가 + 단일 시나리오 smoke
- [ ] Layer 4 scripts/eval/trust_scenarios.py 5 상권 수집 (read-only)
- [ ] Ground truth diff 리포트 작성
- [ ] Layer 5 alembic 005 column comment + `QUARTER_TO_MONTH_DIVISOR` 상수화

### Phase B — Core (Pass 2, 1~2 session)
- [ ] Layer 3 `numeric_sanity.py` 유닛 테스트 포함 구현
- [ ] `respond_node` 통합 + SSE `warning` 이벤트 추가
- [ ] `state.py` `quality_flags` 필드 추가
- [ ] `done.quality_flags` payload 추가

### Phase C — Broaden (Pass 3)
- [ ] Layer 2 intents.yaml 벤치마크 병렬 호출
- [ ] Trust regression 자동화 (pytest or ci 주기)
- [ ] `docs/architecture/agent.md` evaluator 확장 기록

## 재검토 (Self-Review Gate)

- Memory 교훈
  - `feedback_comparison_intent_halluc.md` — numeric sanity 에 comparison intent 특별 처리 (상권 간 비율 수치 검증 포함)
  - `feedback_respond_tool_use_xml_leak.md` — Respond XML leak 스캔과 같은 post-hoc 패턴 재사용 가능
  - `feedback_eval_district_code_hardcode.md` — trust_scenarios 는 district_code 하드코딩 금지, district_name → DB lookup
  - `feedback_sse_hallucination_needs_db_gt.md` — ground truth 반드시 DB 직접 쿼리로 확보
  - `feedback_comparison_intent_halluc.md` — 분기/월 환산 일관성 체크

- 타 Plan 충돌
  - `accuracy-gap-fix.md` W4 카드 단위 PDF 는 독립
  - `accuracy-gap-eval-round2-2026-04-24.md` Round 2 KPI 재측정은 본 plan layer 3 의 quality_flags rate 를 지표로 흡수 가능
  - `e2e-quality-improvement-2026-04-24.md` Pass 2 잔여 FAIL 9 건은 trust 와 overlap 적음 (rewriter 쪽)

- 엣지케이스
  - 매출 0 원 상권 (소상공인 미진입 지역) — divisor=3 assertion 에 0 허용
  - 카테고리 누락 상권 — sum 조건에 `COALESCE(SUM(monthly_sales), 0)` 적용
  - UI 수치 "5천만원" 같은 반올림 표기 → fuzzy 매칭 tolerance ±5% + 한국어 "천/만/억" 파서 bug 주의
  - Benchmark 최신성 — 분기 rollover 시 p95 가 한 분기 stale, Runbook 에 주기 재계산 명시

## Scenario (E2E Ring Mapping)

| Ring | ID | 케이스 | Layer |
|---|---|---|---|
| 2 | `2-TRUST-jongno3` | 종로3가역 요약 → 1,104억 숫자 + p95 컨텍스트 | L1, L4 |
| 2 | `2-TRUST-namdaemun` | 남대문시장 (전통 특화) | L1, L4 |
| 2 | `2-TRUST-gangnam-cmp` | 강남역 vs 홍대 비교 → 수치 비율 sanity | L1, L3 |
| 3 | `3-TRUST-outlier-warn` | 인위적 outlier (tool 결과 p99 초과) → warning 발행 | L3 |
| 3 | `3-TRUST-numeric-mismatch` | Tool 결과와 응답 수치 ±5% 이탈 → warning | L3 |

## Pass 반복

### Pass 0 (baseline 수집, 2026-04-24 완료) — 21/25

| 상권 | DB 월매출 | 검증 | 근본 원인 |
|---|---:|:---:|---|
| 종로3가역 (3120009) | 1,104억 | ✅ 5/5 PASS | 사용자 불신 원인은 **정답 수치의 스케일 불신** — Layer 1 프롬프트 규칙으로 해소 가능 |
| 강남역 (3120189) | 1,396억 | ✅ 5/5 PASS | — |
| 망원시장 (3130186) | 40억 | ✅ 5/5 PASS | — |
| 남대문시장(자유상가) (3130024) | 474억 | ❌ 3/5 FAIL | **Entity mismatch**: 사용자 "남대문시장" → Planner 가 `삼익패션타운(남대문시장)` (43억/586개) 선택. DB ground truth 달라짐 |
| 명동 남대문 북창동 다동 무교동 관광특구 (3001492) | 1,793억 | ❌ 3/5 FAIL | **Entity mismatch**: 긴 공식명을 `명동(명동거리)` (424억/1,713개) 로 부분 매칭 |

**핵심 인사이트**: Trust regression 2건 FAIL 은 **Pass 2 엣지가 아닌 W1 entity linking 의 잔여 갭**. 응답 본문만 보면 attribution tag/벤치마크 컨텍스트/점포당 매출 모두 충족해 "신뢰할 만하게 보이지만", 실제로는 **사용자가 묻지 않은 상권 데이터** 를 보여줌. Layer 3 numeric_sanity evaluator 가 DB ground truth 와 대조하면 바로 탐지 가능. → Plan 의 Phase B 우선순위 격상.

### Pass 1 (2026-04-24 실행) — 25/30 (↑ from 21/25)

| 상권 | Pass 0 | Pass 1 | delta | 핵심 변화 |
|---|:---:|:---:|:---:|---|
| 종로3가역 | 5/5 ✅ | 6/6 ✅ | +1 | L3 warning 부재 체크 추가 통과 |
| 강남역 | 5/5 ✅ | 5/6 ❌ | -0 | store_count 자연 변동 (LLM 응답이 카테고리별만 언급) |
| 망원시장 | 5/5 ✅ | 6/6 ✅ | +1 | — |
| 남대문시장(자유상가) | 3/5 ❌ | 4/6 ❌ | +1 | L3 도 못잡음 — 아래 참조 |
| 명동 관광특구 | 3/5 ❌ | 4/6 ❌ | +1 | L3 도 못잡음 — 아래 참조 |

**L3 numeric_sanity 가 entity mismatch 를 못 잡는 이유**: Planner 가 "남대문시장" → `삼익패션타운(남대문시장)` 으로 **잘못 resolve** 한 뒤, Tool 이 그 잘못된 code 로 데이터 fetch → Respond 는 그 데이터를 충실히 인용. 응답 수치 ↔ tool_results 가 **내부적으로 일치**하므로 `tool_mismatch_ratio_high` 플래그는 발동 안 함. 근본 해결은 **Planner ambiguity 감지 강화** (W1 entity_matching 개선, 별도 Plan 필요).

**L3 의 실효 효과**:
- Tool 결과와 동떨어진 수치 할루시 (현재 `scan_unattributed_numbers` 만으로 탐지 불가) 는 `tool_mismatch_ratio_high` 로 잡을 수 있음
- 벤치마크 p99 초과 outlier (`benchmark_outlier_high`) 도 차단
- 실제 서비스에서 `done.quality_flags` 를 Langfuse/로그에 기록하면 품질 추세 관측 가능

**한계**: Planner 수준 entity mismatch 는 L3 범위 밖. Plan 의 Pass 2 에서 W1 entity_matching 재점검 별도 착수 제안.

### Pass 2 (엣지)
- Phase B. numeric_sanity 오탐/미탐 조정, fuzzy tolerance 튜닝
- Outlier 시나리오 (3-TRUST-outlier-warn) 통과 기준 확정

### Pass 3 (성능)
- Phase C. Planner DAG 에 benchmark 병렬 추가로 TTFT 증가 영향 측정. 목표 delta ≤ +200ms. 초과 시 intent-gated on/off.

## Agent 모델 선택
- 설계: opus (현재)
- 구현 (Layer 3 numeric_sanity): sonnet + subagent `code-reviewer` 로 정합성 리뷰
- 검증 (Trust regression 수집/비교): haiku (반복 curl + SQL diff) 충분

## Validation

### Pass 1 수용 기준
- Trust regression 5 상권 모든 대표 수치(월매출 / 점포 / 폐업률) DB 대비 ±1% 일치
- 적어도 1 상권에서 응답 본문에 "p95 대비" / "점포당" 컨텍스트 중 1종 이상 포함

### Pass 2 수용 기준
- 인위적 outlier 응답에 `quality_flags` 발행 100%
- 정상 응답에 false-positive warning < 5%
- numeric_sanity unit test 커버리지 80%+

### 장기 KPI
- 사용자 "수치 이상" 피드백 rate (F12 feedback) 측정치 50% 감소
- Accuracy Eval Round 3 평균 +0.5 상승

## Metadata

- Created: 2026-04-24
- Owner: cyon1
- Parent: `docs/plan/fix/accuracy-gap-fix.md`
- Trigger: 2026-04-24 종로3가역 UI 응답 불신 피드백
- Status: Phase A + Phase B Pass 1 완료 (L1/L3/L5 구현, L2 defer, L4 자동화 완료)
- Next: W1 entity_matching 재점검 (남대문시장/명동 케이스) — 별도 Plan
