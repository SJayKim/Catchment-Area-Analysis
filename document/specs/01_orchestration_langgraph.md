# MarketScope AI - LangGraph 오케스트레이션 시스템 명세서

> **문서 버전**: 1.1.0
> **최종 수정일**: 2026-03-19
> **작성자**: MarketScope AI 아키텍처 팀
> **상태**: Draft (Phase 1 MVP 기준)
>
> ⚠️ **Phase 1 변경 사항**
> - **활성 에이전트**: population, revenue, competition, location (4개)
> - **비활성(Phase 2)**: trend, financial, risk, real_estate, regulatory
> - **Debate 시스템**: Phase 2 전면 비활성화
> - **AnalysisMode**: BASIC / COMPARISON / QUICK (DEEP은 Phase 2)

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [LangGraph State 정의](#2-langgraph-state-정의)
3. [그래프 토폴로지 (DAG)](#3-그래프-토폴로지-dag)
4. [조건부 엣지 (Conditional Edges)](#4-조건부-엣지-conditional-edges)
5. [노드 구현 패턴](#5-노드-구현-패턴)
6. [체크포인팅 전략](#6-체크포인팅-전략)
7. [병렬 실행](#7-병렬-실행)
8. [스트리밍](#8-스트리밍)
9. [타임아웃 및 서킷 브레이커](#9-타임아웃-및-서킷-브레이커)
10. [코드 구조](#10-코드-구조)
11. [사용자 시나리오](#11-사용자-시나리오)
12. [부록](#12-부록)

---

## 1. 시스템 개요

### 1.1 목적

MarketScope AI는 상권 분석을 수행하는 AI 에이전트 스웜(Agent Swarm) 시스템이다. LangGraph를 활용하여 DAG(Directed Acyclic Graph) 기반의 워크플로우 오케스트레이션을 구현한다. 각 전문 에이전트는 독립적인 분석 역할을 수행하며, 에이전트 간 데이터 의존성에 따라 실행 순서가 결정된다.

### 1.2 아키텍처 구성 요소

| 구성 요소 | 역할 | 수량 | 비고 |
|-----------|------|------|------|
| Commander Agent | 사용자 입력 분석, 실행 계획 수립 | 1 | [Phase 1] Sonnet 4.6 |
| Specialist Agent | 각 도메인별 분석 수행 | 4 (Phase 1) | [Phase 2] 추가 5개 |
| Debate System | 분석 결과의 검증 및 논쟁 | 0 (Phase 1) | [Phase 2] Advocate+Critic+Judge |
| Report Agent | 최종 보고서 생성 | 2 (Visualization + Narrative) | [Phase 1] 유지 |

### 1.3 전문 에이전트 목록

| 에이전트 ID | 이름 | 핵심 역할 | 상태 |
|-------------|------|-----------|------|
| `population` | 유동인구 분석 에이전트 | 상권 내 유동인구 패턴, 시간대별/요일별 분포 분석 | **[Phase 1] 활성** |
| `revenue` | 매출 분석 에이전트 | 업종별 매출 추정, 매출 트렌드 예측 | **[Phase 1] 활성** |
| `competition` | 경쟁 분석 에이전트 | 경쟁 업체 밀도, 시장 포화도, 차별화 기회 | **[Phase 1] 활성** |
| `location` | 입지 분석 에이전트 | 교통 접근성, 가시성, 주변 시설 시너지 | **[Phase 1] 활성** |
| `trend` | 트렌드 분석 에이전트 | 업종 트렌드, 소비자 선호도 변화, 신규 시장 기회 | [Phase 2] 비활성 |
| `financial` | 재무 분석 에이전트 | 투자 수익률(ROI), 손익분기점, 현금 흐름 예측 | [Phase 2] 비활성 |
| `risk` | 리스크 분석 에이전트 | 종합 리스크 평가, 시나리오 분석, 리스크 완화 방안 | [Phase 2] 비활성 |
| `real_estate` | 부동산 분석 에이전트 | 임대료, 권리금, 공실률, 부동산 시세 분석 | [Phase 2] 비활성 |
| `regulatory` | 규제 분석 에이전트 | 영업 허가, 용도지역 규제, 환경 규제, 법적 제약 | [Phase 2] 비활성 |

### 1.4 기술 스택

- **LangGraph**: `>=0.2.0` (StateGraph, fan-out/fan-in, checkpointing)
- **LangChain Core**: `>=0.3.0`
- **Python**: `>=3.11`
- **PostgreSQL**: 체크포인팅 백엔드
- **Redis**: 캐싱 및 실시간 스트리밍 Pub/Sub
- **SSE (Server-Sent Events)**: 프론트엔드 스트리밍

---

## 2. LangGraph State 정의

### 2.1 핵심 설계 원칙

MarketScope AI의 State는 **축적형(Accumulative)** 설계를 따른다. 각 에이전트 노드가 실행될 때마다 자신의 분석 결과를 State에 병합하며, 후속 노드는 이전 노드가 축적한 데이터를 참조한다.

- 불변성: 각 노드는 새로운 State 사본을 반환한다 (LangGraph 내부에서 자동 처리).
- 타입 안전성: `TypedDict`를 사용하여 모든 필드를 명시적으로 정의한다.
- 선택적 필드: 아직 실행되지 않은 에이전트의 결과는 `None`으로 유지된다.

### 2.2 State 스키마 전체 정의

```python
# state.py

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Any, Literal, Optional, TypedDict

from langgraph.graph import add_messages


# ──────────────────────────────────────────────
# 열거형 정의
# ──────────────────────────────────────────────

class AnalysisMode(str, Enum):
    """분석 모드 열거형 (Phase 1)"""
    BASIC = "basic"           # 단일 상권 기본 분석 (4개 에이전트)
    COMPARISON = "comparison"  # 두 상권 비교 분석
    QUICK = "quick"           # 특정 지표만 빠르게 조회 (2개 에이전트)
    # DEEP = "deep"           # [Phase 2] 심층 분석 (Debate 포함)


class NodeStatus(str, Enum):
    """노드 실행 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


# [Phase 2] DebateDecision — Debate 시스템 활성화 시 복원
# class DebateDecision(str, Enum):
#     """디베이트 수행 여부 결정"""
#     TRIGGER = "trigger"
#     SKIP = "skip"


# ──────────────────────────────────────────────
# 에이전트 결과 타입 정의
# ──────────────────────────────────────────────

class AgentConfidence(TypedDict):
    """에이전트 신뢰도 메타데이터"""
    score: float               # 0.0 ~ 1.0
    reasoning: str             # 신뢰도 산출 근거
    data_quality: float        # 데이터 품질 점수 0.0 ~ 1.0
    data_sources: list[str]    # 참조한 데이터 소스 목록


class PopulationResult(TypedDict):
    """유동인구 분석 결과"""
    daily_average: int                    # 일 평균 유동인구
    hourly_distribution: dict[str, int]   # 시간대별 유동인구 {"09": 1200, "10": 1500, ...}
    weekday_weekend_ratio: float          # 평일/주말 비율
    age_distribution: dict[str, float]    # 연령대별 비율 {"20s": 0.35, "30s": 0.28, ...}
    gender_ratio: dict[str, float]        # 성별 비율 {"male": 0.45, "female": 0.55}
    peak_hours: list[str]                 # 피크 시간대 목록
    seasonal_variation: dict[str, float]  # 계절별 변동 계수
    trend_direction: str                  # "increasing" | "decreasing" | "stable"
    confidence: AgentConfidence


class RevenueResult(TypedDict):
    """매출 분석 결과"""
    estimated_monthly_revenue: int                 # 월 매출 추정액 (원)
    revenue_range: dict[str, int]                  # {"min": ..., "max": ..., "median": ...}
    revenue_per_sqm: int                           # 평당 매출
    industry_average_revenue: int                  # 업종 평균 매출
    revenue_trend: list[dict[str, Any]]            # 월별 매출 추이
    revenue_by_time_slot: dict[str, int]           # 시간대별 매출 분포
    revenue_variance_pct: float                    # 매출 추정 분산율 (%)
    customer_unit_price: int                       # 객단가
    estimated_daily_customers: int                 # 일 예상 고객 수
    confidence: AgentConfidence


class CompetitionResult(TypedDict):
    """경쟁 분석 결과"""
    total_competitors: int                         # 경쟁 업체 수
    competitors_in_radius: dict[str, int]          # 반경별 경쟁 업체 수 {"100m": 3, "300m": 8, ...}
    market_saturation_index: float                 # 시장 포화도 지수 (0.0 ~ 1.0)
    top_competitors: list[dict[str, Any]]          # 주요 경쟁업체 정보
    differentiation_opportunities: list[str]       # 차별화 기회
    closure_rate: float                            # 폐업률
    average_operating_period: float                # 평균 영업 기간 (월)
    competitive_advantage_score: float             # 경쟁 우위 점수
    confidence: AgentConfidence


class LocationResult(TypedDict):
    """입지 분석 결과"""
    accessibility_score: float                     # 접근성 점수 (0.0 ~ 1.0)
    visibility_score: float                        # 가시성 점수
    nearby_facilities: list[dict[str, Any]]        # 주변 시설 목록
    transit_stations: list[dict[str, Any]]         # 인근 대중교통 정보
    parking_availability: str                      # 주차 가용성
    pedestrian_flow_direction: str                 # 주 보행 동선 방향
    synergy_score: float                           # 주변 시설 시너지 점수
    location_grade: str                            # 입지 등급 ("A" ~ "D")
    confidence: AgentConfidence


class TrendResult(TypedDict):
    """트렌드 분석 결과"""
    industry_growth_rate: float                    # 업종 성장률 (%)
    consumer_preference_shifts: list[dict[str, Any]]  # 소비자 선호도 변화
    emerging_trends: list[str]                     # 신규 트렌드 키워드
    social_media_sentiment: dict[str, float]       # 소셜미디어 감성 분석
    seasonal_demand_pattern: dict[str, float]      # 계절별 수요 패턴
    market_lifecycle_stage: str                    # 시장 수명주기 단계
    trend_relevance_score: float                   # 트렌드 관련성 점수
    confidence: AgentConfidence


class FinancialResult(TypedDict):
    """재무 분석 결과"""
    initial_investment: int                        # 초기 투자 비용 (원)
    monthly_fixed_costs: int                       # 월 고정비
    monthly_variable_costs: int                    # 월 변동비
    break_even_months: int                         # 손익분기 도달 예상 기간 (월)
    roi_1year: float                               # 1년 ROI (%)
    roi_3year: float                               # 3년 ROI (%)
    npv: int                                       # 순현재가치 (원)
    irr: float                                     # 내부수익률 (%)
    cash_flow_projection: list[dict[str, Any]]     # 월별 현금 흐름 예측
    profitability_grade: str                       # 수익성 등급 ("A" ~ "D")
    confidence: AgentConfidence


class RiskResult(TypedDict):
    """리스크 분석 결과"""
    overall_risk_score: float                      # 종합 리스크 점수 (0.0 ~ 1.0, 높을수록 위험)
    risk_categories: dict[str, float]              # 카테고리별 리스크 점수
    risk_factors: list[dict[str, Any]]             # 개별 리스크 요인
    scenario_analysis: dict[str, dict[str, Any]]   # 시나리오별 분석 (최선/기본/최악)
    mitigation_strategies: list[dict[str, Any]]    # 리스크 완화 전략
    risk_grade: str                                # 리스크 등급 ("A" ~ "D")
    confidence: AgentConfidence


class RealEstateResult(TypedDict):
    """부동산 분석 결과"""
    average_rent_per_sqm: int                      # 평균 평당 임대료 (원)
    rent_range: dict[str, int]                     # 임대료 범위
    key_money: int                                 # 권리금 (원)
    deposit: int                                   # 보증금 (원)
    vacancy_rate: float                            # 공실률 (%)
    rent_trend: str                                # 임대료 추세
    nearby_transactions: list[dict[str, Any]]      # 인근 거래 사례
    real_estate_grade: str                         # 부동산 등급
    price_competitiveness: float                   # 가격 경쟁력 점수
    confidence: AgentConfidence


class RegulatoryResult(TypedDict):
    """규제 분석 결과"""
    zoning_type: str                               # 용도지역
    permitted_uses: list[str]                      # 허용 업종 목록
    restricted_uses: list[str]                     # 제한 업종 목록
    required_permits: list[dict[str, Any]]         # 필요 인허가 목록
    environmental_regulations: list[str]           # 환경 규제
    special_district_rules: list[str]              # 특별구역 규정
    compliance_difficulty: str                     # 규제 준수 난이도
    regulatory_risk_score: float                   # 규제 리스크 점수
    confidence: AgentConfidence


# ──────────────────────────────────────────────
# 디베이트 관련 타입
# ──────────────────────────────────────────────

class DebateArgument(TypedDict):
    """디베이트 단일 주장"""
    agent_role: str            # "advocate" | "critic"
    round_number: int          # 라운드 번호
    argument: str              # 주장 내용
    evidence: list[str]        # 근거 목록
    rebuttal_to: Optional[str] # 반박 대상 주장 요약


class DebateResult(TypedDict):
    """디베이트 시스템 전체 결과"""
    triggered_by: list[str]                     # 디베이트 트리거 사유
    rounds: list[DebateArgument]                # 전체 라운드 기록
    advocate_final_position: str                # 옹호자 최종 입장
    critic_final_position: str                  # 비평가 최종 입장
    judge_verdict: str                          # 심판 최종 판결
    judge_score: float                          # 심판 신뢰도 점수 (0.0 ~ 1.0)
    revised_conclusions: dict[str, Any]         # 수정된 결론 (있는 경우)
    debate_summary: str                         # 디베이트 요약


# ──────────────────────────────────────────────
# 보고서 관련 타입
# ──────────────────────────────────────────────

class VisualizationOutput(TypedDict):
    """시각화 에이전트 출력"""
    charts: list[dict[str, Any]]               # 차트 데이터 [{type, title, data, config}, ...]
    maps: list[dict[str, Any]]                 # 지도 데이터
    tables: list[dict[str, Any]]               # 테이블 데이터
    infographics: list[dict[str, Any]]         # 인포그래픽 데이터


class NarrativeOutput(TypedDict):
    """내러티브 에이전트 출력"""
    executive_summary: str                     # 경영진 요약
    detailed_analysis: str                     # 상세 분석 본문
    key_findings: list[str]                    # 핵심 발견 사항
    recommendations: list[dict[str, Any]]      # 추천 사항 (우선순위 포함)
    risk_warnings: list[str]                   # 리스크 경고
    conclusion: str                            # 결론


# ──────────────────────────────────────────────
# Commander 계획 타입
# ──────────────────────────────────────────────

class CommanderPlan(TypedDict):
    """Commander 에이전트가 수립한 실행 계획"""
    analysis_mode: AnalysisMode
    target_location: str                       # 분석 대상 위치
    target_location_secondary: Optional[str]   # 비교 분석 시 두 번째 위치
    target_industry: str                       # 분석 대상 업종
    agents_to_run: list[str]                   # 실행할 에이전트 ID 목록
    agents_to_skip: list[str]                  # 건너뛸 에이전트 ID 목록
    force_debate: bool                         # 디베이트 강제 여부
    priority_focus: list[str]                  # 우선 분석 분야
    user_constraints: dict[str, Any]           # 사용자 제약 조건 (예산, 면적 등)
    estimated_duration_seconds: int            # 예상 소요 시간


# ──────────────────────────────────────────────
# 노드 실행 추적 타입
# ──────────────────────────────────────────────

class NodeExecution(TypedDict):
    """개별 노드 실행 메타데이터"""
    node_id: str
    status: NodeStatus
    started_at: Optional[str]                  # ISO 8601
    completed_at: Optional[str]                # ISO 8601
    duration_seconds: Optional[float]
    error_message: Optional[str]
    retry_count: int


# ──────────────────────────────────────────────
# 메인 State 정의
# ──────────────────────────────────────────────

class MarketScopeState(TypedDict):
    """
    MarketScope AI의 LangGraph 메인 State.

    모든 에이전트 노드가 이 State를 공유하며,
    각 노드는 실행 후 자신의 결과를 해당 필드에 기록한다.
    State는 축적형으로 운영되며, 이전 노드의 결과는 보존된다.
    """

    # ── 세션 메타데이터 ──
    session_id: str                                        # 고유 세션 식별자 (UUID)
    created_at: str                                        # 세션 생성 시각 (ISO 8601)
    updated_at: str                                        # 마지막 업데이트 시각

    # ── 사용자 입력 ──
    user_input: str                                        # 원본 사용자 입력 텍스트
    messages: Annotated[list, add_messages]                 # LangGraph 메시지 히스토리

    # ── Commander 계획 ──
    commander_plan: Optional[CommanderPlan]                 # Commander의 실행 계획

    # ── [Phase 1] Step 1: 독립 에이전트 결과 (병렬 실행) ──
    population_result: Optional[PopulationResult]          # [Phase 1] 유동인구
    competition_result: Optional[CompetitionResult]        # [Phase 1] 경쟁

    # ── [Phase 1] Step 2: 의존적 에이전트 결과 ──
    revenue_result: Optional[RevenueResult]                # [Phase 1] 매출 (depends on: population)
    location_result: Optional[LocationResult]              # [Phase 1] 입지 (depends on: population, competition)

    # ── [Phase 2] 비활성 에이전트 결과 ──
    # trend_result: Optional[TrendResult]
    # real_estate_result: Optional[RealEstateResult]
    # regulatory_result: Optional[RegulatoryResult]
    # financial_result: Optional[FinancialResult]
    # risk_result: Optional[RiskResult]

    # ── [Phase 2] Debate 시스템 ──
    # debate_decision: Optional[DebateDecision]
    # debate_trigger_reasons: list[str]
    # debate_result: Optional[DebateResult]

    # ── [Phase 1] 보고서 ──
    visualization_output: Optional[VisualizationOutput]
    narrative_output: Optional[NarrativeOutput]

    # ── 최종 출력 ──
    final_report: Optional[dict[str, Any]]                 # 통합 최종 보고서

    # ── 실행 추적 ──
    node_executions: Annotated[list[NodeExecution], operator.add]  # 노드 실행 기록 (append 방식)
    current_phase: int                                     # 현재 실행 Phase (1~3)
    progress_pct: float                                    # 전체 진행률 (0.0 ~ 100.0)

    # ── 에러 및 폴백 ──
    errors: Annotated[list[dict[str, Any]], operator.add]  # 에러 로그 (append 방식)
    has_critical_failure: bool                              # 치명적 실패 플래그

    # ── 비교 분석 전용 (comparison 모드) ──
    secondary_population_result: Optional[PopulationResult]
    secondary_competition_result: Optional[CompetitionResult]
    comparison_summary: Optional[dict[str, Any]]
```

### 2.3 State Reducer 설명

| 필드 | Reducer | 설명 |
|------|---------|------|
| `messages` | `add_messages` | LangGraph 내장 메시지 병합 리듀서. 중복 메시지 자동 제거 |
| `node_executions` | `operator.add` | 리스트 append 방식. 각 노드 실행 기록이 누적 |
| `errors` | `operator.add` | 리스트 append 방식. 에러 로그가 누적 |
| 나머지 필드 | 덮어쓰기 (기본) | 마지막 기록 값이 최종 값 |

### 2.4 State 초기화

```python
# state.py (계속)

def create_initial_state(session_id: str, user_input: str) -> MarketScopeState:
    """신규 분석 세션의 초기 State를 생성한다."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    return MarketScopeState(
        session_id=session_id,
        created_at=now,
        updated_at=now,
        user_input=user_input,
        messages=[],
        commander_plan=None,
        # [Phase 1] 활성 에이전트 결과
        population_result=None,
        competition_result=None,
        revenue_result=None,
        location_result=None,
        # [Phase 2] 비활성 필드 — 초기화 제외
        # trend_result=None,
        # real_estate_result=None,
        # regulatory_result=None,
        # financial_result=None,
        # risk_result=None,
        # debate_decision=None,
        # debate_trigger_reasons=[],
        # debate_result=None,
        visualization_output=None,
        narrative_output=None,
        final_report=None,
        node_executions=[],
        current_phase=0,
        progress_pct=0.0,
        errors=[],
        has_critical_failure=False,
        secondary_population_result=None,
        secondary_competition_result=None,
        comparison_summary=None,
    )
```

---

## 3. 그래프 토폴로지 (DAG)

### 3.1 전체 DAG 구조도

> **Phase 1 단순화 DAG** — 4개 에이전트, Debate 없음

```
                          ┌─────────────┐
                          │ user_input   │
                          └──────┬──────┘
                                 │
                                 ▼
                       ┌─────────────────┐
                       │ commander_plan   │  ← Sonnet 4.6
                       └────────┬────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
              ┌─────────┐           ┌─────────────┐
              │  pop     │           │     cmp      │   Step 1
              │ (Flash)  │           │   (Flash)    │   (병렬)
              └────┬─────┘           └──────┬───────┘
                   │                         │
                   └──────────┬──────────────┘
                              │
                     Step 1 fan-in (sync barrier)
                              │
                    ┌─────────┴──────────┐
                    │                    │
                    ▼                    ▼
              ┌─────────┐         ┌─────────────┐
              │  rev     │         │     loc      │   Step 2
              │ (Flash)  │         │   (Flash)    │   (병렬)
              └────┬─────┘         └──────┬───────┘
                   │                       │
                   └──────────┬────────────┘
                              │
                     Step 2 fan-in (sync barrier)
                              │
                              ▼
                    ┌──────────────────┐
                    │  commander_judge  │   ← Sonnet 4.6
                    └────────┬─────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
              ┌──────────┐     ┌──────────┐
              │   viz    │     │   nar    │   Step 3
              │  (Flash) │     │  (Flash) │   (병렬)
              └────┬─────┘     └────┬─────┘
                   │               │
                   └──────┬─────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │ final_output │
                   └──────────────┘
                          │
                          ▼
                        [END]

※ [Phase 2] 추가 예정:
   Step 1에 trend, real_estate, regulatory 병렬 추가
   Step 2 이후 financial, risk 순차 추가
   commander_judge 이후 Debate 시스템 조건부 삽입
```

### 3.2 노드 정의 상세

#### 3.2.1 전체 노드 목록 (Phase 1)

| 노드 ID | Step | 유형 | 설명 | 상태 |
|---------|------|------|------|------|
| `user_input` | Entry | 입력 처리 | 사용자 입력 파싱, 서울 상권 검증, State 초기화 | [Phase 1] |
| `commander_plan` | Entry | 계획 수립 | 실행 계획 수립, 에이전트 선택 (Sonnet 4.6) | [Phase 1] |
| `population_agent` | 1 | 분석 (독립) | 유동인구 분석 (Flash) | [Phase 1] |
| `competition_agent` | 1 | 분석 (독립) | 경쟁 분석 (Flash) | [Phase 1] |
| `step1_sync` | 1→2 | 동기화 | Step 1 병렬 실행 완료 대기 | [Phase 1] |
| `revenue_agent` | 2 | 분석 (의존) | 매출 분석 (← population) (Flash) | [Phase 1] |
| `location_agent` | 2 | 분석 (의존) | 입지 분석 (← population, competition) (Flash) | [Phase 1] |
| `step2_sync` | 2→3 | 동기화 | Step 2 완료 대기 | [Phase 1] |
| `commander_judge` | 3 | 최종 판단 | 결과 종합 및 품질 게이트 (Sonnet 4.6) | [Phase 1] |
| `visualization_agent` | 3 | 보고서 | 차트, 지도, 테이블 생성 (Flash) | [Phase 1] |
| `narrative_agent` | 3 | 보고서 | 텍스트 보고서 + 면책 조항 생성 (Flash) | [Phase 1] |
| `final_output` | Exit | 통합 | 최종 보고서 조합 및 출력 | [Phase 1] |
| `trend_agent` | - | 분석 | 트렌드 분석 | **[Phase 2]** |
| `real_estate_agent` | - | 분석 | 부동산 분석 | **[Phase 2]** |
| `regulatory_agent` | - | 분석 | 규제 분석 | **[Phase 2]** |
| `financial_agent` | - | 분석 | 재무 분석 | **[Phase 2]** |
| `risk_agent` | - | 분석 | 리스크 분석 | **[Phase 2]** |
| `debate_system` | - | 검증 | Advocate → Critic → Judge | **[Phase 2]** |

#### 3.2.2 노드 간 의존성 매트릭스 (Phase 1 활성 에이전트)

| 에이전트 | pop | cmp |
|----------|-----|-----|
| revenue  |  O  |     |
| location |  O  |  O  |

### 3.3 엣지 정의 상세

```python
# graph.py 의 엣지 정의 부분 (상세 로직은 10장 참조)

# Entry 엣지
"__start__" → "user_input"
"user_input" → "commander_plan"

# Commander → Phase 1 (fan-out)
"commander_plan" → ["population_agent", "competition_agent", "trend_agent",
                     "real_estate_agent", "regulatory_agent"]

# Phase 1 → Phase 1 Sync (fan-in)
["population_agent", "competition_agent", "trend_agent",
 "real_estate_agent", "regulatory_agent"] → "phase1_sync"

# Phase 1 Sync → Phase 2 (fan-out)
"phase1_sync" → ["revenue_agent", "location_agent"]

# Phase 2 → Phase 2 Sync (fan-in)
["revenue_agent", "location_agent"] → "phase2_sync"

# Phase 2 Sync → Phase 3
"phase2_sync" → "financial_agent"

# Phase 3 → Phase 4
"financial_agent" → "risk_agent"

# Phase 4 → Phase 5 (조건부)
"risk_agent" → "debate_check"
"debate_check" → conditional_edge(
    "debate_system"  if debate_decision == "trigger",
    "report_fan_out" if debate_decision == "skip"
)

# Phase 5 → Phase 6
"debate_system" → report_fan_out
report_fan_out → ["visualization_agent", "narrative_agent"]

# Phase 6 → Exit (fan-in)
["visualization_agent", "narrative_agent"] → "final_output"
"final_output" → "__end__"
```

### 3.4 Skip 동작 (부분 분석)

Commander가 `agents_to_skip`에 에이전트를 포함시키면 해당 노드는 즉시 `SKIPPED` 상태를 반환하고 결과는 `None`으로 유지된다. 후속 노드는 의존 데이터가 `None`일 때 대체 로직(fallback)을 사용하거나 해당 부분 분석을 생략한다.

```python
# 노드 skip 로직 예시
async def population_agent_node(state: MarketScopeState) -> dict:
    plan = state["commander_plan"]
    if plan and "population" in plan["agents_to_skip"]:
        return {
            "population_result": None,
            "node_executions": [NodeExecution(
                node_id="population_agent",
                status=NodeStatus.SKIPPED,
                started_at=None,
                completed_at=None,
                duration_seconds=None,
                error_message=None,
                retry_count=0,
            )],
        }
    # ... 정상 실행 로직
```

---

## 4. 조건부 엣지 (Conditional Edges)

### 4.1 디베이트 트리거 조건

디베이트 시스템은 분석 결과의 신뢰성에 의문이 있을 때 자동으로 활성화된다. `debate_check` 노드에서 아래 4가지 조건을 평가한다.

#### 조건 1: 에이전트 신뢰도 임계값 미달

```python
CONFIDENCE_THRESHOLD = 0.6

def check_low_confidence(state: MarketScopeState) -> list[str]:
    """신뢰도가 임계값 미만인 에이전트를 식별한다."""
    triggers = []
    result_fields = [
        ("population_result", "유동인구 분석"),
        ("revenue_result", "매출 분석"),
        ("competition_result", "경쟁 분석"),
        ("location_result", "입지 분석"),
        ("trend_result", "트렌드 분석"),
        ("financial_result", "재무 분석"),
        ("risk_result", "리스크 분석"),
        ("real_estate_result", "부동산 분석"),
        ("regulatory_result", "규제 분석"),
    ]

    for field_name, display_name in result_fields:
        result = state.get(field_name)
        if result is not None:
            confidence = result.get("confidence", {})
            score = confidence.get("score", 1.0)
            if score < CONFIDENCE_THRESHOLD:
                triggers.append(
                    f"{display_name} 신뢰도 부족 "
                    f"(score={score:.2f}, threshold={CONFIDENCE_THRESHOLD})"
                )

    return triggers
```

#### 조건 2: 매출 추정 분산율 초과

```python
REVENUE_VARIANCE_THRESHOLD = 50.0  # %

def check_revenue_variance(state: MarketScopeState) -> list[str]:
    """매출 추정치의 분산율이 50%를 초과하는지 확인한다."""
    triggers = []
    revenue = state.get("revenue_result")

    if revenue is not None:
        variance_pct = revenue.get("revenue_variance_pct", 0.0)
        if variance_pct > REVENUE_VARIANCE_THRESHOLD:
            triggers.append(
                f"매출 추정 분산율 초과 "
                f"(variance={variance_pct:.1f}%, threshold={REVENUE_VARIANCE_THRESHOLD}%)"
            )

    return triggers
```

#### 조건 3: 에이전트 간 결론 충돌

```python
def check_conflicting_conclusions(state: MarketScopeState) -> list[str]:
    """에이전트 간 상충하는 결론을 탐지한다."""
    triggers = []

    # 경쟁 분석 vs 매출 분석: 시장 포화인데 높은 매출 예측
    competition = state.get("competition_result")
    revenue = state.get("revenue_result")
    if competition and revenue:
        saturation = competition.get("market_saturation_index", 0.0)
        estimated_rev = revenue.get("estimated_monthly_revenue", 0)
        industry_avg = revenue.get("industry_average_revenue", 1)

        if saturation > 0.8 and estimated_rev > industry_avg * 1.2:
            triggers.append(
                "결론 충돌: 높은 시장 포화도(>{:.0%})에도 불구하고 "
                "업종 평균 대비 120% 이상의 매출 예측".format(saturation)
            )

    # 트렌드 분석 vs 경쟁 분석: 성장 트렌드인데 높은 폐업률
    trend = state.get("trend_result")
    if trend and competition:
        growth_rate = trend.get("industry_growth_rate", 0.0)
        closure_rate = competition.get("closure_rate", 0.0)

        if growth_rate > 5.0 and closure_rate > 0.15:
            triggers.append(
                "결론 충돌: 업종 성장률 {:.1f}%와 "
                "높은 폐업률 {:.1%} 간 불일치".format(growth_rate, closure_rate)
            )

    # 부동산 vs 재무: 높은 임대료인데 낮은 ROI 경고 없음
    real_estate = state.get("real_estate_result")
    financial = state.get("financial_result")
    if real_estate and financial:
        price_competitiveness = real_estate.get("price_competitiveness", 1.0)
        roi_1year = financial.get("roi_1year", 0.0)

        if price_competitiveness < 0.3 and roi_1year > 20.0:
            triggers.append(
                "결론 충돌: 임대료 경쟁력 하위 30%인데 "
                "1년 ROI {:.1f}% 예측은 낙관적".format(roi_1year)
            )

    # 입지 분석 vs 유동인구: 낮은 접근성인데 높은 유동인구
    location = state.get("location_result")
    population = state.get("population_result")
    if location and population:
        accessibility = location.get("accessibility_score", 1.0)
        daily_avg = population.get("daily_average", 0)

        if accessibility < 0.3 and daily_avg > 10000:
            triggers.append(
                "결론 충돌: 낮은 접근성 점수({:.2f})와 "
                "높은 유동인구({:,}명/일) 간 불일치".format(accessibility, daily_avg)
            )

    return triggers
```

#### 조건 4: 사용자 명시적 요청

```python
def check_user_force_debate(state: MarketScopeState) -> list[str]:
    """사용자가 심층 분석을 명시적으로 요청했는지 확인한다."""
    triggers = []
    plan = state.get("commander_plan")

    if plan and plan.get("force_debate", False):
        triggers.append("사용자 명시적 심층 분석 요청")

    # analysis_mode가 DEEP인 경우에도 트리거
    if plan and plan.get("analysis_mode") == AnalysisMode.DEEP:
        triggers.append("심층 분석 모드(DEEP) 지정됨")

    return triggers
```

### 4.2 통합 디베이트 판단 함수

```python
def debate_check_node(state: MarketScopeState) -> dict:
    """
    모든 디베이트 트리거 조건을 평가하고,
    하나라도 해당되면 디베이트를 트리거한다.
    """
    all_triggers = []
    all_triggers.extend(check_low_confidence(state))
    all_triggers.extend(check_revenue_variance(state))
    all_triggers.extend(check_conflicting_conclusions(state))
    all_triggers.extend(check_user_force_debate(state))

    if all_triggers:
        decision = DebateDecision.TRIGGER
    else:
        decision = DebateDecision.SKIP

    return {
        "debate_decision": decision,
        "debate_trigger_reasons": all_triggers,
        "node_executions": [NodeExecution(
            node_id="debate_check",
            status=NodeStatus.COMPLETED,
            started_at=_now_iso(),
            completed_at=_now_iso(),
            duration_seconds=0.0,
            error_message=None,
            retry_count=0,
        )],
    }


def route_after_debate_check(state: MarketScopeState) -> str:
    """LangGraph conditional_edge 라우팅 함수."""
    if state.get("debate_decision") == DebateDecision.TRIGGER:
        return "debate_system"
    return "report_fan_out"
```

### 4.3 Commander의 동적 에이전트 Skip 조건부 엣지

Commander 노드 이후, `agents_to_run` 목록에 따라 Phase 1 노드를 동적으로 구성한다. LangGraph의 `Send` API를 사용하여 실행할 노드만 fan-out한다.

```python
from langgraph.constants import Send

def route_after_commander(state: MarketScopeState) -> list[Send]:
    """Commander 계획에 따라 Phase 1 에이전트를 동적으로 선택한다."""
    plan = state["commander_plan"]
    agents_to_run = plan["agents_to_run"]

    phase1_agents = ["population", "competition", "trend", "real_estate", "regulatory"]
    sends = []

    for agent_id in phase1_agents:
        if agent_id in agents_to_run:
            sends.append(Send(f"{agent_id}_agent", state))
        else:
            # skip 노드에 Send하여 SKIPPED 상태 기록
            sends.append(Send(f"{agent_id}_agent", state))
            # (노드 내부에서 skip 여부를 판단)

    return sends
```

---

## 5. 노드 구현 패턴

### 5.1 표준 노드 래퍼 패턴

모든 에이전트 노드는 동일한 패턴을 따른다. 이 패턴은 입력 추출, 에이전트 호출, 출력 병합, 에러 처리의 4단계로 구성된다.

```python
# nodes.py

import asyncio
import traceback
from datetime import datetime, timezone
from typing import Any

from agents import (
    PopulationAgent,
    RevenueAgent,
    CompetitionAgent,
    # ... 기타 에이전트 import
)
from state import (
    MarketScopeState,
    NodeExecution,
    NodeStatus,
)


def _now_iso() -> str:
    """현재 시각을 ISO 8601 문자열로 반환한다."""
    return datetime.now(timezone.utc).isoformat()


def _calculate_progress(state: MarketScopeState, node_id: str) -> float:
    """
    완료된 노드 수에 기반하여 전체 진행률을 계산한다.

    가중치:
    - commander_plan: 5%
    - Phase 1 (5 agents): 각 8% = 40%
    - Phase 2 (2 agents): 각 8% = 16%
    - Phase 3 (1 agent): 10%
    - Phase 4 (1 agent): 10%
    - debate_check + debate: 9%
    - Phase 6 (2 agents): 각 5% = 10%
    """
    weight_map = {
        "user_input": 2.0,
        "commander_plan": 3.0,
        "population_agent": 8.0,
        "competition_agent": 8.0,
        "trend_agent": 8.0,
        "real_estate_agent": 8.0,
        "regulatory_agent": 8.0,
        "revenue_agent": 8.0,
        "location_agent": 8.0,
        "financial_agent": 10.0,
        "risk_agent": 10.0,
        "debate_check": 2.0,
        "debate_system": 7.0,
        "visualization_agent": 5.0,
        "narrative_agent": 5.0,
        "final_output": 3.0,
    }

    completed_nodes = set()
    for exec_record in state.get("node_executions", []):
        if exec_record["status"] in (NodeStatus.COMPLETED, NodeStatus.SKIPPED):
            completed_nodes.add(exec_record["node_id"])

    # 현재 노드도 완료된 것으로 포함
    completed_nodes.add(node_id)

    total = sum(weight_map.get(n, 0.0) for n in completed_nodes)
    return min(total, 100.0)
```

### 5.2 에이전트 노드 구현 예시

#### 5.2.1 독립 에이전트 노드 (Phase 1)

```python
# nodes.py (계속)

# ────────────────────────────────────────────────────
# 공통 노드 래퍼 데코레이터
# ────────────────────────────────────────────────────

from functools import wraps
from typing import Callable

NODE_TIMEOUTS: dict[str, float] = {
    "user_input": 5.0,
    "commander_plan": 15.0,
    "population_agent": 30.0,
    "competition_agent": 30.0,
    "trend_agent": 30.0,
    "real_estate_agent": 30.0,
    "regulatory_agent": 30.0,
    "revenue_agent": 30.0,
    "location_agent": 30.0,
    "financial_agent": 45.0,
    "risk_agent": 45.0,
    "debate_system": 120.0,
    "visualization_agent": 30.0,
    "narrative_agent": 30.0,
    "final_output": 10.0,
}

MAX_RETRIES = 2


def agent_node(node_id: str, result_field: str | None = None):
    """
    에이전트 노드 공통 래퍼 데코레이터.

    수행 내용:
    1. 실행 시작 시각 기록
    2. Commander plan에서 skip 여부 확인
    3. 타임아웃 적용하여 에이전트 실행
    4. 실패 시 최대 MAX_RETRIES 회 재시도
    5. 실행 완료/실패 메타데이터 기록
    6. 진행률 계산
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(state: MarketScopeState) -> dict[str, Any]:
            started_at = _now_iso()
            timeout = NODE_TIMEOUTS.get(node_id, 30.0)

            # ── Skip 확인 ──
            plan = state.get("commander_plan")
            if plan and node_id.replace("_agent", "") in plan.get("agents_to_skip", []):
                return {
                    **(({result_field: None}) if result_field else {}),
                    "node_executions": [NodeExecution(
                        node_id=node_id,
                        status=NodeStatus.SKIPPED,
                        started_at=started_at,
                        completed_at=_now_iso(),
                        duration_seconds=0.0,
                        error_message=None,
                        retry_count=0,
                    )],
                    "progress_pct": _calculate_progress(state, node_id),
                }

            # ── 실행 (재시도 포함) ──
            last_error = None
            for attempt in range(MAX_RETRIES + 1):
                try:
                    result = await asyncio.wait_for(
                        func(state),
                        timeout=timeout,
                    )
                    completed_at = _now_iso()
                    started_dt = datetime.fromisoformat(started_at)
                    completed_dt = datetime.fromisoformat(completed_at)
                    duration = (completed_dt - started_dt).total_seconds()

                    return {
                        **result,
                        "node_executions": [NodeExecution(
                            node_id=node_id,
                            status=NodeStatus.COMPLETED,
                            started_at=started_at,
                            completed_at=completed_at,
                            duration_seconds=duration,
                            error_message=None,
                            retry_count=attempt,
                        )],
                        "progress_pct": _calculate_progress(state, node_id),
                        "updated_at": completed_at,
                    }

                except asyncio.TimeoutError:
                    last_error = f"Timeout after {timeout}s (attempt {attempt + 1})"
                except Exception as e:
                    last_error = f"{type(e).__name__}: {str(e)} (attempt {attempt + 1})"
                    # 마지막 시도가 아니면 잠시 대기 후 재시도
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(1.0 * (attempt + 1))  # 지수 백오프

            # ── 모든 재시도 실패 ──
            completed_at = _now_iso()
            started_dt = datetime.fromisoformat(started_at)
            completed_dt = datetime.fromisoformat(completed_at)
            duration = (completed_dt - started_dt).total_seconds()

            return {
                **(({result_field: None}) if result_field else {}),
                "node_executions": [NodeExecution(
                    node_id=node_id,
                    status=NodeStatus.FAILED,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_seconds=duration,
                    error_message=last_error,
                    retry_count=MAX_RETRIES,
                )],
                "errors": [{
                    "node_id": node_id,
                    "error": last_error,
                    "timestamp": completed_at,
                    "traceback": traceback.format_exc(),
                }],
                "progress_pct": _calculate_progress(state, node_id),
                "updated_at": completed_at,
            }

        return wrapper
    return decorator
```

#### 5.2.2 구체적 에이전트 노드 구현

```python
# nodes.py (계속)

# ────────────────────────────────────────────────────
# Phase 1: 독립 에이전트 노드
# ────────────────────────────────────────────────────

@agent_node("population_agent", result_field="population_result")
async def population_agent_node(state: MarketScopeState) -> dict:
    """
    유동인구 분석 에이전트 노드.

    입력: commander_plan (target_location, target_industry)
    출력: population_result
    의존성: 없음 (독립)
    """
    plan = state["commander_plan"]
    agent = PopulationAgent()

    result = await agent.analyze(
        location=plan["target_location"],
        industry=plan["target_industry"],
        constraints=plan.get("user_constraints", {}),
    )

    return {"population_result": result}


@agent_node("competition_agent", result_field="competition_result")
async def competition_agent_node(state: MarketScopeState) -> dict:
    """
    경쟁 분석 에이전트 노드.

    입력: commander_plan (target_location, target_industry)
    출력: competition_result
    의존성: 없음 (독립)
    """
    plan = state["commander_plan"]
    agent = CompetitionAgent()

    result = await agent.analyze(
        location=plan["target_location"],
        industry=plan["target_industry"],
        constraints=plan.get("user_constraints", {}),
    )

    return {"competition_result": result}


@agent_node("trend_agent", result_field="trend_result")
async def trend_agent_node(state: MarketScopeState) -> dict:
    """트렌드 분석 에이전트 노드."""
    plan = state["commander_plan"]
    agent = TrendAgent()

    result = await agent.analyze(
        location=plan["target_location"],
        industry=plan["target_industry"],
    )

    return {"trend_result": result}


@agent_node("real_estate_agent", result_field="real_estate_result")
async def real_estate_agent_node(state: MarketScopeState) -> dict:
    """부동산 분석 에이전트 노드."""
    plan = state["commander_plan"]
    agent = RealEstateAgent()

    result = await agent.analyze(
        location=plan["target_location"],
        constraints=plan.get("user_constraints", {}),
    )

    return {"real_estate_result": result}


@agent_node("regulatory_agent", result_field="regulatory_result")
async def regulatory_agent_node(state: MarketScopeState) -> dict:
    """규제 분석 에이전트 노드."""
    plan = state["commander_plan"]
    agent = RegulatoryAgent()

    result = await agent.analyze(
        location=plan["target_location"],
        industry=plan["target_industry"],
    )

    return {"regulatory_result": result}


# ────────────────────────────────────────────────────
# Phase 2: 의존적 에이전트 노드
# ────────────────────────────────────────────────────

@agent_node("revenue_agent", result_field="revenue_result")
async def revenue_agent_node(state: MarketScopeState) -> dict:
    """
    매출 분석 에이전트 노드.

    입력: commander_plan, population_result
    출력: revenue_result
    의존성: population_result (유동인구 기반 매출 추정)
    """
    plan = state["commander_plan"]
    agent = RevenueAgent()

    result = await agent.analyze(
        location=plan["target_location"],
        industry=plan["target_industry"],
        population_data=state.get("population_result"),
        constraints=plan.get("user_constraints", {}),
    )

    return {"revenue_result": result}


@agent_node("location_agent", result_field="location_result")
async def location_agent_node(state: MarketScopeState) -> dict:
    """
    입지 분석 에이전트 노드.

    입력: commander_plan, population_result, competition_result
    출력: location_result
    의존성: population_result, competition_result
    """
    plan = state["commander_plan"]
    agent = LocationAgent()

    result = await agent.analyze(
        location=plan["target_location"],
        industry=plan["target_industry"],
        population_data=state.get("population_result"),
        competition_data=state.get("competition_result"),
    )

    return {"location_result": result}


# ────────────────────────────────────────────────────
# Phase 3: 재무 분석
# ────────────────────────────────────────────────────

@agent_node("financial_agent", result_field="financial_result")
async def financial_agent_node(state: MarketScopeState) -> dict:
    """
    재무 분석 에이전트 노드.

    입력: revenue_result, real_estate_result, competition_result
    출력: financial_result
    의존성: revenue_result, real_estate_result, competition_result
    """
    plan = state["commander_plan"]
    agent = FinancialAgent()

    result = await agent.analyze(
        location=plan["target_location"],
        industry=plan["target_industry"],
        revenue_data=state.get("revenue_result"),
        real_estate_data=state.get("real_estate_result"),
        competition_data=state.get("competition_result"),
        constraints=plan.get("user_constraints", {}),
    )

    return {"financial_result": result}


# ────────────────────────────────────────────────────
# Phase 4: 리스크 분석 (종합)
# ────────────────────────────────────────────────────

@agent_node("risk_agent", result_field="risk_result")
async def risk_agent_node(state: MarketScopeState) -> dict:
    """
    리스크 분석 에이전트 노드.

    입력: 모든 이전 에이전트 결과
    출력: risk_result
    의존성: ALL (population, competition, trend, real_estate,
            regulatory, revenue, location, financial)
    """
    plan = state["commander_plan"]
    agent = RiskAgent()

    result = await agent.analyze(
        location=plan["target_location"],
        industry=plan["target_industry"],
        population_data=state.get("population_result"),
        competition_data=state.get("competition_result"),
        trend_data=state.get("trend_result"),
        real_estate_data=state.get("real_estate_result"),
        regulatory_data=state.get("regulatory_result"),
        revenue_data=state.get("revenue_result"),
        location_data=state.get("location_result"),
        financial_data=state.get("financial_result"),
    )

    return {"risk_result": result}


# ────────────────────────────────────────────────────
# Phase 5: 디베이트 시스템
# ────────────────────────────────────────────────────

@agent_node("debate_system", result_field="debate_result")
async def debate_system_node(state: MarketScopeState) -> dict:
    """
    디베이트 시스템 노드.

    3단계 순차 실행:
    1. Advocate (옹호자): 분석 결과를 긍정적으로 해석
    2. Critic (비평가): 분석 결과의 약점과 리스크를 강조
    3. Judge (심판): 양측 주장을 종합하여 최종 판결

    디베이트는 최대 3라운드까지 진행한다.
    """
    trigger_reasons = state.get("debate_trigger_reasons", [])

    advocate = AdvocateAgent()
    critic = CriticAgent()
    judge = JudgeAgent()

    # 모든 분석 결과 수집
    all_results = {
        "population": state.get("population_result"),
        "competition": state.get("competition_result"),
        "trend": state.get("trend_result"),
        "real_estate": state.get("real_estate_result"),
        "regulatory": state.get("regulatory_result"),
        "revenue": state.get("revenue_result"),
        "location": state.get("location_result"),
        "financial": state.get("financial_result"),
        "risk": state.get("risk_result"),
    }

    rounds: list[DebateArgument] = []
    max_rounds = 3

    advocate_position = None
    critic_position = None

    for round_num in range(1, max_rounds + 1):
        # Advocate 주장
        advocate_arg = await advocate.argue(
            round_number=round_num,
            analysis_results=all_results,
            trigger_reasons=trigger_reasons,
            previous_rounds=rounds,
        )
        rounds.append(DebateArgument(
            agent_role="advocate",
            round_number=round_num,
            argument=advocate_arg["argument"],
            evidence=advocate_arg["evidence"],
            rebuttal_to=advocate_arg.get("rebuttal_to"),
        ))
        advocate_position = advocate_arg["argument"]

        # Critic 반론
        critic_arg = await critic.argue(
            round_number=round_num,
            analysis_results=all_results,
            trigger_reasons=trigger_reasons,
            previous_rounds=rounds,
        )
        rounds.append(DebateArgument(
            agent_role="critic",
            round_number=round_num,
            argument=critic_arg["argument"],
            evidence=critic_arg["evidence"],
            rebuttal_to=critic_arg.get("rebuttal_to"),
        ))
        critic_position = critic_arg["argument"]

    # Judge 최종 판결
    verdict = await judge.decide(
        analysis_results=all_results,
        debate_rounds=rounds,
        trigger_reasons=trigger_reasons,
    )

    debate_result = DebateResult(
        triggered_by=trigger_reasons,
        rounds=rounds,
        advocate_final_position=advocate_position or "",
        critic_final_position=critic_position or "",
        judge_verdict=verdict["verdict"],
        judge_score=verdict["confidence_score"],
        revised_conclusions=verdict.get("revised_conclusions", {}),
        debate_summary=verdict["summary"],
    )

    return {"debate_result": debate_result}


# ────────────────────────────────────────────────────
# Phase 6: 보고서 생성
# ────────────────────────────────────────────────────

@agent_node("visualization_agent", result_field="visualization_output")
async def visualization_agent_node(state: MarketScopeState) -> dict:
    """시각화 에이전트 노드. 모든 분석 결과를 차트/지도/테이블로 변환."""
    agent = VisualizationAgent()

    result = await agent.generate(
        population=state.get("population_result"),
        competition=state.get("competition_result"),
        trend=state.get("trend_result"),
        real_estate=state.get("real_estate_result"),
        revenue=state.get("revenue_result"),
        location=state.get("location_result"),
        financial=state.get("financial_result"),
        risk=state.get("risk_result"),
        debate=state.get("debate_result"),
        plan=state.get("commander_plan"),
    )

    return {"visualization_output": result}


@agent_node("narrative_agent", result_field="narrative_output")
async def narrative_agent_node(state: MarketScopeState) -> dict:
    """내러티브 에이전트 노드. 전체 분석 결과를 서술형 보고서로 작성."""
    agent = NarrativeAgent()

    result = await agent.generate(
        population=state.get("population_result"),
        competition=state.get("competition_result"),
        trend=state.get("trend_result"),
        real_estate=state.get("real_estate_result"),
        regulatory=state.get("regulatory_result"),
        revenue=state.get("revenue_result"),
        location=state.get("location_result"),
        financial=state.get("financial_result"),
        risk=state.get("risk_result"),
        debate=state.get("debate_result"),
        plan=state.get("commander_plan"),
    )

    return {"narrative_output": result}


# ────────────────────────────────────────────────────
# Entry / Exit 노드
# ────────────────────────────────────────────────────

async def user_input_node(state: MarketScopeState) -> dict:
    """사용자 입력 파싱 및 기본 검증."""
    user_input = state["user_input"]

    # 입력이 비어있는지 확인
    if not user_input or not user_input.strip():
        return {
            "has_critical_failure": True,
            "errors": [{"node_id": "user_input", "error": "빈 입력", "timestamp": _now_iso()}],
            "node_executions": [NodeExecution(
                node_id="user_input",
                status=NodeStatus.FAILED,
                started_at=_now_iso(),
                completed_at=_now_iso(),
                duration_seconds=0.0,
                error_message="빈 입력",
                retry_count=0,
            )],
        }

    return {
        "current_phase": 0,
        "progress_pct": 2.0,
        "node_executions": [NodeExecution(
            node_id="user_input",
            status=NodeStatus.COMPLETED,
            started_at=_now_iso(),
            completed_at=_now_iso(),
            duration_seconds=0.0,
            error_message=None,
            retry_count=0,
        )],
    }


@agent_node("commander_plan", result_field="commander_plan")
async def commander_plan_node(state: MarketScopeState) -> dict:
    """
    Commander 에이전트 노드.

    사용자 입력을 분석하여:
    1. 분석 모드 결정 (basic/comparison/quick/deep)
    2. 대상 위치 및 업종 추출
    3. 실행할 에이전트 목록 결정
    4. 건너뛸 에이전트 목록 결정
    5. 예상 소요 시간 계산
    """
    agent = CommanderAgent()
    plan = await agent.create_plan(user_input=state["user_input"])

    return {
        "commander_plan": plan,
        "current_phase": 1,
    }


async def final_output_node(state: MarketScopeState) -> dict:
    """
    최종 출력 조합 노드.

    visualization_output + narrative_output + debate_result를 통합하여
    최종 보고서를 구성한다.
    """
    final_report = {
        "session_id": state["session_id"],
        "analysis_mode": state["commander_plan"]["analysis_mode"] if state.get("commander_plan") else "unknown",
        "target_location": state["commander_plan"]["target_location"] if state.get("commander_plan") else "unknown",
        "target_industry": state["commander_plan"]["target_industry"] if state.get("commander_plan") else "unknown",
        "narrative": state.get("narrative_output"),
        "visualizations": state.get("visualization_output"),
        "debate": state.get("debate_result"),
        "metadata": {
            "created_at": state.get("created_at"),
            "completed_at": _now_iso(),
            "total_duration_seconds": _compute_total_duration(state),
            "agents_executed": _count_executed_agents(state),
            "agents_failed": _count_failed_agents(state),
            "debate_triggered": state.get("debate_decision") == DebateDecision.TRIGGER,
        },
    }

    return {
        "final_report": final_report,
        "progress_pct": 100.0,
        "current_phase": 6,
        "node_executions": [NodeExecution(
            node_id="final_output",
            status=NodeStatus.COMPLETED,
            started_at=_now_iso(),
            completed_at=_now_iso(),
            duration_seconds=0.0,
            error_message=None,
            retry_count=0,
        )],
    }


def _compute_total_duration(state: MarketScopeState) -> float:
    """전체 소요 시간을 계산한다."""
    executions = state.get("node_executions", [])
    total = sum(
        e.get("duration_seconds", 0.0) or 0.0
        for e in executions
    )
    return round(total, 2)


def _count_executed_agents(state: MarketScopeState) -> int:
    """실행 완료된 에이전트 수를 반환한다."""
    return sum(
        1 for e in state.get("node_executions", [])
        if e["status"] == NodeStatus.COMPLETED
    )


def _count_failed_agents(state: MarketScopeState) -> int:
    """실패한 에이전트 수를 반환한다."""
    return sum(
        1 for e in state.get("node_executions", [])
        if e["status"] == NodeStatus.FAILED
    )
```

---

## 6. 체크포인팅 전략

### 6.1 개요

MarketScope AI는 PostgreSQL 기반 체크포인팅을 사용하여 워크플로우의 중간 상태를 영구 저장한다. 이를 통해 다음을 보장한다:

- **이어하기(Resume)**: 서버 장애 시 마지막 체크포인트부터 재개
- **감사 추적(Audit Trail)**: 각 노드 실행 이력의 영구 보관
- **디버깅**: 특정 시점의 State를 재현하여 문제 진단
- **다중 사용자**: thread_id 기반으로 세션 격리

### 6.2 PostgreSQL 스키마

```sql
-- LangGraph PostgreSQL Checkpointer가 내부적으로 관리하는 테이블.
-- langgraph-checkpoint-postgres 패키지가 자동 생성.

-- 체크포인트 메인 테이블
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata_ JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

-- 체크포인트 기록 (writes) 테이블
CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- MarketScope 전용 인덱스 (성능 최적화)
CREATE INDEX idx_checkpoints_thread_created
    ON checkpoints (thread_id, created_at DESC);

CREATE INDEX idx_checkpoints_metadata
    ON checkpoints USING GIN (metadata_);
```

### 6.3 체크포인터 설정 코드

```python
# checkpointer.py

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


async def create_checkpointer() -> AsyncPostgresSaver:
    """
    PostgreSQL 비동기 체크포인터를 생성한다.

    환경변수:
    - DATABASE_URL: PostgreSQL 연결 문자열
      예: postgresql+asyncpg://user:pass@localhost:5432/marketscope
    """
    import os

    db_url = os.environ["DATABASE_URL"]

    checkpointer = AsyncPostgresSaver.from_conn_string(db_url)
    await checkpointer.setup()  # 테이블 자동 생성

    return checkpointer
```

### 6.4 체크포인팅 동작 방식

```
user_input ──[checkpoint]──▶ commander_plan ──[checkpoint]──▶ Phase 1 agents
     │                              │                              │
     │                              │                              ├─ population ──[checkpoint]
     │                              │                              ├─ competition ──[checkpoint]
     │                              │                              ├─ trend ──[checkpoint]
     │                              │                              ├─ real_estate ──[checkpoint]
     │                              │                              └─ regulatory ──[checkpoint]
     │                              │                              │
     │                              │                        [checkpoint] ── Phase 2 ...
```

- 모든 노드 실행 후 자동으로 체크포인트가 생성된다.
- 병렬 노드의 경우, 각 개별 노드 완료 시마다 체크포인트가 기록된다.
- fan-in 완료 시 통합 체크포인트가 추가로 기록된다.

### 6.5 세션 이어하기 (Resume)

```python
# resume.py

from langgraph.graph import StateGraph

async def resume_session(
    graph: StateGraph,
    checkpointer: AsyncPostgresSaver,
    thread_id: str,
) -> MarketScopeState:
    """
    중단된 세션을 마지막 체크포인트부터 재개한다.

    Args:
        graph: 컴파일된 LangGraph 그래프
        checkpointer: PostgreSQL 체크포인터
        thread_id: 재개할 세션의 thread ID

    Returns:
        최종 완료된 State
    """
    config = {"configurable": {"thread_id": thread_id}}

    # 마지막 체크포인트에서 자동으로 재개
    result = await graph.ainvoke(None, config=config)

    return result


async def get_session_history(
    checkpointer: AsyncPostgresSaver,
    thread_id: str,
) -> list[dict]:
    """특정 세션의 체크포인트 이력을 조회한다."""
    config = {"configurable": {"thread_id": thread_id}}
    history = []

    async for checkpoint in checkpointer.alist(config):
        history.append({
            "checkpoint_id": checkpoint.config["configurable"]["checkpoint_id"],
            "created_at": checkpoint.metadata.get("created_at"),
            "node": checkpoint.metadata.get("source"),
            "step": checkpoint.metadata.get("step"),
        })

    return history
```

### 6.6 체크포인트 보존 정책

| 항목 | 정책 |
|------|------|
| 보존 기간 | 완료된 세션: 30일, 미완료 세션: 7일 |
| 정리 주기 | 일 1회 (새벽 3시 KST) |
| 백업 | 일 1회 pg_dump |
| 최대 저장량 | 세션당 최대 50개 체크포인트 |

```python
# cleanup.py

async def cleanup_old_checkpoints(
    checkpointer: AsyncPostgresSaver,
    completed_retention_days: int = 30,
    incomplete_retention_days: int = 7,
) -> int:
    """
    보존 기간이 지난 체크포인트를 삭제한다.

    Returns:
        삭제된 체크포인트 수
    """
    # checkpointer 내부 DB 연결을 사용하여 직접 쿼리
    query = """
    DELETE FROM checkpoints
    WHERE (
        -- 완료된 세션: 30일 이상
        (metadata_->>'status' = 'completed'
         AND created_at < NOW() - INTERVAL '%s days')
        OR
        -- 미완료 세션: 7일 이상
        (metadata_->>'status' != 'completed'
         AND created_at < NOW() - INTERVAL '%s days')
    )
    RETURNING checkpoint_id;
    """
    # 실행 로직 (구현 세부사항은 DB 어댑터에 따라 다름)
    ...
```

---

## 7. 병렬 실행

### 7.1 LangGraph Fan-Out/Fan-In 패턴

LangGraph는 하나의 노드에서 여러 노드로 동시에 엣지를 연결하면 자동으로 병렬 실행한다. 이 시스템에서는 Phase 1과 Phase 6에서 fan-out/fan-in 패턴을 활용한다.

### 7.2 Phase 1 병렬 실행 구조

```python
# graph.py (Phase 1 부분)

from langgraph.graph import StateGraph, START, END

builder = StateGraph(MarketScopeState)

# Phase 1 에이전트 노드 등록
builder.add_node("population_agent", population_agent_node)
builder.add_node("competition_agent", competition_agent_node)
builder.add_node("trend_agent", trend_agent_node)
builder.add_node("real_estate_agent", real_estate_agent_node)
builder.add_node("regulatory_agent", regulatory_agent_node)

# Phase 1 동기화 노드
async def phase1_sync_node(state: MarketScopeState) -> dict:
    """Phase 1 완료 동기화. 모든 Phase 1 에이전트가 완료된 후 실행된다."""
    return {
        "current_phase": 2,
        "node_executions": [NodeExecution(
            node_id="phase1_sync",
            status=NodeStatus.COMPLETED,
            started_at=_now_iso(),
            completed_at=_now_iso(),
            duration_seconds=0.0,
            error_message=None,
            retry_count=0,
        )],
    }

builder.add_node("phase1_sync", phase1_sync_node)

# Fan-out: commander_plan → 5개 Phase 1 에이전트 (병렬)
builder.add_edge("commander_plan", "population_agent")
builder.add_edge("commander_plan", "competition_agent")
builder.add_edge("commander_plan", "trend_agent")
builder.add_edge("commander_plan", "real_estate_agent")
builder.add_edge("commander_plan", "regulatory_agent")

# Fan-in: 5개 Phase 1 에이전트 → phase1_sync
builder.add_edge("population_agent", "phase1_sync")
builder.add_edge("competition_agent", "phase1_sync")
builder.add_edge("trend_agent", "phase1_sync")
builder.add_edge("real_estate_agent", "phase1_sync")
builder.add_edge("regulatory_agent", "phase1_sync")
```

### 7.3 Phase 2 병렬 실행 구조

```python
# Phase 2 에이전트 노드 등록
builder.add_node("revenue_agent", revenue_agent_node)
builder.add_node("location_agent", location_agent_node)

async def phase2_sync_node(state: MarketScopeState) -> dict:
    """Phase 2 완료 동기화."""
    return {
        "current_phase": 3,
        "node_executions": [NodeExecution(
            node_id="phase2_sync",
            status=NodeStatus.COMPLETED,
            started_at=_now_iso(),
            completed_at=_now_iso(),
            duration_seconds=0.0,
            error_message=None,
            retry_count=0,
        )],
    }

builder.add_node("phase2_sync", phase2_sync_node)

# Fan-out: phase1_sync → revenue + location (병렬)
builder.add_edge("phase1_sync", "revenue_agent")
builder.add_edge("phase1_sync", "location_agent")

# Fan-in: revenue + location → phase2_sync
builder.add_edge("revenue_agent", "phase2_sync")
builder.add_edge("location_agent", "phase2_sync")
```

### 7.4 Phase 6 병렬 실행 구조

```python
# Phase 6: 보고서 에이전트 (병렬)
builder.add_node("visualization_agent", visualization_agent_node)
builder.add_node("narrative_agent", narrative_agent_node)

async def report_fan_out_node(state: MarketScopeState) -> dict:
    """보고서 생성 전 동기화 포인트."""
    return {
        "current_phase": 6,
        "node_executions": [NodeExecution(
            node_id="report_fan_out",
            status=NodeStatus.COMPLETED,
            started_at=_now_iso(),
            completed_at=_now_iso(),
            duration_seconds=0.0,
            error_message=None,
            retry_count=0,
        )],
    }

builder.add_node("report_fan_out", report_fan_out_node)

# Fan-out
builder.add_edge("report_fan_out", "visualization_agent")
builder.add_edge("report_fan_out", "narrative_agent")

# Fan-in
builder.add_edge("visualization_agent", "final_output")
builder.add_edge("narrative_agent", "final_output")
```

### 7.5 병렬 실행 시 State 충돌 방지

LangGraph는 병렬 노드가 동일 필드에 기록하는 것을 금지하지 않지만, MarketScope AI에서는 각 에이전트가 **고유 필드**에만 기록하도록 설계하여 충돌을 원천 방지한다.

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ population_agent │   │ competition_agent│   │  trend_agent    │
│                  │   │                  │   │                 │
│ writes:          │   │ writes:          │   │ writes:         │
│ population_result│   │ competition_result│  │ trend_result    │
│ node_executions  │   │ node_executions  │   │ node_executions │
│ (append reducer) │   │ (append reducer) │   │ (append reducer)│
└─────────────────┘   └─────────────────┘   └─────────────────┘
```

- 분석 결과 필드: 에이전트별로 고유 (`population_result`, `competition_result` 등)
- `node_executions`: `operator.add` reducer로 안전하게 append
- `errors`: `operator.add` reducer로 안전하게 append
- `progress_pct`, `current_phase`: 덮어쓰기 (마지막 완료 노드 기준, 최종적으로 sync 노드에서 보정)

---

## 8. 스트리밍

### 8.1 아키텍처 개요

프론트엔드에 실시간 진행 상황을 전달하기 위해 **SSE(Server-Sent Events)** 를 사용한다. LangGraph의 `astream_events` API를 통해 노드 실행 이벤트를 수신하고, FastAPI의 SSE 엔드포인트로 브릿지한다.

```
┌────────────┐     SSE      ┌──────────┐    astream_events    ┌───────────┐
│  Frontend  │◄────────────│  FastAPI  │◄────────────────────│  LangGraph │
│ (React)    │             │  SSE EP   │                      │   Graph    │
└────────────┘              └──────────┘                      └───────────┘
```

### 8.2 SSE 이벤트 타입 정의

```python
# streaming.py

from dataclasses import dataclass
from enum import Enum
from typing import Any
import json


class SSEEventType(str, Enum):
    """SSE 이벤트 타입 열거형"""
    # 워크플로우 레벨 이벤트
    WORKFLOW_STARTED = "workflow:started"
    WORKFLOW_COMPLETED = "workflow:completed"
    WORKFLOW_FAILED = "workflow:failed"

    # 노드 레벨 이벤트
    NODE_STARTED = "node:started"
    NODE_COMPLETED = "node:completed"
    NODE_FAILED = "node:failed"
    NODE_SKIPPED = "node:skipped"

    # 진행률 이벤트
    PROGRESS_UPDATE = "progress:update"

    # 중간 결과 이벤트
    INTERMEDIATE_RESULT = "result:intermediate"

    # 디베이트 이벤트
    DEBATE_ROUND = "debate:round"
    DEBATE_VERDICT = "debate:verdict"


@dataclass
class SSEEvent:
    """SSE 이벤트 데이터 구조"""
    event_type: SSEEventType
    data: dict[str, Any]
    session_id: str

    def to_sse_string(self) -> str:
        """SSE 프로토콜 형식 문자열로 변환한다."""
        payload = json.dumps({
            "session_id": self.session_id,
            **self.data,
        }, ensure_ascii=False)
        return f"event: {self.event_type.value}\ndata: {payload}\n\n"
```

### 8.3 스트리밍 브릿지 구현

```python
# streaming.py (계속)

from collections.abc import AsyncGenerator
from langgraph.graph.state import CompiledStateGraph


# 노드별 한국어 표시 이름
NODE_DISPLAY_NAMES: dict[str, str] = {
    "user_input": "입력 분석",
    "commander_plan": "실행 계획 수립",
    "population_agent": "유동인구 분석",
    "competition_agent": "경쟁 분석",
    "trend_agent": "트렌드 분석",
    "real_estate_agent": "부동산 분석",
    "regulatory_agent": "규제 분석",
    "revenue_agent": "매출 분석",
    "location_agent": "입지 분석",
    "financial_agent": "재무 분석",
    "risk_agent": "리스크 분석",
    "debate_check": "디베이트 검토",
    "debate_system": "디베이트 진행",
    "visualization_agent": "시각화 생성",
    "narrative_agent": "보고서 작성",
    "final_output": "최종 보고서 조합",
}

# 노드별 Phase 매핑
NODE_PHASE_MAP: dict[str, int] = {
    "user_input": 0,
    "commander_plan": 0,
    "population_agent": 1,
    "competition_agent": 1,
    "trend_agent": 1,
    "real_estate_agent": 1,
    "regulatory_agent": 1,
    "revenue_agent": 2,
    "location_agent": 2,
    "financial_agent": 3,
    "risk_agent": 4,
    "debate_check": 5,
    "debate_system": 5,
    "visualization_agent": 6,
    "narrative_agent": 6,
    "final_output": 6,
}


async def stream_graph_events(
    graph: CompiledStateGraph,
    initial_state: MarketScopeState,
    thread_id: str,
) -> AsyncGenerator[SSEEvent, None]:
    """
    LangGraph 실행 이벤트를 SSE 이벤트로 변환하여 스트리밍한다.

    Args:
        graph: 컴파일된 LangGraph 그래프
        initial_state: 초기 State
        thread_id: 세션 thread ID

    Yields:
        SSEEvent 객체
    """
    config = {"configurable": {"thread_id": thread_id}}
    session_id = initial_state["session_id"]

    # 워크플로우 시작 이벤트
    yield SSEEvent(
        event_type=SSEEventType.WORKFLOW_STARTED,
        data={"message": "분석을 시작합니다."},
        session_id=session_id,
    )

    completed_nodes = set()
    total_nodes = 0

    try:
        async for event in graph.astream_events(
            initial_state,
            config=config,
            version="v2",
        ):
            event_kind = event.get("event")
            node_name = event.get("name", "")

            # ── 노드 시작 이벤트 ──
            if event_kind == "on_chain_start" and node_name in NODE_DISPLAY_NAMES:
                total_nodes += 1
                yield SSEEvent(
                    event_type=SSEEventType.NODE_STARTED,
                    data={
                        "node_id": node_name,
                        "node_name": NODE_DISPLAY_NAMES[node_name],
                        "phase": NODE_PHASE_MAP.get(node_name, 0),
                        "message": f"{NODE_DISPLAY_NAMES[node_name]} 시작...",
                    },
                    session_id=session_id,
                )

            # ── 노드 완료 이벤트 ──
            elif event_kind == "on_chain_end" and node_name in NODE_DISPLAY_NAMES:
                completed_nodes.add(node_name)
                output = event.get("data", {}).get("output", {})
                progress = output.get("progress_pct", 0.0) if isinstance(output, dict) else 0.0

                yield SSEEvent(
                    event_type=SSEEventType.NODE_COMPLETED,
                    data={
                        "node_id": node_name,
                        "node_name": NODE_DISPLAY_NAMES[node_name],
                        "phase": NODE_PHASE_MAP.get(node_name, 0),
                        "message": f"{NODE_DISPLAY_NAMES[node_name]} 완료",
                    },
                    session_id=session_id,
                )

                # 진행률 업데이트
                yield SSEEvent(
                    event_type=SSEEventType.PROGRESS_UPDATE,
                    data={
                        "progress_pct": progress,
                        "completed_nodes": list(completed_nodes),
                        "total_expected_nodes": _estimate_total_nodes(initial_state),
                    },
                    session_id=session_id,
                )

                # 중간 결과 전송 (분석 에이전트인 경우)
                result_field = _get_result_field(node_name)
                if result_field and isinstance(output, dict) and result_field in output:
                    result_data = output[result_field]
                    if result_data is not None:
                        yield SSEEvent(
                            event_type=SSEEventType.INTERMEDIATE_RESULT,
                            data={
                                "node_id": node_name,
                                "result_field": result_field,
                                "summary": _extract_summary(result_data),
                            },
                            session_id=session_id,
                        )

        # 워크플로우 완료 이벤트
        yield SSEEvent(
            event_type=SSEEventType.WORKFLOW_COMPLETED,
            data={
                "message": "분석이 완료되었습니다.",
                "total_nodes_executed": len(completed_nodes),
            },
            session_id=session_id,
        )

    except Exception as e:
        yield SSEEvent(
            event_type=SSEEventType.WORKFLOW_FAILED,
            data={
                "message": f"분석 중 오류가 발생했습니다: {str(e)}",
                "error_type": type(e).__name__,
            },
            session_id=session_id,
        )


def _get_result_field(node_name: str) -> str | None:
    """노드 이름에 해당하는 결과 필드명을 반환한다."""
    mapping = {
        "population_agent": "population_result",
        "competition_agent": "competition_result",
        "trend_agent": "trend_result",
        "real_estate_agent": "real_estate_result",
        "regulatory_agent": "regulatory_result",
        "revenue_agent": "revenue_result",
        "location_agent": "location_result",
        "financial_agent": "financial_result",
        "risk_agent": "risk_result",
    }
    return mapping.get(node_name)


def _extract_summary(result: dict) -> dict:
    """에이전트 결과에서 프론트엔드 표시용 요약을 추출한다."""
    summary = {}
    confidence = result.get("confidence", {})
    if confidence:
        summary["confidence_score"] = confidence.get("score", 0.0)

    # 주요 수치 필드를 자동 추출
    for key, value in result.items():
        if key == "confidence":
            continue
        if isinstance(value, (int, float, str)) and not key.startswith("_"):
            summary[key] = value

    return summary


def _estimate_total_nodes(state: MarketScopeState) -> int:
    """실행 예정인 총 노드 수를 추정한다."""
    plan = state.get("commander_plan")
    if plan:
        base = len(plan.get("agents_to_run", []))
        # +4: user_input, commander_plan, debate_check, final_output
        # +2: visualization, narrative
        return base + 6
    return 16  # 기본값: 모든 노드 실행 가정
```

### 8.4 FastAPI SSE 엔드포인트

```python
# api/routes/analysis.py

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import uuid

router = APIRouter()


@router.post("/api/v1/analysis/stream")
async def stream_analysis(request: Request):
    """
    상권 분석 스트리밍 엔드포인트.

    Request Body:
        {"query": "강남역 카페 분석"}

    Response: SSE 스트림
    """
    body = await request.json()
    user_input = body["query"]
    session_id = str(uuid.uuid4())
    thread_id = f"session_{session_id}"

    # 그래프 및 체크포인터 초기화
    graph = await build_graph()
    initial_state = create_initial_state(session_id, user_input)

    async def event_generator():
        async for event in stream_graph_events(graph, initial_state, thread_id):
            yield event.to_sse_string()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx 버퍼링 비활성화
        },
    )
```

### 8.5 프론트엔드 SSE 수신 예시

```typescript
// frontend/src/hooks/useAnalysisStream.ts

interface AnalysisEvent {
  session_id: string;
  node_id?: string;
  node_name?: string;
  phase?: number;
  progress_pct?: number;
  message?: string;
}

function useAnalysisStream(query: string) {
  const eventSource = new EventSource(`/api/v1/analysis/stream`);

  eventSource.addEventListener('node:started', (e: MessageEvent) => {
    const data: AnalysisEvent = JSON.parse(e.data);
    console.log(`[Phase ${data.phase}] ${data.node_name} 시작...`);
  });

  eventSource.addEventListener('progress:update', (e: MessageEvent) => {
    const data: AnalysisEvent = JSON.parse(e.data);
    updateProgressBar(data.progress_pct);
  });

  eventSource.addEventListener('result:intermediate', (e: MessageEvent) => {
    const data = JSON.parse(e.data);
    renderIntermediateResult(data.node_id, data.summary);
  });

  eventSource.addEventListener('workflow:completed', (e: MessageEvent) => {
    eventSource.close();
    fetchFinalReport(query);
  });
}
```

### 8.6 진행률 계산 상세 로직

진행률은 가중 합계 방식으로 계산한다. 각 Phase와 노드에 아래 가중치를 부여한다.

```
Phase 0 (Entry):       user_input(2%) + commander_plan(3%)     =  5%
Phase 1 (Independent): 5 agents x 8%                          = 40%
Phase 2 (Dependent):   2 agents x 8%                          = 16%
Phase 3 (Financial):   1 agent  x 10%                         = 10%
Phase 4 (Risk):        1 agent  x 10%                         = 10%
Phase 5 (Debate):      debate_check(2%) + debate_system(7%)   =  9%
Phase 6 (Report):      2 agents x 5%                          = 10%
                                                         합계 = 100%
```

skip된 에이전트의 가중치는 자동으로 재분배하지 않고 건너뛰어 해당 퍼센트만큼 즉시 진행된다. 디베이트가 skip되면 7% 점프가 발생한다.

---

## 9. 타임아웃 및 서킷 브레이커

### 9.1 노드별 타임아웃 정의

| 노드 | 타임아웃 (초) | 근거 |
|------|-------------|------|
| `user_input` | 5 | 단순 파싱, 빠른 응답 필수 |
| `commander_plan` | 15 | LLM 호출 1회 |
| `population_agent` | 30 | 외부 API (유동인구 데이터) 호출 |
| `competition_agent` | 30 | 카카오맵/네이버 API 호출 |
| `trend_agent` | 30 | 소셜미디어/뉴스 API 호출 |
| `real_estate_agent` | 30 | 부동산 실거래가 API 호출 |
| `regulatory_agent` | 30 | 토지이용계획 API 호출 |
| `revenue_agent` | 30 | LLM 추론 + 데이터 조합 |
| `location_agent` | 30 | 지도 API + LLM 추론 |
| `financial_agent` | 45 | 복잡한 재무 모델링 |
| `risk_agent` | 45 | 전체 결과 종합 분석 |
| `debate_system` | 120 | 3라운드 x (Advocate + Critic) + Judge |
| `visualization_agent` | 30 | 차트/지도 렌더링 |
| `narrative_agent` | 30 | 장문 보고서 생성 |
| `final_output` | 10 | 단순 조합 |

### 9.2 재시도 전략

```python
# retry.py

from dataclasses import dataclass


@dataclass
class RetryPolicy:
    """노드별 재시도 정책."""
    max_retries: int = 2
    base_delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 10.0
    retryable_exceptions: tuple = (
        TimeoutError,
        ConnectionError,
        # 외부 API 관련 예외
    )

    def get_delay(self, attempt: int) -> float:
        """지수 백오프 지연 시간을 계산한다."""
        delay = self.base_delay_seconds * (self.backoff_multiplier ** attempt)
        return min(delay, self.max_delay_seconds)
```

재시도 흐름:

```
attempt 0 ──실패──▶ wait 1s ──▶ attempt 1 ──실패──▶ wait 2s ──▶ attempt 2 ──실패──▶ FAILED
                                                                                      │
                                                                                      ▼
                                                                            에러 기록, 폴백 실행
```

### 9.3 서킷 브레이커

서킷 브레이커는 외부 API 호출이 반복적으로 실패할 때 빠르게 실패를 반환하여 시스템 전체의 응답성을 보호한다.

```python
# circuit_breaker.py

import asyncio
import time
from enum import Enum
from typing import Any, Callable


class CircuitState(Enum):
    CLOSED = "closed"       # 정상 동작
    OPEN = "open"           # 차단 상태 (빠른 실패)
    HALF_OPEN = "half_open" # 복구 테스트 중


class CircuitBreaker:
    """
    에이전트 노드용 서킷 브레이커.

    동작 방식:
    - CLOSED: 정상 실행. 실패 누적 시 OPEN으로 전환.
    - OPEN: 즉시 CircuitOpenError 발생. 쿨다운 후 HALF_OPEN.
    - HALF_OPEN: 1회 테스트 실행. 성공 시 CLOSED, 실패 시 OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._last_failure_time:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """서킷 브레이커를 통해 함수를 실행한다."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"서킷 브레이커 '{self.name}' 개방 상태. "
                f"{self.recovery_timeout}초 후 재시도."
            )

        if current_state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                raise CircuitOpenError(
                    f"서킷 브레이커 '{self.name}' 반개방 테스트 중."
                )
            self._half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """성공 시 호출. 실패 카운터 리셋."""
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def _on_failure(self):
        """실패 시 호출. 실패 카운터 증가, 임계값 도달 시 OPEN."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN


class CircuitOpenError(Exception):
    """서킷 브레이커 개방 상태 예외."""
    pass


# ── 전역 서킷 브레이커 인스턴스 (외부 API별) ──

circuit_breakers: dict[str, CircuitBreaker] = {
    "population_api": CircuitBreaker("population_api", failure_threshold=3, recovery_timeout=60),
    "real_estate_api": CircuitBreaker("real_estate_api", failure_threshold=3, recovery_timeout=60),
    "competition_api": CircuitBreaker("competition_api", failure_threshold=3, recovery_timeout=60),
    "regulatory_api": CircuitBreaker("regulatory_api", failure_threshold=3, recovery_timeout=60),
    "llm_api": CircuitBreaker("llm_api", failure_threshold=5, recovery_timeout=30),
}
```

### 9.4 에이전트 실패 시 시스템 동작

| 실패 에이전트 | 영향 범위 | 폴백 동작 |
|--------------|----------|----------|
| `population` | `revenue`, `location`, `risk` | 통계청 평균 유동인구 데이터 사용. 매출 분석은 업종 평균 기반 추정으로 전환. |
| `competition` | `location`, `financial`, `risk` | 카카오맵 기본 검색 결과 기반 경쟁업체 수 추정. |
| `trend` | `risk` | 트렌드 분석 생략. 리스크 분석에서 트렌드 항목 제외. |
| `real_estate` | `financial`, `risk` | 국토부 공시지가 기반 임대료 추정. |
| `regulatory` | `risk` | 기본 용도지역 규제만 적용. 특수 규제 확인 불가 경고 표시. |
| `revenue` | `financial`, `risk` | 업종 평균 매출 데이터 사용. 재무 분석 정확도 경고 표시. |
| `location` | `risk` | 입지 분석 생략. 리스크에서 입지 항목 제외. |
| `financial` | `risk` | 간이 손익 계산으로 대체. 상세 재무 지표 미제공 경고. |
| `risk` | 보고서 품질 | 리스크 섹션 "분석 불가" 표시. 다른 에이전트 결과만으로 보고서 생성. |

### 9.5 Critical Failure 처리

아래 조건 중 하나라도 해당하면 `has_critical_failure = True`로 설정하고, 즉시 보고서 생성 Phase로 이동하여 부분 결과만으로 보고서를 작성한다.

1. Commander Agent 실패 (실행 계획 수립 불가)
2. Phase 1에서 3개 이상 에이전트 실패
3. `population` + `competition` 동시 실패 (핵심 데이터 부재)

```python
# nodes.py (추가)

async def check_critical_failure(state: MarketScopeState) -> dict:
    """Phase 전환 시 critical failure 여부를 확인한다."""
    failed_agents = [
        e["node_id"] for e in state.get("node_executions", [])
        if e["status"] == NodeStatus.FAILED
    ]

    is_critical = False
    reason = None

    # 조건 1: Commander 실패
    if "commander_plan" in failed_agents:
        is_critical = True
        reason = "Commander 에이전트 실패: 실행 계획 수립 불가"

    # 조건 2: Phase 1에서 3개 이상 실패
    phase1_agents = {"population_agent", "competition_agent", "trend_agent",
                     "real_estate_agent", "regulatory_agent"}
    phase1_failures = phase1_agents & set(failed_agents)
    if len(phase1_failures) >= 3:
        is_critical = True
        reason = f"Phase 1에서 {len(phase1_failures)}개 에이전트 실패"

    # 조건 3: population + competition 동시 실패
    if "population_agent" in failed_agents and "competition_agent" in failed_agents:
        is_critical = True
        reason = "유동인구 + 경쟁 분석 동시 실패: 핵심 데이터 부재"

    if is_critical:
        return {
            "has_critical_failure": True,
            "errors": [{"node_id": "critical_check", "error": reason, "timestamp": _now_iso()}],
        }

    return {}
```

---

## 10. 코드 구조

### 10.1 디렉토리 구조

```
marketscope/
├── orchestration/
│   ├── __init__.py
│   ├── graph.py              # LangGraph 그래프 빌드 (메인)
│   ├── state.py              # State TypedDict 정의
│   ├── nodes.py              # 노드 구현 (에이전트 래퍼)
│   ├── edges.py              # 조건부 엣지 로직
│   ├── checkpointer.py       # PostgreSQL 체크포인터
│   ├── streaming.py          # SSE 스트리밍 브릿지
│   ├── circuit_breaker.py    # 서킷 브레이커
│   └── retry.py              # 재시도 정책
├── agents/
│   ├── __init__.py
│   ├── base.py               # 에이전트 베이스 클래스
│   ├── commander.py          # Commander 에이전트
│   ├── population.py         # 유동인구 에이전트
│   ├── revenue.py            # 매출 에이전트
│   ├── competition.py        # 경쟁 에이전트
│   ├── location.py           # 입지 에이전트
│   ├── trend.py              # 트렌드 에이전트
│   ├── financial.py          # 재무 에이전트
│   ├── risk.py               # 리스크 에이전트
│   ├── real_estate.py        # 부동산 에이전트
│   ├── regulatory.py         # 규제 에이전트
│   ├── debate/
│   │   ├── __init__.py
│   │   ├── advocate.py       # 옹호자 에이전트
│   │   ├── critic.py         # 비평가 에이전트
│   │   └── judge.py          # 심판 에이전트
│   └── report/
│       ├── __init__.py
│       ├── visualization.py  # 시각화 에이전트
│       └── narrative.py      # 내러티브 에이전트
├── api/
│   ├── __init__.py
│   ├── main.py               # FastAPI 앱
│   └── routes/
│       ├── __init__.py
│       └── analysis.py       # 분석 API 라우트
└── config/
    ├── __init__.py
    └── settings.py           # 전역 설정
```

### 10.2 graph.py - 전체 그래프 빌드 코드

```python
# orchestration/graph.py

"""
MarketScope AI LangGraph 오케스트레이션 그래프.

이 모듈은 전체 분석 워크플로우의 DAG를 정의하고 컴파일한다.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from .state import MarketScopeState
from .nodes import (
    user_input_node,
    commander_plan_node,
    population_agent_node,
    competition_agent_node,
    trend_agent_node,
    real_estate_agent_node,
    regulatory_agent_node,
    phase1_sync_node,
    revenue_agent_node,
    location_agent_node,
    phase2_sync_node,
    financial_agent_node,
    risk_agent_node,
    debate_check_node,
    debate_system_node,
    report_fan_out_node,
    visualization_agent_node,
    narrative_agent_node,
    final_output_node,
)
from .edges import route_after_debate_check
from .checkpointer import create_checkpointer


async def build_graph() -> CompiledStateGraph:
    """
    MarketScope AI 분석 그래프를 빌드하고 컴파일한다.

    Returns:
        컴파일된 StateGraph (체크포인터 포함)
    """
    builder = StateGraph(MarketScopeState)

    # ──────────────────────────────────────────────
    # 1. 노드 등록
    # ──────────────────────────────────────────────

    # Entry 노드
    builder.add_node("user_input", user_input_node)
    builder.add_node("commander_plan", commander_plan_node)

    # Phase 1: 독립 에이전트 (병렬)
    builder.add_node("population_agent", population_agent_node)
    builder.add_node("competition_agent", competition_agent_node)
    builder.add_node("trend_agent", trend_agent_node)
    builder.add_node("real_estate_agent", real_estate_agent_node)
    builder.add_node("regulatory_agent", regulatory_agent_node)
    builder.add_node("phase1_sync", phase1_sync_node)

    # Phase 2: 의존 에이전트 (병렬)
    builder.add_node("revenue_agent", revenue_agent_node)
    builder.add_node("location_agent", location_agent_node)
    builder.add_node("phase2_sync", phase2_sync_node)

    # Phase 3: 재무 분석
    builder.add_node("financial_agent", financial_agent_node)

    # Phase 4: 리스크 분석
    builder.add_node("risk_agent", risk_agent_node)

    # Phase 5: 디베이트
    builder.add_node("debate_check", debate_check_node)
    builder.add_node("debate_system", debate_system_node)

    # Phase 6: 보고서
    builder.add_node("report_fan_out", report_fan_out_node)
    builder.add_node("visualization_agent", visualization_agent_node)
    builder.add_node("narrative_agent", narrative_agent_node)

    # Exit
    builder.add_node("final_output", final_output_node)

    # ──────────────────────────────────────────────
    # 2. 엣지 연결
    # ──────────────────────────────────────────────

    # Entry 시퀀스
    builder.add_edge(START, "user_input")
    builder.add_edge("user_input", "commander_plan")

    # Phase 1 fan-out: commander_plan → 5개 에이전트 (병렬)
    builder.add_edge("commander_plan", "population_agent")
    builder.add_edge("commander_plan", "competition_agent")
    builder.add_edge("commander_plan", "trend_agent")
    builder.add_edge("commander_plan", "real_estate_agent")
    builder.add_edge("commander_plan", "regulatory_agent")

    # Phase 1 fan-in: 5개 에이전트 → phase1_sync
    builder.add_edge("population_agent", "phase1_sync")
    builder.add_edge("competition_agent", "phase1_sync")
    builder.add_edge("trend_agent", "phase1_sync")
    builder.add_edge("real_estate_agent", "phase1_sync")
    builder.add_edge("regulatory_agent", "phase1_sync")

    # Phase 2 fan-out: phase1_sync → revenue + location (병렬)
    builder.add_edge("phase1_sync", "revenue_agent")
    builder.add_edge("phase1_sync", "location_agent")

    # Phase 2 fan-in: revenue + location → phase2_sync
    builder.add_edge("revenue_agent", "phase2_sync")
    builder.add_edge("location_agent", "phase2_sync")

    # Phase 3: phase2_sync → financial
    builder.add_edge("phase2_sync", "financial_agent")

    # Phase 4: financial → risk
    builder.add_edge("financial_agent", "risk_agent")

    # Phase 5: risk → debate_check → 조건부 라우팅
    builder.add_edge("risk_agent", "debate_check")
    builder.add_conditional_edges(
        "debate_check",
        route_after_debate_check,
        {
            "debate_system": "debate_system",
            "report_fan_out": "report_fan_out",
        },
    )

    # debate → report_fan_out
    builder.add_edge("debate_system", "report_fan_out")

    # Phase 6 fan-out: report_fan_out → visualization + narrative (병렬)
    builder.add_edge("report_fan_out", "visualization_agent")
    builder.add_edge("report_fan_out", "narrative_agent")

    # Phase 6 fan-in: visualization + narrative → final_output
    builder.add_edge("visualization_agent", "final_output")
    builder.add_edge("narrative_agent", "final_output")

    # Exit
    builder.add_edge("final_output", END)

    # ──────────────────────────────────────────────
    # 3. 컴파일
    # ──────────────────────────────────────────────

    checkpointer = await create_checkpointer()

    graph = builder.compile(checkpointer=checkpointer)

    return graph
```

### 10.3 edges.py - 조건부 엣지 모듈

```python
# orchestration/edges.py

"""
조건부 엣지 로직 모듈.

debate_check 노드 이후의 라우팅 등 조건부 분기 로직을 정의한다.
"""

from .state import MarketScopeState, DebateDecision


def route_after_debate_check(state: MarketScopeState) -> str:
    """
    디베이트 수행 여부에 따라 다음 노드를 결정한다.

    Returns:
        "debate_system": 디베이트 트리거 조건 충족 시
        "report_fan_out": 디베이트 불필요 시
    """
    decision = state.get("debate_decision")

    if decision == DebateDecision.TRIGGER:
        return "debate_system"

    return "report_fan_out"
```

### 10.4 그래프 실행 진입점

```python
# orchestration/__init__.py

"""
MarketScope AI 오케스트레이션 패키지.

사용법:
    from orchestration import run_analysis, run_analysis_stream

    # 동기식 (전체 결과 반환)
    result = await run_analysis("강남역 카페 분석")

    # 스트리밍 (SSE 이벤트)
    async for event in run_analysis_stream("강남역 카페 분석"):
        print(event)
"""

import uuid
from datetime import datetime, timezone

from .graph import build_graph
from .state import MarketScopeState, create_initial_state
from .streaming import stream_graph_events, SSEEvent


async def run_analysis(user_input: str) -> MarketScopeState:
    """
    상권 분석을 실행하고 최종 State를 반환한다.

    Args:
        user_input: 사용자 입력 텍스트

    Returns:
        분석 완료된 MarketScopeState
    """
    session_id = str(uuid.uuid4())
    thread_id = f"session_{session_id}"
    initial_state = create_initial_state(session_id, user_input)

    graph = await build_graph()
    config = {"configurable": {"thread_id": thread_id}}

    final_state = await graph.ainvoke(initial_state, config=config)

    return final_state


async def run_analysis_stream(user_input: str):
    """
    상권 분석을 실행하면서 SSE 이벤트를 스트리밍한다.

    Args:
        user_input: 사용자 입력 텍스트

    Yields:
        SSEEvent 객체
    """
    session_id = str(uuid.uuid4())
    thread_id = f"session_{session_id}"
    initial_state = create_initial_state(session_id, user_input)

    graph = await build_graph()

    async for event in stream_graph_events(graph, initial_state, thread_id):
        yield event
```

---

## 11. 사용자 시나리오

### 11.1 시나리오 A: 기본 분석 - "강남역 카페 분석"

#### 입력

```
사용자: "강남역 카페 분석"
```

#### Commander 계획

```python
CommanderPlan(
    analysis_mode=AnalysisMode.BASIC,
    target_location="강남역",
    target_location_secondary=None,
    target_industry="카페",
    agents_to_run=["population", "competition", "trend", "real_estate",
                   "regulatory", "revenue", "location", "financial", "risk"],
    agents_to_skip=[],
    force_debate=False,
    priority_focus=["population", "competition", "revenue"],
    user_constraints={},
    estimated_duration_seconds=180,
)
```

#### 실행 흐름

```
[00:00] user_input ── 입력 파싱 완료 (2%)
[00:02] commander_plan ── 실행 계획 수립 (5%)
        → analysis_mode: BASIC
        → 전체 9개 에이전트 실행 결정

[00:02] Phase 1 병렬 시작
        ├─ population_agent ── 강남역 유동인구 분석 중...
        ├─ competition_agent ── 강남역 카페 경쟁 분석 중...
        ├─ trend_agent ── 카페 업종 트렌드 분석 중...
        ├─ real_estate_agent ── 강남역 임대 시세 분석 중...
        └─ regulatory_agent ── 강남역 영업 규제 확인 중...

[00:15] population_agent 완료 (13%)
        → 일 평균 유동인구: 182,000명
        → 피크 시간: 12:00~14:00, 18:00~20:00
        → confidence: 0.85

[00:18] competition_agent 완료 (21%)
        → 반경 300m 내 카페: 47개
        → 시장 포화도: 0.78
        → confidence: 0.82

[00:20] trend_agent 완료 (29%)
        → 스페셜티 커피 성장률: +12%
        → confidence: 0.75

[00:22] real_estate_agent 완료 (37%)
        → 평균 월 임대료: 350만원/10평 기준
        → 권리금: 8,000만원
        → confidence: 0.88

[00:24] regulatory_agent 완료 (45%)
        → 일반상업지역, 카페 영업 가능
        → 별도 인허가 불필요
        → confidence: 0.95

[00:24] phase1_sync ── Phase 1 완료

[00:24] Phase 2 병렬 시작
        ├─ revenue_agent ── 매출 추정 중 (유동인구 데이터 활용)...
        └─ location_agent ── 입지 분석 중...

[00:35] revenue_agent 완료 (53%)
        → 월 매출 추정: 3,200만원 (범위: 2,400~4,000만원)
        → 매출 분산율: 25%
        → confidence: 0.72

[00:38] location_agent 완료 (61%)
        → 접근성: 0.92 (지하철 출구 50m)
        → 가시성: 0.85
        → 입지 등급: A
        → confidence: 0.88

[00:38] phase2_sync ── Phase 2 완료

[00:38] Phase 3 시작
        └─ financial_agent ── 재무 분석 중...

[00:52] financial_agent 완료 (71%)
        → 초기 투자: 1.2억원
        → 손익분기: 14개월
        → 1년 ROI: -8%, 3년 ROI: 42%
        → confidence: 0.68

[00:52] Phase 4 시작
        └─ risk_agent ── 리스크 종합 분석 중...

[01:08] risk_agent 완료 (81%)
        → 종합 리스크: 0.45 (중간)
        → 주요 리스크: 경쟁 과밀(0.78), 높은 초기 투자
        → confidence: 0.70

[01:08] debate_check ── 디베이트 조건 평가 (83%)
        ├─ 신뢰도 검사: financial(0.68) > 0.6 ✓, risk(0.70) > 0.6 ✓
        ├─ 매출 분산율: 25% < 50% ✓
        ├─ 결론 충돌: 없음 ✓
        └─ 사용자 강제: 아님 ✓
        → 결정: SKIP (디베이트 불필요)

[01:08] Phase 6 병렬 시작
        ├─ visualization_agent ── 차트/지도 생성 중...
        └─ narrative_agent ── 보고서 작성 중...

[01:25] visualization_agent 완료 (93%)
[01:28] narrative_agent 완료 (98%)

[01:28] final_output ── 최종 보고서 조합 (100%)
```

#### 최종 출력 요약

```
═══════════════════════════════════════════
  강남역 카페 상권 분석 보고서
═══════════════════════════════════════════

📍 위치: 강남역 일대
🏪 업종: 카페

▸ 핵심 요약
  - 일 평균 유동인구 18.2만명의 초대형 상권
  - 반경 300m 내 카페 47개로 높은 경쟁 밀도
  - 월 매출 약 3,200만원 예상 (업종 평균 대비 +15%)
  - 초기 투자 1.2억, 손익분기 14개월
  - 종합 리스크 등급: 중간 (0.45/1.0)

▸ 추천 사항
  1. 스페셜티 커피로 차별화 (성장률 +12%)
  2. 점심/저녁 피크 타임 집중 운영
  3. 권리금 협상 여지 확인 권장

  분석 소요 시간: 1분 28초
  에이전트 실행: 9/9 완료
  디베이트: 미실시
═══════════════════════════════════════════
```

---

### 11.2 시나리오 B: 비교 분석 - "합정동 vs 연남동 카페 비교"

#### 입력

```
사용자: "합정동 vs 연남동 카페 비교"
```

#### Commander 계획

```python
CommanderPlan(
    analysis_mode=AnalysisMode.COMPARISON,
    target_location="합정동",
    target_location_secondary="연남동",
    target_industry="카페",
    agents_to_run=["population", "competition", "trend", "real_estate",
                   "regulatory", "revenue", "location", "financial", "risk"],
    agents_to_skip=[],
    force_debate=False,
    priority_focus=["population", "competition", "real_estate"],
    user_constraints={},
    estimated_duration_seconds=300,   # 2배 분석이므로 예상 시간 증가
)
```

#### 실행 흐름 (비교 모드)

비교 분석은 **동일한 DAG를 2회** 실행하는 것이 아니라, **각 Phase에서 두 위치를 병렬로 분석**하는 확장 모드로 동작한다. Commander가 comparison 모드를 지정하면, Phase 1~4의 각 에이전트 노드가 내부적으로 두 위치에 대한 분석을 수행한다.

```
[00:00] user_input ── "합정동 vs 연남동 카페 비교" 파싱

[00:02] commander_plan
        → analysis_mode: COMPARISON
        → target_location: "합정동"
        → target_location_secondary: "연남동"

[00:02] Phase 1 병렬 시작 (각 에이전트가 내부적으로 2개 위치 분석)
        ├─ population_agent
        │   ├─ 합정동 유동인구 분석
        │   └─ 연남동 유동인구 분석
        ├─ competition_agent
        │   ├─ 합정동 카페 경쟁 분석
        │   └─ 연남동 카페 경쟁 분석
        ├─ trend_agent (공통: 지역 차이 미미)
        ├─ real_estate_agent
        │   ├─ 합정동 임대 시세
        │   └─ 연남동 임대 시세
        └─ regulatory_agent (공통)

[00:30] Phase 1 완료
        → population: 합정동 45,000명/일 vs 연남동 32,000명/일
        → competition: 합정동 카페 28개 vs 연남동 카페 35개
        → real_estate: 합정동 월 200만원 vs 연남동 월 180만원

[00:30] Phase 2 (비교 분석 포함)
        ├─ revenue_agent ── 양 지역 매출 비교 추정
        └─ location_agent ── 양 지역 입지 비교

[00:45] Phase 2 완료
        → revenue: 합정동 2,400만원 vs 연남동 1,800만원
        → location: 합정동 A등급 vs 연남동 B+등급

[00:45] Phase 3: financial_agent ── 양 지역 재무 비교
[01:05] Phase 4: risk_agent ── 양 지역 리스크 비교

[01:20] debate_check
        → 연남동 카페 경쟁 밀도(35개) 대비 유동인구(32,000) 불균형 감지
        → competition confidence: 0.58 (< 0.6) ← 디베이트 트리거!
        → 결정: TRIGGER

[01:20] debate_system 시작
        ├─ Round 1:
        │   ├─ Advocate: "연남동은 SNS 핫플레이스로 유동인구 성장세. 차별화된
        │   │            카페는 충분한 수요 확보 가능."
        │   └─ Critic: "35개 카페 중 폐업 주기가 짧아 지속성 의문.
        │              실제 체류 소비자 비율은 낮을 수 있음."
        ├─ Round 2:
        │   ├─ Advocate: "연남동의 MZ세대 유입률이 높아 프리미엄 카페 수요 존재."
        │   └─ Critic: "프리미엄 세그먼트도 이미 포화. 객단가 상승의 한계."
        ├─ Round 3: (최종)
        │   ├─ Advocate: 합정동이 안정적이나 연남동도 니치 전략 시 가능성 있음
        │   └─ Critic: 합정동의 유동인구 대비 경쟁 밀도가 더 유리
        └─ Judge: "합정동이 종합적으로 유리. 연남동은 차별화 전략 필수."
                  → judge_score: 0.82

[02:40] Phase 6 (보고서 생성 - 비교 형식)

[03:10] final_output ── 비교 보고서 완성
```

#### 최종 출력 요약 (비교 형식)

```
═══════════════════════════════════════════════════════
  합정동 vs 연남동 카페 상권 비교 분석
═══════════════════════════════════════════════════════

                    합정동          연남동
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
일 유동인구         45,000명        32,000명
카페 수 (300m)     28개            35개
포화도 지수        0.62            0.82
월 임대료 (10평)   200만원         180만원
권리금             5,000만원       4,000만원
월 매출 예상       2,400만원       1,800만원
손익분기           11개월          16개월
1년 ROI           12%             -5%
리스크 점수        0.38            0.55
입지 등급          A               B+
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ 디베이트 결과 (자동 트리거됨)
  사유: 연남동 경쟁 분석 신뢰도 부족(0.58)
  판결: "합정동이 종합적으로 우위.
         연남동은 스페셜티/디저트 특화 시 경쟁력 확보 가능."

▸ 종합 추천: 합정동 ★★★★☆ vs 연남동 ★★★☆☆

  분석 소요 시간: 3분 10초
  디베이트: 실시 (3라운드)
═══════════════════════════════════════════════════════
```

---

### 11.3 시나리오 C: 빠른 조회 - "홍대 유동인구만 알려줘"

#### 입력

```
사용자: "홍대 유동인구만 알려줘"
```

#### Commander 계획

```python
CommanderPlan(
    analysis_mode=AnalysisMode.QUICK,
    target_location="홍대",
    target_location_secondary=None,
    target_industry="",             # 업종 미지정
    agents_to_run=["population"],   # population만 실행
    agents_to_skip=["competition", "trend", "real_estate", "regulatory",
                    "revenue", "location", "financial", "risk"],
    force_debate=False,
    priority_focus=["population"],
    user_constraints={},
    estimated_duration_seconds=30,
)
```

#### 실행 흐름 (Quick 모드)

Quick 모드에서는 Commander가 필요한 에이전트만 선택적으로 실행하고, 나머지는 모두 skip한다. DAG 구조 자체는 동일하지만 대부분의 노드가 즉시 SKIPPED를 반환한다.

```
[00:00] user_input ── 파싱 (2%)
[00:01] commander_plan ── Quick 모드 결정 (5%)
        → agents_to_run: ["population"]
        → 나머지 8개 에이전트 skip

[00:01] Phase 1 병렬 시작
        ├─ population_agent ── 홍대 유동인구 분석 중...
        ├─ competition_agent ── SKIPPED (즉시 완료)
        ├─ trend_agent ── SKIPPED (즉시 완료)
        ├─ real_estate_agent ── SKIPPED (즉시 완료)
        └─ regulatory_agent ── SKIPPED (즉시 완료)

[00:12] population_agent 완료
        → 일 평균: 98,000명
        → 피크: 금/토 18:00~22:00
        → 20대 비율: 42%
        → confidence: 0.87

[00:12] phase1_sync

[00:12] Phase 2 (모두 skip)
        ├─ revenue_agent ── SKIPPED
        └─ location_agent ── SKIPPED

[00:12] phase2_sync → financial_agent(SKIPPED) → risk_agent(SKIPPED)

[00:12] debate_check
        → Quick 모드: 디베이트 자동 SKIP
        → 결정: SKIP

[00:12] Phase 6 (간소화 보고서)
        ├─ visualization_agent ── 유동인구 차트만 생성
        └─ narrative_agent ── 간략 요약만 작성

[00:20] final_output 완료 (100%)
```

#### 최종 출력 요약 (Quick 형식)

```
═══════════════════════════════════════
  홍대 유동인구 분석 (Quick)
═══════════════════════════════════════

📍 위치: 홍대입구역 일대

▸ 일 평균 유동인구: 98,000명

▸ 시간대별 분포:
  06시~09시: ██░░░░░░░░  8,200명
  09시~12시: ████░░░░░░  15,400명
  12시~15시: ██████░░░░  22,100명
  15시~18시: ████████░░  28,500명
  18시~21시: ██████████  35,800명  ← 피크
  21시~24시: ███████░░░  25,300명

▸ 요일별 패턴:
  평일 평균: 82,000명
  주말 평균: 128,000명 (평일 대비 +56%)
  최대: 토요일 (142,000명)

▸ 연령대:
  10대: 8% │ 20대: 42% │ 30대: 25%
  40대: 15% │ 50대+: 10%

▸ 추세: 전년 대비 +3.2% 증가 (안정 성장)

  데이터 신뢰도: 87%
  분석 소요 시간: 20초
═══════════════════════════════════════
```

#### Quick 모드 전체 소요 시간 비교

| 시나리오 | 실행 에이전트 | 소요 시간 |
|---------|-------------|----------|
| Basic (강남역 카페) | 9개 | ~90초 |
| Comparison (합정 vs 연남) | 9개 x2 + 디베이트 | ~190초 |
| Quick (홍대 유동인구) | 1개 | ~20초 |

---

## 12. 부록

### 12.1 환경 변수

```bash
# .env

# PostgreSQL (체크포인팅)
DATABASE_URL=postgresql+asyncpg://marketscope:password@localhost:5432/marketscope

# LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.1

# 외부 API
KAKAO_REST_API_KEY=...          # 카카오맵 API
NAVER_CLIENT_ID=...             # 네이버 검색 API
NAVER_CLIENT_SECRET=...
DATA_GO_KR_API_KEY=...          # 공공데이터포털 API
NICE_BIZ_API_KEY=...            # NICE 상권분석 API

# Redis (캐싱 및 스트리밍)
REDIS_URL=redis://localhost:6379/0

# 서킷 브레이커
CB_FAILURE_THRESHOLD=3
CB_RECOVERY_TIMEOUT=60

# 타임아웃 (기본값, 노드별 오버라이드 가능)
DEFAULT_NODE_TIMEOUT=30
DEBATE_TIMEOUT=120
```

### 12.2 의존성 패키지

```
# requirements.txt

langgraph>=0.2.0
langgraph-checkpoint-postgres>=2.0.0
langchain-core>=0.3.0
langchain-openai>=0.2.0
asyncpg>=0.30.0
fastapi>=0.115.0
uvicorn>=0.32.0
redis>=5.0.0
sse-starlette>=2.0.0
pydantic>=2.0.0
httpx>=0.27.0
```

### 12.3 그래프 시각화 (Mermaid)

```mermaid
graph TD
    START([START]) --> user_input
    user_input --> commander_plan

    commander_plan --> population_agent
    commander_plan --> competition_agent
    commander_plan --> trend_agent
    commander_plan --> real_estate_agent
    commander_plan --> regulatory_agent

    population_agent --> phase1_sync
    competition_agent --> phase1_sync
    trend_agent --> phase1_sync
    real_estate_agent --> phase1_sync
    regulatory_agent --> phase1_sync

    phase1_sync --> revenue_agent
    phase1_sync --> location_agent

    revenue_agent --> phase2_sync
    location_agent --> phase2_sync

    phase2_sync --> financial_agent
    financial_agent --> risk_agent
    risk_agent --> debate_check

    debate_check -->|trigger| debate_system
    debate_check -->|skip| report_fan_out
    debate_system --> report_fan_out

    report_fan_out --> visualization_agent
    report_fan_out --> narrative_agent

    visualization_agent --> final_output
    narrative_agent --> final_output

    final_output --> END([END])

    style population_agent fill:#4CAF50,color:#fff
    style competition_agent fill:#4CAF50,color:#fff
    style trend_agent fill:#4CAF50,color:#fff
    style real_estate_agent fill:#4CAF50,color:#fff
    style regulatory_agent fill:#4CAF50,color:#fff
    style revenue_agent fill:#2196F3,color:#fff
    style location_agent fill:#2196F3,color:#fff
    style financial_agent fill:#FF9800,color:#fff
    style risk_agent fill:#f44336,color:#fff
    style debate_system fill:#9C27B0,color:#fff
    style debate_check fill:#9C27B0,color:#fff
    style visualization_agent fill:#00BCD4,color:#fff
    style narrative_agent fill:#00BCD4,color:#fff
```

### 12.4 성능 벤치마크 목표

| 지표 | 목표 | 비고 |
|------|------|------|
| Quick 모드 응답 시간 | < 30초 | 단일 에이전트 |
| Basic 모드 응답 시간 | < 120초 | 9개 에이전트 전체 |
| Comparison 모드 응답 시간 | < 240초 | 9개 에이전트 x 2 + 디베이트 |
| 체크포인트 저장 지연 | < 100ms | PostgreSQL write |
| SSE 이벤트 지연 | < 200ms | 노드 완료 → 클라이언트 수신 |
| 동시 세션 지원 | 50+  | 수평 확장 가능 |
| 체크포인트 기반 재개 | < 10초 | 마지막 완료 노드부터 |

---

*문서 끝*
