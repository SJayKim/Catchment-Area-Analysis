# 데이터 소스 마이그레이션 — 폴리곤 적재 + API 폴백 개선

> 작성일: 2026-03-31
> 대상: Next Items — 미승인 API 대체 소스 연동

## Context

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
| 상권 폴리곤 | VwsmTrdarSelngW | OA-15560 SHP 파일 + TbgisTrdarRelm API | ✅ SHP 다운로드 가능, API 작동 확인 |
| 상주인구 | VwsmTrdarPopltnQq | 직접 대체 없음 (직장인구로 커버) | ⚠️ 동일 상권코드 기준 대체 소스 부재 |
| 점포 상세 | VwsmTrdarStorW | VwsmTrdarStorQq (이미 폴백 동작) | ✅ 변경 불필요 |

**참고 — 추가 조사한 소스들** (Phase 2+ 고려):
- 서울 실시간 도시데이터 `citydata_ppltn`: 5분 단위 실시간 인구, ~122개 POI, 기존 키로 작동. 단 상권코드와 직접 매핑 안됨 (POI코드 사용)
- SEMAS API (data.go.kr 15012005): 상권 폴리곤 + 점포 목록. data.go.kr 키 별도 발급 필요
- SEMAS CSV (data.go.kr 15083033): 분기별 점포 스냅샷, 개폐업일 없음

---

## 수정 대상 파일

| 파일 | 작업 | 변경량 |
|------|------|--------|
| `server/pyproject.toml` | geopandas 의존성 추가 | 1줄 |
| `server/server/data/etl/shp_collector.py` | **신규** — SHP → loader-compatible dict 변환 | ~60줄 |
| `server/server/data/etl/seoul_opendata.py` | TbgisTrdarRelm 서비스 추가 + collect_districts() 폴백 체인 개선 | ~25줄 |
| `server/server/data/etl/runner.py` | `load-shp` 커맨드 추가 + `run`에 `--shp-file` 옵션 | ~40줄 |
| `server/server/config.py` | `etl_shp_dir` 설정 추가 (선택) | 1줄 |
| `docs/status/current_status.md` | 진행상황 반영 | 갱신 |

**변경하지 않는 파일**:
- `loader.py` — `upsert_districts()`가 이미 `ST_Transform(ST_GeomFromText(:boundary_wkt, 5181), 4326)` 처리, 그대로 호환
- `transformers.py` — `transform_district()`는 API 경로에서만 사용, SHP 경로는 바이패스
- `base.py` — 변경 없음

---

## 구현 순서

### Step 1: 의존성 추가
- `server/pyproject.toml`에 `"geopandas>=1.0"` 추가
- `pip install -e ".[dev]"` 재실행

### Step 2: SHP 파일 다운로드 + 검증
- data.seoul.go.kr에서 OA-15560 SHP ZIP 다운로드
- `data/shp/` 디렉토리에 압축 해제
- geopandas로 열어서 컬럼명 확인 (DBF 10글자 제한으로 TRDAR_CD_NM → TRDAR_CD_N 등 잘릴 수 있음)
- CRS = EPSG:5181 확인
- Geometry 타입 확인 (Polygon vs MultiPolygon)

```python
# 검증 스크립트
import geopandas as gpd
gdf = gpd.read_file("data/shp/OA-15560.shp")
print(gdf.columns.tolist())  # 컬럼명 확인
print(gdf.crs)               # EPSG:5181 확인
print(gdf.geom_type.unique()) # Polygon/MultiPolygon
print(len(gdf))              # ~1,650개 예상
```

### Step 3: shp_collector.py 작성 (신규 파일)
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
- 컬럼 매핑 dict (SHP 컬럼명 잘림 대응):
  ```python
  COL_MAP = {
      "TRDAR_CD": ["TRDAR_CD"],
      "TRDAR_CD_NM": ["TRDAR_CD_NM", "TRDAR_CD_N"],
      "TRDAR_SE_CD": ["TRDAR_SE_CD", "TRDAR_SE_C"],
      "SIGNGU_CD": ["SIGNGU_CD"],
      "ADSTRD_CD": ["ADSTRD_CD"],
  }
  ```
- 반환: `loader.upsert_districts()`와 동일한 dict 형식

### Step 4: seoul_opendata.py — TbgisTrdarRelm 폴백 추가

