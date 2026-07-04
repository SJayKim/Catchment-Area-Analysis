"""Unit tests for recommend_business store-count floor (ISSUE-003).

Run: PYTHONPATH=server python -m pytest server/tests/test_recommendation_scoring.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.repositories.real.recommendation import (  # noqa: E402
    MIN_RELIABLE_STORES,
    SCORE_BAND_FLAT,
    SCORE_BAND_MAX,
    SCORE_BAND_MIN,
    _apply_store_floor,
    _band_scores,
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


def test_band_scores_top_is_not_pinned_at_100():
    # min-max 100 스케일은 1위를 항상 100.0 에 고정(절대 확신 오독) → 유계 밴드로 교체.
    scores = _band_scores([3e8, 2e8, 1e8])
    assert scores[0] == SCORE_BAND_MAX < 100.0
    assert scores[-1] == SCORE_BAND_MIN > 0.0


def test_band_scores_flat_when_single_or_tied():
    # 기존 구현은 단일 카테고리 score 가 0.0 이 됐다 (spread=1 트릭의 버그성 엣지).
    assert _band_scores([5e8]) == [SCORE_BAND_FLAT]
    assert _band_scores([5e8, 5e8]) == [SCORE_BAND_FLAT, SCORE_BAND_FLAT]
    assert _band_scores([]) == []


def test_band_scores_preserve_ranking():
    raw = [1e8, 9e8, 3e8, 7e8]
    banded = _band_scores(raw)
    assert [b for _, b in sorted(zip(raw, banded, strict=True), reverse=True)] == sorted(banded, reverse=True)
    assert all(SCORE_BAND_MIN <= b <= SCORE_BAND_MAX for b in banded)
