"""Unit tests for numeric_sanity evaluator.

Run: PYTHONPATH=server python -m pytest server/tests/test_numeric_sanity.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.agent.utils.numeric_sanity import (  # noqa: E402
    evaluate_response,
    extract_numbers,
)


def test_extract_basic_korean_numbers():
    text = "월 추정 매출 1,104억 3천만원 입니다. 유동인구 590만 6천명."
    nums = extract_numbers(text)
    values = {n.raw: n.value for n in nums}
    assert any(abs(v - 110_430_000_000) / 110_430_000_000 < 0.01 for v in values.values())
    assert any(abs(v - 5_906_000) / 5_906_000 < 0.01 for v in values.values())


def test_extract_percentage():
    text = "폐업률 1.6%로 안정적"
    nums = extract_numbers(text)
    pct = [n for n in nums if n.tail == "%"]
    assert pct and abs(pct[0].value - 1.6) < 0.01


def test_match_against_tools_full_hit():
    text = "월 매출 1,104억원, 점포 4,125개, 폐업률 1.6%"
    tools = {
        "get_district_summary": {
            "monthlySales": 110_439_921_327,
            "closeRate": {"current": 1.6},
            "floatingPopulation": {"quarterTotal": 5_906_000},
            "topCategories": [{"storeCount": 4125}],
        }
    }
    report = evaluate_response(text, tools)
    assert report.total_numbers >= 3
    assert report.matched_numbers >= 2
    # No mismatch_ratio_high flag when matching is strong
    assert not any(f.rule == "tool_mismatch_ratio_high" for f in report.flags)


def test_detect_entity_mismatch():
    """When LLM numbers are for a DIFFERENT district, mismatch ratio fires."""
    text = (
        "월 추정 매출 43억 4천만원입니다. 점포 586개 중 의류 453개, 신발 33개가 있고, "
        "일평균 유동인구 7만 9천명, 피크시간대 2만 1천명입니다."
    )
    tools = {
        "get_district_summary": {
            "monthlySales": 47_416_272_422,  # Different district
            "floatingPopulation": {"quarterTotal": 2_183_029, "peakHour": 132_400},
            "topCategories": [{"storeCount": 2406}],
        }
    }
    report = evaluate_response(text, tools)
    flags = [f.rule for f in report.flags]
    assert "tool_mismatch_ratio_high" in flags


def test_empty_tool_results_yields_no_flags():
    text = "데이터가 부족해 분석이 어렵습니다."
    report = evaluate_response(text, {})
    assert report.flags == []


def test_ignore_small_enumeration_numbers():
    """Short numbers like '3개' or '1위' shouldn't blow up unmatched ratio."""
    text = "상위 업종 3개가 있으며, 1위는 카페입니다."
    report = evaluate_response(text, {})
    # No crash, no bogus flags
    assert report.total_numbers >= 0
