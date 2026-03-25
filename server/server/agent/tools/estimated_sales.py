from sqlalchemy import func, select

from server.config import settings
from server.services.cache import cache_service


async def get_estimated_sales(
    district_code: str, category_code: str | None = None
) -> dict:
    """Query estimated sales for a district.

    Returns total monthly sales, quarterly trend, and trend direction.
    """
    cache_key = f"sales:{district_code}:{category_code or 'all'}"
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return cached

    if settings.use_mock:
        from server.agent.tools.mock_data import ESTIMATED_SALES
        result = ESTIMATED_SALES.get(district_code)
        if result is None:
            return {"error": "해당 상권의 매출 데이터가 없습니다.", "district_code": district_code}
        await cache_service.set(cache_key, result, ttl=86400)
        return result

    from server.models.base import async_session
    from server.models.sales import EstimatedSales

    async with async_session() as session:
        # Determine latest quarter
        latest_q = await session.execute(
            select(EstimatedSales.quarter)
            .where(EstimatedSales.district_code == district_code)
            .order_by(EstimatedSales.quarter.desc())
            .limit(1)
        )
        quarter = latest_q.scalar_one_or_none()
        if quarter is None:
            return {"error": "해당 상권의 매출 데이터가 없습니다.", "district_code": district_code}

        # --- Current quarter totals ---
        base_filter = [
            EstimatedSales.district_code == district_code,
            EstimatedSales.quarter == quarter,
        ]
        if category_code:
            base_filter.append(EstimatedSales.category_code == category_code)

        agg_stmt = select(
            func.sum(EstimatedSales.monthly_sales).label("total_monthly_sales"),
            func.sum(EstimatedSales.sales_count).label("total_sales_count"),
            func.sum(EstimatedSales.weekday_sales).label("weekday_sales"),
            func.sum(EstimatedSales.weekend_sales).label("weekend_sales"),
            func.sum(EstimatedSales.male_sales).label("male_sales"),
            func.sum(EstimatedSales.female_sales).label("female_sales"),
        ).where(*base_filter)
        agg_row = (await session.execute(agg_stmt)).one()

        total_monthly_sales = int(agg_row.total_monthly_sales or 0)
        total_sales_count = int(agg_row.total_sales_count or 0)
        weekday_sales = int(agg_row.weekday_sales or 0)
        weekend_sales = int(agg_row.weekend_sales or 0)
        male_sales = int(agg_row.male_sales or 0)
        female_sales = int(agg_row.female_sales or 0)

        # --- Age breakdown for current quarter ---
        age_stmt = select(
            func.sum(EstimatedSales.age_10_sales).label("age_10"),
            func.sum(EstimatedSales.age_20_sales).label("age_20"),
            func.sum(EstimatedSales.age_30_sales).label("age_30"),
            func.sum(EstimatedSales.age_40_sales).label("age_40"),
            func.sum(EstimatedSales.age_50_sales).label("age_50"),
            func.sum(EstimatedSales.age_60_plus_sales).label("age_60_plus"),
        ).where(*base_filter)
        age_row = (await session.execute(age_stmt)).one()
        age_sales = {
            "10대": int(age_row.age_10 or 0),
            "20대": int(age_row.age_20 or 0),
            "30대": int(age_row.age_30 or 0),
            "40대": int(age_row.age_40 or 0),
            "50대": int(age_row.age_50 or 0),
            "60대 이상": int(age_row.age_60_plus or 0),
        }

        # --- Time-slot breakdown ---
        time_stmt = select(
            func.sum(EstimatedSales.time_1_sales).label("t1"),
            func.sum(EstimatedSales.time_2_sales).label("t2"),
            func.sum(EstimatedSales.time_3_sales).label("t3"),
            func.sum(EstimatedSales.time_4_sales).label("t4"),
            func.sum(EstimatedSales.time_5_sales).label("t5"),
            func.sum(EstimatedSales.time_6_sales).label("t6"),
        ).where(*base_filter)
        time_row = (await session.execute(time_stmt)).one()
        time_sales = {
            "00~06시": int(time_row.t1 or 0),
            "06~11시": int(time_row.t2 or 0),
            "11~14시": int(time_row.t3 or 0),
            "14~17시": int(time_row.t4 or 0),
            "17~21시": int(time_row.t5 or 0),
            "21~24시": int(time_row.t6 or 0),
        }

        # --- Quarterly trend (last 4 quarters) ---
        trend_filter = [EstimatedSales.district_code == district_code]
        if category_code:
            trend_filter.append(EstimatedSales.category_code == category_code)

        trend_stmt = (
            select(
                EstimatedSales.quarter,
                func.sum(EstimatedSales.monthly_sales).label("sales"),
            )
            .where(*trend_filter)
            .group_by(EstimatedSales.quarter)
            .order_by(EstimatedSales.quarter.desc())
            .limit(4)
        )
        trend_rows = (await session.execute(trend_stmt)).all()
        quarterly_sales = [
            {"quarter": row.quarter, "monthly_sales": int(row.sales or 0)}
            for row in reversed(trend_rows)
        ]

        # Determine trend direction
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

    result = {
        "district_code": district_code,
        "quarter": quarter,
        "total_monthly_sales": total_monthly_sales,
        "total_sales_count": total_sales_count,
        "weekday_sales": weekday_sales,
        "weekend_sales": weekend_sales,
        "gender_sales": {
            "male": male_sales,
            "female": female_sales,
        },
        "age_sales": age_sales,
        "time_sales": time_sales,
        "trend": trend,
        "quarterly_sales": quarterly_sales,
    }

    await cache_service.set(cache_key, result, ttl=86400)
    return result
