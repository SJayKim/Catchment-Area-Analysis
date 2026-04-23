"""MarketScope DB Setup — one-command database provisioning.

Usage:
    python scripts/setup_db.py          # Interactive (choose path)
    python scripts/setup_db.py --quick  # pg_restore from seed dump (~30s)
    python scripts/setup_db.py --full   # Full ETL from APIs (~5-10min, API keys required)
    python scripts/setup_db.py --reset  # Drop all data and re-setup
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED_DUMP = PROJECT_ROOT / "data" / "seed" / "marketscope_seed.dump"
SHP_FILE = PROJECT_ROOT / "data" / "shp" / "OA-15560.shp"
RESIDENT_CSV = PROJECT_ROOT / "data" / "csv" / "OA-15584.csv"
# .env.dev 우선 (로컬 개발), 없으면 .env (prod 배포 컨텍스트)
_ENV_DEV = PROJECT_ROOT / ".env.dev"
_ENV_PROD = PROJECT_ROOT / ".env"
ENV_FILE = _ENV_DEV if _ENV_DEV.exists() else _ENV_PROD
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
DOCKER_COMPOSE = PROJECT_ROOT / "docker-compose.yml"
SERVER_DIR = PROJECT_ROOT / "server"

DB_SERVICE = "db"
DB_USER = "marketscope"
DB_NAME = "marketscope"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print(msg: str, style: str = "") -> None:
    """Print with optional ANSI styling (bold/green/red/yellow)."""
    codes = {"bold": "\033[1m", "green": "\033[32m", "red": "\033[31m", "yellow": "\033[33m", "cyan": "\033[36m"}
    reset = "\033[0m"
    prefix = codes.get(style, "")
    print(f"{prefix}{msg}{reset}" if prefix else msg)


def _run(cmd: list[str], *, check: bool = True, capture: bool = False, cwd: str | Path | None = None, stdin_file: Path | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess command."""
    kwargs: dict = {"check": check, "cwd": str(cwd) if cwd else None}
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
        kwargs["text"] = True
    if stdin_file:
        kwargs["stdin"] = open(stdin_file, "rb")
    try:
        result = subprocess.run(cmd, **kwargs)
        if stdin_file and "stdin" in kwargs:
            kwargs["stdin"].close()
        return result
    except FileNotFoundError:
        _print(f"Command not found: {cmd[0]}", "red")
        sys.exit(1)


def _find_docker_compose() -> list[str]:
    """Find docker compose command (V2 or V1 fallback)."""
    if shutil.which("docker"):
        result = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
        if result.returncode == 0:
            return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    _print("Docker Compose not found. Install Docker Desktop.", "red")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Setup Steps
# ---------------------------------------------------------------------------

def check_prerequisites() -> list[str]:
    """Verify Docker, .env, and seed file exist."""
    compose = _find_docker_compose()

    if not ENV_FILE.exists():
        # 로컬 setup 이므로 .env.dev 로 신규 생성 (prod .env 는 별도 수동 생성)
        target = _ENV_DEV
        _print(f"{target.name} not found. Copying from .env.example...", "yellow")
        if ENV_EXAMPLE.exists():
            shutil.copy(ENV_EXAMPLE, target)
            _print(f"Created {target}. Edit it with your API keys if running --full.", "yellow")
        else:
            _print(f".env.example not found either. Create {target.name} manually.", "red")
            sys.exit(1)

    # Check Docker daemon
    result = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if result.returncode != 0:
        _print("Docker daemon is not running. Start Docker Desktop first.", "red")
        sys.exit(1)

    return compose


def ensure_containers(compose: list[str]) -> None:
    """Start db and redis containers."""
    _print("Starting db and redis containers...", "cyan")
    _run([*compose, "-f", str(DOCKER_COMPOSE), "up", "-d", DB_SERVICE, "redis"])


