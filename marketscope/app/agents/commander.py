"""Commander Agent - 사용자 쿼리 분석, 실행 계획 수립, 최종 판단."""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.constants import ANALYSIS_MODE_AGENTS, AnalysisMode
from app.models.state import CommanderPlan, FinalJudgment


# ── Structured Output 용 Pydantic 모델 ──

class CommanderPlanOutput(BaseModel):
    """Commander의 1차 호출 출력 - 실행 계획."""
    analysis_mode: str = Field(
        ..., description="분석 모드: 'basic' | 'quick' | 'comparison'"
    )
    target_location: str = Field(
        ..., description="분석 대상 위치 (예: '강남역', '홍대입구')"
    )
    target_location_secondary: Optional[str] = Field(
        None, description="비교 분석 시 두 번째 위치"
    )
    target_industry: str = Field(
        ..., description="분석 대상 업종 (예: '카페', '삼겹살')"
    )
    priority_focus: list[str] = Field(
        default_factory=list,
        description="우선 분석 분야 (예: ['유동인구', '경쟁강도'])"
    )
    user_constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="사용자 제약 조건 (예: {'budget': 50000000})"
    )
    estimated_duration_seconds: int = Field(
        180, description="예상 소요 시간 (초)"
    )
    clarification_needed: bool = Field(
        False, description="명확화 요청 필요 여부"
    )
    clarification_message: Optional[str] = Field(
        None, description="명확화 요청 메시지"
    )


class FinalJudgmentOutput(BaseModel):
    """Commander의 2차 호출 출력 - 최종 판단."""
    overall_score: float = Field(..., ge=0.0, le=100.0, description="종합 점수")
    overall_grade: str = Field(..., description="종합 등급 (S/A/B/C/D/F)")
    recommendation: str = Field(
        ..., description="최종 추천 ('강력추천'|'추천'|'조건부추천'|'보류'|'비추천')"
    )
    executive_summary: str = Field(..., description="3~5문장 요약")
    key_findings: list[str] = Field(default_factory=list, description="핵심 발견 5~7개")
    critical_actions: list[str] = Field(default_factory=list, description="필수 조치 3~5개")
    score_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="항목별 점수 {'population': 75.0, 'revenue': 60.0, ...}"
    )


