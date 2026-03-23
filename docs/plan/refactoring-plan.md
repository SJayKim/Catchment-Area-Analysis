# MarketScope AI 서비스 분리 리팩토링 계획

## 1. 현재 상태 분석

### 1.1 현재 구조
```
marketscope/app/        (141 Python files, 단일 패키지)
├── main.py             # FastAPI 엔트리포인트
├── config.py           # 전역 설정
├── constants.py        # 상수 정의
├── exceptions.py       # 커스텀 예외
├── logging_config.py   # 로깅 설정
│
├── api/                # REST API 라우트
│   ├── routes/analysis.py
│   ├── routes/health.py
│   └── deps.py
│
├── agents/             # AI 에이전트 (15개)
│   ├── base.py         # BaseAgent ABC
│   ├── commander.py    # 오케스트레이터
│   ├── population.py, competition.py, revenue.py, location.py
│   ├── trend.py, financial.py, risk.py, real_estate.py, regulatory.py
│   ├── narrative.py, visualization.py
│   └── debate/         # 토론 시스템 (advocate, critic, judge, orchestrator)
│
├── graph/              # LangGraph DAG
│   ├── workflow.py     # 워크플로우 빌더
│   ├── nodes.py        # 노드 팩토리 (362 lines)
│   └── edges.py        # 조건부 라우팅
│
├── engine/             # 분석 엔진 워커
│   ├── worker.py       # Redis Stream 소비자
│   └── redis_broker.py # Redis 브로커
│
├── mcp_servers/        # MCP 도구 서버 9개 (39 files)
│   ├── maps/           # 카카오 지도 API
│   ├── google_maps/    # Google Maps API
│   ├── naver_maps/     # 네이버 지도 API
│   ├── public_data/    # 공공데이터 API
│   ├── finance/        # 금융 데이터 API
│   ├── real_estate/    # 부동산 데이터 API
│   ├── news/           # 뉴스 API
│   ├── regulatory/     # 규제 정보 API
│   └── database/       # DB 조회 도구
│
├── pipeline/           # 데이터 수집 스케줄러
├── collectors/         # 외부 데이터 수집기
├── preprocessors/      # 데이터 전처리기
├── scheduler/          # APScheduler 작업
│
├── services/           # 분석 서비스 오케스트레이션
├── models/             # Pydantic 모델 (state, agent_outputs, report, debate, common)
├── db/                 # SQLAlchemy (models, session, repositories)
├── cache/              # Redis 캐시
├── llm/                # LLM Provider (litellm)
├── memory/             # 태스크/개인 메모리
├── monitoring/         # Prometheus, Langfuse, DAG tracer
└── tools/              # MCP 클라이언트, 도구 레지스트리
```

### 1.2 현재 런타임 프로세스 (이미 3개)
| 프로세스 | 실행 명령 | 포트 |
|---------|----------|------|
| API Server | `uvicorn app.main:app` | 8000 |
| Engine Worker | `python -m app.engine` | 9100 (metrics) |
| Pipeline Scheduler | `python -m app.pipeline` | - |
| MCP Servers (9개) | 각각 `uvicorn` | 5100-5108 |

### 1.3 프로세스 간 통신
```
[Client] → HTTP → [API Server] → Redis Stream → [Engine Worker]
                                                      ↓
                   [API Server] ← Redis Pub/Sub ← [Engine Worker]
                                                      ↓
                                                  HTTP → [MCP Servers]
                                                      ↓
                                                  SQLAlchemy → [PostgreSQL]

[Pipeline Scheduler] → Collectors → [PostgreSQL]
```

### 1.4 모듈 간 의존성 (import 분석)
가장 많이 참조되는 모듈 (공유 코드 후보):
- `logging_config` (18회) — 거의 모든 파일에서 사용
- `agents.base` (15회) — 모든 에이전트가 상속
- `config` (12회) — 설정 객체
- `models.agent_outputs` (11회) — 에이전트 출력 스키마
- `db.models` (7회) — DB 모델
- `exceptions` (5회) — 커스텀 예외
- `models.debate` (5회) — 토론 모델

MCP 서버들은 자기 내부만 참조 — **이미 완전히 격리됨**.

---

## 2. 목표 구조

### 2.1 서비스 분리 (5개 서비스 + 1 공유 라이브러리)

