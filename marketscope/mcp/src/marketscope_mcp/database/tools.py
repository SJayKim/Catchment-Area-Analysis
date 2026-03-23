"""Database MCP 도구 구현 — PostGIS 공간쿼리 6개 도구."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from marketscope_mcp.database.db_client import execute_query

logger = logging.getLogger("mcp.database.tools")


async def query_nearby_stores(arguments: dict[str, Any], client: Any = None) -> dict:
    """반경 내 점포 조회 (PostGIS ST_DWithin)."""
    lat = arguments.get("lat")
    lng = arguments.get("lng")
    radius_m = arguments.get("radius_m", 500)
    industry = arguments.get("industry", "")

    if lat is None or lng is None:
        return {"error": "lat, lng 파라미터가 필요합니다."}

    query = """
        SELECT s.store_name, s.industry_name, s.road_address,
               s.industry_code_s,
               ST_Y(s.location::geometry) as lat,
               ST_X(s.location::geometry) as lng,
               ST_Distance(
                   s.location,
                   ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
               ) as distance_m
        FROM stores s
        WHERE s.is_open = true
          AND s.location IS NOT NULL
          AND ST_DWithin(
              s.location,
              ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
              $3
          )
    """
    params: list[Any] = [float(lng), float(lat), int(radius_m)]

    if industry:
        query += " AND (s.industry_name ILIKE $4 OR s.industry_code_s ILIKE $4)"
        params.append(f"%{industry}%")

    query += " ORDER BY distance_m LIMIT 50"

    try:
        rows = await execute_query(query, *params)
        return {
            "stores": rows,
            "total_count": len(rows),
            "search_params": {"lat": lat, "lng": lng, "radius_m": radius_m, "industry": industry},
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("query_nearby_stores 실패")
        return {"error": str(e), "stores": [], "total_count": 0}


async def query_population(arguments: dict[str, Any], client: Any = None) -> dict:
    """상권/행정동별 인구 데이터 조회."""
    district_name = arguments.get("district_name", "")
    district_code = arguments.get("district_code", "")
    stat_type = arguments.get("stat_type", "")  # living, resident, worker, floating

    if not district_name and not district_code:
        return {"error": "district_name 또는 district_code 파라미터가 필요합니다."}

    query = """
        SELECT d.district_code, d.district_name, d.dong_name,
               ps.stat_type, ps.year, ps.quarter, ps.month,
               ps.total_population, ps.male_population, ps.female_population,
               ps.age_20_29, ps.age_30_39, ps.age_40_49, ps.age_50_59, ps.age_60_plus,
               ps.time_00_06, ps.time_06_11, ps.time_11_14,
               ps.time_14_17, ps.time_17_21, ps.time_21_24,
               ps.day_mon, ps.day_tue, ps.day_wed, ps.day_thu,
               ps.day_fri, ps.day_sat, ps.day_sun,
               ps.data_source
        FROM population_stats ps
        JOIN districts d ON d.id = ps.district_id
    """
    params: list[Any] = []
    conditions: list[str] = []

    if district_code:
        conditions.append(f"d.district_code = ${len(params) + 1}")
        params.append(district_code)
    elif district_name:
        conditions.append(f"(d.district_name ILIKE ${len(params) + 1} OR d.dong_name ILIKE ${len(params) + 1})")
        params.append(f"%{district_name}%")

    if stat_type:
        conditions.append(f"ps.stat_type = ${len(params) + 1}")
        params.append(stat_type)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY ps.year DESC, ps.quarter DESC NULLS LAST, ps.month DESC NULLS LAST LIMIT 20"

    try:
        rows = await execute_query(query, *params)
        return {
            "population_data": rows,
            "total_count": len(rows),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("query_population 실패")
        return {"error": str(e), "population_data": [], "total_count": 0}


async def query_revenue(arguments: dict[str, Any], client: Any = None) -> dict:
    """상권/업종별 매출 데이터 조회."""
    district_name = arguments.get("district_name", "")
    district_code = arguments.get("district_code", "")
    industry = arguments.get("industry", "")

    if not district_name and not district_code:
        return {"error": "district_name 또는 district_code 파라미터가 필요합니다."}

    query = """
        SELECT d.district_code, d.district_name,
               rs.industry_code, rs.industry_name,
               rs.year, rs.quarter, rs.month,
               rs.total_revenue, rs.revenue_per_store, rs.transaction_count,
               rs.male_revenue, rs.female_revenue,
               rs.day_mon_revenue, rs.day_tue_revenue, rs.day_wed_revenue,
               rs.day_thu_revenue, rs.day_fri_revenue, rs.day_sat_revenue, rs.day_sun_revenue,
               rs.data_source
        FROM revenue_stats rs
        JOIN districts d ON d.id = rs.district_id
    """
    params: list[Any] = []
    conditions: list[str] = []

    if district_code:
        conditions.append(f"d.district_code = ${len(params) + 1}")
        params.append(district_code)
    elif district_name:
        conditions.append(f"(d.district_name ILIKE ${len(params) + 1} OR d.dong_name ILIKE ${len(params) + 1})")
        params.append(f"%{district_name}%")

    if industry:
        conditions.append(f"(rs.industry_name ILIKE ${len(params) + 1} OR rs.industry_code ILIKE ${len(params) + 1})")
        params.append(f"%{industry}%")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY rs.year DESC, rs.quarter DESC NULLS LAST, rs.month DESC NULLS LAST LIMIT 20"

    try:
        rows = await execute_query(query, *params)
        return {
            "revenue_data": rows,
            "total_count": len(rows),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("query_revenue 실패")
        return {"error": str(e), "revenue_data": [], "total_count": 0}


async def query_commercial_district(arguments: dict[str, Any], client: Any = None) -> dict:
    """상권 정보 조회."""
    district_name = arguments.get("district_name", "")
    district_code = arguments.get("district_code", "")

    if not district_name and not district_code:
        return {"error": "district_name 또는 district_code 파라미터가 필요합니다."}

    if district_code:
        query = """
            SELECT d.district_code, d.district_name, d.district_type,
                   d.gu_name, d.dong_name, d.admin_dong_code,
                   d.center_lat, d.center_lng,
                   (SELECT COUNT(*) FROM stores s
                    WHERE s.district_id = d.id AND s.is_open = true) as total_stores
            FROM districts d
            WHERE d.district_code = $1 AND d.is_active = true
            LIMIT 10
        """
        params: list[Any] = [district_code]
    else:
        query = """
            SELECT d.district_code, d.district_name, d.district_type,
                   d.gu_name, d.dong_name, d.admin_dong_code,
                   d.center_lat, d.center_lng,
                   (SELECT COUNT(*) FROM stores s
                    WHERE s.district_id = d.id AND s.is_open = true) as total_stores
            FROM districts d
            WHERE (d.district_name ILIKE $1 OR d.dong_name ILIKE $1 OR d.gu_name ILIKE $1)
              AND d.is_active = true
            LIMIT 10
        """
        params = [f"%{district_name}%"]

    try:
        rows = await execute_query(query, *params)
        return {
            "districts": rows,
            "total_count": len(rows),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("query_commercial_district 실패")
        return {"error": str(e), "districts": [], "total_count": 0}


async def query_transit(arguments: dict[str, Any], client: Any = None) -> dict:
    """교통(지하철/버스) 통계 조회."""
    station_name = arguments.get("station_name", "")

    if not station_name:
        return {"error": "station_name 파라미터가 필요합니다."}

    query = """
        SELECT station_name, line_name, transit_type,
               year, month,
               boarding_total, alighting_total,
               daily_avg_boarding, daily_avg_alighting,
               data_source
        FROM transit_stats
        WHERE station_name ILIKE $1
        ORDER BY year DESC, month DESC
        LIMIT 12
    """
    params = [f"%{station_name}%"]

    try:
        rows = await execute_query(query, *params)
        return {
            "transit_data": rows,
            "total_count": len(rows),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("query_transit 실패")
        return {"error": str(e), "transit_data": [], "total_count": 0}


async def execute_spatial_query(arguments: dict[str, Any], client: Any = None) -> dict:
    """범용 공간 쿼리 실행 (읽기 전용)."""
    query = arguments.get("query", "")
    if not query:
        return {"error": "query 파라미터가 필요합니다."}

    normalized = query.strip().upper()
    if not normalized.startswith("SELECT"):
        return {"error": "SELECT 쿼리만 허용됩니다."}

    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT"]
    for keyword in forbidden:
        if keyword in normalized:
            return {"error": f"{keyword} 구문은 허용되지 않습니다."}

    try:
        rows = await execute_query(query)
        return {
            "results": rows[:100],
            "total_count": len(rows),
            "truncated": len(rows) > 100,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("execute_spatial_query 실패")
        return {"error": str(e), "results": [], "total_count": 0}


TOOL_REGISTRY: dict[str, Any] = {
    "database.query_nearby_stores": query_nearby_stores,
    "database.query_population": query_population,
    "database.query_revenue": query_revenue,
    "database.query_commercial_district": query_commercial_district,
    "database.query_transit": query_transit,
    "database.execute_spatial_query": execute_spatial_query,
}
