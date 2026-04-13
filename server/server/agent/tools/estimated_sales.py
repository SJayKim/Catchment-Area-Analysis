from server.agent.tools.registry import register_tool
from server.repositories import get_data_access
from server.services.cache import get_cache_service


def _enrich_sales(result: dict) -> dict:
    """Add derived metrics to sales result."""
    sales = result.get("total_monthly_sales", 0)
    count = result.get("total_sales_count", 0)
    weekday = result.get("weekday_sales", 0)
    weekend = result.get("weekend_sales", 0)

    computed: dict = {}

    # Per-transaction amount
    if count > 0:
        computed["avg_transaction"] = round(sales / count)

    # Weekend metrics
    total_wk = weekday + weekend
    if total_wk > 0:
        computed["weekend_share_pct"] = round(weekend / total_wk * 100, 1)
    if weekday > 0:
        computed["weekend_uplift_pct"] = round((weekend - weekday) / weekday * 100, 1)

    # QoQ & annual growth
    quarterly = result.get("quarterly_sales", [])
    if len(quarterly) >= 2:
        prev = quarterly[-2].get("sales", 0)
        curr = quarterly[-1].get("sales", 0)
        if prev > 0:
            computed["qoq_growth_pct"] = round((curr - prev) / prev * 100, 1)
        if len(quarterly) >= 5:
            old = quarterly[-5].get("sales", 0)
            if old > 0:
                computed["annual_growth_pct"] = round((curr - old) / old * 100, 1)

    # Peak daypart
    time_sales = result.get("time_sales", {})
    if time_sales:
        peak_slot = max(time_sales, key=time_sales.get)
        peak_val = time_sales[peak_slot]
        share = round(peak_val / sales * 100, 1) if sales > 0 else 0
        computed["peak_daypart"] = {"slot": peak_slot, "share_pct": share}

    # Dominant age
    age_sales = result.get("age_sales", {})
    if age_sales:
        top_age = max(age_sales, key=age_sales.get)
        share = round(age_sales[top_age] / sales * 100, 1) if sales > 0 else 0
        computed["dominant_age"] = {"group": top_age, "share_pct": share}

    if computed:
        result["computed"] = computed
    return result


@register_tool(
    "get_estimated_sales",
    emoji="🔍",
    progress_label="매출 데이터 조회 중...",
    done_label="매출 조회 완료",
)
async def get_estimated_sales(
    district_code: str, category_code: str | None = None
) -> dict:
    """Query estimated sales for a district."""
    cache = get_cache_service()
    cache_key = f"sales:{district_code}:{category_code or 'all'}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    da = get_data_access()
    result = await da.sales.get_estimated_sales(district_code, category_code)

    if "error" not in result:
        result = _enrich_sales(result)
        await cache.set(cache_key, result, ttl=86400)
    return result
