# F08. 점포 이력/리스크 분석 Spec

> 특정 상권의 과거 점포 변동 이력과 리스크 진단

---

## 1. 개요

| 항목 | 내용 |
|------|------|
| Phase | 2 (차별화) |
| 의존성 | F02 (AI 챗봇) |
| 핵심 차별점 | 오픈업/소상공인365는 "현재"만 → 우리는 **이력 기반 리스크** 제공 |
| 트리거 | "이 자리 위험해?", "폐업률 어때?", "여기 가게 자주 바뀌어?" |

## 2. 분석 항목

| 지표 | 설명 | 산출 방식 |
|------|------|-----------|
| 업종별 평균 생존 기간 | 점포가 평균 몇 개월 유지되는지 | `store_history.duration_months` 평균 |
| 업종 회전율 | 특정 기간 내 개업/폐업 비율 | `stores.open_count + close_count / store_count` |
| 위험 업종 경고 | 폐업률이 극단적으로 높은 업종 | 폐업률 > 상위 10% 기준 |
| 상권 안정성 점수 | 전체 점포 회전율 기반 0~100 | 100 - (전체 회전율 × 가중치) |
| 최근 변동 추이 | 분기별 개폐업 수 추이 | 최근 4분기 stores 데이터 |

## 3. Agent Tool: `get_store_history`

```python
@tool
def get_store_history(district_code: str) -> dict:
    """상권의 점포 이력 및 리스크 지표를 분석합니다."""

    # 1. 업종별 평균 생존 기간
    survival = query_avg_survival_by_category(district_code)

    # 2. 업종별 회전율
    turnover = query_turnover_by_category(district_code)

    # 3. 위험 업종 식별
    risk_categories = [c for c in turnover if c["close_rate"] > threshold]

    # 4. 상권 안정성 점수
    stability = calculate_stability_score(district_code)

    # 5. 분기별 추이
    trend = query_quarterly_open_close(district_code)

    return {
        "survival_by_category": survival,
        "turnover_by_category": turnover,
        "risk_categories": risk_categories,
        "stability_score": stability,
        "quarterly_trend": trend
    }
```

## 4. 반환 데이터

```json
{
  "stability_score": 72,
  "stability_grade": "양호",
  "survival_by_category": [
    {"category": "카페", "avg_months": 21.6, "sample_count": 45},
    {"category": "치킨전문점", "avg_months": 10.8, "sample_count": 23},
    {"category": "한식", "avg_months": 28.4, "sample_count": 67}
  ],
  "risk_categories": [
    {"category": "치킨전문점", "close_rate": 18.2, "warning": "폐업률 매우 높음"},
    {"category": "주점", "close_rate": 14.5, "warning": "폐업률 높음"}
  ],
  "quarterly_trend": [
    {"quarter": "2025Q1", "open": 28, "close": 22},
    {"quarter": "2025Q2", "open": 31, "close": 25},
    {"quarter": "2025Q3", "open": 26, "close": 30},
    {"quarter": "2025Q4", "open": 32, "close": 28}
  ]
}
```

## 5. 안정성 점수 산출

### 5.1 기본 점수 산출

```python
def calculate_stability_score(district_code: str) -> dict:
    """상권 안정성 점수 (0~100) + 추세 분석"""
    # 최근 4분기 데이터
    data = get_recent_quarters(district_code, n=4)

    if len(data) < 2:
        return {"score": None, "grade": "데이터 부족",
                "message": "2분기 이상 데이터가 쌓이면 리스크 분석이 가능합니다"}

    total_stores = sum(d["store_count"] for d in data) / len(data)
    total_close = sum(d["close_count"] for d in data)
    avg_close_rate = total_close / (total_stores * len(data))

    # 기본 점수: 100에서 폐업률 비례 차감
    base_score = max(0, 100 - avg_close_rate * 10)

    # 추세 보정
    trend_result = detect_trend([d["close_count"] for d in data])
    base_score += trend_result["adjustment"]

    score = round(min(100, max(0, base_score)))
    return {
        "score": score,
        "grade": get_grade(score),
        "trend": trend_result,
        "quarters_analyzed": len(data)
    }
```

### 5.2 추세 감지 로직 (선형 회귀 기반)

```python
def detect_trend(close_counts: list[int]) -> dict:
    """
    최근 4분기 폐업 수에 선형 회귀를 적용하여 추세 판단.
    - 기울기(slope)가 양수이고 유의미하면 "증가 추세" → 감점
    - 기울기가 음수이고 유의미하면 "감소 추세" → 가점
    - 그 외 "보합"
    """
    n = len(close_counts)
    if n < 2:
        return {"direction": "insufficient_data", "adjustment": 0}

    # 단순 선형 회귀: y = ax + b
    x = list(range(n))
    x_mean = sum(x) / n
    y_mean = sum(close_counts) / n
    numerator = sum((x[i] - x_mean) * (close_counts[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator != 0 else 0

    # 변화율: 기울기 / 평균 폐업 수 (상대적 크기 판단)
    change_rate = slope / y_mean if y_mean > 0 else 0

    if change_rate > 0.15:      # 분기당 15% 이상 증가
        return {"direction": "increasing", "adjustment": -15,
                "detail": f"폐업이 분기당 {abs(change_rate)*100:.0f}% 증가 추세"}
    elif change_rate > 0.05:    # 분기당 5~15% 증가
        return {"direction": "slightly_increasing", "adjustment": -7,
                "detail": f"폐업이 소폭 증가 추세"}
    elif change_rate < -0.15:   # 분기당 15% 이상 감소
        return {"direction": "decreasing", "adjustment": +10,
                "detail": f"폐업이 분기당 {abs(change_rate)*100:.0f}% 감소 추세"}
    elif change_rate < -0.05:   # 분기당 5~15% 감소
        return {"direction": "slightly_decreasing", "adjustment": +5,
                "detail": f"폐업이 소폭 감소 추세"}
    else:
        return {"direction": "stable", "adjustment": 0,
                "detail": "폐업 추세 보합"}
```

