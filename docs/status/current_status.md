# 현재 진행 상황

> 최종 갱신: 2026-04-06
> **P0 Critical 8건 수정 완료 ✅ — Migration 003 / LLM timeout / SSE backpressure / disconnect / JSON fallback / sanitize / stale closure / AbortController**
> **E2E QA 테스트 플랜 작성 완료 ✅ — 4-ring 계층 (pre-flight → feature → journey → P0 regression) + fresh subagent evaluator**

---

## 전략

**Phase 1A(Mock E2E)** → **Phase 1B(Real Data + UX)** → Phase 2(Premium) → Phase 3(확장)

---

## Phase 1A — Mock E2E ✅ 완료

데이터 없이 "지도 클릭 → AI Agent 응답 → Card 렌더링" 전체 흐름 동작 확인

### 구현 완료
- FastAPI + LangGraph ReAct Agent + SSE 스트리밍
- Next.js 14 + Kakao Map + Zustand + Recharts
- Agent Tools 8종 (유동인구, 매출, 점포, 인구, 요약, 비교, 추천, 이력)
- Card UI 4종 (SummaryCard, CompareCard, RecommendCard, RiskCard)
- Mock 데이터 5개 상권 (강남역, 홍대, 건대, 명동, 서울역)
- SplitPanel, Toolbar, StatusBar, SuggestionChips
- Feature 1: 폴리곤 클릭 → 자동 SummaryCard
- Feature 2: 대화 컨텍스트 유지 (세션 기반)
- Feature 3: 양방향 채팅↔폴리곤 동기화

---

## Phase 1B — Real Data + Streaming UX ✅ 완료 (2026-03-30)

### Step 1: Agent Progress Indicator ✅
- `AgentProgressIndicator.tsx` — 🧠→🔍→📊→✅ 이모지 실시간 단계 표시
- Tool name → 한국어 라벨 + 이모지 매핑 (8종)
- `graph.py`에 `tool_end` SSE 이벤트 + `icon` 필드 추가
- `chatStore.ts`에 `agentSteps` 상태 관리
- 접기/펼치기 토글 UI
- 텍스트 응답 시작 후 1.5초간 완료 상태 유지 후 fade-out

### Step 2: Streaming Enhancement ✅
- SSE 버퍼링 문제 해결 — Chat API를 Next.js rewrite 대신 직접 백엔드 호출
- `firstTextReceived` 변수 위치 버그 수정
- Tool 없는 직접 응답, 에러 시 step 정리, 다중 tool 순차 처리

