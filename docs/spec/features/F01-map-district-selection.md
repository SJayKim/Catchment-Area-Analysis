# F01. 지도 기반 상권 선택 Spec

> 지도에서 상권 영역을 클릭/검색으로 선택하는 기능

---

## 1. 개요

| 항목 | 내용 |
|------|------|
| Phase | 1A(Mock) · 1B(Real) — **완료** |
| Tier | Free |
| 의존성 | D01 (ETL), `districts` 테이블 |
| 상권 단위 | 골목상권, 발달상권, 전통시장, 관광특구 |
| 상권 수 | 서울 전체 **1,650개** (2025Q4) |
| 서비스 범위 | 서울 지역 한정 |

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

구체 필드는 [../../architecture/frontend.md §3](../../architecture/frontend.md) 참조. 요약:

- `mapStore`: `center`, `zoom`, `activeLayers`, heatmap 관련 필드
- `districtStore`: `selected: { code, name, polygon, source: 'map' | 'chat' }`, `isCompareMode`, `compareList (max 3)`, `hoveredCode`
- `useMapSync` 훅이 `selected.source === 'map'` 일 때 챗에 자동 요약 쿼리를 전달

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
SELECT code, name, type,
       ST_AsGeoJSON(boundary) AS geojson,
       ST_AsGeoJSON(center_point) AS center
FROM districts
WHERE ST_Intersects(boundary, ST_MakeEnvelope($sw_lng, $sw_lat, $ne_lng, $ne_lat, 4326));

-- 상권 검색 (이름, 한글 조사 strip 전처리)
SELECT code, name, type, ST_AsGeoJSON(center_point) AS center
FROM districts
WHERE name ILIKE '%' || $keyword || '%'
LIMIT 10;
```

> `memory/feedback_korean_particles.md` — 검색 입력에서 `을/를/이/가/에/의` 등 조사는 서버에서 strip.

## 6. 범위 제한 처리

- 서울 외 지역 클릭/검색 시: "현재 서울 지역만 지원됩니다" 안내 토스트
- 서울 바운딩 박스: 대략 (37.413, 126.734) ~ (37.715, 127.269)

## 7. 수용 기준

- [x] Kakao Map이 로드되고 서울 중심으로 초기화된다 (SDK 프록시 `/_proxy/kakao-sdk` 경유)
- [x] 상권 폴리곤이 지도 위에 렌더링된다 (Real 모드 1,650개)
- [x] 폴리곤 클릭 시 해당 상권이 선택되고 하이라이트된다
- [x] 검색바에서 상권명으로 검색/자동완성이 동작한다 (한글 조사 strip 포함)
- [x] 상권 선택 시 지도가 해당 위치로 이동한다
- [x] 선택된 상권 정보가 StatusBar에 표시된다
- [x] 비교 모드에서 2~3개 상권이 서로 다른 색상으로 하이라이트된다
- [ ] 서울 외 지역 선택 시 안내 메시지가 표시된다 (미확인)
- [x] 뷰포트 기반 폴리곤 로딩이 동작한다 (ST_Intersects)
