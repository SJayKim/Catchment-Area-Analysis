# Real DB 완성 계획 — 폴리곤 적재 + district_summary Real DB + API 폴백

> 작성일: 2026-03-31
> 갱신일: 2026-04-01 — district_summary Real DB 지원 병합
> 대상: Next Items #1 (district_summary Real DB) + #2 (미승인 API 대체 소스)

---

## Context

Phase 1B 완료 상태에서 Real 모드 완성을 위한 남은 두 작업:

1. **district_summary.py Real DB 지원**: 8개 Agent Tool 중 유일하게 Mock 전용. 다른 7개 Tool은 이미 `settings.use_mock` 분기 + Real DB 쿼리 지원.
2. **SHP 폴리곤 적재**: 서울 열린데이터 폴리곤 API(VwsmTrdarSelngW)가 ERROR-500. districts 테이블에 1,650행이 있지만 boundary=NULL, center_point=NULL.

**실행 순서**: Part A(district_summary) 먼저 → Part B(SHP 폴리곤). Part A는 외부 의존 없이 즉시 구현 가능.

---

## Part A: district_summary.py Real DB 지원

### 접근 방식

기존 Tool 함수(`get_floating_population`, `get_estimated_sales`, `get_store_info`)를 `asyncio.gather()`로 병렬 호출 → 결과 집계. 자체 DB 쿼리 불필요 (DRY 원칙).

### 수정 대상 파일

| 파일 | 작업 | 변경량 |
|------|------|--------|
| `server/server/agent/tools/district_summary.py` | 전면 재작성 | ~80줄 |

**변경하지 않는 파일**: 다른 tool 파일들, 프론트엔드, loader, mock_data

### 구현 상세

#### 1. import 변경

```python
# 삭제
from server.agent.tools.mock_data import (
    DISTRICTS, ESTIMATED_SALES, FLOATING_POPULATION, STORE_INFO,
)

# 추가
import asyncio
from server.config import settings
from server.services.cache import cache_service
from server.agent.tools.floating_population import get_floating_population
from server.agent.tools.estimated_sales import get_estimated_sales
from server.agent.tools.store_info import get_store_info
```

#### 2. `_get_district_meta()` 헬퍼 추가

district_name/type은 하위 Tool 반환값에 없으므로 별도 조회 필요.

```python
async def _get_district_meta(district_code: str) -> dict | None:
    """상권 이름/유형 조회. Mock이면 DISTRICTS dict, Real이면 DB."""
    if settings.use_mock:
        from server.agent.tools.mock_data import DISTRICTS
        return DISTRICTS.get(district_code)

    from server.models.base import async_session
    from server.models.district import District
    from sqlalchemy import select

    async with async_session() as session:
        row = (await session.execute(
            select(District.district_name, District.district_type)
            .where(District.district_code == district_code)
        )).one_or_none()
        if row is None:
            return None
        return {"name": row.district_name, "type": row.district_type}
```

#### 3. `get_district_summary()` 본문 재작성

```python
async def get_district_summary(district_code: str) -> dict:
    # 캐시 확인
    cache_key = f"summary:{district_code}"
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return cached

    # 4개 병렬 호출
    fp_result, sales_result, store_result, meta = await asyncio.gather(
        get_floating_population(district_code),
        get_estimated_sales(district_code),
        get_store_info(district_code),
        _get_district_meta(district_code),
    )

    if not meta:
        return {"error": f"상권 코드 '{district_code}'에 해당하는 데이터가 없습니다."}

    # 각 결과 에러 체크
    fp_ok = "error" not in fp_result
    sales_ok = "error" not in sales_result
    store_ok = "error" not in store_result

    # 이하 집계 로직 (기존과 동일한 패턴)
    # fp_result → by_hour 매핑 (time_slot→hour, population→pop)
    # store_result → top_categories 매핑 (category_name→name, store_count→count)
    # sales_result → status, trend
    # dataQuarter: Mock이면 " (샘플)" 접미사, Real이면 그대로
```