```
marketscope/
├── common/                          # 공유 라이브러리 (모든 서비스가 의존)
│   ├── pyproject.toml
│   └── src/
│       └── marketscope_common/
│           ├── __init__.py
│           ├── config.py            ← app/config.py
│           ├── constants.py         ← app/constants.py
│           ├── exceptions.py        ← app/exceptions.py
│           ├── logging.py           ← app/logging_config.py
│           ├── models/              ← app/models/
│           │   ├── __init__.py
│           │   ├── state.py
│           │   ├── agent_outputs.py
│           │   ├── report.py
│           │   ├── debate.py
│           │   └── common.py
│           ├── db/                  ← app/db/
│           │   ├── __init__.py
│           │   ├── models.py
│           │   ├── session.py
│           │   └── repositories.py
│           ├── cache/               ← app/cache/
│           │   ├── __init__.py
│           │   └── redis_client.py
│           └── monitoring/          ← app/monitoring/
│               ├── __init__.py
│               ├── metrics.py
│               ├── dag_tracer.py
│               ├── langfuse_handler.py
│               ├── mcp_monitor.py
│               └── quality_checker.py
│
├── api/                             # Backend API 서비스
│   ├── pyproject.toml               # depends on: marketscope-common
│   ├── Dockerfile
│   └── src/
│       └── marketscope_api/
│           ├── __init__.py
│           ├── main.py              ← app/main.py
│           ├── deps.py              ← app/api/deps.py
│           └── routes/
│               ├── __init__.py
│               ├── analysis.py      ← app/api/routes/analysis.py
│               └── health.py        ← app/api/routes/health.py
│
├── agent/                           # AI 에이전트 + 엔진 서비스
│   ├── pyproject.toml               # depends on: marketscope-common
│   ├── Dockerfile
│   └── src/
│       └── marketscope_agent/
│           ├── __init__.py
│           ├── agents/              ← app/agents/
│           │   ├── __init__.py
│           │   ├── base.py
│           │   ├── commander.py
│           │   ├── population.py
│           │   ├── competition.py
│           │   ├── revenue.py
│           │   ├── location.py
│           │   ├── trend.py
│           │   ├── financial.py
│           │   ├── risk.py
│           │   ├── real_estate.py
│           │   ├── regulatory.py
│           │   ├── narrative.py
│           │   ├── visualization.py
│           │   └── debate/
│           │       ├── __init__.py
│           │       ├── advocate.py
│           │       ├── critic.py
│           │       ├── judge.py
│           │       └── orchestrator.py
│           ├── graph/               ← app/graph/
│           │   ├── __init__.py
│           │   ├── workflow.py
│           │   ├── nodes.py
│           │   └── edges.py
│           ├── engine/              ← app/engine/
│           │   ├── __init__.py
│           │   ├── __main__.py
│           │   ├── worker.py
│           │   └── redis_broker.py
│           ├── services/            ← app/services/
│           │   ├── __init__.py
│           │   └── analysis_service.py
│           ├── llm/                 ← app/llm/
│           │   ├── __init__.py
│           │   ├── provider.py
│           │   ├── litellm_provider.py
│           │   └── pricing.py
│           ├── memory/              ← app/memory/
│           │   ├── __init__.py
│           │   ├── task_memory.py
│           │   ├── lightrag_client.py
│           │   ├── reme_client.py
│           │   └── personal_memory.py
│           └── tools/               ← app/tools/
│               ├── __init__.py
│               ├── mcp_client.py
│               └── registry.py
│
├── mcp/                             # MCP 도구 서버들
│   ├── pyproject.toml               # 독립 (common 불필요)
│   ├── Dockerfile
│   └── src/
│       └── marketscope_mcp/
│           ├── __init__.py
│           ├── maps/                ← app/mcp_servers/maps/
│           ├── google_maps/         ← app/mcp_servers/google_maps/
│           ├── naver_maps/          ← app/mcp_servers/naver_maps/
│           ├── public_data/         ← app/mcp_servers/public_data/
│           ├── finance/             ← app/mcp_servers/finance/
│           ├── real_estate/         ← app/mcp_servers/real_estate/
│           ├── news/                ← app/mcp_servers/news/
│           ├── regulatory/          ← app/mcp_servers/regulatory/
│           └── database/            ← app/mcp_servers/database/
│
├── pipeline/                        # 데이터 수집 파이프라인
│   ├── pyproject.toml               # depends on: marketscope-common
│   ├── Dockerfile
│   └── src/
│       └── marketscope_pipeline/
│           ├── __init__.py
│           ├── __main__.py          ← app/pipeline/__main__.py
│           ├── main.py              ← app/pipeline/main.py
│           ├── collectors/          ← app/collectors/
│           │   ├── __init__.py
│           │   ├── base.py
│           │   ├── seoul.py
│           │   ├── kosis.py
│           │   └── semas.py
│           ├── preprocessors/       ← app/preprocessors/
│           │   ├── __init__.py
│           │   ├── missing_handler.py
│           │   ├── outlier_detector.py
│           │   ├── code_mapper.py
│           │   └── coordinate_transformer.py
│           └── scheduler/           ← app/scheduler/
│               ├── __init__.py
│               └── jobs.py
│
├── docker-compose.yml               # 전체 서비스 오케스트레이션
├── docker-compose.dev.yml           # 개발 환경 오버라이드
├── pyproject.toml                   # 루트 (개발 도구, 워크스페이스 설정)
├── alembic/                         ← marketscope/alembic/
├── tests/                           # 통합 테스트
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── monitoring/                      ← marketscope/monitoring/
│   └── grafana/
├── scripts/                         ← marketscope/scripts/
└── docs/
```

### 2.2 의존성 그래프
```
                    ┌─────────────┐
                    │   common    │
                    └──────┬──────┘
           ┌───────────┬───┴───┬───────────┐
           │           │       │           │
      ┌────▼───┐  ┌───▼──┐  ┌─▼────┐  ┌──▼──────┐
      │  api   │  │agent │  │ mcp  │  │pipeline │
      └────────┘  └──────┘  └──────┘  └─────────┘
                                (독립)
```

