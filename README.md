# MarketScope AI - 상권분석 AI 서비스

> 지도 기반 AI 챗봇으로 서울시 1,650개 상권을 분석하는 Freemium SaaS

소상공인/부동산 투자자가 **"지도에서 상권 선택 → AI가 분석/추천"** 하는 서비스입니다.
자연어 질문만으로 유동인구, 매출, 경쟁 현황, 업종 추천, 리스크 분석까지 한 번에 확인할 수 있습니다.

### [QuickStart Guide (처음이라면 여기부터)](docs/ops/quickstart.md)

> **5분 안에 실행**: 환경 설정 → DB 세팅 → 서비스 기동까지 한 문서로 정리했습니다.
> Mock 모드(DB 없이 바로), Seed 복원(실데이터 5분), Full ETL(API 수집) 3가지 경로를 제공합니다.

---

## 스크린샷

### 다크 테마 (기본)
![MarketScope AI - Dark Theme](docs/images/ui_image_dark.png)
*강남역 상권 선택 → AI 자동 분석 → SummaryCard (유동인구 바 차트 + Top 5 업종)*

### 라이트 테마
![MarketScope AI - Light Theme](docs/images/url_image_light.png)
*업종 추천 카드 — 점수 바 + 추천 근거*

### 상권 비교
![상권 비교](docs/screenshots/real-mode/real-mode-compare.png)
*두 상권의 유동인구/매출/점포 수/폐업률을 비교표로 제공*

### 업종 추천
![업종 추천](docs/screenshots/real-mode/real-mode-recommend.png)
*AI가 상권 데이터 기반으로 추천 업종 Top 5 + 근거 제시*

---

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                             │
│  ┌─────────────────────────┬───────────────────────────────────┐    │
│  │     Map Panel (60%)     │       Chat Panel (40%)            │    │
│  │  ┌───────────────────┐  │  ┌─────────────────────────────┐  │    │
│  │  │  Kakao Map SDK    │  │  │  자연어 입력                 │  │    │
│  │  │  + 상권 폴리곤     │  │  │  + SSE 스트리밍 응답        │  │    │
│  │  │  + 히트맵 레이어   │  │  │  + Rich Card (차트/테이블)  │  │    │
│  │  │  + 마커 레이어     │  │  │  + 추천 질문 칩             │  │    │
│  │  └───────────────────┘  │  └─────────────────────────────┘  │    │
│  └─────────────────────────┴───────────────────────────────────┘    │
│                         Next.js 14 (App Router)                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  REST + SSE (Server-Sent Events)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        API Server (FastAPI)                         │
│  POST /api/chat (SSE)  │  GET /api/districts  │  GET /api/map-data │
└──────────┬──────────────────────────────────────────────────────────┘
           │
     ┌─────┴──────────────────────────────────┐
     ▼                                        ▼
┌──────────────────┐              ┌──────────────────────────────────┐
│   AI Agent       │              │         Data Layer               │
│ (v2 agentic loop)│              │                                  │
│  ┌────────────┐  │   Tool 호출  │  ┌────────────┐ ┌────────────┐   │
│  │ LLM 주도     │──┼─────────────►│  │ PostgreSQL │ │   Redis    │   │
│  │ Tool 루프 +  │  │              │  │ + PostGIS  │ │  (Cache)   │   │
│  │ TrustKernel│  │              │  └────────────┘ └────────────┘   │
│  └────────────┘  │              │                                  │
│  Claude/Gemini   │              │  서울 열린데이터 (공공 API)       │
└──────────────────┘              └──────────────────────────────────┘
```

---

## 데이터 플로우

### 1. 데이터 수집 (ETL)

```
서울 열린데이터 API ──── Batch ETL (분기별) ────► PostgreSQL + PostGIS
  ├ 유동인구 (VwsmTrdarFlpopQq)                    ├ districts (1,650개)
  ├ 추정매출 (VwsmTrdarSelngQq)                    ├ floating_population (9,888행)
  ├ 점포현황 (VwsmTrdarStorQq)                     ├ estimated_sales (21,333행)
  └ 직장인구 (VwsmTrdarWrcPopltnQq)                ├ stores (75,985행)
                                                   └ resident_population (39,288행)
