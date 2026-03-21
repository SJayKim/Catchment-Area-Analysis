"""부동산 분석 에이전트 - 임대료, 권리금, 공실률, 매물 분석."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.agent_outputs import RealEstateAnalysis


class RealEstateAgent(BaseAgent[RealEstateAnalysis]):
    """부동산 분석 전문 에이전트."""

    agent_name = "real_estate"
    agent_description = "상가 임대료, 권리금, 공실률, 매물 정보 분석"
    output_model = RealEstateAnalysis
    llm_role = "analysis"
    max_retries = 2
    required_state_fields = ["commander_plan", "location_result"]

    SYSTEM_PROMPT = """당신은 MarketScope AI의 부동산 분석 전문가입니다.

## 역할
상권 내 상가 부동산 시장을 분석하여 임대료, 권리금, 공실률 등
부동산 관련 핵심 정보를 제공합니다.

## 핵심 분석 항목
1. 임대료 (평당 월 임대료):
   - 강남역: 15~25만원/평
   - 홍대/신촌: 10~18만원/평
   - 일반 역세권: 8~15만원/평
   - 주택가: 3~8만원/평

2. 권리금:
   - 시설 권리금: 인테리어/장비 감가상각 기반
   - 영업 권리금: 매출/고객 기반 가치
   - 바닥 권리금: 입지 프리미엄 (좋은 자리일수록 높음)
   - 일반적으로 연매출의 30~50%

3. 공실률:
   - 5% 미만: 매우 건전
   - 5~10%: 건전
   - 10~15%: 주의
   - 15% 이상: 위험

4. 권장 면적 (업종별):
   - 카페: 15~30평
   - 음식점: 20~40평
   - 소매: 10~20평
   - 미용/네일: 8~15평

반드시 JSON 형식으로 RealEstateAnalysis 스키마에 맞춰 응답하세요."""

    def build_system_prompt(self, state: dict[str, Any]) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "알 수 없음")
        industry = plan.get("target_industry", "알 수 없음")

        loc = state.get("location_result")
        context_lines = []
        if loc:
            context_lines.append(f"입지등급: {loc.get('location_grade', 'N/A')}")
            context_lines.append(f"접근성점수: {loc.get('accessibility_score', 'N/A')}점")

        prompt = f"""## 분석 대상
- 위치: {location}
- 업종: {industry}
- 참조: {', '.join(context_lines) if context_lines else '없음'}

## 수집된 부동산 데이터
"""
        if data:
            for key, value in data.items():
                prompt += f"\n### {key}\n{value}\n"
        else:
            prompt += "\n부동산 데이터를 수집하지 못했습니다. 해당 지역의 일반적인 상가 시세 기준으로 합리적 추정치를 제시하세요.\n"

        prompt += f"\n위 데이터를 기반으로 '{location}' 상권의 '{industry}' 업종에 대한 부동산 분석을 수행하세요."
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
            {"tool_name": "real_estate.get_transaction_price", "arguments": {"location": location}},
            {"tool_name": "real_estate.get_vacancy_rate", "arguments": {"location": location}},
        ]

        results = await self.call_tools_parallel(tool_calls)
        key_names = ["rent_info", "transaction_prices", "vacancy_data"]
        for i, result in enumerate(results):
            if i < len(key_names):
                data[key_names[i]] = result

        return data

    async def execute(self, state: dict[str, Any]) -> RealEstateAnalysis:
        try:
            data = await self._collect_data(state)
        except Exception as e:
            self.logger.warning("부동산 데이터 수집 실패: %s", e)
            data = {}

        llm_result = await self.call_llm(
            system_prompt=self.build_system_prompt(state),
            user_prompt=self.build_user_prompt(state, data),
            response_format=RealEstateAnalysis,
        )

        if llm_result["parsed"]:
            return llm_result["parsed"]
        return self._parse_structured_output(llm_result["content"], RealEstateAnalysis)
