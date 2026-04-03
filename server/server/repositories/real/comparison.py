"""Real comparison repository — DB-backed queries."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class RealComparisonRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def compare_districts(self, district_codes: list[str]) -> dict:
        if len(district_codes) < 2 or len(district_codes) > 3:
            return {"error": "비교는 2~3개 상권만 가능합니다."}

        from server.models.population import FloatingPopulation
        from server.models.sales import EstimatedSales
        from server.models.store import Store

        results: dict[str, dict] = {}

        async with self._sf() as session:
            for code in district_codes:
                district_data: dict = {"district_code": code}

                name_q = await session.execute(
                    select(Store.district_code).where(Store.district_code == code).limit(1)
                )
                if name_q.scalar_one_or_none() is None:
                    district_data["error"] = "데이터 없음"
                    results[code] = district_data
                    continue

                # Floating Population
                fp_latest = await session.execute(
                    select(FloatingPopulation.quarter)
                    .where(FloatingPopulation.district_code == code)
                    .order_by(FloatingPopulation.quarter.desc())
                    .limit(1)
                )
                fp_quarter = fp_latest.scalar_one_or_none()
                if fp_quarter:
                    fp_row = (
                        await session.execute(
                            select(
                                func.sum(FloatingPopulation.total_pop).label("total"),
                                func.sum(FloatingPopulation.age_10_pop).label("a10"),
                                func.sum(FloatingPopulation.age_20_pop).label("a20"),
                                func.sum(FloatingPopulation.age_30_pop).label("a30"),
                                func.sum(FloatingPopulation.age_40_pop).label("a40"),
                                func.sum(FloatingPopulation.age_50_pop).label("a50"),
                                func.sum(FloatingPopulation.age_60_plus_pop).label("a60"),
                            ).where(FloatingPopulation.district_code == code, FloatingPopulation.quarter == fp_quarter)
                        )
                    ).one()
                    age_map = {
                        "10대": int(fp_row.a10 or 0), "20대": int(fp_row.a20 or 0),
                        "30대": int(fp_row.a30 or 0), "40대": int(fp_row.a40 or 0),
                        "50대": int(fp_row.a50 or 0), "60대 이상": int(fp_row.a60 or 0),
                    }
                    district_data["floating_pop"] = int(fp_row.total or 0)
                    district_data["main_age"] = max(age_map, key=age_map.get) if any(age_map.values()) else "-"
                else:
                    district_data["floating_pop"] = 0
                    district_data["main_age"] = "-"

                # Stores
                st_latest = await session.execute(
                    select(Store.quarter).where(Store.district_code == code)
                    .order_by(Store.quarter.desc()).limit(1)
                )
                st_quarter = st_latest.scalar_one_or_none()
                if st_quarter:
                    st_row = (
                        await session.execute(
                            select(
                                func.sum(Store.store_count).label("total"),
                                func.sum(Store.close_count).label("closes"),
                            ).where(Store.district_code == code, Store.quarter == st_quarter)
                        )
                    ).one()
                    total_stores = int(st_row.total or 0)
                    close_count = int(st_row.closes or 0)
                    district_data["store_count"] = total_stores
                    district_data["close_rate"] = round(close_count / total_stores * 100, 1) if total_stores else 0.0
                else:
                    district_data["store_count"] = 0
                    district_data["close_rate"] = 0.0

                # Sales + trend
                sales_latest = await session.execute(
                    select(EstimatedSales.quarter).where(EstimatedSales.district_code == code)
                    .order_by(EstimatedSales.quarter.desc()).limit(1)
                )
                sales_quarter = sales_latest.scalar_one_or_none()
                if sales_quarter:
                    sales_row = (
                        await session.execute(
                            select(func.sum(EstimatedSales.monthly_sales).label("total"))
                            .where(EstimatedSales.district_code == code, EstimatedSales.quarter == sales_quarter)
                        )
                    ).one()
                    monthly_sales = int(sales_row.total or 0)

                    trend_rows = (
                        await session.execute(
                            select(EstimatedSales.quarter, func.sum(EstimatedSales.monthly_sales).label("sales"))
                            .where(EstimatedSales.district_code == code)
                            .group_by(EstimatedSales.quarter)
                            .order_by(EstimatedSales.quarter.desc())
                            .limit(2)
                        )
                    ).all()
                    status = "stable"
                    if len(trend_rows) >= 2:
                        recent = int(trend_rows[0].sales or 0)
                        prev = int(trend_rows[1].sales or 0)
                        if prev > 0:
                            change = (recent - prev) / prev
                            if change > 0.05:
                                status = "growing"
                            elif change < -0.05:
                                status = "declining"
                    district_data["monthly_sales"] = monthly_sales
                    district_data["status"] = status
                    district_data["quarter"] = sales_quarter
                else:
                    district_data["monthly_sales"] = 0
                    district_data["status"] = "stable"

                results[code] = district_data

        return {"districts": results, "district_codes": district_codes}