### 5.3 최소 데이터 요건

| 보유 분기 수 | 동작 |
|-------------|------|
| 0~1분기 | 안정성 점수 미산출, "데이터 축적 중" 메시지 표시 |
| 2~3분기 | 점수 산출 + "N분기 데이터 기준 (4분기 이상 시 정확도 향상)" 안내 |
| 4분기 이상 | 정상 산출 |

### 5.4 위험 업종 경고 임계값

| 등급 | 폐업률 기준 | UI 표시 |
|------|-----------|---------|
| 매우 높음 | 해당 상권 전체 업종 폐업률의 **상위 10%** 또는 절대값 15% 초과 | 🔴 + "폐업률 매우 높음" |
| 높음 | 상위 10~25% 또는 절대값 10~15% | 🟡 + "폐업률 높음" |
| 보통 | 그 외 | 경고 없음 |

> **상대+절대 기준 병용 이유**: 전체적으로 안정적인 상권에서도 특정 업종의 절대 폐업률이 높으면 경고가 필요하고, 반대로 전체가 불안정한 상권에서는 상대적으로 더 나쁜 업종을 식별해야 하기 때문.

### 5.5 생존 기간 산출 대상

```sql
-- 폐업 점포 (실측 생존 기간)
SELECT category_name,
       AVG(duration_months) AS avg_duration,
       COUNT(*) AS sample_count
FROM store_history
WHERE district_code = $1 AND close_date IS NOT NULL
GROUP BY category_name
HAVING COUNT(*) >= 3   -- 최소 3건 이상일 때만 표시 (통계 신뢰도)
ORDER BY avg_duration DESC;
```

> **현재 영업 중인 점포는 제외**: 영업 기간이 아직 확정되지 않았으므로 포함 시 왜곡. 단, 해당 업종의 "현재 영업 중 N개" 정보는 별도 표시.

| 점수 | 등급 | 해석 |
|------|------|------|
| 80~100 | 매우 안정 | 점포 회전이 적고 장기 영업 비율 높음 |
| 60~79 | 양호 | 평균적인 수준 |
| 40~59 | 주의 | 회전율이 높은 편, 입지 검토 필요 |
| 0~39 | 위험 | 빈번한 폐업, 심층 분석 권장 |

## 6. RiskCard UI

```
┌────────────────────────────────────────────┐
│ ⚠ 강남역 상권 리스크 분석                    │
│                                            │
│ 상권 안정성: 72점 (양호)                     │
│ ████████████████████░░░░░░░░░░ 72/100      │
│                                            │
│ 📊 업종별 평균 생존 기간                     │
│ 한식        ████████████████ 28.4개월       │
│ 카페        ██████████████ 21.6개월         │
│ 치킨전문점  ████████ 10.8개월 ⚠             │
│                                            │
│ 🚨 위험 업종                                │
│ • 치킨전문점: 폐업률 18.2% (주의)           │
│ • 주점: 폐업률 14.5% (주의)                 │
│                                            │
│ 📈 분기별 개폐업 추이                        │
│ [개업/폐업 라인 차트]                        │
│                                            │
│ 데이터 기준: 2025년 4분기                    │
├────────────────────────────────────────────┤
│ [안전한 업종 추천받기] [다른 상권 비교]        │
└────────────────────────────────────────────┘
```

## 7. DB 쿼리

```sql
-- 업종별 평균 생존 기간
SELECT category_name,
       AVG(duration_months) as avg_duration,
       COUNT(*) as sample_count
FROM store_history
WHERE district_code = $1 AND close_date IS NOT NULL
GROUP BY category_name
ORDER BY avg_duration DESC;

-- 분기별 개폐업 추이
SELECT quarter, SUM(open_count) as opens, SUM(close_count) as closes
FROM stores
WHERE district_code = $1
GROUP BY quarter
ORDER BY quarter DESC
LIMIT 4;
```

## 8. 수용 기준

- [ ] "이 자리 위험해?" 질문에 리스크 카드가 생성된다
- [ ] 상권 안정성 점수(0~100)가 표시된다
- [ ] 업종별 평균 생존 기간이 바 차트로 표시된다
- [ ] 위험 업종이 경고와 함께 표시된다
- [ ] 분기별 개폐업 추이 차트가 표시된다
- [ ] "안전한 업종 추천" 클릭 시 F07로 연결된다

---

*작성일: 2026-03-24*
