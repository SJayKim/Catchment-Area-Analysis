"""Abstention + attribution helpers for GAP-D.

Goal: when tool results are thin or empty, the Respond node must stop
generating confident prose from LLM priors ("the Seoul F&B close rate is
around 25%...") and either abstain or explicitly flag the gap. This
module ships three pieces:

1. :func:`classify_tool_results` — triage level based on critical fields.
2. :const:`ABSTENTION_PROMPT_ADDENDUM` — extra prompt text injected when
   status is ``partial`` or ``empty``.
3. :func:`scan_unattributed_numbers` — post-hoc regex check that flags
   numeric claims without a tool-attribution tag. Used for structlog
   telemetry today; future iterations can gate on it.
"""

from __future__ import annotations

import re
from typing import Literal

ResultStatus = Literal["full", "partial", "empty"]

# Critical field per tool — when this key is missing/falsy the tool result
# counts as an empty row. Derived from ``_compute_hints`` behaviour in
# ``respond.py`` and the Repository return shapes.
CRITICAL_FIELDS: dict[str, str] = {
    "get_floating_population": "daily_avg",
    "get_estimated_sales": "total_monthly_sales",
    "get_store_info": "total_stores",
    "get_store_history": "benchmarks",
    "get_population_info": "total_population",
    "compare_districts": "districts",
    "recommend_business": "recommendations",
    "get_district_summary": "store_info",
    "estimate_revenue": "monthly_avg",
}


def classify_tool_results(
    tool_results: dict[str, dict],
    tool_errors: dict[str, str] | None = None,
) -> ResultStatus:
    """Triage the Respond node's evidence level.

    - ``empty``: no successful results, or every successful result lacks its
      critical field. LLM should abstain with a fixed template.
    - ``partial``: some critical fields missing or the plan had errors on
      non-critical tools. LLM should mark gaps explicitly.
    - ``full``: every tool that ran produced its critical field.
    """
    if not tool_results:
        return "empty"

    missing = 0
    total = 0
    for name, data in tool_results.items():
        if not isinstance(data, dict) or "error" in data:
            missing += 1
            total += 1
            continue
        critical = CRITICAL_FIELDS.get(name)
        total += 1
        if critical is None:
            continue
        value = data.get(critical)
        if not value and value != 0:
            missing += 1

    if total == 0:
        return "empty"
    if missing == total:
        return "empty"
    if missing > 0 or (tool_errors and any(tool_errors.values())):
        return "partial"
    return "full"


ABSTENTION_PROMPT_ADDENDUM_EMPTY = """\

## ⚠️ 데이터 조회 실패 — 절대 준수 (MOST CRITICAL)
현재 [수집된 데이터] 섹션은 **비어 있습니다**. 어떤 tool 도 성공적으로 호출되지
않았거나 모두 error 상태입니다. 이 경우 **수치 출력 / 업종 Top N / 점포 수
/ 매출액 / 폐업률 등 구체적인 수치 주장은 단 하나도 생성해서는 안 됩니다.**

반드시 아래 템플릿 중 하나를 **그대로** 응답하세요 (수치/업종/순위 금지):

1) 도구 데이터 부재일 때:
> "요청하신 분석에 필요한 공공데이터를 조회하지 못했습니다. 다른 상권을
> 선택하시거나, 비교/추천 대상을 명확히 알려주시면 다시 분석해드리겠습니다."

2) 업종 미지정 (needs_category=True 포함) 일 때:
> "매출 시뮬레이션을 위해서는 구체적인 업종이 필요합니다. 예를 들어
> '카페', '한식음식점', '치킨전문점', '편의점' 등으로 말씀해 주세요."

3) 배제/clarification 후 대상 소실일 때:
> "말씀하신 조건으로는 분석할 대상이 남지 않았어요. 상권 이름과 분석
> 유형(요약/비교/추천/리스크/시뮬)을 다시 알려주세요."

**절대 금지 (위반 시 hallucination):**
- 외부 지식/업계 평균/뉴스/추측을 끌어와 수치를 생성
- "일반적으로 ~% 정도", "약 N억원" 같은 추정 표현
- 타 상권 사례 대체 ("성수동은 보통 …")
- 도구 함수명 (`recommend_business`, `get_estimated_sales`,
  `get_district_summary` 등)을 답변 텍스트에 노출. 어떤 경우에도 raw
  함수명은 사용자에게 보이지 않아야 함 — 출처는 자연어로만 표기.
- 업종 Top N / 추천 리스트 / 비교 표 / 수치 리포트 출력
"""