#### 4. 기존 유지

- `_format_population()`, `_format_sales()` — 변경 없음
- 반환 스키마 — 프론트엔드 SummaryCardData와 동일 유지:
  ```
  districtName, districtType, summary, floatingPopulation{dailyAvg, peakHour, byHour[]},
  topCategories[], status, closeRate{current, average}, dataQuarter
  ```

### 참고할 기존 코드 (Real DB 패턴)

- `server/server/agent/tools/floating_population.py` — 반환 형식: `daily_avg`, `peak_hour`, `by_hour[{time_slot, population}]`
- `server/server/agent/tools/estimated_sales.py` — 반환 형식: `total_monthly_sales`, `trend`, `quarter`
- `server/server/agent/tools/store_info.py` — 반환 형식: `top_categories[{category_name, store_count}]`, `close_rate`, `quarter`
- `server/server/services/cache.py` — `cache_service.get()`, `cache_service.set(key, value, ttl=86400)`
- `server/server/models/district.py` — `District` 모델 (district_name, district_type 컬럼)

### 주의 사항

- 순환 import 없음 (하위 Tool 중 district_summary를 import하는 파일 없음)
- 하위 Tool이 이미 자체 캐싱 → summary 캐시는 4개 호출 자체를 스킵하는 레이어
- `dataQuarter` 필드: `settings.use_mock`이면 `f"{quarter} (샘플)"`, 아니면 `quarter` 그대로

### Part A 검증

```bash
# Mock 모드
USE_MOCK=true uvicorn server.main:app --reload --port 8002
# 브라우저에서 상권 클릭 → SummaryCard 정상 렌더링 확인

# Real 모드 (Docker DB 필요)
USE_MOCK=false uvicorn server.main:app --reload --port 8002
# 실제 데이터 기반 SummaryCard 확인

# E2E 회귀 테스트
cd frontend && npx playwright test
```

### Part A Checklist

- [ ] mock_data 직접 import 제거
- [ ] `asyncio`, `settings`, `cache_service`, 3개 tool 함수 import 추가
- [ ] `_get_district_meta()` 헬퍼 구현 (Mock/Real 분기)
- [ ] `get_district_summary()` 캐시 확인 로직 추가
- [ ] `asyncio.gather()` 4개 병렬 호출
- [ ] 각 결과 에러 체크 + 부분 실패 시 기본값 처리
- [ ] 집계 로직 (by_hour, top_categories, status, closeRate, summary 텍스트)
- [ ] `dataQuarter` Mock/Real 분기
- [ ] `_format_population()`, `_format_sales()` 유지
- [ ] Mock 모드 테스트 → 기존과 동일 결과
- [ ] Real 모드 테스트 → 실제 DB 데이터 기반 SummaryCard
- [ ] E2E 테스트 회귀 없음

---

## Part B: SHP 폴리곤 적재 + API 폴백

### Context

서울 열린데이터 3개 API가 서비스 종료(ERROR-500) 상태:
- `VwsmTrdarSelngW` (상권 폴리곤) → districts 테이블에 boundary=NULL, center_point=NULL
- `VwsmTrdarPopltnQq` (상주인구) → resident_population에 상주인구 없음
- `VwsmTrdarStorW` (점포 상세) → 이미 VwsmTrdarStorQq로 폴백 동작 중

**핵심 문제**: Real 모드에서 지도에 상권 경계가 표시되지 않음 (boundary NULL)

**해결 전략**:
1. **폴리곤**: OA-15560 SHP 파일 다운로드 → geopandas로 읽기 → 기존 loader로 적재
2. **중심점 보완**: `TbgisTrdarRelm` API (작동 확인됨, 기존 키 사용) → 폴백 체인에 추가
3. **상주인구**: 현행 유지 (직장인구로 커버, 대체 소스 없음)
4. **점포 상세**: 현행 유지 (VwsmTrdarStorQq 폴백 이미 동작)

