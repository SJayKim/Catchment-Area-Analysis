# Plan — 데이터 정합성 (Data Integrity / Reliability) Audit

> 작성: 2026-04-23
> 목표: (1) AI 가 생성/활용하는 데이터의 **계산 정확성** 과 (2) 원천 데이터 자체의 **신뢰성(외부 교차검증)** 을 독립 검증.
> 산출물: `docs/qa/runs/data-integrity-audit-2026-04-23.md` (Phase 1~3 verdict + 권장사항)

---

## Context

### 배경 문제의식

프로덕션 운영 중 AI 가 내놓는 수치 (유동인구, 매출, 점포수, 벤치마크 백분위) 가 실제 현장 감각과 괴리되는지 사용자가 판단할 근거가 부족하다. 2026-04-17 매출 단위 혼동 버그 (`THSMON_SELNG_AMT` = 분기 누적 vs. 당월 표기) 가 발견된 이력이 있고, 2026-04-22 완성도 평가에서 **정확성 = 74/100** 으로 가장 낮은 축이었다. 따라서:

1. **계산 정확성** — DB raw → Repository → Tool → Card → LLM 응답 의 파이프라인 각 단계에서 숫자 변형이 의도대로 되는지
2. **원천 신뢰성** — 서울 열린데이터 자체가 실제 상권(강남/홍대/건대/명동/서울역) 의 알려진 규모와 얼마나 일치하는지

### 기존 memory / Plan 교훈 참조

- `feedback_check_env_before_test.md` — USE_MOCK 모드 선확인. 실데이터 audit 이므로 `USE_MOCK=false` + db 컨테이너 기동 필수.
- `feedback_probe_endpoint_shape_first.md` — Card payload shape 는 source Read 가 아니라 curl 로 probe 선행.
- `feedback_marketscope_sse_format.md` — SSE 파싱은 표준 파서 금지, `data:` JSON 내부 `type` 사용.
- `feedback_stale_container_vs_source.md` — backend container 빌드시각 확인 후 테스트.
- 2026-04-17 `docs/plan/fix/...` — 매출 단위 `//3` 환산 분석 및 `verify_sales_units.py` 스크립트 존재.
- `docs/plan/fix/accuracy-gap-fix.md` — GAP-A~F 6건. 이 audit 은 해당 gap 중 "LLM 수치 할루시네이션 (GAP-D)" 와 직접 관련.

### 관찰된 가설 (audit 으로 검증/반증할 대상)

| ID | 가설 | 근거 |
|----|------|------|
| H1 | `estimated_sales.monthly_sales` 는 서울 OpenData `THSMON_SELNG_AMT` 분기 누적, Repository 에서 `// 3` 월환산 | `_units.py` 주석 + 2026-04-17 fix |
| H2 | `floating_population.daily_avg` 는 6개 time_slot count 의 **단순 합**. 같은 사람 복수 시간대 존재 시 **중복 카운트** 발생 가능 | `floating_population.py:39` |
| H3 | `get_store_info.top_categories` 는 `category_code` 없는 빈 문자열 포함 가능 (점포데이터 ETL 에서 집계 레벨 혼재) | `stores.py:96-109` |
| H4 | `sales_count // 3` 도 적용됨 — sales_count 가 상위 API 에서 분기 누적일 경우 OK, 월 count 일 경우 과소추정 | `estimated_sales.py:52` |
| H5 | `franchise_count / total_stores` 비율은 카테고리 간 store_count 의 단순 합 대비 franchise 의 단순 합. 업종 믹스 편향 없음 | `district_summary.py:134` |
| H6 | 서울 열린데이터의 "유동인구" 는 KT 통신사 기지국 data 기반 추정치 — 실제 보행자 수가 아님. 외부 카운터 data 와 다를 수 있음 | Seoul OpenData 메타 |
| H7 | `estimated_sales` 는 **BC카드 가맹점 결제 data** 기반 추정. 현금/타사 카드/무점포 누락 → 실제 매출 대비 과소추정 가능 | Seoul OpenData 메타 |

