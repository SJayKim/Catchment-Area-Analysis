# F06. 시간대별 히트맵 Spec

> 지도 위에 시간대별 유동인구 밀도를 히트맵으로 시각화

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| Phase | 3 — **완료** (Phase 2 Tier 게이팅 대기) |
| Tier | **Premium** (현재 게이팅 없음) |
| 의존성 | F01 (지도) |
| 기술 | deck.gl 9.2 HeatmapLayer |
| API | `GET /api/map-data/heatmap?time_slot` + `/heatmap/all` 프리로드 |
| 용도 | 영업시간 결정, 피크 타임 시각적 확인 |

> 현재 `floating_population` 에 `day_type` 컬럼이 없어 **평일/주말 구분은 미지원** — MVP 는 전체 평균.

## 2. 사용자 인터랙션

| 조작 | 설명 |
|------|------|
| 시간 슬라이더 | 0시~23시 드래그/클릭, 현재 시간 히트맵 표시 |
| 평일/주말 토글 | **미구현** — `floating_population` 에 `day_type` 컬럼이 없어 API/UI 모두 부재 (Phase 2 후보) |
| 레이어 토글 | Toolbar [히트맵] 버튼 ON/OFF |
| 애니메이션 | 재생 버튼 → 0시~23시 자동 재생 (1초/시간) |

## 3. 데이터 구조

### 3.1 히트맵 API

```
GET /api/map-data/heatmap?time_slot={0-23}[&quarter={YYYYQN}]
```

**Response** (`server/server/api/routes/map_data.py::get_heatmap` + `repositories/real/heatmap.py`):
```json
{
  "time_slot": 12,
  "quarter": "2025Q4",
  "points": [
    {"lat": 37.4979, "lng": 127.0276, "weight": 18000},
    {"lat": 37.5563, "lng": 126.9237, "weight": 12500},
    ...
  ]
}
```

- `time_slot` 필수(0~23), `quarter` 생략 시 최신 분기. Redis 캐시 `heatmap:{time_slot}:{quarter|latest}` TTL 24h + singleflight
- `day_type` 파라미터/응답 필드는 **설계만 존재, 미구현** (§1 주석 참조 — 요청/응답 어디에도 없음)
- `weight`: 해당 상권 중심점의 유동인구 수 (`total_pop` 합계)
- 포인트 수 = `center_point` 보유 상권 전체 — 서울 1,650개 상권 규모

### 3.2 DB 쿼리

```sql
SELECT ST_Y(d.center_point) as lat,
       ST_X(d.center_point) as lng,
       SUM(fp.total_pop) as weight
FROM floating_population fp
JOIN districts d ON fp.district_code = d.district_code
WHERE fp.quarter = $1
  AND fp.time_slot = $2
  AND d.center_point IS NOT NULL
GROUP BY d.center_point;
```

## 4. Frontend 구현

### 4.1 HeatmapLayer (`components/map/HeatmapLayer.tsx`)

```typescript
import { HeatmapLayer } from '@deck.gl/aggregation-layers';

const heatmapLayer = new HeatmapLayer({
  data: points,
  getPosition: d => [d.lng, d.lat],
  getWeight: d => d.weight,
  radiusPixels: 60, // 모바일 breakpoint 는 40 (INP 개선)
  intensity: 1,
  threshold: 0.05,
  colorRange: [
    [1, 152, 189],    // 낮음: 파랑
    [73, 227, 206],
    [216, 254, 181],
    [254, 237, 177],
    [254, 173, 84],
    [209, 55, 78]     // 높음: 빨강
  ]
});
```

### 4.2 TimeSlider (`components/map/TimeSlider.tsx`)

```
┌─ 시간대 슬라이더 ─────────────────────────────────────┐
│ ▶  ◀ 06  08  10  12  14  16  18  20  22 ▶           │
│         ────────●──────────────                       │
│                                        현재: 12시      │
└─────────────────────────────────────────────────────┘
```

- 슬라이더 변경 → `requestAnimationFrame` throttle (`TimeSlider.tsx::handleSliderChange`) → 프리로드된 슬롯 데이터로 즉시 전환 (슬라이더 조작당 API 호출 없음)
- 프리로드: 히트맵 최초 활성화 시 24시간 전체 데이터를 한 번에 가져와 클라이언트에서 전환
- 평일/주말 토글 UI 는 미구현 (§1 주석)

### 4.3 프리로드 전략

```
GET /api/map-data/heatmap/all[?quarter={YYYYQN}]
```
→ `{"quarter": "2025Q4", "slots": {"0": [...], ..., "23": [...]}}` — 24시간 전체 데이터 반환 (클라이언트 메모리 캐시, `mapStore.heatmapData`)
→ 슬라이더 조작 시 API 호출 없이 즉시 전환. 서버측 Redis 캐시 `heatmap:all:{quarter|latest}` TTL 24h + singleflight

## 5. Kakao Map + deck.gl 통합

- deck.gl을 Kakao Map 위에 오버레이로 렌더링
- Kakao Map의 줌/팬 이벤트를 deck.gl 뷰포트에 동기화
- `deck.gl` Canvas를 Kakao Map 컨테이너 위에 absolute 포지셔닝

## 6. 수용 기준

- [x] 히트맵 레이어가 지도 위에 렌더링된다 (deck.gl `HeatmapLayer`)
- [x] 시간 슬라이더 0~23시 전환 시 히트맵이 변경된다
- [ ] 평일/주말 토글 — `day_type` 컬럼 부재로 미지원 (후순위)
- [x] 재생 버튼으로 자동 애니메이션 (1초/시간)
- [x] 히트맵 ON/OFF 토글
- [x] 줌/팬 시 히트맵이 지도와 동기화
- [x] 슬라이더 전환 200ms 이내 (프리로드 방식)

---

*작성일: 2026-03-24*
