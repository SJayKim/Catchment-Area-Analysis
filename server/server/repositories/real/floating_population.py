"""Real floating population repository — DB-backed queries."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class RealFloatingPopulationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def get_floating_population(
        self, district_code: str, quarter: str | None = None
    ) -> dict:
        from server.models.population import FloatingPopulation as FPModel

        async with self._sf() as session:
            if quarter is None:
                latest_q = await session.execute(
                    select(FPModel.quarter)
                    .where(FPModel.district_code == district_code)
                    .order_by(FPModel.quarter.desc())
                    .limit(1)
                )
                quarter = latest_q.scalar_one_or_none()
                if quarter is None:
                    return {"error": "해당 상권의 유동인구 데이터가 없습니다.", "district_code": district_code}

            # Hourly breakdown
            hourly_rows = (
                await session.execute(
                    select(FPModel.time_slot, func.sum(FPModel.total_pop).label("total"))
                    .where(FPModel.district_code == district_code, FPModel.quarter == quarter)
                    .group_by(FPModel.time_slot)
                    .order_by(FPModel.time_slot)
                )
            ).all()

            by_hour = [{"time_slot": row.time_slot, "population": int(row.total)} for row in hourly_rows]
            daily_avg = sum(row.total for row in hourly_rows)
            peak_hour = max(hourly_rows, key=lambda r: r.total).time_slot if hourly_rows else None

            # Gender totals
            gender_row = (
                await session.execute(
                    select(
                        func.sum(FPModel.male_pop).label("male"),
                        func.sum(FPModel.female_pop).label("female"),
                    ).where(FPModel.district_code == district_code, FPModel.quarter == quarter)
                )
            ).one()
            male_total = int(gender_row.male or 0)
            female_total = int(gender_row.female or 0)
            gender_sum = male_total + female_total or 1

            # Age distribution
            age_row = (
                await session.execute(
                    select(
                        func.sum(FPModel.age_10_pop).label("age_10"),
                        func.sum(FPModel.age_20_pop).label("age_20"),
                        func.sum(FPModel.age_30_pop).label("age_30"),
                        func.sum(FPModel.age_40_pop).label("age_40"),
                        func.sum(FPModel.age_50_pop).label("age_50"),
                        func.sum(FPModel.age_60_plus_pop).label("age_60_plus"),
                    ).where(FPModel.district_code == district_code, FPModel.quarter == quarter)
                )
            ).one()
            age_values = {
                "10대": int(age_row.age_10 or 0),
                "20대": int(age_row.age_20 or 0),
                "30대": int(age_row.age_30 or 0),
                "40대": int(age_row.age_40 or 0),
                "50대": int(age_row.age_50 or 0),
                "60대 이상": int(age_row.age_60_plus or 0),
            }
            age_total = sum(age_values.values()) or 1
            age_distribution = {k: round(v / age_total * 100, 1) for k, v in age_values.items()}

        return {
            "district_code": district_code,
            "quarter": quarter,
            "daily_avg": int(daily_avg),
            "peak_hour": peak_hour,
            "by_hour": by_hour,
            "gender": {
                "male_ratio": round(male_total / gender_sum * 100, 1),
                "female_ratio": round(female_total / gender_sum * 100, 1),
            },
            "age_distribution": age_distribution,
        }
