# F05. 상권 비교 Spec

> 2~3개 상권을 나란히 비교하는 기능

---

## 1. 개요

| 항목 | 내용 |
|------|------|
| Phase | 2 (차별화) |
| 의존성 | F03 (기본 리포트 — Tool 재활용) |
| 진입점 | 챗봇 "A랑 B 비교해줘" 또는 지도 비교모드 |
| 최대 비교 수 | 3개 상권 |

## 2. 사용자 인터랙션

| 방식 | 흐름 |
|------|------|
| 챗봇 | "강남역이랑 홍대 비교해줘" → Agent가 상권코드 해석 → 비교 실행 |
| 지도 비교모드 | Toolbar [비교모드] ON → 상권 2~3개 클릭 → 자동 비교 실행 |

## 3. 비교 항목

| 항목 | 데이터 | Tool |
|------|--------|------|
| 유동인구 (일 평균) | 합계 | `get_floating_population` |
| 주 연령대 | 최빈 연령대 | `get_floating_population` |
| 총 점포 수 | 합계 | `get_store_info` |
| 총 매출 | 월 총 매출 | `get_estimated_sales` |
| 폐업률 | 폐업/전체 비율 | `get_store_info` |
| 상권 상태 | 성장/안정/침체 | `get_estimated_sales` |

## 4. Agent Tool: `compare_districts`

```python
@tool
def compare_districts(district_codes: list[str]) -> dict:
    """2~3개 상권의 주요 지표를 비교합니다."""
    results = {}
    for code in district_codes:
        fp = get_floating_population(code)
        stores = get_store_info(code)
        sales = get_estimated_sales(code)
        results[code] = {
            "name": get_district_name(code),
            "floating_pop": fp["daily_avg"],
            "main_age": max(fp["by_age"], key=fp["by_age"].get),
            "store_count": stores["total_stores"],
            "monthly_sales": sales["total_monthly_sales"],
            "close_rate": stores["close_rate"],
            "status": determine_status(sales["quarterly_sales"])
        }
    return results
```

## 5. CompareCard UI

```
┌────────────────────────────────────────────────────────┐
│ 📊 상권 비교: 강남역 vs 홍대입구                         │
│                                                        │
│           강남역          홍대입구        판정            │
│ ─────────────────────────────────────────────          │
│ 유동인구   12만/일        9.5만/일       강남역 ▲        │
│ 주 연령대  20~30대        20대           -              │
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

비교 실행 시 `map_cmd` 이벤트:
```json
{
  "action": "highlight_multiple",
  "params": {
    "districts": [
      {"code": "3110032", "color": "#3B82F6"},
      {"code": "3110045", "color": "#10B981"}
    ],
    "fit_bounds": true
  }
}
```
→ 두 상권이 모두 보이도록 지도 뷰포트 조정 + 각각 다른 색상 하이라이트

## 7. Frontend 상태

```typescript
// stores/districtStore.ts
interface DistrictStore {
  // ... 기존
  isCompareMode: boolean;
  compareList: District[];       // 최대 3개
  toggleCompareMode: () => void;
  addCompare: (district: District) => void;
  removeCompare: (code: string) => void;
  clearCompare: () => void;
}
```

## 8. 수용 기준

- [ ] 챗봇에서 "A랑 B 비교해줘" 입력 시 비교 카드가 생성된다
- [ ] 지도 비교모드에서 2~3개 상권 선택 시 자동 비교된다
- [ ] 비교표에 주요 지표가 정확하게 표시된다
- [ ] AI 종합 의견이 데이터 기반으로 생성된다
- [ ] 지도에 비교 상권이 각각 다른 색상으로 하이라이트된다
- [ ] 4개 이상 선택 시 "최대 3개" 안내가 표시된다

---

*작성일: 2026-03-24*
