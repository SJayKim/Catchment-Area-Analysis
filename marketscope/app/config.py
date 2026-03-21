"""Pydantic Settings 설정 클래스."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Optional

import warnings

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MCPTransport(str, Enum):
    STDIO = "stdio"
    SSE = "sse"


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_")

    model_commander: str = "claude-sonnet-4-6-20250514"
    model_population: str = "gemini/gemini-2.5-flash"
    model_revenue: str = "gemini/gemini-2.5-flash"
    model_competition: str = "gemini/gemini-2.5-flash"
    model_location: str = "gemini/gemini-2.5-flash"
    model_narrative: str = "gemini/gemini-2.5-flash"
    model_visualization: str = "gemini/gemini-2.5-flash"

    temperature_analysis: float = 0.1
    temperature_narrative: float = 0.7
    temperature_default: float = 0.2

    def get_model_for_agent(self, agent_name: str) -> str:
        attr = f"model_{agent_name}"
        if hasattr(self, attr):
            return getattr(self, attr)
        raise ValueError(f"알 수 없는 에이전트: {agent_name}")

    @model_validator(mode="after")
    def validate_model_names_not_empty(self) -> "LLMSettings":
        model_fields = [
            "model_commander",
            "model_population",
            "model_revenue",
            "model_competition",
            "model_location",
            "model_narrative",
            "model_visualization",
        ]
        for field_name in model_fields:
            value = getattr(self, field_name)
            if not value or not value.strip():
                raise ValueError(
                    f"LLM {field_name} must not be an empty string"
                )
        return self

    def get_temperature_for_role(self, role: str) -> float:
        mapping = {
            "analysis": self.temperature_analysis,
            "narrative": self.temperature_narrative,
        }
        return mapping.get(role, self.temperature_default)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "MarketScope AI"
    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT
    app_debug: bool = True
    app_version: str = "1.0.0"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_workers: int = 4
    app_log_level: LogLevel = LogLevel.DEBUG
    app_secret_key: str = "default-dev-secret-key-change-me"
    app_cors_origins: list[str] = ["http://localhost:3000"]

    # LLM API keys
    anthropic_api_key: str = ""
    google_api_key: str = ""
    openai_api_key: Optional[str] = None

    # LiteLLM
    litellm_master_key: Optional[str] = None
    litellm_base_url: str = "http://localhost:4000"
    litellm_use_proxy: bool = False
    litellm_max_retries: int = 3
    litellm_timeout: int = 120
    litellm_fallback_enabled: bool = True

    # LLM
    llm: LLMSettings = LLMSettings()

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "marketscope"
    postgres_user: str = "marketscope_user"
    postgres_password: str = ""
    postgres_pool_size: int = 20
    postgres_max_overflow: int = 10
    postgres_echo_sql: bool = False
    database_url: Optional[str] = None

    @model_validator(mode="after")
    def assemble_database_url(self) -> "Settings":
        if self.database_url is None:
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_url: Optional[str] = None
    redis_cache_ttl: int = 3600

    @model_validator(mode="after")
    def assemble_redis_url(self) -> "Settings":
        if self.redis_url is None:
            auth = f":{self.redis_password}@" if self.redis_password else ""
            self.redis_url = f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return self

    _DEFAULT_SECRET_KEY = "default-dev-secret-key-change-me"

    @field_validator("app_secret_key")
    @classmethod
    def warn_default_secret_key(cls, v: str) -> str:
        if v == cls._DEFAULT_SECRET_KEY:
            warnings.warn(
                "app_secret_key is set to the default value. "
                "Change it before deploying to production.",
                UserWarning,
                stacklevel=2,
            )
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.app_env != AppEnvironment.PRODUCTION:
            return self

        errors: list[str] = []

        if not self.anthropic_api_key:
            errors.append("anthropic_api_key must be non-empty in PRODUCTION")
        if not self.google_api_key:
            errors.append("google_api_key must be non-empty in PRODUCTION")
        if not self.postgres_password:
            errors.append("postgres_password must be non-empty in PRODUCTION")

        secret = self.app_secret_key
        if secret == self._DEFAULT_SECRET_KEY:
            errors.append(
                "app_secret_key must not be the default value in PRODUCTION"
            )
        if len(secret) < 32:
            errors.append(
                "app_secret_key must be at least 32 characters in PRODUCTION"
            )

        if errors:
            raise ValueError(
                "Production configuration errors:\n  - " + "\n  - ".join(errors)
            )
        return self

    # MCP
    mcp_server_url: str = "http://localhost:5100"
    mcp_transport: MCPTransport = MCPTransport.STDIO
    mcp_timeout: int = 30
    mcp_max_concurrent_tools: int = 5

    # Langfuse
    langfuse_enabled: bool = False
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # External Data APIs
    data_api_seoul_open_data_key: Optional[str] = None
    data_api_small_biz_key: Optional[str] = None
    data_api_public_data_key: Optional[str] = None
    data_api_naver_client_id: Optional[str] = None
    data_api_naver_client_secret: Optional[str] = None
    data_api_kakao_rest_key: Optional[str] = None

    # Analysis
    analysis_max_parallel_agents: int = 4
    analysis_agent_timeout: int = 60
    analysis_total_timeout: int = 300
    analysis_confidence_threshold: float = 0.5
    analysis_cache_enabled: bool = True
    analysis_cache_ttl: int = 43200

    # Phase 1 region restrictions
    phase1_seoul_only: bool = True
    phase1_allowed_districts: list[str] = [
        "강남", "홍대", "이태원", "건대", "신촌",
        "종로", "명동", "여의도", "성수", "잠실",
    ]

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnvironment.PRODUCTION


@lru_cache()
def get_settings() -> Settings:
    return Settings()
