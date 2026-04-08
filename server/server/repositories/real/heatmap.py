"""Real heatmap repository — PostGIS + floating_population aggregation."""

from __future__ import annotations

from sqlalchemy import func, select, text, cast, Float
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class RealHeatmapRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def get_heatmap_data(
        self, time_slot: int, quarter: str | None = None
    ) -> dict:
        from server.models.district import District
        from server.models.population import FloatingPopulation

        async with self._sf() as session:
            if not quarter:
                latest = await session.execute(
                    select(FloatingPopulation.quarter)
                    .order_by(FloatingPopulation.quarter.desc())
                    .limit(1)
                )
                quarter = latest.scalar_one_or_none()
                if not quarter:
                    return {"time_slot": time_slot, "quarter": "", "points": []}

            # Join floating_population with districts to get center_point coordinates
            stmt = (
                select(
                    func.ST_Y(District.center_point).label("lat"),
                    func.ST_X(District.center_point).label("lng"),
                    func.sum(FloatingPopulation.total_pop).label("weight"),
                )
                .join(
                    District,
                    FloatingPopulation.district_code == District.district_code,
                )
                .where(
                    FloatingPopulation.quarter == quarter,
                    FloatingPopulation.time_slot == time_slot,
                    District.center_point.isnot(None),
                )
                .group_by(District.center_point)
            )

            rows = (await session.execute(stmt)).all()

            points = [
                {
                    "lat": round(float(r.lat), 6),
                    "lng": round(float(r.lng), 6),
                    "weight": int(r.weight or 0),
                }
                for r in rows
                if r.lat and r.lng
            ]

        return {
            "time_slot": time_slot,
            "quarter": quarter,
            "points": points,
        }

    async def get_heatmap_all(self, quarter: str | None = None) -> dict:
        from server.models.district import District
        from server.models.population import FloatingPopulation

        async with self._sf() as session:
            if not quarter:
                latest = await session.execute(
                    select(FloatingPopulation.quarter)
                    .order_by(FloatingPopulation.quarter.desc())
                    .limit(1)
                )
                quarter = latest.scalar_one_or_none()
                if not quarter:
                    return {"quarter": "", "slots": {}}

            stmt = (
                select(
                    FloatingPopulation.time_slot,
                    func.ST_Y(District.center_point).label("lat"),
                    func.ST_X(District.center_point).label("lng"),
                    func.sum(FloatingPopulation.total_pop).label("weight"),
                )
                .join(
                    District,
                    FloatingPopulation.district_code == District.district_code,
                )
                .where(
                    FloatingPopulation.quarter == quarter,
                    District.center_point.isnot(None),
                )
                .group_by(FloatingPopulation.time_slot, District.center_point)
                .order_by(FloatingPopulation.time_slot)
            )

            rows = (await session.execute(stmt)).all()

        slots: dict[str, list[dict]] = {}
        for r in rows:
            if not r.lat or not r.lng:
                continue
            ts = str(r.time_slot)
            if ts not in slots:
                slots[ts] = []
            slots[ts].append({
                "lat": round(float(r.lat), 6),
                "lng": round(float(r.lng), 6),
                "weight": int(r.weight or 0),
            })

        return {"quarter": quarter, "slots": slots}
