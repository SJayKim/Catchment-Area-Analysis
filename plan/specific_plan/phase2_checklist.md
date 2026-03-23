# Phase 2 구현 체크리스트

> 최종 업데이트: 2026-03-21
> 상태: ✅ 구현 완료

## S1: 블로커 해소 + 안정화

### S1-1. MCP 멀티서버 라우팅 [CRITICAL]
- [x] `config.py`: `mcp_servers` dict 설정 추가 (5개 서버 URL 매핑)
- [x] `mcp_client.py`: `MCPClientRouter` 클래스 구현
  - [x] tool_name에서 server prefix 파싱 (`public_data.get_floating_population` → `public_data`)
  - [x] prefix별 `MCPClient` 인스턴스 관리 (lazy init)
  - [x] `call_tool()` 메서드 (prefix 기반 라우팅)
  - [x] `close()` 메서드 (모든 클라이언트 정리)
  - [x] `health_check()` 메서드 (전체 서버 상태 확인)
- [x] `nodes.py`: `_get_mcp_client()` → `_get_mcp_router()` 변경 + `shutdown_mcp_router()` 추가

### S1-2. App Lifespan 통합
- [x] `main.py` lifespan에 Redis 연결 초기화/정리
- [x] `main.py` lifespan에 MCPClientRouter 초기화/정리
- [x] startup/shutdown 로깅 강화

### S1-3. Config 정리
- [x] Phase 2 에이전트 LLM 모델 설정 5개 추가 (trend, financial, risk, real_estate, regulatory)
- [x] Phase 2 MCP 서버 URL 3개 추가 (real_estate:5102, news:5103, regulatory:5104)
- [x] Debate 에이전트 LLM 모델 설정 3개 추가 (advocate, critic, judge)
- [x] `validate_model_names_not_empty`에 Phase 2 + Debate 모델 포함
- [x] Naver DataLab API 키 설정 추가

---

## S2: 에이전트 확장

### S2-1. 에이전트 출력 모델
- [x] `TrendAnalysis` Pydantic 모델
- [x] `FinancialAnalysis` Pydantic 모델
- [x] `RiskAnalysis` Pydantic 모델
- [x] `RealEstateAnalysis` Pydantic 모델
- [x] `RegulatoryAnalysis` Pydantic 모델

### S2-2. Specialist Agent 구현
- [x] `agents/trend.py` — TrendAgent (트렌드, 검색량, 소셜버즈)
- [x] `agents/financial.py` — FinancialAgent (투자비, ROI, 시나리오)
- [x] `agents/risk.py` — RiskAgent (종합 리스크 평가)
- [x] `agents/real_estate.py` — RealEstateAgent (임대료, 권리금, 공실률)
- [x] `agents/regulatory.py` — RegulatoryAgent (인허가, 용도지역, 위생)

### S2-3. MCP 서버 추가
- [x] `mcp_servers/real_estate/server.py` + `tools.py` (4 tools: rent, transaction, vacancy, premium)
- [x] `mcp_servers/news/server.py` + `tools.py` (3 tools: blog, news, datalab)
- [x] `mcp_servers/regulatory/server.py` + `tools.py` (3 tools: permits, zoning, requirements)
- [x] `docker-compose.yml` 5개 MCP 서버 서비스 추가

### S2-4. State 모델 확장
- [x] `state.py`에 Phase 2 결과 필드 5개 추가 (trend/financial/risk/real_estate/regulatory)
- [x] `state.py`에 debate_result 필드 추가
- [x] `create_initial_state()` 업데이트

### S2-5. LangGraph DAG 확장
- [x] `nodes.py`에 7개 노드 추가 (trend, real_estate, regulatory, financial, risk, debate, group3_complete)
- [x] `edges.py`에 `should_run_group3`, `should_run_debate` 추가
- [x] `workflow.py` DAG 재구성 (18 nodes, Group 3, financial, risk, debate 포함)
- [x] `report_assembly_node` Phase 2 + debate 결과 포함

---

## S3: 토론 시스템 + 메모리

### S3-1. Debate 시스템
- [x] `agents/debate/__init__.py`
- [x] `agents/debate/advocate.py` — AdvocateAgent (기회/강점 극대화)
- [x] `agents/debate/critic.py` — CriticAgent (약점/리스크 지적)
- [x] `agents/debate/judge.py` — JudgeAgent (최종 판정 + 수렴 판단)
- [x] `agents/debate/orchestrator.py` — DebateOrchestrator (max 3 rounds, 수렴 체크)
- [x] `models/debate.py` 확장 (JudgeVerdict 추가, DebateResult에 rounds/revised_score 추가)

### S3-2. Memory 시스템
- [x] `memory/task_memory.py` (Redis/인메모리 기반 세션 메모리)
- [x] `memory/personal_memory.py` (PostgreSQL/인메모리 기반 사용자 이력)
- [x] `memory/lightrag_client.py` 실제 구현 (인메모리 키워드 매칭, district/news/regulation 삽입)

### S3-3. Commander Agent 확장
- [x] Phase 2 에이전트 9개 지원 (ALL_AGENTS 상수 연동)
- [x] 점수 가중치 재조정 (9개 에이전트 기반: 각 10~15%)
- [x] 토론 결과 반영 (debate_result → judgment 프롬프트에 포함)
- [x] `run_judgment()` Phase 2 + debate 결과 통합

---

## 검증 결과 (2026-03-21)

```
✅ config.py — mcp_servers dict, Phase 2 LLM 모델, Debate 모델
✅ mcp_client.py — MCPClientRouter (prefix 기반 멀티서버 라우팅)
✅ agent_outputs.py — 9개 Pydantic 출력 모델
✅ debate.py — DebateArgument, DebateRound, JudgeVerdict, DebateResult
✅ state.py — Phase 2 필드 + debate_result
✅ constants.py — ALL_AGENTS (9개), ANALYSIS_MODE_AGENTS 확장
✅ Debate system — Advocate/Critic/Judge/Orchestrator (4 modules)
✅ Memory system — TaskMemory/PersonalMemory/LightRAGClient (3 modules)
✅ edges.py — should_run_group3, should_run_debate
✅ nodes.py — 7개 신규 노드 (trend, real_estate, regulatory, financial, risk, debate, group3_complete)
✅ LangGraph workflow — 18 nodes 정상 빌드
```
