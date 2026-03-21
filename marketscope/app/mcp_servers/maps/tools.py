"""Maps MCP 도구 구현 — 카카오 API 기반."""

from __future__ import annotations

import logging
import math
from typing import Any

from app.mcp_servers.maps.kakao_client import KakaoLocalClient

logger = logging.getLogger("mcp.maps.tools")

# ---------------------------------------------------------------------------
# Category code reference
# MT1=대형마트, CS2=편의점, SW8=지하철, BK9=은행,
# FD6=음식점, CE7=카페, HP8=병원, PM9=약국
# ---------------------------------------------------------------------------


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 사이의 직선 거리(m)를 계산한다."""
    R = 6_371_000  # 지구 반지름 (m)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _place_from_doc(doc: dict) -> dict:
    """카카오 document → 표준 place dict."""
    return {
        "name": doc.get("place_name", ""),
        "address": doc.get("address_name", ""),
        "category": doc.get("category_name", ""),
        "lat": float(doc["y"]) if doc.get("y") else None,
        "lng": float(doc["x"]) if doc.get("x") else None,
        "phone": doc.get("phone", ""),
        "url": doc.get("place_url", ""),
        "distance": int(doc["distance"]) if doc.get("distance") else None,
    }


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def geocode(arguments: dict[str, Any], kakao: KakaoLocalClient) -> dict:
    """주소 → 좌표 변환."""
    address = arguments.get("address")
    if not address:
        return {"error": "address 파라미터가 필요합니다."}

    try:
        result = await kakao.search_address(address)
    except Exception as e:
        logger.exception("geocode 실패")
        return {"error": f"카카오 API 호출 실패: {e}"}

    documents = result.get("documents", [])
    if not documents:
        return {"error": f"주소를 찾을 수 없습니다: {address}"}

    doc = documents[0]
    response: dict[str, Any] = {
        "lat": float(doc.get("y", 0)),
        "lng": float(doc.get("x", 0)),
        "address_name": doc.get("address_name", ""),
    }

    # road address
    road = doc.get("road_address")
    if road:
        response["road_address_name"] = road.get("address_name", "")
        response["dong_code"] = road.get("zone_no", "")
    else:
        response["road_address_name"] = ""

    # detail mode: include all results
    if arguments.get("detail"):
        response["all_results"] = [
            {
                "lat": float(d.get("y", 0)),
                "lng": float(d.get("x", 0)),
                "address_name": d.get("address_name", ""),
                "address_type": d.get("address_type", ""),
            }
            for d in documents
        ]

    return response


async def reverse_geocode(arguments: dict[str, Any], kakao: KakaoLocalClient) -> dict:
    """좌표 → 주소 변환."""
    lat = arguments.get("lat")
    lng = arguments.get("lng")
    if lat is None or lng is None:
        return {"error": "lat, lng 파라미터가 필요합니다."}

    try:
        result = await kakao.coord_to_address(float(lng), float(lat))
    except Exception as e:
        logger.exception("reverse_geocode 실패")
        return {"error": f"카카오 API 호출 실패: {e}"}

    documents = result.get("documents", [])
    if not documents:
        return {"error": f"좌표에 해당하는 주소를 찾을 수 없습니다: ({lat}, {lng})"}

    doc = documents[0]
    addr = doc.get("address", {}) or {}
    road = doc.get("road_address", {}) or {}

    return {
        "address_name": addr.get("address_name", ""),
        "road_address_name": road.get("address_name", ""),
        "region_1depth": addr.get("region_1depth_name", ""),
        "region_2depth": addr.get("region_2depth_name", ""),
        "region_3depth": addr.get("region_3depth_name", ""),
        "lat": lat,
        "lng": lng,
    }


async def search_nearby(arguments: dict[str, Any], kakao: KakaoLocalClient) -> dict:
    """주변 카테고리 검색."""
    lat = arguments.get("lat")
    lng = arguments.get("lng")
    radius_m = arguments.get("radius_m", 500)
    category_code = arguments.get("category_code")

    if lat is None or lng is None or not category_code:
        return {"error": "lat, lng, category_code 파라미터가 필요합니다."}

    try:
        result = await kakao.search_category(
            category_code=category_code,
            lng=float(lng),
            lat=float(lat),
            radius=int(radius_m),
        )
    except Exception as e:
        logger.exception("search_nearby 실패")
        return {"error": f"카카오 API 호출 실패: {e}"}

    places = [_place_from_doc(doc) for doc in result.get("documents", [])]
    return {
        "places": places,
        "total_count": len(places),
    }


async def search_keyword(arguments: dict[str, Any], kakao: KakaoLocalClient) -> dict:
    """키워드 검색."""
    keyword = arguments.get("keyword")
    if not keyword:
        return {"error": "keyword 파라미터가 필요합니다."}

    lat = arguments.get("lat")
    lng = arguments.get("lng")
    radius_m = arguments.get("radius_m")

    try:
        result = await kakao.search_keyword(
            query=keyword,
            lng=float(lng) if lng is not None else None,
            lat=float(lat) if lat is not None else None,
            radius=int(radius_m) if radius_m is not None else None,
        )
    except Exception as e:
        logger.exception("search_keyword 실패")
        return {"error": f"카카오 API 호출 실패: {e}"}

    places = [_place_from_doc(doc) for doc in result.get("documents", [])]
    return {
        "places": places,
        "total_count": result.get("meta", {}).get("total_count", len(places)),
    }


async def get_walking_route(arguments: dict[str, Any], kakao: KakaoLocalClient) -> dict:
    """도보 경로 계산 (직선 거리 기반 추정)."""
    origin_lat = arguments.get("origin_lat")
    origin_lng = arguments.get("origin_lng")
    dest_lat = arguments.get("dest_lat")
    dest_lng = arguments.get("dest_lng")

    if any(v is None for v in (origin_lat, origin_lng, dest_lat, dest_lng)):
        return {"error": "origin_lat, origin_lng, dest_lat, dest_lng 파라미터가 필요합니다."}

    # 직선 거리 계산
    straight_distance = _haversine(
        float(origin_lat), float(origin_lng),
        float(dest_lat), float(dest_lng),
    )

    # 도보 거리는 직선 거리의 약 1.3배로 추정
    walk_distance = straight_distance * 1.3
    # 도보 속도: 80m/min
    walk_duration = walk_distance / 80.0

    return {
        "distance_m": round(walk_distance, 1),
        "duration_min": round(walk_duration, 1),
        "route_summary": f"직선 거리 {straight_distance:.0f}m 기반 도보 추정 (약 {walk_duration:.0f}분)",
        "note": "카카오 보행자 경로 API 미지원으로 직선 거리 기반 추정치입니다.",
    }


async def get_transit_nearby(arguments: dict[str, Any], kakao: KakaoLocalClient) -> dict:
    """주변 교통시설 검색."""
    lat = arguments.get("lat")
    lng = arguments.get("lng")
    radius_m = arguments.get("radius_m", 1000)

    if lat is None or lng is None:
        return {"error": "lat, lng 파라미터가 필요합니다."}

    lat_f, lng_f, radius_i = float(lat), float(lng), int(radius_m)

    try:
        # 지하철역 검색 (SW8)
        subway_result = await kakao.search_category("SW8", lng=lng_f, lat=lat_f, radius=radius_i)
        # 버스 정류장은 별도 카테고리가 없으므로 키워드 검색으로 대체
        bus_result = await kakao.search_keyword(
            query="버스정류장", lng=lng_f, lat=lat_f, radius=radius_i
        )
    except Exception as e:
        logger.exception("get_transit_nearby 실패")
        return {"error": f"카카오 API 호출 실패: {e}"}

    subway_stations = [_place_from_doc(doc) for doc in subway_result.get("documents", [])]
    bus_stops = [_place_from_doc(doc) for doc in bus_result.get("documents", [])]

    return {
        "subway_stations": subway_stations,
        "bus_stops": bus_stops,
        "total_transit_count": len(subway_stations) + len(bus_stops),
    }


async def get_category_pois(arguments: dict[str, Any], kakao: KakaoLocalClient) -> dict:
    """카테고리별 POI 검색."""
    lat = arguments.get("lat")
    lng = arguments.get("lng")
    radius_m = arguments.get("radius_m", 500)
    category = arguments.get("category")

    if lat is None or lng is None or not category:
        return {"error": "lat, lng, category 파라미터가 필요합니다."}

    try:
        result = await kakao.search_category(
            category_code=category,
            lng=float(lng),
            lat=float(lat),
            radius=int(radius_m),
        )
    except Exception as e:
        logger.exception("get_category_pois 실패")
        return {"error": f"카카오 API 호출 실패: {e}"}

    pois = [_place_from_doc(doc) for doc in result.get("documents", [])]
    return {
        "pois": pois,
        "total_count": len(pois),
        "category": category,
    }


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, Any] = {
    "maps.geocode": geocode,
    "maps.reverse_geocode": reverse_geocode,
    "maps.search_nearby": search_nearby,
    "maps.search_keyword": search_keyword,
    "maps.get_walking_route": get_walking_route,
    "maps.get_transit_nearby": get_transit_nearby,
    "maps.get_category_pois": get_category_pois,
}
