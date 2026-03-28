"""get_district_summary tool — aggregates mock data into SummaryCardData format."""

from __future__ import annotations

from server.agent.tools.mock_data import (
    DISTRICTS,
    ESTIMATED_SALES,
    FLOATING_POPULATION,
    STORE_INFO,
)


def _format_population(pop: int) -> str:
    """Format population number into Korean readable string (e.g. 12만 4천명)."""
    man = pop // 10_000
    cheon = (pop % 10_000) // 1_000
    if man and cheon:
        return f"{man}만 {cheon}천명"
    if man:
        return f"{man}만명"
    return f"{pop:,}명"


def _format_sales(sales: int) -> str:
    """Format sales into Korean readable string (e.g. 85억원)."""
    eok = sales // 100_000_000
    cheon_man = (sales % 100_000_000) // 10_000_000
    if eok and cheon_man:
        return f"{eok}억 {cheon_man}천만원"
    if eok:
        return f"{eok}억원"
    return f"{sales:,}원"


async def get_district_summary(district_code: str) -> dict:
    """Aggregate mock data for a district into SummaryCardData shape.

    Returns camelCase keys matching the frontend SummaryCardData interface.
    """
    district = DISTRICTS.get(district_code)
    fp = FLOATING_POPULATION.get(district_code)
    sales = ESTIMATED_SALES.get(district_code)
    store = STORE_INFO.get(district_code)

    if not district:
        return {"error": f"상권 코드 '{district_code}'에 해당하는 데이터가 없습니다."}

    # Build byHour array: rename time_slot→hour, population→pop
    by_hour = []
    if fp:
        for entry in fp.get("by_hour", []):
            by_hour.append({"hour": entry["time_slot"], "pop": entry["population"]})

    # Top categories: rename category_name→name, store_count→count
    top_categories = []
    if store:
        for cat in store.get("top_categories", []):
            top_categories.append({"name": cat["category_name"], "count": cat["store_count"]})

    # Determine status from sales trend
    status = "stable"
    if sales:
        status = sales.get("trend", "stable")

    # Close rate
    close_rate = {"current": 0.0, "average": 6.5}
    if store:
        close_rate["current"] = store.get("close_rate", 0.0)

    # Build summary text
    daily_avg = fp["daily_avg"] if fp else 0
    monthly_sales = sales["total_monthly_sales"] if sales else 0
    status_label = {"growing": "성장 중인", "stable": "안정적인", "declining": "위축 중인"}.get(
        status, "안정적인"
    )
    summary_text = (
        f"하루 평균 유동인구 {_format_population(daily_avg)}, "
        f"월 추정 매출 {_format_sales(monthly_sales)}의 "
        f"{status_label} {district['type']}입니다."
    )

    quarter = fp["quarter"] if fp else sales["quarter"] if sales else "2025Q3"

    return {
        "districtName": district["name"],
        "districtType": district["type"],
        "summary": summary_text,
        "floatingPopulation": {
            "dailyAvg": daily_avg,
            "peakHour": fp["peak_hour"] if fp else 0,
            "byHour": by_hour,
        },
        "topCategories": top_categories,
        "status": status,
        "closeRate": close_rate,
        "dataQuarter": f"{quarter} (샘플)",
    }
