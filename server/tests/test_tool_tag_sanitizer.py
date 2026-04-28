"""Unit tests for `_ToolTagSanitizer` — strips raw tool-name leaks from the
respond stream.

Background:
    `ATTRIBUTION_PROMPT_RULE` previously asked the LLM to suffix numeric
    claims with ``(get_district_summary)`` etc. The intent was post-hoc
    verification, but raw function names leaked into user-facing text.
    The new prompt forbids this and `_ToolTagSanitizer` is a stream-level
    safety net for the rare cases where the LLM relapses.
"""

from __future__ import annotations

from server.agent.nodes.respond import _ToolTagSanitizer


def _drain(s: _ToolTagSanitizer, *chunks: str) -> str:
    out = "".join(s.feed(c) for c in chunks)
    out += s.flush()
    return out


def test_strip_simple_tool_tag() -> None:
    s = _ToolTagSanitizer()
    out = _drain(s, "월 매출 5,320억원 (get_estimated_sales) 입니다.")
    assert "(get_estimated_sales)" not in out
    assert "월 매출 5,320억원" in out
    assert "입니다." in out
    assert s.dropped_count == 1


def test_strip_backticked_tool_tag() -> None:
    s = _ToolTagSanitizer()
    out = _drain(s, "유동인구 12만 명 `(get_floating_population)` 기준")
    assert "(get_floating_population)" not in out
    assert "유동인구 12만 명" in out
    assert "기준" in out
    assert s.dropped_count == 1


def test_chunk_boundary_split_open_paren() -> None:
    """`(get_district_summary)` arrives split across chunks at `(`."""
    s = _ToolTagSanitizer()
    out = _drain(s, "월 매출 5,320억원 (get_", "estimated_sales) 입니다.")
    assert "(get_estimated_sales)" not in out
    assert "월 매출 5,320억원" in out
    assert "입니다." in out
    assert s.dropped_count == 1


def test_chunk_boundary_split_inside_name() -> None:
    """tool name itself split across two chunks."""
    s = _ToolTagSanitizer()
    out = _drain(s, "추천 (recommend_", "business)")
    assert "(recommend_business)" not in out
    assert "추천" in out
    assert s.dropped_count == 1


def test_preserves_korean_parens() -> None:
    """Generic Korean parenthetical phrases must be preserved."""
    s = _ToolTagSanitizer()
    out = _drain(
        s,
        "창업 시 주의 (자본금 부족) 및 (시장 포화) 리스크가 있습니다.",
    )
    assert "(자본금 부족)" in out
    assert "(시장 포화)" in out
    assert s.dropped_count == 0


def test_preserves_unrelated_english_parens() -> None:
    """English parentheticals that aren't tool names stay intact."""
    s = _ToolTagSanitizer()
    out = _drain(s, "결과 (note: 추정치) 참고하세요.")
    assert "(note: 추정치)" in out
    assert s.dropped_count == 0


def test_multiple_tags_in_one_chunk() -> None:
    s = _ToolTagSanitizer()
    out = _drain(
        s,
        "유동 12만 (get_floating_population) 매출 5억 (get_estimated_sales).",
    )
    assert "(get_floating_population)" not in out
    assert "(get_estimated_sales)" not in out
    assert "유동 12만" in out
    assert "매출 5억" in out
    assert s.dropped_count == 2


def test_unterminated_paren_buffer_overflow() -> None:
    """Open `(` with no closing for too long should flush as literal."""
    s = _ToolTagSanitizer()
    long_text = "(" + "x" * 200
    out = _drain(s, long_text)
    assert out == long_text
    assert s.dropped_count == 0


def test_compare_districts_tag() -> None:
    s = _ToolTagSanitizer()
    out = _drain(s, "비교 결과 (compare_districts) 데이터")
    assert "(compare_districts)" not in out
    assert "비교 결과" in out
    assert s.dropped_count == 1


def test_estimate_revenue_tag_with_quote() -> None:
    s = _ToolTagSanitizer()
    out = _drain(s, "예상 매출 1억 '(estimate_revenue)' 수준")
    assert "(estimate_revenue)" not in out
    assert "수준" in out
    assert s.dropped_count == 1


def test_empty_input_safe() -> None:
    s = _ToolTagSanitizer()
    assert s.feed("") == ""
    assert s.flush() == ""
    assert s.dropped_count == 0
