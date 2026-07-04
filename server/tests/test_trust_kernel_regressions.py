# Regression: Accuracy Eval Round 3 P1/P2 — Trust Kernel fallback 붕괴 + 스케일 오기
# Plan: /home/sjkim/.claude/plans/gleaming-juggling-yeti.md (prod-deploy-2026-07-04)
"""Trust Kernel 회귀 가드 — 5개 근본원인(RC1~RC5) 코드화.

- RC1: fact_pool 의 "tool#N" 접미 키가 typed 스칼라 수집에서 완전일치 비교로
  전멸 → S2 no-scalars abstention.
- RC2: _COMPOUND_RE 가 "3억 5,000만원" 을 300,005,000 으로 오파싱 + 인접한
  독립 수치 두 개를 하나로 오병합 → S4 결정론 붕괴.
- RC4: still-unbound 1개에도 draft 전체를 무라벨 fallback 으로 대체(과잉 방어)
  → 마스킹/threshold 로 graduated enforcement.
- RC5: "145만 원"(1.45M) 은 원화 채점 floor(10M) 미만이라 10배 축소 오기가
  무검증 통과 → find_scale_mismatches 신설.
"""

from __future__ import annotations

from server.agent.loop.trust import (
    find_unbound_numbers,
    grounded_fallback,
    mask_unbound,
    should_fallback,
)
from server.agent.utils.numeric_sanity import (
    _collect_tool_scalars,
    extract_numbers,
    find_scale_mismatches,
)


def _values(text: str) -> list[float]:
    return [n.value for n in extract_numbers(text)]


class TestKoreanUnitParsing:
    """RC2 — 복합/단순 패턴의 만·억 단위 파싱."""

    def test_compound_with_man_lo_unit(self):
        # 구 regex: lo_unit 에 '만' 미허용 → 300,005,000 오파싱
        assert 350_000_000.0 in _values("월 매출은 3억 5,000만원입니다.")

    def test_simple_cheonman_unit(self):
        # 구 regex: unit 에 '천만' 없음 → "3천만원" = 3,000 오파싱
        assert 30_000_000.0 in _values("초기 투자비는 3천만원 수준입니다.")

    def test_classic_compound_preserved(self):
        assert 5_906_000.0 in _values("분기 유동인구 590만 6천명")

    def test_adjacent_numbers_not_merged(self):
        # 구 regex: lo_unit optional → "14억"+"8개" 가 1,400,000,008 로 병합
        vals = _values("월 매출 14억 8개 점포 기준입니다.")
        assert 1_400_000_008.0 not in vals
        assert 1_400_000_000.0 in vals
        assert 8.0 in vals

    def test_baek_sip_units_no_crash(self):
        # 구 코드: _UNIT_SCALE 에 백/십 부재 → lo_scale=None → TypeError
        assert 500_000_300.0 in _values("정확히 5억 3백원입니다.")


class TestFactPoolSuffixKeys:
    """RC1 — v2 fact_pool 의 'tool#N' 키 정규화."""

    _POOL = {
        "get_district_summary#1": {
            "monthlySales": 14_700_000_000,
            "floatingPopulation": {"dailyAvg": 1_022_060},
            "insights": {"perStoreSales": 14_503_839},
        }
    }

    def test_typed_scalars_collected_from_suffix_keys(self):
        scalars = _collect_tool_scalars(self._POOL)
        assert ("get_district_summary", 14_700_000_000.0, "원") in scalars
        assert ("get_district_summary", 1_022_060.0, "명") in scalars

    def test_binding_succeeds_with_suffix_keys(self):
        text = "월 매출 147억원, 분기 유동인구 102만 2천명입니다."
        assert find_unbound_numbers(text, self._POOL) == []


