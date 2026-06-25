"""ETL CLI runner — orchestrates collect → transform → load pipeline.

Usage:
    python -m server.data.etl.runner run 2025Q3
    python -m server.data.etl.runner run 2025Q3 --table districts
    python -m server.data.etl.runner run 2025Q3 --dry-run
    python -m server.data.etl.runner validate 2025Q3
"""

from __future__ import annotations

import asyncio
import logging
import re
import time

import typer
from rich.console import Console
from rich.table import Table

from server.config import settings

app = typer.Typer(help="MarketScope ETL Pipeline")
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

VALID_TABLES = ["districts", "floating_pop", "estimated_sales", "stores", "resident_pop"]

# Default CSV path for resident population fallback
DEFAULT_RESIDENT_CSV = "data/csv/OA-15584.csv"


def _parse_quarter(quarter: str) -> tuple[str, str]:
    """Parse quarter string like '2025Q3' into ('2025', '3')."""
    match = re.match(r"^(\d{4})Q([1-4])$", quarter)
    if not match:
        raise typer.BadParameter(f"Invalid quarter format: {quarter}. Use YYYYQN (e.g., 2025Q3)")
    return match.group(1), match.group(2)


async def _run_pipeline(
    quarter: str,
    tables: list[str] | None,
    dry_run: bool,
    shp_file: str | None = None,
    csv_file: str | None = None,
) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from server.data.etl import transformers
    from server.data.etl.loader import DataLoader
    from server.data.etl.seoul_opendata import SeoulOpenDataCollector

    year, q = _parse_quarter(quarter)
    raw_quarter = f"{year}{q}"  # API uses "20253" format

    # Determine which tables to process
    target_tables = tables or VALID_TABLES

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    loader = DataLoader(session_factory)

    results: list[dict] = []

    async with SeoulOpenDataCollector() as collector:
        # --- districts ---
        if "districts" in target_tables:
            t0 = time.time()
            if shp_file:
                from server.data.etl.shp_collector import load_districts_from_shp

                console.print(f"[bold blue]Loading districts from SHP: {shp_file}[/]")
                transformed = load_districts_from_shp(shp_file, quarter)
            else:
                console.print("[bold blue]Collecting districts...[/]")
                raw_districts = await collector.collect_districts()
                transformed = [transformers.transform_district(r) for r in raw_districts]
            elapsed = time.time() - t0
            console.print(f"  Collected & transformed {len(transformed)} districts ({elapsed:.1f}s)")

            if not dry_run:
                count = await loader.upsert_districts(transformed)
                results.append({"table": "districts", "rows": count, "time": elapsed})
            else:
                results.append({"table": "districts", "rows": len(transformed), "time": elapsed})

        # --- floating_population ---
        if "floating_pop" in target_tables:
            t0 = time.time()
            console.print("[bold blue]Collecting floating population...[/]")
            raw_fp = await collector.collect_floating_pop(raw_quarter)
            transformed = []
            for r in raw_fp:
                transformed.extend(transformers.transform_floating_pop(r))
            elapsed = time.time() - t0
            console.print(f"  Collected & transformed {len(transformed)} rows ({elapsed:.1f}s)")

            if not dry_run:
                count = await loader.upsert_floating_pop(transformed)
                results.append({"table": "floating_population", "rows": count, "time": elapsed})
            else:
                results.append({"table": "floating_population", "rows": len(transformed), "time": elapsed})

        # --- estimated_sales ---
        if "estimated_sales" in target_tables:
            t0 = time.time()
            console.print("[bold blue]Collecting estimated sales...[/]")
            raw_sales = await collector.collect_estimated_sales(raw_quarter)
            transformed = [transformers.transform_estimated_sales(r) for r in raw_sales]
            elapsed = time.time() - t0
            console.print(f"  Collected & transformed {len(transformed)} rows ({elapsed:.1f}s)")

            if not dry_run:
                count = await loader.upsert_estimated_sales(transformed)
                results.append({"table": "estimated_sales", "rows": count, "time": elapsed})
            else:
                results.append({"table": "estimated_sales", "rows": len(transformed), "time": elapsed})

        # --- stores ---
        if "stores" in target_tables:
            t0 = time.time()
            console.print("[bold blue]Collecting stores...[/]")
            raw_stores = await collector.collect_stores(raw_quarter)
            transformed = [transformers.transform_store(r) for r in raw_stores]
            elapsed = time.time() - t0
            console.print(f"  Collected & transformed {len(transformed)} rows ({elapsed:.1f}s)")

            if not dry_run:
                count = await loader.upsert_stores(transformed)
                results.append({"table": "stores", "rows": count, "time": elapsed})
            else:
                results.append({"table": "stores", "rows": len(transformed), "time": elapsed})

        # --- resident_population ---
        if "resident_pop" in target_tables:
            t0 = time.time()
            transformed = []

            # Resident population: CSV or API
            if csv_file:
                from server.data.etl.csv_collector import load_resident_pop_csv

                console.print(f"[bold blue]Loading resident population from CSV: {csv_file}[/]")
                transformed.extend(load_resident_pop_csv(csv_file, quarter))
            else:
                console.print("[bold blue]Collecting resident population (API)...[/]")
                try:
                    raw_rp = await collector.collect_resident_pop(raw_quarter)
                    for r in raw_rp:
                        transformed.extend(transformers.transform_resident_pop(r, "resident"))
                except Exception as e:
                    console.print(f"  [yellow]API failed: {e}[/]")
                    # Try CSV fallback
                    from pathlib import Path

                    fallback = Path(DEFAULT_RESIDENT_CSV)
                    if fallback.exists():
                        from server.data.etl.csv_collector import load_resident_pop_csv

                        console.print(f"  [yellow]Falling back to CSV: {fallback}[/]")
                        transformed.extend(load_resident_pop_csv(str(fallback), quarter))
                    else:
                        console.print(f"  [yellow]No CSV fallback at {fallback}. Skipping resident pop.[/]")

            # Worker population (always from API)
            console.print("[bold blue]Collecting worker population (API)...[/]")
            try:
                raw_wp = await collector.collect_worker_pop(raw_quarter)
                for r in raw_wp:
                    transformed.extend(transformers.transform_resident_pop(r, "worker"))
            except Exception as e:
                console.print(f"  [yellow]Worker pop API failed: {e}. Skipping.[/]")

            elapsed = time.time() - t0
            console.print(f"  Collected & transformed {len(transformed)} rows ({elapsed:.1f}s)")

            if not dry_run:
                count = await loader.upsert_resident_pop(transformed)
                results.append({"table": "resident_population", "rows": count, "time": elapsed})
            else:
                results.append({"table": "resident_population", "rows": len(transformed), "time": elapsed})

    # --- category_metadata seeding (after stores) ---
    if "stores" in target_tables and not dry_run:
        t0 = time.time()
        console.print("[bold blue]Seeding category_metadata from stores...[/]")
        from server.data.etl.seed_category_metadata import seed_category_metadata

        cat_count = await seed_category_metadata(session_factory)
        elapsed = time.time() - t0
        results.append({"table": "category_metadata", "rows": cat_count, "time": elapsed})

    await engine.dispose()

    # Summary table
    table = Table(title=f"ETL Results — {quarter}" + (" [DRY RUN]" if dry_run else ""))
    table.add_column("Table", style="cyan")
    table.add_column("Rows", justify="right", style="green")
    table.add_column("Time (s)", justify="right")
    for r in results:
        table.add_row(r["table"], str(r["rows"]), f"{r['time']:.1f}")
    console.print(table)


