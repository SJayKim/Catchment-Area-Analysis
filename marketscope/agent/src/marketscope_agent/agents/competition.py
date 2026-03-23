"""경쟁분석 에이전트 - 경쟁 업체, 포화도, 개폐업률 분석."""

from __future__ import annotations

from typing import Any, Optional

from marketscope_agent.agents.base import BaseAgent
from marketscope_common.exceptions import DataCollectionError
from marketscope_common.models.agent_outputs import CompetitionAnalysis


class CompetitionAgent(BaseAgent[CompetitionAnalysis]):
    """경쟁 분석 전문 에이전트."""

    agent_name = "competition"
    agent_description = "경쟁 업체 현황, 시장 포화도, 개폐업률 분석"
    output_model = CompetitionAnalysis
    llm_role = "analysis"
    max_retries = 2
    required_state_fields = ["commander_plan"]

    SYSTEM_PROMPT = """당신은 MarketScope AI의 경쟁분석 전문가입니다.

## 역할
상권 내 경쟁 환경을 분석하여 시장 진입 가능성과 경쟁 전략을 도출합니다.

## 핵심 분석 항목
1. 경쟁 업체 수: 직접 경쟁(동일 소분류)과 간접 경쟁(동일 대분류) 구분
2. 시장 포화 지수: 인구 대비 점포 수 (1.0=평균, 1.0 초과=포화)
3. 개업률/폐업률: 최근 12개월 신규 개업 및 폐업 비율
4. 평균 영업 기간: 생존율 지표
5. 시장 집중도: 상위 5개 업체 매출 점유율
6. 차별화 기회: 경쟁 공백 또는 미충족 수요

## 포화 지수 해석
- 0.0~0.5: 매우 낮음 (블루오션)
- 0.5~0.8: 낮음 (진입 여지 큼)
- 0.8~1.2: 보통
- 1.2~1.5: 높음 (포화 경고)
- 1.5 이상: 매우 높음 (레드오션)

## 폐업률 해석
- < 5%: 안정적
- 5~10%: 보통
- 10~15%: 높음 (경고)
- > 15%: 매우 높음 (위험)

반드시 JSON 형식으로 CompetitionAnalysis 스키마에 맞춰 응답하세요."""

    def build_system_prompt(self, state: dict[str, Any]) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "알 수 없음")
        industry = plan.get("target_industry", "알 수 없음")

        prompt = f"""## 분석 대상
- 위치: {location}
- 업종: {industry}

## 수집된 경쟁 데이터
"""
        if data:
            for key, value in data.items():
                prompt += f"\n### {key}\n{value}\n"
        else:
            prompt += "\n경쟁 데이터를 수집하지 못했습니다. 일반적인 서울 주요 상권 기준으로 합리적 추정치를 제시하세요.\n"

        prompt += f"\n위 데이터를 기반으로 '{location}' 상권의 '{industry}' 업종 경쟁 환경을 분석하세요."
        return prompt

    async def _collect_data(self, state: dict[str, Any]) -> dict[str, Any]:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "")
        industry = plan.get("target_industry", "")
        data: dict[str, Any] = {}

        try:
            geo = await self.call_tool("maps.geocode", {"address": location})
            data["geocode"] = geo
        except Exception as e:
            self.logger.warning(
                "지오코딩 실패: %s",
                str(e),
                extra={"tool_name": "maps.geocode", "error": str(e)},
            )

        district_code = data.get("geocode", {}).get("district_code", "")

        tool_calls = []
        if district_code:
            tool_calls.extend([
                {"tool_name": "public_data.get_store_count", "arguments": {"district_code": district_code, "industry": industry}},
                {"tool_name": "public_data.get_store_openclose", "arguments": {"district_code": district_code, "industry": industry}},
            ])

        if tool_calls:
            results = await self.call_tools_parallel(tool_calls)
            for i, tc in enumerate(tool_calls):
                name = tc["tool_name"].split(".")[-1]
                data[name] = results[i]

        return data

    async def execute(self, state: dict[str, Any]) -> CompetitionAnalysis:
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

        llm_result = await self.call_llm(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_format=CompetitionAnalysis,
        )

        if llm_result["parsed"]:
            return llm_result["parsed"]
        return self._parse_structured_output(llm_result["content"], CompetitionAnalysis)
