"""Finance MCP 도구 구현 — 6개 도구."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

from marketscope_mcp.finance.api_client import FinanceAPIClient

logger = logging.getLogger("mcp.finance.tools")

# ── 최저임금 내부 데이터 ──
_MINIMUM_WAGE = {
    2024: {"hourly": 9860, "monthly": 2_060_740, "effective_date": "2024-01-01"},
    2025: {"hourly": 10_030, "monthly": 2_096_270, "effective_date": "2025-01-01"},
    2026: {"hourly": 10_200, "monthly": 2_131_800, "effective_date": "2026-01-01"},
}

# ── 4대보험 요율 ──
_INSURANCE_RATES = {
    "국민연금": {"employee": 4.5, "employer": 4.5, "note": "소득의 9% (반반 부담)"},
    "건강보험": {"employee": 3.545, "employer": 3.545, "note": "소득의 7.09%"},
    "장기요양보험": {"employee": 0.4541, "employer": 0.4541, "note": "건강보험료의 12.81%"},
    "고용보험": {"employee": 0.9, "employer": 1.15, "note": "150인 미만 사업장 기준"},
    "산재보험": {"employee": 0.0, "employer": 0.7, "note": "업종별 상이 (음식점 평균)"},
}


# ── Tool 1: search_startup_loans ──

async def search_startup_loans(arguments: dict[str, Any], client: FinanceAPIClient) -> dict:
    """소상공인/창업자 대상 대출 상품 검색."""
    industry = arguments.get("industry", "")
    region = arguments.get("region", "서울")

    area_code = client.get_area_code(region)
    search_text = f"{industry} 창업 대출"

    bizinfo = await client.search_bizinfo(
        search_text=search_text,
        area_code=area_code,
        busi_type="financing",
        rows=10,
    )

    loans = []
    items = bizinfo.get("jsonArray", bizinfo.get("items", []))
    if isinstance(items, list):
        for item in items:
            loans.append({
                "product_id": item.get("inqireNo", ""),
                "product_name": item.get("pblancNm", ""),
                "institution": item.get("excInsttNm", ""),
                "loan_type": "정책자금",
                "target_audience": item.get("jrsdInsttNm", ""),
                "description": item.get("bsnsSumryCn", ""),
                "detail_url": item.get("detailUrl", ""),
                "application_period": item.get("reqstBeginEndDe", ""),
            })

    return {
        "industry": industry,
        "region": region,
        "total_count": len(loans),
        "loans": loans,
        "data_source": "기업마당_지원사업 + K-Startup",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Tool 2: search_government_subsidies ──

async def search_government_subsidies(arguments: dict[str, Any], client: FinanceAPIClient) -> dict:
    """정부/지자체 지원사업(보조금) 검색."""
    industry = arguments.get("industry", "")
    region = arguments.get("region", "서울")
    business_type = arguments.get("business_type", "창업")

    area_code = client.get_area_code(region)
    search_text = f"{industry} {business_type}"

    bizinfo = await client.search_bizinfo(
        search_text=search_text,
        area_code=area_code,
        busi_type="all",
        rows=10,
    )

    subsidies = []
    items = bizinfo.get("jsonArray", bizinfo.get("items", []))
    if isinstance(items, list):
        for item in items:
            subsidies.append({
                "subsidy_id": item.get("inqireNo", ""),
                "subsidy_name": item.get("pblancNm", ""),
                "institution": item.get("excInsttNm", ""),
                "support_type": item.get("bsnsSumryCn", "")[:20] if item.get("bsnsSumryCn") else "",
                "target_audience": item.get("jrsdInsttNm", ""),
                "description": item.get("bsnsSumryCn", ""),
                "detail_url": item.get("detailUrl", ""),
                "application_period": item.get("reqstBeginEndDe", ""),
                "status": "접수중",
            })

    return {
        "industry": industry,
        "region": region,
        "business_type": business_type,
        "total_count": len(subsidies),
        "subsidies": subsidies,
        "data_source": "기업마당_지원사업",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Tool 3: calculate_loan_repayment ──

async def calculate_loan_repayment(arguments: dict[str, Any], client: FinanceAPIClient) -> dict:
    """원리금균등 방식 대출 상환 스케줄 계산 (내부 계산, API 없음)."""
    principal = int(arguments.get("principal", 0))
    annual_rate = float(arguments.get("annual_rate", 0))
    term_months = int(arguments.get("term_months", 0))

    if principal <= 0 or annual_rate <= 0 or term_months <= 0:
        return {"error": "principal, annual_rate, term_months 파라미터가 모두 양수여야 합니다."}

    monthly_rate = annual_rate / 100 / 12
    # 원리금균등상환 공식
    monthly_payment = int(
        principal * monthly_rate * (1 + monthly_rate) ** term_months
        / ((1 + monthly_rate) ** term_months - 1)
    )

    schedule = []
    remaining = principal
    for month in range(1, term_months + 1):
        interest_part = int(remaining * monthly_rate)
        principal_part = monthly_payment - interest_part
        remaining = max(0, remaining - principal_part)
        schedule.append({
            "month": month,
            "payment": monthly_payment,
            "principal_part": principal_part,
            "interest_part": interest_part,
            "remaining_balance": remaining,
        })

    total_payment = monthly_payment * term_months
    total_interest = total_payment - principal

    return {
        "principal": principal,
        "annual_rate": annual_rate,
        "monthly_rate": round(monthly_rate * 100, 4),
        "term_months": term_months,
        "monthly_payment": monthly_payment,
        "total_payment": total_payment,
        "total_interest": total_interest,
        "schedule": schedule[:12],  # 첫 12개월만 반환 (전체는 너무 긴 경우)
        "schedule_total_months": len(schedule),
        "data_source": "internal_calculation",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Tool 4: get_franchise_disclosure ──

async def get_franchise_disclosure(arguments: dict[str, Any], client: FinanceAPIClient) -> dict:
    """프랜차이즈 정보공개서 조회."""
    brand_name = arguments.get("brand_name", "")
    if not brand_name:
        return {"error": "brand_name 파라미터가 필요합니다."}

    result = await client.search_franchise(brand_name)

    return {
        "brand_name": brand_name,
        "data_source": "franchise.ftc.go.kr",
        "status": result.get("status", "error"),
        "note": "프랜차이즈 정보공개서 HTML 파싱이 필요합니다. 향후 구조화 예정.",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Tool 5: get_minimum_wage ──

async def get_minimum_wage(arguments: dict[str, Any], client: FinanceAPIClient) -> dict:
    """최저임금 정보 조회 (내부 데이터)."""
    year = int(arguments.get("year", 2026))

    wage = _MINIMUM_WAGE.get(year)
    if not wage:
        closest = max(y for y in _MINIMUM_WAGE if y <= year) if any(y <= year for y in _MINIMUM_WAGE) else max(_MINIMUM_WAGE.keys())
        wage = _MINIMUM_WAGE[closest]
        year = closest

    return {
        "year": year,
        "hourly_wage": wage["hourly"],
        "monthly_wage_209h": wage["monthly"],
        "weekly_hours": 40,
        "monthly_hours": 209,
        "effective_date": wage["effective_date"],
        "data_source": "internal_data",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Tool 6: get_insurance_rates ──

async def get_insurance_rates(arguments: dict[str, Any], client: FinanceAPIClient) -> dict:
    """4대보험 요율 정보 조회 (내부 데이터)."""
    return {
        "insurance_rates": _INSURANCE_RATES,
        "total_employer_rate": sum(v["employer"] for v in _INSURANCE_RATES.values()),
        "total_employee_rate": sum(v["employee"] for v in _INSURANCE_RATES.values()),
        "note": "2026년 기준 요율 (업종별 산재보험요율은 상이할 수 있음)",
        "data_source": "internal_data",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Tool Registry ──

TOOL_REGISTRY: dict[str, Any] = {
    "finance.search_startup_loans": search_startup_loans,
    "finance.search_government_subsidies": search_government_subsidies,
    "finance.calculate_loan_repayment": calculate_loan_repayment,
    "finance.get_franchise_disclosure": get_franchise_disclosure,
    "finance.get_minimum_wage": get_minimum_wage,
    "finance.get_insurance_rates": get_insurance_rates,
}
