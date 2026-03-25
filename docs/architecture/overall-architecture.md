# Overall Architecture — 상권분석 AI 서비스

> 지도 + AI 챗봇 기반 상권분석 서비스의 전체 시스템 아키텍처
> 기준 문서: `a_drafts/merged_features.md` (Merged v1.0)

---

## 1. 시스템 전체 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                             │
│  ┌─────────────────────────┬───────────────────────────────────┐    │
│  │     Map Panel (Left)    │       Chat Panel (Right)          │    │
│  │  ┌───────────────────┐  │  ┌─────────────────────────────┐  │    │
│  │  │  Kakao Map SDK    │  │  │  Natural Language Input     │  │    │
│  │  │  + Polygon Layer  │  │  │  + Streaming Response       │  │    │
│  │  │  + Heatmap Layer  │  │  │  + Rich Cards (chart/table) │  │    │
│  │  │  + Marker Layer   │  │  │  + Suggestion Chips         │  │    │
│  │  └───────────────────┘  │  └─────────────────────────────┘  │    │
│  └─────────────────────────┴───────────────────────────────────┘    │
│                         Next.js 14 (App Router)                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  REST + WebSocket (SSE)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        API GATEWAY (FastAPI)                        │
│  /api/chat    /api/districts    /api/reports    /api/map-data       │
└──────────┬──────────────────────────────────────────────────────────┘
           │
     ┌─────┴──────────────────────────────────┐
     ▼                                        ▼
┌──────────────────┐              ┌──────────────────────────────────┐
│   AI Agent Layer │              │         Data Layer               │
│  (LangGraph)     │              │                                  │
│  ┌────────────┐  │   tool call  │  ┌────────────┐ ┌────────────┐   │
│  │  ReAct     │──┼─────────────►│  │ PostgreSQL │ │   Redis    │   │
│  │  Agent     │  │              │  │ + PostGIS  │ │  (Cache)   │   │
│  │  Loop      │  │              │  └────────────┘ └────────────┘   │
│  └────────────┘  │              │  ┌────────────────────────────┐  │
│  ┌────────────┐  │              │  │  Public Data APIs          │  │
│  │ Langfuse   │  │              │  │  (서울열린데이터/data.go.kr)│  │
│  │ (Tracing)  │  │              │  └────────────────────────────┘  │
│  └────────────┘  │              └──────────────────────────────────┘
└──────────────────┘
```

---

## 2. 기술 스택

### 2.1 Frontend

| 항목 | 기술 | 선정 이유 |
|------|------|-----------|
| Framework | **Next.js 14** (App Router, TypeScript) | SSR/SSG 지원, API Route로 BFF 역할 가능 |
| Map | **Kakao Map SDK** | 한국 지도 데이터 정확도, 주소 검색 API, 국내 서비스 최적화 |
| Map Visualization | **deck.gl** | Heatmap/Polygon 등 고성능 지도 레이어 렌더링 |
| Chat UI | **자체 구현** (React Component) | 스트리밍 응답, Rich Card, 차트 임베딩 등 커스텀 요구사항 |
| Charts | **Recharts** | React 네이티브, 경량, 챗봇 내 인라인 차트 |
| State | **Zustand** | 경량, 지도-챗봇 간 상태 동기화 |
| Styling | **Tailwind CSS** + **shadcn/ui** | Figma-like 미니멀 디자인 구현에 적합 |
| PDF Export | **@react-pdf/renderer** | F10 리포트 저장 기능 |

### 2.2 Backend

| 항목 | 기술 | 선정 이유 |
|------|------|-----------|
| API Server | **FastAPI** (Python 3.12) | 비동기 지원, AI/LangGraph 생태계와 동일 언어, 자동 API 문서 |
| AI Agent | **LangGraph** | ReAct 패턴 네이티브 지원, Tool 호출 그래프 정의, 상태 관리 |
| LLM | **Claude API** (Anthropic) | 한국어 성능, Tool Use 지원, 긴 컨텍스트 |
| Observability | **Langfuse** | LLM 호출 트레이싱, 비용 추적, 프롬프트 버전 관리 |
| Task Queue | **Celery** + **Redis** | 데이터 ETL 배치 작업, 리포트 생성 비동기 처리 |

### 2.3 Database

| 항목 | 기술 | 선정 이유 |
|------|------|-----------|
| Primary DB | **PostgreSQL 16 + PostGIS** | 상권 폴리곤 저장/공간 쿼리 (ST_Contains, ST_Within 등), 매출/인구 시계열 |
| Cache | **Redis** | 공공 API 응답 캐싱 (분기 갱신이므로 TTL 길게), 세션 관리 |
| File Storage | **S3 (or MinIO)** | 생성된 PDF 리포트 저장 |

### 2.4 Infra / DevOps

| 항목 | 기술 |
|------|------|
| Container | Docker + Docker Compose (개발), Kubernetes (운영) |
| CI/CD | GitHub Actions |
| Hosting | AWS (ECS or EKS) 또는 GCP (Cloud Run) |
| Monitoring | Prometheus + Grafana (시스템), Langfuse (AI) |

---

## 3. AI Agent 아키텍처 (LangGraph ReAct)

### 3.1 Agent 그래프 구조

```
                    ┌─────────────┐
                    │   START     │
                    │ (user query │
                    │  + context) │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
              ┌────►│   REASON    │◄────┐
              │     │ (LLM 판단)  │     │
              │     └──────┬──────┘     │
              │            │            │
              │     ┌──────┴──────┐     │
              │     │   분기 판단  │     │
              │     └──┬───────┬──┘     │
              │        │       │        │
              │   tool call  direct     │
              │        │    response    │
              │        ▼       │        │
              │  ┌──────────┐  │        │
              │  │   ACT    │  │        │
              │  │ (Tool    │  │        │
              │  │  실행)   │  │        │
              │  └────┬─────┘  │        │
              │       │        │        │
              │       ▼        │        │
              │  ┌──────────┐  │        │
              └──┤ OBSERVE  │  │        │
                 │ (결과 해석)├──┘       │
                 └──────────┘           │
                       │                │
                  추가 tool 필요 ────────┘
                       │
                       ▼
                 ┌──────────┐
                 │   END    │
                 │ (최종 응답)│
                 └──────────┘
