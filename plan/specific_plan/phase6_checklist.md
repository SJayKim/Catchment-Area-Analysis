# Phase 6 체크리스트 — 버그 수정, 서비스 분리 & E2E 테스트

> 최종 업데이트: 2026-03-22
> 상태: 🔄 S2 완료, S3/S4 대기

---

## S1: Critical 버그 수정 ✅

### Step 1: debate_check_node Revenue 필드명 수정
- [x] `app/graph/nodes.py` — `estimated_revenue` → `estimated_monthly_revenue` ✅
- [x] `app/graph/nodes.py` — `revenue_lower_bound` → `revenue_range` dict의 `min_value` ✅
- [x] `app/graph/nodes.py` — `revenue_upper_bound` → `revenue_range` dict의 `max_value` ✅
- [x] 수정 후 debate 트리거 조건 정상 동작 확인 ✅

### Step 2: 스케줄러 Collector 호출 파라미터 수정
- [x] `app/scheduler/jobs.py` — SEMAS 3개 job: district 목록 순회 + year/quarter 파라미터 추가 ✅
- [x] `app/scheduler/jobs.py` — Seoul 3개 job: dong_code/date 파라미터 추가 ✅
- [x] 모든 job 함수에 api_key 파라미터 전달 확인 ✅
- [x] Collector `__init__(session, api_key)` 시그니처와 일치 확인 ✅
- [x] 헬퍼 함수 추가: `_current_quarter()`, `_prev_month()`, `_get_districts()` ✅

### Step 3: Health 엔드포인트 Redis import 수정
- [x] `app/api/routes/health.py` — `_redis_client` import → `health_check` 함수 import ✅
- [x] `_check_redis()` 함수 로직을 `health_check()` 호출로 변경 ✅

### Step 4: Quality Checker DB 컬럼 수정
- [x] `app/monitoring/quality_checker.py` — `daily_boarding` → `boarding_total` ✅
- [x] `PopulationStat.period` → `year, quarter` GROUP BY로 수정 ✅
- [x] `CollectionLog.source` → `CollectionLog.collector_name` 수정 ✅
- [x] `CollectionLog.started_at` → `CollectionLog.created_at` 수정 ✅
- [x] anomaly check row index 수정 (rows[0][1] → rows[0][2]) ✅

### Step 5: 기존 테스트 통과 확인
- [x] `tests/unit/test_nodes.py` — revenue variance 테스트 필드명 업데이트 ✅
- [x] `pytest tests/` 실행 — **71개 테스트 전부 PASS** ✅

---

## S2: 서비스 분리 + Docker 인프라 ✅

> 설계 결정: 단일 Docker 이미지 + 다중 엔트리포인트 (코드 변경 최소화)

### Step 6: Dockerfile + 빌드 기반
- [x] `Dockerfile` 작성 (python:3.11-slim, 공용 이미지) ✅
- [x] `.dockerignore` 작성 ✅
- [x] `pyproject.toml` — `[build-system]` 섹션 추가 (pip install 오류 수정) ✅

### Step 7: Redis 브로커 모듈
- [x] `app/engine/redis_broker.py` — RedisBroker 클래스 (Stream/Pub/Sub/Hash) ✅
- [x] publish_request, consume_requests, publish_progress, subscribe_progress ✅
- [x] store_result, get_result, update_status, get_status ✅

### Step 8: Engine Worker (분석 엔진 서비스)
- [x] `app/engine/__init__.py` — 패키지 초기화 ✅
- [x] `app/engine/worker.py` — EngineWorker 클래스 (Redis Stream 소비 → LangGraph 실행) ✅
- [x] `app/engine/__main__.py` — `python -m app.engine` 진입점 ✅

### Step 9: API 리팩토링 (인메모리 → Redis)
- [x] `app/api/routes/analysis.py` — _analysis_store/_analysis_queues 제거 ✅
- [x] create_analysis → `redis_broker.publish_request()` ✅
- [x] get_analysis → `redis_broker.get_status()` + `get_result()` ✅
- [x] stream_analysis → `redis_broker.subscribe_progress()` (SSE) ✅
- [x] `app/main.py` — lifespan에 broker init/close 추가, MCP Router init 제거 ✅

