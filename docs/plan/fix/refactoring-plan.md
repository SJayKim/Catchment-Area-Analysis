# MarketScope AI Refactoring Plan

> 작성일: 2026-04-02
> 목적: 안정성, 범용성, 확장성 개선을 위한 전체 리팩토링 계획
> 원칙: **동작을 바꾸지 않으면서** 내부 구조를 개선하여 Phase 2/3 확장을 용이하게 함

---

## Context

MarketScope AI는 FastAPI + LangGraph + Next.js 14 기반 상권분석 서비스로, 현재 Phase 1A/1B 상태.
`if settings.use_mock:` 분기가 12개 파일 22곳에 산재하고, Agent가 매 요청마다 재생성되며,
chatStore.sendMessage가 230줄 모놀리식 함수인 등 안정성/확장성 문제가 존재.

### 식별된 주요 이슈

| 우선순위 | 항목 | 영향 |
|----------|------|------|
| P0 | Mock/Real 분기 22곳 산재 | 전체 코드 가독성 + 확장성 |
| P0 | Agent 매 요청 생성 | 성능 + 안정성 |
| P1 | DB 세션 관리 불일치 | 안정성 |
| P1 | chatStore.sendMessage 230줄 | 프론트 확장성 |
| P1 | CORS / API URL 하드코딩 | 배포 범용성 |
| P2 | Redis 연결 풀링 미사용 | 성능 |
| P2 | 캐시 무효화 전략 부재 | 데이터 정확성 |
| P2 | Card/Event 핸들러 확장 어려움 | Phase 3 확장성 |
| P3 | Kakao Map 타입 any | 코드 품질 |
| P3 | console.log 디버그 로그 잔존 | 프로덕션 준비 |

---

## 파이프라인 영향 분석

| 영역 | 영향 | 위험도 |
|------|------|--------|
| API 응답 형태 (SSE/JSON) | 변경 없음 — Repository가 기존과 동일한 dict 반환 | 낮음 |
| 프론트엔드 렌더링 | 변경 없음 — 이벤트 타입/카드 데이터 형태 동일 | 낮음 |
| Mock 모드 동작 | 변경 없음 — MockRepository가 기존 mock_data.py 사용 | 낮음 |
| Real DB 모드 동작 | 변경 없음 — RealRepository가 기존 SQL 쿼리 그대로 사용 | 중간 |
| ETL 파이프라인 | 영향 없음 — ETL은 독립적으로 DB 직접 적재 | 없음 |
| E2E 테스트 (7 specs) | 영향 없음 — API surface 동일 | 낮음 |
| LangGraph Agent | tool 함수 시그니처 동일, 내부 위임만 변경 | 중간 |

---

## Phase 1: Backend Refactoring

### Step 1.1 — Repository Protocol + DataAccess 파사드 생성 (신규 파일만)

- [ ] `server/server/repositories/__init__.py` 생성
  - `get_data_access()` / `set_data_access()` 모듈 레벨 접근자
- [ ] `server/server/repositories/protocols.py` 생성
  - `DistrictRepository` Protocol — `get_district_meta`, `list_districts`, `get_district_detail`, `get_polygons_geojson`, `detect_district_by_name`
  - `FloatingPopulationRepository` Protocol — `get_floating_population`
  - `EstimatedSalesRepository` Protocol — `get_estimated_sales`
  - `StoreRepository` Protocol — `get_store_info`, `get_store_history`
  - `PopulationRepository` Protocol — `get_population_info`
  - `ComparisonRepository` Protocol — `compare_districts`
  - `RecommendationRepository` Protocol — `recommend_business`
- [ ] `server/server/repositories/data_access.py` 생성
  - `DataAccess` 파사드 클래스 (7개 repository를 하나로 통합 접근점)

**검증**: import 정상 동작, 기존 코드 영향 없음

### Step 1.2 — Mock Repository 구현 (신규 파일만)

