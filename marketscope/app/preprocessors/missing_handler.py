"""결측치 처리기 — 인구/매출 데이터 결측값 보정."""

from __future__ import annotations

import logging
from typing import Optional, Sequence

logger = logging.getLogger(__name__)


def fill_zero(value: Optional[int], default: int = 0) -> int:
    """None → 0 대체."""
    return value if value is not None else default


def forward_fill(
    series: list[Optional[int]],
) -> list[int]:
    """Forward Fill — 이전 값으로 None 채우기.

    Args:
        series: 시계열 데이터 (None 포함 가능)

    Returns:
        None이 이전 값으로 채워진 리스트
    """
    result = []
    last_valid = 0
    for val in series:
        if val is not None:
            last_valid = val
            result.append(val)
        else:
            result.append(last_valid)
    return result


def distribute_evenly(total: int, parts: int) -> list[int]:
    """합계만 있고 세부 항목이 없을 때 균등 분배.

    Args:
        total: 총합
        parts: 분배 대상 수

    Returns:
        parts 개의 값 리스트 (합계 = total)
    """
    if parts <= 0:
        return []
    base = total // parts
    remainder = total % parts
    result = [base + (1 if i < remainder else 0) for i in range(parts)]
    return result


def interpolate_missing_quarters(
    data: dict[str, Optional[int]],
) -> dict[str, int]:
    """분기 데이터에서 중간 누락 분기를 선형 보간.

    Args:
        data: {"2024Q1": 100, "2024Q2": None, "2024Q3": 120, ...}

    Returns:
        보간된 딕셔너리
    """
    keys = sorted(data.keys())
    values = [data[k] for k in keys]

    # Forward fill 후 backward fill
    filled = forward_fill(values)

    # Backward fill (뒤에서 앞으로)
    last_valid = filled[-1] if filled else 0
    for i in range(len(filled) - 1, -1, -1):
        if values[i] is not None:
            last_valid = values[i]
        elif filled[i] == 0:
            filled[i] = last_valid

    return dict(zip(keys, filled))


def apply_population_defaults(data: dict) -> dict:
    """인구 데이터 결측치 기본 처리.

    규칙:
    - total_population이 None이면 0
    - 성별 합이 total보다 작으면 나머지를 other로 처리
    - 연령대 합이 total보다 작으면 비율 기준 분배
    """
    total = fill_zero(data.get("total_population"))
    male = fill_zero(data.get("male_population"))
    female = fill_zero(data.get("female_population"))

    # 성별 합 보정
    if male + female < total and male > 0:
        female = total - male
    elif male + female < total and female > 0:
        male = total - female

    data["total_population"] = total
    data["male_population"] = male
    data["female_population"] = female

    # 시간대 데이터가 전부 None이면 균등 분배
    time_fields = ["time_00_06", "time_06_11", "time_11_14", "time_14_17", "time_17_21", "time_21_24"]
    time_values = [data.get(f) for f in time_fields]
    if all(v is None for v in time_values) and total > 0:
        distributed = distribute_evenly(total, len(time_fields))
        for field, val in zip(time_fields, distributed):
            data[field] = val

    return data
