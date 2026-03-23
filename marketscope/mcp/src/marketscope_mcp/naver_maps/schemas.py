"""Naver Maps MCP 서버 Pydantic 스키마."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class NaverGeoResult(BaseModel):
    lat: float
    lng: float
    road_address: str = ""
    jibun_address: str = ""


class NaverLocalPlace(BaseModel):
    title: str = ""
    address: str = ""
    road_address: str = ""
    category: str = ""
    telephone: str = ""
    link: str = ""
    mapx: int = 0
    mapy: int = 0


class NaverDirectionResult(BaseModel):
    distance_m: int = 0
    duration_ms: int = 0
    toll_fare: int = 0
    fuel_price: int = 0
    path: list[list[float]] = []