---

## Scope

### In Scope

- **5개 sample 상권** — Mock 세트 그대로: 강남역(D3001 mock 또는 실 code), 홍대, 건대, 명동, 서울역
- **데이터 레이어 3종**: `floating_population`, `estimated_sales`, `store`
- **Tool 결과물 6종**: `get_district_summary`, `get_floating_population`, `get_estimated_sales`, `get_store_info`, `compare_districts`, `estimate_revenue`
- **Card payload 정합성** (SSE 이벤트 → 화면 수치)
- **LLM 응답 hallucination** (Tool 결과에 없는 숫자가 Respond 노드 출력에 포함되는지)

### Out of Scope

- `resident_population` (이번 audit 생략, 추후 라운드)
- `store_history` (실데이터 미적재, 샘플 부족)
- heatmap / PDF 정확성 (동일 data source 이므로 위 검증으로 대체)
- Mock fixture 자체 정확성 (Mock 은 데모용 샘플이지 production data 아님)

### Sample 상권 확정 조건

- 실제 code 는 DB 에서 이름 LIKE 검색 결과 top-hit 1건 (동명 상권 복수면 flow/sales 합 최대)
- 모든 5개 상권의 최신 quarter 가 동일해야 비교 가능. 이질이면 per-district 최신으로 진행.

---

## Design

### Phase 1 — 원천 데이터 신뢰성 (External cross-check)

```
┌──────────────────┐   ┌─────────────────────┐   ┌───────────────┐
│ Seoul OpenData   │   │ DB (local Postgres) │   │ External      │
│ API 직접 raw 호출 │──▶│ 동일 row SQL 조회    │──▶│ 공개 소스 비교 │
└──────────────────┘   └─────────────────────┘   └───────────────┘
        ▲                                                 │
        │                                                 │
        └────────────── 일치성 / 괴리율 리포트 ──────────────┘
```

1. **API ↔ DB 일치성**
   - 5개 상권의 2025Q4 raw row 를 `VwsmTrdarSelngQq` / `VwsmTrdarFlpopQq` / `VwsmTrdarStorW` 에서 직접 fetch
   - DB 의 해당 district_code 분기 row 와 column-by-column diff
   - 허용 오차: ETL `_safe_bigint` 에서 float 변환으로 1 이내 반올림만 허용
2. **외부 소스 교차 검증** (WebSearch + WebFetch)
   - 상권별 "유동인구" 관련 **보도자료/논문/블로그** 3건 이상 수집
   - "월매출" 규모감: 업종별 공개 통계 / 뉴스
   - 점포수: 네이버 플레이스/카카오맵 검색 결과 대략치 ("강남역 카페 OOO곳")
   - 목표: 크기 1 order (10배 이내) 일치면 "신뢰", 그 이상 괴리면 "의심" 으로 flag

### Phase 2 — Tool/Repository 계산 정확성 (Internal math)

1. **직접 SQL 집계 vs Tool 반환 diff**
   - 각 Tool 을 `python -c` 로 직접 호출 → JSON dump
   - 같은 상권·quarter 에 대해 독립 SQL (`psql -c`) 로 raw 집계
   - `// MONTHS_PER_QUARTER` 적용 후 일치하는지 검증
2. **파생 지표 재계산**
   - `perStoreSales = monthly_sales / total_stores` → Python 으로 재계산
   - `franchiseRatio`, `weekendUplift`, `qoqGrowth` 동일 방식
   - `benchmarks.percentile_rank` 가 district_type 내 순위 정의와 일치?
3. **Compare 차이 계산**
   - `compare_districts` 반환의 `winners/gaps` 가 Tool 의 개별 반환과 consistent
