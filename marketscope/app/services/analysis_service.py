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

        # 토큰 사용량 합산
        token_summary = self._aggregate_token_usage(final_state, app, config)

        # 최종 결과 추출
        result: dict[str, Any]
        if final_state and "report_assembly" in final_state:
            result = final_state["report_assembly"].get("final_report", {})
        else:
            logger.warning("분석 완료 - 최종 리포트 없음")
            result = {"error": "분석 결과가 생성되지 않았습니다"}

        # 결과에 토큰 사용 정보 첨부
        result["token_usage"] = token_summary
        return result

    @staticmethod
    def _aggregate_token_usage(
        final_event: dict[str, Any] | None,
        app: Any,
        config: dict,
    ) -> dict[str, Any]:
        """LangGraph state에서 토큰 사용 로그를 합산한다."""
        try:
            # LangGraph state에서 전체 state 가져오기
            state = app.get_state(config)
            token_log: list[dict] = state.values.get("token_usage_log", []) if state else []
        except Exception:
            token_log = []

        if not token_log:
            return {
                "total_tokens": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_cost_usd": 0.0,
                "per_agent": [],
            }

        total_pt = sum(e.get("prompt_tokens", 0) for e in token_log)
        total_ct = sum(e.get("completion_tokens", 0) for e in token_log)
        total_cost = sum(e.get("cost_usd", 0.0) for e in token_log)

        return {
            "total_tokens": total_pt + total_ct,
            "total_prompt_tokens": total_pt,
            "total_completion_tokens": total_ct,
            "total_cost_usd": round(total_cost, 6),
            "per_agent": token_log,
        }
