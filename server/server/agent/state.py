from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# ---------------------------------------------------------------------------
# PAE sub-types
# ---------------------------------------------------------------------------


class ToolPlanStep(TypedDict):
    tool_name: str  # e.g. "get_district_summary"
    args: dict  # e.g. {"district_code": "D3001"}
    reason: str  # e.g. "상권 종합 요약 조회"
    depends_on: list[int]  # indices of steps this depends on


class EvaluationResult(TypedDict):
    sufficient: bool
    missing_info: list[str]
    proactive_suggestions: list[str]
    reasoning: str


# ---------------------------------------------------------------------------
# Agent State
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    """State for the MarketScope agent graph (ReAct & PAE compatible)."""

    # --- existing (ReAct) ---
    messages: Annotated[list[BaseMessage], add_messages]
    district_code: str
    district_name: str
    data_quarter: str
    iteration_count: int

    # --- conversation (PAE) ---
    conversation_history: list[dict]
    session_id: str

    # --- intent (PAE: set by Planner) ---
    user_intent: str
    intent_confidence: float
    referenced_districts: list[str]
    referenced_category: str | None
    # GAP-A: list of {query, top: {code,name,score}, alternatives: [...]} when
    # Planner detected a Top1/Top2 tie in district name matching. Actor can
    # surface a disambiguation card from this state.
    ambiguous_districts: list[dict]

    # --- plan (PAE: set by Planner) ---
    plan: list[ToolPlanStep]
    plan_reasoning: str

    # --- execution (PAE: set by Actor) ---
    tool_results: dict[str, dict]
    tool_errors: dict[str, str]
    execution_round: int

    # --- evaluation (PAE: set by Evaluator) ---
    evaluation: EvaluationResult | None

    # --- response control (PAE) ---
    response_mode: str  # "direct" | "tool_assisted"
    card_emissions: list[dict]
