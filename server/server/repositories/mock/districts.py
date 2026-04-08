"""Mock district repository."""

from __future__ import annotations

from server.agent.tools.mock_data import (
    DISTRICTS,
    get_mock_district_list,
    get_mock_geojson,
)


class MockDistrictRepository:
    async def get_district_meta(self, district_code: str) -> dict | None:
        d = DISTRICTS.get(district_code)
        if d is None:
            return None
        return {"name": d["name"], "type": d["type"]}

    async def resolve_district(self, district_code: str) -> dict | None:
        d = DISTRICTS.get(district_code)
        if d is None:
            return None
        return {
            "name": d["name"],
            "type": d.get("type", "발달상권"),
            "quarter": d["quarter"],
            "center": d.get("center"),
        }

    async def detect_district_by_name(self, message: str) -> dict | None:
        for code, d in DISTRICTS.items():
            if d["name"] in message:
                return {"code": code, "name": d["name"]}
        return None

    async def detect_districts_in_message(self, message: str) -> list[dict]:
        """Find all districts whose names appear in the message (deduped, max 5)."""
        found: list[dict] = []
        seen: set[str] = set()
        for code, d in DISTRICTS.items():
            if d["name"] in message and code not in seen:
                found.append({"code": code, "name": d["name"]})
                seen.add(code)
                if len(found) >= 5:
                    break
        return found

    async def list_districts(
        self, search: str | None, district_type: str | None, limit: int, offset: int
    ) -> tuple[int, list[dict]]:
        all_items = get_mock_district_list(search, district_type)
        total = len(all_items)
        items = all_items[offset : offset + limit]
        return total, items

    async def get_district_detail(self, code: str) -> dict | None:
        d = DISTRICTS.get(code)
        if d is None:
            return None
        return {
            "district_code": d["code"],
            "district_name": d["name"],
            "district_type": d["type"],
            "data_quarter": d["quarter"],
            "center_lng": d["center"]["lng"],
            "center_lat": d["center"]["lat"],
            "polygon": {"type": "Polygon", "coordinates": [d["polygon"]]},
        }

    async def get_polygons_geojson(self, bounds: str | None) -> dict:
        return get_mock_geojson()
