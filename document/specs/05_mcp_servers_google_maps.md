# 05-B. MCP Server: Google Maps

> MarketScope AI Google 지도 서비스 접근 계층
> 작성일: 2026-03-21

---

## 1. 서버 프로필

| 항목 | 내용 |
|------|------|
| **서버명** | `google-maps-server` |
| **포트** | `5107` |
| **목적** | Google Maps Platform API 래핑. 장소 검색, 리뷰, 경로 탐색 등 카카오 API로 제공되지 않는 글로벌 데이터 보완 |
| **담당 에이전트** | 입지분석, 경쟁분석 |
| **래핑 API** | Google Geocoding, Places, Directions API |

---

## 2. 인증 & 할당량

| 항목 | 내용 |
|------|------|
| **API 키** | `DATA_API_GOOGLE_MAPS_KEY` 환경변수 |
| **인증 방식** | Query Parameter `key={API_KEY}` |
| **무료 할당량** | Geocoding: $5/1,000건, Places: $17/1,000건, Directions: $5/1,000건 |
| **월 크레딧** | $200 무료 (Maps Platform) |
| **Rate Limit** | QPS 50 (기본) |

---

## 3. 도구 목록

| # | 도구명 | 설명 | API | 비용/1K건 |
|---|--------|------|-----|-----------|
| 1 | `google_maps.geocode` | 주소 → 좌표 | Geocoding API | $5 |
| 2 | `google_maps.reverse_geocode` | 좌표 → 주소 | Geocoding API | $5 |
| 3 | `google_maps.nearby_search` | 주변 장소 검색 | Places API | $17 |
| 4 | `google_maps.place_details` | 장소 상세 (리뷰, 영업시간) | Place Details API | $17 |
| 5 | `google_maps.directions` | 경로 탐색 | Directions API | $5 |

---

### 3.1 `google_maps.geocode`

주소를 좌표로 변환한다.

```python
@mcp.tool()
async def google_geocode(
    address: str,  # 주소 텍스트 (예: "서울시 마포구 합정동")
) -> GeocodingResult:
    """주소를 좌표로 변환합니다 (Google Geocoding API)."""
```

**외부 API**:
- **엔드포인트**: `https://maps.googleapis.com/maps/api/geocode/json`
- **파라미터**: `address`, `key`, `language=ko`

**반환 스키마**:
```python
class GeocodingResult(BaseModel):
    lat: float
    lng: float
    formatted_address: str
    place_id: str
    retrieved_at: datetime
```

---

### 3.2 `google_maps.reverse_geocode`

좌표를 주소로 변환한다.

```python
@mcp.tool()
async def google_reverse_geocode(
    lat: float,  # 위도
    lng: float,  # 경도
) -> ReverseGeocodingResult:
    """좌표를 주소로 변환합니다."""
```

---

### 3.3 `google_maps.nearby_search`

주변 장소를 검색한다. Places API의 Nearby Search 기능.

```python
@mcp.tool()
async def google_nearby_search(
    lat: float,              # 중심 위도
    lng: float,              # 중심 경도
    radius_m: int = 500,     # 반경 (미터, 최대 50000)
    keyword: str = "",       # 키워드 (예: "카페")
    type: str = "",          # 장소 유형 (예: "restaurant", "cafe")
) -> NearbySearchResult:
    """주변 장소를 검색합니다."""
```

**외부 API**:
- **엔드포인트**: `https://maps.googleapis.com/maps/api/place/nearbysearch/json`
- **파라미터**: `location`, `radius`, `keyword`, `type`, `key`, `language=ko`

---

### 3.4 `google_maps.place_details`

장소 상세 정보를 조회한다. 리뷰, 영업시간 등 카카오 API에서 제공하지 않는 정보.

```python
@mcp.tool()
async def google_place_details(
    place_id: str,  # Google Place ID (nearby_search 결과에서 획득)
) -> PlaceDetailResult:
    """장소 상세 정보 (리뷰, 영업시간 등)를 조회합니다."""
```

**반환 스키마**:
```python
class PlaceDetailResult(BaseModel):
    name: str
    formatted_address: str
    lat: float
    lng: float
    rating: float | None
    total_ratings: int
    opening_hours: list[str]     # 요일별 영업시간
    reviews: list[ReviewSummary] # 최근 리뷰 5개
    types: list[str]
    retrieved_at: datetime
```

---

### 3.5 `google_maps.directions`

두 지점 간 경로를 탐색한다.

```python
@mcp.tool()
async def google_directions(
    origin_lat: float,       # 출발 위도
    origin_lng: float,       # 출발 경도
    dest_lat: float,         # 도착 위도
    dest_lng: float,         # 도착 경도
    mode: str = "transit",   # 이동 수단: driving, walking, transit
) -> DirectionResult:
    """경로를 탐색합니다."""
```

---

## 4. Rate Limiting

```python
# 기본 QPS 50으로 제한
# Token Bucket 패턴 적용
rate_limiter = TokenBucket(
    max_tokens=50,
    refill_rate=50,  # 초당 50건 리필
)
```

---

## 5. 에러 처리

| Google API 에러 | 처리 방식 |
|-----------------|-----------|
| `ZERO_RESULTS` | 빈 결과 + 메시지 반환 |
| `OVER_QUERY_LIMIT` | 429 에러 → 지수 백오프 재시도 |
| `REQUEST_DENIED` | API 키 문제 → 로그 경고 |
| `INVALID_REQUEST` | 파라미터 검증 오류 반환 |

---

## 6. 환경변수

| 변수명 | 설명 | 필수 |
|--------|------|------|
| `DATA_API_GOOGLE_MAPS_KEY` | Google Maps API 키 | ✅ |
