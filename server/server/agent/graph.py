"""LangGraph agent for MarketScope AI.

Supports two modes controlled by settings.agent_mode:
  - "react"  : legacy prebuilt ReAct agent (default)
  - "pae"    : Planner-Actor-Evaluator custom graph
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from server.agent.prompts.system import get_system_prompt
from server.agent.tools.data_sources import get_sources_for_tool
from server.agent.tools.registry import get_tool_registry
from server.config import settings

LLM_PROVIDER = settings.llm_provider

logger = logging.getLogger(__name__)

# Flag to skip Anthropic after first auth failure (avoids repeated 401 roundtrips)
_anthropic_valid = True

# ===================================================================
# LangChain @tool wrappers (used by ReAct mode only)
# ===================================================================


@tool
async def get_floating_population_tool(
    district_code: str, quarter: str | None = None
) -> str:
    """상권의 유동인구 데이터를 조회합니다.

    시간대별, 성별, 연령별 유동인구 ���포를 반환합니다.
    일평균 유동인구, 피크 시간대 등의 정보를 포함합니다.

    Args:
        district_code: 상권코드
        quarter: 조회 분기 (예: "2025Q4"). 생략 시 최신 분기 조회.
    """
    from server.agent.tools.floating_population import get_floating_population

    result = await get_floating_population(district_code, quarter)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
async def get_estimated_sales_tool(
    district_code: str, category_code: str | None = None
) -> str:
    """상권의 추정 매출 데이터를 조회합니다.

    월 추정 매출, 분기별 추이, 성별/연령별/시간대별 매출 분포를 반환합니다.

    Args:
        district_code: 상권코드
        category_code: 업종코드. 생략 시 전체 업종 합산.
    """
    from server.agent.tools.estimated_sales import get_estimated_sales

    result = await get_estimated_sales(district_code, category_code)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
async def get_store_info_tool(
    district_code: str, category_code: str | None = None
) -> str:
    """상권의 점포 현황을 조회합니다.

    총 점포 수, 개업/폐업 수, 폐업률, 상위 5개 업종을 반환합니다.

    Args:
        district_code: 상권코드
        category_code: 업종코드. 생략 시 전체 업종 조회.
    """
    from server.agent.tools.store_info import get_store_info

    result = await get_store_info(district_code, category_code)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
async def get_population_info_tool(district_code: str) -> str:
    """상권의 상주인구 및 직장인구 데이터를 조회합니다.

    Args:
        district_code: 상권코드
    """
    from server.agent.tools.population_info import get_population_info

    result = await get_population_info(district_code)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
async def get_district_summary_tool(district_code: str) -> str:
    """상권의 종합 요약 정보를 조회합니다.

    Args:
        district_code: 상권코드
    """
    from server.agent.tools.district_summary import get_district_summary

    result = await get_district_summary(district_code)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
async def compare_districts_tool(district_codes: list[str]) -> str:
    """2~3개 상권의 주요 지표를 비교합니다.

    Args:
        district_codes: 비교할 상권코드 리스트 (2~3개)
    """
    from server.agent.tools.compare_districts import compare_districts

    result = await compare_districts(district_codes)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
async def recommend_business_tool(
    district_code: str,
    budget: int | None = None,
    preference: str | None = None,
) -> str:
    """상권에 적합한 업종 Top 5를 추천합니다.

    Args:
        district_code: 상권코드
        budget: 창업 예산 (만원 단위, 선택)
        preference: 선호 업종군 (예: "음식", "서비스", "소매", 선택)
    """
    from server.agent.tools.recommend_business import recommend_business

    result = await recommend_business(district_code, budget, preference)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
async def get_store_history_tool(district_code: str) -> str:
    """상권의 점포 이력 및 리스크 지표를 분석합니다.

    Args:
        district_code: 상권코드
    """
    from server.agent.tools.store_history import get_store_history

    result = await get_store_history(district_code)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
async def simulate_revenue_tool(
    district_code: str,
    category_code: str,
    unit_price: int | None = None,
    additional_competitors: int = 0,
) -> str:
    """상권에서 특정 업종 매출을 시뮬레이션합니다.

    하위(p25)/평균/상위(p75) 예상 월매출 범위와 서울 평균 비교를 반환합니다.

    Args:
        district_code: 상권코드
        category_code: 업종코드
        unit_price: 객단가 (원, 선택). 생략 시 기본 객단가 적용.
        additional_competitors: 추가 경쟁점 수 (기본 0)
    """
    from server.agent.tools.simulate_revenue import simulate_revenue

    result = await simulate_revenue(district_code, category_code, unit_price, additional_competitors)
    return json.dumps(result, ensure_ascii=False, default=str)


# ===================================================================
# Shared helpers
# ===================================================================

TOOLS = [
    get_district_summary_tool,
    get_floating_population_tool,
    get_estimated_sales_tool,
    get_store_info_tool,
    get_population_info_tool,
    compare_districts_tool,
    recommend_business_tool,
    get_store_history_tool,
    simulate_revenue_tool,
]

MAX_ITERATIONS = 5


def _create_llm(role: str = "default"):
    """Create the LLM instance based on configured provider and role.

    Role-based model selection (Gemini):
      - "respond", "react" → gemini-2.5-pro  (user-facing, quality matters)
      - "planner", "evaluator" → gemini-2.5-flash  (internal, speed matters)

    Provider "mock" returns a FakeListChatModel for load testing (no API cost).
    """
    if LLM_PROVIDER == "mock":
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        # Planner expects JSON with intent/plan; other roles get plain Korean text
        if role in ("planner",):
            responses = [
                '{"intent": "summary", "confidence": 0.95, '
                '"plan": [{"tool": "district_summary", "input": {"district_code": "%(district_code)s"}, "depends_on": []}], '
                '"direct_response": false, "reasoning": "상권 요약 요청"}'
            ]
        elif role in ("evaluator",):
            responses = [
                '{"sufficient": true, "reasoning": "모든 도구 결과가 정상 반환됨", "missing": []}'
            ]
        else:
            responses = [
                "강남역 상권은 서울 주요 상권 중 하나입니다. "
                "일평균 유동인구는 약 100만 명이며, 피크 시간대는 18시입니다. "
                "주요 업종은 한식, 커피, 편의점 순이고, "
                "최근 분기 추정 매출은 약 500억 원입니다. "
                "폐업률은 5.2%로 서울 평균 대비 양호한 수준입니다.",
            ]

        return FakeListChatModel(responses=responses, sleep=0.02)

    # Planner uses Anthropic Claude Sonnet for superior intent classification.
    # Guarded by _anthropic_valid flag to avoid retrying a known-bad key.
    if role == "planner" and settings.anthropic_api_key and _anthropic_valid:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
            max_tokens=4096,
            temperature=0.3,
        )

    if LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        pro_roles = {"respond", "react", "default"}
        model = settings.gemini_model_pro if role in pro_roles else settings.gemini_model_flash

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,  # type: ignore[arg-type]
            temperature=0.3,
            max_output_tokens=4096,
        )
    else:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
            max_tokens=4096,
            temperature=0.3,
        )


# ===================================================================
# ReAct agent (legacy)
# ===================================================================


def create_agent():
    """Build and return the compiled LangGraph ReAct agent."""
    llm = _create_llm(role="react")
    return create_react_agent(model=llm, tools=TOOLS)


# Singleton
_agent = None


def get_agent():
    if _agent is None:
        raise RuntimeError("Agent not initialized. Call set_agent() first.")
    return _agent


def set_agent(agent) -> None:
    global _agent
    _agent = agent


def _get_react_meta(tool_name: str) -> tuple[str, str | None]:
    """Get emoji and card_type for a ReAct tool name (may have _tool suffix)."""
    reg = get_tool_registry()
    base_name = tool_name.replace("_tool", "")
    meta = reg.get(base_name) or reg.get(tool_name)
    if meta:
        return meta.emoji, meta.card_type
    return "🔧", None


async def run_agent_react(
    message: str,
    district_code: str,
    district_name: str,
    data_quarter: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Legacy ReAct agent — preserved for agent_mode='react'."""
    thinking_emitted = False

    try:
        agent = get_agent()
        system_msg = get_system_prompt(district_name, district_code, data_quarter)
        input_state = {
            "messages": [
                SystemMessage(content=system_msg),
                HumanMessage(content=message),
            ],
        }
        config = {"recursion_limit": MAX_ITERATIONS * 2 + 1}

        async for event in agent.astream_events(input_state, version="v2", config=config):
            kind = event["event"]

            if kind == "on_chat_model_start":
                if not thinking_emitted:
                    yield {"type": "thinking", "step": "분석 중...", "icon": "🧠"}
                    thinking_emitted = True

            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                emoji, _ = _get_react_meta(tool_name)
                yield {
                    "type": "tool",
                    "name": tool_name,
                    "input": tool_input,
                    "icon": emoji,
                }
                thinking_emitted = False

            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                emoji, card_type = _get_react_meta(tool_name)
                yield {"type": "tool_end", "name": tool_name, "icon": emoji}
                if card_type:
                    raw = event.get("data", {}).get("output", "")
                    if hasattr(raw, "content"):
                        raw = raw.content
                    try:
                        card_data = json.loads(raw) if isinstance(raw, str) else raw
                    except (json.JSONDecodeError, TypeError):
                        card_data = {}
                    if card_data:
                        base_name = tool_name.replace("_tool", "")
                        card_data["dataSources"] = get_sources_for_tool(base_name)
                        yield {"type": "card", "card_type": card_type, "data": card_data}

            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk is not None:
                    content = chunk.content
                    if isinstance(content, str) and content:
                        yield {"type": "text", "content": content}
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = block.get("text", "")
                                if text:
                                    yield {"type": "text", "content": text}
                            elif isinstance(block, str) and block:
                                yield {"type": "text", "content": block}

    except Exception:
        logger.exception("Agent execution failed")
        yield {
            "type": "text",
            "content": "죄송합니다. 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        }

    dn = district_name if district_name and district_name != "미선택" else "여기"
    yield {
        "type": "suggestion",
        "questions": [
            f"{dn}에서 뭐하면 좋을까?",
            "이 자리 위험하지 않아?",
            "카페 하면 어때?",
            "유동인구 자세히 알려줘",
        ],
    }
    yield {"type": "done"}


# ===================================================================
# PAE agent (Planner-Actor-Evaluator)
# ===================================================================


def _build_pae_graph(event_queue: asyncio.Queue):
    """Build a fresh PAE StateGraph with closures over event_queue."""
    from langgraph.graph import END, StateGraph

    from server.agent.nodes.actor import actor_node
    from server.agent.nodes.evaluator import evaluator_node
    from server.agent.nodes.planner import planner_node
    from server.agent.nodes.respond import respond_node
    from server.agent.state import AgentState

    async def _planner(state: AgentState) -> dict:
        return await planner_node(state)

    async def _greeting(state: AgentState) -> dict:
        """Emit greeting response directly — no LLM call needed."""
        await event_queue.put({
            "type": "text",
            "content": "안녕하세요! 서울 상권 분석 AI 마켓스코프입니다.\n"
                       "지도에서 상권을 선택하시거나, 분석할 상권명을 알려주세요!",
        })
        await event_queue.put({
            "type": "suggestion",
            "questions": ["강남역 상권 분석해줘", "홍대 어때?", "업종 추천해줘", "상권 비교하고 싶어"],
        })
        return {"final_response": "안녕하세요! 서울 상권 분석 AI 마켓스코프입니다."}

    async def _actor(state: AgentState) -> dict:
        return await actor_node(state, event_queue)

    async def _evaluator(state: AgentState) -> dict:
        return await evaluator_node(state)

    async def _respond(state: AgentState) -> dict:
        return await respond_node(state, event_queue)

    def route_after_planner(state) -> str:
        if state.get("response_mode") == "greeting_direct":
            return "greeting"
        if state.get("response_mode") == "direct" or not state.get("plan"):
            return "respond"
        return "actor"

    def route_after_evaluator(state) -> str:
        evaluation = state.get("evaluation")
        if not evaluation or evaluation["sufficient"]:
            return "respond"
        if (state.get("execution_round") or 0) >= settings.agent_max_rounds:
            return "respond"
        return "planner"

    graph = StateGraph(AgentState)
    graph.add_node("planner", _planner)
    graph.add_node("greeting", _greeting)
    graph.add_node("actor", _actor)
    graph.add_node("evaluator", _evaluator)
    graph.add_node("respond", _respond)

    graph.set_entry_point("planner")
    graph.add_conditional_edges(
        "planner", route_after_planner,
        {"actor": "actor", "respond": "respond", "greeting": "greeting"},
    )
    graph.add_edge("greeting", END)
    graph.add_edge("actor", "evaluator")
    graph.add_conditional_edges("evaluator", route_after_evaluator, {"respond": "respond", "planner": "planner"})
    graph.add_edge("respond", END)

    return graph.compile()


async def run_agent_pae(
    message: str,
    district_code: str,
    district_name: str,
    data_quarter: str,
    conversation_history: list[dict] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """PAE agent — asyncio.Queue based real-time SSE streaming."""
    from server.agent.state import AgentState

    # Bounded queue so a slow/disconnected SSE consumer naturally blocks the
    # LLM/tool producers (backpressure) instead of growing memory unbounded.
    event_queue: asyncio.Queue[dict | None] = asyncio.Queue(
        maxsize=settings.sse_queue_maxsize
    )

    initial_state: AgentState = {  # type: ignore[typeddict-item]
        "messages": [HumanMessage(content=message)],
        "conversation_history": conversation_history or [],
        "district_code": district_code,
        "district_name": district_name,
        "data_quarter": data_quarter,
        "session_id": "",
        "user_intent": "",
        "intent_confidence": 0.0,
        "referenced_districts": [],
        "referenced_category": None,
        "plan": [],
        "plan_reasoning": "",
        "tool_results": {},
        "tool_errors": {},
        "execution_round": 0,
        "evaluation": None,
        "response_mode": "tool_assisted",
        "card_emissions": [],
        "iteration_count": 0,
    }

    compiled = _build_pae_graph(event_queue)

    # Store suggestions from evaluator for the final yield
    final_suggestions: list[str] = []

    async def _run_graph():
        nonlocal final_suggestions
        emitted_card_count = 0  # track to avoid re-emitting accumulated cards

        try:
            await event_queue.put({"type": "thinking", "step": "질문 분석 중...", "icon": "🧠"})

            async for update in compiled.astream(initial_state, stream_mode="updates"):
                for node_name, state_update in update.items():
                    if node_name == "planner":
                        plan = state_update.get("plan", [])
                        intent = state_update.get("user_intent", "")
                        if plan:
                            steps = [s["reason"] for s in plan]
                            await event_queue.put({
                                "type": "plan",
                                "intent": intent,
                                "steps": steps,
                            })

                    elif node_name == "actor":
                        # Only emit NEW cards (actor accumulates across rounds)
                        all_cards = state_update.get("card_emissions", [])
                        new_cards = all_cards[emitted_card_count:]
                        emitted_card_count = len(all_cards)
                        for card in new_cards:
                            await event_queue.put({
                                "type": "card",
                                "card_type": card["card_type"],
                                "data": card["data"],
                            })

                    elif node_name == "evaluator":
                        ev = state_update.get("evaluation") or {}
                        if not ev.get("sufficient", True):
                            await event_queue.put({
                                "type": "thinking",
                                "step": "추가 데이터 수집 중...",
                                "icon": "🔍",
                            })
                        # Capture suggestions
                        sug = ev.get("proactive_suggestions", [])
                        if sug:
                            final_suggestions[:] = sug

                    # respond node streams text tokens directly via event_queue

        except Exception:
            logger.exception("PAE agent execution failed")
            await event_queue.put({
                "type": "text",
                "content": "죄송합니다. 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            })
        finally:
            await event_queue.put(None)  # sentinel

    task = asyncio.create_task(_run_graph())

    try:
        while True:
            event = await event_queue.get()
            if event is None:
                break
            yield event
    finally:
        if not task.done():
            task.cancel()

    # Suggestion + done
    dn = district_name if district_name and district_name != "미선택" else "여기"
    suggestions = final_suggestions or [
        f"{dn}에서 뭐하면 좋을까?",
        "이 자리 위험하지 않아?",
        "카페 하면 어때?",
        "유동인구 자세히 알려줘",
    ]
    yield {"type": "suggestion", "questions": suggestions}
    yield {"type": "done"}


# ===================================================================
# Unified entry point
# ===================================================================


async def run_agent(
    message: str,
    district_code: str,
    district_name: str,
    data_quarter: str,
    conversation_history: list[dict] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Unified agent entry — dispatches to react or pae based on config."""
    if settings.agent_mode == "pae":
        async for event in run_agent_pae(
            message, district_code, district_name, data_quarter, conversation_history
        ):
            yield event
    else:
        async for event in run_agent_react(
            message, district_code, district_name, data_quarter
        ):
            yield event
