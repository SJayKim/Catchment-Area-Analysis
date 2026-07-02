"""Trust Kernel — the keystone of the v2 loop.

Invariant: every numeric claim in the user-facing answer must bind to a value
that a tool actually returned (or that the compute tool derived), within
``trust_numeric_tolerance``. A number the model invented from memory has no
matching fact and is flagged as *unbound*.

This is the structural anti-fabrication guarantee. It reuses the Korean-aware
number extraction + ±5% matching already proven in utils/numeric_sanity.py
(built for the post-hoc warning path); here we elevate it to a hard gate.
"""

from __future__ import annotations

from server.agent.utils.numeric_sanity import (
    ExtractedNumber,
    _collect_tool_scalars,
    extract_numbers,
    match_numbers_to_tools,
)
from server.config import settings

# Synthetic pool key so compute() results participate in binding.
_COMPUTED_KEY = "__computed__"


def _pool(tool_results: dict[str, dict], computed: list[float] | None) -> dict[str, dict]:
    pool = dict(tool_results or {})
    if computed:
        pool[_COMPUTED_KEY] = {"values": list(computed)}
    return pool


def find_unbound_numbers(
    text: str,
    tool_results: dict[str, dict],
    computed: list[float] | None = None,
) -> list[ExtractedNumber]:
    """Return the above-threshold numbers in ``text`` that no fact backs.

    Empty list ⇒ every scored number is grounded. Small contextual numbers
    (rank labels, %, tiny counts) are filtered by the shared threshold logic.
    """
    if not text:
        return []
    numbers = extract_numbers(text)
    if not numbers:
        return []
    _matched, unmatched = match_numbers_to_tools(
        numbers,
        _pool(tool_results, computed),
        tol=settings.trust_numeric_tolerance,
    )
    return unmatched


def is_grounded(text: str, tool_results: dict[str, dict], computed: list[float] | None = None) -> bool:
    return not find_unbound_numbers(text, tool_results, computed)


def _format_won(value: float) -> str:
    v = int(value)
    if v >= 10**8:
        return f"약 {v / 10**8:.1f}억원"
    if v >= 10**4:
        return f"약 {v / 10**4:.0f}만원"
    return f"{v:,}원"


def grounded_fallback(tool_results: dict[str, dict]) -> str:
    """Deterministic, fabrication-proof answer built only from fetched facts.

    Last-resort when the model keeps emitting unbound numbers after a
    corrective pass. Ugly but truthful — guarantees no invented number ships.
    """
    scalars = _collect_tool_scalars(tool_results or {})
    if not scalars:
        return (
            "죄송합니다. 요청하신 내용을 뒷받침할 확인된 데이터를 가져오지 못했습니다. "
            "상권명을 다시 알려주시거나 다른 질문을 해주세요."
        )
    lines: list[str] = ["확인된 데이터 기준으로만 정리하면 다음과 같습니다:"]
    seen: set[tuple[str, int]] = set()
    for _tool, value, unit in scalars:
        key = (unit, int(value))
        if key in seen:
            continue
        seen.add(key)
        if unit == "원":
            rendered = _format_won(value)
        elif unit == "명":
            rendered = f"{int(value):,}명"
        elif unit == "개":
            rendered = f"{int(value):,}개"
        elif unit == "%":
            rendered = f"{value:.1f}%"
        else:
            rendered = f"{int(value):,}"
        lines.append(f"- {rendered}")
        if len(lines) >= 9:
            break
    lines.append("(추정 데이터 기반 참고용입니다.)")
    return "\n".join(lines)
