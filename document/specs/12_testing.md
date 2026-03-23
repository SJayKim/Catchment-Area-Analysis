# MarketScope AI - 테스트 전략 명세서

> **문서 버전**: 1.0.0
> **최종 수정일**: 2026-03-21
> **작성자**: MarketScope AI 아키텍처 팀
> **상태**: Draft (Phase 1 MVP 기준)
>
> **Phase 1 MVP 테스트 범위**
> - **활성 에이전트**: population, revenue, competition, location (4개)
> - **비활성(Phase 2)**: trend, financial, risk, real_estate, regulatory
> - **Debate 시스템**: Phase 2 (테스트 스켈레톤만 준비)
> - **커버리지 목표**: 전체 80% 이상, 핵심 비즈니스 로직 90% 이상

---

## 목차

1. [테스트 아키텍처 개요](#1-테스트-아키텍처-개요)
2. [기술 스택](#2-기술-스택)
3. [테스트 디렉토리 구조](#3-테스트-디렉토리-구조)
4. [에이전트 단위 테스트 패턴](#4-에이전트-단위-테스트-패턴)
5. [MCP 서버 단위 테스트 패턴](#5-mcp-서버-단위-테스트-패턴)
6. [LangGraph 워크플로우 통합 테스트](#6-langgraph-워크플로우-통합-테스트)
7. [API 엔드포인트 테스트](#7-api-엔드포인트-테스트)
8. [테스트 픽스처 & 팩토리](#8-테스트-픽스처--팩토리)
9. [커버리지 목표](#9-커버리지-목표)
10. [테스트 데이터 관리 전략](#10-테스트-데이터-관리-전략)

---

## 1. 테스트 아키텍처 개요

### 1.1 3-Tier 테스트 피라미드

MarketScope AI는 3계층(3-Tier) 테스트 피라미드 전략을 채택한다. 하위 계층일수록 테스트 수가 많고 실행 속도가 빠르며, 상위 계층으로 갈수록 통합 범위가 넓어지고 실행 비용이 증가한다.

```
            ┌─────────┐
            │  E2E    │  ← 전체 분석 파이프라인 (소량, 느림)
            │  Tests  │
           ┌┴─────────┴┐
           │ Integration│  ← 워크플로우 / API / MCP 라우팅 (중간)
           │   Tests    │
          ┌┴────────────┴┐
          │  Unit Tests   │  ← 에이전트 / MCP 도구 / 모델 (대량, 빠름)
          └───────────────┘
```

| 계층 | 목적 | 실행 빈도 | 대상 |
|------|------|-----------|------|
| **단위 테스트 (Unit)** | 개별 함수/클래스의 정확성 검증 | 매 커밋 | 에이전트, MCP 도구, 그래프 노드/엣지, Pydantic 모델 |
| **통합 테스트 (Integration)** | 컴포넌트 간 상호작용 검증 | PR 머지 시 | LangGraph 워크플로우, API 엔드포인트, MCP 라우팅 |
| **E2E 테스트 (End-to-End)** | 전체 분석 파이프라인 검증 | 릴리스 전 | 사용자 요청 → 분석 결과 보고서 생성 |

### 1.2 테스트 실행 환경 분리

| 환경 | 데이터베이스 | Redis | LLM | MCP 서버 |
|------|-------------|-------|-----|----------|
| **Unit** | 없음 (모킹) | 없음 (모킹) | 모킹 | 모킹 |
| **Integration** | PostgreSQL (테스트 DB) | Redis (테스트 인스턴스) | 모킹 또는 Stub | 로컬 프로세스 |
| **E2E** | PostgreSQL (테스트 DB) | Redis (테스트 인스턴스) | 실제 API (선택적) | 실제 서버 |

### 1.3 테스트 실행 명령어

```bash
# 단위 테스트만 실행
pytest tests/unit/ -v --tb=short

# 통합 테스트만 실행
pytest tests/integration/ -v --tb=short

# E2E 테스트만 실행
pytest tests/e2e/ -v --tb=long

# 전체 테스트 실행 (커버리지 포함)
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

# 특정 마커로 필터링
pytest -m "not slow" tests/
pytest -m "unit" tests/
```

---

## 2. 기술 스택

### 2.1 핵심 테스트 프레임워크

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `pytest` | `>=8.0` | 테스트 프레임워크 코어 |
| `pytest-asyncio` | `>=0.23` | 비동기 테스트 지원 |
| `httpx` | `>=0.27` | `AsyncClient`를 통한 API 테스트 |
| `unittest.mock` | stdlib | LLM 호출 및 외부 서비스 모킹 |

### 2.2 보조 테스트 도구

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `pytest-cov` | `>=5.0` | 코드 커버리지 측정 |
| `pytest-env` | `>=1.1` | 테스트 환경 변수 관리 |
| `pytest-xdist` | `>=3.5` | 병렬 테스트 실행 |
| `pytest-timeout` | `>=2.3` | 테스트 타임아웃 설정 |
| `factory-boy` | `>=3.3` | 테스트 데이터 팩토리 |
| `faker` | `>=24.0` | 가짜 데이터 생성 |
| `respx` | `>=0.21` | httpx 요청 모킹 |
| `testcontainers` | `>=4.0` | PostgreSQL/Redis 컨테이너 |

### 2.3 pyproject.toml 테스트 설정

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "unit: 단위 테스트",
    "integration: 통합 테스트",
    "e2e: E2E 테스트",
    "slow: 느린 테스트 (CI에서 선택적 실행)",
]
filterwarnings = [
    "ignore::DeprecationWarning",
]
addopts = [
    "--strict-markers",
    "--tb=short",
    "-q",
]

[tool.coverage.run]
source = ["app"]
omit = [
    "app/config.py",
    "app/__init__.py",
    "*/migrations/*",
]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.",
    "@abstractmethod",
]
```

---

## 3. 테스트 디렉토리 구조

```
tests/
├── conftest.py                         # 전역 픽스처 (DB, Redis, 앱 클라이언트)
├── factories.py                        # factory-boy 팩토리 정의
├── fixtures/                           # 공유 테스트 데이터 (JSON/YAML)
│   ├── sample_state.json              # LangGraph 상태 샘플
│   ├── agent_outputs/                 # 에이전트 출력 샘플
│   │   ├── population_output.json
│   │   ├── revenue_output.json
│   │   ├── competition_output.json
│   │   └── location_output.json
│   ├── mcp_responses/                 # MCP 도구 응답 샘플
│   │   ├── database_query_result.json
│   │   ├── google_maps_result.json
│   │   └── naver_maps_result.json
│   └── api_requests/                  # API 요청 페이로드 샘플
│       ├── analysis_request.json
│       └── comparison_request.json
├── unit/
│   ├── __init__.py
│   ├── conftest.py                    # 단위 테스트 전용 픽스처
│   ├── agents/                        # 각 에이전트 단위 테스트
│   │   ├── __init__.py
│   │   ├── test_base_agent.py         # BaseAgent 추상 클래스 테스트
│   │   ├── test_population.py         # 유동인구 분석 에이전트
│   │   ├── test_revenue.py            # 매출 분석 에이전트
│   │   ├── test_competition.py        # 경쟁 분석 에이전트
│   │   └── test_location.py           # 입지 분석 에이전트
│   ├── mcp_servers/                   # 각 MCP 서버 도구 테스트
│   │   ├── __init__.py
│   │   ├── test_database_tools.py     # DB 쿼리 도구 테스트
│   │   ├── test_google_maps_tools.py  # Google Maps 도구 테스트
│   │   └── test_naver_maps_tools.py   # Naver Maps 도구 테스트
│   ├── graph/                         # 노드, 엣지 테스트
│   │   ├── __init__.py
│   │   ├── test_nodes.py              # 그래프 노드 함수 테스트
│   │   └── test_edges.py             # 조건부 엣지 로직 테스트
│   └── models/                        # Pydantic 모델 테스트
│       ├── __init__.py
│       ├── test_state.py              # LangGraph 상태 모델
│       ├── test_agent_outputs.py      # 에이전트 출력 모델
│       ├── test_common.py             # 공통 모델
│       └── test_report.py             # 리포트 모델
├── integration/
│   ├── __init__.py
│   ├── conftest.py                    # 통합 테스트 전용 픽스처 (DB, Redis)
│   ├── test_workflow.py               # LangGraph 워크플로우 통합 테스트
│   ├── test_api.py                    # API 엔드포인트 통합 테스트
│   └── test_mcp_routing.py            # MCP 라우팅 통합 테스트
└── e2e/
    ├── __init__.py
    ├── conftest.py                    # E2E 전용 픽스처
    └── test_analysis_flow.py          # 전체 분석 파이프라인 E2E 테스트
```

### 3.1 디렉토리별 책임

| 디렉토리 | 책임 | 외부 의존성 |
|----------|------|------------|
| `tests/unit/agents/` | 각 에이전트의 `analyze()` 메서드, 프롬프트 구성, 출력 파싱 검증 | 모두 모킹 |
| `tests/unit/mcp_servers/` | MCP 도구 함수의 입출력 검증, 에러 핸들링 | DB/API 모킹 |
| `tests/unit/graph/` | 노드 함수의 상태 변환, 엣지 조건 분기 로직 | 모두 모킹 |
| `tests/unit/models/` | Pydantic 모델 유효성 검증, 직렬화/역직렬화 | 없음 |
| `tests/integration/` | 컴포넌트 간 데이터 흐름, 실제 DB/Redis 연동 | 테스트 DB/Redis |
| `tests/e2e/` | 사용자 시나리오 기반 전체 파이프라인 | 전체 스택 |

---

## 4. 에이전트 단위 테스트 패턴

### 4.1 설계 원칙

에이전트 단위 테스트의 핵심은 **LLM 호출을 완전히 모킹**하여 결정론적(deterministic) 테스트를 보장하는 것이다. `unittest.mock`의 `AsyncMock`과 `patch`를 활용하여 LiteLLM 호출을 대체한다.

### 4.2 기본 에이전트 테스트 패턴

```python
# tests/unit/agents/test_population.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.population import PopulationAgent
from app.models.state import AnalysisState
from app.models.agent_outputs import PopulationOutput


class TestPopulationAgent:
    """유동인구 분석 에이전트 단위 테스트."""

    @pytest.fixture
    def agent(self):
        """PopulationAgent 인스턴스 생성."""
        return PopulationAgent()

    @pytest.fixture
    def sample_state(self) -> AnalysisState:
        """테스트용 분석 상태."""
        return AnalysisState(
            query="강남역 근처 카페 창업 분석",
            district_name="강남역",
            business_type="카페",
            analysis_mode="BASIC",
            agent_results={},
        )

    @pytest.fixture
    def mock_llm_response(self):
        """LLM 응답 모킹 데이터."""
        return {
            "weekday_avg": 45000,
            "weekend_avg": 62000,
            "peak_hours": ["12:00-14:00", "18:00-20:00"],
            "age_distribution": {"20대": 0.35, "30대": 0.28, "40대": 0.20},
            "trend": "increasing",
            "score": 8.5,
            "summary": "강남역 일대는 높은 유동인구를 보이며...",
        }

    @pytest.mark.asyncio
    async def test_analyze_returns_valid_output(
        self, agent, sample_state, mock_llm_response
    ):
        """analyze() 메서드가 유효한 PopulationOutput을 반환하는지 검증."""
        with patch.object(
            agent, "_call_llm", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_llm_response

            result = await agent.analyze(sample_state)

            assert isinstance(result, PopulationOutput)
            assert result.score >= 0
            assert result.score <= 10
            mock_llm.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_analyze_with_mcp_tool_calls(
        self, agent, sample_state
    ):
        """MCP 도구 호출이 올바르게 수행되는지 검증."""
        mock_mcp_result = {
            "population_data": [
                {"hour": "09:00", "count": 1200},
                {"hour": "12:00", "count": 4500},
            ]
        }

        with patch.object(
            agent, "_call_mcp_tool", new_callable=AsyncMock
        ) as mock_mcp, patch.object(
            agent, "_call_llm", new_callable=AsyncMock
        ) as mock_llm:
            mock_mcp.return_value = mock_mcp_result
            mock_llm.return_value = {"score": 7.5, "summary": "분석 완료"}

            result = await agent.analyze(sample_state)

            mock_mcp.assert_awaited()
            assert result is not None

    @pytest.mark.asyncio
    async def test_analyze_handles_llm_error(self, agent, sample_state):
        """LLM 호출 실패 시 적절한 에러 핸들링 검증."""
        with patch.object(
            agent, "_call_llm", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.side_effect = Exception("LLM API timeout")

            with pytest.raises(Exception, match="LLM API timeout"):
                await agent.analyze(sample_state)

    @pytest.mark.asyncio
    async def test_build_prompt_includes_district(self, agent, sample_state):
        """프롬프트에 상권 정보가 포함되는지 검증."""
        prompt = agent._build_prompt(sample_state)

        assert "강남역" in prompt
        assert "카페" in prompt

    def test_agent_metadata(self, agent):
        """에이전트 메타데이터 검증."""
        assert agent.agent_id == "population"
        assert agent.name == "유동인구 분석 에이전트"
        assert agent.model_name is not None
```

### 4.3 LLM 모킹 전략

```python
# tests/unit/conftest.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_litellm():
    """LiteLLM acompletion 호출을 전역 모킹."""
    with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
        mock.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"score": 7.5, "summary": "분석 결과"}'
                    )
                )
            ],
            usage=MagicMock(
                prompt_tokens=150,
                completion_tokens=200,
                total_tokens=350,
            ),
        )
        yield mock


@pytest.fixture
def mock_litellm_stream():
    """LiteLLM 스트리밍 응답 모킹."""
    async def mock_stream():
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="분석"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" 결과"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" 입니다"))]),
        ]
        for chunk in chunks:
            yield chunk

    with patch("litellm.acompletion", return_value=mock_stream()) as mock:
        yield mock
