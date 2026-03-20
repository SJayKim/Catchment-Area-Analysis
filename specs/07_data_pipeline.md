# 07. MarketScope AI 데이터 수집 및 처리 파이프라인 명세서

> **문서 버전**: 1.1
> **작성일**: 2026-03-19
> **상태**: Draft (Phase 1 MVP 기준)
>
> ⚠️ **Phase 1 데이터 파이프라인 범위**
> - **커버리지**: 서울 특별시 한정 (10개 허용 상권 우선)
> - **[Phase 1] 활성 Collector**: `semas_collector` (소상공인진흥공단), `seoul_collector` (서울 열린데이터)
> - **[Phase 2] 비활성 Collector**: `molit_collector` (국토교통부 부동산) — 부동산 에이전트 비활성과 연동
> - **데이터 시차 고지**: 공공 API 특성상 최대 6개월 시차 → 리포트에 명시
>
> ### Phase 1 에이전트 ↔ 데이터 소스 매핑
>
> | 에이전트 | 주요 데이터 소스 | API | 라이선스 | 수집 주기 |
> |---------|---------------|-----|---------|---------|
> | **유동인구** | 서울 생활인구 | 서울 열린데이터광장 OA-15379 | 공공누리 1유형 ✅ | 월 1회 |
> | **유동인구** (보완) | 주민등록인구 | KOSIS (행안부) | 공공데이터법 ✅ | 월 1회 |
> | **매출추정** | 서울 추정매출 (카드사 기반) | 서울 열린데이터광장 OA-15572 | 공공누리 1유형 ✅ | 분기 1회 |
> | **경쟁분석** | 소상공인 상가정보 (전국 500만+ 사업체) | data.go.kr #15012005 | 공공누리 1유형 ✅ | 분기 1회 |
> | **입지분석** | 소상공인 상가정보 (상권 경계/밀도) | data.go.kr #15012005 | 공공누리 1유형 ✅ | 분기 1회 |
> | **입지분석** (보완) | 서울 지하철 승하차 (역별 일별) | 서울 열린데이터광장 CardSubwayStatsNew | 공공누리 1유형 ✅ | 월 1회 |
>
> ### 제외 데이터 소스
>
> | 소스 | 제외 사유 |
> |------|---------|
> | ~~네이버 데이터랩~~ | 이용약관: 수집 결과 DB화·재배포·상업적 이용 금지 → SaaS 구조적 위반 |
> | ~~LocalData 인허가 (localdata.go.kr)~~ | **2026-04-15 서비스 종료** — 인허가 에이전트 Phase 2 구현 시 data.go.kr 버전으로 재설계 |

---

## 목차

