"""Google Maps MCP 도구 구현 — 5개 도구."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from marketscope_mcp.google_maps.api_client import GoogleMapsClient

logger = logging.getLogger("mcp.google_maps.tools")


async def google_geocode(arguments: dict[str, Any], client: GoogleMapsClient) -> dict:
    """주소 → 좌표 변환."""
    address = arguments.get("address", "")
    if not address:
        return {"error": "address 파라미터가 필요합니다."}

    try:
        result = await client.geocode(address)
        results = result.get("results", [])
        if not results:
            return {"error": f"주소를 찾을 수 없습니다: {address}"}

        geo = results[0]
        location = geo.get("geometry", {}).get("location", {})
        return {
            "lat": location.get("lat"),
            "lng": location.get("lng"),
            "formatted_address": geo.get("formatted_address", ""),
            "place_id": geo.get("place_id", ""),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("google_geocode 실패")
        return {"error": str(e)}


async def google_reverse_geocode(arguments: dict[str, Any], client: GoogleMapsClient) -> dict:
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

        geo = results[0]
        return {
            "formatted_address": geo.get("formatted_address", ""),
            "place_id": geo.get("place_id", ""),
            "address_components": geo.get("address_components", []),
            "lat": lat,
            "lng": lng,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("google_reverse_geocode 실패")
        return {"error": str(e)}


async def google_nearby_search(arguments: dict[str, Any], client: GoogleMapsClient) -> dict:
    """주변 장소 검색 (Places API)."""
    lat = arguments.get("lat")
    lng = arguments.get("lng")
    radius_m = arguments.get("radius_m", 500)
    keyword = arguments.get("keyword", "")
    place_type = arguments.get("type", "")

    if lat is None or lng is None:
        return {"error": "lat, lng 파라미터가 필요합니다."}

    try:
        result = await client.nearby_search(
            lat=float(lat), lng=float(lng), radius=int(radius_m),
            keyword=keyword, type_=place_type,
        )
        places = []
        for p in result.get("results", []):
            loc = p.get("geometry", {}).get("location", {})
            places.append({
                "name": p.get("name", ""),
                "address": p.get("vicinity", ""),
                "lat": loc.get("lat"),
                "lng": loc.get("lng"),
                "rating": p.get("rating"),
                "total_ratings": p.get("user_ratings_total", 0),
                "place_id": p.get("place_id", ""),
                "types": p.get("types", []),
            })

        return {
            "places": places,
            "total_count": len(places),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("google_nearby_search 실패")
        return {"error": str(e)}


async def google_place_details(arguments: dict[str, Any], client: GoogleMapsClient) -> dict:
    """장소 상세 정보 (리뷰, 영업시간)."""
    place_id = arguments.get("place_id", "")
    if not place_id:
        return {"error": "place_id 파라미터가 필요합니다."}

    try:
        result = await client.place_details(place_id)
        detail = result.get("result", {})
        loc = detail.get("geometry", {}).get("location", {})

        reviews = []
        for r in detail.get("reviews", [])[:5]:
            reviews.append({
                "author": r.get("author_name", ""),
                "rating": r.get("rating"),
                "text": r.get("text", "")[:200],
                "time": r.get("relative_time_description", ""),
            })

        return {
            "name": detail.get("name", ""),
            "formatted_address": detail.get("formatted_address", ""),
            "lat": loc.get("lat"),
            "lng": loc.get("lng"),
            "rating": detail.get("rating"),
            "total_ratings": detail.get("user_ratings_total", 0),
            "opening_hours": detail.get("opening_hours", {}).get("weekday_text", []),
            "reviews": reviews,
            "types": detail.get("types", []),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("google_place_details 실패")
        return {"error": str(e)}


async def google_directions(arguments: dict[str, Any], client: GoogleMapsClient) -> dict:
    """경로 탐색."""
    origin_lat = arguments.get("origin_lat")
    origin_lng = arguments.get("origin_lng")
    dest_lat = arguments.get("dest_lat")
    dest_lng = arguments.get("dest_lng")
    mode = arguments.get("mode", "transit")

    if any(v is None for v in (origin_lat, origin_lng, dest_lat, dest_lng)):
        return {"error": "origin_lat, origin_lng, dest_lat, dest_lng 파라미터가 필요합니다."}

    try:
        result = await client.directions(
            float(origin_lat), float(origin_lng),
            float(dest_lat), float(dest_lng),
            mode=mode,
        )
        routes = result.get("routes", [])
        if not routes:
            return {"error": "경로를 찾을 수 없습니다."}

        leg = routes[0].get("legs", [{}])[0]
        return {
            "distance_text": leg.get("distance", {}).get("text", ""),
            "distance_m": leg.get("distance", {}).get("value", 0),
            "duration_text": leg.get("duration", {}).get("text", ""),
            "duration_seconds": leg.get("duration", {}).get("value", 0),
            "start_address": leg.get("start_address", ""),
            "end_address": leg.get("end_address", ""),
            "mode": mode,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("google_directions 실패")
        return {"error": str(e)}


TOOL_REGISTRY: dict[str, Any] = {
    "google_maps.geocode": google_geocode,
    "google_maps.reverse_geocode": google_reverse_geocode,
    "google_maps.nearby_search": google_nearby_search,
    "google_maps.place_details": google_place_details,
    "google_maps.directions": google_directions,
}
