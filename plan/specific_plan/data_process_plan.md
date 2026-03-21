# MarketScope AI - 데이터 구축 & 처리 구현 계획

> 작성일: 2026-03-21
> 기준: specs/05_mcp_servers.md, specs/07_data_pipeline.md
> API 키 확보 현황: 서울 열린데이터(✅), 카카오(✅), KOSIS(✅), Gemini(✅), data.go.kr(미발급)

---

## 전체 구조

```
외부 API  →  Collector  →  Preprocessor  →  DB/Cache  →  MCP Server  →  Agent
```

현재 상태: Agent(✅) → MCP Client(✅) → **MCP Server(❌) → Collector(❌) → DB(❌)** 순서로 구축 필요

---

## Phase 구분

| Phase | 목표 | 비고 |
|-------|------|------|
| **D0** | DB 스키마 + 코드 매핑 테이블 | 모든 데이터의 기반 |
| **D1** | Collector 구현 (API → Raw Data) | 외부 API 호출 + 저장 |
| **D2** | Preprocessor 구현 | 좌표 변환, 코드 매핑, 이상치 |
| **D3** | MCP Server 구현 (Public Data) | 에이전트가 실제 호출하는 도구 |
| **D4** | MCP Server 구현 (Maps/GIS) | 카카오 API 기반 지도 도구 |
| **D5** | 캐싱 + 스케줄링 + 모니터링 | Redis 캐시, APScheduler |

---

## D0: 데이터베이스 스키마 + 코드 매핑

### D0-1. PostgreSQL + PostGIS 환경 설정
- [ ] Docker Compose로 PostgreSQL 15 + PostGIS 3.4 구성
- [ ] `docker-compose.yml` 작성 (postgres + redis)
- [ ] Alembic 초기 설정 (`alembic init`, `alembic.ini`, `env.py`)
- [ ] SQLAlchemy 2.0 async 엔진 구성 (`app/db/session.py` 실구현)

### D0-2. 핵심 테이블 마이그레이션
- [ ] `districts` 테이블 (상권 기본정보, GEOMETRY boundary)
- [ ] `population_stats` 테이블 (YEAR 파티션 2020-2027)
- [ ] `revenue_stats` 테이블 (YEAR 파티션 2020-2027)
- [ ] `stores` 테이블 (GIST 인덱스 on location)
- [ ] `transit_stats` 테이블 (YEAR 파티션 2023-2027)
- [ ] `code_mappings` 테이블 (행정동↔법정동↔상권코드)
- [ ] `unit_prices` 테이블 (업종별 객단가, 수동 입력)
- [ ] `startup_costs` 테이블 (업종별 창업비용, 수동 입력)
- [ ] `analysis_sessions` 테이블 (분석 결과 저장)
- [ ] `collection_logs` 테이블 (수집 이력)

### D0-3. ORM 모델 구현
- [ ] `app/db/models.py` — SQLAlchemy ORM 모델 전체 구현
- [ ] `app/db/repositories.py` — Repository 패턴 CRUD 구현
- [ ] `app/db/session.py` — AsyncSession 팩토리 실구현

