# Plan: Card UI 연동 — 폴리곤 클릭 → AI 인식 → Card 렌더링

> 작성일: 2026-03-27
> Phase 1A 최종 검증 항목

## 최종 목표

**지도에서 폴리곤 클릭 → 클릭된 상권을 AI가 인식 → 채팅에 Card UI 생성**

이 목표가 달성될 때까지 Playwright MCP로 브라우저 테스트 → 버그 발견 → 수정 → 재테스트를 반복한다.

---

## Context

Phase 1A의 마지막 검증 항목. 현재 채팅으로 텍스트 질의 → AI 텍스트 응답은 동작하지만,
**폴리곤 클릭 → SummaryCard 렌더링**이 안 되는 이유는 백엔드에서 `summary` 타입의 card SSE 이벤트를 emit하지 않기 때문.

프론트엔드는 이미 완성됨 (DistrictLayer 클릭 → useMapSync 자동 질의 → useChat SSE 처리 → MessageBubble card 라우팅 → SummaryCard/CompareCard/RecommendCard/RiskCard 렌더링).

## 핵심 문제

`graph.py`의 `_TOOL_CARD_MAP`에 compare/recommend/risk만 있고, **summary가 없음**.
기존 요약 질의 시 Agent가 4개 개별 Tool을 호출하지만 이들은 card 이벤트를 생성하지 않음.

---

## 구현 계획

### Step 1: `get_district_summary` Tool 생성

**파일**: `server/server/agent/tools/district_summary.py` (신규)

Mock 데이터에서 유동인구/매출/점포 정보를 **집계**하여 `SummaryCardData` 형태로 반환.

**출력 형태** (프론트 `SummaryCardData` 인터페이스에 맞춤 — camelCase):
```python
{
    "districtName": "강남역",
    "districtType": "발달상권",
    "summary": "하루 평균 유동인구 12만 4천명, 월 추정 매출 85억원의 성장 중인 발달상권입니다.",
    "floatingPopulation": {
        "dailyAvg": 124350,
        "peakHour": 18,
        "byHour": [{"hour": 0, "pop": 8200}, {"hour": 1, "pop": 4100}, ...]
    },
    "topCategories": [
        {"name": "한식", "count": 245},
        {"name": "커피/음료", "count": 198}, ...
    ],
    "status": "growing",
    "closeRate": {"current": 5.3, "average": 6.5},
    "dataQuarter": "2025Q3"
}
```

**데이터 변환**:
- `FLOATING_POPULATION[code].by_hour` → `time_slot` → `hour`, `population` → `pop`
- `STORE_INFO[code].top_categories` → `category_name` → `name`, `store_count` → `count`
- `STORE_INFO[code].close_rate` → `{"current": close_rate, "average": 6.5}`
- `ESTIMATED_SALES[code].trend` → `status`
- `summary` 텍스트 자동 생성 (유동인구 + 매출 + 상권 타입)

### Step 2: `graph.py` 수정

**파일**: `server/server/agent/graph.py`

1. Tool wrapper 추가 (기존 패턴 동일):
```python
@tool
async def get_district_summary_tool(district_code: str) -> str:
    """상권의 종합 요약을 조회합니다. ..."""
```

2. `TOOLS` 리스트에 추가 (맨 앞)

3. `_TOOL_CARD_MAP`에 추가:
```python
"get_district_summary_tool": "summary",
```

### Step 3: 시스템 프롬프트 수정

**파일**: `server/server/agent/prompts/system.py`

- 도구 목록에 `get_district_summary` 추가
- 질문 유형별 가이드에서 **상권 요약 → `get_district_summary` 사용**으로 변경
  (기존: 4개 Tool 개별 호출 안내 → 변경: 1개 summary Tool 사용 안내)

### Step 4: Playwright MCP로 E2E 검증 (반복)

Playwright MCP 도구를 사용하여 브라우저에서 전체 흐름 검증.
**최종 목표 달성까지 테스트 → 디버깅 → 재테스트 반복.**

#### 검증 시나리오

1. **서버 기동**: frontend(3000) + backend(8000)
2. **브라우저 열기**: `browser_navigate` → `http://localhost:3000`
3. **지도 로딩 확인**: `browser_snapshot` → Kakao Map 렌더링 확인
4. **폴리곤 클릭 → SummaryCard**:
   - `browser_click` → 지도 위 상권 폴리곤 클릭
   - `browser_wait_for` → SummaryCard 렌더링 대기
   - `browser_snapshot` → SummaryCard 내용 확인 (districtName, 유동인구 차트 등)
5. **"홍대랑 비교해줘" → CompareCard**:
   - 채팅 입력 → CompareCard 렌더링 확인
6. **"뭐하면 좋을까?" → RecommendCard**:
   - 채팅 입력 → RecommendCard 렌더링 확인
7. **"이 자리 위험해?" → RiskCard**:
   - 채팅 입력 → RiskCard 렌더링 확인

#### 디버깅 루프

```
Playwright 테스트 실행
    │
    ├── PASS → 다음 시나리오로 이동
    │
    └── FAIL → 원인 분석
              ├── SSE 이벤트 미발송 → 백엔드 수정
              ├── Card 데이터 형태 불일치 → 변환 로직 수정
              ├── 프론트 렌더링 에러 → 컴포넌트 수정
              └── 재테스트 (다시 Playwright)
```

**4종 Card가 모두 정상 렌더링될 때까지 이 루프를 반복한다.**

---

## 변경 파일 요약

| 파일 | 변경 | 설명 |
|------|------|------|
| `server/server/agent/tools/district_summary.py` | **신규** | Mock 데이터 집계 → SummaryCardData 형태 반환 |
| `server/server/agent/graph.py` | 수정 | Tool wrapper + TOOLS 등록 + _TOOL_CARD_MAP 추가 |
| `server/server/agent/prompts/system.py` | 수정 | 도구 목록 + 요약 질의 가이드 변경 |

**프론트엔드 변경 없음** — 이미 SummaryCard 렌더링 로직이 완성되어 있음.
(단, Playwright 디버깅 과정에서 프론트 버그 발견 시 수정 가능)

## 완료 기준

- [ ] 폴리곤 클릭 → SummaryCard 렌더링 (Playwright 스크린샷 확인)
- [ ] "홍대랑 비교해줘" → CompareCard 렌더링
- [ ] "뭐하면 좋을까?" → RecommendCard 렌더링
- [ ] "이 자리 위험해?" → RiskCard 렌더링
- [ ] 4종 Card 모두 Playwright E2E 통과