- [ ] `server/server/repositories/mock/__init__.py` 생성
- [ ] `server/server/repositories/mock/districts.py` — `mock_data.py`의 DISTRICTS + `get_mock_district_list` + `get_mock_geojson` 로직 추출
- [ ] `server/server/repositories/mock/floating_population.py` — `FLOATING_POPULATION` dict lookup
- [ ] `server/server/repositories/mock/estimated_sales.py` — `ESTIMATED_SALES` dict lookup
- [ ] `server/server/repositories/mock/stores.py` — `STORE_INFO` + `STORE_HISTORY` dict lookup, `_detect_trend`/`_get_grade` 헬퍼 포함
- [ ] `server/server/repositories/mock/population.py` — `POPULATION_INFO` dict lookup
- [ ] `server/server/repositories/mock/comparison.py` — `get_compare_data` 로직 추출
- [ ] `server/server/repositories/mock/recommendation.py` — `get_recommendations` 로직 추출
- [ ] `server/server/repositories/mock/factory.py` — `build_mock_data_access() -> DataAccess`

**검증**: 각 mock repo 메서드 호출 → 기존 tool과 동일 dict shape 반환 확인

### Step 1.3 — Real (DB) Repository 구현 (신규 파일만)

- [ ] `server/server/repositories/real/__init__.py` 생성
- [ ] `server/server/repositories/real/districts.py` — `districts.py` + `map_data.py` + `chat.py`의 DB 쿼리 추출 (PostGIS ST_AsGeoJSON, ILIKE 검색, 조사 제거 로직)
- [ ] `server/server/repositories/real/floating_population.py` — `floating_population.py`의 3개 SQL (hourly/gender/age) 추출
- [ ] `server/server/repositories/real/estimated_sales.py` — `estimated_sales.py`의 4개 SQL 추출
- [ ] `server/server/repositories/real/stores.py` — `store_info.py` + `store_history.py`의 SQL 추출
- [ ] `server/server/repositories/real/population.py` — `population_info.py`의 3개 SQL 추출
- [ ] `server/server/repositories/real/comparison.py` — `compare_districts.py`의 multi-district 루프 SQL 추출
- [ ] `server/server/repositories/real/recommendation.py` — `recommend_business.py`의 스코어링 알고리즘 + SQL 추출
- [ ] `server/server/repositories/real/factory.py` — `build_real_data_access(session_factory) -> DataAccess`

**핵심**: 각 Real repo는 생성자에서 `async_sessionmaker`를 받아 `async with self._session_factory() as session:` 패턴 사용

**검증**: SQL 쿼리가 기존 tool 코드와 동일한지 diff 확인

### Step 1.4 — CacheService 분리 (기존 파일 수정)

- [ ] `server/server/services/cache.py` 수정
  - `MemoryCacheService` 클래스 — dict 기반 (기존 mock 분기)
  - `RedisCacheService` 클래스 — Redis 기반 + 연결 풀 재사용 (기존 real 분기)
  - 두 클래스 모두 `get`, `set`, `delete`, `close`, `flush_by_prefix` 메서드
  - `get_cache_service()` / `set_cache_service()` 접근자 패턴
  - 기존 `if settings.use_mock:` 4곳 제거

**수정 파일**: `server/server/services/cache.py`
**검증**: Mock 모드에서 in-memory 캐시 동작, TTL 무시 동작 유지

### Step 1.5 — FastAPI Lifespan + Agent 싱글턴 + CORS 환경변수화

- [ ] `server/server/config.py` 수정 — `cors_origins: list[str] = ["http://localhost:3000"]` 추가
- [ ] `server/server/main.py` 수정
  - `@asynccontextmanager async def lifespan(app)` 추가
  - Startup: `use_mock`에 따라 Mock/Real DataAccess 빌드 → `set_data_access()`
  - Startup: `use_mock`에 따라 Memory/Redis CacheService 빌드 → `set_cache_service()`
  - Startup: `create_agent()` 1회 호출 → `set_agent()`
  - Shutdown: `cache.close()`, `engine.dispose()` (real 모드)
  - CORS origins를 `settings.cors_origins`에서 읽도록 변경
- [ ] `server/server/agent/graph.py` 수정
  - `get_agent()` / `set_agent()` 모듈 레벨 접근자 추가
  - `run_agent()` 내 `create_agent()` 호출 → `get_agent()` 호출로 교체