SHP 폴리곤 파일 ───── geopandas 파싱 ─────────► districts.boundary (EPSG:4326)
```

### 2. 사용자 질의 처리 (실시간)

기본 경로는 **v2 agentic loop**(모델 주도 function-calling + Trust Kernel, `agent/loop/`)이며,
Mock 모드(`LLM_PROVIDER=mock`)에서는 레거시 PAE(Planner-Actor-Evaluator) 그래프로 폴백합니다 (`agent/runtime.py` 디스패치).

```
사용자 (브라우저)                  FastAPI                    v2 Agentic Loop
  │                                 │                              │
  │  "강남역 분석해줘"                │                              │
  │ ───────────────────────────►    │                              │
  │                                 │                              │
  │  SSE: {type: "map_cmd"}        │   (상권 인식 시 지도 이동)     │
  │  ◄──────────────────────────   │                              │
  │                                 │   run_agent(...)             │
  │                                 │ ────────────────────────►    │
  │  SSE: {type: "thinking"}       │     LLM 이 필요한 Tool 결정   │
  │  ◄──────────────────────────   │  ◄────────────────────────   │
  │                                 │                              │
  │  SSE: {type: "tool",           │     Tool 실행                 │
  │        name: "유동인구 조회"}    │         ▼                     │
  │  ◄──────────────────────────   │   PostgreSQL / Redis Cache    │
  │                                 │         │                     │
  │  SSE: {type: "card",           │     결과 → fact_pool 적재     │
  │        card_type: "summary"}   │  ◄────────────────────────   │
  │  SSE: {type: "tool_end"}       │   (충분할 때까지 Tool 반복 —  │
  │  ◄──────────────────────────   │    예산: 6턴 / 12콜 / 90초)   │
  │                                 │                              │
  │  SSE: {type: "text",           │   Trust Kernel 이 응답 수치를 │
  │        content: "강남역은..."}  │   Tool 반환값에 검증 후 방출  │
  │  ◄──────────────────────────   │  ◄────────────────────────   │
  │                                 │                              │
  │  SSE: {type: "suggestion"}     │                              │
  │  SSE: {type: "done"}           │                              │
  │  ◄──────────────────────────   │                              │
```

### 3. 지도-채팅 양방향 동기화

```
┌──────────────┐                           ┌──────────────┐
│   Map Panel  │                           │  Chat Panel  │
│  (Kakao Map) │                           │  (AI 채팅)    │
└──────┬───────┘                           └──────┬───────┘
       │                                          │
       │  폴리곤 클릭 (상권 선택)                    │  자연어 입력
       ▼                                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Zustand Store                         │
│  selectedDistrict: { code, name, polygon }               │
│  mapView: { center, zoom, layers }                       │
│  chatMessages: [...]                                     │
└────────────────────────┬────────────────────────────────┘
                         │
                    Agent API (SSE)
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
      map_cmd 이벤트          text/card 이벤트
      → 지도 이동/하이라이트   → 메시지/카드 추가
```

**동기화 시나리오**:
| 방향 | 트리거 | 결과 |
|------|--------|------|
| 지도 → 채팅 | 상권 폴리곤 클릭 | 프리뷰 카드(LLM 무호출) 즉시 표시 → "AI 분석 보기"로 전체 분석 진입 |
| 채팅 → 지도 | "홍대 보여줘" 입력 | 지도가 홍대로 이동 + 폴리곤 하이라이트 |
| 양방향 | "시간대별 유동인구" | 채팅에 시간대별 바 차트 + 지도에서 히트맵 레이어로 확인 |

---

## 사용자 시나리오

### 시나리오 1: 상권 탐색 및 기본 분석

```
1. 사용자가 서울 지도에서 "강남역" 상권 폴리곤을 클릭
2. 프리뷰 카드(LLM 무호출)가 즉시 뜨고, "AI 분석 보기"를 누르면 AI가 유동인구/매출/점포 데이터를 조회
3. SummaryCard 렌더링:
   - 분기 유동인구 합계 (시간대별 바 차트 + 피크 시간대)
   - 월 환산 추정 매출
   - Top 5 업종: 한식, 카페/음료, 의류, 일식/중식
4. 추천 질문 칩 노출: "여기서 뭐하면 좋을까?", "이 자리 위험해?"
```

### 시나리오 2: 업종 추천

```
1. 사용자: "여기서 뭐하면 좋을까?"
2. AI가 recommend_business Tool로 상권 데이터 기반 업종 분석
3. RecommendCard 렌더링:
   - 1위: 편의점 (95점) — 유동인구 높고 생존율 96%
   - 2위: 서적 (74점) — 경쟁 적고 학생 유입
   - 3위: 골프/스포츠 (55점) — 틈새 시장
   - 점수는 상권 내 상대 순위 밴드(55~95점) — 절대 평가 아님
   - 면책 조항 포함