1. SERVICES dict에 추가:
```python
"district_center": "TbgisTrdarRelm",
```

2. 새 메서드:
```python
async def collect_district_centers(self) -> list[dict]:
    return await self._fetch_service("district_center", SERVICES["district_center"])
```

3. `collect_districts()` 폴백 체인 개선:
```
Tier 1: VwsmTrdarSelngW (폴리곤) — ERROR-500 → skip
Tier 2: TbgisTrdarRelm (중심점, EPSG:5181) — 작동 확인됨
Tier 3: floating pop에서 추출 (기하정보 없음)
```

### Step 5: runner.py — load-shp 커맨드 추가

1. 새 커맨드:
```bash
python -m server.data.etl.runner load-shp data/shp/OA-15560.shp 2025Q4
python -m server.data.etl.runner load-shp data/shp/OA-15560.shp 2025Q4 --dry-run
```

2. `run` 커맨드에 `--shp-file` 옵션 추가:
```bash
python -m server.data.etl.runner run 2025Q4 --shp-file data/shp/OA-15560.shp
```

### Step 6: 적재 및 검증

```bash
# 1. SHP dry-run
python -m server.data.etl.runner load-shp data/shp/OA-15560.shp 2025Q4 --dry-run

# 2. 실제 적재
python -m server.data.etl.runner load-shp data/shp/OA-15560.shp 2025Q4

# 3. 검증
python -m server.data.etl.runner validate 2025Q4

# 4. API 확인
curl http://localhost:8002/api/map-data/polygons?bounds=37.4,126.8,37.7,127.2

# 5. 프론트엔드 확인 (USE_MOCK=false)
```

---

## Checklist

### 준비
- [ ] OA-15560 SHP ZIP 파일 다운로드 (data.seoul.go.kr)
- [ ] `data/shp/` 디렉토리 생성 + 압축 해제
- [ ] geopandas로 SHP 파일 열어 컬럼명/CRS/타입 확인
- [ ] `.gitignore`에 `data/shp/` 추가 (대용량 파일)

### 코드 구현
- [ ] `pyproject.toml`에 geopandas 의존성 추가
- [ ] `pip install -e ".[dev]"` 재실행
- [ ] `shp_collector.py` 작성 — `load_districts_from_shp()` 함수
- [ ] SHP 컬럼 매핑 검증 (실제 파일 컬럼명 반영)
- [ ] MultiPolygon → Polygon 변환 처리
- [ ] `seoul_opendata.py` — SERVICES에 `district_center` 추가
- [ ] `seoul_opendata.py` — `collect_district_centers()` 메서드 추가
- [ ] `seoul_opendata.py` — `collect_districts()` 3단계 폴백 체인
- [ ] `runner.py` — `load-shp` 커맨드 추가
- [ ] `runner.py` — `run` 커맨드에 `--shp-file` 옵션 추가
- [ ] `config.py` — `etl_shp_dir` 설정 추가 (선택)

### 검증
- [ ] `load-shp --dry-run` 정상 동작 (파싱 + 샘플 출력)
- [ ] `load-shp` 실제 적재 → districts 테이블 boundary 채워짐
- [ ] `validate 2025Q4` → boundary NULL % < 5%
- [ ] `GET /api/map-data/polygons` → 실제 GeoJSON 폴리곤 반환
- [ ] 브라우저에서 Real 모드 지도 폴리곤 표시 확인
- [ ] TbgisTrdarRelm 폴백 테스트 (SHP 없이 `run --table districts`)
- [ ] 기존 Mock 모드 정상 동작 확인 (회귀 없음)

### 문서
- [ ] `docs/status/current_status.md` 업데이트

---

## 테스트 시나리오 (Production-Grade)

> **원칙**: 모든 테스트 시나리오를 PASS할 때까지 코드 수정을 반복한다.
> 하나라도 FAIL이면 구현 완료로 간주하지 않는다.

### T1. SHP Collector 단위 테스트

