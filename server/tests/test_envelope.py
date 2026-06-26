"""Unit tests for the agentic-loop tool envelope layer (P1).

Pure-unit: synthetic raw tool dicts → ToolEnvelope. No DB, no live LLM. Runs
under conftest USE_MOCK=true (get_sources_for_tool → mock source). This layer is
brand-new (envelope/adapt/definitions), so these tests are additive and cannot
collide with the existing suite.
"""

from __future__ import annotations

import json

import pytest

from server.agent.tools.adapt import TRUNCATABLE_KEYS, to_envelope
from server.agent.tools.definitions import build_tool_definitions


def test_summary_envelope_card_and_quarter():
    raw = {
        "districtName": "강남역",
        "dataQuarter": "2025년 4분기",
        "summary": "강남역 상권은 하루 평균 유동인구 410만명...",
        "monthlySales": 13_960_000_000,
        "floatingPopulation": {
            "dailyAvg": 4_106_209,
            "peakHour": 18,
            "byHour": [{"hour": 0, "pop": 1}],
        },
    }
    env = to_envelope("get_district_summary", raw)
    assert env.card_type == "summary"
    assert env.card_data is not None
    # card_data keeps the FROZEN frontend key (dailyAvg) + nested dataSources
    assert env.card_data["floatingPopulation"]["dailyAvg"] == 4_106_209
    assert "dataSources" in env.card_data
    assert env.quarter == "2025년 4분기"


def test_summary_llm_view_relabels_and_drops_narrative():
    raw = {
        "districtName": "강남역",
        "summary": "하루 평균 유동인구 410만명",  # legacy misleading label
        "dataSources": [{"id": "seoul_floating_pop", "name": "상권-유동인구"}],
        "floatingPopulation": {"dailyAvg": 4_106_209},
    }
    view = to_envelope("get_district_summary", raw).llm_view()
    result = view["result"]
    # daily_avg relabeled; misleading narrative + citation dropped from LLM view
    assert result["floatingPopulation"]["quarter_total_pop"] == 4_106_209
    assert "dailyAvg" not in result["floatingPopulation"]
    assert "summary" not in result
    assert "dataSources" not in result
    # the misleading "하루 평균" label must not reach the LLM via the data result
    # (the units anchor deliberately says "하루 평균 아님", so assert on result, not view)
    assert "하루 평균" not in json.dumps(result, ensure_ascii=False)


def test_card_data_does_not_alias_grounding_data():
    raw = {
        "districtName": "강남역",
        "dataQuarter": "2025Q4",
        "floatingPopulation": {"dailyAvg": 100},
    }
    env = to_envelope("get_district_summary", raw)
    # mutating a nested node in card_data must NOT corrupt the grounding data
    env.card_data["floatingPopulation"]["dailyAvg"] = 999
    assert env.data["floatingPopulation"]["dailyAvg"] == 100


def test_floating_population_relabel_no_card():
    raw = {
        "district_code": "3120103",
        "quarter": "2025Q4",
        "daily_avg": 4_106_209,
        "peak_hour": 18,
        "by_hour": [{"time_slot": 0, "population": 100}],
    }
    env = to_envelope("get_floating_population", raw)
    assert env.card_type is None
    assert env.card_data is None
    view = env.llm_view()
    assert view["result"]["quarter_total_pop"] == 4_106_209
    assert "daily_avg" not in view["result"]
    assert "quarter_total_pop" in env.units
    assert view["quarter"] == "2025Q4"


def test_truncation_caps_whitelisted_lists_only():
    raw = {
        "quarter": "2025Q4",
        "by_hour": [{"time_slot": i, "population": i} for i in range(24)],  # whitelisted → cap 10
        "other_list": list(range(24)),  # not whitelisted → untouched
    }
    env = to_envelope("get_floating_population", raw)
    assert len(env.data["by_hour"]) == 10
    assert len(env.data["other_list"]) == 24
    assert env.truncated is True


def test_no_truncation_flag_when_short():
    raw = {"quarter": "2025Q4", "by_hour": [{"time_slot": 0, "population": 1}]}
    env = to_envelope("get_floating_population", raw)
    assert env.truncated is False


def test_error_passthrough():
    env = to_envelope(
        "get_floating_population",
        {"error": "해당 상권의 유동인구 데이터가 없습니다.", "district_code": "X"},
    )
    assert env.error is not None
    assert env.card_type is None
    view = env.llm_view()
    assert view["error"] == "해당 상권의 유동인구 데이터가 없습니다."
    assert "result" not in view


def test_needs_category_signal():
    raw = {
        "error": "어떤 업종을 시뮬레이션할까요?",
        "district_code": "X",
        "category_code": None,
        "needs_category": True,
    }
    env = to_envelope("simulate_revenue", raw)
    assert env.needs_category is True
    assert env.llm_view()["needs_category"] is True


def test_compare_card_data_shape_and_no_quarter():
    raw = {
        "district_codes": ["A", "B"],
        "districts": {
            "A": {"district_code": "A", "floating_pop": 100, "monthly_sales": 1},
            "B": {"district_code": "B", "floating_pop": 200, "monthly_sales": 2},
        },
        "winners": {"highest_pop": "B"},
    }
    env = to_envelope("compare_districts", raw)
    assert env.card_type == "compare"
    assert env.card_data["district_codes"] == ["A", "B"]
    assert "districts" in env.card_data
    assert env.quarter == ""  # compare carries no top-level quarter


def test_build_tool_definitions_sorted_and_complete():
    defs = build_tool_definitions()
    names = [d["name"] for d in defs]
    assert names == sorted(names)  # cache-stable order
    expected = {
        "get_district_summary",
        "get_floating_population",
        "get_estimated_sales",
        "get_store_info",
        "get_store_history",
        "get_population_info",
        "compare_districts",
        "recommend_business",
        "simulate_revenue",
    }
    assert expected.issubset(set(names))
    assert "get_district_benchmarks" not in names  # internal helper, not LLM-callable
    for d in defs:
        assert d["input_schema"]["type"] == "object"
        assert d["description"]


def test_compare_schema_has_no_phantom_category():
    # actual compare_districts(district_codes) takes no category_code
    defs = {d["name"]: d for d in build_tool_definitions()}
    props = defs["compare_districts"]["input_schema"]["properties"]
    assert "district_codes" in props
    assert "category_code" not in props


def test_truncatable_keys_match_actor():
    # drift guard: envelope truncation must mirror the legacy actor whitelist
    try:
        from server.agent.nodes.actor import _TRUNCATABLE_KEYS
    except Exception:  # pragma: no cover - actor deps unavailable
        pytest.skip("actor import unavailable")
    assert TRUNCATABLE_KEYS == _TRUNCATABLE_KEYS
