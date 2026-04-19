# F09. 간이 매출 시뮬레이션 Spec

> 업종 + 조건 입력 → 예상 매출 범위 제시

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| Phase | 3 — **완료** (Phase 2 Tier 게이팅 대기) |
| Tier | **Premium** (현재 게이팅 없음) |
| 의존성 | F04 (업종 분석 로직) |
| Tool | `estimate_revenue` |
| Card | SimulationCard (p25 / avg / p75 + 서울 평균 비교) |
| 접근 방식 | 공공데이터 기반 **범위 추정** (정밀 모델 X) |
| 트리거 | "카페 열면 매출 얼마?", "매출 시뮬레이션", "경쟁 2개 더 생기면?" |
| 주의 | DB 매출 컬럼은 분기 누적 → Repository 에서 월 환산 후 percentile 계산 |

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

```python
def get_sales_percentiles(category_code: str, quarter: str) -> dict:
    """서울 전체 동일 업종의 점포당 매출 분포에서 분위수 비율 산출"""

    rows = db.query("""
        SELECT es.district_code,
               es.monthly_sales / NULLIF(s.store_count, 0) AS per_store_sales
        FROM estimated_sales es
        JOIN stores s ON es.district_code = s.district_code
            AND es.category_code = s.category_code
            AND es.quarter = s.quarter
        WHERE es.category_code = $1
            AND es.quarter = $2
            AND s.store_count >= 3   -- 점포 3개 미만 상권은 이상치로 제외
        ORDER BY per_store_sales
    """, category_code, quarter)

    if len(rows) < 10:
        # 데이터 부족 시 고정 비율 사용
        return {"p25_ratio": 0.6, "p75_ratio": 1.5, "sample_count": len(rows), "reliable": False}

    values = [r.per_store_sales for r in rows]
    median = values[len(values) // 2]
    p25 = values[len(values) // 4]
    p75 = values[len(values) * 3 // 4]

    return {
        "p25_ratio": round(p25 / median, 2) if median else 0.6,
        "p75_ratio": round(p75 / median, 2) if median else 1.5,
        "p25_value": p25,
        "p75_value": p75,
        "median_value": median,
        "sample_count": len(values),
        "reliable": True
    }
```

> **설계 근거**: 서울 전체 기준으로 해야 "이 상권이 서울 내에서 어느 위치인지" 맥락이 생긴다. 또한 단일 상권 내 개별 점포 매출 데이터는 공공데이터에 없으므로 상권 간 비교가 유일한 방법.

### 2.4 Agent Tool: `simulate_revenue`

```python
@tool
def simulate_revenue(
    district_code: str,
    category_code: str,
    unit_price: int = None,
    additional_competitors: int = 0
) -> dict:
    """업종별 예상 매출 범위를 시뮬레이션합니다."""

    sales = get_estimated_sales(district_code, category_code)
    stores = get_store_info(district_code, category_code)

    total_sales = sales["monthly_sales"]
    store_count = stores["store_count"]

    # 경쟁 증가 시 비례 분배
    effective_stores = store_count + additional_competitors
    per_store = total_sales / effective_stores

    # 분위수 추정 (서울 전체 동일 업종 기반)
    percentiles = get_sales_percentiles(category_code, sales["quarter"])

    return {
        "estimated_monthly": {
            "low": round(per_store * percentiles["p25_ratio"]),
            "avg": round(per_store),
            "high": round(per_store * percentiles["p75_ratio"])
        },
        "percentile_info": {
            "scope": "서울 전체 동일 업종",
            "sample_count": percentiles["sample_count"],
            "reliable": percentiles["reliable"]
        },
        "assumptions": {
            "total_sales": total_sales,
            "store_count": store_count,
            "additional_competitors": additional_competitors
        },
        "disclaimer": "카드 매출 기반 추정치이며 실제와 다를 수 있습니다"
    }
```

## 3. What-If 시나리오

### 3.1 경쟁 증가

| 시나리오 | 입력 | 산출 |
|----------|------|------|
| 경쟁 증가 | "카페 2개 더 생기면?" | 총매출 / (기존 + 2) 비례 분배 |

### 3.2 객단가 변경 (단순 비례 추정)

> **기존 "업종 이용률" 개념 제거** — 공공데이터에서 업종별 이용률(방문 전환율)은 구할 수 없으며, 임의 수치를 넣으면 오히려 정확도가 떨어진다.

대신 **기존 매출 대비 객단가 비례** 방식을 사용:

```python
def simulate_with_unit_price(
    district_code: str, category_code: str, user_unit_price: int
) -> dict:
    """객단가 변경 시뮬레이션"""
    base = simulate_revenue(district_code, category_code)

    # 업종 기본 객단가 (category_metadata에서 조회, 없으면 추정)
    default_price = get_default_unit_price(category_code)
    if default_price is None:
        return {**base, "note": "해당 업종의 기준 객단가 데이터가 없어 객단가 변경 시뮬레이션이 불가합니다"}

    # 객단가 변경 비율만큼 매출 비례 조정
    price_ratio = user_unit_price / default_price
    return {
        "estimated_monthly": {
            "low": round(base["estimated_monthly"]["low"] * price_ratio),
            "avg": round(base["estimated_monthly"]["avg"] * price_ratio),
            "high": round(base["estimated_monthly"]["high"] * price_ratio),
        },
        "assumptions": {
            **base["assumptions"],
            "unit_price": user_unit_price,
            "default_unit_price": default_price,
            "price_ratio": round(price_ratio, 2)
        },
        "disclaimer": "객단가 변경은 단순 비례 추정이며, 실제로는 객단가와 방문 수가 반비례할 수 있습니다"
    }
```

> **설계 근거**: "객단가 올리면 매출도 비례해서 오른다"는 단순화이지만, 공공데이터만으로 가격 탄력성을 모델링할 수 없다. 면책 문구로 한계를 명시하고, MVP에서는 비례 추정으로 충분.

## 4. 반환 데이터

```json
{
  "category_name": "카페",
  "estimated_monthly": {
    "low": 12000000,
    "avg": 21000000,
    "high": 35000000
  },
  "assumptions": {
    "total_sales": 1512000000,
    "store_count": 72,
    "additional_competitors": 0
  },
  "comparison": {
    "seoul_avg": 18000000,
    "vs_seoul": "+16.7%"
  },
  "disclaimer": "카드 매출 기반 추정치이며 실제와 다를 수 있습니다"
}
```

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
