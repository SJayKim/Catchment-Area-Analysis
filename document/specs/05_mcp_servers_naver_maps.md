# 05-C. MCP Server: Naver Maps

> MarketScope AI 네이버 지도 서비스 접근 계층
> 작성일: 2026-03-21

---

## 1. 서버 프로필

| 항목 | 내용 |
|------|------|
| **서버명** | `naver-maps-server` |
| **포트** | `5108` |
| **목적** | 네이버 지도/검색 API 래핑. 국내 장소 검색, 지오코딩, 경로 탐색. 카카오 API 대비 한국 내 장소 데이터 보완 |
| **담당 에이전트** | 입지분석, 트렌드분석 |
| **래핑 API** | Naver Cloud Platform (Geocoding, Reverse Geocoding, Directions), Naver Search API (Local Search) |

---

## 2. 인증

### 2.1 Naver Cloud Platform API (지도)

| 항목 | 내용 |
|------|------|
| **인증 방식** | HTTP Header (`X-NCP-APIGW-API-KEY-ID`, `X-NCP-APIGW-API-KEY`) |
| **환경변수** | `DATA_API_NAVER_CLIENT_ID`, `DATA_API_NAVER_CLIENT_SECRET` |
| **무료 할당량** | Geocoding: 3,000건/일, Directions: 1,000건/일, Static Map: 3,000건/일 |

### 2.2 Naver Search API (장소 검색)

| 항목 | 내용 |
|------|------|
| **인증 방식** | HTTP Header (`X-Naver-Client-Id`, `X-Naver-Client-Secret`) |
| **환경변수** | 동일 (`DATA_API_NAVER_CLIENT_ID`, `DATA_API_NAVER_CLIENT_SECRET`) |
| **무료 할당량** | 25,000건/일 |

---

## 3. 도구 목록

| # | 도구명 | 설명 | API | 일일 할당량 |
|---|--------|------|-----|------------|
| 1 | `naver_maps.geocode` | 주소 → 좌표 변환 | NCP Geocoding | 3,000건 |
| 2 | `naver_maps.reverse_geocode` | 좌표 → 주소 변환 | NCP Reverse Geocoding | 3,000건 |
| 3 | `naver_maps.local_search` | 장소 검색 | Naver Search Local | 25,000건 |
| 4 | `naver_maps.directions` | 경로 탐색 (자동차) | NCP Directions | 1,000건 |
| 5 | `naver_maps.static_map` | 정적 지도 이미지 URL | NCP Static Map | 3,000건 |

---

### 3.1 `naver_maps.geocode`

주소를 좌표로 변환한다.

```python
@mcp.tool()
async def naver_geocode(
    address: str,  # 주소 텍스트 (예: "서울시 마포구 합정동 123-4")
) -> NaverGeoResult:
    """주소를 좌표로 변환합니다 (네이버 Geocoding API)."""
```

**외부 API**:
- **엔드포인트**: `https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode`
- **메서드**: `GET`
- **파라미터**: `query={address}`
- **인증**: `X-NCP-APIGW-API-KEY-ID`, `X-NCP-APIGW-API-KEY` 헤더

**반환 스키마**:
```python
class NaverGeoResult(BaseModel):
    lat: float
    lng: float
    road_address: str
    jibun_address: str
    retrieved_at: datetime
```

---

### 3.2 `naver_maps.reverse_geocode`

좌표를 주소로 변환한다.

```python
@mcp.tool()
async def naver_reverse_geocode(
    lat: float,  # 위도
    lng: float,  # 경도
) -> NaverReverseGeoResult:
    """좌표를 주소로 변환합니다."""
```

**외부 API**:
- **엔드포인트**: `https://naveropenapi.apigw.ntruss.com/map-reversegeocode/v2/gc`
- **파라미터**: `coords={lng},{lat}`, `output=json`, `orders=roadaddr,addr`

**반환 스키마**:
```python
class NaverReverseGeoResult(BaseModel):
    sido: str          # 시/도
    sigungu: str       # 시/군/구
    dong: str          # 동
    road_name: str     # 도로명
    road_number: str   # 도로 번호
    lat: float
    lng: float
```

