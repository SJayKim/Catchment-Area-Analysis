# F04. 업종별 심층 분석 Spec

> 특정 업종을 지정하면 해당 업종 관점에서의 맞춤 분석 제공

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| Phase | **2 — 미완** (Premium 전용) |
| Tier | **Premium** |
| 의존성 | F02 (AI 챗봇), F03 (기본 리포트), Tier 게이팅 (OAuth2/결제 Phase 2) |
| 트리거 | "카페 하면 어때?", "치킨집 분석해줘" 등 업종 지정 질문 |
| F03 과의 차이 | F03 은 상권 전체 개요, F04 는 **특정 업종** 관점 |
| 현재 상태 | Tool 코드는 존재 (`get_estimated_sales`, `get_store_info` 가 `category_code` 필터 지원). 별도 카드 UI 및 Tier 게이팅 미구현. |

## 2. 분석 항목

| 항목 | 산출 방식 | Tool | 데이터 |
|------|-----------|------|--------|
| 경쟁 밀집도 | 동일 업종 점포 수 / 상권 내 전체 점포 수 | `get_store_info` | stores 테이블 |
| 업종 평균 매출 | 해당 업종 추정 월 매출 / 점포 수 | `get_estimated_sales` | estimated_sales |
| 피크 타임 | 업종별 시간대 매출 비중 | `get_estimated_sales` | estimated_sales |
| 타겟 고객 매칭 | 유동인구 연령·성별 vs 업종 주 소비층 (매출 비중 기반 산출) | `get_floating_population` + `get_estimated_sales` | floating_population + estimated_sales |
| 생존율 | 업종 평균 영업 기간 | `get_store_info` | stores (개폐업) |
| 서울 평균 비교 | 해당 업종의 서울 전체 평균 대비 위치 | `get_estimated_sales` | estimated_sales |

## 3. Agent Tool 호출

```
사용자: "카페 하면 어때?"

Agent:
1. get_store_info(district_code, category_code="카페")        ─┐
2. get_estimated_sales(district_code, category_code="카페")    ├─ 병렬
3. get_floating_population(district_code)                      ─┘

4. LLM 종합 분석 → 텍스트 + 차트 데이터 생성
```

## 4. 업종 코드 매핑

### 4.1 매핑 전략: DB 퍼지 검색 + LLM 폴백 (2단계)

LLM 단독 매핑은 환각(hallucination) 리스크가 있으므로, **DB 우선 검색 → LLM 보조** 전략을 사용한다.

```python
def resolve_category_code(user_input: str) -> dict:
    """자연어 업종 입력 → 업종 코드 매핑 (2단계)"""

    # 1단계: DB 퍼지 검색 (trigram similarity + alias 테이블)
    results = db.query("""
        SELECT category_code, category_name, similarity(alias, $1) AS sim
        FROM category_aliases
        WHERE similarity(alias, $1) > 0.3
        ORDER BY sim DESC
        LIMIT 5
    """, user_input)

    if results and results[0].sim > 0.6:
        # 높은 유사도 → 바로 반환
        return {"code": results[0].category_code, "name": results[0].category_name, "confidence": "high"}

    if results and results[0].sim > 0.3:
        # 중간 유사도 → 후보 목록과 함께 LLM에 확인 요청
        candidates = [{"code": r.category_code, "name": r.category_name} for r in results]
        llm_pick = llm_select_from_candidates(user_input, candidates)
        return {"code": llm_pick["code"], "name": llm_pick["name"], "confidence": "medium"}

    # 2단계: 매칭 실패 → 사용자에게 재입력 요청
    return {"code": None, "confidence": "low", "message": f"'{user_input}'에 해당하는 업종을 찾지 못했습니다. 좀 더 구체적으로 말씀해주세요."}
```

### 4.2 업종 별칭(alias) 테이블

```sql
CREATE TABLE category_aliases (
    id SERIAL PRIMARY KEY,
    category_code VARCHAR(20) REFERENCES category_metadata(category_code),
    alias VARCHAR(100) NOT NULL  -- 자연어 변형
);

-- pg_trgm 확장 필요
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_alias_trgm ON category_aliases USING gin (alias gin_trgm_ops);
```

| category_code | alias (예시) |
|---------------|-------------|
| CS100001 | 카페, 커피숍, 커피전문점, 스타벅스, 카페창업 |
| CS200001 | 치킨, 치킨집, 치킨전문점, 프라이드치킨 |
| CS200002 | 한식, 밥집, 한식당, 한정식, 백반 |
| CS300001 | 편의점, 씨유, GS25, 세븐일레븐 |

- **초기 데이터**: 서울시 SEMAS 업종 분류 247개 × 평균 3~5개 alias = ~1,000건 수동 시딩
- **운영 시**: Langfuse에서 매핑 실패 로그 → 주기적으로 alias 추가

### 4.3 매핑 신뢰도별 동작

| confidence | 동작 |
|------------|------|
| `high` (sim > 0.6) | 바로 분석 진행 |
| `medium` (0.3 < sim ≤ 0.6) | "'{업종명}'으로 분석할까요?" 확인 후 진행 |
| `low` (매칭 없음) | "어떤 업종을 말씀하시는지 좀 더 구체적으로 알려주세요" 재질문 |

- 업종 코드 목록은 DB `category_codes` 참조 테이블에 보관
- Agent 시스템 프롬프트에 주요 매핑 포함

## 4-A. 타겟 고객 매칭률 산출 로직

### 산출 방식: 매출 데이터 기반 연령 소비 비중 (하드코딩 X)

업종 주 소비층을 하드코딩하면 데이터와 괴리가 생긴다. 대신 **서울 전체 해당 업종의 연령대별 매출 비중**에서 주 소비층을 자동 도출한다.

