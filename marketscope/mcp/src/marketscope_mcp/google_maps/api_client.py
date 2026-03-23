"""Google Maps API 클라이언트."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger("mcp.google_maps.api")

_BASE_URL = "https://maps.googleapis.com/maps/api"


class GoogleMapsClient:
    """Google Maps Platform API 래퍼."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("DATA_API_GOOGLE_MAPS_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        return self._client

    async def geocode(self, address: str) -> dict[str, Any]:
        """주소 → 좌표 변환 (Geocoding API)."""
        client = await self._get_client()
        resp = await client.get(
            f"{_BASE_URL}/geocode/json",
            params={"address": address, "key": self.api_key, "language": "ko"},
        )
        resp.raise_for_status()
        return resp.json()

    async def reverse_geocode(self, lat: float, lng: float) -> dict[str, Any]:
        """좌표 → 주소 변환."""
        client = await self._get_client()
        resp = await client.get(
            f"{_BASE_URL}/geocode/json",
            params={"latlng": f"{lat},{lng}", "key": self.api_key, "language": "ko"},
        )
        resp.raise_for_status()
        return resp.json()

    async def nearby_search(
        self, lat: float, lng: float, radius: int = 500,
        keyword: str = "", type_: str = "",
    ) -> dict[str, Any]:
        """주변 장소 검색 (Places API)."""
        client = await self._get_client()
        params: dict[str, Any] = {
            "location": f"{lat},{lng}",
            "radius": str(radius),
            "key": self.api_key,
            "language": "ko",
        }
        if keyword:
            params["keyword"] = keyword
        if type_:
            params["type"] = type_

        resp = await client.get(
            f"{_BASE_URL}/place/nearbysearch/json", params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def place_details(self, place_id: str) -> dict[str, Any]:
        """장소 상세 정보 (리뷰, 영업시간)."""
        client = await self._get_client()
        resp = await client.get(
            f"{_BASE_URL}/place/details/json",
            params={
                "place_id": place_id,
                "key": self.api_key,
                "language": "ko",
                "fields": "name,formatted_address,geometry,rating,user_ratings_total,opening_hours,reviews,types",
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def directions(
        self, origin_lat: float, origin_lng: float,
        dest_lat: float, dest_lng: float, mode: str = "transit",
    ) -> dict[str, Any]:
        """경로 탐색."""
        client = await self._get_client()
        resp = await client.get(
            f"{_BASE_URL}/directions/json",
            params={
                "origin": f"{origin_lat},{origin_lng}",
                "destination": f"{dest_lat},{dest_lng}",
                "mode": mode,
                "key": self.api_key,
                "language": "ko",
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
