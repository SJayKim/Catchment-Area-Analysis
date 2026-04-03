"""Mock comparison repository."""

from __future__ import annotations

from server.agent.tools.mock_data import get_compare_data


class MockComparisonRepository:
    async def compare_districts(self, district_codes: list[str]) -> dict:
        if len(district_codes) < 2 or len(district_codes) > 3:
            return {"error": "비교는 2~3개 상권만 가능합니다."}
        return get_compare_data(district_codes)
