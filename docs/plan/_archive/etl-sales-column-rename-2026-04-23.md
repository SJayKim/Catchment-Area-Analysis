# ETL Sales Column Rename (F-01 Fix) — 2026-04-23

> Plan 유형: fix
> 작성일: 2026-04-23
> 선행 Audit: [docs/qa/runs/data-integrity-audit-2026-04-23.md](../../qa/runs/data-integrity-audit-2026-04-23.md) §1.1
> 상태: ✅ 완료 (2026-07-04 문서 정합성 감사에서 구현 완료 확인 — `transformers.py::transform_estimated_sales` 가 MDWK/WKEND/TMZON_HH_HH 키 사용 중, 재적재·NULL 해소는 status 2026-04-23 "F-01 ETL fix" 기록)

---

## 1. Context

2026-04-23 Data Integrity Audit 에서 발견한 **F-01 (HIGH)** 단일 결함을 해소. 서울 열린데이터 `VwsmTrdarSelngQq` 엔드포인트의 실제 응답 컬럼명이 과거 `transform_estimated_sales` 에서 가정한 이름과 달라 `estimated_sales.weekday_sales / weekend_sales / time_1~6_sales` **8개 컬럼이 2025Q4 전량 NULL** 로 적재됨.

### 1.1 실제 API vs 기대 컬럼

| 의미 | 실제 API | ETL 기대 (현행) | DB |
|------|---------|----------------|----|
| 평일 매출 | `MDWK_SELNG_AMT` | `MDW_SELNG_AMT` | NULL |
| 주말 매출 | `WKEND_SELNG_AMT` | `WND_SELNG_AMT` | NULL |
| 00~06시 | `TMZON_00_06_SELNG_AMT` | `TMZON_1_SELNG_AMT` | NULL |
| 06~11시 | `TMZON_06_11_SELNG_AMT` | `TMZON_2_SELNG_AMT` | NULL |
| 11~14시 | `TMZON_11_14_SELNG_AMT` | `TMZON_3_SELNG_AMT` | NULL |
| 14~17시 | `TMZON_14_17_SELNG_AMT` | `TMZON_4_SELNG_AMT` | NULL |
| 17~21시 | `TMZON_17_21_SELNG_AMT` | `TMZON_5_SELNG_AMT` | NULL |
| 21~24시 | `TMZON_21_24_SELNG_AMT` | `TMZON_6_SELNG_AMT` | NULL |

> `transformers.py:197-202` 의 docstring 은 `MDW_SELNG_AMT` 를 "평일" 로 주석 처리. API 측이 `MDWK/WKEND` 로 변경되었으나 ETL 미반영.

### 1.2 영향 범위

- Summary Card `insights.weekendUplift` 계산 불가 → field 누락.
- `_enrich_sales.peak_daypart`, `weekend_share_pct`, `weekend_uplift_pct` 파생 지표 전부 결측.
- "평일 vs 주말" / "시간대별 매출" 차트 공데이터.
- LLM Respond 노드 프롬프트에 weekday/weekend = 0 주입 → hallucination 유도 가능성.

### 1.3 Memory 교훈

- `feedback_etl_api_column_rename.md` — Seoul OpenData API 컬럼명 변경은 과거에도 재발. ETL 수정 전 API 1행 dump 후 key 직접 확인 (본 Audit 에서 검증 완료).
- `feedback_stale_container_vs_source.md` — backend 컨테이너 재빌드 강제.

---

## 2. Scope

### 2.1 In Scope

- `server/server/data/etl/transformers.py:214-229` 8개 key rename
- 2025Q4 `estimated_sales` 테이블 재적재 (21,333 rows)
- 5개 sample 상권 대상 컬럼 NOT NULL 검증
- Redis 캐시 flush (sales 파생 지표 pre-cache 무효화)

### 2.2 Out of Scope

- 과거 분기 (2025Q3 이전) 재적재 — 현재 서비스가 2025Q4 만 노출
- `_enrich_sales` 파생 지표 계산 로직 검증 (이미 PASS, Audit §2.1)
- Tool / Repository 계약 변경 — 컬럼명 불변, 저장된 값만 바뀜

### 2.3 가정

- API 가 현재 `MDWK/WKEND/TMZON_*_NN` 컬럼을 응답. 2026-04-23 audit script 에서 실제 응답 확인 완료.
- SeoulOpenDataCollector 는 미변경 — 응답 JSON 키를 그대로 전달.
- DataLoader.upsert_estimated_sales 가 ON CONFLICT DO UPDATE 구조라 기존 row overwrite.

---

## 3. Design

### 3.1 변경 지점 (단일 파일)

`server/server/data/etl/transformers.py:214-229`

```python
# BEFORE
"weekday_sales": _safe_bigint(raw.get("MDW_SELNG_AMT")),
"weekend_sales": _safe_bigint(raw.get("WND_SELNG_AMT")),
...
"time_1_sales": _safe_bigint(raw.get("TMZON_1_SELNG_AMT")),
...
"time_6_sales": _safe_bigint(raw.get("TMZON_6_SELNG_AMT")),

# AFTER
"weekday_sales": _safe_bigint(raw.get("MDWK_SELNG_AMT")),
"weekend_sales": _safe_bigint(raw.get("WKEND_SELNG_AMT")),
...
"time_1_sales": _safe_bigint(raw.get("TMZON_00_06_SELNG_AMT")),
"time_2_sales": _safe_bigint(raw.get("TMZON_06_11_SELNG_AMT")),
"time_3_sales": _safe_bigint(raw.get("TMZON_11_14_SELNG_AMT")),
"time_4_sales": _safe_bigint(raw.get("TMZON_14_17_SELNG_AMT")),
"time_5_sales": _safe_bigint(raw.get("TMZON_17_21_SELNG_AMT")),
"time_6_sales": _safe_bigint(raw.get("TMZON_21_24_SELNG_AMT")),
```

