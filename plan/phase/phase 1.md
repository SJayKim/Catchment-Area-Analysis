# Phase 1 완료 보고서 — MarketScope AI

> **기준일:** 2026-03-21
> **원본 계획:** `document/commercial_district_agent_plan.md` (Phase 0 + Phase 1)
> **범위:** 기반 구축 → 핵심 에이전트 MVP → 데이터 파이프라인

---

## 요약

초기 계획서의 Phase 0(기반 구축) + Phase 1(핵심 에이전트 MVP)에 해당하는 작업이 완료되었으며, 일부 Phase 2 영역(데이터 파이프라인)까지 선행 구현되었다.

| 영역 | 계획서 Phase | 상태 | 비고 |
|------|-------------|------|------|
| 프로젝트 기반 | Phase 0 | ✅ 완료 | FastAPI, LangGraph, LiteLLM, Docker Compose |
| DB 스키마·ORM | Phase 0 | ✅ 완료 | PostgreSQL+PostGIS, 10 테이블, Alembic |
| 핵심 에이전트 (7종) | Phase 1 | ✅ 완료 | Commander + 4 분석 + 2 리포트 |
| LangGraph 오케스트레이션 | Phase 1 | ✅ 완료 | DAG, 병렬 그룹, 조건 분기 |
| MCP 서버 (2종) | Phase 1 | ✅ 완료 | Maps 7도구 + Public Data 8도구 |
| REST API + SSE | Phase 1 | ✅ 완료 | POST/GET/Stream, 202 Accepted |
| 데이터 수집기 (3종) | Phase 2 선행 | ✅ 완료 | Seoul + KOSIS + SEMAS |
| 전처리기 (4종) | Phase 2 선행 | ✅ 완료 | 좌표변환, 코드매핑, 결측치, 이상치 |
| 캐시·스케줄러·모니터링 | Phase 2 선행 | ✅ 완료 | Redis, APScheduler 8작업, 품질체크 |
| MCP 멀티서버 라우팅 | Phase 1 필수 | ❌ 미완 | 단일 URL 구조 (BLOCKER) |
| Debate 시스템 | Phase 1 계획 | ❌ 미착수 | Advocate + Critic + Judge 미구현 |
| 프론트엔드 | Phase 3 | ❌ 미착수 | frontend/ 디렉토리 없음 |

---

## 1. 프로젝트 기반 (Phase 0)

### 1-1. 프로젝트 구조 ✅

```
marketscope/
├── app/
│   ├── agents/          # 7개 에이전트 + BaseAgent
│   ├── api/routes/      # analysis, health
│   ├── cache/           # Redis 캐시 클라이언트
│   ├── collectors/      # Seoul, KOSIS, SEMAS 수집기
│   ├── config.py        # Pydantic Settings (전체 설정)
│   ├── db/              # ORM, Repository, Session
│   ├── graph/           # LangGraph workflow, nodes, edges
│   ├── llm/             # LiteLLM provider 추상화
│   ├── mcp_servers/
│   │   ├── maps/        # 카카오 지도 MCP (port 5101)
│   │   └── public_data/ # 공공데이터 MCP (port 5100)
│   ├── monitoring/      # 품질 체크
│   ├── preprocessors/   # 좌표변환, 코드매핑, 결측치, 이상치
│   ├── scheduler/       # APScheduler 배치 작업
│   └── tools/           # MCPClient
├── alembic/             # DB 마이그레이션
├── scripts/             # 시드 스크립트
├── docker-compose.yml   # PostgreSQL 15 + Redis 7
├── pyproject.toml       # 의존성 관리
└── .env                 # API 키 설정
```

### 1-2. 인프라 ✅

| 구성요소 | 설정 |
|---------|------|
| FastAPI | 0.115+, CORS, lifespan, 2 라우터 |
| PostgreSQL 15 + PostGIS 3.4 | docker-compose, healthcheck |
| Redis 7 | docker-compose, 캐시 TTL 3600s |
| SQLAlchemy 2.0 async | asyncpg, 커넥션 풀(20/10) |
| Alembic | async 모드, 초기 마이그레이션 작성 완료 |

### 1-3. LLM 통합 ✅

| 항목 | 상세 |
|------|------|
| Provider 추상화 | `LLMProvider` Protocol + `LiteLLMProvider` 구현 |
| 모델 배치 | 전 에이전트 `gemini/gemini-2.5-flash` 통일 (비용 최적화) |
| 설정 | 에이전트별 모델 교체 가능 (`LLM_MODEL_*` 환경변수) |
| Temperature | 분석 0.1 / 내러티브 0.7 / 기본 0.2 |
| Fallback | LiteLLM 내장 폴백 + 3회 재시도 |

### 1-4. API 키 현황

