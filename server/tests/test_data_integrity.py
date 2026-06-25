"""Data-integrity regression tests — Plan: docs/plan/fix/data-reliability-2026-06-25.md.

Two layers:
  * Pure unit tests (default, CI-safe under USE_MOCK) — guard the ETL transform /
    seed logic that produced the 3 latent load deficiencies (worker all-zero,
    default_unit_price NULL, aliases NULL).
  * @pytest.mark.real DB tests (opt-in: ``pytest -m real``) — assert the *loaded*
    DB content. Skipped automatically when the dev DB is unreachable.

Run unit subset:  pytest server/tests/test_data_integrity.py -q
Run DB subset:    pytest server/tests/test_data_integrity.py -q -m real
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from server.data.etl.seed_category_metadata import (  # noqa: E402
    _DEFAULT_UNIT_PRICE,
    _UNIT_PRICES,
    _load_aliases,
)
from server.data.etl.transformers import transform_resident_pop  # noqa: E402

# --- sample worker raw row (VwsmTrdarWrcPopltnQq shape, verified against live API) ---
_WORKER_RAW = {
    "TRDAR_CD": "3110160",
    "STDR_YR_CD": "2025",
    "STDR_QU_CD": "4",
    "MAG_10_WRC_POPLTN_CO": 1,
    "MAG_20_WRC_POPLTN_CO": 22,
    "MAG_30_WRC_POPLTN_CO": 46,
    "MAG_40_WRC_POPLTN_CO": 50,
    "MAG_50_WRC_POPLTN_CO": 47,
    "MAG_60_ABOVE_WRC_POPLTN_CO": 22,
    "FAG_10_WRC_POPLTN_CO": 0,
    "FAG_20_WRC_POPLTN_CO": 20,
    "FAG_30_WRC_POPLTN_CO": 32,
    "FAG_40_WRC_POPLTN_CO": 38,
    "FAG_50_WRC_POPLTN_CO": 24,
    "FAG_60_ABOVE_WRC_POPLTN_CO": 10,
    "TOT_WRC_POPLTN_CO": 312,
}
_WORKER_TOTAL = 312  # 188 male + 124 female


# ---------------------------------------------------------------------------
# RC1 — worker population field mapping (pure unit)
# ---------------------------------------------------------------------------


def test_worker_transform_shape_and_sum():
    rows = transform_resident_pop(_WORKER_RAW, "worker")
    assert len(rows) == 12  # 6 age groups × 2 genders
    assert {r["gender"] for r in rows} == {"M", "F"}
    assert {r["age_group"] for r in rows} == {"10s", "20s", "30s", "40s", "50s", "60s+"}
    assert all(r["pop_type"] == "worker" and r["quarter"] == "2025Q4" for r in rows)
    assert sum(r["population"] for r in rows) == _WORKER_TOTAL


def test_worker_transform_not_all_zero():
    # Regression guard: the original bug read resident-style keys → every row 0.
    rows = transform_resident_pop(_WORKER_RAW, "worker")
    assert any(r["population"] > 0 for r in rows)


def test_worker_reads_wrc_keys_not_resident_keys():
    # Pin the exact key: WRC value must win over a (wrong) resident-style key.
    raw = dict(_WORKER_RAW, MAG_20_WRC_POPLTN_CO=42, AGRDE_20_MAG_POPLTN_CO=999)
    rows = transform_resident_pop(raw, "worker")
    male_20 = next(r["population"] for r in rows if r["age_group"] == "20s" and r["gender"] == "M")
    assert male_20 == 42


def test_resident_branch_reads_resident_keys():
    # Dormant API path, but must still read AGRDE_NN_MAG_POPLTN_CO (not WRC).
    raw = {"TRDAR_CD": "x", "STDR_YR_CD": "2025", "STDR_QU_CD": "4", "AGRDE_30_FAG_POPLTN_CO": 7}
    rows = transform_resident_pop(raw, "resident")
    female_30 = next(r["population"] for r in rows if r["age_group"] == "30s" and r["gender"] == "F")
    assert female_30 == 7


# ---------------------------------------------------------------------------
# RC2 — default_unit_price seed mapping (pure unit)
# ---------------------------------------------------------------------------


def test_unit_price_mapping():
    assert _UNIT_PRICES["외식"] == 12000
    assert _UNIT_PRICES["서비스"] == 25000
    assert _UNIT_PRICES["소매"] == 15000


def test_unit_price_default_for_unmapped_major():
    # major NULL/미매핑 → 기본값 (NULL default_unit_price 방지).
    assert _UNIT_PRICES.get(None, _DEFAULT_UNIT_PRICE) == 15000
    assert _UNIT_PRICES.get("기타", _DEFAULT_UNIT_PRICE) == 15000


# ---------------------------------------------------------------------------
# RC3 — curated aliases JSON (pure unit)
# ---------------------------------------------------------------------------


def test_aliases_json_well_formed():
    aliases = _load_aliases()
    assert isinstance(aliases, dict)
    assert len(aliases) >= 30  # 핵심 ~30종
    code_re = re.compile(r"^CS\d{6}$")
    for code, alias_list in aliases.items():
        assert code_re.match(code), f"bad category_code: {code}"
        assert isinstance(alias_list, list) and alias_list, f"empty alias list for {code}"
        assert all(isinstance(a, str) and a.strip() for a in alias_list), f"blank alias in {code}"
        assert len(set(alias_list)) == len(alias_list), f"duplicate alias in {code}"


# ---------------------------------------------------------------------------
# Loaded-DB assertions (opt-in: pytest -m real). Skipped if DB unreachable.
# ---------------------------------------------------------------------------

_QUARTER = "2025Q4"


async def _db_scalar(sql: str):
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.ext.asyncio import create_async_engine

    from server.config import settings

    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql))).scalar()
    except (OperationalError, OSError) as e:  # connection refused / DB down → skip, never mask SQL bugs
        pytest.skip(f"real DB unavailable: {e}")
    finally:
        await engine.dispose()


async def _db_rows(sql: str):
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.ext.asyncio import create_async_engine

    from server.config import settings

    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql))).all()
    except (OperationalError, OSError) as e:
        pytest.skip(f"real DB unavailable: {e}")
    finally:
        await engine.dispose()


@pytest.mark.real
async def test_worker_population_not_all_zero_real():
    all_zero = await _db_scalar(
        f"SELECT bool_and(population = 0) FROM resident_population WHERE pop_type='worker' AND quarter='{_QUARTER}'"
    )
    assert all_zero is False


@pytest.mark.real
async def test_default_unit_price_no_null_real():
    null_count = await _db_scalar("SELECT count(*) FILTER (WHERE default_unit_price IS NULL) FROM category_metadata")
    assert null_count == 0


@pytest.mark.real
async def test_aliases_not_all_null_real():
    all_null = await _db_scalar("SELECT bool_and(aliases IS NULL) FROM category_metadata")
    assert all_null is False


@pytest.mark.real
async def test_quarter_uniform_real():
    for table, col in (
        ("districts", "data_quarter"),
        ("floating_population", "quarter"),
        ("estimated_sales", "quarter"),
        ("stores", "quarter"),
        ("resident_population", "quarter"),
    ):
        n = await _db_scalar(f"SELECT count(DISTINCT {col}) FROM {table}")  # noqa: S608
        assert n == 1, f"{table}: expected 1 distinct quarter, got {n}"


@pytest.mark.real
async def test_default_unit_price_matches_major_real():
    # RC2 end-to-end: exercises the seed INSERT result (not just the constant dict).
    rows = await _db_rows("SELECT major_category, default_unit_price FROM category_metadata")
    expect = {"외식": 12000, "서비스": 25000, "소매": 15000}
    for major, price in rows:
        assert price == expect.get(major, 15000), f"major={major} got default_unit_price={price}"


@pytest.mark.real
async def test_validation_gate_fails_on_injected_worker_zero():
    # Codifies R3-VALIDATE-GATE: gate PASSes on good data, FAILs on injected
    # worker=0. Injection runs in an uncommitted transaction that is rolled back.
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.ext.asyncio import create_async_engine

    from server.config import settings
    from server.data.etl.runner import _collect_validation_checks

    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as conn:
            good = await _collect_validation_checks(conn, _QUARTER)
            assert all(c["ok"] for c in good), [c["check"] for c in good if not c["ok"]]

            await conn.execute(
                text("UPDATE resident_population SET population = 0 WHERE pop_type='worker' AND quarter=:q"),
                {"q": _QUARTER},
            )
            bad = await _collect_validation_checks(conn, _QUARTER)
            await conn.rollback()  # discard injection — never committed
    except (OperationalError, OSError) as e:
        pytest.skip(f"real DB unavailable: {e}")
    finally:
        await engine.dispose()

    worker_check = next(c for c in bad if c["check"] == "resident_pop worker not all-zero")
    assert worker_check["ok"] is False
