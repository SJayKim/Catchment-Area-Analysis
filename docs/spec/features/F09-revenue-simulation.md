# F09. 간이 매출 시뮬레이션 Spec

> 업종 + 조건 입력 → 예상 매출 범위 제시

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| Phase | 3 — **완료** (Phase 2 Tier 게이팅 대기) |
| Tier | **Premium** (현재 게이팅 없음) |
| 의존성 | F04 (업종 분석 로직) |
| Tool | `simulate_revenue` |
| Card | SimulationCard (p25 / avg / p75 + 서울 평균 비교) |
| 접근 방식 | 공공데이터 기반 **범위 추정** (정밀 모델 X) |
| 트리거 | "카페 열면 매출 얼마?", "매출 시뮬레이션", "경쟁 2개 더 생기면?" |
| 주의 | DB 매출 컬럼은 분기 누적 → Repository 에서 월 환산 (percentile 비율 p25/p75 는 환산 무관, `seoul_avg_per_store` 절대액만 월 환산) |

## 2. 기본 시뮬레이션

### 2.1 입력

| 항목 | 필수 | 기본값 |
|------|------|--------|
| 업종 | O | - |
| 객단가 | X | 업종 평균 |
| 좌석수/면적 | X | 미사용 (MVP) |

### 2.2 산출 방식

```
해당 상권 + 해당 업종의 추정 매출 데이터 기반:
- 하위 (25th percentile): 점포당 매출 하위
- 평균: 점포당 평균 매출
- 상위 (75th percentile): 점포당 매출 상위
```

### 2.3 분위수(Percentile) 산출 범위 및 방법

**범위: 서울 전체 동일 업종** (해당 상권 단일이 아님)

단일 상권은 "해당 업종 총매출 / 점포 수 = 점포당 평균"이라는 하나의 값만 존재하므로 분위수 산출이 불가능하다. 서울 전체 ~400개 행정동의 동일 업종 점포당 매출 분포에서 분위수를 도출한다.

실 구현: `server/server/repositories/real/simulation.py::get_sales_percentiles(category_code, quarter=None)`.

- `estimated_sales ⨝ stores` (district_code + category_code + quarter 조인, `store_count > 0` 필터) 로 상권별 점포당 매출 분포 구성
- PostgreSQL `percentile_cont(0.25/0.50/0.75)` 로 분위수 산출, **p50(중앙값) 대비 비율**로 반환
- p25/p75 는 비율로만 쓰므로 분기→월 환산 무관. `seoul_avg_per_store` 만 절대액이라 `/ MONTHS_PER_QUARTER` 월 환산
- quarter 미지정 시 최신 분기 자동 선택

```python
# 반환 형상 (repositories/real/simulation.py)
{
    "category_code": "CS100010",
    "quarter": "2025Q4",
    "p25_ratio": 0.62,          # p25 / p50
    "p50_ratio": 1.0,
    "p75_ratio": 1.48,          # p75 / p50
    "seoul_avg_per_store": 18000000,  # 월 환산 절대액
    "sample_count": 214,
}
# sample_count == 0 또는 p50 == 0 이면 고정 비율 (p25 0.6 / p75 1.5, sample_count 0) 반환
```

> **신뢰도 판정은 Tool 레이어에서**: `simulate_revenue` 가 `sample_count >= 10` 일 때만 `reliable=True` 로 DB 비율을 쓰고, 미만이면 고정 비율(0.6 / 1.5)로 폴백한다.

> **설계 근거**: 서울 전체 기준으로 해야 "이 상권이 서울 내에서 어느 위치인지" 맥락이 생긴다. 또한 단일 상권 내 개별 점포 매출 데이터는 공공데이터에 없으므로 상권 간 비교가 유일한 방법.

### 2.4 Agent Tool: `simulate_revenue`

실 구현: `server/server/agent/tools/simulate_revenue.py` (`@register_tool("simulate_revenue", card_type="simulation", ...)`).

```python
@register_tool("simulate_revenue", card_type="simulation", ...)
async def simulate_revenue(
    district_code: str,
    category_code: str | None = None,
    unit_price: int | None = None,
    additional_competitors: int = 0,
) -> dict:
    """업종별 예상 매출 범위를 시뮬레이션합니다."""

    if not category_code:
        # 업종 미지정 시 에러 반환 (needs_category=True) → Agent 가 되물음
        return {"error": "어떤 업종의 매출을 예상해드릴까요? (예: 카페, 한식)",
                "district_code": district_code, "category_code": None, "needs_category": True}

    sales = get_estimated_sales(district_code, category_code)   # 월 환산 완료 값
    stores = get_store_info(district_code, category_code)

    # 경쟁 증가 시 비례 분배
    effective_stores = max(store_count + additional_competitors, 1)
    per_store_avg = total_monthly_sales / effective_stores

    # 분위수 (서울 전체 동일 업종) — sample_count < 10 이면 고정 비율 0.6/1.5 폴백
    percentiles = da.simulation.get_sales_percentiles(category_code, quarter)

    # 객단가 조정: unit_price 지정 시 default_unit_price 대비 비례 (price_ratio)
    # 서울 평균 비교: seoul_avg_per_store 대비 diff_percent + 라벨("높음"/"낮음"/"동일")
    ...
```

