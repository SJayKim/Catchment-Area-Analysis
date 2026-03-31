# 현재 진행 상황

> 최종 갱신: 2026-03-31
> **Phase 1B 완료 ✅ — Mock E2E + Real Data ETL + Dark Theme + Streaming UX + E2E 32 PASS**

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

### 미승인 API (추후 승인 필요)
- `VwsmTrdarSelngW` (상권 폴리곤) — districts boundary/center_point 없음
- `VwsmTrdarStorW` (점포 상세정보)
- `VwsmTrdarPopltnQq` (상주인구)

---

## 현재 실행 환경

| 서비스 | 포트 | 모드 |
|--------|------|------|
| Next.js 프론트엔드 | 3000 | Mock (USE_MOCK=true) |
| FastAPI 백엔드 | 8002 | Mock (USE_MOCK=true) |
| PostGIS (Docker) | 5432 | 실데이터 적재 완료 |
| Redis (Docker) | 6379 | 정상 |

- Mock 모드: 5개 상권 폴리곤 + AI 챗봇 + Card UI 전체 동작
- Real 모드: 1,650개 상권 데이터 + DB 쿼리 (폴리곤 경계선 없음)

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

## Next Items (우선순위 순)

### 🟡 1. district_summary.py Real DB 지원
현재 Mock 데이터만 사용. 다른 7개 Tool처럼 `settings.use_mock` 분기 + Real DB 쿼리 추가 필요.

### 🟡 2. 미승인 API 서비스 승인 요청
승인 후 ETL 재실행 → 폴리곤 지도 표시 + 상주인구 적재

### 🟢 3. Phase 2 — 프리미엄 기능
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

- Phase 1B 구현 계획: `docs/plan/phase1b-comprehensive-plan.md`
- Dark Theme 구현 계획: `docs/plan/streaming-ux-dark-theme.md`
- Card UI 구현 계획: `docs/plan/card-ui-integration.md`
- 체크리스트: `docs/spec/checklist.md`
- 아키텍처: `docs/architecture/overall-architecture.md`
