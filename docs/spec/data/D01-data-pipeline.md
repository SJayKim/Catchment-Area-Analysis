# D01. 데이터 파이프라인 Spec

> 공공데이터 수집 → 변환 → PostgreSQL 적재 파이프라인. 상세 레이어 구조는 [../../architecture/data.md](../../architecture/data.md) 참조.

## 1. 개요

| 항목 | 내용 |
|---|---|
| 목적 | 서울 상권 관련 공공데이터를 수집하여 PostGIS DB 에 적재 |
| Phase | 1B — **완료** (2025Q4 기준 적재 완료) |
| 갱신 주기 | 분기별 (현재 CLI 수동 실행, 스케줄러는 향후 계획) |
| 적재 현황 | districts 1,650 / floating_population 9,888 / estimated_sales 21,333 / stores 75,985 / resident_population 39,288 |

## 2. 데이터 소스

| 데이터셋 | 출처 | API / 서비스 | 적재 테이블 | 상태 |
|---|---|---|---|---|
| 상권 영역 (폴리곤) | 서울시 | SHP 파일 (`data/shp/`) | `districts.boundary` | ✅ |
| 유동인구 | 서울 열린데이터 | `VwsmTrdarFlpopQq` | `floating_population` | ✅ |
| 추정 매출 | 서울 열린데이터 | `VwsmTrdarSelngQq` | `estimated_sales` | ✅ |
| 점포 현황 | 서울 열린데이터 | `VwsmTrdarStorQq` | `stores` | ✅ |
| 직장 인구 | 서울 열린데이터 | `VwsmTrdarWrcPopltnQq` | `resident_population` (worker) | ✅ |
| 상주 인구 | 서울 열린데이터 | OA-15584 CSV | `resident_population` (resident) | ✅ |
| 점포 이력 | 공공데이터포털 | data.go.kr 상가정보 | `store_history` | ⏳ 미연동 |
| 업종 메타 | 내부 시드 | `seed_category_metadata.py` | `category_metadata` | ✅ |

## 3. ETL 구조 (`server/server/data/etl/`)

```
etl/
├── runner.py                 # CLI: python -m server.data.etl.runner run 2025Q4
├── base.py                   # BaseCollector (httpx async + tenacity 재시도)
├── seoul_opendata.py         # 서울 열린데이터 수집 (4 서비스)
├── shp_collector.py          # SHP → PostGIS POLYGON 변환
├── csv_collector.py          # 상주인구 OA-15584
├── transformers.py           # 좌표변환 / unpivot / 성별·연령 매핑
├── loader.py                 # bulk UPSERT (batch_size=1000)
└── seed_category_metadata.py # category_metadata 시드
```

### 3.1 주요 컴포넌트

- **BaseCollector**: 비동기 `httpx.AsyncClient`, tenacity 3회 재시도(지수 백오프), 페이지네이션 1000건/page
- **SeoulOpenDataCollector**: API 4종 수집. `SEOUL_OPENDATA_API_KEY` 필수
- **ShpCollector**: geopandas 로 SHP 파싱 → WKT POLYGON → PostGIS 적재
- **Transformers**: 원본 필드 → DB 스키마 매핑 (아래 §4)
- **Loader**: `ON CONFLICT (district_code, …) DO UPDATE` 패턴, `asyncpg` copy-batch 1000 이하 유지 (`memory/feedback_asyncpg_batch.md`)

## 4. 변환 규칙

| 원본 필드 | 변환 | DB 컬럼 |
|---|---|---|
| 상권_코드 | 그대로 | `districts.code` |
| 상권_코드_명 | 그대로 | `districts.name` |
| 상권_구분_코드 | 매핑 (A→골목상권 / D→발달 / R→전통 / U→관광특구) | `districts.type` |
| 좌표 목록 | WKT POLYGON (EPSG:4326) | `districts.boundary` |
| 기준_분기_코드 | YYYYQN 형식 (예: 2025Q4) | `quarter` |
| 성별_구분_코드 | 1→M, 2→F | `gender` |
| 연령대_구분_코드 | 10→10s … 60→60plus | `age_group` |
| 시간대_N_유동인구_수 | unpivot → 행 변환 | `time_slot` + `population` |
| THSMON_SELNG_AMT | 분기 누적(원) → 컬럼명은 `monthly_sales` 이지만 **월 환산은 Repository 에서 수행** | `estimated_sales.monthly_sales` |

## 5. 적재 전략

| 전략 | 설명 |
|---|---|
| UPSERT | `(district_code, category_code, quarter)` 복합키 기준 |
| 배치 크기 | `batch_size=1000`, 동시 요청 `max_concurrency=3` |
| 재시도 | `max_retries=3`, 지수 백오프 |
| 멱등성 | 동일 분기 재실행 시 UPDATE |
| 실패 처리 | 페이지 단위 실패 로깅, 개별 레코드 에러는 skip + 카운트 |

## 6. 스케줄러

- **현재**: CLI 수동 실행만 지원 (`python -m server.data.etl.runner run 2025Q4`)
- **향후**: GitHub Actions cron (분기 시작 새벽 3시) 또는 Celery Beat
- **캐시 무효화**: ETL 완료 후 `scripts/flush_cache.py` 로 Redis 초기화 필요

## 7. 환경 변수

| 변수 | 용도 |
|---|---|
| `SEOUL_OPENDATA_API_KEY` | 서울 열린데이터 광장 API 키 (필수) |
| `DATA_GO_KR_API_KEY` | 공공데이터포털 API 키 (store_history 연동 시) |
| `DATABASE_URL` / `DATABASE_URL_SYNC` | PostgreSQL 연결 (async + Alembic용) |

## 8. 운영 스크립트

| 스크립트 | 용도 |
|---|---|
| `scripts/setup_db.py` | 신규 환경 DB 초기화 (migrate + seed) |
| `scripts/generate_seed.py` | 시드 덤프 생성 |
| `scripts/backup_db.sh` | DB 백업 (pg_dump) |
| `scripts/verify_sales_units.py` | 매출 단위 변환 정상성 검증 |
| `scripts/flush_cache.py` | Redis 캐시 flush |
| `server/scripts/cleanup_alembic.py` | stale `alembic_version` 정리 |

## 9. 수용 기준

- [x] 서울 열린데이터 API 에서 4개 서비스 수집 가능
- [x] SHP 파일에서 상권 폴리곤 적재 가능
- [x] 수집 데이터가 DB 스키마에 맞게 변환/적재
- [x] 중복 적재 시 기존 데이터 UPDATE (UPSERT 멱등성)
- [x] ETL 실패 시 페이지 단위 재시도 + 에러 로깅
- [x] 1개 분기 전체 ETL 30분 이내 완료 (실측 ~15분)
- [ ] data.go.kr 점포 이력 연동 (미완)
- [ ] 스케줄러 자동 실행 (미완)

## 10. 데이터 품질 주의사항

1. **매출 단위 혼동**: DB `monthly_sales` 컬럼은 실제로는 **분기 누적**. Repository 층에서 `/ MONTHS_PER_QUARTER (=3)` 로 월 환산 (2026-04-17 fix).
2. **boundary NULL**: SHP 적재 전에는 `districts.boundary` NULL → 지도 폴리곤 렌더링 불가. Circle fallback 필요.
3. **store_history 미적재**: data.go.kr 미연동 상태. Real 모드에서 F08 리스크는 `stores` 개폐업 수로 파생 계산.
4. **한글 조사 strip**: 검색 전처리 필수 (`memory/feedback_korean_particles.md`).
