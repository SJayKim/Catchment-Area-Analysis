"""Entity-matching utilities for GAP-A (district fuzzy matching).

Ranking + abstention helpers that keep the real/mock repositories
consistent. Uses stdlib ``difflib`` only — no extra dependencies — since
we only compare short Korean district names (avg 6 chars) against a
1,650-row table. For that scale the ratio is effectively free.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

# Abstention thresholds (tuned empirically for 1,650 Seoul districts).
# - TOP1_MIN: absolute floor — below this we treat the candidate as unmatched.
# - CLOSE_DELTA: if Top1 - Top2 is within this band, we surface ambiguity.
TOP1_MIN = 0.55
CLOSE_DELTA = 0.08

# district_type priority — used to break ties AND baked into the score so that
# when users say "홍대" we prefer the 발달상권 (홍대입구역(홍대)) over incidental
# 골목상권 names like 홍대부중 (a middle-school area). Delta per rank = 0.05.
TYPE_PRIORITY: dict[str, int] = {
    "발달상권": 4,
    "골목상권": 2,
    "관광특구": 2,
    "전통시장": 1,
}
# Type boost per rank. 발달상권 (rank 4) = +0.20 — large enough that when the
# raw-prefix scores are close ("홍대" vs 홍대부중 / 홍대입구역), the busier
# commercial district wins.
_TYPE_BOOST_PER_RANK = 0.05


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    """One ranked candidate for a single user-provided word."""

    code: str
    name: str
    score: float
    district_type: str | None = None

    def to_dict(self) -> dict:
        payload: dict = {"code": self.code, "name": self.name, "score": round(self.score, 4)}
        if self.district_type:
            payload["type"] = self.district_type
        return payload


def _string_similarity(query: str, name: str) -> float:
    """Similarity score in [0, 1].

    Tiered scoring:
    - exact = 1.0
    - prefix = 0.55 + 0.25 × coverage  (short query vs long name still clears
      the TOP1_MIN=0.55 floor; type_boost then decides the winner)
    - substring (contained) = 0.55 + 0.15 × coverage
    - reverse contained (query contains full name, name≥2) = 0.60
    - otherwise fallback to SequenceMatcher ratio × 0.5

    Prefix coverage is ``len(query) / len(name)`` so *longer* names are not
    rewarded purely for being longer; ambiguity between commercial and
    incidental districts is left to ``TYPE_PRIORITY`` bonuses.
    """
    if not query or not name:
        return 0.0
    query = query.strip()
    name = name.strip()
    if not query or not name:
        return 0.0
    if query == name:
        return 1.0

    if name.startswith(query):
        coverage = len(query) / max(len(name), 1)
        return 0.55 + 0.25 * coverage

    if query in name:
        # Internal substring — slightly weaker than prefix.
        coverage = len(query) / max(len(name), 1)
        return 0.55 + 0.15 * coverage

    if name in query and len(name) >= 2:
        return 0.60

    # No direct containment — treat as fuzzy signal only.
    return SequenceMatcher(None, query, name).ratio() * 0.5


def rank_candidates(
    query: str,
    rows: list[tuple[str, str, str | None]],
) -> list[RankedCandidate]:
    """Rank DB rows for a single query word.

    rows: list of ``(district_code, district_name, district_type)``.
    Returns candidates sorted by final score desc. Final score =
    ``_string_similarity`` + ``TYPE_PRIORITY × _TYPE_BOOST_PER_RANK``. The
    type boost makes "홍대" resolve to "홍대입구역(홍대)" (발달상권) rather than
    "홍대부중" (골목상권) when both share the same prefix similarity.
    """
    ranked: list[RankedCandidate] = []
    for code, name, dtype in rows:
        sim = _string_similarity(query, name)
        if sim <= 0:
            continue
        type_rank = TYPE_PRIORITY.get(dtype or "", 0)
        final = min(1.0, sim + _TYPE_BOOST_PER_RANK * type_rank)
        ranked.append(RankedCandidate(code=code, name=name, score=final, district_type=dtype))

    # Secondary sort on type priority keeps deterministic ordering when the
    # final score clamps to 1.0 for several candidates.
    def _sort_key(c: RankedCandidate) -> tuple[float, int]:
        return (c.score, TYPE_PRIORITY.get(c.district_type or "", 0))

    ranked.sort(key=_sort_key, reverse=True)
    return ranked


def pick_best(
    candidates: list[RankedCandidate],
) -> tuple[RankedCandidate | None, list[RankedCandidate], bool]:
    """Select the best candidate and detect abstention.

    Returns ``(best, alternatives, is_ambiguous)``:
    - ``best`` is ``None`` when no candidate clears ``TOP1_MIN``.
    - ``is_ambiguous`` is True when Top1 clears the floor but Top2 is
      within ``CLOSE_DELTA`` of Top1 — the caller should surface both.
    - ``alternatives`` contains up to two runner-ups to help the UI
      disambiguate (always excludes ``best``).
    """
    if not candidates:
        return None, [], False
    top = candidates[0]
    if top.score < TOP1_MIN:
        return None, candidates[:2], False

    # Same-code duplicates can appear when the same district matches multiple
    # query words. Dedupe alternatives by code.
    alternatives: list[RankedCandidate] = []
    seen = {top.code}
    for c in candidates[1:]:
        if c.code in seen:
            continue
        alternatives.append(c)
        seen.add(c.code)
        if len(alternatives) >= 2:
            break

    is_ambiguous = False
    if alternatives and (top.score - alternatives[0].score) < CLOSE_DELTA:
        is_ambiguous = True
    return top, alternatives, is_ambiguous