### 데이터 소스 조사 결과 (2026-03-31)

| 데이터 | 기존 API (종료) | 대체 소스 | 상태 |
|--------|----------------|-----------|------|
| 상권 폴리곤 | VwsmTrdarSelngW | OA-15560 SHP 파일 + TbgisTrdarRelm API | SHP 다운로드 가능, API 작동 확인 |
| 상주인구 | VwsmTrdarPopltnQq | 직접 대체 없음 (직장인구로 커버) | 동일 상권코드 기준 대체 소스 부재 |
| 점포 상세 | VwsmTrdarStorW | VwsmTrdarStorQq (이미 폴백 동작) | 변경 불필요 |

**참고 — 추가 조사한 소스들** (Phase 2+ 고려):
- 서울 실시간 도시데이터 `citydata_ppltn`: 5분 단위 실시간 인구, ~122개 POI, 기존 키로 작동. 단 상권코드와 직접 매핑 안됨 (POI코드 사용)
- SEMAS API (data.go.kr 15012005): 상권 폴리곤 + 점포 목록. data.go.kr 키 별도 발급 필요
- SEMAS CSV (data.go.kr 15083033): 분기별 점포 스냅샷, 개폐업일 없음

### 선행 조건 (사용자 수동)

- [ ] data.seoul.go.kr에서 **OA-15560 SHP ZIP** 다운로드
- [ ] `data/shp/` 디렉토리에 압축 해제
- [ ] geopandas로 컬럼명/CRS/타입 확인 (아래 검증 스크립트)

```python
import geopandas as gpd
gdf = gpd.read_file("data/shp/OA-15560.shp")
print(gdf.columns.tolist())   # 컬럼명 확인
print(gdf.crs)                # EPSG:5181 확인
print(gdf.geom_type.unique()) # Polygon/MultiPolygon
print(len(gdf))               # ~1,650개 예상
```

### 수정 대상 파일

| 파일 | 작업 | 변경량 |
|------|------|--------|
| `.gitignore` | `data/shp/` 추가 | 1줄 |
| `server/server/data/etl/shp_collector.py` | **신규** — SHP → loader-compatible dict 변환 | ~70줄 |
| `server/server/data/etl/runner.py` | `load-shp` 커맨드 추가 + `run`에 `--shp-file` 옵션 | ~50줄 |
| `server/server/data/etl/seoul_opendata.py` | TbgisTrdarRelm 서비스 추가 + collect_districts() 폴백 체인 개선 | ~25줄 |
| `docs/status/current_status.md` | 진행상황 반영 | 갱신 |

**변경하지 않는 파일**:
- `loader.py` — `upsert_districts()`가 이미 `ST_Transform(ST_GeomFromText(:boundary_wkt, 5181), 4326)` 처리, 그대로 호환
- `transformers.py` — `transform_district()`는 API 경로에서만 사용, SHP 경로는 바이패스
- `base.py` — 변경 없음
- `pyproject.toml` — geopandas>=1.0 이미 의존성에 포함
- **프론트엔드** — 변경 없음 (GeoJSON 형식 동일)

### 구현 순서

#### Step B1: `.gitignore` 업데이트

`data/shp/` 추가 (대용량 SHP 바이너리 파일 제외)

#### Step B2: `shp_collector.py` 작성 (신규)

**경로**: `server/server/data/etl/shp_collector.py`

```python
def load_districts_from_shp(shp_path: str | Path, data_quarter: str) -> list[dict]:
```

핵심 로직:
- `geopandas.read_file(shp_path)` — lazy import
- CRS 검증 (EPSG:5181 아니면 reproject)
- MultiPolygon 처리: `max(geom.geoms, key=lambda g: g.area)` 로 최대 폴리곤 추출
- `geom.wkt` → boundary_wkt (EPSG:5181, PostGIS가 4326으로 변환)
- `geom.centroid` → center_wkt (EPSG:5181)
- 컬럼 매핑 dict (SHP 컬럼명 10글자 잘림 대응):
  ```python
  COL_MAP = {
      "TRDAR_CD": ["TRDAR_CD"],
      "TRDAR_CD_NM": ["TRDAR_CD_NM", "TRDAR_CD_N"],
      "TRDAR_SE_CD": ["TRDAR_SE_CD", "TRDAR_SE_C"],
      "SIGNGU_CD": ["SIGNGU_CD", "SIGNGU_CD_"],
      "ADSTRD_CD": ["ADSTRD_CD", "ADSTRD_CD_"],
  }
  ```
