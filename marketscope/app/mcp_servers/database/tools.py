"""Database MCP 도구 구현 — PostGIS 공간쿼리 5개 도구."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.mcp_servers.database.db_client import execute_query, execute_scalar

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
        SELECT store_name, industry_category, address,
               ST_Y(geom::geometry) as lat, ST_X(geom::geometry) as lng,
               ST_Distance(geom, ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography) as distance_m
        FROM stores
        WHERE ST_DWithin(
            geom,
            ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
            $3
        )
    """
    params = [float(lng), float(lat), int(radius_m)]

    if industry:
        query += " AND industry_category ILIKE $4"
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


async def query_population_grid(arguments: dict[str, Any], client: Any = None) -> dict:
    """격자별 인구 데이터 조회."""
    area_code = arguments.get("area_code", "")
    dong_name = arguments.get("dong_name", "")

    if not area_code and not dong_name:
        return {"error": "area_code 또는 dong_name 파라미터가 필요합니다."}

    if area_code:
        query = """
            SELECT grid_id, total_population, male_population, female_population
            FROM population_grid
            WHERE area_code = $1
            ORDER BY total_population DESC LIMIT 20
        """
        params = [area_code]
    else:
        query = """
            SELECT grid_id, total_population, male_population, female_population
            FROM population_grid
            WHERE dong_name ILIKE $1
            ORDER BY total_population DESC LIMIT 20
        """
        params = [f"%{dong_name}%"]

    try:
        rows = await execute_query(query, *params)
        return {
            "grids": rows,
            "total_count": len(rows),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("query_population_grid 실패")
        return {"error": str(e), "grids": [], "total_count": 0}


async def query_revenue_by_area(arguments: dict[str, Any], client: Any = None) -> dict:
    """지역별 매출 데이터 조회."""
    area_code = arguments.get("area_code", "")
    industry = arguments.get("industry", "")
    year_quarter = arguments.get("year_quarter", "")

    if not area_code:
        return {"error": "area_code 파라미터가 필요합니다."}

    query = """
        SELECT area_code, area_name, industry_category,
               monthly_revenue, store_count,
               CASE WHEN store_count > 0 THEN monthly_revenue / store_count ELSE 0 END as avg_revenue
        FROM area_revenue
        WHERE area_code = $1
    """
    params: list[Any] = [area_code]

    if industry:
        query += " AND industry_category ILIKE $2"
        params.append(f"%{industry}%")

    query += " ORDER BY monthly_revenue DESC LIMIT 20"

    try:
        rows = await execute_query(query, *params)
        return {
            "revenues": rows,
            "total_count": len(rows),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("query_revenue_by_area 실패")
        return {"error": str(e), "revenues": [], "total_count": 0}


async def query_commercial_district(arguments: dict[str, Any], client: Any = None) -> dict:
    """상권 정보 조회."""
    lat = arguments.get("lat")
    lng = arguments.get("lng")
    district_name = arguments.get("district_name", "")
    radius_m = arguments.get("radius_m", 1000)

    if lat is not None and lng is not None:
        query = """
            SELECT district_code, district_name, district_type, total_stores,
                   ST_Y(center_geom::geometry) as lat, ST_X(center_geom::geometry) as lng,
                   ST_Distance(center_geom, ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography) as distance_m
            FROM commercial_districts
            WHERE ST_DWithin(
                center_geom,
                ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
                $3
            )
            ORDER BY distance_m LIMIT 10
        """
        params: list[Any] = [float(lng), float(lat), int(radius_m)]
    elif district_name:
        query = """
            SELECT district_code, district_name, district_type, total_stores,
                   ST_Y(center_geom::geometry) as lat, ST_X(center_geom::geometry) as lng
            FROM commercial_districts
            WHERE district_name ILIKE $1
            LIMIT 10
        """
        params = [f"%{district_name}%"]
    else:
        return {"error": "lat/lng 또는 district_name 파라미터가 필요합니다."}

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


async def execute_spatial_query(arguments: dict[str, Any], client: Any = None) -> dict:
    """범용 공간 쿼리 실행 (읽기 전용)."""
    query = arguments.get("query", "")
    if not query:
        return {"error": "query 파라미터가 필요합니다."}

    # 안전성 검사: SELECT만 허용
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
            "results": rows[:100],  # 최대 100행
            "total_count": len(rows),
            "truncated": len(rows) > 100,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("execute_spatial_query 실패")
        return {"error": str(e), "results": [], "total_count": 0}


TOOL_REGISTRY: dict[str, Any] = {
    "database.query_nearby_stores": query_nearby_stores,
    "database.query_population_grid": query_population_grid,
    "database.query_revenue_by_area": query_revenue_by_area,
    "database.query_commercial_district": query_commercial_district,
    "database.execute_spatial_query": execute_spatial_query,
}
