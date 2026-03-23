# Phase 5 구현 계획 — 기능 테스트 & 버그 수정

> **작성일:** 2026-03-21
> **선행 조건:** Phase 4 완료 (리팩토링 & 문서 보강)
> **목표:** 현재 코드베이스의 기능 검증 및 발견된 결함 수정

---

## 목표

Phase 1~4에서 구현된 코드의 **실제 동작 여부를 검증**한다.
Docker 없는 환경에서 수행 가능한 범위로 테스트를 설계하고,
발견된 버그를 즉시 수정하여 코드 품질을 확보한다.

---

## 환경 제약

| 항목 | 상태 | 비고 |
|------|------|------|
| Python 3.10 | ✅ 사용 가능 | 핵심 의존성 설치됨 |
| Docker | ❌ 사용 불가 | 컨테이너 내부 환경 (DinD 불가) |
| PostgreSQL | ❌ 로컬 없음 | mock 필요 |
| Redis | ❌ 로컬 없음 | mock 필요 |
| MCP 서버 | ❌ 미기동 | mock 필요 |
| LLM API (Gemini) | ⚠️ 키 있음 | 실호출 가능하나 비용 고려 |

---

## 전체 일정 개요

| 스프린트 | 핵심 목표 |
|---------|----------|
| S1 | 사전 점검: Settings 로드, import 검증, 빌드 검증 |
| S2 | 버그 수정: S1에서 발견된 결함 즉시 수정 |
| S3 | 단위 테스트: 에이전트, MCP 서버, 그래프 노드 (mock 기반) |
| S4 | 통합 테스트: LangGraph 워크플로우 (mock 기반) |
| S5 | 검증 보고서 작성 |

---

## S1: 사전 점검 (Settings + Import + Build)

### S1-1. Settings 로드 테스트

**문제:** `.env`의 `PHASE1_ALLOWED_DISTRICTS`가 콤마 구분 문자열인데,
`config.py`는 `list[str]` 타입으로 선언 → pydantic-settings 파싱 실패

**검증:**
```bash
cd marketscope && python -c "from app.config import get_settings; s = get_settings(); print(s.app_name)"
```

**수정:** `.env` 포맷 변경 또는 `config.py`에 `@field_validator` 추가

### S1-2. 전체 import 검증

모든 핵심 모듈의 import 성공 여부 확인:
- `app.config` (Settings)
- `app.agents.*` (15개 에이전트)
- `app.graph.workflow` (DAG 빌드)
- `app.graph.nodes` (20개 노드)
- `app.graph.edges` (조건부 엣지)
- `app.models.state` (MarketScopeState)
- `app.mcp_servers.*` (9개 서버)
- `app.tools.mcp_client` (MCPClientRouter)
- `app.monitoring.*` (메트릭, 트레이서)

### S1-3. LangGraph 워크플로우 빌드 검증

```bash
python -c "from app.graph.workflow import build_workflow; g = build_workflow(); print(f'Nodes: {len(g.nodes)}')"
```

- 20개 노드 확인
- 엔트리포인트: `user_input`
- 종료: `report_assembly → END`

### S1-4. State 초기화 검증

```python
from app.models.state import create_initial_state
state = create_initial_state("test-session", "강남역 카페 분석")
assert state["session_id"] == "test-session"
assert state["user_input"] == "강남역 카페 분석"
assert state["debate_decision"] is None
```

---

## S2: 발견 결함 수정

S1에서 발견된 오류를 즉시 수정:
- `.env` 포맷 수정 또는 `config.py` validator 추가
- import 오류 수정 (누락 모듈, 순환 참조 등)
- 타입 불일치, 필드 누락 등

---

## S3: 단위 테스트 (mock 기반)

### S3-1. conftest.py 작성

공통 fixture:
- `mock_settings`: Settings 인스턴스 (기본값)
- `mock_mcp_client`: AsyncMock (call_tool 반환값 설정)
- `mock_llm_provider`: AsyncMock (completion 반환값 설정)
- `sample_state`: create_initial_state()로 생성된 기본 state

### S3-2. 에이전트 단위 테스트

