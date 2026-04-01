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
    "district_center": "TbgisTrdarRelm",
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

    async def collect_district_centers(self) -> list[dict]:
        """Collect district center points from TbgisTrdarRelm API (EPSG:5181)."""
        return await self._fetch_service("district_center", SERVICES["district_center"])

    async def collect_districts(self) -> list[dict]:
        """Collect district info with 3-tier fallback chain.

        Tier 1: VwsmTrdarSelngW (polygon API) — ERROR-500 since 2026
        Tier 2: TbgisTrdarRelm (center points, EPSG:5181) — verified working
        Tier 3: Extract from floating pop API (no geometry)
        """
        # Tier 1: polygon API
        try:
            return await self._fetch_service("district_polygon", SERVICES["district_polygon"])
        except CollectorError as e:
            if "ERROR-500" not in str(e) and "Unexpected" not in str(e):
                raise
            logger.warning("district_polygon API unavailable (Tier 1 failed)")

        # Tier 2: center point API
        try:
            rows = await self.collect_district_centers()
            logger.info(f"[districts] Tier 2 (TbgisTrdarRelm): {len(rows)} rows")
            return rows
        except CollectorError as e:
            logger.warning(f"district_center API also failed (Tier 2): {e}")

        # Tier 3: extract from floating pop
        logger.warning("Falling back to floating pop extraction (Tier 3, no geometry)")
        return await self._extract_districts_from_store_change()

    async def _extract_districts_from_store_change(self) -> list[dict]:
        """Extract unique district info from VwsmTrdarFlpopQq (floating pop API — much smaller)."""
        rows = await self._fetch_service("floating_pop", SERVICES["floating_pop"])
        seen: dict[str, dict] = {}
        for r in rows:
            code = str(r.get("TRDAR_CD", ""))
            if code and code not in seen:
                seen[code] = r
        logger.info(f"[districts] extracted {len(seen)} unique districts from floating pop data")
        return list(seen.values())

    @staticmethod
    def _filter_by_quarter(rows: list[dict], quarter: str) -> list[dict]:
        """Filter rows by quarter. Handles both STDR_YR_CD/STDR_QU_CD and STDR_YYQU_CD formats."""
        year = quarter[:4]
        q = quarter[-1]
        yyqu = f"{year}{q}"
        result = []
        for r in rows:
            yr = str(r.get("STDR_YR_CD", ""))
            qu = str(r.get("STDR_QU_CD", ""))
            yyqu_val = str(r.get("STDR_YYQU_CD", ""))
            if (yr == year and qu == q) or yyqu_val == yyqu:
                # Normalize: ensure STDR_YR_CD and STDR_QU_CD are set
                if not yr:
                    r["STDR_YR_CD"] = year
                if not qu:
                    r["STDR_QU_CD"] = q
                result.append(r)
        return result

    async def collect_floating_pop(self, quarter: str) -> list[dict]:
        """Collect floating population data. Quarter format: '20253' (year + quarter num)."""
        rows = await self._fetch_service("floating_pop", SERVICES["floating_pop"])
        return self._filter_by_quarter(rows, quarter)

    async def collect_estimated_sales(self, quarter: str) -> list[dict]:
        rows = await self._fetch_service("estimated_sales", SERVICES["estimated_sales"])
        return self._filter_by_quarter(rows, quarter)

    async def collect_stores(self, quarter: str) -> list[dict]:
        """Collect store info. Tries VwsmTrdarStorW first, falls back to VwsmTrdarStorQq."""
        try:
            rows = await self._fetch_service("store_info", SERVICES["store_info"])
        except CollectorError:
            logger.warning("store_info API unavailable, using store change API instead")
            rows = await self._fetch_store_change_data(quarter)
            return rows
        year = quarter[:4]
        q = quarter[-1]
        return [r for r in rows if str(r.get("STDR_YR_CD")) == year and str(r.get("STDR_QU_CD")) == q]

    async def _fetch_store_change_data(self, quarter: str) -> list[dict]:
        """Fetch store data from VwsmTrdarStorQq (store change API)."""
        rows = await self._fetch_service("district_change", SERVICES["district_change"])
        year = quarter[:4]
        q = quarter[-1]
        filtered = []
        for r in rows:
            yyqu = str(r.get("STDR_YYQU_CD", ""))
            if len(yyqu) >= 5 and yyqu[:4] == year and yyqu[4:] == q:
                # Map field names to match expected format
                r["STDR_YR_CD"] = year
                r["STDR_QU_CD"] = q
                r["SVC_INDUTY_CD"] = r.get("SVC_INDUTY_CD", "")
                r["SVC_INDUTY_CD_NM"] = r.get("SVC_INDUTY_CD_NM", "")
                filtered.append(r)
        return filtered

    async def collect_resident_pop(self, quarter: str) -> list[dict]:
        try:
            rows = await self._fetch_service("resident_pop", SERVICES["resident_pop"])
        except CollectorError:
            logger.warning("resident_pop API unavailable, skipping")
            return []
        return self._filter_by_quarter(rows, quarter)

    async def collect_worker_pop(self, quarter: str) -> list[dict]:
        rows = await self._fetch_service("worker_pop", SERVICES["worker_pop"])
        return self._filter_by_quarter(rows, quarter)

    async def collect(self, quarter: str) -> list[dict]:
        """Not used directly — use specific collect_* methods instead."""
        raise NotImplementedError("Use specific collect_* methods")