---

### 3.3 `naver_maps.local_search`

네이버 검색 API의 지역 검색 기능. 한국 내 장소 데이터가 가장 풍부하다.

```python
@mcp.tool()
async def naver_local_search(
    query: str,         # 검색어 (예: "합정동 카페")
    display: int = 5,   # 결과 수 (최대 5)
) -> NaverLocalSearchResult:
    """장소를 검색합니다 (네이버 검색 API)."""
```

**외부 API**:
- **엔드포인트**: `https://openapi.naver.com/v1/search/local.json`
- **인증**: `X-Naver-Client-Id`, `X-Naver-Client-Secret` 헤더

**반환 스키마**:
```python
class NaverLocalPlace(BaseModel):
    title: str           # 장소명
    address: str         # 지번 주소
    road_address: str    # 도로명 주소
    category: str        # 카테고리
    telephone: str       # 전화번호
    link: str           # 네이버 플레이스 URL
    mapx: int           # 카텍스 X좌표
    mapy: int           # 카텍스 Y좌표
```

---

### 3.4 `naver_maps.directions`

두 지점 간 자동차 경로를 탐색한다.

```python
@mcp.tool()
async def naver_directions(
    origin_lat: float,   # 출발 위도
    origin_lng: float,   # 출발 경도
    dest_lat: float,     # 도착 위도
    dest_lng: float,     # 도착 경도
) -> NaverDirectionResult:
    """경로를 탐색합니다 (네이버 Directions API)."""
```

**외부 API**:
- **엔드포인트**: `https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving`
- **파라미터**: `start={lng},{lat}`, `goal={lng},{lat}`

**반환 스키마**:
```python
class NaverDirectionResult(BaseModel):
    distance_m: int      # 거리 (미터)
    duration_ms: int     # 소요시간 (밀리초)
    duration_min: float  # 소요시간 (분)
    toll_fare: int       # 통행료 (원)
    fuel_price: int      # 연료비 (원)
```

---

### 3.5 `naver_maps.static_map`

정적 지도 이미지 URL을 생성한다 (이미지 직접 반환 아님).

```python
@mcp.tool()
async def naver_static_map(
    lat: float,           # 중심 위도
    lng: float,           # 중심 경도
    width: int = 600,     # 이미지 폭 (px)
    height: int = 400,    # 이미지 높이 (px)
    level: int = 16,      # 줌 레벨 (1-20)
) -> StaticMapResult:
    """정적 지도 이미지 URL을 생성합니다."""
```

**반환**:
```python
class StaticMapResult(BaseModel):
    map_url: str      # 지도 이미지 URL (NCP 인증 헤더 필요)
    width: int
    height: int
    level: int
    note: str         # "이미지 조회 시 X-NCP-APIGW-API-KEY-ID/KEY 헤더 필요"
```

---

## 4. Rate Limiting

| API | 일일 한도 | QPS |
|-----|----------|-----|
| Geocoding / Reverse Geocoding | 3,000건 | 10 |
| Directions | 1,000건 | 5 |
| Static Map | 3,000건 | 10 |
| Local Search | 25,000건 | 10 |

---

## 5. 에러 처리

| 에러 유형 | HTTP 코드 | 처리 방식 |
|-----------|-----------|-----------|
| 인증 실패 | 401 | API 키 확인 → 로그 경고 |
| 할당량 초과 | 429 | 에러 반환 + 다음 날까지 대기 |
| 잘못된 파라미터 | 400 | 파라미터 검증 에러 반환 |
| 서버 오류 | 500 | 재시도 (최대 3회) |

---

## 6. 환경변수

| 변수명 | 설명 | 필수 |
|--------|------|------|
| `DATA_API_NAVER_CLIENT_ID` | 네이버 Client ID | ✅ |
| `DATA_API_NAVER_CLIENT_SECRET` | 네이버 Client Secret | ✅ |
