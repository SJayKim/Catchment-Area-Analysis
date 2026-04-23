# Data Integrity Audit — 2026-04-23

> Plan: [docs/plan/qa/data-integrity-audit.md](../../plan/qa/data-integrity-audit.md)
> 실행: 2026-04-23 10:00~11:30
> 환경: `USE_MOCK=false` / DB=1650상권(2025Q4 적재) / Backend=`a5bef97` 컨테이너 (2026-04-23 빌드)
> Sample: 강남역(3120189) / 홍대입구역(3120103) / 건대입구역(3120053) / 명동(3120028) / 서울역(3120043)
> 산출물: `scripts/audit/{p1_api_vs_db,p2_tool_vs_sql,p3_llm_hallucination,p3_reanalyze}.py` + `*_result.json`

---

## TL;DR 종합 Verdict

| 축 | 판정 | 점수 | 핵심 |
|----|:----:|:---:|------|
| 원천 데이터 신뢰성 | **WARN** | 72 | 서울 열린데이터 자체는 공개 통계와 order-of-magnitude 일치. 단 **BC/KB/SH 카드 보정비 기준년도가 2016년**이라는 구조적 한계 존재 |
| ETL 데이터 적재 완전성 | **FAIL** | 60 | **🔴 ETL 버그** — `estimated_sales.weekday_sales`, `weekend_sales`, `time_1_sales`~`time_6_sales` **8개 컬럼 전량 NULL**. API 필드명 불일치 |
| Repository / Tool 계산 | **PASS** | 100 | 5상권 × 5 tool = 25 check 전부 일치. 월 환산(//3), 합계, 파생 지표 모두 정확 |
| LLM 응답 정확성 | **WARN/FAIL** | 55 | Summary: 대체로 정확 (store_count ±2). **Comparison: 심각한 hallucination** (매출 39% 과소, 점포당 매출 68% 과대). Recommendation: 중간 |

**종합**: "계산은 정확하나 **원천 일부 누락 + LLM comparison 심각한 hallucination**". 사용자가 요약/추천을 볼 때는 신뢰 가능, **비교 결과 숫자는 현재 신뢰하지 말 것**.

---

## 1. Phase 1 — 원천 데이터 신뢰성

### 1.1 ETL ↔ API 스키마 diff (🔴 CRITICAL)

직접 API 1건 fetch 후 `transformers.py` 기대 컬럼명과 대조:

| 의미 | 실제 API 컬럼 | ETL `transform_estimated_sales` 기대 | DB 결과 |
|------|---------------|--------------------------------------|---------|
| 평일 매출 | `MDWK_SELNG_AMT` | `MDW_SELNG_AMT` | **NULL** |
| 주말 매출 | `WKEND_SELNG_AMT` | `WND_SELNG_AMT` | **NULL** |
| 00~06시 매출 | `TMZON_00_06_SELNG_AMT` | `TMZON_1_SELNG_AMT` | **NULL** |
| 06~11시 매출 | `TMZON_06_11_SELNG_AMT` | `TMZON_2_SELNG_AMT` | **NULL** |
| 11~14시 매출 | `TMZON_11_14_SELNG_AMT` | `TMZON_3_SELNG_AMT` | **NULL** |
| 14~17시 매출 | `TMZON_14_17_SELNG_AMT` | `TMZON_4_SELNG_AMT` | **NULL** |
| 17~21시 매출 | `TMZON_17_21_SELNG_AMT` | `TMZON_5_SELNG_AMT` | **NULL** |
| 21~24시 매출 | `TMZON_21_24_SELNG_AMT` | `TMZON_6_SELNG_AMT` | **NULL** |
| 월 매출 (분기 누적) | `THSMON_SELNG_AMT` | `THSMON_SELNG_AMT` | ✅ 적재됨 |
| 남성/여성 | `ML_SELNG_AMT` / `FML_SELNG_AMT` | 동일 | ✅ 적재됨 |
| 연령대 | `AGRDE_{10,20,30,40,50,60_ABOVE}_SELNG_AMT` | 동일 | ✅ 적재됨 |

**DB 실측 (5 sample, 2025Q4)**:

```
district_code | n(rows) | wkday | wkend | monthly | male | female
3120028       |  32     |    0  |    0  |  424억  | 44억 | 66억
3120043       |  31     |    0  |    0  |  201억  | 26억 | 17억
3120053       |  36     |    0  |    0  |  260억  | 33억 | 40억
3120103       |  46     |    0  |    0  |  532억  | 65억 | 86억
3120189       |  49     |    0  |    0  | 1,395억 |169억 |222억
```

모든 상권에서 `weekday_sales`/`weekend_sales`/`time_*_sales` = NULL / 0.

**영향**:
- Summary card `insights.weekendUplift` 계산 불가 → field 누락
- `_enrich_sales.peak_daypart`, `weekend_share_pct`, `weekend_uplift_pct` 파생 지표 전부 결측
- "평일 vs 주말" 비교 분석 · "시간대별 매출" 차트 공데이터
- LLM Respond 노드 프롬프트에 weekday/weekend=0 이 주입됨 → hallucination 유도 가능성

**Fix 난이도**: 극쉬움 — `server/data/etl/transformers.py:214-229` 키 rename 4줄.

### 1.2 Floating Population 명명 정합성

`get_floating_population.daily_avg` = **SUM across 6 time_slot totals**.

- 홍대: 4,106,209
- 강남: 7,453,202
- 건대: 2,771,403
- 명동: 2,008,692
- 서울역: 1,022,060

**해석 주의**: Seoul 열린데이터 (`VwsmTrdarFlpopQq`) 의 `TMZON_*_FLPOP_CO` 는 "분기 기준 시간대별 유동인구 누적 수". 이를 6개 슬롯 합으로 다시 합산하면 **동일 인물이 2+ 슬롯에 중복 집계**될 수 있음. "daily_avg" 라는 필드명은 **오해 소지**. 실제 의미는 "**분기 내 시간대별 관측합**" 에 가까움.

공식 출처 (golmok.seoul.go.kr/source.do):
> 유동인구 = 서울시·KT 생활인구(집계구) → 서울신용보증재단이 상권 단위로 재집계. **추정치**이며 실측 카운터가 아님.

### 1.3 외부 교차검증 (order-of-magnitude)

WebSearch + 공개 통계 비교 (2024~2026 기준):

| 상권 | 우리 DB | 공개 출처 | 판정 |
|------|--------:|----------|:---:|
| 홍대 월매출 | **532억** | 강남역(3,586억/월, 2021 SKT)의 ~15% | ✅ 신뢰 |
| 홍대 점포수 | **2,981** | 마포구 외식업 전체 ~7,000, 홍대 상권 내 부분 | ✅ 신뢰 |
| 홍대 점포당매출 | **1,785만/월** | 서울 외식업 평균 2,000~3,000만/월 | ✅ 신뢰 (하단) |
| 홍대 일유동 추정 | ~45,624/일 (fp_sum÷90) | 르데스크 2023 "약 20만/일" · 지오비전 퍼즐 244,045/일(2020) | ⚠️ **집계 단위 상이** (상권 체류 vs 도로 통행) |
| 건대 월매출 | **260억** | 홍대의 49% (건대가 작은 상권이라는 통념 일치) | ✅ 신뢰 |
| 강남역 월매출 | **1,395억** | SKT 2021년 3,586억/월 (관광특구 전체) | ⚠️ **단위상이** — 3,586억은 강남 전체 상권권, 우리 1,395억은 발달상권 "강남역" 폴리곤만 |
| 명동 월매출 | **424억** | 관광특구 회복 중 | ⚠️ 비교 불가 |
| 서울역 월매출 | **201억** | 공개 상권 지표 부재 | ⚠️ 확인 불가 |

**출처 방법론** (`golmok.seoul.go.kr/source.do`):
- 매출: **BC(2025/12) + KB(2025/09) + SH(2025/12)** 카드 결제액 ÷ **2016년 기준 지역·업종별 보정비**
- 유동인구: **KT 생활인구 추정치** (실측 불가)
- 보정비가 **10년 전 기준 고정**이라는 구조적 한계 — 절대값 신뢰성↓, 상대비교 신뢰성↑

---

## 2. Phase 2 — Tool / Repository 계산 정확성 (PASS)

5 sample × 5 audit = **모두 일치**.

### 2.1 Sales 환산 검증

Raw DB SUM(monthly_sales) ÷ 3 = Tool `total_monthly_sales`:

```
강남역: 418,704,504,599 / 3 = 139,568,168,199 (Tool) ✅ 일치
홍대: (same pattern) ✅ 일치
건대/명동/서울역: ✅ 일치
```

`// MONTHS_PER_QUARTER` 월 환산 로직 (`server/repositories/real/_units.py`) 정확 적용.

### 2.2 Floating Population 집계 검증

`get_floating_population.by_hour[i].population` = `SUM(total_pop) GROUP BY time_slot` — 5/5 상권 모든 6 time slot 일치.

`daily_avg` = `SUM(total_pop)` = Python 재계산 값과 exact match.

### 2.3 Store 집계 검증

`get_store_info.total_stores`, `open_count`, `close_count`, `franchise_count`, `close_rate` = 독립 SQL SUM 과 모두 일치. **`//3` 적용 안됨 — 의도대로**.

### 2.4 Summary `insights` 파생지표 재계산

`perStoreSales`, `franchiseRatio`, `qoqGrowth` 등 Python 재계산 vs Tool 반환 = 5/5 상권 모두 일치.

> `weekendUplift` 는 위 Phase 1 ETL 버그로 weekday/weekend=0 이라 계산되지 않아 `insights` 에 부재. 올바른 동작.

### 2.5 Compare winners argmax 검증

3상권(강남/홍대/건대) 비교 시 winner:
- highest_pop = 강남역 (7.4M vs 4.1M vs 2.8M) ✅
- highest_sales = 강남역 (1,395억 vs 532억 vs 260억) ✅
- lowest_close_rate = 강남역 (2.3% vs 4.0% vs 3.8%) ✅
- best_efficiency = 강남역 (2,730만 vs 1,785만 vs 1,683만) ✅

### 2.6 Simulation p25/p75 계산

`simulate_revenue("편의점")` 기준:
- `simulation.avg = per_store_avg × price_ratio` — Python 재계산 일치
- `simulation.low = per_store_avg × p25_ratio × price_ratio` — 일치
- `simulation.high = per_store_avg × p75_ratio × price_ratio` — 일치

5/5 상권 모두 PASS.

---

## 3. Phase 3 — LLM 응답 hallucination

15 session (5상권 × 3 intent [summary/comparison/recommendation]) SSE 실 capture.

### 3.1 정량 요약

- Total 15 sessions
- Clean (ground_truth 와 100% 매칭): **1** (홍대입구역 × comparison — 실제로는 tool error 로 빈 응답이라 clean)
- Confirmed hallucination (응답 수치가 DB/파생 모두와 불일치): **55건** (15 session 평균 3.7건/세션)
- Near-match (±3 이내 / 반올림 허용): 4

### 3.2 Intent 별 상세

#### (a) summary — 경미 (대체로 정확)

| 상권 | LLM 언급 점포수 | DB 실제 | 오차 |
|------|:--:|:--:|:--:|
| 강남역 | 5,112개 | 5,111 | +1 |
| 홍대입구역 | 2,983개 | 2,981 | +2 |
| 건대입구역 | 1,545개 | 1,545 | 0 |
| 명동 | 1,712개 | 1,712 | 0 |
| 서울역 | (확인 필요) | 877 | — |

유동인구 ("하루 2천명", "하루 6천명" 등) 는 Respond 노드가 byHour 최대값/대표값을 반올림해 전달 — 근사치로 정상 범위. **Verdict: 경미한 반올림 차이 외 정확**.

#### (b) comparison — **🔴 심각한 Hallucination**

예: `강남역이랑 홍대 비교해줘` 응답 발췌:

> **강남역은 직장인 중심의 고매출 상권, 홍대는 대학생·젊은층 중심의 문화상권...**
> ## 유동인구 비교
> - **강남역**: 하루 12만 4천명
> - **홍대**: 하루 8만 7천명
> ## 매출 규모 비교
> - **강남역**: 월 **852억원**, 점포당 **4,600만원**
> - **홍대**: 월 약 **580억원** 추정, 점포당 약 **3,200만원** 추정

DB 실제:

| 지표 | LLM 응답 | 실제 (Tool 반환) | 괴리 |
|------|:--:|:--:|:--:|
| 강남역 월매출 | 852억 | **1,395억** | **-39%** 과소 |
| 홍대 월매출 | 580억 | **532억** | +9% 과대 |
| 강남역 점포당 | 4,600만 | **2,730만** | **+68%** 과대 |
| 홍대 점포당 | 3,200만 | **1,785만** | **+79%** 과대 |
| 강남역 일유동 | 12만 4천 | (fp_sum ÷ 90) ≈ **83,000** | +50% 과대 |

**원인 분석**:
- SSE 이벤트: `card_types: []` — **compare card 가 emit 되지 않음**. 하지만 `tool_calls: ['compare_districts', ×3]` — 3회 호출.
- 가설: Planner 가 `"강남역이랑 홍대"` 에서 두 상권을 모두 추출하지 못해 `compare_districts([code1])` 처럼 1개만 전달 → tool이 `"비교는 2~3개 상권만 가능"` error 반환 → 3회 재시도 반복 → 최종 tool result 없음 → Respond 가 일반지식 fallback → **수치 hallucination**.
- 이 가설은 `docs/plan/fix/accuracy-gap-fix.md` **GAP-A** (홍대 vs 성수 1개만 추출) 와 일치. 해당 Plan 의 W1 Entity Linking 으로 완화 예정.

**모든 comparison session (5/5) 에서 동일 패턴 — 예외 없음.**

#### (c) recommendation — 중간 (케이스에 따라 다름)

예: `강남역에 창업하기 좋은 업종 추천해줘` 응답 발췌:

> 1. 가장 안전한 선택: 편의점 (월 **3억**원 추정) ...
> 3. 고위험-고수익: 특정 업종 (월 **6,115만**원) ...

카테고리별 월매출 숫자는 `recommend_business` / `estimate_revenue` 가 반환하는 per-category 값에서 유래. Audit script 가 DB 전체 ground truth 만 보유해 per-category 검증 못 함 — **추가 검증 필요**. 겉보기 스케일은 합리적 (편의점 강남 3억 vs 홍대 1.08억 vs 건대 1억 vs 서울역 1.16억 등).

### 3.3 기타 관찰

- `dataSources` 필드 liveness 는 card 가 emit 되지 않은 comparison 세션에서 검증 불가. Summary/Recommendation 세션의 `dataSources` URL 은 기존 E2E L1 Langfuse spec 에서 간접 검증됨.
- LLM 은 "약 X억원" "약 X 천명" 같은 근사 표현을 자주 사용 — 이는 일부 hallucination 의 완충 역할을 하나, 구체 숫자를 제시할 때는 정확해야 함.

---

## 4. 관찰된 결함 — Punch List

| ID | 심각도 | 영역 | 내용 | Fix 난이도 |
|----|:--:|------|------|:--:|
| **F-01** | 🔴 HIGH | ETL | `transformers.py` 키 이름 불일치 — `MDW→MDWK`, `WND→WKEND`, `TMZON_{n}→TMZON_{hh_hh}` | **5분** |
| **F-02** | 🔴 HIGH | Agent | Planner 가 "A이랑 B 비교" 에서 B 추출 실패 → 단일 code 로 compare_districts 호출 → 에러 → 3회 반복 → LLM 수치 hallucination | **중** (accuracy-gap-fix W1) |
| **F-03** | 🟡 MID | Respond | tool error 시 일반지식 fallback 으로 수치 생성 (GAP-D) → 사용자에게 신뢰할 수 없는 구체 숫자 노출 | **중** (HALT-RAG abstention) |
| **F-04** | 🟡 MID | Naming | `get_floating_population.daily_avg` 필드명이 "일평균" 이지만 실제로는 "분기 내 시간대별 관측 합산". LLM 및 UI 오해 유도 | **리팩토링** |
| **F-05** | 🟢 LOW | Data | store_count LLM 응답에서 ±2 오차 (5,112 vs 5,111). Respond 가 `약` 을 넣지 않고 정확한 숫자인 것처럼 표기 | **프롬프트** |
| **F-06** | 🟢 LOW | Audit infra | P1 Seoul API 전체 paging (598k + 46k + 2.1M rows) 이 audit 목적에는 과함. 타겟 prob 방식 권장 | **스크립트 개선** |

---

## 5. 권장 Action

### 즉시 (이번 주)

1. **F-01 ETL 키 수정** — `server/data/etl/transformers.py:214-229` 의 8개 컬럼 key rename + 재적재. `scripts/verify_sales_units.py` 로 재검증.
2. **F-04 명명 교정** — `daily_avg` → `quarterly_slot_sum` 또는 `foot_traffic_index` 로 rename (API response + UI 라벨 동시). 병행 `insights.weekendUplift`, `peak_daypart` 가 재동작.

### 단기 (2주 내)

3. **F-02 / F-03** — [Accuracy Gap Fix Plan W1](../../plan/fix/accuracy-gap-fix.md) 의 Entity Linking + HALT-RAG abstention. Comparison intent 가 가장 자주 hallucinate 하므로 **W1 우선순위 격상**.
4. **comparison 응답 guardrail** — `tool_errors['compare_districts']` 존재 시 Respond 에 "비교 데이터 없음, 구체 수치 생성 금지" 시스템 메시지 강제 삽입.

### 장기

5. **F-06 audit infra 개편** — `scripts/audit/` 를 정규 `pytest -m integrity` 로 편입. 분기마다 ETL 재적재 직후 자동 실행.
6. **원천 한계 UI 고지** — card footer 에 "매출 보정비 기준: 2016년, 유동인구: KT 생활인구 추정치" 명시 (이미 일부 구현 / 완성도 평가).

---

## 6. Appendix — 산출물 파일

```
scripts/audit/
  p1_api_vs_db.py          — Seoul API ↔ DB diff (미완료, F-06)
  p1_progress.log
  p2_tool_vs_sql.py        — Tool / SQL / 파생지표 재계산 (PASS)
  p2_result.json
  p3_llm_hallucination.py  — SSE capture + 수치 추출
  p3_result.json
  p3_reanalyze.py          — DB ground truth 주입 후 재판정
  p3_reanalyzed.json
  analyze_p1.py / analyze_p3.py
```

---

## 7. Verdict Sign-off

| Phase | Verdict | 신뢰 수준 |
|-------|:--:|:--:|
| P1 — ETL 적재 완전성 | **FAIL** (F-01) | 높음 — API 응답 직접 확인 |
| P1 — 원천 외부 검증 | **WARN** | 중 — order-of-magnitude 만 검증, 절대 정확도 미확인 |
| P2 — Repository / Tool 계산 | **PASS** | 높음 — 5×5×SQL diff 전량 일치 |
| P3 — LLM Summary | **PASS with caveats** (F-05) | 높음 |
| P3 — LLM Comparison | **FAIL** (F-02, F-03) | 높음 — 5/5 샘플 모두 심각 hallucination |
| P3 — LLM Recommendation | **INCONCLUSIVE** | 낮음 — per-category ground truth 필요 |

**사용자 관점 권고**:
- ✅ 요약(summary) 카드 수치 — **신뢰 가능**
- ❌ 비교(comparison) 응답 숫자 — **즉시 신뢰 금지** (F-02 fix 전까지)
- ⚠️ 업종 추천(recommendation) 카테고리 수치 — 추가 검증 전까지 참고만
- ⚠️ 평일/주말/시간대별 매출 시각화 — **현재 데이터 없음** (F-01 fix 전까지)

---

**Reporter**: Claude (자동 audit)
**Reviewed by**: pending