- `_resolve_col(target, columns)`: COL_MAP에서 실제 존재하는 컬럼명 찾기
- `DISTRICT_TYPE_MAP` — `transformers.py`에서 import
- NULL/빈 geometry → 로그 + skip
- 반환: `loader.upsert_districts()`와 동일한 dict 형식:
  ```python
  {
      "district_code": str,
      "district_name": str,
      "district_type": str,       # "골목상권"/"발달상권"/"전통시장"/"관광특구"
      "boundary_wkt": str,        # POLYGON((...)) in EPSG:5181
      "center_wkt": str,          # POINT(x y) in EPSG:5181
      "gu_code": str | None,
      "dong_code": str | None,
      "data_quarter": str,
  }
  ```

#### Step B3: `runner.py` 수정

1. **`load-shp` 커맨드 추가** (validate 뒤에):
   ```python
   @app.command(name="load-shp")
   def load_shp(
       shp_file: str = typer.Argument(..., help="Path to SHP file"),
       quarter: str = typer.Argument(..., help="Data quarter (e.g., 2025Q4)"),
       dry_run: bool = typer.Option(False, "--dry-run"),
   ) -> None:
   ```
   - dry_run: 파싱 + 샘플 3개 출력, DB 적재 skip
   - 적재: `DataLoader.upsert_districts(rows)` 재사용

2. **`run` 커맨드에 `--shp-file` 옵션 추가**:
   - `_run_pipeline`에 `shp_file` 파라미터 전달
   - districts 섹션에서 `shp_file`이 있으면 `load_districts_from_shp()` 사용, 없으면 기존 API

#### Step B4: `seoul_opendata.py` 수정

1. SERVICES에 추가: `"district_center": "TbgisTrdarRelm"`

2. 새 메서드:
   ```python
   async def collect_district_centers(self) -> list[dict]:
       return await self._fetch_service("district_center", SERVICES["district_center"])
   ```

3. `collect_districts()` 3단계 폴백 체인:
   ```
   Tier 1: VwsmTrdarSelngW (폴리곤) — ERROR-500 → skip
   Tier 2: TbgisTrdarRelm (중심점, EPSG:5181) — 작동 확인됨
   Tier 3: floating pop에서 추출 (기하정보 없음)
   ```

### 참고할 기존 코드 (SHP 적재)

- `server/server/data/etl/loader.py:27-60` — `upsert_districts()` 입력 dict 형식, ST_Transform SQL
- `server/server/data/etl/transformers.py` — `DISTRICT_TYPE_MAP` (A→골목, D→발달, R→전통시장, G→관광특구)
- `server/server/data/etl/runner.py:45-161` — `_run_pipeline()` 구조, districts 섹션 위치 (line 70-82)
- `server/server/data/etl/seoul_opendata.py:87-95` — 현재 `collect_districts()` 2단계 폴백
- `server/server/data/etl/base.py` — `BaseCollector`, `CollectorError`

### Part B 검증

```bash
# SHP dry-run
python -m server.data.etl.runner load-shp data/shp/OA-15560.shp 2025Q4 --dry-run

# 실제 적재
python -m server.data.etl.runner load-shp data/shp/OA-15560.shp 2025Q4

# 검증
python -m server.data.etl.runner validate 2025Q4
# → districts.boundary NULL % < 2%

# API 확인
curl http://localhost:8002/api/map-data/polygons?bounds=37.4,126.8,37.7,127.2

# 프론트엔드 Real 모드 지도 폴리곤 확인 (USE_MOCK=false)
```