def wait_for_db(compose: list[str], timeout: int = 60) -> None:
    """Wait until PostgreSQL is ready."""
    _print("Waiting for PostgreSQL to be ready...", "cyan")
    start = time.time()
    while time.time() - start < timeout:
        result = _run(
            [*compose, "-f", str(DOCKER_COMPOSE), "exec", "-T", DB_SERVICE,
             "pg_isready", "-U", DB_USER],
            check=False, capture=True,
        )
        if result.returncode == 0:
            _print("PostgreSQL is ready.", "green")
            return
        time.sleep(2)
    _print(f"PostgreSQL not ready after {timeout}s.", "red")
    sys.exit(1)


def run_migrations(compose: list[str]) -> None:
    """Run Alembic migrations."""
    _print("Running Alembic migrations...", "cyan")

    # Try via backend container first
    result = _run(
        [*compose, "-f", str(DOCKER_COMPOSE), "exec", "-T", "backend",
         "alembic", "upgrade", "head"],
        check=False, capture=True,
    )
    if result.returncode == 0:
        _print("Migrations applied (via backend container).", "green")
        return

    # Fallback: run locally (requires alembic + DB accessible on localhost)
    _print("Backend container not available, trying local alembic...", "yellow")
    result = _run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False, capture=True, cwd=SERVER_DIR,
    )
    if result.returncode == 0:
        _print("Migrations applied (locally).", "green")
    else:
        stderr = result.stderr if hasattr(result, "stderr") and result.stderr else ""
        _print(f"Migration failed: {stderr}", "red")
        sys.exit(1)


def check_existing_data(compose: list[str]) -> int:
    """Check if districts table has data. Returns row count."""
    result = _run(
        [*compose, "-f", str(DOCKER_COMPOSE), "exec", "-T", DB_SERVICE,
         "psql", "-U", DB_USER, "-d", DB_NAME, "-t", "-c",
         "SELECT COUNT(*) FROM districts;"],
        check=False, capture=True,
    )
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except (ValueError, AttributeError):
        return 0


def _get_db_container(compose: list[str]) -> str:
    """Get the db container ID via docker compose."""
    result = _run(
        [*compose, "-f", str(DOCKER_COMPOSE), "ps", "-q", DB_SERVICE],
        check=False, capture=True,
    )
    container_id = (result.stdout or "").strip()
    if not container_id:
        _print("DB container not found.", "red")
        sys.exit(1)
    return container_id


def restore_seed(compose: list[str]) -> None:
    """Restore database from pg_dump seed file."""
    if not SEED_DUMP.exists():
        _print(f"Seed file not found: {SEED_DUMP}", "red")
        _print("Run 'git lfs pull' if using Git LFS, or generate with scripts/generate_seed.py", "yellow")
        sys.exit(1)

    # Check if seed file is an LFS pointer (< 1KB) instead of actual data
    if SEED_DUMP.stat().st_size < 1024:
        _print("Seed file looks like a Git LFS pointer. Run 'git lfs pull' first.", "red")
        sys.exit(1)

    _print(f"Restoring from seed dump ({SEED_DUMP.stat().st_size / 1024 / 1024:.1f} MB)...", "cyan")

    container_id = _get_db_container(compose)
    cmd = [
        "docker", "exec", "-i", container_id,
        "pg_restore",
        "-U", DB_USER,
        "-d", DB_NAME,
        "--no-owner",
        "--clean", "--if-exists",
    ]
    result = _run(cmd, check=False, capture=True, stdin_file=SEED_DUMP)

    # pg_restore returns non-zero for warnings (e.g., "relation does not exist" during clean)
    # This is expected and safe to ignore
    _print("Seed restore complete.", "green")


def run_full_etl(compose: list[str]) -> None:
    """Run full ETL pipeline."""
    _print("Running full ETL pipeline (this may take 5-10 minutes)...", "cyan")

    # First run migrations
    run_migrations(compose)

    # Build ETL command
    etl_cmd = [
        sys.executable, "-m", "server.data.etl.runner",
        "run", "2025Q4",
    ]
    if SHP_FILE.exists():
        etl_cmd.extend(["--shp-file", str(SHP_FILE)])
    if RESIDENT_CSV.exists():
        etl_cmd.extend(["--csv-file", str(RESIDENT_CSV)])

    result = _run(etl_cmd, check=False, cwd=SERVER_DIR)
    if result.returncode != 0:
        _print("ETL pipeline failed. Check API keys in .env", "red")
        sys.exit(1)

    _print("ETL pipeline complete.", "green")


