# F03. 상권 기본 리포트 Spec

> 상권 선택 시 AI가 자동 생성하는 요약 카드

---

## 1. 개요

| 항목 | 내용 |
|------|------|
| Phase | 1 (MVP) |
| 의존성 | F02 (AI 챗봇) |
| 트리거 | 상권 선택 시 자동 생성 |
| 출력 | SummaryCard (채팅 패널에 표시) |

## 2. 리포트 구성 항목

| 항목 | 데이터 | Tool | 표현 방식 |
|------|--------|------|-----------|
| 상권 한줄 요약 | LLM 생성 | - | 텍스트 |
| 유동인구 | 일 평균, 피크 시간대 | `get_floating_population` | 숫자 + 미니 바차트 |
| 주요 업종 Top 5 | 점포 수 기준 상위 업종 | `get_store_info` | 리스트 |
| 상권 상태 | 매출/점포수 추이 기반 | `get_estimated_sales` | 뱃지 (성장/안정/침체) |
| 개폐업률 | 최근 분기 개업·폐업 수 | `get_store_info` | 숫자 + 비교 텍스트 |
| 상주/직장인구 | 인구 특성 요약 | `get_population_info` | 텍스트 |

## 3. Agent Tool 호출 순서

상권 선택 시 Agent는 다음 Tool을 순차/병렬 호출:

```
1. get_floating_population(district_code, latest_quarter)  ─┐
2. get_store_info(district_code, category_code=null)        ├─ 병렬 호출
3. get_estimated_sales(district_code, category_code=null)   │
4. get_population_info(district_code)                       ─┘

5. LLM이 결과 종합하여 요약 텍스트 + SummaryCard 데이터 생성
```

## 4. Tool 구현 상세

### 4.1 `get_floating_population` (`server/agent/tools/floating_population.py`)

```python
@tool
def get_floating_population(district_code: str, quarter: str = None) -> dict:
    """상권의 유동인구 데이터를 조회합니다."""
    # DB 쿼리
    # 반환: 시간대별, 요일별, 연령별, 성별 유동인구
```

**반환 예시:**
```json
{
  "daily_avg": 120000,
  "peak_hour": 12,
  "peak_population": 18000,
  "weekday_avg": 135000,
  "weekend_avg": 95000,
  "by_age": {"20s": 35, "30s": 28, "40s": 18, ...},
  "by_gender": {"M": 52, "F": 48},
  "by_hour": [{"hour": 0, "pop": 2000}, ...],
  "quarter": "2025Q4"
}
```

### 4.2 `get_store_info` (`server/agent/tools/store_info.py`)

```python
@tool
def get_store_info(district_code: str, category_code: str = None) -> dict:
    """상권의 점포 현황 및 개폐업 정보를 조회합니다."""
```

**반환 예시:**
```json
{
  "total_stores": 523,
  "open_count": 32,
  "close_count": 28,
  "close_rate": 5.4,
  "avg_close_rate": 5.8,
  "top_categories": [
    {"name": "한식", "count": 89},
    {"name": "카페", "count": 72},
    {"name": "편의점", "count": 45},
    {"name": "미용실", "count": 38},
    {"name": "주점", "count": 31}
  ],
  "quarter": "2025Q4"
}
```

### 4.3 `get_estimated_sales` (`server/agent/tools/estimated_sales.py`)

```python
@tool
def get_estimated_sales(district_code: str, category_code: str = None) -> dict:
    """상권의 추정 매출 데이터를 조회합니다."""
```

**반환 예시:**
```json
{
  "total_monthly_sales": 15200000000,
  "trend": "growing",  // growing/stable/declining
  "quarterly_sales": [
    {"quarter": "2025Q1", "sales": 13800000000},
    {"quarter": "2025Q2", "sales": 14200000000},
    {"quarter": "2025Q3", "sales": 14800000000},
    {"quarter": "2025Q4", "sales": 15200000000}
  ],
  "quarter": "2025Q4"
}
```