Docstring 도 함께 갱신: "평일/주말/시간대 키는 서울 열린데이터 `VwsmTrdarSelngQq` (2025-10 개편) 기준 `MDWK/WKEND/TMZON_HH_HH` 를 사용".

### 3.2 재적재 플로우

```
1. 소스 수정 (transformers.py)
2. backend 이미지 재빌드 (docker compose build backend)
3. backend 컨테이너 재기동 (docker compose up -d backend)
4. ETL 재실행: python -m server.data.etl.runner run 2025Q4 --table estimated_sales
5. Redis flush: sales:* / report:* 키 무효화
6. DB 검증: 5 sample × 8 컬럼 NOT NULL / > 0 확인
7. Smoke: /api/chat "강남 평일 주말 매출 비교"
```

---

## 4. Checklist

### 4.1 구현

- [x] Plan 문서 작성 (본 문서)
- [x] `transformers.py:214-229` 8 key rename + docstring 갱신
- [x] backend 이미지 재빌드
- [x] backend 컨테이너 재기동
- [x] `estimated_sales` 재적재 (quarter=2025Q4, --table estimated_sales)
- [x] Redis flush (`sales:*`, `report:*`, `heatmap:*`)
- [x] DB 검증 쿼리 — 5 sample × weekday/weekend/time_{1..6} 8 컬럼
- [x] audit p1 재실행 (2025Q4 sales row 5 체크)

> ✅ 2026-07-04 문서 정합성 감사에서 구현 완료 확인: 코드는 `transformers.py::transform_estimated_sales` 에 `MDWK_SELNG_AMT`/`WKEND_SELNG_AMT`/`TMZON_00_06~21_24_SELNG_AMT` 전부 반영(docstring 개편 이력 포함), 재적재·8컬럼 NULL 해소는 status 2026-04-23 "F-01 ETL fix (21,333 행 재적재, 8 컬럼 NULL 해소)" 기록으로 완료.

### 4.2 재검토 (Self-Review Gate)

- [ ] **엣지**: API 응답이 `null` 인 row 가 있는지 → `_safe_bigint` 가 이미 None 처리
- [ ] **엣지**: `ON CONFLICT DO UPDATE` 경로에서 기존 컬럼 값 보존하는 트리거 없는지 확인 (loader 리뷰)
- [ ] **엣지**: docstring 에 2025-10 개편 날짜 남겨 재발 감지 용이하게
- [ ] **메모리**: `feedback_etl_api_column_rename.md` 업데이트 (본 fix 참조 추가)
- [ ] **타 Plan 충돌**: `accuracy-gap-fix.md` W1 은 GAP-A/D 영역, 본 fix 와 비충돌

### 4.3 Scenario (E2E Ring Mapping)

| Ring | ID | 시나리오 | 기대 |
|------|----|---------|------|
| 3 | 3-REG-ETL-SALES-COL | audit p1 재실행 | 5 상권 × 8 컬럼 NOT NULL |
| 1 | 1-F03-H7 | "홍대 평일/주말 매출 차이?" | weekend_share_pct 숫자 응답 |
| 1 | 1-F03-H8 | "강남 심야 매출 비중?" | time_6_sales 기반 비율 |

### 4.4 Pass 반복

- **Pass 1**: 재적재 후 DB 직접 쿼리 검증
- **Pass 2**: Summary Card `insights.weekendUplift` 렌더링 확인
- **Pass 3**: LLM Respond attribution 확인 (숫자 → tool 매핑)

### 4.5 Agent 모델 선택

- 구현: sonnet (단순 rename)
- 검증: haiku (SQL count 쿼리)

---

## 5. Validation

### 5.1 DB 검증 쿼리

```sql
SELECT
  district_code,
  COUNT(*) AS rows,
  COUNT(weekday_sales) AS wkday_nn,
  COUNT(weekend_sales) AS wkend_nn,
  COUNT(time_1_sales) AS t1_nn,
  COUNT(time_6_sales) AS t6_nn,
  SUM(weekday_sales)  AS wkday_sum,
  SUM(weekend_sales)  AS wkend_sum
FROM estimated_sales
WHERE quarter = '2025Q4'
  AND district_code IN ('3120028','3120043','3120053','3120103','3120189')
GROUP BY district_code
ORDER BY district_code;
```

기대: 각 상권에 대해 `wkday_nn == wkend_nn == t1_nn == t6_nn == rows` 이고 `sum > 0`.

### 5.2 정량 KPI

| 지표 | 현재 | 목표 |
|------|-----:|-----:|
| `weekday_sales` NOT NULL ratio (2025Q4) | 0% | 95%+ |
| `weekend_sales` NOT NULL ratio | 0% | 95%+ |
| `time_N_sales` (N=1..6) NOT NULL ratio | 0% | 95%+ |
| `insights.weekendUplift` 발행 비율 (summary card) | 0% | 95%+ |

---

## Metadata

| 항목 | 값 |
|------|-----|
| 작성자 | Claude (Opus 4.7) + 사용자 합의 |
| 작성일 | 2026-04-23 |
| 선행 Audit | `docs/qa/runs/data-integrity-audit-2026-04-23.md` |
| 영향 커밋 | `4f4bf2d audit(qa): data integrity audit 2026-04-23` |
| 후행 Plan | `docs/plan/fix/accuracy-gap-fix.md` (본 fix 완료 후 W1 착수) |
