from sqlalchemy import func, select

from server.config import settings
from server.services.cache import cache_service


async def get_store_info(
    district_code: str, category_code: str | None = None
) -> dict:
    """Query store information for a district.

    Returns total stores, open/close counts, close rate, and top categories.
    """
    cache_key = f"store:{district_code}:{category_code or 'all'}"
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return cached

    if settings.use_mock:
        from server.agent.tools.mock_data import STORE_INFO
        result = STORE_INFO.get(district_code)
        if result is None:
            return {"error": "해당 상권의 점포 데이터가 없습니다.", "district_code": district_code}
        await cache_service.set(cache_key, result, ttl=86400)
        return result

    from server.models.base import async_session
    from server.models.store import Store

    async with async_session() as session:
        # Determine latest quarter
        latest_q = await session.execute(
            select(Store.quarter)
            .where(Store.district_code == district_code)
            .order_by(Store.quarter.desc())
            .limit(1)
        )
        quarter = latest_q.scalar_one_or_none()
        if quarter is None:
            return {"error": "해당 상권의 점포 데이터가 없습니다.", "district_code": district_code}

        base_filter = [
            Store.district_code == district_code,
            Store.quarter == quarter,
        ]
        if category_code:
            base_filter.append(Store.category_code == category_code)

        # --- Aggregates ---
        agg_stmt = select(
            func.sum(Store.store_count).label("total_stores"),
            func.sum(Store.open_count).label("open_count"),
            func.sum(Store.close_count).label("close_count"),
            func.sum(Store.franchise_count).label("franchise_count"),
        ).where(*base_filter)
        agg_row = (await session.execute(agg_stmt)).one()

        total_stores = int(agg_row.total_stores or 0)
        open_count = int(agg_row.open_count or 0)
        close_count = int(agg_row.close_count or 0)
        franchise_count = int(agg_row.franchise_count or 0)
        close_rate = round(close_count / total_stores * 100, 1) if total_stores else 0.0

        # --- Top categories by store_count ---
        top_stmt = (
            select(
                Store.category_code,
                Store.category_name,
                Store.store_count,
                Store.open_count,
                Store.close_count,
            )
            .where(
                Store.district_code == district_code,
                Store.quarter == quarter,
            )
            .order_by(Store.store_count.desc())
            .limit(5)
        )
        top_rows = (await session.execute(top_stmt)).all()
        top_categories = [
            {
                "category_code": row.category_code,
                "category_name": row.category_name,
                "store_count": int(row.store_count or 0),
                "open_count": int(row.open_count or 0),
                "close_count": int(row.close_count or 0),
            }
            for row in top_rows
        ]

    result = {
        "district_code": district_code,
        "quarter": quarter,
        "total_stores": total_stores,
        "open_count": open_count,
        "close_count": close_count,
        "close_rate": close_rate,
        "franchise_count": franchise_count,
        "top_categories": top_categories,
    }

    await cache_service.set(cache_key, result, ttl=86400)
    return result
