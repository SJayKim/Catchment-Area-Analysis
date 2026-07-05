# F07. 업종 추천 Spec

> "여기서 뭐 하면 좋을까?" — 상권 기반 적합 업종 추천

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| Phase | 1A(Mock) · 1B(Real) — **완료** (Phase 2 에서 Premium 게이팅 예정) |
| Tier | 현재 Free (Phase 2 후 Premium 전용) |
| 의존성 | F03 (Tool 재활용), F04 (업종 분석 로직) |
| 핵심 차별점 | 오픈업: 업종→장소 / 우리: **장소→업종** (역방향) |
| 트리거 | "뭐 하면 좋을까?", "업종 추천해줘", "예산 3천만원으로 뭐 할 수 있어?" |
| 현재 구현 | `recommend_business` Tool(+ saturation/risk_flag/cost_category enrichment) + RecommendCard + ScoreBar + 면책. 점수는 **55~95 유계 밴드**(§6.3), 점포 3개 미만 카테고리는 랭킹 제외(§6.5) |

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
| 점포당 매출 | 업종 총매출(분기 누적 → `// MONTHS_PER_QUARTER` 월 환산) / 점포 수 (높을수록 수요>공급) | estimated_sales + stores |
| 연령 매칭률 | 업종 주소비층과 상권 유동인구 연령 분포 일치도 | floating_population |
| 폐업률 | 최근 분기 폐업 수 / 전체 점포 수 | stores |
| 경쟁 밀집도 | 동일 업종 점포 수 / 상권 전체 점포 수 | stores |
| **표본 신뢰도 플로어** | `store_count < 3`(`MIN_RELIABLE_STORES`) 카테고리는 점포당 지표가 통계적으로 무의미 → 랭킹 제외. 통과 카테고리 0이면 전체 fallback + "점포 표본이 적어(<3개) 참고용 추천입니다" 안내 (§6.5) | stores |

### 2.3 추가 필터링 (선택)

| 조건 | 효과 |
|------|------|
| 예산 | 업종별 평균 창업 비용(`avg_startup_cost`, 만원) 기준 필터 — 단 §6.4 현행 상태 주의 |
| 선호 업종군 | 외식/서비스/소매 (`major_category`) 부분일치 필터 |

## 3. Agent Tool: `recommend_business`

실구현은 2개 레이어로 나뉜다:

- **Tool 레이어** `server/server/agent/tools/recommend_business.py` — `@register_tool("recommend_business", card_type="recommend")`. 캐시 키 `recommend:{district_code}:{budget|all}:{preference|all}` (TTL 24h) 조회 후 repo 위임, 성공 시 `_enrich_recommendations` 로 항목별 필드 추가:
  - `saturation`: 점포 ≥200 "과포화" / ≥100 "포화" / 그 외 "여유"
  - `risk_flag`: 폐업률 >8% "고위험" / >6% "주의" (그 외 미부여)
  - `cost_category`: 창업비용(만원) ≥10000 "대자본" / ≥5000 "중간" / 그 외 "소자본"
- **Repository 레이어** `server/server/repositories/real/recommendation.py::recommend_business`:
  1. 최신 분기의 전 업종 점포(stores) + 매출(estimated_sales) + 유동인구 연령분포 조회
  2. 업종별 raw 점수 = `(점포당 매출 × age_match × (1 − 폐업률)) / max(경쟁밀집도, 0.01)` — age_match 는 연령대 매출 상위 누적 70% 주 소비층 대비 유동인구 비율(인라인 구현, 데이터 없으면 0.5)
  3. **표본 플로어**: `_apply_store_floor` 가 `store_count < MIN_RELIABLE_STORES(=3)` 카테고리 제외 (§6.5)
  4. 선호 업종군(preference — `major_category` 부분일치) → 예산(budget — `startup_cost <= budget`) 순 필터
  5. `_band_scores` 로 55~95 밴드 정규화 (§6.3) → score 내림차순 Top 5 반환

## 4. 반환 데이터

실제 반환 형상 (repo 필드 + Tool enrichment):