```

### 4.4 BaseAgent 테스트 패턴

```python
# tests/unit/agents/test_base_agent.py
import pytest
from unittest.mock import AsyncMock, patch
from abc import ABC

from app.agents.base import BaseAgent


class ConcreteTestAgent(BaseAgent):
    """테스트용 구체 에이전트 구현."""

    agent_id = "test_agent"
    name = "테스트 에이전트"
    model_name = "gpt-4o-mini"

    async def analyze(self, state):
        data = await self._call_mcp_tool("test_tool", {"param": "value"})
        result = await self._call_llm(
            prompt=f"분석: {data}",
            system_message="당신은 테스트 에이전트입니다.",
        )
        return result


class TestBaseAgent:
    """BaseAgent 추상 클래스 테스트."""

    def test_cannot_instantiate_abstract(self):
        """BaseAgent를 직접 인스턴스화할 수 없음을 검증."""
        with pytest.raises(TypeError):
            BaseAgent()

    def test_concrete_agent_instantiation(self):
        """구체 에이전트가 정상 인스턴스화됨을 검증."""
        agent = ConcreteTestAgent()
        assert agent.agent_id == "test_agent"

    @pytest.mark.asyncio
    async def test_call_llm_with_retry(self):
        """LLM 호출 재시도 로직 검증."""
        agent = ConcreteTestAgent()

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.side_effect = [
                Exception("Rate limit"),
                MagicMock(
                    choices=[MagicMock(message=MagicMock(content="결과"))]
                ),
            ]

            result = await agent._call_llm(
                prompt="테스트", system_message="시스템"
            )
            assert mock.await_count == 2

    @pytest.mark.asyncio
    async def test_call_mcp_tool_timeout(self):
        """MCP 도구 호출 타임아웃 검증."""
        agent = ConcreteTestAgent()

        with patch.object(
            agent, "_call_mcp_tool", new_callable=AsyncMock
        ) as mock:
            mock.side_effect = TimeoutError("MCP tool timeout")

            with pytest.raises(TimeoutError):
                await agent._call_mcp_tool("slow_tool", {})