```

### 3.2 LangGraph 상태 정의

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph
from langfuse.callback import CallbackHandler as LangfuseHandler

class AgentState(TypedDict):
    # 대화 컨텍스트
    messages: list                # 전체 대화 이력
    selected_district_code: str   # 현재 선택된 상권코드
    selected_district_name: str   # 상권명
    selected_category_code: str   # 선택된 업종코드 (있을 경우)

    # Agent 내부 상태
    tool_calls: list              # 호출한 Tool 목록
    tool_results: list            # Tool 반환 데이터
    iteration_count: int          # ReAct 루프 횟수 (무한루프 방지)

    # 응답 제어
    response_type: str            # "text" | "card" | "chart" | "comparison"
    map_commands: list            # 지도 조작 명령 (하이라이트, 히트맵 등)
```

### 3.3 Agent Tools

각 Tool은 LangGraph의 `@tool` 데코레이터로 정의하며, 내부적으로 DB 또는 공공 API를 조회합니다.

| Tool 이름 | 기능 | 입력 | 출력 | 사용 기능 |
|-----------|------|------|------|-----------|
| `get_floating_population` | 유동인구 조회 | 상권코드, 기간 | 시간대/요일/연령/성별 유동인구 | F3, F5, F6 |
| `get_estimated_sales` | 추정매출 조회 | 상권코드, 업종코드 | 업종별 추정 매출액, 추이 | F3, F4, F9 |
| `get_store_info` | 점포 현황 조회 | 상권코드, 업종코드 | 점포 수, 개폐업 현황 | F3, F4, F7 |
| `get_population_info` | 상주/직장인구 조회 | 상권코드 | 상주/직장인구, 연령/성별 분포 | F3, F7 |
| `get_store_history` | 점포 이력 조회 | 상권코드 | 과거 업종 변동 이력 | F8 |
| `compare_districts` | 상권 비교 | 상권코드 2~3개 | 주요 지표 비교표 | F5 |
| `recommend_business` | 업종 추천 | 상권코드, 조건(선택) | 추천 업종 Top 5 + 근거 | F7 |
| `simulate_revenue` | 매출 시뮬레이션 | 상권코드, 업종, 객단가 등 | 예상 월매출 범위 | F9 |
| `update_map_view` | 지도 시각화 제어 | 상권코드, 레이어 타입 | 지도 명령 (highlight/heatmap) | F1, F6 |

