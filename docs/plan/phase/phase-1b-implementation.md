# MarketScope AI — Phase 1B 종합 구현 계획

> 작성일: 2026-03-30
> 범위: 데이터 파이프라인 + 스트리밍 UX + Progress Indicator + E2E 테스트

---

## Context

Phase 1A (Mock E2E)가 완료된 상태. Mock 데이터 기반으로 Agent + SSE 스트리밍 + Card UI 4종이 동작 확인됨.
이제 (1) 실제 공공데이터 연결, (2) 스트리밍 UX 개선, (3) Figma-like Progress Indicator, (4) E2E 테스트 검증까지 진행.

**서울 열린데이터 API 키 보유 확인 → 4개 요구사항 모두 즉시 구현.**

---

## 구현 순서 (의존 관계 기반)

```
Step 1: Progress Indicator (Req 3) ← 스트리밍 핵심 변경
   ↓
Step 2: Streaming Enhancement (Req 2) ← Progress 위에 polish
   ↓
Step 3: E2E 테스트 작성 + 반복 수정 (Req 4)
   ↓ (병렬 가능)
Step 4: 데이터 파이프라인 활성화 (Req 1)
```

---

## Step 1: Figma-like Agent Progress Indicator

### 1.1 디자인

```
┌─────────────────────────────────────┐
│  🟢 질문 분석 완료                    │
│  🟢 유동인구 조회 완료                 │
│  🟡 추정매출 조회 중...                │
│  ⚪ 응답 작성 대기                    │
└─────────────────────────────────────┘
```

- 🟡 = in_progress, 🟢 = completed, ⚪ = pending
- 각 단계는 SSE 이벤트에 따라 실시간 추가/상태 변경
- 응답 텍스트 시작 시 indicator fade-out → 텍스트 스트리밍으로 전환

### 1.2 Tool → 한국어 라벨 매핑

| Tool name | 진행 중 | 완료 |
|-----------|--------|------|
| (initial thinking) | 질문 분석 중... | 질문 분석 완료 |
| `get_floating_population_tool` | 유동인구 조회 중... | 유동인구 조회 완료 |
| `get_estimated_sales_tool` | 추정매출 조회 중... | 추정매출 조회 완료 |
| `get_store_info_tool` | 점포 현황 조회 중... | 점포 현황 조회 완료 |
| `get_population_info_tool` | 인구 데이터 조회 중... | 인구 데이터 조회 완료 |
| `get_district_summary_tool` | 상권 요약 생성 중... | 상권 요약 생성 완료 |
| `compare_districts_tool` | 상권 비교 분석 중... | 상권 비교 분석 완료 |
| `recommend_business_tool` | 업종 추천 분석 중... | 업종 추천 분석 완료 |
| `get_store_history_tool` | 점포 이력 분석 중... | 점포 이력 분석 완료 |
| (final response) | 응답 작성 중... | 분석 완료 |

### 1.3 파일 변경

#### `frontend/src/lib/types.ts` — 타입 추가
```typescript
export type AgentStepStatus = 'pending' | 'in_progress' | 'completed';
export interface AgentStep {
  id: string;
  label: string;
  status: AgentStepStatus;
  toolName?: string;
}
// SSEEvent type에 'tool_end' 추가
```

#### `server/server/agent/graph.py` — `tool_end` 이벤트 추가
- `on_tool_end` 핸들러(~line 282)에서 card 이벤트 전에 `{"type": "tool_end", "name": tool_name}` emit

#### `frontend/src/stores/chatStore.ts` — agentSteps 상태 추가
- 새 state: `agentSteps: AgentStep[]`
- actions: `clearAgentSteps`, `addAgentStep`, `updateAgentStepStatus`
- `handleSSEEvent` 수정:
  - `thinking` → step 추가 (🟡 질문 분석 중...)
  - `tool` → 이전 thinking step 완료(🟢), 새 tool step 추가(🟡)
  - `tool_end` → 해당 tool step 완료(🟢)
  - `text` (첫 토큰) → 모든 step 완료, "응답 작성 중..." 추가 후 즉시 완료
  - `done` → agentSteps 초기화
- `sendMessage` 시작 시 `clearAgentSteps()` 호출

#### `frontend/src/components/chat/AgentProgressIndicator.tsx` — 신규 컴포넌트
- props: `steps: AgentStep[]`
- 각 step을 circle emoji + label로 렌더링
- Tailwind: `text-sm`, completed=`text-gray-500`, in_progress=`text-gray-800 font-medium`
- 새 step 추가 시 fade-in 애니메이션 (`animate-fadeIn` or `transition-opacity`)

