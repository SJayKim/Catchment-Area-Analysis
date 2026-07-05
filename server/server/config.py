from pathlib import Path

from pydantic_settings import BaseSettings

# env 관례: .env = prod (배포 시 존재), .env.dev = 로컬 개발 오버라이드 (gitignored).
# 로컬 host 에서 uvicorn 직접 실행 시 prod 키 오염 방지 — .env.dev 가 있으면 우선 로드.
# Docker 컨테이너는 compose `environment:` 블록으로 env 를 주입하므로 file 로딩과 무관.
_ROOT = Path(__file__).resolve().parents[2]
_ENV_DEV = _ROOT / ".env.dev"
_ENV_PROD = _ROOT / ".env"
_ENV_FILE = _ENV_DEV if _ENV_DEV.exists() else _ENV_PROD


class Settings(BaseSettings):
    # Mock mode — run without DB/Redis
    use_mock: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://marketscope:devpassword@localhost:5432/marketscope"
    database_url_sync: str = "postgresql://marketscope:devpassword@localhost:5432/marketscope"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API Keys
    seoul_opendata_api_key: str = ""
    data_go_kr_api_key: str = ""

    # LLM
    llm_provider: str = "gemini"  # "anthropic" | "gemini" | "mock"
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Per-role Gemini model (pro for critical, flash for lightweight)
    # NOTE: 3.1-preview models have very high TTFT (~16-45s).
    # 2.5 stable models are dramatically faster (1-8s TTFT).
    gemini_model_pro: str = "gemini-2.5-pro"
    gemini_model_flash: str = "gemini-2.5-flash"

    # Anthropic model — env-overridable so a retired model ID (the 2026-06
    # "dead model" incident) can be hotfixed without a code deploy.
    anthropic_model: str = "claude-sonnet-4-6"

    # Langfuse (LLMOps L1 — Trace 활성화)
    # 빈 값이면 tracing 비활성. 둘 중 하나만 세팅 시 경고 로그 후 비활성.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    # Langfuse Cloud 기본값. Self-host 전환 시 덮어쓰기.
    langfuse_host: str = "https://cloud.langfuse.com"
    # 샘플링 비율 (1.0 = 100%). load-test 시 0.1 로 낮춰 플러싱 지연 회피.
    langfuse_sampling_rate: float = 1.0
    # session_id 해싱용 salt. 배포별로 고유값. 비워두면 인스턴스 기동 시 랜덤 생성.
    langfuse_session_salt: str = ""
    # OTEL span export 시 TLS 검증 비활성화. 사내 MITM/corporate proxy 환경에서 필요.
    # 공식 OTEL HTTP exporter 는 verify disable 을 공식 지원 안 함 → SDK 내부 session monkey-patch.
    # ⚠ 프로덕션 기본 False 유지. 로컬 dev 에서 SSL_CERT_FILE / REQUESTS_CA_BUNDLE 로 해결 불가할 때만 true.
    langfuse_otel_insecure: bool = False

    @property
    def langfuse_enabled(self) -> bool:
        """Tracing 활성화 조건: public + secret key 둘 다 세팅."""
        return bool(self.langfuse_public_key) and bool(self.langfuse_secret_key)

    # ETL
    etl_page_size: int = 1000
    etl_max_retries: int = 3
    etl_request_timeout: int = 30
    etl_max_concurrency: int = 3
    etl_batch_size: int = 1000

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # Agent architecture
    agent_max_rounds: int = 3  # max Planner→Actor→Evaluator loops (PAE legacy)

    # Agent loop version. "v2" = model-driven tool loop + Trust Kernel
    # (server/agent/loop/). "pae" = legacy Planner-Actor-Evaluator graph.
    # Mock provider always falls back to PAE (fake LLM can't tool-call).
    agent_loop_version: str = "v2"
    # Budget governor (replaces the rigid PAE max_rounds for v2).
    agent_loop_max_iterations: int = 6  # model turns before forced finalize
    agent_loop_max_tool_calls: int = 12  # total tool executions per request
    agent_loop_wall_clock: float = 90.0  # seconds before forced finalize
    # Trust Kernel — fuzzy tolerance for binding a response number to a fact.
    trust_numeric_tolerance: float = 0.05

    # SQLAlchemy connection pool
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True  # validate connections before use
    db_pool_recycle: int = 1800  # recycle idle connections after 30min
    db_pool_timeout: int = 30  # wait timeout for pool checkout
    db_statement_timeout_ms: int = 10000  # 10s per SQL statement

    # Conversation history
    max_history_turns: int = 10
    history_content_limit: int = 300  # truncate assistant responses in history

    # Evaluator
    evaluator_skip_simple: bool = True  # skip LLM eval for simple intents

    # LLM call timeouts (seconds)
    # Fast-tier models (planner/evaluator, flash) — classification/judgement
    llm_timeout_fast: float = 15.0
    # Slow-tier models (respond, pro) — final streaming answer
    llm_timeout_slow: float = 60.0

    # SSE event queue backpressure (graph.py)
    sse_queue_maxsize: int = 256

    # Rate limiting
    rate_limit_global: str = "60/minute"
    rate_limit_chat: str = "10/minute"

    # Input validation
    chat_message_max_length: int = 500

    # SSE streaming
    sse_heartbeat_interval: float = 25.0
    sse_connection_max_duration: float = 300.0  # 5 min total

    # Tool execution
    tool_execution_timeout: float = 15.0
    tool_result_max_chars: int = 8000

    # Circuit breaker (LLM)
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 60.0

    # Session
    session_max_count: int = 10000
    session_memory_limit_bytes: int = 524288  # 512KB

    # Logging
    log_format: str = "console"  # "json" for production, "console" for dev

    model_config = {
        "env_file": str(_ENV_FILE) if _ENV_FILE.exists() else None,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