### D0-4. 코드 매핑 데이터 구축
- [ ] 행정안전부 행정동-법정동 연계표 CSV 다운로드
- [ ] SEMAS 상권코드 목록 CSV 다운로드 (data.go.kr #15083033)
- [ ] 업종코드 CSV 다운로드 (대분류 8 > 중분류 67 > 소분류 746)
- [ ] `code_mappings` 테이블에 초기 데이터 적재 스크립트 작성
- [ ] `districts` 테이블에 서울 상권 데이터 적재

**검증 기준**:
- `code_mappings` 레코드 수 ≥ 5,000 (서울 기준)
- `districts` WHERE city_name='서울' 레코드 수 ≥ 1,000
- 모든 테이블 CREATE 성공, 파티션 정상 동작

---

## D1: Collector 구현 (외부 API → DB)

### D1-1. BaseCollector 추상 클래스
- [ ] `app/collectors/base.py` 작성
  - `_call_api_with_retry()` — 3회 재시도 + 지수 백오프
  - `_handle_rate_limit()` — 429 응답 처리
  - `_log_collection()` — collection_logs 기록
  - `_validate_response()` — 응답 구조 검증
  - httpx.AsyncClient 설정: timeout 30s, max_connections 5

### D1-2. SemasCollector (소상공인 상권정보)
- [ ] `app/collectors/semas.py` 작성
- [ ] **API 기본 정보**:
  - Base URL: `https://apis.data.go.kr/B553077/api/open`
  - 인증: `serviceKey` URL 파라미터
  - 일일 제한: 1,000건 (확장 신청 시 100,000건)
- [ ] 엔드포인트 구현:
  - [ ] `/trdarFlorpopQq` — 유동인구 (분기별)
  - [ ] `/trdarSelngQq` — 추정매출 (분기별)
  - [ ] `/storeListInArea` — 점포 목록
  - [ ] `/storeListInRadius` — 반경 점포 검색
- [ ] 응답 파싱: `body.items.item` (배열 or 단일 객체 분기 처리)
- [ ] 일일 호출량 제어 (200건/일 for population)
- [ ] `stdrYyquCd` 포맷 변환 ("20244" = 2024 Q4)

### D1-3. SeoulCollector (서울 열린데이터)
- [ ] `app/collectors/seoul.py` 작성
- [ ] **API 기본 정보**:
  - Base URL: `http://openapi.seoul.go.kr:8088/{API_KEY}/json`
  - 인증: URL 경로에 API 키 포함
- [ ] 엔드포인트 구현:
  - [ ] `/SPOP_LOCAL_RESD_DONG/{start}/{end}/{YYYYMM}` — 생활인구
  - [ ] `/CardSubwayStatsNew/{start}/{end}/{YYYYMM01}` — 지하철 승하차
  - [ ] `/tbgiCardInfo/{start}/{end}/{YYYY}/{MM}` — 카드매출
- [ ] 페이지네이션 처리 (1000건씩 반복 조회)
- [ ] `list_total_count` 기반 전체 건수 확인 후 루프

### D1-4. KosisCollector (통계청)
- [ ] `app/collectors/kosis.py` 작성
- [ ] **API 기본 정보**:
  - Base URL: `https://kosis.kr/openapi/Param/statisticsParameterData.do`
  - 인증: `apiKey` 쿼리 파라미터
- [ ] 엔드포인트:
  - [ ] `DT_1B040A3` — 주민등록인구 (행정구역별 성별)
- [ ] On-demand 조회 (스케줄 X, MCP 서버에서 직접 호출)

**검증 기준**:
- 각 Collector로 1건 이상 실제 API 호출 → DB 저장 성공
- collection_logs에 SUCCESS 기록
- 429 에러 시 재시도 로직 동작 확인

---

## D2: Preprocessor 구현

### D2-1. 좌표 변환기
- [ ] `app/preprocessors/coordinate_transformer.py`
  - TM(EPSG:2097) → WGS84(EPSG:4326) 변환
  - UTM-K(EPSG:5178/5179) → WGS84 변환
  - pyproj 기반 Transformer 캐싱
  - 정밀도: 소수점 6자리 (≒0.1m)

### D2-2. 코드 매퍼
- [ ] `app/preprocessors/code_mapper.py`
  - 행정동코드 → 법정동코드 → 상권코드 변환
  - 인메모리 캐시 (~10,000건 로드)
  - `get_district_by_dong(admin_dong_code)` → district_code
  - `get_dong_by_district(district_code)` → admin_dong_code

### D2-3. 결측치 처리기
- [ ] `app/preprocessors/missing_handler.py`
  - 인구/매출 0 대체 규칙
  - Forward fill (이전 분기 데이터 사용)
  - 일별 분배 (합계만 있고 일별 없을 때 균등 분배)

### D2-4. 이상치 탐지기
- [ ] `app/preprocessors/outlier_detector.py`
  - IQR 기반 탐지 (Q1-1.5*IQR ~ Q3+1.5*IQR)
  - 시계열 이상치 (|현재-이전| > 3σ)
  - Zero-ratio 탐지 (50% 이상 0값 → 플래그)
  - anomaly_flag 마킹, 로그 기록

**검증 기준**:
- TM 좌표 → WGS84 변환 결과가 서울 범위 내 (lat 37.4~37.7, lng 126.8~127.2)
- 코드 매핑: 강남구 → district_code 변환 성공
- 결측치/이상치 처리 후 NULL 비율 < 5%

---

## D3: MCP Server — Public Data (공공데이터)

### D3-1. FastMCP 서버 기본 구조
- [ ] `app/mcp_servers/public_data/server.py` — FastMCP 앱 설정
- [ ] 서버 설정: port 5100, health check 엔드포인트
- [ ] DB 연결 풀 설정 (SQLAlchemy async)
- [ ] Redis 캐시 클라이언트 설정

### D3-2. 공공데이터 도구 구현 (8개)
- [ ] `get_floating_population(district_code, quarter)` — 유동인구
  - DB 조회 → 없으면 SEMAS API 직접 호출 → 캐시
  - Redis 키: `pub:fp:{district}:{quarter}`, TTL 7일
- [ ] `get_estimated_revenue(district_code, industry_code, quarter)` — 추정매출
  - Redis 키: `pub:rev:{district}:{industry}:{quarter}`, TTL 7일
- [ ] `get_store_list(lat, lng, radius_m, industry_code?)` — 점포 목록
  - PostGIS ST_DWithin 쿼리 또는 SEMAS 반경 검색
  - Redis 키: `pub:store:{lat_3d}:{lng_3d}:{radius}:{industry}`, TTL 24시간
- [ ] `get_store_count_change(district_code, industry_code, quarters[])` — 점포 증감
  - Redis 키: `pub:scc:{district}:{industry}:{quarters_md5}`, TTL 7일
- [ ] `get_resident_population(region_code)` — 주민등록인구 (KOSIS 직접 호출)
  - Redis 키: `pub:rpop:{region}`, TTL 30일
- [ ] `get_worker_population(region_code)` — 직장인구 (KOSIS 직접 호출)
  - Redis 키: `pub:wpop:{region}`, TTL 30일
- [ ] `get_seoul_living_population(dong_code, date)` — 서울 생활인구
  - Redis 키: `pub:slp:{dong}:{date}`, TTL 24시간
- [ ] `get_card_sales(dong_code, industry_code, quarter)` — 카드매출
  - Redis 키: `pub:card:{dong}:{industry}:{quarter}`, TTL 7일

### D3-3. 리소스 엔드포인트 (3개)
- [ ] `public-data://industry-codes` — 업종코드 CSV (746건)
- [ ] `public-data://district-codes` — 상권코드 CSV (~3,000건)
- [ ] `public-data://dong-codes` — 행정동코드 CSV (~7,000건)

**검증 기준**:
- `http://localhost:5100/tools/list` → 8개 도구 목록 반환
- `http://localhost:5100/health` → 200 OK
- 각 도구 1건 이상 호출 → 정상 JSON 응답
- Redis 캐시 히트 테스트 (같은 요청 2회 → 2회차 latency < 10ms)

---

## D4: MCP Server — Maps/GIS (지도)

### D4-1. FastMCP 서버 기본 구조
- [ ] `app/mcp_servers/maps/server.py` — 카카오 API 클라이언트 설정
- [ ] 서버 설정: port 5101
- [ ] 카카오 API 인증 헤더: `Authorization: KakaoAK {key}`

### D4-2. 지도 도구 구현 (7개)
- [ ] `geocode(address)` — 주소 → 좌표 변환
  - 카카오 `/v2/local/search/address.json`
  - Redis 키: `maps:geo:{address_md5}`, TTL 30일
- [ ] `reverse_geocode(lat, lng)` — 좌표 → 주소 변환
  - 카카오 `/v2/local/geo/coord2address.json`
  - Redis 키: `maps:rgeo:{lat_5d}:{lng_5d}`, TTL 30일
- [ ] `search_nearby(lat, lng, radius_m, category_code)` — 주변 검색
  - 카카오 `/v2/local/search/category.json`
  - Redis 키: `maps:nearby:{lat_3d}:{lng_3d}:{radius}:{category}`, TTL 6시간
- [ ] `search_keyword(keyword, lat?, lng?, radius_m?)` — 키워드 검색
  - 카카오 `/v2/local/search/keyword.json`
  - Redis 키: `maps:kw:{keyword_md5}:{lat_3d}:{lng_3d}:{radius}`, TTL 6시간
- [ ] `get_walking_route(origin_lat, origin_lng, dest_lat, dest_lng)` — 도보 경로
  - 카카오 모빌리티 `/v1/directions`
  - Redis 키: `maps:walk:{olat}:{olng}:{dlat}:{dlng}`, TTL 7일
- [ ] `get_transit_nearby(lat, lng, radius_m)` — 주변 교통
  - 카카오 카테고리 검색 (SW8=지하철역 + BK9=버스정류장)
  - + DB transit_stats 조회 (승하차 데이터 결합)
  - Redis 키: `maps:transit:{lat_3d}:{lng_3d}:{radius}`, TTL 24시간
- [ ] `get_category_pois(lat, lng, radius_m, category)` — 카테고리별 POI
  - 카카오 카테고리 검색
  - Redis 키: `maps:cat:{lat_3d}:{lng_3d}:{radius}:{category}`, TTL 6시간

**검증 기준**:
- `geocode("강남역")` → lat/lng 반환 (37.497~, 127.027~)
- `search_nearby(37.497, 127.027, 500, "CE7")` → 카페 목록 반환
- `search_keyword("스타벅스 강남")` → 결과 반환
- 카카오 API 일일 300,000건 내 호출량 모니터링

---

## D5: 캐싱 + 스케줄링 + 모니터링

### D5-1. Redis 캐싱 레이어
- [ ] Docker Compose에 Redis 추가
- [ ] `app/cache/redis_client.py` — async Redis 클라이언트
- [ ] `cached_call(key, ttl, fetch_fn)` 헬퍼 함수
- [ ] 캐시 키 설계 패턴 적용: `{server}:{tool}:{params}`

### D5-2. APScheduler 배치 수집
- [ ] `app/scheduler/jobs.py` — 수집 작업 정의
- [ ] 스케줄 등록:
  - [ ] `semas_population_quarterly` — 분기 15일 06:00
  - [ ] `semas_revenue_quarterly` — 분기 1일 07:00
  - [ ] `semas_stores_quarterly` — 분기 20일 08:00
  - [ ] `seoul_population_monthly` — 매월 15일 12:00
  - [ ] `seoul_subway_monthly` — 매월 15일 11:00
  - [ ] `seoul_card_sales_monthly` — 매월 15일 13:00
  - [ ] `refresh_mv_monthly` — 매월 25일 02:00 (Materialized View)
  - [ ] `data_quality_daily` — 매일 03:00

### D5-3. 데이터 품질 모니터링
- [ ] `app/monitoring/quality_checker.py`
  - Freshness 체크 (population: 100일, transit: 35일)
  - Completeness 체크 (NULL 비율 < 5%)
  - Anomaly 체크 (300%+ 변동 플래그)
  - 참조 무결성 (orphan district_code)
- [ ] collection_logs 기반 수집 현황 대시보드

**검증 기준**:
- Redis 연결 정상, SET/GET 동작
- APScheduler 작업 등록 확인 (dry-run)
- 품질 체크 실행 → QualityReport 생성

---

## 구현 순서 & 의존성

```
D0 (DB 스키마)
  ├─→ D1 (Collector) ─→ D2 (Preprocessor)
  │                           │
  │                           ▼
  │                    D3 (MCP Public Data)
  │                           │
  └───────────────────→ D4 (MCP Maps/GIS)  ← 카카오 API만 사용, DB 의존 낮음
                              │
                              ▼
                        D5 (캐싱/스케줄링)
```

### 빠른 검증 경로 (DB 없이 먼저 테스트)

에이전트 → MCP 서버 E2E를 빠르게 검증하려면:

```
[빠른 경로] D4 (Maps MCP) → 카카오 API 키 이미 확보, DB 불필요
[빠른 경로] D3 일부 → Seoul/KOSIS API 직접 호출 (DB 캐시 없이)
```

1. **D4부터 먼저** 구현하면 Location 에이전트를 가장 빨리 테스트 가능
2. **D3 일부** (get_seoul_living_population, get_resident_population)는 DB 없이 API 직접 호출로 구현 가능
3. D0~D2는 병렬로 진행

---

## 파일 구조 (신규 생성 예정)

```
marketscope/
├── docker-compose.yml              # D0-1
├── alembic/                        # D0-1
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
├── app/
│   ├── db/
│   │   ├── models.py               # D0-3 (실구현)
│   │   ├── repositories.py         # D0-3 (실구현)
│   │   └── session.py              # D0-3 (실구현)
│   ├── collectors/                  # D1 (신규)
│   │   ├── __init__.py
│   │   ├── base.py                 # D1-1
│   │   ├── semas.py                # D1-2
│   │   ├── seoul.py                # D1-3
│   │   └── kosis.py                # D1-4
│   ├── preprocessors/              # D2 (신규)
│   │   ├── __init__.py
│   │   ├── coordinate_transformer.py  # D2-1
│   │   ├── code_mapper.py            # D2-2
│   │   ├── missing_handler.py        # D2-3
│   │   └── outlier_detector.py       # D2-4
│   ├── mcp_servers/                # D3, D4 (신규)
│   │   ├── __init__.py
│   │   ├── public_data/
│   │   │   ├── __init__.py
│   │   │   ├── server.py           # D3-1
│   │   │   ├── tools.py            # D3-2
│   │   │   └── resources.py        # D3-3
│   │   └── maps/
│   │       ├── __init__.py
│   │       ├── server.py           # D4-1
│   │       └── tools.py            # D4-2
│   ├── cache/                      # D5 (신규)
│   │   ├── __init__.py
│   │   └── redis_client.py         # D5-1
│   ├── scheduler/                  # D5 (신규)
│   │   ├── __init__.py
│   │   └── jobs.py                 # D5-2
│   └── monitoring/                 # D5 (신규)
│       ├── __init__.py
│       └── quality_checker.py      # D5-3
└── data/                           # D0-4 (신규, CSV 원본)
    ├── admin_dong_codes.csv
    ├── legal_dong_codes.csv
    ├── district_codes.csv
    └── industry_codes.csv
```

---

## 필요 추가 패키지

```toml
# pyproject.toml에 추가
"alembic>=1.13.0",
"pyproj>=3.6.0",
"apscheduler>=3.10.0",
"geoalchemy2>=0.15.0",    # PostGIS 지원
"fastmcp>=0.1.0",         # MCP 서버 프레임워크
```

---

## API 키 현황 & .env 매핑

| API | 키 확보 | .env 변수 | 용도 |
|-----|---------|-----------|------|
| 서울 열린데이터 | ✅ | `DATA_API_SEOUL_OPEN_DATA_KEY` | D1-3, D3 |
| 카카오 REST API | ✅ | `DATA_API_KAKAO_REST_KEY` | D4 |
| KOSIS | ✅ | `DATA_API_KOSIS_KEY` | D1-4, D3 |
| Gemini (LLM) | ✅ | `GOOGLE_API_KEY` | 에이전트 LLM |
| data.go.kr (SEMAS) | ❌ 미발급 | `DATA_API_PUBLIC_DATA_KEY` | D1-2, D3 |

**data.go.kr 키 미발급 시**: D1-2(SemasCollector), D3 일부 도구 사용 불가
→ 서울 열린데이터 + KOSIS로 대체 가능한 범위 먼저 구현
