"""재무 분석 에이전트 - 투자비, 운영비, 손익분기, ROI 분석."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.agent_outputs import FinancialAnalysis


class FinancialAgent(BaseAgent[FinancialAnalysis]):
    """재무 분석 전문 에이전트."""

    agent_name = "financial"
    agent_description = "초기 투자비, 월 운영비, 손익분기, ROI, 시나리오 분석"
    output_model = FinancialAnalysis
    llm_role = "analysis"
    max_retries = 2
    required_state_fields = ["commander_plan", "revenue_result", "competition_result"]

    SYSTEM_PROMPT = """당신은 MarketScope AI의 재무 분석 전문가입니다.

## 역할
상권 진입 시 필요한 초기 투자비, 월 운영비를 추정하고
손익분기점, ROI, 시나리오별 수익성을 분석합니다.

## 핵심 분석 항목
1. 초기 투자 항목:
   - 인테리어: 업종별 평당 100~300만원 (카페 200만+, 음식점 150만+)
   - 장비/집기: 업종별 1,000~5,000만원
   - 보증금: 월세의 10~20개월분
   - 권리금: 상권/업종에 따라 0~2억원
   - 초기 재고/원재료: 월 재료비의 1~2개월분

2. 월 운영비 항목:
   - 임대료: 평당 × 면적
   - 인건비: 최저시급 × 근무시간 × 인원 + 4대보험
   - 재료비: 매출의 30~40% (음식점), 20~30% (카페)
   - 공과금: 월 30~80만원
   - 기타: 마케팅, 소모품, 카드수수료 등

3. 손익분기 계산:
   손익분기 매출 = 고정비 / (1 - 변동비율)
   손익분기 기간 = 초기투자 / 월순이익

4. 시나리오 분석 (3개):
   - 낙관: 예상 매출의 120%, 확률 20%
   - 현실: 예상 매출의 100%, 확률 60%
   - 비관: 예상 매출의 70%, 확률 20%

반드시 JSON 형식으로 FinancialAnalysis 스키마에 맞춰 응답하세요."""

    def build_system_prompt(self, state: dict[str, Any]) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "알 수 없음")
        industry = plan.get("target_industry", "알 수 없음")

        revenue = state.get("revenue_result")
        comp = state.get("competition_result")
        real_estate = state.get("real_estate_result")

        context_lines = []
        if revenue:
            context_lines.append(f"예상 월매출: {revenue.get('estimated_monthly_revenue', 'N/A')}원")
            context_lines.append(f"점포당 평균매출: {revenue.get('revenue_per_store', 'N/A')}원")
        if comp:
            context_lines.append(f"직접 경쟁업체: {comp.get('direct_competitors', 'N/A')}개")
            context_lines.append(f"포화지수: {comp.get('saturation_index', 'N/A')}")
        if real_estate:
            context_lines.append(f"평당 임대료: {real_estate.get('avg_rent_per_pyeong', 'N/A')}원")
            context_lines.append(f"예상 권리금: {real_estate.get('premium_estimate', 'N/A')}원")

        prompt = f"""## 분석 대상
- 위치: {location}
- 업종: {industry}
- 참조 데이터: {chr(10).join(f'  - {l}' for l in context_lines) if context_lines else '없음'}

## 수집된 재무 데이터
"""
        if data:
            for key, value in data.items():
                prompt += f"\n### {key}\n{value}\n"
        else:
            prompt += "\n재무 데이터를 수집하지 못했습니다. 한국 일반적인 창업 비용 기준으로 합리적 추정치를 제시하세요.\n"

        prompt += f"\n위 데이터를 기반으로 '{location}'에서 '{industry}' 업종 창업의 재무 분석을 수행하세요."
        return prompt

    async def _collect_data(self, state: dict[str, Any]) -> dict[str, Any]:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "")
        data: dict[str, Any] = {}

        try:
            geo = await self.call_tool("maps.geocode", {"address": location})
            data["geocode"] = geo
        except Exception as e:
            self.logger.warning("지오코딩 실패: %s", e)

        tool_calls = [
            {"tool_name": "real_estate.get_rent_info", "arguments": {"location": location}},
        ]

        results = await self.call_tools_parallel(tool_calls)
        data["rent_info"] = results[0] if results else {}

        return data

    async def execute(self, state: dict[str, Any]) -> FinancialAnalysis:
        try:
            data = await self._collect_data(state)
        except Exception as e:
            self.logger.warning("재무 데이터 수집 실패: %s", e)
            data = {}

        llm_result = await self.call_llm(
            system_prompt=self.build_system_prompt(state),
            user_prompt=self.build_user_prompt(state, data),
            response_format=FinancialAnalysis,
        )

        if llm_result["parsed"]:
            return llm_result["parsed"]
        return self._parse_structured_output(llm_result["content"], FinancialAnalysis)
