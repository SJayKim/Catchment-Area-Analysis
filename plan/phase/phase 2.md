# Phase 2 구현 계획 — MarketScope AI

> **작성일:** 2026-03-21
> **선행 조건:** Phase 1 완료 보고서 참조 (`phase 1.md`)
> **원본 계획:** `document/commercial_district_agent_plan.md` Phase 2–3

---

## 목표

Phase 1에서 구축한 핵심 에이전트 + 2개 MCP 서버 + 데이터 파이프라인 위에,
**블로커 해소 → 통합 검증 → 에이전트 확장 → Debate → 프론트엔드 MVP** 순서로 진행하여
실사용 가능한 상권분석 시스템을 완성한다.

---

## 전체 일정 개요

| 스프린트 | 기간 | 핵심 목표 |
|---------|------|----------|
| S1 | Week 1 | 블로커 해소 + 통합 검증 |
| S2 | Week 2–3 | 추가 MCP 서버 + 에이전트 확장 |
| S3 | Week 4 | Debate 시스템 + 메모리 |
| S4 | Week 5–6 | 프론트엔드 MVP + E2E |
| S5 | Week 7 | 안정화 + 프로덕션 준비 |

---

## S1: 블로커 해소 + 통합 검증 (Week 1)

### S1-1. MCP 멀티서버 라우팅 [BLOCKER] ⭐

**현상:** `MCPClient.base_url = "http://localhost:5100"` 하드코딩.
`maps.*` 도구 호출이 Public Data 서버로 전송됨.

**구현 계획:**

```python
# config.py 변경
class MCPSettings:
    mcp_servers: dict[str, str] = {
        "maps": "http://localhost:5101",
        "public_data": "http://localhost:5100",
    }

# mcp_client.py 변경
class MCPClient:
    def __init__(self, server_configs: dict[str, str]):
        self._clients: dict[str, httpx.AsyncClient] = {
            name: httpx.AsyncClient(base_url=url)
            for name, url in server_configs.items()
        }

    def _resolve_server(self, tool_name: str) -> str:
        prefix = tool_name.split(".")[0]  # "maps" or "public_data"
        return prefix

    async def call_tool(self, tool_name: str, args: dict) -> Any:
        server_name = self._resolve_server(tool_name)
        client = self._clients[server_name]
        # ... existing retry logic
```

**작업 항목:**

| # | 작업 | 파일 | 예상 규모 |
|---|------|------|----------|
| 1 | `config.py`에 `mcp_servers` dict 추가 | `app/config.py` | S |
| 2 | `MCPClient` 멀티서버 라우팅 구현 | `app/tools/mcp_client.py` | M |
| 3 | `MCPClient` 팩토리 수정 (graph/nodes.py) | `app/graph/nodes.py` | S |
| 4 | 라우팅 단위 테스트 | `tests/test_mcp_routing.py` | S |

### S1-2. 앱 Lifespan 통합

현재 `cache`, `scheduler`, `monitoring`이 생성만 되고 FastAPI lifespan에 연결 안 됨.

| # | 작업 | 파일 |
|---|------|------|
| 1 | Redis 연결/해제를 lifespan에 추가 | `app/main.py` |
| 2 | APScheduler start/shutdown lifespan 등록 | `app/main.py` |
| 3 | 에이전트 `call_tool` → `cached_call()` 연동 | `app/agents/base.py` |

### S1-3. 설정 정리

| # | 작업 |
|---|------|
| 1 | `DATA_API_KOSIS_KEY`를 config.py Settings에 추가 (현재 os.environ 직접) |
| 2 | `SEMAS_API_KEY`, `SMALL_BIZ_API_KEY` 발급 및 .env 등록 |
| 3 | `ANTHROPIC_API_KEY` 확보 (Debate 시스템 준비) |

### S1-4. E2E 통합 테스트

| # | 테스트 | 검증 대상 |
|---|--------|----------|
| 1 | DB 연결 테스트 | Docker PostgreSQL + Alembic 마이그레이션 |
| 2 | MCP 서버 기동 테스트 | maps(5101) + public_data(5100) 응답 |
| 3 | 단일 에이전트 테스트 | Population → MCP → 구조화 응답 |
| 4 | 풀 파이프라인 테스트 | API → LangGraph → 에이전트 → MCP → 응답 |
| 5 | SSE 스트리밍 테스트 | 실시간 진행 이벤트 수신 |

