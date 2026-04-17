"""Verify sales unit conversion (quarterly→monthly) on the Real repository.

Runs four sanity checks against a live DB and prints the values with
assertions. Exits non-zero on failure so it can gate CI/deploy.

Usage (inside a server container or with DATABASE_URL set on host):
    USE_MOCK=false python scripts/verify_sales_units.py

Scenarios:
    1. sales.get_estimated_sales(bomun)
         → total_monthly_sales in [1e8, 5e10]
    2. recommendation.recommend_business(bomun)
         → print Top5 per_store_sales (원→만원)
         → warn if 슈퍼마켓 > 3억/월
    3. comparison.compare_districts([bomun, other])
         → print both monthly_sales
    4. simulation.get_sales_percentiles(supermarket_code)
         → seoul_avg_per_store < 3억/월

Final: call the tool-layer get_estimated_sales (which runs _enrich_sales)
and confirm computed.qoq_growth_pct is populated (Phase A bugfix).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "server"))

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Sanity envelopes (in KRW).
TOTAL_SALES_MIN = 100_000_000         # 1억/월
TOTAL_SALES_MAX = 50_000_000_000      # 500억/월
SUPERMARKET_PER_STORE_MAX = 300_000_000  # 3억/월

SUPERMARKET_KEYWORDS = ("슈퍼마켓", "편의점", "SSM")


def _w(v: int | float) -> str:
    """Render KRW as 만원."""
    return f"{int(v) / 10_000:,.0f}만원"


async def _resolve_districts(da) -> tuple[dict, dict]:
    """Pick bomun-like and a second district for comparison."""
    from sqlalchemy import select

    from server.models.district import District

    session_factory = da.sales._sf  # type: ignore[attr-defined]
    async with session_factory() as session:
        bomun = (
            await session.execute(
                select(District.district_code, District.district_name)
                .where(District.district_name.ilike("%보문%"))
                .limit(1)
            )
        ).one_or_none()
        other = (
            await session.execute(
                select(District.district_code, District.district_name)
                .where(District.district_name.ilike("%강남%"))
                .limit(1)
            )
        ).one_or_none()

    if bomun is None:
        # Fallback: first district
        async with session_factory() as session:
            bomun = (
                await session.execute(
                    select(District.district_code, District.district_name).limit(1)
                )
            ).one_or_none()
    if other is None:
        async with session_factory() as session:
            other = (
                await session.execute(
                    select(District.district_code, District.district_name)
                    .where(District.district_code != bomun.district_code)
                    .limit(1)
                )
            ).one_or_none()
    if bomun is None or other is None:
        raise RuntimeError("districts 테이블에 상권 데이터가 부족합니다.")
    return (
        {"code": bomun.district_code, "name": bomun.district_name},
        {"code": other.district_code, "name": other.district_name},
    )


async def _find_supermarket_code(da, district_code: str) -> str | None:
    from sqlalchemy import select

    from server.models.store import Store

    session_factory = da.sales._sf  # type: ignore[attr-defined]
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(Store.category_code, Store.category_name)
                .where(Store.district_code == district_code)
                .distinct()
            )
        ).all()
    for r in rows:
        if any(kw in (r.category_name or "") for kw in SUPERMARKET_KEYWORDS):
            return r.category_code
    return None


async def main() -> int:
    from server.config import settings
    from server.repositories import get_data_access, set_data_access
    from server.services.cache import MemoryCacheService, set_cache_service

    if settings.use_mock:
        print("[verify_sales_units] ❌ USE_MOCK=true — Real DB가 필요합니다.")
        print("  USE_MOCK=false 환경에서 재실행하세요.")
        return 2

    print(f"[verify_sales_units] DB: {settings.database_url}")
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from server.repositories.real.factory import build_real_data_access

    set_data_access(build_real_data_access(session_factory))
    set_cache_service(MemoryCacheService())
    da = get_data_access()

    failures: list[str] = []

    bomun, other = await _resolve_districts(da)
    print(f"\n[대상] 기준 상권: {bomun['name']} ({bomun['code']})")
    print(f"[대상] 대조 상권: {other['name']} ({other['code']})")

    # Scenario 1 — total_monthly_sales envelope
    print("\n=== 1. get_estimated_sales ===")
    sales_result = await da.sales.get_estimated_sales(bomun["code"])
    total = int(sales_result.get("total_monthly_sales", 0))
    print(f"  total_monthly_sales = {total:>18,} 원 ({_w(total)})")
    if not (TOTAL_SALES_MIN <= total <= TOTAL_SALES_MAX):
        failures.append(
            f"total_monthly_sales={total:,} out of sane range "
            f"[{TOTAL_SALES_MIN:,}, {TOTAL_SALES_MAX:,}]"
        )

    # Scenario 2 — Top5 recommendations
    print("\n=== 2. recommend_business (Top5 per_store_sales) ===")
    rec_result = await da.recommendation.recommend_business(bomun["code"])
    recs = rec_result.get("recommendations", [])
    if not recs:
        failures.append("recommend_business returned empty recommendations")
    for r in recs:
        per_store = int(r.get("per_store_sales", 0))
        name = r.get("category_name", "")
        marker = ""
        if any(kw in name for kw in SUPERMARKET_KEYWORDS):
            if per_store > SUPERMARKET_PER_STORE_MAX:
                marker = "  ⚠ 슈퍼마켓 점포당 월매출 > 3억 (의심)"
                failures.append(
                    f"{name} per_store_sales={per_store:,} exceeds 3억/월 threshold"
                )
            else:
                marker = "  ✓ 슈퍼마켓 sane"
        print(f"  {r.get('rank'):>2}. {name:<24s} {_w(per_store):>12s}{marker}")

    # Scenario 3 — compare_districts
    print("\n=== 3. compare_districts ===")
    cmp_result = await da.comparison.compare_districts([bomun["code"], other["code"]])
    for code, data in cmp_result.get("districts", {}).items():
        name = data.get("district_name", code)
        ms = int(data.get("monthly_sales", 0))
        print(f"  {name:<24s} monthly_sales = {_w(ms)}")

    # Scenario 4 — simulation percentiles
    print("\n=== 4. get_sales_percentiles (supermarket) ===")
    sm_code = await _find_supermarket_code(da, bomun["code"])
    if sm_code is None:
        print("  (슈퍼마켓 카테고리를 해당 상권에서 찾지 못함 — skip)")
    else:
        sim_result = await da.simulation.get_sales_percentiles(sm_code)
        avg = int(sim_result.get("seoul_avg_per_store", 0))
        print(f"  category={sm_code} seoul_avg_per_store = {_w(avg)}")
        if avg >= SUPERMARKET_PER_STORE_MAX:
            failures.append(
                f"simulation seoul_avg_per_store={avg:,} >= 3억/월 (구 버그 미해결)"
            )

    # Final — Phase A key-bug fix: computed.qoq_growth_pct present via tool layer
    print("\n=== 5. _enrich_sales QoQ hook (Phase A 검증) ===")
    from server.agent.tools.estimated_sales import get_estimated_sales as tool_get_sales

    # Clear cache to force re-enrichment
    from server.services.cache import get_cache_service

    await get_cache_service().flush_by_prefix("sales:")
    tool_result = await tool_get_sales(bomun["code"])
    computed = tool_result.get("computed", {})
    qoq = computed.get("qoq_growth_pct")
    if qoq is None:
        quarterly = tool_result.get("quarterly_sales", [])
        if len(quarterly) < 2:
            print(f"  (quarterly_sales rows < 2 — 해당 상권 데이터 부족, skip): {len(quarterly)}")
        else:
            failures.append(
                "computed.qoq_growth_pct 미존재 — _enrich_sales 키버그 재발 의심"
            )
    else:
        print(f"  computed.qoq_growth_pct = {qoq:+.1f}%  (정상)")

    await engine.dispose()

    print("\n" + "=" * 48)
    if failures:
        print(f"❌ FAIL: {len(failures)}건")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("✅ 모든 단위 변환 검증 통과")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
