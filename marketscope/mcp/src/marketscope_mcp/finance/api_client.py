"""Finance MCP 외부 API 클라이언트."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger("mcp.finance.api")

_BIZINFO_BASE = "https://www.bizinfo.go.kr/uss/rss/bizInfoRssList.json"
_KSTARTUP_BASE = "http://apis.data.go.kr/B552735/kisedKstartup/getKStartup"
_FRANCHISE_BASE = "https://franchise.ftc.go.kr"

# 지역코드 매핑 (기업마당)
_AREA_CODES = {
    "서울": "11", "부산": "21", "대구": "22", "인천": "23",
    "광주": "24", "대전": "25", "울산": "26", "세종": "29",
    "경기": "31", "강원": "32", "충북": "33", "충남": "34",
    "전북": "35", "전남": "36", "경북": "37", "경남": "38", "제주": "39",
}


class FinanceAPIClient:
    """기업마당 / K-Startup / 프랜차이즈 API 래퍼."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("DATA_API_PUBLIC_DATA_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        return self._client

    async def search_bizinfo(
        self,
        search_text: str,
        area_code: str = "",
        busi_type: str = "all",
        page: int = 1,
        rows: int = 10,
    ) -> dict[str, Any]:
        """기업마당 지원사업 검색."""
        client = await self._get_client()
        params = {
            "dataType": "json",
            "searchTxt": search_text,
            "busiType": busi_type,
            "pageNo": str(page),
            "numOfRows": str(rows),
        }
        if area_code:
            params["areaCd"] = area_code

        try:
            resp = await client.get(_BIZINFO_BASE, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.exception("기업마당 API 호출 실패")
            return {"error": str(e), "items": []}

    async def search_kstartup(
        self,
        keyword: str,
        page: int = 1,
        rows: int = 10,
    ) -> dict[str, Any]:
        """K-Startup 지원사업 검색."""
        client = await self._get_client()
        params = {
            "serviceKey": self.api_key,
            "pageNo": str(page),
            "numOfRows": str(rows),
            "cond[pblancNm::LIKE]": keyword,
        }
        try:
            resp = await client.get(_KSTARTUP_BASE, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.exception("K-Startup API 호출 실패")
            return {"error": str(e), "items": []}

    async def search_franchise(self, brand_name: str) -> dict[str, Any]:
        """프랜차이즈 정보공개서 검색 (공정위)."""
        client = await self._get_client()
        params = {
            "searchBrandNm": brand_name,
        }
        try:
            resp = await client.get(
                f"{_FRANCHISE_BASE}/mnu/00013/program/userRqst/list.do",
                params=params,
            )
            resp.raise_for_status()
            # HTML 파싱이 필요한 경우 text 반환
            return {"raw_html": resp.text[:5000], "status": "ok"}
        except Exception as e:
            logger.exception("프랜차이즈 API 호출 실패")
            return {"error": str(e)}

    @staticmethod
    def get_area_code(region: str) -> str:
        """지역명 → 기업마당 지역코드 변환."""
        for key, code in _AREA_CODES.items():
            if key in region:
                return code
        return ""

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