### 3.4 Langfuse 통합

```python
from langfuse.callback import CallbackHandler

langfuse_handler = CallbackHandler(
    public_key="...",
    secret_key="...",
    host="https://langfuse.your-domain.com"
)

# LangGraph 실행 시 콜백으로 주입
result = agent_graph.invoke(
    state,
    config={"callbacks": [langfuse_handler]}
)
```

**추적 항목**:
- 각 ReAct 루프의 reasoning/tool_call/observation
- Tool별 latency, 성공/실패율
- LLM 토큰 사용량 및 비용
- 사용자 질문 유형 분류 (조회/비교/추천/시뮬레이션)
- 프롬프트 버전별 응답 품질 A/B 테스트

---

## 4. 데이터 아키텍처

### 4.1 데이터 흐름

```
┌─────────────────────┐     Batch ETL (분기별)     ┌──────────────────┐
│  공공데이터 API       │ ──────────────────────────► │  PostgreSQL      │
│  ├ 서울 열린데이터    │     Celery Worker          │  + PostGIS       │
│  ├ data.go.kr        │                            │                  │
│  └ 소상공인진흥공단   │                            │  ┌──────────┐   │
└─────────────────────┘                            │  │ 상권 영역  │   │
                                                   │  │ (polygon) │   │
┌─────────────────────┐     실시간 조회 (캐시)      │  ├──────────┤   │
│  Agent Tool 호출     │ ◄──────────────────────── │  │ 유동인구  │   │
│  (get_floating_pop,  │         Redis              │  ├──────────┤   │
│   get_sales, ...)    │         Cache              │  │ 추정매출  │   │
└─────────────────────┘                            │  ├──────────┤   │
                                                   │  │ 점포정보  │   │
                                                   │  ├──────────┤   │
                                                   │  │ 상주인구  │   │
                                                   │  └──────────┘   │
                                                   └──────────────────┘
```

### 4.2 DB 스키마 (핵심 테이블)

