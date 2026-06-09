"""Unit tests for recommend_business store-count floor (ISSUE-003).

Run: PYTHONPATH=server python -m pytest server/tests/test_recommendation_scoring.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.repositories.real.recommendation import (  # noqa: E402
    MIN_RELIABLE_STORES,
    _apply_store_floor,
)


def test_store_floor_excludes_single_store_category():
    # 편의점 1점포는 per-store 아티팩트로 raw 가 비정상적으로 큼 → 제외돼야 함.
    scored = [
        {"category_name": "편의점", "store_count": 1, "raw_score": 1e10},
        {"category_name": "카페", "store_count": 50, "raw_score": 3e8},
    ]
    filtered, low_confidence = _apply_store_floor(scored)
    names = {s["category_name"] for s in filtered}
    assert "편의점" not in names
    assert "카페" in names
    assert low_confidence is False


def test_store_floor_fallback_when_all_below_threshold():
    # 전부 표본 부족 → 빈 추천 방지 위해 전체 반환 + low_confidence.
    scored = [
        {"category_name": "편의점", "store_count": 1, "raw_score": 1e10},
        {"category_name": "꽃집", "store_count": 2, "raw_score": 5e8},
    ]
    filtered, low_confidence = _apply_store_floor(scored)
    assert len(filtered) == 2
    assert low_confidence is True


def test_min_reliable_stores_constant():
    assert MIN_RELIABLE_STORES == 3
