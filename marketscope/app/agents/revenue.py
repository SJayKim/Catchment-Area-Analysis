"""매출분석 에이전트 - 상권 매출, 업종별 매출 추정."""

from __future__ import annotations

from typing import Any, Optional

from app.agents.base import BaseAgent
from app.exceptions import DataCollectionError
from app.models.agent_outputs import RevenueAnalysis


class RevenueAgent(BaseAgent[RevenueAnalysis]):
    """매출 분석 전문 에이전트."""

    agent_name = "revenue"
    agent_description = "업종별 매출 추정, 매출 트렌드 분석"
    output_model = RevenueAnalysis
    llm_role = "analysis"
    max_retries = 2
    required_state_fields = ["commander_plan", "population_result"]

    SYSTEM_PROMPT = """당신은 MarketScope AI의 매출분석 전문가입니다.

## 역할
소상공인시장진흥공단 매출 데이터를 기반으로 상권의 매출 현황과 신규 점포 매출 전망을 분석합니다.

## 핵심 분석 항목
1. 상권 전체 매출: 해당 상권 내 모든 업종의 합산 월매출
2. 타겟 업종 매출: 분석 요청 업종의 월매출 합계
3. 점포당 평균 매출: 업종 평균 및 상위/하위 분포
4. 매출 추세: 최근 12개월 증감 추이
5. 객단가: 건당 평균 결제 금액
6. 시간대별/요일별 매출 패턴

## 매출 추정 방법
신규 점포 예상 매출 = 업종 평균 매출 × 위치 보정계수 × 시장 진입 할인율(0.7~0.85)
- 위치 보정계수: 유동인구 기반 (인구 분석 결과 참조)
- 시장 진입 할인율: 신규 점포의 인지도 부족 반영

## 해석 기준
- 점포당 월매출 > 5,000만원: 매우 높음
- 점포당 월매출 3,000~5,000만원: 높음
- 점포당 월매출 1,500~3,000만원: 보통
- 점포당 월매출 < 1,500만원: 낮음

반드시 JSON 형식으로 RevenueAnalysis 스키마에 맞춰 응답하세요."""

    def build_system_prompt(self, state: dict[str, Any]) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "알 수 없음")
        industry = plan.get("target_industry", "알 수 없음")

        # 인구 분석 결과 참조
        pop = state.get("population_result")
        pop_summary = ""
        if pop:
            pop_summary = f"일평균 유동인구: {pop.get('total_floating_population', 'N/A')}명"

        prompt = f"""## 분석 대상
- 위치: {location}
- 업종: {industry}
- 유동인구 참조: {pop_summary if pop_summary else '데이터 없음'}

## 수집된 매출 데이터
"""
        if data:
            for key, value in data.items():
                prompt += f"\n### {key}\n{value}\n"
        else:
            prompt += "\n매출 데이터를 수집하지 못했습니다. 일반적인 서울 주요 상권 기준으로 합리적 추정치를 제시하세요.\n"

        prompt += f"\n위 데이터를 기반으로 '{location}' 상권에서 '{industry}' 업종의 매출 전망을 분석하세요."
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

        district_code = data.get("geocode", {}).get("district_code", "")

        tool_calls = []
        if district_code:
            tool_calls.extend([
                {"tool_name": "public_data.get_commercial_revenue", "arguments": {"district_code": district_code}},
                {"tool_name": "public_data.get_industry_revenue", "arguments": {"district_code": district_code, "industry": plan.get("target_industry", "")}},
            ])

        if tool_calls:
            results = await self.call_tools_parallel(tool_calls)
            for i, tc in enumerate(tool_calls):
                name = tc["tool_name"].split(".")[-1]
                data[name] = results[i]

        return data

    async def execute(self, state: dict[str, Any]) -> RevenueAnalysis:
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
            response_format=RevenueAnalysis,
        )

        if llm_result["parsed"]:
            return llm_result["parsed"]
        return self._parse_structured_output(llm_result["content"], RevenueAnalysis)
