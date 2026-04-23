"""CSV collector for resident population data (OA-15584).

Used as a fallback when the Seoul Open Data API (VwsmTrdarPopltnQq) returns ERROR-500.
Download CSV from: https://data.seoul.go.kr/dataList/OA-15584/S/1/datasetView.do

Usage:
    from server.data.etl.csv_collector import load_resident_pop_csv
    rows = load_resident_pop_csv("data/csv/OA-15584.csv", "2025Q4")
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _safe_int(value: str, default: int = 0) -> int:
    """Safely convert CSV string value to int."""
    if not value or value.strip() == "":
        return default
    try:
        return int(float(value.strip()))
    except (ValueError, TypeError):
        return default


def _parse_quarter(raw_quarter: str) -> str:
    """Convert raw quarter code to standard format: '20254' -> '2025Q4'."""
    raw = raw_quarter.strip()
    if len(raw) == 5:
        return f"{raw[:4]}Q{raw[4]}"
    return raw


# CSV column name -> (age_group, gender)
_AGE_GENDER_COLUMNS: dict[str, tuple[str, str]] = {
    "남성연령대_10_상주인구_수": ("10s", "M"),
    "남성연령대_20_상주인구_수": ("20s", "M"),
    "남성연령대_30_상주인구_수": ("30s", "M"),
    "남성연령대_40_상주인구_수": ("40s", "M"),
    "남성연령대_50_상주인구_수": ("50s", "M"),
    "남성연령대_60_이상_상주인구_수": ("60s+", "M"),
    "여성연령대_10_상주인구_수": ("10s", "F"),
    "여성연령대_20_상주인구_수": ("20s", "F"),
    "여성연령대_30_상주인구_수": ("30s", "F"),
    "여성연령대_40_상주인구_수": ("40s", "F"),
    "여성연령대_50_상주인구_수": ("50s", "F"),
    "여성연령대_60_이상_상주인구_수": ("60s+", "F"),
}


def load_resident_pop_csv(
    csv_path: str | Path,
    target_quarter: str | None = None,
) -> list[dict]:
    """Parse OA-15584 resident population CSV into DB-ready dicts.

    Args:
        csv_path: Path to the CSV file (EUC-KR encoded).
        target_quarter: If provided, filter to this quarter only (e.g., "2025Q4").
                       If None, load all quarters.

    Returns:
        List of dicts matching resident_population table schema:
        {district_code, quarter, pop_type, age_group, gender, population}
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    rows: list[dict] = []
    skipped_quarters = 0

    # Try EUC-KR first, then UTF-8
    for encoding in ("euc-kr", "cp949", "utf-8"):
        try:
            with open(csv_path, encoding=encoding) as f:
                reader = csv.DictReader(f)
                for raw_row in reader:
                    # Parse quarter
                    raw_q = raw_row.get("기준_년분기_코드", "")
                    quarter = _parse_quarter(raw_q)

                    if target_quarter and quarter != target_quarter:
                        skipped_quarters += 1
                        continue

                    district_code = raw_row.get("상권_코드", "").strip()
                    if not district_code:
                        continue

                    # Generate one row per (age_group, gender) combination
                    for col_name, (age_group, gender) in _AGE_GENDER_COLUMNS.items():
                        population = _safe_int(raw_row.get(col_name, "0"))
                        rows.append(
                            {
                                "district_code": district_code,
                                "quarter": quarter,
                                "pop_type": "resident",
                                "age_group": age_group,
                                "gender": gender,
                                "population": population,
                            }
                        )
            break  # Success — stop trying other encodings
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"Could not read CSV with any supported encoding: {csv_path}")

    logger.info(
        f"[csv_collector] Parsed {len(rows)} rows from {csv_path.name}"
        f" (quarter={target_quarter or 'all'}, skipped_other_quarters={skipped_quarters})"
    )
    return rows
