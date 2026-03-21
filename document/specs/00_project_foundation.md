# MarketScope AI - 프로젝트 기반 설계 명세서

> **문서 버전**: 1.1.0
> **최종 수정일**: 2026-03-19
> **상태**: 확정 (Phase 1 MVP 기준)
> **범위**: 프로젝트 전체 공유 기반 구조 (설정, 상태, 모델, 에러, 로깅, 상수)
>
> ⚠️ **Phase 1 MVP 범위 제한**
> - **커버리지**: 서울 주요 상권 10개 우선 지원
> - **활성 에이전트**: 유동인구(population), 매출(revenue), 경쟁(competition), 입지(location) — 4개
> - **비활성(Phase 2)**: 트렌드, 재무, 리스크, 부동산, 규제 에이전트
> - **Debate 시스템**: Phase 2 (비용 최적화 이후 도입)
> - **비용 목표**: 분석 1건당 $2 이하 (모델 다운그레이드 적용)

---

## 목차

1. [프로젝트 설정 (Project Configuration)](#1-프로젝트-설정)
2. [공유 상태 스키마 (Shared State Schema)](#2-공유-상태-스키마)
3. [기본 에이전트 클래스 (Base Agent Class)](#3-기본-에이전트-클래스)
4. [공유 Pydantic 모델 (Shared Pydantic Models)](#4-공유-pydantic-모델)
5. [에러 처리 전략 (Error Handling Strategy)](#5-에러-처리-전략)
6. [로깅 및 모니터링 (Logging & Monitoring)](#6-로깅-및-모니터링)
7. [상수 및 열거형 (Constants & Enums)](#7-상수-및-열거형)

---

## 1. 프로젝트 설정

### 1.1 디렉토리 구조

```
marketscope/
├── pyproject.toml
├── .env
├── .env.example
├── alembic/
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 앱 엔트리포인트
│   ├── config.py                  # Pydantic Settings 정의
│   ├── constants.py               # 상수 및 Enum 정의
│   ├── exceptions.py              # 커스텀 예외 클래스
│   ├── logging_config.py          # 구조화된 로깅 설정
│   ├── models/
│   │   ├── __init__.py
│   │   ├── state.py               # LangGraph 공유 상태 TypedDict
│   │   ├── agent_outputs.py       # 에이전트 출력 Pydantic 모델
│   │   ├── debate.py              # 토론 관련 모델
│   │   ├── report.py              # 최종 리포트 모델
│   │   └── common.py              # 공통 재사용 모델
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                # BaseAgent 추상 클래스
│   │   ├── population.py          # [Phase 1] 유동인구 분석 에이전트
│   │   ├── revenue.py             # [Phase 1] 매출 분석 에이전트
│   │   ├── competition.py         # [Phase 1] 경쟁 분석 에이전트
│   │   ├── location.py            # [Phase 1] 입지 분석 에이전트
│   │   ├── trend.py               # [Phase 2] 트렌드 분석 에이전트
│   │   ├── financial.py           # [Phase 2] 재무 분석 에이전트
│   │   ├── risk.py                # [Phase 2] 리스크 분석 에이전트
│   │   ├── real_estate.py         # [Phase 2] 부동산 분석 에이전트
│   │   └── regulatory.py          # [Phase 2] 규제 분석 에이전트
│   ├── debate/                    # [Phase 2] Debate 시스템 (전체 미구현)
│   │   ├── __init__.py
│   │   ├── commander.py           # [Phase 2] 사령관 에이전트
│   │   ├── advocate.py            # [Phase 2] 옹호자 에이전트
│   │   ├── critic.py              # [Phase 2] 비평가 에이전트
│   │   └── judge.py               # [Phase 2] 최종 판단 에이전트
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── workflow.py            # LangGraph 워크플로우 정의
│   │   ├── nodes.py               # 그래프 노드 함수
│   │   └── edges.py               # 조건부 엣지 로직
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── mcp_client.py          # MCP 도구 호출 클라이언트
│   │   └── registry.py            # 도구 레지스트리
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── reme_client.py         # ReMe 메모리 인터페이스
│   │   └── lightrag_client.py     # LightRAG 검색 인터페이스
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py             # SQLAlchemy 세션 관리
│   │   ├── models.py              # ORM 모델
│   │   └── repositories.py        # 데이터 접근 레이어
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── analysis.py        # 분석 요청 API
│   │   │   ├── reports.py         # 리포트 조회 API
│   │   │   └── health.py          # 헬스체크 API
│   │   └── deps.py                # FastAPI 의존성 주입
│   └── services/
│       ├── __init__.py
│       ├── analysis_service.py    # 분석 오케스트레이션
│       └── report_service.py      # 리포트 생성 서비스
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
└── frontend/                      # Next.js 프론트엔드
    └── ...
```

### 1.2 환경 변수 (.env 구조)

```dotenv
# ============================================================
# MarketScope AI - 환경 설정
# ============================================================

# ---- 앱 기본 설정 ----
APP_NAME=MarketScope AI
APP_ENV=development                          # development | staging | production
APP_DEBUG=true
APP_VERSION=1.0.0
APP_HOST=0.0.0.0
APP_PORT=8000
APP_WORKERS=4
APP_LOG_LEVEL=DEBUG                          # DEBUG | INFO | WARNING | ERROR | CRITICAL
APP_SECRET_KEY=your-secret-key-here          # JWT 등에 사용할 시크릿 키
APP_CORS_ORIGINS=["http://localhost:3000"]   # JSON 배열 형식

# ---- LLM API 키 ----
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
GOOGLE_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx           # 폴백용 (선택)

# ---- LiteLLM 설정 ----
LITELLM_MASTER_KEY=sk-litellm-xxxxxxxx
LITELLM_BASE_URL=http://localhost:4000       # LiteLLM 프록시 URL (셀프호스팅 시)
LITELLM_USE_PROXY=false                      # true면 프록시 경유, false면 직접 호출
LITELLM_MAX_RETRIES=3
LITELLM_TIMEOUT=120                          # 초 단위
LITELLM_FALLBACK_ENABLED=true

# ---- LLM 모델 매핑 (Phase 1 비용 최적화 - 분석 1건 $2 이하 목표) ----
# [Phase 1] Commander: Opus → Sonnet 다운그레이드 (비용 약 80% 절감)
LLM_MODEL_COMMANDER=claude-sonnet-4-6-20250514
# [Phase 2] Debate 시스템 모델 (미구현)
# LLM_MODEL_JUDGE=claude-opus-4-6-20250319
# LLM_MODEL_CRITIC=claude-sonnet-4-6-20250514
# LLM_MODEL_ADVOCATE=gemini/gemini-2.5-flash

# [Phase 1] 활성 에이전트 모델
LLM_MODEL_POPULATION=gemini/gemini-2.5-flash
LLM_MODEL_REVENUE=gemini/gemini-2.5-flash
LLM_MODEL_COMPETITION=gemini/gemini-2.5-flash
LLM_MODEL_LOCATION=gemini/gemini-2.5-flash

# [Phase 2] 비활성 에이전트 모델
# LLM_MODEL_TREND=gemini/gemini-2.5-pro
# LLM_MODEL_FINANCIAL=claude-sonnet-4-6-20250514
# LLM_MODEL_RISK=claude-sonnet-4-6-20250514
# LLM_MODEL_REAL_ESTATE=gemini/gemini-2.5-flash
# LLM_MODEL_REGULATORY=claude-sonnet-4-6-20250514

LLM_MODEL_NARRATIVE=gemini/gemini-2.5-flash
LLM_MODEL_VISUALIZATION=gemini/gemini-2.5-flash

# ---- LLM 온도 설정 ----
LLM_TEMPERATURE_ANALYSIS=0.1                 # 데이터 분석 에이전트
LLM_TEMPERATURE_DEBATE=0.4                   # 토론 에이전트
LLM_TEMPERATURE_NARRATIVE=0.7                # 내러티브 생성
LLM_TEMPERATURE_DEFAULT=0.2

# ---- PostgreSQL / PostGIS ----
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=marketscope
POSTGRES_USER=marketscope_user
POSTGRES_PASSWORD=your-postgres-password
POSTGRES_POOL_SIZE=20
POSTGRES_MAX_OVERFLOW=10
POSTGRES_ECHO_SQL=false                      # SQL 로깅 여부
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}

# ---- Redis ----
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your-redis-password
REDIS_URL=redis://:${REDIS_PASSWORD}@${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}
REDIS_CACHE_TTL=3600                         # 기본 캐시 TTL (초)
REDIS_RATE_LIMIT_ENABLED=true

# ---- ChromaDB ----
CHROMA_HOST=localhost
CHROMA_PORT=8001
CHROMA_COLLECTION_PREFIX=marketscope
CHROMA_PERSIST_DIRECTORY=/data/chromadb
CHROMA_EMBEDDING_MODEL=text-embedding-3-small
CHROMA_EMBEDDING_DIMENSION=1536

# ---- LightRAG ----
LIGHTRAG_WORKING_DIR=/data/lightrag
LIGHTRAG_EMBEDDING_MODEL=text-embedding-3-small
LIGHTRAG_CHUNK_SIZE=1200
LIGHTRAG_CHUNK_OVERLAP=200
LIGHTRAG_TOP_K=10

# ---- ReMe (메모리 시스템) ----
REME_STORAGE_BACKEND=redis                   # redis | postgresql
REME_MAX_SHORT_TERM=50                       # 단기 기억 최대 항목 수
REME_MAX_LONG_TERM=500                       # 장기 기억 최대 항목 수
REME_SIMILARITY_THRESHOLD=0.75               # 유사 기억 검색 임계값
REME_DECAY_RATE=0.05                         # 기억 감쇠 계수

# ---- MCP (Model Context Protocol) ----
MCP_SERVER_URL=http://localhost:5100
MCP_TRANSPORT=stdio                          # stdio | sse
MCP_TIMEOUT=30
MCP_MAX_CONCURRENT_TOOLS=5

# ---- Langfuse (모니터링) ----
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxx
LANGFUSE_HOST=https://cloud.langfuse.com    # 셀프호스팅 시 URL 변경
LANGFUSE_FLUSH_AT=15
LANGFUSE_FLUSH_INTERVAL=10

# ---- 외부 데이터 API ----
DATA_API_SEOUL_OPEN_DATA_KEY=xxxxxxxx        # 서울 열린데이터 API 키
DATA_API_SMALL_BIZ_KEY=xxxxxxxx              # 소상공인시장진흥공단 API 키
DATA_API_PUBLIC_DATA_KEY=xxxxxxxx            # 공공데이터포털 API 키
DATA_API_NAVER_CLIENT_ID=xxxxxxxx            # 네이버 검색 트렌드 API
DATA_API_NAVER_CLIENT_SECRET=xxxxxxxx
DATA_API_KAKAO_REST_KEY=xxxxxxxx             # 카카오 로컬 API

# ---- 분석 실행 설정 (Phase 1) ----
ANALYSIS_MAX_PARALLEL_AGENTS=4               # Phase 1: 4개 에이전트만 실행
ANALYSIS_AGENT_TIMEOUT=60                    # Phase 1: 에이전트당 60초 (비용 통제)
ANALYSIS_TOTAL_TIMEOUT=300                   # Phase 1: 전체 5분 이내 목표
# ANALYSIS_MAX_DEBATE_ROUNDS=3               # [Phase 2] Debate 미구현
ANALYSIS_CONFIDENCE_THRESHOLD=0.5            # Phase 1: 데이터 부족 감안하여 완화
ANALYSIS_CACHE_ENABLED=true
ANALYSIS_CACHE_TTL=43200                     # Phase 1: 캐시 12시간 (공공 API 갱신 주기 감안)

# ---- Phase 1 지역 제한 ----
PHASE1_SEOUL_ONLY=true                       # Phase 1: 서울 상권만 지원
PHASE1_ALLOWED_DISTRICTS=강남,홍대,이태원,건대,신촌,종로,명동,여의도,성수,잠실

# ---- Next.js 프론트엔드 ----
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

### 1.3 Pydantic Settings 설정 클래스

```python
# app/config.py

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(str, Enum):
    """애플리케이션 실행 환경."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """로그 레벨."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MCPTransport(str, Enum):
    """MCP 전송 방식."""
    STDIO = "stdio"
    SSE = "sse"


class ReMeStorageBackend(str, Enum):
    """ReMe 저장소 백엔드."""
    REDIS = "redis"
    POSTGRESQL = "postgresql"


class LLMSettings(BaseSettings):
    """LLM 관련 설정. Phase 1: 비용 최적화 기준 모델 선택."""
    model_config = SettingsConfigDict(env_prefix="LLM_")

    # ── Phase 1 활성 모델 매핑 ──
    # Commander: Opus → Sonnet 다운그레이드 (비용 ~80% 절감, 분석 1건 $2 이하 목표)
    model_commander: str = "claude-sonnet-4-6-20250514"
    # 4개 전문 에이전트: 모두 Gemini Flash (가장 저렴한 고품질 모델)
    model_population: str = "gemini/gemini-2.5-flash"
    model_revenue: str = "gemini/gemini-2.5-flash"
    model_competition: str = "gemini/gemini-2.5-flash"
    model_location: str = "gemini/gemini-2.5-flash"
    # 리포트 에이전트: Flash 사용
    model_narrative: str = "gemini/gemini-2.5-flash"
    model_visualization: str = "gemini/gemini-2.5-flash"

    # ── Phase 2 모델 매핑 (참조용 — 미구현) ──
    # model_judge: str = "claude-opus-4-6-20250319"       # [Phase 2] Debate Judge
    # model_critic: str = "claude-sonnet-4-6-20250514"    # [Phase 2] Debate Critic
    # model_advocate: str = "gemini/gemini-2.5-flash"     # [Phase 2] Debate Advocate
    # model_trend: str = "gemini/gemini-2.5-pro"          # [Phase 2] 트렌드 에이전트
    # model_financial: str = "claude-sonnet-4-6-20250514" # [Phase 2] 재무 에이전트
    # model_risk: str = "claude-sonnet-4-6-20250514"      # [Phase 2] 리스크 에이전트
    # model_real_estate: str = "gemini/gemini-2.5-flash"  # [Phase 2] 부동산 에이전트
    # model_regulatory: str = "claude-sonnet-4-6-20250514"# [Phase 2] 규제 에이전트

    # 온도 설정
    temperature_analysis: float = 0.1
    temperature_narrative: float = 0.7
    temperature_default: float = 0.2

    def get_model_for_agent(self, agent_name: str) -> str:
        """에이전트 이름으로 할당된 LLM 모델 식별자를 반환한다."""
        attr = f"model_{agent_name}"
        if hasattr(self, attr):
            return getattr(self, attr)
        raise ValueError(f"알 수 없는 에이전트 이름: {agent_name}")

    def get_temperature_for_role(self, role: str) -> float:
        """역할(analysis/debate/narrative)에 적합한 온도 값을 반환한다."""
        mapping = {
            "analysis": self.temperature_analysis,
            "debate": self.temperature_debate,
            "narrative": self.temperature_narrative,
        }
        return mapping.get(role, self.temperature_default)


class Settings(BaseSettings):
    """
    MarketScope AI 전체 설정.
    .env 파일에서 자동 로드되며, 환경 변수로 오버라이드 가능하다.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- 앱 기본 ----
    app_name: str = "MarketScope AI"
    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT
    app_debug: bool = True
    app_version: str = "1.0.0"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_workers: int = 4
    app_log_level: LogLevel = LogLevel.DEBUG
    app_secret_key: str = Field(..., min_length=16)
    app_cors_origins: list[str] = ["http://localhost:3000"]

    # ---- LLM API 키 ----
    anthropic_api_key: str = Field(..., min_length=1)
    google_api_key: str = Field(..., min_length=1)
    openai_api_key: Optional[str] = None

    # ---- LiteLLM ----
    litellm_master_key: Optional[str] = None
    litellm_base_url: str = "http://localhost:4000"
    litellm_use_proxy: bool = False
    litellm_max_retries: int = Field(default=3, ge=0, le=10)
    litellm_timeout: int = Field(default=120, ge=10, le=600)
    litellm_fallback_enabled: bool = True

    # ---- LLM (중첩 설정) ----
    llm: LLMSettings = LLMSettings()

    # ---- PostgreSQL ----
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "marketscope"
    postgres_user: str = "marketscope_user"
    postgres_password: str = Field(..., min_length=1)
    postgres_pool_size: int = Field(default=20, ge=5, le=100)
    postgres_max_overflow: int = Field(default=10, ge=0, le=50)
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

    # ---- Redis ----
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_url: Optional[str] = None
    redis_cache_ttl: int = Field(default=3600, ge=60)
    redis_rate_limit_enabled: bool = True

    @model_validator(mode="after")
    def assemble_redis_url(self) -> "Settings":
        if self.redis_url is None:
            auth = f":{self.redis_password}@" if self.redis_password else ""
            self.redis_url = f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return self

    # ---- ChromaDB ----
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection_prefix: str = "marketscope"
    chroma_persist_directory: str = "/data/chromadb"
    chroma_embedding_model: str = "text-embedding-3-small"
    chroma_embedding_dimension: int = 1536

    # ---- LightRAG ----
    lightrag_working_dir: str = "/data/lightrag"
    lightrag_embedding_model: str = "text-embedding-3-small"
    lightrag_chunk_size: int = Field(default=1200, ge=256, le=4096)
    lightrag_chunk_overlap: int = Field(default=200, ge=0, le=1024)
    lightrag_top_k: int = Field(default=10, ge=1, le=50)

    # ---- ReMe ----
    reme_storage_backend: ReMeStorageBackend = ReMeStorageBackend.REDIS
    reme_max_short_term: int = Field(default=50, ge=10, le=200)
    reme_max_long_term: int = Field(default=500, ge=50, le=5000)
    reme_similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    reme_decay_rate: float = Field(default=0.05, ge=0.0, le=1.0)

    # ---- MCP ----
    mcp_server_url: str = "http://localhost:5100"
    mcp_transport: MCPTransport = MCPTransport.STDIO
    mcp_timeout: int = Field(default=30, ge=5, le=120)
    mcp_max_concurrent_tools: int = Field(default=5, ge=1, le=20)

    # ---- Langfuse ----
    langfuse_enabled: bool = True
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_flush_at: int = 15
    langfuse_flush_interval: int = 10

    @field_validator("langfuse_public_key", "langfuse_secret_key")
    @classmethod
    def validate_langfuse_keys(cls, v, info):
        """Langfuse가 활성화된 경우 키가 반드시 존재해야 한다."""
        # model_validator에서 langfuse_enabled와 함께 검증
        return v

    @model_validator(mode="after")
    def validate_langfuse_config(self) -> "Settings":
        if self.langfuse_enabled:
            if not self.langfuse_public_key or not self.langfuse_secret_key:
                if self.app_env == AppEnvironment.PRODUCTION:
                    raise ValueError(
                        "프로덕션 환경에서 Langfuse가 활성화된 경우 "
                        "LANGFUSE_PUBLIC_KEY와 LANGFUSE_SECRET_KEY가 필수입니다."
                    )
        return self

    # ---- 외부 데이터 API ----
    data_api_seoul_open_data_key: Optional[str] = None
    data_api_small_biz_key: Optional[str] = None
    data_api_public_data_key: Optional[str] = None
    data_api_naver_client_id: Optional[str] = None
    data_api_naver_client_secret: Optional[str] = None
    data_api_kakao_rest_key: Optional[str] = None

    # ---- 분석 실행 (Phase 1) ----
    analysis_max_parallel_agents: int = Field(default=4, ge=1, le=4)  # Phase 1: 4개 에이전트 고정
    analysis_agent_timeout: int = Field(default=60, ge=30, le=120)    # Phase 1: 60초 타임아웃
    analysis_total_timeout: int = Field(default=300, ge=60, le=600)   # Phase 1: 5분 이내
    # analysis_max_debate_rounds: int = ...                            # [Phase 2] Debate 미구현
    analysis_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)  # Phase 1: 완화
    analysis_cache_enabled: bool = True
    analysis_cache_ttl: int = Field(default=43200, ge=3600)           # Phase 1: 12시간 캐시

    # ---- Phase 1 지역 제한 ----
    phase1_seoul_only: bool = True
    phase1_allowed_districts: list[str] = [
        "강남", "홍대", "이태원", "건대", "신촌",
        "종로", "명동", "여의도", "성수", "잠실",
    ]

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnvironment.PRODUCTION

    @property
    def is_debug(self) -> bool:
        return self.app_debug and not self.is_production


@lru_cache()
def get_settings() -> Settings:
    """
    싱글톤 Settings 인스턴스를 반환한다.
    FastAPI의 Depends()에서 사용하며, 앱 전역에서 동일 인스턴스를 참조한다.
    """
    return Settings()
```

---

## 2. 공유 상태 스키마

### 2.1 설계 원칙

- LangGraph의 `TypedDict`를 사용하며, 모든 에이전트 노드가 동일한 상태 딕셔너리를 읽고 쓴다.
- 각 에이전트의 출력은 `Optional` 필드로 선언하여, 실행 전에는 `None`으로 초기화한다.
- **Reducer 패턴**: 리스트 필드(`messages`, `errors`, `debate_rounds`)는 `Annotated[list, operator.add]`를 사용해 자동 병합한다.
- 상태 변이는 반드시 노드 함수의 반환값을 통해서만 발생한다 (직접 변이 금지).

### 2.2 상태 TypedDict 정의

```python
# app/models/state.py
# ⚠️ canonical 정의: 이 파일이 State의 단일 진실 공급원(SSOT)이다.
# 01_orchestration_langgraph.md의 State도 동일 구조를 참조한다.

from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph.message import add_messages

from app.models.agent_outputs import (
    CompetitionAnalysis,
    LocationAnalysis,
    PopulationAnalysis,
    RevenueAnalysis,
    # [Phase 2] 비활성 에이전트 임포트
    # FinancialAnalysis,
    # RealEstateAnalysis,
    # RegulatoryAnalysis,
    # RiskAnalysis,
    # TrendAnalysis,
)
from app.models.report import VisualizationOutput, NarrativeOutput


# ──────────────────────────────────────────────────────────────────
# API 요청 모델 (State에 저장되지 않음 — API 레이어에서 user_input으로 변환)
# ──────────────────────────────────────────────────────────────────

class AnalysisRequest(TypedDict):
    """
    FastAPI 엔드포인트가 수신하는 구조화된 분석 요청.
    State에 직접 저장되지 않으며, API 레이어에서 user_input 텍스트로
    직렬화되어 LangGraph에 전달된다.
    commander_plan 노드가 이 정보를 파싱하여 CommanderPlan을 생성한다.
    """
    session_id: str                       # UUID v4 — 분석 세션 식별자
    user_input: str                       # 원본 사용자 자연어 입력
    user_id: Optional[str]                # 로그인 사용자 ID (비로그인 시 None)
    # 선택적 힌트 (Commander가 파싱하지 못할 때 폴백으로 사용)
    hint_location: Optional[str]          # 위치 힌트 (예: "강남역")
    hint_industry: Optional[str]          # 업종 힌트 (예: "카페")
    hint_budget: Optional[int]            # 예산 힌트 (원)


# ──────────────────────────────────────────────────────────────────
# Commander 계획 — 01_orchestration_langgraph.md CommanderPlan과 동일
# ──────────────────────────────────────────────────────────────────

class CommanderPlan(TypedDict):
    """Commander 에이전트가 수립한 실행 계획. 02_commander_agent.md 참조."""
    analysis_mode: str                     # "basic" | "quick" | "comparison"
    target_location: str                   # 분석 대상 위치 (파싱된 상권명)
    target_location_secondary: Optional[str]  # 비교 분석 시 두 번째 위치
    target_industry: str                   # 분석 대상 업종
    agents_to_run: list[str]               # 실행할 에이전트 ID 목록
    agents_to_skip: list[str]              # 건너뛸 에이전트 ID 목록
    force_debate: bool                     # [Phase 1] 항상 False
    priority_focus: list[str]             # 우선 분석 분야
    user_constraints: dict[str, Any]       # 사용자 제약 (예산, 면적 등)
    estimated_duration_seconds: int        # 예상 소요 시간 (초)
    clarification_needed: bool            # 명확화 요청 필요 여부
    clarification_message: Optional[str]  # 명확화 요청 메시지


# ──────────────────────────────────────────────────────────────────
# 실행 추적 — 01_orchestration_langgraph.md NodeExecution과 동일
# (llm_model_used, token_usage 필드를 추가로 포함하는 확장 버전)
# ──────────────────────────────────────────────────────────────────

class NodeExecution(TypedDict):
    """
    개별 노드 실행 메타데이터.
    fan-out 병렬 실행 시 여러 노드가 동시에 node_executions에 append 가능.
    """
    node_id: str                          # 노드 식별자 (예: "population_agent")
    status: str                           # "running" | "completed" | "failed" | "skipped"
    started_at: Optional[str]             # ISO 8601
    completed_at: Optional[str]           # ISO 8601
    duration_seconds: Optional[float]     # 실행 소요 시간 (초)
    llm_model_used: Optional[str]         # 실제 사용된 LLM 모델명
    token_usage: Optional[dict[str, int]] # {"prompt_tokens": N, "completion_tokens": N}
    error_message: Optional[str]          # 실패 시 에러 메시지
    retry_count: int                      # 재시도 횟수 (0 = 재시도 없음)


# ──────────────────────────────────────────────────────────────────
# 메인 State — 01_orchestration_langgraph.md MarketScopeState와 동일
# ──────────────────────────────────────────────────────────────────

class MarketScopeState(TypedDict):
    """
    MarketScope AI LangGraph 메인 State.

    모든 에이전트 노드가 공유하며 각 노드는 자신의 담당 필드만 업데이트한다.
    Annotated reducer 필드는 병렬 fan-out 시 자동 병합된다.
    """

    # ── 세션 메타데이터 (불변) ──
    session_id: str                                        # 고유 세션 식별자 (UUID)
    created_at: str                                        # 세션 생성 시각 (ISO 8601)
    updated_at: str                                        # 마지막 업데이트 시각

    # ── 사용자 입력 ──
    user_input: str                                        # 원본 사용자 자연어 입력
    messages: Annotated[list, add_messages]                # LangGraph 메시지 히스토리

    # ── Commander 계획 ──
    commander_plan: Optional[CommanderPlan]                # commander_plan 노드 실행 후 채워짐

    # ── [Phase 1] 에이전트 결과 ──
    # Step 1: 독립 실행 (병렬)
    population_result: Optional[PopulationAnalysis]        # 유동인구 분석
    competition_result: Optional[CompetitionAnalysis]      # 경쟁 분석

    # Step 2: 의존적 실행 (Step 1 완료 후)
    revenue_result: Optional[RevenueAnalysis]              # 매출 추정 (depends: population)
    location_result: Optional[LocationAnalysis]            # 입지 분석 (depends: population, competition)

    # [Phase 2] 비활성 에이전트 결과
    # trend_result: Optional[TrendAnalysis]
    # real_estate_result: Optional[RealEstateAnalysis]
    # regulatory_result: Optional[RegulatoryAnalysis]
    # financial_result: Optional[FinancialAnalysis]
    # risk_result: Optional[RiskAnalysis]

    # [Phase 2] Debate 시스템
    # debate_decision: Optional[str]
    # debate_trigger_reasons: list[str]
    # debate_result: Optional[DebateResult]

    # ── 리포트 산출물 ──
    visualization_output: Optional[VisualizationOutput]    # 시각화 에이전트 출력
    narrative_output: Optional[NarrativeOutput]            # 내러티브 에이전트 출력
    final_report: Optional[dict[str, Any]]                 # 통합 최종 보고서 (직렬화된 dict)

    # ── 실행 추적 ──
    node_executions: Annotated[list[NodeExecution], operator.add]  # append reducer
    current_phase: int                                     # 현재 실행 Phase (0~6)
    progress_pct: float                                    # 전체 진행률 (0.0~100.0)

    # ── 에러 ──
    errors: Annotated[list[dict[str, Any]], operator.add]  # append reducer
    has_critical_failure: bool                             # 치명적 실패 플래그

    # ── 비교 분석 전용 ──
    secondary_population_result: Optional[PopulationAnalysis]
    secondary_competition_result: Optional[CompetitionAnalysis]
    comparison_summary: Optional[dict[str, Any]]
```

### 2.3 State Reducer 요약

| 필드 | Reducer | 설명 |
|------|---------|------|
| `messages` | `add_messages` | LangGraph 내장 — 중복 메시지 자동 제거 |
| `node_executions` | `operator.add` | 리스트 append — 병렬 노드 동시 기록 안전 |
| `errors` | `operator.add` | 리스트 append — 에러 누적 |
| 나머지 | 덮어쓰기 | 마지막 기록 값이 최종 값 |

### 2.4 상태 초기화 팩토리 함수

```python
# app/models/state.py (계속)

from datetime import datetime, timezone


def create_initial_state(session_id: str, user_input: str) -> MarketScopeState:
    """
    신규 분석 세션의 초기 State를 생성한다.
    API 레이어에서 호출하며, session_id는 UUID v4로 생성해서 전달한다.
    """
    now = datetime.now(timezone.utc).isoformat()

    return MarketScopeState(
        # 세션
        session_id=session_id,
        created_at=now,
        updated_at=now,
        user_input=user_input,
        messages=[],

        # Commander 계획 (commander_plan 노드 실행 후 채워짐)
        commander_plan=None,

        # [Phase 1] 에이전트 결과
        population_result=None,
        competition_result=None,
        revenue_result=None,
        location_result=None,
        # [Phase 2] — 초기화 제외 (활성화 시 추가)

        # 리포트 산출물
        visualization_output=None,
        narrative_output=None,
        final_report=None,

        # 실행 추적
        node_executions=[],
        current_phase=0,
        progress_pct=0.0,

        # 에러
        errors=[],
        has_critical_failure=False,

        # 비교 분석
        secondary_population_result=None,
        secondary_competition_result=None,
        comparison_summary=None,
    )
```

---

## 3. 기본 에이전트 클래스

### 3.1 설계 원칙

- 모든 에이전트는 `BaseAgent`를 상속하며, `execute()` 메서드를 반드시 구현한다.
- LLM 호출은 LiteLLM을 통해 통합되며, 모델 선택은 설정에서 자동 결정된다.
- MCP 도구 호출, 메모리 접근, 구조화된 출력 파싱이 공통 인터페이스로 제공된다.
- 재시도 로직, 에러 핸들링, 신뢰도 점수 산출이 기본 내장된다.

### 3.2 BaseAgent 추상 클래스

```python
# app/agents/base.py

from __future__ import annotations

import asyncio
import time
import traceback
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Generic, Optional, Type, TypeVar

import litellm
from langfuse.decorators import observe
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.constants import ConfidenceLevel
from app.exceptions import (
    AgentExecutionError,
    AgentTimeoutError,
    FallbackTriggeredError,
    LLMCallError,
    MCPToolCallError,
    OutputParsingError,
)
from app.logging_config import get_agent_logger
from app.memory.reme_client import ReMeClient
from app.models.state import NodeExecution, ErrorRecord, MarketScopeState
from app.tools.mcp_client import MCPClient

# 에이전트 출력 모델의 제네릭 타입 변수
T = TypeVar("T", bound=BaseModel)


class BaseAgent(ABC, Generic[T]):
    """
    모든 MarketScope AI 에이전트가 상속하는 추상 기본 클래스.

    제네릭 파라미터 T는 에이전트의 구조화된 출력 Pydantic 모델 타입이다.
    예: class PopulationAgent(BaseAgent[PopulationAnalysis])

    책임:
        - LLM 호출 인터페이스 (LiteLLM 경유)
        - MCP 도구 호출 인터페이스
        - ReMe 메모리 읽기/쓰기
        - 구조화된 출력 파싱 (JSON -> Pydantic 모델)
        - 재시도 로직 (지수 백오프)
        - 에러 핸들링 및 폴백
        - 신뢰도 점수 산출
        - Langfuse 트레이싱 자동 연동
    """

    # ---- 서브클래스에서 오버라이드해야 하는 클래스 변수 ----
    agent_name: str = ""                     # 고유 에이전트 이름 (예: "population")
    agent_description: str = ""              # 에이전트 역할 설명 (프롬프트에 포함)
    output_model: Type[T]                    # Pydantic 출력 모델 클래스
    llm_role: str = "analysis"               # "analysis" | "debate" | "narrative"
    max_retries: int = 3                     # 최대 재시도 횟수
    retry_base_delay: float = 1.0            # 재시도 기본 대기 시간 (초)
    required_state_fields: list[str] = []    # 실행 전 검증할 상태 필드 목록

    def __init__(
        self,
        settings: Optional[Settings] = None,
        mcp_client: Optional[MCPClient] = None,
        reme_client: Optional[ReMeClient] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.mcp_client = mcp_client or MCPClient(self.settings)
        self.reme_client = reme_client or ReMeClient(self.settings)
        self.logger = get_agent_logger(self.agent_name)
        self._llm_model = self.settings.llm.get_model_for_agent(self.agent_name)
        self._temperature = self.settings.llm.get_temperature_for_role(self.llm_role)

    # ================================================================
    # 추상 메서드: 서브클래스가 반드시 구현해야 함
    # ================================================================

    @abstractmethod
    async def execute(self, state: MarketScopeState) -> T:
        """
        에이전트의 핵심 실행 로직.

        Args:
            state: 현재 LangGraph 공유 상태.

        Returns:
            구조화된 분석 결과 (Pydantic 모델 T 인스턴스).

        Raises:
            AgentExecutionError: 에이전트 실행 중 복구 불가능한 에러.
        """
        ...

    @abstractmethod
    def build_system_prompt(self, state: MarketScopeState) -> str:
        """
        상태 정보를 반영한 시스템 프롬프트를 구성한다.
        에이전트마다 고유한 역할 및 분석 지침을 포함한다.
        """
        ...

    @abstractmethod
    def build_user_prompt(self, state: MarketScopeState, data: dict[str, Any]) -> str:
        """
        수집된 데이터와 상태를 기반으로 사용자 프롬프트를 구성한다.
        에이전트마다 필요한 데이터 형식이 다르다.
        """
        ...

    # ================================================================
    # LLM 호출 인터페이스
    # ================================================================

    @observe(name="llm_call")
    async def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Type[BaseModel]] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
        additional_messages: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        """
        LiteLLM을 통해 LLM을 호출한다.

        Args:
            system_prompt: 시스템 프롬프트.
            user_prompt: 사용자 프롬프트.
            response_format: Pydantic 모델 클래스 (구조화된 출력 요청 시).
            temperature: 온도 오버라이드 (None이면 에이전트 기본값 사용).
            max_tokens: 최대 토큰 수.
            additional_messages: 추가 메시지 (few-shot 예시 등).

        Returns:
            {
                "content": str,            # LLM 응답 텍스트
                "parsed": Optional[T],     # 파싱된 Pydantic 모델 (response_format 지정 시)
                "usage": {                 # 토큰 사용량
                    "prompt_tokens": int,
                    "completion_tokens": int,
                },
                "model": str,              # 실제 사용된 모델
                "latency_ms": float,       # 호출 지연 시간 (밀리초)
            }

        Raises:
            LLMCallError: LLM 호출 실패 (재시도 후에도).
        """
        messages = [{"role": "system", "content": system_prompt}]
        if additional_messages:
            messages.extend(additional_messages)
        messages.append({"role": "user", "content": user_prompt})

        effective_temperature = temperature if temperature is not None else self._temperature

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.monotonic()

                kwargs: dict[str, Any] = {
                    "model": self._llm_model,
                    "messages": messages,
                    "temperature": effective_temperature,
                    "max_tokens": max_tokens,
                    "timeout": self.settings.litellm_timeout,
                }

                # 구조화된 출력 요청 (모델이 지원하는 경우)
                if response_format is not None:
                    kwargs["response_format"] = response_format

                response = await litellm.acompletion(**kwargs)

                latency_ms = (time.monotonic() - start_time) * 1000

                content = response.choices[0].message.content
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }

                # 구조화된 출력 파싱
                parsed = None
                if response_format is not None and content:
                    parsed = self._parse_structured_output(content, response_format)

                self.logger.info(
                    "LLM 호출 성공",
                    extra={
                        "model": self._llm_model,
                        "attempt": attempt + 1,
                        "latency_ms": round(latency_ms, 2),
                        "prompt_tokens": usage["prompt_tokens"],
                        "completion_tokens": usage["completion_tokens"],
                    },
                )

                return {
                    "content": content,
                    "parsed": parsed,
                    "usage": usage,
                    "model": self._llm_model,
                    "latency_ms": latency_ms,
                }

            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"LLM 호출 실패 (시도 {attempt + 1}/{self.max_retries + 1})",
                    extra={"error": str(e), "model": self._llm_model},
                )
                if attempt < self.max_retries:
                    delay = self.retry_base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)

        raise LLMCallError(
            agent_name=self.agent_name,
            model=self._llm_model,
            original_error=last_error,
            attempts=self.max_retries + 1,
        )

    # ================================================================
    # 구조화된 출력 파싱
    # ================================================================

    def _parse_structured_output(
        self,
        raw_content: str,
        model_class: Type[BaseModel],
    ) -> BaseModel:
        """
        LLM 응답을 Pydantic 모델로 파싱한다.
        JSON 블록 추출 -> Pydantic 유효성 검증 순서로 진행한다.

        3단계 파싱 전략:
        1. response_format으로 이미 파싱된 경우 그대로 반환.
        2. 응답에서 JSON 코드 블록(```json ... ```) 추출 후 파싱.
        3. 응답 전체를 JSON으로 파싱 시도.

        Raises:
            OutputParsingError: 모든 파싱 전략 실패 시.
        """
        import json
        import re

        # 전략 1: JSON 코드 블록 추출
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", raw_content)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return model_class.model_validate(data)
            except (json.JSONDecodeError, ValidationError):
                pass

        # 전략 2: 전체 텍스트를 JSON으로 파싱
        try:
            data = json.loads(raw_content)
            return model_class.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            pass

        # 전략 3: JSON 객체 패턴 추출 (처음 { 부터 마지막 } 까지)
        brace_match = re.search(r"\{[\s\S]*\}", raw_content)
        if brace_match:
            try:
                data = json.loads(brace_match.group(0))
                return model_class.model_validate(data)
            except (json.JSONDecodeError, ValidationError):
                pass

        raise OutputParsingError(
            agent_name=self.agent_name,
            model_class=model_class.__name__,
            raw_content=raw_content[:500],
        )

    # ================================================================
    # MCP 도구 호출 인터페이스
    # ================================================================

    @observe(name="mcp_tool_call")
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        MCP 프로토콜을 통해 외부 도구를 호출한다.

        Args:
            tool_name: MCP 도구 이름 (예: "search_floating_population").
            arguments: 도구 인자 딕셔너리.
            timeout: 타임아웃 (초). None이면 설정 기본값.

        Returns:
            도구 실행 결과 딕셔너리.

        Raises:
            MCPToolCallError: 도구 호출 실패.
        """
        effective_timeout = timeout or self.settings.mcp_timeout

        try:
            result = await asyncio.wait_for(
                self.mcp_client.call_tool(tool_name, arguments),
                timeout=effective_timeout,
            )

            self.logger.info(
                f"MCP 도구 호출 성공: {tool_name}",
                extra={"tool": tool_name, "arguments_keys": list(arguments.keys())},
            )
            return result

        except asyncio.TimeoutError:
            raise MCPToolCallError(
                agent_name=self.agent_name,
                tool_name=tool_name,
                message=f"도구 호출 타임아웃 ({effective_timeout}초)",
            )
        except Exception as e:
            raise MCPToolCallError(
                agent_name=self.agent_name,
                tool_name=tool_name,
                message=str(e),
                original_error=e,
            )

    async def call_tools_parallel(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        여러 MCP 도구를 병렬로 호출한다.

        Args:
            tool_calls: [{"tool_name": str, "arguments": dict}, ...]

        Returns:
            결과 리스트 (호출 순서 유지). 개별 실패 시 해당 항목은
            {"error": str, "tool_name": str} 형태로 반환된다.
        """
        semaphore = asyncio.Semaphore(self.settings.mcp_max_concurrent_tools)

        async def _call_with_semaphore(tc: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                try:
                    return await self.call_tool(tc["tool_name"], tc["arguments"])
                except MCPToolCallError as e:
                    self.logger.error(f"병렬 도구 호출 실패: {tc['tool_name']}", extra={"error": str(e)})
                    return {"error": str(e), "tool_name": tc["tool_name"]}

        tasks = [_call_with_semaphore(tc) for tc in tool_calls]
        return await asyncio.gather(*tasks)

    # ================================================================
    # 메모리 인터페이스 (ReMe)
    # ================================================================

    async def recall_memory(
        self,
        query: str,
        memory_type: str = "long_term",
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        ReMe 메모리 시스템에서 관련 기억을 검색한다.

        Args:
            query: 검색 쿼리.
            memory_type: "short_term" | "long_term" | "episodic".
            top_k: 반환할 최대 기억 수.

        Returns:
            관련 기억 리스트. 각 항목:
            {"content": str, "relevance": float, "created_at": str, "metadata": dict}
        """
        try:
            memories = await self.reme_client.recall(
                agent_name=self.agent_name,
                query=query,
                memory_type=memory_type,
                top_k=top_k,
            )
            self.logger.debug(f"기억 검색 완료: {len(memories)}건", extra={"query": query[:100]})
            return memories
        except Exception as e:
            self.logger.warning(f"기억 검색 실패 (무시): {e}")
            return []

    async def store_memory(
        self,
        content: str,
        memory_type: str = "short_term",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        ReMe 메모리 시스템에 새 기억을 저장한다.

        Args:
            content: 저장할 기억 내용.
            memory_type: "short_term" | "long_term" | "episodic".
            metadata: 추가 메타데이터 (분석 대상 상권, 업종 등).
        """
        try:
            await self.reme_client.store(
                agent_name=self.agent_name,
                content=content,
                memory_type=memory_type,
                metadata=metadata or {},
            )
            self.logger.debug("기억 저장 완료", extra={"memory_type": memory_type})
        except Exception as e:
            self.logger.warning(f"기억 저장 실패 (무시): {e}")

    # ================================================================
    # 신뢰도 점수 산출
    # ================================================================

    def calculate_confidence(
        self,
        data_completeness: float,
        data_freshness: float,
        source_count: int,
        cross_validation_score: float = 0.0,
    ) -> float:
        """
        에이전트 분석 결과의 신뢰도 점수를 산출한다.

        가중치 기반 종합 점수 (0.0 ~ 1.0):
        - 데이터 완전성 (30%): 필수 데이터 필드 중 실제 확보된 비율
        - 데이터 신선도 (25%): 데이터의 최신성 점수
        - 데이터 소스 수 (20%): 참조한 데이터 소스 개수 기반
        - 교차 검증 점수 (25%): 다른 에이전트 결과와의 정합성

        Args:
            data_completeness: 데이터 완전성 (0.0~1.0).
            data_freshness: 데이터 신선도 (0.0~1.0).
            source_count: 참조 데이터 소스 수.
            cross_validation_score: 교차 검증 점수 (0.0~1.0).

        Returns:
            종합 신뢰도 점수 (0.0~1.0).
        """
        # 소스 수를 0~1 점수로 정규화 (5개 이상이면 만점)
        source_score = min(source_count / 5.0, 1.0)

        confidence = (
            data_completeness * 0.30
            + data_freshness * 0.25
            + source_score * 0.20
            + cross_validation_score * 0.25
        )

        return round(min(max(confidence, 0.0), 1.0), 4)

    def classify_confidence(self, score: float) -> ConfidenceLevel:
        """신뢰도 점수를 등급으로 분류한다."""
        if score >= 0.85:
            return ConfidenceLevel.VERY_HIGH
        elif score >= 0.70:
            return ConfidenceLevel.HIGH
        elif score >= 0.55:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.40:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    # ================================================================
    # 상태 검증
    # ================================================================

    def validate_required_state(self, state: MarketScopeState) -> list[str]:
        """
        에이전트 실행 전 필요한 상태 필드가 존재하는지 검증한다.

        Returns:
            누락된 필드 이름 리스트 (비어있으면 검증 통과).
        """
        missing = []
        for field in self.required_state_fields:
            value = state.get(field)
            if value is None:
                missing.append(field)
        return missing

    # ================================================================
    # 에러 기록 생성 헬퍼
    # ================================================================

    def create_error_record(
        self,
        error: Exception,
        is_critical: bool = False,
        fallback_applied: bool = False,
    ) -> ErrorRecord:
        """에러를 구조화된 ErrorRecord로 변환한다."""
        return ErrorRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_name=self.agent_name,
            error_type=type(error).__name__,
            error_message=str(error),
            is_critical=is_critical,
            fallback_applied=fallback_applied,
        )

    # ================================================================
    # 실행 메타데이터 업데이트 헬퍼
    # ================================================================

    def create_execution_started(self) -> NodeExecution:
        """에이전트 실행 시작 메타데이터를 생성한다."""
        return NodeExecution(
            node_id=self.agent_name,
            status="running",
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=None,
            duration_seconds=None,
            llm_model_used=self._llm_model,
            token_usage=None,
            error_message=None,
            retry_count=0,
        )

    def create_execution_completed(
        self,
        started_at: str,
        token_usage: dict[str, int],
        retry_count: int = 0,
    ) -> NodeExecution:
        """에이전트 실행 완료 메타데이터를 생성한다."""
        now = datetime.now(timezone.utc)
        started = datetime.fromisoformat(started_at)
        duration = (now - started).total_seconds()

        return NodeExecution(
            node_id=self.agent_name,
            status="completed",
            started_at=started_at,
            completed_at=now.isoformat(),
            duration_seconds=round(duration, 3),
            llm_model_used=self._llm_model,
            token_usage=token_usage,
            error_message=None,
            retry_count=retry_count,
        )

    def create_execution_failed(
        self,
        started_at: str,
        error_message: str,
        retry_count: int = 0,
    ) -> NodeExecution:
        """에이전트 실행 실패 메타데이터를 생성한다."""
        now = datetime.now(timezone.utc)
        started = datetime.fromisoformat(started_at)
        duration = (now - started).total_seconds()

        return NodeExecution(
            node_id=self.agent_name,
            status="failed",
            started_at=started_at,
            completed_at=now.isoformat(),
            duration_seconds=round(duration, 3),
            llm_model_used=self._llm_model,
            token_usage=None,
            error_message=error_message,
            retry_count=retry_count,
        )

    # ================================================================
    # 그래프 노드 래퍼 (LangGraph 노드에서 호출)
    # ================================================================

    @observe(name="agent_node")
    async def run(self, state: MarketScopeState) -> dict[str, Any]:
        """
        LangGraph 노드 함수로 사용되는 최상위 실행 래퍼.

        1. 상태 필드 검증
        2. 실행 메타 "running" 설정
        3. execute() 호출 (서브클래스 구현)
        4. 결과를 상태 업데이트 딕셔너리로 반환
        5. 에러 발생 시 폴백 처리 + 에러 기록

        Returns:
            LangGraph 상태 업데이트 딕셔너리.
            예: {"population_result": PopulationAnalysis(...),
                 "node_executions": [NodeExecution(...)], "errors": [...]}
        """
        execution_start = datetime.now(timezone.utc).isoformat()
        state_update: dict[str, Any] = {}
        retry_count = 0
        accumulated_errors: list[ErrorRecord] = []

        self.logger.info(f"에이전트 실행 시작: {self.agent_name}")

        # 상태 검증
        missing_fields = self.validate_required_state(state)
        if missing_fields:
            self.logger.warning(f"필수 상태 필드 누락: {missing_fields}")
            # 누락 필드가 있어도 최선을 다해 실행 시도
            # (에이전트 내에서 해당 데이터 없이 분석)

        # 실행 시도 (재시도 포함)
        try:
            result: T = await asyncio.wait_for(
                self._execute_with_retry(state),
                timeout=self.settings.analysis_agent_timeout,
            )

            # 결과 필드명 결정 (에이전트 이름 + "_result")
            result_field = f"{self.agent_name}_result"
            state_update[result_field] = result

            # 실행 메타 업데이트 (list append — operator.add reducer)
            token_usage = getattr(result, "_token_usage", {"prompt_tokens": 0, "completion_tokens": 0})
            state_update["node_executions"] = [
                self.create_execution_completed(
                    started_at=execution_start,
                    token_usage=token_usage,
                    retry_count=retry_count,
                )
            ]

            # 기억 저장 (핵심 인사이트)
            if hasattr(result, "key_insight") and result.key_insight:
                plan = state.get("commander_plan") or {}
                await self.store_memory(
                    content=result.key_insight,
                    memory_type="long_term",
                    metadata={
                        "location": plan.get("target_location", "unknown"),
                        "industry": plan.get("target_industry", "unknown"),
                        "agent": self.agent_name,
                    },
                )

            self.logger.info(f"에이전트 실행 완료: {self.agent_name}")

        except asyncio.TimeoutError:
            error = AgentTimeoutError(
                agent_name=self.agent_name,
                timeout_seconds=self.settings.analysis_agent_timeout,
            )
            self.logger.error(f"에이전트 타임아웃: {self.agent_name}")
            accumulated_errors.append(self.create_error_record(error, is_critical=False, fallback_applied=True))

            # 폴백: 빈 결과 + 최저 신뢰도
            fallback_result = self._create_fallback_result(state, str(error))
            result_field = f"{self.agent_name}_result"
            state_update[result_field] = fallback_result
            state_update["node_executions"] = [
                self.create_execution_failed(
                    started_at=execution_start,
                    error_message=str(error),
                    retry_count=retry_count,
                )
            ]

        except AgentExecutionError as e:
            self.logger.error(f"에이전트 실행 에러: {self.agent_name}", extra={"error": str(e)})
            accumulated_errors.append(self.create_error_record(e, is_critical=e.is_critical, fallback_applied=True))

            fallback_result = self._create_fallback_result(state, str(e))
            result_field = f"{self.agent_name}_result"
            state_update[result_field] = fallback_result
            state_update["node_executions"] = [
                self.create_execution_failed(
                    started_at=execution_start,
                    error_message=str(e),
                    retry_count=retry_count,
                )
            ]

        except Exception as e:
            self.logger.error(
                f"에이전트 예상치 못한 에러: {self.agent_name}",
                extra={"error": str(e), "traceback": traceback.format_exc()},
            )
            accumulated_errors.append(self.create_error_record(e, is_critical=False, fallback_applied=True))

            fallback_result = self._create_fallback_result(state, str(e))
            result_field = f"{self.agent_name}_result"
            state_update[result_field] = fallback_result
            state_update["node_executions"] = [
                self.create_execution_failed(
                    started_at=execution_start,
                    error_message=str(e),
                    retry_count=retry_count,
                )
            ]

        # 에러 기록 추가 (reducer가 자동 append)
        if accumulated_errors:
            state_update["errors"] = accumulated_errors

        return state_update

    async def _execute_with_retry(self, state: MarketScopeState) -> T:
        """execute()를 재시도 로직과 함께 실행한다."""
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                return await self.execute(state)
            except (LLMCallError, OutputParsingError, MCPToolCallError) as e:
                last_error = e
                self.logger.warning(
                    f"실행 재시도 {attempt + 1}/{self.max_retries + 1}",
                    extra={"error": str(e)},
                )
                if attempt < self.max_retries:
                    delay = self.retry_base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)

        raise AgentExecutionError(
            agent_name=self.agent_name,
            message=f"{self.max_retries + 1}회 시도 후 실패",
            original_error=last_error,
        )

    def _create_fallback_result(self, state: MarketScopeState, error_message: str) -> T:
        """
        에러 발생 시 최소한의 폴백 결과를 생성한다.
        서브클래스에서 오버라이드하여 더 정교한 폴백을 구현할 수 있다.

        기본 구현: output_model의 모든 필드를 기본값/None으로 채우고,
        confidence_score를 0.0, key_insight를 에러 메시지로 설정한다.
        """
        # Pydantic 모델의 필드 기본값으로 인스턴스 생성 시도
        defaults: dict[str, Any] = {}
        for field_name, field_info in self.output_model.model_fields.items():
            if field_info.default is not None:
                defaults[field_name] = field_info.default
            elif field_info.default_factory is not None:
                defaults[field_name] = field_info.default_factory()
            else:
                # 타입 기반 기본값 추론
                annotation = field_info.annotation
                if annotation == str or annotation == Optional[str]:
                    defaults[field_name] = ""
                elif annotation == int or annotation == Optional[int]:
                    defaults[field_name] = 0
                elif annotation == float or annotation == Optional[float]:
                    defaults[field_name] = 0.0
                elif annotation == bool:
                    defaults[field_name] = False
                elif annotation == list or str(annotation).startswith("list"):
                    defaults[field_name] = []
                elif annotation == dict or str(annotation).startswith("dict"):
                    defaults[field_name] = {}
                else:
                    defaults[field_name] = None

        # 공통 필드 강제 설정
        if "confidence_score" in defaults:
            defaults["confidence_score"] = 0.0
        if "key_insight" in defaults:
            defaults["key_insight"] = f"[폴백] 분석 실패: {error_message}"

        return self.output_model.model_validate(defaults)
```

---

## 4. 공유 Pydantic 모델

### 4.1 공통 재사용 모델

```python
# app/models/common.py

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TimeSlot(BaseModel):
    """시간대별 데이터 포인트."""
    hour: int = Field(..., ge=0, le=23, description="시간 (0-23)")
    value: float = Field(..., description="해당 시간대의 측정값")
    label: Optional[str] = Field(None, description="시간대 라벨 (예: '출근시간대')")


class DayOfWeek(str, Enum):
    """요일."""
    MONDAY = "월"
    TUESDAY = "화"
    WEDNESDAY = "수"
    THURSDAY = "목"
    FRIDAY = "금"
    SATURDAY = "토"
    SUNDAY = "일"


class DailyValue(BaseModel):
    """요일별 데이터 포인트."""
    day: DayOfWeek = Field(..., description="요일")
    value: float = Field(..., description="해당 요일의 측정값")


class AgeDistribution(BaseModel):
    """연령대별 분포."""
    age_10s: float = Field(0.0, description="10대 비율 (%)", ge=0, le=100)
    age_20s: float = Field(0.0, description="20대 비율 (%)", ge=0, le=100)
    age_30s: float = Field(0.0, description="30대 비율 (%)", ge=0, le=100)
    age_40s: float = Field(0.0, description="40대 비율 (%)", ge=0, le=100)
    age_50s: float = Field(0.0, description="50대 비율 (%)", ge=0, le=100)
    age_60_plus: float = Field(0.0, description="60대 이상 비율 (%)", ge=0, le=100)


class TrendDirection(str, Enum):
    """추세 방향."""
    STRONG_UP = "강한상승"
    UP = "상승"
    STABLE = "보합"
    DOWN = "하락"
    STRONG_DOWN = "강한하락"


class MoneyRange(BaseModel):
    """금액 범위."""
    min_value: int = Field(..., description="최소 금액 (원)")
    max_value: int = Field(..., description="최대 금액 (원)")
    currency: str = Field(default="KRW", description="통화 코드")


class ScenarioResult(BaseModel):
    """시나리오별 재무 예측 결과."""
    label: str = Field(..., description="시나리오 라벨 (예: '낙관', '현실', '비관')")
    monthly_revenue: int = Field(..., description="예상 월 매출 (원)")
    monthly_profit: int = Field(..., description="예상 월 순이익 (원)")
    break_even_months: int = Field(..., description="손익분기 도달 예상 개월 수")
    roi_12m: float = Field(..., description="12개월 ROI (%)")
    probability: float = Field(..., description="해당 시나리오 실현 확률 (0.0~1.0)")
    assumptions: str = Field(..., description="시나리오 전제 조건 요약")


class RiskFactor(BaseModel):
    """개별 리스크 요인."""
    category: str = Field(..., description="리스크 카테고리 (예: '경쟁', '경기', '규제')")
    name: str = Field(..., description="리스크 요인명")
    description: str = Field(..., description="리스크 상세 설명")
    severity: float = Field(..., description="심각도 (1.0~5.0)", ge=1.0, le=5.0)
    probability: float = Field(..., description="발생 확률 (0.0~1.0)", ge=0.0, le=1.0)
    impact_score: float = Field(..., description="영향도 점수 (severity * probability)")
    mitigation: str = Field(..., description="완화 방안")


class PropertyInfo(BaseModel):
    """매물 정보."""
    address: str = Field(..., description="매물 주소")
    size_pyeong: float = Field(..., description="면적 (평)")
    floor: str = Field(..., description="층수 (예: '1층', '지하1층')")
    monthly_rent: int = Field(..., description="월 임대료 (원)")
    deposit: int = Field(..., description="보증금 (원)")
    premium: int = Field(0, description="권리금 (원)")
    available_date: Optional[str] = Field(None, description="입주 가능일")
    source: Optional[str] = Field(None, description="매물 출처")


class PermitRequirement(BaseModel):
    """인허가 요건 정보."""
    permit_name: str = Field(..., description="인허가 명칭")
    issuing_authority: str = Field(..., description="발급 기관")
    estimated_days: int = Field(..., description="예상 소요일")
    estimated_cost: int = Field(0, description="예상 비용 (원)")
    required_documents: list[str] = Field(default_factory=list, description="필요 서류 목록")
    difficulty: str = Field(..., description="난이도 ('쉬움' | '보통' | '어려움')")
    notes: Optional[str] = Field(None, description="특이사항")
```

### 4.2 에이전트 출력 모델

```python
# app/models/agent_outputs.py

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.common import (
    AgeDistribution,
    DailyValue,
    MoneyRange,
    PropertyInfo,
    PermitRequirement,
    RiskFactor,
    ScenarioResult,
    TimeSlot,
    TrendDirection,
)


# ================================================================
# 1. 유동인구 분석 (PopulationAnalysis)
# ================================================================

class PopulationAnalysis(BaseModel):
    """
    유동인구 분석 에이전트의 구조화된 출력.
    서울시 유동인구 데이터, 주민등록 데이터, 직장인 데이터를 종합 분석한다.
    """
    total_floating_population: int = Field(
        ...,
        description="일평균 총 유동인구 (명). 해당 상권을 하루 동안 통과하는 총 인구 수.",
    )
    floating_by_time: list[TimeSlot] = Field(
        default_factory=list,
        description="시간대별 유동인구 분포. 0시부터 23시까지 시간당 유동인구 수.",
    )
    floating_by_day: list[DailyValue] = Field(
        default_factory=list,
        description="요일별 유동인구 분포. 월~일 각 요일의 일평균 유동인구.",
    )
    resident_population: int = Field(
        ...,
        description="상권 반경 내 거주 인구 (명). 주민등록 기준.",
    )
    worker_population: int = Field(
        ...,
        description="상권 반경 내 직장인 인구 (명). 국민연금 가입자 기준.",
    )
    age_distribution: AgeDistribution = Field(
        ...,
        description="유동인구의 연령대별 분포 (%). 10대~60대 이상.",
    )
    gender_ratio: float = Field(
        ...,
        description="남성 비율 (%). 50.0이면 남녀 동등. (예: 45.2 = 남성 45.2%, 여성 54.8%)",
        ge=0.0,
        le=100.0,
    )
    population_trend: TrendDirection = Field(
        ...,
        description="최근 12개월 유동인구 추세 방향.",
    )
    trend_rate: float = Field(
        ...,
        description="전년 대비 유동인구 증감률 (%). 양수면 증가, 음수면 감소.",
    )
    peak_times: list[str] = Field(
        default_factory=list,
        description="유동인구 피크 시간대 목록 (예: ['12:00-13:00', '18:00-19:00']).",
    )
    key_insight: str = Field(
        ...,
        description="유동인구 분석의 핵심 인사이트 요약. 2~3문장으로 사업적 시사점 포함.",
    )
    confidence_score: float = Field(
        ...,
        description="분석 결과 신뢰도 (0.0~1.0). 데이터 품질, 완전성, 신선도 기반.",
        ge=0.0,
        le=1.0,
    )
    data_freshness: str = Field(
        ...,
        description="분석에 사용된 데이터의 기준 시점 (예: '2026년 2월 기준').",
    )


# ================================================================
# 2. 매출 분석 (RevenueAnalysis)
# ================================================================

class RevenueAnalysis(BaseModel):
    """
    매출 분석 에이전트의 구조화된 출력.
    소상공인시장진흥공단 매출 데이터, 카드사 결제 데이터를 기반으로 분석한다.
    """
    area_total_revenue: int = Field(
        ...,
        description="상권 전체 월 총매출 (원). 해당 상권 내 모든 업종의 합산 월매출.",
    )
    target_industry_revenue: int = Field(
        ...,
        description="타겟 업종 월 총매출 (원). 분석 요청 업종의 상권 내 합산 월매출.",
    )
    revenue_per_store: int = Field(
        ...,
        description="타겟 업종 점포당 월 평균 매출 (원).",
    )
    revenue_trend: TrendDirection = Field(
        ...,
        description="최근 12개월 매출 추세 방향.",
    )
    seasonal_pattern: list[DailyValue] = Field(
        default_factory=list,
        description="월별 매출 지수 패턴. 연간 평균=100 기준 상대 지수. DailyValue의 day는 월 이름으로 사용.",
    )
    avg_ticket_price: int = Field(
        ...,
        description="타겟 업종 평균 결제 단가 (원). 건당 평균 결제 금액.",
    )
    estimated_monthly_revenue: int = Field(
        ...,
        description="신규 점포 예상 월 매출 (원). 현실적 시나리오 기준.",
    )
    revenue_range: MoneyRange = Field(
        ...,
        description="예상 월 매출 범위 (원). 하한(비관)~상한(낙관).",
    )
    top_performing_industries: list[str] = Field(
        default_factory=list,
        description="해당 상권 내 매출 상위 업종 목록 (최대 5개). 업종명으로 기술.",
    )
    key_insight: str = Field(
        ...,
        description="매출 분석의 핵심 인사이트 요약. 매출 전망과 사업적 시사점.",
    )
    confidence_score: float = Field(
        ...,
        description="분석 결과 신뢰도 (0.0~1.0).",
        ge=0.0,
        le=1.0,
    )


# ================================================================
# 3. 경쟁 분석 (CompetitionAnalysis)
# ================================================================

class CompetitionAnalysis(BaseModel):
    """
    경쟁 분석 에이전트의 구조화된 출력.
    상권 내 경쟁 업체 현황, 포화도, 개폐업률을 분석한다.
    """
    total_competitors: int = Field(
        ...,
        description="상권 내 전체 경쟁 업체 수 (동일 대분류 업종).",
    )
    direct_competitors: int = Field(
        ...,
        description="직접 경쟁 업체 수 (동일 소분류 업종).",
    )
    indirect_competitors: int = Field(
        ...,
        description="간접 경쟁 업체 수 (동일 대분류, 다른 소분류).",
    )
    saturation_index: float = Field(
        ...,
        description="상권 포화 지수 (0.0~2.0). 1.0이 평균, 1.0 초과 시 포화 상태.",
        ge=0.0,
    )
    opening_rate_12m: float = Field(
        ...,
        description="최근 12개월 개업률 (%). 신규 개업 점포 수 / 기존 점포 수 * 100.",
        ge=0.0,
    )
    closing_rate_12m: float = Field(
        ...,
        description="최근 12개월 폐업률 (%). 폐업 점포 수 / 기존 점포 수 * 100.",
        ge=0.0,
    )
    avg_business_duration: float = Field(
        ...,
        description="타겟 업종의 평균 영업 기간 (개월). 해당 상권 내 동일 업종 기준.",
    )
    market_share_top5: float = Field(
        ...,
        description="상위 5개 업체 매출 점유율 합계 (%). 시장 집중도 지표.",
        ge=0.0,
        le=100.0,
    )
    differentiation_opportunities: list[str] = Field(
        default_factory=list,
        description="차별화 기회 요인 목록. 경쟁 공백 또는 미충족 수요 기반.",
    )
    competitive_threat_level: str = Field(
        ...,
        description="경쟁 위협 수준 ('매우낮음' | '낮음' | '보통' | '높음' | '매우높음').",
    )
    key_insight: str = Field(
        ...,
        description="경쟁 분석의 핵심 인사이트 요약. 경쟁 환경 해석과 진입 전략 시사점.",
    )
    confidence_score: float = Field(
        ...,
        description="분석 결과 신뢰도 (0.0~1.0).",
        ge=0.0,
        le=1.0,
    )


# ================================================================
# 4. 입지 분석 (LocationAnalysis)
# ================================================================

class LocationAnalysis(BaseModel):
    """
    입지 분석 에이전트의 구조화된 출력.
    교통 접근성, 가시성, 주변 앵커 시설, 개발 계획을 분석한다.
    """
    accessibility_score: float = Field(
        ...,
        description="교통 접근성 종합 점수 (0.0~100.0). 지하철, 버스, 주차 종합.",
        ge=0.0,
        le=100.0,
    )
    nearest_subway: str = Field(
        ...,
        description="최근접 지하철역 정보 (예: '강남역 2호선 3번출구 도보 2분').",
    )
    bus_routes_within_300m: int = Field(
        ...,
        description="반경 300m 내 버스 노선 수.",
        ge=0,
    )
    parking_availability: str = Field(
        ...,
        description="주차 편의성 평가 ('매우부족' | '부족' | '보통' | '양호' | '충분').",
    )
    visibility_score: float = Field(
        ...,
        description="가시성/노출도 점수 (0.0~100.0). 유동인구 동선 대비 점포 노출 정도.",
        ge=0.0,
        le=100.0,
    )
    foot_traffic_quality: str = Field(
        ...,
        description="유동인구 질적 평가 (예: '소비 목적 유동인구 비율 높음'). 타겟 업종 관련성 기반.",
    )
    anchor_facilities: list[str] = Field(
        default_factory=list,
        description="주변 앵커 시설 목록 (예: ['코엑스몰', '현대백화점', '삼성서울병원']).",
    )
    nearby_development: list[str] = Field(
        default_factory=list,
        description="주변 개발 계획 목록 (예: ['영동대로 지하공간 복합개발 2027년 완공 예정']).",
    )
    floor_recommendation: str = Field(
        ...,
        description="권장 층수 및 사유 (예: '1층 권장 - 해당 업종은 가시성이 매출에 직접적 영향').",
    )
    location_grade: str = Field(
        ...,
        description="입지 종합 등급 ('S' | 'A' | 'B' | 'C' | 'D').",
    )
    key_insight: str = Field(
        ...,
        description="입지 분석의 핵심 인사이트 요약.",
    )
    confidence_score: float = Field(
        ...,
        description="분석 결과 신뢰도 (0.0~1.0).",
        ge=0.0,
        le=1.0,
    )


# ================================================================
# 5. 트렌드 분석 (TrendAnalysis)
# ================================================================

class TrendAnalysis(BaseModel):
    """
    트렌드 분석 에이전트의 구조화된 출력.
    업종 생애주기, 검색 트렌드, 소셜 버즈, 소비자 선호 변화를 분석한다.
    """
    industry_lifecycle_stage: str = Field(
        ...,
        description="업종 생애주기 단계 ('도입기' | '성장기' | '성숙기' | '쇠퇴기').",
    )
    search_volume_trend: TrendDirection = Field(
        ...,
        description="네이버/구글 검색량 추세 방향 (최근 12개월 기준).",
    )
    social_buzz_score: float = Field(
        ...,
        description="소셜 미디어 버즈 점수 (0.0~100.0). SNS 언급량 및 감성 분석 종합.",
        ge=0.0,
        le=100.0,
    )
    emerging_keywords: list[str] = Field(
        default_factory=list,
        description="부상 중인 관련 키워드 목록 (예: ['건강한 한식', '1인 삼겹살', '숙성 고기']). 최대 10개.",
    )
    consumer_preference_shifts: list[str] = Field(
        default_factory=list,
        description="소비자 선호 변화 요인 목록 (예: ['건강 지향 소비 증가', '1인 가구 외식 증가']). 최대 5개.",
    )
    related_trending_industries: list[str] = Field(
        default_factory=list,
        description="관련 상승 트렌드 업종 (예: ['무인 매장', '밀키트 전문점']). 최대 5개.",
    )
    risk_signals: list[str] = Field(
        default_factory=list,
        description="트렌드 기반 위험 신호 (예: ['해당 업종 검색량 6개월 연속 하락']). 최대 5개.",
    )
    opportunity_signals: list[str] = Field(
        default_factory=list,
        description="트렌드 기반 기회 신호 (예: ['인근 지역 동일 업종 검색량 급증']). 최대 5개.",
    )
    trend_summary: str = Field(
        ...,
        description="트렌드 분석 종합 요약. 업종의 현재 위치와 향후 전망을 3~5문장으로 서술.",
    )
    confidence_score: float = Field(
        ...,
        description="분석 결과 신뢰도 (0.0~1.0).",
        ge=0.0,
        le=1.0,
    )


# ================================================================
# 6. 재무 분석 (FinancialAnalysis)
# ================================================================

class FinancialAnalysis(BaseModel):
    """
    재무 분석 에이전트의 구조화된 출력.
    초기 투자비, 월 운영비, 손익분기, ROI, 시나리오별 예측을 수행한다.
    """
    initial_investment: dict[str, int] = Field(
        ...,
        description=(
            "초기 투자비 항목별 내역 (원). "
            "예: {'인테리어': 30000000, '설비/장비': 15000000, '보증금': 50000000, "
            "'권리금': 20000000, '초기재고': 5000000, '인허가비용': 2000000, '기타': 3000000}"
        ),
    )
    total_initial_cost: int = Field(
        ...,
        description="초기 투자비 총합 (원).",
    )
    monthly_fixed_costs: dict[str, int] = Field(
        ...,
        description=(
            "월 고정비 항목별 내역 (원). "
            "예: {'임대료': 3000000, '인건비': 6000000, '관리비': 500000, "
            "'보험료': 200000, '감가상각': 400000}"
        ),
    )
    monthly_variable_costs: dict[str, int] = Field(
        ...,
        description=(
            "월 변동비 항목별 내역 (원). "
            "예: {'식재료비': 8000000, '포장재': 500000, '카드수수료': 600000, "
            "'배달수수료': 1000000, '소모품': 300000}"
        ),
    )
    break_even_monthly_revenue: int = Field(
        ...,
        description="월 손익분기 매출 (원). 이 이상 매출을 올려야 흑자.",
    )
    break_even_months: int = Field(
        ...,
        description="손익분기 도달 예상 개월 수 (현실적 시나리오 기준).",
    )
    roi_12m: float = Field(
        ...,
        description="12개월 예상 ROI (%). (12개월 순이익 합 / 총 초기 투자) * 100.",
    )
    roi_24m: float = Field(
        ...,
        description="24개월 예상 ROI (%). (24개월 순이익 합 / 총 초기 투자) * 100.",
    )
    scenario_optimistic: ScenarioResult = Field(
        ...,
        description="낙관적 시나리오 예측 결과.",
    )
    scenario_realistic: ScenarioResult = Field(
        ...,
        description="현실적 시나리오 예측 결과.",
    )
    scenario_pessimistic: ScenarioResult = Field(
        ...,
        description="비관적 시나리오 예측 결과.",
    )
    funding_options: list[str] = Field(
        default_factory=list,
        description="활용 가능한 자금 조달 방안 (예: ['소상공인 정책자금', '신용보증기금 창업대출']). 최대 5개.",
    )
    key_insight: str = Field(
        ...,
        description="재무 분석의 핵심 인사이트 요약. 투자 대비 수익성과 재무 리스크.",
    )
    confidence_score: float = Field(
        ...,
        description="분석 결과 신뢰도 (0.0~1.0).",
        ge=0.0,
        le=1.0,
    )


# ================================================================
# 7. 리스크 분석 (RiskAnalysis)
# ================================================================

class RiskAnalysis(BaseModel):
    """
    리스크 분석 에이전트의 구조화된 출력.
    구조적, 규제적, 경쟁적, 환경적 리스크를 종합 평가한다.
    """
    overall_risk_score: float = Field(
        ...,
        description="종합 리스크 점수 (1.0~10.0). 10에 가까울수록 고위험.",
        ge=1.0,
        le=10.0,
    )
    risk_grade: str = Field(
        ...,
        description="리스크 등급 ('매우안전' | '안전' | '보통' | '위험' | '매우위험').",
    )
    risk_factors: list[RiskFactor] = Field(
        default_factory=list,
        description="식별된 전체 리스크 요인 목록. 심각도 순으로 정렬.",
    )
    structural_risks: list[str] = Field(
        default_factory=list,
        description="구조적 리스크 (시장 구조, 인구 변화, 경기 등). 최대 5개.",
    )
    regulatory_risks: list[str] = Field(
        default_factory=list,
        description="규제 리스크 (법규 변화, 인허가 난이도 등). 최대 5개.",
    )
    competitive_risks: list[str] = Field(
        default_factory=list,
        description="경쟁 리스크 (프랜차이즈 진입, 가격 경쟁 등). 최대 5개.",
    )
    environmental_risks: list[str] = Field(
        default_factory=list,
        description="환경적 리스크 (재개발, 교통 변화, 자연재해 등). 최대 5개.",
    )
    seasonal_vulnerability: float = Field(
        ...,
        description="계절 취약도 (0.0~1.0). 1에 가까울수록 계절에 따른 매출 변동 큼.",
        ge=0.0,
        le=1.0,
    )
    exit_difficulty: str = Field(
        ...,
        description="사업 철수 난이도 ('쉬움' | '보통' | '어려움'). 원상복구비, 권리금 회수 가능성 등 고려.",
    )
    key_warnings: list[str] = Field(
        default_factory=list,
        description="핵심 경고 사항. 사업 진입 전 반드시 인지해야 할 위험 요소. 최대 5개.",
    )
    confidence_score: float = Field(
        ...,
        description="분석 결과 신뢰도 (0.0~1.0).",
        ge=0.0,
        le=1.0,
    )


# ================================================================
# 8. 부동산 분석 (RealEstateAnalysis)
# ================================================================

class RealEstateAnalysis(BaseModel):
    """
    부동산 분석 에이전트의 구조화된 출력.
    임대료, 권리금, 공실률, 임대 시장 동향을 분석한다.
    """
    avg_rent_per_pyeong: int = Field(
        ...,
        description="평당 월 평균 임대료 (원/평). 해당 상권 1층 기준.",
    )
    rent_range: MoneyRange = Field(
        ...,
        description="평당 월 임대료 범위 (원/평). 층수, 위치에 따른 하한~상한.",
    )
    premium_avg: int = Field(
        ...,
        description="타겟 업종 평균 권리금 (원). 해당 상권 동일 업종 기준.",
    )
    premium_range: MoneyRange = Field(
        ...,
        description="권리금 범위 (원). 하한~상한.",
    )
    vacancy_rate: float = Field(
        ...,
        description="현재 공실률 (%). 해당 상권 내 비어있는 점포 비율.",
        ge=0.0,
        le=100.0,
    )
    vacancy_trend: TrendDirection = Field(
        ...,
        description="최근 6개월 공실률 추세.",
    )
    lease_term_avg: int = Field(
        ...,
        description="평균 임대 계약 기간 (개월).",
    )
    rent_increase_rate: float = Field(
        ...,
        description="연간 임대료 인상률 (%). 전년 대비.",
    )
    recommended_size: str = Field(
        ...,
        description="타겟 업종 권장 매장 크기 (예: '15~25평'). 업종 특성과 상권 여건 고려.",
    )
    available_properties: list[PropertyInfo] = Field(
        default_factory=list,
        description="현재 확인된 매물 리스트. 최대 10개.",
    )
    key_insight: str = Field(
        ...,
        description="부동산 분석의 핵심 인사이트 요약. 임대 시장 전망과 협상 전략.",
    )
    confidence_score: float = Field(
        ...,
        description="분석 결과 신뢰도 (0.0~1.0).",
        ge=0.0,
        le=1.0,
    )


# ================================================================
# 9. 규제 분석 (RegulatoryAnalysis)
# ================================================================

class RegulatoryAnalysis(BaseModel):
    """
    규제 분석 에이전트의 구조화된 출력.
    인허가, 용도지역, 위생/안전, 영업 제한, 향후 규제 변화를 분석한다.
    """
    required_permits: list[PermitRequirement] = Field(
        default_factory=list,
        description="필요한 인허가 목록. 각 인허가의 요건, 소요 기간, 비용 포함.",
    )
    zoning_status: str = Field(
        ...,
        description="현재 용도지역 상태 (예: '일반상업지역', '근린상업지역').",
    )
    zoning_restrictions: list[str] = Field(
        default_factory=list,
        description="용도지역 관련 제한 사항 (예: ['건축물 높이 제한 45m', '건폐율 80% 이하']). 최대 5개.",
    )
    health_safety_requirements: list[str] = Field(
        default_factory=list,
        description="위생/안전 관련 요구사항 (예: ['영업장 면적 66㎡ 이상', '환기시설 설치 필수']). 최대 10개.",
    )
    operating_hour_restrictions: Optional[str] = Field(
        None,
        description="영업시간 제한 사항 (예: '심야 영업 22시 이후 소음 규제 적용'). 없으면 None.",
    )
    alcohol_license_feasibility: str = Field(
        ...,
        description="주류 판매 허가 가능성 ('가능' | '조건부가능' | '불가'). 해당 없으면 '해당없음'.",
    )
    signage_regulations: list[str] = Field(
        default_factory=list,
        description="간판/광고물 관련 규제 (예: ['돌출간판 1개 제한', '네온사인 금지 구역']). 최대 5개.",
    )
    upcoming_regulation_changes: list[str] = Field(
        default_factory=list,
        description="향후 예정된 규제 변화 (예: ['2027년 1회용품 사용 전면 금지']). 최대 5개.",
    )
    compliance_difficulty: str = Field(
        ...,
        description="규제 준수 종합 난이도 ('쉬움' | '보통' | '어려움' | '매우어려움').",
    )
    estimated_permit_timeline: int = Field(
        ...,
        description="전체 인허가 완료 예상 소요 기간 (영업일 기준).",
    )
    key_insight: str = Field(
        ...,
        description="규제 분석의 핵심 인사이트 요약. 인허가 절차 핵심 포인트와 주의사항.",
    )
    confidence_score: float = Field(
        ...,
        description="분석 결과 신뢰도 (0.0~1.0).",
        ge=0.0,
        le=1.0,
    )
```

### 4.3 토론 모델

```python
# app/models/debate.py

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DebateArgument(BaseModel):
    """토론에서 하나의 주장/반론."""
    agent_role: str = Field(
        ...,
        description="발언자 역할 ('commander' | 'advocate' | 'critic' | 'judge').",
    )
    argument_type: str = Field(
        ...,
        description="주장 유형 ('briefing' | 'support' | 'critique' | 'rebuttal' | 'synthesis' | 'verdict').",
    )
    content: str = Field(
        ...,
        description="주장/반론 본문. Markdown 형식.",
    )
    evidence_references: list[str] = Field(
        default_factory=list,
        description="근거로 인용한 에이전트 분석 결과 또는 데이터 출처 (예: ['population_result.total_floating_population', 'revenue_result.revenue_trend']).",
    )
    confidence: float = Field(
        ...,
        description="해당 주장에 대한 발언자의 확신도 (0.0~1.0).",
        ge=0.0,
        le=1.0,
    )
    counterpoints: list[str] = Field(
        default_factory=list,
        description="이 주장이 반박하는 이전 논점 목록.",
    )
    timestamp: str = Field(
        ...,
        description="발언 시각 (ISO 8601).",
    )


class DebateRound(BaseModel):
    """토론 1라운드의 전체 기록."""
    round_number: int = Field(
        ...,
        description="라운드 번호 (1부터 시작).",
        ge=1,
    )
    topic: str = Field(
        ...,
        description="해당 라운드의 토론 주제 (예: '해당 상권의 삼겹살집 투자 적합성').",
    )
    advocate_argument: DebateArgument = Field(
        ...,
        description="옹호자(Advocate)의 긍정적 주장.",
    )
    critic_argument: DebateArgument = Field(
        ...,
        description="비평가(Critic)의 부정적 주장/반론.",
    )
    advocate_rebuttal: Optional[DebateArgument] = Field(
        None,
        description="옹호자의 재반박 (해당 라운드에서 진행된 경우).",
    )
    critic_rebuttal: Optional[DebateArgument] = Field(
        None,
        description="비평가의 재반박 (해당 라운드에서 진행된 경우).",
    )
    round_summary: Optional[str] = Field(
        None,
        description="사령관이 작성한 라운드 요약.",
    )


class DebateResult(BaseModel):
    """토론 최종 결과 (판사 판정)."""
    overall_verdict: str = Field(
        ...,
        description="종합 판정 ('강력추천' | '추천' | '조건부추천' | '보류' | '비추천').",
    )
    verdict_summary: str = Field(
        ...,
        description="판정 요약. 3~5문장으로 핵심 근거와 결론.",
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="토론에서 도출된 주요 강점 (사업 기회). 최대 7개.",
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="토론에서 도출된 주요 약점 (사업 위험). 최대 7개.",
    )
    conditions_for_success: list[str] = Field(
        default_factory=list,
        description="성공을 위한 필수 조건 (예: ['차별화된 메뉴 구성 필수', '초기 6개월 마케팅 집중 투자']). 최대 5개.",
    )
    unresolved_concerns: list[str] = Field(
        default_factory=list,
        description="토론에서 해결되지 않은 우려 사항. 최대 5개.",
    )
    advocate_score: float = Field(
        ...,
        description="옹호자 주장의 설득력 점수 (0.0~10.0).",
        ge=0.0,
        le=10.0,
    )
    critic_score: float = Field(
        ...,
        description="비평가 주장의 설득력 점수 (0.0~10.0).",
        ge=0.0,
        le=10.0,
    )
    consensus_level: float = Field(
        ...,
        description="토론 참가자 간 합의 수준 (0.0~1.0). 1이면 완전 합의.",
        ge=0.0,
        le=1.0,
    )
    total_debate_rounds: int = Field(
        ...,
        description="실제 진행된 토론 라운드 수.",
    )
    judge_confidence: float = Field(
        ...,
        description="판사의 판정 확신도 (0.0~1.0).",
        ge=0.0,
        le=1.0,
    )
```

### 4.4 최종 리포트 모델

```python
# app/models/report.py

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.agent_outputs import (
    CompetitionAnalysis,
    FinancialAnalysis,
    LocationAnalysis,
    PopulationAnalysis,
    RealEstateAnalysis,
    RegulatoryAnalysis,
    RevenueAnalysis,
    RiskAnalysis,
    TrendAnalysis,
)
from app.models.debate import DebateResult


class ExecutiveSummary(BaseModel):
    """경영진 요약 (리포트 최상단)."""
    headline: str = Field(
        ...,
        description="한 줄 헤드라인 (예: '강남역 삼겹살 전문점 - 조건부 추천, 차별화 전략 필수').",
    )
    overall_score: float = Field(
        ...,
        description="종합 점수 (0.0~100.0). 모든 분석과 토론 결과를 종합한 단일 점수.",
        ge=0.0,
        le=100.0,
    )
    overall_grade: str = Field(
        ...,
        description="종합 등급 ('S' | 'A' | 'B' | 'C' | 'D' | 'F').",
    )
    recommendation: str = Field(
        ...,
        description="최종 추천 의견 ('강력추천' | '추천' | '조건부추천' | '보류' | '비추천').",
    )
    key_findings: list[str] = Field(
        default_factory=list,
        description="핵심 발견 사항. 5~7개의 불릿 포인트.",
    )
    critical_actions: list[str] = Field(
        default_factory=list,
        description="즉시 실행해야 할 핵심 조치 사항. 3~5개.",
    )
    summary_paragraph: str = Field(
        ...,
        description="종합 요약문. 5~10문장으로 분석 결과, 기회, 위험, 권고사항을 아우르는 내러티브.",
    )


class ScoreBreakdown(BaseModel):
    """항목별 점수 분해."""
    population_score: float = Field(..., description="유동인구 점수 (0~100)", ge=0, le=100)
    revenue_score: float = Field(..., description="매출 전망 점수 (0~100)", ge=0, le=100)
    competition_score: float = Field(..., description="경쟁 환경 점수 (0~100)", ge=0, le=100)
    location_score: float = Field(..., description="입지 점수 (0~100)", ge=0, le=100)
    trend_score: float = Field(..., description="트렌드 점수 (0~100)", ge=0, le=100)
    financial_score: float = Field(..., description="재무 점수 (0~100)", ge=0, le=100)
    risk_score: float = Field(..., description="리스크 점수 (0~100, 낮을수록 위험)", ge=0, le=100)
    real_estate_score: float = Field(..., description="부동산 점수 (0~100)", ge=0, le=100)
    regulatory_score: float = Field(..., description="규제 점수 (0~100, 높을수록 유리)", ge=0, le=100)


class FinalReport(BaseModel):
    """
    MarketScope AI 최종 분석 리포트.
    모든 에이전트의 분석 결과, 토론 결과, 종합 판단을 하나로 종합한다.
    """

    # ---- 메타 정보 ----
    report_id: str = Field(..., description="리포트 고유 ID (UUID v4).")
    request_id: str = Field(..., description="원본 분석 요청 ID.")
    generated_at: str = Field(..., description="리포트 생성 시각 (ISO 8601).")
    report_version: str = Field(default="1.0", description="리포트 형식 버전.")

    # ---- 분석 대상 정보 ----
    district_name: str = Field(..., description="분석 대상 상권명.")
    industry_category: str = Field(..., description="대분류 업종.")
    industry_subcategory: str = Field(..., description="중분류 업종.")
    industry_detail: Optional[str] = Field(None, description="소분류 업종.")

    # ---- 경영진 요약 ----
    executive_summary: ExecutiveSummary = Field(..., description="경영진 요약.")

    # ---- 항목별 점수 ----
    score_breakdown: ScoreBreakdown = Field(..., description="항목별 점수 분해.")

    # ---- 개별 에이전트 분석 결과 (원본 전체 포함) ----
    population_result: Optional[PopulationAnalysis] = Field(None, description="유동인구 분석 전문.")
    revenue_result: Optional[RevenueAnalysis] = Field(None, description="매출 분석 전문.")
    competition_result: Optional[CompetitionAnalysis] = Field(None, description="경쟁 분석 전문.")
    location_result: Optional[LocationAnalysis] = Field(None, description="입지 분석 전문.")
    trend_result: Optional[TrendAnalysis] = Field(None, description="[Phase 2] 트렌드 분석 전문.")
    financial_result: Optional[FinancialAnalysis] = Field(None, description="[Phase 2] 재무 분석 전문.")
    risk_analysis: Optional[RiskAnalysis] = Field(None, description="리스크 분석 전문.")
    real_estate_analysis: Optional[RealEstateAnalysis] = Field(None, description="부동산 분석 전문.")
    regulatory_analysis: Optional[RegulatoryAnalysis] = Field(None, description="규제 분석 전문.")

    # ---- 토론 결과 ----
    debate_result: Optional[DebateResult] = Field(None, description="토론 최종 결과.")

    # ---- 내러티브 리포트 ----
    narrative_report: str = Field(
        ...,
        description="사람이 읽기 쉬운 내러티브 형식의 전체 분석 리포트. Markdown 형식.",
    )

    # ---- 실행 통계 ----
    total_execution_time_seconds: float = Field(..., description="전체 분석 소요 시간 (초).")
    total_llm_calls: int = Field(..., description="전체 LLM 호출 횟수.")
    total_tokens_used: int = Field(..., description="전체 사용 토큰 수 (prompt + completion).")
    total_cost_krw: int = Field(0, description="추정 총 비용 (원).")
    agents_succeeded: int = Field(..., description="성공한 에이전트 수.")
    agents_failed: int = Field(0, description="실패한 에이전트 수.")
    data_sources_used: list[str] = Field(
        default_factory=list,
        description="분석에 사용된 데이터 소스 목록 (예: ['서울 유동인구 API', '소상공인 매출 데이터']).",
    )

    # ---- 면책 조항 ----
    disclaimer: str = Field(
        default=(
            "본 리포트는 AI 기반 자동 분석 결과이며, 투자 결정의 유일한 근거로 사용해서는 안 됩니다. "
            "실제 사업 시작 전 전문가 상담 및 현장 조사를 반드시 병행하시기 바랍니다. "
            "분석에 사용된 데이터는 공공 데이터 및 추정치를 포함하고 있어 실제 수치와 차이가 있을 수 있습니다."
        ),
        description="리포트 하단에 표시되는 면책 조항.",
    )
```

---

## 5. 에러 처리 전략

### 5.1 커스텀 예외 계층

```python
# app/exceptions.py

from __future__ import annotations

from typing import Any, Optional


class MarketScopeError(Exception):
    """MarketScope AI 최상위 예외 클래스."""

    def __init__(self, message: str = "", details: Optional[dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


# ================================================================
# 에이전트 관련 예외
# ================================================================

class AgentError(MarketScopeError):
    """에이전트 관련 최상위 예외."""

    def __init__(
        self,
        agent_name: str,
        message: str = "",
        original_error: Optional[Exception] = None,
        is_critical: bool = False,
    ):
        self.agent_name = agent_name
        self.original_error = original_error
        self.is_critical = is_critical
        full_message = f"[{agent_name}] {message}"
        if original_error:
            full_message += f" (원인: {type(original_error).__name__}: {original_error})"
        super().__init__(full_message)


class AgentExecutionError(AgentError):
    """에이전트 실행 중 복구 불가능한 에러."""
    pass


class AgentTimeoutError(AgentError):
    """에이전트 실행 타임아웃."""

    def __init__(self, agent_name: str, timeout_seconds: int):
        super().__init__(
            agent_name=agent_name,
            message=f"실행 타임아웃 ({timeout_seconds}초 초과)",
            is_critical=False,
        )
        self.timeout_seconds = timeout_seconds


# ================================================================
# LLM 관련 예외
# ================================================================

class LLMError(MarketScopeError):
    """LLM 호출 관련 최상위 예외."""
    pass


class LLMCallError(LLMError):
    """LLM API 호출 실패 (재시도 후에도)."""

    def __init__(
        self,
        agent_name: str,
        model: str,
        original_error: Optional[Exception] = None,
        attempts: int = 1,
    ):
        self.agent_name = agent_name
        self.model = model
        self.original_error = original_error
        self.attempts = attempts
        message = (
            f"[{agent_name}] LLM 호출 실패 (모델: {model}, 시도: {attempts}회)"
        )
        if original_error:
            message += f" - {type(original_error).__name__}: {original_error}"
        super().__init__(message)


class LLMRateLimitError(LLMError):
    """LLM API 요청 제한 초과."""

    def __init__(self, model: str, retry_after: Optional[int] = None):
        self.model = model
        self.retry_after = retry_after
        message = f"LLM 요청 제한 초과 (모델: {model})"
        if retry_after:
            message += f" - {retry_after}초 후 재시도 가능"
        super().__init__(message)


class OutputParsingError(MarketScopeError):
    """LLM 응답의 구조화된 출력 파싱 실패."""

    def __init__(
        self,
        agent_name: str,
        model_class: str,
        raw_content: str = "",
    ):
        self.agent_name = agent_name
        self.model_class = model_class
        self.raw_content = raw_content
        super().__init__(
            f"[{agent_name}] 출력 파싱 실패 (대상 모델: {model_class}). "
            f"원본 응답 앞부분: {raw_content[:200]}..."
        )


# ================================================================
# MCP 도구 관련 예외
# ================================================================

class MCPError(MarketScopeError):
    """MCP 도구 호출 관련 최상위 예외."""
    pass


class MCPToolCallError(MCPError):
    """MCP 도구 호출 실패."""

    def __init__(
        self,
        agent_name: str,
        tool_name: str,
        message: str = "",
        original_error: Optional[Exception] = None,
    ):
        self.agent_name = agent_name
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f"[{agent_name}] MCP 도구 '{tool_name}' 호출 실패: {message}")


class MCPConnectionError(MCPError):
    """MCP 서버 연결 실패."""

    def __init__(self, server_url: str, message: str = ""):
        self.server_url = server_url
        super().__init__(f"MCP 서버 연결 실패 ({server_url}): {message}")


# ================================================================
# 데이터 관련 예외
# ================================================================

class DataError(MarketScopeError):
    """데이터 접근/처리 관련 최상위 예외."""
    pass


class DataSourceUnavailableError(DataError):
    """외부 데이터 소스 접근 불가."""

    def __init__(self, source_name: str, message: str = ""):
        self.source_name = source_name
        super().__init__(f"데이터 소스 '{source_name}' 접근 불가: {message}")


class InsufficientDataError(DataError):
    """분석에 필요한 최소 데이터가 부족."""

    def __init__(self, agent_name: str, missing_data: list[str]):
        self.agent_name = agent_name
        self.missing_data = missing_data
        super().__init__(
            f"[{agent_name}] 필요 데이터 부족: {', '.join(missing_data)}"
        )


# ================================================================
# 메모리 관련 예외
# ================================================================

class MemoryError(MarketScopeError):
    """ReMe 메모리 시스템 관련 예외."""
    pass


class MemoryStorageError(MemoryError):
    """메모리 저장 실패."""
    pass


class MemoryRetrievalError(MemoryError):
    """메모리 검색 실패."""
    pass


# ================================================================
# 워크플로우 관련 예외
# ================================================================

class WorkflowError(MarketScopeError):
    """워크플로우 실행 관련 예외."""
    pass


class WorkflowTimeoutError(WorkflowError):
    """전체 워크플로우 타임아웃."""

    def __init__(self, timeout_seconds: int, completed_agents: list[str]):
        self.timeout_seconds = timeout_seconds
        self.completed_agents = completed_agents
        super().__init__(
            f"워크플로우 타임아웃 ({timeout_seconds}초). "
            f"완료된 에이전트: {', '.join(completed_agents) or '없음'}"
        )


class CriticalAgentFailureError(WorkflowError):
    """핵심 에이전트 실패로 워크플로우 진행 불가."""

    def __init__(self, failed_agents: list[str]):
        self.failed_agents = failed_agents
        super().__init__(
            f"핵심 에이전트 실패로 분석 중단: {', '.join(failed_agents)}"
        )


# ================================================================
# 인증/인가 관련 예외
# ================================================================

class AuthError(MarketScopeError):
    """인증/인가 관련 예외."""
    pass


class FallbackTriggeredError(MarketScopeError):
    """폴백이 트리거되었음을 알리는 정보성 예외. 로깅 목적."""

    def __init__(self, agent_name: str, reason: str, fallback_type: str):
        self.agent_name = agent_name
        self.reason = reason
        self.fallback_type = fallback_type
        super().__init__(
            f"[{agent_name}] 폴백 적용됨 (유형: {fallback_type}, 사유: {reason})"
        )
```

### 5.2 폴백 동작 정책

| 에러 유형 | 폴백 동작 | 워크플로우 영향 |
|---|---|---|
| `LLMCallError` (단일 에이전트) | 기본값 모델 반환 + confidence=0.0 | 계속 진행, 해당 분석 결과 저품질 표시 |
| `LLMRateLimitError` | 대체 모델로 폴백 (Gemini ↔ Claude) | 계속 진행 |
| `MCPToolCallError` | 캐시 데이터 사용 또는 해당 데이터 없이 분석 | 계속 진행 |
| `OutputParsingError` | 비구조화 텍스트에서 핵심 필드만 추출 시도 | 계속 진행 |
| `AgentTimeoutError` | 부분 결과 반환 또는 기본값 | 계속 진행 |
| `DataSourceUnavailableError` | 캐시/대체 데이터 소스 사용 | 계속 진행, 신뢰도 하향 |
| `InsufficientDataError` | 가용 데이터로만 분석 + 한계 명시 | 계속 진행, 신뢰도 하향 |
| 5개 이상 에이전트 실패 | `CriticalAgentFailureError` 발생 | **중단**, 부분 리포트 + 사유 반환 |
| `WorkflowTimeoutError` | 완료된 에이전트 결과로 부분 리포트 생성 | 부분 완료 상태로 종료 |

### 5.3 LLM 폴백 체인

```python
# app/agents/base.py 내부 또는 별도 유틸

LLM_FALLBACK_CHAINS: dict[str, list[str]] = {
    # 원본 모델 -> 폴백 1 -> 폴백 2
    "claude-opus-4-6-20250319": [
        "claude-sonnet-4-6-20250514",
        "gemini/gemini-2.5-pro",
    ],
    "claude-sonnet-4-6-20250514": [
        "gemini/gemini-2.5-pro",
        "gemini/gemini-2.5-flash",
    ],
    "gemini/gemini-2.5-pro": [
        "claude-sonnet-4-6-20250514",
        "gemini/gemini-2.5-flash",
    ],
    "gemini/gemini-2.5-flash": [
        "gemini/gemini-2.5-pro",
        "claude-sonnet-4-6-20250514",
    ],
}
```

---

## 6. 로깅 및 모니터링

### 6.1 구조화된 로깅 설정

```python
# app/logging_config.py

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict

from app.config import AppEnvironment, LogLevel


def setup_logging(app_env: AppEnvironment, log_level: LogLevel) -> None:
    """
    structlog 기반 구조화된 로깅을 초기화한다.

    - development: 컬러 콘솔 출력 (사람이 읽기 쉬운 포맷).
    - staging/production: JSON 라인 출력 (로그 수집기 파싱용).
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _add_app_context,
    ]

    if app_env == AppEnvironment.DEVELOPMENT:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)

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

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.value)

    # 외부 라이브러리 로그 레벨 조정
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """모든 로그 이벤트에 앱 컨텍스트를 추가한다."""
    event_dict["service"] = "marketscope-ai"
    return event_dict


def get_agent_logger(agent_name: str) -> structlog.stdlib.BoundLogger:
    """
    에이전트 전용 로거를 생성한다.
    agent_name이 자동으로 모든 로그 이벤트에 바인딩된다.
    """
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(f"agent.{agent_name}")
    return logger.bind(agent_name=agent_name)


def get_service_logger(service_name: str) -> structlog.stdlib.BoundLogger:
    """서비스 계층 전용 로거."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(f"service.{service_name}")
    return logger.bind(service=service_name)
```

### 6.2 로그 이벤트 스키마

모든 구조화된 로그 이벤트는 아래 기본 필드를 포함한다.

```json
{
    "timestamp": "2026-03-19T12:34:56.789Z",
    "level": "info",
    "service": "marketscope-ai",
    "logger": "agent.population",
    "event": "LLM 호출 성공",
    "agent_name": "population",
    "model": "gemini/gemini-2.5-flash",
    "attempt": 1,
    "latency_ms": 2345.67,
    "prompt_tokens": 1500,
    "completion_tokens": 800,
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

주요 로그 이벤트 카탈로그:

| 이벤트 | 레벨 | 필수 필드 |
|---|---|---|
| `에이전트 실행 시작` | INFO | `agent_name` |
| `에이전트 실행 완료` | INFO | `agent_name`, `duration_seconds`, `confidence_score` |
| `에이전트 실행 에러` | ERROR | `agent_name`, `error_type`, `error_message`, `traceback` |
| `LLM 호출 성공` | INFO | `agent_name`, `model`, `latency_ms`, `prompt_tokens`, `completion_tokens` |
| `LLM 호출 실패` | WARNING | `agent_name`, `model`, `attempt`, `error` |
| `LLM 폴백 적용` | WARNING | `agent_name`, `original_model`, `fallback_model` |
| `MCP 도구 호출 성공` | INFO | `agent_name`, `tool_name` |
| `MCP 도구 호출 실패` | ERROR | `agent_name`, `tool_name`, `error` |
| `출력 파싱 실패` | WARNING | `agent_name`, `model_class`, `raw_content_preview` |
| `토론 라운드 완료` | INFO | `round_number`, `advocate_confidence`, `critic_confidence` |
| `워크플로우 시작` | INFO | `request_id`, `district_name`, `industry` |
| `워크플로우 완료` | INFO | `request_id`, `total_duration`, `agents_succeeded`, `agents_failed` |
| `폴백 결과 적용` | WARNING | `agent_name`, `fallback_type`, `reason` |

### 6.3 Langfuse 통합

```python
# app/monitoring/langfuse_setup.py

from __future__ import annotations

from typing import Optional

from langfuse import Langfuse
from langfuse.callback import CallbackHandler as LangfuseCallbackHandler

from app.config import Settings


class LangfuseManager:
    """Langfuse 모니터링 관리자."""

    _instance: Optional[Langfuse] = None

    @classmethod
    def initialize(cls, settings: Settings) -> Optional[Langfuse]:
        """Langfuse 클라이언트를 초기화한다."""
        if not settings.langfuse_enabled:
            return None

        cls._instance = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            flush_at=settings.langfuse_flush_at,
            flush_interval=settings.langfuse_flush_interval,
        )
        return cls._instance

    @classmethod
    def get_instance(cls) -> Optional[Langfuse]:
        return cls._instance

    @classmethod
    def create_trace(
        cls,
        name: str,
        request_id: str,
        metadata: Optional[dict] = None,
    ):
        """
        새 Langfuse 트레이스를 생성한다.

        사용 시점:
        - 분석 요청 시작 시 1개의 트레이스 생성
        - 트레이스 하위에 각 에이전트가 span으로 기록
        """
        if cls._instance is None:
            return None

        return cls._instance.trace(
            name=name,
            id=request_id,
            metadata=metadata or {},
        )

    @classmethod
    def create_callback_handler(
        cls,
        trace_id: str,
        agent_name: str,
    ) -> Optional[LangfuseCallbackHandler]:
        """
        LiteLLM과 연동할 Langfuse 콜백 핸들러를 생성한다.

        LiteLLM의 success_callback / failure_callback에 등록하여
        모든 LLM 호출의 입력/출력/토큰/비용이 자동으로 Langfuse에 기록된다.
        """
        if cls._instance is None:
            return None

        return LangfuseCallbackHandler(
            trace_id=trace_id,
            span_name=f"agent_{agent_name}",
            public_key=cls._instance.public_key,
            secret_key=cls._instance.secret_key,
            host=cls._instance.host,
        )

    @classmethod
    def shutdown(cls) -> None:
        """남은 이벤트를 플러시하고 종료한다."""
        if cls._instance:
            cls._instance.flush()
            cls._instance.shutdown()
```

Langfuse 트레이싱 구조 (분석 요청 1건 기준):

```
Trace: "analysis_강남역_삼겹살" (request_id)
├── Span: "phase_data_collection"
├── Span: "phase_parallel_analysis"
│   ├── Span: "agent_population"
│   │   ├── Generation: "llm_call_1" (시스템+유저 프롬프트 → 구조화된 출력)
│   │   └── Span: "mcp_tool_search_floating_pop"
│   ├── Span: "agent_revenue"
│   │   └── Generation: "llm_call_1"
│   ├── Span: "agent_competition"
│   │   └── ...
│   └── ... (9개 에이전트 병렬)
├── Span: "phase_debate"
│   ├── Span: "agent_commander"
│   │   └── Generation: "briefing"
│   ├── Span: "debate_round_1"
│   │   ├── Generation: "advocate_argument"
│   │   └── Generation: "critic_argument"
│   ├── Span: "debate_round_2"
│   └── Span: "agent_judge"
│       └── Generation: "verdict"
└── Span: "phase_report_generation"
    └── Generation: "narrative_report"
```

---

## 7. 상수 및 열거형

```python
# app/constants.py

from __future__ import annotations

from enum import Enum


# ================================================================
# 1. 신뢰도 수준
# ================================================================

class ConfidenceLevel(str, Enum):
    """분석 결과 신뢰도 등급."""
    VERY_HIGH = "매우높음"       # 0.85 이상
    HIGH = "높음"                # 0.70 ~ 0.84
    MEDIUM = "보통"              # 0.55 ~ 0.69
    LOW = "낮음"                 # 0.40 ~ 0.54
    VERY_LOW = "매우낮음"        # 0.39 이하


# ================================================================
# 2. 리스크 등급
# ================================================================

class RiskGrade(str, Enum):
    """리스크 종합 등급."""
    VERY_SAFE = "매우안전"       # 1.0 ~ 2.5
    SAFE = "안전"                # 2.6 ~ 4.0
    MODERATE = "보통"            # 4.1 ~ 5.5
    RISKY = "위험"               # 5.6 ~ 7.5
    VERY_RISKY = "매우위험"      # 7.6 ~ 10.0


# ================================================================
# 3. 상권 등급
# ================================================================

class DistrictGrade(str, Enum):
    """상권/입지 종합 등급."""
    S = "S"   # 최우수 (상위 5%)
    A = "A"   # 우수 (상위 20%)
    B = "B"   # 양호 (상위 50%)
    C = "C"   # 보통 (하위 50%)
    D = "D"   # 미흡 (하위 20%)
    F = "F"   # 부적합 (하위 5%)


# ================================================================
# 4. 경쟁 위협 수준
# ================================================================

class CompetitiveThreatLevel(str, Enum):
    """경쟁 위협 수준."""
    VERY_LOW = "매우낮음"
    LOW = "낮음"
    MODERATE = "보통"
    HIGH = "높음"
    VERY_HIGH = "매우높음"


# ================================================================
# 5. 업종 생애주기 단계
# ================================================================

class IndustryLifecycleStage(str, Enum):
    """업종 생애주기."""
    INTRODUCTION = "도입기"
    GROWTH = "성장기"
    MATURITY = "성숙기"
    DECLINE = "쇠퇴기"


# ================================================================
# 6. 투자 추천 등급
# ================================================================

class RecommendationGrade(str, Enum):
    """최종 투자 추천 등급."""
    STRONGLY_RECOMMENDED = "강력추천"
    RECOMMENDED = "추천"
    CONDITIONALLY_RECOMMENDED = "조건부추천"
    HOLD = "보류"
    NOT_RECOMMENDED = "비추천"


# ================================================================
# 7. 워크플로우 상태
# ================================================================

class WorkflowStatus(str, Enum):
    """워크플로우 실행 상태."""
    INITIALIZED = "initialized"
    ANALYZING = "analyzing"
    # DEBATING = "debating"       # [Phase 2] Debate 미구현
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"


class WorkflowPhase(str, Enum):
    """워크플로우 단계 (Phase 1 기준)."""
    DATA_COLLECTION = "data_collection"     # Commander 계획 수립
    PARALLEL_ANALYSIS = "parallel_analysis" # 4개 에이전트 병렬 실행
    # DEBATE = "debate"                     # [Phase 2] Debate 미구현
    SYNTHESIS = "synthesis"                 # Commander 최종 판단
    REPORT_GENERATION = "report_generation" # 리포트 생성


# ================================================================
# 8. 에이전트 실행 상태
# ================================================================

class AgentStatus(str, Enum):
    """개별 에이전트 실행 상태."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ================================================================
# 9. 토론 역할
# ================================================================

class DebateRole(str, Enum):
    """토론 참가자 역할."""
    COMMANDER = "commander"    # 사령관: 분석 요약 및 토론 조율
    ADVOCATE = "advocate"      # 옹호자: 긍정적 논거 제시
    CRITIC = "critic"          # 비평가: 부정적 논거 / 반론 제시
    JUDGE = "judge"            # 판사: 최종 판정


class DebateArgumentType(str, Enum):
    """토론 주장 유형."""
    BRIEFING = "briefing"      # 사령관 브리핑
    SUPPORT = "support"        # 옹호 주장
    CRITIQUE = "critique"      # 비판 주장
    REBUTTAL = "rebuttal"      # 재반박
    SYNTHESIS = "synthesis"    # 종합
    VERDICT = "verdict"        # 판결


# ================================================================
# 10. 업종 분류 코드 (소상공인시장진흥공단 기준, 주요 분류만 포함)
# ================================================================

class IndustryMajorCategory(str, Enum):
    """업종 대분류."""
    FOOD = "음식"
    RETAIL = "소매"
    SERVICE = "서비스"
    EDUCATION = "교육"
    MEDICAL = "의료"
    LEISURE = "여가/오락"
    ACCOMMODATION = "숙박"


# 업종 중분류 매핑 (대분류 -> 중분류 리스트)
INDUSTRY_SUBCATEGORIES: dict[str, list[str]] = {
    "음식": [
        "한식", "중식", "일식", "양식", "분식", "치킨", "피자",
        "패스트푸드", "카페/디저트", "주점", "뷔페", "배달전문",
        "동남아/인도음식", "멕시칸/남미음식", "퓨전음식", "기타음식",
    ],
    "소매": [
        "편의점", "슈퍼마켓", "의류", "화장품", "전자기기",
        "문구/완구", "약국", "반려동물용품", "꽃/원예",
        "주류판매", "건강식품", "기타소매",
    ],
    "서비스": [
        "미용실", "네일/피부관리", "세탁", "수리/정비",
        "부동산중개", "법률/세무", "사진/인화", "인력파견",
        "반려동물서비스", "기타서비스",
    ],
    "교육": [
        "학원(입시)", "학원(예체능)", "학원(외국어)",
        "학원(컴퓨터/IT)", "독서실/스터디카페", "기타교육",
    ],
    "의료": [
        "병원/의원", "치과", "한의원", "약국", "안경점",
        "동물병원", "기타의료",
    ],
    "여가/오락": [
        "PC방", "노래방", "당구장", "볼링장", "헬스장",
        "요가/필라테스", "골프연습장", "스크린골프",
        "방탈출/VR", "기타여가",
    ],
    "숙박": [
        "호텔", "모텔", "게스트하우스", "펜션", "기타숙박",
    ],
}


# ================================================================
# 11. LLM 모델 매핑 상수
# ================================================================

class LLMProvider(str, Enum):
    """LLM 제공자."""
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OPENAI = "openai"


# 모델별 가격 (1K 토큰 기준, 원화, 2026.03 기준 추정치)
LLM_PRICING_KRW_PER_1K_TOKENS: dict[str, dict[str, float]] = {
    "claude-opus-4-6-20250319": {
        "prompt": 21.0,         # $15 / 1M tokens * 1400 KRW/USD
        "completion": 105.0,    # $75 / 1M tokens * 1400 KRW/USD
    },
    "claude-sonnet-4-6-20250514": {
        "prompt": 4.2,          # $3 / 1M tokens
        "completion": 21.0,     # $15 / 1M tokens
    },
    "gemini/gemini-2.5-pro": {
        "prompt": 1.75,         # $1.25 / 1M tokens
        "completion": 14.0,     # $10 / 1M tokens
    },
    "gemini/gemini-2.5-flash": {
        "prompt": 0.105,        # $0.075 / 1M tokens
        "completion": 0.42,     # $0.30 / 1M tokens
    },
}


# ================================================================
# 12. 에이전트 역할별 LLM 할당 요약
# ================================================================

AGENT_LLM_ASSIGNMENTS: dict[str, str] = {
    # ── [Phase 1] 활성 에이전트 ──
    # Commander 다운그레이드: Opus → Sonnet (비용 ~80% 절감)
    "commander": "claude-sonnet-4-6-20250514",
    # 4개 전문 에이전트: Gemini Flash (저렴 + 충분한 성능)
    "population": "gemini/gemini-2.5-flash",
    "revenue": "gemini/gemini-2.5-flash",
    "competition": "gemini/gemini-2.5-flash",
    "location": "gemini/gemini-2.5-flash",
    # 리포트 에이전트: Gemini Flash
    "narrative": "gemini/gemini-2.5-flash",
    "visualization": "gemini/gemini-2.5-flash",

    # ── [Phase 2] 비활성 에이전트 ──
    # "judge": "claude-opus-4-6-20250319",
    # "critic": "claude-sonnet-4-6-20250514",
    # "advocate": "gemini/gemini-2.5-flash",
    # "financial": "claude-sonnet-4-6-20250514",
    # "risk": "claude-sonnet-4-6-20250514",
    # "regulatory": "claude-sonnet-4-6-20250514",
    # "real_estate": "gemini/gemini-2.5-flash",
    # "trend": "gemini/gemini-2.5-pro",
}


# ================================================================
# 13. 기타 상수
# ================================================================

# 기본 분석 반경 (미터)
DEFAULT_ANALYSIS_RADIUS_METERS: int = 500

# ================================================================
# Phase 1 제약 상수
# ================================================================

# Phase 1: 서울 허용 상권 목록 (순차적으로 확장 예정)
PHASE1_ALLOWED_DISTRICTS: list[str] = [
    "강남", "홍대", "이태원", "건대", "신촌",
    "종로", "명동", "여의도", "성수", "잠실",
]

# Phase 1: 활성 에이전트 목록 (4개 고정)
PHASE1_ACTIVE_AGENTS: list[str] = [
    "population", "revenue", "competition", "location",
]

# Phase 1: 비용 목표 (분석 1건당 $2 이하)
# Gemini Flash 기준: 4 에이전트 × 평균 15K 토큰 + Commander Sonnet 8K ≈ $0.8~1.5
PHASE1_COST_TARGET_USD: float = 2.0

# Phase 1: 분석 완료 목표 시간 (초)
PHASE1_TARGET_DURATION_SEC: int = 180   # 3분 이내

# ================================================================
# 법적 면책 상수
# ================================================================

# 모든 리포트 하단에 반드시 포함되는 면책 조항
LEGAL_DISCLAIMER: str = (
    "본 분석 결과는 AI가 공공 데이터를 바탕으로 생성한 참고 정보이며, "
    "실제 투자·창업 의사결정의 근거로 단독 사용하지 마십시오. "
    "공공 데이터 특성상 최대 6개월의 시차가 있을 수 있으며, "
    "MarketScope AI는 본 분석 결과의 정확성 및 완전성을 보증하지 않습니다. "
    "최종 의사결정 전 전문가(공인중개사, 세무사, 경영 컨설턴트 등)와 반드시 상담하시기 바랍니다."
)

# 금융 관련 분석 추가 면책 (재무 에이전트 활성화 시 — Phase 2)
FINANCIAL_DISCLAIMER: str = (
    "본 수익성 분석 및 ROI 추정은 금융투자 자문에 해당하지 않으며, "
    "여신금융업법 및 자본시장법상 규제 대상 서비스가 아닙니다."
)

# 상권 분석 시 최소 필요 에이전트 수 (이 수 미만 성공 시 분석 실패)
MIN_REQUIRED_AGENTS_FOR_REPORT: int = 3  # Phase 1: 4개 중 최소 3개 성공

# 리포트 생성에 필수적인 에이전트 (이 중 하나라도 실패 시 분석 중단 고려)
CRITICAL_AGENTS: list[str] = [
    "population",
    "competition",
]

# [Phase 2] 토론 주제 템플릿
# DEBATE_TOPIC_TEMPLATE: str = (
#     "{district_name} 상권에서 {industry_detail} 업종의 "
#     "창업 투자 적합성에 대한 종합 평가"
# )

# 평(坪)을 제곱미터로 변환하는 계수
PYEONG_TO_SQM: float = 3.305785

# API 기본 페이지 크기
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100
```

---

## 부록: 구현 체크리스트

아래 항목을 순서대로 구현하면 프로젝트 기반 구조가 완성된다.

- [ ] `app/config.py` - Settings 클래스 및 get_settings()
- [ ] `app/constants.py` - 모든 Enum 및 상수
- [ ] `app/exceptions.py` - 커스텀 예외 계층
- [ ] `app/logging_config.py` - structlog 초기화
- [ ] `app/models/common.py` - 공통 재사용 Pydantic 모델
- [ ] `app/models/agent_outputs.py` - 9개 에이전트 출력 모델
- [ ] `app/models/debate.py` - 토론 관련 모델
- [ ] `app/models/report.py` - 최종 리포트 모델
- [ ] `app/models/state.py` - LangGraph 상태 TypedDict + 초기화 함수
- [ ] `app/agents/base.py` - BaseAgent 추상 클래스
- [ ] `app/monitoring/langfuse_setup.py` - Langfuse 통합
- [ ] `.env.example` - 환경 변수 템플릿
- [ ] `pyproject.toml` - 의존성 정의
- [ ] 유닛 테스트: Settings 로딩, Pydantic 모델 직렬화/역직렬화, 예외 계층 검증
