"""Mock simulation repository."""

from __future__ import annotations

# Default unit prices by major category keyword
_DEFAULT_PRICES: dict[str, int] = {
    "카페": 5500,
    "커피": 5500,
    "한식": 9000,
    "중식": 12000,
    "일식": 15000,
    "양식": 14000,
    "분식": 6000,
    "치킨": 18000,
    "편의점": 8000,
    "미용": 25000,
    "약국": 12000,
    "주점": 20000,
    "제과": 4500,
}


class MockSimulationRepository:
    async def get_sales_percentiles(self, category_code: str, quarter: str | None = None) -> dict:
        return {
            "category_code": category_code,
            "quarter": quarter or "2025Q3",
            "p25_ratio": 0.65,
            "p50_ratio": 1.0,
            "p75_ratio": 1.45,
            "seoul_avg_per_store": 3_200_000,
            "sample_count": 850,
        }

    async def get_default_unit_price(self, category_code: str) -> int | None:
        # Simple mapping for mock
        code_to_name = {
            "CS100001": "카페",
            "CS200001": "한식",
            "CS200002": "중식",
            "CS200003": "일식",
            "CS200004": "양식",
            "CS200006": "분식",
            "CS200009": "주점",
            "CS200010": "치킨",
            "CS200014": "제과",
            "CS300001": "편의점",
            "CS400001": "미용",
            "CS500001": "약국",
        }
        name = code_to_name.get(category_code, "")
        return _DEFAULT_PRICES.get(name, 10000)