- `common` ← api, agent, pipeline이 의존
- `mcp` — 외부 의존 없음 (자체 config만 사용)
- 서비스 간 통신: Redis (api ↔ agent), HTTP (agent → mcp)

---

## 3. 단계별 실행 계획

### Phase 1: common 패키지 추출 (예상: 가장 중요, 선행 작업)

**목표**: 공유 코드를 `marketscope-common` 패키지로 추출

#### 1.1 패키지 초기화
```bash
mkdir -p common/src/marketscope_common
```

#### 1.2 pyproject.toml 작성
```toml
[project]
name = "marketscope-common"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "redis>=5.0",
    "structlog>=24.0",
    "prometheus-client>=0.20",
    "langfuse>=2.0",
]
```

#### 1.3 파일 이동 매핑
| 현재 위치 | 새 위치 |
|----------|---------|
| `app/config.py` | `common/src/marketscope_common/config.py` |
| `app/constants.py` | `common/src/marketscope_common/constants.py` |
| `app/exceptions.py` | `common/src/marketscope_common/exceptions.py` |
| `app/logging_config.py` | `common/src/marketscope_common/logging.py` |
| `app/models/*.py` | `common/src/marketscope_common/models/*.py` |
| `app/db/*.py` | `common/src/marketscope_common/db/*.py` |
| `app/cache/*.py` | `common/src/marketscope_common/cache/*.py` |
| `app/monitoring/*.py` | `common/src/marketscope_common/monitoring/*.py` |

#### 1.4 Import 경로 변경 규칙
```python
# Before
from app.config import get_settings
from app.logging_config import get_logger
from app.models.state import MarketScopeState
from app.db.session import get_session
from app.exceptions import AgentExecutionError

# After
from marketscope_common.config import get_settings
from marketscope_common.logging import get_logger
from marketscope_common.models.state import MarketScopeState
from marketscope_common.db.session import get_session
from marketscope_common.exceptions import AgentExecutionError
```

#### 1.5 검증
- `cd common && pip install -e .` 로 설치
- 기존 `app/` 코드에서 import 경로를 변경하여 테스트 통과 확인

---

### Phase 2: MCP 서버 분리 (가장 쉬움)

**목표**: MCP 서버를 독립 패키지로 분리

#### 2.1 이유: 가장 쉬운 이유
- 이미 `app.mcp_servers.*` 내부만 참조
- `app.config`, `app.models` 등 참조 없음
- 각 서버가 독립 FastAPI 앱

#### 2.2 파일 이동
```
app/mcp_servers/* → mcp/src/marketscope_mcp/
```

#### 2.3 Import 경로 변경
```python
# Before
from app.mcp_servers.maps.kakao_client import KakaoLocalClient
from app.mcp_servers.maps.tools import TOOL_REGISTRY

# After
from marketscope_mcp.maps.kakao_client import KakaoLocalClient
from marketscope_mcp.maps.tools import TOOL_REGISTRY
```

#### 2.4 pyproject.toml
```toml
[project]
name = "marketscope-mcp"
version = "0.1.0"
dependencies = [
    "fastapi>=0.110",
    "uvicorn>=0.27",
    "httpx>=0.27",
    "asyncpg>=0.29",      # database MCP용
]
```

#### 2.5 Dockerfile
- 각 MCP 서버를 환경변수로 선택하여 실행
- `CMD ["uvicorn", "marketscope_mcp.maps.server:app", "--host", "0.0.0.0", "--port", "5101"]`
- 또는 `MCP_SERVER=maps` 환경변수로 동적 선택

---

### Phase 3: Agent/Engine 서비스 분리

**목표**: LangGraph DAG + 에이전트 + Engine Worker를 독립 패키지로 분리

#### 3.1 파일 이동
| 현재 위치 | 새 위치 |
|----------|---------|
| `app/agents/*.py` | `agent/src/marketscope_agent/agents/*.py` |
| `app/graph/*.py` | `agent/src/marketscope_agent/graph/*.py` |
| `app/engine/*.py` | `agent/src/marketscope_agent/engine/*.py` |
| `app/services/*.py` | `agent/src/marketscope_agent/services/*.py` |
| `app/llm/*.py` | `agent/src/marketscope_agent/llm/*.py` |
| `app/memory/*.py` | `agent/src/marketscope_agent/memory/*.py` |
| `app/tools/*.py` | `agent/src/marketscope_agent/tools/*.py` |

#### 3.2 Import 경로 변경
```python
# Before
from app.agents.base import BaseAgent
from app.graph.workflow import create_app
from app.llm.provider import LLMProvider
from app.tools.mcp_client import MCPClientRouter

# After
from marketscope_agent.agents.base import BaseAgent
from marketscope_agent.graph.workflow import create_app
from marketscope_agent.llm.provider import LLMProvider
from marketscope_agent.tools.mcp_client import MCPClientRouter
```

#### 3.3 pyproject.toml
```toml
[project]
name = "marketscope-agent"
version = "0.1.0"
dependencies = [
    "marketscope-common",
    "langgraph>=0.2",
    "litellm>=1.30",
    "httpx>=0.27",
]

[project.scripts]
marketscope-engine = "marketscope_agent.engine.__main__:main"
```

