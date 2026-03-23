"""내러티브 리포트 생성 에이전트."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from marketscope_agent.agents.base import BaseAgent


class NarrativeReportOutput(BaseModel):
    """내러티브 에이전트 출력."""
    executive_summary: str = Field(..., description="경영진 요약 (3~5문장)")
    detailed_sections: list[dict[str, str]] = Field(
        default_factory=list,
        description="섹션별 상세 분석 [{'title': str, 'content': str}]"
    )
    recommendations: list[str] = Field(default_factory=list, description="권고사항 목록")
    risk_warnings: list[str] = Field(default_factory=list, description="위험 경고 목록")


class NarrativeAgent(BaseAgent[NarrativeReportOutput]):
    """내러티브 리포트 생성 에이전트."""

    agent_name = "narrative"
    agent_description = "구조화된 분석 결과를 사람이 읽기 좋은 리포트로 변환"
    output_model = NarrativeReportOutput
    llm_role = "narrative"
    max_retries = 2

    SYSTEM_PROMPT = """당신은 MarketScope AI의 리포트 작성 전문가입니다.

## 역할
전문 에이전트들의 분석 결과를 종합하여 사업자가 읽기 쉬운 상권 분석 리포트를 작성합니다.

## 작성 원칙
1. 전문 용어를 최소화하고, 비즈니스 임팩트 중심으로 서술
2. 핵심 수치는 반드시 포함 (유동인구, 예상매출, 경쟁점포수 등)
3. 기회와 위험을 균형있게 서술
4. 구체적이고 실행 가능한 권고사항 제시
5. 한국어로 작성, 존댓말 사용

## 리포트 구조
1. 경영진 요약 (3~5문장으로 핵심 결론)
2. 상세 분석 섹션:
   - 유동인구 분석
   - 매출 전망
   - 경쟁 환경
   - 입지 평가
3. 권고사항 (3~5개)
4. 위험 경고 (주의해야 할 사항)

반드시 JSON 형식으로 NarrativeReportOutput 스키마에 맞춰 응답하세요."""

    def build_system_prompt(self, state: dict[str, Any]) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        plan = state.get("commander_plan", {})
        judgment = state.get("final_judgment", {})

        sections = []
        sections.append(f"분석 대상: {plan.get('target_location', '')} / {plan.get('target_industry', '')}")
        sections.append(f"종합 점수: {judgment.get('overall_score', 'N/A')} ({judgment.get('overall_grade', '')})")
        sections.append(f"추천: {judgment.get('recommendation', '')}")

        # 에이전트 결과 요약
        for key in ["population_result", "revenue_result", "competition_result", "location_result"]:
            result = state.get(key)
            if result:
                insight = result.get("key_insight", "")
                if insight:
                    sections.append(f"{key}: {insight}")

        return "\n".join(sections) + "\n\n위 분석 결과를 바탕으로 상권 분석 리포트를 작성하세요."

    async def execute(self, state: dict[str, Any]) -> NarrativeReportOutput:
        user_prompt = self.build_user_prompt(state, {})

        llm_result = await self.call_llm(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_format=NarrativeReportOutput,
        )

        if llm_result["parsed"]:
            return llm_result["parsed"]
        return self._parse_structured_output(llm_result["content"], NarrativeReportOutput)