#### `frontend/src/components/chat/MessageList.tsx` — bouncing dots 교체
- lines 46-61의 bouncing dots → `<AgentProgressIndicator steps={agentSteps} />`
- 조건: `isThinking && agentSteps.length > 0`

### 1.4 Checklist
- [ ] `types.ts`에 `AgentStep`, `AgentStepStatus` 타입 추가
- [ ] `types.ts` SSEEvent에 `'tool_end'` 추가
- [ ] `graph.py`에 `tool_end` SSE 이벤트 emit
- [ ] `chatStore.ts`에 `agentSteps` state + actions 추가
- [ ] `chatStore.ts` `handleSSEEvent`에서 thinking/tool/tool_end/text/done 처리
- [ ] `chatStore.ts` `sendMessage`에서 `clearAgentSteps()` 호출
- [ ] `AgentProgressIndicator.tsx` 컴포넌트 생성
- [ ] Tool name → 한국어 라벨 매핑 유틸 작성
- [ ] `MessageList.tsx` bouncing dots → AgentProgressIndicator 교체
- [ ] fade-in 애니메이션 적용

---

## Step 2: Streaming Enhancement (Progress 위에 polish)

### 2.1 파일 변경

#### `chatStore.ts` — 엣지케이스 처리
- Tool 없는 직접 응답: thinking → text만 올 때 "질문 분석 중..." → "응답 작성 중..." 자연 전환
- 에러 발생 시: in_progress step들을 ⚪ (gray)로 변경 + 에러 메시지 표시
- 다중 tool 순차 호출: 각 tool_start/tool_end 쌍이 순서대로 업데이트

#### `AgentProgressIndicator.tsx` — 전환 효과
- 텍스트 스트리밍 시작 시 300ms fade-out
- 모든 step 🟢 flash → 사라짐

### 2.2 Checklist
- [ ] Tool 없는 직접 응답 처리 (thinking → text)
- [ ] 에러 시 in_progress step 정리
- [ ] 다중 tool 순차 호출 정상 동작 확인
- [ ] Progress → 텍스트 전환 시 fade-out 효과
- [ ] 수동 브라우저 테스트: 5개 시나리오 확인

---

## Step 3: E2E 테스트 (~20개 시나리오)

### 3.1 테스트 파일 구성

#### `frontend/e2e/feature4-progress-indicator.spec.ts` (신규, 6개)

| ID | 시나리오 | 검증 |
|----|---------|------|
| 4-1 | 메시지 전송 시 progress 표시 | 🟡 emoji 2초 내 출현 |
| 4-2 | tool 호출 시 단계 추가 | "유동인구" 관련 step 텍스트 출현 |
| 4-3 | tool 완료 시 🟢 전환 | 🟢 emoji 출현 확인 |
| 4-4 | 응답 완료 시 indicator 사라짐 | progress 영역 DOM에서 제거 |
| 4-5 | 다중 tool 호출 시 순차 표시 | "요약" 요청 → 2개 이상 step 표시 |
| 4-6 | 에러 시 indicator 정리 | indicator stuck 안 됨 확인 |

#### `frontend/e2e/feature5-card-rendering.spec.ts` (신규, 5개)

| ID | 시나리오 | 검증 |
|----|---------|------|
| 5-1 | SummaryCard 렌더링 | "강남역 요약" → 차트 + 유동인구 데이터 표시 |
| 5-2 | CompareCard 렌더링 | "강남역이랑 홍대 비교" → 비교표 렌더링 |
| 5-3 | RecommendCard 렌더링 | "뭐하면 좋을까" → Top 5 추천 리스트 |
| 5-4 | RiskCard 렌더링 | "위험해?" → 안정성 게이지 표시 |
| 5-5 | 카드 데이터 정합성 | 카드에 상권명 + 분기 정보 포함 |

#### `frontend/e2e/feature6-streaming-ux.spec.ts` (신규, 5개)

| ID | 시나리오 | 검증 |
|----|---------|------|
| 6-1 | 텍스트 스트리밍 점진 표시 | 응답이 한번에 아닌 점진적으로 나타남 |
| 6-2 | suggestion chips 표시 | 응답 후 추천 질문 버튼 출현 |
| 6-3 | suggestion chip 클릭 | 클릭 시 새 쿼리 전송 + 응답 |
| 6-4 | 빈 메시지 전송 방지 | 빈 입력 시 전송 안 됨 |
| 6-5 | 로딩 중 중복 전송 방지 | 응답 대기 중 입력 disabled |