```

### 시나리오 3: 상권 비교

```
1. 사용자: "강남역이랑 홍대 비교해줘"
2. AI가 compare_districts Tool로 두 상권 데이터 병렬 조회
3. CompareCard 렌더링:
   - 분기 유동인구 합계 비교 (시간대별 데이터 기반)
   - 월 환산 매출 비교
   - 폐업률, 안정성 등급 비교
4. 지도에 두 상권 동시 하이라이트
```

### 시나리오 4: 리스크 분석

```
1. 사용자: "이 자리 위험하지 않아?"
2. AI가 get_store_history Tool로 점포 이력/폐업 데이터 조회
3. RiskCard 렌더링:
   - 안정성 게이지 (안전/주의/위험)
   - 업종별 평균 생존 기간 바 차트
   - 최근 폐업 트렌드
```

### 시나리오 5: 매출 시뮬레이션

```
1. 사용자: "카페 하면 매출 얼마나 나와?"
2. AI가 simulate_revenue Tool로 업종별 매출 분위수 산출
3. SimulationCard 렌더링:
   - 하위(p25) / 평균 / 상위(p75) 예상 월매출 범위
   - 서울 평균 대비 비교
   - 산출 근거 + 면책 안내
```

---

## 프로젝트 구조

```
MarketScope-AI/
├── frontend/                          # Next.js 14 (App Router)
│   └── src/
│       ├── app/                       # 페이지 & Route Handlers
│       │   ├── page.tsx               # 랜딩 (역할 온보딩)
│       │   ├── app/page.tsx           # 분석 앱 (지도 + 채팅)
│       │   └── proxy/kakao-sdk/       # Kakao SDK 프록시
│       ├── components/
│       │   ├── layout/                # SplitPanel, Toolbar, StatusBar
│       │   ├── map/                   # MapContainer, DistrictLayer, MapControls
│       │   └── chat/                  # ChatPanel, MessageList, ChatInput
│       │       └── cards/             # SummaryCard, CompareCard, RecommendCard, RiskCard, SimulationCard
│       ├── stores/                    # Zustand (mapStore, chatStore, districtStore, toastStore)
│       ├── hooks/                     # useChat (SSE), useMapSync
│       └── lib/                       # API 클라이언트, 타입 정의
│
├── server/                            # FastAPI (Python 3.12)
│   └── server/
│       ├── main.py                    # FastAPI 앱 + lifespan
│       ├── config.py                  # pydantic-settings (Mock/Real 전환)
│       ├── agent/                     # AI Agent (v2 agentic loop + Trust Kernel)
│       │   ├── runtime.py            # v2 루프 ↔ 레거시 PAE 디스패치 (단일 진입점)
│       │   ├── loop/                 # v2: engine, trust (Trust Kernel), tools_fc, prompts, models
│       │   ├── graph.py              # 레거시 PAE 그래프 (Mock 모드 폴백)
│       │   ├── state.py / history.py # 상태 + 세션 히스토리
│       │   ├── nodes/                # PAE: planner, actor, evaluator, respond
│       │   ├── prompts/              # PAE: system, planner, evaluator
│       │   ├── config/intents.yaml   # Intent 분류 규칙 (PAE)
│       │   └── tools/                # Agent Tools 9종 + registry + mock JSON
│       ├── api/                      # routes, middleware, rate_limiter
│       │   └── routes/               # chat (SSE), districts, map_data
│       ├── data/etl/                 # 공공데이터 ETL (서울 열린데이터 + SHP + CSV)
│       ├── repositories/             # mock/ · real/ + protocols.py (10 인터페이스)
│       ├── models/                   # SQLAlchemy + PostGIS 모델
│       └── services/                 # cache / circuit_breaker / category_resolver
│
├── data/                              # SHP 폴리곤 파일 + seed 덤프
├── scripts/                           # 운영 스크립트 (verify_sales_units, validate_env, setup_db, …)
├── nginx/                             # 내장 + 외부 리버스 프록시 설정
├── docs/
│   ├── architecture/                  # 계층별 설계 (overview/backend/frontend/agent/data/deployment)
│   ├── spec/                          # 기능 스펙 (F01~F13, D01, B01)
│   ├── ops/                           # 운영 (quickstart, runbook, deployment, DR)
│   ├── plan/                          # 현재 진행 중인 계획만 유지
│   ├── qa/                            # E2E test plan + 실행 로그
│   ├── status/current-status.md       # 단일 마스터 상태
│   ├── screenshots/                   # UI 스크린샷
│   └── images/                        # README 이미지
│
├── docker-compose.yml                 # 개발 (PostGIS + Redis + Backend + Frontend + Nginx)
├── docker-compose.prod.yml            # 프로덕션 (내부 네트워크 + 외부 Nginx)
├── .env.example                       # 환경 변수 템플릿
└── CLAUDE.md                          # AI 어시스턴트 개발 가이드
```

---

## 기술 스택

| 레이어 | 기술 | 역할 |
|--------|------|------|
| **Frontend** | Next.js 14 (App Router, TypeScript) | SSR, BFF |
| **Map** | Kakao Map SDK | 서울 지도 + 상권 폴리곤 |
| **상태 관리** | Zustand | 지도-채팅 양방향 동기화 |
| **차트** | Recharts | SummaryCard 내 인라인 바 차트 |
| **UI** | shadcn/ui + Tailwind CSS | 다크 테마 미니멀 디자인 |
| **Backend** | FastAPI (Python 3.12, async) | REST + SSE 스트리밍 |
| **AI Agent** | v2 Agentic Loop + Trust Kernel | 모델 주도 Tool 호출 + 응답 수치 검증 (레거시 PAE(LangGraph)는 Mock 폴백) |
| **LLM** | Claude Sonnet → Gemini 2.5 fallback chain | 한국어 상권 분석 + Tool Use (기본 provider 는 Gemini, env 로 전환) |
| **Database** | PostgreSQL 16 + PostGIS | 상권 폴리곤 + 매출/인구 시계열 |
| **Cache** | Redis 7 | 쿼리 결과 캐싱 (TTL 24h) |
| **Container** | Docker Compose | 개발 환경 통합 |

---

## AI Agent Tools

Agent 가 사용하는 등록 Tool **9종** (`@register_tool`, `agent/tools/registry.py`):

| Tool | 기능 | 데이터 소스 |
|------|------|-------------|
| `get_district_summary` | 상권 종합 요약 (4개 조회 병렬 집계) | 복합 조회 |
| `get_floating_population` | 시간대/연령/성별 유동인구 (분기 합계) | floating_population |
| `get_estimated_sales` | 업종별 추정 매출 (분기→월 환산) | estimated_sales |
| `get_store_info` | 점포 수, 개폐업, Top 업종 | stores |
| `get_population_info` | 상주/직장인구 | resident_population |
| `get_store_history` | 안정성 스코어 / 생존 기간 | stores (history 미적재) |
| `compare_districts` | 2~3 상권 지표 비교 | 복합 조회 |
| `recommend_business` | 추천 업종 Top 5 + 점수 + 면책 | 복합 분석 |
| `simulate_revenue` | p25/avg/p75 매출 범위 시뮬레이션 | estimated_sales |

> v2 agentic loop 는 여기에 메타 Tool 3종 — `resolve_district`(상권명→코드), `compute`(안전 산술), `abstain`(데이터 없음 1급 거부) — 을 더해 총 12개 스키마를 LLM 에 제공합니다.
> `get_district_benchmarks` 는 등록 Tool 이 아닌 내부 헬퍼(상권 유형별 벤치마크 집계)로, summary/risk 결과에 주입됩니다.

---

## 빠른 시작

### 사전 요구사항

- Node.js 18+
- Python 3.12+
- Docker & Docker Compose (Real 모드 시)
- API 키: LLM (기본 provider 는 Gemini → `GOOGLE_API_KEY`, `LLM_PROVIDER=anthropic` 사용 시 `ANTHROPIC_API_KEY`), Kakao Map, 서울 열린데이터 (Real 모드)

### 1. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일에 API 키 입력
```

