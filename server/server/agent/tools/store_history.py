from sqlalchemy import func, select

from server.config import settings
from server.services.cache import cache_service


def _detect_trend(close_counts: list[int]) -> dict:
    """Detect trend direction from recent quarterly close counts using linear regression."""
    n = len(close_counts)
    if n < 2:
        return {"direction": "insufficient_data", "adjustment": 0, "detail": "데이터 부족"}

    x = list(range(n))
    x_mean = sum(x) / n
    y_mean = sum(close_counts) / n
    numerator = sum((x[i] - x_mean) * (close_counts[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator != 0 else 0

    change_rate = slope / y_mean if y_mean > 0 else 0

    if change_rate > 0.15:
        return {"direction": "increasing", "adjustment": -15,
                "detail": f"폐업이 분기당 {abs(change_rate) * 100:.0f}% 증가 추세"}
    elif change_rate > 0.05:
        return {"direction": "slightly_increasing", "adjustment": -7,
                "detail": "폐업이 소폭 증가 추세"}
    elif change_rate < -0.15:
        return {"direction": "decreasing", "adjustment": 10,
                "detail": f"폐업이 분기당 {abs(change_rate) * 100:.0f}% 감소 추세"}
    elif change_rate < -0.05:
        return {"direction": "slightly_decreasing", "adjustment": 5,
                "detail": "폐업이 소폭 감소 추세"}
    else:
        return {"direction": "stable", "adjustment": 0, "detail": "폐업 추세 보합"}


def _get_grade(score: int) -> str:
    if score >= 80:
        return "매우 안정"
    elif score >= 60:
        return "양호"
    elif score >= 40:
        return "주의"
    else:
        return "위험"


async def get_store_history(district_code: str) -> dict:
    """Analyze store history and risk indicators for a district.

    Returns stability score, survival by category, risk categories,
    and quarterly open/close trend.
    """
    cache_key = f"history:{district_code}"
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return cached

    if settings.use_mock:
        from server.agent.tools.mock_data import STORE_HISTORY
        result = STORE_HISTORY.get(district_code)
        if result is None:
            return {"error": "해당 상권의 이력 데이터가 없습니다.", "district_code": district_code}
        await cache_service.set(cache_key, result, ttl=86400)
        return result

    from server.models.base import async_session
    from server.models.store import Store, StoreHistory as StoreHistoryModel

    async with async_session() as session:
        # --- 1. Survival by category (closed stores only, min 3 samples) ---
        survival_stmt = (
            select(
                StoreHistoryModel.category_name,
                func.avg(StoreHistoryModel.duration_months).label("avg_months"),
                func.count().label("sample_count"),
            )
            .where(
                StoreHistoryModel.district_code == district_code,
                StoreHistoryModel.close_date.isnot(None),
                StoreHistoryModel.duration_months.isnot(None),
            )
            .group_by(StoreHistoryModel.category_name)
            .having(func.count() >= 3)
            .order_by(func.avg(StoreHistoryModel.duration_months).desc())
        )
        survival_rows = (await session.execute(survival_stmt)).all()
        survival_by_category = [
            {
                "category": row.category_name,
                "avg_months": round(float(row.avg_months), 1),
                "sample_count": int(row.sample_count),
            }
            for row in survival_rows
        ]

        # --- 2. Quarterly open/close trend (last 4 quarters) ---
        trend_stmt = (
            select(
                Store.quarter,
                func.sum(Store.store_count).label("stores"),
                func.sum(Store.open_count).label("opens"),
                func.sum(Store.close_count).label("closes"),
            )
            .where(Store.district_code == district_code)
            .group_by(Store.quarter)
            .order_by(Store.quarter.desc())
            .limit(4)
        )
        trend_rows = (await session.execute(trend_stmt)).all()
        quarterly_trend = [
            {
                "quarter": row.quarter,
                "store_count": int(row.stores or 0),
                "open": int(row.opens or 0),
                "close": int(row.closes or 0),
            }
            for row in reversed(trend_rows)
        ]

        # --- 3. Stability score ---
        if len(quarterly_trend) < 2:
            stability = {
                "score": None,
                "grade": "데이터 부족",
                "message": "2분기 이상 데이터가 쌓이면 리스크 분석이 가능합니다",
                "quarters_analyzed": len(quarterly_trend),
            }
        else:
            avg_stores = sum(q["store_count"] for q in quarterly_trend) / len(quarterly_trend)
            total_closes = sum(q["close"] for q in quarterly_trend)
            avg_close_rate = total_closes / (avg_stores * len(quarterly_trend)) if avg_stores else 0
            base_score = max(0, 100 - avg_close_rate * 1000)

            trend_result = _detect_trend([q["close"] for q in quarterly_trend])
            score = round(min(100, max(0, base_score + trend_result["adjustment"])))
            stability = {
                "score": score,
                "grade": _get_grade(score),
                "trend": trend_result,
                "quarters_analyzed": len(quarterly_trend),
            }

        # --- 4. Risk categories (high close rate) ---
        latest_quarter = quarterly_trend[-1]["quarter"] if quarterly_trend else None
        risk_categories = []

        if latest_quarter:
            cat_stmt = (
                select(
                    Store.category_name,
                    Store.store_count,
                    Store.close_count,
                )
                .where(
                    Store.district_code == district_code,
                    Store.quarter == latest_quarter,
                    Store.store_count > 0,
                )
                .order_by(
                    (Store.close_count * 100.0 / Store.store_count).desc()
                )
            )
            cat_rows = (await session.execute(cat_stmt)).all()

            close_rates = []
            for row in cat_rows:
                store_ct = int(row.store_count or 0)
                close_ct = int(row.close_count or 0)
                if store_ct > 0:
                    close_rates.append(close_ct / store_ct * 100)

            if close_rates:
                sorted_rates = sorted(close_rates, reverse=True)
                p10_idx = max(0, len(sorted_rates) // 10)
                relative_threshold = sorted_rates[p10_idx] if p10_idx < len(sorted_rates) else 10.0
            else:
                relative_threshold = 10.0

            for row in cat_rows:
                store_ct = int(row.store_count or 0)
                close_ct = int(row.close_count or 0)
                if store_ct <= 0:
                    continue
                rate = round(close_ct / store_ct * 100, 1)
                if rate > 15 or rate >= relative_threshold:
                    warning = "폐업률 매우 높음" if rate > 15 else "폐업률 높음"
                    risk_categories.append({
                        "category": row.category_name,
                        "close_rate": rate,
                        "warning": warning,
                    })

    result = {
        "district_code": district_code,
        "stability": stability,
        "survival_by_category": survival_by_category,
        "risk_categories": risk_categories[:10],
        "quarterly_trend": quarterly_trend,
    }

    await cache_service.set(cache_key, result, ttl=86400)
    return result