```sql
-- 상권 영역 (공간 데이터)
CREATE TABLE districts (
    district_code   VARCHAR(20) PRIMARY KEY,
    district_name   VARCHAR(100) NOT NULL,
    district_type   VARCHAR(20) NOT NULL,      -- 골목상권/발달상권/전통시장/행정동
    boundary        GEOMETRY(POLYGON, 4326),   -- PostGIS 폴리곤
    center_point    GEOMETRY(POINT, 4326),     -- 중심 좌표
    data_quarter    VARCHAR(10) NOT NULL,      -- 데이터 기준 분기 (2025Q4)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_districts_boundary ON districts USING GIST(boundary);

-- 유동인구
CREATE TABLE floating_population (
    id              BIGSERIAL PRIMARY KEY,
    district_code   VARCHAR(20) REFERENCES districts(district_code),
    quarter         VARCHAR(10) NOT NULL,       -- 2025Q4
    day_type        VARCHAR(10) NOT NULL,       -- weekday/weekend
    time_slot       SMALLINT NOT NULL,          -- 0~23
    age_group       VARCHAR(10) NOT NULL,       -- 10s/20s/30s/40s/50s/60s+
    gender          VARCHAR(1) NOT NULL,        -- M/F
    population      INTEGER NOT NULL
);
CREATE INDEX idx_fp_district_quarter ON floating_population(district_code, quarter);

-- 추정 매출
CREATE TABLE estimated_sales (
    id              BIGSERIAL PRIMARY KEY,
    district_code   VARCHAR(20) REFERENCES districts(district_code),
    category_code   VARCHAR(20) NOT NULL,       -- 업종 코드
    category_name   VARCHAR(100) NOT NULL,
    quarter         VARCHAR(10) NOT NULL,
    monthly_sales   BIGINT,                     -- 월 추정 매출 (원)
    sales_count     INTEGER,                    -- 건수
    weekday_sales   BIGINT,
    weekend_sales   BIGINT
);
CREATE INDEX idx_es_district_category ON estimated_sales(district_code, category_code, quarter);

-- 점포 정보
CREATE TABLE stores (
    id              BIGSERIAL PRIMARY KEY,
    district_code   VARCHAR(20) REFERENCES districts(district_code),
    category_code   VARCHAR(20) NOT NULL,
    category_name   VARCHAR(100) NOT NULL,
    quarter         VARCHAR(10) NOT NULL,
    store_count     INTEGER,                    -- 점포 수
    open_count      INTEGER,                    -- 개업 수
    close_count     INTEGER,                    -- 폐업 수
    franchise_count INTEGER                     -- 프랜차이즈 수
);

-- 점포 이력 (F8: 이력/실패 분석용)
CREATE TABLE store_history (
    id              BIGSERIAL PRIMARY KEY,
    district_code   VARCHAR(20) REFERENCES districts(district_code),
    address         VARCHAR(200),
    category_code   VARCHAR(20),
    category_name   VARCHAR(100),
    open_date       DATE,
    close_date      DATE,
    duration_months INTEGER                     -- 영업 기간 (월)
);
CREATE INDEX idx_sh_district ON store_history(district_code);

-- 상주/직장 인구
CREATE TABLE resident_population (
    id              BIGSERIAL PRIMARY KEY,
    district_code   VARCHAR(20) REFERENCES districts(district_code),
    quarter         VARCHAR(10) NOT NULL,
    pop_type        VARCHAR(10) NOT NULL,       -- resident/worker
    age_group       VARCHAR(10) NOT NULL,
    gender          VARCHAR(1) NOT NULL,
    population      INTEGER NOT NULL
);

-- 대화 세션 (분석 이력 저장)
CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID,                       -- 비로그인이면 NULL
    district_code   VARCHAR(20),
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    ended_at        TIMESTAMPTZ
);

-- 대화 메시지
CREATE TABLE chat_messages (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID REFERENCES chat_sessions(id),
    role            VARCHAR(10) NOT NULL,       -- user/assistant/tool
    content         JSONB NOT NULL,             -- 텍스트, 카드, 차트 등
    tool_name       VARCHAR(50),                -- tool 호출인 경우
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.3 활용 데이터 전략

| 데이터 유형 | 저장 방식 | 갱신 주기 | 캐싱 전략 |
|-------------|-----------|-----------|-----------|
| 상권 폴리곤 | PostGIS POLYGON | 분기 | 앱 시작 시 전체 로드 → 프론트 캐시 |
| 유동인구 | 시계열 테이블 | 분기 | Redis TTL 24h (동일 쿼리 반복 방지) |
| 추정매출 | 시계열 테이블 | 분기 | Redis TTL 24h |
| 점포 현황 | 스냅샷 테이블 | 분기 | Redis TTL 24h |
| 점포 이력 | 히스토리 테이블 | 분기 | Redis TTL 1h (이력 조회는 덜 빈번) |
| 대화 이력 | JSONB | 실시간 | 세션 내 메모리 유지 |

---

## 5. Frontend 아키텍처

### 5.1 Figma-like UI 설계 원칙

```
┌──────────────────────────────────────────────────────────────────────┐
│  ┌─ Toolbar ──────────────────────────────────────────────────────┐  │
│  │  [🔍 상권 검색...]  [📍 내 위치]  [레이어 ▾]  [비교모드]      │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─ Map Canvas (60%) ──────────┬─ Chat Panel (40%) ──────────────┐  │
│  │                             │                                  │  │
│  │    ┌──────────────┐         │  ┌──────────────────────────┐   │  │
│  │    │  서울 지도     │         │  │  📍 강남역 상권 요약      │   │  │
│  │    │              │         │  │                          │   │  │
│  │    │  [상권 폴리곤] │         │  │  하루 평균 유동인구 12만  │   │  │
│  │    │  [히트맵]     │         │  │  명으로 서울 상위 3%...   │   │  │
│  │    │  [마커]       │         │  │                          │   │  │
│  │    │              │         │  │  ┌────────────────────┐  │   │  │
│  │    │              │         │  │  │ 📊 시간대별 유동인구 │  │   │  │
│  │    │              │         │  │  │    (인라인 차트)     │  │   │  │
│  │    │              │         │  │  └────────────────────┘  │   │  │
│  │    │              │         │  │                          │   │  │
│  │    │              │         │  │  💡 이런 것도 물어보세요: │   │  │
│  │    │              │         │  │  [여기서 뭐하면 좋을까?]  │   │  │
│  │    │              │         │  │  [카페 하면 어때?]        │   │  │
│  │    │              │         │  │  [홍대랑 비교해줘]       │   │  │
│  │    └──────────────┘         │  │                          │   │  │
│  │                             │  ├──────────────────────────┤   │  │
│  │  ┌─ Time Slider ─────────┐ │  │ 💬 무엇이든 물어보세요... │   │  │
│  │  │ ◀ 06  09  12  15  18 ▶│ │  └──────────────────────────┘   │  │
│  │  └────────────────────────┘ │                                  │  │
│  └─────────────────────────────┴──────────────────────────────────┘  │
│                                                                      │
│  ┌─ Status Bar ──────────────────────────────────────────────────┐  │
│  │  데이터 기준: 2025년 4분기  │  선택: 강남역 발달상권           │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