#### 3.4 핵심 주의사항
- `engine/redis_broker.py`는 `api`에서도 import됨 → **common으로 이동하거나** api에서 독립 broker 사용
- **결정**: `redis_broker.py`를 `common/`에 배치 (api와 agent 양쪽에서 사용)

---

### Phase 4: API 서비스 분리

**목표**: FastAPI API를 독립 패키지로 분리

#### 4.1 파일 이동
| 현재 위치 | 새 위치 |
|----------|---------|
| `app/main.py` | `api/src/marketscope_api/main.py` |
| `app/api/routes/*.py` | `api/src/marketscope_api/routes/*.py` |
| `app/api/deps.py` | `api/src/marketscope_api/deps.py` |

#### 4.2 pyproject.toml
```toml
[project]
name = "marketscope-api"
version = "0.1.0"
dependencies = [
    "marketscope-common",
    "fastapi>=0.110",
    "uvicorn>=0.27",
    "prometheus-client>=0.20",
]

[project.scripts]
marketscope-api = "marketscope_api.main:create_app"
```

#### 4.3 API → Agent 통신
- API는 Agent를 직접 import하지 않음
- Redis Broker를 통해서만 통신 (현재 구조 유지)
- `redis_broker.py`는 common에 위치

---

### Phase 5: Pipeline 서비스 분리

**목표**: 데이터 수집 파이프라인을 독립 패키지로 분리

#### 5.1 파일 이동
| 현재 위치 | 새 위치 |
|----------|---------|
| `app/pipeline/*.py` | `pipeline/src/marketscope_pipeline/*.py` |
| `app/collectors/*.py` | `pipeline/src/marketscope_pipeline/collectors/*.py` |
| `app/preprocessors/*.py` | `pipeline/src/marketscope_pipeline/preprocessors/*.py` |
| `app/scheduler/*.py` | `pipeline/src/marketscope_pipeline/scheduler/*.py` |

#### 5.2 pyproject.toml
```toml
[project]
name = "marketscope-pipeline"
version = "0.1.0"
dependencies = [
    "marketscope-common",
    "httpx>=0.27",
    "apscheduler>=3.10",
    "pyproj>=3.6",
]
```

---

### Phase 6: Docker 인프라 구성

#### 6.1 docker-compose.yml (프로덕션)
```yaml
services:
  # ── 인프라 ──
  postgres:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: marketscope
      POSTGRES_USER: marketscope_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

  # ── 애플리케이션 서비스 ──
  api:
    build:
      context: .
      dockerfile: api/Dockerfile
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    env_file: .env

  engine:
    build:
      context: .
      dockerfile: agent/Dockerfile
    depends_on:
      - redis
      - mcp-maps
      - mcp-public-data
      - mcp-finance
      - mcp-database
    env_file: .env

  pipeline:
    build:
      context: .
      dockerfile: pipeline/Dockerfile
    depends_on:
      - postgres
    env_file: .env

  # ── MCP 서버 ──
  mcp-maps:
    build:
      context: .
      dockerfile: mcp/Dockerfile
    command: ["uvicorn", "marketscope_mcp.maps.server:app", "--host", "0.0.0.0", "--port", "5101"]
    ports:
      - "5101:5101"

  mcp-public-data:
    build:
      context: .
      dockerfile: mcp/Dockerfile
    command: ["uvicorn", "marketscope_mcp.public_data.server:app", "--host", "0.0.0.0", "--port", "5100"]
    ports:
      - "5100:5100"

  mcp-finance:
    build:
      context: .
      dockerfile: mcp/Dockerfile
    command: ["uvicorn", "marketscope_mcp.finance.server:app", "--host", "0.0.0.0", "--port", "5105"]

  mcp-database:
    build:
      context: .
      dockerfile: mcp/Dockerfile
    command: ["uvicorn", "marketscope_mcp.database.server:app", "--host", "0.0.0.0", "--port", "5106"]
    depends_on:
      - postgres

  mcp-news:
    build:
      context: .
      dockerfile: mcp/Dockerfile
    command: ["uvicorn", "marketscope_mcp.news.server:app", "--host", "0.0.0.0", "--port", "5103"]

  mcp-real-estate:
    build:
      context: .
      dockerfile: mcp/Dockerfile
    command: ["uvicorn", "marketscope_mcp.real_estate.server:app", "--host", "0.0.0.0", "--port", "5102"]

  mcp-regulatory:
    build:
      context: .
      dockerfile: mcp/Dockerfile
    command: ["uvicorn", "marketscope_mcp.regulatory.server:app", "--host", "0.0.0.0", "--port", "5104"]

  mcp-google-maps:
    build:
      context: .
      dockerfile: mcp/Dockerfile
    command: ["uvicorn", "marketscope_mcp.google_maps.server:app", "--host", "0.0.0.0", "--port", "5107"]

  mcp-naver-maps:
    build:
      context: .
      dockerfile: mcp/Dockerfile
    command: ["uvicorn", "marketscope_mcp.naver_maps.server:app", "--host", "0.0.0.0", "--port", "5108"]

  # ── 모니터링 ──
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    volumes:
      - ./monitoring/grafana:/etc/grafana/provisioning

volumes:
  pgdata:
```

#### 6.2 Dockerfile 전략
각 서비스가 공통 라이브러리를 포함하도록 **멀티스테이지 빌드**:

