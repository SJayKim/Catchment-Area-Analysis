# F07. 업종 추천 Spec

> "여기서 뭐 하면 좋을까?" — 상권 기반 적합 업종 추천

---

## 1. 개요

| 항목 | 내용 |
|------|------|
| Phase | 2 (차별화) |
| 의존성 | F03 (Tool 재활용), F04 (업종 분석 로직) |
| 핵심 차별점 | 오픈업: 업종→장소 / 우리: **장소→업종** (역방향) |
| 트리거 | "뭐 하면 좋을까?", "업종 추천해줘", "예산 3천만원으로 뭐 할 수 있어?" |

## 2. 추천 로직

### 2.1 추천 점수 공식

```
추천 점수 = (점포당 매출)
           × (유동인구 연령 매칭률)
           × (1 - 폐업률)
           ÷ (경쟁 밀집도)
```

### 2.2 산출 상세

| 요소 | 산출 방식 | 데이터 |
|------|-----------|--------|
| 점포당 매출 | 업종 총매출 / 점포 수 (높을수록 수요>공급) | estimated_sales + stores |
| 연령 매칭률 | 업종 주소비층과 상권 유동인구 연령 분포 일치도 | floating_population |
| 폐업률 | 최근 분기 폐업 수 / 전체 점포 수 | stores |
| 경쟁 밀집도 | 동일 업종 점포 수 / 상권 전체 점포 수 | stores |

### 2.3 추가 필터링 (선택)

| 조건 | 효과 |
|------|------|
| 예산 | 업종별 평균 창업 비용 기준 필터 (메타데이터) |
| 선호 업종군 | 음식/서비스/판매 등 카테고리 필터 |

## 3. Agent Tool: `recommend_business`

```python
@tool
def recommend_business(district_code: str, budget: int = None, preference: str = None) -> dict:
    """상권에 적합한 업종 Top 5를 추천합니다."""

    # 1. 해당 상권의 전 업종 데이터 조회
    all_categories = get_all_category_stats(district_code)

    # 2. 유동인구 연령 분포 조회
    pop_data = get_floating_population(district_code)

    # 3. 각 업종별 추천 점수 계산
    scores = []
    for cat in all_categories:
        score = calculate_recommendation_score(cat, pop_data)
        scores.append({"category": cat, "score": score})

    # 4. 필터링 (예산, 선호)
    if budget:
        scores = [s for s in scores if s["category"]["avg_startup_cost"] <= budget]

    # 5. 상위 5개 반환
    top5 = sorted(scores, key=lambda x: x["score"], reverse=True)[:5]
    return {"recommendations": top5, "district_code": district_code}
```

## 4. 반환 데이터

```json
{
  "recommendations": [
    {
      "rank": 1,
      "category_name": "디저트/베이커리",
      "score": 87.5,
      "reasons": [
        "점포당 월매출 2,400만원 (상위 20%)",
        "20~30대 유동인구 63%로 타겟 적합",
        "동일 업종 8개로 경쟁 낮음",
        "최근 폐업 0건"
      ],
      "monthly_sales_avg": 24000000,
      "store_count": 8,
      "close_rate": 0
    },
    ...
  ]
}
```

## 5. RecommendCard UI

```
┌────────────────────────────────────────────┐
│ 💡 강남역 업종 추천 Top 5                   │
│                                            │
│ 1. 디저트/베이커리            점수 87.5     │
│    ├ 점포당 월매출 2,400만 (상위 20%)       │
│    ├ 타겟 매칭률 높음 (20~30대 63%)        │
│    └ 경쟁 낮음 (8개점)                     │
│                                            │
│ 2. 브런치/샐러드              점수 82.3     │
│    ├ 점포당 월매출 1,900만                  │
│    ├ 직장인 수요 높음                       │
│    └ 신규 성장 트렌드                       │
│                                            │
│ 3. ...                                     │
│                                            │
│ 데이터 기준: 2025년 4분기                   │
│ ⚠ 추정치이며 실제 결과와 다를 수 있습니다    │
├────────────────────────────────────────────┤
│ [디저트 자세히 분석] [매출 시뮬레이션]        │
└────────────────────────────────────────────┘
```

