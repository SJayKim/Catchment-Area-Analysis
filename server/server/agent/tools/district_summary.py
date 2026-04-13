"""get_district_summary tool — aggregates data into SummaryCardData format."""

from __future__ import annotations

import asyncio

from server.agent.tools.benchmarks import get_district_benchmarks
from server.agent.tools.data_sources import get_sources_for_tool
from server.agent.tools.registry import register_tool
from server.agent.tools.estimated_sales import get_estimated_sales
from server.agent.tools.floating_population import get_floating_population
from server.agent.tools.store_info import get_store_info
from server.config import settings
from server.repositories import get_data_access
from server.services.cache import get_cache_service


def _format_population(pop: int) -> str:
    """Format population number into Korean readable string."""
    man = pop // 10_000
    cheon = (pop % 10_000) // 1_000
    if man and cheon:
        return f"{man}만 {cheon}천명"
    if man:
        return f"{man}만명"
    return f"{pop:,}명"


def _format_sales(sales: int) -> str:
    """Format sales into Korean readable string."""
    eok = sales // 100_000_000
    cheon_man = (sales % 100_000_000) // 10_000_000
    if eok and cheon_man:
        return f"{eok}억 {cheon_man}천만원"
    if eok:
        return f"{eok}억원"
    return f"{sales:,}원"


@register_tool(
    "get_district_summary",
    card_type="summary",
    progress_label="상권 요약 분석 중...",
    done_label="상권 요약 완료",
)
async def get_district_summary(district_code: str) -> dict:
    """Aggregate data for a district into SummaryCardData shape."""
    cache = get_cache_service()
    cache_key = f"summary:{district_code}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    da = get_data_access()

    # 4 parallel calls
    fp_result, sales_result, store_result, meta = await asyncio.gather(
        get_floating_population(district_code),
        get_estimated_sales(district_code),
        get_store_info(district_code),
        da.districts.get_district_meta(district_code),
    )

    if not meta:
        return {"error": f"상권 코드 '{district_code}'에 해당하는 데이터가 없습니다."}

    fp_ok = "error" not in fp_result
    sales_ok = "error" not in sales_result
    store_ok = "error" not in store_result

    by_hour = []
    if fp_ok:
        for entry in fp_result.get("by_hour", []):
            by_hour.append({"hour": entry["time_slot"], "pop": entry["population"]})

    top_categories = []
    if store_ok:
        for cat in store_result.get("top_categories", []):
            top_categories.append({"name": cat["category_name"], "count": cat["store_count"]})

    status = sales_result.get("trend", "stable") if sales_ok else "stable"

    close_rate = {"current": 0.0, "average": 6.5}
    if store_ok:
        close_rate["current"] = store_result.get("close_rate", 0.0)

    daily_avg = fp_result.get("daily_avg", 0) if fp_ok else 0
    monthly_sales = sales_result.get("total_monthly_sales", 0) if sales_ok else 0
    status_label = {"growing": "성장 중인", "stable": "안정적인", "declining": "위축 중인"}.get(status, "안정적인")
    summary_text = (
        f"하루 평균 유동인구 {_format_population(daily_avg)}, "
        f"월 추정 매출 {_format_sales(monthly_sales)}의 "
        f"{status_label} {meta['type']}입니다."
    )

    quarter = (
        fp_result.get("quarter") if fp_ok
        else sales_result.get("quarter") if sales_ok
        else store_result.get("quarter") if store_ok
        else "N/A"
    )

    # "(샘플)" suffix is the one allowed use_mock check (display logic only)
    data_quarter = f"{quarter} (샘플)" if settings.use_mock else quarter

    # --- Insights block (derived metrics for LLM) ---
    insights: dict = {}

    if fp_ok:
        gender = fp_result.get("gender", {})
        m_ratio = gender.get("male_ratio", 50)
        f_ratio = gender.get("female_ratio", 50)
        diff = abs(m_ratio - f_ratio)
        if diff >= 5:
            dominant = "남성" if m_ratio > f_ratio else "여성"
            insights["genderInsight"] = f"{dominant} 비중 높음 ({dominant} {max(m_ratio, f_ratio):.1f}%, 차이 {diff:.1f}%p)"

        age_dist = fp_result.get("age_distribution", {})
        if age_dist:
            top_age = max(age_dist, key=age_dist.get)
            insights["ageInsight"] = f"{top_age} ({age_dist[top_age]:.1f}%)"

    total_stores = store_result.get("total_stores", 0) if store_ok else 0
    if sales_ok and total_stores > 0:
        insights["perStoreSales"] = round(monthly_sales / total_stores)

    if store_ok:
        fran = store_result.get("franchise_count", 0)
        if total_stores > 0:
            insights["franchiseRatio"] = round(fran / total_stores * 100, 1)

    if sales_ok:
        weekday_s = sales_result.get("weekday_sales", 0)
        weekend_s = sales_result.get("weekend_sales", 0)
        if weekday_s > 0:
            insights["weekendUplift"] = round((weekend_s - weekday_s) / weekday_s * 100, 1)

        quarterly = sales_result.get("quarterly_sales", [])
        if len(quarterly) >= 2:
            prev = quarterly[-2].get("sales", 0)
            curr = quarterly[-1].get("sales", 0)
            if prev > 0:
                insights["qoqGrowth"] = round((curr - prev) / prev * 100, 1)

    # --- Benchmarks block (percentile rankings within district type) ---
    per_store = insights.get("perStoreSales", 0)
    benchmarks = await get_district_benchmarks(
        meta["type"],
        floating_pop=daily_avg,
        monthly_sales=monthly_sales,
        close_rate=close_rate["current"],
        store_count=total_stores,
        per_store_sales=per_store,
    )

    result = {
        "districtName": meta["name"],
        "districtType": meta["type"],
        "summary": summary_text,
        "floatingPopulation": {
            "dailyAvg": daily_avg,
            "peakHour": fp_result.get("peak_hour", 0) if fp_ok else 0,
            "byHour": by_hour,
        },
        "topCategories": top_categories,
        "status": status,
        "closeRate": close_rate,
        "insights": insights,
        "dataQuarter": data_quarter,
        "dataSources": get_sources_for_tool("get_district_summary"),
    }

    if benchmarks:
        result["benchmarks"] = benchmarks

    await cache.set(cache_key, result, ttl=86400)
    return result
