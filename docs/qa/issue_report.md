# 전체 프로젝트 품질 평가 리포트 (Issue Report)

> **평가일**: 2026-04-06
> **범위**: Backend Python + Frontend TypeScript + Agent/LLM + Data/Infra + Tests + Security
> **방법**: 6개 병렬 Explore Sub-Agent (Opus/Sonnet)로 영역별 감사 수행
> **전체 LOC**: Backend ~2,500 / Frontend ~3,700 / Agent ~1,800

---

## 종합 등급: **B- (6.8/10)**

| 영역 | 등급 | 점수 | 핵심 이슈 |
|------|------|-----:|-----------|
| **아키텍처** | A- | 8.5 | PAE 패턴, Repository 분리, Tool Registry 잘 설계됨 |
| **안정성** | C+ | 5.5 | LLM 타임아웃 없음, SSE 리소스 누수, race condition |
| **코드 컨벤션** | B+ | 7.5 | strict mode, 타입힌트 양호. `any` 일부, 도크스트링 부족 |
| **효율성** | B | 7.0 | N+1 쿼리, 불필요한 리렌더, 캐시 TTL 일괄 적용 |
| **테스트** | D | 4.0 | Unit 0건, Integration 0건, E2E만 9개 |
| **보안** | B- | 6.5 | Rate limiting 부족, 세션 메모리, 프롬프트 방어 약함 |
| **인프라** | B | 7.0 | Docker 양호, non-root 미적용, 헬스체크 불완전 |

---

## P0 — Critical (즉시 수정 필요, 8건)

### 1. `category_metadata.aliases` 컬럼 마이그레이션 누락 ⚠️ 자체 도입
- **위치**: `server/alembic/versions/` (001, 002만 존재, 003 없음)
- **원인**: Step 3 (하드코딩 개선)에서 `aliases` 컬럼을 모델에 추가했으나 마이그레이션 미생성
- **영향**: `USE_MOCK=false` 전환 시 `CategoryResolver.load_from_db()` 호출에서 컬럼 없음 에러
- **조치**: `003_add_category_aliases.py` 마이그레이션 생성
  ```python
  def upgrade():
      op.add_column("category_metadata",
          sa.Column("aliases", sa.String(500), nullable=True))
  def downgrade():
      op.drop_column("category_metadata", "aliases")
  ```

### 2. LLM 호출 타임아웃 부재
- **위치**: `agent/nodes/planner.py:84`, `evaluator.py:86`, `respond.py:146`
- **문제**: `llm.ainvoke()` 무한 대기 가능 → 전체 그래프 hang
- **영향**: 단일 느린 요청이 서버 스레드 블로킹
- **조치**: `asyncio.wait_for(..., timeout=10.0)` 래핑

### 3. SSE 이벤트 큐 무제한 + 블로킹 리스크
- **위치**: `agent/graph.py:424` — `asyncio.Queue()` (maxsize=0)
- **문제**: 클라이언트 연결 종료 시 consumer 사라짐 → producer `put()` 블로킹 또는 메모리 증가
- **조치**: `Queue(maxsize=100)` + consumer 측 timeout

### 4. ReAct 모드 Task 취소 누락 (chat 라우트)
- **위치**: `api/routes/chat.py` event_generator
- **문제**: 클라이언트 disconnect 시 `run_agent()` 태스크가 백그라운드에서 계속 실행
- **영향**: 리소스 누수, 세마포어 슬롯 해제 지연
- **조치**: `asyncio.create_task()` + `finally: task.cancel()`

### 5. LLM JSON 응답 파싱 실패 처리 미흡
- **위치**: `agent/nodes/planner.py:92-100`, `evaluator.py:94-102`
- **문제**: LLM이 손상된 JSON 반환 시 `json.loads()` 실패 → 하드코드 fallback "summary"
- **영향**: 위험 분석 요청에 요약 카드 응답되는 UX 버그
- **조치**: rule-based fallback 재사용, 오류 원인 로깅

### 6. DistrictLayer Stale Closure
- **위치**: `frontend/src/components/map/DistrictLayer.tsx:45-64`
- **문제**: 폴리곤 hover/click 리스너가 `selectedCode`의 옛값 캡처
- **영향**: 빠른 폴리곤 전환 시 hover 스타일 꼬임
- **조치**: `useRef`로 최신값 참조 or 의존성 변경 시 폴리곤 재등록