---

## S2: MCP 서버 확장 + 추가 에이전트 (Week 2–3)

### S2-1. 추가 MCP 서버 (3종)

초기 계획서에서 6개 MCP 서버를 정의. 현재 2종 완료, 4종 미구현.
우선순위로 3종을 추가한다.

#### ① Real Estate MCP Server (port 5102)

| 도구 | 데이터 소스 | 용도 |
|------|-----------|------|
| `realestate.get_rent_prices` | 국토부 실거래가 API | 임대료 시세 |
| `realestate.get_commercial_rent` | 한국부동산원 | 상가 임대 추이 |
| `realestate.get_land_price` | 공시지가 API | 지가 동향 |
| `realestate.get_vacancy_rate` | KB / 한국부동산원 | 공실률 |

#### ② News & SNS MCP Server (port 5103)

| 도구 | 데이터 소스 | 용도 |
|------|-----------|------|
| `news.search_articles` | 네이버 뉴스 API | 상권 관련 기사 |
| `news.search_blogs` | 네이버 블로그 API | 소비자 동향 |
| `news.get_trends` | 네이버 DataLab | 검색 트렌드 |
| `news.get_sentiment` | LLM 기반 분석 | 긍부정 분석 |

#### ③ Regulatory MCP Server (port 5104)

| 도구 | 데이터 소스 | 용도 |
|------|-----------|------|
| `regulatory.get_zoning` | 국토부 토지이용 API | 용도지역 |
| `regulatory.get_permits` | 지자체 인허가 API | 영업허가 요건 |
| `regulatory.get_restricted_areas` | 지자체 조례 DB | 거리제한 |

### S2-2. 추가 에이전트 (5종)

초기 계획서 기준 10종 에이전트 중 현재 7종 완료. 3종 + Debate 3종 추가.

| 에이전트 | Role | 입력 | 출력 스키마 |
|---------|------|------|-----------|
| **RealEstateAgent** | 임대료·투자비 분석 | 좌표+업종+면적 | `RealEstateAnalysis` |
| **RegulatoryAgent** | 규제·인허가 분석 | 좌표+업종 | `RegulatoryAnalysis` |
| **TrendAgent** | 트렌드·SNS·뉴스 | 업종+지역 | `TrendAnalysis` |

> Risk, Financial 에이전트는 Phase 3으로 이관 (데이터 확보 후).

### S2-3. LangGraph DAG 확장

```
commander_plan
     ↓
     ├─→ Group 1: [population, competition]   (기존)
     │     ↓
     ├─→ Group 2: [revenue, location]         (기존)
     │     ↓
     ├─→ Group 3: [real_estate, regulatory, trend]  ← 신규
     │     ↓
     └─→ commander_judgment
          ↓ (신뢰도 < 0.6 or 결론 충돌)
          ├─→ [Debate] ← S3에서 구현
          └─→ narrative → visualization → report_assembly
```

- Group 3을 Group 2 이후 병렬 실행
- `should_run_group3` 조건 분기 추가
- 그래프 상태에 새 에이전트 결과 필드 추가

### S2-4. 데이터 수집기 확장

| 수집기 | 대상 API | 매핑 에이전트 |
|--------|---------|-------------|
| `RentCollector` | 국토부 실거래가, KB 시세 | RealEstateAgent |
| `TrendCollector` | 네이버 DataLab, 뉴스 | TrendAgent |
| `RegulatoryCollector` | 국토부 토지이용, 지자체 | RegulatoryAgent |

기존 `BaseCollector` 상속, `collection_logs` 동일 활용.

---

## S3: Debate 시스템 + 메모리 (Week 4)

### S3-1. Debate 에이전트 (3종)

초기 계획서 Section 5 기반. 핵심:

| 에이전트 | 모델 | 역할 |
|---------|------|------|
| **AdvocateAgent** | `gemini/gemini-2.5-pro` | 긍정 관점. 사업 기회 극대화 |
| **CriticAgent** | `anthropic/claude-sonnet-4-20250514` | 비판 관점. 숨겨진 리스크 발굴 |
| **JudgeAgent** | `gemini/gemini-2.5-pro` | 양측 논거 평가, 최종 판정 |

**Debate 프로토콜:**