- [ ] `server/server/models/base.py` 수정
  - 모듈 레벨 engine/async_session 생성 제거 → `Base` 클래스만 유지
  - engine 생성은 lifespan에서 처리

**수정 파일**: `config.py`, `main.py`, `graph.py`, `base.py`
**검증**: `USE_MOCK=true` 서버 기동 → `/health` 200 OK → 채팅 요청 정상 응답

### Step 1.6 — Tool 함수 Repository 위임으로 전환 (핵심 변경)

각 tool 함수를 ~100줄 → ~15줄로 축소. `if settings.use_mock:` 제거.

- [ ] `server/server/agent/tools/floating_population.py` — `da.floating_pop.get_floating_population()` 위임
- [ ] `server/server/agent/tools/estimated_sales.py` — `da.sales.get_estimated_sales()` 위임
- [ ] `server/server/agent/tools/store_info.py` — `da.stores.get_store_info()` 위임
- [ ] `server/server/agent/tools/population_info.py` — `da.population.get_population_info()` 위임
- [ ] `server/server/agent/tools/store_history.py` — `da.stores.get_store_history()` 위임
- [ ] `server/server/agent/tools/compare_districts.py` — `da.comparison.compare_districts()` 위임
- [ ] `server/server/agent/tools/recommend_business.py` — `da.recommendation.recommend_business()` 위임
- [ ] `server/server/agent/tools/district_summary.py` — `_get_district_meta` → `da.districts.get_district_meta()`. `"(샘플)"` 표시는 유일하게 남는 `settings.use_mock` 체크 (표현 로직)

**리팩토링 후 tool 패턴**:
```python
async def get_floating_population(district_code, quarter=None):
    cache = get_cache_service()
    cached = await cache.get(f"fp:{district_code}:{quarter or 'latest'}")
    if cached: return cached
    da = get_data_access()
    result = await da.floating_pop.get_floating_population(district_code, quarter)
    if "error" not in result:
        await cache.set(f"fp:{district_code}:{quarter or 'latest'}", result)
    return result
```

**수정 파일**: 8개 tool 파일
**검증**: 각 tool의 반환 dict shape가 리팩토링 전후 동일

### Step 1.7 — Route 핸들러 Repository 위임으로 전환

- [ ] `server/server/api/routes/districts.py` — Mock/Real 분기 제거, `da.districts.list_districts()` / `da.districts.get_district_detail()` 사용
- [ ] `server/server/api/routes/map_data.py` — Mock 분기 제거, `da.districts.get_polygons_geojson()` 사용
- [ ] `server/server/api/routes/chat.py` — 3개 Mock/Real 블록 제거, `da.districts.get_district_meta()` / `da.districts.detect_district_by_name()` 사용
- [ ] `server/server/api/deps.py` — `get_db()` / `get_redis()` 제거 → `get_da()` 반환 `get_data_access()`

**수정 파일**: 4개 route/deps 파일
**검증**: API 응답 shape 동일 확인 (`/api/districts`, `/api/districts/{code}`, `/api/map-data/polygons`, `/api/chat`)

### Step 1.8 — 세션 스토리지 캐시 기반 전환

- [ ] `server/server/api/routes/chat.py` — `_sessions` dict → CacheService 기반
  - 키: `session:{session_id}`, TTL: 1800초
  - 매 요청마다 전체 dict 순회 cleanup 제거

**수정 파일**: `chat.py`

### Step 1.9 — 시스템 프롬프트 + 동적 Suggestion

- [ ] `server/server/agent/prompts/system.py` — `is_mock` 파라미터화 (`settings` 직접 참조 제거)
- [ ] `server/server/agent/graph.py` — suggestion에 `district_name` 포함

**수정 파일**: `system.py`, `graph.py`

### Step 1.10 — 캐시 무효화 전략

- [ ] `CacheService`에 `flush_by_prefix(prefix)` 메서드 추가 (이미 1.4에서 추가)
- [ ] ETL 완료 후 캐시 flush 호출 추가 (`server/data/etl/loader.py` 또는 `runner.py`)
- [ ] (선택) `/admin/cache/flush` 관리 엔드포인트 추가