1. [개요](#1-개요)
2. [데이터베이스 스키마 (PostgreSQL + PostGIS)](#2-데이터베이스-스키마)
3. [Collector 계층](#3-collector-계층)
4. [Preprocessor 계층](#4-preprocessor-계층)
5. [자체 구축 데이터 테이블](#5-자체-구축-데이터-테이블)
6. [APScheduler 설정](#6-apscheduler-설정)
7. [데이터 품질 모니터링](#7-데이터-품질-모니터링)
8. [마이그레이션 전략](#8-마이그레이션-전략)
9. [LightRAG 연동](#9-lightrag-연동)

---

## 1. 개요

### 1.1 시스템 목적

MarketScope AI는 상권 분석을 위해 다양한 공공 API로부터 데이터를 수집하고, 전처리 후 PostgreSQL(PostGIS) 및 LightRAG에 저장하는 데이터 파이프라인을 운영한다. APScheduler를 통해 주기적으로 수집이 실행되며, 수집된 데이터는 분석 엔진과 RAG 기반 질의응답 시스템에 제공된다.

### 1.2 아키텍처 개요

```
┌────────────────────────────────────────────────────────────────────────┐
│                 외부 데이터 소스 (Phase 1 서울 한정)                      │
│  ┌─────────────────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │      data.go.kr          │  │    KOSIS     │  │ 서울 열린데이터광장  │ │
│  │  #15012005 소상공인 상권  │  │ (행안부 주민 │  │ OA-15379 생활인구  │ │
│  │  상가정보 (공공누리 1유형) │  │ 등록인구)    │  │ OA-15572 추정매출  │ │
│  │  경쟁분석·입지 에이전트   │  │ 유동인구 보완│  │ 지하철 승하차       │ │
│  └──────────┬──────────────┘  └──────┬───────┘  └─────────┬──────────┘ │
│             │ [Phase 2 비활성]        │                    │            │
│  ┌──────────┴──────────────┐         │                    │            │
│  │ 국토교통부 부동산 실거래  │         │                    │            │
│  │ [Phase 2] 부동산 에이전트│         │                    │            │
│  └─────────────────────────┘         │                    │            │
└──────────────────────────────────────┼────────────────────┼────────────┘
                                       │ (MCP 경유)          │
                                       ▼                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Collector 계층                                   │
│  ┌────────────────────┐  ┌──────────────────────┐  ┌─────────────────┐ │
│  │  semas_collector    │  │   molit_collector     │  │ seoul_collector  │ │
│  │ (소상공인진흥공단)   │  │  [Phase 2] 부동산     │  │(서울열린데이터)  │ │
│  │ [Phase 1] 활성      │  │  에이전트 활성 시      │  │[Phase 1] 활성   │ │
│  │ 경쟁·입지·매출 원천  │  │                      │  │ 유동인구·매출    │ │
│  └─────────┬──────────┘  └──────────────────────┘  └────────┬────────┘ │
└────────────┼───────────────────────────────────────────────┼───────────┘
           │                 │                 │
           ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────┐
│                  Preprocessor 계층                        │
│  ┌────────────┐ ┌───────────┐ ┌───────────┐ ┌────────┐ │
│  │좌표계 변환  │ │코드 매핑   │ │결측치 처리 │ │이상치  │ │
│  │TM→WGS84   │ │행정동↔법정동│ │전략별 보정 │ │탐지    │ │
│  └─────┬──────┘ └─────┬─────┘ └─────┬─────┘ └───┬────┘ │
└────────┼──────────────┼─────────────┼────────────┼──────┘
         │              │             │            │
         ▼              ▼             ▼            ▼
┌─────────────────────────────────────────────────────────┐
│                    저장 계층                              │
│  ┌──────────────────────┐  ┌─────────────────────────┐  │
│  │ PostgreSQL + PostGIS  │  │       LightRAG          │  │
│  │ (구조화 데이터)        │  │ (비정형 분석 결과)       │  │
│  └──────────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 1.3 기술 스택

| 구성요소 | 기술 | 버전 |
|---------|------|------|
| RDBMS | PostgreSQL + PostGIS | 16 + 3.4 |
| 스케줄러 | APScheduler | 3.10+ |
| ORM | SQLAlchemy + GeoAlchemy2 | 2.0+ |
| 마이그레이션 | Alembic | 1.13+ |
| 좌표 변환 | pyproj | 3.6+ |
| HTTP 클라이언트 | httpx (async) | 0.27+ |
| RAG | LightRAG | 최신 |
| 데이터 검증 | Pydantic | 2.0+ |

---

## 2. 데이터베이스 스키마

### 2.1 확장 모듈 활성화

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;       -- 텍스트 유사도 검색
CREATE EXTENSION IF NOT EXISTS btree_gist;    -- 복합 GiST 인덱스
```

### 2.2 Enum 타입 정의

```sql
-- 상권 유형
CREATE TYPE district_type AS ENUM (
    'DEVELOPED',      -- 발달상권
    'TRADITIONAL',    -- 전통시장
    'NEIGHBORHOOD',   -- 골목상권
    'SPECIFIC'        -- 특수상권
);

-- 점포 상태
CREATE TYPE store_status AS ENUM (
    'ACTIVE',    -- 영업중
    'CLOSED',    -- 폐업
    'SUSPENDED'  -- 휴업
);

-- 상권 등급
CREATE TYPE district_grade AS ENUM ('A', 'B', 'C');

-- 데이터 수집 상태
CREATE TYPE collection_status AS ENUM (
    'PENDING',
    'RUNNING',
    'SUCCESS',
    'PARTIAL_FAILURE',
    'FAILURE'
);
```

### 2.3 districts (상권 정보)

```sql
CREATE TABLE districts (
    id                  BIGSERIAL       PRIMARY KEY,
    district_code       VARCHAR(10)     NOT NULL UNIQUE,
    district_name       VARCHAR(100)    NOT NULL,
    district_type       district_type   NOT NULL,
    district_grade      district_grade,
    city_code           VARCHAR(5)      NOT NULL,           -- 시도코드
    city_name           VARCHAR(50)     NOT NULL,
    gu_code             VARCHAR(5)      NOT NULL,           -- 시군구코드
    gu_name             VARCHAR(50)     NOT NULL,
    dong_code           VARCHAR(10),                        -- 행정동코드
    dong_name           VARCHAR(50),
    boundary            GEOMETRY(POLYGON, 4326),            -- WGS84 경계 폴리곤
    center_point        GEOMETRY(POINT, 4326),              -- 중심점
    area_sqm            NUMERIC(12, 2),                     -- 면적 (㎡)
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    meta                JSONB           DEFAULT '{}',       -- 추가 메타 정보
    collected_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_districts_boundary_gist ON districts USING GIST (boundary);
CREATE INDEX idx_districts_center_gist ON districts USING GIST (center_point);
CREATE INDEX idx_districts_type ON districts (district_type);
CREATE INDEX idx_districts_grade ON districts (district_grade);
CREATE INDEX idx_districts_city_gu ON districts (city_code, gu_code);
CREATE INDEX idx_districts_dong ON districts (dong_code);
CREATE INDEX idx_districts_name_trgm ON districts USING GIN (district_name gin_trgm_ops);

-- 트리거: updated_at 자동 갱신
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_districts_updated
    BEFORE UPDATE ON districts
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();
```

### 2.4 population_stats (유동인구 통계)

```sql
CREATE TABLE population_stats (
    id                  BIGSERIAL,
    district_code       VARCHAR(10)     NOT NULL,
    year                SMALLINT        NOT NULL,           -- 연도
    quarter             SMALLINT        NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    -- 시간대별 유동인구 (일 평균)
    pop_time_00_06      INTEGER         DEFAULT 0,          -- 00시~06시
    pop_time_06_11      INTEGER         DEFAULT 0,          -- 06시~11시
    pop_time_11_14      INTEGER         DEFAULT 0,          -- 11시~14시
    pop_time_14_17      INTEGER         DEFAULT 0,          -- 14시~17시
    pop_time_17_21      INTEGER         DEFAULT 0,          -- 17시~21시
    pop_time_21_24      INTEGER         DEFAULT 0,          -- 21시~24시
    -- 요일별 유동인구 (일 평균)
    pop_mon             INTEGER         DEFAULT 0,
    pop_tue             INTEGER         DEFAULT 0,
    pop_wed             INTEGER         DEFAULT 0,
    pop_thu             INTEGER         DEFAULT 0,
    pop_fri             INTEGER         DEFAULT 0,
    pop_sat             INTEGER         DEFAULT 0,
    pop_sun             INTEGER         DEFAULT 0,
    -- 연령대별 유동인구
    pop_age_10s         INTEGER         DEFAULT 0,
    pop_age_20s         INTEGER         DEFAULT 0,
    pop_age_30s         INTEGER         DEFAULT 0,
    pop_age_40s         INTEGER         DEFAULT 0,
    pop_age_50s         INTEGER         DEFAULT 0,
    pop_age_60_plus     INTEGER         DEFAULT 0,
    -- 성별 유동인구
    pop_male            INTEGER         DEFAULT 0,
    pop_female          INTEGER         DEFAULT 0,
    -- 총 유동인구
    pop_total           INTEGER         NOT NULL DEFAULT 0,
    -- 메타
    data_source         VARCHAR(50)     DEFAULT 'SEMAS',
    collected_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id, year)
) PARTITION BY RANGE (year);

-- 연도별 파티션 생성 (2020~2027)
CREATE TABLE population_stats_2020 PARTITION OF population_stats
    FOR VALUES FROM (2020) TO (2021);
CREATE TABLE population_stats_2021 PARTITION OF population_stats
    FOR VALUES FROM (2021) TO (2022);
CREATE TABLE population_stats_2022 PARTITION OF population_stats
    FOR VALUES FROM (2022) TO (2023);
CREATE TABLE population_stats_2023 PARTITION OF population_stats
    FOR VALUES FROM (2023) TO (2024);
CREATE TABLE population_stats_2024 PARTITION OF population_stats
    FOR VALUES FROM (2024) TO (2025);
CREATE TABLE population_stats_2025 PARTITION OF population_stats
    FOR VALUES FROM (2025) TO (2026);
CREATE TABLE population_stats_2026 PARTITION OF population_stats
    FOR VALUES FROM (2026) TO (2027);
CREATE TABLE population_stats_2027 PARTITION OF population_stats
    FOR VALUES FROM (2027) TO (2028);

-- 인덱스 (파티션 테이블에 자동 적용)
CREATE INDEX idx_pop_district_year_qtr ON population_stats (district_code, year, quarter);
CREATE UNIQUE INDEX uidx_pop_unique ON population_stats (district_code, year, quarter);

-- FK는 파티션 테이블에서 직접 지원되지 않으므로 트리거로 참조 무결성 확보
CREATE OR REPLACE FUNCTION check_district_exists()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM districts WHERE district_code = NEW.district_code) THEN
        RAISE EXCEPTION 'district_code % does not exist in districts table', NEW.district_code;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_pop_check_district
    BEFORE INSERT OR UPDATE ON population_stats
    FOR EACH ROW EXECUTE FUNCTION check_district_exists();
```

### 2.5 revenue_stats (매출 통계)

```sql
CREATE TABLE revenue_stats (
    id                      BIGSERIAL,
    district_code           VARCHAR(10)     NOT NULL,
    industry_code_l         VARCHAR(10)     NOT NULL,   -- 업종 대분류 코드
    industry_code_m         VARCHAR(10),                -- 업종 중분류 코드
    industry_code_s         VARCHAR(10),                -- 업종 소분류 코드
    industry_name           VARCHAR(100)    NOT NULL,   -- 업종명
    year                    SMALLINT        NOT NULL,
    quarter                 SMALLINT        NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    -- 총 매출
    revenue_total           BIGINT          DEFAULT 0,          -- 총 추정매출액 (원)
    revenue_count           INTEGER         DEFAULT 0,          -- 총 거래건수
    -- 요일별 매출액
    revenue_mon             BIGINT          DEFAULT 0,
    revenue_tue             BIGINT          DEFAULT 0,
    revenue_wed             BIGINT          DEFAULT 0,
    revenue_thu             BIGINT          DEFAULT 0,
    revenue_fri             BIGINT          DEFAULT 0,
    revenue_sat             BIGINT          DEFAULT 0,
    revenue_sun             BIGINT          DEFAULT 0,
    -- 시간대별 매출액
    revenue_time_00_06      BIGINT          DEFAULT 0,
    revenue_time_06_11      BIGINT          DEFAULT 0,
    revenue_time_11_14      BIGINT          DEFAULT 0,
    revenue_time_14_17      BIGINT          DEFAULT 0,
    revenue_time_17_21      BIGINT          DEFAULT 0,
    revenue_time_21_24      BIGINT          DEFAULT 0,
    -- 연령대별 매출액
    revenue_age_10s         BIGINT          DEFAULT 0,
    revenue_age_20s         BIGINT          DEFAULT 0,
    revenue_age_30s         BIGINT          DEFAULT 0,
    revenue_age_40s         BIGINT          DEFAULT 0,
    revenue_age_50s         BIGINT          DEFAULT 0,
    revenue_age_60_plus     BIGINT          DEFAULT 0,
    -- 성별 매출액
    revenue_male            BIGINT          DEFAULT 0,
    revenue_female          BIGINT          DEFAULT 0,
    -- 객단가 (매출액 ÷ 거래건수, 계산 컬럼)
    avg_ticket_price        NUMERIC(12, 2)  GENERATED ALWAYS AS (
                                CASE WHEN revenue_count > 0
                                     THEN revenue_total::NUMERIC / revenue_count
                                     ELSE 0 END
                            ) STORED,
    -- 메타
    data_source             VARCHAR(50)     DEFAULT 'SEMAS',
    collected_at            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id, year)
) PARTITION BY RANGE (year);

-- 연도별 파티션 (2020~2027)
CREATE TABLE revenue_stats_2020 PARTITION OF revenue_stats FOR VALUES FROM (2020) TO (2021);
CREATE TABLE revenue_stats_2021 PARTITION OF revenue_stats FOR VALUES FROM (2021) TO (2022);
CREATE TABLE revenue_stats_2022 PARTITION OF revenue_stats FOR VALUES FROM (2022) TO (2023);
CREATE TABLE revenue_stats_2023 PARTITION OF revenue_stats FOR VALUES FROM (2023) TO (2024);
CREATE TABLE revenue_stats_2024 PARTITION OF revenue_stats FOR VALUES FROM (2024) TO (2025);
CREATE TABLE revenue_stats_2025 PARTITION OF revenue_stats FOR VALUES FROM (2025) TO (2026);
CREATE TABLE revenue_stats_2026 PARTITION OF revenue_stats FOR VALUES FROM (2026) TO (2027);
CREATE TABLE revenue_stats_2027 PARTITION OF revenue_stats FOR VALUES FROM (2027) TO (2028);

-- 인덱스
CREATE INDEX idx_rev_district_industry ON revenue_stats (district_code, industry_code_l);
CREATE INDEX idx_rev_year_qtr ON revenue_stats (year, quarter);
CREATE UNIQUE INDEX uidx_rev_unique ON revenue_stats (district_code, industry_code_l, industry_code_m, year, quarter);
```

### 2.6 stores (점포 정보)

```sql
CREATE TABLE stores (
    id                  BIGSERIAL       PRIMARY KEY,
    store_name          VARCHAR(200)    NOT NULL,
    district_code       VARCHAR(10),
    industry_code_l     VARCHAR(10)     NOT NULL,       -- 업종 대분류
    industry_code_m     VARCHAR(10),                    -- 업종 중분류
    industry_code_s     VARCHAR(10),                    -- 업종 소분류
    industry_name       VARCHAR(100),
    branch_name         VARCHAR(100),                   -- 지점명
    road_address        VARCHAR(300),                   -- 도로명 주소
    jibun_address       VARCHAR(300),                   -- 지번 주소
    zip_code            VARCHAR(10),
    location            GEOMETRY(POINT, 4326),          -- 좌표 (경도, 위도)
    floor               VARCHAR(20),                    -- 층 정보
    status              store_status    NOT NULL DEFAULT 'ACTIVE',
    open_date           DATE,                           -- 개업일
    close_date          DATE,                           -- 폐업일
    phone               VARCHAR(20),
    building_name       VARCHAR(200),
    dong_code           VARCHAR(10),                    -- 법정동 코드
    admin_dong_code     VARCHAR(10),                    -- 행정동 코드
    meta                JSONB           DEFAULT '{}',
    collected_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_stores_location_gist ON stores USING GIST (location);
CREATE INDEX idx_stores_district ON stores (district_code);
CREATE INDEX idx_stores_industry ON stores (industry_code_l, industry_code_m);
CREATE INDEX idx_stores_status ON stores (status);
CREATE INDEX idx_stores_dong ON stores (dong_code);
CREATE INDEX idx_stores_admin_dong ON stores (admin_dong_code);
CREATE INDEX idx_stores_name_trgm ON stores USING GIN (store_name gin_trgm_ops);
CREATE INDEX idx_stores_open_date ON stores (open_date) WHERE open_date IS NOT NULL;
CREATE INDEX idx_stores_close_date ON stores (close_date) WHERE close_date IS NOT NULL;

CREATE TRIGGER trg_stores_updated
    BEFORE UPDATE ON stores
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();
```

### 2.7 real_estate_transactions (상가 실거래가)

```sql
CREATE TABLE real_estate_transactions (
    id                  BIGSERIAL,
    deal_type           VARCHAR(20)     NOT NULL,       -- '매매', '전월세'
    legal_dong_code     VARCHAR(10)     NOT NULL,       -- 법정동코드 (5자리 또는 10자리)
    legal_dong_name     VARCHAR(50),
    building_name       VARCHAR(200),
    building_purpose    VARCHAR(50),                    -- 건물용도 (근린생활시설 등)
    floor               VARCHAR(10),
    area_sqm            NUMERIC(10, 2),                 -- 전용면적 (㎡)
    deal_amount         BIGINT,                         -- 거래금액 (만원)
    deposit             BIGINT,                         -- 보증금 (만원, 전월세)
    monthly_rent        BIGINT,                         -- 월세 (만원, 전월세)
    deal_year           SMALLINT        NOT NULL,
    deal_month          SMALLINT        NOT NULL CHECK (deal_month BETWEEN 1 AND 12),
    deal_day            SMALLINT,
    deal_date           DATE,                           -- 계산된 거래일
    jibun               VARCHAR(20),                    -- 지번
    road_address        VARCHAR(300),
    location            GEOMETRY(POINT, 4326),
    -- 건물 정보
    build_year          SMALLINT,                       -- 건축년도
    -- 메타
    data_source         VARCHAR(50)     DEFAULT 'MOLIT',
    collected_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id, deal_year)
) PARTITION BY RANGE (deal_year);

-- 연도별 파티션
CREATE TABLE real_estate_tx_2020 PARTITION OF real_estate_transactions FOR VALUES FROM (2020) TO (2021);
CREATE TABLE real_estate_tx_2021 PARTITION OF real_estate_transactions FOR VALUES FROM (2021) TO (2022);
CREATE TABLE real_estate_tx_2022 PARTITION OF real_estate_transactions FOR VALUES FROM (2022) TO (2023);
CREATE TABLE real_estate_tx_2023 PARTITION OF real_estate_transactions FOR VALUES FROM (2023) TO (2024);
CREATE TABLE real_estate_tx_2024 PARTITION OF real_estate_transactions FOR VALUES FROM (2024) TO (2025);
CREATE TABLE real_estate_tx_2025 PARTITION OF real_estate_transactions FOR VALUES FROM (2025) TO (2026);
CREATE TABLE real_estate_tx_2026 PARTITION OF real_estate_transactions FOR VALUES FROM (2026) TO (2027);
CREATE TABLE real_estate_tx_2027 PARTITION OF real_estate_transactions FOR VALUES FROM (2027) TO (2028);

-- 인덱스
CREATE INDEX idx_re_tx_dong ON real_estate_transactions (legal_dong_code);
CREATE INDEX idx_re_tx_date ON real_estate_transactions (deal_year, deal_month);
CREATE INDEX idx_re_tx_location_gist ON real_estate_transactions USING GIST (location);
CREATE INDEX idx_re_tx_purpose ON real_estate_transactions (building_purpose);
CREATE INDEX idx_re_tx_type ON real_estate_transactions (deal_type);
```

### 2.8 transit_stats (대중교통 승하차 통계)

```sql
CREATE TABLE transit_stats (
    id                  BIGSERIAL,
    transit_type        VARCHAR(20)     NOT NULL,       -- 'SUBWAY', 'BUS'
    station_name        VARCHAR(100)    NOT NULL,       -- 역/정류장명
    station_code        VARCHAR(20),                    -- 역/정류장 코드
    line_name           VARCHAR(50),                    -- 노선명 (2호선, 버스번호 등)
    location            GEOMETRY(POINT, 4326),          -- 역/정류장 좌표
    year                SMALLINT        NOT NULL,
    month               SMALLINT        NOT NULL CHECK (month BETWEEN 1 AND 12),
    -- 승하차 통계 (일 평균)
    boarding_total      INTEGER         DEFAULT 0,      -- 승차 합계
    alighting_total     INTEGER         DEFAULT 0,      -- 하차 합계
    -- 시간대별 승차
    boarding_05         INTEGER DEFAULT 0,
    boarding_06         INTEGER DEFAULT 0,
    boarding_07         INTEGER DEFAULT 0,
    boarding_08         INTEGER DEFAULT 0,
    boarding_09         INTEGER DEFAULT 0,
    boarding_10         INTEGER DEFAULT 0,
    boarding_11         INTEGER DEFAULT 0,
    boarding_12         INTEGER DEFAULT 0,
    boarding_13         INTEGER DEFAULT 0,
    boarding_14         INTEGER DEFAULT 0,
    boarding_15         INTEGER DEFAULT 0,
    boarding_16         INTEGER DEFAULT 0,
    boarding_17         INTEGER DEFAULT 0,
    boarding_18         INTEGER DEFAULT 0,
    boarding_19         INTEGER DEFAULT 0,
    boarding_20         INTEGER DEFAULT 0,
    boarding_21         INTEGER DEFAULT 0,
    boarding_22         INTEGER DEFAULT 0,
    boarding_23         INTEGER DEFAULT 0,
    boarding_00         INTEGER DEFAULT 0,
    -- 메타
    data_source         VARCHAR(50)     DEFAULT 'SEOUL_OPEN',
    collected_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id, year)
) PARTITION BY RANGE (year);

-- 파티션
CREATE TABLE transit_stats_2023 PARTITION OF transit_stats FOR VALUES FROM (2023) TO (2024);
CREATE TABLE transit_stats_2024 PARTITION OF transit_stats FOR VALUES FROM (2024) TO (2025);
CREATE TABLE transit_stats_2025 PARTITION OF transit_stats FOR VALUES FROM (2025) TO (2026);
CREATE TABLE transit_stats_2026 PARTITION OF transit_stats FOR VALUES FROM (2026) TO (2027);
CREATE TABLE transit_stats_2027 PARTITION OF transit_stats FOR VALUES FROM (2027) TO (2028);

-- 인덱스
CREATE INDEX idx_transit_station ON transit_stats (station_name, transit_type);
CREATE INDEX idx_transit_location_gist ON transit_stats USING GIST (location);
CREATE INDEX idx_transit_year_month ON transit_stats (year, month);
CREATE UNIQUE INDEX uidx_transit_unique ON transit_stats (station_code, transit_type, year, month);
```

### 2.9 unit_prices (업종별 객단가 - 자체 구축)

```sql
CREATE TABLE unit_prices (
    id                  SERIAL          PRIMARY KEY,
    industry_code_l     VARCHAR(10)     NOT NULL,       -- 업종 대분류 코드
    industry_name       VARCHAR(100)    NOT NULL,       -- 업종명
    district_grade      district_grade  NOT NULL,       -- 상권 등급 A/B/C
    avg_ticket_price    NUMERIC(10, 0)  NOT NULL,       -- 평균 객단가 (원)
    min_ticket_price    NUMERIC(10, 0),                 -- 최소 객단가
    max_ticket_price    NUMERIC(10, 0),                 -- 최대 객단가
    daily_customers     INTEGER,                        -- 일 평균 고객수
    data_year           SMALLINT        NOT NULL,       -- 기준연도
    source_description  TEXT,                           -- 출처 설명
    confidence_level    VARCHAR(10)     DEFAULT 'MEDIUM', -- HIGH/MEDIUM/LOW
    notes               TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uidx_unit_prices ON unit_prices (industry_code_l, district_grade, data_year);
CREATE INDEX idx_unit_prices_industry ON unit_prices (industry_code_l);

CREATE TRIGGER trg_unit_prices_updated
    BEFORE UPDATE ON unit_prices
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();
```

### 2.10 startup_costs (업종별 초기투자비 - 자체 구축)

```sql
CREATE TABLE startup_costs (
    id                      SERIAL          PRIMARY KEY,
    industry_code_l         VARCHAR(10)     NOT NULL,       -- 업종 대분류 코드
    industry_name           VARCHAR(100)    NOT NULL,       -- 업종명
    interior_cost_per_pyeong NUMERIC(10, 0) NOT NULL,       -- 인테리어 비용/평 (원)
    equipment_cost_per_pyeong NUMERIC(10, 0) NOT NULL,      -- 설비 비용/평 (원)
    furniture_cost_per_pyeong NUMERIC(10, 0) DEFAULT 0,     -- 가구/집기 비용/평 (원)
    signage_cost            NUMERIC(10, 0)  DEFAULT 0,      -- 간판 비용 (원, 고정)
    initial_inventory_cost  NUMERIC(12, 0)  DEFAULT 0,      -- 초기 재고비 (원, 고정)
    franchise_fee           NUMERIC(12, 0)  DEFAULT 0,      -- 가맹비 (원, 해당시)
    education_fee           NUMERIC(10, 0)  DEFAULT 0,      -- 교육비 (원, 해당시)
    deposit_months          SMALLINT        DEFAULT 10,     -- 보증금 월수 (월세 기준)
    other_fixed_cost        NUMERIC(12, 0)  DEFAULT 0,      -- 기타 고정비 (원)
    -- 기준 면적 (참고용)
    reference_area_pyeong   NUMERIC(6, 1),                  -- 기준 면적 (평)
    total_estimate_min      NUMERIC(12, 0),                 -- 최소 총 투자비 추정
    total_estimate_max      NUMERIC(12, 0),                 -- 최대 총 투자비 추정
    data_year               SMALLINT        NOT NULL,
    source_description      TEXT,
    notes                   TEXT,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uidx_startup_costs ON startup_costs (industry_code_l, data_year);
CREATE INDEX idx_startup_industry ON startup_costs (industry_code_l);

CREATE TRIGGER trg_startup_costs_updated
    BEFORE UPDATE ON startup_costs
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();
```

### 2.11 code_mappings (행정동-법정동-상권코드 매핑)

```sql
CREATE TABLE code_mappings (
    id                  SERIAL          PRIMARY KEY,
    admin_dong_code     VARCHAR(10)     NOT NULL,       -- 행정동코드 (10자리)
    admin_dong_name     VARCHAR(50)     NOT NULL,       -- 행정동명
    legal_dong_code     VARCHAR(10)     NOT NULL,       -- 법정동코드 (10자리)
    legal_dong_name     VARCHAR(50)     NOT NULL,       -- 법정동명
    district_code       VARCHAR(10),                    -- 상권코드 (SEMAS)
    district_name       VARCHAR(100),                   -- 상권명
    sigungu_code        VARCHAR(5)      NOT NULL,       -- 시군구코드
    sigungu_name        VARCHAR(50)     NOT NULL,       -- 시군구명
    sido_code           VARCHAR(2)      NOT NULL,       -- 시도코드
    sido_name           VARCHAR(20)     NOT NULL,       -- 시도명
    -- 다대다 관계 (하나의 행정동에 여러 상권, 하나의 상권이 여러 법정동에 걸침)
    overlap_ratio       NUMERIC(5, 4)   DEFAULT 1.0,    -- 상권과 동의 겹침 비율
    is_primary          BOOLEAN         DEFAULT TRUE,   -- 주 매핑 여부
    valid_from          DATE            DEFAULT CURRENT_DATE,
    valid_to            DATE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cm_admin_dong ON code_mappings (admin_dong_code);
CREATE INDEX idx_cm_legal_dong ON code_mappings (legal_dong_code);
CREATE INDEX idx_cm_district ON code_mappings (district_code);
CREATE INDEX idx_cm_sigungu ON code_mappings (sigungu_code);
CREATE UNIQUE INDEX uidx_cm_mapping ON code_mappings (admin_dong_code, legal_dong_code, district_code)
    WHERE valid_to IS NULL;

CREATE TRIGGER trg_code_mappings_updated
    BEFORE UPDATE ON code_mappings
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();
```

### 2.12 analysis_results (분석 결과 저장)

```sql
CREATE TABLE analysis_results (
    id                  BIGSERIAL       PRIMARY KEY,
    user_id             BIGINT,                         -- 분석 요청 사용자 (nullable = 시스템 자동)
    analysis_type       VARCHAR(50)     NOT NULL,       -- 'LOCATION', 'REVENUE_FORECAST', 'RISK'
    request_params      JSONB           NOT NULL,       -- 요청 파라미터
    result_summary      TEXT            NOT NULL,       -- 분석 결과 요약 (자연어)
    result_data         JSONB           NOT NULL,       -- 상세 결과 (구조화)
    district_code       VARCHAR(10),                    -- 관련 상권코드
    industry_code_l     VARCHAR(10),                    -- 관련 업종코드
    score               NUMERIC(5, 2),                  -- 종합 점수 (0~100)
    model_version       VARCHAR(20),                    -- 분석 모델 버전
    processing_time_ms  INTEGER,                        -- 처리 시간 (ms)
    status              VARCHAR(20)     NOT NULL DEFAULT 'COMPLETED',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ                     -- TTL (선택)
);

CREATE INDEX idx_ar_user ON analysis_results (user_id);
CREATE INDEX idx_ar_type ON analysis_results (analysis_type);
CREATE INDEX idx_ar_district ON analysis_results (district_code);
CREATE INDEX idx_ar_industry ON analysis_results (industry_code_l);
CREATE INDEX idx_ar_created ON analysis_results (created_at DESC);
CREATE INDEX idx_ar_result_data ON analysis_results USING GIN (result_data);
```

### 2.12.1 analysis_sessions (LangGraph 세션 결과 저장)

> `analysis_results`는 공공데이터 수집 이벤트 단위 테이블이다.
> `analysis_sessions`는 LangGraph 분석 세션 전체를 저장하는 테이블 — `MarketScopeState`와 1:1 매핑된다.

```sql
CREATE TABLE analysis_sessions (
    id                  BIGSERIAL       PRIMARY KEY,
    session_id          UUID            NOT NULL UNIQUE,    -- MarketScopeState.session_id
    user_id             BIGINT          REFERENCES users(id),
    user_input          TEXT            NOT NULL,           -- MarketScopeState.user_input (원본 질의)

    -- Commander Plan
    analysis_mode       VARCHAR(20)     NOT NULL,           -- 'basic' | 'quick' | 'comparison'
    target_location     VARCHAR(200)    NOT NULL,
    target_location_secondary VARCHAR(200),                  -- 비교 모드 시
    target_industry     VARCHAR(100)    NOT NULL,
    commander_plan      JSONB           NOT NULL,           -- CommanderPlan 전체

    -- 분석 결과 (에이전트별)
    population_result   JSONB,                              -- PopulationAnalysis
    competition_result  JSONB,                              -- CompetitionAnalysis
    revenue_result      JSONB,                              -- RevenueAnalysis
    location_result     JSONB,                              -- LocationAnalysis

    -- 비교 모드 보조 결과
    secondary_population_result  JSONB,
    secondary_competition_result JSONB,
    comparison_summary           JSONB,

    -- 최종 리포트
    final_report        JSONB,                              -- FinalReport (dict)
    overall_score       NUMERIC(5, 2),                      -- 종합 점수 0~100
    verdict             VARCHAR(20),                        -- '매우 유망' | '유망' | ...

    -- 실행 메타데이터
    node_executions     JSONB           DEFAULT '[]',       -- list[NodeExecution]
    errors              JSONB           DEFAULT '[]',       -- list[dict]
    current_phase       SMALLINT        DEFAULT 0,
    progress_pct        NUMERIC(5, 2)   DEFAULT 0.0,
    has_critical_failure BOOLEAN        DEFAULT FALSE,
    processing_time_ms  INTEGER,                            -- 총 처리 시간

    -- 상태
    status              VARCHAR(20)     NOT NULL DEFAULT 'PENDING',
    -- 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ     GENERATED ALWAYS AS
                            (created_at + INTERVAL '90 days') STORED  -- 90일 TTL
);

CREATE INDEX idx_as_session_id   ON analysis_sessions (session_id);
CREATE INDEX idx_as_user_id      ON analysis_sessions (user_id);
CREATE INDEX idx_as_status       ON analysis_sessions (status);
CREATE INDEX idx_as_location     ON analysis_sessions (target_location);
CREATE INDEX idx_as_industry     ON analysis_sessions (target_industry);
CREATE INDEX idx_as_created      ON analysis_sessions (created_at DESC);
CREATE INDEX idx_as_final_report ON analysis_sessions USING GIN (final_report);

CREATE TRIGGER trg_as_updated
    BEFORE UPDATE ON analysis_sessions
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();
```

**저장 시점**:
```python
# 세션 시작 시 (status='RUNNING')
await db.execute(
    "INSERT INTO analysis_sessions (session_id, user_id, user_input, ...) VALUES (...)",
    session_id=state["session_id"], status="RUNNING", ...
)

# 분석 완료 시 (status='COMPLETED')
await db.execute(
    """UPDATE analysis_sessions SET
       population_result=$1, competition_result=$2, revenue_result=$3, location_result=$4,
       final_report=$5, overall_score=$6, verdict=$7,
       node_executions=$8, processing_time_ms=$9, status='COMPLETED'
       WHERE session_id=$10""",
    ...
)

# 실패 시 (status='FAILED')
await db.execute(
    "UPDATE analysis_sessions SET errors=$1, has_critical_failure=TRUE, status='FAILED' WHERE session_id=$2",
    ...
)
```

### 2.13 users (사용자 정보)

```sql
CREATE TABLE users (
    id                  BIGSERIAL       PRIMARY KEY,
    email               VARCHAR(255)    NOT NULL UNIQUE,
    password_hash       VARCHAR(255)    NOT NULL,
    name                VARCHAR(100)    NOT NULL,
    phone               VARCHAR(20),
    role                VARCHAR(20)     NOT NULL DEFAULT 'USER',    -- 'ADMIN', 'USER', 'ANALYST'
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    subscription_plan   VARCHAR(20)     DEFAULT 'FREE',             -- 'FREE', 'BASIC', 'PRO'
    subscription_expires_at TIMESTAMPTZ,
    last_login_at       TIMESTAMPTZ,
    login_count         INTEGER         DEFAULT 0,
    preferences         JSONB           DEFAULT '{}',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_role ON users (role);
CREATE INDEX idx_users_active ON users (is_active) WHERE is_active = TRUE;

CREATE TRIGGER trg_users_updated
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();
```

### 2.14 collection_logs (수집 로그 - 보조 테이블)

```sql
CREATE TABLE collection_logs (
    id                  BIGSERIAL       PRIMARY KEY,
    collector_name      VARCHAR(50)     NOT NULL,       -- 'semas', 'molit', 'seoul'
    job_id              VARCHAR(100),                   -- APScheduler job ID
    status              collection_status NOT NULL DEFAULT 'PENDING',
    started_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    finished_at         TIMESTAMPTZ,
    records_fetched     INTEGER         DEFAULT 0,
    records_inserted    INTEGER         DEFAULT 0,
    records_updated     INTEGER         DEFAULT 0,
    records_failed      INTEGER         DEFAULT 0,
    error_message       TEXT,
    error_detail        JSONB,
    params              JSONB           DEFAULT '{}',   -- 수집 파라미터
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cl_collector ON collection_logs (collector_name);
CREATE INDEX idx_cl_status ON collection_logs (status);
CREATE INDEX idx_cl_started ON collection_logs (started_at DESC);
```

### 2.15 파티셔닝 전략 요약

| 테이블 | 파티션 키 | 파티션 방식 | 파티션 단위 | 비고 |
|--------|----------|------------|-----------|------|
| population_stats | year | RANGE | 연도별 | 분기 데이터, 연 4건/상권 |
| revenue_stats | year | RANGE | 연도별 | 분기 데이터, 업종별 다수 |
| real_estate_transactions | deal_year | RANGE | 연도별 | 월별 거래 데이터 |
| transit_stats | year | RANGE | 연도별 | 월별 통계 데이터 |
| stores | - | 파티션 없음 | - | 시점 데이터, 변경 추적은 별도 이력 |
| districts | - | 파티션 없음 | - | 약 3,000건, 소규모 |

---

## 3. Collector 계층

### 3.1 공통 구조

```
app/
├── collectors/
│   ├── __init__.py
│   ├── base_collector.py       # 추상 베이스 클래스
│   ├── semas_collector.py      # 소상공인진흥공단
│   ├── molit_collector.py      # 국토교통부
│   └── seoul_collector.py      # 서울 열린데이터
├── preprocessors/
│   ├── __init__.py
│   ├── coordinate_transformer.py
│   ├── code_mapper.py
│   ├── missing_value_handler.py
│   └── outlier_detector.py
├── models/
│   ├── __init__.py
│   └── db_models.py            # SQLAlchemy 모델
├── scheduler/
│   ├── __init__.py
│   └── job_config.py           # APScheduler 설정
└── config/
    └── settings.py             # 환경 변수, API 키
```

#### 3.1.1 BaseCollector (추상 클래스)

```python
# app/collectors/base_collector.py

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import CollectionLog


class BaseCollector(ABC):
    """모든 Collector의 베이스 클래스."""

    def __init__(self, db_session: AsyncSession, api_key: str):
        self.db = db_session
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
        )
        self.log: CollectionLog | None = None

    @property
    @abstractmethod
    def collector_name(self) -> str:
        """Collector 식별자."""
        ...

    @abstractmethod
    async def collect(self, **params) -> dict[str, Any]:
        """데이터 수집 실행. 수집 결과 요약 반환."""
        ...

    @abstractmethod
    async def _fetch_page(self, endpoint: str, params: dict) -> dict:
        """단일 API 페이지 호출."""
        ...

    @abstractmethod
    async def _parse_response(self, raw: dict) -> list[dict]:
        """API 응답 JSON 파싱 → 정규화된 dict 리스트."""
        ...

    @abstractmethod
    async def _validate_and_insert(self, records: list[dict]) -> tuple[int, int]:
        """검증 후 DB 삽입. (inserted, failed) 반환."""
        ...

    async def _start_log(self, params: dict) -> CollectionLog:
        """수집 시작 로그 기록."""
        self.log = CollectionLog(
            collector_name=self.collector_name,
            status="RUNNING",
            started_at=datetime.utcnow(),
            params=params,
        )
        self.db.add(self.log)
        await self.db.flush()
        return self.log

    async def _finish_log(
        self,
        status: str,
        fetched: int = 0,
        inserted: int = 0,
        updated: int = 0,
        failed: int = 0,
        error: str | None = None,
    ):
        """수집 완료 로그 갱신."""
        if self.log:
            self.log.status = status
            self.log.finished_at = datetime.utcnow()
            self.log.records_fetched = fetched
            self.log.records_inserted = inserted
            self.log.records_updated = updated
            self.log.records_failed = failed
            self.log.error_message = error
            await self.db.flush()

    async def _call_api_with_retry(
        self,
        url: str,
        params: dict,
        max_retries: int = 3,
        backoff_base: float = 2.0,
    ) -> dict:
        """
        API 호출 + 재시도 로직.
        429 (Rate Limit) → 지수 백오프 재시도.
        """
        import asyncio

        for attempt in range(max_retries):
            try:
                response = await self.client.get(url, params=params)

                if response.status_code == 429:
                    wait = backoff_base ** (attempt + 1)
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.TimeoutException:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(backoff_base ** attempt)

            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < max_retries - 1:
                    await asyncio.sleep(backoff_base ** attempt)
                    continue
                raise

        raise RuntimeError(f"API 호출 실패: {url} (max_retries={max_retries} 초과)")

    async def close(self):
        """HTTP 클라이언트 정리."""
        await self.client.aclose()
```

### 3.2 semas_collector.py (소상공인진흥공단)

#### 3.2.1 API 정보

| 항목 | 값 |
|------|---|
| 데이터셋 | data.go.kr #15012005 (소상공인시장진흥공단_상가(상권)정보) |
| Base URL | `https://apis.data.go.kr/B553077/api/open` |
| 인증 방식 | ServiceKey (URL 파라미터) |
| 일일 호출 제한 | 1,000건 |
| 응답 형식 | JSON / XML |
| 페이지 크기 | 최대 1,000건/page |

#### 3.2.2 수집 대상 API 목록

| API 엔드포인트 | 수집 대상 | 대상 테이블 |
|---------------|----------|------------|
| `/storeListInArea` | 상가업소 목록 | stores |
| `/trdarSelngQq` | 상권 추정매출 (분기별) | revenue_stats |
| `/trdarFlorpopQq` | 상권 유동인구 (분기별) | population_stats |
| `/trdarIncDecQq` | 상권 점포 증감 | stores (상태 변경) |
| `/trdarNmListInArea` | 상권 목록 | districts |

#### 3.2.3 분산 수집 전략

일일 1,000건 제한을 고려한 분산 수집 전략:

```
전체 상권 수: 약 3,000개
필요 API 호출수 (분기 1회):
  - 유동인구: 3,000건 (상권 당 1건)
  - 추정매출: 3,000건 × 약 5페이지 = 15,000건
  - 상가업소: 약 50,000건
  - 점포증감: 3,000건

총 약 71,000건 → 일 1,000건 제한 → 최소 71일 필요

분산 전략:
  1. 수집 기간: 분기 종료 후 15일 차부터 85일간 분산 수집
  2. 우선순위: 서울(1순위) → 수도권(2순위) → 기타(3순위)
  3. 일일 할당:
     - 유동인구: 200건/일 → 15일 완료
     - 추정매출: 500건/일 → 30일 완료
     - 상가업소: 200건/일 → 병렬 진행
     - 점포증감: 100건/일 → 30일 완료
  4. 일 중 분산: 06:00~22:00 사이 시간당 ~60건 (분당 1건)
```

#### 3.2.4 수집 실행 스케줄

```
수집 주기: 분기 1회
실행 시점: 매 분기 종료 후 15일 (데이터 갱신 지연 감안)
  - Q1 데이터 → 4월 15일부터 수집 시작
  - Q2 데이터 → 7월 15일부터 수집 시작
  - Q3 데이터 → 10월 15일부터 수집 시작
  - Q4 데이터 → 1월 15일부터 수집 시작
```

#### 3.2.5 구현 명세

```python
# app/collectors/semas_collector.py

from typing import Any
from pydantic import BaseModel, field_validator

from app.collectors.base_collector import BaseCollector


# --- Pydantic 검증 모델 ---

class PopulationRecord(BaseModel):
    """유동인구 레코드 검증 스키마."""
    trdar_cd: str                # 상권코드
    stdr_yyqu_cd: str            # 기준년분기코드 (예: 20244)
    tot_flpop_co: int            # 총 유동인구
    ml_flpop_co: int = 0         # 남성 유동인구
    fml_flpop_co: int = 0        # 여성 유동인구
    agrde_10_flpop_co: int = 0   # 10대
    agrde_20_flpop_co: int = 0   # 20대
    agrde_30_flpop_co: int = 0   # 30대
    agrde_40_flpop_co: int = 0   # 40대
    agrde_50_flpop_co: int = 0   # 50대
    agrde_60_above_flpop_co: int = 0  # 60대 이상
    tmzn_00_06_flpop_co: int = 0
    tmzn_06_11_flpop_co: int = 0
    tmzn_11_14_flpop_co: int = 0
    tmzn_14_17_flpop_co: int = 0
    tmzn_17_21_flpop_co: int = 0
    tmzn_21_24_flpop_co: int = 0
    mon_flpop_co: int = 0
    tues_flpop_co: int = 0
    wed_flpop_co: int = 0
    thur_flpop_co: int = 0
    fri_flpop_co: int = 0
    sat_flpop_co: int = 0
    sun_flpop_co: int = 0

    @field_validator("tot_flpop_co")
    @classmethod
    def validate_total(cls, v):
        if v < 0:
            raise ValueError("유동인구 총합은 0 이상이어야 합니다")
        return v


class RevenueRecord(BaseModel):
    """추정매출 레코드 검증 스키마."""
    trdar_cd: str
    stdr_yyqu_cd: str
    svc_induty_cd: str           # 서비스업종코드
    svc_induty_nm: str           # 서비스업종명
    thsmon_selng_amt: int = 0    # 당월 매출금액
    thsmon_selng_co: int = 0     # 당월 매출건수
    # 요일별, 시간대별, 연령대별, 성별 매출 필드 생략 (PopulationRecord와 유사한 패턴)


# --- Collector 구현 ---

class SemasCollector(BaseCollector):
    """소상공인시장진흥공단 데이터 수집기."""

    BASE_URL = "https://apis.data.go.kr/B553077/api/open"
    DAILY_LIMIT = 1000
    PAGE_SIZE = 1000

    ENDPOINTS = {
        "population": "/trdarFlorpopQq",
        "revenue": "/trdarSelngQq",
        "stores": "/storeListInArea",
        "store_change": "/trdarIncDecQq",
        "districts": "/trdarNmListInArea",
    }

    @property
    def collector_name(self) -> str:
        return "semas"

    async def collect(self, target: str, year: int, quarter: int, **params) -> dict[str, Any]:
        """
        수집 실행 메인 메서드.

        Args:
            target: 수집 대상 ('population', 'revenue', 'stores', 'store_change', 'districts')
            year: 수집 연도
            quarter: 수집 분기 (1~4)

        Returns:
            수집 결과 요약 dict
        """
        log_params = {"target": target, "year": year, "quarter": quarter, **params}
        await self._start_log(log_params)

        total_fetched = 0
        total_inserted = 0
        total_failed = 0

        try:
            # 대상 상권코드 목록 조회
            district_codes = await self._get_target_districts(params.get("priority", "ALL"))

            # 일일 할당량 계산
            daily_batch_size = self._calculate_daily_batch(target, len(district_codes))

            for batch_start in range(0, len(district_codes), daily_batch_size):
                batch = district_codes[batch_start:batch_start + daily_batch_size]

                for code in batch:
                    try:
                        raw = await self._fetch_page(
                            self.ENDPOINTS[target],
                            {
                                "serviceKey": self.api_key,
                                "pageNo": 1,
                                "numOfRows": self.PAGE_SIZE,
                                "trdarCd": code,
                                "stdrYyquCd": f"{year}{quarter}",
                                "type": "json",
                            },
                        )
                        records = await self._parse_response(raw)
                        total_fetched += len(records)

                        inserted, failed = await self._validate_and_insert(records)
                        total_inserted += inserted
                        total_failed += failed

                    except Exception as e:
                        total_failed += 1
                        # 개별 상권 실패는 로깅 후 계속 진행
                        await self._log_partial_error(code, str(e))

            status = "SUCCESS" if total_failed == 0 else "PARTIAL_FAILURE"
            await self._finish_log(status, total_fetched, total_inserted, 0, total_failed)

        except Exception as e:
            await self._finish_log("FAILURE", total_fetched, total_inserted, 0, total_failed, str(e))
            raise

        return {
            "status": status,
            "fetched": total_fetched,
            "inserted": total_inserted,
            "failed": total_failed,
        }

    async def _fetch_page(self, endpoint: str, params: dict) -> dict:
        """SEMAS API 단일 페이지 호출."""
        url = f"{self.BASE_URL}{endpoint}"
        return await self._call_api_with_retry(url, params)

    async def _parse_response(self, raw: dict) -> list[dict]:
        """
        SEMAS API 응답 파싱.
        응답 구조: { "header": {...}, "body": { "items": [...], "totalCount": N } }
        """
        try:
            body = raw.get("body", {})
            items = body.get("items", [])
            if isinstance(items, dict):
                items = items.get("item", [])
            if isinstance(items, dict):
                items = [items]
            return items
        except (KeyError, TypeError):
            return []

    async def _validate_and_insert(self, records: list[dict]) -> tuple[int, int]:
        """Pydantic 검증 후 DB upsert."""
        inserted = 0
        failed = 0

        for record in records:
            try:
                # 대상 테이블에 따른 검증 모델 선택 및 변환은 실제 구현에서 분기
                # 여기서는 population을 예시로 표시
                validated = PopulationRecord(**record)
                await self._upsert_population(validated)
                inserted += 1
            except Exception:
                failed += 1

        await self.db.commit()
        return inserted, failed

    async def _upsert_population(self, record: PopulationRecord):
        """유동인구 데이터 upsert (INSERT ON CONFLICT UPDATE)."""
        year = int(record.stdr_yyqu_cd[:4])
        quarter = int(record.stdr_yyqu_cd[4])

        stmt = """
            INSERT INTO population_stats (
                district_code, year, quarter,
                pop_total, pop_male, pop_female,
                pop_age_10s, pop_age_20s, pop_age_30s,
                pop_age_40s, pop_age_50s, pop_age_60_plus,
                pop_time_00_06, pop_time_06_11, pop_time_11_14,
                pop_time_14_17, pop_time_17_21, pop_time_21_24,
                pop_mon, pop_tue, pop_wed, pop_thu, pop_fri, pop_sat, pop_sun,
                data_source
            ) VALUES (
                :district_code, :year, :quarter,
                :total, :male, :female,
                :age10, :age20, :age30, :age40, :age50, :age60,
                :t0006, :t0611, :t1114, :t1417, :t1721, :t2124,
                :mon, :tue, :wed, :thu, :fri, :sat, :sun,
                'SEMAS'
            )
            ON CONFLICT (district_code, year, quarter) DO UPDATE SET
                pop_total = EXCLUDED.pop_total,
                pop_male = EXCLUDED.pop_male,
                pop_female = EXCLUDED.pop_female,
                collected_at = NOW()
        """
        await self.db.execute(stmt, {
            "district_code": record.trdar_cd,
            "year": year,
            "quarter": quarter,
            "total": record.tot_flpop_co,
            "male": record.ml_flpop_co,
            "female": record.fml_flpop_co,
            "age10": record.agrde_10_flpop_co,
            "age20": record.agrde_20_flpop_co,
            "age30": record.agrde_30_flpop_co,
            "age40": record.agrde_40_flpop_co,
            "age50": record.agrde_50_flpop_co,
            "age60": record.agrde_60_above_flpop_co,
            "t0006": record.tmzn_00_06_flpop_co,
            "t0611": record.tmzn_06_11_flpop_co,
            "t1114": record.tmzn_11_14_flpop_co,
            "t1417": record.tmzn_14_17_flpop_co,
            "t1721": record.tmzn_17_21_flpop_co,
            "t2124": record.tmzn_21_24_flpop_co,
            "mon": record.mon_flpop_co,
            "tue": record.tues_flpop_co,
            "wed": record.wed_flpop_co,
            "thu": record.thur_flpop_co,
            "fri": record.fri_flpop_co,
            "sat": record.sat_flpop_co,
            "sun": record.sun_flpop_co,
        })

    def _calculate_daily_batch(self, target: str, total_districts: int) -> int:
        """대상별 일일 배치 크기 계산."""
        allocation = {
            "population": 200,
            "revenue": 100,      # 업종별 다수 페이지 → 보수적
            "stores": 50,        # 건수 많음
            "store_change": 200,
            "districts": 500,
        }
        return allocation.get(target, 100)

    async def _get_target_districts(self, priority: str) -> list[str]:
        """수집 대상 상권 코드 목록 조회 (우선순위순 정렬)."""
        query = """
            SELECT district_code FROM districts
            WHERE is_active = TRUE
            ORDER BY
                CASE
                    WHEN city_name = '서울특별시' THEN 1
                    WHEN city_name IN ('경기도', '인천광역시') THEN 2
                    ELSE 3
                END,
                district_code
        """
        if priority == "SEOUL":
            query += " LIMIT 1000"
        result = await self.db.execute(query)
        return [row[0] for row in result.fetchall()]

    async def _log_partial_error(self, district_code: str, error: str):
        """개별 상권 수집 실패 로깅."""
        if self.log and self.log.error_detail is None:
            self.log.error_detail = {}
        if self.log:
            errors = self.log.error_detail or {}
            errors[district_code] = error
            self.log.error_detail = errors
```

#### 3.2.6 에러 처리 전략

| 에러 유형 | HTTP 코드 | 처리 방식 |
|----------|----------|----------|
| Rate Limit | 429 | 지수 백오프 (2초, 4초, 8초) 후 재시도, 최대 3회 |
| Server Error | 5xx | 2회 재시도 후 해당 상권 건너뛰기, partial failure 기록 |
| Timeout | - | 10초 connect / 30초 read, 3회 재시도 |
| Invalid Response | - | 레코드 단위 스킵, failed 카운트 증가 |
| 일일 한도 초과 | - | 다음 날 06:00에 재개 (남은 목록 별도 저장) |
| 네트워크 단절 | - | 5분 후 재시도, 30분 이상 실패 시 알림 발송 |

### 3.3 molit_collector.py (국토교통부)

> 🚫 **[Phase 2] 미구현** — 부동산 에이전트(real_estate_agent) 비활성 기간 동안 수집 불필요.
> Phase 2에서 부동산 에이전트 활성화 시 함께 구현. 주요 데이터: 임대료 시세, 실거래가, 공실률.

#### 3.3.1 API 정보

| 항목 | 값 |
|------|---|
| API 1 | 국토교통부_상업업무용 부동산 매매 신고 자료 |
| API 2 | 국토교통부_상업업무용 부동산 전월세 신고 자료 |
| Base URL | `http://apis.data.go.kr/1613000` |
| 인증 방식 | ServiceKey (URL 파라미터) |
| 요청 파라미터 | 법정동코드 5자리 + DEAL_YMD (년월 6자리) |
| 일일 호출 제한 | 1,000건 |

#### 3.3.2 수집 대상 및 스케줄

```
수집 주기: 월 1회
실행 시점: 매월 20일 (전월 데이터 수집)
대상 지역: 법정동코드 5자리 기준 약 250개 시군구
월별 API 호출: 250(시군구) × 2(매매+전월세) = 500건/월 → 일 1,000건 내

법정동코드 5자리 구성:
  - 서울: 11XXX (25개 구)
  - 경기: 41XXX (31개 시군)
  - 부산: 26XXX (16개 구군)
  - ... (전국 250개)
```

#### 3.3.3 구현 명세

```python
# app/collectors/molit_collector.py

from app.collectors.base_collector import BaseCollector


class MolitCollector(BaseCollector):
    """국토교통부 실거래가 데이터 수집기."""

    BASE_URL = "http://apis.data.go.kr/1613000"

    ENDPOINTS = {
        "trade": "/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade",        # 매매
        "rent": "/RTMSDataSvcNrgRent/getRTMSDataSvcNrgRent",           # 전월세
    }

    @property
    def collector_name(self) -> str:
        return "molit"

    async def collect(self, deal_type: str, year: int, month: int, **params):
        """
        실거래가 수집.

        Args:
            deal_type: 'trade' (매매) 또는 'rent' (전월세)
            year: 연도
            month: 월
        """
        await self._start_log({"deal_type": deal_type, "year": year, "month": month})
        deal_ymd = f"{year}{month:02d}"

        total_fetched = 0
        total_inserted = 0
        total_failed = 0

        # 법정동코드 5자리 목록 가져오기
        sigungu_codes = await self._get_sigungu_codes()

        for code in sigungu_codes:
            try:
                raw = await self._fetch_page(
                    self.ENDPOINTS[deal_type],
                    {
                        "serviceKey": self.api_key,
                        "LAWD_CD": code,        # 법정동코드 5자리
                        "DEAL_YMD": deal_ymd,   # 계약년월
                        "pageNo": 1,
                        "numOfRows": 1000,
                        "type": "json",
                    },
                )
                records = await self._parse_response(raw)
                total_fetched += len(records)

                for record in records:
                    try:
                        await self._insert_transaction(record, deal_type, code)
                        total_inserted += 1
                    except Exception:
                        total_failed += 1

            except Exception as e:
                total_failed += 1
                await self._log_partial_error(code, str(e))

        await self.db.commit()
        status = "SUCCESS" if total_failed == 0 else "PARTIAL_FAILURE"
        await self._finish_log(status, total_fetched, total_inserted, 0, total_failed)
        return {"status": status, "fetched": total_fetched, "inserted": total_inserted}

    async def _fetch_page(self, endpoint: str, params: dict) -> dict:
        url = f"{self.BASE_URL}{endpoint}"
        return await self._call_api_with_retry(url, params)

    async def _parse_response(self, raw: dict) -> list[dict]:
        """국토교통부 API 응답 파싱."""
        try:
            response = raw.get("response", {})
            body = response.get("body", {})
            items = body.get("items", {})
            item_list = items.get("item", [])
            if isinstance(item_list, dict):
                item_list = [item_list]
            return item_list
        except (KeyError, TypeError):
            return []

    async def _validate_and_insert(self, records: list[dict]) -> tuple[int, int]:
        """일괄 검증 및 삽입."""
        inserted = 0
        failed = 0
        for record in records:
            try:
                await self._insert_transaction(record, "trade", "")
                inserted += 1
            except Exception:
                failed += 1
        return inserted, failed

    async def _insert_transaction(self, record: dict, deal_type: str, sigungu_code: str):
        """개별 거래 데이터 삽입."""
        deal_amount = self._parse_amount(record.get("거래금액", "0"))
        deposit = self._parse_amount(record.get("보증금액", "0")) if deal_type == "rent" else None
        monthly_rent = self._parse_amount(record.get("월세금액", "0")) if deal_type == "rent" else None

        stmt = """
            INSERT INTO real_estate_transactions (
                deal_type, legal_dong_code, legal_dong_name,
                building_name, building_purpose, floor,
                area_sqm, deal_amount, deposit, monthly_rent,
                deal_year, deal_month, deal_day, deal_date,
                jibun, build_year, data_source
            ) VALUES (
                :deal_type, :dong_code, :dong_name,
                :building, :purpose, :floor,
                :area, :amount, :deposit, :rent,
                :year, :month, :day, :date,
                :jibun, :build_year, 'MOLIT'
            )
        """
        year = int(record.get("년", 0))
        month = int(record.get("월", 0))
        day = int(record.get("일", 0)) if record.get("일") else None

        await self.db.execute(stmt, {
            "deal_type": "매매" if deal_type == "trade" else "전월세",
            "dong_code": sigungu_code + record.get("법정동코드", "00000"),
            "dong_name": record.get("법정동", ""),
            "building": record.get("건물명", ""),
            "purpose": record.get("건물용도", ""),
            "floor": record.get("층", ""),
            "area": float(record.get("전용면적", 0)),
            "amount": deal_amount,
            "deposit": deposit,
            "rent": monthly_rent,
            "year": year,
            "month": month,
            "day": day,
            "date": f"{year}-{month:02d}-{day:02d}" if day else None,
            "jibun": record.get("지번", ""),
            "build_year": int(record.get("건축년도", 0)) or None,
        })

    @staticmethod
    def _parse_amount(raw: str) -> int:
        """금액 문자열 파싱 (쉼표, 공백 제거)."""
        if not raw:
            return 0
        return int(raw.replace(",", "").replace(" ", "").strip() or "0")

    async def _get_sigungu_codes(self) -> list[str]:
        """법정동코드 5자리 목록 조회."""
        result = await self.db.execute(
            "SELECT DISTINCT sigungu_code FROM code_mappings ORDER BY sigungu_code"
        )
        return [row[0] for row in result.fetchall()]
```

### 3.4 seoul_collector.py (서울 열린데이터)

#### 3.4.1 API 정보

| API | 엔드포인트 | 설명 |
|-----|----------|------|
| 서울 생활인구 | `http://openapi.seoul.go.kr:8088/{KEY}/json/SPOP_LOCAL_RESD_JACHI` | 자치구별 생활인구 |
| 지하철 승하차 | `http://openapi.seoul.go.kr:8088/{KEY}/json/CardSubwayStatsNew` | 역별 일별 승하차 |
| 카드매출 | `http://openapi.seoul.go.kr:8088/{KEY}/json/tbgiCardInfo` | 카드사 가맹점 매출 |

#### 3.4.2 수집 스케줄

```
수집 주기: 월 1회
실행 시점: 매월 15일 (전월 데이터)
대상: 서울특별시 25개 자치구
```

#### 3.4.3 구현 명세

```python
# app/collectors/seoul_collector.py

from app.collectors.base_collector import BaseCollector


class SeoulCollector(BaseCollector):
    """서울 열린데이터광장 수집기."""

    BASE_URL = "http://openapi.seoul.go.kr:8088"

    @property
    def collector_name(self) -> str:
        return "seoul"

    async def collect(self, target: str, year: int, month: int, **params):
        """
        서울 데이터 수집.

        Args:
            target: 'population', 'subway', 'card_sales'
            year: 연도
            month: 월
        """
        await self._start_log({"target": target, "year": year, "month": month})

        collectors = {
            "population": self._collect_population,
            "subway": self._collect_subway,
            "card_sales": self._collect_card_sales,
        }

        result = await collectors[target](year, month)
        return result

    async def _collect_subway(self, year: int, month: int):
        """지하철 승하차 데이터 수집."""
        total_fetched = 0
        total_inserted = 0
        page_size = 1000
        start_idx = 1

        while True:
            end_idx = start_idx + page_size - 1
            url = (
                f"{self.BASE_URL}/{self.api_key}/json"
                f"/CardSubwayStatsNew/{start_idx}/{end_idx}"
                f"/{year}{month:02d}01"
            )

            raw = await self._call_api_with_retry(url, {})
            data = raw.get("CardSubwayStatsNew", {})
            rows = data.get("row", [])

            if not rows:
                break

            for row in rows:
                await self._insert_subway_stat(row, year, month)
                total_fetched += 1
                total_inserted += 1

            if len(rows) < page_size:
                break
            start_idx += page_size

        await self.db.commit()
        await self._finish_log("SUCCESS", total_fetched, total_inserted)
        return {"status": "SUCCESS", "fetched": total_fetched, "inserted": total_inserted}

    async def _collect_population(self, year: int, month: int):
        """서울 생활인구 수집."""
        url = (
            f"{self.BASE_URL}/{self.api_key}/json"
            f"/SPOP_LOCAL_RESD_JACHI/1/1000/{year}{month:02d}"
        )
        raw = await self._call_api_with_retry(url, {})
        rows = raw.get("SPOP_LOCAL_RESD_JACHI", {}).get("row", [])
        # 데이터 삽입 로직 (생략 - subway와 동일 패턴)
        return {"status": "SUCCESS", "fetched": len(rows)}

    async def _collect_card_sales(self, year: int, month: int):
        """카드 매출 데이터 수집."""
        url = (
            f"{self.BASE_URL}/{self.api_key}/json"
            f"/tbgiCardInfo/1/1000/{year}/{month:02d}"
        )
        raw = await self._call_api_with_retry(url, {})
        rows = raw.get("tbgiCardInfo", {}).get("row", [])
        return {"status": "SUCCESS", "fetched": len(rows)}

    async def _insert_subway_stat(self, row: dict, year: int, month: int):
        """지하철 승하차 데이터 삽입."""
        stmt = """
            INSERT INTO transit_stats (
                transit_type, station_name, station_code, line_name,
                year, month,
                boarding_total, alighting_total,
                boarding_05, boarding_06, boarding_07, boarding_08,
                boarding_09, boarding_10, boarding_11, boarding_12,
                boarding_13, boarding_14, boarding_15, boarding_16,
                boarding_17, boarding_18, boarding_19, boarding_20,
                boarding_21, boarding_22, boarding_23, boarding_00,
                data_source
            ) VALUES (
                'SUBWAY', :station, :code, :line,
                :year, :month,
                :board_total, :alight_total,
                :b05, :b06, :b07, :b08, :b09, :b10, :b11, :b12,
                :b13, :b14, :b15, :b16, :b17, :b18, :b19, :b20,
                :b21, :b22, :b23, :b00,
                'SEOUL_OPEN'
            )
            ON CONFLICT (station_code, transit_type, year, month) DO UPDATE SET
                boarding_total = EXCLUDED.boarding_total,
                alighting_total = EXCLUDED.alighting_total,
                collected_at = NOW()
        """
        await self.db.execute(stmt, {
            "station": row.get("SUB_STA_NM", ""),
            "code": row.get("STATION_CD", ""),
            "line": row.get("LINE_NUM", ""),
            "year": year,
            "month": month,
            "board_total": int(row.get("RIDE_PASGR_NUM", 0)),
            "alight_total": int(row.get("ALIGHT_PASGR_NUM", 0)),
            # 시간대별 데이터 매핑 (실제 API 필드명에 맞게 조정)
            **{f"b{h:02d}": int(row.get(f"HR_{h}", 0)) for h in range(24)},
        })

    async def _fetch_page(self, endpoint: str, params: dict) -> dict:
        return await self._call_api_with_retry(endpoint, params)

    async def _parse_response(self, raw: dict) -> list[dict]:
        return []

    async def _validate_and_insert(self, records: list[dict]) -> tuple[int, int]:
        return (0, 0)
```

---

## 4. Preprocessor 계층

### 4.1 좌표계 변환 (TM -> WGS84)

```python
# app/preprocessors/coordinate_transformer.py

from pyproj import Transformer
from typing import Optional


class CoordinateTransformer:
    """
    좌표계 변환 유틸리티.

    소상공인진흥공단 API: 중부원점TM (EPSG:2097) 또는 UTM-K (EPSG:5178, 5179)
    국토교통부 API: WGS84 (EPSG:4326) 또는 도로명주소 기반
    저장 형식: WGS84 (EPSG:4326) - longitude, latitude
    """

    # 변환기 캐시 (CRS 변환은 비용이 높으므로 재사용)
    _transformers: dict[tuple[int, int], Transformer] = {}

    # 알려진 좌표계 매핑
    CRS_MAP = {
        "TM_CENTRAL": 2097,     # 중부원점 TM
        "UTM_K": 5178,          # UTM-K (구)
        "UTM_K_NEW": 5179,      # UTM-K (신)
        "KATEC": 5186,          # KATEC (한국교통연구원)
        "WGS84": 4326,          # WGS84
    }

    @classmethod
    def get_transformer(cls, from_epsg: int, to_epsg: int = 4326) -> Transformer:
        """변환기 인스턴스 캐시에서 조회 또는 생성."""
        key = (from_epsg, to_epsg)
        if key not in cls._transformers:
            cls._transformers[key] = Transformer.from_crs(
                f"EPSG:{from_epsg}",
                f"EPSG:{to_epsg}",
                always_xy=True,  # (x=경도, y=위도) 순서 보장
            )
        return cls._transformers[key]

    @classmethod
    def transform(
        cls,
        x: float,
        y: float,
        from_crs: str = "TM_CENTRAL",
    ) -> tuple[float, float]:
        """
        좌표 변환: 원본 CRS → WGS84 (경도, 위도).

        Args:
            x: 원본 X좌표 (TM의 경우 Easting)
            y: 원본 Y좌표 (TM의 경우 Northing)
            from_crs: 원본 좌표계 키 ('TM_CENTRAL', 'UTM_K', 'UTM_K_NEW', 'KATEC')

        Returns:
            (longitude, latitude) 튜플

        Raises:
            ValueError: 알 수 없는 좌표계이거나 변환 결과가 범위 밖인 경우
        """
        from_epsg = cls.CRS_MAP.get(from_crs)
        if from_epsg is None:
            raise ValueError(f"Unknown CRS: {from_crs}")

        if from_epsg == 4326:
            return (x, y)

        transformer = cls.get_transformer(from_epsg)
        lon, lat = transformer.transform(x, y)

        # 대한민국 범위 검증 (대략적)
        if not (124.0 <= lon <= 132.0 and 33.0 <= lat <= 43.0):
            raise ValueError(
                f"변환 결과가 대한민국 범위 밖: ({lon}, {lat}). "
                f"입력: ({x}, {y}), CRS: {from_crs}"
            )

        return (round(lon, 7), round(lat, 7))

    @classmethod
    def detect_crs(cls, x: float, y: float) -> Optional[str]:
        """
        좌표값 범위로 원본 좌표계 자동 감지.

        Returns:
            감지된 좌표계 키 또는 None
        """
        # WGS84 범위
        if 124.0 <= x <= 132.0 and 33.0 <= y <= 43.0:
            return "WGS84"

        # 중부원점 TM 범위 (대략)
        if 100_000 <= x <= 400_000 and 100_000 <= y <= 700_000:
            return "TM_CENTRAL"

        # UTM-K 범위 (대략)
        if 800_000 <= x <= 1_400_000 and 1_400_000 <= y <= 2_100_000:
            return "UTM_K"

        return None

    @classmethod
    def to_postgis_point(cls, lon: float, lat: float) -> str:
        """PostGIS POINT 형식 문자열 생성."""
        return f"SRID=4326;POINT({lon} {lat})"
```

### 4.2 코드 매핑 (행정동 <-> 법정동 <-> 상권코드)

```python
# app/preprocessors/code_mapper.py

from functools import lru_cache
from sqlalchemy.ext.asyncio import AsyncSession


class CodeMapper:
    """
    행정동코드 ↔ 법정동코드 ↔ 상권코드 간 매핑.

    코드 체계:
    - 행정동코드: 10자리 (시도2 + 시군구3 + 읍면동3 + 리2)
    - 법정동코드: 10자리 (시도2 + 시군구3 + 읍면동3 + 리2)
    - 상권코드: SEMAS 자체 코드 체계 (최대 10자리)

    관계:
    - 1 행정동 : N 법정동 (1:N)
    - 1 행정동 : N 상권 (1:N)
    - 1 상권 : N 법정동 (N:M, 경계 겹침)
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self._cache: dict[str, dict] = {}

    async def load_cache(self):
        """매핑 테이블 전체를 메모리에 캐시 (약 10,000건 이하)."""
        result = await self.db.execute(
            """
            SELECT admin_dong_code, admin_dong_name,
                   legal_dong_code, legal_dong_name,
                   district_code, district_name,
                   sigungu_code, sigungu_name,
                   sido_code, sido_name,
                   is_primary
            FROM code_mappings
            WHERE valid_to IS NULL
            """
        )
        rows = result.fetchall()

        self._admin_to_legal = {}    # 행정동 → [법정동]
        self._legal_to_admin = {}    # 법정동 → [행정동]
        self._admin_to_district = {} # 행정동 → [상권]
        self._district_to_admin = {} # 상권 → [행정동]
        self._legal_to_district = {} # 법정동 → [상권]

        for row in rows:
            admin, admin_nm, legal, legal_nm, district, district_nm, *rest = row
            is_primary = row[-1]

            self._admin_to_legal.setdefault(admin, []).append({
                "code": legal, "name": legal_nm, "primary": is_primary
            })
            self._legal_to_admin.setdefault(legal, []).append({
                "code": admin, "name": admin_nm, "primary": is_primary
            })
            if district:
                self._admin_to_district.setdefault(admin, []).append({
                    "code": district, "name": district_nm, "primary": is_primary
                })
                self._district_to_admin.setdefault(district, []).append({
                    "code": admin, "name": admin_nm, "primary": is_primary
                })
                self._legal_to_district.setdefault(legal, []).append({
                    "code": district, "name": district_nm
                })

    async def admin_dong_to_legal_dongs(self, admin_dong_code: str) -> list[dict]:
        """행정동코드 → 법정동코드 목록."""
        return self._admin_to_legal.get(admin_dong_code, [])

    async def legal_dong_to_admin_dongs(self, legal_dong_code: str) -> list[dict]:
        """법정동코드 → 행정동코드 목록."""
        return self._legal_to_admin.get(legal_dong_code, [])

    async def admin_dong_to_districts(self, admin_dong_code: str) -> list[dict]:
        """행정동코드 → 상권코드 목록."""
        return self._admin_to_district.get(admin_dong_code, [])

    async def district_to_admin_dongs(self, district_code: str) -> list[dict]:
        """상권코드 → 행정동코드 목록."""
        return self._district_to_admin.get(district_code, [])

    async def resolve_by_coordinate(
        self, lon: float, lat: float
    ) -> dict | None:
        """좌표 기반 매핑: PostGIS 공간 쿼리로 상권 → 행정동 → 법정동 매핑."""
        result = await self.db.execute(
            """
            SELECT d.district_code, d.district_name,
                   cm.admin_dong_code, cm.admin_dong_name,
                   cm.legal_dong_code, cm.legal_dong_name
            FROM districts d
            LEFT JOIN code_mappings cm ON cm.district_code = d.district_code
                AND cm.is_primary = TRUE AND cm.valid_to IS NULL
            WHERE ST_Contains(d.boundary, ST_SetSRID(ST_Point(:lon, :lat), 4326))
            LIMIT 1
            """,
            {"lon": lon, "lat": lat},
        )
        row = result.fetchone()
        if row:
            return {
                "district_code": row[0],
                "district_name": row[1],
                "admin_dong_code": row[2],
                "admin_dong_name": row[3],
                "legal_dong_code": row[4],
                "legal_dong_name": row[5],
            }
        return None
```

### 4.3 결측치 처리 전략

```python
# app/preprocessors/missing_value_handler.py

from enum import Enum
from typing import Any, Optional
import numpy as np


class ImputationStrategy(Enum):
    """결측치 보정 전략."""
    ZERO = "zero"                   # 0으로 대체
    MEAN = "mean"                   # 동일 상권 평균
    MEDIAN = "median"               # 동일 상권 중앙값
    PREV_QUARTER = "prev_quarter"   # 직전 분기 값
    LINEAR_INTERP = "linear_interp" # 선형 보간
    DISTRICT_AVG = "district_avg"   # 동일 유형 상권 평균
    DROP = "drop"                   # 해당 레코드 제외


# 데이터 유형별 결측치 처리 규칙
IMPUTATION_RULES: dict[str, dict[str, ImputationStrategy]] = {
    "population_stats": {
        # 유동인구: 직전 분기 값으로 보정 (계절성 고려 시 전년 동기 우선)
        "pop_total": ImputationStrategy.PREV_QUARTER,
        "pop_male": ImputationStrategy.PREV_QUARTER,
        "pop_female": ImputationStrategy.PREV_QUARTER,
        "pop_age_*": ImputationStrategy.PREV_QUARTER,
        "pop_time_*": ImputationStrategy.PREV_QUARTER,
        "pop_mon~sun": ImputationStrategy.PREV_QUARTER,
    },
    "revenue_stats": {
        # 매출: 동일 유형 상권 평균으로 보정
        "revenue_total": ImputationStrategy.DISTRICT_AVG,
        "revenue_count": ImputationStrategy.DISTRICT_AVG,
        "revenue_*_by_time": ImputationStrategy.ZERO,      # 시간대별은 0 허용
    },
    "stores": {
        # 점포: 좌표 없으면 도로명주소 기반 지오코딩 시도 후 DROP
        "location": ImputationStrategy.DROP,
        "industry_code_m": ImputationStrategy.ZERO,         # 중분류 없으면 대분류만 사용
    },
    "real_estate_transactions": {
        # 실거래가: 금액 없으면 제외
        "deal_amount": ImputationStrategy.DROP,
        "area_sqm": ImputationStrategy.DROP,
        "floor": ImputationStrategy.ZERO,                   # 층 정보 없으면 '정보없음'
    },
    "transit_stats": {
        # 대중교통: 0 허용 (해당 시간대 운행 없을 수 있음)
        "boarding_*": ImputationStrategy.ZERO,
        "alighting_*": ImputationStrategy.ZERO,
    },
}


class MissingValueHandler:
    """결측치 처리기."""

    def __init__(self, db_session):
        self.db = db_session

    async def handle(
        self,
        table_name: str,
        records: list[dict],
    ) -> list[dict]:
        """
        결측치 처리 수행.

        Returns:
            처리 완료된 레코드 리스트 (DROP 전략으로 제거된 레코드 제외)
        """
        rules = IMPUTATION_RULES.get(table_name, {})
        result = []

        for record in records:
            should_drop = False

            for field, value in record.items():
                if value is not None and value != "":
                    continue

                strategy = self._find_strategy(rules, field)

                if strategy == ImputationStrategy.DROP:
                    should_drop = True
                    break
                elif strategy == ImputationStrategy.ZERO:
                    record[field] = 0
                elif strategy == ImputationStrategy.PREV_QUARTER:
                    record[field] = await self._get_prev_quarter_value(
                        table_name, record, field
                    )
                elif strategy == ImputationStrategy.DISTRICT_AVG:
                    record[field] = await self._get_district_avg(
                        table_name, record, field
                    )
                elif strategy == ImputationStrategy.LINEAR_INTERP:
                    record[field] = await self._linear_interpolate(
                        table_name, record, field
                    )

            if not should_drop:
                result.append(record)

        return result

    def _find_strategy(self, rules: dict, field: str) -> ImputationStrategy:
        """필드명에 매칭되는 전략 탐색 (와일드카드 지원)."""
        if field in rules:
            return rules[field]
        # 와일드카드 매칭
        for pattern, strategy in rules.items():
            if pattern.endswith("*") and field.startswith(pattern[:-1]):
                return strategy
        return ImputationStrategy.ZERO  # 기본값

    async def _get_prev_quarter_value(
        self, table_name: str, record: dict, field: str
    ) -> Optional[Any]:
        """직전 분기 값 조회."""
        year = record.get("year", 0)
        quarter = record.get("quarter", 0)
        district_code = record.get("district_code", "")

        prev_year = year if quarter > 1 else year - 1
        prev_quarter = quarter - 1 if quarter > 1 else 4

        result = await self.db.execute(
            f"""
            SELECT {field} FROM {table_name}
            WHERE district_code = :dc AND year = :y AND quarter = :q
            LIMIT 1
            """,
            {"dc": district_code, "y": prev_year, "q": prev_quarter},
        )
        row = result.fetchone()
        return row[0] if row else 0

    async def _get_district_avg(
        self, table_name: str, record: dict, field: str
    ) -> Optional[Any]:
        """동일 유형 상권 평균값 조회."""
        year = record.get("year", 0)
        quarter = record.get("quarter", 0)
        district_code = record.get("district_code", "")

        result = await self.db.execute(
            f"""
            SELECT AVG(t.{field})
            FROM {table_name} t
            JOIN districts d1 ON t.district_code = d1.district_code
            JOIN districts d2 ON d2.district_code = :dc
            WHERE d1.district_type = d2.district_type
              AND t.year = :y AND t.quarter = :q
            """,
            {"dc": district_code, "y": year, "q": quarter},
        )
        row = result.fetchone()
        return int(row[0]) if row and row[0] else 0

    async def _linear_interpolate(
        self, table_name: str, record: dict, field: str
    ) -> Optional[Any]:
        """선형 보간 (전후 분기 데이터 사용)."""
        # 전후 분기 값 조회 후 중간값 계산
        prev = await self._get_prev_quarter_value(table_name, record, field)
        # 다음 분기 값이 있으면 선형 보간, 없으면 전 분기값 사용
        return prev or 0
```

### 4.4 이상치 탐지

```python
# app/preprocessors/outlier_detector.py

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession


class AnomalyType(Enum):
    REVENUE_SPIKE = "revenue_spike"         # 매출 급증
    REVENUE_DROP = "revenue_drop"           # 매출 급감
    POPULATION_SPIKE = "population_spike"   # 유동인구 급증
    POPULATION_DROP = "population_drop"     # 유동인구 급감
    STORE_MASS_CLOSE = "store_mass_close"   # 대량 폐업
    PRICE_ANOMALY = "price_anomaly"         # 거래가 이상


@dataclass
class AnomalyAlert:
    anomaly_type: AnomalyType
    district_code: str
    field: str
    current_value: float
    reference_value: float
    change_ratio: float     # 변동률 (%)
    severity: str           # 'WARNING', 'CRITICAL'
    description: str


class OutlierDetector:
    """
    이상치 탐지기.

    규칙 기반 이상치 탐지 로직:
    - 매출 300% 이상 변동 → CRITICAL
    - 매출 150% 이상 변동 → WARNING
    - 유동인구 200% 이상 변동 → CRITICAL
    - 유동인구 100% 이상 변동 → WARNING
    - 단일 상권 내 분기 대비 폐업 50개 이상 → WARNING
    - 실거래가 동일 건물 이전 거래 대비 200% 이상 → CRITICAL
    """

    RULES = {
        "revenue_total": {
            "warning_threshold": 1.5,    # 150% 변동
            "critical_threshold": 3.0,   # 300% 변동
            "spike_type": AnomalyType.REVENUE_SPIKE,
            "drop_type": AnomalyType.REVENUE_DROP,
        },
        "pop_total": {
            "warning_threshold": 1.0,    # 100% 변동
            "critical_threshold": 2.0,   # 200% 변동
            "spike_type": AnomalyType.POPULATION_SPIKE,
            "drop_type": AnomalyType.POPULATION_DROP,
        },
        "deal_amount": {
            "warning_threshold": 1.5,
            "critical_threshold": 2.0,
            "spike_type": AnomalyType.PRICE_ANOMALY,
            "drop_type": AnomalyType.PRICE_ANOMALY,
        },
    }

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def detect(
        self,
        table_name: str,
        record: dict,
    ) -> list[AnomalyAlert]:
        """
        단일 레코드에 대한 이상치 탐지.

        Returns:
            탐지된 이상치 알림 리스트
        """
        alerts = []

        for field, rules in self.RULES.items():
            if field not in record or record[field] is None:
                continue

            current = float(record[field])
            reference = await self._get_reference_value(table_name, record, field)

            if reference is None or reference == 0:
                continue

            change_ratio = abs(current - reference) / reference

            if change_ratio >= rules["critical_threshold"]:
                severity = "CRITICAL"
            elif change_ratio >= rules["warning_threshold"]:
                severity = "WARNING"
            else:
                continue

            anomaly_type = (
                rules["spike_type"] if current > reference else rules["drop_type"]
            )

            alerts.append(AnomalyAlert(
                anomaly_type=anomaly_type,
                district_code=record.get("district_code", ""),
                field=field,
                current_value=current,
                reference_value=reference,
                change_ratio=round(change_ratio * 100, 1),
                severity=severity,
                description=(
                    f"{field}: {reference:,.0f} → {current:,.0f} "
                    f"({change_ratio * 100:+.1f}% 변동)"
                ),
            ))

        return alerts

    async def detect_batch(
        self,
        table_name: str,
        records: list[dict],
    ) -> list[AnomalyAlert]:
        """배치 이상치 탐지."""
        all_alerts = []
        for record in records:
            alerts = await self.detect(table_name, record)
            all_alerts.extend(alerts)
        return all_alerts

    async def detect_mass_closure(
        self,
        district_code: str,
        year: int,
        quarter: int,
        threshold: int = 50,
    ) -> Optional[AnomalyAlert]:
        """대량 폐업 탐지."""
        result = await self.db.execute(
            """
            SELECT COUNT(*) FROM stores
            WHERE district_code = :dc
              AND status = 'CLOSED'
              AND close_date >= :start_date
              AND close_date < :end_date
            """,
            {
                "dc": district_code,
                "start_date": f"{year}-{(quarter - 1) * 3 + 1:02d}-01",
                "end_date": f"{year}-{quarter * 3 + 1:02d}-01"
                    if quarter < 4 else f"{year + 1}-01-01",
            },
        )
        count = result.scalar()

        if count and count >= threshold:
            return AnomalyAlert(
                anomaly_type=AnomalyType.STORE_MASS_CLOSE,
                district_code=district_code,
                field="store_closures",
                current_value=count,
                reference_value=threshold,
                change_ratio=(count / threshold - 1) * 100,
                severity="CRITICAL" if count >= threshold * 2 else "WARNING",
                description=f"상권 {district_code}: 분기 내 폐업 {count}건 (임계값: {threshold})",
            )
        return None

    async def _get_reference_value(
        self,
        table_name: str,
        record: dict,
        field: str,
    ) -> Optional[float]:
        """이전 분기(또는 이전 거래) 기준값 조회."""
        district_code = record.get("district_code", "")
        year = record.get("year", 0)
        quarter = record.get("quarter", 0)

        prev_year = year if quarter > 1 else year - 1
        prev_quarter = quarter - 1 if quarter > 1 else 4

        if table_name in ("population_stats", "revenue_stats"):
            result = await self.db.execute(
                f"""
                SELECT {field} FROM {table_name}
                WHERE district_code = :dc AND year = :y AND quarter = :q
                LIMIT 1
                """,
                {"dc": district_code, "y": prev_year, "q": prev_quarter},
            )
            row = result.fetchone()
            return float(row[0]) if row and row[0] else None

        return None
```

### 4.5 시계열 정렬 및 인덱싱

```python
# app/preprocessors/time_series_aligner.py

"""
시계열 데이터 정렬 전략.

문제:
  - 유동인구, 매출: 분기 단위 (Q1~Q4)
  - 실거래가: 월 단위
  - 대중교통: 월 단위
  - 점포 정보: 수시 갱신 (시점 데이터)

해결:
  1. 분기 코드 통일: YYYYQ 형식 (예: 20244 = 2024년 4분기)
  2. 월별 데이터 → 분기 집계 뷰 생성
  3. 시점 데이터 → 스냅샷 테이블로 이력 관리
"""


# 분기 집계 뷰 (실거래가: 월 → 분기)
QUARTERLY_REAL_ESTATE_VIEW = """
CREATE MATERIALIZED VIEW mv_real_estate_quarterly AS
SELECT
    legal_dong_code,
    deal_type,
    deal_year AS year,
    CEIL(deal_month / 3.0)::INT AS quarter,
    COUNT(*) AS deal_count,
    AVG(deal_amount) AS avg_deal_amount,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY deal_amount) AS median_deal_amount,
    MIN(deal_amount) AS min_deal_amount,
    MAX(deal_amount) AS max_deal_amount,
    AVG(area_sqm) AS avg_area_sqm,
    AVG(CASE WHEN area_sqm > 0 THEN deal_amount * 10000.0 / area_sqm END)
        AS avg_price_per_sqm    -- 평당 단가 (원/㎡)
FROM real_estate_transactions
WHERE deal_amount IS NOT NULL AND deal_amount > 0
GROUP BY legal_dong_code, deal_type, deal_year, CEIL(deal_month / 3.0)::INT;

CREATE UNIQUE INDEX uidx_mv_re_quarterly
    ON mv_real_estate_quarterly (legal_dong_code, deal_type, year, quarter);
"""

# 분기 집계 뷰 (대중교통: 월 → 분기)
QUARTERLY_TRANSIT_VIEW = """
CREATE MATERIALIZED VIEW mv_transit_quarterly AS
SELECT
    station_name,
    station_code,
    transit_type,
    line_name,
    year,
    CEIL(month / 3.0)::INT AS quarter,
    AVG(boarding_total) AS avg_daily_boarding,
    AVG(alighting_total) AS avg_daily_alighting,
    SUM(boarding_total) AS total_boarding,
    SUM(alighting_total) AS total_alighting
FROM transit_stats
GROUP BY station_name, station_code, transit_type, line_name, year, CEIL(month / 3.0)::INT;

CREATE UNIQUE INDEX uidx_mv_transit_quarterly
    ON mv_transit_quarterly (station_code, transit_type, year, quarter);
"""

# Materialized View 갱신 스케줄 (수집 완료 후 실행)
REFRESH_VIEWS_SQL = """
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_real_estate_quarterly;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_transit_quarterly;
"""
```

---

## 5. 자체 구축 데이터 테이블

### 5.1 업종별 객단가 테이블

#### 5.1.1 데이터 출처 및 산출 방법

```
출처: 프랜차이즈 정보공개서 (franchise.ftc.go.kr)
  - 공정거래위원회 가맹사업정보제공시스템
  - 가맹본부별 정보공개서 PDF에서 매출액, 거래건수 추출

산출 공식:
  평균 객단가 = 가맹점 평균 매출액(연) ÷ 가맹점 평균 거래건수(연)

상권 등급별 보정:
  - A등급 (발달상권, 유동인구 상위 20%): 기준값 × 1.2
  - B등급 (일반상권, 유동인구 중위 60%): 기준값 × 1.0
  - C등급 (골목상권, 유동인구 하위 20%): 기준값 × 0.8

갱신 주기: 연 1회 (정보공개서 갱신 시점: 매년 4~5월)
```

#### 5.1.2 초기 데이터 (상위 20개 업종)

```sql
INSERT INTO unit_prices (industry_code_l, industry_name, district_grade, avg_ticket_price, min_ticket_price, max_ticket_price, daily_customers, data_year, source_description, confidence_level)
VALUES
-- 한식
('CS100001', '한식음식점', 'A', 12000, 8000, 18000, 120, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS100001', '한식음식점', 'B', 10000, 7000, 15000, 85, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS100001', '한식음식점', 'C', 8000, 6000, 12000, 55, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
-- 커피/음료
('CS200001', '커피전문점', 'A', 5500, 4000, 7000, 250, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS200001', '커피전문점', 'B', 5000, 3800, 6500, 170, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS200001', '커피전문점', 'C', 4500, 3500, 6000, 100, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
-- 치킨
('CS100002', '치킨전문점', 'A', 22000, 18000, 28000, 80, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS100002', '치킨전문점', 'B', 20000, 17000, 25000, 55, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS100002', '치킨전문점', 'C', 19000, 16000, 23000, 35, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
-- 피자
('CS100003', '피자전문점', 'A', 25000, 20000, 35000, 55, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS100003', '피자전문점', 'B', 23000, 18000, 30000, 40, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS100003', '피자전문점', 'C', 21000, 17000, 28000, 25, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
-- 분식
('CS100004', '분식전문점', 'A', 7000, 4000, 10000, 150, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS100004', '분식전문점', 'B', 6000, 3500, 8500, 110, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS100004', '분식전문점', 'C', 5500, 3000, 7500, 70, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
-- 중식
('CS100005', '중식음식점', 'A', 11000, 8000, 16000, 100, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS100005', '중식음식점', 'B', 9500, 7000, 14000, 70, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS100005', '중식음식점', 'C', 8500, 6000, 12000, 45, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
-- 일식
('CS100006', '일식음식점', 'A', 18000, 12000, 30000, 70, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS100006', '일식음식점', 'B', 15000, 10000, 25000, 50, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS100006', '일식음식점', 'C', 13000, 9000, 20000, 30, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
-- 양식
('CS100007', '양식음식점', 'A', 20000, 14000, 35000, 65, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS100007', '양식음식점', 'B', 17000, 12000, 28000, 45, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS100007', '양식음식점', 'C', 14000, 10000, 22000, 28, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
-- 편의점
('CS300001', '편의점', 'A', 4500, 2000, 8000, 500, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS300001', '편의점', 'B', 4000, 1800, 7000, 350, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS300001', '편의점', 'C', 3500, 1500, 6000, 200, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
-- 제과/베이커리
('CS200002', '베이커리', 'A', 8000, 5000, 12000, 180, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS200002', '베이커리', 'B', 7000, 4500, 10000, 120, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS200002', '베이커리', 'C', 6000, 4000, 8500, 70, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
-- 미용실
('CS400001', '미용실', 'A', 25000, 15000, 45000, 15, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS400001', '미용실', 'B', 20000, 12000, 35000, 12, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS400001', '미용실', 'C', 16000, 10000, 28000, 8, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
-- 세탁소
('CS400002', '세탁소', 'A', 8000, 4000, 15000, 25, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS400002', '세탁소', 'B', 7000, 3500, 12000, 18, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS400002', '세탁소', 'C', 6000, 3000, 10000, 12, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
-- 약국
('CS500001', '약국', 'A', 15000, 5000, 40000, 80, 2025, '건강보험심사평가원 참고', 'MEDIUM'),
('CS500001', '약국', 'B', 13000, 4500, 35000, 55, 2025, '건강보험심사평가원 참고', 'MEDIUM'),
('CS500001', '약국', 'C', 11000, 4000, 30000, 35, 2025, '건강보험심사평가원 참고', 'MEDIUM'),
-- 노래방/PC방
('CS600001', 'PC방', 'A', 6000, 3000, 10000, 120, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS600001', 'PC방', 'B', 5000, 2500, 8000, 80, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS600001', 'PC방', 'C', 4000, 2000, 6000, 50, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
-- 햄버거
('CS100008', '햄버거전문점', 'A', 9500, 7000, 14000, 200, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS100008', '햄버거전문점', 'B', 8500, 6500, 12000, 140, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
('CS100008', '햄버거전문점', 'C', 8000, 6000, 11000, 85, 2025, '프랜차이즈 정보공개서 기반 산출', 'HIGH'),
-- 주점/호프
('CS100009', '주점/호프', 'A', 35000, 20000, 55000, 50, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS100009', '주점/호프', 'B', 30000, 18000, 45000, 35, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS100009', '주점/호프', 'C', 25000, 15000, 38000, 22, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
-- 헬스/피트니스
('CS700001', '헬스/피트니스', 'A', 80000, 50000, 120000, 3, 2025, '월 회원권 기준, 일 환산', 'LOW'),
('CS700001', '헬스/피트니스', 'B', 65000, 40000, 100000, 3, 2025, '월 회원권 기준, 일 환산', 'LOW'),
('CS700001', '헬스/피트니스', 'C', 50000, 30000, 80000, 2, 2025, '월 회원권 기준, 일 환산', 'LOW'),
-- 네일/뷰티
('CS400003', '네일샵', 'A', 40000, 20000, 70000, 10, 2025, '업계 평균 추정', 'LOW'),
('CS400003', '네일샵', 'B', 35000, 18000, 55000, 7, 2025, '업계 평균 추정', 'LOW'),
('CS400003', '네일샵', 'C', 28000, 15000, 45000, 5, 2025, '업계 평균 추정', 'LOW'),
-- 반찬가게
('CS100010', '반찬전문점', 'A', 15000, 8000, 25000, 60, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS100010', '반찬전문점', 'B', 12000, 7000, 20000, 45, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM'),
('CS100010', '반찬전문점', 'C', 10000, 6000, 16000, 30, 2025, '프랜차이즈 정보공개서 기반 산출', 'MEDIUM');
```

### 5.2 업종별 초기투자비 테이블

#### 5.2.1 데이터 출처

```
출처:
  1. 프랜차이즈 정보공개서 (franchise.ftc.go.kr) - 가맹점 평균 창업비용
  2. 소상공인시장진흥공단 창업비용 가이드
  3. 업종별 인테리어 시공 사례 (실측 데이터)

구조:
  - 인테리어 비용/평: 바닥, 벽면, 천장, 조명 등 포함
  - 설비 비용/평: 주방설비, 냉난방, 전기 등
  - 기타 고정비: 간판, 초기 재고, 가맹비, 교육비 등

갱신 주기: 연 1회
```

#### 5.2.2 초기 데이터 (상위 15개 업종)

```sql
INSERT INTO startup_costs (
    industry_code_l, industry_name,
    interior_cost_per_pyeong, equipment_cost_per_pyeong, furniture_cost_per_pyeong,
    signage_cost, initial_inventory_cost, franchise_fee, education_fee,
    deposit_months, other_fixed_cost,
    reference_area_pyeong, total_estimate_min, total_estimate_max,
    data_year, source_description
) VALUES
-- 한식음식점 (20평 기준)
('CS100001', '한식음식점',
 2800000, 2200000, 500000,
 3000000, 5000000, 0, 0,
 10, 2000000,
 20, 120000000, 180000000,
 2025, '프랜차이즈 정보공개서 + 소진공 창업가이드'),

-- 커피전문점 (15평 기준)
('CS200001', '커피전문점',
 3500000, 2500000, 600000,
 4000000, 3000000, 10000000, 2000000,
 10, 3000000,
 15, 120000000, 200000000,
 2025, '프랜차이즈 정보공개서 (주요 프랜차이즈 평균)'),

-- 치킨전문점 (12평 기준)
('CS100002', '치킨전문점',
 2500000, 3000000, 300000,
 3000000, 2000000, 8000000, 1500000,
 10, 2000000,
 12, 85000000, 130000000,
 2025, '프랜차이즈 정보공개서 (BBQ, BHC, 교촌 평균)'),

-- 피자전문점 (15평 기준)
('CS100003', '피자전문점',
 2800000, 3200000, 400000,
 3000000, 2000000, 12000000, 2000000,
 10, 2000000,
 15, 115000000, 170000000,
 2025, '프랜차이즈 정보공개서'),

-- 분식전문점 (10평 기준)
('CS100004', '분식전문점',
 2000000, 1800000, 300000,
 2500000, 1500000, 5000000, 1000000,
 10, 1000000,
 10, 52000000, 80000000,
 2025, '프랜차이즈 정보공개서'),

-- 편의점 (15평 기준)
('CS300001', '편의점',
 2000000, 1500000, 300000,
 2000000, 15000000, 5000000, 500000,
 10, 1000000,
 15, 80000000, 130000000,
 2025, 'CU, GS25, 세븐일레븐 정보공개서 평균'),

-- 베이커리 (20평 기준)
('CS200002', '베이커리',
 3000000, 3500000, 500000,
 4000000, 5000000, 15000000, 3000000,
 10, 3000000,
 20, 170000000, 280000000,
 2025, '파리바게뜨, 뚜레쥬르 등 정보공개서'),

-- 미용실 (15평 기준)
('CS400001', '미용실',
 3500000, 1000000, 800000,
 3000000, 2000000, 0, 0,
 10, 2000000,
 15, 86500000, 140000000,
 2025, '업계 평균 추정'),

-- 세탁소 (8평 기준)
('CS400002', '세탁소',
 1500000, 4000000, 200000,
 2000000, 500000, 3000000, 500000,
 10, 500000,
 8, 52000000, 75000000,
 2025, '크린토피아 등 정보공개서'),

-- 약국 (10평 기준)
('CS500001', '약국',
 3000000, 1500000, 500000,
 2000000, 20000000, 0, 0,
 10, 5000000,
 10, 77000000, 120000000,
 2025, '약사회 창업가이드 참고'),

-- PC방 (30평 기준)
('CS600001', 'PC방',
 2000000, 3500000, 200000,
 3000000, 0, 0, 0,
 10, 5000000,
 30, 180000000, 280000000,
 2025, '업계 평균 추정 (PC 장비 포함)'),

-- 햄버거전문점 (15평 기준)
('CS100008', '햄버거전문점',
 3000000, 3000000, 400000,
 3500000, 3000000, 15000000, 2000000,
 10, 2000000,
 15, 120000000, 190000000,
 2025, '맥도날드, 버거킹 등 정보공개서'),

-- 주점/호프 (20평 기준)
('CS100009', '주점/호프',
 3500000, 1500000, 800000,
 4000000, 5000000, 5000000, 1000000,
 10, 2000000,
 20, 133000000, 210000000,
 2025, '프랜차이즈 정보공개서'),

-- 헬스/피트니스 (50평 기준)
('CS700001', '헬스/피트니스',
 2000000, 2000000, 500000,
 5000000, 0, 0, 0,
 10, 5000000,
 50, 235000000, 380000000,
 2025, '업계 평균 추정'),

-- 네일샵 (8평 기준)
('CS400003', '네일샵',
 3000000, 500000, 600000,
 2000000, 1500000, 0, 500000,
 10, 500000,
 8, 37300000, 60000000,
 2025, '업계 평균 추정');
```

### 5.3 행정동-법정동-상권코드 매핑 테이블 구축

#### 5.3.1 데이터 소스

```
1. 행정동코드:
   - 행정안전부 행정표준코드관리시스템 (code.go.kr)
   - 행정기관코드 (10자리): 시도(2) + 시군구(3) + 읍면동(3) + 리(2)
   - 갱신 주기: 수시 (행정구역 개편 시)
   - 다운로드: CSV 파일 제공

2. 법정동코드:
   - 행정안전부 행정표준코드관리시스템 (code.go.kr)
   - 법정기관코드 (10자리): 시도(2) + 시군구(3) + 읍면동(3) + 리(2)
   - 갱신 주기: 수시
   - 다운로드: CSV 파일 제공

3. 행정동-법정동 매핑:
   - 행정안전부 제공 '행정동-법정동 연계표'
   - 주소정보 누리집 (juso.go.kr) 에서 다운로드 가능
   - 1:N 관계 (1 행정동에 여러 법정동 포함 가능)

4. 상권코드:
   - 소상공인시장진흥공단 상권정보 API
   - 상권 경계 폴리곤과 행정동 경계 폴리곤의 공간 교차(ST_Intersects)로 매핑

매핑 구축 절차:
  Step 1: 행정동코드, 법정동코드 CSV 다운로드 → code_mappings 기본 적재
  Step 2: 행정동-법정동 연계표 적용
  Step 3: SEMAS API로 상권 목록 + 경계 폴리곤 수집
  Step 4: PostGIS ST_Intersects로 상권↔행정동 공간 매핑
  Step 5: 겹침 비율(ST_Area 기반) 계산하여 overlap_ratio 갱신
  Step 6: 가장 넓은 겹침 영역 기준 is_primary 설정
```

#### 5.3.2 매핑 구축 SQL

```sql
-- Step 4: 상권-행정동 공간 매핑 (PostGIS)
-- 행정동 경계 테이블이 별도로 있다고 가정 (admin_boundaries)
INSERT INTO code_mappings (
    admin_dong_code, admin_dong_name,
    legal_dong_code, legal_dong_name,
    district_code, district_name,
    sigungu_code, sigungu_name,
    sido_code, sido_name,
    overlap_ratio, is_primary
)
SELECT
    ab.admin_dong_code,
    ab.admin_dong_name,
    lb.legal_dong_code,
    lb.legal_dong_name,
    d.district_code,
    d.district_name,
    LEFT(ab.admin_dong_code, 5),
    ab.sigungu_name,
    LEFT(ab.admin_dong_code, 2),
    ab.sido_name,
    -- 겹침 비율 계산
    CASE
        WHEN ST_Area(ab.boundary::geography) > 0
        THEN ST_Area(ST_Intersection(d.boundary, ab.boundary)::geography)
             / ST_Area(ab.boundary::geography)
        ELSE 0
    END AS overlap_ratio,
    FALSE  -- 이후 별도 UPDATE로 is_primary 설정
FROM districts d
JOIN admin_boundaries ab ON ST_Intersects(d.boundary, ab.boundary)
JOIN legal_boundaries lb ON ST_Intersects(d.boundary, lb.boundary)
    AND LEFT(ab.admin_dong_code, 5) = LEFT(lb.legal_dong_code, 5)  -- 같은 시군구
ON CONFLICT DO NOTHING;

-- Step 6: is_primary 설정 (가장 넓은 겹침)
WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY district_code
               ORDER BY overlap_ratio DESC
           ) AS rn
    FROM code_mappings
    WHERE valid_to IS NULL
)
UPDATE code_mappings cm
SET is_primary = (r.rn = 1)
FROM ranked r
WHERE cm.id = r.id;
```

---

## 6. APScheduler 설정

### 6.1 스케줄러 설정

```python
# app/scheduler/job_config.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MISSED,
)

from app.config.settings import settings


def create_scheduler() -> AsyncIOScheduler:
    """APScheduler 인스턴스 생성 및 설정."""

    jobstores = {
        "default": SQLAlchemyJobStore(
            url=settings.DATABASE_URL,
            tablename="apscheduler_jobs",  # 작업 지속성을 위한 DB 저장
        ),
    }

    executors = {
        "default": AsyncIOExecutor(),
    }

    job_defaults = {
        "coalesce": True,           # 누적된 미실행 작업 1회만 실행
        "max_instances": 1,         # 동일 작업 동시 실행 방지
        "misfire_grace_time": 3600, # 1시간 내 미스파이어 허용
    }

    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone="Asia/Seoul",
    )

    # 이벤트 리스너 등록
    scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
    scheduler.add_listener(_on_job_missed, EVENT_JOB_MISSED)

    return scheduler


# --- 이벤트 핸들러 ---

async def _on_job_executed(event):
    """작업 성공 완료 시 처리."""
    import logging
    logger = logging.getLogger("scheduler")
    logger.info(f"Job executed: {event.job_id}, return={event.retval}")


async def _on_job_error(event):
    """작업 실패 시 알림 발송."""
    import logging
    import traceback
    logger = logging.getLogger("scheduler")
    logger.error(
        f"Job failed: {event.job_id}, exception={event.exception}",
        exc_info=True,
    )
    # 슬랙/이메일 알림
    await _send_failure_notification(
        job_id=event.job_id,
        error=str(event.exception),
        traceback=traceback.format_exception(
            type(event.exception), event.exception, event.exception.__traceback__
        ),
    )


async def _on_job_missed(event):
    """미스파이어 시 경고 로깅."""
    import logging
    logger = logging.getLogger("scheduler")
    logger.warning(f"Job missed: {event.job_id}")


async def _send_failure_notification(job_id: str, error: str, traceback: list[str]):
    """
    실패 알림 발송 (슬랙 웹훅 / 이메일).
    설정에 따라 발송 채널 결정.
    """
    import httpx

    if settings.SLACK_WEBHOOK_URL:
        async with httpx.AsyncClient() as client:
            await client.post(
                settings.SLACK_WEBHOOK_URL,
                json={
                    "text": (
                        f":rotating_light: *데이터 수집 실패*\n"
                        f"*Job*: `{job_id}`\n"
                        f"*Error*: {error}\n"
                        f"```{''.join(traceback[-5:])}```"
                    ),
                },
            )
```

### 6.2 작업 등록

```python
# app/scheduler/register_jobs.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.collectors.semas_collector import SemasCollector
# [Phase 2] from app.collectors.molit_collector import MolitCollector
from app.collectors.seoul_collector import SeoulCollector


def register_all_jobs(scheduler: AsyncIOScheduler):
    """전체 수집 작업 등록."""

    # ============================================================
    # 1. SEMAS 수집 (분기 1회)
    # ============================================================

    # 유동인구 수집: 분기 종료 후 15일차 시작, 매일 06:00
    scheduler.add_job(
        func="app.scheduler.tasks:run_semas_population",
        trigger=CronTrigger(
            month="1,4,7,10",   # 매 분기 시작월
            day=15,             # 15일부터
            hour=6,
            minute=0,
        ),
        id="semas_population_quarterly",
        name="SEMAS 유동인구 수집 (분기)",
        replace_existing=True,
    )

    # 추정매출 수집: 유동인구 완료 후 시작, 매일 07:00
    scheduler.add_job(
        func="app.scheduler.tasks:run_semas_revenue",
        trigger=CronTrigger(
            month="2,5,8,11",   # 유동인구 수집 완료 예상 후
            day=1,
            hour=7,
            minute=0,
        ),
        id="semas_revenue_quarterly",
        name="SEMAS 추정매출 수집 (분기)",
        replace_existing=True,
    )

    # 상가업소 수집: 분기 종료 후, 매일 08:00
    scheduler.add_job(
        func="app.scheduler.tasks:run_semas_stores",
        trigger=CronTrigger(
            month="1,4,7,10",
            day=20,
            hour=8,
            minute=0,
        ),
        id="semas_stores_quarterly",
        name="SEMAS 상가업소 수집 (분기)",
        replace_existing=True,
    )

    # ============================================================
    # 2. [Phase 2] 국토교통부 실거래가 (월 1회) — 부동산 에이전트 활성화 시 복원
    # ============================================================

    # [Phase 2] 상업용 매매 실거래가: 매월 20일 09:00
    # scheduler.add_job(
    #     func="app.scheduler.tasks:run_molit_trade",
    #     trigger=CronTrigger(day=20, hour=9, minute=0),
    #     id="molit_trade_monthly",
    #     name="MOLIT 상업용 매매 실거래가 (월간)",
    #     replace_existing=True,
    # )

    # [Phase 2] 상업용 전월세: 매월 20일 10:00
    # scheduler.add_job(
    #     func="app.scheduler.tasks:run_molit_rent",
    #     trigger=CronTrigger(day=20, hour=10, minute=0),
    #     id="molit_rent_monthly",
    #     name="MOLIT 상업용 전월세 (월간)",
    #     replace_existing=True,
    # )

    # ============================================================
    # 3. 서울 열린데이터 (월 1회)
    # ============================================================

    # 지하철 승하차: 매월 15일 11:00
    scheduler.add_job(
        func="app.scheduler.tasks:run_seoul_subway",
        trigger=CronTrigger(
            day=15,
            hour=11,
            minute=0,
        ),
        id="seoul_subway_monthly",
        name="서울 지하철 승하차 (월간)",
        replace_existing=True,
    )

    # 서울 생활인구: 매월 15일 12:00
    scheduler.add_job(
        func="app.scheduler.tasks:run_seoul_population",
        trigger=CronTrigger(
            day=15,
            hour=12,
            minute=0,
        ),
        id="seoul_population_monthly",
        name="서울 생활인구 (월간)",
        replace_existing=True,
    )

    # 카드매출: 매월 15일 13:00
    scheduler.add_job(
        func="app.scheduler.tasks:run_seoul_card_sales",
        trigger=CronTrigger(
            day=15,
            hour=13,
            minute=0,
        ),
        id="seoul_card_sales_monthly",
        name="서울 카드매출 (월간)",
        replace_existing=True,
    )

    # ============================================================
    # 4. Materialized View 갱신 (수집 완료 후)
    # ============================================================

    scheduler.add_job(
        func="app.scheduler.tasks:refresh_materialized_views",
        trigger=CronTrigger(
            day=25,             # 수집 완료 예상 후
            hour=2,
            minute=0,
        ),
        id="refresh_mv_monthly",
        name="Materialized View 갱신 (월간)",
        replace_existing=True,
    )

    # ============================================================
    # 5. 데이터 품질 점검 (일간)
    # ============================================================

    scheduler.add_job(
        func="app.scheduler.tasks:run_data_quality_check",
        trigger=CronTrigger(
            hour=3,
            minute=0,
        ),
        id="data_quality_daily",
        name="데이터 품질 점검 (일간)",
        replace_existing=True,
    )
```

### 6.3 작업 실행 함수

```python
# app/scheduler/tasks.py

from datetime import datetime

from app.collectors.semas_collector import SemasCollector
# [Phase 2] from app.collectors.molit_collector import MolitCollector
from app.collectors.seoul_collector import SeoulCollector
from app.database import get_async_session
from app.config.settings import settings


def _current_quarter_params() -> dict:
    """현재 시점 기준 수집 대상 분기 계산."""
    now = datetime.now()
    # 현재 월 기준으로 직전 분기 결정
    if now.month in (1, 2, 3):
        return {"year": now.year - 1, "quarter": 4}
    elif now.month in (4, 5, 6):
        return {"year": now.year, "quarter": 1}
    elif now.month in (7, 8, 9):
        return {"year": now.year, "quarter": 2}
    else:
        return {"year": now.year, "quarter": 3}


def _prev_month_params() -> dict:
    """전월 연/월 반환."""
    now = datetime.now()
    if now.month == 1:
        return {"year": now.year - 1, "month": 12}
    return {"year": now.year, "month": now.month - 1}


async def run_semas_population():
    """SEMAS 유동인구 수집 태스크."""
    async with get_async_session() as session:
        collector = SemasCollector(session, settings.SEMAS_API_KEY)
        try:
            params = _current_quarter_params()
            result = await collector.collect(target="population", **params)
            return result
        finally:
            await collector.close()


async def run_semas_revenue():
    """SEMAS 추정매출 수집 태스크."""
    async with get_async_session() as session:
        collector = SemasCollector(session, settings.SEMAS_API_KEY)
        try:
            params = _current_quarter_params()
            result = await collector.collect(target="revenue", **params)
            return result
        finally:
            await collector.close()


async def run_semas_stores():
    """SEMAS 상가업소 수집 태스크."""
    async with get_async_session() as session:
        collector = SemasCollector(session, settings.SEMAS_API_KEY)
        try:
            params = _current_quarter_params()
            result = await collector.collect(target="stores", **params)
            return result
        finally:
            await collector.close()


async def run_molit_trade():
    """MOLIT 매매 실거래가 수집."""
    async with get_async_session() as session:
        collector = MolitCollector(session, settings.MOLIT_API_KEY)
        try:
            params = _prev_month_params()
            result = await collector.collect(deal_type="trade", **params)
            return result
        finally:
            await collector.close()


async def run_molit_rent():
    """MOLIT 전월세 수집."""
    async with get_async_session() as session:
        collector = MolitCollector(session, settings.MOLIT_API_KEY)
        try:
            params = _prev_month_params()
            result = await collector.collect(deal_type="rent", **params)
            return result
        finally:
            await collector.close()


async def run_seoul_subway():
    """서울 지하철 승하차 수집."""
    async with get_async_session() as session:
        collector = SeoulCollector(session, settings.SEOUL_API_KEY)
        try:
            params = _prev_month_params()
            result = await collector.collect(target="subway", **params)
            return result
        finally:
            await collector.close()


async def run_seoul_population():
    """서울 생활인구 수집."""
    async with get_async_session() as session:
        collector = SeoulCollector(session, settings.SEOUL_API_KEY)
        try:
            params = _prev_month_params()
            result = await collector.collect(target="population", **params)
            return result
        finally:
            await collector.close()


async def run_seoul_card_sales():
    """서울 카드매출 수집."""
    async with get_async_session() as session:
        collector = SeoulCollector(session, settings.SEOUL_API_KEY)
        try:
            params = _prev_month_params()
            result = await collector.collect(target="card_sales", **params)
            return result
        finally:
            await collector.close()


async def refresh_materialized_views():
    """Materialized View 갱신."""
    async with get_async_session() as session:
        await session.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_real_estate_quarterly")
        await session.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_transit_quarterly")
        await session.commit()


async def run_data_quality_check():
    """데이터 품질 점검 태스크."""
    from app.monitoring.quality_checker import DataQualityChecker
    async with get_async_session() as session:
        checker = DataQualityChecker(session)
        report = await checker.run_all_checks()
        if report.has_critical_issues:
            await checker.send_alert(report)
        return report
```

### 6.4 스케줄 요약

**[Phase 1] 활성 잡**

| Job ID | Collector | 대상 데이터 | Cron 표현식 | 주기 | 담당 에이전트 |
|--------|-----------|-----------|------------|------|-------------|
| semas_population_quarterly | SEMAS | 유동인구 (data.go.kr #15012005) | `0 6 15 1,4,7,10 *` | 분기 1회 | 유동인구 |
| semas_revenue_quarterly | SEMAS | 추정매출 (OA-15572 경유) | `0 7 1 2,5,8,11 *` | 분기 1회 | 매출추정 |
| semas_stores_quarterly | SEMAS | 상가업소 목록 | `0 8 20 1,4,7,10 *` | 분기 1회 | 경쟁분석 / 입지 |
| seoul_subway_monthly | Seoul | 지하철 승하차 (CardSubwayStatsNew) | `0 11 15 * *` | 월 1회 | 입지 |
| seoul_population_monthly | Seoul | 서울 생활인구 (OA-15379) | `0 12 15 * *` | 월 1회 | 유동인구 핵심 |
| seoul_card_sales_monthly | Seoul | 서울 카드매출 추정 (OA-15572) | `0 13 15 * *` | 월 1회 | 매출추정 핵심 |
| refresh_mv_monthly | - | Materialized View 갱신 | `0 2 25 * *` | 월 1회 | - |
| data_quality_daily | - | 데이터 품질 점검 | `0 3 * * *` | 일 1회 | - |

**[Phase 2] 비활성 잡** (부동산 에이전트 활성화 시 등록)

| Job ID | Collector | 대상 데이터 | Cron 표현식 | 주기 |
|--------|-----------|-----------|------------|------|
| ~~molit_trade_monthly~~ | MOLIT | 매매 실거래가 | `0 9 20 * *` | 월 1회 |
| ~~molit_rent_monthly~~ | MOLIT | 전월세 실거래 | `0 10 20 * *` | 월 1회 |

---

## 7. 데이터 품질 모니터링

### 7.1 품질 점검 항목

```python
# app/monitoring/quality_checker.py

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class QualityIssue:
    check_name: str
    severity: str           # 'INFO', 'WARNING', 'CRITICAL'
    table_name: str
    description: str
    metric_value: Optional[float] = None
    threshold: Optional[float] = None


@dataclass
class QualityReport:
    checked_at: datetime = field(default_factory=datetime.utcnow)
    issues: list[QualityIssue] = field(default_factory=list)

    @property
    def has_critical_issues(self) -> bool:
        return any(i.severity == "CRITICAL" for i in self.issues)

    @property
    def summary(self) -> dict:
        return {
            "total_checks": len(self.issues),
            "critical": len([i for i in self.issues if i.severity == "CRITICAL"]),
            "warning": len([i for i in self.issues if i.severity == "WARNING"]),
            "info": len([i for i in self.issues if i.severity == "INFO"]),
        }


class DataQualityChecker:
    """데이터 품질 점검기."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def run_all_checks(self) -> QualityReport:
        """전체 품질 점검 실행."""
        report = QualityReport()

        # 1. 데이터 신선도 점검
        await self._check_freshness(report)

        # 2. 데이터 완전성 점검
        await self._check_completeness(report)

        # 3. 이상치 점검
        await self._check_anomalies(report)

        # 4. 참조 무결성 점검
        await self._check_referential_integrity(report)

        # 5. 수집 로그 점검
        await self._check_collection_logs(report)

        return report

    async def _check_freshness(self, report: QualityReport):
        """
        데이터 신선도 점검.
        각 테이블의 최신 데이터가 기대 주기 내에 있는지 확인.
        """
        freshness_rules = [
            {
                "table": "population_stats",
                "query": "SELECT MAX(collected_at) FROM population_stats",
                "max_age_days": 100,    # 분기 + 여유
                "severity": "CRITICAL",
            },
            {
                "table": "revenue_stats",
                "query": "SELECT MAX(collected_at) FROM revenue_stats",
                "max_age_days": 100,
                "severity": "CRITICAL",
            },
            {
                "table": "stores",
                "query": "SELECT MAX(collected_at) FROM stores",
                "max_age_days": 100,
                "severity": "WARNING",
            },
            {
                "table": "real_estate_transactions",
                "query": "SELECT MAX(collected_at) FROM real_estate_transactions",
                "max_age_days": 35,     # 월간 + 여유
                "severity": "WARNING",
            },
            {
                "table": "transit_stats",
                "query": "SELECT MAX(collected_at) FROM transit_stats",
                "max_age_days": 35,
                "severity": "WARNING",
            },
        ]

        for rule in freshness_rules:
            result = await self.db.execute(rule["query"])
            last_collected = result.scalar()

            if last_collected is None:
                report.issues.append(QualityIssue(
                    check_name="freshness",
                    severity="CRITICAL",
                    table_name=rule["table"],
                    description=f"{rule['table']}: 데이터 없음",
                ))
                continue

            age_days = (datetime.utcnow() - last_collected).days
            if age_days > rule["max_age_days"]:
                report.issues.append(QualityIssue(
                    check_name="freshness",
                    severity=rule["severity"],
                    table_name=rule["table"],
                    description=(
                        f"{rule['table']}: 최신 데이터 {age_days}일 경과 "
                        f"(임계값: {rule['max_age_days']}일)"
                    ),
                    metric_value=age_days,
                    threshold=rule["max_age_days"],
                ))

    async def _check_completeness(self, report: QualityReport):
        """
        데이터 완전성 점검.
        필수 필드 NULL 비율, 전체 레코드 수 등.
        """
        completeness_checks = [
            {
                "table": "population_stats",
                "query": """
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE pop_total = 0) AS zero_count,
                        COUNT(*) FILTER (WHERE pop_total IS NULL) AS null_count
                    FROM population_stats
                    WHERE year = EXTRACT(YEAR FROM NOW())
                """,
                "max_null_ratio": 0.05,
                "max_zero_ratio": 0.10,
            },
            {
                "table": "stores",
                "query": """
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE location IS NULL) AS null_location,
                        COUNT(*) FILTER (WHERE district_code IS NULL) AS null_district
                    FROM stores
                    WHERE status = 'ACTIVE'
                """,
                "max_null_ratio": 0.15,
                "max_zero_ratio": 0.20,
            },
            {
                "table": "districts",
                "query": """
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE boundary IS NULL) AS null_boundary
                    FROM districts
                    WHERE is_active = TRUE
                """,
                "max_null_ratio": 0.01,
                "max_zero_ratio": 0.01,
            },
        ]

        for check in completeness_checks:
            result = await self.db.execute(check["query"])
            row = result.fetchone()
            if row and row[0] > 0:
                total = row[0]
                null_ratio = row[2] / total if len(row) > 2 else 0
                if null_ratio > check["max_null_ratio"]:
                    report.issues.append(QualityIssue(
                        check_name="completeness",
                        severity="WARNING",
                        table_name=check["table"],
                        description=(
                            f"{check['table']}: NULL 비율 {null_ratio:.1%} "
                            f"(임계값: {check['max_null_ratio']:.1%})"
                        ),
                        metric_value=null_ratio,
                        threshold=check["max_null_ratio"],
                    ))

    async def _check_anomalies(self, report: QualityReport):
        """
        이상치 점검.
        최근 수집 데이터에서 전분기 대비 급격한 변동 탐지.
        """
        # 매출 급변 상권 수
        result = await self.db.execute("""
            WITH latest AS (
                SELECT district_code, revenue_total, year, quarter
                FROM revenue_stats
                WHERE (year, quarter) = (
                    SELECT (year, quarter) FROM revenue_stats
                    ORDER BY year DESC, quarter DESC LIMIT 1
                )
            ),
            prev AS (
                SELECT district_code, revenue_total
                FROM revenue_stats
                WHERE (year, quarter) = (
                    SELECT (year, quarter) FROM revenue_stats
                    ORDER BY year DESC, quarter DESC LIMIT 1 OFFSET 1
                )
            )
            SELECT COUNT(*)
            FROM latest l
            JOIN prev p ON l.district_code = p.district_code
            WHERE p.revenue_total > 0
              AND ABS(l.revenue_total - p.revenue_total)::FLOAT / p.revenue_total > 3.0
        """)
        anomaly_count = result.scalar() or 0

        if anomaly_count > 10:
            report.issues.append(QualityIssue(
                check_name="anomaly",
                severity="CRITICAL",
                table_name="revenue_stats",
                description=f"매출 300% 이상 급변 상권: {anomaly_count}개",
                metric_value=anomaly_count,
                threshold=10,
            ))

    async def _check_referential_integrity(self, report: QualityReport):
        """참조 무결성 점검 (파티션 테이블 FK 대체)."""
        # population_stats의 district_code가 districts에 존재하는지
        result = await self.db.execute("""
            SELECT COUNT(DISTINCT ps.district_code)
            FROM population_stats ps
            LEFT JOIN districts d ON ps.district_code = d.district_code
            WHERE d.district_code IS NULL
        """)
        orphan_count = result.scalar() or 0

        if orphan_count > 0:
            report.issues.append(QualityIssue(
                check_name="referential_integrity",
                severity="WARNING",
                table_name="population_stats",
                description=f"고아 district_code {orphan_count}개 (districts 테이블에 없음)",
                metric_value=orphan_count,
                threshold=0,
            ))

    async def _check_collection_logs(self, report: QualityReport):
        """최근 수집 작업 실패 여부 점검."""
        result = await self.db.execute("""
            SELECT collector_name, status, COUNT(*)
            FROM collection_logs
            WHERE started_at > NOW() - INTERVAL '7 days'
              AND status IN ('FAILURE', 'PARTIAL_FAILURE')
            GROUP BY collector_name, status
        """)
        rows = result.fetchall()

        for collector_name, status, count in rows:
            severity = "CRITICAL" if status == "FAILURE" else "WARNING"
            report.issues.append(QualityIssue(
                check_name="collection_log",
                severity=severity,
                table_name="collection_logs",
                description=(
                    f"최근 7일간 {collector_name} 수집 {status}: {count}건"
                ),
                metric_value=count,
            ))

    async def send_alert(self, report: QualityReport):
        """품질 리포트 알림 발송."""
        import httpx
        from app.config.settings import settings

        if not settings.SLACK_WEBHOOK_URL:
            return

        issues_text = "\n".join(
            f"- [{i.severity}] {i.description}"
            for i in report.issues
            if i.severity in ("CRITICAL", "WARNING")
        )

        async with httpx.AsyncClient() as client:
            await client.post(
                settings.SLACK_WEBHOOK_URL,
                json={
                    "text": (
                        f":bar_chart: *데이터 품질 리포트* ({report.checked_at:%Y-%m-%d %H:%M})\n"
                        f"Critical: {report.summary['critical']} | "
                        f"Warning: {report.summary['warning']}\n\n"
                        f"{issues_text}"
                    ),
                },
            )
```

### 7.2 모니터링 대시보드 쿼리

```sql
-- 테이블별 데이터 현황 요약
SELECT
    'districts' AS table_name,
    COUNT(*) AS total_records,
    MAX(collected_at) AS last_collected,
    NULL AS latest_period
FROM districts WHERE is_active = TRUE

UNION ALL

SELECT
    'population_stats',
    COUNT(*),
    MAX(collected_at),
    MAX(year || 'Q' || quarter)
FROM population_stats

UNION ALL

SELECT
    'revenue_stats',
    COUNT(*),
    MAX(collected_at),
    MAX(year || 'Q' || quarter)
FROM revenue_stats

UNION ALL

SELECT
    'stores',
    COUNT(*),
    MAX(collected_at),
    NULL
FROM stores WHERE status = 'ACTIVE'

UNION ALL

SELECT
    'real_estate_transactions',
    COUNT(*),
    MAX(collected_at),
    MAX(deal_year || '-' || LPAD(deal_month::TEXT, 2, '0'))
FROM real_estate_transactions

UNION ALL

SELECT
    'transit_stats',
    COUNT(*),
    MAX(collected_at),
    MAX(year || '-' || LPAD(month::TEXT, 2, '0'))
FROM transit_stats;
```

---

## 8. 마이그레이션 전략

### 8.1 Alembic 설정

```python
# alembic/env.py (핵심 설정)

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from geoalchemy2 import Geometry  # PostGIS 타입 인식

from app.models.db_models import Base
from app.config.settings import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()
```

```ini
# alembic.ini (핵심 설정)
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic
```

### 8.2 초기 마이그레이션 생성

```bash
# 마이그레이션 초기화
alembic init alembic

# 초기 스키마 마이그레이션 생성
alembic revision --autogenerate -m "initial_schema_with_postgis"

# 마이그레이션 실행
alembic upgrade head
```

### 8.3 초기 데이터 시딩 스크립트

```python
# scripts/seed_initial_data.py

"""
초기 데이터 시딩 스크립트.

실행 순서:
  1. 확장 모듈 활성화 (PostGIS 등)
  2. Enum 타입 생성
  3. 테이블 생성 (Alembic migration)
  4. code_mappings 초기 데이터 적재
  5. unit_prices 초기 데이터 적재
  6. startup_costs 초기 데이터 적재
  7. Materialized View 생성
  8. districts 초기 수집 (SEMAS API)
"""

import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings


async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. PostGIS 확장 활성화
        await session.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        await session.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        await session.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        await session.commit()

        # 2. 코드매핑 초기 데이터 (CSV에서 로드)
        await _load_code_mappings(session)

        # 3. 객단가 초기 데이터
        seed_sql_path = Path(__file__).parent / "sql" / "seed_unit_prices.sql"
        if seed_sql_path.exists():
            sql = seed_sql_path.read_text(encoding="utf-8")
            await session.execute(sql)
            await session.commit()

        # 4. 초기투자비 초기 데이터
        seed_sql_path = Path(__file__).parent / "sql" / "seed_startup_costs.sql"
        if seed_sql_path.exists():
            sql = seed_sql_path.read_text(encoding="utf-8")
            await session.execute(sql)
            await session.commit()

        # 5. Materialized View 생성
        await _create_materialized_views(session)

        print("초기 데이터 시딩 완료")

    await engine.dispose()


async def _load_code_mappings(session: AsyncSession):
    """행정동-법정동 연계 CSV 로드."""
    import csv

    csv_path = Path(__file__).parent / "data" / "admin_legal_mapping.csv"
    if not csv_path.exists():
        print(f"WARNING: {csv_path} 파일 없음, 코드매핑 시딩 생략")
        return

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            await session.execute(
                """
                INSERT INTO code_mappings (
                    admin_dong_code, admin_dong_name,
                    legal_dong_code, legal_dong_name,
                    sigungu_code, sigungu_name,
                    sido_code, sido_name,
                    is_primary
                ) VALUES (
                    :adc, :adn, :ldc, :ldn,
                    :sgc, :sgn, :sc, :sn, TRUE
                )
                ON CONFLICT DO NOTHING
                """,
                {
                    "adc": row["admin_dong_code"],
                    "adn": row["admin_dong_name"],
                    "ldc": row["legal_dong_code"],
                    "ldn": row["legal_dong_name"],
                    "sgc": row["admin_dong_code"][:5],
                    "sgn": row.get("sigungu_name", ""),
                    "sc": row["admin_dong_code"][:2],
                    "sn": row.get("sido_name", ""),
                },
            )
    await session.commit()
    print("코드매핑 시딩 완료")


async def _create_materialized_views(session: AsyncSession):
    """Materialized View 생성."""
    # 실거래가 분기 집계 뷰
    await session.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_real_estate_quarterly AS
        SELECT
            legal_dong_code, deal_type,
            deal_year AS year,
            CEIL(deal_month / 3.0)::INT AS quarter,
            COUNT(*) AS deal_count,
            AVG(deal_amount) AS avg_deal_amount,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY deal_amount) AS median_deal_amount,
            MIN(deal_amount) AS min_deal_amount,
            MAX(deal_amount) AS max_deal_amount,
            AVG(area_sqm) AS avg_area_sqm
        FROM real_estate_transactions
        WHERE deal_amount IS NOT NULL AND deal_amount > 0
        GROUP BY legal_dong_code, deal_type, deal_year, CEIL(deal_month / 3.0)::INT
    """)

    # 대중교통 분기 집계 뷰
    await session.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_transit_quarterly AS
        SELECT
            station_name, station_code, transit_type, line_name,
            year, CEIL(month / 3.0)::INT AS quarter,
            AVG(boarding_total) AS avg_daily_boarding,
            AVG(alighting_total) AS avg_daily_alighting,
            SUM(boarding_total) AS total_boarding,
            SUM(alighting_total) AS total_alighting
        FROM transit_stats
        GROUP BY station_name, station_code, transit_type, line_name, year, CEIL(month / 3.0)::INT
    """)

    await session.commit()
    print("Materialized View 생성 완료")


if __name__ == "__main__":
    asyncio.run(seed())
```

### 8.4 마이그레이션 운영 절차

```
1. 개발 환경에서 모델 변경 후:
   $ alembic revision --autogenerate -m "add_column_xxx"
   $ alembic upgrade head    # 로컬 DB 반영

2. 코드 리뷰 후 staging 배포:
   $ alembic upgrade head    # staging DB 반영
   $ python scripts/seed_initial_data.py  # 필요 시 시딩

3. Production 배포:
   $ alembic upgrade head    # production DB 반영 (다운타임 최소화)

4. 롤백 필요 시:
   $ alembic downgrade -1    # 직전 버전으로 롤백

주의사항:
  - 파티션 테이블 변경은 autogenerate가 감지하지 못하므로 수동 마이그레이션 필요
  - PostGIS 컬럼 추가/변경은 GeoAlchemy2 타입 명시 필요
  - Materialized View는 Alembic 관리 대상이 아니므로 별도 SQL 스크립트로 관리
  - 대규모 데이터가 있는 테이블에 인덱스 추가 시 CONCURRENTLY 옵션 사용
```

---

## 9. LightRAG 연동

### 9.1 연동 시점

수집 및 전처리가 완료된 데이터를 LightRAG에 적재하는 시점:

```
1. 분석 결과 저장 시:
   - analysis_results 테이블에 INSERT 후
   - result_summary (자연어 텍스트)를 LightRAG에 동시 적재

2. 분기별 상권 요약 생성 시:
   - 유동인구, 매출, 점포수 등을 종합한 상권 프로파일 텍스트 생성
   - LightRAG에 상권 단위 문서로 적재

3. 실거래가 요약 시:
   - 지역별 월간 실거래가 트렌드 텍스트 생성
   - LightRAG 적재
```

### 9.2 LightRAG 문서 형식

```python
# app/rag/document_builder.py

from typing import Any


def build_district_profile(
    district_code: str,
    district_name: str,
    population: dict,
    revenue: dict,
    stores: dict,
    transit: dict,
) -> str:
    """상권 프로파일 RAG 문서 생성."""
    return f"""
# 상권 프로파일: {district_name} ({district_code})

## 유동인구 현황 ({population.get('year')}년 {population.get('quarter')}분기)
- 총 유동인구: {population.get('total', 0):,}명/일
- 주중 평균: {population.get('weekday_avg', 0):,}명/일
- 주말 평균: {population.get('weekend_avg', 0):,}명/일
- 피크 시간대: {population.get('peak_time', 'N/A')}
- 주요 연령대: {population.get('main_age_group', 'N/A')}
- 전분기 대비: {population.get('change_ratio', 0):+.1f}%

## 매출 현황
- 총 추정매출: {revenue.get('total', 0):,.0f}원/분기
- 업종 수: {revenue.get('industry_count', 0)}개
- 상위 업종: {revenue.get('top_industries', 'N/A')}
- 평균 객단가: {revenue.get('avg_ticket', 0):,.0f}원
- 전분기 대비: {revenue.get('change_ratio', 0):+.1f}%

## 점포 현황
- 영업중 점포: {stores.get('active', 0)}개
- 신규 개업: {stores.get('new', 0)}개
- 폐업: {stores.get('closed', 0)}개
- 업종 다양성 지수: {stores.get('diversity_index', 0):.2f}

## 교통 접근성
- 최근접 지하철역: {transit.get('nearest_station', 'N/A')}
- 일 평균 승하차: {transit.get('daily_transit', 0):,}명
""".strip()


def build_analysis_document(
    analysis_type: str,
    params: dict,
    result: dict,
    summary: str,
) -> str:
    """분석 결과 RAG 문서 생성."""
    return f"""
# 분석 결과: {analysis_type}

## 분석 조건
{_dict_to_markdown(params)}

## 분석 결과 요약
{summary}

## 주요 지표
{_dict_to_markdown(result.get('metrics', {}))}

## 위험 요인
{chr(10).join('- ' + r for r in result.get('risks', []))}

## 기회 요인
{chr(10).join('- ' + o for o in result.get('opportunities', []))}
""".strip()


def _dict_to_markdown(d: dict, indent: int = 0) -> str:
    """dict를 마크다운 리스트로 변환."""
    lines = []
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{prefix}- **{k}**:")
            lines.append(_dict_to_markdown(v, indent + 1))
        else:
            lines.append(f"{prefix}- **{k}**: {v}")
    return "\n".join(lines)
```

### 9.3 LightRAG 적재 흐름

```python
# app/rag/indexer.py

from lightrag import LightRAG


class RAGIndexer:
    """LightRAG 문서 적재기."""

    def __init__(self, rag: LightRAG):
        self.rag = rag

    async def index_district_profile(self, document: str, metadata: dict):
        """상권 프로파일 적재."""
        await self.rag.ainsert(
            document,
            metadata={
                "type": "district_profile",
                "district_code": metadata.get("district_code"),
                "period": metadata.get("period"),
                **metadata,
            },
        )

    async def index_analysis_result(self, document: str, metadata: dict):
        """분석 결과 적재."""
        await self.rag.ainsert(
            document,
            metadata={
                "type": "analysis_result",
                "analysis_type": metadata.get("analysis_type"),
                **metadata,
            },
        )

    async def reindex_all_districts(self, db_session):
        """전체 상권 프로파일 재색인 (분기별 실행)."""
        from app.rag.document_builder import build_district_profile

        result = await db_session.execute(
            "SELECT district_code, district_name FROM districts WHERE is_active = TRUE"
        )
        districts = result.fetchall()

        for code, name in districts:
            # 각 상권의 최신 데이터 조합하여 프로파일 생성
            population = await self._get_latest_population(db_session, code)
            revenue = await self._get_latest_revenue(db_session, code)
            stores = await self._get_store_summary(db_session, code)
            transit = await self._get_transit_info(db_session, code)

            document = build_district_profile(code, name, population, revenue, stores, transit)
            await self.index_district_profile(document, {
                "district_code": code,
                "district_name": name,
                "period": f"{population.get('year', '')}Q{population.get('quarter', '')}",
            })

    async def _get_latest_population(self, session, district_code: str) -> dict:
        result = await session.execute(
            """
            SELECT year, quarter, pop_total, pop_male, pop_female,
                   pop_mon, pop_tue, pop_wed, pop_thu, pop_fri, pop_sat, pop_sun
            FROM population_stats
            WHERE district_code = :dc
            ORDER BY year DESC, quarter DESC
            LIMIT 1
            """,
            {"dc": district_code},
        )
        row = result.fetchone()
        if not row:
            return {}
        weekday_avg = (row[5] + row[6] + row[7] + row[8] + row[9]) / 5
        weekend_avg = (row[10] + row[11]) / 2
        return {
            "year": row[0], "quarter": row[1], "total": row[2],
            "weekday_avg": int(weekday_avg), "weekend_avg": int(weekend_avg),
        }

    async def _get_latest_revenue(self, session, district_code: str) -> dict:
        result = await session.execute(
            """
            SELECT SUM(revenue_total), COUNT(DISTINCT industry_code_l),
                   SUM(revenue_count)
            FROM revenue_stats
            WHERE district_code = :dc
              AND (year, quarter) = (
                  SELECT (year, quarter) FROM revenue_stats
                  WHERE district_code = :dc
                  ORDER BY year DESC, quarter DESC LIMIT 1
              )
            """,
            {"dc": district_code},
        )
        row = result.fetchone()
        if not row or not row[0]:
            return {}
        avg_ticket = row[0] / row[2] if row[2] and row[2] > 0 else 0
        return {"total": row[0], "industry_count": row[1], "avg_ticket": avg_ticket}

    async def _get_store_summary(self, session, district_code: str) -> dict:
        result = await session.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'ACTIVE') AS active,
                COUNT(*) FILTER (WHERE status = 'CLOSED' AND close_date > NOW() - INTERVAL '90 days') AS closed,
                COUNT(*) FILTER (WHERE open_date > NOW() - INTERVAL '90 days') AS new_open
            FROM stores WHERE district_code = :dc
            """,
            {"dc": district_code},
        )
        row = result.fetchone()
        return {"active": row[0] or 0, "closed": row[1] or 0, "new": row[2] or 0} if row else {}

    async def _get_transit_info(self, session, district_code: str) -> dict:
        # 상권 중심점 기준 가장 가까운 지하철역 조회
        result = await session.execute(
            """
            SELECT ts.station_name, ts.boarding_total + ts.alighting_total AS daily_transit
            FROM transit_stats ts
            JOIN districts d ON d.district_code = :dc
            WHERE ts.transit_type = 'SUBWAY'
              AND ts.location IS NOT NULL
              AND (ts.year, ts.month) = (
                  SELECT (year, month) FROM transit_stats
                  ORDER BY year DESC, month DESC LIMIT 1
              )
            ORDER BY ST_Distance(ts.location, d.center_point)
            LIMIT 1
            """,
            {"dc": district_code},
        )
        row = result.fetchone()
        return {"nearest_station": row[0], "daily_transit": row[1]} if row else {}
```

---

## 부록 A: 환경 변수 설정

```python
# app/config/settings.py

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 데이터베이스
    DATABASE_URL: str = "postgresql+asyncpg://marketscope:password@localhost:5432/marketscope"

    # API 키
    SEMAS_API_KEY: str = ""      # data.go.kr 소상공인진흥공단
    MOLIT_API_KEY: str = ""      # data.go.kr 국토교통부
    SEOUL_API_KEY: str = ""      # openapi.seoul.go.kr

    # 알림
    SLACK_WEBHOOK_URL: str = ""

    # 스케줄러
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TIMEZONE: str = "Asia/Seoul"

    # LightRAG
    LIGHTRAG_WORKING_DIR: str = "./lightrag_data"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

## 부록 B: 전체 ERD 관계도

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│   districts  │       │ population_stats │       │  revenue_stats   │
│──────────────│       │──────────────────│       │──────────────────│
│ district_code│◄──────│ district_code    │       │ district_code    │──►districts
│ district_name│       │ year, quarter    │       │ industry_code_l  │
│ district_type│       │ pop_total        │       │ year, quarter    │
│ boundary     │       │ pop_male/female  │       │ revenue_total    │
│ center_point │       │ pop_age_*        │       │ revenue_count    │
│ ...          │       │ pop_time_*       │       │ avg_ticket_price │
└──────┬───────┘       └──────────────────┘       └──────────────────┘
       │
       │  1:N
       ▼
┌──────────────┐       ┌──────────────────────┐   ┌──────────────────┐
│    stores    │       │real_estate_transactions│   │  transit_stats   │
│──────────────│       │─────────────────────  │   │──────────────────│
│ store_name   │       │ deal_type             │   │ transit_type     │
│ district_code│       │ legal_dong_code       │   │ station_name     │
│ industry_*   │       │ deal_amount           │   │ location         │
│ location     │       │ deposit/monthly_rent  │   │ year, month      │
│ status       │       │ deal_year, deal_month │   │ boarding_total   │
│ ...          │       │ area_sqm              │   │ alighting_total  │
└──────────────┘       └──────────────────────┘   └──────────────────┘

┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│ unit_prices  │       │  startup_costs   │       │ code_mappings    │
│──────────────│       │──────────────────│       │──────────────────│
│ industry_*   │       │ industry_*       │       │ admin_dong_code  │
│ district_grade│      │ interior_cost/평  │      │ legal_dong_code  │
│ avg_ticket   │       │ equipment_cost/平 │      │ district_code    │
│ daily_customers│     │ franchise_fee    │       │ overlap_ratio    │
│ ...          │       │ total_estimate   │       │ is_primary       │
└──────────────┘       └──────────────────┘       └──────────────────┘

┌──────────────────┐   ┌──────────────────┐       ┌──────────────────┐
│ analysis_results │   │     users        │       │ collection_logs  │
│──────────────────│   │──────────────────│       │──────────────────│
│ user_id ─────────│──►│ id               │       │ collector_name   │
│ analysis_type    │   │ email            │       │ status           │
│ request_params   │   │ role             │       │ records_fetched  │
│ result_data      │   │ subscription_plan│       │ error_message    │
│ score            │   │ ...              │       │ ...              │
└──────────────────┘   └──────────────────┘       └──────────────────┘
```
