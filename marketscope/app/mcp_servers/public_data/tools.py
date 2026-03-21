"""Public Data MCP 도구 구현 — 8개 데이터 조회 도구.

각 도구는 (arguments: dict, clients: dict) → dict 시그니처.
DB가 없으면 외부 API 직접 호출 (fallback 모드).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Coroutine

import httpx

logger = logging.getLogger("mcp.public_data.tools")

ToolFunc = Callable[[dict[str, Any], dict[str, Any]], Coroutine[Any, Any, dict]]


def create_api_clients() -> dict[str, Any]:
    """API 클라이언트 및 키 초기화."""
    return {
        "seoul_key": os.environ.get("DATA_API_SEOUL_OPEN_DATA_KEY", ""),
        "kosis_key": os.environ.get("DATA_API_KOSIS_KEY", ""),
        "semas_key": os.environ.get("DATA_API_PUBLIC_DATA_KEY", ""),
        "http_client": httpx.AsyncClient(
            timeout=httpx.Timeout(30),
            limits=httpx.Limits(max_connections=10),
            follow_redirects=True,
        ),
    }


# ---------------------------------------------------------------------------
# 도구 1: 유동인구 (SEMAS)
# ---------------------------------------------------------------------------

async def get_floating_population(args: dict, clients: dict) -> dict:
    """유동인구 조회 — SEMAS /trdarFlorpopQq.

    Args:
        district_code: 상권코드
        quarter: 분기 코드 (예: "20244" = 2024년 4분기)
    """
    semas_key = clients.get("semas_key")
    if not semas_key:
        return {"error": "SEMAS API 키가 설정되지 않았습니다 (DATA_API_PUBLIC_DATA_KEY)"}

    client: httpx.AsyncClient = clients["http_client"]
    params = {
        "serviceKey": semas_key,
        "type": "json",
        "trdarCd": args.get("district_code", ""),
        "stdrYyquCd": args.get("quarter", ""),
        "numOfRows": "10",
        "pageNo": "1",
    }
    resp = await client.get(
        "https://apis.data.go.kr/B553077/api/open/trdarFlorpopQq", params=params,
    )
    resp.raise_for_status()
    data = resp.json()
    items = _extract_items(data)

    if not items:
        return {"data": [], "message": "데이터 없음"}

    return {
        "data": [
            {
                "district_code": args.get("district_code"),
                "quarter": args.get("quarter"),
                "total_population": _safe_int(item.get("totFlpop")),
                "male_population": _safe_int(item.get("mlFlpop")),
                "female_population": _safe_int(item.get("fmlFlpop")),
                "age_20s": _safe_int(item.get("agrde20Flpop")),
                "age_30s": _safe_int(item.get("agrde30Flpop")),
                "age_40s": _safe_int(item.get("agrde40Flpop")),
                "age_50s": _safe_int(item.get("agrde50Flpop")),
                "age_60_plus": _safe_int(item.get("agrde60AbvFlpop")),
            }
            for item in items
        ],
    }


# ---------------------------------------------------------------------------
# 도구 2: 추정매출 (SEMAS)
# ---------------------------------------------------------------------------

async def get_estimated_revenue(args: dict, clients: dict) -> dict:
    """추정매출 조회 — SEMAS /trdarSelngQq.

    Args:
        district_code: 상권코드
        industry_code: 업종코드 (선택)
        quarter: 분기 코드
    """
    semas_key = clients.get("semas_key")
    if not semas_key:
        return {"error": "SEMAS API 키가 설정되지 않았습니다"}

    client: httpx.AsyncClient = clients["http_client"]
    params = {
        "serviceKey": semas_key,
        "type": "json",
        "trdarCd": args.get("district_code", ""),
        "stdrYyquCd": args.get("quarter", ""),
        "numOfRows": "100",
        "pageNo": "1",
    }
    resp = await client.get(
        "https://apis.data.go.kr/B553077/api/open/trdarSelngQq", params=params,
    )
    resp.raise_for_status()
    data = resp.json()
    items = _extract_items(data)

    industry_code = args.get("industry_code")
    if industry_code:
        items = [i for i in items if i.get("svcIndutyCd") == industry_code]

    return {
        "data": [
            {
                "industry_code": item.get("svcIndutyCd"),
                "industry_name": item.get("svcIndutyNm"),
                "total_revenue": _safe_int(item.get("totSelngAmt")),
                "transaction_count": _safe_int(item.get("totSelngCo")),
                "revenue_per_store": _safe_int(item.get("perStrSelngAmt")),
            }
            for item in items
        ],
    }


# ---------------------------------------------------------------------------
# 도구 3: 점포 목록
# ---------------------------------------------------------------------------

async def get_store_list(args: dict, clients: dict) -> dict:
    """점포 목록 조회 — SEMAS /storeListInRadius.

    Args:
        lat: 위도
        lng: 경도
        radius_m: 반경 (미터, 기본 500)
        industry_code: 업종코드 (선택)
    """
    semas_key = clients.get("semas_key")
    if not semas_key:
        return {"error": "SEMAS API 키가 설정되지 않았습니다"}

    client: httpx.AsyncClient = clients["http_client"]
    params = {
        "serviceKey": semas_key,
        "type": "json",
        "radius": str(args.get("radius_m", 500)),
        "cx": str(args.get("lng", "")),
        "cy": str(args.get("lat", "")),
        "numOfRows": "100",
        "pageNo": "1",
    }
    industry_code = args.get("industry_code")
    if industry_code:
        params["indsSclsCd"] = industry_code

    resp = await client.get(
        "https://apis.data.go.kr/B553077/api/open/storeListInRadius", params=params,
    )
    resp.raise_for_status()
    data = resp.json()
    items = _extract_items(data)

    return {
        "data": [
            {
                "store_name": item.get("bizesNm"),
                "industry_name": item.get("smlClsNm"),
                "industry_code": item.get("smlClsCd"),
                "road_address": item.get("rdnmAdr"),
                "lat": _safe_float(item.get("lat")),
                "lng": _safe_float(item.get("lon")),
            }
            for item in items
        ],
        "total_count": len(items),
    }


# ---------------------------------------------------------------------------
# 도구 4: 점포 증감
# ---------------------------------------------------------------------------

async def get_store_count_change(args: dict, clients: dict) -> dict:
    """점포 증감 추이 — 여러 분기 비교.

    Args:
        district_code: 상권코드
        industry_code: 업종코드
        quarters: 분기 목록 ["20241", "20242", "20243", "20244"]
    """
    semas_key = clients.get("semas_key")
    if not semas_key:
        return {"error": "SEMAS API 키가 설정되지 않았습니다"}

    quarters = args.get("quarters", [])
    results = []

    client: httpx.AsyncClient = clients["http_client"]
    for q in quarters:
        params = {
            "serviceKey": semas_key,
            "type": "json",
            "trdarCd": args.get("district_code", ""),
            "stdrYyquCd": q,
            "numOfRows": "100",
            "pageNo": "1",
        }
        resp = await client.get(
            "https://apis.data.go.kr/B553077/api/open/storeListInArea", params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        items = _extract_items(data)

        industry_code = args.get("industry_code")
        if industry_code:
            items = [i for i in items if i.get("smlClsCd") == industry_code]

        results.append({
            "quarter": q,
            "store_count": len(items),
        })

    return {"data": results}


# ---------------------------------------------------------------------------
# 도구 5: 주민등록인구 (KOSIS)
# ---------------------------------------------------------------------------

async def get_resident_population(args: dict, clients: dict) -> dict:
    """주민등록인구 조회 — KOSIS DT_1B040A3.

    Args:
        region_code: 행정구역코드 (예: "1168000000" = 강남구)
        year: 기준년도 (기본: 2025)
    """
    kosis_key = clients.get("kosis_key")
    if not kosis_key:
        return {"error": "KOSIS API 키가 설정되지 않았습니다 (DATA_API_KOSIS_KEY)"}

    year = str(args.get("year", 2025))
    client: httpx.AsyncClient = clients["http_client"]
    params = {
        "method": "getList",
        "apiKey": kosis_key,
        "itmId": "T2+T3+",
        "objL1": args.get("region_code", ""),
        "objL2": "ALL",
        "format": "json",
        "jsonVD": "Y",
        "prdSe": "Y",
        "startPrdDe": year,
        "endPrdDe": year,
        "orgId": "101",
        "tblId": "DT_1B040A3",
    }
    resp = await client.get(
        "https://kosis.kr/openapi/Param/statisticsParameterData.do", params=params,
    )
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list):
        return {"data": None, "message": "응답 형식 오류"}

    result = {"region_code": args.get("region_code"), "year": year}
    for item in data:
        itm_nm = item.get("ITM_NM", "")
        if "총인구" in itm_nm or item.get("ITM_ID") == "T2":
            result["total_population"] = _safe_int(item.get("DT"))
        elif "남자" in itm_nm or item.get("ITM_ID") == "T3":
            result["male_population"] = _safe_int(item.get("DT"))

    total = result.get("total_population")
    male = result.get("male_population")
    if total and male:
        result["female_population"] = total - male

    return {"data": result}


# ---------------------------------------------------------------------------
# 도구 6: 직장인구 (KOSIS)
# ---------------------------------------------------------------------------

async def get_worker_population(args: dict, clients: dict) -> dict:
    """직장인구 조회 — KOSIS.

    Args:
        region_code: 행정구역코드
        year: 기준년도
    """
    kosis_key = clients.get("kosis_key")
    if not kosis_key:
        return {"error": "KOSIS API 키가 설정되지 않았습니다"}

    year = str(args.get("year", 2025))
    client: httpx.AsyncClient = clients["http_client"]
    params = {
        "method": "getList",
        "apiKey": kosis_key,
        "itmId": "ALL",
        "objL1": args.get("region_code", ""),
        "objL2": "ALL",
        "format": "json",
        "jsonVD": "Y",
        "prdSe": "Y",
        "startPrdDe": year,
        "endPrdDe": year,
        "orgId": "101",
        "tblId": "DT_1ES4011",  # 사업체 종사자 수
    }
    resp = await client.get(
        "https://kosis.kr/openapi/Param/statisticsParameterData.do", params=params,
    )
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list):
        return {"data": None, "message": "응답 형식 오류 또는 데이터 없음"}

    total_workers = None
    for item in data:
        if "종사자" in item.get("ITM_NM", "") or "합계" in item.get("ITM_NM", ""):
            total_workers = _safe_int(item.get("DT"))
            break

    return {
        "data": {
            "region_code": args.get("region_code"),
            "year": year,
            "worker_population": total_workers,
        }
    }


# ---------------------------------------------------------------------------
# 도구 7: 서울 생활인구
# ---------------------------------------------------------------------------

async def get_seoul_living_population(args: dict, clients: dict) -> dict:
    """서울 생활인구 조회 — 서울 열린데이터 SPOP_LOCAL_RESD_DONG.

    Args:
        dong_code: 행정동코드
        date: 기준일 (YYYYMMDD)
    """
    seoul_key = clients.get("seoul_key")
    if not seoul_key:
        return {"error": "서울 열린데이터 API 키가 설정되지 않았습니다"}

    dong_code = args.get("dong_code", "")
    date_str = args.get("date", "")
    client: httpx.AsyncClient = clients["http_client"]

    url = f"http://openapi.seoul.go.kr:8088/{seoul_key}/json/SPOP_LOCAL_RESD_DONG/1/100/{date_str}/{dong_code}"
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()

    service_data = data.get("SPOP_LOCAL_RESD_DONG", {})
    rows = service_data.get("row", [])

    if not rows:
        return {"data": [], "message": "데이터 없음"}

    return {
        "data": [
            {
                "dong_code": dong_code,
                "date": date_str,
                "total_population": _safe_int(row.get("TOT_LVPOP_CO")),
                "male_population": _safe_int(row.get("ML_LVPOP_CO")),
                "female_population": _safe_int(row.get("FML_LVPOP_CO")),
                "age_20s": _safe_int(row.get("AGRDE_20_LVPOP_CO")),
                "age_30s": _safe_int(row.get("AGRDE_30_LVPOP_CO")),
                "age_40s": _safe_int(row.get("AGRDE_40_LVPOP_CO")),
                "age_50s": _safe_int(row.get("AGRDE_50_LVPOP_CO")),
                "age_60_plus": _safe_int(row.get("AGRDE_60_ABOVE_LVPOP_CO")),
            }
            for row in rows
        ],
        "total_count": len(rows),
    }


# ---------------------------------------------------------------------------
# 도구 8: 카드매출
# ---------------------------------------------------------------------------

async def get_card_sales(args: dict, clients: dict) -> dict:
    """카드매출 조회 — 서울 열린데이터 tbgiCardInfo.

    Args:
        year: 년도
        month: 월
    """
    seoul_key = clients.get("seoul_key")
    if not seoul_key:
        return {"error": "서울 열린데이터 API 키가 설정되지 않았습니다"}

    year = args.get("year", "2025")
    month = args.get("month", "01")
    client: httpx.AsyncClient = clients["http_client"]

    url = f"http://openapi.seoul.go.kr:8088/{seoul_key}/json/tbgiCardInfo/1/100/{year}/{month}"
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()

    service_data = data.get("tbgiCardInfo", {})
    rows = service_data.get("row", [])

    if not rows:
        return {"data": [], "message": "데이터 없음"}

    return {
        "data": [
            {
                "industry_code": row.get("SVC_INDUTY_CD"),
                "industry_name": row.get("SVC_INDUTY_CD_NM"),
                "total_sales": _safe_int(row.get("TOT_SELNG_AMT")),
                "transaction_count": _safe_int(row.get("TOT_SELNG_CO")),
            }
            for row in rows[:50]  # 최대 50건
        ],
        "total_count": len(rows),
    }


# ---------------------------------------------------------------------------
# TOOL_REGISTRY
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, ToolFunc] = {
    "public_data.get_floating_population": get_floating_population,
    "public_data.get_estimated_revenue": get_estimated_revenue,
    "public_data.get_store_list": get_store_list,
    "public_data.get_store_count_change": get_store_count_change,
    "public_data.get_resident_population": get_resident_population,
    "public_data.get_worker_population": get_worker_population,
    "public_data.get_seoul_living_population": get_seoul_living_population,
    "public_data.get_card_sales": get_card_sales,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_items(data: dict) -> list[dict]:
    """SEMAS API 응답에서 items 추출."""
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


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (ValueError, TypeError):
        return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
