# Disaster Recovery Plan - MarketScope AI

> Backup strategy, restoration procedures, and recovery targets.

---

## Recovery Targets

| Metric | Target | Description |
|--------|--------|-------------|
| **RTO** (Recovery Time Objective) | < 1 hour | Maximum acceptable downtime from incident detection to service restoration |
| **RPO** (Recovery Point Objective) | < 24 hours | Maximum acceptable data loss, measured in time since last backup |

**Rationale**: Public data is refreshed quarterly. Chat sessions are ephemeral. The primary risk is losing ETL-processed data, which can be re-generated from public APIs. Daily backups provide sufficient coverage.

---

## Backup Strategy

### Database Backups (PostgreSQL)

**Method**: `pg_dump` via Docker Compose, automated daily.

**Schedule**: Daily at 03:00 KST (cron job on host machine).

**Retention**: 30 days rolling (older backups auto-pruned).

**Storage**: Local `data/backups/` directory. For production, copy to offsite storage (S3, GCS).

**Backup script**: `scripts/backup_db.sh`

```bash
# Manual backup
bash scripts/backup_db.sh

# Verify backup exists
ls -lh data/backups/
```

**What is backed up**:
- All tables: districts, floating_population, estimated_sales, stores, store_history, resident_population
- chat_sessions / chat_messages 테이블 (단, 런타임 대화 세션은 인메모리라 백업과 무관하게 재시작 시 유실)
- Category metadata (+ learned_aliases)
- PostGIS spatial data (polygon geometries)

**What is NOT backed up** (reconstructable):
- Redis cache (ephemeral, auto-rebuilds)
- Docker volumes metadata
- Application logs (managed by Docker json-file driver)

### Backup Verification

After each backup, verify the dump file:
```bash
# Check file size (should be > 1MB for a populated database)
ls -lh data/backups/marketscope_*.dump

# Verify dump integrity (list contents without restoring)
# 백업 파일은 "호스트"의 data/backups/ 에 있다 — db 컨테이너에는 /backups 마운트가 없으므로
# (compose 의 db 볼륨은 pgdata 뿐) 컨테이너 안 경로로 직접 지정하면 실패한다. 먼저 복사해 넣는다:
docker compose cp data/backups/marketscope_<TIMESTAMP>.dump db:/tmp/verify.dump
docker compose exec db pg_restore --list /tmp/verify.dump
docker compose exec db rm /tmp/verify.dump
```

---

## Restoration Procedure

### Step 1: Assess the Situation

```bash
# Check current database state
docker compose ps db
docker compose exec db psql -U marketscope -d marketscope -c "SELECT count(*) FROM districts;"
```

### Step 2: Select a Backup

```bash
# List available backups (newest first)
ls -lt data/backups/marketscope_*.dump
```

### Step 3: Stop Application Services

```bash
# Stop backend and frontend to prevent writes during restore
# dev (docker-compose.yml — nginx 컨테이너 포함):
docker compose stop nginx frontend backend

# prod (docker-compose.prod.yml — nginx "서비스 없음", 외부 호스트 nginx 사용):
docker compose -f docker-compose.prod.yml stop frontend backend
# (호스트 nginx 는 그대로 두면 upstream 502 를 반환한다. 점검 페이지가 필요하면 호스트 nginx 설정에서 처리)
```

### Step 4: Restore the Database

> 백업 dump 는 호스트의 `data/backups/` 에 있고, db 컨테이너에는 `/backups` 마운트가 없다
> (compose 볼륨은 `pgdata` 뿐). `docker compose cp` 로 컨테이너에 넣은 뒤 pg_restore 한다.

```bash
# 0. 백업 파일을 db 컨테이너로 복사
docker compose cp data/backups/marketscope_<TIMESTAMP>.dump db:/tmp/restore.dump

# Option A: Restore into existing database (drop + recreate)
docker compose exec db dropdb -U marketscope marketscope
docker compose exec db createdb -U marketscope marketscope
docker compose exec db pg_restore \
    --no-owner --no-acl \
    -U marketscope \
    -d marketscope \
    /tmp/restore.dump

# Option B: If database container is corrupted, recreate from scratch
docker compose down db
# 볼륨명은 compose project 이름에 따른다:
#   dev  = marketscope-dev_pgdata          (docker-compose.yml 의 name: marketscope-dev)
#   prod = catchment-area-analysis_pgdata  (prod compose 는 name 미지정 → 디렉토리명)
docker volume rm marketscope-dev_pgdata          # dev 기준. prod 는 catchment-area-analysis_pgdata
docker compose up -d db
# Wait for health check
sleep 10
docker compose cp data/backups/marketscope_<TIMESTAMP>.dump db:/tmp/restore.dump
docker compose exec db createdb -U marketscope marketscope 2>/dev/null || true
docker compose exec db pg_restore \
    --no-owner --no-acl \
    -U marketscope \
    -d marketscope \
    /tmp/restore.dump

# 복원 후 임시 파일 정리
docker compose exec db rm /tmp/restore.dump
```

