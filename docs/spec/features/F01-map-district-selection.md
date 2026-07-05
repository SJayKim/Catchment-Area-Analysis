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
| 현재 위치 | GPS 좌표로 지도 이동 (가까운 상권 자동 선택은 없음) | 📍 "내 위치" 버튼 (`Toolbar.tsx::handleLocate`) |
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
- `districtStore`: `selected: District | null` + **별도 최상위 필드** `selectSource: 'map' | 'chat' | null` (`districtStore.ts` — `source` 가 `selected` 객체에 내장돼 있지 않음), `isCompareMode`, `compareList (max 3)`, `hoveredCode`
- `useMapSync` 훅이 `selectSource === 'map'` 일 때 **LLM 호출 없이** `chatStore.setPreview(code)` 로 zero-LLM 프리뷰(`GET /api/districts/{code}/preview`, F13)만 호출 — 자동 요약 쿼리는 발사하지 않는다 (2026-04-23 제거). 풀 분석은 사용자가 PreviewCard 칩 / "AI 분석 보기" 를 눌러야 시작

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
| 비교 모드 | `compareList` 슬롯 순서별 색상 (파랑/주황/핑크 — `DistrictLayer.tsx::COMPARE_STYLES`) |

### 3.5 검색 기능

- Toolbar 검색바에 타이핑 → debounce 300ms 후 `GET /api/districts?search=` 서버 검색 (`lib/api.ts::fetchDistricts` — 클라이언트 필터링 아님)
- 자동완성 드롭다운 최대 10건 (`results.slice(0, 10)`)
- 선택 시 `mapStore.setView(center, 5)` + `districtStore.select(district, 'map')` (비교모드 ON 이면 `addToCompare`)

## 4. Backend API

### 4.1 상권 목록 조회

```
GET /api/districts?search={keyword}&type={district_type}&limit={1~100, 기본 20}&offset={0~}
```

**Response** (`api/routes/districts.py::DistrictListResponse`):
```json
{
  "total": 1234,
  "items": [
    {
      "district_code": "3110032",
      "district_name": "강남역",
      "district_type": "발달상권",
      "gu_code": "11680",
      "dong_code": null,
      "data_quarter": "2025Q4",
      "center_lng": 127.0276,
      "center_lat": 37.4979
    }
  ]
}
```

> 래퍼 키는 `items` (`districts` 아님), 필드는 flat `district_*` + `center_lng`/`center_lat` (중첩 `center` 객체 없음). 프론트 `lib/api.ts::fetchDistricts` 가 이를 `District{code, name, type, center:{lat,lng}, dataQuarter}` 로 변환한다.

### 4.2 상권 폴리곤 GeoJSON

```
GET /api/map-data/polygons?bounds={sw_lat,sw_lng,ne_lat,ne_lng}
```

- 현재 지도 뷰포트 내 폴리곤만 반환 (성능 최적화, 최대 500건 `LIMIT`)
- GeoJSON FeatureCollection 형식

**Response** (`repositories/real/districts.py::get_polygons_geojson`):
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "district_code": "3110032",
        "district_name": "강남역",
        "district_type": "발달상권",
        "data_quarter": "2025Q4",
        "center": [127.0276, 37.4979]
      },
      "geometry": { "type": "Polygon", "coordinates": [[[127.02, 37.49], ...]] }
    }
  ]
}
```

> properties 키도 flat `district_*` 이며 `center` 는 `[lng, lat]` 배열. 프론트 변환은 `lib/api.ts` 참조.

### 4.3 상권 상세 조회

```
GET /api/districts/{code}
```

**Response** (`api/routes/districts.py::DistrictDetail`):
```json
{
  "district_code": "3110032",
  "district_name": "강남역",
  "district_type": "발달상권",
  "gu_code": "11680",
  "dong_code": null,
  "data_quarter": "2025Q4",
  "center_lng": 127.0276,
  "center_lat": 37.4979,
  "polygon": { "type": "Polygon", "coordinates": [[[127.02, 37.49], ...]] }
}
```

> `polygon` 은 좌표 배열이 아니라 **GeoJSON geometry 객체**(`ST_AsGeoJSON(boundary)` 파싱 결과, 없으면 `null`). 미존재 코드는 404.

## 5. DB 쿼리

실제 구현은 SQLAlchemy (`repositories/real/districts.py`) — 아래는 등가 SQL. 컬럼명은 `district_code` / `district_name` / `district_type` (`code`/`name`/`type` 아님).

```sql
-- 뷰포트 내 상권 폴리곤 조회 (get_polygons_geojson)
SELECT district_code, district_name, district_type, data_quarter,
       ST_AsGeoJSON(boundary) AS geojson,
       ST_X(center_point), ST_Y(center_point)
FROM districts
WHERE ST_Intersects(boundary, ST_MakeEnvelope($sw_lng, $sw_lat, $ne_lng, $ne_lat, 4326))
LIMIT 500;

-- 상권 목록/검색 (list_districts — 단순 ILIKE 부분일치)
SELECT district_code, district_name, district_type, gu_code, dong_code, data_quarter,
       ST_X(center_point), ST_Y(center_point)
FROM districts
WHERE district_name ILIKE '%' || $keyword || '%'
ORDER BY district_name
LIMIT $limit OFFSET $offset;
```

> 한글 조사 strip(`을/를/이/가/에/의` 등) + 위치 접미사(`입구/역/앞`) 축약 + 후보 랭킹은 목록 검색이 아니라 **챗 메시지 상권 감지 경로**(`detect_district_by_name` / `detect_districts_in_message` 의 `_candidate_words`)에서 수행한다 — [[feedback_korean_particles]] 교훈.

## 6. 범위 제한 처리

- 서울 외 지역 클릭/검색 시: "현재 서울 지역만 지원됩니다" 안내 토스트
- 서울 바운딩 박스: 대략 (37.413, 126.734) ~ (37.715, 127.269)

## 7. 수용 기준

- [x] Kakao Map이 로드되고 서울 중심으로 초기화된다 (SDK 프록시 `/proxy/kakao-sdk` 경유)
- [x] 상권 폴리곤이 지도 위에 렌더링된다 (Real 모드 1,650개)
- [x] 폴리곤 클릭 시 해당 상권이 선택되고 하이라이트된다
- [x] 검색바에서 상권명으로 검색/자동완성이 동작한다 (서버 ILIKE 부분일치 — 조사 strip 은 챗 메시지 감지 경로에만 있음)
- [x] 상권 선택 시 지도가 해당 위치로 이동한다
- [x] 선택된 상권 정보가 StatusBar에 표시된다
- [x] 비교 모드에서 2~3개 상권이 서로 다른 색상으로 하이라이트된다
- [ ] 서울 외 지역 선택 시 안내 메시지가 표시된다 (미확인)
- [x] 뷰포트 기반 폴리곤 로딩이 동작한다 (ST_Intersects)
