#!/usr/bin/env bash
# MarketScope AI - Database Backup Script
# Usage: bash scripts/backup_db.sh
#
# Creates a pg_dump of the marketscope database and prunes old backups.
# Designed to run via cron or manually.

set -euo pipefail

# --- Configuration ---
BACKUP_DIR="$(cd "$(dirname "$0")/.." && pwd)/data/backups"
RETENTION_DAYS=30
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/marketscope_${TIMESTAMP}.dump"

# --- Ensure backup directory exists ---
mkdir -p "${BACKUP_DIR}"

echo "[backup] Starting database backup at $(date)"
echo "[backup] Target: ${BACKUP_FILE}"

# --- Run pg_dump inside the db container ---
docker compose exec -T db pg_dump \
    -U marketscope \
    -d marketscope \
    --format=custom \
    --compress=6 \
    > "${BACKUP_FILE}"

# --- Verify backup file ---
FILESIZE=$(stat -c%s "${BACKUP_FILE}" 2>/dev/null || stat -f%z "${BACKUP_FILE}" 2>/dev/null || echo "0")

if [ "${FILESIZE}" -lt 1024 ]; then
    echo "[backup] ERROR: Backup file is too small (${FILESIZE} bytes). Backup may have failed."
    rm -f "${BACKUP_FILE}"
    exit 1
fi

echo "[backup] Backup complete: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"

# --- Prune backups older than retention period ---
echo "[backup] Pruning backups older than ${RETENTION_DAYS} days..."
PRUNED=0
find "${BACKUP_DIR}" -name "marketscope_*.dump" -type f -mtime +${RETENTION_DAYS} -print -delete | while read -r f; do
    echo "[backup] Pruned: ${f}"
    PRUNED=$((PRUNED + 1))
done

echo "[backup] Backup finished at $(date)"
echo "[backup] Backups in ${BACKUP_DIR}:"
ls -lh "${BACKUP_DIR}"/marketscope_*.dump 2>/dev/null || echo "  (none)"
