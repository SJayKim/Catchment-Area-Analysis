"""Benchmarking utilities — percentile ranking within district types."""

from __future__ import annotations

import logging

from server.repositories import get_data_access
from server.services.cache import get_cache_service

logger = logging.getLogger(__name__)


def get_percentile_rank(value: float, stats: dict) -> str:
    """Return human-readable percentile rank based on p25/p50/p75."""
    if value >= stats["p75"]:
        return "상위 25%"
    if value >= stats["p50"]:
        return "상위 50%"
    if value >= stats["p25"]:
        return "상위 75%"
    return "하위 25%"


def get_percentile_rank_inverted(value: float, stats: dict) -> str:
    """Inverted ranking for metrics where lower is better (e.g. close_rate)."""
    if value <= stats["p25"]:
        return "상위 25% (우수)"
    if value <= stats["p50"]:
        return "상위 50%"
    if value <= stats["p75"]:
        return "상위 75%"
    return "하위 25% (주의)"


async def get_district_benchmarks(
    district_type: str,
    *,
    floating_pop: int = 0,
    monthly_sales: int = 0,
    close_rate: float = 0.0,
    store_count: int = 0,
    per_store_sales: int = 0,
) -> dict | None:
    """Build a benchmarks block with rankings for a specific district."""
    try:
        da = get_data_access()
        if da.benchmarks is None:
            return None

        cache = get_cache_service()
        cache_key = f"bench_stats:{district_type}"
        bench = await cache.get(cache_key)
        if bench is None:
            bench = await da.benchmarks.get_benchmarks(district_type)
            if bench:
                await cache.set(cache_key, bench, ttl=86400)

        if not bench or "metrics" not in bench:
            return None

        metrics = bench["metrics"]
        rankings: dict[str, str] = {}

        if floating_pop > 0 and "floating_pop" in metrics:
            rankings["floatingPop"] = get_percentile_rank(floating_pop, metrics["floating_pop"])
        if monthly_sales > 0 and "monthly_sales" in metrics:
            rankings["monthlySales"] = get_percentile_rank(monthly_sales, metrics["monthly_sales"])
        if close_rate > 0 and "close_rate" in metrics:
            rankings["closeRate"] = get_percentile_rank_inverted(close_rate, metrics["close_rate"])
        if store_count > 0 and "store_count" in metrics:
            rankings["storeCount"] = get_percentile_rank(store_count, metrics["store_count"])
        if per_store_sales > 0 and "per_store_sales" in metrics:
            rankings["perStoreSales"] = get_percentile_rank(per_store_sales, metrics["per_store_sales"])

        # Seoul-wide averages (from benchmark means)
        seoul_avg = {k: v["mean"] for k, v in metrics.items()}

        return {
            "districtType": district_type,
            "sampleCount": bench.get("sample_count", 0),
            "rankings": rankings,
            "seoulAvg": seoul_avg,
        }

    except Exception:
        logger.debug("Benchmark lookup failed, skipping", exc_info=True)
        return None