**디자인 핵심**:
- **Canvas 중심**: 지도가 주인공, 사이드바가 아닌 **분할 패널** 구조
- **미니멀 크롬**: 최소한의 UI 요소, 대부분의 조작은 자연어로 처리
- **Floating Controls**: 지도 위 도구는 오버레이 형태로 필요 시만 노출
- **Resizable Panels**: 지도/채팅 패널 비율을 드래그로 조절 가능
- **반응형**: 모바일에서는 지도 전체 → 하단 시트로 채팅 전환

### 5.2 컴포넌트 구조

```
src/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # 루트 레이아웃
│   ├── page.tsx                  # 메인 페이지 (지도+챗)
│   └── api/                      # BFF (Backend-for-Frontend)
│       ├── chat/route.ts         # → FastAPI /api/chat 프록시 (SSE)
│       └── districts/route.ts    # → FastAPI /api/districts 프록시
│
├── components/
│   ├── layout/
│   │   ├── SplitPanel.tsx        # 좌우 분할 (resizable)
│   │   ├── Toolbar.tsx           # 상단 도구 바
│   │   └── StatusBar.tsx         # 하단 상태 바
│   │
│   ├── map/
│   │   ├── MapContainer.tsx      # Kakao Map 래퍼
│   │   ├── DistrictLayer.tsx     # 상권 폴리곤 레이어
│   │   ├── HeatmapLayer.tsx      # 히트맵 레이어 (deck.gl)
│   │   ├── MarkerLayer.tsx       # 점포 마커
│   │   ├── TimeSlider.tsx        # 시간대 슬라이더
│   │   └── MapControls.tsx       # 줌, 레이어 토글 등
│   │
│   ├── chat/
│   │   ├── ChatPanel.tsx         # 채팅 패널 컨테이너
│   │   ├── MessageList.tsx       # 메시지 목록
│   │   ├── MessageBubble.tsx     # 개별 메시지
│   │   ├── ChatInput.tsx         # 자연어 입력
│   │   ├── SuggestionChips.tsx   # 추천 질문 버튼
│   │   └── cards/
│   │       ├── SummaryCard.tsx   # F3 상권 요약 카드
│   │       ├── CompareCard.tsx   # F5 비교 카드
│   │       ├── RecommendCard.tsx # F7 업종 추천 카드
│   │       ├── RiskCard.tsx      # F8 리스크 카드
│   │       ├── SimulationCard.tsx# F9 시뮬레이션 카드
│   │       └── InlineChart.tsx   # 인라인 차트 공통
│   │
│   └── report/
│       └── ReportExport.tsx      # F10 PDF 내보내기
│
├── stores/
│   ├── mapStore.ts               # 지도 상태 (Zustand)
│   ├── chatStore.ts              # 채팅 상태
│   └── districtStore.ts          # 선택 상권 상태
│
├── hooks/
│   ├── useChat.ts                # 채팅 SSE 스트리밍
│   ├── useDistrict.ts            # 상권 선택/조회
│   └── useMapSync.ts             # 지도↔채팅 상태 동기화
│
└── lib/
    ├── api.ts                    # API 클라이언트
    └── types.ts                  # 공유 타입 정의
```

