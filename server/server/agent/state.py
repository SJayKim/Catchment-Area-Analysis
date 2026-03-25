from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State for the MarketScope ReAct agent graph."""

    messages: Annotated[list[BaseMessage], add_messages]
    district_code: str
    district_name: str
    data_quarter: str
    iteration_count: int
