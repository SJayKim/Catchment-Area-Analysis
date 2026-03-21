"""좌표 변환기 — TM/UTM-K → WGS84 등 좌표계 변환."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from pyproj import Transformer

logger = logging.getLogger(__name__)

# 서울 범위 (WGS84)
SEOUL_LAT_RANGE = (37.40, 37.72)
SEOUL_LNG_RANGE = (126.75, 127.20)


@lru_cache(maxsize=16)
def _get_transformer(from_epsg: int, to_epsg: int = 4326) -> Transformer:
    """pyproj Transformer를 캐싱하여 재사용."""
    return Transformer.from_crs(f"EPSG:{from_epsg}", f"EPSG:{to_epsg}", always_xy=True)


def tm_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """TM (EPSG:2097) → WGS84 (EPSG:4326) 변환.

    Returns:
        (latitude, longitude) 소수점 6자리 (≒0.1m 정밀도)
    """
    transformer = _get_transformer(2097, 4326)
    lng, lat = transformer.transform(x, y)
    return round(lat, 6), round(lng, 6)


def utmk_to_wgs84(x: float, y: float, *, epsg: int = 5178) -> tuple[float, float]:
    """UTM-K (EPSG:5178 또는 5179) → WGS84 변환.

    Args:
        x: X 좌표 (easting)
        y: Y 좌표 (northing)
        epsg: 입력 좌표계 (5178 또는 5179)

    Returns:
        (latitude, longitude)
    """
    if epsg not in (5178, 5179):
        raise ValueError(f"지원하지 않는 EPSG: {epsg}. 5178 또는 5179만 가능")
    transformer = _get_transformer(epsg, 4326)
    lng, lat = transformer.transform(x, y)
    return round(lat, 6), round(lng, 6)


def katec_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """KATEC (EPSG:5174) → WGS84 변환 (카텍 좌표계)."""
    transformer = _get_transformer(5174, 4326)
    lng, lat = transformer.transform(x, y)
    return round(lat, 6), round(lng, 6)


def is_in_seoul(lat: float, lng: float) -> bool:
    """WGS84 좌표가 서울 범위 내인지 검증."""
    return (
        SEOUL_LAT_RANGE[0] <= lat <= SEOUL_LAT_RANGE[1]
        and SEOUL_LNG_RANGE[0] <= lng <= SEOUL_LNG_RANGE[1]
    )


def auto_convert_to_wgs84(
    x: float, y: float, *, source_crs: Optional[str] = None
) -> tuple[float, float]:
    """좌표계를 자동 감지하여 WGS84로 변환.

    Args:
        x, y: 입력 좌표
        source_crs: "tm", "utmk", "utmk5179", "katec", "wgs84", None(자동감지)

    Returns:
        (latitude, longitude) in WGS84
    """
    if source_crs:
        crs = source_crs.lower()
        if crs == "wgs84":
            return (round(y, 6), round(x, 6)) if x > 100 else (round(x, 6), round(y, 6))
        elif crs == "tm":
            return tm_to_wgs84(x, y)
        elif crs == "utmk":
            return utmk_to_wgs84(x, y, epsg=5178)
        elif crs == "utmk5179":
            return utmk_to_wgs84(x, y, epsg=5179)
        elif crs == "katec":
            return katec_to_wgs84(x, y)
        else:
            raise ValueError(f"알 수 없는 좌표계: {source_crs}")

    # 자동 감지: WGS84 범위인지 확인
    if 33 <= x <= 43 and 124 <= y <= 132:
        return round(x, 6), round(y, 6)
    if 33 <= y <= 43 and 124 <= x <= 132:
        return round(y, 6), round(x, 6)

    # TM 좌표 범위 (한반도: x 125,000~350,000, y 30,000~65,0000)
    if 100_000 < x < 400_000 and 100_000 < y < 700_000:
        return tm_to_wgs84(x, y)

    # UTM-K 범위 (훨씬 큰 값: x ~900,000~1,100,000, y ~1,700,000~2,100,000)
    if 800_000 < x < 1_200_000 and 1_500_000 < y < 2_200_000:
        return utmk_to_wgs84(x, y)

    logger.warning("좌표 자동 감지 실패: x=%.2f, y=%.2f. WGS84로 해석 시도", x, y)
    return round(x, 6), round(y, 6)
