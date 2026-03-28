# 현재 진행 상황

> 최종 갱신: 2026-03-28 (Card UI 4종 E2E 검증 완료, Phase 1A 핵심 목표 달성)
> **Phase 1A: Mock E2E — 지도 + AI 챗봇 + Card UI 렌더링 전체 흐름 완료 ✅**

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

#### 카카오맵 SDK 로딩 해결 + 지도-챗봇 연동 (2026-03-27)
- [x] **SDK 로드 차단 해결**: Next.js API Route `/api/kakao-sdk` 프록시 생성 → SDK를 same-origin으로 제공
- [x] MapContainer.tsx: `fetch('/api/kakao-sdk')` → inline `<script>` 주입 방식으로 전환
- [x] MapContainer.tsx: SDK 내부 appkey 추출을 위한 더미 `<script src="dapi.kakao.com/...">` 태그 삽입
- [x] layout.tsx: 기존 `<Script>` 태그 제거 (프록시로 대체)
- [x] chat.py: `district_code` 없이도 메시지 텍스트에서 상권명 자동 인식 → `map_cmd` 발생 (지도 이동)
- [x] chat.py: `map_cmd` zoom level 5→4로 조정 (더 확대된 뷰)
- [x] **Playwright E2E 검증 완료**: 강남역, 홍대입구, 명동 상권 — 자연어 질의 → AI 응답 → 지도 이동 확인

#### Card UI 4종 E2E 연동 완료 (2026-03-28) ✅
- [x] `district_summary.py` 신규 — Mock 데이터(유동인구+매출+점포) 집계 → SummaryCardData 형태 반환
- [x] `graph.py` — `get_district_summary_tool` Tool wrapper 추가 + TOOLS 리스트 등록
- [x] `graph.py` — LLM을 Gemini 2.5 Flash → **Gemini 2.5 Pro**로 변경 (도구 선택 정확도 향상)
- [x] `system.py` — 도구 선택 규칙 강화 (요약 요청 시 `get_district_summary` 단일 호출 가이드)
- [x] `chat.py` — 요약 요청 패턴 감지(regex) → `get_district_summary` 직접 호출 → card SSE 이벤트 emit
  - LLM 도구 선택에 의존하지 않는 확실한 방식으로 SummaryCard 보장
- [x] `graph.py` — `_TOOL_CARD_MAP`에서 summary 제거 (chat.py에서 직접 emit하므로 중복 방지)
- [x] **Playwright E2E 검증 — 4종 Card 모두 통과**:
  - ✅ "강남역 요약해줘" → **SummaryCard**: 유동인구 바차트(0~23시) + Top 5 업종 + 폐업률(5.3%, 평균 대비)
  - ✅ "강남역이랑 홍대 비교해줘" → **CompareCard**: 비교표(유동인구/연령/점포/매출/폐업률/상태) + 판정 컬럼
  - ✅ "강남역에서 뭐하면 좋을까?" → **RecommendCard**: 업종 Top 5 점수바 + 점포당 매출/매칭률/경쟁밀집도/창업비용
  - ✅ "강남역 위험해?" → **RiskCard**: 안정성 게이지(72점/양호) + 업종별 생존 기간 바 + 위험 업종 + 분기별 개폐업 추이 차트

### 해결 완료 ✅

#### 카카오맵 SDK 로딩 이슈 — 해결 (2026-03-27)
- **증상**: 지도 영역에 "지도 로딩 중..." 표시, 맵 렌더링 안됨
- **원인**: 외부 도메인(`dapi.kakao.com`) 스크립트가 `net::ERR_BLOCKED_BY_ORB` / `net::ERR_FAILED`로 차단
- **해결 방법**:
  1. Next.js API Route `/api/kakao-sdk`로 SDK 프록시 생성 (서버 측에서 카카오 서버로 fetch)
  2. MapContainer에서 `fetch('/api/kakao-sdk')` → inline `<script>` 주입
  3. SDK 내부 appkey 추출을 위한 더미 `<script src="dapi.kakao.com/...">` 태그 삽입
- **검증**: Playwright 브라우저 자동화로 지도 로딩 + AI 응답 + 지도 이동 E2E 확인 완료

#### Card UI 렌더링 이슈 — 해결 (2026-03-28)
- **증상**: 채팅에서 텍스트 응답만 출력, Card UI가 렌더링되지 않음
- **원인**:
  1. `_TOOL_CARD_MAP`에 `summary` 미등록 → 기본 요약 시 card 이벤트 미발송
  2. Gemini Flash/Pro가 시스템 프롬프트의 도구 선택 가이드를 무시하고 개별 Tool 4종 호출
- **해결 방법**:
  1. `get_district_summary` Tool 신규 생성 (유동인구+매출+점포 집계)
  2. `chat.py`에서 요약 요청 패턴 감지 → card 이벤트 직접 emit (LLM 의존 제거)
  3. compare/recommend/risk는 기존 `_TOOL_CARD_MAP` 매커니즘으로 정상 동작
- **검증**: Playwright E2E로 4종 Card 모두 렌더링 확인

### 남은 작업 (Phase 1A 마무리)

#### 폴리곤 클릭 → 자동 요약 (선택적 개선)
- [ ] 지도에서 폴리곤 클릭 시 `districtStore.selected` 설정 → `useMapSync`가 자동 질의 → SummaryCard
  - 현재: 채팅에서 "강남역 요약해줘" 입력하면 동작
  - 개선: 폴리곤 직접 클릭만으로도 SummaryCard 자동 표시
- [ ] 대화 컨텍스트 유지 — 이전 대화에서 선택된 상권을 후속 질문에서 자동 참조
  - 현재: 매 질문마다 상권명을 포함해야 함 ("강남역 위험해?" O, "위험해?" X)

#### LLM 전환 (선택)
- [ ] Anthropic API 크레딧 충전 후 `LLM_PROVIDER=anthropic`으로 전환 테스트
- [ ] 현재 Gemini 2.5 Pro로 검증 완료 — Claude 전환 시 응답 품질 비교

---

---

## Next Items (우선순위 순)

### 1. Phase 1A 마무리 — 폴리곤 클릭 자동 요약 + 대화 컨텍스트
- 폴리곤 클릭 → `districtStore.selected` → `useMapSync` 자동 질의 → SummaryCard (현재는 채팅 입력 필요)
- 대화 컨텍스트 유지: 이전에 선택된 상권을 후속 질문에서 자동 참조

### 2. Phase 1B — Real Data 연결
- Docker Compose 기동 (PostGIS, Redis)
- 서울 열린데이터 / data.go.kr API 키 발급 및 1개 분기 적재
- `USE_MOCK=false` 전환 후 실제 데이터 기반 동작 확인
- Redis 캐시 활성화 + 뷰포트 기반 폴리곤 로딩

### 3. UX/UI 개선
- 반응형 레이아웃 (모바일 기본 대응)
- 에러 상태 UX (로딩 스피너, 스켈레톤)
- 데이터 기준 시점 일관 표시

### 4. Phase 2 — 프리미엄 기능
- Tier 게이팅 인프라 (OAuth2, 결제)
- 비교모드 복수 상권 하이라이트

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

- Card UI 구현 계획: `docs/plan/card-ui-integration.md`
- E2E 테스트 상세 보고서: `docs/status/e2e_test_report.md`
- 체크리스트: `docs/spec/checklist.md`
- 아키텍처: `docs/architecture/overall-architecture.md`