### 7. SSE Reader 해제 누락
- **위치**: `frontend/src/stores/chatStore.ts:172-174`
- **문제**: `reader.cancel()` finally에서 누락 → 네트워크 중단 시 리소스 누수
- **조치**: `try/finally { reader?.cancel() }`

### 8. 프롬프트 인젝션 취약 (sanitize 약함)
- **위치**: `agent/prompts/system.py:71-73`
- **문제**: `{`, `}`만 제거. `\n`, 특수 토큰 방어 없음
- **조치**: `json.dumps()` 기반 escape + 길이 제한

---

## P1 — High (1주 이내, 25건)

### Backend (8건)

| ID | 위치 | 이슈 |
|----|------|------|
| P1-B1 | `chat.py:39-45` | Session pruning race condition — lock 외부 시간 체크 |
| P1-B2 | `real/comparison.py:28-144` | N+1 Query: 2~3 상권 × 7개 쿼리 순차 실행 (14~21 roundtrip) |
| P1-B3 | `real/floating_population.py` 등 | Repository 예외 처리 불일치 (try/except 없음) |
| P1-B4 | `real/districts.py:216` | ST_Intersects bounds lat/lng 범위 검증 부족 (DoS 리스크) |
| P1-B5 | `chat.py:100-135` | District 중복 조회 — 동일 code를 두 번 쿼리 |
| P1-B6 | `chat.py:25-31` | 전역 mutable state `_sessions`, `_last_prune_time` 캡슐화 필요 |
| P1-B7 | `server/Dockerfile`, `frontend/Dockerfile` | Non-root user 미적용 |
| P1-B8 | `chat.py:31` | Rate limit 부재 — asyncio.Semaphore만 존재, per-IP/per-user 없음 |

### Frontend (7건)

| ID | 위치 | 이슈 |
|----|------|------|
| P1-F1 | `DistrictLayer`, `MapContainer`, `HeatmapLayer`, `api.ts` | `any` 타입 다수 |
| P1-F2 | `api.ts:62` | Fallback center `(0,0)` — 태평양 좌표 → 서울 중심으로 변경 |
| P1-F3 | `useMapSync.ts` | 폴리곤 연속 클릭 시 쿼리 중첩, 최신값만 유지 로직 필요 |
| P1-F4 | `MapContainer.tsx` | Error Boundary 부재 — SDK 로드 실패 시 복구 없음 |
| P1-F5 | Card 컴포넌트 전체 | `React.memo` 미적용 |
| P1-F6 | `useReportExport.ts` | PDF 생성 에러 사용자 피드백 없음 |
| P1-F7 | `ChatInput.tsx` | 길이 제한, XSS 기본 방어 필요 |

### Agent (5건)

| ID | 위치 | 이슈 |
|----|------|------|
| P1-A1 | `system.py` vs `respond.py:RESPOND_SYSTEM_PROMPT` | System 프롬프트 ReAct/PAE 이중 유지 |
| P1-A2 | `actor.py:37-42` | Circular dependency silent — 경고 없이 실행 |
| P1-A3 | Tool 파일 전체 | Tool 반환 규약 불일치 (일부 try/except, 일부 raw) |
| P1-A4 | `actor.py:45` | `plan.index(step)` O(n²) dependency lookup |
| P1-A5 | `prompts/evaluator.py` | Evaluator 출력 포맷 모호 — `missing_info` 타입 array 명시 없음 |

### Data/ETL (3건)

| ID | 위치 | 이슈 |
|----|------|------|
| P1-D1 | `data/etl/seoul_opendata.py` | Rate limit 429 처리 부재 — backoff 없음 |
| P1-D2 | `data/etl/loader.py` | Transaction rollback 누락 — batch 실패 시 partial commit |
| P1-D3 | `services/cache.py` | Cache key 포맷 문서화 부재 — 충돌 리스크 |

### Tests (2건)

| ID | 위치 | 이슈 |
|----|------|------|
| P1-T1 | Backend/Frontend 전체 | Unit 테스트 0건 — E2E만 9개 존재 |
| P1-T2 | `e2e/helpers/setup.ts` | Flaky 패턴 — `waitForTimeout(800~2000ms)` 의존, `waitFor` 조건 미사용 |

---

## P2 — Medium (2주 이내, 14건)