### 5.3 자연어 쿼리 중심 UX

**모든 조작을 채팅으로 가능하게** 설계:

| 사용자 입력 (자연어) | Agent 처리 | 화면 반응 |
|---------------------|-----------|-----------|
| "강남역 상권 보여줘" | 상권 검색 → 지도 이동 + F3 요약 | 지도: 강남역 이동 + 하이라이트, 채팅: 요약 카드 |
| "유동인구 시간대별로 보여줘" | `get_floating_population` → 차트 생성 | 채팅: 시간대별 바 차트, 지도: 히트맵 ON |
| "홍대랑 비교해줘" | `compare_districts` → 비교표 생성 | 채팅: 비교 카드, 지도: 두 상권 하이라이트 |
| "여기서 뭐 하면 좋을까?" | `recommend_business` → 추천 리스트 | 채팅: 업종 추천 카드 |
| "카페 하면 매출 얼마나?" | `simulate_revenue` → 범위 추정 | 채팅: 시뮬레이션 카드 |
| "이 자리 위험하지 않아?" | `get_store_history` → 리스크 분석 | 채팅: 리스크 카드 |
| "PDF로 저장해줘" | 대화 이력 + 차트 → PDF 생성 | 다운로드 트리거 |

**핵심**: 지도 클릭도 내부적으로 자연어 쿼리와 동일한 파이프라인을 탐. 지도 클릭 이벤트 → "사용자가 {상권명} 상권을 선택했습니다" 형태로 Agent에 전달.

---

## 6. Backend 아키텍처

### 6.1 디렉토리 구조

```
server/
├── main.py                       # FastAPI 앱 진입점
├── config.py                     # 환경 설정
│
├── api/
│   ├── routes/
│   │   ├── chat.py               # POST /api/chat (SSE 스트리밍)
│   │   ├── districts.py          # GET /api/districts, /api/districts/{code}
│   │   ├── map_data.py           # GET /api/map-data/polygons, /heatmap
│   │   └── reports.py            # POST /api/reports/export
│   └── deps.py                   # 의존성 주입 (DB, Redis, Agent)
│
├── agent/
│   ├── graph.py                  # LangGraph 그래프 정의 (ReAct)
│   ├── state.py                  # AgentState 정의
│   ├── nodes/
│   │   ├── reason.py             # 추론 노드 (LLM 호출)
│   │   ├── act.py                # 실행 노드 (Tool 호출)
│   │   └── observe.py            # 관찰 노드 (결과 해석)
│   ├── tools/
│   │   ├── floating_population.py
│   │   ├── estimated_sales.py
│   │   ├── store_info.py
│   │   ├── store_history.py
│   │   ├── population_info.py
│   │   ├── compare_districts.py
│   │   ├── recommend_business.py
│   │   ├── simulate_revenue.py
│   │   └── map_control.py
│   └── prompts/
│       ├── system.py             # 시스템 프롬프트
│       └── templates.py          # 응답 템플릿
│
├── data/
│   ├── etl/
│   │   ├── seoul_opendata.py     # 서울 열린데이터 수집
│   │   ├── semas.py              # 소상공인시장진흥공단 수집
│   │   └── scheduler.py          # 분기별 ETL 스케줄러
│   └── repositories/
│       ├── district_repo.py      # 상권 CRUD
│       ├── population_repo.py    # 유동인구 조회
│       ├── sales_repo.py         # 매출 조회
│       └── store_repo.py         # 점포 조회
│
├── models/
│   ├── district.py               # SQLAlchemy 모델
│   ├── population.py
│   ├── sales.py
│   └── store.py
│
└── services/
    ├── cache.py                  # Redis 캐싱 래퍼
    └── report_generator.py       # PDF 리포트 생성
```

