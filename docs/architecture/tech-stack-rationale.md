# 설계도 ↔ 코드 매핑 + 기술 스택 선택 근거

> 비개발자도 이해할 수 있도록 작성한 문서. "시스템이 어떤 부품으로 이루어져 있고, 각 부품이 코드 어디에 있으며, 왜 그 기술을 골랐는지"를 설명한다.
> 작성일: 2026-06-10 · 갱신: 2026-07-03 (Agentic Loop v2 반영)

---

## 1. 서비스를 한 문장으로

> **"지도에서 서울 상권(1,650개)을 클릭하면, AI가 공공데이터를 읽고 분석해서 채팅으로 알려주는 서비스"**

이를 위해 시스템은 크게 4개의 층으로 나뉜다. 식당에 비유하면:

| 층 | 비유 | 역할 |
|---|---|---|
| ① 화면 (Frontend) | 손님이 앉는 홀 + 메뉴판 | 지도와 채팅창을 보여주고, 사용자의 클릭/질문을 받음 |
| ② 서버 (Backend API) | 주문을 받는 카운터 | 화면의 요청을 받아 적절한 곳으로 전달하고, 결과를 돌려줌 |
| ③ AI 에이전트 (Agent) | 주방장 | 질문을 해석하고, 필요한 데이터를 골라 분석한 뒤 답변을 작성 |
| ④ 데이터 (Database/Cache) | 냉장고 + 창고 | 서울시 공공데이터(유동인구·매출·점포 등)를 보관 |

---

## 2. 설계도 ↔ 실제 코드 위치 매핑

### ① 화면 (Frontend) — `frontend/`

설계도(architecture/frontend.md)의 컴포넌트가 실제 코드 어디에 있는지:

| 설계도의 부품 | 하는 일 (쉬운 설명) | 실제 코드 위치 |
|---|---|---|
| 랜딩 페이지 | 처음 방문자가 보는 소개 화면 | `frontend/src/app/page.tsx` + `components/landing/` |
| 분석 앱 화면 | 지도 + 채팅이 나란히 있는 메인 화면 | `frontend/src/app/app/page.tsx` |
| 지도 패널 | 서울 지도에 상권 경계선을 그리고 클릭 받기 | `components/map/` (MapContainer, DistrictLayer 등) |
| 시간대별 히트맵 | 시간대별 유동인구를 색으로 표현 | `components/map/HeatmapLayer.tsx` (deck.gl) |
| 채팅 패널 | AI와 대화하는 창, 답변이 실시간으로 타이핑되듯 표시 | `components/chat/` (ChatPanel, MessageList 등) |
| 분석 카드 5종 | 요약/비교/추천/리스크/시뮬레이션 결과를 차트로 표시 | `components/chat/cards/` (Recharts 차트 포함) |
| 상태 보관함 | "지금 어떤 상권을 선택했나" 등을 화면 전체가 공유 | `frontend/src/stores/` (Zustand: chat/district/map/toast) |
| 실시간 수신기 | 서버가 한 글자씩 보내는 답변을 받아 화면에 붙임 | `frontend/src/lib/sseParser.ts` + `eventHandlers.ts` |
| PDF 리포트 | 분석 결과를 PDF 파일로 저장 | `components/report/` + `hooks/useReportExport.ts` |
| 모바일 UI | 휴대폰에서는 하단 시트/탭으로 전환 | `components/mobile/` (BottomNav, BottomSheet) |

### ② 서버 (Backend API) — `server/server/`

