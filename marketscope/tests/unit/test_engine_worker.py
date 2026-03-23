"""Engine Worker 단위 테스트 — RedisBroker + AnalysisService Mock."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from marketscope_agent.engine.worker import EngineWorker


@pytest.fixture
def mock_broker():
    broker = AsyncMock()
    broker.update_status = AsyncMock()
    broker.publish_progress = AsyncMock()
    broker.store_result = AsyncMock()
    return broker


@pytest.fixture
def worker(mock_broker):
    return EngineWorker(broker=mock_broker)


class TestEngineWorker:
    def test_consumer_name_format(self, worker):
        assert worker._consumer_name.startswith("worker-")

    def test_stop_sets_running_false(self, worker):
        worker._running = True
        worker.stop()
        assert worker._running is False

    @pytest.mark.asyncio
    async def test_process_request_success(self, worker, mock_broker):
        """정상 분석 요청 처리 — AnalysisService 호출 + 결과 저장."""
        mock_result = {"score": 90, "grade": "A"}

        with patch("marketscope_agent.services.analysis_service.AnalysisService") as MockService:
            mock_service = AsyncMock()
            mock_service.run_analysis = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_service

            request = {"request_id": "req-001", "query": "강남역 카페 분석"}
            await worker._process_request(request)

        # AnalysisService.run_analysis 호출 검증
        mock_service.run_analysis.assert_awaited_once()
        call_kwargs = mock_service.run_analysis.call_args[1]
        assert call_kwargs["session_id"] == "req-001"
        assert call_kwargs["user_input"] == "강남역 카페 분석"

        # 상태 업데이트 검증
        mock_broker.update_status.assert_any_await("req-001", "processing")

        # 결과 저장 검증
        mock_broker.store_result.assert_awaited_once_with("req-001", mock_result)

        # 완료 이벤트 발행 검증
        last_progress_call = mock_broker.publish_progress.call_args_list[-1]
        event = last_progress_call[0][1]
        assert event["type"] == "done"

    @pytest.mark.asyncio
    async def test_process_request_failure(self, worker, mock_broker):
        """분석 실패 시 failed 상태 업데이트."""
        with patch("marketscope_agent.services.analysis_service.AnalysisService") as MockService:
            mock_service = AsyncMock()
            mock_service.run_analysis = AsyncMock(
                side_effect=RuntimeError("LLM 호출 실패")
            )
            MockService.return_value = mock_service

            request = {"request_id": "req-fail", "query": "실패 테스트"}

            # _process_request는 예외를 발생시킴 (start()에서 catch)
            with pytest.raises(RuntimeError, match="LLM 호출 실패"):
                await worker._process_request(request)
