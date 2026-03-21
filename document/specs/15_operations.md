# 15. 운영 & 트러블슈팅 명세서

> MarketScope AI 운영 가이드
> 작성일: 2026-03-21

---

## 목차

1. [로깅 전략](#1-로깅-전략)
2. [모니터링 대시보드](#2-모니터링-대시보드)
3. [알림 규칙](#3-알림-규칙)
4. [장애 유형 & 디버깅](#4-장애-유형--디버깅)
5. [백업 & 복구](#5-백업--복구)
6. [성능 튜닝](#6-성능-튜닝)
7. [수평 확장](#7-수평-확장)
8. [인시던트 대응 런북](#8-인시던트-대응-런북)

---

## 1. 로깅 전략

### 1.1 로깅 파이프라인

```
App (structlog)
  ↓ JSON (production) / Console (dev)
stdout/stderr
  ↓ Docker log driver
Loki (로그 수집)
  ↓ LogQL 쿼리
Grafana (시각화)
```

### 1.2 structlog 설정

| 환경 | 렌더러 | 출력 형식 |
|------|--------|-----------|
| 개발 (`development`) | `ConsoleRenderer(colors=True)` | 컬러 텍스트 |
| 운영 (`production`) | `JSONRenderer(ensure_ascii=False)` | JSON (Loki 호환) |

### 1.3 로그 이벤트 카탈로그

| 이벤트 | 모듈 | 레벨 | 컨텍스트 |
|--------|------|------|----------|
| `agent.start` | agents/base.py | INFO | agent_name, session_id, location, industry |
| `agent.llm_call` | agents/base.py | INFO | model, tokens, latency_ms |
| `agent.mcp_call` | agents/base.py | INFO | tool, success, latency_ms |
| `agent.complete` | agents/base.py | INFO | confidence, duration_ms |
| `agent.error` | agents/base.py | ERROR | error_type, error_message |
| `node.start` | monitoring/dag_tracer.py | INFO | node_name |
| `node.complete` | monitoring/dag_tracer.py | INFO | node_name, duration_ms |
| `edge.decision` | graph/edges.py | INFO | edge, result, reason |
| `debate.start` | debate/orchestrator.py | INFO | session_id, trigger_reason |
| `debate.round.complete` | debate/orchestrator.py | INFO | round_number, duration_ms |
| `debate.complete` | debate/orchestrator.py | INFO | total_rounds, convergence_reached |
| `debate_check.evaluated` | graph/nodes.py | INFO | decision, triggers, avg_confidence |
| `user_input.parsed` | graph/nodes.py | INFO | session_id, input_length |
| `mcp.routing` | tools/mcp_client.py | INFO | tool, server, actual_name |
| `mcp.circuit_breaker` | monitoring/mcp_monitor.py | WARNING | server, consecutive_errors |

### 1.4 LogQL 유용한 쿼리

```logql
# 에이전트 에러 (최근 1시간)
{job="marketscope"} |= "agent.error" | json | line_format "{{.agent_name}}: {{.error_message}}"

# 느린 LLM 호출 (> 10초)
{job="marketscope"} |= "agent.llm_call" | json | latency_ms > 10000

# 토론 트리거 이유
{job="marketscope"} |= "debate_check.evaluated" | json | decision="trigger"

# MCP 서킷 브레이커 경고
{job="marketscope"} |= "mcp.circuit_breaker"
```

---

## 2. 모니터링 대시보드

### 2.1 Prometheus 메트릭 (11종)

| 메트릭 | 타입 | 라벨 | 용도 |
|--------|------|------|------|
| `http_request_duration_seconds` | Histogram | method, path, status | API 레이턴시 |
| `http_requests_total` | Counter | method, path, status | API 처리량 |
| `agent_execution_seconds` | Histogram | agent_name | 에이전트 실행 시간 |
| `agent_errors_total` | Counter | agent_name, error_type | 에이전트 에러 |
| `llm_tokens_total` | Counter | model, type (prompt/completion) | 토큰 사용량 |
| `llm_cost_dollars` | Counter | model | LLM 비용 |
| `mcp_call_duration_seconds` | Histogram | server, tool | MCP 레이턴시 |
| `mcp_errors_total` | Counter | server, error_type | MCP 에러 |
| `debate_rounds_total` | Counter | — | 토론 라운드 수 |
| `debate_convergence` | Gauge | — | 토론 수렴률 |
| `pipeline_duration_seconds` | Histogram | mode | 파이프라인 전체 시간 |
| `pipeline_node_duration_seconds` | Histogram | node | 노드별 시간 |

### 2.2 핵심 대시보드 패널

| 패널 | PromQL | 목적 |
|------|--------|------|
| API p95 레이턴시 | `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` | SLA 모니터링 |
| 분석 처리량 | `rate(http_requests_total{path="/analyze"}[5m])` | 트래픽 |
| 에이전트 에러율 | `rate(agent_errors_total[5m]) / rate(agent_execution_seconds_count[5m])` | 안정성 |
| LLM 시간당 비용 | `increase(llm_cost_dollars[1h])` | 비용 관리 |
| MCP 서버별 상태 | `rate(mcp_errors_total[5m])` by server | MCP 건강도 |

---

## 3. 알림 규칙

### 3.1 AlertManager 규칙

```yaml
groups:
  - name: marketscope
    rules:
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API p95 레이턴시 5초 초과"

      - alert: HighAgentErrorRate
        expr: rate(agent_errors_total[5m]) > 0.1
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "에이전트 에러율 분당 0.1 초과"

      - alert: MCPCircuitBreakerOpen
        expr: mcp_errors_total > 3
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "MCP 서버 연속 3회 실패 (서킷 브레이커)"

      - alert: HighLLMCost
        expr: increase(llm_cost_dollars[1h]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "시간당 LLM 비용 $10 초과"

      - alert: DatabaseConnectionPoolExhausted
        expr: pg_stat_activity_count > 90
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "DB 커넥션 풀 90% 이상 사용"
```

---

## 4. 장애 유형 & 디버깅

### 4.1 LLM API 장애

| 증상 | 원인 | 해결 |
|------|------|------|
| `litellm.RateLimitError` | API 할당량 초과 | Fallback 모델 확인, 비용 대시보드 확인 |
| `litellm.AuthenticationError` | API 키 만료/잘못됨 | `.env` API 키 갱신 |
| `litellm.Timeout` | 모델 응답 지연 | timeout 설정 확인, 재시도 로직 확인 |

### 4.2 MCP 서버 장애

| 증상 | 원인 | 해결 |
|------|------|------|
| `MCPConnectionError` | MCP 서버 다운 | `docker ps` 확인, 서버 재시작 |
| 서킷 브레이커 경고 | 연속 3회 실패 | 해당 서버 로그 확인, 외부 API 상태 점검 |
| 라우팅 실패 | tool_name prefix 오류 | `MCPClientRouter._server_map` 확인 |

### 4.3 DB 장애

| 증상 | 원인 | 해결 |
|------|------|------|
| `asyncpg.ConnectionError` | DB 연결 불가 | `docker-compose logs postgres` 확인 |
| 마이그레이션 실패 | 스키마 불일치 | `alembic history` → `alembic upgrade head` |
| 쿼리 타임아웃 | 인덱스 누락 / 대량 데이터 | `EXPLAIN ANALYZE` 실행, 인덱스 추가 |

### 4.4 Redis 장애

| 증상 | 원인 | 해결 |
|------|------|------|
| `ConnectionRefusedError` | Redis 다운 | `docker-compose up -d redis` |
| 메모리 초과 | 캐시 과다 | `redis-cli INFO memory` → TTL 조정 |

---

## 5. 백업 & 복구

### 5.1 PostgreSQL 백업

```bash
# 일일 백업 (cron: 0 3 * * *)
pg_dump -h localhost -U marketscope_user -d marketscope \
  --format=custom --compress=9 \
  -f /backups/marketscope_$(date +%Y%m%d_%H%M%S).dump

# 복구
pg_restore -h localhost -U marketscope_user -d marketscope \
  --clean --if-exists \
  /backups/marketscope_20260321_030000.dump
```

### 5.2 Redis 백업

```bash
# RDB 스냅샷 (기본 설정)
redis-cli BGSAVE

# AOF 활성화 (docker-compose.yml)
command: redis-server --appendonly yes
```

### 5.3 백업 보존 정책

| 유형 | 보존 기간 | 주기 |
|------|-----------|------|
| PostgreSQL 전체 | 30일 | 일 1회 (03:00) |
| PostgreSQL WAL | 7일 | 연속 |
| Redis RDB | 7일 | 일 1회 |
| Prometheus TSDB | 7일 | 자동 (retention) |

---

## 6. 성능 튜닝

### 6.1 PostgreSQL

```sql
-- PostGIS 공간 인덱스
CREATE INDEX idx_stores_geom ON stores USING GIST (geom);
CREATE INDEX idx_commercial_districts_center ON commercial_districts USING GIST (center_geom);

-- 자주 사용되는 쿼리 인덱스
CREATE INDEX idx_stores_industry ON stores (industry_category);
CREATE INDEX idx_area_revenue_code ON area_revenue (area_code);
CREATE INDEX idx_population_grid_area ON population_grid (area_code);
```

### 6.2 Redis 캐시

| 키 패턴 | TTL | 용도 |
|---------|-----|------|
| `mcp:{server}:{tool}:{hash}` | 1~12시간 | MCP 응답 캐시 |
| `session:{session_id}` | 24시간 | 분석 세션 |
| `rate_limit:{ip}` | 1분 | Rate limiting |

### 6.3 커넥션 풀

| 서비스 | 풀 크기 | 설정 |
|--------|---------|------|
| PostgreSQL (앱) | min=5, max=20 | `asyncpg.create_pool()` |
| PostgreSQL (MCP DB) | min=2, max=10 | `asyncpg.create_pool()` |
| Redis | max=10 | `redis.ConnectionPool()` |
| httpx (MCP 클라이언트) | max=10 | `httpx.Limits()` |

---

## 7. 수평 확장

### 7.1 확장 포인트

| 컴포넌트 | 확장 방식 | 고려사항 |
|----------|-----------|----------|
| FastAPI 앱 | Cloud Run 인스턴스 증가 | 세션 상태 Redis 공유 |
| MCP 서버 | 개별 컨테이너 스케일링 | Stateless 설계 |
| PostgreSQL | Read Replica | 읽기 분산, 쓰기는 Primary |
| Redis | Redis Cluster | 캐시 분산 |

### 7.2 Celery (Phase 5)

```python
# 비동기 분석 작업 큐
celery_app = Celery("marketscope", broker="redis://localhost:6379/1")

@celery_app.task
def run_analysis_task(session_id: str, user_input: str):
    """백그라운드 분석 실행."""
    ...
```

---

## 8. 인시던트 대응 런북

### 8.1 Severity 정의

| 레벨 | 정의 | 응답 시간 | 예시 |
|------|------|-----------|------|
| **P1 (Critical)** | 서비스 전면 장애 | 15분 | DB 다운, 전체 MCP 장애 |
| **P2 (High)** | 주요 기능 장애 | 30분 | LLM API 전면 장애, 분석 실패율 > 50% |
| **P3 (Medium)** | 부분 기능 장애 | 2시간 | 개별 MCP 서버 장애, 느린 응답 |
| **P4 (Low)** | 비기능적 이슈 | 24시간 | 로그 누락, 대시보드 표시 오류 |

### 8.2 대응 절차

```
1. 감지 → Grafana 알림 또는 사용자 보고
2. 확인 → 대시보드에서 영향 범위 파악
3. 분류 → Severity 결정
4. 조치 → 아래 체크리스트 실행
5. 복구 확인 → 헬스체크 정상 여부
6. 사후 분석 → 원인 분석 & 재발 방지
```

### 8.3 빠른 진단 명령어

```bash
# 서비스 상태 확인
docker-compose ps

# 앱 헬스체크
curl http://localhost:8000/health/detailed

# 로그 확인 (최근 100줄)
docker-compose logs --tail=100 app

# PostgreSQL 연결 확인
docker exec marketscope-postgres pg_isready

# Redis 연결 확인
docker exec marketscope-redis redis-cli ping

# MCP 서버 상태 일괄 확인
for port in 5100 5101 5102 5103 5104 5105 5106 5107 5108; do
  echo -n "Port $port: "
  curl -s http://localhost:$port/health | jq -r '.status // "DOWN"'
done
```
