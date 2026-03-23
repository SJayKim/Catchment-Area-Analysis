"""Naver Maps MCP 도구 구현 — 5개 도구."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from marketscope_mcp.naver_maps.api_client import NaverMapsClient

logger = logging.getLogger("mcp.naver_maps.tools")


async def naver_geocode(arguments: dict[str, Any], client: NaverMapsClient) -> dict:
    """주소 → 좌표 변환."""
    address = arguments.get("address", "")
    if not address:
        return {"error": "address 파라미터가 필요합니다."}

    try:
        result = await client.geocode(address)
        addresses = result.get("addresses", [])
        if not addresses:
            return {"error": f"주소를 찾을 수 없습니다: {address}"}

        addr = addresses[0]
        return {
            "lat": float(addr.get("y", 0)),
            "lng": float(addr.get("x", 0)),
            "road_address": addr.get("roadAddress", ""),
            "jibun_address": addr.get("jibunAddress", ""),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("naver_geocode 실패")
        return {"error": str(e)}


async def naver_reverse_geocode(arguments: dict[str, Any], client: NaverMapsClient) -> dict:
    """좌표 → 주소 변환."""
    lat = arguments.get("lat")
    lng = arguments.get("lng")
    if lat is None or lng is None:
        return {"error": "lat, lng 파라미터가 필요합니다."}

    try:
        result = await client.reverse_geocode(float(lat), float(lng))
        results = result.get("results", [])
        if not results:
            return {"error": f"좌표에 해당하는 주소가 없습니다: ({lat}, {lng})"}

        addr_info = results[0]
        region = addr_info.get("region", {})
        land = addr_info.get("land", {})

        return {
            "sido": region.get("area1", {}).get("name", ""),
            "sigungu": region.get("area2", {}).get("name", ""),
            "dong": region.get("area3", {}).get("name", ""),
            "road_name": land.get("name", ""),
            "road_number": land.get("number1", ""),
            "lat": lat,
            "lng": lng,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("naver_reverse_geocode 실패")
        return {"error": str(e)}


async def naver_local_search(arguments: dict[str, Any], client: NaverMapsClient) -> dict:
    """장소 검색 (Naver Search API)."""
    query = arguments.get("query", "")
    display = arguments.get("display", 5)
    if not query:
        return {"error": "query 파라미터가 필요합니다."}

    try:
        result = await client.local_search(query, display=int(display))
        places = []
        for item in result.get("items", []):
            # HTML 태그 제거
            title = item.get("title", "").replace("<b>", "").replace("</b>", "")
            places.append({
                "title": title,
                "address": item.get("address", ""),
                "road_address": item.get("roadAddress", ""),
                "category": item.get("category", ""),
                "telephone": item.get("telephone", ""),
                "link": item.get("link", ""),
                "mapx": item.get("mapx", 0),
                "mapy": item.get("mapy", 0),
            })

        return {
            "places": places,
            "total_count": result.get("total", len(places)),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("naver_local_search 실패")
        return {"error": str(e)}


async def naver_directions(arguments: dict[str, Any], client: NaverMapsClient) -> dict:
    """경로 탐색 (Naver Directions API)."""
    origin_lat = arguments.get("origin_lat")
    origin_lng = arguments.get("origin_lng")
    dest_lat = arguments.get("dest_lat")
    dest_lng = arguments.get("dest_lng")

    if any(v is None for v in (origin_lat, origin_lng, dest_lat, dest_lng)):
        return {"error": "origin_lat, origin_lng, dest_lat, dest_lng 파라미터가 필요합니다."}

    try:
        result = await client.directions(
            start_lng=float(origin_lng), start_lat=float(origin_lat),
            goal_lng=float(dest_lng), goal_lat=float(dest_lat),
        )
        route = result.get("route", {})
        traoptimal = route.get("traoptimal", [{}])
        if not traoptimal:
            return {"error": "경로를 찾을 수 없습니다."}

        summary = traoptimal[0].get("summary", {})
        return {
            "distance_m": summary.get("distance", 0),
            "duration_ms": summary.get("duration", 0),
            "duration_min": round(summary.get("duration", 0) / 60000, 1),
            "toll_fare": summary.get("tollFare", 0),
            "fuel_price": summary.get("fuelPrice", 0),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("naver_directions 실패")
        return {"error": str(e)}


async def naver_static_map(arguments: dict[str, Any], client: NaverMapsClient) -> dict:
    """정적 지도 이미지 URL 생성."""
    lat = arguments.get("lat")
    lng = arguments.get("lng")
    width = arguments.get("width", 600)
    height = arguments.get("height", 400)
    level = arguments.get("level", 16)

    if lat is None or lng is None:
        return {"error": "lat, lng 파라미터가 필요합니다."}

    url = client.static_map_url(
        lat=float(lat), lng=float(lng),
        width=int(width), height=int(height), level=int(level),
    )

    return {
        "map_url": url,
        "width": width,
        "height": height,
        "level": level,
        "note": "이미지 조회 시 X-NCP-APIGW-API-KEY-ID/KEY 헤더 필요",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


TOOL_REGISTRY: dict[str, Any] = {
    "naver_maps.geocode": naver_geocode,
    "naver_maps.reverse_geocode": naver_reverse_geocode,
    "naver_maps.local_search": naver_local_search,
    "naver_maps.directions": naver_directions,
    "naver_maps.static_map": naver_static_map,
}
