"""User-Journey scenarios for MarketScope E2E Quality Sweep (2026-04-24).

Realistic usage patterns — NOT intent-coverage-focused:
  UJ1  single-district deep drill (연쇄 질문 on one area)
  UJ2  multi-area context switching
  UJ3  multi-district comparison (3-way and pick-best)
  UJ4  detailed report assembly (ending in PDF request or long synthesis)

Each journey reflects how a real 소상공인/투자자 explores.  Rubric on the FINAL turn only;
intermediate turns must still `done` (implicit) but are not scored individually.
"""
from __future__ import annotations


def _s(id: str, cat: str, turns: list[dict], expected: dict, notes: str = "") -> dict:
    return {"id": id, "category": cat, "turns": turns, "expected": expected, "notes": notes}


SCENARIOS: list[dict] = []


# =============================================================
# UJ1 — Single-district deep drill (연쇄 질문)  [4 journeys]
# =============================================================

SCENARIOS.append(_s("UJ1-cafe-startup-강남", "UJ1",
    [
        {"message": "강남역 상권 요약해줘"},
        {"message": "20대 유동인구 비중 얼마나 돼?"},
        {"message": "카페 경쟁 치열해?"},
        {"message": "이 업종으로 창업하면 예상 매출 시뮬 해줘"},
    ],
    {
        "no_xml_leak": True,
        "min_text_chars": 150,
        "intent_any": ["simulation", "sales_simulation", "revenue"],
        "tool_names_include_any": ["estimate_revenue", "simulate_revenue", "get_estimated_sales"],
    },
    "cafe startup journey on 강남역 — summary → demo → competition → simulation"))

SCENARIOS.append(_s("UJ1-restaurant-홍대", "UJ1",
    [
        {"message": "홍대 상권 어때?"},
        {"message": "한식집 몇 개나 있어?"},
        {"message": "점포 평균 생존기간은?"},
        {"message": "리스크 한 번 정리해줘"},
    ],
    {
        "no_xml_leak": True,
        "min_text_chars": 150,
        "intent_any": ["risk", "risk_analysis"],
        "tool_names_include_any": ["get_store_history", "get_store_info"],
    },
    "restaurant owner journey on 홍대 — summary → category → survival → risk"))

SCENARIOS.append(_s("UJ1-retail-성수", "UJ1",
    [
        {"message": "성수역 상권 요약"},
        {"message": "최근 점포 증가하는 추세야?"},
        {"message": "평일이랑 주말 매출 차이 보여줘"},
        {"message": "편의점 창업 어떨까?"},
    ],
    {
        "no_xml_leak": True,
        "min_text_chars": 150,
        "intent_any": ["recommendation", "category_analysis", "simulation"],
    },
    "retail journey 성수 — summary → growth → weekday/weekend → recommend"))

SCENARIOS.append(_s("UJ1-pub-건대", "UJ1",
    [
        {"message": "건대입구 유동인구 얼마나 돼?"},
        {"message": "저녁 피크 시간대 언제야?"},
        {"message": "주점 몇 개 있어?"},
        {"message": "이 상권에서 가장 안전한 창업 업종 추천해줘"},
    ],
    {
        "no_xml_leak": True,
        "min_text_chars": 150,
        "intent_any": ["recommendation"],
        "tool_names_include_any": ["recommend_business"],
    },
    "pub/night journey 건대 — floating → peak → competition → recommend"))


# =============================================================
# UJ2 — Multi-area context switching  [4 journeys]
# =============================================================

SCENARIOS.append(_s("UJ2-switch-강남-종로", "UJ2",
    [
        {"message": "강남역 상권 요약"},
        {"message": "종로3가역은 어때?"},
        {"message": "둘 중에 월 매출 더 높은 곳 어디야?"},
        {"message": "아까 강남 얘기로 돌아가서 추천 업종 알려줘"},
    ],
    {
        "no_xml_leak": True,
        "min_text_chars": 150,
        "intent_any": ["recommendation"],
        "card_district_name_any": ["강남역"],
        "coref_resolved_to": "강남",
    },
    "switch 강남→종로 → compare → back to 강남"))

SCENARIOS.append(_s("UJ2-switch-홍대-성수", "UJ2",
    [
        {"message": "홍대 상권 요약"},
        {"message": "성수역도 보여줘"},
        {"message": "이 두 곳 비교해줘"},
    ],
    {
        "no_xml_leak": True,
        "intent_any": ["comparison"],
        "tool_names_include": ["compare_districts"],
        "compare_district_count_min": 2,
    },
    "switch 홍대→성수 → '이 두 곳' coref compare"))

SCENARIOS.append(_s("UJ2-switch-명동-남대문", "UJ2",
    [
        {"message": "명동 상권 분석해줘"},
        {"message": "남대문시장은 어때?"},
        {"message": "관광지 특성은 어느 쪽이 더 강해?"},
    ],
    {
        "no_xml_leak": True,
        "min_text_chars": 150,
    },
    "switch 명동→남대문 → compare qualitative"))