```json
{
  "district_code": "3110008",
  "quarter": "2025Q4",
  "total_categories_analyzed": 42,
  "recommendations": [
    {
      "rank": 1,
      "category_name": "디저트/베이커리",
      "category_code": "CS100020",
      "score": 95.0,
      "per_store_sales": 24000000,
      "monthly_sales": 192000000,
      "store_count": 8,
      "close_rate": 0.0,
      "age_match": 63.0,
      "reasons": [
        "점포당 월매출 2400만원",
        "타겟 고객 매칭률 63%",
        "경쟁 점포 8개 (밀집도 3.2%)",
        "폐업률 낮음 (0.0%)"
      ],
      "saturation": "여유",
      "cost_category": "소자본"
    },
    ...
  ]
}
```

- `score` 는 55~95 유계 밴드(§6.3) — **1위는 항상 95.0**, 최하위 55.0, 단일/전원 동점은 75.0
- `startup_cost` 는 메타데이터 값이 있을 때만, `risk_flag` 는 폐업률 >6% 일 때만 포함
- 표본 부족·예산 미매칭 시 최상위에 `message` 필드 동봉 (§6.5)

## 5. RecommendCard UI

```
┌────────────────────────────────────────────┐
│ 💡 강남역 업종 추천 Top 5                   │
│                                            │
│ 1. 디저트/베이커리            점수 95.0     │
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

실제 스키마 (alembic 001+002+003, `server/server/models/category.py`):

```sql
CREATE TABLE category_metadata (
    category_code      VARCHAR(20) PRIMARY KEY,
    category_name      VARCHAR(100) NOT NULL,
    major_category     VARCHAR(50),        -- 외식 / 서비스 / 소매
    avg_startup_cost   INTEGER,            -- 평균 창업 비용 (만원)
    default_unit_price INTEGER,            -- 기본 객단가 (원, alembic 002 — F09 시뮬레이션용)
    aliases            VARCHAR(500)        -- 업종 별칭, 쉼표 구분 (alembic 003 — F04 매핑용)
);
```

> 초기 설계의 `category_group`(구현명 `major_category`)·`avg_monthly_rent`·`data_source`·`updated_at` 컬럼은 미구현.
> **`avg_startup_cost` 단위는 만원(원 아님)** — enrichment 가 `≥10000(만원)=대자본 / ≥5000=중간 / 그 외 소자본` 기준으로 소비한다 (`recommend_business.py::_enrich_recommendations`).

> **`target_age_groups` 컬럼 제거**: 주 소비층은 하드코딩 대신 `estimated_sales`의 연령대별 매출 비중에서 **동적 산출**한다 (F04 Spec §4-A 참조). 분기마다 자동 갱신되어 트렌드 변화도 반영됨.

### 6.2 추천 점수 공식 (연령 매칭률 산출 변경)

```
raw 점수 = (점포당 매출)
          × (유동인구 연령 매칭률)    ← 연령대 매출 상위 누적 70% 주 소비층 방식 (F04 §4-A 설계와 동일 로직 — recommendation.py 에 인라인 구현, 별도 calculate_customer_match() 함수는 없음)
          × (1 - 폐업률)
          ÷ (경쟁 밀집도)
```

raw 점수는 §6.3 의 55~95 밴드 정규화를 거쳐 `score` 로 표기된다.

### 6.3 점수 정규화 (55~95 유계 밴드)

원시 점수는 매출 규모에 따라 편차가 크므로 **해당 상권 내 상대 정규화**를 적용한다.
단, min-max 를 0~100 으로 그대로 펴면 1위가 항상 100.0(절대 확신으로 오독)·꼴찌 0.0·단일 카테고리 0.0 이 되는 문제가 있어 **55~95 유계 밴드**로 정규화한다 (2026-07-04 deferred 백로그 fix, `repositories/real/recommendation.py::_band_scores`):

```python
SCORE_BAND_MIN = 55.0
SCORE_BAND_MAX = 95.0
SCORE_BAND_FLAT = 75.0  # 단일 카테고리 / 전원 동점