def validate_data(compose: list[str]) -> None:
    """Print table row counts as validation."""
    _print("\nValidating loaded data...", "cyan")

    tables = ["districts", "floating_population", "estimated_sales", "stores", "resident_population"]
    for table in tables:
        result = _run(
            [*compose, "-f", str(DOCKER_COMPOSE), "exec", "-T", DB_SERVICE,
             "psql", "-U", DB_USER, "-d", DB_NAME, "-t", "-c",
             f"SELECT COUNT(*) FROM {table};"],
            check=False, capture=True,
        )
        count = "0"
        if result.returncode == 0 and result.stdout:
            count = result.stdout.strip()
        status = "OK" if count.strip() != "0" else "EMPTY"
        _print(f"  {table:.<35} {count.strip():>10} rows  [{status}]")

    _print("")


def print_summary(mode: str) -> None:
    """Print next steps."""
    _print("=" * 60, "bold")
    _print(f"DB setup complete! (mode: {mode})", "green")
    _print("=" * 60, "bold")
    _print("")
    _print("Next steps:")
    _print("  1. Set USE_MOCK=false in .env")
    _print("  2. Start backend: cd server && uvicorn server.main:app --reload --port 8000")
    _print("  3. Start frontend: cd frontend && npm run dev")
    _print("")


def reset_db(compose: list[str]) -> None:
    """Drop and recreate the database."""
    _print("Resetting database (dropping all data)...", "yellow")
    _run(
        [*compose, "-f", str(DOCKER_COMPOSE), "exec", "-T", DB_SERVICE,
         "psql", "-U", DB_USER, "-d", "postgres", "-c",
         f"DROP DATABASE IF EXISTS {DB_NAME}; CREATE DATABASE {DB_NAME};"],
        check=False,
    )
    # Re-enable PostGIS
    _run(
        [*compose, "-f", str(DOCKER_COMPOSE), "exec", "-T", DB_SERVICE,
         "psql", "-U", DB_USER, "-d", DB_NAME, "-c",
         "CREATE EXTENSION IF NOT EXISTS postgis;"],
        check=False,
    )
    _print("Database reset complete.", "green")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="MarketScope DB Setup")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quick", action="store_true", help="Restore from seed dump (fast, no API keys)")
    group.add_argument("--full", action="store_true", help="Run full ETL pipeline (requires API keys)")
    group.add_argument("--reset", action="store_true", help="Drop and recreate database")
    args = parser.parse_args()

    _print("")
    _print("=" * 60, "bold")
    _print("  MarketScope DB Setup", "bold")
    _print("=" * 60, "bold")
    _print("")

    compose = check_prerequisites()
    ensure_containers(compose)
    wait_for_db(compose)

    if args.reset:
        reset_db(compose)
        _print("Database has been reset. Run setup again to load data.", "yellow")
        return

    # Check existing data
    row_count = check_existing_data(compose)
    if row_count > 0:
        _print(f"Database already has {row_count} districts.", "yellow")
        answer = input("Reset and reload? [y/N] ").strip().lower()
        if answer == "y":
            reset_db(compose)
        else:
            _print("Skipping data load. Existing data preserved.", "green")
            validate_data(compose)
            return

    # Determine mode
    if args.quick:
        mode = "quick"
    elif args.full:
        mode = "full"
    else:
        # Interactive
        _print("Choose setup mode:", "bold")
        _print("  [1] Quick Start — restore from seed dump (~30s, no API keys)")
        _print("  [2] Full ETL    — fetch from Seoul Open Data APIs (~5-10min)")
        _print("")
        choice = input("Enter choice [1/2]: ").strip()
        mode = "full" if choice == "2" else "quick"

    if mode == "quick":
        run_migrations(compose)
        restore_seed(compose)
    else:
        run_full_etl(compose)

    validate_data(compose)
    print_summary(mode)


if __name__ == "__main__":
    main()