### Step 10: Pipeline 진입점 (스케줄러 서비스)
- [x] `app/pipeline/__init__.py` — 패키지 초기화 ✅
- [x] `app/pipeline/main.py` — APScheduler 독립 실행 + graceful shutdown ✅
- [x] `app/pipeline/__main__.py` — `python -m app.pipeline` 진입점 ✅

### Step 11: docker-compose.yml 재구성
- [x] `marketscope-api` 서비스 추가 (port 8000, depends_on: redis, postgres) ✅
- [x] `marketscope-engine` 서비스 추가 (depends_on: redis, postgres) ✅
- [x] `marketscope-pipeline` 서비스 추가 (depends_on: postgres, redis) ✅
- [x] 9개 MCP 서버 유지 (기존 구조) ✅
- [x] 기존 71개 테스트 전부 PASS 확인 ✅

---

## S3: 서비스별 테스트

### Step 12: API 서비스 테스트
- [ ] `GET /health` → 200 OK
- [ ] `GET /health/ready` → DB, Redis 상태 확인
- [ ] `POST /api/v1/analysis` → 202 Accepted + request_id
- [ ] Redis Stream에 메시지 발행 확인
- [ ] `GET /api/v1/analysis/{id}` → 상태 조회
- [ ] `GET /api/v1/analysis/{id}/stream` → SSE 연결 유지

### Step 13: Engine 서비스 테스트
- [ ] LangGraph DAG 빌드 (20노드) 확인
- [ ] Redis Stream에서 작업 수신 확인
- [ ] MCP 서버 연결 확인 (health check)
- [ ] 단일 에이전트 실행 → 결과 반환
- [ ] 분석 완료 → Redis Hash에 결과 저장 확인

### Step 14: MCP 서버 테스트
- [ ] public_data (5100) — `/health` 응답
- [ ] maps (5101) — `/health` 응답
- [ ] real_estate (5102) — `/health` 응답
- [ ] news (5103) — `/health` 응답
- [ ] regulatory (5104) — `/health` 응답
- [ ] finance (5105) — `/health` 응답
- [ ] database (5106) — `/health` 응답 (postgres 의존)
- [ ] google_maps (5107) — `/health` 응답
- [ ] naver_maps (5108) — `/health` 응답

### Step 15: Pipeline 서비스 테스트
- [ ] 스케줄러 job 등록 확인 (8개)
- [ ] Collector 단위 실행 (dry-run)

---

## S4: E2E 테스트

### Step 16: 전체 인프라 기동
- [ ] `docker-compose up -d` 실행
- [ ] 14개 서비스 전부 healthy 확인

### Step 17: Happy Path — 강남역 카페 분석
- [ ] `POST /api/v1/analysis` 요청 전송
- [ ] SSE 스트리밍으로 진행률 수신 확인
- [ ] 분석 완료 대기 (최대 120초)
- [ ] `GET /api/v1/analysis/{id}` — 결과 조회
- [ ] 결과 필드 검증 (population, competition, revenue, location, judgment, narrative)

### Step 18: 에러 시나리오 테스트
- [ ] 빈 query 전송 → 적절한 에러 응답
- [ ] 존재하지 않는 request_id 조회 → 404
- [ ] MCP 서버 1개 중지 후 분석 실행 → graceful degradation

### Step 19: 성능 측정
- [ ] Standard 분석 소요 시간 기록
- [ ] LLM 호출 횟수 및 토큰 사용량 기록
- [ ] 분석 1건당 예상 비용 계산

### Step 20: 검증 보고서 작성
- [ ] E2E 테스트 결과 요약
- [ ] 발견된 이슈 및 해결 방안
- [ ] 다음 단계 (Phase 7) 제안

---

## 검증 결과

```
✅ S1: Critical 버그 수정 — 완료 (4건 수정, 71개 테스트 PASS)
✅ S2: 서비스 분리 + Docker — 완료 (3서비스 분리, docker-compose 구성)
⬜ S3: 서비스별 테스트 — 대기
⬜ S4: E2E 테스트 — 대기
```
