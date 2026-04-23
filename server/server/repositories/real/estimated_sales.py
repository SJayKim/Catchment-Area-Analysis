"""Real estimated sales repository — DB-backed queries."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server.repositories.real._units import MONTHS_PER_QUARTER


class RealEstimatedSalesRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def get_estimated_sales(self, district_code: str, category_code: str | None = None) -> dict:
        from server.models.sales import EstimatedSales

        async with self._sf() as session:
            latest_q = await session.execute(
                select(EstimatedSales.quarter)
                .where(EstimatedSales.district_code == district_code)
                .order_by(EstimatedSales.quarter.desc())
                .limit(1)
            )
            quarter = latest_q.scalar_one_or_none()
            if quarter is None:
                return {"error": "해당 상권의 매출 데이터가 없습니다.", "district_code": district_code}

            base_filter = [
                EstimatedSales.district_code == district_code,
                EstimatedSales.quarter == quarter,
            ]
            if category_code:
                base_filter.append(EstimatedSales.category_code == category_code)

            # Current quarter aggregates
            agg_row = (
                await session.execute(
                    select(
                        func.sum(EstimatedSales.monthly_sales).label("total_monthly_sales"),
                        func.sum(EstimatedSales.sales_count).label("total_sales_count"),
                        func.sum(EstimatedSales.weekday_sales).label("weekday_sales"),
                        func.sum(EstimatedSales.weekend_sales).label("weekend_sales"),
                        func.sum(EstimatedSales.male_sales).label("male_sales"),
                        func.sum(EstimatedSales.female_sales).label("female_sales"),
                    ).where(*base_filter)
                )
            ).one()

            # DB stores quarterly aggregates; convert to monthly for display.
            total_monthly_sales = int(agg_row.total_monthly_sales or 0) // MONTHS_PER_QUARTER
            total_sales_count = int(agg_row.total_sales_count or 0) // MONTHS_PER_QUARTER
            weekday_sales = int(agg_row.weekday_sales or 0) // MONTHS_PER_QUARTER
            weekend_sales = int(agg_row.weekend_sales or 0) // MONTHS_PER_QUARTER
            male_sales = int(agg_row.male_sales or 0) // MONTHS_PER_QUARTER
            female_sales = int(agg_row.female_sales or 0) // MONTHS_PER_QUARTER

            # Age breakdown
            age_row = (
                await session.execute(
                    select(
                        func.sum(EstimatedSales.age_10_sales).label("age_10"),
                        func.sum(EstimatedSales.age_20_sales).label("age_20"),
                        func.sum(EstimatedSales.age_30_sales).label("age_30"),
                        func.sum(EstimatedSales.age_40_sales).label("age_40"),
                        func.sum(EstimatedSales.age_50_sales).label("age_50"),
                        func.sum(EstimatedSales.age_60_plus_sales).label("age_60_plus"),
                    ).where(*base_filter)
                )
            ).one()
            age_sales = {
                "10대": int(age_row.age_10 or 0) // MONTHS_PER_QUARTER,
                "20대": int(age_row.age_20 or 0) // MONTHS_PER_QUARTER,
                "30대": int(age_row.age_30 or 0) // MONTHS_PER_QUARTER,
                "40대": int(age_row.age_40 or 0) // MONTHS_PER_QUARTER,
                "50대": int(age_row.age_50 or 0) // MONTHS_PER_QUARTER,
                "60대 이상": int(age_row.age_60_plus or 0) // MONTHS_PER_QUARTER,
            }

            # Time-slot breakdown
            time_row = (
                await session.execute(
                    select(
                        func.sum(EstimatedSales.time_1_sales).label("t1"),
                        func.sum(EstimatedSales.time_2_sales).label("t2"),
                        func.sum(EstimatedSales.time_3_sales).label("t3"),
                        func.sum(EstimatedSales.time_4_sales).label("t4"),
                        func.sum(EstimatedSales.time_5_sales).label("t5"),
                        func.sum(EstimatedSales.time_6_sales).label("t6"),
                    ).where(*base_filter)
                )
            ).one()
            time_sales = {
                "00~06시": int(time_row.t1 or 0) // MONTHS_PER_QUARTER,
                "06~11시": int(time_row.t2 or 0) // MONTHS_PER_QUARTER,
                "11~14시": int(time_row.t3 or 0) // MONTHS_PER_QUARTER,
                "14~17시": int(time_row.t4 or 0) // MONTHS_PER_QUARTER,
                "17~21시": int(time_row.t5 or 0) // MONTHS_PER_QUARTER,
                "21~24시": int(time_row.t6 or 0) // MONTHS_PER_QUARTER,
            }

            # Quarterly trend (last 4 quarters)
            trend_filter = [EstimatedSales.district_code == district_code]
            if category_code:
                trend_filter.append(EstimatedSales.category_code == category_code)

            trend_rows = (
                await session.execute(
                    select(
                        EstimatedSales.quarter,
                        func.sum(EstimatedSales.monthly_sales).label("sales"),
                    )
                    .where(*trend_filter)
                    .group_by(EstimatedSales.quarter)
                    .order_by(EstimatedSales.quarter.desc())
                    .limit(4)
                )
            ).all()
            quarterly_sales = [
                {"quarter": row.quarter, "monthly_sales": int(row.sales or 0) // MONTHS_PER_QUARTER}
                for row in reversed(trend_rows)
            ]

            trend = "stable"
            if len(quarterly_sales) >= 2:
                recent = quarterly_sales[-1]["monthly_sales"]
                previous = quarterly_sales[-2]["monthly_sales"]
                if previous > 0:
                    change_rate = (recent - previous) / previous
                    if change_rate > 0.05:
                        trend = "growing"
                    elif change_rate < -0.05:
                        trend = "declining"

        return {
            "district_code": district_code,
            "quarter": quarter,
            "total_monthly_sales": total_monthly_sales,
            "total_sales_count": total_sales_count,
            "weekday_sales": weekday_sales,
            "weekend_sales": weekend_sales,
            "gender_sales": {"male": male_sales, "female": female_sales},
            "age_sales": age_sales,
            "time_sales": time_sales,
            "trend": trend,
            "quarterly_sales": quarterly_sales,
        }