#### `frontend/e2e/feature7-error-handling.spec.ts` (신규, 4개)

| ID | 시나리오 | 검증 |
|----|---------|------|
| 7-1 | 네트워크 에러 graceful 처리 | API intercept → 에러 메시지 표시 |
| 7-2 | 에러 후 재시도 가능 | 에러 후 새 메시지 전송 성공 |
| 7-3 | 긴 응답 중 스크롤 자동 이동 | 메시지 추가 시 하단 자동 스크롤 |
| 7-4 | 연속 요청 시 이전 응답 유지 | 2개 질문 → 2개 응답 모두 화면에 존재 |

### 3.2 테스트 헬퍼 업데이트

`frontend/e2e/helpers/setup.ts`:
- `waitForResponseComplete()` — 🟡 emoji 부재도 확인 조건 추가
- `waitForProgressStep(page, labelText)` — 특정 step 출현 대기
- `verifyProgressGone(page)` — progress indicator DOM 제거 확인

### 3.3 실행 전략
```
테스트 작성 → npx playwright test → FAIL 분석 → 코드 수정 → 재실행 → 반복
```

### 3.4 Checklist
- [ ] `feature4-progress-indicator.spec.ts` 작성 (6개 테스트)
- [ ] `feature5-card-rendering.spec.ts` 작성 (5개 테스트)
- [ ] `feature6-streaming-ux.spec.ts` 작성 (5개 테스트)
- [ ] `feature7-error-handling.spec.ts` 작성 (4개 테스트)
- [ ] `helpers/setup.ts` 헬퍼 함수 업데이트
- [ ] 기존 feature1~3 테스트에 progress indicator 검증 추가
- [ ] 전체 테스트 실행 → ALL PASS 확인
- [ ] FAIL 테스트 원인 분석 → 코드 수정 → 재실행 반복

---

## Step 4: 데이터 파이프라인 활성화

### 4.1 데이터 소스 & 활용 계획

| 데이터 | 소스 | API 서비스 | 적재 테이블 | 활용 기능 |
|--------|------|-----------|------------|----------|
| 상권 폴리곤 | 서울열린데이터 | VwsmTrdarSelngW (OA-15560) | `districts` | F01 지도, 전체 기반 |
| 유동인구 | 서울열린데이터 | VwsmTrdarFlpopQq (OA-15568) | `floating_population` | F03 리포트, F06 히트맵 |
| 추정매출 | 서울열린데이터 | VwsmTrdarSelngQq (OA-15572) | `estimated_sales` | F04 업종분석, F09 시뮬 |
| 점포정보 | 서울열린데이터 | VwsmTrdarStorW (OA-15577) | `stores` | F05 비교, F07 추천 |
| 상주인구 | 서울열린데이터 | VwsmTrdarPopltnQq (OA-15570) | `resident_population` | F03, F07 |
| 직장인구 | 서울열린데이터 | VwsmTrdarWrcPopltnQq (OA-15569) | `resident_population` | F03, F07 |
| 상권변화지표 | 서울열린데이터 | VwsmTrdarStorQq (OA-15571) | (확장) | F03 상태 판정 |

**좌표계 변환**: EPSG:5181 (서울 로컬) → EPSG:4326 (WGS84) — `transformers.py`에 구현 완료

**캐싱 전략**:
- Redis TTL 24h — 분기 데이터이므로 장기 캐시 가능
- 키 패턴: `{tool_type}:{district_code}:{quarter}`
- ETL 완료 시 관련 캐시 무효화

### 4.2 실행 단계