### Step 3: Dark Theme + Streaming UX ✅
- **CSS 변수 기반 다크 테마** — `globals.css`에 `:root` 변수 정의 (bg-primary: #0f172a, bot-bubble: #1e293b 등)
- **Streaming 블링킹 커서** — `.streaming::after` CSS 애니메이션
- **react-markdown + remark-gfm** — AI 응답 마크다운 렌더링
- **메시지 애니메이션** — `animate-msg-in` (fade-in), `animate-step-in` (slide-in)
- **다크 테마 적용 컴포넌트**: ChatPanel, ChatInput, SuggestionChips, Toolbar, MessageBubble, MessageList, AgentProgressIndicator
- **서버 SSE icon 필드** — thinking(🧠), tool(🔍/📋/📊/💡), tool_end 이벤트에 icon 추가
- `tailwind.config.ts`에 `msgIn`/`stepIn` 키프레임 추가
- `layout.tsx` body에 CSS 변수 배경/텍스트 적용

### Step 4: E2E 테스트 ✅ — 32/32 ALL PASSED
- `feature4-progress-indicator.spec.ts` (6개)
- `feature5-card-rendering.spec.ts` (5개)
- `feature6-streaming-ux.spec.ts` (5개)
- `feature7-error-handling.spec.ts` (4개)
- 기존 feature1~3 (12개) 모두 통과

### Step 5: 데이터 파이프라인 ✅
- Docker Compose: PostGIS 16 + Redis 7 기동
- Alembic migration: 9개 테이블 + 인덱스 생성
- 서울 열린데이터 API 연동 (4개 서비스 승인)
- ETL 적재 완료:

| 테이블 | 행 수 | 분기 | 소스 API |
|--------|------:|------|----------|
| districts | 1,650 | 전체 | VwsmTrdarFlpopQq에서 추출 |
| floating_population | 9,888 | 2025Q4 | VwsmTrdarFlpopQq |
| estimated_sales | 21,333 | 2025Q4 | VwsmTrdarSelngQq |
| stores | 75,985 | 2025Q4 | VwsmTrdarStorQq |
| resident_population | 39,288 | 2025Q4 | VwsmTrdarWrcPopltnQq (직장인구) + OA-15584 CSV (상주인구) |

- `USE_MOCK=false` 전환 → 실제 DB 데이터 API 반환 확인
- Redis 연결 확인

### 해결한 버그들 (Phase 1B)
- **SSE 버퍼링**: Next.js rewrite 프록시가 SSE 이벤트를 버퍼링 → Chat API 직접 연결로 해결
- **텍스트 응답 누락**: `firstTextReceived` 변수가 `finally` 뒤에 선언 → `try` 앞으로 이동
- **Progress Indicator 안 보임**: text 이벤트 시 즉시 isThinking=false → agentSteps만으로 표시하도록 변경
- **Progress 너무 빨리 사라짐**: 300ms → 1.5초로 연장
- **ETL 쿼터 필터**: `STDR_YR_CD`/`STDR_QU_CD` 대신 `STDR_YYQU_CD` 사용하도록 통합 필터
- **asyncpg 파라미터 제한**: batch_size 5000 → 1000으로 축소
- **Alembic GiST 인덱스 충돌**: `CREATE INDEX IF NOT EXISTS`로 변경

### 비가용 API (서버 ERROR-500, 키 문제 아님)
- `VwsmTrdarSelngW` (상권 폴리곤) — **SHP 파일로 대체 완료**
- `VwsmTrdarStorW` (점포 상세정보) — VwsmTrdarStorQq 폴백 동작 중
- `VwsmTrdarPopltnQq` (상주인구) — 서버 ERROR-500 지속, **CSV 다운로드 대안 확인 완료** (아래 참조)

### 상주인구 CSV 적재 완료 (2026-04-03)
- **데이터셋**: [OA-15584 서울시 상권분석서비스(상주인구-상권)](https://data.seoul.go.kr/dataList/OA-15584/S/1/datasetView.do)
- **파일**: `data/csv/OA-15584.csv` (40,812행, EUC-KR, 2025Q4 필터 → 19,596행 적재)
- **적재 방법**: `python -m server.data.etl.runner load-csv data/csv/OA-15584.csv 2025Q4`
- **setup_db.py**: `--full` 모드에서 CSV 자동 감지 (`data/csv/OA-15584.csv` 존재 시 `--csv-file` 전달)

---

## 현재 실행 환경

| 서비스 | 포트 | 모드 |
|--------|------|------|
| Next.js 프론트엔드 | 3000 | Real (USE_MOCK=false) |
| FastAPI 백엔드 | 8002 | Real (USE_MOCK=false) |
| PostGIS (Docker) | 5432 | 실데이터 적재 완료 (폴리곤 100%) |
| Redis (Docker) | 6379 | 정상 |

- Mock 모드: 5개 상권 폴리곤 + AI 챗봇 + Card UI 전체 동작 (32/32 E2E PASS)
- **Real 모드**: 1,650개 상권 + 실제 폴리곤 + 유동인구/매출/점포 데이터 전체 동작

---

## 완료 항목 (2026-04-01)

### ✅ Playwright MCP 브라우저 E2E QA (26개 시나리오)
- **결과**: 22 PASS / 4 SOFT FAIL / 0 HARD FAIL
- **그룹 1** (지도/폴리곤/검색): 5/6 PASS
- **그룹 2** (채팅/Card/답변품질): 8/10 PASS
- **그룹 3** (UX/에러/개선점): 9/10 PASS
- **수정 완료 버그 2건**:
  - `store_info.py`: Top 5 업종에 점포 수 0개 업종 포함 → `store_count > 0` 필터 추가
  - `chat.py`: 한국어 조사("은/는/이/가" 등) 포함 시 상권 DB 검색 실패 → `_strip_korean_particles()` 추가
- **잔여 SOFT FAIL**: "여기 카페 많아?" 컨텍스트 불일치 (Agent LLM 수준, 낮은 심각도)
- **상세 리포트**: `docs/status/e2e-qa-report.md`

### ✅ SHP 폴리곤 적재 + Real 모드 전환
- **OA-15560 SHP** 다운로드(data.seoul.go.kr) → geopandas 파싱 → PostGIS 적재
- 1,650개 상권 boundary/center_point 100% 채워짐 (EPSG:5181→4326 변환)
- `DISTRICT_TYPE_MAP`에 `U`(관광특구) 추가
- Real 모드 지도에 실제 불규칙 폴리곤 표시 확인

### ✅ Real 모드 차단 버그 2건 수정
- **시스템 프롬프트**: Mock 코드(D3001~D3005) 하드코딩 제거 → `settings.use_mock` 분기
- **채팅 라우트**: Real 모드 이름→코드 DB 감지 + center_point/district_type 조회 추가

### ✅ district_summary.py Real DB 지원
- Mock 직접 import 제거 → `asyncio.gather()`로 3개 하위 Tool 병렬 호출
- `_get_district_meta()` Mock/Real 분기 + 캐시 레이어

### ✅ Real 모드 E2E 검증 (수동 QA)
| 시나리오 | 결과 |
|----------|------|
| 지도에 실제 폴리곤 표시 | PASS |
| 자연어 "강남역 분석해줘" → SummaryCard | PASS (유동인구 745만, 매출 4187억, 피크 17시) |
| 상권 비교 (강남역 vs 홍대입구) | PASS |
| 업종 추천 Top 5 | PASS (편의점 100점, 서적 46점 등) |
| 리스크 분석 | PASS (위험 업종 + 폐업률) |

### ✅ Mock 모드 회귀 테스트
- 32/32 ALL PASSED (14.3분)

### ✅ floating_population ETL 버그 수정 + 재적재
- **원인**: API 컬럼명이 `TMZON_00_06_FLPOP_CO` 형식인데, 변환 코드가 `TMZON_1_FLPOP_CO` 형식을 기대
- **수정**: `transformers.py` TIME_SLOTS를 `"00_06"→0, "06_11"→6, ...` 형식으로 변경 + legacy fallback
- **결과**: 9,885/9,888행 non-zero, 강남역 일 평균 유동인구 745만 3천명 정상 표시
- SummaryCard 시간대별 바 차트 + 피크 시간(17시) 정상 동작

---

## 완료 항목 (2026-03-31)

### ✅ Card UI 4종 다크 테마 적용
- SummaryCard, CompareCard, RecommendCard, RiskCard — `bg-white`/`text-gray-*` → CSS 변수(`var(--bg-secondary)`, `var(--text-primary)`) 교체
- InlineChart — 그리드/축/툴팁 다크 색상 (#334155, #94a3b8, #1e293b)
- 상태 뱃지/등급 뱃지 — `rgba()` 반투명 배경으로 변경
- 그라디언트 헤더 유지 (primary/indigo/amber/red)

### ✅ .gitignore 정리
- `.playwright-mcp/` 디렉토리 전체 제외 (기존 `*.log`만 제외 → 전체)
- `frontend/test-results/` 추가

---

## 완료 항목 (2026-04-06)

### ✅ 대규모 E2E QA 테스트 플랜 작성 (commit 예정)

**문서**: `docs/qa/e2e-qa-test-plan.md` (약 500 lines)

**범위**: 10개 섹션, M01 + F01~F10 전 기능, P0 8건 회귀 매트릭스, 5개 consumer journey, 15개 failure mode

**구성**:
1. **Section A — Test Strategy**: 4-ring 계층 (pre-flight → feature → journey → negative/P0), Mock/Real 매트릭스, evaluator loop
2. **Section B — Test Suite 구조**: `frontend/e2e/ring0~ring3` 디렉토리 레이아웃, 7개 신규 helper (~270 LOC)
3. **Section C — Per-feature Checklist**: M01/F01~F10 각 기능의 Purpose, Happy path, Edge case + 기계 검증 가능한 PASS 기준
4. **Section D — Consumer Journeys**: J01 첫방문자 / J02 비교쇼퍼 / J03 리스크우선 / J04 에러복구 / J05 PDF공유
5. **Section E — P0 Regression Matrix**: 8개 P0 × test 시나리오 × PASS 기준 (artifact 기반 검증)
6. **Section F — Evaluation Protocol (Fresh Subagent)**: 시나리오별 fresh `general-purpose` subagent, evaluation packet(코드 금지), failure_class 5분류(code/llm_quality/flake/infra/criteria_unclear)
7. **Section G — Reporting**: TaskCreate 라이브 추적, Consumer-experience score 0~100 가중 평균, 실패 공개 프로토콜
8. **Section H — Execution Order**: 의존성 기반 순서(M01→F01→F02→F03→…), 2개 pause point
9. **Section I — Helper LOC 예산**: sseCapture(60) + evalPacket(80) + modeGuard(25) + polygonClick(40) + waitSSE(30) + backendLogs(25) + setup 확장(10)
10. **Section J — Trade-offs/리스크**: 7개 리스크 + 완화책

**사용자 결정**:
- Mode: **Mock + Real 풀 실행** (Real 블로커 3건 `districts.boundary` / `district_summary.py` Real 경로 / `store_history`는 명시 SKIP)
- Instrumentation: **Full** (SSE 캡처 + backend 로그 수집 포함)
- Evaluator: **시나리오별 fresh subagent** (Ring 1은 5개 배치, Ring 2/3는 per-scenario)

**통과 조건**: Consumer-experience score ≥ 85/100 → "READY" 판정

**다음 단계**: 사용자 승인 후 helper 구현 → ring별 실행 → fresh subagent 평가 → `docs/qa/e2e-run-{date}.md` 리포트

---

### ✅ P0 Critical 이슈 8건 수정 (commit d8c0155)

**기준 문서**: `docs/qa/issue_report.md` (종합 감사 B- 6.8/10), `docs/plan/p0-critical-fix-plan.md`

**수정 목록**:

| # | 이슈 | 변경 파일 | 영향 |
|---|------|-----------|------|
| P0-1 | `category_metadata.aliases` 마이그레이션 | `alembic/versions/003_add_category_aliases.py` (신규, `IF NOT EXISTS` 가드) | USE_MOCK=false 블로커 해소 |
| P0-2 | Planner/Evaluator/Respond LLM 타임아웃 | `config.py` (`llm_timeout_fast=15.0`, `llm_timeout_slow=60.0`), `planner.py`/`evaluator.py` `asyncio.wait_for`, `respond.py` `asyncio.timeout()` + 부분 응답 | 무한 hang 제거 |
| P0-3 | SSE 이벤트 큐 백프레셔 | `config.py` (`sse_queue_maxsize=256`), `graph.py:424` | 느린 클라이언트에서 메모리 누수 제거 |
| P0-4 | 클라이언트 disconnect 감지 | `api/routes/chat.py` — `Request` 주입, `body`로 param 이름 변경, 매 yield 전 `is_disconnected()` 체크 → 기존 `finally: task.cancel()` 체인 활용 | 탭 닫기 시 background task 자동 취소 |
| P0-5 | LLM JSON 파싱 실패 시 rule fallback 재사용 | `planner.py` `_rule_fallback_result`, `evaluator.py` `_rule_based_evaluate` (parse fail + broad exception 두 경로) | hardcoded summary 제거, 의도 보존 |
| P0-6 | DistrictLayer stale closure | `DistrictLayer.tsx` `selectedCodeRef` + `useEffect([selectedCode])`로 `setOptions` in-place 업데이트, `renderPolygons` deps에서 `selectedCode` 제거 | 빠른 폴리곤 전환 시 잔존 하이라이트 제거 |
| P0-7 | Frontend SSE reader cleanup + AbortController | `chatStore.ts` `currentAbortController` 상태, `api.ts` `signal` 파라미터, `sseParser.ts` `finally releaseLock`, AbortError 비노출 | locked stream 에러 + 이중 스트림 제거 |
| P0-8 | 프롬프트 sanitize 강화 | `agent/prompts/system.py` `sanitize_prompt_value` (`\n\r\t"'\\` + `{}` 스트립), `respond.py` + `planner.py` 값 보간 전 적용 | prompt injection 방어 |

**검증**:
- Python: `ast.parse` 전체 통과 (8개 파일)
- TypeScript: `tsc --noEmit` 0 errors
- Commit: `d8c0155` — 14 files changed, +896/-113

**수정 파일 요약**:
- Backend (8): `alembic/versions/003_add_category_aliases.py` (신규), `config.py`, `agent/prompts/system.py`, `agent/nodes/planner.py`, `agent/nodes/evaluator.py`, `agent/nodes/respond.py`, `agent/graph.py`, `api/routes/chat.py`
- Frontend (4): `components/map/DistrictLayer.tsx`, `stores/chatStore.ts`, `lib/api.ts`, `lib/sseParser.ts`
- Docs (2): `docs/plan/p0-critical-fix-plan.md`, `docs/qa/issue_report.md`

**다음 단계**: E2E QA 테스트 플랜으로 P0 fix를 사용자 경험 수준에서 회귀 검증 (Section E — P0 Regression Matrix)

---

### ✅ 버그 수정 — 지도 폴리곤 미표시 (CORS)

**증상**: 프론트엔드 지도에 상권 폴리곤이 전혀 렌더링되지 않음.

**원인**:
- 프론트엔드가 포트 **3001**에서 실행 중이었으나 백엔드 CORS 허용 origin이 `http://localhost:3000`만 포함
- `DistrictLayer.tsx`의 `catch {}` 블록이 에러를 **silent**하게 무시하여 콘솔에 단서 없음
- Next.js `next.config.mjs`에 이미 `/api/:path*` → `http://localhost:8002/api/:path*` rewrite 프록시가 구성되어 있어, `API_BASE`는 상대 경로 `/api` 그대로 사용 시 CORS 우회 가능

**수정 파일 (3개)**:
- `server/server/config.py` — `cors_origins`에 `http://localhost:3001` 추가 (직접 호출 대비 보강)
- `frontend/src/lib/api.ts` — `API_BASE`/`CHAT_API_BASE`를 `/api` 상대 경로로 통일 (Next.js rewrite 프록시 경유)
- `frontend/src/components/map/DistrictLayer.tsx` — silent catch → `console.warn('[DistrictLayer] Failed to load polygons:', err)`로 변경

**검증 (Playwright MCP 브라우저)**:
- `http://localhost:3001/api/map-data/polygons?bounds=...` → 200 OK (GeoJSON 5개 Feature 반환)
- 콘솔 에러 0건, 네트워크 탭 `/api/map-data/polygons` 200 OK 확인
- `daum-maps-shape-*` 5개 컨테이너 생성 확인
- "강남역 발달상권" 검색 → 클릭 → 파란색 하이라이트 폴리곤 시각 확인, 우측 채팅 패널 자동 SummaryCard 분석 트리거

---

### ✅ Phase 3 — F09 매출 시뮬레이션 / F06 히트맵 / F10 PDF 리포트

**F09 매출 시뮬레이션** (simulate_revenue Tool + SimulationCard):
- `SimulationRepository` Protocol + Mock/Real 구현 (서울 전체 per-store 매출 분위수 p25/p50/p75)
- `simulate_revenue` Tool: 점포당 평균 → 분위수 적용 → 객단가 보정 → 서울 평균 비교
- PAE Planner: `simulation` intent 패턴 (`시뮬레이션|매출.*예상|매출.*얼마|열면.*매출` 등)
- `SimulationCard.tsx`: low/avg/high 바차트 (Recharts) + 서울 평균 기준선 + 산출 근거 + disclaimer
- Alembic 마이그레이션: `category_metadata.default_unit_price` 컬럼 + major_category별 시드값

**F06 시간대별 히트맵** (deck.gl + TimeSlider):
- `HeatmapRepository` Protocol + Mock/Real 구현 (PostGIS center_point + floating_population JOIN)
- `GET /api/map-data/heatmap?time_slot=N` + `GET /api/map-data/heatmap/all` API (Redis 캐시)
- deck.gl `HeatmapLayer` + Kakao Map viewport 동기화 (center_changed/zoom_changed/idle 이벤트)
- `TimeSlider`: 0-23시 슬라이더 + play/pause 1초 애니메이션 + 프리로드 (네트워크 요청 없이 전환)
- `MapControls`: 히트맵 토글 버튼 (🔥 아이콘)
- 패키지: `@deck.gl/core`, `@deck.gl/layers`, `@deck.gl/aggregation-layers`, `@deck.gl/react`

**F10 PDF 리포트** (@react-pdf/renderer + html2canvas):
- `ReportDocument.tsx`: 표지 (MarketScope AI + 상권명 + 분석일) + 대화 이력 + 차트 이미지 + 면책
- `useReportExport` Hook: html2canvas 차트 캡처 → @react-pdf/renderer PDF 생성 → Blob 다운로드
- 한글 폰트: Spoqa Han Sans Neo (Regular + Bold)
- ChatPanel 상단 PDF 버튼 + "PDF로 저장해줘" 채팅 패턴 감지 (로컬 처리, 서버 미전송)
- 패키지: `@react-pdf/renderer`, `html2canvas`

**신규 파일 (13개)**:
- `server/alembic/versions/002_add_default_unit_price.py`
- `server/server/repositories/mock/simulation.py`, `mock/heatmap.py`
- `server/server/repositories/real/simulation.py`, `real/heatmap.py`
- `server/server/agent/tools/simulate_revenue.py`
- `frontend/src/components/chat/cards/SimulationCard.tsx`
- `frontend/src/components/map/HeatmapLayer.tsx`, `TimeSlider.tsx`
- `frontend/src/components/report/ReportDocument.tsx`
- `frontend/src/hooks/useReportExport.ts`
- `frontend/public/fonts/SpoqaHanSansNeo-Regular.ttf`, `SpoqaHanSansNeo-Bold.ttf`

**수정 파일 (18개)**:
- Backend: `protocols.py`, `data_access.py`, `mock/factory.py`, `real/factory.py`, `category.py`, `actor.py`, `planner.py`, `graph.py`, `data_sources.py`, `map_data.py`, `planner.py` (prompt)
- Frontend: `types.ts`, `eventHandlers.ts`, `registry.ts`, `api.ts`, `mapStore.ts`, `MapContainer.tsx`, `MapControls.tsx`, `ChatPanel.tsx`, `chatStore.ts`

**검증**: `tsc --noEmit` 0 errors, `npm run build` 성공 (428 kB)

**E2E 테스트 (Playwright)**: `phase3-scenario.spec.ts` — **12/12 ALL PASSED** (1.6m)

| Suite | Tests | Result |
|-------|-------|--------|
| F09: Revenue Simulation | S9-1 SimulationCard, S9-4 상권미선택, S9-5 Disclaimer, S9-6 서울평균 | 4/4 PASS |
| F06: Heatmap API | B6-1 단일시간, B6-2 프리로드, B6-3 범위초과422, B6-4 캐시일관성 | 4/4 PASS |
| F06: Heatmap UI | S6-1 토글버튼, S6-5 ON/OFF | 2/2 PASS |
| F10: PDF Report | S10-1 PDF버튼, S10-5 빈채팅 | 2/2 PASS |

**API 수준 테스트 (Sub-Agent)**: 12/12 ALL PASSED — 전체 결과 포함 S9-2(경쟁추가), S9-3(한식매핑), B6-3b(음수), B6-5(시간별가중치)

---

## 완료 항목 (2026-04-05)

### ✅ Docker 통합 — `docker compose up` 원커맨드 기동

**Before**: DB/Redis만 Docker, Backend/Frontend는 로컬 수동 실행
**After**: `docker compose up`으로 DB → migrate → seed → backend → frontend 전체 자동 기동

**주요 변경**:

1. **Multi-stage Dockerfile (server)**: `builder` (컴파일 의존성) → `runner` (런타임만, curl 포함 health check)
2. **Multi-stage Dockerfile (frontend)**: `deps` → `builder` (next build) → `runner` (standalone output)
3. **docker-compose.yml 재작성**:
   - `migrate` 서비스: Alembic migration (init container, 실행 후 종료)
   - `seed` 서비스: `data/seed/marketscope_seed.dump` 자동 복원 (districts 행 수 체크하여 중복 방지)
   - `backend` 서비스: health check + 환경변수 직접 주입 (service name 기반 DB/Redis URL)
   - `frontend` 서비스: build-time ARG로 NEXT_PUBLIC 변수 주입, standalone 모드
   - `backend-dev` / `frontend-dev`: `--profile dev`로 볼륨 마운트 + hot-reload 개발 모드
4. **next.config.mjs**: `output: 'standalone'` 추가 (Docker production 빌드용)
5. **server/pyproject.toml**: `psycopg2-binary` 추가 (Alembic sync migration용)
6. **server/config.py**: `.env` 파일 미존재 시 `env_file: None` (Docker 환경변수 전용 모드)
7. **.env.example**: Docker 환경 설명 업데이트, `GOOGLE_API_KEY`/`AGENT_MODE`/`LLM_PROVIDER` 추가, `USE_MOCK` 기본값 `false`
8. **.dockerignore 2개 신규**: `frontend/.dockerignore`, `server/.dockerignore`

**서비스 기동 순서**:
```
db (PostGIS) → redis → migrate (alembic) → seed (pg_restore) → backend → frontend
```

**개발 모드**: `docker compose --profile dev up` (소스 볼륨 마운트 + hot-reload)

---

## 완료 항목 (2026-04-04)

### ✅ Frontend 환경변수 로딩 근본 수정
- **문제**: `frontend/.env.local` 없으면 `NEXT_PUBLIC_KAKAO_MAP_KEY=undefined` → 카카오맵 로딩 실패
- **원인**: Next.js는 자신의 프로젝트 루트(`frontend/`)에서만 `.env` 읽음, root `.env` 미참조
- **해결**: `next.config.mjs`에서 `dotenv`로 root `.env` 자동 로드 (`override: false`)
- **추가**: `.env.example`에 env 로딩 구조 문서화, `docker-compose.yml` frontend에 `NEXT_PUBLIC_API_URL` 추가
- **카카오맵 SDK**: 브라우저 ORB 차단 확인 → 서버 프록시(`/api/kakao-sdk`) 방식 확정, `next.config.mjs` rewrite에서 제외 처리
- **결과**: `frontend/.env.local` 불필요, root `.env` 하나로 모든 환경 동작

### ✅ QA P0+P1 버그 수정 — 8건 전체 완료

**기준**: 종합 QA 194개 테스트 (Grade C, 3.22/5.0, 134/194 PASS)
**목표**: Grade B+ (4.2/5.0, 180/194 PASS)
**계획 문서**: `docs/plan/qa-bugfix-plan.md`, `docs/qa/qa-improvements.md`

| # | 버그 | 우선순위 | 수정 내용 | 수정 파일 |
|---|------|---------|----------|----------|
| 1 | BUG-001: 3개 Tool 크래시 | P0 | Repository 3개 try/except + district_name 조회 + ORDER BY cast/nullif + Tool 래퍼 3개 try/except + seed_category_metadata | comparison.py, recommendation.py, stores.py, compare_districts.py, recommend_business.py, store_history.py, seed_category_metadata.py |
| 2 | BUG-002: 프롬프트 인젝션 | P0 | 시스템 프롬프트 가드레일(규칙9,10) + format-string 인젝션 방지(_sanitize) + respond.py 가드레일 | system.py, respond.py |
| 3 | BUG-003: Frontend 404 | P0 | next.config.mjs rewrite destination 환경변수화 | next.config.mjs |
| 4 | BUG-004: PAE 모드 미활성 | P1 | `.env`에 `AGENT_MODE=pae` 추가 | .env |
| 5 | BUG-005: 응답 시간 초과 | P1 | 인사 단축(Agent 스킵, <1s) + planner greeting 패턴 + role-based Gemini 모델(pro→respond/react, flash→planner/evaluator) | chat.py, planner.py, graph.py, evaluator.py, respond.py, config.py |
| 6 | BUG-006: 상권 자동감지 오작동 | P1 | 우선순위 재배치(explicit > session > auto-detect) + stopword 필터(30개) + prefix 매칭(3글자 이상) | chat.py, districts.py |
| 7 | BUG-007: Redis fallback 없음 | P1 | RedisCacheService 전면 try/except + 자동 재연결 + graceful degradation | cache.py |
| 8 | BUG-008: 동시 사용자 성능 | P1 | asyncio.Lock + 쓰로틀 pruning(60초) + Semaphore(20) + DB pool(10/20) | chat.py, config.py, main.py |

**추가 최적화**: Gemini 모델 role-based 선택 (graph.py)
- `pro_roles` (respond, react, planner, default) → `gemini-3.1-pro-preview`
- `flash_roles` (evaluator) → `gemini-3.1-flash-lite-preview`
- 각 노드가 `_create_llm(role=...)` 호출하여 자동 분기

**총 수정**: P0 3건 + P1 5건 = 8건, 16개 수정 + 1개 신규 = 17개 파일

---

## 완료 항목 (2026-04-03)

### ✅ Agent 아키텍처 전환 — Planner-Actor-Evaluator (PAE)

**아키텍처**:
```
START → PLANNER → ACTOR → EVALUATOR → RESPOND → END
              ↑                  │
              └── insufficient ──┘ (max 3회)
        PLANNER → RESPOND (direct, 도구 불필요 시)
```

**신규 파일 (9개)**:
- `server/server/agent/state.py` — `ToolPlanStep`, `EvaluationResult` TypedDict + `AgentState` 확장 (기존 5필드 + 신규 14필드)
- `server/server/agent/history.py` — `ConversationHistory` 클래스 (멀티턴 대화 이력 관리, truncation, format_for_planner)
- `server/server/agent/nodes/planner.py` — 3단계 의도 분류 (규칙→LLM→계획 생성), 8종 의도 패턴, INTENT_TO_PLAN 매핑
- `server/server/agent/nodes/actor.py` — 병렬 도구 실행기 (LLM 미사용), `group_by_dependencies()` layer 분리, SSE 이벤트 큐 직접 push
- `server/server/agent/nodes/evaluator.py` — Fast path (규칙 기반) / Slow path (LLM) 결과 충분성 판단 + `generate_proactive_suggestions()` 동적 suggestion
- `server/server/agent/nodes/respond.py` — 수집 데이터+이력+제안 기반 LLM 스트리밍 응답, `build_respond_prompt()` 프롬프트 조립
- `server/server/agent/prompts/planner.py` — Planner LLM 프롬프트 (도구 카탈로그, 의도 분류 가이드, JSON 스키마)
- `server/server/agent/prompts/evaluator.py` — Evaluator LLM 프롬프트 (충분성 판단 기준, JSON 출력)
- `server/server/agent/nodes/__init__.py`

**수정 파일 (6개)**:
- `server/server/config.py` — `agent_mode` (react/pae), `agent_max_rounds`, `max_history_turns`, `history_content_limit`, `evaluator_skip_simple` 설정 추가
- `server/server/agent/graph.py` — 기존 `run_agent` → `run_agent_react` 보존 + `run_agent_pae` (asyncio.Queue 기반 실시간 스트리밍) + `_build_pae_graph()` + 통합 `run_agent` 분기
- `server/server/api/routes/chat.py` — `ConversationHistory` 세션 연동, PAE 모드 분기, text 수집→이력 저장, summary 선발행 PAE 스킵
- `server/server/main.py` — PAE 모드 시 ReAct 싱글턴 생성 스킵
- `frontend/src/lib/types.ts` — SSEEvent union에 `plan` 타입 추가
- `frontend/src/lib/eventHandlers.ts` — `plan` 이벤트 핸들러 (의도별 한국어 라벨 8종, pending step 추가)

**핵심 설계 결정**:
- `asyncio.Queue` 기반 실시간 SSE: Actor/Respond 노드가 큐에 직접 push → 노드 완료 전에 클라이언트에 이벤트 도달
- `agent_mode` 플래그 (`react`/`pae`): `.env`에서 전환, 기존 ReAct 코드 100% 보존하여 즉시 롤백 가능
- Planner 규칙 우선: 7가지 패턴이 0.9 확신도로 매칭 → LLM 미호출 (토큰 절약), 모호한 경우만 LLM fallback
- Evaluator Fast path: 단순 의도 + 전체 성공 시 LLM 미호출로 즉시 `sufficient=True`

**검증 결과**:
| 시나리오 | 결과 | SSE 이벤트 흐름 |
|----------|------|----------------|
| PAE Summary (강남역 분석해줘) | PASS | thinking→plan→tool→tool_end→card(summary)→text→suggestion→done |
| PAE Recommendation (뭐하면 좋을까?) | PASS | thinking→plan→tool→card(recommend)→text→done |
| PAE Risk (위험하지 않아?) | PASS | thinking→plan→tool→card(risk)→text→done |
| PAE Direct (안녕하세요) | PASS | thinking→text→suggestion→done (도구 미호출) |
| PAE Multi-turn History (2턴) | PASS | 이력 4턴 누적, format_for_planner 정상 |
| ReAct 모드 회귀 | PASS | 기존 SSE 이벤트 순서 동일 |
| `tsc --noEmit` | 0 errors |
| `npm run build` | 성공 |

**전환 방법**: `.env`에 `AGENT_MODE=pae` 추가. 기본값은 `react` (기존 동작 유지).

---

### ✅ 코드 리팩토링 — Repository 패턴 + Frontend 분리

**Backend 리팩토링 (Phase 1)**:
- **Repository Protocol + DataAccess 파사드**: 7개 Protocol 정의 (`protocols.py`), `DataAccess` 파사드 클래스, 모듈 레벨 `get_data_access()` / `set_data_access()` 접근자
- **Mock Repository (9개 파일)**: `mock_data.py` 위임, `build_mock_data_access()` 팩토리
- **Real Repository (9개 파일)**: 기존 tool 파일의 SQL 쿼리 추출, `build_real_data_access(session_factory)` 팩토리
- **CacheService 분리**: `MemoryCacheService` (mock) / `RedisCacheService` (real) + `flush_by_prefix()` 메서드 + 모듈 레벨 접근자
- **FastAPI Lifespan**: Mock/Real 결정의 단일 진입점 (`main.py`), startup에서 DataAccess + CacheService + Agent 초기화, shutdown에서 정리
- **Agent 싱글턴**: `create_agent()` 매 요청 호출 → `get_agent()` / `set_agent()` 싱글턴
- **CORS 환경변수화**: 하드코딩 `["http://localhost:3000"]` → `settings.cors_origins`
- **Tool 슬림화 (8개 파일)**: ~100줄 → ~20줄 (캐시 체크 + `get_data_access()` 위임만)
- **Route 정리 (4개 파일)**: 모든 `if settings.use_mock` 분기 제거, `get_data_access()` 위임
- **동적 Suggestion**: 선택된 상권명이 suggestion 질문에 자동 반영
- **`settings.use_mock` 잔존**: main.py(lifespan 결정) + 표현 로직 3곳만 (tool/route에서 **0곳**)

**Frontend 리팩토링 (Phase 2)**:
- **SSEEvent discriminated union**: `[key: string]: unknown` 제거 → 9개 타입 union (타입 안전성 확보)
- **SSE Parser 모듈** (`sseParser.ts`): AsyncGenerator 기반 스트림 파싱 분리
- **Event Handler Registry** (`eventHandlers.ts`): 9개 핸들러 함수 + TOOL_LABELS + CARD_LABELS 추출
- **chatStore 슬림화**: 351줄 → 139줄 (**60% 축소**), switch문/SSE 파싱 로직 완전 제거
- **Card Component Registry** (`registry.ts`): 4단 ternary chain → 동적 `CARD_REGISTRY[cardType]` lookup
- **console.log 제거**: MapContainer.tsx 5개 `console.log` 제거 (3개 `console.error`만 유지)
- **Kakao Map 타입** (`kakao.maps.d.ts`): Map/LatLng/Polygon/event 타입 선언, `Window.kakao` any 제거

**신규 파일**: 25개 | **수정 파일**: 20개
**검증**: `tsc --noEmit` 0 errors, `npm run build` 성공 (243 kB), Mock API 4/4 PASS

### ✅ 데이터 출처 표시 기능 (Card footer 출처 citation)
- **신규 파일**: `server/server/agent/tools/data_sources.py` (출처 레지스트리), `frontend/src/components/chat/cards/SourcesCitation.tsx` (출처 UI)
- **수정 파일**: `district_summary.py`, `graph.py`, `types.ts`, `SummaryCard.tsx`, `CompareCard.tsx`, `RecommendCard.tsx`, `RiskCard.tsx`
- 4개 Card 모두 동일한 SourcesCitation 컴포넌트 사용, collapsed(1줄)/expanded(상세) 토글
- Mock 모드: "출처: 샘플 데이터" 표시, Real 모드: "출처: 서울 열린데이터광장 (N)" + 펼침 시 데이터셋/기관/라이선스/URL
- 공공데이터 이용 시 출처 표시 의무 충족 (공공누리 제1유형)

---

## 완료 항목 (2026-04-02)

### ✅ DB 셋업 자동화
- `scripts/setup_db.py` — 원커맨드 DB 프로비저닝 (`--quick`/`--full`/`--reset`)
- `scripts/generate_seed.py` — 시드 덤프 재생성 유틸리티
- `data/seed/marketscope_seed.dump` — pg_dump 시드 파일 (4.9MB, Git LFS)
- `.gitattributes` — Git LFS 트래킹 설정
- `server/server/data/etl/csv_collector.py` — 상주인구 CSV 로더 (OA-15584)
- `server/server/data/etl/runner.py` — `load-csv` 커맨드 + `--csv-file` 옵션 + API 실패 시 CSV 폴백
- `.env.example` — API 키 발급 가이드 주석 추가
- `docs/setup/DATABASE_SETUP.md` — 셋업 가이드 문서
- Quick Start 테스트 완료: DB 초기화 → `--quick` → 5개 테이블 전부 복원 확인

---

## Next Items (우선순위 순)

### ~~🔴 1. 데이터 출처 표시 기능~~ ✅ 완료 (2026-04-03)
Card footer에 데이터 출처(서울 열린데이터광장, API명, 라이선스) 표시.
- **Backend**: `data_sources.py` 정적 레지스트리 (6개 Seoul Open Data 소스 + MOCK_SOURCE + Tool→소스 매핑)
- `district_summary.py` result에 `dataSources` 주입, `graph.py` on_tool_end에서 compare/recommend/risk card에 주입
- **Frontend**: `SourcesCitation.tsx` 재사용 컴포넌트 (collapsed/expanded 토글), 4개 Card footer 교체
- `types.ts`에 `DataSourceInfo` 인터페이스 + 4개 Card 타입 확장
- **Collapsed**: `데이터 기준: 2025Q4  ·  출처: 서울 열린데이터광장 (3) ▼`
- **Expanded**: 데이터셋 트리 + 기관명/라이선스 + 플랫폼 링크
- **Mock 모드**: `출처: 샘플 데이터` (펼침 버튼 없음)
- **하위 호환**: `dataSources` 없으면 기존 footer만 표시
- `tsc --noEmit` + `npm run build` 통과

### ~~🔴 2. 코드 리팩토링~~ ✅ 완료 (2026-04-03)
12개 파일 22곳의 `if settings.use_mock:` 분기 → **Repository 패턴**으로 통합 완료.
- **상세 결과**: 아래 "완료 항목 (2026-04-03) — 코드 리팩토링" 참조
- 상태: **구현 완료** (`tsc --noEmit` 0 errors, `npm run build` 성공, Mock API 4/4 PASS)

### ~~🔴 3. Agent 아키텍처 전환 — Planner-Actor-Evaluator~~ ✅ 완료 (2026-04-03)
`create_react_agent` (prebuilt ReAct) → **커스텀 Planner-Actor-Evaluator 그래프** 전환 완료.
- **상세 결과**: 아래 "완료 항목 (2026-04-03) — PAE Agent 아키텍처" 참조
- 상태: **구현 완료** (PAE 4/4 PASS, ReAct 회귀 PASS, `tsc --noEmit` 0 errors, `npm run build` 성공)

### ~~🟡 4. 상주인구 CSV 적재~~ ✅ 완료 (2026-04-03)
- `data/csv/OA-15584.csv` → `load-csv` → resident 19,596행 적재 (기존 worker 19,692 + 신규 resident 19,596 = 39,288행)
- `setup_db.py --full` ETL에 `--csv-file` 자동 전달 반영
- 시드 덤프 재생성 완료 (5.0MB)

### ~~🔴 4. 종합 QA 테스트~~ ✅ 완료 (2026-04-03)
9개 카테고리 **194개** 테스트 케이스를 3개 독립 Opus 4.6 Sub-Agent가 병렬 평가

**종합 등급: C (3.22/5.0)** — 134/194 PASS (69.1%)

| 카테고리 | 점수 | Pass/Total |
|---------|------|-----------|
| CAT-1 기능 정확성 | 2/5 | 12/35 |
| CAT-2 데이터 정확성 | 3/5 | 14/18 |
| CAT-3 AI Agent 품질 | 3/5 | 55/86 |
| CAT-4 성능/응답속도 | 3/5 | 9/14 |
| CAT-5 보안/입력검증 | 4/5 | 12/16 |
| CAT-6 에러 핸들링 | 3/5 | 6/12 |
| CAT-7 UX/접근성 | 4/5 | 13/15 |
| CAT-8 인프라/배포 | 4/5 | 8/10 |
| CAT-9 회귀/크로스기능 | 3/5 | 5/8 |

**Top P0 ���슈**: (1) 3개 Tool 크래시(compare/recommend/risk), (2) 프롬프트 인젝션 취약점, (3) Frontend 404
- **산출물**: `docs/qa/qa-summary-report.md`, `docs/qa/qa-detailed-results.md`, `docs/qa/qa-improvements.md`
- **P0+P1 수정 완료** (2026-04-04): 8건 전체 수정 → 예상 Grade B+ (4.2/5.0, 180/194)

### ~~🔴 5. QA P0 버그 수정 (3건)~~ ✅ 완료 (2026-04-04)
- [x] BUG-001: 3개 Tool 크래시 수정 — Repository 3개 try/except + Tool 래퍼 3개 + seed_category_metadata
- [x] BUG-002: 프롬프트 인젝션 방어 — system.py/respond.py 가드레일 + _sanitize()
- [x] BUG-003: Frontend 404 해결 — next.config.mjs rewrite destination 환경변수화

### ~~🟡 6. QA P1 개선 (5건)~~ ✅ 완료 (2026-04-04)
- [x] BUG-004: AGENT_MODE=pae .env 설정
- [x] BUG-005: 응답 시간 최적화 — 인사 단축 + role-based Gemini 모델(pro/flash)
- [x] BUG-006: 상권 자동감지 우선순위 수정 — explicit > session > auto-detect + stopword 필터
- [x] BUG-007: Redis fallback — RedisCacheService 전면 try/except + 자동 재연결
- [x] BUG-008: 동시 사용자 성능 — asyncio.Lock + Semaphore(20) + DB pool(10/20)

### ~~🔴 7. Docker 통합 정비~~ ✅ 완료 (2026-04-05)

- **계획 문서**: `docs/plan/docker-integration-plan.md`
- **구현 완료**: `docker compose up` 한 줄로 전체 서비스 기동
- **수정 파일**: docker-compose.yml, server/Dockerfile, frontend/Dockerfile, frontend/next.config.mjs, server/pyproject.toml, server/server/config.py, .env.example + .dockerignore 2개 신규
- 상세는 아래 "완료 항목 (2026-04-05)" 참조

### ~~🟡 8. 기능 고도화~~ ✅ Phase 3 완료 (2026-04-06)

- 비교모드 복수 상권 하이라이트 (미완료, 후순위)
- category_aliases 퍼지 검색 (미완료, 후순위)
- ~~F06 히트맵 / F09 시뮬레이션 / F10 PDF~~ ✅ 완료

### ~~🟢 9. 하드코딩 개선 (5건)~~ ✅ 완료 (2026-04-06)

**계획 문서**: `docs/plan/hardcoding-improvement-plan.md`
**목표**: 단일 진실 소스(SSOT) 확보 + 유지보수성 향상 — 새 업종/Tool 추가 시 한 곳만 수정

| # | 개선 | 신규 | 수정 | 검증 |
|---|------|-----:|-----:|------|
| 1 | Mock 데이터 → JSON 파일 분리 | 8 | 1 | 5개 상권 데이터 assertion 통과 |
| 2 | INTENT_PATTERNS → YAML 설정 | 3 | 1 | 7개 intent 패턴 매칭 동일 |
| 3 | `_CATEGORY_KEYWORDS` → DB 동적 로딩 | 2 | 3 | Mock defaults 12개 키워드 resolve 통과 |
| 4 | Tool 레지스트리 자동 등록 | 1 | 11 | 9개 tool 자동 discover, card_type 매핑 확인 |
| 5 | Frontend 라벨 → Backend SSE 전달 | 0 | 2 | `tsc --noEmit` 0 errors |

**주요 변경**:
- `server/server/agent/tools/mock/` — 7개 JSON + `__init__.py` 로더 (`@lru_cache`)
- `mock_data.py` — 1,138줄 → ~120줄 (public API 불변)
- `server/server/agent/config/intents.yaml` + `intent_loader.py` — regex 패턴 + Tool 계획 YAML화
- `server/server/services/category_resolver.py` — 싱글턴 서비스 (mock defaults + DB 로딩 + `aliases` 컬럼)
- `server/server/agent/tools/registry.py` — `@register_tool` 데코레이터 + `ToolMeta`
- 9개 tool 파일에 `@register_tool` 적용 (emoji, card_type, progress_label, done_label)
- `actor.py` — `TOOL_REGISTRY`/`TOOL_CARD_MAP`/`TOOL_EMOJI` 제거, registry 사용
- `graph.py` — 중복 emoji/card map 제거, `_get_react_meta()` 헬퍼 사용
- SSE `tool`/`tool_end` 이벤트에 `progress_label`/`done_label` 추가
- Frontend `eventHandlers.ts` — backend 값 우선, `TOOL_LABELS` fallback 유지
- `CategoryMetadata` 모델에 `aliases: str | None` 컬럼 추가 (마이그레이션은 후속)

**검증**: Python import 체인 통과, tool registry 9/9 자동 등록, TypeScript 0 errors

---

## Phase 2 — 프리미엄 (미착수)

### 코드 작성 완료
- [x] F04 업종 심층 분석 (기존 Tool에 category 필터 지원)
- [x] F05 상권 비교 (compare_districts Tool + CompareCard)
- [x] F07 업종 추천 (recommend_business Tool + RecommendCard)
- [x] F08 이력/리스크 (get_store_history Tool + RiskCard)

### 미완료
- [ ] category_aliases 퍼지 검색 테이블 (pg_trgm)
- [ ] 지도 비교모드에서 복수 상권 다른 색상 하이라이트

---

## Phase 3 — 확장 ✅ 완료 (2026-04-06)
- [x] F09 간이 매출 시뮬레이션 (simulate_revenue Tool + SimulationCard)
- [x] F06 시간대별 히트맵 (deck.gl HeatmapLayer + TimeSlider)
- [x] F10 리포트 저장 (PDF — @react-pdf/renderer + html2canvas)

---

## Phase 4 — 수익화 (후순위)
- [ ] Tier 게이팅 인프라 (OAuth2 인증, 결제 연동)
- [ ] Free/Premium 접근 제어 미들웨어
- [ ] 일일 사용 횟수 카운터 (Free: 5회)
- [ ] 결제 연동 (Toss Payments / PortOne)

---

## 참고

- **종합 QA 결과**: `docs/qa/qa-summary-report.md` (Grade C, 3.22/5.0, 134/194 PASS)
- **종합 QA 상세**: `docs/qa/qa-detailed-results.md` (194개 테스트 개별 결과)
- **종합 QA 개선**: `docs/qa/qa-improvements.md` (P0: 3건, P1: 5건, P2: 4건, P3: 6건)
- **종합 QA 테스트 계획**: `docs/qa/qa-test-plan.md` (9개 카테고리, 194개 테스트, 3개 Sub-Agent — CAT-3 PAE 86개 포함)
- **E2E QA 리포트**: `docs/status/e2e-qa-report.md`
- **스크린샷**: `docs/screenshots/e2e-qa/` (20개), `docs/screenshots/real-mode/` (7개), `docs/screenshots/dev/` (5개)
- **데이터 출처 표시 계획**: `docs/plan/data-source-citation.md` (Card footer 출처 표시, 10개 시나리오)
- **리팩토링 계획/결과**: `docs/plan/refactoring-plan.md` (계획) — 구현 완료: Repository 25개 신규 파일, 20개 수정
- **Agent 개선 계획/결과**: `docs/plan/agent_improvement/` (10개 모듈) — 구현 완료: 9개 신규 파일, 6개 수정, PAE 4/4 PASS
- Phase 1B 구현 계획: `docs/plan/phase1b-comprehensive-plan.md`
- Real DB 마이그레이션 계획: `docs/plan/data-source-migration.md`
- Dark Theme 구현 계획: `docs/plan/streaming-ux-dark-theme.md`
- Card UI 구현 계획: `docs/plan/card-ui-integration.md`
- 체크리스트: `docs/spec/checklist.md`
- 아키텍처: `docs/architecture/overall-architecture.md`