```
트리거 조건:
  - 에이전트 결론 충돌 (낙관 vs 비관 스코어 > 30점 차)
  - commander 신뢰도 < 0.6
  - 사용자 명시 요청

흐름:
  1. commander_judgment → debate_trigger (조건 평가)
  2. advocate.analyze(agent_results, pro_bias=True)
  3. critic.analyze(agent_results, con_bias=True)
  4. judge.evaluate(advocate_result, critic_result) → FinalVerdict
  5. commander_updated_judgment (기존 판단 + verdict 반영)
```

**LangGraph 확장:**

```
commander_judgment
     ↓ (should_debate?)
     ├─→ [advocate, critic]  (병렬)
     │     ↓
     │   debate_complete (배리어)
     │     ↓
     │   judge
     │     ↓
     │   commander_revised   ← 기존 판단 수정
     └─→ skip (debate 불필요)
          ↓
     narrative → visualization → report_assembly
```

### S3-2. 메모리 시스템

초기 계획서 Section 7 기반. 3계층 메모리:

| 계층 | 저장소 | TTL | 용도 |
|------|-------|-----|------|
| **TaskMemory** | Redis Hash | 세션 | 현재 분석 세션의 중간 결과 |
| **PersonalMemory** | PostgreSQL | 영구 | 사용자 선호·과거 분석 이력 |
| **WorldMemory** | LightRAG + PostgreSQL | 영구 | 상권 지식, 업종 인사이트 |

**구현 우선순위:**
1. TaskMemory (Redis 기반, 이미 캐시 인프라 존재) — S3 구현
2. PersonalMemory (DB 기반, 세션 테이블 확장) — S3 구현
3. WorldMemory (LightRAG 통합) — S4로 이관

### S3-3. MCP 모니터링 미들웨어

| 기능 | 상세 |
|------|------|
| 요청/응답 로깅 | 모든 MCP 호출을 구조화 로그로 기록 |
| 지연시간 추적 | 도구별·서버별 P50/P95/P99 |
| 에러율 대시보드 | 서버별 500/429/timeout 카운트 |
| 캐시 적중률 | Redis hit/miss 비율 집계 |

---

## S4: 프론트엔드 MVP + E2E (Week 5–6)

### S4-1. 기술 스택

| 구성 | 선택 |
|------|------|
| Framework | Next.js 15 (App Router) |
| UI | Tailwind CSS + shadcn/ui |
| 상태관리 | React Server Components + Zustand (클라이언트) |
| 차트 | Recharts 또는 Nivo |
| 지도 | Kakao Maps SDK (이미 API 키 보유) |
| SSE 연동 | EventSource API |

### S4-2. 페이지 구성

| 페이지 | 경로 | 핵심 컴포넌트 |
|--------|------|-------------|
| 홈 | `/` | 검색 바, 최근 분석 |
| 분석 입력 | `/analysis/new` | 주소 검색(카카오맵), 업종 선택, 면적 입력 |
| 분석 진행 | `/analysis/[id]` | SSE 실시간 진행률, 에이전트 상태 카드 |
| 분석 결과 | `/analysis/[id]/result` | 대시보드 (점수, 차트, 지도, 내러티브) |
| 비교 분석 | `/analysis/compare` | 2개 이상 지역 나란히 비교 |

### S4-3. 핵심 컴포넌트

```
AnalysisDashboard
├── ScoreCard (종합 점수, 등급 뱃지)
├── AgentResultTabs
│   ├── PopulationTab (시간대 차트, 연령 히스토그램)
│   ├── RevenueTab (매출 트렌드 라인, 업종 바)
│   ├── CompetitionTab (포화도 게이지, 개폐업 차트)
│   ├── LocationTab (카카오맵 + POI 마커)
│   ├── RealEstateTab (임대료 비교, 투자비)
│   └── TrendTab (검색 트렌드, 뉴스)
├── DebatePanel (찬성/반대 논거, 판결)
├── NarrativeSection (경영진 요약)
└── ActionItems (구체적 실행 권고)
```

### S4-4. SSE 연동

```typescript
// hooks/useAnalysisStream.ts
const useAnalysisStream = (analysisId: string) => {
  const [progress, setProgress] = useState<ProgressEvent[]>([]);
  const [status, setStatus] = useState<'running' | 'complete' | 'error'>('running');

  useEffect(() => {
    const es = new EventSource(`/api/v1/analysis/${analysisId}/stream`);
    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'agent_complete') setProgress(prev => [...prev, data]);
      if (data.type === 'final_result') { setStatus('complete'); es.close(); }
    };
    return () => es.close();
  }, [analysisId]);

  return { progress, status };
};
```

