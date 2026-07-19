"""Langfuse 무음사망 가시화 — trace-missing 카운터 + /metrics + health detail.

Plan: docs/plan/infra/langfuse-ops-hardening-2026-07-06.md (Workstream B).
Memory 근거: feedback_langfuse_sdk_drift_silent — tracing 이 조용히 꺼지면
`agent_done trace_id=-` 로그가 유일한 흔적이었다.
"""

from __future__ import annotations

import pytest

from server.middleware import metrics as m


def test_record_langfuse_trace_missing_increments():
    # 모듈 전역 카운터 — 절대값이 아닌 delta 로 검증
    before = m.get_langfuse_trace_missing_total()
    m.record_langfuse_trace_missing()
    m.record_langfuse_trace_missing()
    assert m.get_langfuse_trace_missing_total() == before + 2


@pytest.mark.asyncio
async def test_metrics_endpoint_serializes_langfuse_counter(app_client) -> None:
    r = await app_client.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "langfuse_trace_missing_total" in body
    assert isinstance(body["langfuse_trace_missing_total"], int)


@pytest.mark.asyncio
async def test_health_detail_exposes_langfuse_block(app_client) -> None:
    r = await app_client.get("/api/health/detail")
    assert r.status_code == 200
    lf = r.json()["langfuse"]
    assert set(lf.keys()) == {"enabled", "tracer_valid", "client_initialized", "sampling_rate"}
    # 테스트 env 는 keys="" → disabled (무음사망과 구분되는 "의도된 off")
    assert lf["enabled"] is False


@pytest.mark.asyncio
async def test_health_detail_exposes_llm_chain(app_client) -> None:
    """배포 직후 컨테이너가 인지한 LLM 체인/순서를 원큐 확인하는 필드."""
    r = await app_client.get("/api/health/detail")
    assert r.status_code == 200
    chain = r.json()["llm_chain"]
    assert isinstance(chain, list)
    assert all(isinstance(x, str) and ":" in x for x in chain)