| 설계도의 부품 | 하는 일 | 실제 코드 위치 |
|---|---|---|
| 앱 시동부 | 서버 켤 때 DB·캐시·AI를 연결 | `server/server/main.py` |
| 환경 설정 | "Mock 모드인가, 어느 AI를 쓰나" 등 스위치 모음 | `server/server/config.py` |
| 채팅 API | 질문을 받아 AI 답변을 실시간 스트리밍 | `server/server/api/routes/chat.py` |
| 상권 검색/상세 API | 상권 이름 검색, 폴리곤(경계선) 제공 | `api/routes/districts.py` |
| 지도 데이터 API | 폴리곤 일괄 제공 + 히트맵 데이터 | `api/routes/map_data.py` |
| 요청 제한기 | 1분에 60회 초과 요청 차단 (악용 방지) | `api/rate_limiter.py` |
| 보안/추적 미들웨어 | 모든 요청에 보안 헤더와 추적 ID 부여 | `api/middleware.py` |
| 캐시 서비스 | 같은 질문은 다시 계산하지 않고 저장본 사용 | `services/cache.py` |
| 회로 차단기 | AI가 연속 실패하면 잠시 호출을 끊어 전체 장애 방지 | `services/circuit_breaker.py` |
| 업종 해석기 | "카페" 같은 말을 데이터 코드로 변환 | `services/category_resolver.py` |
| 관측 도구 | AI 호출 비용·품질을 외부 대시보드(Langfuse)로 기록 | `services/langfuse_tracer.py` |

### ③ AI 에이전트 — `server/server/agent/`

**v2 모델주도 루프 (현행 기본 경로)** — AI가 스스로 도구를 골라 호출을 반복하고, 코드가 그 결과를 검증한다:

| 설계도의 부품 | 하는 일 (쉬운 설명) | 실제 코드 위치 |
|---|---|---|
| 경로 선택기 (dispatch) | 설정(`agent_loop_version`)에 따라 v2 루프/레거시 PAE 분기. mock 모드는 항상 PAE | `agent/runtime.py` |
| 루프 엔진 | AI가 필요한 도구를 직접 고르고 호출을 반복하며 답변 완성. 예산(모델 턴 6회·도구 12회·90초) 초과 시 강제 마무리 | `agent/loop/engine.py` |
| Trust Kernel (검증기) | 답변 속 숫자가 실제 도구 결과에 근거하는지 대조, 근거 없는 숫자는 교정 | `agent/loop/trust.py` |
| FC 도구 12종 | 도메인 조회기 9종 + 메타 3종(상권명 해석 `resolve_district` · 안전 계산 `compute` · 답변 거절 `abstain`) | `agent/loop/tools_fc.py` |
| 모델 폴백 | Anthropic 장애 시 Gemini pro → flash 로 자동 대체 | `agent/loop/models.py` |
| 프롬프트 계약 | "상권명은 먼저 resolve, 산술은 반드시 compute, 데이터 없으면 abstain" 규칙 | `agent/loop/prompts.py` |

**PAE 그래프 (레거시 — mock 경로 전용)** — mock provider/E2E 테스트에서만 실행:

| 설계도의 부품 | 하는 일 (비유) | 실제 코드 위치 |
|---|---|---|
| Planner (기획자) | 질문 의도 파악 + "어떤 데이터를 조회할지" 계획 수립 | `agent/nodes/planner.py` + `agent/config/intents.yaml` |
| Actor (실행자) | 계획대로 데이터 조회 도구들을 동시에 실행 | `agent/nodes/actor.py` |
| Evaluator (검수자) | 모은 데이터가 답변에 충분한지 판정, 부족하면 재시도 | `agent/nodes/evaluator.py` |
| Respond (작가) | 최종 한국어 답변을 작성해 한 글자씩 전송 | `agent/nodes/respond.py` |

**두 경로 공용**:

| 설계도의 부품 | 하는 일 | 실제 코드 위치 |
|---|---|---|
| 도메인 도구 9종 | 유동인구/매출/점포/비교/추천/시뮬레이션 등 데이터 조회기 | `agent/tools/` (registry.py 가 명단 관리) |
| 대화 기억 | "거기서 카페는?" 같은 이어지는 질문 이해 (v2는 최근 6턴 주입) | `agent/history.py` |

### ④ 데이터 — `server/server/repositories/`, `models/`, `data/`

| 설계도의 부품 | 하는 일 | 실제 코드 위치 |
|---|---|---|
| DB 테이블 정의 | 상권/유동인구/매출/점포 테이블 구조 | `server/server/models/` |
| 저장소 (Repository) | "DB에서 데이터 꺼내오기"를 담당하는 창구 | `repositories/real/` (실데이터) · `repositories/mock/` (연습용) |
| 저장소 계약서 | Mock과 Real이 똑같은 모양을 갖도록 강제하는 인터페이스 | `repositories/protocols.py` |
| ETL (데이터 적재) | 서울 열린데이터를 내려받아 DB에 채우는 일괄 작업 | `server/server/data/etl/` |
| DB 변경 이력 | 테이블 구조 변경을 버전으로 관리 | `server/alembic/` (001~005) |
| 원본 파일 | 상권 경계 지도파일(SHP), 초기 데이터 덤프 | `data/` |