### 2A. Mock 모드 (DB 없이 빠른 실행)

```bash
# .env에서 USE_MOCK=true 확인

# Backend
cd server
pip install -e ".[dev]"
uvicorn server.main:app --reload --port 8000

# Frontend (새 터미널)
cd frontend
npm install
npm run dev
```

`http://localhost:3000` 접속 → 5개 샘플 상권 (강남역, 홍대, 건대, 명동, 서울역) 으로 전체 기능 체험

### 2B. Real 모드 (실제 데이터)

```bash
# .env에서 USE_MOCK=false 설정 + 서울 열린데이터 API 키 입력

# Docker (PostGIS + Redis)
docker compose up -d db redis

# DB 마이그레이션
cd server
alembic upgrade head

# ETL 데이터 적재 (분기 지정)
python -m server.data.etl.runner run 2025Q4

# Backend
uvicorn server.main:app --reload --port 8000

# Frontend (새 터미널)
cd frontend
npm run dev
```

`http://localhost:3000` 접속 → 서울시 1,650개 실제 상권 데이터로 분석

---

## SSE 이벤트 타입

채팅 API(`POST /api/chat`)는 Server-Sent Events로 실시간 스트리밍합니다.
기본 v2 루프는 `thinking / tool / tool_end / card / text / suggestion / done` 7종을 방출하며,
`plan` · `warning` 은 레거시 PAE 경로 전용, `map_cmd` 는 상권 인식 시 라우트 계층(chat.py)이 방출합니다:

