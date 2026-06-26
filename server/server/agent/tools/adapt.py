"""Adapt raw tool dicts into ToolEnvelope for the agentic loop.

The agentic loop wraps every tool result through to_envelope(); the legacy PAE
actor keeps the raw dict, so this module is agentic-only and additive.
"""

from __future__ import annotations

import copy
from typing import Any

from server.agent.tools.data_sources import get_sources_for_tool
from server.agent.tools.envelope import ToolEnvelope

# Mirror of actor._TRUNCATABLE_KEYS (kept in sync by the drift-guard test in
# tests/test_envelope.py). Lists under these keys are capped at 10 items.
TRUNCATABLE_KEYS = frozenset(
    {
        "by_hour",
        "quarterly_sales",
        "top_categories",
        "by_age_group",
        "by_gender",
        "by_day_type",
        "by_time_slot",
        "trends",
        "history",
        "recommendations",
        "stores",
        "categories",
        "monthly_data",
    }
)

# Unit anchors surfaced to the LLM via envelope.llm_view().units. These carry the
# semantics that prevent S7-class fabrications (daily_avg misread as a per-day
# average; quarterly sales misread as monthly).
_UNITS: dict[str, dict[str, str]] = {
    "get_floating_population": {
        "quarter_total_pop": (
            "명 · 해당 분기 전체 시간대 합계(집계 총량). 하루 평균이 아니므로 "
            "일수로 나누지 말 것. 시간대별 인구는 by_hour 값만 인용."
        ),
        "peak_hour": "0–23 시간대 인덱스(인구수 아님).",
    },
    "get_district_summary": {
        "floatingPopulation.quarter_total_pop": "명 · 분기 시간대 합계(집계 총량), 하루 평균 아님.",
        "monthlySales": "원 · 월 환산값(분기누적÷3).",
    },
    "get_estimated_sales": {"total_monthly_sales": "원 · 월 환산값(분기누적÷3)."},
    "compare_districts": {
        "monthly_sales": "원 · 월 환산값(분기누적÷3).",
        "floating_pop": "명 · 분기 시간대 합계(집계 총량).",
    },
    "recommend_business": {
        "monthly_sales": "원 · 월 환산값.",
        "per_store_sales": "원 · 점포당 월 환산값.",
    },
    "simulate_revenue": {"simulation": "원 · 월 환산 추정 매출."},
}

# Top-level quarter key differs per tool; a few tools carry no top-level quarter.
_QUARTER_KEY: dict[str, str] = {"get_district_summary": "dataQuarter"}
_NO_QUARTER = frozenset({"get_store_history", "compare_districts"})

# Dropped from the LLM view (kept on card_data for the user): the summary text
# embeds the legacy "하루 평균" label that cannot be fixed on the pae path, and
# the citation array (dataSources) is pure token waste in the model's grounding.
_LLM_OMIT: dict[str, tuple[str, ...]] = {"get_district_summary": ("summary", "dataSources")}


def _truncate(data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Replicate actor._truncate_result and report whether anything was trimmed."""
    changed = False

    def walk(d: dict[str, Any]) -> dict[str, Any]:
        nonlocal changed
        out: dict[str, Any] = {}
        for key, value in d.items():
            if isinstance(value, list) and key in TRUNCATABLE_KEYS and len(value) > 10:
                out[key] = value[:10]
                changed = True
            elif isinstance(value, dict):
                out[key] = walk(value)
            else:
                out[key] = value
        return out

    return walk(data), changed


def _extract_quarter(name: str, data: dict[str, Any]) -> str:
    if name in _NO_QUARTER:
        return ""
    return str(data.get(_QUARTER_KEY.get(name, "quarter"), "") or "")


def to_envelope(name: str, raw: Any) -> ToolEnvelope:
    """Wrap a raw tool result dict into a ToolEnvelope."""
    if not isinstance(raw, dict):
        return ToolEnvelope(tool=name, error="도구가 예상치 못한 형식을 반환했습니다.")

    if "error" in raw:
        return ToolEnvelope(
            tool=name,
            error=str(raw["error"]),
            needs_category=bool(raw.get("needs_category")),
        )

    data, truncated = _truncate(raw)
    sources = get_sources_for_tool(name)
    quarter = _extract_quarter(name, data)

    from server.agent.tools.registry import get_tool_registry

    meta = get_tool_registry().get(name)
    card_type = meta.card_type if meta else None

    card_data: dict[str, Any] | None = None
    if card_type:
        # Deep copy so downstream card-shaping never mutates the grounding `data`
        # (and vice versa) — the two diverge (card keeps frozen frontend keys,
        # llm_view relabels for the LLM).
        card_data = copy.deepcopy(data)
        if sources:
            card_data["dataSources"] = sources

    return ToolEnvelope(
        tool=name,
        data=data,
        units=_UNITS.get(name, {}),
        source=sources,
        quarter=quarter,
        truncated=truncated,
        card_type=card_type,
        card_data=card_data,
        needs_category=bool(raw.get("needs_category")),
        llm_omit=_LLM_OMIT.get(name, ()),
    )