| ID | 테스트 | 합격 기준 | 검증 방법 |
|----|--------|-----------|-----------|
| T1.1 | SHP 파일 파싱 | `load_districts_from_shp()` 반환 리스트 길이 ≥ 1,400 | `assert len(rows) >= 1400` |
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
| T2.1 | 적재 행 수 | `districts` 테이블 행 수 ≥ 1,400 | `SELECT COUNT(*) FROM districts` |
| T2.2 | boundary NULL 비율 | boundary가 NULL인 행 비율 < **2%** | `SELECT COUNT(*) FILTER (WHERE boundary IS NULL) * 100.0 / COUNT(*) FROM districts` |
| T2.3 | center_point NULL 비율 | center_point가 NULL인 행 비율 < **2%** | 동일 패턴 |
| T2.4 | SRID 정확성 | 모든 boundary의 SRID가 4326 | `SELECT DISTINCT ST_SRID(boundary) FROM districts WHERE boundary IS NOT NULL` → 결과 `{4326}` |
| T2.5 | 좌표 변환 정확성 | 변환된 WGS84 좌표가 서울 범위 내 (lat: 37.4~37.7 / lng: 126.7~127.2) | `SELECT ST_XMin(boundary), ST_YMin(boundary), ST_XMax(boundary), ST_YMax(boundary) FROM districts WHERE boundary IS NOT NULL LIMIT 10` |
| T2.6 | Polygon 유효성 | 모든 boundary가 ST_IsValid = true | `SELECT COUNT(*) FROM districts WHERE boundary IS NOT NULL AND NOT ST_IsValid(boundary)` → 결과 0 |
| T2.7 | UPSERT 멱등성 | 같은 SHP 2회 적재 후 행 수 변화 없음 | 2회 적재 후 COUNT 비교 |
| T2.8 | 기존 데이터 보존 | SHP 적재 후 floating_population FK 무결성 유지 | `SELECT COUNT(*) FROM floating_population fp WHERE NOT EXISTS (SELECT 1 FROM districts d WHERE d.district_code = fp.district_code)` → 0 |
| T2.9 | GiST 인덱스 동작 | 공간 쿼리에 GiST 인덱스 사용 확인 | `EXPLAIN ANALYZE SELECT * FROM districts WHERE ST_Intersects(boundary, ST_MakeEnvelope(126.9, 37.5, 127.1, 37.6, 4326))` → Index Scan |

### T3. API 엔드포인트 검증

| ID | 테스트 | 합격 기준 | 검증 방법 |
|----|--------|-----------|-----------|
| T3.1 | GeoJSON 응답 구조 | `GET /api/map-data/polygons` 응답이 유효한 GeoJSON FeatureCollection | `response["type"] == "FeatureCollection"` + `len(features) > 0` |
| T3.2 | Feature 필수 필드 | 모든 feature에 `properties.district_code`, `properties.district_name`, `geometry.type`, `geometry.coordinates` 존재 | 전수 검사 |
| T3.3 | 좌표 형식 | `geometry.coordinates[0]`이 `[[lng, lat], ...]` 형식, 모든 좌표 서울 범위 내 | lng: 126.7~127.2, lat: 37.4~37.7 |
| T3.4 | bounds 필터링 | bounds 파라미터 전달 시 해당 영역 내 상권만 반환 | 강남 bounds 전달 → 강북 상권 미포함 확인 |
| T3.5 | 응답 시간 | 전체 폴리곤 로딩 **3초 이내** | `time.time()` 측정 |
| T3.6 | 빈 bounds | 서울 외 영역 요청 시 빈 FeatureCollection 반환 (에러 아님) | `features: []` |
| T3.7 | center 좌표 | 모든 feature의 `properties.center`가 `[lng, lat]` 형식 + 서울 범위 내 | 값 검증 |

### T4. TbgisTrdarRelm 폴백 검증

| ID | 테스트 | 합격 기준 | 검증 방법 |
|----|--------|-----------|-----------|
| T4.1 | API 호출 성공 | `collect_district_centers()` 반환 리스트 길이 ≥ 1,400 | 단위 테스트 |
| T4.2 | 폴백 체인 동작 | VwsmTrdarSelngW ERROR-500 시 자동으로 TbgisTrdarRelm 호출 | 로그에 "trying TbgisTrdarRelm" 메시지 확인 |
| T4.3 | center_point 적재 | 폴백 경로로 districts 적재 시 center_point NOT NULL 비율 > 95% | DB 검증 |
| T4.4 | 기존 boundary 미훼손 | SHP로 boundary 적재 후 → API 폴백 실행 시 기존 boundary 덮어쓰지 않음 | boundary NOT NULL 비율 변화 없음 확인 |

