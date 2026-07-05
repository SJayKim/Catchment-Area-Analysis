# F03. 상권 기본 리포트 Spec

> 사용자가 프리뷰(F13)에서 분석을 요청하면 생성되는 상권 요약 카드

---

## 1. 개요

| 항목 | 내용 |
|------|------|
| Phase | 1 (MVP) |
| 의존성 | F02 (AI 챗봇) |
| 트리거 | 상권 선택 → Zero-LLM 프리뷰(F13) 노출 → 사용자가 chip / "AI 분석 보기" 클릭 시 생성 (2026-04-23 이후 자동 챗 전송 없음) |
| 출력 | SummaryCard (채팅 패널에 표시) |

## 2. 리포트 구성 항목

| 항목 | 데이터 | Tool | 표현 방식 |
|------|--------|------|-----------|
| 상권 한줄 요약 | 코드 템플릿(f-string) 생성 — LLM 아님 | `get_district_summary` 조립부 | 텍스트 |
| 유동인구 | **분기 시간대 합계**(`quarter_total`), 피크 시간대 | `get_floating_population` | 숫자 + 미니 바차트 |
| 주요 업종 Top 5 | 점포 수 기준 상위 업종 | `get_store_info` | 리스트 |
| 상권 상태 | 매출 QoQ 추이 기반 | `get_estimated_sales` | 뱃지 (성장/안정/침체) |
| 개폐업률 | 최근 분기 개업·폐업 수 | `get_store_info` | 숫자 + 비교 텍스트 |
| 파생 인사이트 | 성비/주연령/점포당매출/프랜차이즈비율/주말상승률/QoQ | 조립부 `insights` 블록 | LLM 컨텍스트 |
| 유형 내 백분위 | 동일 상권유형 내 순위 (`benchmarks`) | `get_district_benchmarks` (내부 헬퍼) | 카드 하단 |

> ⚠ **상주/직장인구는 SummaryCard 에 포함되지 않는다.** `get_district_summary` 는 `get_population_info` 를 호출하지 않으며 (`agent/tools/district_summary.py` — import 자체가 없음), 결과 dict 에도 resident/worker 필드가 없다. 인구 특성 질문 시 Agent 가 `get_population_info` 를 별도 Tool 로 호출한다 (§4.4).

## 3. Tool 집계 구조

`get_district_summary` (`server/server/agent/tools/district_summary.py`) 가 내부에서 집계한다:

```
1. get_floating_population(district_code)          ─┐
2. get_estimated_sales(district_code)               ├─ asyncio.gather 4개 병렬
3. get_store_info(district_code)                    │
4. da.districts.get_district_meta(district_code)   ─┘  ← repo 직접 호출 (등록 Tool 아님)

5. get_district_benchmarks(...)   ← gather 이후 순차 (동일 유형 백분위, 내부 헬퍼)
6. 요약 문장 = 코드 템플릿: "분기 유동인구 X, 월 추정 매출 Y의 {상태} {유형}입니다."
```

> `get_population_info` 는 이 병렬 집계에 **포함되지 않는다** (4개 병렬 = fp / sales / store / district_meta).

## 4. Tool 구현 상세

### 4.1 `get_floating_population` (`server/server/agent/tools/floating_population.py`)

```python
@register_tool("get_floating_population", progress_label="유동인구 데이터 조회 중...", done_label="유동인구 조회 완료")
async def get_floating_population(district_code: str, quarter: str | None = None) -> dict:
    """캐시(`fp:{code}:{quarter|latest}`, 24h) 확인 후 repository 위임."""
```

**반환 예시** (`repositories/real/floating_population.py`):
```json
{
  "district_code": "3110032",
  "quarter": "2025Q4",
  "quarter_total": 4106209,
  "peak_hour": 12,
  "by_hour": [{"time_slot": 0, "population": 21000}, ...],
  "gender": {"male_ratio": 52.0, "female_ratio": 48.0},
  "age_distribution": {"10대": 4.1, "20대": 35.2, "30대": 28.0, ...}
}
```

