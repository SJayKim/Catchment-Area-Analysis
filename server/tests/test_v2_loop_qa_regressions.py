# Regression: ISSUE-001/002/004 — v2 loop 사용자 관점 QA findings
# Found by /qa on 2026-07-02
# Report: .gstack/qa-reports/qa-report-localhost-2026-07-02.md
"""v2 루프 QA 회귀 가드.

- ISSUE-001: trust 교정 패스가 메타 발화("...검토하겠습니다")를 최종 답변으로
  유출 — _is_answer_shaped 가드가 걸러야 한다.
- ISSUE-002: category_code 에 업종명("카페")이 오면 실행부가 코드로 resolve
  해야 한다(시스템 프롬프트가 허용을 약속).
- ISSUE-004: 상권 미선택 턴에서 "이 상권 ..." suggestion 금지.
"""

from server.agent.loop.engine import _is_answer_shaped, _proactive_suggestions
from server.agent.loop.prompts import corrective_instruction
from server.agent.loop.tools_fc import _normalize_category
from server.services.category_resolver import CategoryResolver, set_category_resolver


class TestIssue001CorrectiveLeak:
    def test_meta_ack_rejected(self):
        # 라이브에서 실제 유출된 문자열 2종
        assert not _is_answer_shaped("지적 감사합니다. 두 수치를 정확히 검토하겠습니다.")
        assert not _is_answer_shaped("지적 감사합니다. 편의점 점포당 월매출 수치를 정확히 확인하겠습니다.")

    def test_empty_rejected(self):
        assert not _is_answer_shaped("")
        assert not _is_answer_shaped("   \n ")

    def test_numeric_rewrite_accepted(self):
        assert _is_answer_shaped("홍대 유동인구는 4,106,209명으로 성수(1,412,369명)보다 많습니다.")

    def test_long_numberless_prose_accepted(self):
        prose = (
            "정확한 수치는 데이터 없음으로 처리했습니다. 강남역은 발달상권으로 "
            "직장인 고정 수요가 탄탄하고, 점심·저녁 시간대 소비가 집중되는 특성이 "
            "있어 외식업 창업에 유리한 편입니다. 추정치이며 실제와 다를 수 있습니다(참고용)."
        )
        assert _is_answer_shaped(prose)

    def test_corrective_instruction_is_prose_only(self):
        text = corrective_instruction(["1,234", "5.6억"])
        assert "compute" not in text  # 교정 턴엔 도구가 없다
        assert "메타 문구 없이" in text


class TestIssue002CategoryResolve:
    def setup_method(self):
        resolver = CategoryResolver()
        resolver.load_defaults()
        set_category_resolver(resolver)

    def test_korean_name_resolves_to_code(self):
        # 기본(mock 13종)과 Real(DB aliases)의 코드값이 달라 정확한 코드 대신
        # "업종명이 CS 코드로 변환된다"는 계약을 검증한다.
        code = _normalize_category("카페")
        assert code != "카페"
        assert code.startswith("CS")

    def test_code_passthrough(self):
        assert _normalize_category("CS100010") == "CS100010"

    def test_unknown_name_passthrough(self):
        assert _normalize_category("존재하지않는업종명") == "존재하지않는업종명"


class TestIssue004Suggestions:
    def test_no_district_has_no_dangling_chip(self):
        for called in (set(), {"resolve_district"}, {"abstain"}):
            questions = _proactive_suggestions(called, "")
            assert questions, "suggestion 은 항상 존재해야 한다"
            assert all("이 상권" not in q for q in questions)

    def test_placeholder_name_treated_as_missing(self):
        questions = _proactive_suggestions(set(), "미선택")
        assert all("이 상권" not in q for q in questions)

    def test_selected_district_personalized(self):
        questions = _proactive_suggestions(set(), "강남역")
        assert any("강남역" in q for q in questions)

    def test_compare_branch_unchanged(self):
        questions = _proactive_suggestions({"compare_districts"}, "")
        assert "각 상권 추천 업종 알려줘" in questions
