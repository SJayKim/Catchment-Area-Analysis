# Data Layer

> PostgreSQL 16 + PostGIS 3.4, Redis 7, SQLAlchemy async Repository 패턴. ETL 은 서울 열린데이터 + SHP + CSV.

## 1. 레포지토리 구조 (`server/server/repositories/`)

```
repositories/
├── protocols.py       # 9개 프로토콜 (Protocol[T])
├── data_access.py     # DataAccess 파사드
├── mock/              # JSON 기반 인-메모리 구현
│   ├── districts.py / floating_population.py / …
│   └── factory.py
└── real/              # SQLAlchemy async 구현
    ├── districts.py / floating_population.py / …
    ├── _units.py       # 분기→월 단위 변환 유틸
    └── factory.py
```

### 9개 프로토콜

| Protocol | 주요 메서드 | 사용 Tool |
|---|---|---|
| `DistrictRepository` | `resolve(name)`, `detect(names[])`, `list(search, type)`, `detail(code)`, `polygons(bounds)` | F01, 모든 Tool |
| `FloatingPopulationRepository` | `by_district(code, quarter)`, `anomaly_detect(code)` | F03, F06 |
| `EstimatedSalesRepository` | `by_district(code, quarter, category?)` | F03, F04, F09 |
| `StoreRepository` | `info(code, category?)`, `history(code)` | F03, F04, F07, F08 |
| `PopulationRepository` | `info(code, quarter)` | F03, F07 |
| `ComparisonRepository` | `compare(codes[])` | F05 |
| `RecommendationRepository` | `recommend(code, budget?)` | F07 |
| `SimulationRepository` | `estimate(code, category, unit_price?)` | F09 |
| `HeatmapRepository` | `by_time_slot(slot, quarter)`, `all_slots(quarter)` | F06 |
| `BenchmarkRepository` | `for_type(district_type)` | 벤치마킹 |

### Mock ↔ Real 동등성

- Mock 은 `agent/tools/mock/*.json` 또는 `repositories/mock/*.py` 에서 JSON fixture 사용
- Mock 에서 **DB/Redis 연결 시도 금지** (`memory/feedback_mock_real_pattern.md`)
- Real Repository 는 `settings.use_mock=false` 일 때만 SQLAlchemy 세션 주입

## 2. DB 스키마

### 2.1 핵심 테이블

```sql
-- 상권 영역 (1,650개)
districts (
  code            VARCHAR(20) PK,
  name            VARCHAR(100),
  type            VARCHAR(20),           -- 골목/발달/전통/관광특구
  boundary        GEOMETRY(POLYGON,4326),
  center_point    GEOMETRY(POINT,4326),
  gu_code         VARCHAR(10),
  dong_code       VARCHAR(10),
  quarter         VARCHAR(10),           -- 데이터 기준 분기
  created_at      TIMESTAMPTZ
);
CREATE INDEX idx_districts_boundary ON districts USING GIST(boundary);

-- 유동인구 (9,888행 / 2025Q4)
floating_population (
  id              BIGSERIAL PK,
  district_code   VARCHAR(20) FK,
  quarter         VARCHAR(10),
  time_slot       SMALLINT,              -- 0~23
  total, male, female  INT,
  age_10, age_20, age_30, age_40, age_50, age_60plus  INT,
  UNIQUE(district_code, quarter, time_slot)
);

-- 추정매출 (21,333행 / 2025Q4)  ⚠ monthly_sales = 분기 누적 (단위 오해 주의)
estimated_sales (
  id BIGSERIAL PK,
  district_code FK, category_code, category_name, quarter,
  monthly_sales   BIGINT,                -- 실제로는 분기 누적(원). Repo에서 /3 월 환산
  sales_count     INT,
  weekday_sales, weekend_sales  BIGINT,
  male_sales, female_sales BIGINT,
  age_*_sales BIGINT,
  time_1_sales ~ time_6_sales BIGINT,    -- 6시간대 구간
  UNIQUE(district_code, category_code, quarter)
);

-- 점포 현황 (75,985행 / 2025Q4)
stores (
  id BIGSERIAL PK,
  district_code FK, category_code, category_name, quarter,
  store_count, open_count, close_count, franchise_count  INT,
  UNIQUE(district_code, category_code, quarter)
);

-- 점포 이력
store_history (
  id BIGSERIAL PK,
  district_code FK, address, category_code, category_name,
  open_date DATE, close_date DATE, duration_months INT
);
-- ⚠ 실데이터 적재 미완 — data.go.kr API 미연동 (Phase 2 대기)

-- 상주/직장 인구 (39,288행)
resident_population (
  id BIGSERIAL PK,
  district_code FK, quarter, pop_type VARCHAR(10),   -- resident / worker
  age_group, gender, population,
  UNIQUE(district_code, quarter, pop_type, age_group, gender)
);

-- 업종 메타 (category_resolver + F07/F09 사용)
category_metadata (
  code            VARCHAR(20) PK,
  name            VARCHAR(100),
  major_category  VARCHAR(100),
  avg_startup_cost BIGINT,
  default_unit_price BIGINT,
  aliases         TEXT[]                 -- 한국어 키워드
);
```

