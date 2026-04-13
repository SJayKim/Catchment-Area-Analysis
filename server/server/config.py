from pathlib import Path

from pydantic_settings import BaseSettings

# Resolve .env from project root (one level above server/)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # Mock mode — run without DB/Redis
    use_mock: bool = True

    # Database
    database_url: str = (
        "postgresql+asyncpg://marketscope:devpassword@localhost:5432/marketscope"
    )
    database_url_sync: str = (
        "postgresql://marketscope:devpassword@localhost:5432/marketscope"
    )

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

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"

    # ETL
    etl_page_size: int = 1000
    etl_max_retries: int = 3
    etl_request_timeout: int = 30
    etl_max_concurrency: int = 3
    etl_batch_size: int = 1000

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # Agent architecture
    agent_mode: str = "react"  # "react" (legacy) | "pae" (Planner-Actor-Evaluator)
    agent_max_rounds: int = 3  # max Planner→Actor→Evaluator loops

    # SQLAlchemy connection pool
    db_pool_size: int = 10
    db_max_overflow: int = 20

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

    model_config = {
        "env_file": str(_ENV_FILE) if _ENV_FILE.exists() else None,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
