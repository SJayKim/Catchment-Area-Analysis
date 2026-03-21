"""카카오 로컬 API HTTP 클라이언트."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger("mcp.maps.kakao_client")

_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class KakaoLocalClient:
    """카카오 로컬 API 클라이언트."""

    BASE_URL = "https://dapi.kakao.com"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={"Authorization": f"KakaoAK {self.api_key}"},
                timeout=httpx.Timeout(10.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def _request(
        self, method: str, path: str, params: Optional[dict[str, Any]] = None
    ) -> dict:
        """HTTP 요청을 재시도 로직과 함께 실행한다."""
        client = await self._get_client()
        last_exc: Optional[Exception] = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.info("Kakao API %s %s params=%s (attempt %d)", method, path, params, attempt)
                response = await client.request(method, path, params=params)

                if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                    delay = _BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "Kakao API %s 오류, %.1f초 후 재시도 (%d/%d)",
                        response.status_code, delay, attempt, _MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.TimeoutException as e:
                last_exc = e
                if attempt < _MAX_RETRIES:
                    delay = _BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning("Kakao API 타임아웃, %.1f초 후 재시도 (%d/%d)", delay, attempt, _MAX_RETRIES)
                    await asyncio.sleep(delay)
                    continue

            except httpx.HTTPStatusError as e:
                last_exc = e
                if attempt < _MAX_RETRIES and e.response.status_code in _RETRYABLE_STATUS_CODES:
                    delay = _BACKOFF_BASE * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
                    continue
                break

            except httpx.HTTPError as e:
                last_exc = e
                if attempt < _MAX_RETRIES:
                    delay = _BACKOFF_BASE * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
                    continue
                break

        raise RuntimeError(f"Kakao API 요청 실패 ({_MAX_RETRIES}회 시도): {last_exc}") from last_exc

    # -- Public API -----------------------------------------------------------

    async def search_address(self, query: str) -> dict:
        """주소 검색 (주소 → 좌표)."""
        return await self._request("GET", "/v2/local/search/address.json", params={"query": query})

    async def coord_to_address(self, lng: float, lat: float) -> dict:
        """좌표 → 주소 변환."""
        return await self._request(
            "GET", "/v2/local/geo/coord2address.json", params={"x": lng, "y": lat}
        )

    async def search_keyword(
        self,
        query: str,
        lng: Optional[float] = None,
        lat: Optional[float] = None,
        radius: Optional[int] = None,
    ) -> dict:
        """키워드 검색."""
        params: dict[str, Any] = {"query": query}
        if lng is not None:
            params["x"] = lng
        if lat is not None:
            params["y"] = lat
        if radius is not None:
            params["radius"] = radius
        return await self._request("GET", "/v2/local/search/keyword.json", params=params)

    async def search_category(
        self,
        category_code: str,
        lng: float,
        lat: float,
        radius: int = 500,
    ) -> dict:
        """카테고리 검색 (페이지네이션 포함, 최대 3페이지)."""
        all_documents: list[dict] = []

        for page in range(1, 4):  # max 3 pages
            params: dict[str, Any] = {
                "category_group_code": category_code,
                "x": lng,
                "y": lat,
                "radius": radius,
                "page": page,
                "size": 15,
            }
            result = await self._request("GET", "/v2/local/search/category.json", params=params)
            documents = result.get("documents", [])
            all_documents.extend(documents)

            meta = result.get("meta", {})
            if meta.get("is_end", True):
                break

        return {
            "documents": all_documents,
            "meta": {"total_count": len(all_documents)},
        }

    async def close(self) -> None:
        """HTTP 클라이언트를 정리한다."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