```dockerfile
# api/Dockerfile
FROM python:3.11-slim as base

WORKDIR /app

# common 먼저 설치
COPY common/ /tmp/common/
RUN pip install /tmp/common/

# api 설치
COPY api/ /tmp/api/
RUN pip install /tmp/api/

EXPOSE 8000
CMD ["uvicorn", "marketscope_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### Phase 7: 테스트 구조 재편

#### 7.1 테스트 분리
```
tests/
├── conftest.py                 # 공통 fixture
├── unit/
│   ├── common/                 # common 패키지 테스트
│   │   ├── test_config.py
│   │   └── test_models.py
│   ├── agent/                  # agent 패키지 테스트
│   │   ├── test_agents.py
│   │   ├── test_nodes.py
│   │   ├── test_edges.py
│   │   └── test_engine_worker.py
│   ├── api/                    # api 패키지 테스트
│   │   └── test_analysis_routes.py
│   └── mcp/                    # mcp 패키지 테스트
│       └── test_mcp_tools.py
└── integration/
    └── test_workflow.py        # E2E 워크플로우 테스트
```

---

## 4. Import 변경 전체 매핑

### 4.1 패키지별 변환 규칙

| 기존 import 패턴 | 새 import 패턴 | 대상 서비스 |
|-----------------|---------------|-----------|
| `from app.config import ...` | `from marketscope_common.config import ...` | all |
| `from app.constants import ...` | `from marketscope_common.constants import ...` | all |
| `from app.exceptions import ...` | `from marketscope_common.exceptions import ...` | all |
| `from app.logging_config import ...` | `from marketscope_common.logging import ...` | all |
| `from app.models.* import ...` | `from marketscope_common.models.* import ...` | all |
| `from app.db.* import ...` | `from marketscope_common.db.* import ...` | all |
| `from app.cache.* import ...` | `from marketscope_common.cache.* import ...` | all |
| `from app.monitoring.* import ...` | `from marketscope_common.monitoring.* import ...` | all |
| `from app.agents.* import ...` | `from marketscope_agent.agents.* import ...` | agent |
| `from app.graph.* import ...` | `from marketscope_agent.graph.* import ...` | agent |
| `from app.engine.* import ...` | `from marketscope_agent.engine.* import ...` | agent, api |
| `from app.llm.* import ...` | `from marketscope_agent.llm.* import ...` | agent |
| `from app.tools.* import ...` | `from marketscope_agent.tools.* import ...` | agent |
| `from app.memory.* import ...` | `from marketscope_agent.memory.* import ...` | agent |
| `from app.services.* import ...` | `from marketscope_agent.services.* import ...` | agent |
| `from app.api.* import ...` | `from marketscope_api.* import ...` | api |
| `from app.mcp_servers.* import ...` | `from marketscope_mcp.* import ...` | mcp |
| `from app.collectors.* import ...` | `from marketscope_pipeline.collectors.* import ...` | pipeline |
| `from app.preprocessors.* import ...` | `from marketscope_pipeline.preprocessors.* import ...` | pipeline |
| `from app.scheduler.* import ...` | `from marketscope_pipeline.scheduler.* import ...` | pipeline |
| `from app.pipeline.* import ...` | `from marketscope_pipeline.* import ...` | pipeline |

### 4.2 경계 이슈 해결

**이슈 1: `redis_broker.py`를 api와 agent 양쪽에서 사용**
- 해결: `common/src/marketscope_common/broker/redis_broker.py`로 이동
- api는 `publish_request`, `get_status`, `subscribe_progress`만 사용
- agent는 `consume_requests`, `update_status`, `store_result`만 사용

**이슈 2: `engine/worker.py`가 `services/analysis_service.py`를 import**
- 해결: 둘 다 agent 패키지 내부이므로 문제 없음

**이슈 3: `api/routes/analysis.py`가 `engine/redis_broker.py`를 import**
- 해결: redis_broker를 common으로 이동하면 해결

---

## 5. 실행 순서 및 우선순위

```
Phase 1 (common)  ──→  Phase 2 (mcp)  ──→  Phase 3 (agent)
                                               │
                                               ▼
                       Phase 5 (pipeline)  ←  Phase 4 (api)
                                               │
                                               ▼
                                          Phase 6 (docker)
                                               │
                                               ▼
                                          Phase 7 (tests)