### Part B Checklist

#### 준비
- [ ] OA-15560 SHP ZIP 파일 다운로드 (data.seoul.go.kr)
- [ ] `data/shp/` 디렉토리 생성 + 압축 해제
- [ ] geopandas로 SHP 파일 열어 컬럼명/CRS/타입 확인
- [ ] `.gitignore`에 `data/shp/` 추가 (대용량 파일)

#### 코드 구현
- [ ] `shp_collector.py` 작성 — `load_districts_from_shp()` 함수
- [ ] SHP 컬럼 매핑 검증 (실제 파일 컬럼명 반영)
- [ ] MultiPolygon → Polygon 변환 처리
- [ ] `seoul_opendata.py` — SERVICES에 `district_center` 추가
- [ ] `seoul_opendata.py` — `collect_district_centers()` 메서드 추가
- [ ] `seoul_opendata.py` — `collect_districts()` 3단계 폴백 체인
- [ ] `runner.py` — `load-shp` 커맨드 추가
- [ ] `runner.py` — `run` 커맨드에 `--shp-file` 옵션 추가

#### 검증
- [ ] `load-shp --dry-run` 정상 동작 (파싱 + 샘플 출력)
- [ ] `load-shp` 실제 적재 → districts 테이블 boundary 채워짐
- [ ] `validate 2025Q4` → boundary NULL % < 2%
- [ ] `GET /api/map-data/polygons` → 실제 GeoJSON 폴리곤 반환
- [ ] 브라우저에서 Real 모드 지도 폴리곤 표시 확인
- [ ] TbgisTrdarRelm 폴백 테스트 (SHP 없이 `run --table districts`)
- [ ] 기존 Mock 모드 정상 동작 확인 (회귀 없음)

#### 문서
- [ ] `docs/status/current_status.md` 업데이트

---

## 테스트 시나리오 (Production-Grade)

> **원칙**: 모든 테스트 시나리오를 PASS할 때까지 코드 수정을 반복한다.
> 하나라도 FAIL이면 구현 완료로 간주하지 않는다.

### T0. district_summary Real DB 검증

| ID | 테스트 | 합격 기준 | 검증 방법 |
|----|--------|-----------|-----------|
| T0.1 | Mock 모드 동작 | USE_MOCK=true에서 SummaryCard 정상 렌더링 | 상권 클릭 → SummaryCard 확인 |
| T0.2 | Real 모드 동작 | USE_MOCK=false에서 실제 DB 데이터 기반 SummaryCard | SummaryCard에 실제 데이터 표시 확인 |
| T0.3 | 캐시 동작 | 동일 상권 2회 호출 시 2번째는 캐시 히트 | Redis/메모리 캐시 키 확인 |
| T0.4 | 부분 실패 처리 | 유동인구 없는 상권 호출 시 에러 아닌 부분 데이터 반환 | 에러 키 없이 기본값 포함 확인 |
| T0.5 | E2E 회귀 | 기존 32개 E2E 테스트 전체 PASS | `npx playwright test` |

### T1. SHP Collector 단위 테스트

