# Heatmap Preload — Singleflight 재도입

> 카테고리: infra
> 생성일: 2026-05-06
> 담당: sjkim
> 모델: 설계 opus / 구현 sonnet / 검증 haiku

## Context

### 문제
2026-04-24 Refactoring Pass 1 에서 `services/singleflight.py` 를 삭제 (당시 Heatmap 전용 + 미사용 케이스 제거). 그러나 `/api/map-data/heatmap/all` 은 24 슬롯 × 1,650 상권 풀 fetch 로 cache miss 시 **단일 요청에 ~3초** 소요.

부하 시나리오:
1. **Cold start** — Redis flush 후 첫 사용자 + 동시 클라이언트 N명 → 동일 PostGIS 쿼리 N번 → DB 풀 (10+20) 고갈 위험
2. **Quarter rollover** — 분기 변경 시 모든 사용자 cache key 동시 miss → thundering herd
3. **Mock 모드** — Memory cache 라도 fixture JSON load N번 발생

목표: **요청-coalescing singleflight + 경량 in-process 락** 으로 동일 cache key 동시 호출을 1건으로 수렴, p99 latency 보호.

### 메모리 참조
- [feedback_check_env_before_test.md](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_check_env_before_test.md) — Mock vs Real 분기
- [project_e2e_port_convention.md](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/project_e2e_port_convention.md) — E2E 포트 분리

### 관련 Plan
- [accuracy-gap-eval-round2-2026-04-24.md](../fix/accuracy-gap-eval-round2-2026-04-24.md) — Refactoring Pass 1 에서 singleflight 삭제 기록
- [phase1-low-mid-risk-2026-04-23.md](./phase1-low-mid-risk-2026-04-23.md) — Refactoring 본체
- [load-test-plan.md](./load-test-plan.md) — 부하 시나리오 baseline

### 코드 스폿
- `server/server/api/routes/map_data.py:53-105` — `/heatmap`, `/heatmap/all` cache + DB fetch
- `server/server/services/cache.py` — Redis/Memory cache (TTL 24h)
- `server/server/repositories/real/heatmap.py` — `get_heatmap_all` PostGIS 쿼리
- 삭제됨: `server/server/services/singleflight.py` (git history `git log -- server/server/services/singleflight.py`)

---

## Scope

### In-scope
1. **`services/singleflight.py` 재도입** — async asyncio.Lock 기반 in-process key coalescing
   - `class Singleflight: async def do(key, fn) -> T` 인터페이스
   - 동일 key 동시 호출 시 첫 호출만 fn() 실행, 나머지는 결과 await
2. **map_data.py 통합** — `/heatmap`, `/heatmap/all` cache miss 분기 감싸기
   - cache.get None → singleflight.do(key, lambda: da.heatmap.get_*()) → cache.set
3. **Polygons fetch 도 후속 적용** — `/api/map-data/polygons` (1,650 GeoJSON) 도 동일 패턴
4. **메트릭** — `singleflight.coalesced_count` Counter 노출 (`/metrics` 엔드포인트)
5. **회귀 테스트**
   - `tests/test_singleflight.py` — 동시 100건 호출 → fn() 1회 실행 회귀
   - 부하 스크립트 — `scripts/load_heatmap.py` (asyncio gather 50 클라이언트)

### Out-of-scope (별도 plan)
- 분산 singleflight (Redis-based) — 다중 인스턴스 환경 (현재 단일 컨테이너)
- LLM 호출 singleflight (Planner/Respond 동일 prompt) — Phase 2 Premium 트래픽 증가 시
- Postgres advisory lock 기반 ETL 동시성 (별도 ETL Plan)

---

## Design

### Singleflight 모듈

