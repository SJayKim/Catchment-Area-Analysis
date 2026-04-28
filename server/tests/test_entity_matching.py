"""Unit tests for entity_matching ranking + abstention.

Covers the W1 regression fixes from 2026-04-27:
  - "X시장" query → boost 전통시장 type so the market itself wins over
    incidental districts that contain the market name in their parens.
  - Paren alias-only matches (root 미일치) damped so self-name matches win.
  - "홍대" → 발달상권 (홍대입구역(홍대)) deterministic over 골목상권 (홍대부중).
"""

from __future__ import annotations

from server.agent.utils.entity_matching import pick_best, rank_candidates


def _names(ranked) -> list[str]:
    return [c.name for c in ranked]


def test_namdaemun_market_self_match_wins() -> None:
    """\"남대문시장\" → 전통시장 본체가 alias-only paren 매치를 이긴다."""
    rows = [
        ("3110900", "삼익패션타운(남대문시장)", "골목상권"),
        ("3130012", "남대문시장(자유상가)", "전통시장"),
        ("3110901", "남대문로", "골목상권"),
    ]
    ranked = rank_candidates("남대문시장", rows)
    assert ranked, "expected at least one candidate"
    top = ranked[0]
    assert top.code == "3130012", (
        f"expected 남대문시장(자유상가) to win, got {top.name} ({top.code}) score={top.score:.3f}"
    )
    assert top.district_type == "전통시장"


def test_market_query_boosts_traditional_market_type() -> None:
    """일반 시장명 쿼리도 전통시장 type 가산을 받는다."""
    rows = [
        ("A", "광장시장", "전통시장"),
        ("B", "광장시장 인근", "골목상권"),
    ]
    ranked = rank_candidates("광장시장", rows)
    top = ranked[0]
    assert top.code == "A"
    assert top.district_type == "전통시장"


def test_hongdae_resolves_to_dev_district() -> None:
    """\"홍대\" → 홍대입구역(홍대) (발달상권) 우선."""
    rows = [
        ("3110285", "홍대부중", "골목상권"),
        ("3120103", "홍대입구역(홍대)", "발달상권"),
        ("3110286", "홍대거리", "골목상권"),
    ]
    ranked = rank_candidates("홍대", rows)
    top = ranked[0]
    assert top.code == "3120103", f"expected 홍대입구역(홍대) on top, got {top.name} ({top.code})"
    assert top.district_type == "발달상권"


def test_seongsu_two_char_query_resolves() -> None:
    """\"성수\" 2-char 쿼리: 발달상권(성수역) 우선."""
    rows = [
        ("3110127", "성수1가1동", "골목상권"),
        ("3110131", "성수동카페거리", "골목상권"),
        ("3120052", "성수역", "발달상권"),
    ]
    ranked = rank_candidates("성수", rows)
    top = ranked[0]
    assert top.code == "3120052"
    assert top.district_type == "발달상권"


def test_market_boost_does_not_affect_non_market_queries() -> None:
    """일반 쿼리에는 시장 boost 가 적용되지 않는다 (회귀 가드)."""
    rows = [
        ("A", "강남역(강남)", "발달상권"),
        ("B", "강남시장", "전통시장"),
    ]
    ranked = rank_candidates("강남", rows)
    top = ranked[0]
    assert top.code == "A", f"강남 → 발달상권이 우선이어야 함, got {top.name}"


def test_pick_best_abstention_below_floor() -> None:
    rows = [("X", "전혀다른이름", "골목상권")]
    ranked = rank_candidates("강남역", rows)
    best, alts, ambiguous = pick_best(ranked)
    assert best is None
    assert ambiguous is False