class TestLabeledFallback:
    """RC4/S4 — fallback 은 무라벨 숫자 나열이 아니라 라벨된 스칼라."""

    def test_summary_lines_are_labeled(self):
        pool = {
            "get_district_summary#1": {
                "name": "건대입구역",
                "monthlySales": 1_470_000_000,
                "insights": {"perStoreSales": 14_503_839},
            }
        }
        text = grounded_fallback(pool)
        assert "월 추정 매출" in text
        assert "점포당 월매출" in text
        # 모든 항목 라인은 "라벨: 값" 형태 — 무라벨 나열 금지
        for line in text.splitlines():
            if line.startswith("- "):
                assert ": " in line

    def test_recommendations_carry_category_labels(self):
        pool = {
            "recommend_business#1": {
                "recommendations": [{"category_name": "편의점", "per_store_sales": 14_503_839, "store_count": 8}]
            }
        }
        text = grounded_fallback(pool)
        assert "편의점" in text


class TestAbstentionScope:
    """S2 — 데이터가 있는데 abstention 이 유출되면 안 된다."""

    def test_nonempty_pool_never_abstains(self):
        pool = {"get_estimated_sales#1": {"total_monthly_sales": 4_598_000_000}}
        text = grounded_fallback(pool)
        assert "가져오지 못했습니다" not in text
        assert "월 추정 매출" in text

    def test_cards_emitted_blocks_abstention(self):
        # 카드가 이미 나갔으면 pool 이 비어도 abstention 금지 — 카드로 안내
        text = grounded_fallback({}, cards_emitted=True)
        assert "가져오지 못했습니다" not in text
        assert "카드" in text


class TestFabricationDefenseRetained:
    """방어 회귀 가드 — P1 fix 가 원래의 날조 차단을 약화시키면 안 된다."""

    def test_empty_pool_still_abstains(self):
        text = grounded_fallback({})
        assert "가져오지 못했습니다" in text

    def test_fabricated_number_still_detected(self):
        pool = {"get_district_summary#1": {"monthlySales": 1_470_000_000}}
        unbound = find_unbound_numbers("이 상권의 월 매출은 999억원입니다.", pool)
        assert len(unbound) == 1
        assert unbound[0].value == 99_900_000_000.0


class TestGraduatedEnforcement:
    """RC4 — 마스킹 보존 vs 전체 대체 threshold."""

    def test_should_fallback_boundaries(self):
        assert should_fallback(3, 6) is True  # 정확히 50%
        assert should_fallback(3, 7) is False  # 50% 미만 → 마스킹
        assert should_fallback(2, 2) is False  # 3개 미만 → 마스킹
        assert should_fallback(5, 6) is True  # 다수 날조 → 폐기

    def test_mask_replaces_and_footnotes_once(self):
        text = "유동인구는 124,386명이고 매출은 999억원입니다."
        unbound = find_unbound_numbers(text, {})
        masked = mask_unbound(text, unbound)
        assert "124,386명" not in masked
        assert "999억원" not in masked
        assert masked.count("[미확인]") >= 2
        assert masked.count("※ 일부 수치는") == 1

    def test_mask_noop_without_numbers(self):
        text = "수치 없이 정성적 해석만 있는 답변입니다."
        assert mask_unbound(text, []) == text


class TestScaleGuard:
    """RC5/S8 — ×10/×100 자릿수 축소 오기 검출."""

    _POOL = {"get_district_summary#1": {"insights": {"perStoreSales": 14_503_839}}}

    def test_tenfold_understatement_detected(self):
        text = "점포당 월매출은 약 145만 원입니다."
        hits = find_scale_mismatches(text, self._POOL)
        assert len(hits) == 1
        assert hits[0].factor == 10
        assert hits[0].expected == 14_503_839.0

    def test_face_value_match_not_flagged(self):
        # 소액이라도 도구가 실제 반환한 값이면 오탐하지 않는다
        pool = {"get_estimated_sales#1": {"monthly_sales": 14_503_839, "rent_fee": 1_450_000}}
        assert find_scale_mismatches("월세는 145만 원입니다.", pool) == []

    def test_below_floor_amount_skipped(self):
        # 10만원 미만(객단가 등)은 스케일 검사 범위 밖 — 오탐 억제
        pool = {"simulate_revenue#1": {"monthly_avg": 5_000_000}}
        assert find_scale_mismatches("평균 객단가는 5만 원입니다.", pool) == []