async def _collect_validation_checks(conn, quarter: str) -> list[dict]:
    """Run all data-quality checks against ``conn`` for ``quarter``.

    Returns ``[{check, result, ok}]``. Pure collection (no rendering / no exit)
    so tests can drive it directly — e.g. inside a rolled-back transaction with
    an injected deficiency to prove the gate FAILs (R3-VALIDATE-GATE).
    """
    from sqlalchemy import text as sql_text

    checks: list[dict] = []

    async def scalar(sql: str, **params: object) -> object:
        r = await conn.execute(sql_text(sql), params)
        return r.scalar()

    # Row counts. districts is the static master (global); the four time-series
    # tables are scoped to `quarter` so an EMPTY quarter FAILs here instead of
    # vacuously passing every quarter-scoped content check below.
    districts = int(await scalar("SELECT COUNT(*) FROM districts") or 0)
    checks.append({"check": "districts row count", "result": str(districts), "ok": districts > 0})
    for table_name in ("floating_population", "estimated_sales", "stores", "resident_population"):
        n = int(await scalar(f"SELECT COUNT(*) FROM {table_name} WHERE quarter = :q", q=quarter) or 0)  # noqa: S608
        checks.append({"check": f"{table_name} row count ({quarter})", "result": str(n), "ok": n > 0})

    # Referential integrity: floating_population district_codes exist in districts
    orphans = int(
        await scalar(
            "SELECT COUNT(*) FROM floating_population fp "
            "WHERE NOT EXISTS (SELECT 1 FROM districts d WHERE d.district_code = fp.district_code)"
        )
        or 0
    )
    checks.append({"check": "floating_pop FK integrity", "result": f"{orphans} orphans", "ok": orphans == 0})

    # NULL ratio for districts.boundary
    null_pct = float(
        await scalar("SELECT COUNT(*) FILTER (WHERE boundary IS NULL) * 100.0 / NULLIF(COUNT(*), 0) FROM districts")
        or 0
    )
    checks.append({"check": "districts.boundary NULL %", "result": f"{null_pct:.1f}%", "ok": null_pct < 5})

    # --- Content checks (RC0 가드: 행 존재 ≠ 내용 유효) ---
    # 행수/FK 만으로는 "행은 있으나 컬럼이 전부 0/NULL" 결손을 못 잡는다.
    # all-zero 는 bool_and 로 "전량 0" 일 때만 FAIL (개별 0/소규모 상권은 허용).
    for pop_type in ("worker", "resident"):
        all_zero = await scalar(
            "SELECT bool_and(population = 0) FROM resident_population WHERE pop_type = :pt AND quarter = :q",
            pt=pop_type,
            q=quarter,
        )
        checks.append(
            {
                # NB: avoid '[..]' — rich.Table parses it as style markup and drops it.
                "check": f"resident_pop {pop_type} not all-zero",
                "result": "all-zero" if all_zero else "ok",
                "ok": all_zero is not True,  # None(=무행) → row-count 체크가 별도로 잡음
            }
        )

    # category_metadata.default_unit_price: NULL 0건 (RC2 — F09 시뮬레이션)
    dup_null = int(
        await scalar("SELECT count(*) FILTER (WHERE default_unit_price IS NULL) FROM category_metadata") or 0
    )
    checks.append({"check": "category_metadata.default_unit_price NULL", "result": str(dup_null), "ok": dup_null == 0})

    # category_metadata.aliases: 전량 NULL 만 FAIL (RC3 — 핵심 ~30종 외 NULL 은 의도)
    aliases_all_null = await scalar("SELECT bool_and(aliases IS NULL) FROM category_metadata")
    checks.append(
        {
            "check": "category_metadata.aliases not all-NULL",
            "result": "all-NULL" if aliases_all_null else "ok",
            "ok": aliases_all_null is not True,
        }
    )

    # 음수 sanity (매출/인구는 음수가 될 수 없음)
    for label, sql in (
        (
            "estimated_sales.monthly_sales >= 0",
            "SELECT count(*) FROM estimated_sales WHERE quarter=:q AND monthly_sales < 0",
        ),
        (
            "floating_population.total_pop >= 0",
            "SELECT count(*) FROM floating_population WHERE quarter=:q AND total_pop < 0",
        ),
        (
            "resident_population.population >= 0",
            "SELECT count(*) FROM resident_population WHERE quarter=:q AND population < 0",
        ),
    ):
        neg = int(await scalar(sql, q=quarter) or 0)
        checks.append({"check": label, "result": f"{neg} negatives", "ok": neg == 0})

    # 핵심 numeric all-zero 차단 — COALESCE 로 all-NULL 도 dead 로 간주 (NULL-safe).
    for label, sql in (
        (
            "estimated_sales.monthly_sales not all-zero",
            "SELECT bool_and(COALESCE(monthly_sales,0)=0) FROM estimated_sales WHERE quarter=:q",
        ),
        (
            "floating_population.total_pop not all-zero",
            "SELECT bool_and(COALESCE(total_pop,0)=0) FROM floating_population WHERE quarter=:q",
        ),
    ):
        all_zero = await scalar(sql, q=quarter)
        checks.append({"check": label, "result": "all-zero" if all_zero else "ok", "ok": all_zero is not True})

    return checks


