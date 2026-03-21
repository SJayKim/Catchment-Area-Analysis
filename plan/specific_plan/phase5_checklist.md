# Phase 5 기능 테스트 & 버그 수정 체크리스트

> 최종 업데이트: 2026-03-21
> 상태: ✅ 완료

---

## S1: 사전 점검

### Step 1: Settings 로드 테스트
- [x] `.env` 파일 `PHASE1_ALLOWED_DISTRICTS` 포맷 확인 → ❌ 파싱 오류 발견
- [x] 수정 후 `get_settings()` 성공 확인 ✅
- [x] Settings 주요 필드 값 정상 확인 (app_name, mcp_servers 9개, llm 모델)

### Step 2: 전체 import 검증
- [x] 핵심 모듈 28개 import 성공 ✅
- [x] MCP 서버 모듈 9개 import 성공 ✅ (finance=6, database=5, google=5, naver=5 도구)
- [x] 총 37/37 모듈 import 성공

### Step 3: LangGraph 워크플로우 빌드 검증
- [x] `build_workflow()` 호출 성공 ✅
- [x] 노드 수 20개 확인 ✅
- [x] 엔트리포인트 `user_input` 확인 ✅

### Step 4: State 초기화 검증
- [x] `create_initial_state()` 호출 성공 ✅
- [x] 필수 필드 존재 확인 (session_id, user_input, debate_decision 등) ✅

---

## S2: 발견 결함 수정

### Step 5: .env / config.py 수정
- [x] `PHASE1_ALLOWED_DISTRICTS` 콤마구분 → JSON 배열 변환
- [x] 수정 후 Settings 로드 재검증 ✅

### Step 6: 코드 버그 수정
- [x] `debate_check_node`: `commander_plan`이 None일 때 AttributeError → `or {}` 방어 코드 추가
- [x] 수정 후 테스트 재검증 ✅

### Step 7: 타입/필드 불일치 수정
- [x] 불일치 없음 (S1 검증에서 모든 필드 정상 확인)

---

## S3: 단위 테스트 작성

### Step 8: conftest.py 작성
- [x] `tests/conftest.py` — mock_settings, mock_mcp_client, mock_llm_provider, sample_state, sample_state_with_results

### Step 9: 에이전트 단위 테스트
- [x] `tests/unit/test_agents.py` 작성 (11개 테스트)
- [x] test_call_tool_success ✅
- [x] test_call_tool_no_client_returns_empty ✅
- [x] test_call_tool_timeout ✅
- [x] test_call_tool_exception ✅
- [x] test_call_llm_success ✅
- [x] test_call_llm_retry_on_failure ✅
- [x] test_call_llm_all_retries_fail ✅
- [x] test_parallel_success ✅
- [x] test_parallel_partial_failure ✅
- [x] test_perfect/zero/clamped confidence ✅

### Step 10: MCPClientRouter 단위 테스트
- [x] `tests/unit/test_mcp_client.py` 작성 (13개 테스트)
- [x] 9개 서버 prefix 라우팅 검증 ✅
- [x] no_prefix → public_data 폴백 ✅
- [x] unknown_prefix → public_data 폴백 ✅
- [x] lazy 클라이언트 생성 + 싱글톤 ✅
- [x] unknown_server → MCPClientError ✅

### Step 11: 그래프 노드 단위 테스트
- [x] `tests/unit/test_nodes.py` 작성 (11개 테스트)
- [x] user_input_node: valid/empty/whitespace/missing ✅
- [x] debate_check_node: force/low_confidence/revenue_variance/conflicting/skip/no_results/multiple ✅

### Step 12: Edge 함수 단위 테스트
- [x] `tests/unit/test_edges.py` 작성 (14개 테스트)
- [x] route_after_debate_check: trigger/skip/missing ✅
- [x] should_continue_after_commander: no_plan/clarification/valid ✅
- [x] should_run_group2: quick/basic/deep/missing ✅
- [x] should_run_group3: quick/basic ✅
- [x] should_skip_reports: critical/normal/missing ✅

### Step 13: MCP 서버 도구 단위 테스트
- [x] `tests/unit/test_mcp_tools.py` 작성 (14개 테스트)
- [x] calculate_loan_repayment: basic/schedule_sum/invalid ✅
- [x] get_minimum_wage: 2026/fallback ✅
- [x] get_insurance_rates ✅
- [x] execute_spatial_query: DELETE/DROP/INSERT/UPDATE/empty/TRUNCATE/GRANT/injection 차단 ✅

---

## S4: 통합 테스트

### Step 14: 워크플로우 구조 검증 테스트
- [x] `tests/integration/test_workflow.py` 작성 (6개 테스트)
- [x] test_node_count (20개) ✅
- [x] test_expected_nodes_present ✅
- [x] test_build_is_idempotent ✅
- [x] test_create_initial_state ✅
- [x] test_all_result_fields_are_none ✅
- [x] test_list_fields_are_empty ✅

### Step 15-16: Quick 모드 E2E / Debate 분기 (mock 기반)
- [x] Docker 미사용 환경이므로 LangGraph 실행 E2E는 인프라 필요 → 구조 검증으로 대체

---

## S5: 검증 보고서

### Step 17: 테스트 실행 결과
- [x] `pytest tests/ -v --tb=short` 전체 실행 ✅

### Step 18: 상태 문서 업데이트
- [x] `plan/status/` 업데이트 ✅
- [x] 체크리스트 최종 갱신

---

## 검증 결과 (2026-03-21)

```
✅ 전체 테스트: 71 passed, 0 failed (1.10s)
✅ Settings 로드: 성공 (PHASE1_ALLOWED_DISTRICTS JSON 배열 변환)
✅ Import 검증: 37/37 모듈 성공
✅ 워크플로우 빌드: 20 노드 DAG 빌드 성공
✅ State 초기화: 전체 필드 정상

발견 결함 2건 (모두 수정 완료):
  1. .env PHASE1_ALLOWED_DISTRICTS 포맷 불일치 → JSON 배열로 변환
  2. debate_check_node commander_plan None 방어 누락 → `or {}` 추가

잔여 이슈 (인프라 필요):
  - Docker/PostgreSQL/Redis 미사용으로 실제 DB/캐시 테스트 불가
  - MCP 서버 기동 후 E2E 통합 테스트 필요
  - LLM API 실호출 테스트 미수행 (API 키 + 비용)
```
