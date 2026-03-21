"""분석 오케스트레이션 서비스."""

from __future__ import annotations

from typing import Any, Callable, Optional

from app.config import get_settings
from app.graph.workflow import create_app
from app.logging_config import get_logger
from app.models.state import create_initial_state

logger = get_logger("analysis_service")


class AnalysisService:
    """LangGraph 워크플로우를 실행하는 서비스."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._app = None

    def _get_app(self):
        if self._app is None:
            self._app = create_app()
        return self._app

    async def run_analysis(
        self,
        session_id: str,
        user_input: str,
        on_progress: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> dict[str, Any]:
        """분석 파이프라인을 실행한다."""
        logger.info(f"분석 시작: session={session_id}")

        initial_state = create_initial_state(session_id, user_input)
        app = self._get_app()

        config = {"configurable": {"thread_id": session_id}}

        # LangGraph 실행
        final_state = None
        async for event in app.astream(initial_state, config=config):
            logger.debug(f"Graph event: {list(event.keys())}")

            if on_progress:
                # 진행률 이벤트 발행
                for node_name, node_output in event.items():
                    if isinstance(node_output, dict):
                        progress = node_output.get("progress_pct")
                        if progress is not None:
                            on_progress({
                                "type": "progress",
                                "node": node_name,
                                "progress_pct": progress,
                            })

            final_state = event

        # 최종 결과 추출
        if final_state and "report_assembly" in final_state:
            return final_state["report_assembly"].get("final_report", {})

        logger.warning("분석 완료 - 최종 리포트 없음")
        return {"error": "분석 결과가 생성되지 않았습니다"}
