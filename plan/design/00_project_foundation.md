# Phase 1: Project Foundation Checklist

## 1. 디렉토리 구조 생성
- [ ] `marketscope/` 루트 디렉토리
- [ ] `app/__init__.py`
- [ ] `app/models/` (state, agent_outputs, common, report, debate)
- [ ] `app/agents/` (base, population, revenue, competition, location)
- [ ] `app/graph/` (workflow, nodes, edges)
- [ ] `app/tools/` (mcp_client, registry)
- [ ] `app/memory/` (reme_client, lightrag_client)
- [ ] `app/db/` (session, models, repositories)
- [ ] `app/api/routes/` (analysis, reports, health)
- [ ] `app/services/`
- [ ] `tests/`

## 2. 설정 파일
- [ ] `pyproject.toml` (의존성 정의)
- [ ] `.env.example`
- [ ] `app/config.py` (Pydantic Settings)

## 3. 공통 모델
- [ ] `app/models/common.py` (TimeSlot, AgeDistribution, TrendDirection 등)
- [ ] `app/models/agent_outputs.py` (PopulationAnalysis, RevenueAnalysis 등)
- [ ] `app/models/state.py` (MarketScopeState, CommanderPlan 등)
- [ ] `app/models/report.py` (VisualizationOutput, NarrativeOutput)

## 4. 공통 인프라
- [ ] `app/constants.py` (Enums, 상수)
- [ ] `app/exceptions.py` (커스텀 예외)
- [ ] `app/logging_config.py` (구조화 로깅)
- [ ] `app/agents/base.py` (BaseAgent 추상 클래스)