### ⑤ 인프라/운영

| 부품 | 하는 일 | 위치 |
|---|---|---|
| 개발용 실행 묶음 | DB+캐시+서버+화면을 명령 한 번에 기동 | `docker-compose.yml` |
| 운영용 실행 묶음 | 실서비스(marketscope.robitlabs.co.kr)용 구성 | `docker-compose.prod.yml` |
| 리버스 프록시 | 외부 접속을 안전하게 내부 서버로 연결 | `nginx/` |
| 운영 스크립트 | DB 셋업, 환경 검증, 매출 단위 검증 등 | `scripts/` |
| 자동 테스트 | 사람이 클릭하듯 화면을 자동 검사 (43+ 시나리오) | `frontend/e2e/` (ring0~3) + `server/tests/` |

---

## 3. 기술 스택 선택 근거 — "왜 이걸 골랐나"

각 항목: **선택한 것 / 대안이 있었는데 왜 이것인가**

### 화면 쪽

**Next.js 14 (React)** — 대안: 순수 React(Vite), Vue, Svelte
- 첫 화면(랜딩)은 검색엔진에 잘 노출되어야 하고(SSR), 분석 앱은 복잡한 상호작용이 필요하다. Next.js는 이 둘을 한 프로젝트에서 해결한다.
- `output: standalone` 으로 Docker 배포가 가벼워지고, 생태계(문서·라이브러리·채용 풀)가 가장 크다. 솔로 개발에서는 "막혔을 때 자료가 많은 것"이 곧 속도다.

**TypeScript** — 대안: JavaScript
- "상권 데이터에 어떤 항목이 들어있는지"를 코드가 스스로 검사한다. 서버 ↔ 화면 사이 데이터 모양이 어긋나는 사고(가장 흔한 버그)를 작성 시점에 잡는다. 혼자 개발할수록 컴파일러가 동료 역할을 해준다.

**Kakao Map SDK** — 대안: Google Maps, Naver Maps, Mapbox
- 한국 지도 디테일(골목 단위)과 한국어 지명 품질이 국내 서비스 기준 최상. Google Maps는 국내 정밀 지도 반출 제한으로 디테일이 떨어지고, Mapbox는 유료 + 한국 지명 약함. 타깃 사용자(국내 소상공인)에게 익숙한 지도이기도 하다.

**deck.gl (히트맵)** — 대안: Kakao 기본 오버레이, canvas 직접 그리기
- 1,650개 상권 × 24시간대 유동인구 점을 그리려면 수만 개 도형을 부드럽게 렌더링해야 한다. deck.gl은 GPU(그래픽카드)를 써서 이를 처리한다. 기본 오버레이로는 점이 많아지면 버벅인다.

**Zustand (상태 관리)** — 대안: Redux, React Context, Jotai
- "지도에서 클릭한 상권"을 채팅창도 알아야 하는 식의 화면 간 공유가 핵심인데, Redux는 같은 일에 코드가 3~4배 든다. Zustand는 보일러플레이트가 거의 없고, 스토어 3개(map/chat/district) 규모에 정확히 맞는 크기의 도구다. (Simplicity First)

**Recharts (차트)** — 대안: Chart.js, D3, ECharts
- 카드 UI 안에 들어가는 중간 복잡도 차트(막대·게이지)가 목적. D3는 자유도가 높지만 개발 비용이 크고, Recharts는 React 컴포넌트로 바로 끼워 넣을 수 있어 카드 5종을 빠르게 만들 수 있었다.

**@react-pdf/renderer + html2canvas (PDF)** — 대안: 서버에서 PDF 생성(puppeteer 등)
- 사용자가 보고 있는 차트를 그대로 캡처해 PDF로 만드는 방식이라 서버 부담이 0이다. 서버 생성 방식은 별도 렌더링 서버가 필요해 운영 비용이 늘어난다.

