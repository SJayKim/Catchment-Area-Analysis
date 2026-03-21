"""Google Maps MCP 서버 Pydantic 스키마."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class GeocodingResult(BaseModel):
    lat: float
    lng: float
    formatted_address: str = ""
    place_id: str = ""


class NearbyPlace(BaseModel):
    name: str = ""
    address: str = ""
    lat: float = 0.0
    lng: float = 0.0
    rating: Optional[float] = None
    total_ratings: int = 0
    place_id: str = ""
    types: list[str] = []
    distance_m: Optional[float] = None


class PlaceDetail(BaseModel):
    name: str = ""
    formatted_address: str = ""
    lat: float = 0.0
    lng: float = 0.0
    rating: Optional[float] = None
    total_ratings: int = 0
    opening_hours: Optional[dict[str, Any]] = None
    reviews: list[dict[str, Any]] = []
    types: list[str] = []


class DirectionResult(BaseModel):
    distance_text: str = ""
    distance_m: int = 0
    duration_text: str = ""
    duration_seconds: int = 0
    steps: list[dict[str, str]] = []