SCENARIOS.append(_s("UJ2-switch-잠실-신촌", "UJ2",
    [
        {"message": "잠실역 상권 요약해줘"},
        {"message": "신촌은 어때?"},
        {"message": "대학가 상권이랑 번화가 상권 차이점 알려줘"},
    ],
    {
        "no_xml_leak": True,
        "min_text_chars": 200,
    },
    "switch 잠실→신촌 → qualitative diff"))


# =============================================================
# UJ3 — Multi-district comparison (3-way, pick-best)  [4 journeys]
# =============================================================

SCENARIOS.append(_s("UJ3-3way-major", "UJ3",
    [
        {"message": "강남역, 홍대, 성수역 세 곳 비교해줘"},
    ],
    {
        "no_xml_leak": True,
        "intent_any": ["comparison"],
        "tool_names_include": ["compare_districts"],
        "compare_district_count_min": 3,
        "min_text_chars": 200,
    },
    "3-way compare major hubs"))

SCENARIOS.append(_s("UJ3-3way-retail-hubs", "UJ3",
    [
        {"message": "여의도랑 광화문이랑 시청 중에 오피스 상권 어디가 가장 커?"},
    ],
    {
        "no_xml_leak": True,
        "intent_any": ["comparison"],
        "compare_district_count_min": 2,
        "min_text_chars": 150,
    },
    "3-way office districts"))

SCENARIOS.append(_s("UJ3-3way-young-picks", "UJ3",
    [
        {"message": "홍대, 성수, 건대 중에서 20대 유동인구 가장 많은 곳은 어디야?"},
    ],
    {
        "no_xml_leak": True,
        "intent_any": ["comparison"],
        "compare_district_count_min": 2,
        "must_contain_any_in_text": ["20대", "유동인구", "%"],
    },
    "pick-best 20대 target"))

SCENARIOS.append(_s("UJ3-3way-cafe-best", "UJ3",
    [
        {"message": "강남역이랑 잠실이랑 여의도 비교해서 카페 창업하기 가장 좋은 곳 추천해줘"},
    ],
    {
        "no_xml_leak": True,
        "intent_any": ["comparison", "recommendation"],
        "compare_district_count_min": 2,
        "min_text_chars": 200,
        "must_contain_any_in_text": ["카페", "추천", "매출"],
    },
    "3-way compare → recommend integrated"))


# =============================================================
# UJ4 — Detailed report assembly  [4 journeys]
# =============================================================

SCENARIOS.append(_s("UJ4-full-report-강남", "UJ4",
    [
        {"message": "강남역 상권 요약"},
        {"message": "유동인구 자세히 알려줘"},
        {"message": "매출 동향 자세히"},
        {"message": "위 내용 종합해서 리포트 PDF로 저장해줘"},
    ],
    {
        "no_xml_leak": True,
        "pdf_trigger": True,
        "min_text_chars": 100,
    },
    "4-step drill → PDF request"))

SCENARIOS.append(_s("UJ4-report-from-recommend", "UJ4",
    [
        {"message": "건대입구 창업 추천 업종 알려줘"},
        {"message": "첫번째 업종 리스크 분석"},
        {"message": "예상 매출 시뮬도 해줘"},
        {"message": "전부 묶어서 PDF 보고서로 만들어줘"},
    ],
    {
        "no_xml_leak": True,
        "pdf_trigger": True,
        "min_text_chars": 100,
    },
    "recommend → risk → sim → PDF"))

SCENARIOS.append(_s("UJ4-report-from-compare", "UJ4",
    [
        {"message": "홍대랑 성수역 비교해줘"},
        {"message": "홍대에 어떤 업종 추천해?"},
        {"message": "이 비교+추천 내용 상세 리포트 PDF로 저장"},
    ],
    {
        "no_xml_leak": True,
        "pdf_trigger": True,
    },
    "compare → recommend → PDF"))

SCENARIOS.append(_s("UJ4-long-synthesis", "UJ4",
    [
        {
            "message": (
                "이태원 관광특구 상권을 상세 분석 보고서 형태로 정리해줘. "
                "유동인구, 월 매출, 점포 수, 추천 업종, 리스크 모두 포함해서 "
                "길게 써줘"
            )
        },
    ],
    {
        "no_xml_leak": True,
        "min_text_chars": 500,
        "tool_names_include_any": ["get_district_summary", "get_floating_population", "get_estimated_sales"],
        "must_contain_any_in_text": ["유동인구", "매출", "점포"],
    },
    "single-turn long synthesis request"))


def all_scenarios() -> list[dict]:
    return SCENARIOS


if __name__ == "__main__":
    print(f"Total UJ scenarios: {len(SCENARIOS)}")
    by_cat: dict[str, int] = {}
    for s in SCENARIOS:
        by_cat[s["category"]] = by_cat.get(s["category"], 0) + 1
    for k in sorted(by_cat):
        print(f"  {k}: {by_cat[k]}  ({sum(len(x['turns']) for x in SCENARIOS if x['category']==k)} turns)")
    print(f"Total turns: {sum(len(s['turns']) for s in SCENARIOS)}")
