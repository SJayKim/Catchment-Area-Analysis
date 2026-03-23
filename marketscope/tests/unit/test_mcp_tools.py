"""MCP 서버 도구 단위 테스트."""

import pytest


@pytest.mark.asyncio
class TestFinanceTools:
    async def test_calculate_loan_repayment_basic(self):
        from marketscope_mcp.finance.tools import calculate_loan_repayment

        result = await calculate_loan_repayment(
            {"principal": 100000000, "annual_rate": 5.0, "term_months": 12},
            client=None,
        )
        assert "error" not in result
        assert result["principal"] == 100000000
        assert result["annual_rate"] == 5.0
        assert result["term_months"] == 12
        assert result["monthly_payment"] > 0
        assert result["total_payment"] > result["principal"]
        assert result["total_interest"] > 0
        assert result["schedule_total_months"] == 12

    async def test_calculate_loan_repayment_schedule_sum(self):
        from marketscope_mcp.finance.tools import calculate_loan_repayment

        result = await calculate_loan_repayment(
            {"principal": 50000000, "annual_rate": 4.0, "term_months": 6},
            client=None,
        )
        # 마지막 달의 remaining_balance가 0이어야 함
        schedule = result["schedule"]
        assert schedule[-1]["remaining_balance"] == 0

    async def test_calculate_loan_repayment_invalid_params(self):
        from marketscope_mcp.finance.tools import calculate_loan_repayment

        result = await calculate_loan_repayment(
            {"principal": 0, "annual_rate": 5.0, "term_months": 12},
            client=None,
        )
        assert "error" in result

    async def test_get_minimum_wage_2026(self):
        from marketscope_mcp.finance.tools import get_minimum_wage

        result = await get_minimum_wage({"year": 2026}, client=None)
        assert result["year"] == 2026
        assert result["hourly_wage"] > 0
        assert result["monthly_wage_209h"] > 0
        assert result["weekly_hours"] == 40

    async def test_get_minimum_wage_fallback(self):
        from marketscope_mcp.finance.tools import get_minimum_wage

        # 먼 미래 연도 → 가장 가까운 과거 데이터로 폴백
        result = await get_minimum_wage({"year": 2050}, client=None)
        assert result["hourly_wage"] > 0

    async def test_get_insurance_rates(self):
        from marketscope_mcp.finance.tools import get_insurance_rates

        result = await get_insurance_rates({}, client=None)
        assert "insurance_rates" in result
        assert result["total_employer_rate"] > 0
        assert result["total_employee_rate"] > 0


@pytest.mark.asyncio
class TestDatabaseTools:
    async def test_execute_spatial_query_blocks_delete(self):
        from marketscope_mcp.database.tools import execute_spatial_query

        result = await execute_spatial_query(
            {"query": "DELETE FROM stores WHERE id = 1"}, client=None
        )
        assert "error" in result
        assert "SELECT" in result["error"] or "DELETE" in result["error"]

    async def test_execute_spatial_query_blocks_drop(self):
        from marketscope_mcp.database.tools import execute_spatial_query

        result = await execute_spatial_query(
            {"query": "DROP TABLE stores"}, client=None
        )
        assert "error" in result

    async def test_execute_spatial_query_blocks_insert(self):
        from marketscope_mcp.database.tools import execute_spatial_query

        result = await execute_spatial_query(
            {"query": "INSERT INTO stores VALUES (1, 'test')"}, client=None
        )
        assert "error" in result

    async def test_execute_spatial_query_blocks_update(self):
        from marketscope_mcp.database.tools import execute_spatial_query

        result = await execute_spatial_query(
            {"query": "UPDATE stores SET name='hack'"}, client=None
        )
        assert "error" in result

    async def test_execute_spatial_query_empty(self):
        from marketscope_mcp.database.tools import execute_spatial_query

        result = await execute_spatial_query({"query": ""}, client=None)
        assert "error" in result

    async def test_execute_spatial_query_blocks_truncate(self):
        from marketscope_mcp.database.tools import execute_spatial_query

        result = await execute_spatial_query(
            {"query": "TRUNCATE stores"}, client=None
        )
        assert "error" in result

    async def test_execute_spatial_query_blocks_grant(self):
        from marketscope_mcp.database.tools import execute_spatial_query

        result = await execute_spatial_query(
            {"query": "GRANT ALL ON stores TO public"}, client=None
        )
        assert "error" in result

    async def test_execute_spatial_query_blocks_injection_in_select(self):
        from marketscope_mcp.database.tools import execute_spatial_query

        result = await execute_spatial_query(
            {"query": "SELECT * FROM stores; DROP TABLE stores;--"},
            client=None,
        )
        assert "error" in result
