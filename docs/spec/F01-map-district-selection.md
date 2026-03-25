# F01. 지도 기반 상권 선택 Spec

> 지도에서 상권 영역을 클릭/검색으로 선택하는 기능

---

## 1. 개요

| 항목 | 내용 |
|------|------|
| Phase | 1 (MVP) |
| 의존성 | D01 (데이터 적재), D02 (DB 스키마) |
| 상권 단위 | 골목상권, 발달상권, 전통시장, (행정동) |
| 서비스 범위 | 서울 지역 한정 (MVP) |

## 2. 사용자 인터랙션

| 방법 | 설명 | 트리거 |
|------|------|--------|
| 지도 클릭 | 폴리곤 영역 클릭 → 상권 선택 | `onClick` 이벤트 |
| 검색 | 상권명/주소/지역명 입력 → 자동완성 → 선택 | Toolbar 검색바 |
| 현재 위치 | GPS 기반 가장 가까운 상권 자동 선택 | 📍 버튼 |
| 챗봇 입력 | "강남역 상권 보여줘" → 지도 이동 + 선택 | 자연어 (F02 연동) |

## 3. Frontend 구현

### 3.1 관련 컴포넌트

| 컴포넌트 | 파일 | 역할 |
|----------|------|------|
| MapContainer | `components/map/MapContainer.tsx` | Kakao Map SDK 초기화, 이벤트 바인딩 |
| DistrictLayer | `components/map/DistrictLayer.tsx` | 상권 폴리곤 렌더링, 클릭 핸들링 |
| MapControls | `components/map/MapControls.tsx` | 줌, 레이어 토글 |
| Toolbar | `components/layout/Toolbar.tsx` | 검색바, 현재 위치 버튼 |
| StatusBar | `components/layout/StatusBar.tsx` | 선택된 상권 표시, 데이터 기준 시점 |

### 3.2 상태 관리 (Zustand)

```typescript
// stores/mapStore.ts
interface MapStore {
  center: { lat: number; lng: number };
  zoom: number;
  activeLayers: string[];  // ['polygon', 'heatmap', 'marker']
  setCenter: (center: { lat: number; lng: number }) => void;
  setZoom: (zoom: number) => void;
  toggleLayer: (layer: string) => void;
}

// stores/districtStore.ts
interface DistrictStore {
  selected: District | null;       // 현재 선택된 상권
  compareList: District[];         // 비교 모드 상권 목록 (F05용)
  allDistricts: District[];        // 전체 상권 목록 (검색용)
  select: (district: District) => void;
  deselect: () => void;
  addCompare: (district: District) => void;
}

interface District {
  code: string;
  name: string;
  type: '골목상권' | '발달상권' | '전통시장';
  center: { lat: number; lng: number };
  polygon: number[][];  // 좌표 배열
}
```

### 3.3 지도 초기화

- Kakao Map SDK 로드 (스크립트 동적 삽입)
- 초기 뷰: 서울 중심 (37.5665, 126.9780), 줌 레벨 11
- 상권 폴리곤을 GeoJSON으로 로드하여 오버레이

### 3.4 상권 폴리곤 시각화

| 상태 | 스타일 |
|------|--------|
| 기본 | 투명 배경, 연한 테두리 |
| 호버 | 연한 파란 배경 (opacity 0.2) |
| 선택됨 | 파란 배경 (opacity 0.4) + 굵은 테두리 |
| 비교 모드 | 각 상권 다른 색상 (파랑/초록/주황) |

### 3.5 검색 기능

- Toolbar 검색바에 타이핑 → `allDistricts`에서 필터링 (debounce 300ms)
- 자동완성 드롭다운 최대 10건
- 선택 시 `mapStore.setCenter()` + `districtStore.select()`

## 4. Backend API

### 4.1 상권 목록 조회

```
GET /api/districts?search={keyword}&type={district_type}
```

**Response:**
```json
{
  "districts": [
    {
      "code": "3110032",
      "name": "강남역",
      "type": "발달상권",
      "center": { "lat": 37.4979, "lng": 127.0276 }
    }
  ],
  "total": 1234
}
```

### 4.2 상권 폴리곤 GeoJSON

```
GET /api/map-data/polygons?bounds={sw_lat,sw_lng,ne_lat,ne_lng}
```

- 현재 지도 뷰포트 내 폴리곤만 반환 (성능 최적화)
- GeoJSON FeatureCollection 형식

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": { "code": "3110032", "name": "강남역", "type": "발달상권" },
      "geometry": { "type": "Polygon", "coordinates": [[[127.02, 37.49], ...]] }
    }
  ]
}
```

### 4.3 상권 상세 조회

```
GET /api/districts/{code}
```

**Response:**
```json
{
  "code": "3110032",
  "name": "강남역",
  "type": "발달상권",
  "center": { "lat": 37.4979, "lng": 127.0276 },
  "polygon": [[127.02, 37.49], ...],
  "data_quarter": "2025Q4"
}
```

## 5. DB 쿼리

```sql
-- 뷰포트 내 상권 폴리곤 조회
SELECT district_code, district_name, district_type,
       ST_AsGeoJSON(boundary) as geojson,
       ST_AsGeoJSON(center_point) as center
FROM districts
WHERE ST_Intersects(boundary, ST_MakeEnvelope($sw_lng, $sw_lat, $ne_lng, $ne_lat, 4326));

-- 상권 검색 (이름)
SELECT district_code, district_name, district_type,
       ST_AsGeoJSON(center_point) as center
FROM districts
WHERE district_name ILIKE '%' || $keyword || '%'
LIMIT 10;
```

## 6. 범위 제한 처리

- 서울 외 지역 클릭/검색 시: "현재 서울 지역만 지원됩니다" 안내 토스트
- 서울 바운딩 박스: 대략 (37.413, 126.734) ~ (37.715, 127.269)

## 7. 수용 기준

- [ ] Kakao Map이 로드되고 서울 중심으로 초기화된다
- [ ] 상권 폴리곤이 지도 위에 렌더링된다
- [ ] 폴리곤 클릭 시 해당 상권이 선택되고 하이라이트된다
- [ ] 검색바에서 상권명으로 검색/자동완성이 동작한다
- [ ] 상권 선택 시 지도가 해당 위치로 이동한다
- [ ] 선택된 상권 정보가 StatusBar에 표시된다
- [ ] 서울 외 지역 선택 시 안내 메시지가 표시된다
- [ ] 뷰포트 기반 폴리곤 로딩이 동작한다 (성능)

---

*작성일: 2026-03-24*
