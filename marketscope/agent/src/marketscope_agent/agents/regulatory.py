"""규제/인허가 분석 에이전트 - 필요 허가, 용도지역, 위생/안전 요건."""

from __future__ import annotations

from typing import Any

from marketscope_agent.agents.base import BaseAgent
from marketscope_common.models.agent_outputs import RegulatoryAnalysis


class RegulatoryAgent(BaseAgent[RegulatoryAnalysis]):
    """규제/인허가 분석 전문 에이전트."""

    agent_name = "regulatory"
    agent_description = "업종별 필요 인허가, 용도지역 규제, 위생/안전 요건 분석"
    output_model = RegulatoryAnalysis
    llm_role = "analysis"
    max_retries = 2
    required_state_fields = ["commander_plan", "location_result"]

    SYSTEM_PROMPT = """당신은 MarketScope AI의 규제/인허가 분석 전문가입니다.

## 역할
업종별 필요한 인허가 사항, 용도지역 적합성, 위생·안전 요건을 분석하여
창업 전 반드시 확인해야 할 규제 사항을 정리합니다.

## 핵심 분석 항목
1. 필수 인허가:
   - 일반음식점: 영업신고 (구청), 위생교육 이수
   - 제과점: 제과점영업 신고, 식품제조가공업
   - 주류: 주류판매업 면허 (세무서)
   - 미용실: 미용업 신고, 미용사 자격증
   - 학원: 학원설립·운영 등록 (교육청)
   - 숙박: 숙박업 등록, 소방시설완비증명

2. 용도지역 확인:
   - 일반상업지역: 대부분 영업 가능
   - 준주거지역: 주거 환경 보호 제한
   - 근린생활시설: 2종 근생 해당 여부
   - 학교정화구역: 유해업소 제한 (200m)

3. 위생/안전 요건:
   - 객석 면적 기준
   - 화장실 설치 기준
   - 환기/배연 설비
   - 소방시설 (소화기, 감지기, 스프링클러)
   - 장애인 편의시설

4. 영업시간 제한:
   - 주거밀집지역: 야간 소음 규제
   - 학교 인근: 유해업소 영업시간 제한

반드시 JSON 형식으로 RegulatoryAnalysis 스키마에 맞춰 응답하세요."""

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
            context_lines.append(f"층수추천: {loc.get('floor_recommendation', 'N/A')}")

        prompt = f"""## 분석 대상
- 위치: {location}
- 업종: {industry}
- 참조: {', '.join(context_lines) if context_lines else '없음'}

## 수집된 규제 데이터
"""
        if data:
            for key, value in data.items():
                prompt += f"\n### {key}\n{value}\n"
        else:
            prompt += "\n규제 데이터를 수집하지 못했습니다. 한국 법령 기준으로 해당 업종의 인허가 요건을 정리하세요.\n"

        prompt += f"\n위 데이터를 기반으로 '{location}'에서 '{industry}' 업종 창업 시 필요한 규제/인허가 사항을 분석하세요."
        return prompt

    async def _collect_data(self, state: dict[str, Any]) -> dict[str, Any]:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "")
        industry = plan.get("target_industry", "")
        data: dict[str, Any] = {}

        tool_calls = [
            {"tool_name": "regulatory.get_permits", "arguments": {"industry": industry}},
            {"tool_name": "regulatory.get_zoning", "arguments": {"location": location}},
        ]

        results = await self.call_tools_parallel(tool_calls)
        key_names = ["permits", "zoning"]
        for i, result in enumerate(results):
            if i < len(key_names):
                data[key_names[i]] = result

        return data

    async def execute(self, state: dict[str, Any]) -> RegulatoryAnalysis:
        try:
            data = await self._collect_data(state)
        except Exception as e:
            self.logger.warning("규제 데이터 수집 실패: %s", e)
            data = {}

        llm_result = await self.call_llm(
            system_prompt=self.build_system_prompt(state),
            user_prompt=self.build_user_prompt(state, data),
            response_format=RegulatoryAnalysis,
        )

        if llm_result["parsed"]:
            return llm_result["parsed"]
        return self._parse_structured_output(llm_result["content"], RegulatoryAnalysis)