def _band_scores(values: list[float]) -> list[float]:
    """raw_score 리스트를 순위 보존한 채 SCORE_BAND_MIN~MAX 로 정규화."""
    if not values:
        return []
    min_val, max_val = min(values), max(values)
    if max_val == min_val:
        return [SCORE_BAND_FLAT] * len(values)
    span = SCORE_BAND_MAX - SCORE_BAND_MIN
    return [round(SCORE_BAND_MIN + (v - min_val) / (max_val - min_val) * span, 1) for v in values]
```

> 점수는 상권 내 **상대 순위** 표기다 — 1위 = 95.0, 최하위 = 55.0, 단일/동점 = 75.0.
> "점수 87.5 = 상위 87.5% 위치" 같은 백분위 해석은 성립하지 않는다.

### 6.4 평균 창업 비용 데이터 출처

| 출처 | 커버리지 | 갱신 주기 |
|------|---------|----------|
| 소상공인시장진흥공단 창업비용 통계 | 주요 50개 업종 | 연 1회 |
| 프랜차이즈 정보공개서 (공정위) | 프랜차이즈 업종 | 연 1회 |

- **초기 시딩**: 위 출처에서 주요 30개 업종 수동 입력
- **미보유 업종**: 동일 `category_group`의 평균값으로 대체, UI에 "추정치" 표시
- **예산 필터 미입력 시**: 필터링 스킵 (전 업종 대상 추천)

> ⚠ 현행 상태(2026-07-04): 리포 내에 `avg_startup_cost` 적재 경로가 **없다** — `seed_category_metadata.py` 는 `major_category`/`default_unit_price`/`aliases` 만 채운다. 값 부재 시 repo 가 0 으로 취급해 예산 필터가 사실상 전 업종을 통과시키고, 응답에서 `startup_cost` 필드가 생략되며 `cost_category` 는 일괄 "소자본" 으로 표시된다. 위 출처 기반 수동 시딩은 후속 과제.

### 6.5 표본 신뢰도 플로어 + 추천 결과가 5개 미만인 경우

**표본 플로어 (`MIN_RELIABLE_STORES = 3`)** — 점포 1~2개 카테고리는 점포당 매출이 카테고리 전체 매출로 잡히는 아티팩트로 1순위를 고정 점유했던 문제(2026-06-09 ISSUE-003)의 근본 대책:

| 상황 | 동작 |
|------|------|
| `store_count >= 3` 카테고리 존재 | 해당 카테고리만 랭킹 대상 (`_apply_store_floor`) |
| 전 카테고리 `store_count < 3` (작은 골목상권) | 전체로 fallback + `low_confidence` → `message: "점포 표본이 적어(<3개) 참고용 추천입니다"` |

**필터 후 개수 처리** (필터 순서: 표본 플로어 → 선호 업종군 → 예산):

| 상황 | 동작 |
|------|------|
| 필터 후 5개 이상 | Top 5 반환 |
| 필터 후 1~4개 | 해당 수만큼 반환 (별도 안내 메시지 없음) |
| 예산 필터 매칭 0개 | 예산 필터를 무시하고 추천 + `message: "예산 조건에 맞는 업종이 없어 전체 기준으로 추천합니다"` |
| 선호 필터 매칭 0개 | 선호 필터를 무시하고 추천 (안내 메시지 없음) |

## 7. 수용 기준

- [x] "뭐 하면 좋을까?" 에 Top 5 업종 추천
- [x] 각 추천에 점수(55~95 유계 밴드, §6.3) + 근거 제시
- [x] 점수 공식 적용 (점포당 매출 × 연령매칭 × (1-폐업률) / 경쟁밀집도)
- [x] 점포 3개 미만 카테고리 랭킹 제외 + fallback 시 참고용 안내 (§6.5, `MIN_RELIABLE_STORES`)
- [x] 예산 조건 입력 시 필터링 (Mock 검증 완료 — 단 Real DB 는 `avg_startup_cost` 미적재로 실질 변별력 없음, §6.4 주의)
- [x] 면책 조항 표시 (`RecommendCard` footer)
- [ ] "자세히 분석" → F04 연결 (F04 미완성으로 보류)
