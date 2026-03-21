"""Critic (방패) 에이전트 - 약점과 리스크를 지적하는 비판적 논거 제시."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.debate import DebateArgument


class CriticAgent(BaseAgent[DebateArgument]):
    """약점·리스크 지적 에이전트 (방패, Shield)."""

    agent_name = "critic"
    agent_description = "분석 결과에서 약점, 리스크, 논리적 허점을 지적"
    output_model = DebateArgument
    llm_role = "analysis"
    max_retries = 2

    SYSTEM_PROMPT = """당신은 MarketScope AI 토론 시스템의 Critic(비평가)입니다.

## 역할
분석 결과에서 **약점, 리스크, 논리적 허점, 과대평가된 요소**를 지적합니다.
투자자가 함정에 빠지지 않도록 냉철하게 문제점을 부각합니다.

## 논거 작성 원칙
1. 데이터의 한계점·불확실성 지적
2. 과도한 낙관을 견제 (과거 실패 사례 유추)
3. 숨겨진 리스크 발굴 (경쟁 심화, 규제, 임대료 상승 등)
4. 가정(assumption)의 취약점 공격
5. 대안적 해석 제시

## 출력 형식
반드시 JSON으로 DebateArgument 스키마에 맞춰 응답:
- agent_role: "critic"
- argument_type: "risk" | "weakness" | "counterargument"
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

        results_summary = self._summarize_results(state)

        round_num = data.get("round_number", 1)
        previous_advocate = data.get("previous_advocate_argument", "")

        prompt = f"""## 토론 라운드 {round_num}

### 분석 대상
- 위치: {location}
- 업종: {industry}

### 에이전트 분석 결과 요약
{results_summary}
"""
        if previous_advocate:
            prompt += f"""
### Advocate의 이번 라운드 주장
{previous_advocate}

위 Advocate의 주장에서 약점과 논리적 허점을 지적하세요.
"""
        else:
            prompt += "\n분석 결과에서 리스크와 약점을 찾아 투자 위험성을 논증하세요.\n"

        return prompt

    def _summarize_results(self, state: dict[str, Any]) -> str:
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