```

---

## 5. MCP 서버 단위 테스트 패턴

### 5.1 설계 원칙

MCP 서버 도구 테스트는 각 도구 함수의 **입력 유효성 검증**, **외부 API/DB 호출 모킹**, **응답 변환 로직** 검증에 집중한다. 외부 서비스 호출은 모두 모킹 처리한다.

### 5.2 데이터베이스 MCP 도구 테스트

```python
# tests/unit/mcp_servers/test_database_tools.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.tools.mcp_servers.database import (
    query_population_data,
    query_revenue_data,
    query_competition_data,
)


class TestDatabaseTools:
    """데이터베이스 MCP 도구 단위 테스트."""

    @pytest.fixture
    def mock_db_session(self):
        """비동기 DB 세션 모킹."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_query_population_data_valid_input(self, mock_db_session):
        """유효한 입력으로 유동인구 데이터 조회."""
        mock_rows = [
            {"hour": "09:00", "count": 1200, "date": "2026-03-01"},
            {"hour": "12:00", "count": 4500, "date": "2026-03-01"},
        ]
        mock_db_session.execute.return_value = MagicMock(
            fetchall=MagicMock(return_value=mock_rows)
        )

        result = await query_population_data(
            session=mock_db_session,
            district_code="11680",
            start_date="2026-01-01",
            end_date="2026-03-01",
        )

        assert len(result) == 2
        assert result[0]["hour"] == "09:00"
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_population_data_empty_result(self, mock_db_session):
        """조회 결과가 없는 경우 빈 리스트 반환."""
        mock_db_session.execute.return_value = MagicMock(
            fetchall=MagicMock(return_value=[])
        )

        result = await query_population_data(
            session=mock_db_session,
            district_code="99999",
            start_date="2026-01-01",
            end_date="2026-03-01",
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_query_population_data_invalid_date_format(
        self, mock_db_session
    ):
        """잘못된 날짜 형식 입력 시 ValueError 발생."""
        with pytest.raises(ValueError, match="날짜 형식"):
            await query_population_data(
                session=mock_db_session,
                district_code="11680",
                start_date="invalid-date",
                end_date="2026-03-01",
            )

    @pytest.mark.asyncio
    async def test_query_revenue_data_with_postgis(self, mock_db_session):
        """PostGIS 공간 쿼리를 포함한 매출 데이터 조회."""
        mock_rows = [
            {
                "business_type": "카페",
                "monthly_revenue": 15000000,
                "store_count": 45,
            }
        ]
        mock_db_session.execute.return_value = MagicMock(
            fetchall=MagicMock(return_value=mock_rows)
        )

        result = await query_revenue_data(
            session=mock_db_session,
            latitude=37.4979,
            longitude=127.0276,
            radius_meters=500,
            business_type="카페",
        )

        assert result[0]["business_type"] == "카페"
        assert result[0]["monthly_revenue"] == 15000000
```

### 5.3 Google Maps MCP 도구 테스트

```python
# tests/unit/mcp_servers/test_google_maps_tools.py
import pytest
from unittest.mock import AsyncMock, patch

from app.tools.mcp_servers.google_maps import (
    search_nearby_places,
    get_place_details,
    get_directions,
)


class TestGoogleMapsTools:
    """Google Maps MCP 도구 단위 테스트."""

    @pytest.fixture
    def mock_google_client(self):
        """Google Maps API 클라이언트 모킹."""
        client = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_search_nearby_places(self, mock_google_client):
        """주변 장소 검색 결과 반환 검증."""
        mock_google_client.nearby_search.return_value = {
            "results": [
                {
                    "name": "스타벅스 강남역점",
                    "place_id": "ChIJ...",
                    "geometry": {
                        "location": {"lat": 37.4979, "lng": 127.0276}
                    },
                    "rating": 4.2,
                    "user_ratings_total": 1500,
                },
            ]
        }

        with patch(
            "app.tools.mcp_servers.google_maps.get_client",
            return_value=mock_google_client,
        ):
            result = await search_nearby_places(
                latitude=37.4979,
                longitude=127.0276,
                radius=500,
                place_type="cafe",
            )

        assert len(result) == 1
        assert result[0]["name"] == "스타벅스 강남역점"

    @pytest.mark.asyncio
    async def test_search_nearby_places_api_error(self, mock_google_client):
        """Google Maps API 에러 시 적절한 예외 처리."""
        mock_google_client.nearby_search.side_effect = Exception(
            "OVER_QUERY_LIMIT"
        )

        with patch(
            "app.tools.mcp_servers.google_maps.get_client",
            return_value=mock_google_client,
        ):
            with pytest.raises(Exception, match="OVER_QUERY_LIMIT"):
                await search_nearby_places(
                    latitude=37.4979,
                    longitude=127.0276,
                    radius=500,
                    place_type="cafe",
                )
```

### 5.4 Naver Maps MCP 도구 테스트

```python
# tests/unit/mcp_servers/test_naver_maps_tools.py
import pytest
from unittest.mock import AsyncMock, patch

from app.tools.mcp_servers.naver_maps import (
    search_local,
    get_geocode,
    get_reverse_geocode,
)


class TestNaverMapsTools:
    """Naver Maps MCP 도구 단위 테스트."""

    @pytest.mark.asyncio
    async def test_search_local_returns_businesses(self):
        """네이버 지역 검색 결과 반환 검증."""
        mock_response = {
            "items": [
                {
                    "title": "강남역 카페거리",
                    "category": "카페",
                    "address": "서울특별시 강남구 역삼동",
                    "mapx": "1270276",
                    "mapy": "374979",
                }
            ],
            "total": 1,
        }

        with patch(
            "app.tools.mcp_servers.naver_maps._call_naver_api",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await search_local(query="강남역 카페", display=10)

        assert len(result["items"]) == 1
        assert result["items"][0]["category"] == "카페"

    @pytest.mark.asyncio
    async def test_get_geocode_valid_address(self):
        """유효한 주소의 지오코딩 변환 검증."""
        mock_response = {
            "addresses": [
                {
                    "x": "127.0276",
                    "y": "37.4979",
                    "roadAddress": "서울특별시 강남구 테헤란로 100",
                }
            ]
        }

        with patch(
            "app.tools.mcp_servers.naver_maps._call_naver_api",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await get_geocode(address="서울특별시 강남구 테헤란로 100")

        assert result["addresses"][0]["x"] == "127.0276"
```

---

## 6. LangGraph 워크플로우 통합 테스트

### 6.1 설계 원칙

워크플로우 통합 테스트는 LangGraph의 **그래프 실행 흐름**, **노드 간 상태 전달**, **조건부 엣지 분기**, **병렬 실행(fan-out/fan-in)** 을 검증한다. LLM 호출은 모킹하되, 그래프 실행 엔진은 실제로 동작시킨다.

### 6.2 워크플로우 통합 테스트

```python
# tests/integration/test_workflow.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.graph.workflow import create_analysis_workflow
from app.models.state import AnalysisState


class TestAnalysisWorkflow:
    """LangGraph 분석 워크플로우 통합 테스트."""

    @pytest.fixture
    def mock_agents(self):
        """모든 에이전트의 analyze() 메서드를 모킹."""
        agents = {}
        for agent_id in ["population", "revenue", "competition", "location"]:
            mock = AsyncMock()
            mock.return_value = {
                "score": 7.5,
                "summary": f"{agent_id} 분석 완료",
                "data": {"key": "value"},
            }
            agents[agent_id] = mock
        return agents

    @pytest.fixture
    def initial_state(self) -> AnalysisState:
        """워크플로우 초기 상태."""
        return {
            "query": "강남역 근처 카페 창업 분석",
            "district_name": "강남역",
            "business_type": "카페",
            "analysis_mode": "BASIC",
            "agent_results": {},
            "errors": [],
            "status": "pending",
        }

    @pytest.mark.asyncio
    async def test_basic_workflow_completes(
        self, mock_agents, initial_state
    ):
        """BASIC 모드 워크플로우가 정상 완료되는지 검증."""
        with patch(
            "app.graph.nodes.get_agent", side_effect=lambda id: mock_agents[id]
        ):
            workflow = create_analysis_workflow(mode="BASIC")
            result = await workflow.ainvoke(initial_state)

        assert result["status"] == "completed"
        assert "population" in result["agent_results"]
        assert "revenue" in result["agent_results"]

    @pytest.mark.asyncio
    async def test_parallel_agent_execution(
        self, mock_agents, initial_state
    ):
        """에이전트가 병렬로 실행되는지 검증 (fan-out/fan-in)."""
        execution_order = []

        async def track_execution(agent_id):
            execution_order.append(("start", agent_id))
            result = await mock_agents[agent_id]()
            execution_order.append(("end", agent_id))
            return result

        with patch(
            "app.graph.nodes.execute_agent",
            side_effect=track_execution,
        ):
            workflow = create_analysis_workflow(mode="BASIC")
            await workflow.ainvoke(initial_state)

        # 병렬 실행 시, 독립 에이전트들의 start가 연속됨
        start_events = [e for e in execution_order if e[0] == "start"]
        assert len(start_events) >= 2  # 최소 2개 에이전트가 시작됨

    @pytest.mark.asyncio
    async def test_workflow_handles_agent_failure(
        self, mock_agents, initial_state
    ):
        """개별 에이전트 실패 시 워크플로우가 graceful하게 처리."""
        mock_agents["population"].side_effect = Exception("분석 실패")

        with patch(
            "app.graph.nodes.get_agent", side_effect=lambda id: mock_agents[id]
        ):
            workflow = create_analysis_workflow(mode="BASIC")
            result = await workflow.ainvoke(initial_state)

        assert "population" in [e["agent_id"] for e in result["errors"]]
        assert result["status"] in ["completed_with_errors", "completed"]

    @pytest.mark.asyncio
    async def test_conditional_edge_routing(self, initial_state):
        """분석 모드에 따른 조건부 엣지 분기 검증."""
        from app.graph.edges import route_by_analysis_mode

        # BASIC 모드
        initial_state["analysis_mode"] = "BASIC"
        route = route_by_analysis_mode(initial_state)
        assert "debate" not in route  # Phase 1: Debate 비활성

        # COMPARISON 모드
        initial_state["analysis_mode"] = "COMPARISON"
        route = route_by_analysis_mode(initial_state)
        assert isinstance(route, (str, list))
```

### 6.3 그래프 노드 단위 테스트

```python
# tests/unit/graph/test_nodes.py
import pytest
from unittest.mock import AsyncMock, patch

from app.graph.nodes import (
    commander_node,
    agent_node,
    report_node,
    merge_results_node,
)


class TestGraphNodes:
    """그래프 노드 함수 단위 테스트."""

    @pytest.mark.asyncio
    async def test_commander_node_creates_execution_plan(self):
        """Commander 노드가 실행 계획을 생성하는지 검증."""
        state = {
            "query": "강남역 카페 분석",
            "analysis_mode": "BASIC",
        }

        with patch(
            "app.graph.nodes.commander_agent.plan",
            new_callable=AsyncMock,
        ) as mock_plan:
            mock_plan.return_value = {
                "active_agents": ["population", "revenue", "competition", "location"],
                "execution_order": [
                    ["population", "location"],  # 병렬 그룹 1
                    ["revenue", "competition"],   # 병렬 그룹 2
                ],
            }

            result = await commander_node(state)

        assert "execution_plan" in result
        assert len(result["execution_plan"]["active_agents"]) == 4

    @pytest.mark.asyncio
    async def test_merge_results_node_aggregates_scores(self):
        """결과 병합 노드가 점수를 정확히 집계하는지 검증."""
        state = {
            "agent_results": {
                "population": {"score": 8.0},
                "revenue": {"score": 7.0},
                "competition": {"score": 6.5},
                "location": {"score": 9.0},
            }
        }

        result = await merge_results_node(state)

        assert "overall_score" in result
        assert 6.0 <= result["overall_score"] <= 10.0
```

### 6.4 조건부 엣지 테스트

```python
# tests/unit/graph/test_edges.py
import pytest
from app.graph.edges import (
    route_by_analysis_mode,
    should_run_debate,
    check_agent_completion,
)


class TestConditionalEdges:
    """조건부 엣지 로직 단위 테스트."""

    def test_route_basic_mode(self):
        """BASIC 모드 라우팅."""
        state = {"analysis_mode": "BASIC", "agent_results": {}}
        result = route_by_analysis_mode(state)
        assert result == "run_agents"

    def test_route_comparison_mode(self):
        """COMPARISON 모드 라우팅."""
        state = {
            "analysis_mode": "COMPARISON",
            "comparison_districts": ["강남역", "홍대입구"],
        }
        result = route_by_analysis_mode(state)
        assert result == "run_comparison"

    def test_should_run_debate_phase1_disabled(self):
        """Phase 1에서 Debate 시스템이 비활성화됨을 검증."""
        state = {"analysis_mode": "BASIC", "phase": 1}
        assert should_run_debate(state) is False

    def test_check_agent_completion_all_done(self):
        """모든 에이전트 완료 시 다음 단계로 진행."""
        state = {
            "execution_plan": {
                "active_agents": ["population", "revenue"]
            },
            "agent_results": {
                "population": {"score": 8.0},
                "revenue": {"score": 7.0},
            },
        }
        result = check_agent_completion(state)
        assert result == "merge_results"

    def test_check_agent_completion_partial(self):
        """일부 에이전트만 완료 시 대기."""
        state = {
            "execution_plan": {
                "active_agents": ["population", "revenue"]
            },
            "agent_results": {
                "population": {"score": 8.0},
            },
        }
        result = check_agent_completion(state)
        assert result == "wait"
```

---

## 7. API 엔드포인트 테스트

### 7.1 설계 원칙

API 테스트는 `httpx.AsyncClient`를 사용하여 FastAPI 애플리케이션에 대한 비동기 HTTP 요청을 수행한다. 실제 서버를 기동하지 않고 ASGI 프로토콜을 통해 직접 테스트한다.

### 7.2 API 테스트 픽스처

```python
# tests/integration/conftest.py
import pytest
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.config import settings


@pytest.fixture
async def async_client():
    """httpx AsyncClient 픽스처."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.fixture
