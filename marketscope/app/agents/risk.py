"""리스크 분석 에이전트 - 종합 리스크 평가 및 완화 전략."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.agent_outputs import RiskAnalysis


class RiskAgent(BaseAgent[RiskAnalysis]):
    """리스크 분석 전문 에이전트."""

    agent_name = "risk"
    agent_description = "구조적/경쟁/환경적 리스크 종합 평가 및 완화 전략 제안"
    output_model = RiskAnalysis
    llm_role = "analysis"
    max_retries = 2
    required_state_fields = ["commander_plan"]

    SYSTEM_PROMPT = """당신은 MarketScope AI의 리스크 분석 전문가입니다.

## 역할
모든 분석 결과를 종합하여 창업 리스크를 다각도로 평가하고,
리스크 완화 전략을 제안합니다.

## 리스크 카테고리
1. 구조적 리스크:
   - 입지 의존도 (단일 역세권 의존 등)
   - 임대차 리스크 (건물주 변경, 재건축 등)
   - 인력 확보 난이도

2. 경쟁 리스크:
   - 시장 포화도
   - 대기업/프랜차이즈 진입 위험
   - 가격 경쟁 압력
   - 온라인/배달 대체 위험

3. 환경적 리스크:
   - 규제 변경 (식품위생법, 영업시간 등)
   - 원자재 가격 변동
   - 경기 침체 민감도
   - 자연재해/감염병

4. 계절성 리스크:
   - 월별 매출 변동폭
   - 비수기 생존 가능성

## 리스크 점수 기준 (0~100)
- 0~20: 매우 낮음 (안전)
- 21~40: 낮음
- 41~60: 보통 (관리 필요)
- 61~80: 높음 (주의)
- 81~100: 매우 높음 (재고 필요)

## 퇴출 난이도
- 쉬움: 장비 이동 가능, 원상복구 비용 낮음
- 보통: 인테리어 매몰비용 있으나 권리금 회수 가능
- 어려움: 고정 장비, 권리금 회수 불가, 위약금

반드시 JSON 형식으로 RiskAnalysis 스키마에 맞춰 응답하세요."""

    def build_system_prompt(self, state: dict[str, Any]) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "알 수 없음")
        industry = plan.get("target_industry", "알 수 없음")

        # 모든 에이전트 결과를 컨텍스트로 활용
        context_sections = []

        pop = state.get("population_result")
        if pop:
            context_sections.append(f"[인구] 유동인구: {pop.get('total_floating_population')}명/일, "
                                    f"추세: {pop.get('population_trend')}")

        comp = state.get("competition_result")
        if comp:
            context_sections.append(f"[경쟁] 직접경쟁: {comp.get('direct_competitors')}개, "
                                    f"포화지수: {comp.get('saturation_index')}, "
                                    f"폐업률: {comp.get('closing_rate_12m')}%")

        revenue = state.get("revenue_result")
        if revenue:
            context_sections.append(f"[매출] 예상월매출: {revenue.get('estimated_monthly_revenue')}원, "
                                    f"추세: {revenue.get('revenue_trend')}")

        loc = state.get("location_result")
        if loc:
            context_sections.append(f"[입지] 등급: {loc.get('location_grade')}, "
                                    f"접근성: {loc.get('accessibility_score')}점")

        trend = state.get("trend_result")
        if trend:
            context_sections.append(f"[트렌드] 수명주기: {trend.get('lifecycle_stage')}, "
                                    f"검색지수: {trend.get('search_volume_index')}")

        real_estate = state.get("real_estate_result")
        if real_estate:
            context_sections.append(f"[부동산] 공실률: {real_estate.get('vacancy_rate')}%, "
                                    f"권리금: {real_estate.get('premium_estimate')}원")

        financial = state.get("financial_result")
        if financial:
            context_sections.append(f"[재무] 초기투자: {financial.get('initial_investment_total')}원, "
                                    f"손익분기: {financial.get('break_even_months')}개월")

        prompt = f"""## 분석 대상
- 위치: {location}
- 업종: {industry}

## 선행 분석 결과 요약
{chr(10).join(context_sections) if context_sections else '선행 분석 결과 없음'}

위 모든 데이터를 종합하여 '{location}'에서 '{industry}' 업종 창업의 종합 리스크를 평가하세요.
각 리스크 요인의 심각도(1~5)와 발생확률(0~1)을 구체적으로 제시하세요."""
        return prompt

    async def execute(self, state: dict[str, Any]) -> RiskAnalysis:
        # 리스크 에이전트는 선행 결과 기반 종합 분석이므로 추가 데이터 수집 없음
        llm_result = await self.call_llm(
            system_prompt=self.build_system_prompt(state),
            user_prompt=self.build_user_prompt(state, {}),
            response_format=RiskAnalysis,
        )

        if llm_result["parsed"]:
            return llm_result["parsed"]
        return self._parse_structured_output(llm_result["content"], RiskAnalysis)