## 6. 업종별 메타데이터 (참조 테이블)

### 6.1 스키마

```sql
CREATE TABLE category_metadata (
    category_code VARCHAR(20) PRIMARY KEY,
    category_name VARCHAR(100),
    category_group VARCHAR(50),        -- 음식/서비스/판매/...
    avg_startup_cost BIGINT,           -- 평균 창업 비용 (원)
    avg_monthly_rent BIGINT,           -- 평균 월 임대료 (원, MVP 제외)
    data_source VARCHAR(200),          -- 출처
    updated_at TIMESTAMP DEFAULT NOW()
);
```

> **`target_age_groups` 컬럼 제거**: 주 소비층은 하드코딩 대신 `estimated_sales`의 연령대별 매출 비중에서 **동적 산출**한다 (F04 Spec §4-A 참조). 분기마다 자동 갱신되어 트렌드 변화도 반영됨.

### 6.2 추천 점수 공식 (연령 매칭률 산출 변경)

```
추천 점수 = (점포당 매출 정규화)
           × (유동인구 연령 매칭률)    ← F04 §4-A의 calculate_customer_match() 사용
           × (1 - 폐업률)
           ÷ (경쟁 밀집도)
```

### 6.3 점수 정규화 (0~100 스케일)

원시 점수는 매출 규모에 따라 편차가 크므로, **해당 상권 내 상대 정규화**를 적용한다:

```python
def normalize_scores(raw_scores: list[dict]) -> list[dict]:
    """상권 내 전 업종 추천 점수를 0~100으로 정규화"""
    values = [s["raw_score"] for s in raw_scores]
    min_val, max_val = min(values), max(values)
    spread = max_val - min_val if max_val != min_val else 1

    for s in raw_scores:
        s["score"] = round((s["raw_score"] - min_val) / spread * 100, 1)
    return raw_scores
```

> 점수 87.5는 "해당 상권에서 분석된 전 업종 중 상위 87.5% 위치"를 의미함.

### 6.4 평균 창업 비용 데이터 출처

| 출처 | 커버리지 | 갱신 주기 |
|------|---------|----------|
| 소상공인시장진흥공단 창업비용 통계 | 주요 50개 업종 | 연 1회 |
| 프랜차이즈 정보공개서 (공정위) | 프랜차이즈 업종 | 연 1회 |

- **초기 시딩**: 위 출처에서 주요 30개 업종 수동 입력
- **미보유 업종**: 동일 `category_group`의 평균값으로 대체, UI에 "추정치" 표시
- **예산 필터 미입력 시**: 필터링 스킵 (전 업종 대상 추천)

### 6.5 추천 결과가 5개 미만인 경우

| 상황 | 동작 |
|------|------|
| 필터 후 5개 이상 | Top 5 반환 |
| 필터 후 1~4개 | 해당 수만큼 반환 + "조건에 맞는 업종이 N개입니다" 안내 |
| 필터 후 0개 | 필터 없이 Top 5 반환 + "예산 조건에 맞는 업종이 없어 전체 기준으로 추천합니다" 안내 |

## 7. 수용 기준

- [ ] "뭐 하면 좋을까?" 질문에 Top 5 업종이 추천된다
- [ ] 각 추천에 점수와 근거(3~4개)가 제시된다
- [ ] 추천 점수 공식이 정확하게 적용된다
- [ ] 예산 조건 입력 시 필터링이 반영된다
- [ ] 추천 카드에서 "자세히 분석" 클릭 시 F04로 연결된다
- [ ] 데이터 기준 시점과 면책 안내가 표시된다

---

*작성일: 2026-03-24*