### S4-5. E2E 테스트 (프론트 + 백엔드)

| # | 시나리오 | 검증 |
|---|---------|------|
| 1 | 주소 입력 → 분석 시작 | API 202 응답, 세션 생성 |
| 2 | SSE 스트림 수신 | 에이전트 완료 이벤트 < 60초 |
| 3 | 결과 대시보드 렌더링 | 모든 탭 데이터 표시 |
| 4 | Debate 트리거 | 신뢰도 조건 시 debate 패널 |
| 5 | 비교 분석 | 2지역 나란히 비교 |

---

## S5: 안정화 + 프로덕션 준비 (Week 7)

### S5-1. 성능 최적화

| 항목 | 목표 |
|------|------|
| 전체 분석 응답 시간 | < 90초 (MCP 캐시 히트 시 < 30초) |
| MCP 도구 호출 | P95 < 3초 |
| 동시 분석 요청 | 5건 이상 |

### S5-2. 에러 핸들링

| 계층 | 전략 |
|------|------|
| MCP 서버 장애 | Circuit Breaker (5회 실패 → 10초 차단) |
| LLM Rate Limit | Token Bucket + 큐잉 |
| 데이터 수집 실패 | Graceful Degradation (캐시 or 기본값) |
| 에이전트 타임아웃 | 30초 제한, 부분 결과 반환 |

### S5-3. Docker Compose 확장

```yaml
services:
  # 기존
  postgres:  ...
  redis:     ...

  # 추가
  backend:
    build: ./marketscope
    ports: ["8000:8000"]
    depends_on: [postgres, redis, mcp-maps, mcp-public-data]

  mcp-maps:
    build: ./marketscope/app/mcp_servers/maps
    ports: ["5101:5101"]

  mcp-public-data:
    build: ./marketscope/app/mcp_servers/public_data
    ports: ["5100:5100"]

  mcp-realestate:
    build: ./marketscope/app/mcp_servers/realestate
    ports: ["5102:5102"]

  mcp-news:
    build: ./marketscope/app/mcp_servers/news
    ports: ["5103:5103"]

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [backend]
```

### S5-4. 프로덕션 체크리스트

| # | 항목 | 상태 |
|---|------|------|
| 1 | API 키 전체 확보 (SEMAS, 국토부 등) | ☐ |
| 2 | Docker Compose 전 서비스 기동 확인 | ☐ |
| 3 | Alembic 마이그레이션 실행 검증 | ☐ |
| 4 | 시드 데이터 적재 | ☐ |
| 5 | 전체 E2E 테스트 통과 | ☐ |
| 6 | 에러 시나리오 테스트 | ☐ |
| 7 | 로깅·모니터링 확인 | ☐ |
| 8 | CORS·보안 헤더 설정 | ☐ |
| 9 | 환경변수 분리 (.env.production) | ☐ |

---

## 의존성 그래프

```
S1-1 (MCP 라우팅) ──┐
S1-2 (Lifespan)    ──┤
S1-3 (설정 정리)   ──┤
                     ├──→ S1-4 (통합 테스트)
                     │         │
                     │         ▼
                     ├──→ S2-1 (MCP 서버 3종)
                     │    S2-2 (에이전트 3종)
                     │    S2-3 (DAG 확장)
                     │    S2-4 (수집기 확장)
                     │         │
                     │         ▼
                     ├──→ S3-1 (Debate)
                     │    S3-2 (메모리)
                     │    S3-3 (MCP 모니터링)
                     │         │
                     │         ▼
                     ├──→ S4 (프론트엔드 + E2E)
                     │         │
                     │         ▼
                     └──→ S5 (안정화 + 프로덕션)
```

---

## 즉시 착수 항목 (S1 Day 1)

1. **`app/config.py`** — `mcp_servers: dict[str, str]` 추가
2. **`app/tools/mcp_client.py`** — 멀티서버 라우팅 리팩터링
3. **`app/graph/nodes.py`** — MCPClient 팩토리 수정
4. **`app/main.py`** — lifespan에 Redis + Scheduler 연결
5. **테스트** — MCP 라우팅 + lifespan 단위 테스트
