"""LangGraph 워크플로우 통합 테스트."""

import pytest

from marketscope_agent.graph.workflow import build_workflow
from marketscope_common.models.state import create_initial_state


class TestWorkflowStructure:
    def test_node_count(self):
        graph = build_workflow()
        nodes = list(graph.nodes.keys())
        assert len(nodes) == 20, f"Expected 20 nodes, got {len(nodes)}: {nodes}"

    def test_expected_nodes_present(self):
        graph = build_workflow()
        nodes = set(graph.nodes.keys())
        expected = {
            "user_input", "commander_plan",
            "population", "competition", "group1_complete",
            "revenue", "location", "group2_complete",
            "trend", "real_estate", "regulatory", "group3_complete",
            "financial", "risk",
            "debate_check", "debate",
            "commander_judgment",
            "narrative", "visualization", "report_assembly",
        }
        missing = expected - nodes
        extra = nodes - expected
        assert not missing, f"Missing nodes: {missing}"
        assert not extra, f"Unexpected nodes: {extra}"

    def test_build_is_idempotent(self):
        g1 = build_workflow()
        g2 = build_workflow()
        assert set(g1.nodes.keys()) == set(g2.nodes.keys())


class TestStateInitialization:
    def test_create_initial_state(self):
        state = create_initial_state("sess-1", "강남역 카페")
        assert state["session_id"] == "sess-1"
        assert state["user_input"] == "강남역 카페"
        assert state["has_critical_failure"] is False
        assert state["current_phase"] == 0
        assert state["progress_pct"] == 0.0
        assert state["debate_decision"] is None
        assert state["debate_trigger_reasons"] == []

    def test_all_result_fields_are_none(self):
        state = create_initial_state("sess-2", "test")
        result_fields = [
            "commander_plan", "population_result", "competition_result",
            "revenue_result", "location_result",
        ]
        for field in result_fields:
            assert state.get(field) is None, f"{field} should be None"

    def test_list_fields_are_empty(self):
        state = create_initial_state("sess-3", "test")
        list_fields = ["errors", "node_executions", "debate_trigger_reasons"]
        for field in list_fields:
            val = state.get(field)
            assert isinstance(val, list) and len(val) == 0, f"{field} should be empty list"
