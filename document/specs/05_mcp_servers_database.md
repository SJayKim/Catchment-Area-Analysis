# 05-A. MCP Server: Database (PostGIS 공간쿼리)

> MarketScope AI 데이터베이스 직접 접근 계층
> 작성일: 2026-03-21

---

## 1. 서버 프로필

| 항목 | 내용 |
|------|------|
| **서버명** | `database-server` |
| **포트** | `5106` |
| **목적** | PostgreSQL + PostGIS 공간쿼리를 에이전트에게 제공. 점포, 인구, 매출 등 내부 DB에 직접 접근 |
| **담당 에이전트** | 입지분석, 경쟁분석, 유동인구분석 |
| **전송 방식** | HTTP (FastAPI) |

---

## 2. 도구 목록

| # | 도구명 | 설명 | 데이터 소스 | 캐시 TTL |
|---|--------|------|-------------|----------|
| 1 | `database.query_nearby_stores` | 반경 내 점포 조회 | PostGIS ST_DWithin | 1시간 |
| 2 | `database.query_population_grid` | 격자별 인구 데이터 | population_grid 테이블 | 6시간 |
| 3 | `database.query_revenue_by_area` | 지역별 매출 데이터 | area_revenue 테이블 | 6시간 |
| 4 | `database.query_commercial_district` | 상권 정보 조회 | commercial_districts 테이블 | 12시간 |
| 5 | `database.execute_spatial_query` | 범용 공간 쿼리 (SELECT 전용) | 전체 DB | 없음 |

---

### 2.1 `database.query_nearby_stores`

반경 내 점포를 PostGIS `ST_DWithin`으로 조회한다.

```python
@mcp.tool()
async def query_nearby_stores(
    lat: float,          # 중심 위도
    lng: float,          # 중심 경도
    radius_m: int = 500, # 반경 (미터)
    industry: str = "",  # 업종 필터 (ILIKE)
) -> NearbyStoresResult:
    """반경 내 점포를 조회합니다."""
```

**SQL 쿼리 패턴**:
```sql
SELECT store_name, industry_category, address,
       ST_Y(geom::geometry) as lat, ST_X(geom::geometry) as lng,
       ST_Distance(geom, ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography) as distance_m
FROM stores
WHERE ST_DWithin(
    geom,
    ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
    $3
)
ORDER BY distance_m LIMIT 50
```

**반환 스키마**:
```python
class NearbyStoresResult(BaseModel):
    stores: list[NearbyStore]
    total_count: int
    search_params: dict
    retrieved_at: datetime
```

---

### 2.2 `database.query_population_grid`

행정동 코드 또는 동 이름으로 격자별 인구 데이터를 조회한다.

```python
@mcp.tool()
async def query_population_grid(
    area_code: str = "",   # 행정동 코드
    dong_name: str = "",   # 동 이름 (ILIKE 검색)
) -> PopulationGridResult:
    """격자별 인구 데이터를 조회합니다."""
```

---

### 2.3 `database.query_revenue_by_area`

지역코드 + 업종별 매출 데이터를 조회한다.

```python
@mcp.tool()
async def query_revenue_by_area(
    area_code: str,        # 지역코드 (필수)
    industry: str = "",    # 업종 필터
    year_quarter: str = "",# 연도-분기 (예: "2025-Q4")
) -> RevenueAreaResult:
    """지역별 매출 데이터를 조회합니다."""
```

---

### 2.4 `database.query_commercial_district`

좌표 기반 또는 이름 기반으로 상권 정보를 조회한다.

```python
@mcp.tool()
async def query_commercial_district(
    lat: float = None,           # 중심 위도
    lng: float = None,           # 중심 경도
    district_name: str = "",     # 상권명 검색
    radius_m: int = 1000,        # 반경 (좌표 검색 시)
) -> CommercialDistrictResult:
    """상권 정보를 조회합니다."""
```

---

### 2.5 `database.execute_spatial_query`

범용 공간 쿼리 실행. **SELECT 쿼리만 허용**하며, DML/DDL은 차단한다.

```python
@mcp.tool()
async def execute_spatial_query(
    query: str,  # SQL 쿼리 (SELECT만 허용)
) -> SpatialQueryResult:
    """범용 공간 쿼리를 실행합니다 (읽기 전용)."""
```

**보안**:
- `SELECT`로 시작하지 않는 쿼리 차단
- `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT` 키워드 차단
- 최대 100행 반환

---

## 3. 인프라

### 3.1 커넥션 풀

```python
# asyncpg 커넥션 풀
pool = await asyncpg.create_pool(
    dsn=DATABASE_URL,
    min_size=2,
    max_size=10,
)
```

### 3.2 PostGIS 함수

| 함수 | 용도 |
|------|------|
| `ST_MakePoint(lng, lat)` | 좌표 → Point 변환 |
| `ST_SetSRID(..., 4326)` | WGS84 좌표계 설정 |
| `ST_DWithin(geom, point, distance)` | 반경 검색 |
| `ST_Distance(geom1, geom2)` | 두 지점 간 거리 (m) |
| `ST_Y(geom)` / `ST_X(geom)` | 위도/경도 추출 |

### 3.3 환경변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `DATABASE_URL` | PostgreSQL 연결 문자열 | `postgresql://marketscope:marketscope@localhost:5432/marketscope` |

---

## 4. 에러 처리

| 에러 유형 | 처리 방식 |
|-----------|-----------|
| 커넥션 풀 미초기화 | `RuntimeError` 반환 |
| 쿼리 실행 실패 | `{"error": "..."}` + 빈 결과 |
| DML/DDL 시도 | 즉시 차단, 에러 메시지 |
| 타임아웃 | 30초 기본 타임아웃 |
