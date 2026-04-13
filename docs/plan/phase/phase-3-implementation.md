# Phase 3 구현 계획 — F06 히트맵 / F09 매출 시뮬레이션 / F10 PDF 리포트

> 작성일: 2026-04-05
> 상태: 계획 수립 완료, 구현 대기

## Context

Phase 1A(Mock E2E) + Phase 1B(Real Data) 완료. 1,650개 상권 + 실데이터 + PAE Agent 동작 중.
Phase 3는 Premium 전용 기능 3개를 추가하여 서비스 차별화를 완성하는 단계.

**핵심 발견사항**:
- `floating_population` 테이블에 `day_type` 컬럼 없음 → F06 히트맵은 평일/주말 구분 없이 MVP 구현
- `category_metadata`에 `default_unit_price` 컬럼 없음 → F09에 Alembic 마이그레이션 필요
- `deck.gl`, `@react-pdf/renderer`, `html2canvas` 미설치 → 각각 설치 필요

---

## 구현 순서

```
F09 (매출 시뮬레이션) → F06 (히트맵) → F10 (PDF 리포트)
```

- **F09 먼저**: 기존 Tool 패턴과 동일 (Repository→Tool→Agent→SSE→Card). 가장 낮은 위험도.
- **F06 다음**: 새로운 프론트엔드 인프라(deck.gl + Kakao Map 연동). REST API 엔드포인트 추가.
- **F10 마지막**: 기존 Card 데이터를 소비하므로 F09 Card가 있으면 더 풍부한 테스트 가능.

---

## F09. 매출 시뮬레이션

### 파이프라인

```
DB (estimated_sales + stores + category_metadata)
  → RealSimulationRepository (서울 전체 p25/p50/p75 산출)
  → simulate_revenue Tool (캐시 + 계산 로직)
  → PAE Actor (TOOL_CARD_MAP → "simulation" card)
  → SSE card 이벤트
  → SimulationCard.tsx (low/avg/high 바차트 + 서울 평균 비교)
```

### 수정/생성 파일

| Action | File | 내용 |
|--------|------|------|
| MODIFY | `server/server/models/category.py` | `default_unit_price: int \| None` 컬럼 추가 |
| CREATE | `server/alembic/versions/XXX_add_unit_price.py` | migration: `default_unit_price INTEGER` 추가 + major_category별 시드값 |
| MODIFY | `server/server/repositories/protocols.py` | `SimulationRepository` Protocol 추가 |
| CREATE | `server/server/repositories/mock/simulation.py` | Mock percentile 데이터 반환 |
| CREATE | `server/server/repositories/real/simulation.py` | SQL: 서울 전체 동일 업종 per-store 매출 분위수 |
| MODIFY | `server/server/repositories/data_access.py` | `simulation` 필드 추가 |
| MODIFY | `server/server/repositories/mock/factory.py` | MockSimulationRepository 생성 |
| MODIFY | `server/server/repositories/real/factory.py` | RealSimulationRepository 생성 |
| CREATE | `server/server/agent/tools/simulate_revenue.py` | Tool 함수 (cache→repo→계산→결과) |
| MODIFY | `server/server/agent/nodes/actor.py` | TOOL_REGISTRY, TOOL_CARD_MAP, TOOL_EMOJI 추가 |
| MODIFY | `server/server/agent/nodes/planner.py` | INTENT_PATTERNS에 `simulation` 추가, INTENT_TO_PLAN 추가 |
| MODIFY | `server/server/agent/graph.py` | ReAct용 `simulate_revenue_tool` wrapper + TOOLS 리스트 |
| MODIFY | `frontend/src/lib/types.ts` | `SimulationCardData` 인터페이스 |
| MODIFY | `frontend/src/lib/eventHandlers.ts` | TOOL_LABELS + CARD_LABELS 추가 |
| CREATE | `frontend/src/components/chat/cards/SimulationCard.tsx` | 카드 컴포넌트 |
| MODIFY | `frontend/src/components/chat/cards/registry.ts` | `simulation: SimulationCard` |

### 핵심 로직: `simulate_revenue` Tool

