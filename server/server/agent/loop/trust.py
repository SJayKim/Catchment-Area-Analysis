"""Trust Kernel — the keystone of the v2 loop.

Invariant: every numeric claim in the user-facing answer must bind to a value
that a tool actually returned (or that the compute tool derived), within
``trust_numeric_tolerance``. A number the model invented from memory has no
matching fact and is flagged as *unbound*.

This is the structural anti-fabrication guarantee. It reuses the Korean-aware
number extraction + ±5% matching already proven in utils/numeric_sanity.py
(built for the post-hoc warning path); here we elevate it to a hard gate.

Enforcement is graduated (eval Round 3 P1 — availability loss from
over-defense): a draft with a few residual unbound numbers is preserved with
those numbers masked; full deterministic replacement is reserved for
entity-mismatch-grade fabrication where most scored numbers are unbound.
"""

from __future__ import annotations

from server.agent.utils.numeric_sanity import (
    ExtractedNumber,
    ScaleMismatch,
    _deep_get,
    extract_numbers,
    find_scale_mismatches,
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


def binding_stats(
    text: str,
    tool_results: dict[str, dict],
    computed: list[float] | None = None,
) -> tuple[int, list[ExtractedNumber]]:
    """Return (scored_total, unbound) for the graduated-enforcement decision."""
    if not text:
        return 0, []
    numbers = extract_numbers(text)
    if not numbers:
        return 0, []
    matched, unmatched = match_numbers_to_tools(
        numbers,
        _pool(tool_results, computed),
        tol=settings.trust_numeric_tolerance,
    )
    return matched + len(unmatched), unmatched


def find_scale_errors(
    text: str,
    tool_results: dict[str, dict],
    computed: list[float] | None = None,
) -> list[ScaleMismatch]:
    """×10/×100 자릿수 오기 검출 (S8 "145만 원" for 14,503,839원)."""
    if not text:
        return []
    return find_scale_mismatches(
        text,
        _pool(tool_results, computed),
        tol=settings.trust_numeric_tolerance,
    )


_MASK_TOKEN = "[미확인]"
_MASK_NOTE = "※ 일부 수치는 도구 데이터로 확인되지 않아 [미확인] 으로 표기했습니다."


def mask_unbound(text: str, numbers: list[ExtractedNumber]) -> str:
    """Replace offending numbers with a mask token, preserving the draft.

    Appends the explanatory footnote once. Longer raws are replaced first so
    a shorter raw that is a substring of a longer one cannot corrupt it.
    """
    if not text or not numbers:
        return text
    masked = text
    for raw in sorted({n.raw for n in numbers if n.raw}, key=len, reverse=True):
        masked = masked.replace(raw, _MASK_TOKEN)
    if _MASK_TOKEN in masked and _MASK_NOTE not in masked:
        masked = f"{masked}\n\n{_MASK_NOTE}"
    return masked


def should_fallback(unbound_count: int, scored_total: int) -> bool:
    """Full deterministic replacement only for fabrication-heavy drafts:
    at least 3 unbound AND ≥50% of all scored numbers unbound. Below that,
    masking preserves the draft (availability > over-defense)."""
    return unbound_count >= 3 and unbound_count * 2 >= scored_total


def _format_won(value: float) -> str:
    v = int(value)
    if v >= 10**8:
        return f"약 {v / 10**8:.1f}억원"
    if v >= 10**4:
        return f"약 {v / 10**4:,.0f}만원"
    return f"{v:,}원"


def _render(value: float, unit: str) -> str:
    if unit == "원":
        return _format_won(value)
    if unit == "명":
        return f"{int(value):,}명"
    if unit == "개":
        return f"{int(value):,}개"
    if unit == "%":
        return f"{value:.1f}%"
    return f"{int(value):,}"


def _entity_label(payload: dict) -> str:
    for key in ("name", "district_name", "districtName"):
        v = payload.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


# (field_path, caption, unit) per tool — captions are fixed code-side strings;
# entity names are pulled from the tool payloads themselves. Nothing in the
# fallback text originates from the model ⇒ fabrication-proof.
_LABELED_FIELDS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "get_district_summary": (
        ("floatingPopulation.quarterTotal", "분기 유동인구", "명"),
        # legacy key — Redis 캐시된 구버전 card payload 방어 (rename 2026-07-04)
        ("floatingPopulation.dailyAvg", "분기 유동인구", "명"),
        ("monthlySales", "월 추정 매출", "원"),
        ("closeRate.current", "폐업률", "%"),
        ("insights.perStoreSales", "점포당 월매출", "원"),
    ),
    "get_floating_population": (
        ("quarter_total", "분기 유동인구", "명"),
        ("quarterTotal", "분기 유동인구", "명"),
        ("daily_avg", "분기 유동인구", "명"),
        ("dailyAvg", "분기 유동인구", "명"),
    ),
    "get_estimated_sales": (
        ("total_monthly_sales", "월 추정 매출", "원"),
        ("totalMonthlySales", "월 추정 매출", "원"),
        ("monthly_sales", "월 추정 매출", "원"),
    ),
    "get_store_info": (
        ("total_stores", "총 점포 수", "개"),
        ("totalStores", "총 점포 수", "개"),
        ("close_rate", "폐업률", "%"),
        ("closeRate", "폐업률", "%"),
    ),
    "simulate_revenue": (
        ("monthly_avg", "예상 월매출(평균)", "원"),
        ("monthlyAvg", "예상 월매출(평균)", "원"),
    ),
    "get_population_info": (
        ("resident_population", "상주인구", "명"),
        ("worker_population", "직장인구", "명"),
    ),
}