---

## Phase 2: Frontend Refactoring

### Step 2.1 — SSEEvent 타입 강화 (선행 작업)

- [ ] `frontend/src/lib/types.ts` — `SSEEvent`를 discriminated union으로 교체
  ```typescript
  export type SSEEvent =
    | { type: 'thinking'; step?: string; icon?: string }
    | { type: 'tool'; name: string; input?: Record<string, unknown>; icon?: string }
    | { type: 'tool_end'; name: string; icon?: string }
    | { type: 'text'; content: string }
    | { type: 'card'; card_type: string; data: Record<string, unknown> }
    | { type: 'map_cmd'; action: string; params?: Record<string, unknown>;
        district_code?: string; district_name?: string; district_type?: string }
    | { type: 'suggestion'; questions: string[] }
    | { type: 'done' }
    | { type: 'error'; message?: string };
  ```
  - `[key: string]: unknown` catch-all 제거

**수정 파일**: `types.ts`

### Step 2.2 — SSE Parser 모듈 추출

- [ ] `frontend/src/lib/sseParser.ts` 생성
  - `parseSSEStream(reader)` AsyncGenerator — TextDecoder, 라인 버퍼링, JSON 파싱 담당
  - chatStore.ts의 lines 161-197 로직 추출
  - 엣지 케이스: 빈 줄, `[DONE]`, 잘못된 JSON (silent skip), 버퍼 잔여분

**신규 파일**: `sseParser.ts`

### Step 2.3 — Event Handler Registry 추출

- [ ] `frontend/src/lib/eventHandlers.ts` 생성
  - `EventHandlerContext` 인터페이스 (get, set, firstTextReceived ref, onMapCmd callback)
  - 9개 핸들러 함수: `handleThinking`, `handleTool`, `handleToolEnd`, `handleText`, `handleCard`, `handleMapCmd`, `handleSuggestion`, `handleDone`, `handleError`
  - `EVENT_HANDLERS: Record<string, SSEEventHandler>` 레지스트리
  - `TOOL_LABELS` 상수 이동 (chatStore.ts → eventHandlers.ts)

**신규 파일**: `eventHandlers.ts`

### Step 2.4 — chatStore.sendMessage 슬림화

- [ ] `frontend/src/stores/chatStore.ts` 수정
  - `sendMessage` 함수: parseSSEStream + EVENT_HANDLERS 사용
  - 350줄 → ~120줄 축소
  - switch문, SSE 파싱 로직 제거

**수정 파일**: `chatStore.ts`

### Step 2.5 — Card Component Registry

- [ ] `frontend/src/components/chat/cards/registry.ts` 생성
  ```typescript
  export const CARD_REGISTRY: Record<string, ComponentType<{ data: Record<string, unknown> }>> = {
    summary: SummaryCard,
    compare: CompareCard,
    recommend: RecommendCard,
    risk: RiskCard,
  };
  ```
- [ ] `frontend/src/components/chat/MessageBubble.tsx` 수정
  - ternary chain (lines 32-46) → `CARD_REGISTRY[cardType]` 동적 lookup으로 교체
  - fallback: unknown type은 JSON dump (기존 동작 유지)

**신규 파일**: `registry.ts`
**수정 파일**: `MessageBubble.tsx`

### Step 2.6 — Console.log 정리

- [ ] `frontend/src/components/map/MapContainer.tsx` 수정
  - 5개 `console.log` 제거 (lines 25, 33, 51, 55, 84)
  - 2개 `console.error` 유지 (진짜 에러 핸들링)

**수정 파일**: `MapContainer.tsx`

### Step 2.7 — Kakao Map 타입 선언

- [ ] `frontend/src/types/kakao.maps.d.ts` 생성
  - `kakao.maps.Map`, `kakao.maps.LatLng`, `kakao.maps.Polygon`, `kakao.maps.event` 타입
- [ ] `MapContainer.tsx` — `window.kakao: any` → 타입 적용, `mapInstanceRef` 타입 지정
- [ ] `DistrictLayer.tsx` — `mapInstance: MutableRefObject<any>` → 타입 적용

