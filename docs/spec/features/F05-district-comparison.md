# F05. 상권 비교 Spec

> 2~3개 상권을 나란히 비교하는 기능

---

## 1. 개요

| 항목 | 내용 |
|------|------|
| Phase | 1A(Mock) · 1B(Real) — **완료** (Phase 2 에서 Premium 게이팅 예정) |
| 의존성 | F03 (기본 리포트 — 데이터 레이어 재활용) |
| 진입점 | 챗봇 "A랑 B 비교해줘" 또는 지도 비교모드 |
| 최대 비교 수 | 3개 상권 |

## 2. 사용자 인터랙션

| 방식 | 흐름 |
|------|------|
| 챗봇 | "강남역이랑 홍대 비교해줘" → Agent가 상권코드 해석 → `compare_districts` 실행 → CompareCard |
| 지도 비교모드 | Toolbar [비교모드] ON → 상권 2~3개 클릭 → `compareList` 등록 + 다색 하이라이트 (비교 분석 자체는 챗 질문으로 실행 — 자동 실행 아님) |

역방향 동기화: 챗에서 compare 카드가 도착하면 프론트가 `compareList` 를 카드 상권들로 자동 동기화한다 (`lib/eventHandlers.ts` card 핸들러).

## 3. 비교 항목

전 항목을 `compare_districts` Tool 하나가 repository 에서 직접 SQL 집계한다 — 개별 Tool(`get_floating_population` 등)을 재호출하지 않는다 (`repositories/real/comparison.py`).

| 항목 | 데이터 | 반환 키 |
|------|--------|---------|
| 유동인구 (**분기 합계**) | 분기 시간대별 `SUM(total_pop)` — '일 평균' 아님 | `floating_pop` |
| 주 연령대 | 최빈 연령대 | `main_age` |
| 총 점포 수 | `store_count` 합계 | `store_count` |
| 월 매출 | 분기 누적 → `// MONTHS_PER_QUARTER` 월 환산 | `monthly_sales` |
| 폐업률 | 폐업/전체 비율 (%) | `close_rate` |
| 상권 상태 | 매출 QoQ ±5% 기준 성장/안정/침체 | `status` |

## 4. Agent Tool: `compare_districts` (`server/server/agent/tools/compare_districts.py`)

```python
@register_tool("compare_districts", card_type="compare",
               progress_label="상권 비교 분석 중...", done_label="상권 비교 완료")
async def compare_districts(district_codes: list[str]) -> dict:
    """2~3개 상권만 허용. 캐시(`compare:{정렬된 코드 _ 조인}`, 24h) → repo SQL 집계 → _enrich_comparison."""
```

**반환 형상** (`repositories/real/comparison.py` + 툴 레이어 `_enrich_comparison`):
```json
{
  "districts": {
    "3110032": {
      "district_code": "3110032",
      "district_name": "강남역",
      "floating_pop": 4106209,
      "main_age": "20대",
      "store_count": 523,
      "close_rate": 5.4,
      "monthly_sales": 15200000000,
      "status": "growing",
      "quarter": "2025Q4",
      "sales_per_store": 29063097,
      "pop_per_store": 7851
    }, ...
  },
  "district_codes": ["3110032", "3110045"],
  "winners": {"highest_pop": "...", "highest_sales": "...", "lowest_close_rate": "...", "best_efficiency": "..."}
}
```

> `floating_pop` 은 분기 시간대 합계(`SUM(total_pop)`)다. respond/loop 프롬프트가 이를 '하루 평균'으로 부르는 것을 금지한다. card_type 은 **`compare`** ("comparison" 아님).

## 5. CompareCard UI

```
┌────────────────────────────────────────────────────────┐
│ 📊 상권 비교: 강남역 vs 홍대입구                         │
│                                                        │
│           강남역          홍대입구        판정            │
│ ─────────────────────────────────────────────          │
│ 유동인구   411만/분기     306만/분기     강남역 ▲        │
│ 주 연령대  20대           20대           -              │
│ 점포 수    523개          412개          -              │
│ 월 매출    152억          98억           강남역 ▲        │
│ 폐업률     5.4%           6.1%          강남역 ▲        │
│ 상태       🟢 성장        🟡 안정        -              │
│                                                        │
│ 💬 AI 종합 의견                                         │
│ 강남역이 유동인구와 매출 모두 높지만, 경쟁이 더             │
│ 치열합니다. 홍대는 20대 타겟 업종에 유리하고               │
│ 진입 비용이 상대적으로 낮습니다.                          │
├────────────────────────────────────────────────────────┤
│ [강남역 자세히 보기] [홍대 자세히 보기]                    │
└────────────────────────────────────────────────────────┘
```

## 6. 지도 연동

다중 하이라이트는 `map_cmd` 이벤트가 아니라 **프론트 상태 동기화**로 구현돼 있다:

1. compare 카드 SSE 수신 → `lib/eventHandlers.ts` card 핸들러가 카드의 상권들로 `districtStore.compareList` 를 자동 동기화 (최대 3)
2. `DistrictLayer.tsx` 가 `compareList` 슬롯 순서(0/1/2)별 색상(파랑/주황/핑크, `COMPARE_STYLES`)으로 폴리곤 하이라이트

> `map_cmd` 는 백엔드 `api/routes/chat.py` 가 **단일 상권 `{action: "move"}` 용도로만** 방출한다 — `highlight_multiple` 액션은 존재하지 않는다. Agent(v2/PAE) 노드는 map_cmd 를 방출하지 않는다.

## 7. Frontend 상태

```typescript
// stores/districtStore.ts (실제 시그니처)
interface DistrictState {
  selected: District | null;
  selectSource: 'map' | 'chat' | null;   // selected 와 별도 최상위 필드
  isCompareMode: boolean;
  compareList: District[];               // 최대 3개 — 초과 시 toastStore warning 후 거부
  hoveredCode: string | null;
  toggleCompareMode: () => void;
  addToCompare: (district: District) => void;
  removeFromCompare: (code: string) => void;
  clearCompare: () => void;
}
```

## 8. 수용 기준

- [x] 챗봇에서 "A랑 B 비교해줘" → CompareCard 생성 (v2 루프: LLM 이 `compare_districts` 직접 호출 / PAE legacy: Planner comparison intent)
- [x] 지도 비교모드에서 2~3개 상권 다중 선택 + 다색 하이라이트 (비교 분석 실행은 챗 질문으로 — 자동 실행 없음)
- [x] 비교표에 주요 지표 정확 표시 (유동인구는 분기 합계 기준)
- [x] AI 종합 의견 데이터 기반 생성
- [x] 비교 상권이 각각 다른 색상(파랑/주황/핑크 — `COMPARE_STYLES`)으로 지도 하이라이트 — 2026-04-17 `DistrictLayer.tsx` 수정
- [x] 최대 3개 제한 (`compareList` in `districtStore`, 초과 시 toast 경고)

---

*Phase 1A(Mock) · 1B(Real) 완료*