```python
async def simulate_revenue(district_code, category_code, unit_price=None, additional_competitors=0):
    # 1. 해당 상권+업종 매출/점포 데이터
    sales = await da.sales.get_estimated_sales(district_code, category_code)
    stores = await da.stores.get_store_info(district_code, category_code)
    
    # 2. 점포당 평균 = total_sales / store_count
    per_store_avg = total_sales / (store_count + additional_competitors)
    
    # 3. 서울 전체 동일 업종 분위수 (p25/p75)
    percentiles = await da.simulation.get_sales_percentiles(category_code)
    # sample_count < 10 → fallback ratio 0.6 / 1.5
    
    # 4. low = avg * p25_ratio, high = avg * p75_ratio
    # 5. unit_price 보정: price_ratio = user_price / default_price
    # 6. Seoul 평균 비교
```

### SimulationCard UI

- 그라디언트 헤더: `{상권명} {업종명} 매출 시뮬레이션`
- 3단 바: 하위(p25) / 평균 / 상위(p75) — Recharts BarChart
- 서울 평균 기준선 + 대비 %
- 산출 근거: 점포수, 총매출, 추가 경쟁점
- What-If 버튼: `[경쟁 2개 추가]` `[다른 업종]`
- Disclaimer 박스 + SourcesCitation

---

## F06. 시간대별 히트맵

### 파이프라인

```
DB (floating_population JOIN districts.center_point)
  → RealHeatmapRepository (PostGIS ST_Y/ST_X + SUM)
  → GET /api/map-data/heatmap/all (24시간 프리로드)
  → Frontend mapStore (heatmapData 캐시)
  → deck.gl HeatmapLayer (canvas overlay)
  → TimeSlider (0-23시 슬라이더 + 재생)
```

### 수정/생성 파일

| Action | File | 내용 |
|--------|------|------|
| MODIFY | `server/server/repositories/protocols.py` | `HeatmapRepository` Protocol |
| CREATE | `server/server/repositories/mock/heatmap.py` | Mock 히트맵 데이터 (5개 상권) |
| CREATE | `server/server/repositories/real/heatmap.py` | PostGIS 쿼리: center_point + population |
| MODIFY | `server/server/repositories/data_access.py` | `heatmap` 필드 추가 |
| MODIFY | `server/server/repositories/mock/factory.py` | MockHeatmapRepository 생성 |
| MODIFY | `server/server/repositories/real/factory.py` | RealHeatmapRepository 생성 |
| MODIFY | `server/server/api/routes/map_data.py` | `GET /heatmap`, `GET /heatmap/all` 엔드포인트 |
| MODIFY | `frontend/package.json` | `deck.gl`, `@deck.gl/core`, `@deck.gl/layers`, `@deck.gl/aggregation-layers` |
| MODIFY | `frontend/src/lib/api.ts` | `fetchHeatmapAll()` 함수 |
| MODIFY | `frontend/src/stores/mapStore.ts` | heatmapTimeSlot, heatmapPlaying, heatmapData 상태 |
| CREATE | `frontend/src/components/map/HeatmapLayer.tsx` | deck.gl HeatmapLayer + Kakao Map viewport 동기화 |
| CREATE | `frontend/src/components/map/TimeSlider.tsx` | 0-23시 슬라이더 + play/pause |
| MODIFY | `frontend/src/components/map/MapContainer.tsx` | HeatmapLayer + TimeSlider 통합 |
| MODIFY | `frontend/src/components/map/MapControls.tsx` | 히트맵 토글 버튼 |

### 핵심 설계 결정

**deck.gl + Kakao Map 동기화 방식**:
- `<canvas>` 를 Kakao Map 컨테이너 위에 absolute 배치
- Kakao Map `idle`, `zoom_changed`, `center_changed` 이벤트마다 deck.gl viewport 업데이트
- Kakao Map 좌표 → deck.gl WebMercator 좌표 변환

**day_type 없음 (MVP 결정)**:
- 현재 `floating_population` 테이블에 `day_type` 컬럼 없음 (UniqueConstraint: district_code, quarter, time_slot)
- MVP: 평일/주말 토글 비활성 또는 숨김, 전체 합계만 표시
- 향후: ETL에서 평일/주말 분리 적재 시 `day_type` 컬럼 추가 + 토글 활성화

**프리로드 전략**:
- `/heatmap/all` 한 번 호출 → 24시간분 전체 데이터 (~500KB) 클라이언트 캐시
- TimeSlider 변경 시 네트워크 요청 없이 로컬 데이터 교체 → 200ms 이내 응답

### deck.gl HeatmapLayer 설정

