"""Post-hoc numeric sanity check for Respond node output.

Purpose (data-trust-reliability-2026-04-24):
    Trust eval harness (`scripts/eval/trust_scenarios.py`) showed that 2/5
    districts FAILed because the Planner silently resolved an ambiguous
    district name to the wrong code. The response text had all surface
    quality signals (attribution tags, benchmark context, per-store sales)
    — but the underlying numbers came from a different district than the
    user asked about. `scan_unattributed_numbers` in `abstention.py` only
    checks for missing `(tool_name)` tags; it cannot detect this class of
    silent entity mismatch.

What this module does:
    1. Extract Korean-formatted numbers (억/만/천, %, 명, 개) from a LLM
       response text.
    2. Match each number against the executed tool results (±5% fuzzy).
    3. Range-check against benchmark distribution (p99 / p1) for the
       district type, if ``get_district_benchmarks`` was called.
    4. Emit a list of :class:`QualityFlag` entries for post-hoc telemetry
       and optionally an SSE ``warning`` event.

This module is side-effect-free: it does not mutate state or logger. The
caller decides what to do with the flags.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Unit scale in base (원 for KRW, 1 for counts, 1 for %)
_UNIT_SCALE: dict[str | None, int] = {
    "조": 10**12,
    "억": 10**8,
    "천만": 10**7,
    "백만": 10**6,
    "십만": 10**5,
    "만": 10**4,
    "천": 10**3,
    "백": 10**2,
    "십": 10,
    None: 1,
}

# Compound pattern: "590만 6천명" → 5,906,000. Must run before the simple
# pattern so the lo-unit part is not double-counted. lo_unit is REQUIRED —
# without it "3억 5,000만원" mis-parses (lo=5,000 at scale 1) and two adjacent
# independent numbers ("14억 ... 8개") get merged into one bogus compound.
_COMPOUND_RE = re.compile(
    r"(?P<hi>\d+(?:,\d{3})*)\s*(?P<hi_unit>조|억|만)\s*"
    r"(?P<lo>\d+(?:,\d{3})*)\s*(?P<lo_unit>천만|백만|십만|만|천|백|십)\s*(?P<tail>원|명|개)?"
)

_SIMPLE_RE = re.compile(
    r"(?P<num>\d{1,3}(?:,\d{3})*|\d+)(?:\.(?P<frac>\d+))?"
    r"\s*(?P<unit>조|억|천만|백만|십만|만|천)?\s*(?P<tail>원|명|개|%|퍼센트)?"
)


@dataclass(frozen=True)
class ExtractedNumber:
    raw: str
    value: float  # scalar in base unit (원 for KRW, 1 for counts, 0~100 for %)
    tail: str | None  # "원" | "명" | "개" | "%" | None
    start: int
    end: int


@dataclass
class QualityFlag:
    severity: str  # "warning" | "info"
    rule: str
    evidence: str
    tool_hint: str | None = None


@dataclass
class QualityReport:
    total_numbers: int = 0
    matched_numbers: int = 0
    flags: list[QualityFlag] = field(default_factory=list)

    def as_payload(self) -> dict[str, Any]:
        return {
            "total_numbers": self.total_numbers,
            "matched_numbers": self.matched_numbers,
            "match_rate": (round(self.matched_numbers / self.total_numbers, 3) if self.total_numbers else 1.0),
            "flags": [
                {
                    "severity": f.severity,
                    "rule": f.rule,
                    "evidence": f.evidence,
                    "tool_hint": f.tool_hint,
                }
                for f in self.flags
            ],
        }


def extract_numbers(text: str) -> list[ExtractedNumber]:
    """Parse Korean-style numbers from ``text``.

    Handles ``1,104억원``, ``590만 6천명``, ``2,679만원``, ``24.2%``,
    ``4,125개``.
    """
    found: list[ExtractedNumber] = []
    consumed_spans: list[tuple[int, int]] = []

    for m in _COMPOUND_RE.finditer(text):
        hi = int(m.group("hi").replace(",", ""))
        hi_scale = _UNIT_SCALE[m.group("hi_unit")]
        lo = int(m.group("lo").replace(",", ""))
        lo_scale = _UNIT_SCALE[m.group("lo_unit")]
        value = hi * hi_scale + lo * lo_scale
        tail = m.group("tail")
        found.append(
            ExtractedNumber(
                raw=m.group(0),
                value=float(value),
                tail=tail,
                start=m.start(),
                end=m.end(),
            )
        )
        consumed_spans.append((m.start(), m.end()))

    def is_consumed(start: int, end: int) -> bool:
        for s, e in consumed_spans:
            if start >= s and end <= e:
                return True
        return False

    for m in _SIMPLE_RE.finditer(text):
        if is_consumed(m.start(), m.end()):
            continue
        base_str = m.group("num")
        if not base_str:
            continue
        base = int(base_str.replace(",", ""))
        unit = m.group("unit")
        tail = m.group("tail")
        # Skip lone integers without unit or tail — they are paragraph numbers
        # (e.g. "1위", raw "5" inside "5개").
        if unit is None and tail is None:
            continue
        scale = _UNIT_SCALE[unit] if unit else 1
        value = base * scale
        frac_str = m.group("frac")
        if frac_str:
            frac_value = int(frac_str) * scale / (10 ** len(frac_str))
            value = value + frac_value
        found.append(
            ExtractedNumber(
                raw=m.group(0).strip(),
                value=float(value),
                tail=tail,
                start=m.start(),
                end=m.end(),
            )
        )

    found.sort(key=lambda n: n.start)
    return found


def _within(actual: float, expected: float, tol: float = 0.05) -> bool:
    if expected == 0:
        return actual == 0
    return abs(actual - expected) / expected <= tol


# Tool result keys that carry ground-truth scalars we can fuzzy-match against.
# (tool_name, field_path, unit_tail)
# Matches actual Tool return shapes (camelCase) — see agent/tools/*.py.
_TOOL_SCALAR_FIELDS: tuple[tuple[str, str, str], ...] = (
    # get_district_summary
    ("get_district_summary", "floatingPopulation.dailyAvg", "명"),
    ("get_district_summary", "monthlySales", "원"),
    ("get_district_summary", "closeRate.current", "%"),
    ("get_district_summary", "insights.perStoreSales", "원"),
    # get_floating_population (repo layer returns daily_avg)
    ("get_floating_population", "daily_avg", "명"),
    ("get_floating_population", "dailyAvg", "명"),
    # get_estimated_sales
    ("get_estimated_sales", "total_monthly_sales", "원"),
    ("get_estimated_sales", "totalMonthlySales", "원"),
    ("get_estimated_sales", "monthly_sales", "원"),
    # get_store_info
    ("get_store_info", "total_stores", "개"),
    ("get_store_info", "totalStores", "개"),
    ("get_store_info", "close_rate", "%"),
    ("get_store_info", "closeRate", "%"),
    # simulate_revenue
    ("simulate_revenue", "monthly_avg", "원"),
    ("simulate_revenue", "monthlyAvg", "원"),
    # recommend_business — nested under recommendations[].metrics
    ("recommend_business", "", ""),
    # compare_districts — nested under districts.{code}
    ("compare_districts", "", ""),
)


def _deep_get(obj: Any, path: str) -> Any:
    if not path:
        return obj
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _walk_numeric_leaves(obj: Any, acc: list[float], depth: int = 0) -> None:
    """Recursively collect every int/float leaf > 0 from ``obj``."""
    if depth > 6:
        return
    if isinstance(obj, dict):
        for v in obj.values():
            _walk_numeric_leaves(v, acc, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _walk_numeric_leaves(v, acc, depth + 1)
    elif isinstance(obj, (int, float)) and obj > 0:
        acc.append(float(obj))


def _collect_tool_scalars(tool_results: dict[str, dict]) -> list[tuple[str, float, str]]:
    """Flatten tool_results into (tool_name, scalar, unit_tail) tuples.

    Pool keys may carry a ``#N`` call-index suffix (v2 loop fact_pool stores
    ``get_district_summary#1``) — normalize before comparing to tool names.
    """
    scalars: list[tuple[str, float, str]] = []
    for pool_key, payload in (tool_results or {}).items():
        if not isinstance(payload, dict):
            continue
        tool_name = pool_key.split("#", 1)[0]
        for candidate_tool, path, unit in _TOOL_SCALAR_FIELDS:
            if candidate_tool != tool_name:
                continue
            value = _deep_get(payload, path)
            if isinstance(value, (int, float)) and value > 0:
                scalars.append((tool_name, float(value), unit))
        # get_district_summary.topCategories[] — list of store_count per category
        top_cats = payload.get("topCategories") or payload.get("top_categories")
        if isinstance(top_cats, list):
            for cat in top_cats:
                if isinstance(cat, dict):
                    sc = cat.get("storeCount") or cat.get("store_count") or cat.get("count")
                    if isinstance(sc, (int, float)) and sc > 0:
                        scalars.append((tool_name, float(sc), "개"))
        # get_store_info return — category breakdown
        stores_list = payload.get("stores") if isinstance(payload, dict) else None
        if isinstance(stores_list, list):
            for s in stores_list:
                if isinstance(s, dict):
                    sc = s.get("store_count")
                    if isinstance(sc, (int, float)) and sc > 0:
                        scalars.append((tool_name, float(sc), "개"))
        # compare_districts.districts.{code}.{field} — shallow scan
        districts = payload.get("districts") if isinstance(payload, dict) else None
        if isinstance(districts, dict):
            for code_payload in districts.values():
                if not isinstance(code_payload, dict):
                    continue
                for key, unit_tail in (
                    ("monthly_sales", "원"),
                    ("floating_pop", "명"),
                    ("store_count", "개"),
                    ("close_rate", "%"),
                    ("sales_per_store", "원"),
                ):
                    value = code_payload.get(key)
                    if isinstance(value, (int, float)) and value > 0:
                        scalars.append((tool_name, float(value), unit_tail))
        # recommend_business.recommendations[].metrics.*
        recs = payload.get("recommendations") if isinstance(payload, dict) else None
        if isinstance(recs, list):
            for rec in recs:
                if not isinstance(rec, dict):
                    continue
                metrics = rec.get("metrics") or rec
                for key, unit_tail in (
                    ("monthly_sales", "원"),
                    ("avg_monthly_sales", "원"),
                    ("per_store_sales", "원"),
                    ("store_count", "개"),
                    ("close_rate", "%"),
                ):
                    v = metrics.get(key) if isinstance(metrics, dict) else None
                    if isinstance(v, (int, float)) and v > 0:
                        scalars.append((tool_name, float(v), unit_tail))
    return scalars


def match_numbers_to_tools(
    numbers: list[ExtractedNumber],
    tool_results: dict[str, dict],
    tol: float = 0.05,
) -> tuple[int, list[ExtractedNumber]]:
    """Return (matched_count, unmatched_large_numbers).

    Only numbers above the per-unit threshold are scored — small numbers
    (e.g. "25%" rank label, "3개" enumeration, "9만 2천명" Seoul-average
    contextual mention) are filtered out before scoring.
    """
    # Unit floor — small numbers below this are ignored (rank labels etc.).
    thresholds = {"원": 10_000_000, "명": 100_000, "개": 30, "%": 101, None: 100}
    # Percentage floor of 101 effectively drops all "%" numbers — they are
    # almost always rank labels / rate values ("폐업률 1.6%", "상위 25%")
    # and not suitable for fuzzy scalar matching.
    typed_scalars = _collect_tool_scalars(tool_results)
    # Add every numeric leaf in the tool output for wildcard matching.
    wildcard_scalars: list[float] = []
    for payload in (tool_results or {}).values():
        _walk_numeric_leaves(payload, wildcard_scalars)
    matched = 0
    unmatched: list[ExtractedNumber] = []
    for num in numbers:
        floor = thresholds.get(num.tail, 1)
        if num.value < floor:
            continue
        any_hit = False
        # Prefer typed match first.
        for _tool, scalar, unit in typed_scalars:
            if num.tail and unit and unit != num.tail:
                continue
            if _within(num.value, scalar, tol):
                any_hit = True
                break
        # Fallback: any numeric leaf (typed_scalars misses deep nested values).
        if not any_hit:
            for scalar in wildcard_scalars:
                if _within(num.value, scalar, tol):
                    any_hit = True
                    break
        if any_hit:
            matched += 1
        else:
            unmatched.append(num)
    return matched, unmatched


@dataclass(frozen=True)
class ScaleMismatch:
    """A number whose ×10/×100 multiple matches a tool scalar — 자릿수 오기."""

    number: ExtractedNumber
    expected: float  # the tool-confirmed value the text should have used
    factor: int  # 10 or 100


# Suspect ranges sit BELOW the per-unit scoring floor in
# match_numbers_to_tools — such numbers skip binding entirely, so a 10x
# under-statement ("145만 원" for 14,503,839원) passes unchecked. Ranges are
# deliberately narrow and 개-unit is excluded to suppress false positives on
# legit small numbers (객단가, 임대료, rank labels).
_SCALE_SUSPECT_RANGES: dict[str, tuple[float, float]] = {
    "원": (100_000, 10_000_000),
    "명": (10_000, 100_000),
}


def find_scale_mismatches(
    text: str,
    tool_results: dict[str, dict],
    tol: float = 0.05,
) -> list[ScaleMismatch]:
    """Detect ×10/×100 under-stated numbers against typed tool scalars.

    Only fires when the number itself binds to nothing but its ×10 or ×100
    multiple matches a typed scalar of the same unit within ``tol``.
    """
    numbers = extract_numbers(text or "")
    if not numbers:
        return []
    typed_scalars = _collect_tool_scalars(tool_results or {})
    if not typed_scalars:
        return []
    wildcard_scalars: list[float] = []
    for payload in (tool_results or {}).values():
        _walk_numeric_leaves(payload, wildcard_scalars)
    out: list[ScaleMismatch] = []
    for num in numbers:
        rng = _SCALE_SUSPECT_RANGES.get(num.tail or "")
        if rng is None:
            continue
        lo, hi = rng
        if not (lo <= num.value < hi):
            continue
        # A value the tools actually returned at face value is fine.
        if any(_within(num.value, s, tol) for s in wildcard_scalars):
            continue
        hit: ScaleMismatch | None = None
        for factor in (10, 100):
            scaled = num.value * factor
            for _tool, scalar, unit in typed_scalars:
                if unit != num.tail:
                    continue
                if _within(scaled, scalar, tol):
                    hit = ScaleMismatch(number=num, expected=scalar, factor=factor)
                    break
            if hit:
                break
        if hit:
            out.append(hit)
    return out


def check_benchmark_outliers(
    numbers: list[ExtractedNumber],
    tool_results: dict[str, dict],
) -> list[QualityFlag]:
    """Flag numbers exceeding benchmark p99 or below p1 for the district type."""
    benchmarks = (tool_results or {}).get("get_district_benchmarks")
    if not isinstance(benchmarks, dict):
        return []
    # Expected shape: {district_type: str, monthly_sales_p99: int, ...}
    flags: list[QualityFlag] = []
    p99 = benchmarks.get("monthly_sales_p99") or benchmarks.get("sales_p99")
    p1 = benchmarks.get("monthly_sales_p1") or benchmarks.get("sales_p1")
    dtype = benchmarks.get("district_type") or "상권"
    if not (p99 or p1):
        return flags
    for num in numbers:
        if num.tail != "원":
            continue
        if p99 and num.value > p99 * 1.5:
            flags.append(
                QualityFlag(
                    severity="warning",
                    rule="benchmark_outlier_high",
                    evidence=f"{num.raw} > {dtype} p99×1.5 ({int(p99 * 1.5):,}원)",
                    tool_hint="get_district_benchmarks",
                )
            )
        elif p1 and num.value < p1 / 2 and num.value > 10_000_000:
            flags.append(
                QualityFlag(
                    severity="info",
                    rule="benchmark_outlier_low",
                    evidence=f"{num.raw} < {dtype} p1/2 ({int(p1 / 2):,}원)",
                    tool_hint="get_district_benchmarks",
                )
            )
    return flags


def evaluate_response(
    text: str,
    tool_results: dict[str, dict] | None = None,
    *,
    max_flags: int = 15,
) -> QualityReport:
    """Run the full numeric sanity pipeline over ``text``.

    Returns a report with counts and flags. Never raises.
    """
    tool_results = tool_results or {}
    numbers = extract_numbers(text or "")
    report = QualityReport(total_numbers=len(numbers))

    if not numbers:
        return report

    matched, unmatched = match_numbers_to_tools(numbers, tool_results)
    report.matched_numbers = matched

    # Rule 1: when the bulk of scored numbers have no match, the response
    # probably came from a different district than the one we fetched data
    # for. Threshold tuned so normal contextual references (서울 평균,
    # peak-hour counts, rank labels) don't trigger false positives.
    if tool_results:
        total_scored = matched + len(unmatched)
        if total_scored >= 4:
            mismatch_ratio = len(unmatched) / total_scored
            if mismatch_ratio >= 0.75:
                report.flags.append(
                    QualityFlag(
                        severity="warning",
                        rule="tool_mismatch_ratio_high",
                        evidence=(
                            f"{len(unmatched)}/{total_scored} 수치가 tool 결과와 "
                            f"±5% 안에서 매칭 실패 — entity mismatch 가능성"
                        ),
                        tool_hint=", ".join(sorted(tool_results.keys()))[:80],
                    )
                )
                # Expose up to 3 sample mismatches only when the ratio fires.
                for n in unmatched[:3]:
                    report.flags.append(
                        QualityFlag(
                            severity="info",
                            rule="tool_mismatch_sample",
                            evidence=n.raw,
                        )
                    )

    # Rule 2: benchmark outliers
    report.flags.extend(check_benchmark_outliers(numbers, tool_results))

    # Bound
    report.flags = report.flags[:max_flags]
    return report