### Step 5: Run Migrations

```bash
# Ensure schema is up to date (in case backup is from an older schema version)
docker compose up migrate
```

### Step 6: Verify Restoration

```bash
docker compose exec db psql -U marketscope -d marketscope -c "
  SELECT 'districts' AS tbl, count(*) FROM districts
  UNION ALL
  SELECT 'floating_population', count(*) FROM floating_population
  UNION ALL
  SELECT 'estimated_sales', count(*) FROM estimated_sales
  UNION ALL
  SELECT 'stores', count(*) FROM stores;
"
```

### Step 7: Restart Services

```bash
# dev (docker-compose.yml):
docker compose up -d backend frontend nginx
curl -f http://localhost/health          # dev nginx 경유

# prod (docker-compose.prod.yml — nginx 서비스 없음):
docker compose -f docker-compose.prod.yml up -d backend frontend
curl -f http://localhost:8000/health                                # backend 직접
curl -f https://marketscope.robitlabs.co.kr/api/health/detail       # 외부 도메인 (외부 nginx 라우팅상 /health 루트는 404)
```

### Step 8: Clear Cache

```bash
# Redis cache may have stale data from before the restore
docker compose exec redis redis-cli flushdb
```

---

## Re-ingestion from Public APIs

If backups are unavailable or too old, data can be re-ingested.
ETL 진입점은 Typer CLI `server.data.etl.runner` 이며 quarter 는 **위치 인자**다
(`--full` / `--quarter` 플래그나 스케줄러 모듈은 존재하지 않는다 — 수동 CLI 전용):

```bash
# 해당 분기 전체 테이블 재수집 (districts / floating_pop / estimated_sales / stores / resident_pop)
docker compose exec backend python -m server.data.etl.runner run 2025Q4

# 특정 테이블만
docker compose exec backend python -m server.data.etl.runner run 2025Q4 --table estimated_sales

# 적재 후 검증 게이트 (컬럼 내용/행수/FK — 실패 시 비-0 exit)
docker compose exec backend python -m server.data.etl.runner validate 2025Q4
```

**Estimated time**: 1-2 hours for full re-ingestion (depends on API rate limits).

---

## Quarterly Drill Checklist

Perform this drill every quarter to validate the DR plan.

| # | Step | Verified | Date | Notes |
|---|------|----------|------|-------|
| 1 | Run `scripts/backup_db.sh` and verify dump file size | [ ] | | |
| 2 | List backups, confirm 30-day retention is working | [ ] | | |
| 3 | Restore backup to a **test** database (not production) | [ ] | | |
| 4 | Verify row counts match production | [ ] | | |
| 5 | Test application health against restored database | [ ] | | |
| 6 | Verify ETL re-ingestion works for at least 1 data source | [ ] | | |
| 7 | Document any issues found and update this plan | [ ] | | |
| 8 | Confirm backup files are readable (not corrupted) | [ ] | | |
| 9 | Test secret rotation procedure (rotate a non-critical key) | [ ] | | |
| 10 | Review and update RTO/RPO targets if needed | [ ] | | |

**Drill coordinator**: Assign one team member per quarter.

**Post-drill action**: File a brief report in `docs/ops/` with findings and improvements.

---

## Contact and Escalation

| Severity | Response Time | Action |
|----------|--------------|--------|
| P1 - Full outage | 15 minutes | All hands, follow Full Outage in runbook.md |
| P2 - Partial degradation | 1 hour | On-call engineer, follow specific scenario in runbook.md |
| P3 - Non-critical | Next business day | Log issue, schedule fix |

---

*Last updated: 2026-07-04 (문서 정합성 감사 — /backups 경로·nginx 절차·ETL 명령을 실제 토폴로지/CLI 로 정정)*
*Next drill scheduled: 2026-Q3*