```typescript
{
  radiusPixels: 60,
  intensity: 1,
  threshold: 0.05,
  colorRange: [
    [1, 152, 189],    // 파랑
    [73, 227, 206],   // 시안
    [216, 254, 181],  // 연두
    [254, 237, 177],  // 노랑
    [254, 173, 84],   // 주황
    [209, 55, 78],    // 빨강
  ]
}
```

---

## F10. PDF 리포트 내보내기

### 파이프라인

```
chatStore (메시지 + Card 데이터) + districtStore (선택 상권)
  → useReportExport Hook (데이터 수집)
  → html2canvas (차트 캡처 → base64 PNG)
  → @react-pdf/renderer (PDF 문서 생성)
  → Blob → 다운로드 트리거
```

### 수정/생성 파일

| Action | File | 내용 |
|--------|------|------|
| MODIFY | `frontend/package.json` | `@react-pdf/renderer`, `html2canvas` |
| ADD | `frontend/public/fonts/NotoSansKR-Regular.ttf` | 한글 폰트 파일 |
| CREATE | `frontend/src/components/report/ReportDocument.tsx` | PDF 문서 컴포넌트 |
| CREATE | `frontend/src/hooks/useReportExport.ts` | PDF 생성 + 다운로드 Hook |
| MODIFY | `frontend/src/components/chat/ChatPanel.tsx` | PDF 내보내기 버튼 |
| MODIFY | `frontend/src/stores/chatStore.ts` | "PDF로 저장" 패턴 감지 → 클라이언트 PDF 트리거 |

### PDF 섹션 구성

1. **표지**: MarketScope AI, 상권명, 분석일, 데이터 기준 분기
2. **요약**: SummaryCardData 기반 (유동인구, 매출, 점포 현황)
3. **대화 이력**: 주요 Q&A (text 메시지만, 최대 20턴)
4. **차트**: html2canvas로 캡처한 InlineChart 이미지 (base64)
5. **면책**: "본 리포트는 카드매출 기반 추정치이며..."

### 트리거 방식

- **UI 버튼**: ChatPanel 상단에 PDF 아이콘 버튼 (대화 있을 때만 활성)
- **채팅 명령**: "PDF로 저장해줘", "리포트 만들어줘" → 클라이언트에서 감지하여 바로 생성
  - 서버에는 보내지 않고 로컬 처리 (서버 부하 없음)
  - 로컬 어시스턴트 메시지 추가: "PDF 리포트를 생성 중입니다..."

---

## 체크리스트

### F09 매출 시뮬레이션

**Backend**:
- [ ] `category_metadata` 모델에 `default_unit_price` 컬럼 추가
- [ ] Alembic 마이그레이션 생성 + major_category별 시드값 backfill
- [ ] `SimulationRepository` Protocol 정의
- [ ] `MockSimulationRepository` 구현
- [ ] `RealSimulationRepository` 구현 (서울 전체 p25/p50/p75 SQL)
- [ ] DataAccess + 양쪽 Factory 업데이트
- [ ] `simulate_revenue` Tool 구현 (cache + 계산 + fallback)
- [ ] actor.py: TOOL_REGISTRY/TOOL_CARD_MAP/TOOL_EMOJI 등록
- [ ] planner.py: INTENT_PATTERNS + INTENT_TO_PLAN 추가
- [ ] graph.py: ReAct용 tool wrapper + TOOLS 리스트 추가
- [ ] Mock 모드 동작 확인
- [ ] Real 모드 동작 확인

**Frontend**:
- [ ] `SimulationCardData` 인터페이스 (types.ts)
- [ ] TOOL_LABELS + CARD_LABELS 추가 (eventHandlers.ts)
- [ ] `SimulationCard.tsx` 컴포넌트 (low/avg/high 바 + 서울 평균 + disclaimer)
- [ ] `registry.ts`에 등록
- [ ] Card 다크 테마 스타일 확인
- [ ] `tsc --noEmit` + `npm run build` 통과

### F06 히트맵

**Backend**:
- [ ] `HeatmapRepository` Protocol 정의
- [ ] `MockHeatmapRepository` 구현 (5개 상권 × 24시간 합성 데이터)
- [ ] `RealHeatmapRepository` 구현 (PostGIS center_point + floating_population JOIN)
- [ ] DataAccess + 양쪽 Factory 업데이트
- [ ] `GET /api/map-data/heatmap?time_slot=N` 엔드포인트
- [ ] `GET /api/map-data/heatmap/all` 프리로드 엔드포인트
- [ ] Redis 캐시 (TTL 86400)
- [ ] Mock 모드 동작 확인
- [ ] Real 모드 동작 확인