```

| Phase | 난이도 | 파일 수 | 핵심 리스크 |
|-------|-------|--------|-----------|
| 1. common | ★★★ | ~25 | import 변경이 전체에 파급 |
| 2. mcp | ★☆☆ | ~39 | 이미 격리되어 있어 단순 이동 |
| 3. agent | ★★★ | ~35 | LangGraph 워크플로우 깨지지 않도록 주의 |
| 4. api | ★★☆ | ~5 | redis_broker 경계 처리 |
| 5. pipeline | ★★☆ | ~10 | scheduler 설정 이전 |
| 6. docker | ★★☆ | 새로 작성 | 멀티스테이지 빌드 설정 |
| 7. tests | ★★☆ | ~12 | fixture/conftest 재구성 |

---

## 6. 리스크 및 주의사항

### 6.1 순환 참조 방지
- `common`은 다른 서비스를 절대 import하지 않음
- `api`는 `agent`를 직접 import하지 않음 (Redis 통신만)
- `agent`는 `mcp`를 직접 import하지 않음 (HTTP 통신만)

### 6.2 개발 환경 설정
```bash
# 개발 시 editable install
pip install -e common/
pip install -e agent/
pip install -e api/
pip install -e mcp/
pip install -e pipeline/
```

루트 `pyproject.toml`에서 워크스페이스로 관리:
```toml
[tool.uv.workspace]
members = ["common", "api", "agent", "mcp", "pipeline"]
```

### 6.3 마이그레이션 전략
- **Big Bang이 아닌 점진적 마이그레이션** 권장
- 각 Phase 완료 후 전체 테스트 통과 확인
- 기존 `marketscope/app/`은 모든 서비스 분리 완료 후 삭제
- Phase 1 완료 시점에서 기존 코드가 `marketscope-common`을 import하도록 변경하고 검증

### 6.4 호환성 유지
- 분리 중에도 기존 실행 방식(`uvicorn app.main:app` 등) 유지
- Phase 1에서 `common` 추출 후 기존 `app/` 내에서 re-export하면 기존 코드 깨지지 않음:
  ```python
  # app/config.py (임시 호환성 레이어)
  from marketscope_common.config import *  # noqa: F401,F403
  ```
- 모든 서비스 분리 완료 후 호환성 레이어 삭제

---

## 7. 완료 기준

- [ ] 각 서비스가 독립 `pyproject.toml`로 설치 가능
- [ ] `docker-compose up`으로 전체 시스템 기동 가능
- [ ] 기존 단위/통합 테스트 전체 통과
- [ ] 서비스 간 순환 의존 없음
- [ ] `marketscope/app/` 디렉토리 완전 삭제
- [ ] 각 서비스 독립 Dockerfile 빌드 성공

---

## 8. 진행 상황

### Phase 1: common 패키지 추출 — **완료** (2026-03-23)

**구현 내용:**
- `marketscope/common/` 패키지 생성 (`pyproject.toml` + `src/marketscope_common/`)
- 27개 파일 추출 (config, constants, exceptions, logging, models/5, db/3, cache/1, broker/1, monitoring/6, _pricing/1)
- 모든 내부 import를 `marketscope_common.*`으로 변환
- 기존 `app/` 파일을 호환성 shim으로 교체 (re-export from `marketscope_common`)
- `pip install -e common/` 검증 완료
- 기존 `app.*` import와 `marketscope_common.*` import 모두 동작 확인

**패키지 구조:**
```
common/
├── pyproject.toml
└── src/
    └── marketscope_common/
        ├── __init__.py
        ├── config.py
        ├── constants.py
        ├── exceptions.py
        ├── logging.py
        ├── models/          (5 files: common, debate, agent_outputs, report, state)
        ├── db/              (3 files: models, session, repositories)
        ├── cache/           (1 file: redis_client)
        ├── broker/          (1 file: redis_broker)
        └── monitoring/      (6 files: metrics, dag_tracer, langfuse_handler, mcp_monitor, quality_checker, _pricing)
```

**특이 사항:**
- `app/llm/pricing.py`가 존재하지 않았으나 `metrics.py`와 `base.py`에서 lazy import → `monitoring/_pricing.py`로 스텁 생성
- `engine/redis_broker.py`는 API와 Agent 양쪽에서 사용 → `common/broker/`로 이동 (계획대로)
- `langgraph`, `langchain-core`를 common의 dependencies에 포함 (`models/state.py`가 `langgraph.graph.message.add_messages` 사용)

### Phase 2: MCP 서버 분리 — **완료** (2026-03-23)

**구현 내용:**
- `marketscope/mcp/` 패키지 생성 (`pyproject.toml` + `src/marketscope_mcp/`)
- 9개 MCP 서버 (39 files) 추출: maps, google_maps, naver_maps, public_data, finance, real_estate, news, regulatory, database
- 모든 내부 import `app.mcp_servers.*` → `marketscope_mcp.*` 변환
- 기존 `app/mcp_servers/` 파일을 호환성 shim으로 교체
- `pip install -e mcp/` 검증 완료
- 새 경로(`marketscope_mcp.*`)와 기존 경로(`app.mcp_servers.*`) 모두 동작 확인
- 객체 identity 검증 통과 (shim이 동일 객체 re-export)

**패키지 구조:**
```
mcp/
├── pyproject.toml
└── src/
    └── marketscope_mcp/
        ├── __init__.py
        ├── maps/           (kakao_client, tools, server, __main__)
        ├── google_maps/    (api_client, schemas, tools, server)
        ├── naver_maps/     (api_client, schemas, tools, server)
        ├── public_data/    (resources, tools, server)
        ├── finance/        (api_client, schemas, tools, server)
        ├── real_estate/    (tools, server)
        ├── news/           (tools, server)
        ├── regulatory/     (tools, server)
        └── database/       (db_client, schemas, tools, server)