_COMPARE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("monthly_sales", "월 매출", "원"),
    ("floating_pop", "분기 유동인구", "명"),
    ("store_count", "점포 수", "개"),
    ("close_rate", "폐업률", "%"),
    ("sales_per_store", "점포당 매출", "원"),
)

_RECOMMEND_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("monthly_sales", "월 매출", "원"),
    ("avg_monthly_sales", "평균 월 매출", "원"),
    ("per_store_sales", "점포당 월매출", "원"),
    ("store_count", "점포 수", "개"),
)


def _labeled_scalars(tool_results: dict[str, dict]) -> list[tuple[str, float, str]]:
    """Flatten the fact pool into (label, value, unit) rows for the fallback."""
    out: list[tuple[str, float, str]] = []
    for pool_key, payload in (tool_results or {}).items():
        if not isinstance(payload, dict):
            continue
        tool_name = pool_key.split("#", 1)[0]
        entity = _entity_label(payload)
        prefix = f"{entity} " if entity else ""
        for path, caption, unit in _LABELED_FIELDS.get(tool_name, ()):
            value = _deep_get(payload, path)
            if isinstance(value, (int, float)) and value > 0:
                out.append((f"{prefix}{caption}", float(value), unit))
        districts = payload.get("districts")
        if isinstance(districts, dict):
            for code, dp in districts.items():
                if not isinstance(dp, dict):
                    continue
                dname = _entity_label(dp) or str(code)
                for key, caption, unit in _COMPARE_FIELDS:
                    v = dp.get(key)
                    if isinstance(v, (int, float)) and v > 0:
                        out.append((f"{dname} {caption}", float(v), unit))
        recs = payload.get("recommendations")
        if isinstance(recs, list):
            for rec in recs[:5]:
                if not isinstance(rec, dict):
                    continue
                rname = rec.get("category_name") or rec.get("name") or rec.get("category") or ""
                metrics = rec.get("metrics") if isinstance(rec.get("metrics"), dict) else rec
                for key, caption, unit in _RECOMMEND_FIELDS:
                    v = metrics.get(key)
                    if isinstance(v, (int, float)) and v > 0:
                        out.append((f"{rname} {caption}".strip(), float(v), unit))
    deduped: list[tuple[str, float, str]] = []
    seen: set[tuple[str, str, int]] = set()
    for label, value, unit in out:
        key = (label, unit, int(value))
        if key in seen:
            continue
        seen.add(key)
        deduped.append((label, value, unit))
    return deduped


_ABSTENTION_TEXT = (
    "죄송합니다. 요청하신 내용을 뒷받침할 확인된 데이터를 가져오지 못했습니다. "
    "상권명을 다시 알려주시거나 다른 질문을 해주세요."
)

_CARDS_TEXT = (
    "핵심 지표는 위 카드에 정리되어 있습니다. 카드의 수치를 기준으로 확인해 주세요. (추정 데이터 기반 참고용입니다.)"
)


def grounded_fallback(tool_results: dict[str, dict], cards_emitted: bool = False) -> str:
    """Deterministic, fabrication-proof answer built only from fetched facts.

    Last-resort when the model keeps emitting unbound numbers after a
    corrective pass. Every line carries a label sourced from code-side
    captions + tool-returned entity strings — never model output. When cards
    already shipped, never abstain: point at the cards instead.
    """
    labeled = _labeled_scalars(tool_results or {})
    if not labeled:
        return _CARDS_TEXT if cards_emitted else _ABSTENTION_TEXT
    lines = ["확인된 데이터 기준으로 정리하면 다음과 같습니다:"]
    lines.extend(f"- {label}: {_render(value, unit)}" for label, value, unit in labeled[:10])
    lines.append("(추정 데이터 기반 참고용입니다.)")
    return "\n".join(lines)