| ID | 위치 | 이슈 |
|----|------|------|
| P2-01 | `services/cache.py:MemoryCacheService` | TTL 무시 — mock 모드에서 영원히 캐시 |
| P2-02 | `services/cache.py` | TTL 일괄 86400 하드코딩 — key별 차등 필요 |
| P2-03 | `api/routes/chat.py(229)`, `ReportDocument.tsx(206)`, `Toolbar.tsx(198)` | 대용량 파일 분리 필요 |
| P2-04 | `repositories/mock/districts.py` | Mock vs Real 드리프트 — `bounds` 파라미터 무시 |
| P2-05 | `real/districts.py:174`, `real/heatmap.py:33-34` | `ST_AsGeoJSON` DB측 변환 오버헤드 |
| P2-06 | `config.py:30-31` | API key 빈 문자열 default → 시작 시 검증 없음 |
| P2-07 | `server/pyproject.toml` | 의존성 `>=` (minor 깨짐 가능) |
| P2-08 | `docker-compose.yml:45` | `|| true` seed 에러 마스킹 |
| P2-09 | `config.py:57-58` | `db_pool_size=10` F05 비교 시 부족 가능 |
| P2-10 | `respond.py:60-61` | 응답 JSON 2000자 단순 truncate → JSON 깨짐 |
| P2-11 | `agent/history.py:28-31` | `conversation_history` 300자 말단 truncate → 리스트 손실 |
| P2-12 | `MessageBubble.tsx:32` | `ChatMessage.cardData as any` 타입 우회 |
| P2-13 | `next.config.mjs` | env loading 이중화 (`.env` vs `.env.local`) |
| P2-14 | `server/pyproject.toml:58` | Ruff config deprecated 문법 (`select` → `lint.select`) |

---

## P3 — Low (후순위, 7건)

- 테이블 naming 일관성 (일부 singular/plural 혼용)
- `column` naming — `age_10_sales` 모호 (10대? 10만원?)
- CSV 경로 하드코딩 (`data/csv/OA-15584.csv`)
- 대용량 JSON 압축 부재
- Legacy singleton `cache_service = MemoryCacheService()` 미사용
- `__all__` 미정의 `__init__.py`
- Security headers 부재 (X-Content-Type-Options, CSP)

---

## 오탐 정정 (Sub-Agent가 잘못 리포트한 것)

### ❌ "API 키가 git history에 노출됨" — **사실 아님**

**Agent 주장**: `.env` 파일이 git history에 커밋되어 API 키 노출됨

**실제 검증 결과**:
- `git ls-files | grep .env` → 빈 결과 (트래킹 안 됨)
- `git log -S "sk-ant" --all` → 커밋 없음
- history의 `sk-ant-*` 매치는 모두 문서의 플레이스홀더 (`sk-ant-xxxx`, `sk-ant-실제키입력`)
- `.env`는 `.gitignore`에 포함되어 안전
- 백그라운드 grep 결과 소스 코드에 실제 키 없음 (매치는 `mdast-util-gfm-task-list-item` 등 패키지 이름의 `-sk-`)

**원인**: Agent가 로컬의 gitignored `.env` 파일을 읽고 git history에 있다고 오인

### ⚠️ mypy `# type: ignore[arg-type]` 3건
- 위치: `agent/graph.py:215, 224, 432`
- Gemini/Anthropic SDK의 Pydantic `SecretStr` 타입 불일치 문제
- 실제로는 정상 동작, 우선순위 낮음

---

## 강점 (Well-Designed 요소)

1. **깔끔한 아키텍처 분리**
   - Repository 패턴 (Mock/Real 전환)
   - PAE/ReAct 이중 모드
   - Tool Registry 자동 등록 (@register_tool 데코레이터)

2. **타입 안정성 기반**
   - TypeScript `strict: true`
   - Python mypy `strict = true`

3. **Mock-first 전략**
   - DB 없이 E2E 흐름 검증 가능
   - JSON 파일 기반 (최근 개선)

4. **SSE 스트리밍**
   - 정상 경로에서 잘 동작 (thinking → tool → card → text → done)
   - 이벤트 타입별 handler 분리

5. **데이터 출처 citation**
   - Card footer SourcesCitation 재사용 패턴
   - 공공누리 라이선스 준수

6. **하드코딩 개선 (2026-04-06 완료)**
   - Mock JSON, YAML 인텐트, Category DB, Tool Registry, SSE 라벨
   - SSOT (Single Source of Truth) 확보