ABSTENTION_PROMPT_ADDENDUM_PARTIAL = """\

## ⚠️ 일부 데이터 누락
[수집된 데이터] 섹션의 일부 도구 결과에서 핵심 필드가 비어 있습니다.
비어 있는 항목은 **"해당 데이터 없음"** 으로 명시하고, 확보된 지표만으로
분석을 진행하세요. 비어 있는 항목에 대해 임의 수치 추정 금지.
"""

# LLM 이 raw 함수명 (`(get_district_summary)` 등) 을 사용자 응답에 노출하지
# 않도록 강하게 가드. 사용자에게 보이는 텍스트는 자연어 출처만 허용한다.
# 후처리 검증은 numeric_sanity (entity mismatch 까지 감지) 가 담당하므로
# attribution tag 자체는 더 이상 필요하지 않다.
ATTRIBUTION_PROMPT_RULE = """\

## 수치 주장 출처 가드 (필수)
구체적 수치(원/명/%/억/만/건/개)는 [수집된 데이터] 섹션에 있는 값만 사용하세요.
도구 데이터에 없는 수치는 쓰지 않습니다. 없으면 "해당 데이터 없음" 으로 표기하거나
정성적 설명으로 전환하세요.

**중요 — 사용자에게 노출 금지**:
- 절대로 raw 도구/함수 이름 (`get_district_summary`, `recommend_business`,
  `get_floating_population`, `compare_districts`, `estimate_revenue`,
  `get_store_info`, `get_store_history`, `get_population_info`,
  `get_estimated_sales`, `get_district_benchmarks`,
  `detect_floating_pop_anomaly`)을 답변 텍스트에 포함하지 마세요.
- 수치 옆에 ``(get_xxx)`` 같은 괄호 함수명 표기를 붙이지 마세요. 사용자에게는
  내부 구현 노출일 뿐입니다.
- 출처가 필요하면 자연어로만 (예: "공공데이터 기준", "유동인구 자료"
  "매출 추정 자료") 본문에 녹여서 표기하세요.

올바른 예: "월 추정 매출은 공공데이터 기준 5,320억원이며, 하루 평균 유동인구는 12만 4천명입니다."
잘못된 예: "월 추정 매출 5,320억원 (get_estimated_sales)" ← 함수명 노출 금지
잘못된 예: "유동인구 12만 4천명 `(get_floating_population)`" ← 함수명 노출 금지
잘못된 예: "업계 평균은 보통 25% 정도입니다" ← 출처 없는 추정 금지
"""


# 숫자(콤마/소수 허용) + 단위 패턴. 뒤에 ``(tool_snake_case)`` 가 바로 이어지면
# attribution 적용으로 간주하고 flag 하지 않음.
_NUMERIC_PATTERN = re.compile(
    r"(?P<num>\d[\d,\.]*)\s*(?P<unit>원|명|%|퍼센트|억|만|천|건|개|회|배)"
    r"(?P<tail>[^(\n]{0,6})",
    re.UNICODE,
)
_ATTRIBUTION_TAIL = re.compile(r"^\s*(?:원|명)?\s*\(\s*[a-z_][a-z0-9_]+\s*\)")


def scan_unattributed_numbers(text: str) -> list[str]:
    """Return every unattributed numeric snippet found in ``text``.

    Heuristic: a numeric + unit is considered attributed when immediately
    followed by ``(tool_snake_case)``. The scanner skips trivial numbers in
    list headers ("1위", "3개") when they are inside a short structural
    phrase — those are enumerations, not factual claims.
    """
    violations: list[str] = []
    for match in _NUMERIC_PATTERN.finditer(text):
        tail = match.group("tail")
        if _ATTRIBUTION_TAIL.match(tail):
            continue
        num = match.group("num")
        unit = match.group("unit")
        if unit in ("위", "개") and num in {"1", "2", "3", "4", "5"} and len(num) == 1:
            # Rank suffix or tiny enumeration — ignore.
            continue
        violations.append(f"{num}{unit}")
        if len(violations) >= 25:
            break
    return violations