### 서버 쪽

**FastAPI (Python)** — 대안: Node.js(Express/Nest), Django, Spring
- 두 가지가 결정적이다: (1) **AI 생태계가 Python**이다 — LangGraph, Anthropic/Gemini SDK, 데이터 처리 모두 Python이 1군. (2) **async 지원** — AI 답변 스트리밍과 도구 병렬 실행은 "기다리는 동안 다른 일을 하는" 비동기 처리가 필수인데 FastAPI는 이것이 기본이다. Django는 비동기·스트리밍이 약하고, Node.js를 쓰면 AI 라이브러리를 위해 결국 Python 서버를 하나 더 둬야 한다.

**SSE 스트리밍 (Server-Sent Events)** — 대안: WebSocket, 일반 요청-응답
- AI 답변은 길어서(수십 초) 한 번에 주면 사용자가 빈 화면을 오래 본다. SSE는 "서버 → 화면 한 방향으로 글자를 흘려보내는" 가장 단순한 방식. WebSocket은 양방향이 필요할 때 쓰는 더 무거운 도구인데, 채팅 질문은 일반 POST로 충분해서 양방향이 필요 없다. 실제로 TTFT(첫 글자까지 시간)를 25초 → 1.5초로 줄인 핵심.

**모델주도 Agentic Loop v2 + Trust Kernel (현행 기본)** — 대안: PAE 유지, 프레임워크 기성 에이전트
- PAE는 "무엇을 조회할지"를 사람이 짠 규칙·계획 프리셋에 의존해, 규칙 밖 질문(예: "거기 중 유동인구 더 많은 곳은?" 같은 이어지는 질문)에서 도구를 부르지 않고 숫자를 지어내는 사고가 반복됐다. v2는 도구 선택을 모델의 function-calling에 맡기는 대신, (1) **예산 governor**(모델 턴 6회 / 도구 12회 / 90초)로 폭주를 막고 (2) **Trust Kernel**이 답변의 모든 숫자를 도구 결과와 대조해 근거 없는 숫자를 차단한다 — "자유는 모델에게, 검증은 코드에게".
- 트레이드오프: v2 는 검증을 마친 최종 답변을 90자 청크로 흘려보내는 pseudo-streaming — PAE의 true 토큰 스트리밍 대비 첫 글자 체감이 느리다 (스트리밍 재설계는 deferred).

**LangGraph 커스텀 PAE 그래프 (레거시 — mock 경로)** — 대안: LangChain 기본 ReAct 에이전트, 직접 구현
- 처음엔 기성품(create_react_agent)을 썼지만 **블랙박스**였다 — 왜 이상한 답을 했는지 추적이 어려웠다. Planner(기획) → Actor(실행) → Evaluator(검수) 단계를 직접 설계하면 각 단계를 따로 테스트·교체·디버깅할 수 있다. 정확도가 생명인 데이터 분석 서비스라 "통제 가능성"을 선택했다. 최대 3회 재시도 상한으로 폭주도 방지.
- 2026-07-03 v2 머지로 기본 경로에서 물러남 — 현재는 mock provider/E2E 테스트 경로에서만 실행된다.

**Claude + Gemini 역할 분담 (레거시 — PAE 경로)** — 대안: 단일 LLM
- 역할마다 다른 모델: 계획 수립은 정확도가 중요해 Claude Sonnet 4, 검수는 횟수가 많아 저렴·빠른 Gemini Flash, 최종 답변은 한국어 품질 좋은 모델. 한 모델로 통일하면 비싼 모델은 비용 폭탄, 싼 모델은 품질 하락. 한쪽 장애 시 다른 쪽으로 자동 전환(fallback)되는 보험 효과도 있다.
- **v2 루프(현행 기본)는 역할 분담 대신 단일 tool-calling 모델 + 폴백 체인**: anthropic `claude-sonnet-4-6` → gemini pro → gemini flash (`agent/loop/models.py`). 모델 ID 는 전부 settings 에서 오기 때문에 env 로 hotfix 가능(하드코딩 은퇴 모델 ID 사고 재발 방지). 역할 분담의 보험 효과(장애 시 자동 전환)는 per-invoke 폴백 체인으로 승계.

