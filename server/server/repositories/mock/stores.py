"""Mock store repository."""

from __future__ import annotations

from server.agent.tools.mock_data import STORE_HISTORY, STORE_INFO


class MockStoreRepository:
    async def get_store_info(self, district_code: str, category_code: str | None = None) -> dict:
        result = STORE_INFO.get(district_code)
        if result is None:
            return {"error": "해당 상권의 점포 데이터가 없습니다.", "district_code": district_code}
        return result

    async def get_store_history(self, district_code: str) -> dict:
        result = STORE_HISTORY.get(district_code)
        if result is None:
            return {"error": "해당 상권의 이력 데이터가 없습니다.", "district_code": district_code}
        return result