| type | 설명 | data | 방출 경로 |
|------|------|------|-----------|
| `thinking` | Agent 추론 중 | `{step, icon}` | v2 · PAE |
| `plan` | 실행 계획 수립 | `{intent, steps[]}` | PAE 전용 |
| `tool` | Tool 호출 시작 | `{name, input, icon}` | v2 · PAE |
| `tool_end` | Tool 실행 완료 | `{name, icon}` | v2 · PAE |
| `text` | 텍스트 응답 (청크 단위) | `{content}` | v2 · PAE |
| `card` | Rich Card 데이터 | `{card_type, data}` | v2 · PAE |
| `warning` | 수치 검증 경고 | `{rules, match_rate}` | PAE 전용 |
| `map_cmd` | 지도 조작 명령 | `{action, params}` | chat.py (공통) |
| `suggestion` | 추천 질문 목록 | `{questions: [...]}` | v2 · PAE |
| `done` | 응답 완료 | `{trace_id?}` | v2 · PAE |

---

## DB 스키마 (핵심 테이블)

```
districts                 상권 영역 (PostGIS POLYGON, 1,650개)
floating_population       유동인구 (시간대/요일/연령/성별, 분기별)
estimated_sales           추정매출 (업종별, 분기별)
stores                    점포 현황 (점포 수/개업/폐업/프랜차이즈)
store_history             점포 이력 (영업 기간, 업종 변동)
resident_population       상주/직장 인구 (연령/성별)
chat_sessions             대화 세션
chat_messages             대화 메시지 (JSONB)
category_metadata         업종 코드 참조
```

---

## 개발 로드맵

```
Phase 1A ✅  Mock E2E      지도 선택 → AI 챗봇 → Card UI (5개 샘플 상권)
Phase 1B ✅  Real Data     공공데이터 ETL → PostGIS → 1,650개 상권 실데이터
Phase 3  ✅  확장          시간대별 히트맵 (deck.gl), 매출 시뮬레이션, PDF 리포트
Phase 2  ⏳  Premium       업종 심층 분석, Tier 게이팅 (OAuth2, 결제)
Prod     ✅  마켓스코프    marketscope.robitlabs.co.kr 라이브
```

### 현재 상태 (2026-07-04)

- Phase 1A · 1B · 3 완료. Agent 는 **v2 agentic loop + Trust Kernel** 전환 완료 (등록 Tool 9종 / Card 5종, 레거시 PAE 는 Mock 모드 폴백)
- backend pytest 190 passed / 6 skipped (2026-07-04) · Mock E2E 131 passed (2026-07-02)
- 프로덕션 배포 완료 (marketscope.robitlabs.co.kr, 외부 Nginx + SSE 스트리밍 정상)
- 상세 진행 상황: [docs/status/current-status.md](docs/status/current-status.md)

---

## 개발 명령어

```bash
# 린트/포맷
npx prettier --write .                   # TypeScript
ruff check --fix . && ruff format .      # Python

# 테스트
cd frontend && npm run test:e2e          # E2E (Playwright)
cd server && pytest                      # Backend 테스트

# Docker
docker compose up -d                     # 전체 서비스 기동
docker compose up -d db redis            # DB + Redis만 기동
```

---

## 데이터 소스

| 소스 | 제공 데이터 | 갱신 주기 |
|------|-------------|-----------|
| [서울 열린데이터](https://data.seoul.go.kr) | 상권 폴리곤, 유동인구, 추정매출, 직장인구 | 분기 |
| [공공데이터포털](https://data.go.kr) | 점포 정보, 점포 이력 | 분기 |

---

## 라이선스

Private project.
