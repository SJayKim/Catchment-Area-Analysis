"""LangGraph DAG 노드 트레이싱 — 실행 시간·상태 추적."""

from __future__ import annotations

import functools
import time
from typing import Any, Callable

from marketscope_common.logging import get_logger

logger = get_logger("monitoring.dag")


class DAGTracer:
    """워크플로우 실행 추적기.

    파이프라인 전체 및 노드별 실행 시간을 기록한다.
    """

    def __init__(self) -> None:
        self._timings: dict[str, float] = {}
        self._pipeline_start: float | None = None
        self._session_id: str = ""

    def start_pipeline(self, session_id: str) -> None:
        self._pipeline_start = time.monotonic()
        self._session_id = session_id
        self._timings.clear()
        logger.info("pipeline.start", session_id=session_id)

    def record_node(self, node_name: str, duration_ms: float) -> None:
        self._timings[node_name] = duration_ms

    def end_pipeline(self) -> None:
        if self._pipeline_start is not None:
            total_ms = (time.monotonic() - self._pipeline_start) * 1000
            logger.info(
                "pipeline.complete",
                session_id=self._session_id,
                total_ms=round(total_ms, 1),
                node_count=len(self._timings),
                node_timings=self._timings,
            )

            # Prometheus 메트릭
            from marketscope_common.monitoring.metrics import observe_pipeline_duration
            observe_pipeline_duration(total_ms / 1000)

    def get_timings(self) -> dict[str, float]:
        return dict(self._timings)


# 글로벌 트레이서 인스턴스
_dag_tracer = DAGTracer()


def get_dag_tracer() -> DAGTracer:
    return _dag_tracer


def trace_node(func: Callable) -> Callable:
    """노드 함수에 자동 트레이싱을 추가하는 데코레이터."""

    @functools.wraps(func)
    async def wrapper(state: dict[str, Any]) -> dict[str, Any]:
        node_name = func.__name__
        logger.info("node.start", node=node_name)
        start = time.monotonic()

        try:
            result = await func(state)
            duration_ms = (time.monotonic() - start) * 1000

            logger.info(
                "node.complete",
                node=node_name,
                duration_ms=round(duration_ms, 1),
            )

            # 글로벌 트레이서에 기록
            _dag_tracer.record_node(node_name, round(duration_ms, 1))

            # Prometheus 메트릭
            from marketscope_common.monitoring.metrics import observe_node_duration
            observe_node_duration(node_name, duration_ms / 1000)

            return result

        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error(
                "node.error",
                node=node_name,
                error_type=type(e).__name__,
                error=str(e),
                duration_ms=round(duration_ms, 1),
            )
            raise

    return wrapper