class CommanderAgent(BaseAgent[CommanderPlanOutput]):
    """Commander Agent - 분석 파이프라인의 중앙 두뇌."""

    agent_name = "commander"
    agent_description = "사용자 쿼리 분석, 분석 계획 수립, 최종 종합 판단"
    output_model = CommanderPlanOutput
    llm_role = "analysis"
    max_retries = 2

    PLANNING_SYSTEM_PROMPT = """당신은 MarketScope AI의 Commander Agent입니다. 상권 분석 시스템의 중앙 두뇌 역할을 수행합니다.

## 역할
사용자의 자연어 쿼리를 분석하여 구조화된 분석 계획을 수립합니다.

## Phase 1 제한사항
- 서울 주요 상권만 지원: 강남, 홍대, 이태원, 건대, 신촌, 종로, 명동, 여의도, 성수, 잠실
- 활성 에이전트: population(유동인구), revenue(매출), competition(경쟁), location(입지) — 4개
- 분석 모드: basic(전체 4개), quick(population+competition만), comparison(두 상권 비교)

## 분석 모드 결정 기준
- "비교", "vs", "어디가 나은지" → comparison
- "빨리", "간단하게", "대략" → quick
- 그 외 일반 분석 → basic

## 위치 추출 규칙
- "강남역 근처 카페" → target_location: "강남역", target_industry: "카페"
- "홍대 vs 합정" → comparison 모드, target_location: "홍대", target_location_secondary: "합정"
- 위치가 명확하지 않으면 clarification_needed: true

## 업종 추출 규칙
- "카페", "커피" → "카페"
- "삼겹살", "고기집" → "삼겹살/고기"
- "음식점", "식당" → "음식점"
- 업종이 불분명하면 clarification_needed: true

## 출력
반드시 JSON 형식으로 CommanderPlanOutput 스키마에 맞춰 응답하세요."""

    JUDGMENT_SYSTEM_PROMPT = """당신은 MarketScope AI의 Commander Agent입니다. 모든 전문 에이전트의 분석 결과를 종합하여 최종 판단을 내립니다.

## 역할
각 에이전트의 분석 결과를 종합하여:
1. 종합 점수 (0~100)와 등급 (S/A/B/C/D/F) 산출
2. 최종 추천 의견 도출
3. 핵심 발견사항과 필수 조치사항 정리

## 점수 산출 기준
- 유동인구 (30%): 일평균 유동인구, 타겟 연령대 매칭도
- 매출 전망 (25%): 점포당 매출, 매출 추세
- 경쟁 환경 (25%): 포화 지수, 차별화 기회
- 입지 조건 (20%): 접근성, 가시성, 앵커 시설

## 등급 기준
- S (90~100): 최상급 상권, 강력 추천
- A (80~89): 우수 상권, 추천
- B (70~79): 양호, 조건부 추천
- C (60~69): 보통, 보류 권장
- D (50~59): 부족, 비추천
- F (0~49): 매우 부적합

반드시 JSON 형식으로 FinalJudgmentOutput 스키마에 맞춰 응답하세요."""

    def build_system_prompt(self, state: dict[str, Any]) -> str:
        return self.PLANNING_SYSTEM_PROMPT

    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        return f"사용자 쿼리: {state.get('user_input', '')}"

    async def execute(self, state: dict[str, Any]) -> CommanderPlanOutput:
        """1차 호출: 분석 계획 수립."""
        user_input = state.get("user_input", "")

        llm_result = await self.call_llm(
            system_prompt=self.PLANNING_SYSTEM_PROMPT,
            user_prompt=f"사용자 쿼리를 분석하여 실행 계획을 JSON으로 생성하세요.\n\n사용자 쿼리: {user_input}",
            response_format=CommanderPlanOutput,
        )

        if llm_result["parsed"]:
            return llm_result["parsed"]

        return self._parse_structured_output(
            llm_result["content"], CommanderPlanOutput
        )

    async def run_planning(self, state: dict[str, Any]) -> dict[str, Any]:
        """LangGraph 노드: 실행 계획 수립."""
        from datetime import datetime, timezone

        execution_start = datetime.now(timezone.utc).isoformat()

        try:
            plan_output = await self.execute(state)

            # AnalysisMode에 따른 에이전트 목록 결정
            mode = plan_output.analysis_mode
            try:
                analysis_mode = AnalysisMode(mode)
            except ValueError:
                analysis_mode = AnalysisMode.BASIC

            agents_to_run = ANALYSIS_MODE_AGENTS.get(
                analysis_mode,
                ANALYSIS_MODE_AGENTS[AnalysisMode.BASIC]
            )

            commander_plan: CommanderPlan = {
                "analysis_mode": plan_output.analysis_mode,
                "target_location": plan_output.target_location,
                "target_location_secondary": plan_output.target_location_secondary,
                "target_industry": plan_output.target_industry,
                "agents_to_run": agents_to_run,
                "agents_to_skip": [
                    a for a in ["population", "competition", "revenue", "location"]
                    if a not in agents_to_run
                ],
                "force_debate": False,
                "priority_focus": plan_output.priority_focus,
                "user_constraints": plan_output.user_constraints,
                "estimated_duration_seconds": plan_output.estimated_duration_seconds,
                "clarification_needed": plan_output.clarification_needed,
                "clarification_message": plan_output.clarification_message,
            }

            return {
                "commander_plan": commander_plan,
                "current_phase": 1,
                "progress_pct": 10.0,
                "node_executions": [
                    self.create_node_execution("completed", execution_start)
                ],
            }

        except Exception as e:
            self.logger.error(f"Commander planning 실패: {e}")
            # 폴백: 기본 계획
            fallback_plan: CommanderPlan = {
                "analysis_mode": "basic",
                "target_location": state.get("user_input", "강남역")[:20],
                "target_location_secondary": None,
                "target_industry": "일반",
                "agents_to_run": ["population", "competition", "revenue", "location"],
                "agents_to_skip": [],
                "force_debate": False,
                "priority_focus": [],
                "user_constraints": {},
                "estimated_duration_seconds": 180,
                "clarification_needed": False,
                "clarification_message": None,
            }
            return {
                "commander_plan": fallback_plan,
                "current_phase": 1,
                "progress_pct": 10.0,
                "node_executions": [
                    self.create_node_execution("completed", execution_start, error_message=str(e))
                ],
                "errors": [{"agent": "commander", "error": str(e)}],
            }

    async def run_judgment(self, state: dict[str, Any]) -> dict[str, Any]:
        """LangGraph 노드: 최종 종합 판단."""
        from datetime import datetime, timezone

        execution_start = datetime.now(timezone.utc).isoformat()

        # 에이전트 결과 수집
        results_summary = []

        pop = state.get("population_result")
        if pop:
            results_summary.append(f"유동인구: 일평균 {pop.get('total_floating_population', 'N/A')}명, 신뢰도 {pop.get('confidence_score', 'N/A')}")

        rev = state.get("revenue_result")
        if rev:
            results_summary.append(f"매출: 점포당 월 {rev.get('revenue_per_store', 'N/A')}원, 신뢰도 {rev.get('confidence_score', 'N/A')}")

        comp = state.get("competition_result")
        if comp:
            results_summary.append(f"경쟁: 직접경쟁 {comp.get('direct_competitors', 'N/A')}개, 포화지수 {comp.get('saturation_index', 'N/A')}")

        loc = state.get("location_result")
        if loc:
            results_summary.append(f"입지: 접근성 {loc.get('accessibility_score', 'N/A')}, 등급 {loc.get('location_grade', 'N/A')}")

        plan = state.get("commander_plan", {})
        user_prompt = f"""다음은 '{plan.get('target_location', '')}' 상권의 '{plan.get('target_industry', '')}' 업종 분석 결과입니다.

에이전트 분석 결과:
{chr(10).join(results_summary) if results_summary else "분석 결과 없음"}

사용자 원본 쿼리: {state.get('user_input', '')}

위 결과를 종합하여 최종 판단을 JSON으로 생성하세요."""

        try:
            llm_result = await self.call_llm(
                system_prompt=self.JUDGMENT_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_format=FinalJudgmentOutput,
            )

            judgment_output: FinalJudgmentOutput = (
                llm_result["parsed"]
                if llm_result["parsed"]
                else self._parse_structured_output(llm_result["content"], FinalJudgmentOutput)
            )

            final_judgment: FinalJudgment = {
                "overall_score": judgment_output.overall_score,
                "overall_grade": judgment_output.overall_grade,
                "recommendation": judgment_output.recommendation,
                "executive_summary": judgment_output.executive_summary,
                "key_findings": judgment_output.key_findings,
                "critical_actions": judgment_output.critical_actions,
                "score_breakdown": judgment_output.score_breakdown,
            }

            return {
                "final_judgment": final_judgment,
                "current_phase": 5,
                "progress_pct": 80.0,
                "node_executions": [
                    self.create_node_execution("completed", execution_start)
                ],
            }

        except Exception as e:
            self.logger.error(f"Commander judgment 실패: {e}")
            return {
                "final_judgment": {
                    "overall_score": 50.0,
                    "overall_grade": "C",
                    "recommendation": "보류",
                    "executive_summary": "분석 데이터가 불충분하여 정확한 판단이 어렵습니다.",
                    "key_findings": ["분석 중 오류 발생"],
                    "critical_actions": ["추가 데이터 수집 필요"],
                    "score_breakdown": {},
                },
                "current_phase": 5,
                "progress_pct": 80.0,
                "node_executions": [
                    self.create_node_execution("failed", execution_start, error_message=str(e))
                ],
                "errors": [{"agent": "commander_judgment", "error": str(e)}],
            }
