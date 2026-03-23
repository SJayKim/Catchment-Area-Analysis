"""LangGraph 그래프 노드 함수 - 에이전트 팩토리 패턴."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from marketscope_common.config import Settings, get_settings
from marketscope_common.logging import get_logger
from marketscope_common.monitoring.dag_tracer import trace_node
from marketscope_common.monitoring.mcp_monitor import MCPMonitoringMiddleware
from marketscope_agent.tools.mcp_client import MCPClientRouter

logger = get_logger("graph.nodes")


# ── 싱글톤 인프라 ──

@lru_cache()
def _get_settings() -> Settings:
    return get_settings()


_mcp_router: MCPClientRouter | None = None
_mcp_monitor: MCPMonitoringMiddleware | None = None


def _get_mcp_router() -> MCPClientRouter:
    """MCPClientRouter 싱글톤. 모든 에이전트가 공유한다."""
    global _mcp_router
    if _mcp_router is None:
        _mcp_router = MCPClientRouter(_get_settings())
    return _mcp_router


def _get_mcp_monitor() -> MCPMonitoringMiddleware:
    """MCP 모니터링 미들웨어 싱글톤."""
    global _mcp_monitor
    if _mcp_monitor is None:
        _mcp_monitor = MCPMonitoringMiddleware(_get_mcp_router())
    return _mcp_monitor


async def shutdown_mcp_router() -> None:
    """MCPClientRouter 종료. lifespan에서 호출."""
    global _mcp_router, _mcp_monitor
    if _mcp_monitor is not None:
        await _mcp_monitor.close()
        _mcp_monitor = None
    if _mcp_router is not None:
        await _mcp_router.close()
        _mcp_router = None


# ── 에이전트 팩토리 ──

def _create_agent(agent_cls: type, **extra_kwargs: Any) -> Any:
    """에이전트 인스턴스를 생성한다. settings + mcp_client(모니터링 미들웨어)를 자동 주입."""
    return agent_cls(
        settings=_get_settings(),
        mcp_client=_get_mcp_monitor(),
        **extra_kwargs,
    )


# ── Entry 노드 ──

@trace_node
async def user_input_node(state: dict[str, Any]) -> dict[str, Any]:
    """사용자 입력 파싱 및 기본 검증.

    스펙 01_orchestration_langgraph.md 정의:
    - 빈 입력 → has_critical_failure=True
    - 정상 → current_phase=0, progress_pct=2.0
    """
    user_input = state.get("user_input", "")

    if not user_input or not user_input.strip():
        logger.warning("user_input.empty", session_id=state.get("session_id"))
        return {
            "has_critical_failure": True,
            "errors": [{"node_id": "user_input", "error": "빈 입력"}],
            "node_executions": [{
                "node_id": "user_input",
                "status": "failed",
                "error_message": "빈 입력",
                "retry_count": 0,
            }],
        }

    logger.info("user_input.parsed", session_id=state.get("session_id"), input_length=len(user_input))
    return {
        "current_phase": 0,
        "progress_pct": 2.0,
        "node_executions": [{
            "node_id": "user_input",
            "status": "completed",
            "error_message": None,
            "retry_count": 0,
        }],
    }


# ── 노드 함수 ──

@trace_node
async def commander_plan_node(state: dict[str, Any]) -> dict[str, Any]:
    """Commander Agent: 분석 계획 수립."""
    from marketscope_agent.agents.commander import CommanderAgent
    agent = _create_agent(CommanderAgent)
    return await agent.run_planning(state)


@trace_node
async def population_node(state: dict[str, Any]) -> dict[str, Any]:
    """인구분석 에이전트 노드."""
    from marketscope_agent.agents.population import PopulationAgent
    agent = _create_agent(PopulationAgent)
    return await agent.run(state)


@trace_node
async def competition_node(state: dict[str, Any]) -> dict[str, Any]:
    """경쟁분석 에이전트 노드."""
    from marketscope_agent.agents.competition import CompetitionAgent
    agent = _create_agent(CompetitionAgent)
    return await agent.run(state)


@trace_node
async def revenue_node(state: dict[str, Any]) -> dict[str, Any]:
    """매출분석 에이전트 노드."""
    from marketscope_agent.agents.revenue import RevenueAgent
    agent = _create_agent(RevenueAgent)
    return await agent.run(state)


@trace_node
async def location_node(state: dict[str, Any]) -> dict[str, Any]:
    """입지분석 에이전트 노드."""
    from marketscope_agent.agents.location import LocationAgent
    agent = _create_agent(LocationAgent)
    return await agent.run(state)


@trace_node
async def trend_node(state: dict[str, Any]) -> dict[str, Any]:
    """트렌드 분석 에이전트 노드."""
    from marketscope_agent.agents.trend import TrendAgent
    agent = _create_agent(TrendAgent)
    return await agent.run(state)


@trace_node
async def real_estate_node(state: dict[str, Any]) -> dict[str, Any]:
    """부동산 분석 에이전트 노드."""
    from marketscope_agent.agents.real_estate import RealEstateAgent
    agent = _create_agent(RealEstateAgent)
    return await agent.run(state)


@trace_node
async def regulatory_node(state: dict[str, Any]) -> dict[str, Any]:
    """규제/인허가 분석 에이전트 노드."""
    from marketscope_agent.agents.regulatory import RegulatoryAgent
    agent = _create_agent(RegulatoryAgent)
    return await agent.run(state)


@trace_node
async def financial_node(state: dict[str, Any]) -> dict[str, Any]:
    """재무 분석 에이전트 노드."""
    from marketscope_agent.agents.financial import FinancialAgent
    agent = _create_agent(FinancialAgent)
    return await agent.run(state)


@trace_node
async def risk_node(state: dict[str, Any]) -> dict[str, Any]:
    """리스크 분석 에이전트 노드."""
    from marketscope_agent.agents.risk import RiskAgent
    agent = _create_agent(RiskAgent)
    return await agent.run(state)


@trace_node
async def debate_check_node(state: dict[str, Any]) -> dict[str, Any]:
    """디베이트 트리거 조건 평가 노드.

    스펙 01_orchestration_langgraph.md Section 4.2 정의:
    4가지 조건을 평가하여 debate_decision (trigger/skip) 결정.
    """
    triggers: list[str] = []
    plan = state.get("commander_plan") or {}

    # 조건 1: force_debate
    if plan.get("force_debate"):
        triggers.append("force_debate")

    # 조건 2: 에이전트 confidence 평균 < 0.6
    result_keys = [
        "population_result", "competition_result", "revenue_result",
        "location_result", "trend_result", "real_estate_result",
        "regulatory_result",
    ]
    scores = []
    for key in result_keys:
        result = state.get(key)
        if isinstance(result, dict) and "confidence_score" in result:
            scores.append(result["confidence_score"])
    avg_confidence = (sum(scores) / len(scores)) if scores else 1.0
    if scores and avg_confidence < 0.6:
        triggers.append(f"low_confidence:{avg_confidence:.3f}")

    # 조건 3: 매출 추정치 분산 > 30%
    revenue = state.get("revenue_result")
    if isinstance(revenue, dict):
        estimated = revenue.get("estimated_monthly_revenue", 0)
        revenue_range = revenue.get("revenue_range", {})
        if isinstance(revenue_range, dict):
            lower = revenue_range.get("min_value", estimated)
            upper = revenue_range.get("max_value", estimated)
        else:
            lower = estimated
            upper = estimated
        if estimated and estimated > 0:
            variance_pct = (upper - lower) / estimated * 100
            if variance_pct > 30:
                triggers.append(f"revenue_variance:{variance_pct:.1f}%")

    # 조건 4: 에이전트 간 결론 충돌 (population vs competition 점수 차이)
    pop = state.get("population_result")
    comp = state.get("competition_result")
    if isinstance(pop, dict) and isinstance(comp, dict):
        pop_score = pop.get("confidence_score", 0.5)
        comp_score = comp.get("confidence_score", 0.5)
        if abs(pop_score - comp_score) > 0.3:
            triggers.append(f"conflicting_conclusions:pop={pop_score:.2f},comp={comp_score:.2f}")

    decision = "trigger" if triggers else "skip"
    logger.info(
        "debate_check.evaluated",
        session_id=state.get("session_id"),
        decision=decision,
        trigger_count=len(triggers),
        triggers=triggers,
        avg_confidence=round(avg_confidence, 3),
    )

    return {
        "debate_decision": decision,
        "debate_trigger_reasons": triggers,
        "node_executions": [{
            "node_id": "debate_check",
            "status": "completed",
            "error_message": None,
            "retry_count": 0,
        }],
    }


@trace_node
async def debate_node(state: dict[str, Any]) -> dict[str, Any]:
    """토론(Debate) 노드 - Advocate/Critic/Judge 오케스트레이션."""
    from marketscope_agent.agents.debate.orchestrator import DebateOrchestrator
    orchestrator = DebateOrchestrator(
        settings=_get_settings(),
        mcp_client=_get_mcp_monitor(),
    )
    return await orchestrator.run(state)


@trace_node
async def commander_judgment_node(state: dict[str, Any]) -> dict[str, Any]:
    """Commander Agent: 최종 종합 판단."""
    from marketscope_agent.agents.commander import CommanderAgent
    agent = _create_agent(CommanderAgent)
    return await agent.run_judgment(state)


@trace_node
async def narrative_node(state: dict[str, Any]) -> dict[str, Any]:
    """내러티브 리포트 생성 노드."""
    from marketscope_agent.agents.narrative import NarrativeAgent
    agent = _create_agent(NarrativeAgent)
    return await agent.run(state)


@trace_node
async def visualization_node(state: dict[str, Any]) -> dict[str, Any]:
    """시각화 설정 생성 노드."""
    from marketscope_agent.agents.visualization import VisualizationAgent
    agent = _create_agent(VisualizationAgent)
    return await agent.run(state)


@trace_node
async def group1_complete_node(state: dict[str, Any]) -> dict[str, Any]:
    """Group 1 병렬 실행 완료 대기 지점 (fan-in barrier)."""
    return {"current_phase": 3, "progress_pct": 25.0}


@trace_node
async def group2_complete_node(state: dict[str, Any]) -> dict[str, Any]:
    """Group 2 병렬 실행 완료 대기 지점 (fan-in barrier)."""
    return {"current_phase": 4, "progress_pct": 45.0}


@trace_node
async def group3_complete_node(state: dict[str, Any]) -> dict[str, Any]:
    """Group 3 병렬 실행 완료 대기 지점 (fan-in barrier)."""
    return {"current_phase": 5, "progress_pct": 60.0}


@trace_node
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
        # Phase 1 에이전트 결과
        "population_result": state.get("population_result"),
        "revenue_result": state.get("revenue_result"),
        "competition_result": state.get("competition_result"),
        "location_result": state.get("location_result"),
        # Phase 2 에이전트 결과
        "trend_result": state.get("trend_result"),
        "financial_result": state.get("financial_result"),
        "risk_result": state.get("risk_result"),
        "real_estate_result": state.get("real_estate_result"),
        "regulatory_result": state.get("regulatory_result"),
        # 토론 결과
        "debate_result": state.get("debate_result"),
    }

    return {
        "final_report": final_report,
        "current_phase": 6,
        "progress_pct": 100.0,
    }
