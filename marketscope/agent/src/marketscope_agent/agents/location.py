"""입지분석 에이전트 - 교통, 접근성, 주변시설 분석."""

from __future__ import annotations

from typing import Any, Optional

from marketscope_agent.agents.base import BaseAgent
from marketscope_common.exceptions import DataCollectionError
from marketscope_common.models.agent_outputs import LocationAnalysis


class LocationAgent(BaseAgent[LocationAnalysis]):
    """입지 분석 전문 에이전트."""

    agent_name = "location"
    agent_description = "교통 접근성, 가시성, 주변 앵커 시설, 개발 계획 분석"
    output_model = LocationAnalysis
    llm_role = "analysis"
    max_retries = 2
    required_state_fields = ["commander_plan", "population_result", "competition_result"]

    SYSTEM_PROMPT = """당신은 MarketScope AI의 입지분석 전문가입니다.

## 역할
상권의 교통 접근성, 가시성, 주변 앵커 시설을 종합 분석하여 입지 등급을 평가합니다.

## 핵심 분석 항목
1. 교통 접근성: 지하철역 거리/도보시간, 버스 노선 수, 주차 가용성
2. 가시성: 주요 보행 동선 대비 점포 노출 정도
3. 앵커 시설: 백화점, 대형마트, 병원, 대학교 등 집객 시설
4. 개발 계획: 인근 재개발, 신규 건축 등 미래 가치
5. 층수 권장: 업종별 최적 층수 및 사유

## 접근성 점수 기준 (0~100)
- 90~100: 지하철 도보 1분, 버스 10개+
- 70~89: 지하철 도보 5분 이내, 버스 5개+
- 50~69: 지하철 도보 10분 이내
- 30~49: 지하철 도보 15분 이내
- 0~29: 대중교통 불편

## 입지 등급
- S: 초역세권 + 대형 앵커 + 개발 호재
- A: 역세권 + 앵커 시설
- B: 준역세권 또는 앵커 인접
- C: 대중교통 보통
- D: 접근성 및 집객력 부족

반드시 JSON 형식으로 LocationAnalysis 스키마에 맞춰 응답하세요."""

    def build_system_prompt(self, state: dict[str, Any]) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "알 수 없음")
        industry = plan.get("target_industry", "알 수 없음")

        # 인구/경쟁 결과 참조
        pop = state.get("population_result")
        comp = state.get("competition_result")

        context_lines = []
        if pop:
            context_lines.append(f"일평균 유동인구: {pop.get('total_floating_population', 'N/A')}명")
        if comp:
            context_lines.append(f"직접 경쟁업체: {comp.get('direct_competitors', 'N/A')}개")

        prompt = f"""## 분석 대상
- 위치: {location}
- 업종: {industry}
- 참조: {', '.join(context_lines) if context_lines else '없음'}

## 수집된 입지 데이터
"""
        if data:
            for key, value in data.items():
                prompt += f"\n### {key}\n{value}\n"
        else:
            prompt += "\n입지 데이터를 수집하지 못했습니다. 일반적인 서울 주요 상권 기준으로 합리적 추정치를 제시하세요.\n"

        prompt += f"\n위 데이터를 기반으로 '{location}' 상권의 '{industry}' 업종에 대한 입지를 분석하세요."
        return prompt

    async def _collect_data(self, state: dict[str, Any]) -> dict[str, Any]:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "")
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

        lat = data.get("geocode", {}).get("lat")
        lng = data.get("geocode", {}).get("lng")

        tool_calls = []
        if lat and lng:
            tool_calls.extend([
                {"tool_name": "maps.get_transit_info", "arguments": {"lat": lat, "lng": lng, "radius": 500}},
                {"tool_name": "maps.search_nearby", "arguments": {"lat": lat, "lng": lng, "radius": 500, "category": "대형시설"}},
            ])

        if tool_calls:
            results = await self.call_tools_parallel(tool_calls)
            for i, tc in enumerate(tool_calls):
                name = tc["tool_name"].split(".")[-1]
                data[name] = results[i]

        return data

    async def execute(self, state: dict[str, Any]) -> LocationAnalysis:
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
            response_format=LocationAnalysis,
        )

        if llm_result["parsed"]:
            return llm_result["parsed"]
        return self._parse_structured_output(llm_result["content"], LocationAnalysis)