**신규 파일**: `kakao.maps.d.ts`
**수정 파일**: `MapContainer.tsx`, `DistrictLayer.tsx`

---

## Phase 3: Scenario Testing

### 테스트 그레이딩 기준

| 등급 | 의미 |
|------|------|
| **fail** | 테스트 실패. 기능 미동작, 에러 발생, 데이터 누락 |
| **normal** | 기능적으로 동작하나 품질 이슈 존재 (느린 응답, 불완전한 데이터, 리팩토링 패턴 미적용) |
| **perfect** | 테스트 통과 + UX 원활 + 리팩토링 패턴 완전 적용 + 콘솔 에러 없음 |

**완료 조건: 모든 시나리오 perfect일 때만 완료**

### Group R — 리팩토링 검증 (정적 분석 + 유닛 테스트)

| ID | 시나리오 | 검증 방법 | fail | normal | perfect |
|----|----------|-----------|------|--------|---------|
| R1 | SSE Parser 모듈 독립 | `sseParser.test.ts` 유닛 테스트 | 모듈 미존재 또는 파싱 실패 | 존재하나 엣지케이스 미처리 | 모든 엣지케이스(빈줄, 불량JSON, 버퍼잔여) 통과 |
| R2 | Event Handler Registry | `eventHandlers.test.ts` 유닛 테스트 | 파일 미존재 또는 핸들러 누락 | 일부 핸들러만 등록 | 9개 핸들러 전부 등록, 개별 테스트 통과 |
| R3 | chatStore 슬림화 | grep 확인 | switch문 여전히 존재 | SSE 파싱 제거되었으나 handleSSEEvent 인라인 | switch/SSE파싱 없음, 130줄 이하 |
| R4 | Card Registry 패턴 | grep 확인 | ternary chain 여전히 존재 | registry 있으나 일부 ternary 잔존 | ternary 없음, registry로만 dispatch |
| R5 | SSEEvent Union 타입 | `tsc --noEmit` | `[key: string]: unknown` 잔존 | union 있으나 catch-all도 잔존 | clean union, `as string` 캐스트 제거 |
| R6 | Kakao Map 타입 | grep `any` 확인 | `kakao.maps.d.ts` 미존재 | 타입 있으나 불완전 | Map/LatLng/Polygon/event 타입 완비 |
| R7 | console.log 제거 | grep 확인 | console.log 잔존 | 일부 제거 | 0개 console.log (console.error만 유지) |
| R8 | Repository 패턴 적용 | grep `settings.use_mock` in tools | tool 파일에 use_mock 잔존 | 일부 tool만 전환 | tool/route에 use_mock 없음 (district_summary의 "(샘플)" 1건만 허용) |
| R9 | Agent 싱글턴 | 서버 로그 확인 | 매 요청 create_agent 호출 | 싱글턴이나 에러 처리 미흡 | lifespan에서 1회 생성, run_agent에서 get_agent 사용 |
| R10 | CORS 환경변수화 | config.py + main.py 확인 | 하드코딩 잔존 | 환경변수 있으나 기본값 미설정 | settings.cors_origins 사용, 기본값 localhost:3000 |
| R11 | 동적 Suggestion | API 응답 확인 | 하드코딩 suggestion | 일부만 district_name 포함 | 선택된 상권명이 suggestion에 반영 |

### Group E — E2E 회귀 테스트 (기존 Playwright specs)

| ID | 시나리오 | 기존 스펙 | fail | normal | perfect |
|----|----------|-----------|------|--------|---------|
| E1 | 폴리곤 → SummaryCard | feature1-polygon-summary.spec.ts | 테스트 실패 | 통과하나 flaky | 3개 테스트 전부 안정 통과 |
| E2 | 컨텍스트 유지 | feature2-context-retention.spec.ts | 실패 | 가끔 컨텍스트 유실 | 4개 테스트 전부 안정 통과 |
| E3 | 양방향 동기화 | feature3-bidirectional-sync.spec.ts | 실패 | 중복 쿼리 발생 | 5개 테스트 전부 안정 통과 |
| E4 | Progress Indicator | feature4-progress-indicator.spec.ts | 실패 | 라벨 불일치 | 6개 테스트 전부 안정 통과 |
| E5 | Card 렌더링 (4종) | feature5-card-rendering.spec.ts | 실패 | 일부 카드 렌더링 이상 | 5개 테스트 전부 안정 통과 |
| E6 | SSE 스트리밍 UX | feature6-streaming-ux.spec.ts | 실패 | 스트리밍 끊김 | 5개 테스트 전부 안정 통과 |
| E7 | 에러 핸들링 | feature7-error-handling.spec.ts | 실패 | 에러 표시되나 복구 안됨 | 4개 테스트 전부 안정 통과 |

