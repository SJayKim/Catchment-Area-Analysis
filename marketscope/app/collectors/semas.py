"""SEMAS (소상공인진흥공단) 상권정보 API Collector.

수집 대상:
- /trdarFlorpopQq: 유동인구 (분기별)
- /trdarSelngQq: 추정매출 (분기별)
- /storeListInArea: 점포 목록 (상권코드)
- /storeListInRadius: 반경 점포 검색

참고: data.go.kr API 키가 필요합니다 (DATA_API_PUBLIC_DATA_KEY).
현재 키 미발급 상태이므로 코드만 구현, 실 테스트 대기.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional
from urllib.parse import quote

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector, CollectionError
from app.db.models import PopulationStat, RevenueStat, Store

logger = logging.getLogger(__name__)


class SemasCollector(BaseCollector):
    """소상공인 상권정보 API 수집기.

    Base URL: https://apis.data.go.kr/B553077/api/open
    인증: serviceKey URL 파라미터 (URL encoding 필요)
    일일 제한: 1,000건 (확장 신청 시 100,000건)
    """

    COLLECTOR_NAME = "semas"
    BASE_URL = "https://apis.data.go.kr/B553077/api/open"
    DAILY_LIMIT = 1000

    def __init__(self, session: AsyncSession, api_key: str) -> None:
        super().__init__(session, api_key)
        if not api_key:
            raise ValueError("data.go.kr API 키가 필요합니다 (DATA_API_PUBLIC_DATA_KEY)")

    def _base_params(self) -> dict:
        return {
            "serviceKey": self.api_key,
            "type": "json",
            "numOfRows": "100",
            "pageNo": "1",
        }

    def _parse_items(self, data: dict) -> list[dict]:
        """body → items → item 배열 추출 (단일 객체 분기)."""
        body = data.get("body", data)
        items = body.get("items", {})
        if isinstance(items, dict):
            item = items.get("item", [])
        else:
            item = items

        if isinstance(item, dict):
            return [item]
        if isinstance(item, list):
            return item
        return []

    @staticmethod
    def _quarter_code(year: int, quarter: int) -> str:
        """연도/분기 → stdrYyquCd 변환 (예: 2024Q4 → '20244')."""
        return f"{year}{quarter}"

    async def collect_floating_population(
        self,
        district_code: str,
        year: int,
        quarter: int,
        district_id: int,
    ) -> dict[str, Any]:
        """유동인구 수집 (/trdarFlorpopQq)."""
        t0 = time.monotonic()
        endpoint = "/trdarFlorpopQq"

        params = self._base_params()
        params["trdarCd"] = district_code
        params["stdrYyquCd"] = self._quarter_code(year, quarter)

        try:
            data = await self._call_api_with_retry(
                "GET", self.BASE_URL + endpoint, params=params,
            )
            rows = self._parse_items(data)
            if not rows:
                await self._log_collection(
                    endpoint, params, status="partial", records_fetched=0,
                )
                return {"status": "no_data", "count": 0}

            inserted = 0
            for row in rows:
                values = dict(
                    district_id=district_id,
                    stat_type="floating",
                    year=year,
                    quarter=quarter,
                    total_population=_safe_int(row.get("totFlpop")),
                    male_population=_safe_int(row.get("mlFlpop")),
                    female_population=_safe_int(row.get("fmlFlpop")),
                    age_10_19=_safe_int(row.get("agrde10Flpop")),
                    age_20_29=_safe_int(row.get("agrde20Flpop")),
                    age_30_39=_safe_int(row.get("agrde30Flpop")),
                    age_40_49=_safe_int(row.get("agrde40Flpop")),
                    age_50_59=_safe_int(row.get("agrde50Flpop")),
                    age_60_plus=_safe_int(row.get("agrde60AbvFlpop")),
                    time_00_06=_safe_int(row.get("tmzn1Flpop")),
                    time_06_11=_safe_int(row.get("tmzn2Flpop")),
                    time_11_14=_safe_int(row.get("tmzn3Flpop")),
                    time_14_17=_safe_int(row.get("tmzn4Flpop")),
                    time_17_21=_safe_int(row.get("tmzn5Flpop")),
                    time_21_24=_safe_int(row.get("tmzn6Flpop")),
                    day_mon=_safe_int(row.get("monFlpop")),
                    day_tue=_safe_int(row.get("tuesFlpop")),
                    day_wed=_safe_int(row.get("wedFlpop")),
                    day_thu=_safe_int(row.get("thurFlpop")),
                    day_fri=_safe_int(row.get("friFlpop")),
                    day_sat=_safe_int(row.get("satFlpop")),
                    day_sun=_safe_int(row.get("sunFlpop")),
                    data_source="SEMAS",
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
                endpoint, {"district_code": district_code, "year": year, "quarter": quarter},
                records_fetched=len(rows), records_inserted=inserted,
                duration_ms=elapsed,
            )
            return {"status": "success", "fetched": len(rows), "inserted": inserted}

        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"district_code": district_code, "year": year, "quarter": quarter},
                status="failed", error_message=str(e), duration_ms=elapsed,
            )
            raise

    async def collect_estimated_revenue(
        self,
        district_code: str,
        industry_code: str,
        year: int,
        quarter: int,
        district_id: int,
    ) -> dict[str, Any]:
        """추정매출 수집 (/trdarSelngQq)."""
        t0 = time.monotonic()
        endpoint = "/trdarSelngQq"

        params = self._base_params()
        params["trdarCd"] = district_code
        params["stdrYyquCd"] = self._quarter_code(year, quarter)

        try:
            data = await self._call_api_with_retry(
                "GET", self.BASE_URL + endpoint, params=params,
            )
            rows = self._parse_items(data)
            if not rows:
                await self._log_collection(
                    endpoint, params, status="partial", records_fetched=0,
                )
                return {"status": "no_data", "count": 0}

            inserted = 0
            for row in rows:
                ind_code = row.get("svcIndutyCd", "")
                if industry_code and ind_code != industry_code:
                    continue

                values = dict(
                    district_id=district_id,
                    industry_code=ind_code,
                    industry_name=row.get("svcIndutyNm", ""),
                    year=year,
                    quarter=quarter,
                    total_revenue=_safe_decimal(row.get("totSelngAmt")),
                    transaction_count=_safe_int(row.get("totSelngCo")),
                    male_revenue=_safe_decimal(row.get("mlSelngAmt")),
                    female_revenue=_safe_decimal(row.get("fmlSelngAmt")),
                    age_20_revenue=_safe_decimal(row.get("agrde20SelngAmt")),
                    age_30_revenue=_safe_decimal(row.get("agrde30SelngAmt")),
                    age_40_revenue=_safe_decimal(row.get("agrde40SelngAmt")),
                    age_50_revenue=_safe_decimal(row.get("agrde50SelngAmt")),
                    age_60_plus_revenue=_safe_decimal(row.get("agrde60AbvSelngAmt")),
                    day_mon_revenue=_safe_decimal(row.get("monSelngAmt")),
                    day_tue_revenue=_safe_decimal(row.get("tuesSelngAmt")),
                    day_wed_revenue=_safe_decimal(row.get("wedSelngAmt")),
                    day_thu_revenue=_safe_decimal(row.get("thurSelngAmt")),
                    day_fri_revenue=_safe_decimal(row.get("friSelngAmt")),
                    day_sat_revenue=_safe_decimal(row.get("satSelngAmt")),
                    day_sun_revenue=_safe_decimal(row.get("sunSelngAmt")),
                    time_00_06_revenue=_safe_decimal(row.get("tmzn1SelngAmt")),
                    time_06_11_revenue=_safe_decimal(row.get("tmzn2SelngAmt")),
                    time_11_14_revenue=_safe_decimal(row.get("tmzn3SelngAmt")),
                    time_14_17_revenue=_safe_decimal(row.get("tmzn4SelngAmt")),
                    time_17_21_revenue=_safe_decimal(row.get("tmzn5SelngAmt")),
                    time_21_24_revenue=_safe_decimal(row.get("tmzn6SelngAmt")),
                    data_source="SEMAS",
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
                endpoint, {"district_code": district_code, "industry_code": industry_code, "year": year, "quarter": quarter},
                records_fetched=len(rows), records_inserted=inserted,
                duration_ms=elapsed,
            )
            return {"status": "success", "fetched": len(rows), "inserted": inserted}

        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"district_code": district_code},
                status="failed", error_message=str(e), duration_ms=elapsed,
            )
            raise

    async def collect_store_list(
        self,
        district_code: str,
        district_id: int,
    ) -> dict[str, Any]:
        """점포 목록 수집 (/storeListInArea)."""
        t0 = time.monotonic()
        endpoint = "/storeListInArea"

        params = self._base_params()
        params["trdarCd"] = district_code
        params["numOfRows"] = "1000"

        try:
            data = await self._call_api_with_retry(
                "GET", self.BASE_URL + endpoint, params=params,
            )
            rows = self._parse_items(data)
            if not rows:
                await self._log_collection(
                    endpoint, params, status="partial", records_fetched=0,
                )
                return {"status": "no_data", "count": 0}

            inserted = 0
            for row in rows:
                lat = _safe_decimal(row.get("lat"))
                lng = _safe_decimal(row.get("lon"))

                values = dict(
                    district_id=district_id,
                    store_name=row.get("bizesNm", "Unknown"),
                    branch_name=row.get("brchNm"),
                    industry_code_l=row.get("lrgClsCd"),
                    industry_code_m=row.get("mdlClsCd"),
                    industry_code_s=row.get("smlClsCd"),
                    industry_name=row.get("smlClsNm"),
                    road_address=row.get("rdnmAdr"),
                    jibun_address=row.get("lnoAdr"),
                    lat=lat,
                    lng=lng,
                    floor_info=row.get("flrNo"),
                    data_source="SEMAS",
                    is_open=True,
                    raw_data=row,
                )
                # 이름+주소 기준 upsert는 별도 키 없으므로 단순 insert
                store = Store(**values)
                self.session.add(store)
                inserted += 1

            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"district_code": district_code},
                records_fetched=len(rows), records_inserted=inserted,
                duration_ms=elapsed,
            )
            return {"status": "success", "fetched": len(rows), "inserted": inserted}

        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            await self._log_collection(
                endpoint, {"district_code": district_code},
                status="failed", error_message=str(e), duration_ms=elapsed,
            )
            raise

    async def collect(self, **kwargs) -> dict[str, Any]:
        collect_type = kwargs.pop("collect_type", None)
        if collect_type == "floating_population":
            return await self.collect_floating_population(**kwargs)
        elif collect_type == "estimated_revenue":
            return await self.collect_estimated_revenue(**kwargs)
        elif collect_type == "store_list":
            return await self.collect_store_list(**kwargs)
        raise ValueError(f"Unknown collect_type: {collect_type}")


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (ValueError, TypeError):
        return None


def _safe_decimal(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
