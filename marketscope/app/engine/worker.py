"""MarketScope Engine Worker — Redis Stream에서 분석 요청을 수신하여 실행.

실행: python -m app.engine
동작:
1. Redis Stream (analysis:requests)에서 블로킹 수신
2. LangGraph DAG 실행 (AnalysisService)
3. 진행률 → Redis Pub/Sub 발행
4. 최종 결과 → Redis Hash 저장
"""

from __future__ import annotations

import asyncio
import logging
import signal
import os
from typing import Any

from app.config import get_settings
from app.engine.redis_broker import RedisBroker
from app.logging_config import setup_logging

logger = logging.getLogger("engine.worker")


class EngineWorker:
    """분석 엔진 워커."""

    def __init__(self, broker: RedisBroker) -> None:
        self._broker = broker
        self._running = False
        self._consumer_name = f"worker-{os.getpid()}"

    async def start(self) -> None:
        """워커 시작 — Redis Stream 구독 및 처리 루프."""
        self._running = True
        logger.info(
            "Engine Worker 시작: consumer=%s",
            self._consumer_name,
        )

        async for request in self._broker.consume_requests(
            consumer_name=self._consumer_name,
        ):
            if not self._running:
                break

            request_id = request.get("request_id", "unknown")
            logger.info("분석 요청 수신: %s", request_id)

            try:
                await self._process_request(request)
            except Exception:
                logger.exception("분석 처리 실패: %s", request_id)
                await self._broker.update_status(request_id, "failed")
                await self._broker.publish_progress(request_id, {
                    "type": "error",
                    "message": "분석 처리 중 오류가 발생했습니다.",
                })

    async def _process_request(self, request: dict[str, Any]) -> None:
        """단일 분석 요청 처리."""
        request_id = request["request_id"]
        query = request.get("query", "")

        await self._broker.update_status(request_id, "processing")
        await self._broker.publish_progress(request_id, {
            "type": "status",
            "status": "processing",
            "message": "분석을 시작합니다...",
        })

        # on_progress 콜백: LangGraph 노드 완료 시마다 호출
        async def on_progress(event: dict[str, Any]) -> None:
            await self._broker.publish_progress(request_id, event)

        # LangGraph 실행
        from app.services.analysis_service import AnalysisService
        service = AnalysisService()
        result = await service.run_analysis(
            session_id=request_id,
            user_input=query,
            on_progress=on_progress,
        )

        # 결과 저장
        await self._broker.store_result(request_id, result)
        await self._broker.publish_progress(request_id, {
            "type": "done",
            "status": "completed",
            "message": "분석이 완료되었습니다.",
        })
        logger.info("분석 완료: %s", request_id)

    def stop(self) -> None:
        """워커 종료 시그널."""
        self._running = False
        logger.info("Engine Worker 종료 요청")


async def main() -> None:
    """Engine Worker 메인 루프."""
    settings = get_settings()
    setup_logging(settings.app_log_level.value, env=settings.app_env.value)

    logger.info("MarketScope Engine Worker 초기화 중...")

    # MCP Router 초기화 (에이전트가 사용)
    from app.graph.nodes import _get_mcp_router
    _get_mcp_router()
    logger.info("MCP Router 초기화 완료")

    # Redis Broker 연결
    broker = RedisBroker(redis_url=settings.redis_url)
    await broker.connect()
    logger.info("Redis Broker 연결 완료")

    # Worker 시작
    worker = EngineWorker(broker)

    # 시그널 핸들러
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.stop)

    try:
        await worker.start()
    finally:
        await broker.close()
        logger.info("Engine Worker 종료 완료")