```

**특이 사항:**
- MCP 서버들은 이미 완전히 격리 (외부 `app.*` 의존 없음, 서버 간 상호 참조 없음)
- `marketscope-mcp`는 `marketscope-common`에 의존하지 않음 (독립 패키지)
- 외부 의존성: fastapi, uvicorn, pydantic, httpx, asyncpg (database 서버용)

### Phase 3: Agent/Engine 서비스 분리 — **완료** (2026-03-23)

**구현 내용:**
- `marketscope/agent/` 패키지 생성 (`pyproject.toml` + `src/marketscope_agent/`)
- 7개 디렉토리, 40개 파일 추출: agents(19), graph(4), engine(4), services(2), llm(3), memory(5), tools(3)
- 내부 import `app.agents/graph/engine/services/llm/memory/tools.*` → `marketscope_agent.*` 변환 (45개)
- common 참조 `app.config/logging_config/constants/exceptions/models/monitoring.*` → `marketscope_common.*` 변환 (52개)
- 기존 `app/` 파일 39개를 호환성 shim으로 교체
- `pip install -e agent/` 검증 완료
- 새 경로(`marketscope_agent.*`)와 기존 경로(`app.*`) 모두 동작 확인
- 객체 identity 검증 통과 (shim이 동일 객체 re-export)

**패키지 구조:**
```
agent/
├── pyproject.toml
└── src/
    └── marketscope_agent/
        ├── __init__.py
        ├── agents/          (15 agents + debate/ 서브패키지)
        │   ├── base.py      (BaseAgent ABC)
        │   ├── commander.py, population.py, competition.py, ...
        │   └── debate/      (advocate, critic, judge, orchestrator)
        ├── graph/           (workflow, nodes, edges)
        ├── engine/          (worker, redis_broker shim, __main__)
        ├── services/        (analysis_service)
        ├── llm/             (provider, litellm_provider)
        ├── memory/          (task_memory, lightrag_client, reme_client, personal_memory)
        └── tools/           (mcp_client, registry)
```

**특이 사항:**
- `agents/base.py:135`의 `app.llm.pricing` → `marketscope_common.monitoring._pricing`으로 수정 (계획된 사전 작업)
- `engine/redis_broker.py`는 Phase 1에서 이미 common으로 이동 → agent에서 `marketscope_common.broker.redis_broker` re-export
- common 참조는 `marketscope_common.*`을 직접 사용 (shim 경유 아님)
- 외부 의존성: marketscope-common, langgraph>=0.2, langchain-core>=0.3, litellm>=1.50, httpx>=0.27, redis>=5.0, structlog>=24.1

### Phase 4: API 서비스 분리 — **완료** (2026-03-23)

**구현 내용:**
- `marketscope/api/` 패키지 생성 (`pyproject.toml` + `src/marketscope_api/`)
- 4개 파일 추출: main.py, deps.py, routes/analysis.py, routes/health.py
- common 참조 변환 (13개): config(3), logging(1), cache.redis_client(3), monitoring(3), db.session(1), broker.redis_broker(1)
- 내부 참조 변환 (4개): `app.api.routes.*` → `marketscope_api.routes.*`
- agent 참조 변환 (2개, optional/try-except): `app.graph.nodes` → `marketscope_agent.graph.nodes`
- 기존 `app/` 파일 4개를 호환성 shim으로 교체
- `pip install -e api/` 검증 완료
- 새 경로(`marketscope_api.*`)와 기존 경로(`app.*`) 모두 동작 확인
- 객체 identity 검증 통과

**패키지 구조:**
```
api/
├── pyproject.toml
└── src/
    └── marketscope_api/
        ├── __init__.py
        ├── main.py          (FastAPI app factory + lifespan)
        ├── deps.py          (DI utilities)
        └── routes/
            ├── __init__.py
            ├── analysis.py  (분석 요청/결과/SSE 스트리밍)
            └── health.py    (K8s probes + 상세 헬스체크)
```

**특이 사항:**
- API는 Agent를 직접 import하지 않음 — Redis Broker를 통해서만 통신
- health.py의 MCP 상태 체크는 `marketscope_agent.graph.nodes`를 try/except로 참조 (optional)
- `RedisBroker` 참조는 `marketscope_common.broker.redis_broker` 사용 (계획대로)
- 외부 의존성: marketscope-common, fastapi>=0.115, uvicorn>=0.30, prometheus-client>=0.20, sse-starlette>=2.0

---

### Phase 5 완료 (2026-03-23) — Pipeline 서비스 분리

**이동된 파일 (15):**
- `app/pipeline/{__init__, __main__, main}.py` → `pipeline/src/marketscope_pipeline/`
- `app/collectors/{__init__, base, kosis, semas, seoul}.py` → `pipeline/src/marketscope_pipeline/collectors/`
- `app/preprocessors/{__init__, code_mapper, coordinate_transformer, missing_handler, outlier_detector}.py` → `pipeline/src/marketscope_pipeline/preprocessors/`
- `app/scheduler/{__init__, jobs}.py` → `pipeline/src/marketscope_pipeline/scheduler/`

**import 변환 (총 30건):**
- `app.config` → `marketscope_common.config` (10건, 동적 import 포함)
- `app.logging_config` → `marketscope_common.logging` (1건)
- `app.db.models` → `marketscope_common.db.models` (4건)
- `app.db.session` → `marketscope_common.db.session` (10건, 동적 import)
- `app.monitoring.quality_checker` → `marketscope_common.monitoring.quality_checker` (1건)
- `app.collectors.*` → `marketscope_pipeline.collectors.*` (4건, 내부)

**검증 결과:**
- `pip install -e pipeline/` 검증 완료
- 새 경로(`marketscope_pipeline.*`)와 기존 경로(`app.*`) 모두 동작 확인
- 객체 identity 검증 통과

**패키지 구조:**
```
pipeline/
├── pyproject.toml
└── src/
    └── marketscope_pipeline/
        ├── __init__.py
        ├── __main__.py      (python -m 진입점)
        ├── main.py           (스케줄러 메인 루프)
        ├── collectors/
        │   ├── __init__.py
        │   ├── base.py       (BaseCollector ABC + 재시도 로직)
        │   ├── kosis.py      (통계청 API)
        │   ├── semas.py      (소상공인 상권정보 API)
        │   └── seoul.py      (서울 열린데이터 API)
        ├── preprocessors/
        │   ├── __init__.py
        │   ├── code_mapper.py          (행정동↔상권코드 변환)
        │   ├── coordinate_transformer.py (TM/UTM-K→WGS84)
        │   ├── missing_handler.py      (결측치 보정)
        │   └── outlier_detector.py     (이상치 탐지)
        └── scheduler/
            ├── __init__.py
            └── jobs.py        (APScheduler 10개 수집 스케줄)