**Frontend**:
- [ ] `deck.gl` 관련 패키지 설치
- [ ] `fetchHeatmapAll()` API 함수 (api.ts)
- [ ] mapStore에 heatmap 상태 추가 (timeSlot, playing, data)
- [ ] `HeatmapLayer.tsx` — deck.gl canvas + Kakao Map 뷰포트 동기화
- [ ] `TimeSlider.tsx` — 0-23시 슬라이더 + play/pause 애니메이션
- [ ] MapContainer.tsx에 HeatmapLayer + TimeSlider 통합
- [ ] MapControls.tsx에 히트맵 토글 버튼
- [ ] 슬라이더 응답 ≤ 200ms 확인 (프리로드 데이터)
- [ ] zoom/pan 시 히트맵 동기화 확인
- [ ] `tsc --noEmit` + `npm run build` 통과

### F10 PDF 리포트

**Frontend**:
- [ ] `@react-pdf/renderer` + `html2canvas` 설치
- [ ] 한글 폰트 파일 배치 (`public/fonts/NotoSansKR-Regular.ttf`)
- [ ] `ReportDocument.tsx` — 5개 섹션 (표지/요약/대화/차트/면책)
- [ ] Font.register()로 한글 폰트 등록
- [ ] `useReportExport.ts` Hook (데이터 수집 + 차트 캡처 + PDF 생성 + 다운로드)
- [ ] ChatPanel에 PDF 버튼 추가
- [ ] chatStore에서 "PDF로 저장" 패턴 감지
- [ ] 한글 렌더링 정상 확인
- [ ] PDF 생성 ≤ 5초 확인
- [ ] 대화 없을 때 graceful 처리
- [ ] `tsc --noEmit` + `npm run build` 통과

---

## Scenario Test 계획

모든 Scenario Test는 **독립 세션**에서 실행 (별도 Sub-Agent가 브라우저/API를 직접 테스트).

### F09 Scenario Tests

| ID | 시나리오 | 입력 | 기대 결과 | Pass 기준 |
|----|---------|------|----------|----------|
| S9-1 | 기본 시뮬레이션 | 강남역 선택 → "카페 열면 매출 얼마?" | SimulationCard 표시 | card에 low/avg/high 3개 숫자 존재 |
| S9-2 | 경쟁 추가 | "카페 2개 더 생기면?" | avg가 S9-1보다 낮음 | additional_competitors=2, avg 감소 |
| S9-3 | 업종 키워드 추출 | "홍대에서 한식 매출 예상" | 한식 카테고리 | card에 "한식" 표시 |
| S9-4 | 상권 미선택 | 상권 없이 "매출 시뮬레이션" | 상권 선택 안내 | 응답에 "상권" + "선택" 포함 |
| S9-5 | Disclaimer | 성공적 시뮬레이션 | 면책 문구 | "추정치" 또는 "실제와 다를" 포함 |
| S9-6 | 서울 평균 비교 | 성공적 시뮬레이션 | 서울 평균 대비 표시 | "서울" + "평균" 또는 "대비" 포함 |

**Backend 단위 테스트** (`server/tests/test_simulate_revenue.py`):

| ID | 테스트 | 기대 |
|----|-------|------|
| B9-1 | Mock 기본 호출 | low < avg < high |
| B9-2 | 경쟁 추가 | avg 감소 |
| B9-3 | 샘플 < 10 | reliable=False, fallback ratio 적용 |
| B9-4 | 캐시 히트 | 두 번째 호출 캐시 반환 |

### F06 Scenario Tests

| ID | 시나리오 | 입력 | 기대 결과 | Pass 기준 |
|----|---------|------|----------|----------|
| S6-1 | 히트맵 토글 ON | 히트맵 버튼 클릭 | canvas 요소 출현 | map 컨테이너 내 canvas 존재 |
| S6-2 | TimeSlider 표시 | 히트맵 ON 상태 | 슬라이더 표시 | range input (0-23) visible |
| S6-3 | 시간 변경 | 슬라이더 12→18 이동 | 히트맵 업데이트 | 네트워크 요청 없음 (프리로드) |
| S6-4 | 재생 애니메이션 | Play 버튼 | 시간 자동 증가 | 1초마다 값 변경 |
| S6-5 | 히트맵 OFF | 히트맵 버튼 재클릭 | canvas + slider 제거 | DOM에서 사라짐 |
| S6-6 | 슬라이더 성능 | 빠른 슬라이더 이동 | 200ms 이내 반응 | 눈에 띄는 지연 없음 |

