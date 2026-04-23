"""Mock benchmark repository — hardcoded percentile stats by district type."""

from __future__ import annotations

# Seoul district-type benchmarks (based on realistic aggregated data).
# Keys: floating_pop (daily avg), monthly_sales (won), close_rate (%),
#        store_count, per_store_sales (won/month)
_BENCHMARKS: dict[str, dict] = {
    "발달상권": {
        "district_type": "발달상권",
        "sample_count": 120,
        "metrics": {
            "floating_pop": {"p25": 52000, "p50": 78000, "p75": 115000, "mean": 92000},
            "monthly_sales": {
                "p25": 25_000_000_000,
                "p50": 48_000_000_000,
                "p75": 75_000_000_000,
                "mean": 55_000_000_000,
            },
            "close_rate": {"p25": 4.0, "p50": 5.8, "p75": 7.5, "mean": 5.9},
            "store_count": {"p25": 450, "p50": 850, "p75": 1500, "mean": 950},
            "per_store_sales": {"p25": 28_000_000, "p50": 42_000_000, "p75": 62_000_000, "mean": 46_000_000},
        },
    },
    "골목상권": {
        "district_type": "골목상권",
        "sample_count": 980,
        "metrics": {
            "floating_pop": {"p25": 8000, "p50": 18000, "p75": 35000, "mean": 22000},
            "monthly_sales": {
                "p25": 3_000_000_000,
                "p50": 8_000_000_000,
                "p75": 18_000_000_000,
                "mean": 10_000_000_000,
            },
            "close_rate": {"p25": 5.5, "p50": 7.2, "p75": 9.8, "mean": 7.5},
            "store_count": {"p25": 80, "p50": 180, "p75": 350, "mean": 210},
            "per_store_sales": {"p25": 20_000_000, "p50": 32_000_000, "p75": 48_000_000, "mean": 35_000_000},
        },
    },
    "전통시장": {
        "district_type": "전통시장",
        "sample_count": 320,
        "metrics": {
            "floating_pop": {"p25": 5000, "p50": 12000, "p75": 25000, "mean": 15000},
            "monthly_sales": {"p25": 2_000_000_000, "p50": 5_500_000_000, "p75": 12_000_000_000, "mean": 7_000_000_000},
            "close_rate": {"p25": 3.0, "p50": 4.5, "p75": 6.5, "mean": 4.8},
            "store_count": {"p25": 50, "p50": 120, "p75": 250, "mean": 140},
            "per_store_sales": {"p25": 18_000_000, "p50": 30_000_000, "p75": 45_000_000, "mean": 32_000_000},
        },
    },
}

# Fallback for unknown types
_DEFAULT = _BENCHMARKS["발달상권"]


def _get_percentile_rank(value: float, stats: dict) -> str:
    """Return human-readable percentile rank."""
    if value >= stats["p75"]:
        return "상위 25%"
    if value >= stats["p50"]:
        return "상위 50%"
    if value >= stats["p25"]:
        return "상위 75%"
    return "하위 25%"


class MockBenchmarkRepository:
    async def get_benchmarks(self, district_type: str) -> dict:
        return _BENCHMARKS.get(district_type, _DEFAULT)
