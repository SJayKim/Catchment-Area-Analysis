"""Naver Maps API 클라이언트."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger("mcp.naver_maps.api")

_GEOCODE_URL = "https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode"
_REVERSE_GEOCODE_URL = "https://naveropenapi.apigw.ntruss.com/map-reversegeocode/v2/gc"
_LOCAL_SEARCH_URL = "https://openapi.naver.com/v1/search/local.json"
_DIRECTIONS_URL = "https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving"
_STATIC_MAP_URL = "https://naveropenapi.apigw.ntruss.com/map-static/v2/raster"


class NaverMapsClient:
    """네이버 지도/검색 API 래퍼."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> None:
        self.client_id = client_id or os.environ.get("DATA_API_NAVER_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("DATA_API_NAVER_CLIENT_SECRET", "")
        self._client: Optional[httpx.AsyncClient] = None

    def _ncp_headers(self) -> dict[str, str]:
        """Naver Cloud Platform API 헤더."""
        return {
            "X-NCP-APIGW-API-KEY-ID": self.client_id,
            "X-NCP-APIGW-API-KEY": self.client_secret,
        }

    def _search_headers(self) -> dict[str, str]:
        """Naver Search API 헤더."""
        return {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        return self._client

    async def geocode(self, query: str) -> dict[str, Any]:
        """주소 → 좌표 변환."""
        client = await self._get_client()
        resp = await client.get(
            _GEOCODE_URL,
            params={"query": query},
            headers=self._ncp_headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def reverse_geocode(self, lat: float, lng: float) -> dict[str, Any]:
        """좌표 → 주소 변환."""
        client = await self._get_client()
        resp = await client.get(
            _REVERSE_GEOCODE_URL,
            params={
                "coords": f"{lng},{lat}",
                "output": "json",
                "orders": "roadaddr,addr",
            },
            headers=self._ncp_headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def local_search(self, query: str, display: int = 5) -> dict[str, Any]:
        """장소 검색 (Naver Search API)."""
        client = await self._get_client()
        resp = await client.get(
            _LOCAL_SEARCH_URL,
            params={"query": query, "display": str(display)},
            headers=self._search_headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def directions(
        self, start_lng: float, start_lat: float,
        goal_lng: float, goal_lat: float,
    ) -> dict[str, Any]:
        """경로 탐색 (Directions API)."""
        client = await self._get_client()
        resp = await client.get(
            _DIRECTIONS_URL,
            params={
                "start": f"{start_lng},{start_lat}",
                "goal": f"{goal_lng},{goal_lat}",
            },
            headers=self._ncp_headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def static_map_url(
        self, lat: float, lng: float,
        width: int = 600, height: int = 400, level: int = 16,
    ) -> str:
        """정적 지도 이미지 URL 생성."""
        return (
            f"{_STATIC_MAP_URL}?"
            f"center={lng},{lat}&level={level}"
            f"&w={width}&h={height}"
            f"&markers=type:d|size:mid|pos:{lng} {lat}"
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