### 데이터 쪽

**PostgreSQL + PostGIS** — 대안: MySQL, MongoDB, 전용 GIS 솔루션
- 핵심 질의가 "이 좌표가 어느 상권 폴리곤 안에 있나"(공간 연산)인데, PostGIS는 이 분야의 사실상 표준이다. MySQL의 공간 기능은 빈약하고, MongoDB는 복잡한 집계·조인(상권×업종×분기 매출)에 불리하다. 공공데이터는 표 형태라 관계형 DB가 자연스럽다.

**Redis (캐시)** — 대안: 캐시 없음, Memcached
- 상권 요약·히트맵은 분기마다 갱신되는 데이터라 24시간 저장해두면 같은 계산을 반복하지 않는다. AI 호출은 건당 돈이 들기 때문에 캐시 적중 = 비용 절감이다. 단, Redis가 죽어도 서비스는 (느려질 뿐) 동작하도록 메모리 fallback을 둠 — 캐시는 보조 장치라는 원칙.

**Repository 패턴 + USE_MOCK 스위치** — 대안: DB 코드 직접 호출
- "연습용 가짜 데이터(mock/)"와 "실제 DB(real/)"를 같은 계약서(protocols.py)로 묶어, 스위치 하나로 전환한다. 덕분에 DB 없이도 화면·AI 전체 흐름을 개발/테스트할 수 있었고(Phase 1A), 자동 테스트도 DB 없이 돈다. 솔로 개발에서 개발 속도를 좌우한 결정.

### 인프라 쪽

**Docker Compose** — 대안: Kubernetes, 클라우드 매니지드(PaaS)
- 서버 1대에 컨테이너 5개(DB/Redis/백엔드/프론트/nginx) 규모다. Kubernetes는 수십~수백 대 운영용 도구라 이 규모엔 관리 비용만 늘어난다(과잉 설계). Compose는 `docker compose up` 한 줄로 동일한 환경을 어디서든 재현한다.

**Nginx (리버스 프록시)** — 대안: Caddy, 클라우드 로드밸런서
- HTTPS 처리와 내부 서버 연결이라는 단순한 역할. 가장 검증되고 자료가 많은 표준 선택. 특히 SSE 스트리밍이 중간에 버퍼링되지 않도록 하는 설정 레퍼런스가 풍부하다.

**Playwright (자동 테스트)** — 대안: Cypress, Selenium
- 실제 브라우저로 "지도 클릭 → AI 답변 확인"까지 사람처럼 검사한다. Cypress는 멀티탭·모바일 뷰포트 에뮬레이션이 약한데, 이 서비스는 모바일(BottomSheet) 검증이 필수라 4개 디바이스 프로젝트(chromium/iphone/galaxy/ipad)를 지원하는 Playwright가 맞았다.

**Langfuse (AI 관측)** — 대안: 자체 로깅, LangSmith
- AI 호출마다 "얼마 들었나, 품질 점수는 몇 점인가"를 대시보드로 본다. AI 비용이 곧 원가인 서비스라 필수. 오픈소스 + 셀프호스팅 가능성이 LangSmith 대비 장점.

---

## 4. 선택을 관통하는 3가지 원칙

1. **솔로 개발자의 속도**: 자료 많고(Next.js, Postgres, Nginx), 코드량 적은(Zustand, FastAPI) 도구. 운영할 사람이 1명이므로 관리 비용이 낮아야 한다.
2. **규모에 맞는 크기**: 서버 1대 규모에 Kubernetes/Redux 같은 대규모용 도구를 쓰지 않음. 반대로 공간 연산(PostGIS)·GPU 렌더링(deck.gl)처럼 꼭 필요한 곳엔 전문 도구를 씀.
3. **장애에 무너지지 않기**: 캐시 죽어도 동작(graceful degradation), AI 연속 실패 시 회로 차단(Circuit Breaker), 모델 장애 시 대체 모델(fallback). 외부 의존이 많은 서비스라 "하나가 죽어도 전체는 산다"를 기본값으로.
