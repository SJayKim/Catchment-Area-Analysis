"""Edge 함수 단위 테스트."""

from langgraph.graph import END
from langgraph.types import Send

from marketscope_agent.graph.edges import (
    route_after_debate_check,
    should_continue_after_commander,
    should_run_group2,
    should_run_group3,
    should_skip_reports,
)


class TestRouteAfterDebateCheck:
    def test_trigger_routes_to_debate(self):
        state = {"debate_decision": "trigger"}
        assert route_after_debate_check(state) == "debate"

    def test_skip_routes_to_judgment(self):
        state = {"debate_decision": "skip"}
        assert route_after_debate_check(state) == "commander_judgment"

    def test_missing_field_defaults_to_skip(self):
        state = {}
        assert route_after_debate_check(state) == "commander_judgment"


class TestShouldContinueAfterCommander:
    def test_no_plan_returns_end(self):
        state = {}
        assert should_continue_after_commander(state) == END

    def test_clarification_needed_returns_end(self):
        state = {"commander_plan": {"clarification_needed": True}}
        assert should_continue_after_commander(state) == END

    def test_valid_plan_returns_group1_sends(self):
        state = {"commander_plan": {"analysis_mode": "basic"}}
        result = should_continue_after_commander(state)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == Send("population", state)
        assert result[1] == Send("competition", state)


class TestShouldRunGroup2:
    def test_quick_mode_skips_to_judgment(self):
        state = {"commander_plan": {"analysis_mode": "quick"}}
        assert should_run_group2(state) == "commander_judgment"

    def test_basic_mode_runs_group2_sends(self):
        state = {"commander_plan": {"analysis_mode": "basic"}}
        result = should_run_group2(state)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == Send("revenue", state)
        assert result[1] == Send("location", state)

    def test_deep_mode_runs_group2_sends(self):
        state = {"commander_plan": {"analysis_mode": "deep"}}
        result = should_run_group2(state)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_missing_plan_defaults_to_basic(self):
        state = {}
        result = should_run_group2(state)
        assert isinstance(result, list)
        assert len(result) == 2


class TestShouldRunGroup3:
    def test_quick_mode_skips_to_financial(self):
        state = {"commander_plan": {"analysis_mode": "quick"}}
        assert should_run_group3(state) == "financial"

    def test_basic_mode_runs_group3_sends(self):
        state = {"commander_plan": {"analysis_mode": "basic"}}
        result = should_run_group3(state)
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == Send("trend", state)
        assert result[1] == Send("real_estate", state)
        assert result[2] == Send("regulatory", state)


class TestShouldSkipReports:
    def test_critical_failure_skips_to_assembly(self):
        state = {"has_critical_failure": True}
        assert should_skip_reports(state) == "report_assembly"

    def test_normal_runs_report_generation(self):
        state = {"has_critical_failure": False}
        assert should_skip_reports(state) == "report_generation"

    def test_missing_flag_runs_report_generation(self):
        state = {}
        assert should_skip_reports(state) == "report_generation"