| ID | 테스트 | 합격 기준 | 검증 방법 |
|----|--------|-----------|-----------|
| T1.1 | SHP 파일 파싱 | `load_districts_from_shp()` 반환 리스트 길이 >= 1,400 | `assert len(rows) >= 1400` |
| T1.2 | 필수 필드 존재 | 모든 row에 `district_code`, `district_name`, `district_type`, `boundary_wkt`, `center_wkt` 키 존재 | 전수 검사 loop |
| T1.3 | district_code 유일성 | 중복 district_code 없음 | `assert len(codes) == len(set(codes))` |
| T1.4 | district_code 형식 | 모든 코드가 숫자 문자열, 길이 5~10 | `assert code.isdigit() and 5 <= len(code) <= 10` |
| T1.5 | district_type 유효값 | 모든 type이 `골목상권`, `발달상권`, `전통시장`, `관광특구` 중 하나 | set 비교 |
| T1.6 | boundary_wkt 유효성 | 모든 WKT가 `POLYGON((`로 시작, `))`로 끝남 | 문자열 검사 |
| T1.7 | boundary 좌표 범위 | 모든 좌표가 서울 EPSG:5181 범위 내 (X: 180,000~220,000 / Y: 430,000~470,000) | 좌표 파싱 + 범위 검사 |
| T1.8 | center_wkt 유효성 | 모든 center가 `POINT(`로 시작, boundary 내부에 위치 | 문자열 검사 |
| T1.9 | MultiPolygon 처리 | MultiPolygon 입력 시 단일 Polygon으로 변환됨 | `assert "MULTI" not in row["boundary_wkt"]` |
| T1.10 | 빈 geometry 스킵 | geometry=None인 feature는 결과에 포함되지 않음 | NULL geometry SHP 테스트 |
| T1.11 | data_quarter 전파 | 모든 row의 `data_quarter`가 입력값과 동일 | `assert all(r["data_quarter"] == quarter for r in rows)` |

### T2. DB 적재 검증 (PostGIS)

| ID | 테스트 | 합격 기준 | 검증 SQL |
|----|--------|-----------|----------|
| T2.1 | 적재 행 수 | `districts` 테이블 행 수 >= 1,400 | `SELECT COUNT(*) FROM districts` |
| T2.2 | boundary NULL 비율 | boundary가 NULL인 행 비율 < **2%** | `SELECT COUNT(*) FILTER (WHERE boundary IS NULL) * 100.0 / NULLIF(COUNT(*), 0) FROM districts` |
| T2.3 | center_point NULL 비율 | center_point가 NULL인 행 비율 < **2%** | 동일 패턴 |
| T2.4 | SRID 정확성 | 모든 boundary의 SRID가 4326 | `SELECT DISTINCT ST_SRID(boundary) FROM districts WHERE boundary IS NOT NULL` → `{4326}` |
| T2.5 | 좌표 변환 정확성 | 변환된 WGS84 좌표가 서울 범위 내 (lat: 37.4~37.7 / lng: 126.7~127.2) | `ST_XMin/YMin/XMax/YMax` 검사 |
| T2.6 | Polygon 유효성 | 모든 boundary가 ST_IsValid = true | `SELECT COUNT(*) FROM districts WHERE boundary IS NOT NULL AND NOT ST_IsValid(boundary)` → 0 |
| T2.7 | UPSERT 멱등성 | 같은 SHP 2회 적재 후 행 수 변화 없음 | 2회 적재 후 COUNT 비교 |
| T2.8 | 기존 데이터 보존 | SHP 적재 후 floating_population FK 무결성 유지 | orphan 0 확인 |
| T2.9 | GiST 인덱스 동작 | 공간 쿼리에 GiST 인덱스 사용 확인 | `EXPLAIN ANALYZE` → Index Scan |

### T3. API 엔드포인트 검증

| ID | 테스트 | 합격 기준 | 검증 방법 |
|----|--------|-----------|-----------|
| T3.1 | GeoJSON 응답 구조 | `GET /api/map-data/polygons` 응답이 유효한 GeoJSON FeatureCollection | `response["type"] == "FeatureCollection"` |
| T3.2 | Feature 필수 필드 | 모든 feature에 district_code, district_name, geometry 존재 | 전수 검사 |
| T3.3 | 좌표 형식 | 좌표가 서울 범위 내 | lng: 126.7~127.2, lat: 37.4~37.7 |
| T3.4 | bounds 필터링 | bounds 파라미터로 영역 제한 동작 | 강남 bounds → 강북 미포함 |
| T3.5 | 응답 시간 | 전체 폴리곤 로딩 **3초 이내** | 시간 측정 |
| T3.6 | 빈 bounds | 서울 외 영역 요청 시 빈 FeatureCollection | `features: []` |
| T3.7 | center 좌표 | 모든 feature의 center가 서울 범위 내 | 값 검증 |

