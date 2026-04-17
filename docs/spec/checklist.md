# 개발 체크리스트

> 전체 기능 구현 체크리스트. 완료 시 체크 표시 후 검토 기준으로 활용.
> **전략**: Mock 데이터로 E2E 흐름을 먼저 검증 (Phase 1A) → 실제 데이터 연결 (Phase 1B)

---

## Phase 1A — E2E Mock (DB 없이 Agent + Chat 동작)

### M01. Mock 데이터 레이어
- [ ] `mock_data.py` 작성 (3~5개 상권: 강남역, 홍대, 건대입구 등)
- [ ] Mock 유동인구 데이터 (시간대/요일/연령/성별)
- [ ] Mock 추정매출 데이터 (업종별, 분기별 추이)
- [ ] Mock 점포 데이터 (점포수, 개폐업, Top 업종)
- [ ] Mock 상주/직장인구 데이터
- [ ] Mock 점포 이력 데이터 (생존기간, 업종 변동)
- [ ] Mock 상권 폴리곤 GeoJSON (실제 좌표 기반)
- [ ] `USE_MOCK` 환경 변수로 Mock/Real 전환
- [ ] Mock 모드에서 DB/Redis 연결 없이 FastAPI 기동 확인

### F01. 지도 기반 상권 선택 (Mock)
- [ ] Next.js 14 프로젝트 초기화 (App Router, TypeScript)
- [ ] Kakao Map SDK 로드 및 지도 렌더링
- [ ] 서울 중심 초기 뷰 (37.5665, 126.9780, zoom 11)
- [ ] Mock 폴리곤 GeoJSON 지도 오버레이
- [ ] 폴리곤 호버 시 스타일 변경
- [ ] 폴리곤 클릭 → 상권 선택 + 하이라이트
- [ ] Zustand `districtStore`, `mapStore` 구현
- [ ] Mock 상권 검색 (Toolbar 검색바)
- [ ] StatusBar (선택 상권명 표시)
- [ ] SplitPanel (지도 60% / 채팅 40%, resizable)

### F02. AI 챗봇 에이전트 (Mock Tools)
- [ ] FastAPI 프로젝트 초기화 (DB 없이 단독 실행)
- [ ] LangGraph ReAct Agent 그래프 정의
- [ ] `AgentState` 상태 정의
- [ ] Claude API 연동 (reason 노드)
- [ ] Mock Tool 호출 (act 노드)
- [ ] 결과 해석 (observe 노드)
- [ ] ReAct 루프 최대 5회 제한
- [ ] 시스템 프롬프트 작성 (한국어 상권 분석 컨설턴트)
- [ ] `POST /api/chat` SSE 스트리밍 엔드포인트
- [ ] SSE 이벤트: thinking, tool, text, card, suggestion, done
- [ ] ChatPanel, MessageList, MessageBubble, ChatInput UI
- [ ] `useChat` 훅 (SSE 클라이언트)
- [ ] thinking 상태 표시 (로딩 인디케이터)
- [ ] SuggestionChips 추천 질문
- [ ] 상권 선택 시 자동 쿼리 (`useMapSync`)
- [ ] map_cmd → 지도 반영 연동
- [ ] 에러 처리 (Agent 실패 시 graceful fallback)

### F03. 상권 기본 리포트 (Mock)
- [ ] `get_floating_population` Tool — Mock 데이터 반환
- [ ] `get_store_info` Tool — Mock 데이터 반환
- [ ] `get_estimated_sales` Tool — Mock 데이터 반환
- [ ] `get_population_info` Tool — Mock 데이터 반환
- [ ] SummaryCard 컴포넌트 (Recharts 바차트)
- [ ] InlineChart 공통 차트 컴포넌트
- [ ] 데이터 기준 분기 명시 (Mock: "2025Q3 (샘플)")
- [ ] 추천 질문 칩

### F05. 상권 비교 (Mock)
- [ ] `compare_districts` Tool — Mock 비교 데이터 반환
- [ ] CompareCard 컴포넌트 (비교표 + AI 의견)
- [ ] 비교 모드 UI (Toolbar 토글)
- [ ] 최대 3개 상권 제한 처리

### F07. 업종 추천 (Mock)
- [ ] `recommend_business` Tool — Mock 추천 결과 반환
- [ ] RecommendCard 컴포넌트 (점수바 + 추천 근거 + 면책)