### Group F — 기능 심층 테스트 (신규 테스트)

| ID | 시나리오 | 검증 내용 | fail | normal | perfect |
|----|----------|-----------|------|--------|---------|
| F1 | Summary E2E (Mock) | "강남역 분석해줘" → SummaryCard + 차트 + 유동인구 + Top업종 + 폐업률 | 카드 미렌더링 | 카드 렌더링하나 섹션 누락 | 모든 섹션 정상, mock 데이터 값 정확 |
| F2 | Compare E2E | "강남역이랑 홍대 비교해줘" → CompareCard + 비교표 | 카드 미렌더링 | 카드 있으나 지표 누락 | 전체 비교표 + AI 요약 + winner 표시 |
| F3 | Recommend E2E | "여기서 뭐하면 좋을까?" → RecommendCard Top 5 | 카드 미렌더링 | 카드 있으나 추천 불완전 | Top 5 + 점수바 + 근거 + 면책 |
| F4 | Risk E2E | "이 자리 위험해?" → RiskCard | 카드 미렌더링 | 카드 있으나 게이지 누락 | 안정성 게이지 + 생존 바 + 위험 업종 + 추이 |
| F5 | SSE 이벤트 시퀀스 | thinking→tool→tool_end→(card)→text→suggestion→done 순서 검증 | 이벤트 누락 | 순서 불일치 | 정확한 순서로 모든 이벤트 수신 |
| F6 | 지도↔채팅 동기화 | "홍대 보여줘" → map_cmd → 지도 이동 + StatusBar 업데이트 | 지도 미이동 | 이동하나 StatusBar 미갱신 | 지도 이동 + StatusBar + 컨텍스트 설정 |
| F7 | 에러 복구 | API 500 → 에러 메시지 → 재시도 성공 | 크래시 또는 영구 에러 | 에러 표시되나 입력 비활성 | 에러 표시 → 완전 복구 → 다음 쿼리 성공 |
| F8 | Card Registry 확장성 | CARD_REGISTRY에 더미 엔트리 추가 → MessageBubble 코드 수정 불필요 확인 | registry 패턴 미사용 | registry 사용하나 fallback 없음 | registry + unknown type fallback |

### Group P — 품질/성능 테스트

| ID | 시나리오 | 검증 방법 | fail | normal | perfect |
|----|----------|-----------|------|--------|---------|
| P1 | 첫 토큰 지연 | Playwright timing 측정 | >10초 | 2~5초 | <2초 |
| P2 | 콘솔 에러 없음 | `page.on('console')` 감시 | console.error 존재 | console.warn 존재 | error/warn 0건 |
| P3 | TypeScript 컴파일 | `npx tsc --noEmit` | 타입 에러 존재 | 경고만 존재 | 에러/경고 0건 |
| P4 | 빌드 성공 | `npm run build` | 빌드 실패 | 경고와 함께 성공 | 클린 빌드 |

### 테스트 실행 워크플로

