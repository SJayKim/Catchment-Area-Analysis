# 현재 진행 상황

> 최종 갱신: 2026-03-26 (브라우저 E2E 테스트 — 카카오맵 로딩 이슈 디버깅 중)
> **Phase 1A: Mock E2E — 백엔드 완료, 프론트엔드 카카오맵 로딩 이슈 해결 중**

---

## 전략 변경 요약

**기존**: Phase 0(DB/ETL) → Phase 1(MVP) → Phase 2(Premium)
**변경**: **Phase 1A(Mock E2E)** → Phase 1B(Real Data) → Phase 2(Premium)

---

## Phase 1A — E2E Mock ⬅️ 현재 단계

### 목표
데이터 없이 "지도 클릭 → AI Agent 응답 → Card 렌더링" 전체 흐름 동작 확인

### 완료된 작업

#### 코드 구현 ✅
- [x] FastAPI 프로젝트 구조 (main, config, routes, agent)
- [x] LangGraph ReAct Agent 그래프 정의 (create_react_agent)
- [x] 시스템 프롬프트 (한국어 상권 분석 컨설턴트)
- [x] POST /api/chat SSE 스트리밍 엔드포인트
- [x] Agent Tools 7종 (유동인구, 매출, 점포, 인구, 비교, 추천, 이력)
- [x] Next.js 14 프로젝트 (App Router, TypeScript, Tailwind)
- [x] Kakao Map + DistrictLayer + MapControls
- [x] ChatPanel + MessageList + MessageBubble + ChatInput
- [x] SplitPanel (resizable), Toolbar, StatusBar
- [x] useChat 훅 (SSE 클라이언트)
- [x] useMapSync (지도↔채팅 동기화)
- [x] SummaryCard, CompareCard, RecommendCard, RiskCard, InlineChart
- [x] Zustand stores (district, map, chat), SuggestionChips

#### Mock 데이터 레이어 ✅
- [x] `mock_data.py` — 5개 상권 (강남역, 홍대, 건대, 명동, 서울역)
- [x] Mock 유동인구/매출/점포/인구/이력 데이터셋
- [x] Mock 상권 폴리곤 GeoJSON (실제 서울 좌표)
- [x] `USE_MOCK` 환경변수 분기 (config.py, 각 Tool, API routes)
- [x] Mock 모드에서 DB/Redis 연결 없이 기동 확인

#### 백엔드 E2E 검증 ✅ (2026-03-25)
- [x] API 엔드포인트 정상: /health, /api/districts, /api/map-data/polygons, /api/chat
- [x] Agent ReAct Loop: 질문 유형별 Tool 선택 → 실행 → 결과 종합 → 응답 생성
- [x] SSE 스트리밍: thinking → tool → text → card → suggestion → done 흐름 정상
- [x] TEST 1 — 강남역 종합분석: 4 Tools 호출, 1,177자 응답 (7.5s)
- [x] TEST 2 — 홍대 vs 건대 비교: compare_districts 정상, 상권코드 정확 매핑
- [x] TEST 3 — 명동 업종추천+리스크: 2 Tools 조합, 면책 안내 포함

