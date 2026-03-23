"""규제/인허가 MCP 도구 구현."""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

import httpx

logger = logging.getLogger("mcp.regulatory.tools")

# 업종별 기본 인허가 요건 데이터 (자체 구축)
_INDUSTRY_PERMITS: dict[str, list[dict[str, Any]]] = {
    "일반음식점": [
        {"permit_name": "영업신고", "authority": "구청 위생과", "days": 7, "cost": 0},
        {"permit_name": "위생교육 이수", "authority": "한국외식업중앙회", "days": 1, "cost": 30000},
        {"permit_name": "건강진단서", "authority": "보건소", "days": 3, "cost": 30000},
    ],
    "카페": [
        {"permit_name": "휴게음식점 영업신고", "authority": "구청 위생과", "days": 7, "cost": 0},
        {"permit_name": "위생교육 이수", "authority": "한국외식업중앙회", "days": 1, "cost": 30000},
    ],
    "주점": [
        {"permit_name": "유흥주점영업허가", "authority": "구청", "days": 14, "cost": 0},
        {"permit_name": "주류판매업면허", "authority": "세무서", "days": 7, "cost": 0},
        {"permit_name": "위생교육 이수", "authority": "한국외식업중앙회", "days": 1, "cost": 30000},
    ],
    "미용실": [
        {"permit_name": "미용업 신고", "authority": "구청 보건위생과", "days": 7, "cost": 0},
        {"permit_name": "미용사 자격증", "authority": "한국산업인력공단", "days": 0, "cost": 0},
    ],
    "학원": [
        {"permit_name": "학원설립운영등록", "authority": "교육청", "days": 30, "cost": 50000},
        {"permit_name": "소방시설완비증명", "authority": "소방서", "days": 7, "cost": 0},
    ],
}


async def get_permits(args: dict[str, Any], client: httpx.AsyncClient) -> dict[str, Any]:
    """업종별 필요 인허가 목록 조회."""
    industry = args.get("industry", "")

    # 키워드 매칭으로 업종 분류
    matched_key = None
    for key in _INDUSTRY_PERMITS:
        if key in industry:
            matched_key = key
            break

    if matched_key:
        permits = _INDUSTRY_PERMITS[matched_key]
        return {
            "industry": industry,
            "matched_category": matched_key,
            "permits": permits,
            "total_estimated_days": sum(p["days"] for p in permits),
            "total_estimated_cost": sum(p["cost"] for p in permits),
        }

    # 기본 사업자등록 + 일반적 인허가
    return {
        "industry": industry,
        "matched_category": "기타",
        "permits": [
            {"permit_name": "사업자등록", "authority": "세무서", "days": 3, "cost": 0},
        ],
        "total_estimated_days": 3,
        "total_estimated_cost": 0,
        "message": "정확한 업종 매칭 실패. LLM이 업종별 인허가 요건을 추정합니다.",
    }


async def get_zoning(args: dict[str, Any], client: httpx.AsyncClient) -> dict[str, Any]:
    """용도지역 정보 조회."""
    location = args.get("location", "")

    # 토지이용규제정보서비스 API 연동 시 실제 데이터 제공
    return {
        "location": location,
        "status": "estimated",
        "zoning_type": "일반상업지역",
        "message": "토지이용규제정보 API 연동 시 정확한 용도지역 제공 가능. LLM이 지역 특성을 기반으로 추정합니다.",
    }


async def get_business_requirements(args: dict[str, Any], client: httpx.AsyncClient) -> dict[str, Any]:
    """업종별 영업 요건 조회."""
    industry = args.get("industry", "")
    size_pyeong = args.get("size_pyeong", 20)

    return {
        "industry": industry,
        "size_pyeong": size_pyeong,
        "requirements": {
            "fire_safety": "소화기 1개 이상, 감지기 설치" if size_pyeong < 33 else "스프링클러 설치 의무",
            "accessibility": "장애인 편의시설 설치" if size_pyeong >= 50 else "해당 없음",
            "ventilation": "환기 설비 필수" if "음식" in industry or "카페" in industry else "권장",
        },
        "message": "일반적인 기준입니다. LLM이 구체적 요건을 보완합니다.",
    }


TOOL_REGISTRY: dict[str, Callable[..., Coroutine[Any, Any, dict[str, Any]]]] = {
    "get_permits": get_permits,
    "get_zoning": get_zoning,
    "get_business_requirements": get_business_requirements,
}