### F08. 점포 이력/리스크 (Mock)
- [ ] `get_store_history` Tool — Mock 이력/리스크 데이터 반환
- [ ] RiskCard 컴포넌트 (안정성 게이지 + 생존 바차트)

### Phase 1A 통합 검증
- [ ] 브라우저에서 지도 + 채팅 화면 정상 로드
- [ ] 폴리곤 클릭 → Agent 자동 요약 → SummaryCard 렌더링
- [ ] "홍대랑 비교해줘" → CompareCard 렌더링
- [ ] "여기서 뭐하면 좋을까?" → RecommendCard 렌더링
- [ ] "이 자리 위험해?" → RiskCard 렌더링
- [ ] SSE 스트리밍 (thinking → tool → text → card → done) 정상 흐름
- [ ] SuggestionChips 클릭 → 추가 질문 동작
- [ ] CORS 정상 동작 (localhost:3000 → localhost:8000)

---

## Phase 1B — Real Data 연결

### D03. Docker 개발환경
- [ ] `docker-compose.yml` 작성 (frontend, backend, db, redis)
- [ ] PostGIS 16 이미지 설정 및 초기화
- [ ] Redis 7 설정
- [ ] 환경 변수 `.env.example` 작성
- [ ] `docker compose up`으로 전체 서비스 기동 확인

### D02. DB 스키마
- [ ] `districts` 테이블 + PostGIS GIST 인덱스
- [ ] `floating_population` 테이블 + 인덱스
- [ ] `estimated_sales` 테이블 + 인덱스
- [ ] `stores` 테이블
- [ ] `store_history` 테이블 + 인덱스
- [ ] `resident_population` 테이블
- [ ] `chat_sessions` + `chat_messages` 테이블
- [ ] `category_metadata` 참조 테이블 (업종 코드 + 메타)
- [ ] 마이그레이션 스크립트 작성 (Alembic)

### D01. 데이터 파이프라인
- [ ] 서울 열린데이터 API 키 발급 및 연동 테스트
- [ ] data.go.kr API 키 발급 및 연동 테스트
- [ ] 상권 폴리곤 수집 → `districts` 적재
- [ ] 유동인구 수집 → `floating_population` 적재
- [ ] 추정 매출 수집 → `estimated_sales` 적재
- [ ] 상주/직장인구 수집 → `resident_population` 적재
- [ ] 점포 정보 수집 → `stores` 적재
- [ ] 점포 이력 수집 → `store_history` 적재
- [ ] UPSERT 및 중복 방지 확인
- [ ] ETL 실패 시 롤백 확인
- [ ] 1개 분기 전체 적재 완료 확인

### Mock → Real 전환
- [ ] `USE_MOCK=false`로 전환
- [ ] 각 Tool 내부에서 실제 DB 쿼리 실행 확인
- [ ] `GET /api/map-data/polygons` — PostGIS 실제 폴리곤 반환
- [ ] `GET /api/districts?search=` — 실제 DB 검색
- [ ] 뷰포트 기반 폴리곤 로딩 (ST_Intersects)
- [ ] Redis 캐싱 활성화 (`report:{code}:{quarter}`, TTL 24h)
- [ ] 실제 데이터 기반 Agent 응답 정확성 확인
- [ ] 첫 토큰 2초 이내 응답 확인

---

## Phase 2 — 프리미엄 차별화 기능 (Premium)

### F04. 업종별 심층 분석 ⭐ Premium
- [ ] `get_estimated_sales` 업종 필터 지원
- [ ] `get_store_info` 업종 필터 지원
- [ ] 경쟁 밀집도 산출
- [ ] 점포당 평균 매출 + 서울 평균 비교
- [ ] 시간대별 매출 비중 차트
- [ ] 타겟 고객 매칭률 산출
- [ ] 업종 생존율 (평균 영업 기간)
- [ ] 자연어 → 업종 코드 매핑 (Agent LLM)
- [ ] 업종 분석 텍스트 응답 + 인라인 차트

### Tier 게이팅 인프라 — ⏸️ Business 스코프 (현재 구현 고려 대상 아님)

인증/결제/구독/Tier 게이팅 관련 구현은 PMF 검증 이후 착수.
상세 로드맵 및 체크리스트는 `docs/plan/business/commercialization-plan.md` (Stage 2 — Public Launch, M3~M4) 참조.

