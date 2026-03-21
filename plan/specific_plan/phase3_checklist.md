# Phase 3 구현 체크리스트

> 최종 업데이트: 2026-03-21
> 상태: ✅ 구현 완료

## S1: structlog 전환 + Langfuse 활성화

### S1-1. structlog 파이프라인 구축
- [x] `pyproject.toml`: `structlog >= 24.1.0` 의존성 추가
- [x] `logging_config.py` 재작성
  - [x] `structlog.configure()` 프로세서 체인 설정
  - [x] 개발 환경: `ConsoleRenderer` (컬러 출력)
  - [x] 운영 환경: `JSONRenderer` (Loki/ELK 호환)
  - [x] `get_logger()` → `structlog.get_logger()` 반환
  - [x] `get_agent_logger()` → agent_name 바인딩된 structlog 로거
- [x] 기존 `logging.getLogger()` 호출부 교체
  - [x] `agents/base.py`
  - [x] `agents/commander.py` (get_agent_logger 호환)
  - [x] `agents/debate/orchestrator.py`
  - [x] `graph/nodes.py`
  - [x] `memory/task_memory.py`
  - [x] `memory/personal_memory.py`
  - [x] `memory/lightrag_client.py`
  - [x] `tools/mcp_client.py`
  - [x] `monitoring/quality_checker.py`

### S1-2. Langfuse LLM 트레이싱 활성화
- [x] `monitoring/langfuse_handler.py` 신규 생성
  - [x] `setup_langfuse()` — LiteLLM 콜백 등록
  - [x] `create_trace()` — 세션별 trace 생성
  - [x] `flush_langfuse()` / `shutdown_langfuse()`
- [x] `agents/base.py` — LiteLLM metadata 자동 전달 (Langfuse 네이티브 콜백)
- [x] `main.py` lifespan — `setup_langfuse()` / `shutdown_langfuse()` 추가

### S1-3. 에이전트 실행 컨텍스트 로깅
- [x] `agents/base.py` run() 메서드 로그 이벤트 추가
  - [x] `agent.start` — agent_name, session_id, location, industry
  - [x] `agent.llm_call` — model, tokens, latency_ms
  - [x] `agent.mcp_call` — tool_name, server, latency_ms, success
  - [x] `agent.complete` — confidence, duration_ms
  - [x] `agent.error` — error_type, error_message, exc_info

---

## S2: MCP 모니터링 + DAG 관측성

### S2-1. MCP 모니터링 미들웨어
- [x] `monitoring/mcp_monitor.py` 신규 생성
  - [x] `MCPMonitoringMiddleware` 클래스
  - [x] `call_tool()` 래퍼 (요청/응답 로깅, 실행 시간)
  - [x] 에러 분류 (timeout, connection_error, tool_error)
  - [x] 서버별 통계 집계 (calls, errors, avg_ms, error_rate)
  - [x] `get_stats()` 메서드
  - [x] Circuit Breaker 경고 (연속 3회 실패)
- [x] `graph/nodes.py` — `_get_mcp_monitor()` 팩토리 추가
- [x] 에이전트 팩토리가 모니터링 미들웨어 사용

### S2-2. LangGraph DAG 관측성
- [x] `monitoring/dag_tracer.py` 신규 생성
  - [x] `DAGTracer` 클래스 (파이프라인 시작/종료, 노드 타이밍)
  - [x] `@trace_node` 데코레이터 (자동 시작/종료 로깅)
- [x] `graph/nodes.py` — 18개 노드에 `@trace_node` 적용
- [x] `graph/edges.py` — 6개 조건부 엣지 분기 결정 로깅

### S2-3. 토론 시스템 모니터링
- [x] `agents/debate/orchestrator.py` 로그 이벤트 추가
  - [x] `debate.start` — session_id, trigger_reason
  - [x] `debate.round.start` — round_number
  - [x] `debate.advocate` — argument_length
  - [x] `debate.critic` — argument_length
  - [x] `debate.judge` — confidence, is_converged, accepted/rejected counts
  - [x] `debate.round.complete` — duration_ms
  - [x] `debate.complete` — total_rounds, revised_score, convergence_reached
- [x] Langfuse 토론 trace 생성 (`create_trace`)

---

## S3: 메트릭 엔드포인트 + 대시보드

### S3-1. Prometheus 메트릭
- [x] `pyproject.toml`: `prometheus-client >= 0.20.0` 추가
- [x] `monitoring/metrics.py` 신규 생성
  - [x] HTTP 메트릭 (request_duration, requests_total)
  - [x] 에이전트 메트릭 (execution_seconds, errors_total)
  - [x] LLM 메트릭 (tokens_total, cost_dollars)
  - [x] MCP 메트릭 (call_duration, errors_total)
  - [x] 토론 메트릭 (rounds_total, convergence)
  - [x] 파이프라인 메트릭 (duration, node_duration)
  - [x] 헬퍼 함수 (observe_*, inc_*)
- [x] `main.py` — `/metrics` 엔드포인트 마운트
- [x] `main.py` — HTTP 메트릭 미들웨어 추가

### S3-2. 헬스체크 확장
- [x] `api/routes/health.py` 확장
  - [x] `/health/live` — 프로세스 생존
  - [x] `/health/ready` — DB, Redis, MCP 서버 5개 상태
  - [x] `/health/detailed` — 상세 상태 + MCP 통계 + DAG 타이밍

### S3-3. Docker Compose 모니터링 스택
- [x] `docker-compose.monitoring.yml` 생성
  - [x] Prometheus 서비스 (v2.51.0)
  - [x] Grafana 서비스 (v10.4.0)
  - [x] Loki 서비스 (v2.9.0)
- [x] `monitoring/prometheus.yml` scrape config
- [x] Grafana 프로비저닝 (datasources, dashboards)

---

## 검증 결과 (2026-03-21)

```
✅ pyproject.toml — structlog, prometheus-client 의존성
✅ logging_config.py — structlog 파이프라인 (Console/JSON 렌더러)
✅ monitoring/langfuse_handler.py — LiteLLM 콜백 등록, trace 생성
✅ monitoring/mcp_monitor.py — MCPMonitoringMiddleware (레이턴시/에러율)
✅ monitoring/dag_tracer.py — @trace_node 데코레이터, DAGTracer
✅ monitoring/metrics.py — Prometheus 메트릭 11종 + 헬퍼 함수 8개
✅ main.py — lifespan(Langfuse), /metrics, HTTP 미들웨어
✅ agents/base.py — agent.start/llm_call/mcp_call/complete/error 이벤트
✅ graph/nodes.py — 18개 노드 @trace_node, _get_mcp_monitor()
✅ graph/edges.py — 6개 조건부 엣지 edge.decision 로깅
✅ debate/orchestrator.py — 토론 라운드별 구조화 로깅 + Langfuse trace
✅ api/routes/health.py — /health/live, /health/ready, /health/detailed
✅ docker-compose.monitoring.yml — Prometheus + Grafana + Loki
✅ monitoring/prometheus.yml — scrape config
✅ tools/mcp_client.py — structlog 스타일 로깅
✅ monitoring/quality_checker.py — get_logger 사용
```