> ⚠ `quarter_total` 은 **해당 분기의 시간대별 합계 총량**이다 — '일 평균'이 아니며, respond/loop 프롬프트가 일수 분할·'일평균' 라벨을 명시적으로 금지한다 (`agent/nodes/respond.py` · `agent/loop/prompts.py`). `daily_avg` 는 2026-07-04 rename 이전 legacy 키로, Redis 구버전 캐시 방어용 매처(`numeric_sanity.py` 등)와 프론트 fallback 에만 잔존한다. 요일별(weekday/weekend) 유동인구 분해는 반환하지 않는다.

### 4.2 `get_store_info` (`server/server/agent/tools/store_info.py`)

```python
@register_tool("get_store_info", progress_label="점포 현황 조회 중...", done_label="점포 현황 조회 완료")
async def get_store_info(district_code: str, category_code: str | None = None) -> dict:
    """캐시(`store:{code}:{category|all}`, 24h) 확인 후 repository 위임."""
```

**반환 예시** (`repositories/real/stores.py::get_store_info`):
```json
{
  "district_code": "3110032",
  "quarter": "2025Q4",
  "total_stores": 523,
  "open_count": 32,
  "close_count": 28,
  "close_rate": 5.4,
  "franchise_count": 61,
  "top_categories": [
    {"category_code": "CS200001", "category_name": "한식음식점", "store_count": 89, "open_count": 4, "close_count": 3},
    ...
  ]
}
```

> `avg_close_rate` 는 반환하지 않는다 — 서울 평균 폐업률 비교는 카드 조립부(`closeRate.average`)와 `benchmarks` 블록이 담당.

### 4.3 `get_estimated_sales` (`server/server/agent/tools/estimated_sales.py`)

```python
@register_tool("get_estimated_sales", progress_label="매출 데이터 조회 중...", done_label="매출 조회 완료")
async def get_estimated_sales(district_code: str, category_code: str | None = None) -> dict:
    """캐시(`sales:{code}:{category|all}`, 24h) → repository → `_enrich_sales` 파생 지표 추가."""
```

**반환 예시** (`repositories/real/estimated_sales.py` + 툴 레이어 `_enrich_sales`):
```json
{
  "district_code": "3110032",
  "quarter": "2025Q4",
  "total_monthly_sales": 15200000000,
  "total_sales_count": 1820000,
  "weekday_sales": 11400000000,
  "weekend_sales": 3800000000,
  "gender_sales": {"male": 8200000000, "female": 7000000000},
  "age_sales": {"20대": 5300000000, ...},
  "time_sales": {"11~14시": 4600000000, ...},
  "trend": "growing",
  "quarterly_sales": [
    {"quarter": "2025Q1", "monthly_sales": 13800000000},
    {"quarter": "2025Q4", "monthly_sales": 15200000000}
  ],
  "computed": {
    "avg_transaction": 8350, "weekend_share_pct": 25.0, "weekend_uplift_pct": -66.7,
    "qoq_growth_pct": 2.7, "peak_daypart": {"slot": "11~14시", "share_pct": 30.3},
    "dominant_age": {"group": "20대", "share_pct": 34.9}
  }
}
```

> 모든 매출 값은 DB 분기 누적을 `// MONTHS_PER_QUARTER`(=3) 로 **월 환산**한 값. `quarterly_sales` 항목 키는 `monthly_sales` (`sales` 아님). `computed` 블록은 툴 레이어 파생(LLM 컨텍스트용, 카드 미발행).

### 4.4 `get_population_info` (`server/server/agent/tools/population_info.py`)

> SummaryCard 집계에는 포함되지 않음 — 인구 특성 질문 시 Agent 가 개별 호출하는 Tool (카드 미발행).

```python
@register_tool("get_population_info", progress_label="인구 데이터 조회 중...", done_label="인구 조회 완료")
async def get_population_info(district_code: str) -> dict:
    """캐시(`pop:{code}`, 24h) 확인 후 repository 위임."""
```

**반환 예시** (`repositories/real/population.py`):
```json
{
  "district_code": "3110032",
  "quarter": "2025Q4",
  "resident": {
    "total": 15200,
    "age_distribution": {"20": 3300, "30": 4200, ...},
    "gender": {"male": 7400, "female": 7800, "male_ratio": 48.7, "female_ratio": 51.3}
  },
  "worker": {
    "total": 85000,
    "age_distribution": {"20": 29800, "30": 25500, ...},
    "gender": {"male": 44200, "female": 40800, "male_ratio": 52.0, "female_ratio": 48.0}
  }
}
```

