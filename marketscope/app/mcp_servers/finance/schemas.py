"""Finance MCP 서버 Pydantic 스키마."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LoanProduct(BaseModel):
    """대출 상품."""
    product_id: str
    product_name: str
    institution: str
    loan_type: str  # "정책자금", "보증", "융자" 등
    target_audience: str
    max_amount: Optional[int] = None
    interest_rate: Optional[str] = None
    repayment_period: Optional[str] = None
    application_period: str = ""
    description: str = ""
    detail_url: str = ""
    contact: Optional[str] = None


class LoanSearchResult(BaseModel):
    """대출 검색 결과."""
    industry: str
    region: str
    total_count: int
    loans: list[LoanProduct]
    data_source: str = "기업마당_지원사업 + K-Startup"
    retrieved_at: datetime


class Subsidy(BaseModel):
    """정부 지원사업."""
    subsidy_id: str
    subsidy_name: str
    institution: str
    support_type: str  # "금융", "기술", "인력" 등
    target_audience: str
    support_amount: Optional[str] = None
    application_period: str = ""
    description: str = ""
    detail_url: str = ""
    status: str = "접수중"


class SubsidySearchResult(BaseModel):
    """지원사업 검색 결과."""
    industry: str
    region: str
    business_type: str
    total_count: int
    subsidies: list[Subsidy]
    data_source: str = "기업마당_지원사업"
    retrieved_at: datetime


class MonthlyPayment(BaseModel):
    """월별 상환 내역."""
    month: int
    payment: int
    principal_part: int
    interest_part: int
    remaining_balance: int


class RepaymentSchedule(BaseModel):
    """대출 상환 스케줄."""
    principal: int
    annual_rate: float
    monthly_rate: float
    term_months: int
    monthly_payment: int
    total_payment: int
    total_interest: int
    schedule: list[MonthlyPayment]
    data_source: str = "internal_calculation"
    retrieved_at: datetime


class FranchiseInfo(BaseModel):
    """프랜차이즈 정보공개서."""
    brand_name: str
    franchisor: str
    industry_category: str
    initial_fee: Optional[int] = None
    royalty: Optional[str] = None
    total_stores: Optional[int] = None
    new_stores_year: Optional[int] = None
    closed_stores_year: Optional[int] = None
    avg_revenue_per_store: Optional[int] = None
    contract_period: Optional[str] = None
    detail_url: str = ""
    data_source: str = "franchise.ftc.go.kr"
    retrieved_at: datetime