```
1. 리팩토링 전 기존 E2E baseline 기록 (npx playwright test)
2. Phase 1 (Backend) 구현
3. Phase 2 (Frontend) 구현
4. 독립 subagent 세션으로 전체 시나리오 평가:

   [Subagent Phase A] 정적 분석 (R1-R11)
     - grep, tsc --noEmit, 코드 구조 확인

   [Subagent Phase B] 유닛 테스트
     - sseParser.test.ts, eventHandlers.test.ts 실행

   [Subagent Phase C] E2E 회귀 (E1-E7)
     - 서버 + 프론트 기동
     - npx playwright test (기존 7 specs)

   [Subagent Phase D] 기능 심층 (F1-F8)
     - 신규 refactoring-verification.spec.ts 실행
     - 백엔드 SSE 시퀀스 테스트

   [Subagent Phase E] 품질 (P1-P4)
     - 성능 측정, 빌드, 타입 체크

5. 그레이딩 리포트 생성
6. fail/normal 항목 수정 → 해당 항목만 재평가
7. 전체 perfect → 종료
```

### 테스트 파일 생성 목록

| 파일 | 용도 | 커버 시나리오 |
|------|------|---------------|
| `frontend/src/lib/__tests__/sseParser.test.ts` | SSE 파서 유닛테스트 | R1 |
| `frontend/src/lib/__tests__/eventHandlers.test.ts` | 이벤트 핸들러 유닛테스트 | R2 |
| `frontend/e2e/refactoring-verification.spec.ts` | 리팩토링 전용 E2E | F1-F8, R8, R11 |
| `scripts/verify-refactoring.sh` | 정적 분석 스크립트 | R3-R7, R10 |
| `server/tests/test_sse_events.py` | SSE 이벤트 시퀀스 | F5 |
| `server/tests/test_repositories.py` | Repository Mock/Real shape 일치 검증 | R8 |

---

## 전체 구현 순서 및 체크리스트

| # | 단계 | 신규 파일 | 수정 파일 | 위험도 |
|---|------|-----------|-----------|--------|
| 1.1 | Repository Protocol + DataAccess | 3 | 0 | 낮음 |
| 1.2 | Mock Repository | 9 | 0 | 낮음 |
| 1.3 | Real Repository | 9 | 0 | 낮음 |
| 1.4 | CacheService 분리 | 0 | 1 | 중간 |
| 1.5 | Lifespan + Agent 싱글턴 + CORS | 0 | 4 | 중간 |
| 1.6 | Tool 함수 위임 전환 | 0 | 8 | 높음 |
| 1.7 | Route 핸들러 위임 전환 | 0 | 4 | 높음 |
| 1.8 | 세션 스토리지 캐시 전환 | 0 | 1 | 낮음 |
| 1.9 | 시스템 프롬프트 + Suggestion | 0 | 2 | 낮음 |
| 1.10 | 캐시 무효화 | 0 | 1~2 | 낮음 |
| 2.1 | SSEEvent Union 타입 | 0 | 1 | 낮음 |
| 2.2 | SSE Parser 추출 | 1 | 0 | 낮음 |
| 2.3 | Event Handler Registry | 1 | 0 | 낮음 |
| 2.4 | chatStore 슬림화 | 0 | 1 | 중간 |
| 2.5 | Card Registry | 1 | 1 | 낮음 |
| 2.6 | console.log 정리 | 0 | 1 | 낮음 |
| 2.7 | Kakao Map 타입 | 1 | 2 | 낮음 |
| 3 | 시나리오 테스트 실행 | 6 | 0 | — |

**총계**: 신규 ~31개 파일, 수정 ~27개 파일 (대부분 축소/단순화)

---

## 핵심 파일 목록

### Backend 핵심
- `server/server/repositories/protocols.py` — 7개 Repository Protocol 정의 (전체 아키텍처 계약)
- `server/server/main.py` — lifespan 컨텍스트 매니저 (Mock/Real 결정의 단일 지점)
- `server/server/agent/graph.py` — Agent 싱글턴 + tool 래퍼
- `server/server/services/cache.py` — MemoryCacheService / RedisCacheService 분리
- `server/server/agent/tools/mock_data.py` — Mock 데이터 원본 (수정 없음, 참조만)

### Frontend 핵심
- `frontend/src/lib/types.ts` — SSEEvent discriminated union (선행 작업)
- `frontend/src/stores/chatStore.ts` — sendMessage 분해 대상
- `frontend/src/components/chat/MessageBubble.tsx` — Card registry 적용 대상
- `frontend/e2e/helpers/setup.ts` — 기존 테스트 헬퍼 (재사용)
