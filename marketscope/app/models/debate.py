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


class DebateResult(BaseModel):
    overall_verdict: str = Field(...)
    verdict_summary: str = Field(...)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    conditions_for_success: list[str] = Field(default_factory=list)
    total_debate_rounds: int = Field(...)
    judge_confidence: float = Field(..., ge=0.0, le=1.0)
