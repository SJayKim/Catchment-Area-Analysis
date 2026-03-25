"""Seoul Open Data API collector.

API: http://openapi.seoul.go.kr:8088/{KEY}/json/{SERVICE}/{START}/{END}
Pagination: 1,000 rows per page, list_total_count in first response.
"""

from __future__ import annotations

import asyncio
import logging
import math

from server.config import settings
from server.data.etl.base import BaseCollector, CollectorError

logger = logging.getLogger(__name__)

BASE_URL = "http://openapi.seoul.go.kr:8088"

# Service name → API endpoint name
SERVICES = {
    "district_polygon": "VwsmTrdarSelngW",
    "floating_pop": "VwsmTrdarFlpopQq",
    "worker_pop": "VwsmTrdarWrcPopltnQq",
    "resident_pop": "VwsmTrdarPopltnQq",
    "district_change": "VwsmTrdarStorQq",
    "estimated_sales": "VwsmTrdarSelngQq",
    "store_info": "VwsmTrdarStorW",
}


class SeoulOpenDataCollector(BaseCollector):
    """Collector for Seoul Open Data (data.seoul.go.kr) APIs."""

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key or settings.seoul_opendata_api_key)

    def _build_url(self, service: str, start: int, end: int) -> str:
        return f"{BASE_URL}/{self.api_key}/json/{service}/{start}/{end}"

    async def _fetch_service(self, service_key: str, service_name: str) -> list[dict]:
        """Fetch all pages for a given service endpoint."""
        page_size = settings.etl_page_size

        # First page to get total count
        url = self._build_url(service_name, 1, page_size)
        data = await self._fetch_page(url)

        # Seoul API wraps response under the service name key
        wrapper = data.get(service_name)
        if wrapper is None:
            raise CollectorError(f"Unexpected response format for {service_name}: {list(data.keys())}")

        result_code = wrapper.get("RESULT", {}).get("CODE", "")
        if result_code not in ("INFO-000", "INFO-200"):
            msg = wrapper.get("RESULT", {}).get("MESSAGE", "Unknown error")
            raise CollectorError(f"[{service_key}] API error {result_code}: {msg}")

        total_count = wrapper.get("list_total_count", 0)
        rows = wrapper.get("row", [])
        logger.info(f"[{service_key}] total_count={total_count}, first page={len(rows)} rows")

        if total_count <= page_size:
            return rows

        # Fetch remaining pages concurrently
        total_pages = math.ceil(total_count / page_size)
        tasks = []
        for page in range(2, total_pages + 1):
            start = (page - 1) * page_size + 1
            end = page * page_size
            url = self._build_url(service_name, start, end)
            tasks.append(self._fetch_page(url))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[{service_key}] Page {i + 2} failed: {result}")
                continue
            page_wrapper = result.get(service_name, {})
            page_rows = page_wrapper.get("row", [])
            rows.extend(page_rows)

        self.log_progress(service_key, len(rows), total_count)
        return rows

    async def collect_districts(self) -> list[dict]:
        return await self._fetch_service("district_polygon", SERVICES["district_polygon"])

    async def collect_floating_pop(self, quarter: str) -> list[dict]:
        """Collect floating population data. Quarter format: '20253' (year + quarter num)."""
        rows = await self._fetch_service("floating_pop", SERVICES["floating_pop"])
        # Filter by quarter if API returns all quarters
        year = quarter[:4]
        q = quarter[-1]
        return [r for r in rows if str(r.get("STDR_YR_CD")) == year and str(r.get("STDR_QU_CD")) == q]

    async def collect_estimated_sales(self, quarter: str) -> list[dict]:
        rows = await self._fetch_service("estimated_sales", SERVICES["estimated_sales"])
        year = quarter[:4]
        q = quarter[-1]
        return [r for r in rows if str(r.get("STDR_YR_CD")) == year and str(r.get("STDR_QU_CD")) == q]

    async def collect_stores(self, quarter: str) -> list[dict]:
        rows = await self._fetch_service("store_info", SERVICES["store_info"])
        year = quarter[:4]
        q = quarter[-1]
        return [r for r in rows if str(r.get("STDR_YR_CD")) == year and str(r.get("STDR_QU_CD")) == q]

    async def collect_resident_pop(self, quarter: str) -> list[dict]:
        rows = await self._fetch_service("resident_pop", SERVICES["resident_pop"])
        year = quarter[:4]
        q = quarter[-1]
        return [r for r in rows if str(r.get("STDR_YR_CD")) == year and str(r.get("STDR_QU_CD")) == q]

    async def collect_worker_pop(self, quarter: str) -> list[dict]:
        rows = await self._fetch_service("worker_pop", SERVICES["worker_pop"])
        year = quarter[:4]
        q = quarter[-1]
        return [r for r in rows if str(r.get("STDR_YR_CD")) == year and str(r.get("STDR_QU_CD")) == q]

    async def collect(self, quarter: str) -> list[dict]:
        """Not used directly — use specific collect_* methods instead."""
        raise NotImplementedError("Use specific collect_* methods")
