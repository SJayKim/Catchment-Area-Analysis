"""Real simulation repository — DB-backed percentile queries."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server.repositories.real._units import MONTHS_PER_QUARTER


class RealSimulationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def get_sales_percentiles(self, category_code: str, quarter: str | None = None) -> dict:
        """Get per-store sales percentiles across all Seoul districts for a category."""
        from server.models.sales import EstimatedSales
        from server.models.store import Store

        async with self._sf() as session:
            # Determine quarter
            if not quarter:
                latest = await session.execute(
                    select(EstimatedSales.quarter).order_by(EstimatedSales.quarter.desc()).limit(1)
                )
                quarter = latest.scalar_one_or_none()
                if not quarter:
                    return {"error": "매출 데이터가 없습니다."}

            # Per-store monthly sales across all districts for this category
            # JOIN estimated_sales + stores on district_code + category_code + quarter
            per_store_sales = (
                select((EstimatedSales.monthly_sales / func.nullif(Store.store_count, 0)).label("per_store"))
                .join(
                    Store,
                    (EstimatedSales.district_code == Store.district_code)
                    & (EstimatedSales.category_code == Store.category_code)
                    & (EstimatedSales.quarter == Store.quarter),
                )
                .where(
                    EstimatedSales.category_code == category_code,
                    EstimatedSales.quarter == quarter,
                    Store.store_count > 0,
                    EstimatedSales.monthly_sales.isnot(None),
                )
            ).subquery()

            result = await session.execute(
                select(
                    func.percentile_cont(0.25).within_group(per_store_sales.c.per_store).label("p25"),
                    func.percentile_cont(0.50).within_group(per_store_sales.c.per_store).label("p50"),
                    func.percentile_cont(0.75).within_group(per_store_sales.c.per_store).label("p75"),
                    func.avg(per_store_sales.c.per_store).label("avg"),
                    func.count().label("sample_count"),
                )
            )
            row = result.one()

            p50 = float(row.p50 or 0)
            sample_count = int(row.sample_count or 0)

            if sample_count == 0 or p50 == 0:
                return {
                    "category_code": category_code,
                    "quarter": quarter,
                    "p25_ratio": 0.6,
                    "p50_ratio": 1.0,
                    "p75_ratio": 1.5,
                    "seoul_avg_per_store": 0,
                    "sample_count": 0,
                }

            # p25/p50/p75 are used as ratios only — unaffected by quarterly→monthly scaling.
            # seoul_avg_per_store is an absolute amount, so convert it here.
            return {
                "category_code": category_code,
                "quarter": quarter,
                "p25_ratio": round(float(row.p25 or 0) / p50, 3),
                "p50_ratio": 1.0,
                "p75_ratio": round(float(row.p75 or 0) / p50, 3),
                "seoul_avg_per_store": int(float(row.avg or 0) / MONTHS_PER_QUARTER),
                "sample_count": sample_count,
            }

    async def get_default_unit_price(self, category_code: str) -> int | None:
        from server.models.category import CategoryMetadata

        async with self._sf() as session:
            result = await session.execute(
                select(CategoryMetadata.default_unit_price).where(CategoryMetadata.category_code == category_code)
            )
            return result.scalar_one_or_none()
