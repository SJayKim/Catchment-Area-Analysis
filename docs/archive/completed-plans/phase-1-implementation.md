# Phase 1 구현 계획 — Mock-First E2E → Real Data

> 작성일: 2026-03-25
> 수정일: 2026-03-25 — Mock-first 전략으로 재구성

## 핵심 전략 변경

**기존**: Phase 0(DB/ETL) → Phase 1(MVP) 순서로, 데이터가 준비되어야 기능 확인 가능
**변경**: **Phase 1A(Mock E2E)** → **Phase 1B(Real Data)** 순서로, Mock 데이터로 Agent + Chat UI 흐름을 먼저 검증

### 왜 Mock-First인가?
- 실제 공공데이터 API 키 발급/적재 없이도 **Agent 로직 + UI/UX 흐름을 즉시 확인** 가능
- Chat SSE 스트리밍, ReAct 루프, Card 렌더링 등 **핵심 사용자 경험을 빠르게 검증**
- Mock → Real 전환은 Tool 내부 구현만 교체하면 됨 (인터페이스 동일)

---

## Phase 1A — E2E Mock (DB 없이 동작)

### 목표
"지도에서 상권 선택 → AI 챗봇이 Mock 데이터 기반으로 분석 응답" 전체 흐름이 브라우저에서 동작

### 범위

#### 1. Backend: Mock Tool 레이어
- 기존 7개 Agent Tool의 DB 쿼리 부분을 **Mock 데이터 반환**으로 대체
- `server/server/agent/tools/mock_data.py` — 상권별 Mock 데이터셋 (3~5개 상권)
- Mock 데이터는 실제 서울 상권 데이터 형태를 모방 (강남역, 홍대, 건대입구 등)
- Tool 인터페이스(입출력 스키마)는 변경 없음 → 나중에 Real DB로 교체 용이
- **DB 의존성 제거**: `USE_MOCK=true` 환경 변수로 Mock/Real 전환
- Redis 없이도 동작 (캐싱 skip 또는 in-memory fallback)

#### 2. Backend: 최소 인프라
- FastAPI 단독 실행 (DB, Redis 없이)
- `POST /api/chat` SSE 스트리밍 정상 동작
- `GET /api/districts` — Mock 상권 목록 반환
- `GET /api/map-data/polygons` — Mock 폴리곤 GeoJSON 반환 (하드코딩 3~5개)
- CORS 설정 확인 (Next.js dev → FastAPI)

#### 3. Frontend: 전체 UI 동작
- Kakao Map 렌더링 + Mock 폴리곤 오버레이
- 폴리곤 클릭 → 상권 선택 → 자동 Agent 쿼리
- ChatPanel에서 자연어 입력 → SSE 스트리밍 응답 수신
- thinking/tool/text/card/suggestion/done 이벤트 처리
- SummaryCard, CompareCard, RecommendCard, RiskCard 렌더링
- SuggestionChips 클릭 → 추가 질문
- SplitPanel 리사이즈 동작

#### 4. Agent: 전체 ReAct 루프
- LangGraph ReAct Agent가 Mock Tool을 호출하며 정상 동작
- Claude API 호출 → Tool 선택 → Mock 데이터 반환 → 응답 생성
- 시스템 프롬프트 기반 한국어 상권 분석 컨설턴트 역할
- 복수 Tool 연쇄 호출 (예: 유동인구 + 매출 → 종합 분석)

### 실행 방법 (Phase 1A)
```bash
# Backend (DB/Redis 없이)
cd server
USE_MOCK=true uvicorn server.main:app --reload --port 8000

# Frontend
cd frontend
npm run dev
```

### Phase 1A 완료 기준
- [ ] 브라우저에서 지도 + 채팅 화면 로드
- [ ] Mock 폴리곤 3~5개 지도에 표시
- [ ] 폴리곤 클릭 시 ChatPanel에 자동 요약 요청 전송
- [ ] Agent가 Mock Tool 호출 → SSE 스트리밍 응답 정상 수신
- [ ] SummaryCard (차트 포함) 정상 렌더링
- [ ] 자연어로 "홍대랑 비교해줘" → CompareCard 렌더링
- [ ] "여기서 뭐하면 좋을까?" → RecommendCard 렌더링
- [ ] "이 자리 위험해?" → RiskCard 렌더링
- [ ] SuggestionChips 클릭 동작
- [ ] 에러 시 graceful fallback 메시지

---

## Phase 1B — Real Data 연결

### 목표
Mock 데이터를 실제 PostgreSQL + PostGIS 데이터로 교체

### 범위

#### 1. 인프라 (기존 Phase 0)
- Docker Compose 기동 (PostGIS, Redis)
- Alembic 마이그레이션 실행
- 공공데이터 API 키 발급
- ETL 파이프라인으로 1개 분기 데이터 적재

#### 2. Tool 전환
- `USE_MOCK=false`로 전환
- 각 Tool 내부에서 실제 DB 쿼리 실행
- Redis 캐싱 활성화

#### 3. 지도 데이터
- `GET /api/map-data/polygons` → PostGIS 실제 폴리곤 반환
- 뷰포트 기반 폴리곤 로딩 (ST_Intersects)
- 검색 API 실제 DB 조회

### Phase 1B 완료 기준
- [ ] `docker compose up`으로 전체 서비스 기동
- [ ] 1개 분기 데이터 적재 완료
- [ ] 실제 상권 폴리곤 지도 표시 (서울 전체)
- [ ] Agent Tool이 실제 DB 데이터 기반으로 응답
- [ ] Redis 캐싱 동작 확인
- [ ] 첫 토큰 2초 이내 응답 확인

---

## 파일 구조

### Phase 1A에서 추가/수정할 파일

```
server/server/
├── agent/tools/
│   └── mock_data.py              # ✨ 신규: Mock 데이터셋
├── api/routes/
│   ├── districts.py              # 수정: Mock 모드 분기
│   └── map_data.py               # 수정: Mock 폴리곤 반환
├── config.py                     # 수정: USE_MOCK 설정 추가
└── main.py                       # 수정: Mock 모드일 때 DB 연결 skip
```

### Mock → Real 전환 포인트

| 컴포넌트 | Mock 모드 | Real 모드 |
|----------|-----------|-----------|
| Agent Tools | `mock_data.py`에서 하드코딩 반환 | DB 쿼리 (repository 패턴) |
| Districts API | Mock 리스트 반환 | PostGIS 조회 |
| Polygons API | Mock GeoJSON 반환 | ST_Intersects 쿼리 |
| 캐싱 | skip (또는 dict) | Redis TTL 24h |
| DB 연결 | 불필요 | SQLAlchemy + Alembic |

---

## 기술 의존성

### Phase 1A (최소)
- Python: fastapi, langgraph, langchain-anthropic, sse-starlette
- Node: next, react, zustand, recharts, tailwindcss
- 외부: Anthropic API 키, Kakao Map API 키

### Phase 1B (추가)
- Docker: postgis/postgis:16-3.4, redis:7-alpine
- Python: sqlalchemy, alembic, asyncpg, redis
- 데이터: 서울 열린데이터 API 키, data.go.kr API 키
