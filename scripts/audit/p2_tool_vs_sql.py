"""Phase 2 audit: Tool/Repository 계산 정확성.

- Run each tool directly (USE_MOCK=false assumed from .env)
- Cross-check against independent SQL aggregations on the same DB
- Re-compute all derived metrics in pure Python and diff
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

SAMPLES = [
    ("3120189", "강남역"),
    ("3120103", "홍대입구역"),
    ("3120053", "건대입구역"),
    ("3120028", "명동"),
    ("3120043", "서울역"),
]


def psql(sql: str) -> list[dict]:
    wrapped = f"SELECT json_agg(t) FROM ({sql}) t;"
    r = subprocess.run(
        [
            "docker", "exec", "catchment-area-analysis-db-1",
            "psql", "-U", "marketscope", "-d", "marketscope",
            "-At", "-c", wrapped,
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    raw = r.stdout.strip()
    if not raw:
        return []
    return json.loads(raw)


async def audit_sales(code: str) -> dict:
    from server.agent.tools.estimated_sales import get_estimated_sales

    tool_out = await get_estimated_sales(code)

    sql = psql(f"""
      SELECT
        COALESCE(SUM(monthly_sales),0) AS raw_monthly_sales,
        COALESCE(SUM(sales_count),0)   AS raw_sales_count,
        COALESCE(SUM(weekday_sales),0) AS raw_weekday,
        COALESCE(SUM(weekend_sales),0) AS raw_weekend,
        COALESCE(SUM(male_sales),0)    AS raw_male,
        COALESCE(SUM(female_sales),0)  AS raw_female
      FROM estimated_sales
      WHERE district_code='{code}' AND quarter='2025Q4'
    """)[0]

    raw_monthly = int(sql["raw_monthly_sales"])
    expected_monthly = raw_monthly // 3

    checks = [
        {"field": "total_monthly_sales", "tool": tool_out.get("total_monthly_sales"),
         "expected_raw//3": expected_monthly,
         "match": tool_out.get("total_monthly_sales") == expected_monthly},
        {"field": "total_sales_count", "tool": tool_out.get("total_sales_count"),
         "expected_raw//3": int(sql["raw_sales_count"]) // 3,
         "match": tool_out.get("total_sales_count") == int(sql["raw_sales_count"]) // 3},
        {"field": "weekday_sales", "tool": tool_out.get("weekday_sales"),
         "expected_raw//3": int(sql["raw_weekday"]) // 3,
         "match": tool_out.get("weekday_sales") == int(sql["raw_weekday"]) // 3},
        {"field": "weekend_sales", "tool": tool_out.get("weekend_sales"),
         "expected_raw//3": int(sql["raw_weekend"]) // 3,
         "match": tool_out.get("weekend_sales") == int(sql["raw_weekend"]) // 3},
        {"field": "gender_sales.male", "tool": tool_out.get("gender_sales", {}).get("male"),
         "expected_raw//3": int(sql["raw_male"]) // 3,
         "match": tool_out.get("gender_sales", {}).get("male") == int(sql["raw_male"]) // 3},
        {"field": "gender_sales.female", "tool": tool_out.get("gender_sales", {}).get("female"),
         "expected_raw//3": int(sql["raw_female"]) // 3,
         "match": tool_out.get("gender_sales", {}).get("female") == int(sql["raw_female"]) // 3},
    ]

    return {
        "district_code": code,
        "raw_db_sum_monthly_sales": raw_monthly,
        "checks": checks,
        "all_match": all(c["match"] for c in checks),
    }


async def audit_flpop(code: str) -> dict:
    from server.agent.tools.floating_population import get_floating_population

    tool_out = await get_floating_population(code)

    sql_rows = psql(f"""
      SELECT time_slot, SUM(total_pop) AS total
      FROM floating_population
      WHERE district_code='{code}' AND quarter='2025Q4'
      GROUP BY time_slot
      ORDER BY time_slot
    """)

    db_by_hour = {int(r["time_slot"]): int(r["total"]) for r in sql_rows}
    tool_by_hour = {e["time_slot"]: e["population"] for e in tool_out.get("by_hour", [])}

    checks = []
    for slot in sorted(db_by_hour):
        tool_v = tool_by_hour.get(slot)
        db_v = db_by_hour[slot]
        checks.append({"slot": slot, "tool": tool_v, "db": db_v, "match": tool_v == db_v})

    db_sum = sum(db_by_hour.values())
    checks.append({
        "field": "daily_avg",
        "tool": tool_out.get("daily_avg"),
        "expected_sum_across_slots": db_sum,
        "match": tool_out.get("daily_avg") == db_sum,
        "note": "daily_avg field is SUM of 6 time_slot counts — potentially double-counts individuals",
    })

    return {
        "district_code": code,
        "checks": checks,
        "all_match": all(c["match"] for c in checks),
    }


async def audit_store(code: str) -> dict:
    from server.agent.tools.store_info import get_store_info

    tool_out = await get_store_info(code)

    sql = psql(f"""
      SELECT
        COALESCE(SUM(store_count),0) AS total_stores,
        COALESCE(SUM(open_count),0)  AS opens,
        COALESCE(SUM(close_count),0) AS closes,
        COALESCE(SUM(franchise_count),0) AS franchises
      FROM stores
      WHERE district_code='{code}' AND quarter='2025Q4'
    """)[0]

    checks = [
        {"field": "total_stores", "tool": tool_out.get("total_stores"),
         "db": int(sql["total_stores"]), "match": tool_out.get("total_stores") == int(sql["total_stores"])},
        {"field": "open_count", "tool": tool_out.get("open_count"),
         "db": int(sql["opens"]), "match": tool_out.get("open_count") == int(sql["opens"])},
        {"field": "close_count", "tool": tool_out.get("close_count"),
         "db": int(sql["closes"]), "match": tool_out.get("close_count") == int(sql["closes"])},
        {"field": "franchise_count", "tool": tool_out.get("franchise_count"),
         "db": int(sql["franchises"]), "match": tool_out.get("franchise_count") == int(sql["franchises"])},
    ]

    total_stores = int(sql["total_stores"])
    close_count = int(sql["closes"])
    expected_close_rate = round(close_count / total_stores * 100, 1) if total_stores else 0.0
    checks.append({
        "field": "close_rate",
        "tool": tool_out.get("close_rate"),
        "expected": expected_close_rate,
        "match": tool_out.get("close_rate") == expected_close_rate,
    })

    return {
        "district_code": code,
        "checks": checks,
        "all_match": all(c["match"] for c in checks),
    }


async def audit_summary_insights(code: str) -> dict:
    """Re-compute SummaryCardData.insights from raw tool outputs."""
    from server.agent.tools.district_summary import get_district_summary
    from server.agent.tools.estimated_sales import get_estimated_sales
    from server.agent.tools.floating_population import get_floating_population
    from server.agent.tools.store_info import get_store_info

    summary = await get_district_summary(code)
    sales = await get_estimated_sales(code)
    fp = await get_floating_population(code)
    stores = await get_store_info(code)

    expected: dict = {}

    monthly_sales = sales.get("total_monthly_sales", 0)
    total_stores = stores.get("total_stores", 0)
    if total_stores > 0 and monthly_sales:
        expected["perStoreSales"] = round(monthly_sales / total_stores)

    franchise = stores.get("franchise_count", 0)
    if total_stores > 0:
        expected["franchiseRatio"] = round(franchise / total_stores * 100, 1)

    wd = sales.get("weekday_sales", 0)
    we = sales.get("weekend_sales", 0)
    if wd > 0:
        expected["weekendUplift"] = round((we - wd) / wd * 100, 1)

    q_sales = sales.get("quarterly_sales", [])
    if len(q_sales) >= 2:
        prev = q_sales[-2].get("monthly_sales", 0)
        curr = q_sales[-1].get("monthly_sales", 0)
        if prev > 0:
            expected["qoqGrowth"] = round((curr - prev) / prev * 100, 1)

    insights = summary.get("insights", {})
    checks = []
    for k, v in expected.items():
        actual = insights.get(k)
        checks.append({"field": k, "tool": actual, "expected": v, "match": actual == v})

    return {
        "district_code": code,
        "checks": checks,
        "all_match": all(c["match"] for c in checks),
        "tool_insights": insights,
        "expected_insights": expected,
    }


async def audit_compare(codes: list[str]) -> dict:
    from server.agent.tools.compare_districts import compare_districts

    out = await compare_districts(codes)
    districts = out.get("districts", {})
    winners = out.get("winners", {})

    # Re-derive winners from per-district numbers
    items = [d for d in districts.values() if "error" not in d]
    expected: dict = {}
    if items:
        expected["highest_pop"] = max(items, key=lambda d: d.get("floating_pop", 0)).get("district_name")
        expected["highest_sales"] = max(items, key=lambda d: d.get("monthly_sales", 0)).get("district_name")
        expected["lowest_close_rate"] = min(items, key=lambda d: d.get("close_rate", 1e9)).get("district_name")
        items_with_eff = [d for d in items if "sales_per_store" in d]
        if items_with_eff:
            expected["best_efficiency"] = max(items_with_eff, key=lambda d: d["sales_per_store"]).get("district_name")

    checks = []
    for k, v in expected.items():
        actual = winners.get(k)
        checks.append({"winner": k, "tool": actual, "expected": v, "match": actual == v})

    return {
        "codes": codes,
        "checks": checks,
        "all_match": all(c["match"] for c in checks),
        "districts_summary": {
            c: {k: d.get(k) for k in ("district_name", "floating_pop", "monthly_sales",
                                      "store_count", "close_rate", "sales_per_store")}
            for c, d in districts.items()
        },
    }


async def audit_simulate(code: str, category: str = "CS200001") -> dict:
    """CS200001 is a common category code (편의점). Run simulation and check formula."""
    from server.agent.tools.simulate_revenue import simulate_revenue

    out = await simulate_revenue(code, category)
    if "error" in out:
        return {"district_code": code, "category": category, "error": out["error"]}

    basis = out.get("basis", {})
    sim = out.get("simulation", {})
    percentiles = out.get("percentiles", {})

    ms = basis.get("total_monthly_sales", 0)
    es = basis.get("effective_stores", 1)
    per_store_avg = ms / es if es else 0

    price_ratio = basis.get("price_ratio", 1.0)
    expected_avg = int(per_store_avg * price_ratio)
    expected_low = int(per_store_avg * percentiles.get("p25_ratio", 0.6) * price_ratio)
    expected_high = int(per_store_avg * percentiles.get("p75_ratio", 1.5) * price_ratio)

    checks = [
        {"field": "simulation.avg", "tool": sim.get("avg"), "expected": expected_avg,
         "match": sim.get("avg") == expected_avg},
        {"field": "simulation.low", "tool": sim.get("low"), "expected": expected_low,
         "match": sim.get("low") == expected_low},
        {"field": "simulation.high", "tool": sim.get("high"), "expected": expected_high,
         "match": sim.get("high") == expected_high},
    ]
    return {
        "district_code": code,
        "category": category,
        "basis": basis,
        "simulation": sim,
        "checks": checks,
        "all_match": all(c["match"] for c in checks),
    }


async def bootstrap() -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from server.config import settings
    from server.repositories import set_data_access
    from server.repositories.real.factory import build_real_data_access
    from server.services.cache import MemoryCacheService, set_cache_service

    set_cache_service(MemoryCacheService())

    engine = create_async_engine(settings.database_url, echo=False, pool_size=5)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    da = build_real_data_access(session_factory)
    set_data_access(da)


async def main() -> None:
    await bootstrap()
    out: dict = {"meta": {"quarter": "2025Q4", "samples": SAMPLES}}

    out["sales_audit"] = []
    out["flpop_audit"] = []
    out["store_audit"] = []
    out["summary_insights_audit"] = []
    out["simulate_audit"] = []

    for code, name in SAMPLES:
        print(f"=== {name} ({code}) ===", file=sys.stderr)
        out["sales_audit"].append({"name": name, **(await audit_sales(code))})
        out["flpop_audit"].append({"name": name, **(await audit_flpop(code))})
        out["store_audit"].append({"name": name, **(await audit_store(code))})
        out["summary_insights_audit"].append({"name": name, **(await audit_summary_insights(code))})
        out["simulate_audit"].append({"name": name, **(await audit_simulate(code))})

    # Compare: 강남 vs 홍대 vs 건대
    out["compare_audit"] = await audit_compare(["3120189", "3120103", "3120053"])

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
