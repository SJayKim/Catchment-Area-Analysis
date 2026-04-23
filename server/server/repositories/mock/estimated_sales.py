"""Mock estimated sales repository."""

from __future__ import annotations

from server.agent.tools.mock_data import ESTIMATED_SALES


class MockEstimatedSalesRepository:
    async def get_estimated_sales(self, district_code: str, category_code: str | None = None) -> dict:
        result = ESTIMATED_SALES.get(district_code)
        if result is None:
            return {"error": "해당 상권의 매출 데이터가 없습니다.", "district_code": district_code}
        return result
