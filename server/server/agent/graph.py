"""LangGraph ReAct agent for MarketScope AI."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from server.agent.prompts.system import get_system_prompt
from server.config import settings

# LLM provider — swap between Gemini (test) and Anthropic (production)
LLM_PROVIDER = settings.llm_provider  # "gemini" or "anthropic"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LangChain tool wrappers
# ---------------------------------------------------------------------------


@tool
async def get_floating_population_tool(
    district_code: str, quarter: str | None = None
) -> str:
    """상권의 유동인구 데이터를 조회합니다.

    시간대별, 성별, 연령별 유동인구 분포를 반환합니다.
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
    매출 추이가 성장/안정/감소 중인지도 판단합니다.

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

    상주인구/직장인구 총수, 연령별/성별 분포를 반환합니다.

    Args:
        district_code: 상권코드
    """
    from server.agent.tools.population_info import get_population_info

    result = await get_population_info(district_code)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
async def get_district_summary_tool(district_code: str) -> str:
    """상권의 종합 요약 정보를 조회합니다.

    유동인구, 매출, 점포 현황을 집계하여 한눈에 볼 수 있는 요약 데이터를 반환합니다.
    사용자가 상권을 선택하거나 "상권 분석해줘", "요약해줘" 등을 요청할 때 사용합니다.

    Args:
        district_code: 상권코드
    """
    from server.agent.tools.district_summary import get_district_summary

    result = await get_district_summary(district_code)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
async def compare_districts_tool(district_codes: list[str]) -> str:
    """2~3개 상권의 주요 지표를 비교합니다.

    유동인구, 점포 수, 월매출, 폐업률, 주 연령대, 상권 상태를 비교합니다.
    사용자가 "A랑 B 비교해줘" 같은 요청을 할 때 사용합니다.

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

    점포당 매출, 유동인구 매칭률, 폐업률, 경쟁 밀집도를 종합하여
    추천 점수를 산출합니다. 예산이나 업종 선호 필터도 지원합니다.

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

    업종별 평균 생존 기간, 폐업률 높은 위험 업종, 상권 안정성 점수(0~100),
    분기별 개폐업 추이를 반환합니다.

    Args:
        district_code: 상권코드
    """
    from server.agent.tools.store_history import get_store_history

    result = await get_store_history(district_code)
    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Agent creation
# ---------------------------------------------------------------------------

TOOLS = [
    get_district_summary_tool,
    get_floating_population_tool,
    get_estimated_sales_tool,
    get_store_info_tool,
    get_population_info_tool,
    compare_districts_tool,
    recommend_business_tool,
    get_store_history_tool,
]

MAX_ITERATIONS = 5


def _create_llm():
    """Create the LLM instance based on configured provider."""
    if LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
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


def create_agent():
    """Build and return the compiled LangGraph ReAct agent."""
    llm = _create_llm()

    agent = create_react_agent(
        model=llm,
        tools=TOOLS,
    )

    return agent


# ---------------------------------------------------------------------------
# SSE event streaming
# ---------------------------------------------------------------------------


async def run_agent(
    message: str,
    district_code: str,
    district_name: str,
    data_quarter: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run the agent and yield SSE-formatted event dicts.

    Event types:
        thinking  - agent is reasoning
        tool      - tool invocation started
        text      - streamed text token(s)
        suggestion - recommended follow-up questions
        done      - stream finished
    """
    thinking_emitted = False

    try:
        agent = create_agent()

        system_msg = get_system_prompt(district_name, district_code, data_quarter)

        input_state = {
            "messages": [
                SystemMessage(content=system_msg),
                HumanMessage(content=message),
            ],
        }

        config = {"recursion_limit": MAX_ITERATIONS * 2 + 1}

        # Map tool names → card types for structured card events
        _TOOL_CARD_MAP = {
            "get_district_summary_tool": "summary",
            "compare_districts_tool": "compare",
            "recommend_business_tool": "recommend",
            "get_store_history_tool": "risk",
        }

        async for event in agent.astream_events(input_state, version="v2", config=config):
            kind = event["event"]

            if kind == "on_chat_model_start":
                if not thinking_emitted:
                    yield {"type": "thinking", "step": "분석 중..."}
                    thinking_emitted = True

            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                yield {
                    "type": "tool",
                    "name": tool_name,
                    "input": tool_input,
                }
                # Reset so we emit thinking again for the next LLM call
                thinking_emitted = False

            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                card_type = _TOOL_CARD_MAP.get(tool_name)
                if card_type:
                    raw = event.get("data", {}).get("output", "")
                    # output is a ToolMessage; get its content
                    if hasattr(raw, "content"):
                        raw = raw.content
                    try:
                        card_data = json.loads(raw) if isinstance(raw, str) else raw
                    except (json.JSONDecodeError, TypeError):
                        card_data = {}
                    if card_data:
                        yield {
                            "type": "card",
                            "card_type": card_type,
                            "data": card_data,
                        }

            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk is not None:
                    content = chunk.content
                    # content can be a string or a list of content blocks
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

    # Always emit suggestion and done
    yield {
        "type": "suggestion",
        "questions": [
            "여기서 뭐하면 좋을까?",
            "이 자리 위험하지 않아?",
            "카페 하면 어때?",
            "유동인구 자세히 알려줘",
        ],
    }
    yield {"type": "done"}
