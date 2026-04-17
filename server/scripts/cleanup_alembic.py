"""Drop stale rows from ``alembic_version`` before ``alembic upgrade head``.

Runs inside the migrate init container. Idempotent — safe on a fresh DB
(CREATE TABLE IF NOT EXISTS) and on an existing DB (keeps only the latest
version_num row, so multiple stale heads from older dumps collapse).

Why: seed dumps generated before ``generate_seed.py`` excluded this table
carry old migration markers; upgrading against them raises "overlaps".
Cleaning here (pre-upgrade) guarantees re-execution on every container
boot, unlike the seed service which only runs on first import.
"""

from __future__ import annotations

import os
import sys

import psycopg2


def main() -> int:
    url = os.environ.get("DATABASE_URL_SYNC")
    if not url:
        print("[cleanup_alembic] DATABASE_URL_SYNC not set", file=sys.stderr)
        return 1

    conn = psycopg2.connect(url)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) PRIMARY KEY);"
            )
            cur.execute(
                "DELETE FROM alembic_version WHERE version_num NOT IN "
                "(SELECT version_num FROM alembic_version "
                "ORDER BY version_num DESC LIMIT 1);"
            )
            removed = cur.rowcount
        print(f"[cleanup_alembic] stale rows removed: {removed}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
