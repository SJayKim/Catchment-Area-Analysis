"""LangGraph 그래프 노드 함수 - 에이전트 팩토리 패턴."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from app.config import Settings, get_settings
from app.tools.mcp_client import MCPClient


# ── 싱글톤 인프라 ──

@lru_cache()
def _get_settings() -> Settings:
    return get_settings()


_mcp_client: MCPClient | None = None


def _get_mcp_client() -> MCPClient:
    """MCPClient 싱글톤. 모든 에이전트가 공유한다."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient(_get_settings())
    return _mcp_client


# ── 에이전트 팩토리 ──

def _create_agent(agent_cls: type, **extra_kwargs: Any) -> Any:
    """에이전트 인스턴스를 생성한다. settings + mcp_client를 자동 주입."""
    return agent_cls(
        settings=_get_settings(),
        mcp_client=_get_mcp_client(),
        **extra_kwargs,
    )


# ── 노드 함수 ──

async def commander_plan_node(state: dict[str, Any]) -> dict[str, Any]:
    """Commander Agent: 분석 계획 수립."""
    from app.agents.commander import CommanderAgent
    agent = _create_agent(CommanderAgent)
    return await agent.run_planning(state)


async def population_node(state: dict[str, Any]) -> dict[str, Any]:
    """인구분석 에이전트 노드."""
    from app.agents.population import PopulationAgent
    agent = _create_agent(PopulationAgent)
    return await agent.run(state)


async def competition_node(state: dict[str, Any]) -> dict[str, Any]:
    """경쟁분석 에이전트 노드."""
    from app.agents.competition import CompetitionAgent
    agent = _create_agent(CompetitionAgent)
    return await agent.run(state)


async def revenue_node(state: dict[str, Any]) -> dict[str, Any]:
    """매출분석 에이전트 노드."""
    from app.agents.revenue import RevenueAgent
    agent = _create_agent(RevenueAgent)
    return await agent.run(state)


async def location_node(state: dict[str, Any]) -> dict[str, Any]:
    """입지분석 에이전트 노드."""
    from app.agents.location import LocationAgent
    agent = _create_agent(LocationAgent)
    return await agent.run(state)


async def commander_judgment_node(state: dict[str, Any]) -> dict[str, Any]:
    """Commander Agent: 최종 종합 판단."""
    from app.agents.commander import CommanderAgent
    agent = _create_agent(CommanderAgent)
    return await agent.run_judgment(state)


async def narrative_node(state: dict[str, Any]) -> dict[str, Any]:
    """내러티브 리포트 생성 노드."""
    from app.agents.narrative import NarrativeAgent
    agent = _create_agent(NarrativeAgent)
    return await agent.run(state)


async def visualization_node(state: dict[str, Any]) -> dict[str, Any]:
    """시각화 설정 생성 노드."""
    from app.agents.visualization import VisualizationAgent
    agent = _create_agent(VisualizationAgent)
    return await agent.run(state)


async def group1_complete_node(state: dict[str, Any]) -> dict[str, Any]:
    """Group 1 병렬 실행 완료 대기 지점 (fan-in barrier)."""
    return {"current_phase": 3}


async def group2_complete_node(state: dict[str, Any]) -> dict[str, Any]:
    """Group 2 병렬 실행 완료 대기 지점 (fan-in barrier)."""
    return {"current_phase": 4}


async def report_assembly_node(state: dict[str, Any]) -> dict[str, Any]:
    """최종 리포트 조립 노드. 모든 결과를 dict 기반으로 통합."""
    plan = state.get("commander_plan", {})
    judgment = state.get("final_judgment", {})
    narrative = state.get("narrative_output", {})
    viz = state.get("visualization_output")

    narrative_text = ""
    if isinstance(narrative, dict):
        narrative_text = narrative.get("executive_summary", "")

    final_report = {
        "report_id": str(uuid.uuid4()),
        "request_id": state.get("session_id", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "district_name": plan.get("target_location", ""),
        "industry_category": plan.get("target_industry", ""),
        "overall_score": judgment.get("overall_score", 0),
        "overall_grade": judgment.get("overall_grade", "N/A"),
        "recommendation": judgment.get("recommendation", ""),
        "executive_summary": judgment.get("executive_summary", ""),
        "key_findings": judgment.get("key_findings", []),
        "score_breakdown": judgment.get("score_breakdown", {}),
        "narrative_report": narrative_text,
        "visualization_config": viz,
        # 개별 에이전트 결과 포함
        "population_result": state.get("population_result"),
        "revenue_result": state.get("revenue_result"),
        "competition_result": state.get("competition_result"),
        "location_result": state.get("location_result"),
    }

    return {
        "final_report": final_report,
        "current_phase": 6,
        "progress_pct": 100.0,
    }
