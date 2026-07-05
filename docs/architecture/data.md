# Data Layer

> PostgreSQL 16 + PostGIS 3.4, Redis 7, SQLAlchemy async Repository 패턴. ETL 은 서울 열린데이터 + SHP + CSV.

## 1. 레포지토리 구조 (`server/server/repositories/`)

```
repositories/
├── protocols.py       # 10개 프로토콜 (평범한 Protocol 상속, 제네릭 아님)
├── data_access.py     # DataAccess 파사드 (10개 repo 번들)
├── mock/              # JSON 기반 인-메모리 구현
│   ├── districts.py / floating_population.py / …
│   └── factory.py
└── real/              # SQLAlchemy async 구현
    ├── districts.py / floating_population.py / …
    ├── _units.py       # MONTHS_PER_QUARTER=3 (분기→월 환산 상수)
    └── factory.py
```

### 10개 프로토콜

> 메서드명은 `protocols.py` 실제 시그니처 기준.

| Protocol | 주요 메서드 | 사용 Tool |
|---|---|---|
| `DistrictRepository` | `get_district_meta(code)` · `resolve_district(code)` · `detect_district_by_name(msg)` · `detect_districts_in_message(msg)` · `list_districts(search, type, limit, offset)` · `get_district_detail(code)` · `get_polygons_geojson(bounds?)` | F01, 모든 Tool |
| `FloatingPopulationRepository` | `get_floating_population(district_code, quarter?)` | F03, F05, F06 |
| `EstimatedSalesRepository` | `get_estimated_sales(district_code, category_code?)` | F03, F04, F09 |
| `StoreRepository` | `get_store_info(district_code, category_code?)` · `get_store_history(district_code)` | F03, F04, F07, F08 |
| `PopulationRepository` | `get_population_info(district_code)` | F03, F07 |
| `ComparisonRepository` | `compare_districts(district_codes[])` | F05 |
| `RecommendationRepository` | `recommend_business(district_code, budget?, preference?)` | F07 |
| `SimulationRepository` | `get_sales_percentiles(category_code, quarter?)` · `get_default_unit_price(category_code)` | F09 |
| `HeatmapRepository` | `get_heatmap_data(time_slot, quarter?)` · `get_heatmap_all(quarter?)` | F06 |
| `BenchmarkRepository` | `get_benchmarks(district_type)` | 벤치마킹 (내부 헬퍼) |

> ⚠ `anomaly_detect` / `estimate` 같은 메서드는 존재하지 않는다. 매출 시뮬레이션은 Tool 레이어(`simulate_revenue`)가 `get_sales_percentiles` + `get_default_unit_price` 를 조합해 계산한다.

### Real 레포 특이 로직

- **`real/recommendation.py`**: raw_score 를 min-max 0~100 이 아니라 **55~95 유계 밴드**(`_band_scores`, `SCORE_BAND_MIN/MAX`)로 정규화 — 1위가 항상 100.0 으로 고정돼 절대 확신으로 오독되는 문제 방지. 동점/단일 카테고리는 75.0. `_apply_store_floor` 가 `store_count < MIN_RELIABLE_STORES(=3)` 카테고리를 랭킹에서 제외하고, 통과 카테고리 0이면 전체 fallback + `low_confidence` 안내 메시지("점포 표본이 적어(<3개) 참고용 추천입니다").
- **`real/simulation.py`**: `get_default_unit_price` 가 DB `default_unit_price` NULL 이면 major_category 기준 기본 객단가로 폴백(외식 12,000 / 서비스 25,000 / 소매 15,000, 최종 폴백 15,000원).
- **`real/floating_population.py`**: 분기 시간대 합계를 **`quarter_total`** 로 반환 — '일평균' 아님 (§7 데이터 함정 참조).
- **`real/estimated_sales.py`** 등 매출 계열: DB 분기 누적값을 `// MONTHS_PER_QUARTER(=3)` 로 월 환산 후 반환.

### Mock ↔ Real 동등성