async def _validate_data(quarter: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.connect() as conn:
        checks = await _collect_validation_checks(conn, quarter)
    await engine.dispose()

    table = Table(title=f"Validation — {quarter}")
    table.add_column("Check", style="cyan")
    table.add_column("Result", justify="right")
    table.add_column("Status", justify="center")
    for c in checks:
        status = "[green]PASS[/]" if c["ok"] else "[red]FAIL[/]"
        table.add_row(c["check"], c["result"], status)
    console.print(table)

    failed = [c for c in checks if not c["ok"]]
    if failed:
        console.print(f"[bold red]Validation FAILED — {len(failed)} check(s) below threshold[/]")
        raise typer.Exit(code=1)
    console.print("[bold green]Validation PASSED[/]")


@app.command()
def run(
    quarter: str = typer.Argument(..., help="Target quarter (e.g., 2025Q3)"),
    table: list[str] | None = typer.Option(None, "--table", "-t", help="Specific tables to load"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Collect & transform only, skip DB load"),
    shp_file: str | None = typer.Option(None, "--shp-file", help="SHP file for districts (overrides API)"),
    csv_file: str | None = typer.Option(None, "--csv-file", help="CSV file for resident population (overrides API)"),
) -> None:
    """Run ETL pipeline for a given quarter."""
    _parse_quarter(quarter)  # validate format
    if table:
        for t in table:
            if t not in VALID_TABLES:
                raise typer.BadParameter(f"Unknown table: {t}. Valid: {VALID_TABLES}")
    console.print(f"[bold]Starting ETL for {quarter}[/]" + (" [DRY RUN]" if dry_run else ""))
    asyncio.run(_run_pipeline(quarter, table, dry_run, shp_file=shp_file, csv_file=csv_file))


@app.command(name="load-shp")
def load_shp(
    shp_file: str = typer.Argument(..., help="Path to SHP file"),
    quarter: str = typer.Argument(..., help="Data quarter (e.g., 2025Q4)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse and show sample, skip DB load"),
) -> None:
    """Load districts from SHP file into the database."""
    from server.data.etl.shp_collector import load_districts_from_shp

    _parse_quarter(quarter)
    console.print(f"[bold]Loading SHP: {shp_file} for {quarter}[/]")

    rows = load_districts_from_shp(shp_file, quarter)
    console.print(f"  Parsed {len(rows)} districts")

    if dry_run:
        console.print("[yellow]DRY RUN — showing first 3 rows:[/]")
        for r in rows[:3]:
            console.print(f"  {r['district_code']} | {r['district_name']} | {r['district_type']}")
            console.print(f"    boundary: {r['boundary_wkt'][:80]}...")
        return

    async def _load() -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from server.data.etl.loader import DataLoader

        engine = create_async_engine(settings.database_url, echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        loader = DataLoader(session_factory)
        count = await loader.upsert_districts(rows)
        await engine.dispose()
        console.print(f"[green]Upserted {count} districts[/]")

    asyncio.run(_load())


@app.command(name="load-csv")
def load_csv(
    csv_file: str = typer.Argument(..., help="Path to resident population CSV (OA-15584)"),
    quarter: str = typer.Argument(..., help="Target quarter (e.g., 2025Q4)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse only, skip DB load"),
) -> None:
    """Load resident population from CSV file into the database."""
    from server.data.etl.csv_collector import load_resident_pop_csv

    _parse_quarter(quarter)
    console.print(f"[bold]Loading resident population CSV: {csv_file} for {quarter}[/]")

    rows = load_resident_pop_csv(csv_file, quarter)
    console.print(f"  Parsed {len(rows)} rows")

    if dry_run:
        console.print("[yellow]DRY RUN — showing sample:[/]")
        for r in rows[:6]:
            console.print(
                f"  {r['district_code']} | {r['quarter']} | {r['pop_type']} | "
                f"{r['age_group']} | {r['gender']} | {r['population']}"
            )
        return

    async def _load() -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from server.data.etl.loader import DataLoader

        engine = create_async_engine(settings.database_url, echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        loader = DataLoader(session_factory)
        count = await loader.upsert_resident_pop(rows)
        await engine.dispose()
        console.print(f"[green]Upserted {count} rows into resident_population[/]")

    asyncio.run(_load())


@app.command()
def validate(
    quarter: str = typer.Argument(..., help="Quarter to validate (e.g., 2025Q3)"),
) -> None:
    """Validate loaded data for a quarter."""
    _parse_quarter(quarter)
    console.print(f"[bold]Validating data for {quarter}[/]")
    asyncio.run(_validate_data(quarter))


if __name__ == "__main__":
    app()
