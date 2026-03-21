# MarketScope AI - 코드 개선 계획 (Revision Plan 1)

> 작성일: 2026-03-21
> 평가 기준: 안정성, 확장성, 범용성, 기능 분리

---

## Phase 0: CRITICAL (즉시 수정 - 기능 불가 이슈)

### P0-1. nodes.py에 MCPClient 전달
- **문제**: 모든 노드 함수에서 에이전트 생성 시 mcp_client를 전달하지 않아 도구 호출이 전부 빈 dict 반환
- **수정 파일**: `app/graph/nodes.py`
- **수정 내용**:
  - 모듈 레벨에서 MCPClient 싱글톤 생성
  - 모든 에이전트 인스턴스에 mcp_client 주입
  - 에이전트 팩토리 패턴 도입 (반복 인스턴스 생성 제거)

### P0-2. LLM Provider 추상화 레이어
- **문제**: BaseAgent가 litellm에 직접 결합 → 프로바이더 교체 불가
- **수정 파일**:
  - `app/llm/__init__.py` (신규)
  - `app/llm/provider.py` (신규) - 추상 인터페이스
  - `app/llm/litellm_provider.py` (신규) - litellm 구현체
  - `app/agents/base.py` - provider 인터페이스 사용으로 변경
  - `app/config.py` - provider 설정 추가
- **수정 내용**:
  - LLMProvider 프로토콜(인터페이스) 정의
  - LiteLLMProvider 구현체
  - BaseAgent에서 provider 인터페이스만 참조
  - config에서 provider 선택 가능하도록

---

## Phase 1: HIGH (안정성 - 프로덕션 배포 전 필수)

### P1-1. 인메모리 저장소 TTL + API 검증 강화
- **문제**: _analysis_store가 무한 증가, depth 필드 검증 없음
- **수정 파일**: `app/api/routes/analysis.py`
- **수정 내용**:
  - TTL 기반 자동 만료 (1시간)
  - AnalysisCreateRequest.depth에 Literal 타입 제한
  - 글로벌 에러 핸들러 등록
  - SSE heartbeat 추가

### P1-2. narrative/visualization run() 통일
- **문제**: BaseAgent.run()을 각각 다르게 오버라이드 → 반환 구조 불일치
- **수정 파일**:
  - `app/agents/base.py` - result_field 결정 로직 개선
  - `app/agents/narrative.py` - custom run() 제거, BaseAgent.run() 사용
  - `app/agents/visualization.py` - 동일
- **수정 내용**:
  - BaseAgent.run()의 result_field 매핑을 설정 가능하게
  - narrative/visualization이 BaseAgent.run() 그대로 사용
  - 반환 구조 통일 (node_executions, errors 항상 포함)

### P1-3. State 타입 일관성 강제
- **문제**: agent_outputs가 Pydantic 모델인데 dict로도 들어감 → isinstance 방어코드 산재
- **수정 파일**:
  - `app/agents/base.py` - run()에서 결과를 model_dump()으로 dict 통일
  - `app/agents/commander.py` - isinstance 분기 제거
  - `app/agents/narrative.py` - 동일
  - `app/agents/visualization.py` - 동일
  - `app/agents/location.py` - 동일
  - `app/agents/revenue.py` - 동일
- **수정 내용**:
  - 모든 에이전트 결과를 dict로 통일 (Pydantic → model_dump())
  - 또는 모든 곳에서 Pydantic 모델로 통일
  - 선택: **dict 통일** (TypedDict State와 자연스럽게 호환)

### P1-4. config.py 프로덕션 검증
- **문제**: API 키, 시크릿 키 등 필수값 검증 없음
- **수정 파일**: `app/config.py`
- **수정 내용**:
  - production 환경에서 API 키 필수 검증
  - app_secret_key 최소 길이 강제
  - LLM 모델명 검증 (빈 문자열 방지)

---

## Phase 2: MEDIUM (완성도 - 기능 안정화)

### P2-1. 병렬 실행 구현
- **문제**: population → competition이 순차 실행이지만 독립적이라 병렬 가능
- **수정 파일**: `app/graph/workflow.py`
- **수정 내용**:
  - fan-out 노드 추가 (parallel_dispatch)
  - fan-in 노드 추가 (parallel_collect)
  - Group 1 (population + competition) 동시 실행
  - Group 2 (revenue + location) 동시 실행

### P2-2. MCP 클라이언트 커넥션 관리
- **수정 파일**: `app/tools/mcp_client.py`
- **수정 내용**:
  - async context manager (__aenter__/__aexit__)
  - connection pool limits 설정
  - JSON decode 에러 처리
  - 재시도 로직 추가 (3회)
  - MCPToolCallError로 래핑

### P2-3. 비교모드 완성 + 에이전트 에러 표준화
- **수정 파일**:
  - `app/models/state.py` - secondary_revenue/location 필드 추가
  - `app/graph/edges.py` - comparison 모드 라우팅
  - `app/agents/*.py` - 에러 처리 표준화 (silent fail 제거)
  - `app/exceptions.py` - DataCollectionError 등 추가
- **수정 내용**:
  - comparison 모드 전체 파이프라인 완성
  - 에이전트 간 에러 핸들링 패턴 통일 (silent pass → 로깅 + 구조화 에러)

---

## 수정 순서 요약

```
P0-1 (nodes.py MCPClient) ──┐
                             ├─→ P1-2 (run() 통일) ──→ P1-3 (State 타입) ──→ P2-3 (비교모드)
P0-2 (LLM 추상화)     ──────┘

P1-1 (메모리/API) ──────────────→ P2-1 (병렬 실행)

P1-4 (config 검증) ──────────────→ P2-2 (MCP 커넥션)
```

## 예상 영향 범위

| 단계 | 수정 파일 수 | 신규 파일 수 | 위험도 |
|------|------------|------------|--------|
| P0-1 | 1 | 0 | 낮음 |
| P0-2 | 2 | 3 | 중간 (인터페이스 변경) |
| P1-1 | 1 | 0 | 낮음 |
| P1-2 | 3 | 0 | 중간 (반환 구조 변경) |
| P1-3 | 6 | 0 | 높음 (전체 에이전트 수정) |
| P1-4 | 1 | 0 | 낮음 |
| P2-1 | 1 | 0 | 중간 (DAG 구조 변경) |
| P2-2 | 1 | 0 | 낮음 |
| P2-3 | 5 | 0 | 높음 (다수 파일 수정) |