async def test_db_session():
    """테스트용 비동기 DB 세션."""
    test_engine = create_async_engine(
        settings.TEST_DATABASE_URL,
        echo=False,
    )
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()
```

### 7.3 분석 API 엔드포인트 테스트

```python
# tests/integration/test_api.py
import pytest
import httpx
from unittest.mock import AsyncMock, patch


class TestAnalysisAPI:
    """분석 API 엔드포인트 통합 테스트."""

    @pytest.mark.asyncio
    async def test_create_analysis_success(self, async_client: httpx.AsyncClient):
        """분석 요청 생성 - 성공 케이스."""
        request_body = {
            "query": "강남역 근처 카페 창업 분석해줘",
            "district_name": "강남역",
            "business_type": "카페",
            "analysis_mode": "BASIC",
        }

        with patch(
            "app.api.routes.analysis.start_analysis",
            new_callable=AsyncMock,
        ) as mock_start:
            mock_start.return_value = {
                "analysis_id": "analysis-uuid-001",
                "status": "processing",
            }

            response = await async_client.post(
                "/api/v1/analysis",
                json=request_body,
            )

        assert response.status_code == 202
        data = response.json()
        assert "analysis_id" in data
        assert data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_create_analysis_invalid_request(
        self, async_client: httpx.AsyncClient
    ):
        """잘못된 요청 형식 - 422 Validation Error."""
        request_body = {
            "query": "",  # 빈 쿼리
        }

        response = await async_client.post(
            "/api/v1/analysis",
            json=request_body,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_analysis_result(self, async_client: httpx.AsyncClient):
        """분석 결과 조회 - 완료된 분석."""
        analysis_id = "analysis-uuid-001"

        with patch(
            "app.api.routes.analysis.get_analysis",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = {
                "analysis_id": analysis_id,
                "status": "completed",
                "result": {
                    "overall_score": 7.8,
                    "agent_results": {
                        "population": {"score": 8.0},
                        "revenue": {"score": 7.5},
                    },
                },
            }

            response = await async_client.get(
                f"/api/v1/analysis/{analysis_id}"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result"]["overall_score"] == 7.8

    @pytest.mark.asyncio
    async def test_get_analysis_not_found(self, async_client: httpx.AsyncClient):
        """존재하지 않는 분석 결과 조회 - 404."""
        with patch(
            "app.api.routes.analysis.get_analysis",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.get(
                "/api/v1/analysis/nonexistent-id"
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_analysis_sse_stream(self, async_client: httpx.AsyncClient):
        """SSE 스트리밍 엔드포인트 검증."""
        analysis_id = "analysis-uuid-001"

        async def mock_event_stream():
            events = [
                {"event": "agent_start", "data": {"agent": "population"}},
                {"event": "agent_complete", "data": {"agent": "population", "score": 8.0}},
                {"event": "analysis_complete", "data": {"overall_score": 7.8}},
            ]
            for event in events:
                yield event

        with patch(
            "app.api.routes.analysis.stream_analysis_events",
            return_value=mock_event_stream(),
        ):
            response = await async_client.get(
                f"/api/v1/analysis/{analysis_id}/stream",
                headers={"Accept": "text/event-stream"},
            )

        assert response.status_code == 200


class TestHealthAPI:
    """헬스체크 API 테스트."""

    @pytest.mark.asyncio
    async def test_health_check(self, async_client: httpx.AsyncClient):
        """헬스체크 엔드포인트 정상 응답."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_readiness_check(self, async_client: httpx.AsyncClient):
        """Readiness 체크 (DB, Redis 연결 확인)."""
        with patch(
            "app.api.routes.health.check_dependencies",
            new_callable=AsyncMock,
            return_value={"database": "ok", "redis": "ok", "mcp_servers": "ok"},
        ):
            response = await async_client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["database"] == "ok"
        assert data["redis"] == "ok"
```

### 7.4 MCP 라우팅 통합 테스트

```python
# tests/integration/test_mcp_routing.py
import pytest
from unittest.mock import AsyncMock, patch

from app.tools.mcp_client import MCPClient
from app.tools.registry import ToolRegistry


class TestMCPRouting:
    """MCP 라우팅 통합 테스트."""

    @pytest.fixture
    def mcp_client(self):
        """MCP 클라이언트 인스턴스."""
        return MCPClient()

    @pytest.mark.asyncio
    async def test_tool_registry_discovers_tools(self, mcp_client):
        """도구 레지스트리가 MCP 서버에서 도구를 검색하는지 검증."""
        with patch.object(
            mcp_client, "list_tools", new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = [
                {"name": "query_population", "server": "database"},
                {"name": "search_nearby", "server": "google_maps"},
                {"name": "search_local", "server": "naver_maps"},
            ]

            registry = ToolRegistry(mcp_client)
            tools = await registry.discover()

        assert len(tools) == 3
        assert any(t["name"] == "query_population" for t in tools)

    @pytest.mark.asyncio
    async def test_tool_call_routes_to_correct_server(self, mcp_client):
        """도구 호출이 올바른 MCP 서버로 라우팅되는지 검증."""
        with patch.object(
            mcp_client, "call_tool", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = {"result": "data"}

            result = await mcp_client.call_tool(
                server="database",
                tool_name="query_population",
                arguments={"district_code": "11680"},
            )

        mock_call.assert_awaited_once_with(
            server="database",
            tool_name="query_population",
            arguments={"district_code": "11680"},
        )
        assert result["result"] == "data"

    @pytest.mark.asyncio
    async def test_mcp_server_failover(self, mcp_client):
        """MCP 서버 장애 시 폴백 처리 검증."""
        with patch.object(
            mcp_client, "call_tool", new_callable=AsyncMock
        ) as mock_call:
            mock_call.side_effect = ConnectionError("MCP server down")

            with pytest.raises(ConnectionError):
                await mcp_client.call_tool(
                    server="database",
                    tool_name="query_population",
                    arguments={"district_code": "11680"},
                )
```

---

## 8. 테스트 픽스처 & 팩토리

### 8.1 전역 픽스처 (conftest.py)

```python
# tests/conftest.py
import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ──────────────────────────────────────────────
# 1. 테스트 데이터 로더
# ──────────────────────────────────────────────

@pytest.fixture
def load_fixture():
    """JSON 픽스처 파일 로더."""
    def _load(filename: str) -> dict:
        filepath = FIXTURES_DIR / filename
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return _load


@pytest.fixture
def sample_analysis_state(load_fixture):
    """샘플 분석 상태."""
    return load_fixture("sample_state.json")


@pytest.fixture
def sample_population_output(load_fixture):
    """유동인구 에이전트 출력 샘플."""
    return load_fixture("agent_outputs/population_output.json")


# ──────────────────────────────────────────────
# 2. 모킹 픽스처
# ──────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    """Redis 클라이언트 모킹."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.publish = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_mcp_client():
    """MCP 클라이언트 모킹."""
    client = AsyncMock()
    client.call_tool = AsyncMock(return_value={"result": "mocked"})
    client.list_tools = AsyncMock(return_value=[])
    return client


# ──────────────────────────────────────────────
# 3. 환경 설정
# ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """테스트 환경 변수 설정."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/marketscope_test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
    monkeypatch.setenv("LITELLM_API_KEY", "test-api-key")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-google-key")
    monkeypatch.setenv("NAVER_CLIENT_ID", "test-naver-id")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "test-naver-secret")
```

### 8.2 팩토리 패턴 (factory-boy)

```python
# tests/factories.py
import factory
from factory import fuzzy
from datetime import datetime, timedelta

from app.models.agent_outputs import (
    PopulationOutput,
    RevenueOutput,
    CompetitionOutput,
    LocationOutput,
)
from app.models.state import AnalysisState


class AnalysisStateFactory(factory.Factory):
    """분석 상태 팩토리."""

    class Meta:
        model = dict

    query = factory.Faker("sentence", locale="ko_KR")
    district_name = factory.fuzzy.FuzzyChoice([
        "강남역", "홍대입구", "명동", "여의도", "판교", "잠실", "건대입구",
        "신촌", "이태원", "성수동",
    ])
    business_type = factory.fuzzy.FuzzyChoice([
        "카페", "음식점", "편의점", "헬스장", "미용실", "약국", "베이커리",
    ])
    analysis_mode = factory.fuzzy.FuzzyChoice(["BASIC", "COMPARISON", "QUICK"])
    agent_results = factory.LazyFunction(dict)
    errors = factory.LazyFunction(list)
    status = "pending"


class PopulationOutputFactory(factory.Factory):
    """유동인구 분석 출력 팩토리."""

    class Meta:
        model = dict

    weekday_avg = factory.fuzzy.FuzzyInteger(10000, 100000)
    weekend_avg = factory.fuzzy.FuzzyInteger(15000, 120000)
    peak_hours = factory.LazyFunction(
        lambda: ["12:00-14:00", "18:00-20:00"]
    )
    age_distribution = factory.LazyFunction(
        lambda: {"20대": 0.30, "30대": 0.25, "40대": 0.20, "50대": 0.15, "기타": 0.10}
    )
    trend = factory.fuzzy.FuzzyChoice(["increasing", "stable", "decreasing"])
    score = factory.fuzzy.FuzzyFloat(1.0, 10.0)
    summary = factory.Faker("paragraph", locale="ko_KR")


class RevenueOutputFactory(factory.Factory):
    """매출 분석 출력 팩토리."""

    class Meta:
        model = dict

    monthly_avg_revenue = factory.fuzzy.FuzzyInteger(5000000, 100000000)
    revenue_trend = factory.fuzzy.FuzzyChoice(["increasing", "stable", "decreasing"])
    peak_season = factory.fuzzy.FuzzyChoice(["봄", "여름", "가을", "겨울"])
    estimated_daily_customers = factory.fuzzy.FuzzyInteger(50, 1000)
    score = factory.fuzzy.FuzzyFloat(1.0, 10.0)
    summary = factory.Faker("paragraph", locale="ko_KR")


class CompetitionOutputFactory(factory.Factory):
    """경쟁 분석 출력 팩토리."""

    class Meta:
        model = dict

    competitor_count = factory.fuzzy.FuzzyInteger(0, 100)
    market_saturation = factory.fuzzy.FuzzyFloat(0.0, 1.0)
    avg_competitor_rating = factory.fuzzy.FuzzyFloat(1.0, 5.0)
    differentiation_opportunities = factory.LazyFunction(
        lambda: ["특화 메뉴", "인테리어 차별화", "디지털 주문 시스템"]
    )
    score = factory.fuzzy.FuzzyFloat(1.0, 10.0)
    summary = factory.Faker("paragraph", locale="ko_KR")


class LocationOutputFactory(factory.Factory):
    """입지 분석 출력 팩토리."""

    class Meta:
        model = dict

    transit_accessibility = factory.fuzzy.FuzzyFloat(1.0, 10.0)
    visibility_score = factory.fuzzy.FuzzyFloat(1.0, 10.0)
    nearby_facilities = factory.LazyFunction(
        lambda: ["지하철역", "버스정류장", "대학교", "오피스빌딩"]
    )
    parking_availability = factory.fuzzy.FuzzyChoice(["good", "moderate", "poor"])
    score = factory.fuzzy.FuzzyFloat(1.0, 10.0)
    summary = factory.Faker("paragraph", locale="ko_KR")
```

### 8.3 픽스처 데이터 파일 예시

```json
// tests/fixtures/sample_state.json
{
    "query": "강남역 근처 카페 창업 분석",
    "district_name": "강남역",
    "business_type": "카페",
    "analysis_mode": "BASIC",
    "agent_results": {},
    "errors": [],
    "status": "pending",
    "execution_plan": {
        "active_agents": ["population", "revenue", "competition", "location"],
        "execution_order": [
            ["population", "location"],
            ["revenue", "competition"]
        ]
    }
}
```

```json
// tests/fixtures/agent_outputs/population_output.json
{
    "weekday_avg": 45000,
    "weekend_avg": 62000,
    "peak_hours": ["12:00-14:00", "18:00-20:00"],
    "age_distribution": {
        "10대": 0.05,
        "20대": 0.35,
        "30대": 0.28,
        "40대": 0.20,
        "50대 이상": 0.12
    },
    "gender_ratio": {"남성": 0.48, "여성": 0.52},
    "trend": "increasing",
    "score": 8.5,
    "summary": "강남역 일대는 일평균 유동인구 약 45,000명으로 서울 주요 상권 중 상위권에 해당합니다."
}
```

---

## 9. 커버리지 목표

### 9.1 전체 커버리지 기준

| 구분 | 목표 커버리지 | 최소 기준 | 비고 |
|------|-------------|----------|------|
| **전체 프로젝트** | 85% | **80%** | `fail_under = 80` 설정 |
| **핵심 비즈니스 로직** | 95% | **90%** | 에이전트, 그래프 노드/엣지 |
| **API 엔드포인트** | 90% | **85%** | 모든 라우트 핸들러 |
| **Pydantic 모델** | 95% | **90%** | 유효성 검증 로직 |
| **MCP 도구 함수** | 90% | **85%** | 도구별 입출력 검증 |
| **유틸리티/헬퍼** | 80% | **70%** | 설정, 로깅 등 |

### 9.2 모듈별 세부 기준

```
app/
├── agents/          → 90% 이상 (analyze, prompt 구성, 출력 파싱)
├── graph/
│   ├── nodes.py     → 95% 이상 (모든 노드 함수)
│   ├── edges.py     → 95% 이상 (모든 분기 경로)
│   └── workflow.py  → 85% 이상 (워크플로우 구성)
├── tools/
│   ├── mcp_client.py    → 85% 이상
│   └── mcp_servers/     → 90% 이상 (각 도구 함수)
├── api/
│   └── routes/      → 90% 이상 (모든 엔드포인트)
├── models/          → 95% 이상 (유효성 검증)
└── config.py        → 제외 (환경 설정)
```

### 9.3 커버리지 측정 및 리포팅

```bash
# 커버리지 측정 실행
pytest tests/ \
    --cov=app \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-report=xml:coverage.xml \
    --cov-fail-under=80

# 특정 모듈 커버리지 확인
pytest tests/unit/agents/ --cov=app/agents --cov-report=term-missing

# CI/CD 환경용 (XML 리포트 + 실패 기준 적용)
pytest tests/ \
    --cov=app \
    --cov-report=xml:coverage.xml \
    --cov-fail-under=80 \
    --junitxml=test-results.xml
```

### 9.4 커버리지 제외 항목

다음 코드는 커버리지 측정에서 제외한다.

| 제외 대상 | 사유 |
|----------|------|
| `app/config.py` | 환경 변수 설정, 런타임 의존 |
| `app/__init__.py` | 패키지 초기화 |
| `alembic/` | DB 마이그레이션 스크립트 |
| `TYPE_CHECKING` 블록 | 타입 힌트 전용 임포트 |
| `@abstractmethod` | 추상 메서드 (구현체에서 테스트) |
| `if __name__ == "__main__"` | 직접 실행 블록 |

### 9.5 CI 파이프라인 연동

```yaml
# .github/workflows/test.yml (발췌)
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:16-3.4
        env:
          POSTGRES_DB: marketscope_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - name: Run Unit Tests
        run: pytest tests/unit/ --cov=app --cov-report=xml -q

      - name: Run Integration Tests
        run: pytest tests/integration/ --cov=app --cov-append --cov-report=xml -q

      - name: Check Coverage Threshold
        run: |
          coverage report --fail-under=80

      - name: Upload Coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
```

---

## 10. 테스트 데이터 관리 전략

### 10.1 데이터 관리 원칙

| 원칙 | 설명 |
|------|------|
| **격리성 (Isolation)** | 각 테스트는 독립적으로 실행 가능해야 하며, 다른 테스트의 데이터에 의존하지 않는다 |
| **재현성 (Reproducibility)** | 동일한 입력으로 항상 동일한 결과를 생성한다 |
| **최소성 (Minimality)** | 테스트에 필요한 최소한의 데이터만 사용한다 |
| **보안성 (Security)** | 실제 API 키, 사용자 정보 등 민감 데이터를 포함하지 않는다 |

### 10.2 데이터 계층 전략

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: 정적 픽스처 (Static Fixtures)                           │
│  ├── JSON/YAML 파일로 관리                                       │
│  ├── 버전 관리 대상 (Git 추적)                                    │
│  └── 용도: 예측 가능한 기본 테스트 데이터                           │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2: 동적 팩토리 (Dynamic Factories)                         │
│  ├── factory-boy + Faker 활용                                    │
│  ├── 런타임 생성                                                 │
│  └── 용도: 다양한 시나리오의 랜덤 데이터 생성                       │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3: 데이터베이스 시딩 (DB Seeding)                           │
│  ├── 통합/E2E 테스트 전용                                        │
│  ├── 테스트 시작 시 시딩, 종료 시 롤백                             │
│  └── 용도: 실제 DB 쿼리 테스트                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 10.3 정적 픽스처 관리

```
tests/fixtures/
├── sample_state.json                  # LangGraph 상태 샘플
├── agent_outputs/                     # 에이전트별 출력 샘플
│   ├── population_output.json         #   - 유동인구 (정상 결과)
│   ├── population_output_empty.json   #   - 유동인구 (빈 결과)
│   ├── revenue_output.json            #   - 매출 (정상 결과)
│   ├── competition_output.json        #   - 경쟁 (정상 결과)
│   └── location_output.json           #   - 입지 (정상 결과)
├── mcp_responses/                     # MCP 서버 응답 샘플
│   ├── database_query_result.json     #   - DB 쿼리 결과
│   ├── database_empty_result.json     #   - DB 빈 결과
│   ├── google_maps_result.json        #   - Google Maps 응답
│   ├── google_maps_error.json         #   - Google Maps 에러 응답
│   ├── naver_maps_result.json         #   - Naver Maps 응답
│   └── naver_maps_error.json          #   - Naver Maps 에러 응답
└── api_requests/                      # API 요청 페이로드 샘플
    ├── analysis_request.json          #   - 분석 요청 (정상)
    ├── analysis_request_invalid.json  #   - 분석 요청 (유효하지 않음)
    └── comparison_request.json        #   - 비교 분석 요청
```

### 10.4 데이터베이스 테스트 데이터 관리

```python
# tests/integration/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text


@pytest.fixture(scope="session")
async def test_engine():
    """테스트 세션 동안 유지되는 DB 엔진."""
    engine = create_async_engine(
        "postgresql+asyncpg://test:test@localhost:5432/marketscope_test",
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db(test_engine):
    """테스트 DB 스키마 초기화 (세션 단위)."""
    async with test_engine.begin() as conn:
        # PostGIS 확장 활성화
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        # 테이블 생성 (Alembic 마이그레이션 적용)
        # await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        # 테스트 종료 후 정리
        # await conn.run_sync(Base.metadata.drop_all)
        pass


@pytest.fixture
async def db_session(test_engine):
    """각 테스트마다 트랜잭션으로 격리된 DB 세션."""
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn)

        yield session

        await session.close()
        await trans.rollback()  # 테스트 후 자동 롤백


@pytest.fixture
async def seeded_db(db_session):
    """테스트 데이터가 시딩된 DB 세션."""
    # 상권 마스터 데이터
    await db_session.execute(
        text("""
            INSERT INTO districts (code, name, geometry)
            VALUES
                ('11680', '강남역', ST_GeomFromText('POINT(127.0276 37.4979)', 4326)),
                ('11440', '홍대입구', ST_GeomFromText('POINT(126.9246 37.5563)', 4326))
        """)
    )

    # 유동인구 데이터
    await db_session.execute(
        text("""
            INSERT INTO population_data (district_code, date, hour, count)
            VALUES
                ('11680', '2026-03-01', '09:00', 1200),
                ('11680', '2026-03-01', '12:00', 4500),
                ('11680', '2026-03-01', '18:00', 5200)
        """)
    )

    await db_session.commit()
    yield db_session
```

### 10.5 E2E 테스트 데이터

```python
# tests/e2e/test_analysis_flow.py
import pytest
from unittest.mock import AsyncMock, patch
import httpx


class TestAnalysisE2EFlow:
    """전체 분석 파이프라인 E2E 테스트."""

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_full_basic_analysis_flow(
        self, async_client: httpx.AsyncClient, seeded_db
    ):
        """BASIC 모드 전체 분석 흐름 E2E 테스트.

        1. 분석 요청 생성 → 202 Accepted
        2. 분석 상태 폴링 → processing → completed
        3. 최종 결과 조회 → 보고서 데이터 확인
        """
        # Step 1: 분석 요청
        response = await async_client.post(
            "/api/v1/analysis",
            json={
                "query": "강남역 근처 카페 창업 분석",
                "district_name": "강남역",
                "business_type": "카페",
                "analysis_mode": "BASIC",
            },
        )
        assert response.status_code == 202
        analysis_id = response.json()["analysis_id"]

        # Step 2: 결과 조회 (완료 대기)
        import asyncio
        max_retries = 30
        for _ in range(max_retries):
            status_response = await async_client.get(
                f"/api/v1/analysis/{analysis_id}"
            )
            if status_response.json()["status"] == "completed":
                break
            await asyncio.sleep(1)

        # Step 3: 결과 검증
        result = status_response.json()
        assert result["status"] == "completed"
        assert "result" in result
        assert "overall_score" in result["result"]

        # 에이전트 결과 확인
        agent_results = result["result"]["agent_results"]
        assert "population" in agent_results
        assert "revenue" in agent_results
        assert "competition" in agent_results
        assert "location" in agent_results

        # 점수 범위 확인
        for agent_id, agent_result in agent_results.items():
            assert 0 <= agent_result["score"] <= 10, (
                f"{agent_id} 점수가 범위를 벗어남: {agent_result['score']}"
            )

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_comparison_analysis_flow(
        self, async_client: httpx.AsyncClient, seeded_db
    ):
        """COMPARISON 모드 비교 분석 E2E 테스트."""
        response = await async_client.post(
            "/api/v1/analysis",
            json={
                "query": "강남역과 홍대입구 카페 창업 비교 분석",
                "district_name": "강남역",
                "business_type": "카페",
                "analysis_mode": "COMPARISON",
                "comparison_districts": ["강남역", "홍대입구"],
            },
        )
        assert response.status_code == 202

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_analysis_with_invalid_district(
        self, async_client: httpx.AsyncClient
    ):
        """존재하지 않는 상권으로 분석 요청 시 에러 처리."""
        response = await async_client.post(
            "/api/v1/analysis",
            json={
                "query": "없는상권 분석",
                "district_name": "없는상권",
                "business_type": "카페",
                "analysis_mode": "BASIC",
            },
        )
        # 422 (Validation Error) 또는 400 (Bad Request) 중 하나
        assert response.status_code in [400, 422]
```

### 10.6 테스트 데이터 보안 정책

| 정책 | 설명 |
|------|------|
| **API 키 절대 포함 금지** | 모든 API 키는 환경 변수로 주입, 테스트에서는 `test-xxx` 형식의 더미 값 사용 |
| **개인정보 배제** | 실제 사용자 데이터 미사용, Faker로 가짜 데이터 생성 |
| **.gitignore 설정** | `tests/fixtures/.env`, `*.db`, `htmlcov/` 등 추적 제외 |
| **시크릿 스캐닝** | CI에서 `gitleaks` 또는 `trufflehog`로 시크릿 유출 검사 |

### 10.7 테스트 데이터 생명주기

```
테스트 시작
    │
    ├── [Session Scope] DB 스키마 생성, PostGIS 확장 활성화
    │
    ├── [Function Scope] 트랜잭션 시작
    │   ├── 팩토리/픽스처로 데이터 생성
    │   ├── 테스트 실행
    │   └── 트랜잭션 롤백 (자동 정리)
    │
    ├── [Function Scope] 다음 테스트 (새 트랜잭션)
    │   └── ...
    │
    └── [Session Scope] DB 스키마 정리 (선택적)
```

---

## 부록

### A. pytest 마커 정의

| 마커 | 설명 | 실행 조건 |
|------|------|----------|
| `@pytest.mark.unit` | 단위 테스트 | 매 커밋 |
| `@pytest.mark.integration` | 통합 테스트 | PR 머지 시 |
| `@pytest.mark.e2e` | E2E 테스트 | 릴리스 전 |
| `@pytest.mark.slow` | 느린 테스트 (>10초) | 선택적 실행 |
| `@pytest.mark.asyncio` | 비동기 테스트 | 자동 (asyncio_mode=auto) |

### B. 테스트 네이밍 규칙

```
test_<대상>_<시나리오>_<기대결과>

예시:
- test_analyze_valid_input_returns_population_output
- test_query_population_empty_result_returns_empty_list
- test_create_analysis_invalid_request_returns_422
- test_workflow_agent_failure_continues_with_errors
```

### C. 모킹 체크리스트

테스트 작성 시 다음 외부 의존성은 반드시 모킹한다.

| 의존성 | 모킹 대상 | 모킹 방법 |
|--------|----------|----------|
| LLM API (LiteLLM) | `litellm.acompletion` | `unittest.mock.AsyncMock` + `patch` |
| PostgreSQL | `AsyncSession` | `AsyncMock` 또는 테스트 DB |
| Redis | `redis.asyncio.Redis` | `AsyncMock` |
| Google Maps API | HTTP 클라이언트 | `respx` 또는 `AsyncMock` |
| Naver Maps API | HTTP 클라이언트 | `respx` 또는 `AsyncMock` |
| MCP 서버 | `MCPClient.call_tool` | `AsyncMock` |

### D. 참고 문서

| 문서 | 관련 영역 |
|------|----------|
| `00_project_foundation.md` | 프로젝트 구조, 에러 처리 전략 |
| `01_orchestration_langgraph.md` | LangGraph 워크플로우, 노드/엣지 설계 |
| `03_specialist_agents.md` | 전문 에이전트 인터페이스 |
| `05_mcp_servers.md` | MCP 서버 도구 정의 |
| `08_api_endpoints.md` | API 엔드포인트 명세 |
