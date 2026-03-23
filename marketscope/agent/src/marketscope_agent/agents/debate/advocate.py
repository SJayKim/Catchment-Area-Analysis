"""Advocate (창) 에이전트 - 기회와 강점을 극대화하는 긍정적 논거 제시."""

from __future__ import annotations

from typing import Any

from marketscope_agent.agents.base import BaseAgent
from marketscope_common.models.debate import DebateArgument


class AdvocateAgent(BaseAgent[DebateArgument]):
    """기회·강점 극대화 에이전트 (창, Spear)."""

    agent_name = "advocate"
    agent_description = "분석 결과에서 기회와 강점을 찾아 긍정적 논거를 제시"
    output_model = DebateArgument
    llm_role = "analysis"
    max_retries = 2

    SYSTEM_PROMPT = """당신은 MarketScope AI 토론 시스템의 Advocate(옹호자)입니다.

## 역할
분석 결과에서 **기회, 강점, 긍정적 요소**를 극대화하여 논거를 제시합니다.
투자 기회를 놓치지 않도록 잠재적 가능성을 적극적으로 발굴합니다.

## 논거 작성 원칙
1. 데이터에 기반한 구체적 근거 제시 (감정적 주장 금지)
2. 경쟁 우위 요소 발굴
3. 시장 성장 가능성 강조
4. 리스크에 대한 완화 가능성 제시
5. 성공 사례 유추 (유사 상권/업종)

## 출력 형식
반드시 JSON으로 DebateArgument 스키마에 맞춰 응답:
- agent_role: "advocate"
- argument_type: "opportunity" | "strength" | "mitigation"
- content: 핵심 논거 (구체적 데이터 포함)
- evidence_references: 참조한 분석 결과 목록
- confidence: 논거 신뢰도 (0.0~1.0)
- timestamp: ISO 형식 타임스탬프"""

    def build_system_prompt(self, state: dict[str, Any]) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "알 수 없음")
        industry = plan.get("target_industry", "알 수 없음")

        # 분석 결과 요약
        results_summary = self._summarize_results(state)

        round_num = data.get("round_number", 1)
        previous_critic = data.get("previous_critic_argument", "")

        prompt = f"""## 토론 라운드 {round_num}

### 분석 대상
- 위치: {location}
- 업종: {industry}

### 에이전트 분석 결과 요약
{results_summary}
"""
        if previous_critic:
            prompt += f"""
### Critic의 이전 라운드 주장
{previous_critic}

위 Critic의 주장에 대응하면서, 데이터에 기반한 긍정적 논거를 제시하세요.
"""
        else:
            prompt += "\n분석 결과에서 기회와 강점을 찾아 투자 가치를 논증하세요.\n"

        return prompt

    def _summarize_results(self, state: dict[str, Any]) -> str:
        """분석 결과를 요약한다."""
        sections = []
        result_map = {
            "인구": "population_result",
            "매출": "revenue_result",
            "경쟁": "competition_result",
            "입지": "location_result",
            "트렌드": "trend_result",
            "재무": "financial_result",
            "부동산": "real_estate_result",
            "규제": "regulatory_result",
        }
        for label, key in result_map.items():
            result = state.get(key)
            if isinstance(result, dict):
                insight = result.get("key_insight", "")
                confidence = result.get("confidence_score", 0)
                sections.append(f"- [{label}] {insight} (신뢰도: {confidence:.2f})")

        return "\n".join(sections) if sections else "분석 결과 없음"

    async def execute(self, state: dict[str, Any]) -> DebateArgument:
        data = state.get("_debate_context", {})
        llm_result = await self.call_llm(
            system_prompt=self.build_system_prompt(state),
            user_prompt=self.build_user_prompt(state, data),
            response_format=DebateArgument,
        )
        if llm_result["parsed"]:
            return llm_result["parsed"]
        return self._parse_structured_output(llm_result["content"], DebateArgument)