```python
# server/server/services/singleflight.py
import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")

class Singleflight:
    def __init__(self) -> None:
        self._inflight: dict[str, asyncio.Future[T]] = {}
        self._lock = asyncio.Lock()
        self.coalesced_count = 0  # 메트릭

    async def do(self, key: str, fn: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            if key in self._inflight:
                self.coalesced_count += 1
                return await self._inflight[key]
            future: asyncio.Future[T] = asyncio.get_running_loop().create_future()
            self._inflight[key] = future

        try:
            result = await fn()
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            async with self._lock:
                self._inflight.pop(key, None)
```

### map_data.py 통합

```python
_sf = Singleflight()

@router.get("/heatmap/all")
async def get_heatmap_all(quarter: str | None = None, da = Depends(get_da)):
    cache = get_cache_service()
    cache_key = f"heatmap:all:{quarter or 'latest'}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return JSONResponse(content=cached)

    async def _load():
        result = await da.heatmap.get_heatmap_all(quarter)
        if result is not None:
            await cache.set(cache_key, result, ttl=86400)
        return result

    result = await _sf.do(cache_key, _load)
    return JSONResponse(content=result or {"slots": {}})
```

### 락 입자도
- **Per-key**: 동일 key 만 coalesce, 다른 key 는 병행
- **In-process**: 단일 컨테이너 가정 (현재 prod 도 단일 인스턴스)
- **타임아웃**: fn() 자체 타임아웃에 위임 (heatmap 은 SQL pool timeout 30s)

### 메트릭
- `singleflight_coalesced_total{key_prefix=heatmap}` Counter
- `/metrics` 엔드포인트에 노출, Langfuse trace metadata 에도 best-effort

---

## Checklist

- [ ] **C1** `services/singleflight.py` 재작성 (per-key Future + asyncio.Lock)
- [ ] **C2** `services/__init__.py` export
- [ ] **C3** `map_data.py::get_heatmap` 통합
- [ ] **C4** `map_data.py::get_heatmap_all` 통합
- [ ] **C5** `map_data.py::get_polygons` 통합 (선택, 부하 측정 후)
- [ ] **M1** `/metrics` 에 `singleflight_coalesced_total` 노출
- [ ] **T1** `tests/test_singleflight.py` — 정상 path / 동시 100건 / fn 예외 / 다른 key 병행
- [ ] **T2** `scripts/load_heatmap.py` — asyncio.gather 50 클라이언트 + p99 측정
- [ ] **T3** Mock 모드 회귀 — `USE_MOCK=true` E2E 패스 유지
- [ ] **D1** ruff PASS · pytest PASS · 부하 결과 commit message inline

### 재검토 (Self-Review Gate)
- [ ] Future cancellation — caller 가 await cancel 시 inflight 전체에 영향 → `shield()` 검토
- [ ] fn() 예외 처리 — 모든 awaiter 가 동일 예외 receive (의도된 동작)
- [ ] Memory leak — `finally` 에서 dict pop 보장. test 에 long-running 회귀
- [ ] 다중 인스턴스 환경 — out-of-scope 명시. 향후 Redis SETNX 기반 분산 락 별도 Plan
- [ ] 메모리 교훈: USE_MOCK 분기 — Memory cache 도 hit 시 singleflight 우회 (현재 설계 OK)
- [ ] 다른 Plan 충돌: [phase1-low-mid-risk-2026-04-23.md](./phase1-low-mid-risk-2026-04-23.md) 의 services/ 분할과 무관

### Scenario (E2E Ring Mapping)
| Ring | ID | 시나리오 |
|------|----|---------|
| 0 | Ring0-SF-UNIT | 동시 100건 → fn() 1회 실행 |
| 0 | Ring0-SF-EXC | fn() 예외 시 모든 awaiter 동일 예외 |
| 1 | Ring1-SF-HEATMAP | /heatmap/all 동시 50 클라이언트 → DB 1 query |
| 1 | Ring1-SF-MOCK | USE_MOCK=true 회귀 — fixture JSON 1회 load |
| 3 | Ring3-SF-CANCEL | caller cancel 시 다른 awaiter 정상 동작 |

