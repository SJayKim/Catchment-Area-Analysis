# D01. 데이터 파이프라인 Spec

> 공공데이터 수집 → 변환 → PostgreSQL 적재 파이프라인

---

## 1. 개요

| 항목 | 내용 |
|------|------|
| 목적 | 서울 상권 관련 공공데이터를 수집하여 DB에 적재 |
| Phase | 0 (선행 작업) |
| 갱신 주기 | 분기별 (수동 트리거 또는 Celery 스케줄러) |

## 2. 데이터 소스

| 데이터셋 | 출처 | API/다운로드 | 적재 테이블 |
|----------|------|-------------|-------------|
| 상권 영역 정보 (폴리곤) | 서울 열린데이터 광장 | REST API | `districts` |
| 유동인구 (시간대/연령/성별) | 서울 열린데이터 광장 | REST API | `floating_population` |
| 추정 매출 (업종별/시간대별) | 서울 열린데이터 광장 | REST API | `estimated_sales` |
| 상주/직장 인구 | 서울 열린데이터 광장 | REST API | `resident_population` |
| 상가(점포) 정보 | 소상공인시장진흥공단 (data.go.kr) | REST API | `stores`, `store_history` |

## 3. ETL 파이프라인 구조

```
[수집 단계]                    [변환 단계]              [적재 단계]
API 호출                      데이터 정제/매핑          DB INSERT
─────────                     ────────────             ──────────
서울 열린데이터 API ──→ JSON ──→ 컬럼 매핑 ──→ Validation ──→ PostgreSQL
data.go.kr API     ──→ JSON ──→ 코드 정규화 ──→ 중복 제거  ──→ UPSERT
```

## 4. 수집 모듈

### 4.1 서울 열린데이터 수집 (`server/data/etl/seoul_opendata.py`)

```python
# 주요 함수
async def fetch_district_polygons(quarter: str) -> list[dict]
async def fetch_floating_population(quarter: str) -> list[dict]
async def fetch_estimated_sales(quarter: str) -> list[dict]
async def fetch_resident_population(quarter: str) -> list[dict]
```

- 서울 열린데이터 API 키 필요 (`SEOUL_OPENDATA_API_KEY`)
- 페이지네이션 처리 (1000건/page)
- 요청 실패 시 3회 재시도 (exponential backoff)

### 4.2 소상공인진흥공단 수집 (`server/data/etl/semas.py`)

```python
async def fetch_store_info(quarter: str) -> list[dict]
async def fetch_store_history() -> list[dict]  # 전체 스냅샷 비교 기반
```

- data.go.kr API 키 필요 (`DATA_GO_KR_API_KEY`)
- XML 응답 → JSON 변환

## 5. 변환 규칙

| 원본 필드 | 변환 | 대상 필드 |
|-----------|------|-----------|
| 상권_코드 | 그대로 | `district_code` |
| 상권_코드_명 | 그대로 | `district_name` |
| 상권_구분_코드 | 매핑 (A→골목상권, ...) | `district_type` |
| 좌표 목록 | WKT POLYGON 변환 | `boundary` (PostGIS) |
| 기준_분기_코드 | YYYYQN 형식 | `quarter` |
| 성별_구분_코드 | 1→M, 2→F | `gender` |
| 연령대_구분_코드 | 10→10s, 20→20s, ... | `age_group` |
| 시간대_N | 컬럼 → 행 변환 (unpivot) | `time_slot` + `population` |

## 6. 적재 전략

| 전략 | 설명 |
|------|------|
| UPSERT | `district_code` + `quarter` 기준 중복 시 UPDATE |
| 트랜잭션 | 테이블별 전체 적재 성공 시에만 COMMIT |
| 백업 | 적재 전 기존 분기 데이터를 `_backup` 테이블에 복사 |
| 검증 | 적재 후 row count 비교, NULL 비율 체크 |

## 7. 스케줄러 (`server/data/etl/scheduler.py`)

```python
# Celery Beat 또는 수동 트리거
@celery_app.task
def run_quarterly_etl(quarter: str):
    """분기별 전체 ETL 실행"""
    # 1. 수집
    # 2. 변환
    # 3. 적재
    # 4. 캐시 무효화 (Redis FLUSHDB)
    # 5. 결과 로깅
```

## 8. 환경 변수

| 변수 | 용도 |
|------|------|
| `SEOUL_OPENDATA_API_KEY` | 서울 열린데이터 광장 API 키 |
| `DATA_GO_KR_API_KEY` | 공공데이터포털 API 키 |
| `DATABASE_URL` | PostgreSQL 연결 문자열 |

## 9. 수용 기준 (Acceptance Criteria)

- [ ] 서울 열린데이터 API에서 상권 폴리곤 데이터를 수집할 수 있다
- [ ] 유동인구, 추정매출, 상주인구 데이터를 수집할 수 있다
- [ ] 소상공인진흥공단 API에서 점포 정보를 수집할 수 있다
- [ ] 수집 데이터가 DB 스키마에 맞게 변환/적재된다
- [ ] 중복 적재 시 기존 데이터가 정상적으로 업데이트된다
- [ ] ETL 실패 시 롤백되고 에러가 로깅된다
- [ ] 1개 분기 전체 ETL이 30분 이내에 완료된다

---

*작성일: 2026-03-24*