7. **인프라 기본기**
   - Langfuse (LLM 관찰성)
   - Docker Compose (PostGIS + Redis + Backend + Frontend)
   - Alembic 마이그레이션

---

## 파일별 리스크 랭킹

| 파일 | LOC | P0/P1/P2 | 리스크 | 주요 이슈 |
|------|----:|---------:|--------|-----------|
| `api/routes/chat.py` | 229 | 1/4/2 | **CRITICAL** | Race condition, N+1, global state, task 취소 누락 |
| `agent/graph.py` | 562 | 2/1/1 | **HIGH** | Queue 무제한, 타임아웃 없음, 시스템 프롬프트 이중화 |
| `agent/nodes/planner.py` | 285 | 2/1/0 | **HIGH** | JSON 파싱 실패, 타임아웃 없음, 하드코드 fallback |
| `frontend/components/map/DistrictLayer.tsx` | ~150 | 1/2/0 | **HIGH** | Stale closure, any 타입 |
| `frontend/stores/chatStore.ts` | ~200 | 1/0/0 | **MEDIUM** | Reader leak |
| `agent/nodes/actor.py` | 158 | 0/2/1 | **MEDIUM** | Circular dep silent, O(n²) lookup, timeout per-tool 없음 |
| `agent/nodes/respond.py` | 180 | 1/1/1 | **MEDIUM** | LLM 스트림 예외 미처리, JSON truncate |
| `services/cache.py` | 152 | 0/1/3 | **MEDIUM** | Redis 에러 처리, TTL 무시, 레거시 싱글턴 |
| `real/comparison.py` | ~150 | 0/1/0 | **MEDIUM** | N+1 query (14~21 roundtrip) |
| `models/category.py` | 16 | 1/0/0 | **BLOCKER** | `aliases` 컬럼 마이그레이션 누락 |

---

## 권장 조치 우선순위

### Week 1 — P0 8건 (즉시)

1. ✅ `003_add_category_aliases.py` 마이그레이션 생성 (self-inflicted bug)
2. LLM 호출 전체 타임아웃 적용 (`asyncio.wait_for` wrapper)
3. SSE 이벤트 큐 `maxsize=100` + task 명시적 취소
4. DistrictLayer stale closure 수정 (`useRef` 또는 재등록)
5. chatStore SSE reader cleanup (`try/finally`)
6. JSON 파싱 예외 → rule-based fallback 재사용
7. 프롬프트 sanitize 강화 (`json.dumps` 기반 escape)
8. ReAct mode task 취소 패턴 적용

### Week 2 — P1 핵심 (25건 중 우선)

- `compare_districts` 쿼리 배치화 or JOIN 재작성
- Repository 예외 처리 일원화 (모두 try/except로 error dict 반환)
- bounds geographic 검증 Pydantic BaseModel 도입
- `any` 타입 제거 (DistrictLayer, api.ts 우선)
- Card 컴포넌트 `React.memo`
- Docker non-root user (appuser UID 1000)
- pytest 기반 backend unit 테스트 도입 (Tool + Repository부터)
- System 프롬프트 단일화 (ReAct/PAE 공유)

### Week 3+ — P2 최적화

- Cache TTL 계층화, Mock drift 수정
- 대용량 파일 분리 (`chat.py`, `ReportDocument.tsx`, `Toolbar.tsx`)
- 의존성 정밀 pinning (production), Ruff config 업그레이드
- Frontend Vitest 단위 테스트
- 로깅 구조화 (request_id ContextVar, JSON formatter)
- ST_AsGeoJSON 최적화 (binary geometry + shapely)

---

## 방법론 메모

**감사 수행 방식**:
- 6개 병렬 Explore Sub-Agent 사용
- 각 에이전트는 독립적으로 영역 담당
  1. Backend core (routes, services, config, main)
  2. Frontend (components, stores, hooks, lib)
  3. Agent/LLM (graph, nodes, tools, prompts)
  4. Data/ETL/Infra (repositories, models, alembic, docker)
  5. Testing & Security & Config
  6. (중복 방지용 교차 검증)

**산출물 분량**: ~500KB 감사 원문 → 본 리포트로 요약 정리

---

*작성일: 2026-04-06*
*작성자: Claude Code (Opus 4.6 + 5 Sub-Agents)*
*검증 방법: 일부 P0 findings는 수동 재확인 수행*
