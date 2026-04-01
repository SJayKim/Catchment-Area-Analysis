"""SHP file loader — reads OA-15560 SHP and produces loader-compatible dicts.

Usage:
    from server.data.etl.shp_collector import load_districts_from_shp
    rows = load_districts_from_shp("data/shp/OA-15560.shp", "2025Q4")
"""

from __future__ import annotations

import logging
from pathlib import Path

from server.data.etl.transformers import DISTRICT_TYPE_MAP

logger = logging.getLogger(__name__)

# SHP column names can be truncated to 10 chars — map target to possible names
COL_MAP: dict[str, list[str]] = {
    "TRDAR_CD": ["TRDAR_CD"],
    "TRDAR_CD_NM": ["TRDAR_CD_NM", "TRDAR_CD_N"],
    "TRDAR_SE_CD": ["TRDAR_SE_CD", "TRDAR_SE_C"],
    "SIGNGU_CD": ["SIGNGU_CD", "SIGNGU_CD_"],
    "ADSTRD_CD": ["ADSTRD_CD", "ADSTRD_CD_"],
}


def _resolve_col(target: str, columns: list[str]) -> str | None:
    """Find the actual column name in the dataframe for a target field."""
    candidates = COL_MAP.get(target, [target])
    for c in candidates:
        if c in columns:
            return c
    return None


def load_districts_from_shp(shp_path: str | Path, data_quarter: str) -> list[dict]:
    """Read SHP file and return list of dicts compatible with DataLoader.upsert_districts().

    Coordinates are kept in EPSG:5181 — PostGIS ST_Transform converts to 4326.
    """
    import geopandas as gpd

    shp_path = Path(shp_path)
    if not shp_path.exists():
        raise FileNotFoundError(f"SHP file not found: {shp_path}")

    gdf = gpd.read_file(shp_path)
    logger.info(f"[shp] Loaded {len(gdf)} features, CRS={gdf.crs}, columns={gdf.columns.tolist()}")

    # Ensure EPSG:5181
    if gdf.crs is not None and gdf.crs.to_epsg() != 5181:
        logger.warning(f"[shp] CRS is {gdf.crs}, reprojecting to EPSG:5181")
        gdf = gdf.to_crs(epsg=5181)

    cols = gdf.columns.tolist()
    col_code = _resolve_col("TRDAR_CD", cols)
    col_name = _resolve_col("TRDAR_CD_NM", cols)
    col_type = _resolve_col("TRDAR_SE_CD", cols)
    col_gu = _resolve_col("SIGNGU_CD", cols)
    col_dong = _resolve_col("ADSTRD_CD", cols)

    if not col_code:
        raise ValueError(f"Cannot find TRDAR_CD column in SHP. Available: {cols}")

    rows: list[dict] = []
    skipped = 0

    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            skipped += 1
            continue

        # Handle MultiPolygon → extract largest polygon
        if geom.geom_type == "MultiPolygon":
            geom = max(geom.geoms, key=lambda g: g.area)

        if geom.geom_type != "Polygon":
            logger.warning(f"[shp] Row {idx}: unexpected geom type {geom.geom_type}, skipping")
            skipped += 1
            continue

        boundary_wkt = geom.wkt
        center_wkt = f"POINT({geom.centroid.x} {geom.centroid.y})"

        code = str(row[col_code]) if col_code else ""
        name = str(row[col_name]) if col_name else ""
        type_code = str(row[col_type]) if col_type else ""
        gu_code = str(row[col_gu]) if col_gu else None
        dong_code = str(row[col_dong]) if col_dong else None

        # Map type code to Korean name
        district_type = DISTRICT_TYPE_MAP.get(type_code, type_code)

        rows.append({
            "district_code": code,
            "district_name": name,
            "district_type": district_type,
            "boundary_wkt": boundary_wkt,
            "center_wkt": center_wkt,
            "gu_code": gu_code if gu_code and gu_code != "nan" else None,
            "dong_code": dong_code if dong_code and dong_code != "nan" else None,
            "data_quarter": data_quarter,
        })

    if skipped:
        logger.warning(f"[shp] Skipped {skipped} features with empty/invalid geometry")
    logger.info(f"[shp] Produced {len(rows)} district rows from SHP")
    return rows
