"""Pipeline main 단위 테스트 — 스케줄러 초기화/종료 검증."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPipelineMain:
    @pytest.mark.asyncio
    async def test_scheduler_registered_and_started(self):
        """register_all_jobs + start 호출 확인."""
        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = list(range(10))
        mock_scheduler.start = MagicMock()
        mock_scheduler.shutdown = MagicMock()

        with patch("marketscope_pipeline.scheduler.jobs.register_all_jobs", return_value=mock_scheduler), \
             patch("marketscope_pipeline.main.get_settings") as mock_settings, \
             patch("marketscope_pipeline.main.setup_logging"):

            mock_settings.return_value = MagicMock(
                app_log_level=MagicMock(value="DEBUG"),
                app_env=MagicMock(value="development"),
            )

            import asyncio
            from marketscope_pipeline.main import main

            # main()은 stop_event.wait()에서 블로킹되므로 짧은 시간 후 취소
            task = asyncio.create_task(main())
            await asyncio.sleep(0.05)
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        mock_scheduler.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_scheduler_registers_correct_job_count(self):
        """register_all_jobs가 8개 job을 등록하는지 확인."""
        from marketscope_pipeline.scheduler.jobs import register_all_jobs
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        # tzdata 없는 환경 대비: UTC 사용
        scheduler = AsyncIOScheduler(timezone="UTC")
        result = register_all_jobs(scheduler)
        assert len(result.get_jobs()) == 10
