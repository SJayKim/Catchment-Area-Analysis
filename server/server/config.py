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
    llm_provider: str = "anthropic"  # "anthropic" or "gemini"
    anthropic_api_key: str = ""
    google_api_key: str = ""

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
    cors_origins: list[str] = ["http://localhost:3000"]

    # Agent architecture
    agent_mode: str = "react"  # "react" (legacy) | "pae" (Planner-Actor-Evaluator)
    agent_max_rounds: int = 3  # max Planner→Actor→Evaluator loops

    # Conversation history
    max_history_turns: int = 10
    history_content_limit: int = 300  # truncate assistant responses in history

    # Evaluator
    evaluator_skip_simple: bool = True  # skip LLM eval for simple intents

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
