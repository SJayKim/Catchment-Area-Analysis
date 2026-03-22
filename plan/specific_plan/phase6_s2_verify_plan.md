# Phase 6 S2 검증 계획 — Import 검증 + 단위 테스트

> **작성일:** 2026-03-22
> **선행 조건:** S2 서비스 분리 코드 작성 완료
> **목표:** Docker 빌드 전 코드 품질 확보 — import 오류 0건, 신규 모듈 단위 테스트 커버

---

## 현재 상태

- S2 코드 작성 완료 (7개 신규, 3개 수정)
- 기존 71개 테스트 PASS
- Docker 환경 불가 (컨테이너 내부 개발 중)

## 발견된 이슈

| # | 파일 | 문제 | 심각도 |
|---|------|------|--------|
| 1 | `app/api/routes/health.py:115` | `async_session_factory` → `get_session_factory` import명 불일치 | Critical |

---

## Step별 실행 계획

### Step 1: 발견된 버그 수정 (5분)

- `app/api/routes/health.py` — `async_session_factory` → `get_session_factory` 수정

### Step 2: Import 검증 (10분)

각 신규 모듈의 import가 깨지지 않는지 Python 인터프리터로 검증:

```bash
python -c "from app.engine.redis_broker import RedisBroker"
python -c "from app.engine.worker import EngineWorker, main"
python -c "from app.pipeline.main import main"
python -c "from app.api.routes.analysis import init_broker, close_broker"
```

### Step 3: Redis Broker 단위 테스트 (30분)

`tests/unit/test_redis_broker.py` 작성

테스트 항목:
- `RedisBroker` 초기 상태 (연결 전 RuntimeError)
- `publish_request()` — Redis XADD 호출 검증
- `consume_requests()` — XREADGROUP 반환값 처리
- `publish_progress()` — Pub/Sub PUBLISH 호출 검증
- `subscribe_progress()` — 메시지 수신 + done 시 종료
- `store_result()` / `get_result()` — SET/GET 호출 검증
- `update_status()` / `get_status()` — HSET/HGETALL 호출 검증

목킹 대상: `redis.asyncio.Redis` (실제 Redis 없음)

### Step 4: API Analysis 라우트 테스트 (30분)

`tests/unit/test_analysis_routes.py` 작성

테스트 항목:
- `POST /api/v1/analysis` → 202 + request_id 반환
- `GET /api/v1/analysis/{id}` → 상태 조회 (존재/미존재)
- `GET /api/v1/analysis/{id}/stream` → SSE 스트리밍 (완료 상태)
- 에러 응답 형식 검증 (404 ANALYSIS_NOT_FOUND)

목킹 대상: `RedisBroker` (analysis.py의 `_broker`)

### Step 5: Engine Worker 단위 테스트 (20분)

`tests/unit/test_engine_worker.py` 작성

테스트 항목:
- `EngineWorker` 생성 + consumer_name 포맷
- `_process_request()` — AnalysisService 호출 + 결과 저장
- 에러 시 status "failed" 업데이트
- `stop()` 호출 시 `_running = False`

목킹 대상: `RedisBroker`, `AnalysisService`

### Step 6: Pipeline Main 테스트 (10분)

`tests/unit/test_pipeline_main.py` 작성

테스트 항목:
- `register_all_jobs()` 호출 확인
- 스케줄러 `start()` 호출 확인

목킹 대상: `app.scheduler.jobs`

### Step 7: 전체 테스트 실행 + 결과 확인 (5분)

```bash
pytest tests/ -v
```

기존 71개 + 신규 테스트 전부 PASS 확인

---

## 신규 테스트 파일 목록

| 파일 | 테스트 대상 | 예상 테스트 수 |
|------|-----------|--------------|
| `tests/unit/test_redis_broker.py` | RedisBroker 전체 메서드 | ~10 |
| `tests/unit/test_analysis_routes.py` | API analysis 라우트 | ~5 |
| `tests/unit/test_engine_worker.py` | EngineWorker | ~4 |
| `tests/unit/test_pipeline_main.py` | Pipeline main | ~2 |

---

## 성공 기준

| 기준 | 측정 | 결과 |
|------|------|------|
| Import 오류 0건 | 4개 모듈 python -c import 성공 | ✅ 4/4 |
| 발견 버그 수정 | health.py 수정 후 기존 테스트 PASS | ✅ |
| 신규 테스트 PASS | 27개 신규 테스트 전부 PASS | ✅ 27/27 |
| 기존 테스트 유지 | 71개 기존 테스트 PASS | ✅ 71/71 |
| 총 테스트 수 | **98개 PASS** (2.41s) | ✅ |

---

## 실행 결과 (2026-03-22)

```
✅ Step 1: health.py async_session_factory → get_session_factory 수정
✅ Step 2: Import 검증 — 4개 모듈 전부 성공
✅ Step 3: Redis Broker 테스트 — 13개 PASS
✅ Step 4: API Analysis 라우트 테스트 — 8개 PASS
✅ Step 5: Engine Worker 테스트 — 4개 PASS
✅ Step 6: Pipeline Main 테스트 — 2개 PASS
✅ Step 7: 전체 테스트 — 98개 PASS (2.41s)
```
