"""MarketScope Pipeline — 데이터 수집 스케줄러 독립 실행.

실행: python -m marketscope_pipeline
동작:
1. DB 연결 확인
2. APScheduler 8개 수집 작업 등록
3. 스케줄러 시작 (무한 대기)
4. SIGTERM/SIGINT 시 graceful shutdown
"""

from __future__ import annotations

import asyncio
import logging
import signal

from marketscope_common.config import get_settings
from marketscope_common.logging import setup_logging

logger = logging.getLogger("pipeline.main")


async def main() -> None:
    """Pipeline 스케줄러 메인 루프."""
    settings = get_settings()
    setup_logging(settings.app_log_level.value, env=settings.app_env.value)

    logger.info("MarketScope Pipeline 초기화 중...")

    # 스케줄러 등록 및 시작
    from marketscope_pipeline.scheduler.jobs import register_all_jobs
    scheduler = register_all_jobs()
    scheduler.start()
    logger.info("Pipeline 스케줄러 시작 완료 (%d개 작업)", len(scheduler.get_jobs()))

    # graceful shutdown 이벤트
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _shutdown():
        logger.info("Pipeline 종료 시그널 수신")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown)

    # 종료 시그널까지 대기
    try:
        await stop_event.wait()
    finally:
        scheduler.shutdown(wait=False)
        logger.info("Pipeline 스케줄러 종료 완료")
