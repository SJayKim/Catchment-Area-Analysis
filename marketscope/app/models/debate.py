"""토론 관련 모델 (Phase 2 - 스텁)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DebateArgument(BaseModel):
    agent_role: str = Field(...)
    argument_type: str = Field(...)
    content: str = Field(...)
    evidence_references: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    timestamp: str = Field(...)


class DebateRound(BaseModel):
    round_number: int = Field(..., ge=1)
    topic: str = Field(...)
    advocate_argument: DebateArgument = Field(...)
    critic_argument: DebateArgument = Field(...)
    round_summary: Optional[str] = None


class JudgeVerdict(BaseModel):
    """Judge 에이전트의 라운드별 판정."""
    accepted_claims: list[str] = Field(default_factory=list)
    rejected_claims: list[str] = Field(default_factory=list)
    reasoning: str = Field(...)
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_converged: bool = Field(False, description="토론이 수렴했는지 여부")


class DebateResult(BaseModel):
    """토론 최종 결과."""
    overall_verdict: str = Field(..., description="최종 판정 (추천/조건부추천/비추천)")
    verdict_summary: str = Field(...)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    conditions_for_success: list[str] = Field(default_factory=list)
    revised_score: Optional[float] = Field(None, ge=0.0, le=100.0, description="토론 반영 수정 점수")
    total_debate_rounds: int = Field(...)
    rounds: list[DebateRound] = Field(default_factory=list)
    judge_confidence: float = Field(..., ge=0.0, le=1.0)
