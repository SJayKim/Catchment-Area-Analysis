# Database Setup Guide

> MarketScope AI 데이터베이스 셋업 가이드.
> 두 가지 경로 제공: Quick Start (시드 복원, 30초) / Full ETL (API 수집, 5~10분)

---

## 사전 요구사항

| 항목 | 버전 | 확인 명령 |
|------|------|-----------|
| Docker Desktop | 4.x+ | `docker --version` |
| Python | 3.12+ | `python --version` |
| Git LFS | 3.x+ | `git lfs version` |

Git LFS가 없으면:
```bash
git lfs install   # 최초 1회
git lfs pull      # seed dump 파일 다운로드
```

---

## Quick Start (30초, API 키 불필요)

pg_dump 시드 파일에서 전체 DB를 복원합니다. 1,650개 상권 + 유동인구/매출/점포 데이터 포함.

```bash
# 1. 환경 변수 파일 복사
cp .env.example .env
# .env에서 ANTHROPIC_API_KEY, NEXT_PUBLIC_KAKAO_MAP_KEY 설정

# 2. DB 셋업 (한 커맨드)
python scripts/setup_db.py --quick
```

이것만으로 끝입니다. 내부적으로:
1. `docker compose up -d db redis` (PostgreSQL + Redis 기동)
2. `alembic upgrade head` (테이블 생성)
3. `pg_restore` (시드 데이터 복원)

### 복원되는 데이터

| 테이블 | 행 수 | 분기 | 설명 |
|--------|------:|------|------|
| districts | 1,650 | 전체 | 상권 폴리곤 (PostGIS) |
| floating_population | 9,888 | 2025Q4 | 시간대별 유동인구 |
| estimated_sales | 21,333 | 2025Q4 | 업종별 추정매출 |
| stores | 75,985 | 2025Q4 | 점포 현황 |
| resident_population | 19,692 | 2025Q4 | 직장인구 |

---

## Full ETL (5~10분, API 키 필요)

서울 열린데이터 API에서 직접 데이터를 수집합니다. 최신 분기 데이터가 필요하거나 데이터를 커스터마이징할 때 사용.

### 1. API 키 발급

| 키 | 발급처 | 필수 |
|----|--------|------|
| `SEOUL_OPENDATA_API_KEY` | [data.seoul.go.kr](https://data.seoul.go.kr) → 회원가입 → 인증키 신청 | Yes |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys | 서비스 운영 시 |
| `NEXT_PUBLIC_KAKAO_MAP_KEY` | [developers.kakao.com](https://developers.kakao.com) → 앱 생성 → JavaScript 키 | 프론트엔드 |

### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일에 발급받은 API 키 입력
```

### 3. DB 셋업

```bash
python scripts/setup_db.py --full
```

### 4. 상주인구 CSV (선택사항)

상주인구 API가 ERROR-500이므로 CSV로 대체 적재:

1. [OA-15584](https://data.seoul.go.kr/dataList/OA-15584/S/1/datasetView.do) → "내려받기(CSV)"
2. 파일을 `data/csv/OA-15584.csv`에 저장
3. 적재:
```bash
cd server
python -m server.data.etl.runner load-csv ../data/csv/OA-15584.csv 2025Q4
```

---

## 기타 명령

### DB 초기화 (데이터 삭제 후 재셋업)
```bash
python scripts/setup_db.py --reset
python scripts/setup_db.py --quick   # 또는 --full
```

### 데이터 검증
```bash
cd server
python -m server.data.etl.runner validate 2025Q4
```

### 시드 덤프 재생성 (관리자용)

ETL로 데이터를 업데이트한 후, 다른 개발자를 위해 시드 파일을 갱신:
```bash
python scripts/generate_seed.py
git add data/seed/marketscope_seed.dump
git commit -m "chore: update seed dump"
```

### 개별 테이블 ETL
```bash
cd server
python -m server.data.etl.runner run 2025Q4 --table floating_pop
python -m server.data.etl.runner run 2025Q4 --table stores --table estimated_sales
python -m server.data.etl.runner run 2025Q4 --shp-file ../data/shp/OA-15560.shp --table districts
```

---

## 데이터 소스

| 데이터 | 소스 | 다운로드 |
|--------|------|----------|
| 상권 폴리곤 (SHP) | OA-15560 | [다운로드](https://data.seoul.go.kr/dataList/OA-15560/S/1/datasetView.do) |
| 상주인구 (CSV) | OA-15584 | [다운로드](https://data.seoul.go.kr/dataList/OA-15584/S/1/datasetView.do) |
| 유동인구 | VwsmTrdarFlpopQq | API (서울 열린데이터) |
| 추정매출 | VwsmTrdarSelngQq | API (서울 열린데이터) |
| 점포현황 | VwsmTrdarStorQq | API (서울 열린데이터) |
| 직장인구 | VwsmTrdarWrcPopltnQq | API (서울 열린데이터) |

SHP 파일은 `data/shp/`에, CSV 파일은 `data/csv/`에 배치합니다.

---

## 트러블슈팅

### Docker 컨테이너가 시작되지 않음
```bash
docker compose logs db    # PostgreSQL 로그 확인
docker compose down -v    # 볼륨 포함 초기화 후 재시도
```

### 포트 5432 충돌
로컬에 PostgreSQL이 이미 실행 중인 경우:
```bash
# docker-compose.yml에서 포트 변경
ports:
  - "5433:5432"
# .env에서 DATABASE_URL 포트도 변경
```

### Git LFS 시드 파일이 비어 있음
```bash
git lfs pull              # LFS 파일 다운로드
ls -lh data/seed/         # 파일 크기 확인 (~5MB)
```

### Alembic migration 실패
```bash
# PostGIS 확장 수동 생성
docker exec catchment-area-analysis-db-1 \
  psql -U marketscope -d marketscope -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

### Windows 경로 문제
Git Bash에서 실행 시 경로에 `C:/` 형식을 사용합니다. PowerShell에서는 `C:\` 형식.

---

*작성일: 2026-04-02*