- OAuth2 (Google/Kakao), `users` / `subscriptions` 테이블
- Tier 미들웨어 (Free/Premium 접근 제어), Free 일 5회 카운터
- Toss Payments 빌링키 정기결제, 구독 상태 관리, 업그레이드 유도 UI

---

## Phase 3 — 확장 (Premium)

### F06. 시간대별 히트맵 ⭐ Premium ✅
- [x] deck.gl 설치 및 Kakao Map 통합
- [x] `GET /api/map-data/heatmap` API
- [x] `GET /api/map-data/heatmap/all` 프리로드 API
- [x] HeatmapLayer 컴포넌트
- [x] TimeSlider 컴포넌트 (0~23시)
- [ ] 평일/주말 토글 (MVP: day_type 없음, 후순위)
- [x] 재생 애니메이션 (1초/시간)
- [x] 히트맵 ON/OFF 토글
- [x] 줌/팬 동기화 확인
- [x] 슬라이더 전환 200ms 이내 반응 (프리로드 방식)

### F09. 간이 매출 시뮬레이션 ⭐ Premium ✅
- [x] `simulate_revenue` Tool 구현
- [x] 매출 분위수(p25/p75) 산출 로직
- [x] 경쟁 증가 비례 분배 로직
- [x] SimulationCard 컴포넌트
- [x] 하위/평균/상위 범위 시각화
- [x] 서울 평균 비교 표시
- [x] 산출 근거 명시
- [ ] What-If "경쟁 N개 추가" 시뮬레이션 (Tool은 지원, UI 버튼 후순위)
- [x] 면책 안내 표시

### F10. 리포트 저장 (PDF) ⭐ Premium ✅
- [x] `@react-pdf/renderer` 설치
- [x] ReportPDF 컴포넌트 (표지, 요약, 대화, 차트)
- [x] 한글 폰트 설정 (Spoqa Han Sans Neo)
- [x] 차트 → 이미지 캡처 (`html2canvas`)
- [x] PDF 다운로드 트리거 (챗봇 명령 + UI 버튼)
- [x] 면책 조항 포함
- [ ] PDF 생성 5초 이내 확인 (브라우저 테스트 필요)

---

## 공통 / 비기능 요구사항

### 성능
- [ ] SSE 첫 토큰 2초 이내
- [ ] 지도 폴리곤 로딩 1초 이내
- [ ] Redis 캐싱 동작 확인 (Phase 1B~)

### 보안
- [ ] Rate Limiting (IP 기반 분당 30회)
- [ ] API 키 환경 변수 관리 (.env, 노출 방지)
- [ ] 입력 검증 (XSS, SQL Injection 방지)

### UX
- [ ] 반응형 레이아웃 (데스크탑 우선, 모바일 기본 대응)
- [ ] 데이터 기준 시점 항상 표시
- [ ] 에러 상태 사용자 친화적 메시지
- [ ] 로딩 스피너/스켈레톤

### 코드 품질
- [ ] TypeScript strict 모드
- [ ] ESLint + Prettier 설정
- [ ] Python mypy + ruff 설정
- [ ] API 엔드포인트 테스트 (pytest)
- [ ] 주요 컴포넌트 단위 테스트

### CI/CD
- [ ] GitHub Actions 워크플로우
- [ ] PR 시 lint + test 자동 실행
- [ ] Docker 이미지 빌드 확인

---

## 검토 기준

### Phase 1A 검토 (Mock E2E)
| 검토 항목 | 확인 사항 |
|-----------|-----------|
| E2E 동작 | 지도 클릭 → Agent 응답 → Card 렌더링 전체 흐름 |
| Agent 품질 | Mock 데이터 기반으로 적절한 Tool 선택 + 자연어 해석 |
| UI/UX | SplitPanel, 스트리밍 응답, Card 렌더링 자연스러움 |
| 에러 처리 | Agent/API 실패 시 graceful fallback |

### Phase 1B 검토 (Real Data)
| 검토 항목 | 확인 사항 |
|-----------|-----------|
| 데이터 정확성 | DB 데이터와 화면 표시 값 일치 |
| 응답 속도 | SSE 첫 토큰 2초, 지도 로딩 1초 이내 |
| 일관성 | 모든 응답에 데이터 기준 분기 명시 |
| 캐싱 | Redis 캐싱 정상 동작 |

---

*작성일: 2026-03-24*
*수정일: 2026-03-25 — Mock-first E2E 전략으로 Phase 재구성, Phase 0을 Phase 1B로 이동*
*총 체크 항목: 약 150개*