4. **Simulate p25/avg/p75**
   - `estimate_revenue` 의 3분위값이 해당 업종 유사 상권 표본에서 분위수 정의와 일치

### Phase 3 — AI 응답 정확성 (LLM hallucination check)

1. **SSE end-to-end capture**
   - 5개 상권 × 3 intent (`summary`/`comparison`/`recommendation`) = 15 session
   - `text` 이벤트 누적 = 최종 assistant 응답
   - `card` / `tool_end` 이벤트에서 나온 **ground-truth 숫자 집합** 추출
2. **Number extraction diff**
   - 응답 텍스트에서 정규식 (`\d+(?:,\d{3})*(?:\.\d+)?\s*(?:억|만|명|%|원|곳|개)`) 으로 모든 수치 추출
   - ground-truth 숫자 집합에 없는 값이 있으면 hallucination 의심 case 로 로깅
   - 허용: 단순 반올림 (예: 2,345만 → 약 2천3백만), 비율 파생 (A/B 계산값)
3. **출처 citation 검증**
   - `dataSources` 필드의 URL/기관명이 실존하는지 WebFetch 로 200 확인
   - LLM 이 dataSources 에 없는 기관을 응답에서 인용하면 fail

---

## Checklist

### Pre-flight (환경)

- [ ] 1. `.env` 값 확인: `USE_MOCK=false`, `DATABASE_URL` = localhost:5432, `SEOUL_OPENDATA_API_KEY` 존재
- [ ] 2. `docker compose up -d db redis` — DB/Redis 만 기동 (audit 은 backend 없이 직접 호출)
- [ ] 3. `alembic head` + seed dump 적재 확인 (districts 1650 건, 4개 ETL 테이블 row count)
- [ ] 4. 5개 sample 상권의 실제 `district_code` 확정 (이름 LIKE 검색)

### Phase 1 — 원천 데이터 신뢰성

- [ ] P1-1. 5개 상권 최신 quarter 확인 (모두 동일 quarter 인가?)
- [ ] P1-2. `VwsmTrdarSelngQq` 호출 → 해당 TRDAR_CD 필터 → DB estimated_sales row 와 column diff
- [ ] P1-3. `VwsmTrdarFlpopQq` 호출 → TMZON_* 6 컬럼 diff (unpivot 전 raw 비교)
- [ ] P1-4. `VwsmTrdarStorW` 호출 → STOR_CO/OPBIZ/CLSBIZ/FRC_STOR diff
- [ ] P1-5. 유동인구 외부 보도자료 5건 수집 (WebSearch) → 규모 order-of-magnitude 비교
- [ ] P1-6. 매출 외부 통계 2건 이상 수집 → 규모 비교 (예: "강남 카페 평균 월매출")
- [ ] P1-7. 점포수: 네이버지도/카카오맵 UI 에서 "OO역 카페" 대략치 vs Seoul data 수치
- [ ] P1-8. **Verdict** — 원천 데이터: PASS / WARN / FAIL 각 상권별 기록

### Phase 2 — Tool/Repository 계산 정확성

- [ ] P2-1. `get_floating_population(D_CODE)` 직접 호출 결과 vs raw SQL `SUM(total_pop) GROUP BY time_slot` diff
- [ ] P2-2. `get_estimated_sales(D_CODE)` vs raw SQL `SUM(monthly_sales) // 3` — 분기→월 환산 정확한가
- [ ] P2-3. `get_store_info(D_CODE)` vs raw SQL `SUM(store_count)` — `// 3` 적용 **되지 않아야** 함 (store_count 는 분기 시점 값)
- [ ] P2-4. `get_district_summary.insights.perStoreSales` = monthly_sales / total_stores 재계산 일치
- [ ] P2-5. `franchiseRatio`, `weekendUplift`, `qoqGrowth` 재계산 일치
- [ ] P2-6. `compare_districts` 반환의 `winners` 가 지표별 argmax 와 일치
- [ ] P2-7. `estimate_revenue` p25/avg/p75 가 표본 집합에서 numpy.percentile 와 일치
- [ ] P2-8. `benchmarks.percentile_rank` 가 district_type 내 순위/count 정의와 일치
- [ ] P2-9. `H2 유동인구 daily_avg 중복카운트 가설` — Seoul OpenData 메타 / FAQ 로 확인
- [ ] P2-10. `H4 sales_count 분기/월 단위` — upstream 문서로 확인
- [ ] P2-11. **Verdict** — Repository 계산: PASS / FAIL 리스트