## 5. SummaryCard 데이터 구조

`frontend/src/lib/types.ts::SummaryCardData` (2026-07-04 `dailyAvg` → `quarterTotal` rename 반영):

```typescript
interface SummaryCardData {
  districtName: string;
  districtType: string;
  summary: string;              // 코드 템플릿 생성 한줄 요약 (LLM 아님)
  floatingPopulation: {
    quarterTotal: number;       // 분기 시간대 합계 — '일 평균' 아님
    /** @deprecated rename 이전(2026-07-04) Redis 캐시 payload 하위호환 */
    dailyAvg?: number;
    peakHour: number;
    byHour: { hour: number; pop: number }[];
  };
  topCategories: { name: string; count: number }[];
  status: 'growing' | 'stable' | 'declining';
  closeRate: { current: number; average: number };
  dataQuarter: string;
  dataSources?: DataSourceInfo[];
}
```

> 백엔드 카드 payload 에는 이 외에 `monthlySales` / `insights` / `benchmarks` 키가 추가로 실린다 (`district_summary.py` 결과 dict).

## 6. SummaryCard UI (`components/chat/cards/SummaryCard.tsx`)

```
┌─────────────────────────────────────────┐
│ 📍 강남역 상권 요약                      │
│                                         │
│ 분기 유동인구 410만 6천명,               │
│ 월 추정 매출 152억원의                   │
│ 성장 중인 발달상권입니다.                 │
│                                         │
│ 유동인구  분기 합계 4,106,209명 (피크: 12시)│
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

`repositories/real/estimated_sales.py` trend 산출부에 인라인 구현 (등가 로직):

```python
def determine_status(quarterly_sales: list) -> str:
    """최근 분기 매출 QoQ 로 상권 상태 판정"""
    if len(quarterly_sales) < 2:
        return "stable"

    recent = quarterly_sales[-1]["monthly_sales"]
    previous = quarterly_sales[-2]["monthly_sales"]
    change_rate = (recent - previous) / previous

    if change_rate > 0.05:
        return "growing"
    elif change_rate < -0.05:
        return "declining"
    else:
        return "stable"
```

## 8. 캐싱 전략

- Redis 키: `summary:{district_code}` — **quarter 미포함** (`district_summary.py`). `report:*` 키는 존재하지 않는다.
- TTL: 24시간 (86400s)
- 개별 Tool 도 자체 키로 캐시: `fp:{code}:{quarter|latest}` / `sales:{code}:{category|all}` / `store:{code}:{category|all}` / `pop:{code}`
- 동일 상권 재요청 시 캐시에서 즉시 반환. quarter 가 키에 없으므로 **분기 갱신·데이터 fix 배포 시 `server/scripts/flush_cache.py` 필수** (DEFAULT_PREFIXES 에 `summary:` 포함)

## 9. 수용 기준

- [x] 상권 선택 시 Zero-LLM 프리뷰(F13)가 표시되고, chip / "AI 분석 보기" 클릭 시 요약 카드가 생성된다 (`useMapSync` 는 자동 챗 전송 없이 `setPreview` 만 호출)
- [x] 유동인구(분기 합계 라벨), 업종, 매출, 개폐업률이 정확하게 표시된다
- [x] 시간대별 미니 차트가 렌더링된다 (Recharts `InlineChart`)
- [x] 상권 상태 뱃지가 표시된다
- [x] 데이터 기준 분기가 명시된다 (Mock 은 `"2025Q4 (샘플)"`)
- [x] 추천 질문 칩이 표시된다 (v2 루프: engine `_proactive_suggestions` / PAE legacy: Evaluator suggestion)
- [x] 진행 이벤트(thinking/tool)가 즉시 표시된다 — 현행 v2 루프는 Trust Kernel 검증-후-방출이라 본문은 토큰 스트리밍이 아닌 90자 청크 일괄 방출 (토큰 스트리밍 재설계는 deferred)
- [x] Redis 캐시 hit 시 즉시 반환 (TTL 24h)

> ⚠ 매출 단위: Repository 가 분기→월 환산 후 반환. 프롬프트 예시 수치도 월 단위 기준.