**Backend 단위 테스트** (`server/tests/test_heatmap_api.py`):

| ID | 테스트 | 기대 |
|----|-------|------|
| B6-1 | `GET /heatmap?time_slot=12` | points 배열 + time_slot=12 |
| B6-2 | `GET /heatmap/all` | slots 객체 (0~23 키) |
| B6-3 | time_slot=25 (범위 초과) | 422 에러 |
| B6-4 | 캐시 동작 | 두 번째 호출 캐시 적중 |

### F10 Scenario Tests

| ID | 시나리오 | 입력 | 기대 결과 | Pass 기준 |
|----|---------|------|----------|----------|
| S10-1 | PDF 버튼 존재 | 대화 후 | PDF 버튼 visible | 다운로드 아이콘 버튼 존재 |
| S10-2 | PDF 다운로드 | PDF 버튼 클릭 | 파일 다운로드 | download 이벤트 발생 또는 blob 생성 |
| S10-3 | 채팅 트리거 | "PDF로 저장해줘" 입력 | PDF 생성 시작 | "PDF 리포트를 생성" 메시지 + 다운로드 |
| S10-4 | 한글 렌더링 | PDF 생성 | 한글 정상 표시 | blob 크기 > 10KB (폰트 포함) |
| S10-5 | 대화 없음 | 대화 없이 PDF 클릭 | 에러 또는 빈 PDF | 크래시 없음 |
| S10-6 | 생성 성능 | 전체 PDF 생성 | 5초 이내 | timestamp 차이 < 5000ms |

### 테스트 실행 방식

```
각 기능 구현 완료 후:
1. Backend pytest 실행 → 단위 테스트 통과 확인
2. tsc --noEmit + npm run build → 빌드 확인
3. 독립 Sub-Agent 세션에서 Scenario Test 실행
   - 서버 기동 상태에서 브라우저 시나리오 순차 실행
   - 각 시나리오별 PASS/FAIL 판정
4. FAIL 시나리오 → 원인 분석 → 수정 → 재테스트
5. 전체 PASS 시에만 해당 기능 완료 처리
```

---

## 리스크 및 완화

| 리스크 | 기능 | 영향 | 완화 |
|--------|------|------|------|
| deck.gl + Kakao Map 뷰포트 동기화 | F06 | 히트맵 위치 어긋남 | Fallback: canvas 직접 렌더링 (deck.gl 없이). 먼저 POC 테스트 |
| @react-pdf Korean 폰트 | F10 | 한글 깨짐 | 대안: jsPDF + html2canvas 풀페이지 캡처 |
| 히트맵 프리로드 데이터 크기 | F06 | 느린 초기 로딩 | GZIP 압축 + 로딩 인디케이터 |
| html2canvas 차트 캡처 실패 | F10 | PDF에 차트 누락 | recharts toDataURL 대안 + 차트 없이도 생성 가능하게 |
| Percentile 쿼리 성능 | F09 | 느린 응답 | category_code+quarter 인덱스 + Redis 캐시 (TTL 24h) |

---

## 검증 방법

### 각 기능별 완료 기준

1. **Backend**: `pytest server/tests/test_*.py` 전체 PASS
2. **Frontend**: `tsc --noEmit` 0 errors + `npm run build` 성공
3. **Scenario Test**: 독립 세션에서 모든 시나리오 PASS
4. **Mock 모드**: 기존 32/32 E2E 회귀 테스트 통과
5. **Real 모드**: 실데이터 기반 수동 QA 확인

### 전체 Phase 3 완료 기준

- F09 Scenario 6/6 PASS
- F06 Scenario 6/6 PASS
- F10 Scenario 6/6 PASS
- 기존 기능 회귀 없음 (Mock E2E 32/32 PASS)
- `docs/status/current-status.md` 업데이트
- `docs/spec/checklist.md` Phase 3 항목 체크
