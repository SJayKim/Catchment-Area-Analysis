"""인구분석 에이전트 - 유동인구, 거주인구, 직장인구 분석."""

from __future__ import annotations

from typing import Any, Optional

from marketscope_agent.agents.base import BaseAgent
from marketscope_common.exceptions import DataCollectionError
from marketscope_common.models.agent_outputs import PopulationAnalysis


class PopulationAgent(BaseAgent[PopulationAnalysis]):
    """유동인구 분석 전문 에이전트."""

    agent_name = "population"
    agent_description = "상권 내 유동인구, 거주인구, 직장인구 패턴 분석"
    output_model = PopulationAnalysis
    llm_role = "analysis"
    max_retries = 2
    required_state_fields = ["commander_plan"]

    SYSTEM_PROMPT = """당신은 MarketScope AI의 인구분석 전문가입니다.

## 역할
상권의 유동인구, 거주인구, 직장인구 데이터를 종합 분석하여 해당 상권의 인구 특성과 패턴을 파악합니다.

## 핵심 개념 구분
1. 유동인구: 특정 시간대에 상권을 지나가거나 방문하는 사람 수 (통신사 기지국 데이터 기반)
2. 거주인구: 해당 행정동에 주민등록된 인구 (주민등록인구통계 기반)
3. 직장인구: 해당 지역에 출퇴근하는 인구 (사업체 종사자 수 기반)

## 시간대 분석
- 새벽(00~06): 심야 업종 관련
- 출근(06~09): 모닝 카페, 아침식사
- 오전(09~12): 주부/시니어 활동
- 점심(12~15): 직장인 점심 핵심
- 오후(15~18): 카페, 디저트, 학원가
- 저녁(18~21): 퇴근 후 외식, 쇼핑
- 야간(21~24): 2차, 야식

## 해석 기준
- 유동인구 > 10,000/일: 매우 많음 (상위 10%)
- 유동인구 5,000~10,000/일: 많음 (상위 30%)
- 유동인구 1,000~5,000/일: 보통
- 유동인구 < 1,000/일: 적음
- 거주인구 대비 직장인구 > 2배: 오피스 상권
- 직장인구 대비 거주인구 > 2배: 주거 상권

반드시 JSON 형식으로 PopulationAnalysis 스키마에 맞춰 응답하세요."""

    def build_system_prompt(self, state: dict[str, Any]) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "알 수 없음")
        industry = plan.get("target_industry", "알 수 없음")

        prompt = f"""## 분석 대상
- 위치: {location}
- 업종: {industry}

## 수집된 데이터
"""
        if data:
            for key, value in data.items():
                prompt += f"\n### {key}\n{value}\n"
        else:
            prompt += "\n데이터를 수집하지 못했습니다. 일반적인 서울 주요 상권 기준으로 합리적 추정치를 제시하세요.\n"

        prompt += f"\n위 데이터를 기반으로 '{location}' 상권의 인구 특성을 분석하고, '{industry}' 업종에 대한 시사점을 도출하세요."
        return prompt

    async def _collect_data(self, state: dict[str, Any]) -> dict[str, Any]:
        """MCP 도구를 통해 데이터 수집."""
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "")
        data: dict[str, Any] = {}

        # 지오코딩
        try:
            geo = await self.call_tool("maps.geocode", {"address": location, "detail": True})
            data["geocode"] = geo
        except Exception as e:
            self.logger.warning(
                "지오코딩 실패: %s",
                str(e),
                extra={"tool_name": "maps.geocode", "error": str(e)},
            )

        dong_code = data.get("geocode", {}).get("dong_code", "")

        # 병렬 데이터 수집
        tool_calls = []
        if dong_code:
            tool_calls.extend([
                {"tool_name": "public_data.get_seoul_living_population", "arguments": {"dong_code": dong_code}},
                {"tool_name": "public_data.get_resident_population", "arguments": {"admin_dong_code": dong_code, "year": 2025}},
                {"tool_name": "public_data.get_worker_population", "arguments": {"admin_dong_code": dong_code, "year": 2025}},
            ])

        if tool_calls:
            results = await self.call_tools_parallel(tool_calls)
            for i, tc in enumerate(tool_calls):
                name = tc["tool_name"].split(".")[-1]
                data[name] = results[i]

        return data

    async def execute(self, state: dict[str, Any]) -> PopulationAnalysis:
        try:
            data = await self._collect_data(state)
        except Exception as e:
            self.logger.warning(
                "데이터 수집 전체 실패, 빈 데이터로 진행: %s",
                str(e),
                extra={"tool_name": "_collect_data", "error": str(e)},
            )
            data = {}

        user_prompt = self.build_user_prompt(state, data)
        system_prompt = self.build_system_prompt(state)

        llm_result = await self.call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format=PopulationAnalysis,
        )

        if llm_result["parsed"]:
            return llm_result["parsed"]

        return self._parse_structured_output(llm_result["content"], PopulationAnalysis)
