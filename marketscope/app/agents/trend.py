"""트렌드 분석 에이전트 - 업종 트렌드, 검색량, 소셜 버즈 분석."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.agent_outputs import TrendAnalysis


class TrendAgent(BaseAgent[TrendAnalysis]):
    """업종 트렌드 분석 전문 에이전트."""

    agent_name = "trend"
    agent_description = "업종 수명주기, 검색 트렌드, 소비자 선호 변화 분석"
    output_model = TrendAnalysis
    llm_role = "analysis"
    max_retries = 2
    required_state_fields = ["commander_plan", "population_result"]

    SYSTEM_PROMPT = """당신은 MarketScope AI의 트렌드 분석 전문가입니다.

## 역할
업종의 시장 트렌드, 검색량 변화, SNS 버즈, 소비자 선호 변화를 분석하여
해당 업종의 성장 가능성과 시장 진입 타이밍을 평가합니다.

## 핵심 분석 항목
1. 업종 수명주기 판단:
   - 도입기: 검색량 급증, 경쟁 적음, 인지도 낮음
   - 성장기: 검색량 꾸준히 증가, 가맹점 증가, 언론 노출 증가
   - 성숙기: 검색량 정체, 경쟁 치열, 차별화 필수
   - 쇠퇴기: 검색량 감소, 폐업 증가, 트렌드 전환

2. 검색 트렌드 해석:
   - 검색량 지수 80+ (상위 20%): 높은 관심
   - 검색량 지수 50~80: 보통 관심
   - 검색량 지수 30 미만: 낮은 관심 또는 니치 시장

3. 소셜 버즈:
   - 블로그/뉴스 언급 빈도
   - 긍정/부정 감성 비율
   - 떠오르는 키워드 vs 하락 키워드

4. 계절성:
   - 성수기/비수기 패턴
   - 월별 매출 변동폭

반드시 JSON 형식으로 TrendAnalysis 스키마에 맞춰 응답하세요."""

    def build_system_prompt(self, state: dict[str, Any]) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "알 수 없음")
        industry = plan.get("target_industry", "알 수 없음")

        pop = state.get("population_result")
        context_lines = []
        if pop:
            context_lines.append(f"일평균 유동인구: {pop.get('total_floating_population', 'N/A')}명")
            context_lines.append(f"인구 추세: {pop.get('population_trend', 'N/A')}")

        prompt = f"""## 분석 대상
- 위치: {location}
- 업종: {industry}
- 참조: {', '.join(context_lines) if context_lines else '없음'}

## 수집된 트렌드 데이터
"""
        if data:
            for key, value in data.items():
                prompt += f"\n### {key}\n{value}\n"
        else:
            prompt += "\n트렌드 데이터를 수집하지 못했습니다. 일반적인 한국 시장 트렌드 기준으로 합리적 추정치를 제시하세요.\n"

        prompt += f"\n위 데이터를 기반으로 '{industry}' 업종의 '{location}' 지역 트렌드를 분석하세요."
        return prompt

    async def _collect_data(self, state: dict[str, Any]) -> dict[str, Any]:
        plan = state.get("commander_plan", {})
        industry = plan.get("target_industry", "")
        location = plan.get("target_location", "")
        data: dict[str, Any] = {}

        tool_calls = [
            {"tool_name": "news.search_blog", "arguments": {"query": f"{location} {industry}", "count": 10}},
            {"tool_name": "news.search_news", "arguments": {"query": f"{industry} 트렌드", "count": 10}},
        ]

        if industry:
            tool_calls.append(
                {"tool_name": "news.get_naver_datalab", "arguments": {"keyword": industry, "period": "12m"}},
            )

        results = await self.call_tools_parallel(tool_calls)
        key_names = ["blog_results", "news_results", "search_trend"]
        for i, result in enumerate(results):
            if i < len(key_names):
                data[key_names[i]] = result

        return data

    async def execute(self, state: dict[str, Any]) -> TrendAnalysis:
        try:
            data = await self._collect_data(state)
        except Exception as e:
            self.logger.warning("트렌드 데이터 수집 실패: %s", e)
            data = {}

        llm_result = await self.call_llm(
            system_prompt=self.build_system_prompt(state),
            user_prompt=self.build_user_prompt(state, data),
            response_format=TrendAnalysis,
        )

        if llm_result["parsed"]:
            return llm_result["parsed"]
        return self._parse_structured_output(llm_result["content"], TrendAnalysis)