### 2.2 세션/채팅 (인메모리 → DB 이관은 out of scope)

현재 `chat_sessions` / `chat_messages` 테이블은 스키마만 있고 사용하지 않는다. 세션 저장소는 백엔드 인메모리 (`backend.md §7`).

## 3. Alembic 마이그레이션

```
server/alembic/versions/
├── 001_initial_schema.py           # 핵심 테이블 + PostGIS 인덱스
├── 002_add_default_unit_price.py   # F09 simulation 지원
└── 003_add_category_aliases.py     # category_resolver 확장
```

- `alembic.ini` + `server/alembic/env.py` 는 `database_url_sync` 사용
- 운영 배포 이슈 회피용 `server/scripts/cleanup_alembic.py` 존재 (시드 덤프에서 stale `alembic_version` 제거)

## 4. ETL 파이프라인 (`server/server/data/etl/`)

```
etl/
├── runner.py             # CLI: python -m server.data.etl.runner run 2025Q4
├── base.py               # httpx async client + tenacity 재시도
├── seoul_opendata.py     # 서울 열린데이터 4개 서비스
├── shp_collector.py      # SHP → PostGIS POLYGON
├── csv_collector.py      # 상주인구 OA-15584
├── transformers.py       # 좌표변환 / unpivot / 성별·연령 매핑
├── loader.py             # batch_size=1000 UPSERT
└── seed_category_metadata.py   # category_metadata 시드
```

### 4.1 데이터 소스

| 테이블 | 서비스 | 제공 기관 | 갱신 |
|---|---|---|---|
| `districts` | SHP (서울 상권 영역) | 서울시 | 분기 |
| `floating_population` | `VwsmTrdarFlpopQq` | 서울 열린데이터 | 분기 |
| `estimated_sales` | `VwsmTrdarSelngQq` | 서울 열린데이터 | 분기 |
| `stores` | `VwsmTrdarStorQq` | 서울 열린데이터 | 분기 |
| `resident_population` (직장) | `VwsmTrdarWrcPopltnQq` | 서울 열린데이터 | 분기 |
| `resident_population` (상주) | OA-15584 CSV | 서울 열린데이터 | 분기 |
| `store_history` | data.go.kr 점포 이력 | 공공데이터포털 | ⏳ 미연동 |

### 4.2 ETL 제약

- 페이지 크기 1000, 최대 재시도 3회, 타임아웃 30s, 동시 3 요청
- asyncpg copy batch 는 1000 이하 유지 (`memory/feedback_asyncpg_batch.md`)
- UPSERT: `ON CONFLICT (district_code, category_code, quarter) DO UPDATE`

### 4.3 스케줄러

- 현재 CLI 수동 실행만 지원
- GitHub Actions cron 또는 Celery Beat 은 향후 계획

## 5. 캐시 규약

| 키 패턴 | TTL | 저장 내용 |
|---|---|---|
| `report:{district_code}:{quarter}` | 24h | Tool 결과 병합 캐시 |
| `heatmap:{quarter}:{slot}` | 24h | 히트맵 시간대별 포인트 |
| `category:metadata` | 프로세스 수명 | 싱글톤 |

Redis 장애 시 graceful degradation — 함수는 `None` 반환, 호출측은 DB 재조회.

## 6. 운영 스크립트

| 스크립트 | 용도 |
|---|---|
| `scripts/verify_sales_units.py` | 매출 단위(분기→월) 변환이 정상인지 검증 |
| `scripts/flush_cache.py` | Redis 캐시 초기화 (매출 단위 fix 후 stale 제거) |
| `scripts/validate_env.py` | 필수 환경변수 누락 가드 |
| `scripts/generate_seed.py` | seed 덤프 생성 |
| `scripts/backup_db.sh` | DB 덤프 백업 |
| `scripts/setup_db.py` | 신규 환경 DB 초기화 |
| `server/scripts/cleanup_alembic.py` | alembic_version 정리 |

## 7. 데이터 품질 주의사항

- **매출 단위**: DB `monthly_sales` 컬럼은 분기 누적. Repository 가 `/3` 월 환산 후 반환. 직접 쿼리 시 혼동 주의.
- **polygon 누락**: SHP 적재 전 districts 는 boundary NULL → Circle Overlay fallback 필요
- **store_history 미적재**: Real 모드에서 F08 리스크는 `stores` 개폐업 집계로 파생 계산
- **한글 조사 strip**: 검색 시 `"강남역을"`, `"홍대에"` 등 조사 제거 (`memory/feedback_korean_particles.md`)
