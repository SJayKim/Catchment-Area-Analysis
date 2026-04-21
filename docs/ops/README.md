# Ops — 운영 가이드

개발 환경 셋업, 프로덕션 배포, 장애 대응, 안정성 체크리스트.

| 문서 | 용도 |
|---|---|
| [quickstart.md](quickstart.md) | 5분 안에 로컬 기동 (Mock / Seed 복원 / Full ETL 3 경로) |
| [database-setup.md](database-setup.md) | PostgreSQL + PostGIS 초기 세팅 |
| [production-deployment.md](production-deployment.md) | 외부 Nginx 경유 프로덕션 배포 |
| [runbook.md](runbook.md) | 일상 운영 — 배포, 롤백, 로그 확인, 세션 정리 |
| [disaster-recovery.md](disaster-recovery.md) | DB 백업/복구, 장애 시나리오 |
| [serving-stability.md](serving-stability.md) | 서빙 안정성 체크리스트 (API / Agent / Data / Observability) |

## 자주 사용하는 스크립트 (`scripts/`)

| 스크립트 | 용도 |
|---|---|
| `verify_sales_units.py` | 매출 단위(분기→월) 변환 정상 검증 |
| `validate_env.py` | 필수 환경변수 누락 체크 |
| `generate_seed.py` | seed 덤프 생성 |
| `backup_db.sh` | DB 백업 (pg_dump) |
| `setup_db.py` | 신규 환경 DB 초기화 |
| `server/scripts/cleanup_alembic.py` | stale `alembic_version` 정리 |
| `server/scripts/flush_cache.py` | Redis 캐시 flush (단위 변환 후 stale 제거) |

## 관련 문서

- 시스템 전체 구조: [../architecture/overview.md](../architecture/overview.md)
- 배포 상세: [../architecture/deployment.md](../architecture/deployment.md)
- 데이터 계층: [../architecture/data.md](../architecture/data.md)