- Mock 은 `agent/tools/mock/*.json` 또는 `repositories/mock/*.py` 에서 JSON fixture 사용
- Mock 에서 **DB/Redis 연결 시도 금지** ([[feedback_mock_real_pattern]] 교훈)
- Real Repository 는 `settings.use_mock=false` 일 때만 SQLAlchemy 세션 주입

## 2. DB 스키마

### 2.1 핵심 테이블

```sql
-- 상권 영역 (1,650개)  ⚠ 컬럼명 주의: code/name/type 아님
districts (
  district_code   VARCHAR(20) PK,
  district_name   VARCHAR(100) NOT NULL,
  district_type   VARCHAR(20) NOT NULL,  -- 골목/발달/전통/관광특구
  boundary        GEOMETRY(POLYGON,4326),
  center_point    GEOMETRY(POINT,4326),
  gu_code         VARCHAR(10),
  dong_code       VARCHAR(10),
  data_quarter    VARCHAR(10) NOT NULL,  -- 데이터 기준 분기 (⚠ districts 만 quarter 가 아니라 data_quarter)
  created_at      TIMESTAMPTZ
);
CREATE INDEX idx_districts_boundary ON districts USING GIST(boundary);

-- 유동인구 (9,888행 / 2025Q4)  ⚠ 인구 컬럼은 전부 _pop 접미사
floating_population (
  id              BIGSERIAL PK,
  district_code   VARCHAR(20) FK,
  quarter         VARCHAR(10),
  time_slot       SMALLINT,              -- 0~23
  total_pop, male_pop, female_pop  INT,
  age_10_pop, age_20_pop, age_30_pop, age_40_pop, age_50_pop, age_60_plus_pop  INT,
  UNIQUE(district_code, quarter, time_slot)
);

-- 추정매출 (21,333행 / 2025Q4)  ⚠ monthly_sales = 분기 누적 (단위 오해 주의)
estimated_sales (
  id BIGSERIAL PK,
  district_code FK, category_code, category_name, quarter,
  monthly_sales   BIGINT,                -- 실제로는 분기 누적(원). Repo에서 // MONTHS_PER_QUARTER(=3) 월 환산
  sales_count     INT,
  weekday_sales, weekend_sales  BIGINT,
  male_sales, female_sales BIGINT,
  age_10_sales ~ age_60_plus_sales BIGINT,  -- 6컬럼
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

-- 업종 메타 (category_resolver + F07/F09 사용)  ⚠ 컬럼명 주의: code/name 아님
category_metadata (
  category_code       VARCHAR(20) PK,
  category_name       VARCHAR(100) NOT NULL,
  major_category      VARCHAR(50),       -- 외식/서비스/소매
  avg_startup_cost    INTEGER,           -- 평균 창업비용 (만원)
  default_unit_price  INTEGER,           -- 기본 객단가 (원, 002 추가)
  aliases             VARCHAR(500)       -- 한국어 별칭, 쉼표 구분 "문자열" (003 추가. ⚠ TEXT[] 배열 아님)
);

-- 자가학습 별칭 저장소 (004 추가. SQLAlchemy 모델 없음 — raw SQL 전용)
learned_aliases (
  alias          VARCHAR(200) PK,
  code           VARCHAR(20) NOT NULL FK → category_metadata(category_code) ON DELETE CASCADE,
  confidence     REAL NOT NULL,          -- CHECK 0~1
  source         VARCHAR(50) NOT NULL,   -- 기본 "llm_gemini_flash"
  hit_count      INTEGER NOT NULL DEFAULT 1,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_used_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_learned_aliases_code ON learned_aliases(code);
```

**별칭 자가학습 흐름** (`services/category_resolver.py`):

1. 기동 시 `load_from_db` 가 기본 키워드 + `category_metadata.category_name`(`/` split) + `aliases`(`,` split) 를 병합하고, 이어서 `learned_aliases` 에서 **confidence ≥ 0.7** 인 것만 로드 (기존 키 충돌 시 기존 우선. 테이블 부재 시 무시).
2. LLM 이 새 별칭을 resolve 하면 `record_learned_alias` 가 `INSERT ... ON CONFLICT (alias) DO UPDATE`(hit_count+1, last_used_at 갱신, confidence GREATEST) 로 UPSERT — 실패 시 무예외 no-op.
3. 시드: `data/etl/category_aliases.json` 핵심 32종을 `seed_category_metadata.py` 가 쉼표 조인해 `aliases` 에 INSERT. 나머지 카테고리 aliases 는 의도적 NULL.

