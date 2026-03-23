"""시각화 설정 생성 에이전트."""

from __future__ import annotations

from typing import Any

from marketscope_agent.agents.base import BaseAgent
from pydantic import BaseModel, Field


class VisualizationConfigOutput(BaseModel):
    """시각화 에이전트 출력."""
    chart_configs: list[dict[str, Any]] = Field(default_factory=list)
    map_config: dict[str, Any] = Field(default_factory=dict)
    summary_cards: list[dict[str, Any]] = Field(default_factory=list)


class VisualizationAgent(BaseAgent[VisualizationConfigOutput]):
    """시각화 설정 생성 에이전트 - 차트/지도 설정을 결정."""

    agent_name = "visualization"
    agent_description = "분석 결과를 시각화하기 위한 차트/지도 설정 생성"
    output_model = VisualizationConfigOutput
    llm_role = "analysis"
    max_retries = 1

    def build_system_prompt(self, state: dict[str, Any]) -> str:
        return ""

    def build_user_prompt(self, state: dict[str, Any], data: dict[str, Any]) -> str:
        return ""

    async def execute(self, state: dict[str, Any]) -> VisualizationConfigOutput:
        """LLM 호출 없이 규칙 기반으로 시각화 설정 생성."""
        plan = state.get("commander_plan", {})
        judgment = state.get("final_judgment", {})
        charts = []
        summary_cards = []

        # 종합 점수 카드
        summary_cards.append({
            "type": "score",
            "title": "종합 점수",
            "value": judgment.get("overall_score", 0),
            "grade": judgment.get("overall_grade", "N/A"),
            "recommendation": judgment.get("recommendation", ""),
        })

        # 항목별 점수 레이더 차트
        breakdown = judgment.get("score_breakdown", {})
        if breakdown:
            charts.append({
                "type": "radar",
                "title": "항목별 분석 점수",
                "data": breakdown,
            })

        # 유동인구 시간대별 차트
        pop = state.get("population_result")
        if pop:
            time_data = pop.get("floating_by_time", [])
            if time_data:
                charts.append({
                    "type": "bar",
                    "title": "시간대별 유동인구",
                    "data": time_data,
                    "x_axis": "hour",
                    "y_axis": "value",
                })

        # 매출 추이 차트
        rev = state.get("revenue_result")
        if rev:
            charts.append({
                "type": "gauge",
                "title": "예상 월 매출",
                "value": rev.get("estimated_monthly_revenue", 0),
            })

        # 경쟁 포화 지수 게이지
        comp = state.get("competition_result")
        if comp:
            charts.append({
                "type": "gauge",
                "title": "시장 포화 지수",
                "value": comp.get("saturation_index", 0),
                "max": 2.0,
            })

        # 지도 설정
        map_config = {}
        geo = {}
        if pop:
            geo = pop.get("geocode", {})
        if geo:
            map_config = {
                "center": {"lat": geo.get("lat", 37.5665), "lng": geo.get("lng", 126.978)},
                "zoom": 16,
                "markers": [{"type": "target", "label": plan.get("target_location", "")}],
            }

        return VisualizationConfigOutput(
            chart_configs=charts,
            map_config=map_config,
            summary_cards=summary_cards,
        )

