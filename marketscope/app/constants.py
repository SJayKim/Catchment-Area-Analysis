"""MarketScope AI 상수 및 열거형 정의."""

from __future__ import annotations

from enum import Enum


class AnalysisMode(str, Enum):
    BASIC = "basic"
    COMPARISON = "comparison"
    QUICK = "quick"


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


class ConfidenceLevel(str, Enum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class AnalysisIntent(str, Enum):
    NEW_BUSINESS = "NEW_BUSINESS"
    EXISTING_BUSINESS = "EXISTING_BUSINESS"
    INVESTMENT = "INVESTMENT"
    COMPARISON = "COMPARISON"
    QUICK_LOOKUP = "QUICK_LOOKUP"


class ThreatLevel(str, Enum):
    VERY_LOW = "매우낮음"
    LOW = "낮음"
    MEDIUM = "보통"
    HIGH = "높음"
    VERY_HIGH = "매우높음"


# Phase 1 활성 에이전트
PHASE1_ACTIVE_AGENTS = ["population", "competition", "revenue", "location"]

# Phase 1 병렬 실행 그룹
PARALLEL_GROUP_1 = ["population", "competition"]  # 독립 실행
PARALLEL_GROUP_2 = ["revenue", "location"]  # Group 1 의존

# 분석 모드별 에이전트 매핑
ANALYSIS_MODE_AGENTS = {
    AnalysisMode.BASIC: ["population", "competition", "revenue", "location"],
    AnalysisMode.QUICK: ["population", "competition"],
    AnalysisMode.COMPARISON: ["population", "competition", "revenue", "location"],
}
