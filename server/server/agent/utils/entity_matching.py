"""Entity-matching utilities for GAP-A (district fuzzy matching).

Ranking + abstention helpers that keep the real/mock repositories
consistent. Uses stdlib ``difflib`` only — no extra dependencies — since
we only compare short Korean district names (avg 6 chars) against a
1,650-row table. For that scale the ratio is effectively free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

# Abstention thresholds (tuned empirically for 1,650 Seoul districts).
# - TOP1_MIN: absolute floor — below this we treat the candidate as unmatched.
# - CLOSE_DELTA: if Top1 - Top2 is within this band, we surface ambiguity.
TOP1_MIN = 0.55
CLOSE_DELTA = 0.08

# district_type priority — used to break ties AND baked into the score so that
# when users say "홍대" we prefer the 발달상권 (홍대입구역(홍대)) over incidental
# 골목상권 names like 홍대부중 (a middle-school area).
TYPE_PRIORITY: dict[str, int] = {
    "발달상권": 4,
    "골목상권": 2,
    "관광특구": 2,
    "전통시장": 1,
}
# Type boost per rank. 발달상권 (rank 4) = +0.20.
_TYPE_BOOST_PER_RANK = 0.05

# Seoul OpenData 발달상권 명명 규칙: 본명 뒤에 "(별칭)" 을 붙인다
# (예: "홍대입구역(홍대)", "상수역(홍대)"). 사용자가 별칭으로 질의하면
# 괄호 안 토큰이 exact 매치되므로, 이 신호를 가장 강한 확증으로 취급.
_PAREN_EXACT_BONUS = 0.15
# 괄호 제거 본명이 query prefix 와 일치하는 경우의 소폭 보너스.
# (홍대입구역(홍대) 의 "홍대입구역" 이 "홍대" 로 시작)
_ROOT_PREFIX_BONUS = 0.05
# Self-name guard: paren bonus 가 self-match 을 이기는 경우를 막는다.
# 예: query "남대문시장" 일 때 ``삼익패션타운(남대문시장)`` 의 paren_exact 가
# self-match 인 ``남대문시장(자유상가)`` 보다 높아질 수 있음 — root 가 query 와
# 무관한(=alias-only) 매치일 때만 bonus 를 절반으로 낮춘다.
_PAREN_ALIAS_ONLY_DAMP = 0.5

# Traditional-market query suffix → 전통시장 type 가산점.
# "X시장" 형태 쿼리는 사용자가 명백히 시장(market) 자체를 가리키므로,
# TYPE_PRIORITY(전통시장=1) 의 낮은 가중치를 보정한다.
_MARKET_TYPE_BOOST = 0.15
_MARKET_QUERY_RE = re.compile(r".{2,}시장$")

_PAREN_TOKEN_RE = re.compile(r"\(([^()]+)\)")


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


def _paren_and_root_bonus(query: str, name: str) -> float:
    """Extra boost when ``query`` matches the parenthesised alias or the
    pre-paren root of ``name``.

    Seoul OpenData 발달상권 이름은 "본명(별칭)" 형식이다. 사용자가 별칭으로
    질의할 때 괄호 내부 토큰이 exact 매치되면 "바로 이 상권" 이라는 확증
    신호이므로 + ``_PAREN_EXACT_BONUS``. 본명이 prefix 매치면 소폭 추가.

    Guard: query 가 paren 토큰에는 매치되지만 root 와는 무관할 때
    (예: "남대문시장" → ``삼익패션타운(남대문시장)``), bonus 를 절반으로
    낮춰 self-name 매치(``남대문시장(자유상가)``) 가 우선되도록 한다.
    """
    q = query.strip()
    if not q or "(" not in name:
        return 0.0
    bonus = 0.0
    paren_hit = False
    for match in _PAREN_TOKEN_RE.finditer(name):
        token = match.group(1).strip()
        if token == q:
            paren_hit = True
            bonus += _PAREN_EXACT_BONUS
            break
    root = _PAREN_TOKEN_RE.sub("", name).strip()
    root_matches = bool(root and root != name and root.startswith(q))
    if root_matches:
        bonus += _ROOT_PREFIX_BONUS
    # Alias-only 매치 — root 가 query 와 무관하면 paren bonus 를 절반으로.
    if paren_hit and not root_matches:
        bonus -= _PAREN_EXACT_BONUS * _PAREN_ALIAS_ONLY_DAMP
    return bonus


def _market_type_boost(query: str, dtype: str | None) -> float:
    """Boost 전통시장 type when query explicitly ends in '시장'.

    "남대문시장" 같이 명시적인 시장명 쿼리에서 TYPE_PRIORITY 의 전통시장 가산
    (rank 1, +0.05) 이 발달/골목 보다 작아 self-name 매치를 놓치는 문제를
    보정한다. 일반 쿼리("강남")는 영향 없음.
    """
    if dtype != "전통시장":
        return 0.0
    if not _MARKET_QUERY_RE.match(query.strip()):
        return 0.0
    return _MARKET_TYPE_BOOST


def rank_candidates(
    query: str,
    rows: list[tuple[str, str, str | None]],
) -> list[RankedCandidate]:
    """Rank DB rows for a single query word.

    rows: list of ``(district_code, district_name, district_type)``.
    Returns candidates sorted by final score desc. Final score =
    ``_string_similarity`` + ``TYPE_PRIORITY × _TYPE_BOOST_PER_RANK`` +
    paren/root bonus. The paren-exact bonus makes "홍대" resolve decisively
    to "홍대입구역(홍대)" (발달상권) over incidental 골목상권 names.
    """
    ranked: list[RankedCandidate] = []
    for code, name, dtype in rows:
        sim = _string_similarity(query, name)
        if sim <= 0:
            continue
        type_rank = TYPE_PRIORITY.get(dtype or "", 0)
        extra = _paren_and_root_bonus(query, name)
        market_extra = _market_type_boost(query, dtype)
        final = min(1.0, sim + _TYPE_BOOST_PER_RANK * type_rank + extra + market_extra)
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
