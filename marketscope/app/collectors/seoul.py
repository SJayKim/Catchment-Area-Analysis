"""서울 열린데이터 API Collector.

수집 대상:
- SPOP_LOCAL_RESD_DONG: 서울 생활인구 (행정동별)
- CardSubwayStatsNew: 지하철 승하차 인원
- tbgiCardInfo: 카드매출 통계
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector, CollectionError
from app.db.models import PopulationStat, RevenueStat, TransitStat

logger = logging.getLogger(__name__)


class SeoulCollector(BaseCollector):
    """서울 열린데이터광장 API 수집기.

    Base URL: http://openapi.seoul.go.kr:8088/{API_KEY}/json/{서비스명}/{시작}/{끝}/...
    인증: URL 경로에 API 키 포함
    """

    COLLECTOR_NAME = "seoul"
    BASE_URL = "http://openapi.seoul.go.kr:8088"
    PAGE_SIZE = 1000

    def __init__(self, session: AsyncSession, api_key: str) -> None:
        super().__init__(session, api_key)
        if not api_key:
            raise ValueError("서울 열린데이터 API 키가 필요합니다")

    def _build_url(self, service: str, start: int, end: int, *path_params: str) -> str:
        parts = [self.BASE_URL, self.api_key, "json", service, str(start), str(end)]
        parts.extend(path_params)
        return "/".join(parts)

    async def _fetch_all_pages(self, service: str, *path_params: str) -> list[dict]:
        """전체 페이지 반복 조회 (1000건씩)."""
        all_rows: list[dict] = []
        start = 1

        while True:
            end = start + self.PAGE_SIZE - 1
            url = self._build_url(service, start, end, *path_params)

            data = await self._call_api_with_retry("GET", url)
            service_data = data.get(service)
            if not service_data:
                break

            total_count = service_data.get("list_total_count", 0)
            rows = service_data.get("row", [])
            if not rows:
                break

            all_rows.extend(rows)

            if start + self.PAGE_SIZE - 1 >= total_count:
                break
            start += self.PAGE_SIZE

        return all_rows

    async def collect_living_population(
        self,
        dong_code: str,
        date_str: str,  # YYYYMMDD
        district_id: int,
    ) -> dict[str, Any]:
        """서울 생활인구 수집 (SPOP_LOCAL_RESD_DONG).

        Args:
            dong_code: 행정동 코드
            date_str: 기준일 (YYYYMMDD)
            district_id: districts 테이블 FK
        """
        t0 = time.monotonic()
        endpoint = "SPOP_LOCAL_RESD_DONG"

        try:
            rows = await self._fetch_all_pages(endpoint, date_str, dong_code)
            if not rows:
                await self._log_collection(
                    endpoint, {"dong_code": dong_code, "date": date_str},
                    status="partial", records_fetched=0,
                )
                return {"status": "no_data", "count": 0}

            inserted = 0
            for row in rows:
                year = int(date_str[:4])
                month = int(date_str[4:6])

                values = dict(
                    district_id=district_id,
                    stat_type="living",
                    year=year,
                    month=month,
                    total_population=_safe_int(row.get("TOT_LVPOP_CO")),
                    male_population=_safe_int(row.get("ML_LVPOP_CO")),
                    female_population=_safe_int(row.get("FML_LVPOP_CO")),
                    age_0_9=_safe_int(row.get("AGRDE_0_LVPOP_CO")),
                    age_10_19=_safe_int(row.get("AGRDE_10_LVPOP_CO")),
                    age_20_29=_safe_int(row.get("AGRDE_20_LVPOP_CO")),
                    age_30_39=_safe_int(row.get("AGRDE_30_LVPOP_CO")),
                    age_40_49=_safe_int(row.get("AGRDE_40_LVPOP_CO")),
                    age_50_59=_safe_int(row.get("AGRDE_50_LVPOP_CO")),
                    age_60_plus=_safe_int(row.get("AGRDE_60_ABOVE_LVPOP_CO")),
                    data_source="SEOUL",
                    raw_data=row,
                )
                stmt = pg_insert(PopulationStat).values(**values).on_conflict_do_update(
                    constraint="uq_population_period",
                    set_={k: v for k, v in values.items() if k not in ("district_id", "stat_type", "year", "quarter", "month", "date")},
                )
                await self.session.execute(stmt)
                inserted += 1

            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"dong_code": dong_code, "date": date_str},
                records_fetched=len(rows), records_inserted=inserted,
                duration_ms=elapsed,
            )
            return {"status": "success", "fetched": len(rows), "inserted": inserted}

        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"dong_code": dong_code, "date": date_str},
                status="failed", error_message=str(e), duration_ms=elapsed,
            )
            raise

    async def collect_subway_stats(
        self,
        year_month: str,  # YYYYMM01 형식
    ) -> dict[str, Any]:
        """지하철 승하차 인원 수집 (CardSubwayStatsNew)."""
        t0 = time.monotonic()
        endpoint = "CardSubwayStatsNew"

        try:
            rows = await self._fetch_all_pages(endpoint, year_month)
            if not rows:
                await self._log_collection(
                    endpoint, {"year_month": year_month},
                    status="partial", records_fetched=0,
                )
                return {"status": "no_data", "count": 0}

            inserted = 0
            year = int(year_month[:4])
            month = int(year_month[4:6])

            for row in rows:
                station = row.get("SUB_STA_NM", "").strip()
                line = row.get("LINE_NUM", "").strip()
                if not station:
                    continue

                values = dict(
                    station_name=station,
                    line_name=line,
                    transit_type="subway",
                    year=year,
                    month=month,
                    boarding_total=_safe_int(row.get("RIDE_PASGR_NUM")),
                    alighting_total=_safe_int(row.get("ALIGHT_PASGR_NUM")),
                    data_source="SEOUL",
                    raw_data=row,
                )
                stmt = pg_insert(TransitStat).values(**values).on_conflict_do_update(
                    constraint="uq_transit_period",
                    set_={k: v for k, v in values.items() if k not in ("station_name", "line_name", "transit_type", "year", "month")},
                )
                await self.session.execute(stmt)
                inserted += 1

            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"year_month": year_month},
                records_fetched=len(rows), records_inserted=inserted,
                duration_ms=elapsed,
            )
            return {"status": "success", "fetched": len(rows), "inserted": inserted}

        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"year_month": year_month},
                status="failed", error_message=str(e), duration_ms=elapsed,
            )
            raise

    async def collect_card_sales(
        self,
        year: str,
        month: str,
        district_id: int,
        dong_code: str,
        industry_code: Optional[str] = None,
    ) -> dict[str, Any]:
        """카드매출 통계 수집 (tbgiCardInfo)."""
        t0 = time.monotonic()
        endpoint = "tbgiCardInfo"

        try:
            rows = await self._fetch_all_pages(endpoint, year, month)
            if not rows:
                await self._log_collection(
                    endpoint, {"year": year, "month": month},
                    status="partial", records_fetched=0,
                )
                return {"status": "no_data", "count": 0}

            inserted = 0
            for row in rows:
                ind_code = row.get("SVC_INDUTY_CD", "")
                if industry_code and ind_code != industry_code:
                    continue

                values = dict(
                    district_id=district_id,
                    industry_code=ind_code,
                    industry_name=row.get("SVC_INDUTY_CD_NM", ""),
                    year=int(year),
                    month=int(month),
                    total_revenue=_safe_decimal(row.get("TOT_SELNG_AMT")),
                    transaction_count=_safe_int(row.get("TOT_SELNG_CO")),
                    male_revenue=_safe_decimal(row.get("ML_SELNG_AMT")),
                    female_revenue=_safe_decimal(row.get("FML_SELNG_AMT")),
                    day_mon_revenue=_safe_decimal(row.get("MON_SELNG_AMT")),
                    day_tue_revenue=_safe_decimal(row.get("TUES_SELNG_AMT")),
                    day_wed_revenue=_safe_decimal(row.get("WED_SELNG_AMT")),
                    day_thu_revenue=_safe_decimal(row.get("THUR_SELNG_AMT")),
                    day_fri_revenue=_safe_decimal(row.get("FRI_SELNG_AMT")),
                    day_sat_revenue=_safe_decimal(row.get("SAT_SELNG_AMT")),
                    day_sun_revenue=_safe_decimal(row.get("SUN_SELNG_AMT")),
                    data_source="SEOUL",
                    raw_data=row,
                )
                stmt = pg_insert(RevenueStat).values(**values).on_conflict_do_update(
                    constraint="uq_revenue_period",
                    set_={k: v for k, v in values.items() if k not in ("district_id", "industry_code", "year", "quarter", "month")},
                )
                await self.session.execute(stmt)
                inserted += 1

            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"year": year, "month": month, "dong_code": dong_code},
                records_fetched=len(rows), records_inserted=inserted,
                duration_ms=elapsed,
            )
            return {"status": "success", "fetched": len(rows), "inserted": inserted}

        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"year": year, "month": month},
                status="failed", error_message=str(e), duration_ms=elapsed,
            )
            raise

    async def collect(self, **kwargs) -> dict[str, Any]:
        """범용 수집 (collect_type으로 분기)."""
        collect_type = kwargs.pop("collect_type", None)
        if collect_type == "living_population":
            return await self.collect_living_population(**kwargs)
        elif collect_type == "subway":
            return await self.collect_subway_stats(**kwargs)
        elif collect_type == "card_sales":
            return await self.collect_card_sales(**kwargs)
        raise ValueError(f"Unknown collect_type: {collect_type}")


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _safe_decimal(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