```python
def calculate_customer_match(district_code: str, category_code: str) -> dict:
    """타겟 고객 매칭률 산출"""

    # 1. 서울 전체 해당 업종의 연령대별 매출 비중 → "주 소비층" 도출
    age_sales = db.query("""
        SELECT age_group,
               SUM(monthly_sales) AS total_sales,
               SUM(monthly_sales) * 100.0 / SUM(SUM(monthly_sales)) OVER () AS pct
        FROM estimated_sales
        WHERE category_code = $1 AND quarter = $2
        GROUP BY age_group
        ORDER BY total_sales DESC
    """, category_code, current_quarter)

    # 상위 누적 70% 이상이 되는 연령대를 "주 소비층"으로 정의
    target_ages = []
    cumulative = 0
    for row in age_sales:
        target_ages.append(row.age_group)
        cumulative += row.pct
        if cumulative >= 70:
            break

    # 2. 해당 상권 유동인구 중 주 소비층 비율
    pop = db.query("""
        SELECT age_group, SUM(population) AS pop
        FROM floating_population
        WHERE district_code = $1 AND quarter = $2
        GROUP BY age_group
    """, district_code, current_quarter)

    total_pop = sum(p.pop for p in pop)
    target_pop = sum(p.pop for p in pop if p.age_group in target_ages)
    match_ratio = target_pop / total_pop if total_pop > 0 else 0

    # 3. 매칭 점수: 0~100 (비율 × 100, 최대 100)
    score = min(100, round(match_ratio * 100))

    return {
        "score": score,
        "target_age_groups": target_ages,
        "target_age_sales_pct": round(cumulative, 1),
        "district_target_pop_ratio": round(match_ratio * 100, 1)
    }
```

### 산출 예시

| 업종 | 서울 매출 기준 주 소비층 | 강남역 해당 연령 유동인구 비율 | 매칭 점수 |
|------|------------------------|-------------------------------|----------|
| 카페 | 20대(38%), 30대(32%) = 70% | 20~30대 63% | 63점 |
| 한식 | 40대(28%), 50대(25%), 30대(20%) = 73% | 30~50대 52% | 52점 |
| 편의점 | 20대(42%), 10대(18%), 30대(15%) = 75% | 10~30대 71% | 71점 |

> **설계 근거**: `estimated_sales` 테이블에 이미 연령대별 매출 컬럼(`sales_age_10`, `sales_age_20`, ...)이 있으므로 별도 메타데이터 불필요. 분기마다 자동 갱신되어 트렌드 변화도 반영됨.

## 5. 응답 형태

### 5.1 텍스트 분석

```
🔍 강남역 카페 분석 (2025년 4분기 기준)

강남역에 카페가 72개 있어서 경쟁이 꽤 치열합니다 (상권 내 점포 비율 13.8%).
점포당 월 평균 매출은 약 2,100만 원으로, 서울 카페 평균(1,800만 원)보다 높습니다.

매출은 점심시간(11~14시)에 집중되고, 20~30대 직장인이 주 고객층입니다.
이 상권의 유동인구 중 20~30대가 63%로, 카페 타겟과 잘 맞습니다.

다만, 최근 분기 카페 폐업이 5건 있었고 평균 영업 기간은 1.8년입니다.
진입 시 차별화 전략(스페셜티, 디저트 등)이 필요합니다.
```

### 5.2 인라인 차트 데이터

```typescript
interface IndustryAnalysisData {
  categoryName: string;
  competition: {
    storeCount: number;
    totalStores: number;
    ratio: number;          // 경쟁 밀집도 (%)
    seoulAvgRatio: number;  // 서울 평균 비교
  };
  sales: {
    monthlyAvg: number;     // 점포당 월 평균
    seoulAvg: number;       // 서울 평균
    byTimeSlot: { hour: number; ratio: number }[];  // 시간대별 비중
  };
  customerMatch: {
    score: number;          // 0~100 매칭 점수
    targetAgeGroup: string; // 주 소비 연령대
    districtAgeRatio: number; // 해당 연령대 유동인구 비율
  };
  survival: {
    avgDurationMonths: number; // 평균 영업 기간
    recentCloseCount: number;  // 최근 분기 폐업 수
  };
}
```

## 6. DB 쿼리

```sql
-- 업종별 점포 수 및 경쟁도
SELECT category_name, store_count, open_count, close_count
FROM stores
WHERE district_code = $1 AND category_code = $2 AND quarter = $3;

-- 업종별 추정 매출 (점포당)
SELECT monthly_sales, sales_count,
       monthly_sales / NULLIF(
         (SELECT store_count FROM stores
          WHERE district_code = $1 AND category_code = $2 AND quarter = $3), 0
       ) as per_store_sales
FROM estimated_sales
WHERE district_code = $1 AND category_code = $2 AND quarter = $3;

-- 서울 전체 평균 (비교용)
SELECT AVG(monthly_sales / NULLIF(s.store_count, 0)) as seoul_avg_per_store
FROM estimated_sales es
JOIN stores s ON es.district_code = s.district_code
  AND es.category_code = s.category_code AND es.quarter = s.quarter
WHERE es.category_code = $1 AND es.quarter = $2;
```

## 7. 수용 기준

- [ ] 업종 지정 질문 시 해당 업종의 심층 분석이 제공된다
- [ ] 경쟁 밀집도가 수치와 해석으로 표시된다
- [ ] 점포당 평균 매출이 서울 평균과 비교하여 표시된다
- [ ] 시간대별 매출 비중 차트가 표시된다
- [ ] 타겟 고객 매칭률이 계산되어 표시된다
- [ ] 업종 생존율/평균 영업 기간이 표시된다
- [ ] 자연어 업종 입력이 정확한 업종 코드로 매핑된다

---

*작성일: 2026-03-24*
