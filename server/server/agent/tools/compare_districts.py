import logging

from server.agent.tools.registry import register_tool
from server.repositories import get_data_access
from server.services.cache import get_cache_service

logger = logging.getLogger(__name__)


def _enrich_comparison(result: dict) -> dict:
    """Add winners and efficiency metrics to comparison result."""
    districts = result.get("districts", {})
    items = [d for d in districts.values() if "error" not in d]
    if len(items) < 2:
        return result

    # Per-store efficiency for each district
    for d in items:
        ms = d.get("monthly_sales", 0)
        sc = d.get("store_count", 0)
        fp = d.get("floating_pop", 0)
        if sc > 0:
            d["sales_per_store"] = round(ms / sc)
            d["pop_per_store"] = round(fp / sc)

    # Winners by metric
    winners: dict = {}
    for metric, label, lower_is_better in [
        ("floating_pop", "highest_pop", False),
        ("monthly_sales", "highest_sales", False),
        ("close_rate", "lowest_close_rate", True),
        ("sales_per_store", "best_efficiency", False),
    ]:
        valid = [d for d in items if metric in d]
        if valid:
            best = min(valid, key=lambda d: d[metric]) if lower_is_better else max(valid, key=lambda d: d[metric])
            winners[label] = best.get("district_name", best.get("district_code"))

    result["winners"] = winners
    return result


@register_tool(
    "compare_districts",
    card_type="compare",
    progress_label="상권 비교 분석 중...",
    done_label="상권 비교 완료",
)
async def compare_districts(district_codes: list[str]) -> dict:
    """Compare key metrics across 2-3 districts."""
    if len(district_codes) < 2 or len(district_codes) > 3:
        return {"error": "비교는 2~3개 상권만 가능합니다."}

    try:
        cache = get_cache_service()
        cache_key = f"compare:{'_'.join(sorted(district_codes))}"
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

        da = get_data_access()
        result = await da.comparison.compare_districts(district_codes)

        if "error" not in result:
            result = _enrich_comparison(result)
            await cache.set(cache_key, result, ttl=86400)
        return result
    except Exception as exc:
        logger.exception("compare_districts tool failed")
        return {"error": f"상권 비교 도구 오류: {type(exc).__name__}"}