### 6.2 API 설계

| Endpoint | Method | 설명 | 응답 |
|----------|--------|------|------|
| `/api/chat` | POST | 자연어 쿼리 처리 (SSE 스트리밍) | `text/event-stream` |
| `/api/districts` | GET | 상권 목록 (검색, 필터) | JSON |
| `/api/districts/{code}` | GET | 상권 상세 정보 | JSON |
| `/api/map-data/polygons` | GET | 상권 폴리곤 GeoJSON | GeoJSON |
| `/api/map-data/heatmap` | GET | 히트맵 데이터 | JSON |
| `/api/reports/export` | POST | PDF 리포트 생성 | PDF file |

### 6.3 채팅 SSE 스트리밍 흐름

```
Client                    FastAPI                   LangGraph Agent
  │                          │                            │
  │  POST /api/chat          │                            │
  │  {message, session_id,   │                            │
  │   district_code}         │                            │
  │ ─────────────────────►   │                            │
  │                          │  invoke(state)             │
  │                          │ ──────────────────────►    │
  │                          │                            │
  │  SSE: {"type":"thinking"}│    REASON (LLM)            │
  │  ◄─────────────────────  │ ◄──────────────────────    │
  │                          │                            │
  │  SSE: {"type":"tool",    │    ACT (Tool 호출)          │
  │        "name":"get_fp"}  │ ◄──────────────────────    │
  │  ◄─────────────────────  │                            │
  │                          │                            │
  │  SSE: {"type":"map_cmd", │    OBSERVE + map command   │
  │  "action":"heatmap_on"}  │ ◄──────────────────────    │
  │  ◄─────────────────────  │                            │
  │                          │                            │
  │  SSE: {"type":"text",    │    END (최종 응답)           │
  │  "content":"강남역..."}  │ ◄──────────────────────    │
  │  ◄─────────────────────  │                            │
  │                          │                            │
  │  SSE: {"type":"card",    │                            │
  │  "data":{chart_data}}    │                            │
  │  ◄─────────────────────  │                            │
  │                          │                            │
  │  SSE: {"type":"done"}    │                            │
  │  ◄─────────────────────  │                            │
```

**SSE 이벤트 타입**:

| type | 설명 | data |
|------|------|------|
| `thinking` | Agent가 추론 중 | `{step: "분석 중..."}` |
| `tool` | Tool 호출 시작 | `{name, input}` |
| `text` | 텍스트 응답 (스트리밍) | `{content}` (토큰 단위) |
| `card` | Rich Card 데이터 | `{card_type, data}` |
| `map_cmd` | 지도 조작 명령 | `{action, params}` |
| `suggestion` | 추천 질문 | `{questions: [...]}` |
| `done` | 응답 완료 | `{}` |

---

## 7. 지도-채팅 동기화 아키텍처

지도와 채팅은 **양방향 동기화**되어야 합니다.

