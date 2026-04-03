"""Real population repository — DB-backed queries."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class RealPopulationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def get_population_info(self, district_code: str) -> dict:
        from server.models.population import ResidentPopulation

        async with self._sf() as session:
            latest_q = await session.execute(
                select(ResidentPopulation.quarter)
                .where(ResidentPopulation.district_code == district_code)
                .order_by(ResidentPopulation.quarter.desc())
                .limit(1)
            )
            quarter = latest_q.scalar_one_or_none()
            if quarter is None:
                return {"error": "해당 상권의 인구 데이터가 없습니다.", "district_code": district_code}

            base_filter = [
                ResidentPopulation.district_code == district_code,
                ResidentPopulation.quarter == quarter,
            ]

            # Totals by pop_type
            type_rows = (
                await session.execute(
                    select(ResidentPopulation.pop_type, func.sum(ResidentPopulation.population).label("total"))
                    .where(*base_filter)
                    .group_by(ResidentPopulation.pop_type)
                )
            ).all()
            totals = {row.pop_type: int(row.total) for row in type_rows}

            # Age distribution by pop_type
            age_rows = (
                await session.execute(
                    select(
                        ResidentPopulation.pop_type,
                        ResidentPopulation.age_group,
                        func.sum(ResidentPopulation.population).label("total"),
                    )
                    .where(*base_filter)
                    .group_by(ResidentPopulation.pop_type, ResidentPopulation.age_group)
                    .order_by(ResidentPopulation.pop_type, ResidentPopulation.age_group)
                )
            ).all()
            age_by_type: dict[str, dict[str, int]] = {}
            for row in age_rows:
                age_by_type.setdefault(row.pop_type, {})[row.age_group] = int(row.total)

            # Gender distribution by pop_type
            gender_rows = (
                await session.execute(
                    select(
                        ResidentPopulation.pop_type,
                        ResidentPopulation.gender,
                        func.sum(ResidentPopulation.population).label("total"),
                    )
                    .where(*base_filter)
                    .group_by(ResidentPopulation.pop_type, ResidentPopulation.gender)
                )
            ).all()
            gender_by_type: dict[str, dict[str, int]] = {}
            for row in gender_rows:
                gender_by_type.setdefault(row.pop_type, {})[row.gender] = int(row.total)

        def _build_pop_detail(pop_type: str) -> dict:
            total = totals.get(pop_type, 0)
            age_data = age_by_type.get(pop_type, {})
            gender_data = gender_by_type.get(pop_type, {})
            gender_total = sum(gender_data.values()) or 1
            return {
                "total": total,
                "age_distribution": age_data,
                "gender": {
                    "male": gender_data.get("M", 0),
                    "female": gender_data.get("F", 0),
                    "male_ratio": round(gender_data.get("M", 0) / gender_total * 100, 1),
                    "female_ratio": round(gender_data.get("F", 0) / gender_total * 100, 1),
                },
            }

        return {
            "district_code": district_code,
            "quarter": quarter,
            "resident": _build_pop_detail("resident"),
            "worker": _build_pop_detail("worker"),
        }
