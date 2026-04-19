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
| 평일/주말 토글 | 평일(월~금 평균) / 주말(토~일 평균) 전환 |
| 레이어 토글 | Toolbar [히트맵] 버튼 ON/OFF |
| 애니메이션 | 재생 버튼 → 0시~23시 자동 재생 (1초/시간) |

## 3. 데이터 구조

### 3.1 히트맵 API

```
GET /api/map-data/heatmap?time_slot={0-23}&day_type={weekday|weekend}
```

**Response:**
```json
{
  "points": [
    {"lat": 37.4979, "lng": 127.0276, "weight": 18000},
    {"lat": 37.5563, "lng": 126.9237, "weight": 12500},
    ...
  ],
  "time_slot": 12,
  "day_type": "weekday",
  "quarter": "2025Q4"
}
```

- `weight`: 해당 상권 중심점의 유동인구 수
- 전체 상권 ~1,000개 포인트

### 3.2 DB 쿼리

```sql
SELECT d.center_point,
       ST_Y(d.center_point) as lat,
       ST_X(d.center_point) as lng,
       SUM(fp.population) as weight
FROM districts d
JOIN floating_population fp ON d.district_code = fp.district_code
WHERE fp.time_slot = $1
  AND fp.day_type = $2
  AND fp.quarter = $3
GROUP BY d.district_code, d.center_point;
```

## 4. Frontend 구현

### 4.1 HeatmapLayer (`components/map/HeatmapLayer.tsx`)

```typescript
import { HeatmapLayer } from '@deck.gl/aggregation-layers';

const heatmapLayer = new HeatmapLayer({
  data: points,
  getPosition: d => [d.lng, d.lat],
  getWeight: d => d.weight,
  radiusPixels: 60,
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
│ [평일] [주말]                          현재: 12시      │
└─────────────────────────────────────────────────────┘
```

- 슬라이더 변경 → debounce 200ms → API 호출 또는 프리로드 데이터 전환
- 프리로드: 초기 로드 시 24시간 전체 데이터를 한 번에 가져와 클라이언트에서 전환

### 4.3 프리로드 전략

```
GET /api/map-data/heatmap/all?day_type={weekday|weekend}
```
→ 24시간 전체 데이터 반환 (클라이언트 메모리 캐시)
→ 슬라이더 조작 시 API 호출 없이 즉시 전환

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
