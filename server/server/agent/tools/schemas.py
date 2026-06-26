"""LLM-facing tool schemas (input_schema + Korean description) for the agentic loop.

definitions.build_tool_definitions() merges these with the registry to produce the
Anthropic `tools` param. Descriptions state WHEN to call each tool — Opus 4.8
under-calls tools, so explicit trigger conditions raise the call rate.

Property names MUST match the tool function parameters (the loop calls fn(**args)).
"""

from __future__ import annotations

from typing import Any

_DISTRICT_CODE = {
    "type": "string",
    "description": "상권 코드 (예: '3120103'). 현재 선택된 상권 코드를 사용.",
}

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_district_summary": {
        "description": (
            "한 상권의 종합 요약(유동인구·매출·점포·업종 Top·안정성)을 한 번에 집계한다. "
            "사용자가 특정 상권을 '알려줘/요약/어때/분석'처럼 포괄적으로 물으면 가장 먼저 호출."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"district_code": _DISTRICT_CODE},
            "required": ["district_code"],
        },
    },
    "get_floating_population": {
        "description": (
            "한 상권의 시간대/성별/연령별 유동인구를 조회한다. '유동인구', '사람 많은 시간대', "
            "'성비/연령대' 등 인구 흐름을 물을 때 반드시 호출. 상권 비교에서 인구 수치가 "
            "필요하면 상권별로 각각 호출."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "district_code": _DISTRICT_CODE,
                "quarter": {
                    "type": "string",
                    "description": "분기 (예: '2025Q4'). 생략 시 최신 분기.",
                },
            },
            "required": ["district_code"],
        },
    },
    "get_estimated_sales": {
        "description": (
            "한 상권의 추정 매출(월 환산·시간대/요일/성별/연령별·추세)을 조회한다. "
            "'매출', '얼마 버는지', '장사 잘 되는지'를 물을 때 호출. 특정 업종이면 category_code 지정."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "district_code": _DISTRICT_CODE,
                "category_code": {
                    "type": "string",
                    "description": "업종 코드 (선택). 특정 업종 매출만 볼 때.",
                },
            },
            "required": ["district_code"],
        },
    },
    "get_store_info": {
        "description": (
            "한 상권의 점포 수·개폐업·폐업률·프랜차이즈·업종 Top을 조회한다. "
            "'점포 수', '폐업률', '경쟁', '프랜차이즈 비중'을 물을 때 호출."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "district_code": _DISTRICT_CODE,
                "category_code": {"type": "string", "description": "업종 코드 (선택)."},
            },
            "required": ["district_code"],
        },
    },
    "get_store_history": {
        "description": (
            "한 상권의 점포 안정성 점수·업종별 생존기간·리스크 업종을 분석한다. "
            "'위험', '안정성', '버틸 수 있는지', '폐업 위험'을 물을 때 호출."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"district_code": _DISTRICT_CODE},
            "required": ["district_code"],
        },
    },
    "get_population_info": {
        "description": (
            "한 상권의 상주인구·직장인구(성별·연령 분포)를 조회한다. "
            "'상주인구', '직장인구', '거주/근무 인구'를 물을 때 호출."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"district_code": _DISTRICT_CODE},
            "required": ["district_code"],
        },
    },
    "compare_districts": {
        "description": (
            "2~3개 상권의 핵심 지표를 비교하고 우위 상권을 가린다. '비교', 'A랑 B 중 어디', "
            "'어디가 더'처럼 복수 상권을 견줄 때 호출. 반드시 2~3개 상권 코드를 전달."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "district_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 3,
                    "description": "비교할 상권 코드 2~3개.",
                }
            },
            "required": ["district_codes"],
        },
    },
    "recommend_business": {
        "description": (
            "한 상권에 적합한 업종 Top5를 점수·근거와 함께 추천한다. '뭐 하면 좋을까', "
            "'추천 업종', '어떤 가게'를 물을 때 호출. 예산이 있으면 budget(만원) 전달."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "district_code": _DISTRICT_CODE,
                "budget": {"type": "integer", "description": "창업 예산 (만원, 선택)."},
                "preference": {"type": "string", "description": "선호 업종/조건 (선택)."},
            },
            "required": ["district_code"],
        },
    },
    "simulate_revenue": {
        "description": (
            "특정 상권+업종의 월 예상 매출을 p25/평균/p75 범위로 시뮬레이션한다. "
            "'얼마 벌까', '매출 시뮬레이션', '예상 매출'을 물을 때 호출. 업종(category_code)이 반드시 필요."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "district_code": _DISTRICT_CODE,
                "category_code": {"type": "string", "description": "업종 코드 (필수)."},
                "unit_price": {
                    "type": "integer",
                    "description": "객단가 (원, 선택). 생략 시 업종 기본값.",
                },
            },
            "required": ["district_code", "category_code"],
        },
    },
}
