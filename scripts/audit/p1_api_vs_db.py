"""Phase 1 audit: Seoul OpenData API raw ↔ DB 일치성 검증.

- 5 sample districts × 3 service (sales/flpop/stor) × 2025Q4
- Seoul API paging through all rows (1650+ districts, 15k+ rows per service)
- Filter by TRDAR_CD ∈ SAMPLES, compare key columns with DB row
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

SAMPLES = [
    ("3120189", "강남역"),
    ("3120103", "홍대입구역"),
    ("3120053", "건대입구역"),
    ("3120028", "명동"),
    ("3120043", "서울역"),
]
YEAR = "2025"
QUARTER_NUM = "4"
PAGE_SIZE = 1000

BASE = "http://openapi.seoul.go.kr:8088"


def load_env() -> str:
    root = Path(__file__).resolve().parents[2]
    # .env.dev 우선 (로컬 audit), 없으면 .env (prod 배포 컨텍스트)
    dev = root / ".env.dev"
    env_path = dev if dev.exists() else root / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("SEOUL_OPENDATA_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"SEOUL_OPENDATA_API_KEY missing in {env_path}")


def fetch_page(service: str, key: str, start: int, end: int) -> dict:
    url = f"{BASE}/{key}/json/{service}/{start}/{end}"
    with urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_all(service: str, key: str) -> list[dict]:
    """Fetch all rows for a service endpoint."""
    first = fetch_page(service, key, 1, PAGE_SIZE)
    wrapper = first.get(service)
    if wrapper is None:
        # Endpoint returned unknown shape (common for deprecated StorW)
        raise RuntimeError(f"{service} missing in response. top-keys={list(first.keys())}")
    code = wrapper.get("RESULT", {}).get("CODE", "")
    if code not in ("INFO-000", "INFO-200"):
        raise RuntimeError(f"{service} API error: {wrapper.get('RESULT')}")
    total = wrapper.get("list_total_count", 0)
    rows = list(wrapper.get("row", []))
    print(f"[{service}] total_count={total}, first page={len(rows)}", file=sys.stderr)
    cur = PAGE_SIZE + 1
    while cur <= total:
        end = min(cur + PAGE_SIZE - 1, total)
        data = fetch_page(service, key, cur, end)
        rows.extend(data.get(service, {}).get("row", []))
        time.sleep(0.1)
        cur = end + 1
    return rows


def filter_quarter_and_samples(rows: list[dict], sample_codes: set[str]) -> dict[str, list[dict]]:
    """Filter rows to our sample districts for the current quarter.

    Seoul APIs use two shapes:
        STDR_YR_CD + STDR_QU_CD  (sales, flpop, stor)
        STDR_YYQU_CD              (some endpoints)
    """
    out: dict[str, list[dict]] = {c: [] for c in sample_codes}
    for r in rows:
        cd = str(r.get("TRDAR_CD", ""))
        if cd not in sample_codes:
            continue
        yr = str(r.get("STDR_YR_CD", ""))
        qu = str(r.get("STDR_QU_CD", ""))
        yyqu = str(r.get("STDR_YYQU_CD", ""))
        is_match = (yr == YEAR and qu == QUARTER_NUM) or yyqu == f"{YEAR}{QUARTER_NUM}"
        if is_match:
            out[cd].append(r)
    return out


def db_query(sql: str) -> list[dict]:
    """Run a read-only SQL via docker exec and parse JSON output."""
    wrapped = f"SELECT json_agg(t) FROM ({sql}) t;"
    result = subprocess.run(
        [
            "docker", "exec", "catchment-area-analysis-db-1",
            "psql", "-U", "marketscope", "-d", "marketscope",
            "-At", "-c", wrapped,
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"psql failed: {result.stderr}")
    raw = result.stdout.strip()
    if not raw or raw == "":
        return []
    return json.loads(raw)


def compare_sales(api_rows: dict[str, list[dict]]) -> list[dict]:
    results = []
    db_rows = db_query(
        """
        SELECT district_code, category_code, category_name,
               monthly_sales, sales_count, weekday_sales, weekend_sales,
               male_sales, female_sales
        FROM estimated_sales
        WHERE district_code IN ('3120189','3120103','3120053','3120028','3120043')
          AND quarter='2025Q4'
        """
    )
    db_idx = {}
    for r in db_rows:
        db_idx.setdefault(r["district_code"], {})[r["category_code"]] = r

    for code, rows in api_rows.items():
        api_idx = {str(r.get("SVC_INDUTY_CD", "")): r for r in rows}
        db_cats = db_idx.get(code, {})
        common = sorted(set(api_idx) & set(db_cats))
        api_only = sorted(set(api_idx) - set(db_cats))
        db_only = sorted(set(db_cats) - set(api_idx))

        diffs = []
        for cat in common:
            a = api_idx[cat]
            d = db_cats[cat]
            def pick(api_key, db_key):
                a_v = a.get(api_key)
                d_v = d.get(db_key)
                try:
                    a_i = int(float(str(a_v))) if a_v not in (None, "") else None
                except (ValueError, TypeError):
                    a_i = None
                return a_i, d_v

            checks = []
            for ak, dk in [
                ("THSMON_SELNG_AMT", "monthly_sales"),
                ("THSMON_SELNG_CO", "sales_count"),
                ("MDW_SELNG_AMT", "weekday_sales"),
                ("WND_SELNG_AMT", "weekend_sales"),
                ("ML_SELNG_AMT", "male_sales"),
                ("FML_SELNG_AMT", "female_sales"),
            ]:
                api_v, db_v = pick(ak, dk)
                match = api_v == db_v
                checks.append({"field": dk, "api": api_v, "db": db_v, "match": match})
            diffs.append({"category": cat, "checks": checks})

        results.append({
            "district_code": code,
            "common_categories": len(common),
            "api_only_categories": api_only[:5],
            "db_only_categories": db_only[:5],
            "sample_diffs": diffs[:3],  # first 3 categories per district
            "all_match": all(c["match"] for d in diffs for c in d["checks"]),
        })
    return results


def compare_flpop(api_rows: dict[str, list[dict]]) -> list[dict]:
    results = []
    db_rows = db_query(
        """
        SELECT district_code, time_slot, total_pop, male_pop, female_pop,
               age_10_pop, age_20_pop, age_30_pop, age_40_pop, age_50_pop, age_60_plus_pop
        FROM floating_population
        WHERE district_code IN ('3120189','3120103','3120053','3120028','3120043')
          AND quarter='2025Q4'
        ORDER BY district_code, time_slot
        """
    )
    db_idx: dict[str, dict] = {}
    for r in db_rows:
        db_idx.setdefault(r["district_code"], {})[r["time_slot"]] = r

    slot_to_api = [
        (0,  "TMZON_00_06_FLPOP_CO"),
        (6,  "TMZON_06_11_FLPOP_CO"),
        (11, "TMZON_11_14_FLPOP_CO"),
        (14, "TMZON_14_17_FLPOP_CO"),
        (17, "TMZON_17_21_FLPOP_CO"),
        (21, "TMZON_21_24_FLPOP_CO"),
    ]

    for code, rows in api_rows.items():
        if not rows:
            results.append({"district_code": code, "error": "no API row"})
            continue
        api = rows[0]  # 1 district = 1 row per quarter
        db_slots = db_idx.get(code, {})

        checks = []
        for slot, api_key in slot_to_api:
            a_v = api.get(api_key)
            try:
                a_i = int(float(str(a_v))) if a_v not in (None, "") else None
            except (ValueError, TypeError):
                a_i = None
            d_row = db_slots.get(slot, {})
            d_v = d_row.get("total_pop")
            checks.append({"slot": slot, "api_key": api_key, "api": a_i, "db": d_v, "match": a_i == d_v})

        # Gender aggregate
        ml = int(float(str(api.get("ML_FLPOP_CO", 0)) or 0))
        fml = int(float(str(api.get("FML_FLPOP_CO", 0)) or 0))
        db_ml_sum = sum(d.get("male_pop", 0) for d in db_slots.values())
        db_fml_sum = sum(d.get("female_pop", 0) for d in db_slots.values())

        results.append({
            "district_code": code,
            "time_slot_checks": checks,
            "gender_check": {
                "api_male_total": ml,
                "db_male_sum_across_slots": db_ml_sum,
                "api_female_total": fml,
                "db_female_sum_across_slots": db_fml_sum,
                "note": "DB unpivots gender proportionally across slots — sum may round-drift ±6"
            },
            "all_slots_match": all(c["match"] for c in checks),
        })
    return results


def compare_stores(api_rows: dict[str, list[dict]]) -> list[dict]:
    results = []
    db_rows = db_query(
        """
        SELECT district_code, category_code, category_name,
               store_count, open_count, close_count, franchise_count
        FROM stores
        WHERE district_code IN ('3120189','3120103','3120053','3120028','3120043')
          AND quarter='2025Q4'
        """
    )
    db_idx = {}
    for r in db_rows:
        db_idx.setdefault(r["district_code"], {})[r["category_code"]] = r

    for code, rows in api_rows.items():
        api_idx = {str(r.get("SVC_INDUTY_CD", "")): r for r in rows}
        db_cats = db_idx.get(code, {})
        common = sorted(set(api_idx) & set(db_cats))

        diffs = []
        for cat in common[:3]:
            a = api_idx[cat]
            d = db_cats[cat]
            checks = []
            for ak, dk in [
                ("STOR_CO", "store_count"),
                ("OPBIZ_STOR_CO", "open_count"),
                ("CLSBIZ_STOR_CO", "close_count"),
                ("FRC_STOR_CO", "franchise_count"),
            ]:
                a_v = a.get(ak)
                try:
                    a_i = int(float(str(a_v))) if a_v not in (None, "") else None
                except (ValueError, TypeError):
                    a_i = None
                d_v = d.get(dk)
                checks.append({"field": dk, "api": a_i, "db": d_v, "match": a_i == d_v})
            diffs.append({"category": cat, "checks": checks})

        results.append({
            "district_code": code,
            "common_categories": len(common),
            "sample_diffs": diffs,
            "all_match": all(c["match"] for d in diffs for c in d["checks"]),
        })
    return results


def main() -> None:
    key = load_env()
    sample_codes = {c for c, _ in SAMPLES}

    out: dict = {"meta": {"quarter": f"{YEAR}Q{QUARTER_NUM}", "samples": SAMPLES}}

    print("=== fetching VwsmTrdarSelngQq (estimated sales) ...", file=sys.stderr)
    sales = fetch_all("VwsmTrdarSelngQq", key)
    sales_filtered = filter_quarter_and_samples(sales, sample_codes)
    out["sales_compare"] = compare_sales(sales_filtered)

    print("=== fetching VwsmTrdarFlpopQq (floating pop) ...", file=sys.stderr)
    flpop = fetch_all("VwsmTrdarFlpopQq", key)
    flpop_filtered = filter_quarter_and_samples(flpop, sample_codes)
    out["flpop_compare"] = compare_flpop(flpop_filtered)

    stores_service = "VwsmTrdarStorW"
    try:
        print(f"=== fetching {stores_service} (stores) ...", file=sys.stderr)
        stores = fetch_all(stores_service, key)
    except RuntimeError as e:
        print(f"[{stores_service}] failed: {e} — falling back to VwsmTrdarStorQq", file=sys.stderr)
        stores_service = "VwsmTrdarStorQq"
        stores = fetch_all(stores_service, key)
    stores_filtered = filter_quarter_and_samples(stores, sample_codes)
    out["stores_service_used"] = stores_service
    out["stores_compare"] = compare_stores(stores_filtered)

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
