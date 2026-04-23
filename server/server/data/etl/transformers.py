"""Transform raw API responses to DB-ready dicts.

Pure functions — no I/O, easily testable.
Coordinate transform (EPSG:5181→4326) is done in SQL via PostGIS ST_Transform.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 상권 구분 코드 → 한글명
DISTRICT_TYPE_MAP = {
    "A": "골목상권",
    "D": "발달상권",
    "R": "전통시장",
    "G": "관광특구",
    "U": "관광특구",
}

# 시간대 매핑: API 컬럼 suffix → time_slot 값 (시간대 시작 시각)
# API uses two naming patterns depending on the endpoint:
#   Pattern A: TMZON_1_FLPOP_CO (VwsmTrdarFlpopQq with year/quarter split)
#   Pattern B: TMZON_00_06_FLPOP_CO (VwsmTrdarFlpopQq with STDR_YYQU_CD)
TIME_SLOTS = {
    "00_06": 0,
    "06_11": 6,
    "11_14": 11,
    "14_17": 14,
    "17_21": 17,
    "21_24": 21,
}

# Legacy pattern mapping (for backward compatibility)
_LEGACY_TIME_SLOTS = {
    "1": 0,
    "2": 6,
    "3": 11,
    "4": 14,
    "5": 17,
    "6": 21,
}


def _safe_int(value: object, default: int = 0) -> int:
    """Safely convert value to int."""
    if value is None:
        return default
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return default


def _safe_bigint(value: object) -> int | None:
    """Safely convert value to int, returning None for missing."""
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return None


def _build_polygon_wkt(raw: dict) -> str | None:
    """Build WKT POLYGON from XCORD_*/YCORD_* coordinate columns.

    The API provides up to ~30 coordinate pairs as individual columns:
    XCORD_1, YCORD_1, XCORD_2, YCORD_2, ...
    Coordinates are in EPSG:5181 (will be transformed in SQL).
    """
    coords: list[tuple[float, float]] = []
    for i in range(1, 51):  # up to 50 points
        x_key = f"XCORD_{i:02d}" if i >= 10 else f"XCORD_{i}"
        y_key = f"YCORD_{i:02d}" if i >= 10 else f"YCORD_{i}"
        # Try both naming patterns
        x = raw.get(x_key) or raw.get(f"XCORD_{i}")
        y = raw.get(y_key) or raw.get(f"YCORD_{i}")
        if x is None or y is None:
            break
        try:
            xf, yf = float(x), float(y)
            if xf == 0 or yf == 0:
                break
            coords.append((xf, yf))
        except (ValueError, TypeError):
            break

    if len(coords) < 3:
        return None

    # Close the ring if needed
    if coords[0] != coords[-1]:
        coords.append(coords[0])

    coord_str = ", ".join(f"{x} {y}" for x, y in coords)
    return f"POLYGON(({coord_str}))"


def transform_district(raw: dict) -> dict:
    """Transform raw district API row to districts table format.

    Handles both polygon API (VwsmTrdarSelngW) and store change API (VwsmTrdarStorQq) formats.
    """
    code = str(raw.get("TRDAR_CD", ""))
    type_code = str(raw.get("TRDAR_SE_CD", ""))

    # Build WKT for polygon (EPSG:5181, transformed in loader)
    polygon_wkt = _build_polygon_wkt(raw)

    # Center point
    cx = raw.get("XCNTS_VALUE")
    cy = raw.get("YDNTS_VALUE")
    center_wkt = None
    if cx and cy:
        try:
            center_wkt = f"POINT({float(cx)} {float(cy)})"
        except (ValueError, TypeError):
            pass

    # Quarter: "STDR_YR_CD" + "Q" + "STDR_QU_CD" or from STDR_YYQU_CD
    year = raw.get("STDR_YR_CD", "")
    qu = raw.get("STDR_QU_CD", "")
    if year and qu:
        quarter = f"{year}Q{qu}"
    elif raw.get("STDR_YYQU_CD"):
        yyqu = str(raw["STDR_YYQU_CD"])
        quarter = f"{yyqu[:4]}Q{yyqu[4:]}" if len(yyqu) >= 5 else yyqu
    else:
        quarter = ""

    return {
        "district_code": code,
        "district_name": str(raw.get("TRDAR_CD_NM", "")),
        "district_type": DISTRICT_TYPE_MAP.get(type_code, type_code),
        "boundary_wkt": polygon_wkt,  # WKT string, SRID=5181 (None if from store change API)
        "center_wkt": center_wkt,  # WKT string, SRID=5181 (None if from store change API)
        "gu_code": str(raw.get("SIGNGU_CD", "")) or None,
        "dong_code": str(raw.get("ADSTRD_CD", "")) or None,
        "data_quarter": quarter,
    }


def transform_floating_pop(raw: dict) -> list[dict]:
    """Unpivot floating population time zone columns into separate rows.

    Returns up to 6 rows per input row (one per time slot).
    """
    code = str(raw.get("TRDAR_CD", ""))
    year = str(raw.get("STDR_YR_CD", ""))
    qu = str(raw.get("STDR_QU_CD", ""))
    quarter = f"{year}Q{qu}"

    # Demographic aggregates (same for all time slots)
    male_pop = _safe_int(raw.get("ML_FLPOP_CO"))
    female_pop = _safe_int(raw.get("FML_FLPOP_CO"))
    age_10 = _safe_int(raw.get("AGRDE_10_FLPOP_CO"))
    age_20 = _safe_int(raw.get("AGRDE_20_FLPOP_CO"))
    age_30 = _safe_int(raw.get("AGRDE_30_FLPOP_CO"))
    age_40 = _safe_int(raw.get("AGRDE_40_FLPOP_CO"))
    age_50 = _safe_int(raw.get("AGRDE_50_FLPOP_CO"))
    age_60 = _safe_int(raw.get("AGRDE_60_ABOVE_FLPOP_CO"))
    total = _safe_int(raw.get("TOT_FLPOP_CO"))

    rows = []
    for slot_key, slot_value in TIME_SLOTS.items():
        col = f"TMZON_{slot_key}_FLPOP_CO"
        pop = _safe_int(raw.get(col))
        # Fallback to legacy pattern (TMZON_1_FLPOP_CO)
        if pop == 0:
            legacy_key = {v: k for k, v in _LEGACY_TIME_SLOTS.items()}.get(slot_value)
            if legacy_key:
                pop = _safe_int(raw.get(f"TMZON_{legacy_key}_FLPOP_CO"))
        # Distribute demographics proportionally across time slots
        ratio = pop / total if total > 0 else 0
        rows.append(
            {
                "district_code": code,
                "quarter": quarter,
                "time_slot": slot_value,
                "total_pop": pop,
                "male_pop": round(male_pop * ratio),
                "female_pop": round(female_pop * ratio),
                "age_10_pop": round(age_10 * ratio),
                "age_20_pop": round(age_20 * ratio),
                "age_30_pop": round(age_30 * ratio),
                "age_40_pop": round(age_40 * ratio),
                "age_50_pop": round(age_50 * ratio),
                "age_60_plus_pop": round(age_60 * ratio),
            }
        )

    return rows


def transform_estimated_sales(raw: dict) -> dict:
    """Transform estimated sales API row.

    The ``*_AMT`` fields (THSMON_SELNG_AMT, MDW_SELNG_AMT, ...) are raw
    quarterly aggregates in won per Seoul OpenData FAQ. They are stored
    verbatim; conversion to monthly happens in real-mode repositories.
    """
    year = str(raw.get("STDR_YR_CD", ""))
    qu = str(raw.get("STDR_QU_CD", ""))

    return {
        "district_code": str(raw.get("TRDAR_CD", "")),
        "category_code": str(raw.get("SVC_INDUTY_CD", "")),
        "category_name": str(raw.get("SVC_INDUTY_CD_NM", "")),
        "quarter": f"{year}Q{qu}",
        "monthly_sales": _safe_bigint(raw.get("THSMON_SELNG_AMT")),
        "sales_count": _safe_int(raw.get("THSMON_SELNG_CO")) or None,
        "weekday_sales": _safe_bigint(raw.get("MDW_SELNG_AMT")),
        "weekend_sales": _safe_bigint(raw.get("WND_SELNG_AMT")),
        "male_sales": _safe_bigint(raw.get("ML_SELNG_AMT")),
        "female_sales": _safe_bigint(raw.get("FML_SELNG_AMT")),
        "age_10_sales": _safe_bigint(raw.get("AGRDE_10_SELNG_AMT")),
        "age_20_sales": _safe_bigint(raw.get("AGRDE_20_SELNG_AMT")),
        "age_30_sales": _safe_bigint(raw.get("AGRDE_30_SELNG_AMT")),
        "age_40_sales": _safe_bigint(raw.get("AGRDE_40_SELNG_AMT")),
        "age_50_sales": _safe_bigint(raw.get("AGRDE_50_SELNG_AMT")),
        "age_60_plus_sales": _safe_bigint(raw.get("AGRDE_60_ABOVE_SELNG_AMT")),
        "time_1_sales": _safe_bigint(raw.get("TMZON_1_SELNG_AMT")),
        "time_2_sales": _safe_bigint(raw.get("TMZON_2_SELNG_AMT")),
        "time_3_sales": _safe_bigint(raw.get("TMZON_3_SELNG_AMT")),
        "time_4_sales": _safe_bigint(raw.get("TMZON_4_SELNG_AMT")),
        "time_5_sales": _safe_bigint(raw.get("TMZON_5_SELNG_AMT")),
        "time_6_sales": _safe_bigint(raw.get("TMZON_6_SELNG_AMT")),
    }


def transform_store(raw: dict) -> dict:
    """Transform store info API row."""
    year = str(raw.get("STDR_YR_CD", ""))
    qu = str(raw.get("STDR_QU_CD", ""))

    return {
        "district_code": str(raw.get("TRDAR_CD", "")),
        "category_code": str(raw.get("SVC_INDUTY_CD", "")),
        "category_name": str(raw.get("SVC_INDUTY_CD_NM", "")),
        "quarter": f"{year}Q{qu}",
        "store_count": _safe_int(raw.get("STOR_CO")) or None,
        "open_count": _safe_int(raw.get("OPBIZ_STOR_CO")) or None,
        "close_count": _safe_int(raw.get("CLSBIZ_STOR_CO")) or None,
        "franchise_count": _safe_int(raw.get("FRC_STOR_CO")) or None,
    }


def transform_resident_pop(raw: dict, pop_type: str = "resident") -> list[dict]:
    """Transform resident/worker population API row into narrow rows.

    Generates rows for each (age_group, gender) combination.
    """
    code = str(raw.get("TRDAR_CD", ""))
    year = str(raw.get("STDR_YR_CD", ""))
    qu = str(raw.get("STDR_QU_CD", ""))
    quarter = f"{year}Q{qu}"

    age_groups = {
        "10s": ("AGRDE_10", "AGRDE_10"),
        "20s": ("AGRDE_20", "AGRDE_20"),
        "30s": ("AGRDE_30", "AGRDE_30"),
        "40s": ("AGRDE_40", "AGRDE_40"),
        "50s": ("AGRDE_50", "AGRDE_50"),
        "60s+": ("AGRDE_60_ABOVE", "AGRDE_60_ABOVE"),
    }

    # Column suffix depends on pop_type
    if pop_type == "resident":
        male_suffix = "MAG_POPLTN_CO"  # 남성 상주인구
        female_suffix = "FAG_POPLTN_CO"  # 여성 상주인구
    else:  # worker
        male_suffix = "MAG_POPLTN_CO"
        female_suffix = "FAG_POPLTN_CO"

    rows = []
    for age_label, (age_prefix, _) in age_groups.items():
        # Male
        male_key = f"{age_prefix}_{male_suffix}"
        male_val = _safe_int(raw.get(male_key))
        rows.append(
            {
                "district_code": code,
                "quarter": quarter,
                "pop_type": pop_type,
                "age_group": age_label,
                "gender": "M",
                "population": male_val,
            }
        )
        # Female
        female_key = f"{age_prefix}_{female_suffix}"
        female_val = _safe_int(raw.get(female_key))
        rows.append(
            {
                "district_code": code,
                "quarter": quarter,
                "pop_type": pop_type,
                "age_group": age_label,
                "gender": "F",
                "population": female_val,
            }
        )

    return rows