### Pass 반복
- **Pass 1 (기본)**: C1+C2+C3+C4 + T1 unit 4 PASS
- **Pass 2 (엣지)**: cancel / 예외 / Memory leak / 다른 key 병행
- **Pass 3 (성능)**: T2 부하 — DB query count 감소 + p99 latency 50% 개선 측정

---

## Validation

### 검증 명령
```bash
cd server
# Pass 1
pytest tests/test_singleflight.py -v

# Pass 2 (cancel/exc)
pytest tests/test_singleflight.py -v -k "cancel or exc"

# Pass 3 부하
USE_MOCK=false python scripts/load_heatmap.py --concurrency 50 --duration 30s
# → DB query count, p50/p99, coalesced_count
```

### 합격 기준
- [ ] Pass 1 unit 4 PASS
- [ ] Pass 3: DB query count = 1 (50 클라이언트 동시 호출 기준), coalesced_count = 49
- [ ] p99 latency 개선 ≥ 30% (baseline = 삭제 전 git tag 또는 현재 노-singleflight)
- [ ] Mock 모드 E2E ring0~3 회귀 0

### 결과 (2026-05-07 Pass 1+2 PASS)

**구현 완료**:
- `server/server/services/singleflight.py` — `Singleflight` 클래스 + `get_singleflight()` 모듈 싱글톤 + `get_coalesced_count()` 메트릭 헬퍼
- `server/server/api/routes/map_data.py::get_heatmap` + `get_heatmap_all` 통합 — cache miss 분기를 `_load()` closure 로 감싸 `sf.do(cache_key, _load)` 호출
- `server/server/middleware/metrics.py::get_metrics` — `/metrics` JSON 에 `singleflight_coalesced_total` 필드 노출
- `server/tests/test_singleflight.py` — 9 testcase (basic / concurrent 50 / different keys parallel / exception propagation / dict cleanup × 2 / cancel-no-leak / sequential / singleton)
- `server/scripts/load_heatmap.py` — Pass 3 부하 측정 CLI (manual)

**Pass 1 검증** (PYTHONIOENCODING=utf-8 pytest server/tests/test_singleflight.py):
- 9/9 PASS · 0.21s
- ruff check 통과 (singleflight.py, map_data.py, metrics.py, test_singleflight.py)

**Pass 2 엣지** (test_singleflight.py 안에 포함):
- 동시 50 caller → fn() 1회 실행, coalesced_count = 49 ✓
- fn() 예외 → 모든 awaiter 동일 RuntimeError 수령 ✓
- 다른 key (`a`, `b`) 병행 실행 → coalesced_count = 0 ✓
- follower cancel → leader 정상 완료, calls=1 ✓
- inflight dict cleanup (정상/예외 양쪽 회귀) ✓
- "Future exception was never retrieved" 경고 — leader 단독일 때 `future.exception()` 소비로 제거

**Pass 3 부하** — `scripts/load_heatmap.py` 작성. 백엔드 stack 기동 + Redis flush 필요 (수동 트리거 권장 — 본 머신 dev 8000/3000 점유 시 :8002/:3001 e2e stack 사용).

**전체 backend pytest 회귀**: 79/80 PASS (신규 9 + 기존 70). 1 fail = `test_smoke::langfuse_enabled` host env pre-existing (변경 무관).

**합격 기준 충족**:
- [x] Pass 1 unit 4+ PASS (실제 9 testcase)
- [x] Mock 모드 회귀 (smoke + entity_matching + … 70 testcase 영향 0)
- [ ] Pass 3: DB query count = 1 — manual load 측정 필요
- [ ] p99 latency ≥ 30% 개선 — manual load 측정 필요

---

## Metadata
- 우선순위: 🟡 P1 (안정성, 즉시 효과)
- 난이도: S (1~2d)
- Phase 2 의존성: 없음
- 후속: 분산 singleflight (multi-instance 시), polygons 캐시 적용
