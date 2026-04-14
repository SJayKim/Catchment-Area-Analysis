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
- Chat sessions and messages
- Category metadata
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
docker compose exec db pg_restore --list /backups/marketscope_LATEST.dump
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
docker compose stop nginx frontend backend
```

### Step 4: Restore the Database

```bash
# Option A: Restore into existing database (drop + recreate)
docker compose exec db dropdb -U marketscope marketscope
docker compose exec db createdb -U marketscope marketscope
docker compose exec db pg_restore \
    --no-owner --no-acl \
    -U marketscope \
    -d marketscope \
    /backups/marketscope_20260414_030000.dump

# Option B: If database container is corrupted, recreate from scratch
docker compose down db
docker volume rm catchment-area-analysis_pgdata
docker compose up -d db
# Wait for health check
sleep 10
docker compose exec db createdb -U marketscope marketscope 2>/dev/null || true
docker compose exec db pg_restore \
    --no-owner --no-acl \
    -U marketscope \
    -d marketscope \
    /backups/marketscope_20260414_030000.dump
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
docker compose up -d backend frontend nginx

# Verify health
curl -f http://localhost/health
```

### Step 8: Clear Cache

```bash
# Redis cache may have stale data from before the restore
docker compose exec redis redis-cli flushdb
```

---

## Re-ingestion from Public APIs

If backups are unavailable or too old, data can be re-ingested:

```bash
# Re-run full ETL pipeline
docker compose exec backend python -m server.data.etl.scheduler --full

# Or for a specific quarter
docker compose exec backend python -m server.data.etl.scheduler --quarter 2025Q4
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

*Last updated: 2026-04-14*
*Next drill scheduled: 2026-Q3*
