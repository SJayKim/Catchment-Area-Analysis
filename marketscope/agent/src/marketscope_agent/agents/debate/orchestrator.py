"""Debate Orchestrator - 토론 라운드 관리 및 수렴 판단."""

from __future__ import annotations

import time
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

from marketscope_agent.agents.debate.advocate import AdvocateAgent
from marketscope_agent.agents.debate.critic import CriticAgent
from marketscope_agent.agents.debate.judge import JudgeAgent
from marketscope_common.config import Settings, get_settings
from marketscope_common.logging import get_logger
from marketscope_common.models.debate import DebateResult, DebateRound

logger = get_logger("debate.orchestrator")

MAX_ROUNDS = 3


class DebateOrchestrator:
    """Advocate/Critic/Judge 토론을 라운드 단위로 관리한다."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        mcp_client: Optional[Any] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.mcp_client = mcp_client

    def _create_agents(self) -> tuple[AdvocateAgent, CriticAgent, JudgeAgent]:
        kwargs = {"settings": self.settings, "mcp_client": self.mcp_client}
        return (
            AdvocateAgent(**kwargs),
            CriticAgent(**kwargs),
            JudgeAgent(**kwargs),
        )

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """토론을 수행하고 DebateResult를 반환한다."""
        session_id = state.get("session_id", "")
        debate_start = time.monotonic()

        advocate, critic, judge = self._create_agents()

        # 토론 트리거 이유 판단
        plan = state.get("commander_plan", {})
        trigger_reason = "low_confidence"
        if plan.get("force_debate"):
            trigger_reason = "force_debate"

        logger.info(
            "debate.start",
            session_id=session_id,
            trigger_reason=trigger_reason,
            max_rounds=MAX_ROUNDS,
        )

        # Langfuse trace 생성
        from marketscope_common.monitoring.langfuse_handler import create_trace
        trace = create_trace(session_id, "debate", {"trigger_reason": trigger_reason})

        rounds: list[DebateRound] = []
        previous_verdicts: list[dict[str, Any]] = []
        previous_advocate_arg = ""
        previous_critic_arg = ""

        final_verdict = None

        for round_num in range(1, MAX_ROUNDS + 1):
            round_start = time.monotonic()
            logger.info("debate.round.start", round_number=round_num)

            try:
                # 1. Advocate 주장
                advocate_state = {
                    **state,
                    "_debate_context": {
                        "round_number": round_num,
                        "previous_critic_argument": previous_critic_arg,
                    },
                }
                advocate_result = await advocate.execute(advocate_state)
                advocate_arg_content = advocate_result.content if hasattr(advocate_result, "content") else str(advocate_result)

                logger.info(
                    "debate.advocate",
                    round_number=round_num,
                    argument_length=len(advocate_arg_content),
                )

                # 2. Critic 반론
                critic_state = {
                    **state,
                    "_debate_context": {
                        "round_number": round_num,
                        "previous_advocate_argument": advocate_arg_content,
                    },
                }
                critic_result = await critic.execute(critic_state)
                critic_arg_content = critic_result.content if hasattr(critic_result, "content") else str(critic_result)

                logger.info(
                    "debate.critic",
                    round_number=round_num,
                    argument_length=len(critic_arg_content),
                )

                # 3. Judge 판정
                judge_state = {
                    **state,
                    "_debate_context": {
                        "round_number": round_num,
                        "advocate_argument": advocate_arg_content,
                        "critic_argument": critic_arg_content,
                        "previous_verdicts": previous_verdicts,
                    },
                }
                verdict = await judge.execute(judge_state)
                final_verdict = verdict

                # Judge 로깅
                verdict_confidence = getattr(verdict, "confidence", 0)
                verdict_converged = getattr(verdict, "is_converged", False)
                logger.info(
                    "debate.judge",
                    round_number=round_num,
                    confidence=verdict_confidence,
                    is_converged=verdict_converged,
                    accepted_claims=len(getattr(verdict, "accepted_claims", []) or []),
                    rejected_claims=len(getattr(verdict, "rejected_claims", []) or []),
                )

                # 라운드 기록
                debate_round = DebateRound(
                    round_number=round_num,
                    topic=f"라운드 {round_num}",
                    advocate_argument=advocate_result,
                    critic_argument=critic_result,
                    round_summary=verdict.reasoning if hasattr(verdict, "reasoning") else "",
                )
                rounds.append(debate_round)

                round_duration_ms = (time.monotonic() - round_start) * 1000
                logger.info(
                    "debate.round.complete",
                    round_number=round_num,
                    duration_ms=round(round_duration_ms, 1),
                )

                previous_verdicts.append({
                    "round": round_num,
                    "reasoning": verdict.reasoning if hasattr(verdict, "reasoning") else "",
                })
                previous_advocate_arg = advocate_arg_content
                previous_critic_arg = critic_arg_content

                # 수렴 체크
                if hasattr(verdict, "is_converged") and verdict.is_converged:
                    logger.info("debate.converged", round_number=round_num)
                    break

                if hasattr(verdict, "confidence") and verdict.confidence >= 0.7:
                    logger.info("debate.confidence_sufficient", round_number=round_num, confidence=verdict.confidence)
                    break

            except Exception as e:
                logger.error(
                    "debate.round.error",
                    round_number=round_num,
                    error_type=type(e).__name__,
                    error=str(e),
                    exc_info=True,
                )
                break

        # 최종 결과 조립
        debate_result = self._build_result(rounds, final_verdict)

        total_duration_ms = (time.monotonic() - debate_start) * 1000
        converged = final_verdict and hasattr(final_verdict, "is_converged") and final_verdict.is_converged
        logger.info(
            "debate.complete",
            session_id=session_id,
            total_rounds=len(rounds),
            revised_score=debate_result.revised_score,
            overall_verdict=debate_result.overall_verdict,
            convergence_reached=converged,
            duration_ms=round(total_duration_ms, 1),
        )

        # Prometheus 메트릭
        from marketscope_common.monitoring.metrics import observe_debate
        observe_debate(len(rounds), converged or False)

        return {
            "debate_result": debate_result.model_dump() if debate_result else None,
            "progress_pct": 80.0,
        }

    def _build_result(
        self,
        rounds: list[DebateRound],
        final_verdict: Any,
    ) -> DebateResult:
        """라운드 결과를 종합하여 DebateResult를 생성한다."""
        # 수용/기각된 주장 수집
        strengths: list[str] = []
        weaknesses: list[str] = []
        conditions: list[str] = []

        if final_verdict and hasattr(final_verdict, "accepted_claims"):
            strengths = final_verdict.accepted_claims or []
        if final_verdict and hasattr(final_verdict, "rejected_claims"):
            weaknesses = final_verdict.rejected_claims or []

        judge_confidence = 0.5
        if final_verdict and hasattr(final_verdict, "confidence"):
            judge_confidence = final_verdict.confidence

        # 판정 결정
        if judge_confidence >= 0.7 and len(strengths) > len(weaknesses):
            verdict = "추천"
        elif judge_confidence >= 0.5:
            verdict = "조건부추천"
        else:
            verdict = "비추천"

        reasoning = ""
        if final_verdict and hasattr(final_verdict, "reasoning"):
            reasoning = final_verdict.reasoning

        return DebateResult(
            overall_verdict=verdict,
            verdict_summary=reasoning,
            strengths=strengths,
            weaknesses=weaknesses,
            conditions_for_success=conditions,
            revised_score=None,
            total_debate_rounds=len(rounds),
            rounds=rounds,
            judge_confidence=judge_confidence,
        )