### T4. TbgisTrdarRelm 폴백 검증

| ID | 테스트 | 합격 기준 | 검증 방법 |
|----|--------|-----------|-----------|
| T4.1 | API 호출 성공 | `collect_district_centers()` 반환 길이 >= 1,400 | 단위 테스트 |
| T4.2 | 폴백 체인 동작 | VwsmTrdarSelngW ERROR-500 시 자동 TbgisTrdarRelm 호출 | 로그 확인 |
| T4.3 | center_point 적재 | 폴백 경로로 적재 시 center_point NOT NULL > 95% | DB 검증 |
| T4.4 | 기존 boundary 미훼손 | SHP 적재 후 API 폴백 실행 시 boundary 덮어쓰지 않음 | 비율 변화 없음 확인 |

### T5. 프론트엔드 E2E 검증

| ID | 테스트 | 합격 기준 |
|----|--------|-----------|
| T5.1 | 폴리곤 렌더링 | USE_MOCK=false에서 지도에 폴리곤 표시 |
| T5.2 | 폴리곤 클릭 | 클릭 시 상권 선택 + SummaryCard 렌더링 |
| T5.3 | 뷰포트 로딩 | 지도 이동/줌 시 해당 영역만 로드 |
| T5.4 | Mock 모드 회귀 | USE_MOCK=true 전환 시 기존 5개 Mock 폴리곤 정상 |
| T5.5 | 폴리곤 형태 | 실제 상권 경계 (불규칙 다각형) |

### T6. 데이터 정합성 검증

| ID | 테스트 | 합격 기준 |
|----|--------|-----------|
| T6.1 | 상권코드 일치 | SHP/기존 floating_pop 교집합 >= 1,200개 |
| T6.2 | 상권 유형 분포 | 4가지 유형 모두 존재, 골목상권 최다 |
| T6.3 | 면적 합리성 | 100m2 ~ 5km2 |
| T6.4 | 폴리곤 겹침 | 면적 50% 이상 겹침 없음 |

### 테스트 실행 규칙

1. **전수 PASS 필수**: T0~T6 모든 항목 PASS여야 구현 완료
2. **FAIL 시 수정 반복**: 하나라도 FAIL이면 원인 분석 → 코드 수정 → 재실행
3. **수정 반복 상한**: 동일 테스트 5회 연속 FAIL 시 근본 원인 재검토
4. **회귀 방지**: 수정 시 이전 PASS 항목 FAIL 여부 확인
5. **테스트 자동화**: T0~T4는 pytest, T5는 Playwright 또는 수동
6. **결과 기록**: `docs/status/current_status.md`에 날짜와 함께 기록

---

## 리스크 & 대응

| 리스크 | 대응 |
|--------|------|
| SHP 컬럼명 10글자 잘림 | Step B2 검증 후 COL_MAP 조정 |
| MultiPolygon 존재 | 최대 면적 폴리곤 추출 로직 포함 |
| geopandas Windows 설치 이슈 | pip wheel 사용, 안 되면 conda |
| SHP 파일 구버전 (2023.10) | 1,650개 상권코드 DB 일치 확인 필요 |
| EPSG:5181 좌표 범위 이상 | PostGIS ST_Transform 실패 시 로그 + skip |
| district_summary 순환 import | 하위 Tool 중 district_summary import 없음 (확인 완료) |

---

## 변경하지 않는 것

- **상주인구**: 대체 소스 없음. worker_pop으로 현행 유지
- **점포 상세**: VwsmTrdarStorQq 폴백 이미 동작. 변경 불필요
- **loader.py**: upsert_districts() SQL 완전 호환 — 수정 없음
- **transformers.py**: API 경로 전용 — SHP 경로는 바이패스
- **프론트엔드**: 변경 없음 (GeoJSON 형식 동일)
- **pyproject.toml**: geopandas>=1.0 이미 포함
