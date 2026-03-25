from sqlalchemy import func, select

from server.config import settings
from server.services.cache import cache_service


async def get_population_info(district_code: str) -> dict:
    """Query resident and worker population for a district.

    Returns totals and age/gender breakdowns for both population types.
    """
    cache_key = f"pop:{district_code}"
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return cached

    if settings.use_mock:
        from server.agent.tools.mock_data import POPULATION_INFO
        result = POPULATION_INFO.get(district_code)
        if result is None:
            return {"error": "해당 상권의 인구 데이터가 없습니다.", "district_code": district_code}
        await cache_service.set(cache_key, result, ttl=86400)
        return result

    from server.models.base import async_session
    from server.models.population import ResidentPopulation

    async with async_session() as session:
        # Determine latest quarter
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

        # --- Totals by pop_type ---
        type_stmt = (
            select(
                ResidentPopulation.pop_type,
                func.sum(ResidentPopulation.population).label("total"),
            )
            .where(*base_filter)
            .group_by(ResidentPopulation.pop_type)
        )
        type_rows = (await session.execute(type_stmt)).all()
        totals = {row.pop_type: int(row.total) for row in type_rows}

        # --- Age distribution by pop_type ---
        age_stmt = (
            select(
                ResidentPopulation.pop_type,
                ResidentPopulation.age_group,
                func.sum(ResidentPopulation.population).label("total"),
            )
            .where(*base_filter)
            .group_by(ResidentPopulation.pop_type, ResidentPopulation.age_group)
            .order_by(ResidentPopulation.pop_type, ResidentPopulation.age_group)
        )
        age_rows = (await session.execute(age_stmt)).all()

        age_by_type: dict[str, dict[str, int]] = {}
        for row in age_rows:
            age_by_type.setdefault(row.pop_type, {})[row.age_group] = int(row.total)

        # --- Gender distribution by pop_type ---
        gender_stmt = (
            select(
                ResidentPopulation.pop_type,
                ResidentPopulation.gender,
                func.sum(ResidentPopulation.population).label("total"),
            )
            .where(*base_filter)
            .group_by(ResidentPopulation.pop_type, ResidentPopulation.gender)
        )
        gender_rows = (await session.execute(gender_stmt)).all()

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

    result = {
        "district_code": district_code,
        "quarter": quarter,
        "resident": _build_pop_detail("resident"),
        "worker": _build_pop_detail("worker"),
    }

    await cache_service.set(cache_key, result, ttl=86400)
    return result