### Phase 3 — AI 응답 hallucination 검증

- [ ] P3-1. docker backend 기동 (또는 local uvicorn) — `/api/health` 200 확인
- [ ] P3-2. 5상권 × 3 intent = 15 SSE capture (python script)
- [ ] P3-3. 각 session 의 `card.data` / `tool_end.result` 에서 ground-truth 수치 집합 추출
- [ ] P3-4. `text` 이벤트 concat → 응답 텍스트 확보 → 수치 정규식 추출
- [ ] P3-5. 응답 수치 ∖ ground-truth ≠ ∅ 시 hallucination 의심 리스트업
- [ ] P3-6. 단순 파생 (예: 합계/비율) 허용 규칙 적용 후 residual 수치 최종 판정
- [ ] P3-7. `dataSources` 필드 URL HEAD 200 확인
- [ ] P3-8. **Verdict** — 응답별 hallucination 0 / 경미 / 심각 분류

### Report

- [ ] R-1. `docs/qa/runs/data-integrity-audit-2026-04-23.md` 작성 — 테이블 요약 + 상세 diff
- [ ] R-2. 발견된 각 결함을 `feedback_*.md` memory 저장 또는 후속 fix plan 생성
- [ ] R-3. `docs/status/current-status.md` 2026-04-23 섹션에 audit verdict 추가

---

## 재검토 (Self-Review Gate)

### 엣지케이스

- **Quarter 불일치**: 5개 상권 중 최신 quarter 가 다르면 비교 어려움. → 각 상권 최신 quarter 기준으로 독립 검증하고 verdict 는 상권별로 분리.
- **API rate limit**: Seoul OpenData 는 하루 10,000 호출 제한. 5 상권 × 3 service × 페이징 = 충분. 단, page_size 1000 로 1 호출로 끝내고 필터링.
- **외부 검증 주관성**: 블로그/뉴스 수치는 연도·측정방법 제각각. 따라서 "order-of-magnitude" 로만 판단, 정확한 숫자 일치는 요구하지 않음.
- **LLM 응답 비결정성**: Respond 노드는 LLM stream 이므로 seed 고정 불가. 동일 질문 2번 호출 후 숫자 일치 여부만 확인 (결정적 수치여야 함 — Tool 결과 기반).
- **Hallucination 오탐**: "약 2만명" 같은 반올림을 hallucination 으로 오판할 수 있음. residual 판정 시 ±10% 허용 또는 ground-truth 중 가장 가까운 값과의 ratio 비교.

### 타 Plan 충돌

- `docs/plan/fix/accuracy-gap-fix.md` W1 에 "HALT-RAG / abstention" 이 예정됨. 이 audit 은 그 필요성 근거를 제공 → 충돌 아닌 보완 관계.
- `docs/plan/infra/e2e-regression-plan-2026-04-19.md` E2E 회귀와 중복 아님 (E2E 는 기능 동작 회귀, 이 audit 은 숫자 정합성).

### Memory 교훈 재확인

- ✅ USE_MOCK false 사전 확인 (`.env` 확인 완료, 위 Pre-flight 1)
- ✅ SSE 표준 파서 금지 → Phase 3 에서 custom 파서 사용 예정
- ✅ endpoint shape probe 선행 → Phase 2 에서 직접 호출로 확인
- ✅ backend container 빌드시각 확인 → Phase 3 에서 `docker inspect --format "{{.Created}}"` 기록

