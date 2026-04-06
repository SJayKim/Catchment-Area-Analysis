"""simulate_revenue tool — estimate monthly revenue for a business category."""

from __future__ import annotations

from server.agent.tools.registry import register_tool
from server.repositories import get_data_access
from server.services.cache import get_cache_service


@register_tool(
    "simulate_revenue",
    emoji="💰",
    card_type="simulation",
    progress_label="매출 시뮬레이션 중...",
    done_label="매출 시뮬레이션 완료",
)
async def simulate_revenue(
    district_code: str,
    category_code: str,
    unit_price: int | None = None,
    additional_competitors: int = 0,
) -> dict:
    """Simulate monthly revenue for opening a business in a district.

    Steps:
    1. Get sales + store data for district+category
    2. Calculate per-store average (adjusted for additional competitors)
    3. Get Seoul-wide percentiles for the category
    4. Apply p25/p75 ratios for low/high estimates
    5. Adjust for user-provided unit price vs default
    6. Compare against Seoul average
    """
    cache = get_cache_service()
    cache_key = f"simulation:{district_code}:{category_code}:{unit_price or 'default'}:{additional_competitors}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    da = get_data_access()

    # 1. Get district sales + store data
    sales_data = await da.sales.get_estimated_sales(district_code, category_code)
    store_data = await da.stores.get_store_info(district_code, category_code)

    if "error" in sales_data:
        return {
            "error": f"해당 상권의 {category_code} 업종 매출 데이터가 없습니다.",
            "district_code": district_code,
            "category_code": category_code,
        }

    # Extract values
    total_monthly_sales = sales_data.get("total_monthly_sales", 0)
    store_count = store_data.get("total_stores", store_data.get("store_count", 0))
    category_name = store_data.get("category_name") or sales_data.get("category_name", "")
    quarter = sales_data.get("quarter", "")

    if store_count == 0 and total_monthly_sales == 0:
        return {
            "error": "해당 업종의 점포/매출 데이터가 부족합니다.",
            "district_code": district_code,
            "category_code": category_code,
        }

    # 2. Per-store average (with additional competitors)
    effective_stores = max(store_count + additional_competitors, 1)
    per_store_avg = total_monthly_sales / effective_stores

    # 3. Seoul-wide percentiles
    percentiles = await da.simulation.get_sales_percentiles(category_code, quarter)
    if "error" in percentiles:
        # Fallback ratios
        p25_ratio = 0.6
        p75_ratio = 1.5
        seoul_avg = 0
        sample_count = 0
        reliable = False
    else:
        sample_count = percentiles.get("sample_count", 0)
        reliable = sample_count >= 10
        if reliable:
            p25_ratio = percentiles["p25_ratio"]
            p75_ratio = percentiles["p75_ratio"]
        else:
            p25_ratio = 0.6
            p75_ratio = 1.5
        seoul_avg = percentiles.get("seoul_avg_per_store", 0)

    # 4. Low / High estimates
    low_estimate = int(per_store_avg * p25_ratio)
    high_estimate = int(per_store_avg * p75_ratio)

    # 5. Unit price adjustment
    default_price = await da.simulation.get_default_unit_price(category_code)
    price_ratio = 1.0
    if unit_price and default_price and default_price > 0:
        price_ratio = unit_price / default_price
        per_store_avg = int(per_store_avg * price_ratio)
        low_estimate = int(low_estimate * price_ratio)
        high_estimate = int(high_estimate * price_ratio)

    # 6. Seoul comparison
    seoul_comparison = None
    if seoul_avg and seoul_avg > 0:
        diff_pct = round((per_store_avg - seoul_avg) / seoul_avg * 100, 1)
        seoul_comparison = {
            "seoul_avg": int(seoul_avg),
            "diff_percent": diff_pct,
            "label": "높음" if diff_pct > 0 else "낮음" if diff_pct < 0 else "동일",
        }

    result = {
        "district_code": district_code,
        "category_code": category_code,
        "category_name": category_name,
        "quarter": quarter,
        "simulation": {
            "low": low_estimate,
            "avg": int(per_store_avg),
            "high": high_estimate,
        },
        "basis": {
            "total_monthly_sales": total_monthly_sales,
            "store_count": store_count,
            "additional_competitors": additional_competitors,
            "effective_stores": effective_stores,
            "unit_price": unit_price,
            "default_unit_price": default_price,
            "price_ratio": round(price_ratio, 2),
        },
        "percentiles": {
            "p25_ratio": p25_ratio,
            "p75_ratio": p75_ratio,
            "sample_count": sample_count,
            "reliable": reliable,
        },
        "seoul_comparison": seoul_comparison,
        "disclaimer": "본 시뮬레이션은 카드매출 기반 추정치이며, 실제 매출과 다를 수 있습니다.",
    }

    await cache.set(cache_key, result, ttl=86400)
    return result
