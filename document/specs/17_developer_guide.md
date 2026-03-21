# 17. 개발자 온보딩 가이드

> MarketScope AI 개발 환경 설정 및 기여 가이드
> 작성일: 2026-03-21

---

## 목차

1. [퀵스타트](#1-퀵스타트)
2. [개발 환경 설정](#2-개발-환경-설정)
3. [프로젝트 구조](#3-프로젝트-구조)
4. [새 에이전트 추가 방법](#4-새-에이전트-추가-방법)
5. [새 MCP 서버 추가 방법](#5-새-mcp-서버-추가-방법)
6. [Git 워크플로우](#6-git-워크플로우)
7. [디버깅 가이드](#7-디버깅-가이드)
8. [코드 리뷰 가이드라인](#8-코드-리뷰-가이드라인)

---

## 1. 퀵스타트

```bash
# 1. 리포지토리 클론
git clone https://github.com/your-org/Catchment-Area-Analysis.git
cd Catchment-Area-Analysis/marketscope

# 2. 환경변수 설정
cp .env.example .env
# .env 파일 편집: 최소한 아래 항목 설정
# - OPENAI_API_KEY 또는 ANTHROPIC_API_KEY 또는 GEMINI_API_KEY (LLM용)
# - DATA_API_KAKAO_REST_KEY (지도 API용)

# 3. Docker 서비스 시작
docker-compose up -d postgres redis

# 4. Python 환경 설정
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 5. DB 마이그레이션
alembic upgrade head

# 6. 앱 실행
uvicorn app.main:app --reload --port 8000

# 7. 헬스체크
curl http://localhost:8000/health
# → {"status": "ok"}
```

---

## 2. 개발 환경 설정

### 2.1 필수 소프트웨어

| 소프트웨어 | 버전 | 용도 |
|-----------|------|------|
| Python | >= 3.11 | 애플리케이션 런타임 |
| Docker + Docker Compose | >= 24.0 | PostgreSQL, Redis, MCP 서버 |
| Git | >= 2.40 | 버전 관리 |

### 2.2 권장 IDE

| IDE | 설정 |
|-----|------|
| **VS Code** | Python + Pylance + Ruff 확장 설치 |
| **PyCharm** | Professional (FastAPI 디버거 지원) |

### 2.3 VS Code 설정

```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll.ruff": "explicit",
      "source.organizeImports.ruff": "explicit"
    }
  },
  "python.testing.pytestArgs": ["tests"],
  "python.testing.pytestEnabled": true
}
```

### 2.4 환경변수 (.env)

```bash
# ── 필수 ──
DATABASE_URL=postgresql+asyncpg://marketscope_user:marketscope_dev_pw@localhost:5432/marketscope
REDIS_URL=redis://localhost:6379/0

# ── LLM (최소 1개 필수) ──
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GEMINI_API_KEY=AI...

# ── 데이터 API ──
DATA_API_KAKAO_REST_KEY=...        # 카카오 지도 (필수)
DATA_API_PUBLIC_DATA_KEY=...       # data.go.kr
DATA_API_SEOUL_OPEN_DATA_KEY=...   # 서울 열린데이터
# DATA_API_GOOGLE_MAPS_KEY=...     # Google Maps (선택)
# DATA_API_NAVER_CLIENT_ID=...     # 네이버 (선택)
# DATA_API_NAVER_CLIENT_SECRET=...

# ── 모니터링 (선택) ──
# LANGFUSE_PUBLIC_KEY=...
# LANGFUSE_SECRET_KEY=...
# LANGFUSE_HOST=https://cloud.langfuse.com
```

---

## 3. 프로젝트 구조

```
marketscope/
├── app/
│   ├── agents/                  # AI 에이전트 (15개)
│   │   ├── base.py              # BaseAgent 추상 클래스
│   │   ├── commander.py         # Commander (계획 + 판단)
│   │   ├── population.py        # 유동인구 분석
│   │   ├── revenue.py           # 매출 분석
│   │   ├── competition.py       # 경쟁 분석
│   │   ├── location.py          # 입지 분석
│   │   ├── trend.py             # 트렌드 분석
│   │   ├── financial.py         # 재무 분석
│   │   ├── risk.py              # 리스크 분석
│   │   ├── real_estate.py       # 부동산 분석
│   │   ├── regulatory.py        # 규제 분석
│   │   ├── narrative.py         # 내러티브 리포트
│   │   ├── visualization.py     # 시각화 설정
│   │   └── debate/              # 토론 시스템
│   │       ├── advocate.py      # 찬성 에이전트
│   │       ├── critic.py        # 비판 에이전트
│   │       ├── judge.py         # 판정 에이전트
│   │       └── orchestrator.py  # 토론 오케스트레이터
│   ├── api/                     # REST API
│   │   └── routes/              # FastAPI 라우터
│   ├── graph/                   # LangGraph 오케스트레이션
│   │   ├── nodes.py             # 20개 노드 함수
│   │   ├── edges.py             # 조건부 엣지 로직
│   │   ├── workflow.py          # DAG 구성
│   │   └── builder.py           # 그래프 빌더
│   ├── mcp_servers/             # MCP 도구 서버 (9개)
│   │   ├── public_data/         # 공공데이터
│   │   ├── maps/                # 카카오 지도
│   │   ├── real_estate/         # 부동산
│   │   ├── news/                # 뉴스/SNS
│   │   ├── regulatory/          # 규제/인허가
│   │   ├── finance/             # 금융/대출
│   │   ├── database/            # PostGIS 쿼리
│   │   ├── google_maps/         # Google Maps
│   │   └── naver_maps/          # 네이버 지도
│   ├── models/                  # Pydantic 모델
│   │   ├── state.py             # LangGraph State (MarketScopeState)
│   │   ├── agent_outputs.py     # 에이전트 출력 모델
│   │   └── debate.py            # 토론 모델
│   ├── monitoring/              # 모니터링
│   │   ├── metrics.py           # Prometheus 메트릭
│   │   ├── dag_tracer.py        # @trace_node 데코레이터
│   │   ├── mcp_monitor.py       # MCP 모니터링 미들웨어
│   │   └── langfuse_handler.py  # Langfuse 트레이싱
│   ├── tools/                   # MCP 클라이언트
│   │   └── mcp_client.py        # MCPClientRouter
│   ├── config.py                # Pydantic Settings
│   ├── logging_config.py        # structlog 설정
│   └── main.py                  # FastAPI 앱 엔트리포인트
├── tests/                       # 테스트
├── monitoring/                  # 모니터링 설정 (Prometheus, Grafana)
├── docker-compose.yml           # 메인 Docker Compose
├── docker-compose.monitoring.yml# 모니터링 스택
└── pyproject.toml               # 프로젝트 설정
```

---

## 4. 새 에이전트 추가 방법

### Step 1: 에이전트 클래스 생성

```python
# app/agents/my_new_agent.py
from app.agents.base import BaseAgent

class MyNewAgent(BaseAgent):
    """새로운 분석 에이전트."""

    agent_name = "my_new"
    system_prompt = """당신은 ... 전문 분석가입니다. ..."""

    async def run(self, state: dict) -> dict:
        # 1. 필요한 MCP 도구 호출
        data = await self.call_tool("database.query_nearby_stores", {...})

        # 2. LLM 호출
        result = await self.call_llm(prompt=f"...\n{data}")

        # 3. 결과 반환
        return {"my_new_result": result}
```

### Step 2: 출력 모델 정의

```python
# app/models/agent_outputs.py에 추가
class MyNewAnalysis(BaseModel):
    confidence_score: float
    # ... 분석 결과 필드
```

### Step 3: State에 필드 추가

```python
# app/models/state.py의 MarketScopeState에 추가
my_new_result: Optional[MyNewAnalysis]
```

### Step 4: 노드 함수 생성

```python
# app/graph/nodes.py에 추가
@trace_node
async def my_new_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.agents.my_new_agent import MyNewAgent
    agent = _create_agent(MyNewAgent)
    return await agent.run(state)
```

### Step 5: 워크플로우에 연결

```python
# app/graph/workflow.py에 추가
workflow.add_node("my_new", my_new_node)
workflow.add_edge("some_previous_node", "my_new")
```

---

## 5. 새 MCP 서버 추가 방법

### Step 1: 디렉토리 생성

```bash
mkdir -p app/mcp_servers/my_service
touch app/mcp_servers/my_service/{__init__,server,tools,schemas,api_client}.py
```

### Step 2: 기존 패턴을 따라 구현

- `server.py`: FastAPI 앱 + lifespan + /health, /tools/list, /tools/call
- `tools.py`: 도구 함수 + TOOL_REGISTRY dict
- `api_client.py`: 외부 API httpx 래퍼
- `schemas.py`: Pydantic 모델

### Step 3: Config에 등록

```python
# app/config.py의 mcp_servers에 추가
"my_service": "http://localhost:5109",
```

### Step 4: docker-compose.yml에 추가

```yaml
mcp-my-service:
  build: { context: ., dockerfile: Dockerfile }
  command: python -m app.mcp_servers.my_service.server
  ports: ["5109:5109"]
  env_file: .env
```

---

## 6. Git 워크플로우

### 6.1 브랜치 전략

```
main          ← 프로덕션 (protected)
  └── develop ← 개발 통합
       ├── feature/agent-xyz   ← 기능 개발
       ├── fix/mcp-timeout     ← 버그 수정
       └── docs/testing-spec   ← 문서
```

### 6.2 커밋 컨벤션

```
<type>(<scope>): <subject>

feat(agents): add trend analysis agent
fix(mcp): handle timeout in public_data server
docs(specs): add testing strategy document
refactor(graph): simplify debate routing
test(agents): add population agent unit tests
chore(docker): update postgres to 16
```

### 6.3 PR 규칙

- PR 제목은 커밋 컨벤션을 따른다
- 최소 1명의 리뷰어 승인 필요
- CI 통과 필수 (lint + test)
- Draft PR로 작업 중인 상태 공유 가능

---

## 7. 디버깅 가이드

### 7.1 로컬 디버깅

```bash
# structlog 컬러 출력으로 로그 확인
ENV=development uvicorn app.main:app --reload --log-level debug

# 특정 에이전트만 테스트
python -c "
import asyncio
from app.agents.population import PopulationAgent
from app.config import get_settings

async def test():
    agent = PopulationAgent(settings=get_settings(), mcp_client=None)
    result = await agent.run({'user_input': '합정동 카페', 'commander_plan': {...}})
    print(result)

asyncio.run(test())
"
```

### 7.2 MCP 서버 개별 테스트

```bash
# MCP 서버 단독 실행
python -m app.mcp_servers.maps.server

# 도구 호출 테스트
curl -X POST http://localhost:5101/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name": "maps.geocode", "arguments": {"address": "서울시 마포구 합정동"}}'
```

### 7.3 LangGraph 워크플로우 디버깅

```python
from app.graph.workflow import create_app
from app.models.state import create_initial_state

app = create_app()
state = create_initial_state("test-session", "합정동 카페 분석")

# 스트림 모드로 노드별 실행 추적
async for event in app.astream(state, {"configurable": {"thread_id": "debug-1"}}):
    for key, value in event.items():
        print(f"[{key}] → {list(value.keys()) if isinstance(value, dict) else type(value)}")
```

---

## 8. 코드 리뷰 가이드라인

### 8.1 체크리스트

- [ ] 기존 패턴과 일관성이 있는가? (BaseAgent 상속, TOOL_REGISTRY 패턴 등)
- [ ] Pydantic 모델이 정의되어 있는가? (입출력 스키마)
- [ ] 에러 처리가 적절한가? (try/except, 의미 있는 에러 메시지)
- [ ] structlog 이벤트가 추가되어 있는가? (로깅)
- [ ] `@trace_node` 데코레이터가 적용되어 있는가? (노드)
- [ ] State 필드가 `models/state.py`에 추가되어 있는가?
- [ ] 보안 취약점이 없는가? (SQL injection, 입력 검증)
- [ ] 테스트가 작성되어 있는가?

### 8.2 코드 스타일

- **Formatter**: `ruff format` (자동)
- **Linter**: `ruff check` (자동)
- **타입 힌트**: 모든 함수에 타입 힌트 필수
- **Docstring**: 공개 함수에 한국어 docstring
