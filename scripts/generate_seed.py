"""Generate a fresh seed dump from the current database.

Usage:
    python scripts/generate_seed.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED_DUMP = PROJECT_ROOT / "data" / "seed" / "marketscope_seed.dump"
DOCKER_COMPOSE = PROJECT_ROOT / "docker-compose.yml"
DB_SERVICE = "db"
DB_USER = "marketscope"
DB_NAME = "marketscope"


def _get_container_name() -> str:
    """Get the db container name from docker compose."""
    result = subprocess.run(
        ["docker", "compose", "-f", str(DOCKER_COMPOSE), "ps", "-q", DB_SERVICE],
        capture_output=True, text=True,
    )
    container_id = result.stdout.strip()
    if not container_id:
        print("ERROR: db container not running. Run 'docker compose up -d db' first.")
        sys.exit(1)
    return container_id


def _get_row_counts(container: str) -> dict[str, int]:
    """Get row counts for main tables."""
    tables = ["districts", "floating_population", "estimated_sales", "stores", "resident_population"]
    counts = {}
    for table in tables:
        result = subprocess.run(
            ["docker", "exec", container, "psql", "-U", DB_USER, "-d", DB_NAME,
             "-t", "-c", f"SELECT COUNT(*) FROM {table};"],
            capture_output=True, text=True,
        )
        try:
            counts[table] = int(result.stdout.strip())
        except (ValueError, AttributeError):
            counts[table] = 0
    return counts


def main() -> None:
    print("=" * 50)
    print("  MarketScope Seed Generator")
    print("=" * 50)
    print()

    container = _get_container_name()

    # Validate data exists
    counts = _get_row_counts(container)
    print("Current DB row counts:")
    for table, count in counts.items():
        print(f"  {table:.<35} {count:>10}")
    print()

    if counts.get("districts", 0) < 100:
        print("ERROR: districts table has < 100 rows. Load data first before generating seed.")
        sys.exit(1)

    # Generate dump
    SEED_DUMP.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating seed dump: {SEED_DUMP}")
    with open(SEED_DUMP, "wb") as f:
        result = subprocess.run(
            ["docker", "exec", container, "pg_dump",
             "-U", DB_USER,
             "--no-owner", "--no-privileges",
             "--clean", "--if-exists",
             "-F", "c",
             "--exclude-table=chat_sessions",
             "--exclude-table=chat_messages",
             DB_NAME],
            stdout=f,
            stderr=subprocess.PIPE,
            text=False,
        )

    if result.returncode != 0:
        stderr = result.stderr.decode() if result.stderr else ""
        print(f"WARNING: pg_dump exited with code {result.returncode}")
        if stderr:
            print(f"  stderr: {stderr[:200]}")

    size_mb = SEED_DUMP.stat().st_size / 1024 / 1024
    print(f"Seed dump generated: {size_mb:.1f} MB")
    print()
    print("Next: commit with 'git add data/seed/marketscope_seed.dump && git commit'")
    print("(File is tracked via Git LFS)")


if __name__ == "__main__":
    main()