**반환 형상** (§4 참조): `simulation{low, avg, high}` + `basis{...}` + `percentiles{...}` + `seoul_comparison{...}|null` + `disclaimer`. 캐시 키 `simulation:{district}:{category}:{unit_price|default}:{additional_competitors}`, TTL 24h.

## 3. What-If 시나리오

### 3.1 경쟁 증가

| 시나리오 | 입력 | 산출 |
|----------|------|------|
| 경쟁 증가 | "카페 2개 더 생기면?" | 총매출 / (기존 + 2) 비례 분배 |

### 3.2 객단가 변경 (단순 비례 추정)

> **기존 "업종 이용률" 개념 제거** — 공공데이터에서 업종별 이용률(방문 전환율)은 구할 수 없으며, 임의 수치를 넣으면 오히려 정확도가 떨어진다.

대신 **기존 매출 대비 객단가 비례** 방식을 사용한다. 별도 함수가 아니라 `simulate_revenue` 의 `unit_price` 인자로 통합 구현되어 있다:

- 업종 기본 객단가: `da.simulation.get_default_unit_price(category_code)` — `category_metadata.default_unit_price`, NULL 이면 major_category 기본값(외식 12000 / 서비스 25000 / 소매 15000, 최종 폴백 15000)
- `unit_price` 지정 + 기본 객단가 존재 시 `price_ratio = unit_price / default_price` 를 low/avg/high 에 곱해 비례 조정
- 반환 `basis` 블록에 `unit_price` / `default_unit_price` / `price_ratio` 가 그대로 노출되어 산출 근거 추적 가능

> **설계 근거**: "객단가 올리면 매출도 비례해서 오른다"는 단순화이지만, 공공데이터만으로 가격 탄력성을 모델링할 수 없다. 면책 문구로 한계를 명시하고, MVP에서는 비례 추정으로 충분.

## 4. 반환 데이터

실제 반환 키 (`agent/tools/simulate_revenue.py`, 프론트 `SimulationCard` 가 `simulation`/`basis`/`percentiles`/`seoul_comparison` 소비):

```json
{
  "district_code": "3120052",
  "category_code": "CS100010",
  "category_name": "카페",
  "quarter": "2025Q4",
  "simulation": {
    "low": 12000000,
    "avg": 21000000,
    "high": 35000000
  },
  "basis": {
    "total_monthly_sales": 1512000000,
    "store_count": 72,
    "additional_competitors": 0,
    "effective_stores": 72,
    "unit_price": null,
    "default_unit_price": 12000,
    "price_ratio": 1.0
  },
  "percentiles": {
    "p25_ratio": 0.62,
    "p75_ratio": 1.48,
    "sample_count": 214,
    "reliable": true
  },
  "seoul_comparison": {
    "seoul_avg": 18000000,
    "diff_percent": 16.7,
    "label": "높음"
  },
  "disclaimer": "본 시뮬레이션은 카드매출 기반 추정치이며, 실제 매출과 다를 수 있습니다."
}
```

> `seoul_comparison` 은 서울 평균이 없으면 `null`. 업종 미지정 시에는 `{error, district_code, category_code: null, needs_category: true}` 에러 형상 반환.

## 5. SimulationCard UI

```
┌────────────────────────────────────────────┐
│ 🧮 강남역 카페 매출 시뮬레이션               │
│                                            │
│ 예상 월매출 범위                             │
│                                            │
│ 하위        평균          상위              │
│ 1,200만     2,100만       3,500만           │
│ ├──────────●──────────────┤                │
│                                            │
│ 서울 카페 평균(1,800만) 대비 +16.7%         │
│                                            │
│ 📌 산출 근거                                │
│ • 해당 상권 카페 72개 기준                   │
│ • 카페 전체 월매출 15.1억 기준               │
│                                            │
│ ⚠ 카드 매출 기반 추정치이며                  │
│   실제 결과와 다를 수 있습니다               │
├────────────────────────────────────────────┤
│ [경쟁 2개 추가 시뮬레이션] [다른 업종 비교]   │
└────────────────────────────────────────────┘
```

## 6. 수용 기준

- [x] "카페 매출 얼마?" → 매출 범위 제시
- [x] 하위(p25) / 평균 / 상위(p75) 3구간 표시
- [x] 서울 평균 대비 비교값 표시
- [x] 산출 근거 명시 (점포 수, 총매출)
- [ ] What-If "경쟁 N개 추가" — Tool 은 지원, UI 버튼 미구현
- [x] 면책 안내 표시
