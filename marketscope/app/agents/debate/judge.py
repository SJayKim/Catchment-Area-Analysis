"""Judge (판사) 에이전트 - Advocate/Critic 양측 논거를 평가하여 최종 판정."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.debate import JudgeVerdict


class JudgeAgent(BaseAgent[JudgeVerdict]):
    """최종 판정 에이전트 (판사)."""

    agent_name = "judge"
    agent_description = "Advocate와 Critic의 논거를 평가하여 최종 판정"
    output_model = JudgeVerdict
    llm_role = "analysis"
    max_retries = 2

    SYSTEM_PROMPT = """당신은 MarketScope AI 토론 시스템의 Judge(판사)입니다.

## 역할
Advocate(옹호자)와 Critic(비평가)의 논거를 **공정하게 평가**하여
어떤 주장이 더 타당한지 판정합니다.

## 판정 원칙
1. 데이터 기반 주장에 높은 가중치 부여
2. 논리적 일관성 검증
3. 가정의 현실성 평가
4. 양측 논거의 강점과 약점을 균형있게 정리
5. 최종 판정에 대한 명확한 근거 제시

## 수렴 판단
- 양측 논거의 핵심 쟁점이 해소되면 `is_converged: true`
- 새로운 유의미한 논거가 없으면 `is_converged: true`
- confidence ≥ 0.7이면 수렴 권장

## 출력 형식
반드시 JSON으로 JudgeVerdict 스키마에 맞춰 응답:
- accepted_claims: 수용된 주장 목록
- rejected_claims: 기각된 주장 목록
- reasoning: 판정 근거 (상세)
- confidence: 판정 신뢰도 (0.0~1.0)
- is_converged: 토론 수렴 여부"""

    def build_system_prompt(self, state: dict[str, Any]) -> str:
        return self.SYSTEM_PROMPT

    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        plan = state.get("commander_plan", {})
        location = plan.get("target_location", "알 수 없음")
        industry = plan.get("target_industry", "알 수 없음")

        round_num = data.get("round_number", 1)
        advocate_arg = data.get("advocate_argument", "")
        critic_arg = data.get("critic_argument", "")
        previous_verdicts = data.get("previous_verdicts", [])

        prompt = f"""## 토론 라운드 {round_num} 판정

### 분석 대상
- 위치: {location}
- 업종: {industry}

### Advocate 주장
{advocate_arg}

### Critic 주장
{critic_arg}
"""
        if previous_verdicts:
            prompt += "\n### 이전 라운드 판정 이력\n"
            for v in previous_verdicts:
                prompt += f"- 라운드 {v.get('round', '?')}: {v.get('reasoning', '')[:200]}\n"

        prompt += "\n양측 논거를 평가하고 최종 판정을 내리세요."
        return prompt

    async def execute(self, state: dict[str, Any]) -> JudgeVerdict:
        data = state.get("_debate_context", {})
        llm_result = await self.call_llm(
            system_prompt=self.build_system_prompt(state),
            user_prompt=self.build_user_prompt(state, data),
            response_format=JudgeVerdict,
        )
        if llm_result["parsed"]:
            return llm_result["parsed"]
        return self._parse_structured_output(llm_result["content"], JudgeVerdict)