| 테스트 | 검증 항목 |
|--------|-----------|
| `test_commander_planning` | LLM 호출 → CommanderPlanOutput 파싱 |
| `test_commander_judgment` | 전체 결과 수집 → FinalJudgment 생성 |
| `test_population_agent` | MCP 3개 도구 병렬 호출 → PopulationAnalysis 반환 |
| `test_competition_agent` | MCP 도구 호출 → CompetitionAnalysis 반환 |
| `test_agent_tool_call_failure` | MCP 타임아웃 → 에러 핸들링 |
| `test_agent_llm_retry` | LLM 첫 호출 실패 → 재시도 성공 |

### S3-3. MCPClientRouter 단위 테스트

| 테스트 | 검증 항목 |
|--------|-----------|
| `test_resolve_server_with_prefix` | `maps.geocode` → maps 서버 URL |
| `test_resolve_server_no_prefix` | `get_data` → public_data 기본 서버 |
| `test_resolve_server_unknown_prefix` | `unknown.tool` → public_data 폴백 |
| `test_call_tool_routes_correctly` | prefix별 올바른 서버로 HTTP 요청 |

### S3-4. 그래프 노드 단위 테스트

| 테스트 | 검증 항목 |
|--------|-----------|
| `test_user_input_node_valid` | 정상 입력 → current_phase=0, progress=2.0 |
| `test_user_input_node_empty` | 빈 입력 → has_critical_failure=True |
| `test_debate_check_force` | force_debate=True → debate_decision="trigger" |
| `test_debate_check_low_confidence` | avg confidence < 0.6 → trigger |
| `test_debate_check_skip` | 정상 결과 → debate_decision="skip" |

### S3-5. Edge 함수 단위 테스트

| 테스트 | 검증 항목 |
|--------|-----------|
| `test_route_after_debate_check_trigger` | debate_decision="trigger" → "debate" |
| `test_route_after_debate_check_skip` | debate_decision="skip" → "commander_judgment" |
| `test_should_continue_after_commander` | commander_plan 존재 → "parallel_group_1" |
| `test_should_skip_group2` | quick 모드 → "commander_judgment" |

### S3-6. MCP 서버 도구 단위 테스트

| 서버 | 테스트 | 검증 |
|------|--------|------|
| finance | `test_calculate_loan_repayment` | 원리금균등 계산 정확성 |
| finance | `test_get_minimum_wage` | 연도별 최저시급 반환 |
| finance | `test_get_insurance_rates` | 4대보험 요율 반환 |
| database | `test_execute_spatial_query_select` | SELECT 쿼리 허용 |
| database | `test_execute_spatial_query_block_delete` | DELETE 차단 |

---

## S4: 통합 테스트 (LangGraph mock 기반)

### S4-1. 워크플로우 구조 검증

- 전체 노드 목록 (20개) 일치 확인
- 엣지 연결 검증 (user_input → commander_plan → ...)
- 조건부 엣지 분기 확인

### S4-2. Quick 모드 E2E (mock)

모든 에이전트를 mock하고 LangGraph를 실제 실행:
```
user_input → commander_plan → population + competition
→ group1_complete → commander_judgment → narrative
→ visualization → report_assembly → END
```

- 각 노드가 순서대로 실행되는지 확인
- state가 올바르게 전달되는지 확인
- 최종 report_assembly 결과가 존재하는지 확인

### S4-3. Debate 분기 테스트 (mock)

- debate_check에서 "trigger" 반환 시 debate 노드 실행 확인
- debate_check에서 "skip" 반환 시 commander_judgment 직행 확인

---

## S5: 검증 보고서

- 전체 테스트 결과 집계
- 발견 결함 목록 및 수정 내역
- 잔여 이슈 (Docker/인프라 필요 항목)
- `plan/status/` 업데이트

---

## 성공 기준

| 항목 | 기준 |
|------|------|
| Settings 로드 | ✅ `get_settings()` 정상 반환 |
| Import 검증 | ✅ 모든 핵심 모듈 import 성공 |
| 워크플로우 빌드 | ✅ 20개 노드 DAG 빌드 성공 |
| 단위 테스트 | ✅ 전체 pass (mock 기반) |
| 통합 테스트 | ✅ Quick 모드 E2E pass (mock 기반) |