| API 키 | 상태 | 용도 |
|--------|------|------|
| `GOOGLE_API_KEY` | ✅ 설정됨 | Gemini LLM |
| `DATA_API_KAKAO_REST_KEY` | ✅ 설정됨 | 카카오 지도 |
| `DATA_API_SEOUL_OPEN_DATA_KEY` | ✅ 설정됨 | 서울 열린데이터 |
| `DATA_API_KOSIS_KEY` | ✅ 설정됨 | 통계청 |
| `ANTHROPIC_API_KEY` | ❌ 미설정 | Claude (현재 Gemini 통일) |
| `DATA_API_PUBLIC_DATA_KEY` | ❌ 미설정 | SEMAS (data.go.kr) |
| `DATA_API_SMALL_BIZ_KEY` | ❌ 미설정 | 소상공인진흥공단 |

---

## 2. 에이전트 시스템 (Phase 1)

### 2-1. BaseAgent 프레임워크 ✅

`BaseAgent[T]` — 제네릭 추상 클래스

- `call_llm()`: 3계층 JSON 파싱 (블록 → 전문 → 중괄호 추출)
- `call_tool()`: MCPClient 연동, 재시도 2회 + 지수 백오프
- 구조화 출력: Pydantic 모델 자동 파싱
- 에이전트 로거 자동 구성

### 2-2. 에이전트 구현 현황 ✅

| 에이전트 | 파일 | LOC | 기능 | MCP 도구 |
|---------|------|-----|------|---------|
| Commander | `commander.py` | ~310 | 계획 수립 + 최종 판단 (이중 모드) | 없음 (LLM only) |
| Population | `population.py` | ~170 | 유동/거주/직장 인구 분석 | `maps.geocode`, `public_data.*population` |
| Revenue | `revenue.py` | ~160 | 매출 규모·트렌드·업종별 분석 | `maps.geocode`, `public_data.*revenue` |
| Competition | `competition.py` | ~180 | 점포 수·포화도·개폐업률 | `maps.geocode`, `public_data.get_store_*` |
| Location | `location.py` | ~180 | 접근성·교통·POI·가시성 | `maps.geocode`, `maps.get_transit_nearby`, `maps.search_nearby` |
| Narrative | `narrative.py` | ~80 | 경영진 요약 텍스트 생성 | 없음 |
| Visualization | `visualization.py` | ~80 | 차트 설정 JSON 생성 | 없음 |

### 2-3. LangGraph DAG ✅

```
START → commander_plan
     ↓ (조건: should_continue_after_commander)
     ├─→ [population, competition]  (Group 1 — 병렬)
     │     ↓
     │   group1_complete (배리어)
     │     ↓ (조건: should_run_group2)
     │     ├─→ [revenue, location]  (Group 2 — 병렬)
     │     │     ↓
     │     │   group2_complete (배리어)
     │     │     ↓
     │     └─→ commander_judgment (Group 2 스킵: quick 모드)
     └─→ END (clarification_needed)

commander_judgment
     ↓ (조건: should_skip_reports)
     ├─→ narrative → visualization → report_assembly
     └─→ report_assembly (에러 시 최소 리포트)
          ↓
         END
```

- 노드 11개, 조건 분기 4개
- `MemorySaver` 체크포인팅 (개발 모드)
- `_get_mcp_client()` 싱글턴 팩토리 패턴

### 2-4. REST API ✅

| 엔드포인트 | 메서드 | 기능 |
|-----------|--------|------|
| `/api/v1/analysis/` | POST | 분석 요청 → 202 Accepted + stream URL |
| `/api/v1/analysis/{id}` | GET | 분석 결과 조회 |
| `/api/v1/analysis/{id}/stream` | GET(SSE) | 실시간 진행 스트리밍 (15초 하트비트) |
| `/api/v1/health` | GET | 서버 상태 |

---

## 3. MCP 서버 (Phase 1)

### 3-1. Maps MCP Server (port 5101) ✅

7개 도구 — 카카오 로컬 API 기반:

| # | 도구명 | 기능 |
|---|--------|------|
| 1 | `maps.geocode` | 주소 → 좌표 |
| 2 | `maps.reverse_geocode` | 좌표 → 주소 |
| 3 | `maps.search_nearby` | 반경 내 장소 검색 |
| 4 | `maps.search_keyword` | 키워드 장소 검색 |
| 5 | `maps.get_walking_route` | 도보 경로 |
| 6 | `maps.get_transit_nearby` | 주변 대중교통 |
| 7 | `maps.get_category_pois` | 카테고리별 POI |

### 3-2. Public Data MCP Server (port 5100) ✅

8개 도구 + 3개 리소스:

| # | 도구명 | 데이터 소스 |
|---|--------|-----------|
| 1 | `public_data.get_floating_population` | SEMAS (분기별) |
| 2 | `public_data.get_estimated_revenue` | SEMAS (분기별) |
| 3 | `public_data.get_store_list` | SEMAS (반경 기반) |
| 4 | `public_data.get_store_count_change` | SEMAS (분기 비교) |
| 5 | `public_data.get_resident_population` | KOSIS |
| 6 | `public_data.get_worker_population` | KOSIS |
| 7 | `public_data.get_seoul_living_population` | 서울 열린데이터 |
| 8 | `public_data.get_card_sales` | 서울 열린데이터 |

