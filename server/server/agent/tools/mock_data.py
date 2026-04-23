"""Mock data for Phase 1A — 5 districts with realistic Seoul commercial data.

All data shapes match the return types of the real DB-backed tool functions.
Data is loaded from JSON files in the ``mock/`` directory.
"""

from server.agent.tools.mock import (
    get_districts,
    get_estimated_sales,
    get_floating_population,
    get_population_info,
    get_recommendations_data,
    get_store_history,
    get_store_info,
)

MOCK_QUARTER = "2025Q3"

# ---------------------------------------------------------------------------
# Public data accessors (same API as before — keeps mock repo files unchanged)
# ---------------------------------------------------------------------------

DISTRICTS = get_districts()
FLOATING_POPULATION = get_floating_population()
ESTIMATED_SALES = get_estimated_sales()
STORE_INFO = get_store_info()
POPULATION_INFO = get_population_info()
STORE_HISTORY = get_store_history()

_recs = get_recommendations_data()
MOCK_RECOMMENDATIONS = _recs["districts"]
_DEFAULT_RECOMMENDATIONS = _recs["default"]

# ---------------------------------------------------------------------------
# Compare districts helper
# ---------------------------------------------------------------------------


def get_compare_data(district_codes: list[str]) -> dict:
    """Build comparison result from mock data."""
    results = {}
    for code in district_codes:
        fp = FLOATING_POPULATION.get(code)
        si = STORE_INFO.get(code)
        es = ESTIMATED_SALES.get(code)
        d = DISTRICTS.get(code)

        if not d:
            results[code] = {"district_code": code, "error": "데이터 없음"}
            continue

        # Find main age group
        main_age = "-"
        if fp:
            age_dist = fp["age_distribution"]
            main_age = max(age_dist, key=age_dist.get)

        results[code] = {
            "district_code": code,
            "district_name": d["name"],
            "floating_pop": fp["daily_avg"] if fp else 0,
            "main_age": main_age,
            "store_count": si["total_stores"] if si else 0,
            "close_rate": si["close_rate"] if si else 0.0,
            "monthly_sales": es["total_monthly_sales"] if es else 0,
            "status": es["trend"] if es else "stable",
            "quarter": MOCK_QUARTER,
        }

    return {"districts": results, "district_codes": district_codes}


# ---------------------------------------------------------------------------
# Recommend business helper
# ---------------------------------------------------------------------------


def get_recommendations(district_code: str, budget: int | None = None) -> dict:
    """Return mock recommendations for a district."""
    if district_code in MOCK_RECOMMENDATIONS:
        result = {**MOCK_RECOMMENDATIONS[district_code]}
    else:
        result = {"district_code": district_code, **_DEFAULT_RECOMMENDATIONS}

    # Apply budget filter
    if budget:
        filtered = [r for r in result["recommendations"] if r.get("startup_cost", 0) <= budget]
        if filtered:
            for i, rec in enumerate(filtered, 1):
                rec["rank"] = i
            result["recommendations"] = filtered

    return result


# ---------------------------------------------------------------------------
# GeoJSON feature collection builder
# ---------------------------------------------------------------------------


def get_mock_geojson() -> dict:
    """Build GeoJSON FeatureCollection from mock districts."""
    features = []
    for code, d in DISTRICTS.items():
        coords = d["polygon"]
        feature = {
            "type": "Feature",
            "properties": {
                "district_code": code,
                "district_name": d["name"],
                "district_type": d["type"],
                "data_quarter": d["quarter"],
                "center": [d["center"]["lng"], d["center"]["lat"]],
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords],
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def get_mock_district_list(search: str | None = None, district_type: str | None = None) -> list[dict]:
    """Return filtered list of mock districts."""
    results = []
    for code, d in DISTRICTS.items():
        if search and search.lower() not in d["name"].lower():
            continue
        if district_type and d["type"] != district_type:
            continue
        results.append(
            {
                "district_code": code,
                "district_name": d["name"],
                "district_type": d["type"],
                "data_quarter": d["quarter"],
                "center_lng": d["center"]["lng"],
                "center_lat": d["center"]["lat"],
            }
        )
    return results
