# Phase 2 상세 구현 계획서

> 작성일: 2026-03-21
> 상태: 실행 대기

## 목차
1. [S1: 블로커 해소 + 안정화](#s1)
2. [S2: 에이전트 확장 + MCP 서버 추가](#s2)
3. [S3: 토론 시스템 + 메모리 + Commander 확장](#s3)

---

## <a id="s1"></a>S1: 블로커 해소 + 안정화 (Week 1)

### S1-1. MCP 멀티서버 라우팅 수정 [CRITICAL BLOCKER]

**문제**: `MCPClient`가 `settings.mcp_server_url` (localhost:5100) 하나만 사용.
Maps 서버(5101)에 접근 불가.

**해결 방안**: tool_name prefix 기반 서버 라우팅

| 파일 | 변경 내용 |
|------|-----------|
| `app/config.py` | `mcp_server_url` → `mcp_servers: dict` (서버별 URL 매핑) |
| `app/tools/mcp_client.py` | `MCPClientRouter` 추가, tool prefix → 서버 URL 라우팅 |
| `app/graph/nodes.py` | `MCPClientRouter` 사용으로 변경 |

**라우팅 규칙**:
```
public_data.* → http://localhost:5100
maps.*        → http://localhost:5101
real_estate.* → http://localhost:5102  (Phase 2)
news.*        → http://localhost:5103  (Phase 2)
regulatory.*  → http://localhost:5104  (Phase 2)
```

**체크리스트**:
- [ ] `config.py`에 `mcp_servers` dict 설정 추가
- [ ] `MCPClientRouter` 클래스 구현 (tool prefix 파싱 → 적절한 서버 HTTP 클라이언트 선택)
- [ ] 기존 `MCPClient` 단일 서버 클래스는 유지 (Router가 내부적으로 사용)
- [ ] `nodes.py`에서 `_get_mcp_client()` → `_get_mcp_router()` 변경
- [ ] 에이전트의 `call_tool()` 호출 패턴 변경 불필요 (Router가 투명하게 처리)

### S1-2. App Lifespan 통합

**문제**: `main.py` lifespan에서 Redis, Scheduler 초기화/정리 없음.

**체크리스트**:
- [ ] lifespan에서 Redis 연결 초기화 + 종료 시 close
- [ ] MCPClientRouter 초기화 + 종료 시 close
- [ ] 로깅 강화 (startup/shutdown 이벤트)

### S1-3. Config 정리

**체크리스트**:
- [ ] Phase 2 에이전트 LLM 모델 설정 추가 (trend, financial, risk, real_estate, regulatory)
- [ ] Phase 2 MCP 서버 URL 설정 추가
- [ ] `LLMSettings.validate_model_names_not_empty`에 Phase 2 모델 추가
- [ ] Naver API 키 설정 추가 (뉴스/SNS MCP용)

---

## <a id="s2"></a>S2: 에이전트 확장 + MCP 서버 추가 (Week 2-3)

### S2-1. 에이전트 출력 모델 추가

**파일**: `app/models/agent_outputs.py`

| 모델 | 주요 필드 |
|------|-----------|
| `TrendAnalysis` | lifecycle_stage, search_volume_trend, social_buzz_score, emerging_keywords, consumer_preference_shift, risk_signals, opportunity_signals |
| `FinancialAnalysis` | initial_investment, monthly_operating_cost, break_even_months, roi_12m, roi_24m, scenarios (optimistic/realistic/pessimistic), funding_options |
| `RiskAnalysis` | overall_risk_score, risk_factors[], seasonal_vulnerability, exit_difficulty, risk_mitigation_strategies |
| `RealEstateAnalysis` | rent_per_pyeong, premium_estimate, vacancy_rate, lease_terms, available_properties[] |
| `RegulatoryAnalysis` | required_permits[], zoning_restrictions, health_safety_requirements, operating_hour_restrictions, estimated_permit_timeline |

**체크리스트**:
- [ ] 5개 Pydantic 출력 모델 정의
- [ ] `app/models/common.py`에 필요한 공통 타입 추가

### S2-2. 5개 Specialist Agent 구현

각 에이전트는 `BaseAgent[T]` 패턴을 따름.

| 에이전트 | 파일 | 사용 MCP 도구 | 의존성 |
|----------|------|--------------|--------|
| `TrendAgent` | `agents/trend.py` | `news.search_blog`, `news.search_news`, `news.get_naver_datalab` | population_result |
| `FinancialAgent` | `agents/financial.py` | `real_estate.get_rent_info`, `public_data.get_estimated_revenue` | revenue_result, competition_result |
| `RiskAgent` | `agents/risk.py` | 기존 데이터 기반 종합 | 모든 Phase 1 결과 |
| `RealEstateAgent` | `agents/real_estate.py` | `real_estate.get_rent_info`, `real_estate.get_transaction_price`, `real_estate.get_vacancy_rate` | location_result |
| `RegulatoryAgent` | `agents/regulatory.py` | `regulatory.get_permits`, `regulatory.get_zoning` | location_result |

**체크리스트**:
- [ ] `TrendAgent` 구현 (시스템/유저 프롬프트 + execute + MCP 도구 호출)
- [ ] `FinancialAgent` 구현
- [ ] `RiskAgent` 구현
- [ ] `RealEstateAgent` 구현
- [ ] `RegulatoryAgent` 구현
- [ ] `config.py` LLMSettings에 모델 매핑 추가
- [ ] `agents/__init__.py` 업데이트

### S2-3. 3개 MCP 서버 추가

| 서버 | 포트 | 도구 목록 |
|------|------|----------|
| Real Estate (부동산) | 5102 | `get_rent_info`, `get_transaction_price`, `get_vacancy_rate`, `get_premium_estimate` |
| News/SNS (뉴스/트렌드) | 5103 | `search_blog`, `search_news`, `get_naver_datalab` |
| Regulatory (규제/허가) | 5104 | `get_permits`, `get_zoning`, `get_business_requirements` |

**체크리스트**:
- [ ] `mcp_servers/real_estate/` 디렉토리 및 server.py, tools.py 구현
- [ ] `mcp_servers/news/` 디렉토리 및 server.py, tools.py 구현
- [ ] `mcp_servers/regulatory/` 디렉토리 및 server.py, tools.py 구현
- [ ] docker-compose.yml에 3개 서버 추가

### S2-4. State 모델 확장

**파일**: `app/models/state.py`

**체크리스트**:
- [ ] Phase 2 에이전트 결과 필드 추가: `trend_result`, `financial_result`, `risk_result`, `real_estate_result`, `regulatory_result`
- [ ] 토론 결과 필드 추가: `debate_result`
- [ ] `create_initial_state()`에 새 필드 초기값 추가
- [ ] Secondary(비교모드) 결과 필드도 추가

### S2-5. LangGraph DAG 확장

**새로운 DAG 구조**:
```
START
  → commander_plan
  → [conditional] fan-out Group 1: [population, competition]
  → group1_complete (fan-in)
  → [conditional] fan-out Group 2: [revenue, location]
  → group2_complete (fan-in)
  → [conditional] fan-out Group 3: [trend, real_estate, regulatory]
  → group3_complete (fan-in)
  → financial (revenue + competition 의존)
  → risk (전체 결과 의존)
  → [conditional] debate (confidence < 0.6 또는 결론 충돌 시)
  → commander_judgment
  → [conditional] report_generation (narrative → visualization)
  → report_assembly
  → END
```

**체크리스트**:
- [ ] `nodes.py`에 5개 에이전트 노드 함수 추가
- [ ] `nodes.py`에 `group3_complete_node` 추가
- [ ] `workflow.py`에 Group 3 병렬 실행 추가
- [ ] `workflow.py`에 financial, risk 순차 노드 추가
- [ ] `edges.py`에 `should_run_group3`, `should_run_debate` 조건부 엣지 추가
- [ ] `report_assembly_node`에 Phase 2 결과 포함

---

## <a id="s3"></a>S3: 토론 시스템 + 메모리 + Commander 확장 (Week 4)

### S3-1. Debate 시스템 구현

**파일**: `app/agents/debate/`

| 컴포넌트 | 파일 | 역할 |
|----------|------|------|
| `AdvocateAgent` | `debate/advocate.py` | 기회·강점 극대화 (Gemini 2.5 Pro) |
| `CriticAgent` | `debate/critic.py` | 약점·리스크 지적 (Claude Sonnet) |
| `JudgeAgent` | `debate/judge.py` | 최종 판정 (Claude Opus) |
| `DebateOrchestrator` | `debate/orchestrator.py` | 라운드 관리 + 수렴 판단 |

**토론 프로토콜**:
1. Advocate가 분석 결과 기반 긍정 논거 제시
2. Critic이 약점·리스크·논리 오류 지적
3. Judge가 양측 논거 평가 → 최종 판정 (max 3 라운드)
4. 수렴 조건: Judge 판정 confidence ≥ 0.7 또는 3라운드 완료

**트리거 조건**:
- 에이전트 간 결론 충돌 (예: population=긍정, competition=부정)
- confidence_score 평균 < 0.6
- 사용자 명시적 요청 (`force_debate: true`)

**체크리스트**:
- [ ] `AdvocateAgent` 구현
- [ ] `CriticAgent` 구현
- [ ] `JudgeAgent` 구현
- [ ] `DebateOrchestrator` 구현 (라운드 루프 + 수렴 판단)
- [ ] `models/debate.py` 출력 모델 확장
- [ ] `config.py`에 debate LLM 모델 설정 추가
- [ ] DAG에 debate 노드 + 조건부 엣지 연결

### S3-2. Memory 시스템 확장

**3계층 메모리**:

| 계층 | 저장소 | 용도 | TTL |
|------|--------|------|-----|
| TaskMemory | Redis | 현재 분석 세션 컨텍스트 | 세션 종료 시 삭제 |
| PersonalMemory | PostgreSQL | 사용자별 분석 이력·선호도 | 영구 |
| WorldMemory | LightRAG | 상권 특성·뉴스·규제 지식 | 분기 갱신 |

**체크리스트**:
- [ ] `memory/task_memory.py` (Redis 기반 세션 메모리)
- [ ] `memory/personal_memory.py` (PostgreSQL 기반 사용자 이력)
- [ ] `memory/lightrag_client.py` 실제 구현 (현재 stub)
- [ ] 에이전트에서 메모리 조회/저장 인터페이스

### S3-3. Commander Agent Phase 2 확장

**체크리스트**:
- [ ] `agents_to_run`에 Phase 2 에이전트 5개 추가 가능하도록 확장
- [ ] 점수 가중치 업데이트 (10개 에이전트 기반)
- [ ] 토론 트리거 판단 로직 추가
- [ ] `run_judgment()` Phase 2 결과 통합
- [ ] Phase 2 지역 제한 완화 (서울 전체 또는 수도권)

---

## 의존성 그래프

```
S1-1 (MCP 라우팅) ──┐
S1-2 (Lifespan)  ──┤
S1-3 (Config)    ──┘
         │
         ▼
S2-1 (출력 모델) ──→ S2-2 (에이전트 5개) ──→ S2-5 (DAG 확장)
S2-3 (MCP 서버 3개) ─────────────────────┘        │
S2-4 (State 확장) ─────────────────────────────────┘
                                                    │
                                                    ▼
                              S3-1 (Debate) ──→ S3-3 (Commander 확장)
                              S3-2 (Memory) ──┘
```

## 구현 순서 (코딩 순서)

1. **S1-1**: `config.py` MCP 설정 → `mcp_client.py` Router → `nodes.py` 연결
2. **S1-2**: `main.py` lifespan 통합
3. **S1-3**: `config.py` Phase 2 설정
4. **S2-1**: `agent_outputs.py` 모델 5개
5. **S2-4**: `state.py` 확장
6. **S2-2**: 에이전트 5개 구현
7. **S2-3**: MCP 서버 3개
8. **S2-5**: DAG 확장 (`nodes.py`, `workflow.py`, `edges.py`)
9. **S3-1**: Debate 시스템
10. **S3-3**: Commander 확장
11. **S3-2**: Memory 시스템
