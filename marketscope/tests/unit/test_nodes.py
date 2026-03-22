"""그래프 노드 단위 테스트."""

import pytest

from app.graph.nodes import debate_check_node, user_input_node


@pytest.mark.asyncio
class TestUserInputNode:
    async def test_valid_input(self, sample_state):
        result = await user_input_node(sample_state)
        assert result["current_phase"] == 0
        assert result["progress_pct"] == 2.0
        assert result["node_executions"][0]["status"] == "completed"

    async def test_empty_input(self):
        state = {"session_id": "test", "user_input": ""}
        result = await user_input_node(state)
        assert result["has_critical_failure"] is True
        assert result["errors"][0]["error"] == "빈 입력"

    async def test_whitespace_only_input(self):
        state = {"session_id": "test", "user_input": "   "}
        result = await user_input_node(state)
        assert result["has_critical_failure"] is True

    async def test_missing_input(self):
        state = {"session_id": "test"}
        result = await user_input_node(state)
        assert result["has_critical_failure"] is True


@pytest.mark.asyncio
class TestDebateCheckNode:
    async def test_force_debate(self, sample_state_with_results):
        sample_state_with_results["commander_plan"]["force_debate"] = True
        result = await debate_check_node(sample_state_with_results)
        assert result["debate_decision"] == "trigger"
        assert "force_debate" in result["debate_trigger_reasons"]

    async def test_low_confidence_triggers(self, sample_state_with_results):
        # 모든 결과의 confidence를 0.4로 설정
        for key in ["population_result", "competition_result", "revenue_result", "location_result"]:
            sample_state_with_results[key]["confidence_score"] = 0.4
        result = await debate_check_node(sample_state_with_results)
        assert result["debate_decision"] == "trigger"
        assert any("low_confidence" in r for r in result["debate_trigger_reasons"])

    async def test_high_revenue_variance_triggers(self, sample_state_with_results):
        sample_state_with_results["revenue_result"] = {
            "confidence_score": 0.8,
            "estimated_monthly_revenue": 10000000,
            "revenue_range": {
                "min_value": 5000000,
                "max_value": 15000000,  # variance = 100%
            },
        }
        result = await debate_check_node(sample_state_with_results)
        assert result["debate_decision"] == "trigger"
        assert any("revenue_variance" in r for r in result["debate_trigger_reasons"])

    async def test_conflicting_conclusions_triggers(self, sample_state_with_results):
        sample_state_with_results["population_result"]["confidence_score"] = 0.9
        sample_state_with_results["competition_result"]["confidence_score"] = 0.3
        result = await debate_check_node(sample_state_with_results)
        assert result["debate_decision"] == "trigger"
        assert any("conflicting_conclusions" in r for r in result["debate_trigger_reasons"])

    async def test_normal_results_skip(self, sample_state_with_results):
        # 기본 fixture는 정상 범위 confidence, 적절한 revenue 범위
        result = await debate_check_node(sample_state_with_results)
        assert result["debate_decision"] == "skip"
        assert result["debate_trigger_reasons"] == []

    async def test_no_results_skip(self, sample_state):
        result = await debate_check_node(sample_state)
        assert result["debate_decision"] == "skip"

    async def test_multiple_triggers(self, sample_state_with_results):
        sample_state_with_results["commander_plan"]["force_debate"] = True
        for key in ["population_result", "competition_result", "revenue_result", "location_result"]:
            sample_state_with_results[key]["confidence_score"] = 0.3
        result = await debate_check_node(sample_state_with_results)
        assert result["debate_decision"] == "trigger"
        assert len(result["debate_trigger_reasons"]) >= 2