### T5. 프론트엔드 E2E 검증

| ID | 테스트 | 합격 기준 | 검증 방법 |
|----|--------|-----------|-----------|
| T5.1 | 폴리곤 렌더링 | `USE_MOCK=false` 상태에서 지도에 상권 폴리곤이 표시됨 | Playwright 스크린샷 또는 수동 확인 |
| T5.2 | 폴리곤 클릭 | 폴리곤 클릭 시 상권 선택 + AI Agent 자동 질의 트리거 | 클릭 → SummaryCard 렌더링 확인 |
| T5.3 | 뷰포트 로딩 | 지도 이동/줌 시 해당 영역 폴리곤만 로드 (전체 로드 아님) | Network 탭에서 bounds 파라미터 변경 확인 |
| T5.4 | Mock 모드 회귀 | `USE_MOCK=true`로 전환 시 기존 5개 Mock 폴리곤 정상 동작 | Mock 모드 E2E 전체 통과 |
| T5.5 | 폴리곤 형태 | 폴리곤이 실제 상권 경계 형태 (사각형이 아닌 불규칙 다각형) | 시각적 확인 |

### T6. 데이터 정합성 검증

| ID | 테스트 | 합격 기준 | 검증 SQL/방법 |
|----|--------|-----------|---------------|
| T6.1 | 상권코드 일치 | SHP districts와 기존 floating_population의 district_code 교집합 ≥ 1,200개 | `SELECT COUNT(DISTINCT fp.district_code) FROM floating_population fp JOIN districts d ON fp.district_code = d.district_code WHERE d.boundary IS NOT NULL` |
| T6.2 | 상권 유형 분포 | 4가지 유형 모두 존재, 골목상권이 가장 많음 | `SELECT district_type, COUNT(*) FROM districts GROUP BY district_type ORDER BY 2 DESC` |
| T6.3 | 면적 합리성 | 변환된 폴리곤 면적이 100m² ~ 5km² 범위 | `SELECT district_code, ST_Area(boundary::geography) FROM districts WHERE boundary IS NOT NULL` 범위 검사 |
| T6.4 | 폴리곤 겹침 | 임의 10개 상권 쌍에서 면적 50% 이상 겹치는 케이스 없음 | `ST_Intersection` + `ST_Area` 비교 |

### 테스트 실행 규칙

1. **전수 PASS 필수**: T1~T6 모든 테스트 항목이 PASS여야 구현 완료
2. **FAIL 시 수정 반복**: 하나라도 FAIL이면 원인 분석 → 코드 수정 → 전체 테스트 재실행
3. **수정 반복 상한**: 동일 테스트 5회 연속 FAIL 시 근본 원인 재검토 (데이터 문제 vs 코드 문제)
4. **회귀 방지**: 수정 시 이전 PASS 항목이 FAIL로 바뀌지 않았는지 반드시 확인
5. **테스트 자동화**: T1~T4는 pytest로 자동화, T5는 Playwright 또는 수동 체크리스트
6. **결과 기록**: 각 테스트 실행 결과를 `docs/status/current_status.md`에 날짜와 함께 기록

---

## 리스크 & 대응

| 리스크 | 대응 |
|--------|------|
| SHP 컬럼명 10글자 잘림 | Step 2에서 확인 후 COL_MAP 조정 |
| MultiPolygon 존재 | 최대 면적 폴리곤 추출 로직 포함 |
| geopandas Windows 설치 이슈 | pip wheel 사용, 안 되면 conda |
| SHP 파일 구버전 (2023.10) | 1,650개 상권코드가 현재 DB와 일치하는지 확인 필요 |
| EPSG:5181 좌표 범위 이상 | PostGIS ST_Transform 실패 시 로그 + skip |

---

## 변경하지 않는 것

- **상주인구**: 대체 소스 없음. worker_pop으로 현행 유지
- **점포 상세**: VwsmTrdarStorQq 폴백 이미 동작. 변경 불필요
- **loader.py**: upsert_districts() SQL 완전 호환 — 수정 없음
- **transformers.py**: API 경로 전용 — SHP 경로는 바이패스
- **프론트엔드**: 변경 없음 (GeoJSON 형식 동일)