리소스: `industry-codes`, `district-codes`, `dong-codes`

### 3-3. MCP Client ⚠️ (라우팅 미완)

- `MCPClient` — httpx 비동기 클라이언트
- 재시도: 3회, 지수 백오프, 502/503/504 재시도
- **문제점:** `base_url = "http://localhost:5100"` 단일 URL 하드코딩
  → `maps.*` 도구 호출 시 5101이 아닌 5100으로 전달됨

---

## 4. 데이터 파이프라인 (Phase 2 선행)

### 4-1. DB 스키마 (D0) ✅

10개 ORM 모델 + Alembic 초기 마이그레이션:

| 테이블 | 주요 필드 | 특이사항 |
|--------|----------|---------|
| `districts` | code, name, boundary(POLYGON) | PostGIS GIST 인덱스 |
| `population_stats` | 30+ 컬럼 (연령/시간/요일) | UNIQUE(district_id, stat_type, period) |
| `revenue_stats` | 업종별 매출/건수 | UNIQUE(district_id, industry_code, period) |
| `stores` | 위치(POINT), 업종, 상태 | PostGIS 공간 인덱스 |
| `transit_stats` | 승하차/노선 | 역별 시계열 |
| `code_mappings` | 행정동↔법정동↔업종 | UNIQUE(type, code) |
| `unit_prices` | 업종별 객단가 | 상권등급별 |
| `startup_costs` | 초기투자비 | 업종×면적별 |
| `analysis_sessions` | 분석 이력 | 결과 JSONB |
| `collection_logs` | 수집 감사 로그 | source, status, records |

Repository 패턴: `BaseRepository[T]` + 전문 레포지토리 6종

### 4-2. Collector (D1) ✅

| 수집기 | 파일 | 대상 API | LOC |
|--------|------|---------|-----|
| BaseCollector | `base.py` | (추상) | ~170 |
| SeoulCollector | `seoul.py` | 서울 열린데이터 3종 | ~300 |
| KosisCollector | `kosis.py` | 통계청 KOSIS | ~140 |
| SemasCollector | `semas.py` | 소상공인진흥공단 4종 | ~335 |

공통: 3회 재시도, Rate Limit(429) 처리, collection_logs 기록

### 4-3. Preprocessor (D2) ✅

| 전처리기 | 기능 |
|---------|------|
| `coordinate_transformer.py` | TM/UTM-K/KATEC → WGS84, 서울 범위 검증 |
| `code_mapper.py` | 인메모리 코드 매핑 캐시, 행정동→상권 변환 |
| `missing_handler.py` | Forward fill, 균등 분배, 인구 기본값 |
| `outlier_detector.py` | IQR, 시계열, 변동률 이상치 감지 |

### 4-4. 캐시·스케줄러·모니터링 (D5) ✅

| 구성요소 | 파일 | 기능 |
|---------|------|------|
| Redis 캐시 | `cache/redis_client.py` | `cached_call()`, 키 패턴 `{server}:{tool}:{hash}` |
| APScheduler | `scheduler/jobs.py` | 8개 배치 작업 (분기/월/일 주기) |
| 품질 체크 | `monitoring/quality_checker.py` | Freshness/Completeness/Anomaly/무결성 |

---

## 5. 미완료·미착수 항목

### 5-1. BLOCKER: MCP 멀티서버 라우팅

`config.py`에 `mcp_server_url` 하나만 존재 → Maps 서버 (5101) 도달 불가.
에이전트가 `maps.*` 도구를 호출해도 public_data 서버(5100)로 전달됨.

### 5-2. Debate 시스템 (계획서 Phase 1 범위)

초기 계획서에서 Phase 1 Week 5에 배치했으나 미구현:
- Advocate Agent (긍정 관점, Gemini 2.5 Pro)
- Critic Agent (비판 관점, Claude Sonnet)
- Judge Agent (최종 판정, Opus/Commander)
- 선택적 트리거 조건 (신뢰도 < 0.6, 에이전트 결론 충돌 등)

### 5-3. 프론트엔드

계획서 Phase 3 범위. `frontend/` 디렉토리 미생성.

### 5-4. 통합 검증

- DB 실가동 미확인 (Docker 환경 미실행)
- E2E 테스트 미실행 (Agent → MCP → API → 응답)
- 실제 API 호출 검증 미실시

---

## 6. 코드 통계

| 영역 | 파일 수 | 총 LOC |
|------|--------|--------|
| agents/ | 8 | ~1,400 |
| graph/ | 4 | ~350 |
| api/ | 3 | ~250 |
| llm/ | 2 | ~130 |
| mcp_servers/ | 8 | ~1,000 |
| db/ | 3 | ~720 |
| collectors/ | 4 | ~950 |
| preprocessors/ | 4 | ~530 |
| cache+scheduler+monitoring | 3 | ~720 |
| tools/ | 1 | ~190 |
| config+main+logging | 3 | ~400 |
| alembic+scripts | 2 | ~510 |
| **합계** | **~45** | **~7,150** |