### 2.2 세션/채팅 (인메모리 → DB 이관은 out of scope)

현재 `chat_sessions` / `chat_messages` 테이블은 스키마만 있고 사용하지 않는다. 세션 저장소는 백엔드 인메모리 (`backend.md §7`).

## 3. Alembic 마이그레이션

```
server/alembic/versions/
├── 001_initial_schema.py                    # PostGIS extension + 초기 9테이블 + 인덱스
├── 002_add_default_unit_price.py            # category_metadata.default_unit_price (F09 simulation 지원)
├── 003_add_category_aliases.py              # category_metadata.aliases VARCHAR(500) (category_resolver 확장)
├── 004_learned_aliases.py                   # learned_aliases 테이블 신설 (런타임 별칭 자가학습)
└── 005_estimated_sales_column_comment.py    # 스키마 변경 없음 — monthly_sales 에 '분기 누적' COLUMN COMMENT
```

- `alembic.ini` + `server/alembic/env.py` 는 `database_url_sync` 사용
- 운영 배포 이슈 회피용 `server/scripts/cleanup_alembic.py` 존재 (시드 덤프에서 stale `alembic_version` 제거)

## 4. ETL 파이프라인 (`server/server/data/etl/`)

```
etl/
├── runner.py             # CLI 4 서브커맨드: run / load-shp / load-csv / validate
│                         #   예: python -m server.data.etl.runner run 2025Q4
├── base.py               # httpx async client + tenacity 재시도
├── seoul_opendata.py     # 서울 열린데이터 4개 서비스
├── shp_collector.py      # SHP → PostGIS POLYGON
├── csv_collector.py      # 상주인구 OA-15584
├── transformers.py       # 좌표변환 / unpivot / 성별·연령 매핑
├── loader.py             # batch_size=1000 UPSERT
├── category_aliases.json # 핵심 별칭 32종 시드 소스
└── seed_category_metadata.py   # category_metadata 시드 (객단가 + aliases)
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
- asyncpg copy batch 는 1000 이하 유지 ([[feedback_asyncpg_batch]] 교훈)
- UPSERT: `ON CONFLICT (district_code, category_code, quarter) DO UPDATE`

### 4.3 데이터 품질 게이트 (`runner validate <quarter>`)

2026-06-25 적재결손 재발 차단용. `runner.py::_collect_validation_checks` 가 다음을 검사하고 **하나라도 실패하면 exit 1** 로 적재/배포를 막는다:

- 행수: districts 전역 + 4개 시계열 테이블 **quarter-scope** (빈 분기 FAIL)
- FK: floating_population orphan 0건
- `districts.boundary` NULL < 5%
- 컬럼 내용: resident_pop worker/resident all-zero(`bool_and`) FAIL · `default_unit_price` NULL 0건 · `aliases` 전량-NULL FAIL · 음수 sanity · `monthly_sales`/`total_pop` all-zero (COALESCE NULL-safe)

행이 존재해도 컬럼이 전량 0/NULL 인 "조용한 결손"을 잡기 위한 게이트다 (기존 행수/FK 검증만으로는 통과됨).

### 4.4 스케줄러

- 현재 CLI 수동 실행만 지원
- GitHub Actions cron 또는 Celery Beat 은 향후 계획

## 5. 캐시 규약

Tool/라우트별 개별 키 구성 (통합 `report:*` 키는 존재하지 않음). **전 키 TTL 86400s(24h)**.

| 키 패턴 | 위치 | 저장 내용 |
|---|---|---|
| `summary:{district_code}` | `agent/tools/district_summary.py` | 상권 요약 (⚠ quarter 미포함) |
| `fp:{district_code}:{quarter\|latest}` | `agent/tools/floating_population.py` | 유동인구 |
| `sales:{district_code}:{category\|all}` | `agent/tools/estimated_sales.py` | 추정매출 (quarter 미포함) |
| `store:{district_code}:{category\|all}` | `agent/tools/store_info.py` | 점포 현황 |
| `history:{district_code}` | `agent/tools/store_history.py` | 점포 이력/리스크 |
| `pop:{district_code}` | `agent/tools/population_info.py` | 상주/직장 인구 |
| `compare:{정렬된 코드 '_' 조인}` | `agent/tools/compare_districts.py` | 상권 비교 |
| `recommend:{district_code}:{budget\|all}:{preference\|all}` | `agent/tools/recommend_business.py` | 업종 추천 |
| `simulation:{district_code}:{category}:{unit_price\|default}:{competitors}` | `agent/tools/simulate_revenue.py` | 매출 시뮬레이션 |
| `benchmarks:{district_type}` / `bench_stats:{district_type}` | `real/benchmarks.py` / `agent/tools/benchmarks.py` | 벤치마크 |
| `heatmap:{time_slot}:{quarter\|latest}` / `heatmap:all:{quarter\|latest}` | `api/routes/map_data.py` | 히트맵 (⚠ time_slot 이 앞, quarter 가 뒤) |
| `preview:{code}:{role\|default}` | `api/routes/districts.py` | F13 프리뷰 |
| `feedback:seen:{trace_id}` | `api/routes/feedback.py` | 피드백 멱등 가드 |

- CategoryResolver 는 캐시 키가 아니라 **프로세스 싱글톤** (lifespan 에서 1회 로드).
- Redis 장애 시 graceful degradation — 함수는 `None` 반환, 호출측은 DB 재조회.
- 캐시 flush: `server/scripts/flush_cache.py` 기본 prefix 5종 = `sales:` `compare:` `recommend:` `simulation:` `summary:`. 데이터 fix/재적재 배포 후 필수 실행 (stale payload 방어).

## 6. 운영 스크립트

| 스크립트 | 용도 |
|---|---|
| `scripts/verify_sales_units.py` | 매출 단위(분기→월) 변환이 정상인지 검증 |
| `scripts/validate_env.py` | 필수 환경변수 누락 가드 |
| `scripts/generate_seed.py` | seed 덤프 생성 |
| `scripts/backup_db.sh` | DB 덤프 백업 |
| `scripts/setup_db.py` | 신규 환경 DB 초기화 |
| `server/scripts/cleanup_alembic.py` | alembic_version 정리 |
| `server/scripts/flush_cache.py` | Redis 캐시 초기화 (매출 단위 fix 후 stale 제거) |

## 7. 데이터 품질 주의사항

- **매출 단위**: DB `monthly_sales` 컬럼은 분기 누적. Repository 가 `// MONTHS_PER_QUARTER(=3)` 월 환산 후 반환. 직접 쿼리 시 혼동 주의.
- **유동인구 집계 의미**: `get_floating_population` 이 반환하는 `quarter_total` 은 **분기 전체의 시간대별(by_hour) 합계 총량**이지 '일평균'이 아니다. 일수로 나눈 파생값을 만들면 시간대 peak 를 초과하는 물리 모순이 생긴다 (2026-06-26 S7 날조 근원). 2026-07-04 에 `daily_avg` → `quarter_total` 로 rename 완료 — `daily_avg` 는 구버전 Redis 캐시 payload 방어용 legacy 매처(numeric_sanity / trust / 프론트 `dailyAvg?` fallback)에만 잔존한다. rename 류 배포 시 `flush_cache.py` 필수.
- **polygon 누락**: SHP 적재 전 districts 는 boundary NULL → Circle Overlay fallback 필요
- **store_history 미적재**: Real 모드에서 F08 리스크는 `stores` 개폐업 집계로 파생 계산
- **한글 조사 strip**: 검색 시 `"강남역을"`, `"홍대에"` 등 조사 제거 ([[feedback_korean_particles]] 교훈)