```

**특이 사항:**
- scheduler/jobs.py의 동적 import (함수 내부 import)도 모두 변환 완료
- preprocessors 모듈 중 coordinate_transformer, missing_handler, outlier_detector는 외부 의존 없는 순수 유틸리티
- 외부 의존성: marketscope-common, httpx, sqlalchemy, asyncpg, apscheduler, pyproj

---

### Phase 6 완료 (2026-03-23) — Docker 인프라 구성

**변경된 파일 (4):**
- `Dockerfile` — 워크스페이스 패키지 구조 지원으로 재작성
- `docker-compose.yml` — 모든 서비스 명령어를 새 패키지 경로로 변환 (12건)
- `.dockerignore` — 새 구조에 맞게 업데이트
- `docker-compose.monitoring.yml` — 변경 없음 (패키지 경로 미참조)

**명령어 변환 (12건):**
| 서비스 | 기존 | 변경 |
|--------|------|------|
| api | `app.main:app` | `marketscope_api.main:app` |
| engine | `python -m app.engine` | `python -m marketscope_agent.engine` |
| pipeline | `python -m app.pipeline` | `python -m marketscope_pipeline` |
| mcp-* (9개) | `app.mcp_servers.{name}.server:app` | `marketscope_mcp.{name}.server:app` |

**Dockerfile 개선:**
- 2단계 캐시 전략: pyproject.toml 먼저 복사 → pip install → 소스 복사
- 5개 워크스페이스 패키지 editable install
- 기존 단일 Dockerfile 구조 유지 (서비스별 command override)

**검증:**
- docker-compose.yml 파싱 검증 (16 서비스, `app.*` 참조 0건)
- Dockerfile 패키지 설치 검증 (5개 workspace 패키지 모두 포함)

---

## 9. Next Actions

### Phase 7 완료 (2026-03-23) — 테스트 재편

**변경된 파일 (12):**
- `tests/conftest.py` — app.config→marketscope_common.config, app.models.state→marketscope_common.models.state, app.llm.provider→marketscope_agent.llm.provider
- `tests/unit/test_edges.py` — app.graph.edges→marketscope_agent.graph.edges
- `tests/unit/test_nodes.py` — app.graph.nodes→marketscope_agent.graph.nodes
- `tests/unit/test_agents.py` — app.agents.*→marketscope_agent.agents.*, app.exceptions→marketscope_common.exceptions, app.llm.provider→marketscope_agent.llm.provider
- `tests/unit/test_redis_broker.py` — app.engine.redis_broker→marketscope_common.broker.redis_broker
- `tests/unit/test_engine_worker.py` — app.engine.worker→marketscope_agent.engine.worker, patch 경로 변환
- `tests/unit/test_mcp_tools.py` — app.mcp_servers.*→marketscope_mcp.*
- `tests/unit/test_mcp_client.py` — app.tools.mcp_client→marketscope_agent.tools.mcp_client
- `tests/unit/test_analysis_routes.py` — app.api.routes.*→marketscope_api.routes.*, app.main→marketscope_api.main
- `tests/unit/test_pipeline_main.py` — app.pipeline.*→marketscope_pipeline.*, app.scheduler.*→marketscope_pipeline.scheduler.*, job count 8→10 수정
- `tests/integration/test_workflow.py` — app.graph.workflow→marketscope_agent.graph.workflow, app.models.state→marketscope_common.models.state

**검증 결과:** 98 tests passed, 0 failed

---

## 10. 리팩토링 완료 — 남은 작업

### 호환성 shim 제거 (선택적)
- 모든 7 Phase 완료 — `app/` 디렉토리의 shim 파일 제거 가능
- 외부 참조(CI, 스크립트 등) 확인 후 `app/` 디렉토리 삭제
- 제거 시 `pyproject.toml`의 `[tool.setuptools.packages.find] include = ["app*"]` 도 제거
