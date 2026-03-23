"""KOSIS (통계청) API Collector.

수집 대상:
- DT_1B040A3: 주민등록인구 (행정구역별/성별)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from marketscope_pipeline.collectors.base import BaseCollector, CollectionError
from marketscope_common.db.models import PopulationStat

logger = logging.getLogger(__name__)


class KosisCollector(BaseCollector):
    """KOSIS 통계청 API 수집기.

    Base URL: https://kosis.kr/openapi/Param/statisticsParameterData.do
    인증: apiKey 쿼리 파라미터
    """

    COLLECTOR_NAME = "kosis"
    BASE_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"

    def __init__(self, session: AsyncSession, api_key: str) -> None:
        super().__init__(session, api_key)
        if not api_key:
            raise ValueError("KOSIS API 키가 필요합니다")

    async def collect_resident_population(
        self,
        region_code: str,
        year: int,
        district_id: int,
    ) -> dict[str, Any]:
        """주민등록인구 수집 (DT_1B040A3).

        Args:
            region_code: 행정구역코드 (예: "1168000000" = 강남구)
            year: 기준년도
            district_id: districts 테이블 FK
        """
        t0 = time.monotonic()
        endpoint = "DT_1B040A3"

        params = {
            "method": "getList",
            "apiKey": self.api_key,
            "itmId": "T2+T3+",  # 총인구 + 남 + 여
            "objL1": region_code,
            "objL2": "ALL",
            "format": "json",
            "jsonVD": "Y",
            "prdSe": "Y",  # 연간
            "startPrdDe": str(year),
            "endPrdDe": str(year),
            "orgId": "101",
            "tblId": "DT_1B040A3",
        }

        try:
            data = await self._call_api_with_retry("GET", self.BASE_URL, params=params)

            if not isinstance(data, list) or len(data) == 0:
                await self._log_collection(
                    endpoint, {"region_code": region_code, "year": year},
                    status="partial", records_fetched=0,
                )
                return {"status": "no_data", "count": 0}

            total_pop = None
            male_pop = None
            female_pop = None

            for item in data:
                itm_id = item.get("ITM_ID", "")
                value = _safe_int(item.get("DT"))

                if itm_id == "T2":  # 총인구
                    total_pop = value
                elif itm_id == "T3":  # 남자
                    male_pop = value
                # T3 다음이 여자 (T4 or 패턴)
                elif "여" in item.get("ITM_NM", ""):
                    female_pop = value

            if female_pop is None and total_pop and male_pop:
                female_pop = total_pop - male_pop

            values = dict(
                district_id=district_id,
                stat_type="resident",
                year=year,
                total_population=total_pop,
                male_population=male_pop,
                female_population=female_pop,
                data_source="KOSIS",
                raw_data=data[:5] if len(data) > 5 else data,  # 샘플만 보관
            )
            stmt = pg_insert(PopulationStat).values(**values).on_conflict_do_update(
                constraint="uq_population_period",
                set_={k: v for k, v in values.items() if k not in ("district_id", "stat_type", "year", "quarter", "month", "date")},
            )
            await self.session.execute(stmt)

            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"region_code": region_code, "year": year},
                records_fetched=len(data), records_inserted=1,
                duration_ms=elapsed,
            )
            return {"status": "success", "fetched": len(data), "inserted": 1}

        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"region_code": region_code, "year": year},
                status="failed", error_message=str(e), duration_ms=elapsed,
            )
            raise

    async def collect_worker_population(
        self,
        region_code: str,
        year: int,
        district_id: int,
    ) -> dict[str, Any]:
        """직장인구(종사자수) 수집 — 사업체조사 (DT_1K52B01).

        Args:
            region_code: 행정구역코드 (예: "1168000000" = 강남구)
            year: 기준년도
            district_id: districts 테이블 FK
        """
        t0 = time.monotonic()
        endpoint = "DT_1K52B01"

        params = {
            "method": "getList",
            "apiKey": self.api_key,
            "itmId": "T1+",  # 종사자수
            "objL1": region_code,
            "objL2": "ALL",
            "format": "json",
            "jsonVD": "Y",
            "prdSe": "Y",
            "startPrdDe": str(year),
            "endPrdDe": str(year),
            "orgId": "101",
            "tblId": "DT_1K52B01",
        }

        try:
            data = await self._call_api_with_retry("GET", self.BASE_URL, params=params)

            if not isinstance(data, list) or len(data) == 0:
                await self._log_collection(
                    endpoint, {"region_code": region_code, "year": year},
                    status="partial", records_fetched=0,
                )
                return {"status": "no_data", "count": 0}

            # 종사자수 파싱 — ITM_ID: T1=종사자수
            total_workers = None
            male_workers = None
            female_workers = None

            for item in data:
                itm_id = item.get("ITM_ID", "")
                itm_nm = item.get("ITM_NM", "")
                value = _safe_int(item.get("DT"))

                if itm_id == "T1" or "종사자" in itm_nm:
                    if "남" in itm_nm:
                        male_workers = value
                    elif "여" in itm_nm:
                        female_workers = value
                    elif total_workers is None:
                        total_workers = value

            if female_workers is None and total_workers and male_workers:
                female_workers = total_workers - male_workers

            values = dict(
                district_id=district_id,
                stat_type="worker",
                year=year,
                total_population=total_workers,
                male_population=male_workers,
                female_population=female_workers,
                data_source="KOSIS",
                raw_data=data[:5] if len(data) > 5 else data,
            )
            stmt = pg_insert(PopulationStat).values(**values).on_conflict_do_update(
                constraint="uq_population_period",
                set_={k: v for k, v in values.items() if k not in ("district_id", "stat_type", "year", "quarter", "month", "date")},
            )
            await self.session.execute(stmt)

            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"region_code": region_code, "year": year},
                records_fetched=len(data), records_inserted=1,
                duration_ms=elapsed,
            )
            return {"status": "success", "fetched": len(data), "inserted": 1}

        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"region_code": region_code, "year": year},
                status="failed", error_message=str(e), duration_ms=elapsed,
            )
            raise

    async def collect(self, **kwargs) -> dict[str, Any]:
        collect_type = kwargs.pop("collect_type", "resident_population")
        if collect_type == "resident_population":
            return await self.collect_resident_population(**kwargs)
        elif collect_type == "worker_population":
            return await self.collect_worker_population(**kwargs)
        raise ValueError(f"Unknown collect_type: {collect_type}")


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        v = str(value).replace(",", "").strip()
        return int(float(v)) if v and v != "-" else None
    except (ValueError, TypeError):
        return None