#### 프론트엔드 통합 테스트 ✅ (2026-03-26)
- [x] 프론트엔드+백엔드 동시 기동 (localhost:3000 + localhost:8000)
- [x] Next.js API rewrite 프록시 정상 동작 (/api/* → backend)
- [x] 프론트엔드 TypeScript 빌드 성공 (에러 0건)
- [x] SSE 스트리밍: 프록시 통해 thinking → tool → text → card → suggestion → done 정상
- [x] compare/recommend/risk Card 이벤트 SSE 전달 확인

#### 버그 수정 — 백엔드 (2026-03-25~26)
- [x] config.py: `.env` 경로를 프로젝트 루트 절대경로로 수정
- [x] config.py: `extra="ignore"` 추가 (프론트 전용 env 변수 ValidationError 해결)
- [x] system.py: 시스템 프롬프트에 상권코드 목록 명시 (Agent 코드 추측 방지)
- [x] graph.py: `LLM_PROVIDER` 설정으로 Gemini/Anthropic 동적 전환 지원
- [x] graph.py: `on_tool_end` 이벤트 캡처하여 card SSE 이벤트 emit 추가 (compare/recommend/risk)
- [x] chat.py: 상권 코드 제공 시 `map_cmd` 이벤트 emit 추가 (채팅→지도 위치 연동)

#### 버그 수정 — 프론트엔드 (2026-03-26)
- [x] api.ts `fetchPolygons`: GeoJSON FeatureCollection → PolygonFeature[] 변환 추가
- [x] api.ts `fetchPolygons`: 백엔드 `bounds` 파라미터 형식에 맞게 쿼리스트링 수정
- [x] api.ts `fetchDistricts`: 백엔드 응답 `{total, items}` → `District[]` 변환 + 필드명 매핑 추가
- [x] CompareCard.tsx: `districtNames` 없을 때 `district_name` 필드에서 이름 가져오도록 수정
- [x] RecommendCard.tsx: `startup_cost` 만원 단위 → 원 단위 변환 수정
- [x] types.ts: `CompareCardData`에 `district_name` 필드 추가 (TS 에러 해결)
- [x] MapContainer.tsx: React Strict Mode 호환 — `initializedRef` 제거, SDK 재로드 로직 개선
- [x] MapContainer.tsx: `mapReady` state 추가 → DistrictLayer 조건부 렌더링
- [x] MapContainer.tsx: Next.js `<Script>` 컴포넌트로 SDK 로딩 방식 전환
- [x] DistrictLayer.tsx: `renderPolygons`를 `useCallback`으로 래핑, 맵 준비 후에만 마운트
- [x] frontend/.env.local: Kakao Map API 키 설정

### 진행 중 🔧

#### 카카오맵 SDK 로딩 이슈 (2026-03-26)
- **증상**: 지도 영역에 "지도 로딩 중..." 표시, 맵 렌더링 안됨
- **디버깅 결과**:
  - `curl`로 SDK URL 접근 시 정상 응답 (200 OK)
  - 브라우저에서 `<script>` 태그로 로드 시 `onerror` 발생
  - 프로토콜 `//` → `https://`로 변경 후에도 동일 현상
  - Next.js `<Script strategy="afterInteractive">` 방식으로 전환 후에도 동일
- **추정 원인**: 카카오 개발자 콘솔에서 JavaScript 키의 허용 도메인에 `localhost`가 미등록
  - 카카오 API 키는 등록된 도메인에서만 SDK 로드 허용
  - https://developers.kakao.com → 내 애플리케이션 → 플랫폼 → Web → 사이트 도메인에 `http://localhost:3000` 추가 필요
- **대안**: API 키 문제 확인 불가 시, 새 카카오 앱 생성 후 키 재발급 고려

### 남은 작업 (Phase 1A 최종 확인)

#### 카카오맵 로딩 해결 후
- [ ] 브라우저에서 지도 + 채팅 화면 정상 로드 (Kakao Map 렌더링)
- [ ] 폴리곤 클릭 → Agent 자동 요약 → 텍스트 응답 렌더링
- [ ] "홍대랑 비교해줘" → CompareCard 렌더링
- [ ] "뭐하면 좋을까?" → RecommendCard 렌더링
- [ ] "이 자리 위험해?" → RiskCard 렌더링
- [ ] SuggestionChips 클릭 → 추가 질문 동작

#### LLM 전환 (선택)
- [ ] Anthropic API 크레딧 충전 후 `LLM_PROVIDER=anthropic`으로 전환 테스트
- [ ] 현재 Gemini 2.5 Flash로 검증 완료 — Claude 전환 시 응답 품질 비교

---

## Phase 1B — Real Data 연결 (Phase 1A 완료 후)

### 기존 구현 (재활용)
- [x] `docker-compose.yml` (PostGIS 16, Redis 7, backend, frontend)
- [x] SQLAlchemy 모델 9개 테이블 + Alembic 마이그레이션
- [x] ETL 스켈레톤 (BaseCollector, SeoulOpenDataCollector, Transformers, DataLoader, CLI)

### 남은 작업
- [ ] 서울 열린데이터 / data.go.kr API 키 발급 및 연동 테스트
- [ ] 1개 분기 전체 적재 + 검증
- [ ] data.go.kr 소상공인시장진흥공단 collector 구현
- [ ] `USE_MOCK=false` 전환 후 실제 데이터 기반 동작 확인
- [ ] Redis 캐시 활성화 (TTL 24h)
- [ ] 뷰포트 기반 폴리곤 로딩 (ST_Intersects)
- [ ] 실제 데이터 기반 Agent 응답 정확성 확인

---

## Phase 2 — 프리미엄 (Phase 1B 완료 후)

### 코드 작성 완료
- [x] F04 업종 심층 분석 (기존 Tool에 category 필터 지원)
- [x] F05 상권 비교 (compare_districts Tool + CompareCard)
- [x] F07 업종 추천 (recommend_business Tool + RecommendCard)
- [x] F08 이력/리스크 (get_store_history Tool + RiskCard)

### 미완료
- [ ] Tier 게이팅 인프라 (OAuth2 인증, 결제 연동)
- [ ] category_aliases 퍼지 검색 테이블 (pg_trgm)
- [ ] 지도 비교모드에서 복수 상권 다른 색상 하이라이트
- [ ] 비교모드에서 상권 선택 시 자동 비교 쿼리 전송

---

## Phase 3 — 확장 (미착수)
- [ ] F06 시간대별 히트맵 (deck.gl + TimeSlider)
- [ ] F09 간이 매출 시뮬레이션 (simulate_revenue Tool)
- [ ] F10 리포트 저장 (PDF)

---

## 참고

- E2E 테스트 상세 보고서: `docs/status/e2e_test_report.md`
- 체크리스트: `docs/spec/checklist.md`
- 아키텍처: `docs/architecture/overall-architecture.md`