---

## Scenario (E2E Ring Mapping)

> 이 audit 은 E2E 기능 회귀가 아니라 **데이터 audit** 이므로 Ring 3 (Negative/Edge) 연장선으로 매핑. 시나리오 ID 규약: `R3-DATA-<ID>`.

| ID | Ring | 범위 | Pass 조건 |
|----|:--:|------|----------|
| R3-DATA-01 | 3 | Seoul API ↔ DB 일치 (estimated_sales) | 5/5 상권 모든 key column 일치 |
| R3-DATA-02 | 3 | Seoul API ↔ DB 일치 (floating_pop raw) | 5/5 상권 TMZON_* 6개 일치 |
| R3-DATA-03 | 3 | Seoul API ↔ DB 일치 (stores) | 5/5 상권 STOR_CO 일치 |
| R3-DATA-04 | 3 | 외부 소스 order-of-magnitude | 5/5 상권 유동인구/매출/점포수 ≤10배 괴리 |
| R3-DATA-05 | 3 | Tool vs raw SQL (sales, `//3` 환산) | 모든 상권 정확히 일치 |
| R3-DATA-06 | 3 | Tool vs raw SQL (floating pop) | daily_avg == sum(time_slot totals) |
| R3-DATA-07 | 3 | 파생 지표 재계산 (insights) | 5 key (perStoreSales/franchiseRatio/weekendUplift/qoqGrowth/genderInsight) |
| R3-DATA-08 | 3 | compare_districts winners argmax | 2상권 비교 시 winner 가 실제 큰 값 |
| R3-DATA-09 | 3 | estimate_revenue 3분위 | numpy.percentile 결과와 ±1원 이내 |
| R3-DATA-10 | 3 | LLM hallucination 검증 | 응답 내 모든 수치 ∈ ground-truth ∪ 파생 |
| R3-DATA-11 | 3 | dataSources URL liveness | 5개 URL 모두 HEAD 200 |

---

## Pass 반복

### Pass 1 — 기본 (5 상권, latest quarter, sample 상권)

Checklist 전체 진행. 각 FAIL 은 즉시 memory 에 원인 저장. 수정 가능한 fix 는 hotfix PR 로 분리.

### Pass 2 — 엣지

- 분기 1차례 전 (lag) data 추가 검증: quarter = latest - 1 에서도 같은 Tool 결과 정합성 유지?
- 업종 필터 유·무 비교: `get_estimated_sales(code, None)` vs `get_estimated_sales(code, "CS200001")` 합산 일치?
- 상권 type 4종 (골목/발달/전통시장/관광특구) 각 1개씩 sample 늘려 benchmarks percentile 정확성 확인

### Pass 3 — 성능 / 규모

- 1650 상권 전체 대상 요약 통계 (avg/max floating_pop, avg monthly_sales, std dev) 계산 후 outlier 확인
- 특정 상권의 매출이 1조원/월을 넘으면 (= 강남역 전체도 수백억 수준) **이상치 flag** — 단위 환산 버그 잠복 가능성

---

## Agent 모델 선택

- **설계 (이 Plan)**: Opus (현재 턴)
- **구현 — SQL/API 스크립트 작성 및 실행**: Sonnet (직접 실행)
- **검증 — 외부 소스 교차조회 (WebSearch/WebFetch)**: Opus (판단 필요)
- **Hallucination 판정 — 수치 매칭 로직**: Sonnet

---

## Metadata

- 생성일: 2026-04-23
- 종결 예상: 당일 (~3~4시간)
- 연관: `docs/plan/fix/accuracy-gap-fix.md` (GAP-D hallucination 완화 근거 자료)
- 후속: audit 결과에 따라 `plan/fix/data-source-*` 또는 UI "데이터 출처/한계" 고지 강화