#### 4.2.1 인프라 기동
```bash
docker compose up -d db redis
# PostGIS extension 확인
docker compose exec db psql -U marketscope -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

#### 4.2.2 환경 변수 설정
`.env` 파일에 추가:
```
USE_MOCK=false
SEOUL_OPENDATA_API_KEY=<서울열린데이터 인증키>
DATABASE_URL=postgresql+asyncpg://marketscope:devpassword@localhost:5432/marketscope
DATABASE_URL_SYNC=postgresql://marketscope:devpassword@localhost:5432/marketscope
REDIS_URL=redis://localhost:6379/0
```

#### 4.2.3 DB 스키마 생성
```bash
cd server
python -c "from server.models.base import Base; from sqlalchemy import create_engine; engine = create_engine('postgresql://...'); Base.metadata.create_all(engine)"
```
- 또는 Alembic migration 실행

#### 4.2.4 ETL 실행 (1분기 데이터)
```bash
python -m server.data.etl.runner run 2025Q3 --dry-run  # 테스트
python -m server.data.etl.runner run 2025Q3             # 실제 적재
python -m server.data.etl.runner validate 2025Q3        # 검증
```

#### 4.2.5 전환 & 검증
- `USE_MOCK=false`로 서버 재시작
- 브라우저에서 실제 폴리곤 지도 표시 확인
- Agent tool이 실제 DB 데이터 반환 확인
- Redis 캐시 히트 확인 (두번째 조회 속도 개선)

### 4.3 Checklist
- [ ] Docker Compose로 PostGIS + Redis 기동
- [ ] PostGIS extension 활성화
- [ ] `.env` 파일에 API 키 + DB URL 설정
- [ ] DB 스키마 생성 (테이블 + 인덱스 + unique constraint)
- [ ] ETL dry-run 성공
- [ ] ETL 실제 1분기(2025Q3) 적재 실행
- [ ] ETL validate 통과 (row count, NULL 비율 확인)
- [ ] `USE_MOCK=false` 전환
- [ ] 실제 폴리곤 지도 렌더링 확인
- [ ] Agent tool 실제 데이터 반환 확인
- [ ] Redis 캐시 동작 확인
- [ ] SSE 첫 토큰 2초 이내 확인

---

## 수정 대상 파일 목록

| 파일 | 변경 내용 |
|------|----------|
| `frontend/src/lib/types.ts` | AgentStep, AgentStepStatus 타입 + SSEEvent에 tool_end |
| `frontend/src/stores/chatStore.ts` | agentSteps state + SSE 이벤트 핸들링 확장 |
| `frontend/src/components/chat/AgentProgressIndicator.tsx` | **신규** — progress indicator 컴포넌트 |
| `frontend/src/components/chat/MessageList.tsx` | bouncing dots → AgentProgressIndicator 교체 |
| `server/server/agent/graph.py` | tool_end SSE 이벤트 emit 추가 |
| `frontend/e2e/feature4-progress-indicator.spec.ts` | **신규** — 6개 테스트 |
| `frontend/e2e/feature5-card-rendering.spec.ts` | **신규** — 5개 테스트 |
| `frontend/e2e/feature6-streaming-ux.spec.ts` | **신규** — 5개 테스트 |
| `frontend/e2e/feature7-error-handling.spec.ts` | **신규** — 4개 테스트 |
| `frontend/e2e/helpers/setup.ts` | progress 관련 헬퍼 추가 |
| `.env` | API 키, DB URL, USE_MOCK=false |

---

## 검증 방법

### 수동 검증
1. `npm run dev` + `uvicorn` 기동
2. 브라우저에서 상권 클릭 → Progress Indicator 🟡→🟢 전환 확인
3. "강남역 요약해줘" → SummaryCard + progress 표시 확인
4. "홍대랑 비교해줘" → CompareCard + 다중 step 확인
5. 응답 완료 후 indicator 사라짐 + suggestion chips 표시 확인

### 자동 검증
```bash
cd frontend
npx playwright test              # 전체 ~32개 테스트
npx playwright test --reporter=html  # 리포트 생성
```

### 데이터 검증
```bash
python -m server.data.etl.runner validate 2025Q3
# 각 테이블 row count + NULL 비율 출력
```

---

## 전체 Checklist (TODO)

### Step 1: Progress Indicator
- [ ] `types.ts` 타입 추가
- [ ] `graph.py` tool_end 이벤트
- [ ] `chatStore.ts` agentSteps 상태
- [ ] `chatStore.ts` SSE 이벤트 핸들링
- [ ] `AgentProgressIndicator.tsx` 생성
- [ ] Tool → 한국어 라벨 매핑
- [ ] `MessageList.tsx` 교체
- [ ] fade-in 애니메이션

### Step 2: Streaming Polish
- [ ] Tool 없는 직접 응답 처리
- [ ] 에러 시 step 정리
- [ ] 다중 tool 순차 처리
- [ ] fade-out 전환 효과

### Step 3: E2E 테스트
- [ ] feature4 (6개) 작성
- [ ] feature5 (5개) 작성
- [ ] feature6 (5개) 작성
- [ ] feature7 (4개) 작성
- [ ] helpers 업데이트
- [ ] ALL PASS 달성

### Step 4: 데이터 파이프라인
- [ ] Docker 인프라 기동
- [ ] DB 스키마 생성
- [ ] ETL 1분기 적재
- [ ] USE_MOCK=false 전환
- [ ] 실데이터 E2E 확인
- [ ] Redis 캐시 확인