```
┌──────────────┐                           ┌──────────────┐
│   Map Panel  │                           │  Chat Panel  │
└──────┬───────┘                           └──────┬───────┘
       │                                          │
       │  지도 클릭 이벤트                          │  자연어 입력
       │  (상권 선택)                               │
       ▼                                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Zustand Store                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  selectedDistrict: { code, name, polygon }       │    │
│  │  mapView: { center, zoom, layers }               │    │
│  │  chatMessages: [...]                             │    │
│  │  isCompareMode: boolean                          │    │
│  └─────────────────────────────────────────────────┘    │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │  Agent API   │
                  │  (SSE 응답)   │
                  └──────┬───────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
      map_cmd 이벤트          text/card 이벤트
      → mapStore 업데이트     → chatStore 업데이트
      → 지도 리렌더링         → 메시지 추가
```

**동기화 시나리오**:
1. **지도 → 채팅**: 상권 클릭 → `districtStore.select()` → Agent에 자동 질의 → F3 요약 표시
2. **채팅 → 지도**: "홍대 보여줘" → Agent가 `map_cmd` 반환 → 지도 이동 + 하이라이트
3. **양방향**: "시간대별 유동인구" → 채팅에 차트 + 지도에 히트맵 동시 표시

---

## 8. 배포 아키텍처

### 8.1 개발 환경

```yaml
# docker-compose.yml
services:
  frontend:
    build: ./client
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000

  backend:
    build: ./server
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://...
      - REDIS_URL=redis://redis:6379
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
    depends_on: [db, redis]

  db:
    image: postgis/postgis:16-3.4
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  langfuse:
    image: langfuse/langfuse:latest
    ports: ["3001:3000"]
    depends_on: [db]
```

### 8.2 프로덕션 환경

```
                    ┌─────────────┐
                    │  CloudFlare │
                    │  (CDN/WAF)  │
                    └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │  ALB/NLB    │
                    └──┬──────┬──┘
                       │      │
              ┌────────┴┐  ┌──┴────────┐
              │ Next.js │  │  FastAPI  │
              │ (Vercel │  │ (ECS or   │
              │  or ECS)│  │  Cloud    │
              └─────────┘  │  Run)     │
                           └────┬─────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
              ┌─────┴───┐ ┌────┴────┐ ┌────┴────┐
              │ RDS     │ │ Elasti- │ │   S3    │
              │ PostGIS │ │ Cache   │ │ (PDF)   │
              └─────────┘ └─────────┘ └─────────┘
```

---

## 9. 보안 및 비기능 요구사항

| 항목 | 구현 방식 |
|------|-----------|
| API 인증 | MVP: 미인증 (무료 서비스), 이후: JWT (리포트 저장 등) |
| Rate Limiting | FastAPI middleware, IP 기반 분당 30회 |
| LLM 비용 제어 | 세션당 최대 20회 Agent 호출, ReAct 루프 최대 5회 |
| 데이터 정합성 | 모든 응답에 데이터 기준 분기 명시 |
| 응답 속도 | 첫 토큰 2초 이내 (SSE 스트리밍으로 체감 속도 향상) |
| 에러 처리 | Agent Tool 실패 시 graceful fallback ("데이터를 불러오지 못했습니다") |

---

## 10. 구현 로드맵과 아키텍처 매핑

| Phase | 기능 | 아키텍처 컴포넌트 |
|-------|------|-------------------|
| **Phase 1 (MVP)** | F1 지도 선택 | Kakao Map + PostGIS 폴리곤 |
| | F2 AI 챗봇 | LangGraph Agent + SSE 스트리밍 |
| | F3 기본 리포트 | Agent Tool 5종 + SummaryCard |
| | F4 업종 심층 | `get_estimated_sales` + `get_store_info` |
| **Phase 2** | F5 상권 비교 | `compare_districts` Tool + CompareCard |
| | F7 업종 추천 | `recommend_business` Tool + 추천 로직 |
| | F8 이력/리스크 | `store_history` 테이블 + RiskCard |
| **Phase 3** | F6 히트맵 | deck.gl HeatmapLayer + TimeSlider |
| | F9 시뮬레이션 | `simulate_revenue` Tool + SimulationCard |
| | F10 리포트 | react-pdf + S3 저장 |

---

*작성일: 2026-03-24*
*버전: v1.0*
*기준 문서: a_drafts/merged_features.md (Merged v1.0)*
