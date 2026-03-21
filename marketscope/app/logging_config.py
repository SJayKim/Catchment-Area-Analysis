"""구조화 로깅 설정 — structlog 기반."""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(level: str = "DEBUG", env: str = "development") -> None:
    """structlog 파이프라인을 설정한다.

    - 개발 환경: ConsoleRenderer (컬러 출력)
    - 운영 환경: JSONRenderer (Loki/ELK 호환)
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if env == "production":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer(
            ensure_ascii=False,
        )
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.DEBUG))

    # 기존 핸들러 교체
    if root.handlers:
        root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # 외부 라이브러리 로그 레벨 조정
    for noisy in ("httpx", "httpcore", "asyncio", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """모듈용 structlog 로거를 반환한다."""
    return structlog.get_logger(f"marketscope.{name}")


def get_agent_logger(agent_name: str) -> structlog.stdlib.BoundLogger:
    """에이전트용 structlog 로거를 반환한다. agent_name이 자동 바인딩된다."""
    return structlog.get_logger(f"marketscope.agents.{agent_name}").bind(
        agent_name=agent_name,
    )
