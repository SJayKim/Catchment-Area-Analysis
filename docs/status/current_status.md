# 현재 진행 상황

> 최종 갱신: 2026-04-02
> **Phase 1B 완료 ✅ — Playwright E2E QA 22/26 PASS + 버그 2건 수정 + HARD FAIL 0건**

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
| resident_population | 19,692 | 2025Q4 | VwsmTrdarWrcPopltnQq (직장인구) |

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

### 상주인구 CSV 대안 (검증 완료 2026-04-02)
- **데이터셋**: [OA-15584 서울시 상권분석서비스(상주인구-상권)](https://data.seoul.go.kr/dataList/OA-15584/S/1/datasetView.do)
- **다운로드**: Sheet 탭 → "내려받기(CSV)" 버튼 (`#btnCsv`)
- **파일 정보**: 40,812행, EUC-KR 인코딩
- **컬럼 (29개)**: 기준_년분기_코드, 상권_구분_코드, 상권_코드, 상권_코드_명, 총/남/여_상주인구_수, 연령대별(10~60+) 남/여 상주인구, 총/아파트/비아파트_가구_수
- **구현 TODO**: `data/` 폴더에 CSV 저장 → ETL에 CSV 파싱 로더 추가 → `resident_population` 테이블 적재 (pop_type="resident")

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

### 🔴 1. 데이터 출처 표시 기능 (계획 수립 완료 2026-04-02)
Card footer에 데이터 출처(서울 열린데이터광장, API명, 라이선스) 표시. 현재 "데이터 기준: 2025Q4"만 있고 출처 정보 전무 → 신뢰성 부족 + 공공데이터 출처 표시 의무 미충족
- **상세 계획**: `docs/plan/data-source-citation.md`
- **UX**: Card footer 1줄에 `출처: 서울 열린데이터광장 (3) ▼` 표시, 클릭 시 데이터셋 목록/기관/라이선스 펼침
- **Backend**: `data_sources.py` 정적 레지스트리 + Tool/SSE에 dataSources 필드 주입
- **Frontend**: `SourcesCitation.tsx` 재사용 컴포넌트, 4개 Card footer 교체
- **Scenario Test**: 10개 시나리오 (10점 만점, 10점만 통과), 독립 subagent 평가
- **영향 범위**: 신규 2개, 수정 7개 파일
- 상태: **계획 완료, 구현 미착수**

### 🔴 2. 코드 리팩토링 — 안정성/범용성/확장성 개선 (계획 수립 완료 2026-04-02)
12개 파일 22곳의 `if settings.use_mock:` 분기 → **Repository 패턴**으로 통합, Agent 매 요청 재생성 → **싱글턴**, chatStore 230줄 → **SSE Parser + Event Handler Registry 분리**
- **상세 계획**: `docs/plan/refactoring-plan.md`
- **Backend**: Repository Protocol + DataAccess 파사드, Mock/Real Repository, CacheService 분리, FastAPI Lifespan + Agent 싱글턴, CORS 환경변수화, Tool/Route 위임 전환, 세션 캐시화, 동적 Suggestion, 캐시 무효화
- **Frontend**: SSEEvent discriminated union, SSE Parser 모듈, Event Handler Registry, chatStore 슬림화, Card Component Registry, console.log 정리, Kakao Map 타입
- **Scenario Test**: 34개 시나리오 (R11 + E7 + F8 + P4), fail/normal/perfect 그레이딩, 독립 subagent 평가, 전체 perfect시 완료
- **영향 범위**: 신규 ~31개 파일, 수정 ~27개 파일 (API 응답 형태/프론트 렌더링 변경 없음)
- 상태: **계획 완료, 구현 미착수**

### 🟡 3. Agent 아키텍처 전환 — Planner-Actor-Evaluator (계획 수립 완료)
현재 `create_react_agent` (prebuilt ReAct) → **커스텀 Planner-Actor-Evaluator 그래프**로 전환
- **목적**: 멀티턴 대화 지원, 의도 분류 정확성, 도구 호출 효율화, 결과 평가
- **상세 계획**: `docs/plan/agent_improvement/` (10개 모듈, 70개 시나리오 테스트)
- **구현 순서**: State확장 → 대화이력 → Planner → Actor → Evaluator → Respond → Graph조립 → Chat통합 → 프론트 → UX개선
- **마이그레이션**: `agent_mode` 플래그로 react/pae 전환, 롤백 가능
- 상태: **계획 완료, 구현 미착수**

### 🟡 4. 상주인구 CSV 적재 (대안 검증 완료)
API 서버 ERROR-500 → CSV 다운로드 대안 확인 완료 (OA-15584, 40,812행)
- CSV를 `data/` 폴더에 저장 → ETL 로더에 CSV 파싱 추가 → `resident_population` 적재

### 🟢 5. Phase 2 — 프리미엄 기능
- Tier 게이팅 인프라 (OAuth2 인증, 결제)
- 비교모드 복수 상권 하이라이트

---

## Phase 2 — 프리미엄 (미착수)

### 코드 작성 완료
- [x] F04 업종 심층 분석 (기존 Tool에 category 필터 지원)
- [x] F05 상권 비교 (compare_districts Tool + CompareCard)
- [x] F07 업종 추천 (recommend_business Tool + RecommendCard)
- [x] F08 이력/리스크 (get_store_history Tool + RiskCard)

### 미완료
- [ ] Tier 게이팅 인프라 (OAuth2 인증, 결제 연동)
- [ ] category_aliases 퍼지 검색 테이블 (pg_trgm)
- [ ] 지도 비교모드에서 복수 상권 다른 색상 하이라이트

---

## Phase 3 — 확장 (미착수)
- [ ] F06 시간대별 히트맵 (deck.gl + TimeSlider)
- [ ] F09 간이 매출 시뮬레이션 (simulate_revenue Tool)
- [ ] F10 리포트 저장 (PDF)

---

## 참고

- **E2E QA 리포트**: `docs/status/e2e-qa-report.md`
- **스크린샷**: `docs/screenshots/e2e-qa/` (20개), `docs/screenshots/real-mode/` (7개), `docs/screenshots/dev/` (5개)
- **데이터 출처 표시 계획**: `docs/plan/data-source-citation.md` (Card footer 출처 표시, 10개 시나리오)
- **리팩토링 계획**: `docs/plan/refactoring-plan.md` (Backend/Frontend/Scenario Test 3단계, 34개 시나리오)
- **Agent 개선 계획**: `docs/plan/agent_improvement/` (10개 모듈, TODO 78개, Checklist 111개, 시나리오 테스트 70개)
- Phase 1B 구현 계획: `docs/plan/phase1b-comprehensive-plan.md`
- Real DB 마이그레이션 계획: `docs/plan/data-source-migration.md`
- Dark Theme 구현 계획: `docs/plan/streaming-ux-dark-theme.md`
- Card UI 구현 계획: `docs/plan/card-ui-integration.md`
- 체크리스트: `docs/spec/checklist.md`
- 아키텍처: `docs/architecture/overall-architecture.md`
