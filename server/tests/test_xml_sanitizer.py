"""Unit tests for `_XMLTagSanitizer` in respond.py.

Guards against the Claude `<tool_use>` XML leak that surfaced in the
2026-04-24 accuracy eval Round 2 (S3, S8). The sanitizer must:
  - drop banned function-call XML even when split across stream chunks
  - keep markdown / inline HTML untouched
  - keep attribution-style parens like ``(get_district_summary)`` (these are
    natural language, not tags)
"""

from __future__ import annotations

from server.agent.nodes.respond import _XMLTagSanitizer


def _drain(s: _XMLTagSanitizer, chunks: list[str]) -> str:
    out = "".join(s.feed(c) for c in chunks)
    out += s.flush()
    return out


def test_strips_tool_use_block() -> None:
    s = _XMLTagSanitizer()
    body = (
        "분석 결과:\n"
        "<tool_use>\n<tool_name>compare_districts</tool_name>\n</tool_use>\n"
        "<tool_result>{...}</tool_result>\n"
        "강남역은 발달상권입니다."
    )
    out = _drain(s, [body])
    assert "<tool_use>" not in out
    assert "<tool_result>" not in out
    assert "<tool_name>" not in out
    assert "강남역은 발달상권입니다." in out
    assert s.dropped_count >= 4  # opening + close pairs


def test_strips_get_district_xml_form() -> None:
    s = _XMLTagSanitizer()
    out = _drain(
        s,
        ['응답입니다. <get_district_analysis>{"name":"성수"}</get_district_analysis> 끝.'],
    )
    assert "<get_district" not in out
    assert "응답입니다." in out
    assert s.dropped_count >= 2


def test_strips_split_across_chunks() -> None:
    """Tag boundary lands on a chunk seam — sanitizer must buffer until ``>``."""
    s = _XMLTagSanitizer()
    out = _drain(s, ["pre <tool_", "use>body</tool_use", "> post"])
    assert "<tool_use" not in out
    assert "</tool_use" not in out
    assert "pre " in out
    assert "post" in out


def test_keeps_attribution_parens() -> None:
    """``(get_district_summary)`` is a citation marker, not an XML tag."""
    s = _XMLTagSanitizer()
    text = "월 추정 매출 1,104억원 (get_district_summary) 입니다."
    out = _drain(s, [text])
    assert out == text
    assert s.dropped_count == 0


def test_keeps_markdown_and_safe_html() -> None:
    s = _XMLTagSanitizer()
    text = "**굵게** _기울임_ <strong>안전</strong> <br/> <em>강조</em>"
    out = _drain(s, [text])
    assert "<strong>" in out
    assert "<em>" in out
    assert "<br" in out
    assert s.dropped_count == 0


def test_unterminated_tag_at_eos_is_flushed() -> None:
    """Stream ends with a half-open tag — flush must not eat user-visible chars."""
    s = _XMLTagSanitizer()
    out = "".join(s.feed(c) for c in ["text <unfini"])
    out += s.flush()
    # Flush returns the buffered tail. Behaviour: text is preserved.
    assert "text " in out
    assert "<unfini" in out  # treated as literal at flush