### 4.4 `get_population_info` (`server/agent/tools/population_info.py`)

```python
@tool
def get_population_info(district_code: str) -> dict:
    """상권의 상주인구 및 직장인구 데이터를 조회합니다."""
```

**반환 예시:**
```json
{
  "resident": 15200,
  "worker": 85000,
  "resident_by_age": {"20s": 22, "30s": 28, ...},
  "worker_by_age": {"20s": 35, "30s": 30, ...},
  "quarter": "2025Q4"
}
```

## 5. SummaryCard 데이터 구조

```typescript
interface SummaryCardData {
  districtName: string;
  districtType: string;
  summary: string;              // AI 생성 한줄 요약
  floatingPopulation: {
    dailyAvg: number;
    peakHour: number;
    byHour: { hour: number; pop: number }[];
  };
  topCategories: { name: string; count: number }[];
  status: 'growing' | 'stable' | 'declining';
  closeRate: { current: number; average: number };
  dataQuarter: string;
}
```

## 6. SummaryCard UI (`components/chat/cards/SummaryCard.tsx`)

```
┌─────────────────────────────────────────┐
│ 📍 강남역 상권 요약                      │
│                                         │
│ 하루 평균 유동인구 12만 명으로            │
│ 서울 상위 3% 상권입니다.                  │
│ 20~30대 직장인이 70%를 차지하며,          │
│ 점심(11~13시)에 가장 붐빕니다.            │
│                                         │
│ ┌─ 시간대별 유동인구 ──────────────┐     │
│ │ ▁▂▃▅▇█▇▅▃▂▁▁▂▃▅▇▆▄▃▂▁        │     │
│ │ 0  3  6  9  12 15 18 21        │     │
│ └─────────────────────────────────┘     │
│                                         │
│ 주요 업종: 한식(89) 카페(72) 편의점(45)  │
│                                         │
│ 상권 상태: 🟢 성장 중                    │
│ 폐업률: 5.4% (평균 5.8% 대비 양호)      │
│                                         │
│ 데이터 기준: 2025년 4분기                │
├─────────────────────────────────────────┤
│ 💡 궁금한 점을 물어보세요!               │
│ [여기서 뭐하면 좋을까?] [카페 분석해줘]    │
└─────────────────────────────────────────┘
```

## 7. 상권 상태 판정 로직

```python
def determine_status(quarterly_sales: list) -> str:
    """최근 4분기 매출 추이로 상권 상태 판정"""
    if len(quarterly_sales) < 2:
        return "stable"

    recent = quarterly_sales[-1]["sales"]
    previous = quarterly_sales[-2]["sales"]
    change_rate = (recent - previous) / previous

    if change_rate > 0.05:
        return "growing"
    elif change_rate < -0.05:
        return "declining"
    else:
        return "stable"
```

## 8. 캐싱 전략

- Redis 키: `report:{district_code}:{quarter}`
- TTL: 24시간
- 동일 상권 재선택 시 캐시에서 즉시 반환

## 9. 수용 기준

- [x] 상권 선택 시 자동으로 요약 카드가 생성된다 (`useMapSync`)
- [x] 유동인구, 업종, 매출, 개폐업률이 정확하게 표시된다
- [x] 시간대별 미니 차트가 렌더링된다 (Recharts `InlineChart`)
- [x] 상권 상태 뱃지가 표시된다
- [x] 데이터 기준 분기가 명시된다 (Mock 은 `"2025Q4 (샘플)"`)
- [x] 추천 질문 칩이 Evaluator suggestion 으로 표시된다
- [x] 첫 토큰 3초 이내 (Gemini 스트리밍)
- [x] Redis 캐시 hit 시 즉시 반환 (TTL 24h)

> ⚠ 매출 단위: Repository 가 분기→월 환산 후 반환. 프롬프트 예시 수치도 월 단위 기준.
