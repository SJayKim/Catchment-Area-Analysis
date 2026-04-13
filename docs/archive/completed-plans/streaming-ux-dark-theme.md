# Plan: Streaming UX + Dark Theme 적용

> 작성일: 2026-03-30
> 참조 프로젝트: `C:\Users\cyon1\OneDrive\Desktop\agentic_ai`

## Context

agentic_ai 프로젝트의 프론트엔드 UI를 참조하여, 현재 MarketScope AI 프로젝트에 두 가지를 적용한다:
1. **Streaming UX 개선** — 타이핑 커서, 마크다운 렌더링, 메시지/step 애니메이션, thinking step 이모지 + 접기
2. **다크 테마 색상** — CSS 변수 기반 다크 모드 (agentic_ai와 동일한 색상 팔레트)

**제약**: 컴포넌트 트리 구조, SSE 이벤트 타입, Zustand 스토어 인터페이스, Card 컴포넌트는 변경하지 않는다.

---

## Step 1: 의존성 설치

```bash
cd frontend && npm install react-markdown remark-gfm
```

---

## Step 2: `frontend/src/app/globals.css` — CSS 변수 + 애니메이션 + 마크다운 스타일

현재 내용(40줄)을 아래로 교체:

**추가할 내용:**
- `:root` CSS 변수 (다크 테마 색상 팔레트)
- `body` 배경/텍스트를 CSS 변수로 변경
- `.streaming::after` — 블링킹 커서 (`▊`, 0.7s blink)
- `@keyframes msg-in` — 메시지 fade-in (0.25s, translateY 8px)
- `@keyframes step-in` — thinking step slide-in (0.2s, translateX -8px)
- `.animate-msg-in`, `.animate-step-in` 유틸리티 클래스
- `.markdown-body` — 마크다운 렌더링 스타일 (p, code, pre, ul, table, blockquote 등)
- `.thin-scrollbar` 다크 테마 색상 업데이트

**CSS 변수 (agentic_ai 동일):**
```css
:root {
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --bg-tertiary: #283548;
  --bg-accent: #3b82f6;
  --bg-accent-hover: #2563eb;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --border-color: #334155;
  --bot-bubble: #1e293b;
  --user-bubble: #3b82f6;
  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;
  --thinking-bg: rgba(59, 130, 246, 0.06);
  --thinking-border: #3b82f6;
}
```

---

## Step 3: `frontend/tailwind.config.ts` — 새 키프레임 추가

기존 `fadeIn` 유지, `msgIn`/`stepIn` 키프레임 + 애니메이션 추가:

```ts
keyframes: {
  fadeIn: { /* 기존 유지 */ },
  msgIn: {
    '0%': { opacity: '0', transform: 'translateY(8px)' },
    '100%': { opacity: '1', transform: 'translateY(0)' },
  },
  stepIn: {
    '0%': { opacity: '0', transform: 'translateX(-8px)' },
    '100%': { opacity: '1', transform: 'translateX(0)' },
  },
},
animation: {
  fadeIn: 'fadeIn 0.3s ease-in forwards',
  msgIn: 'msgIn 0.25s ease-out forwards',
  stepIn: 'stepIn 0.2s ease-out forwards',
},
```

---

## Step 4: `frontend/src/app/layout.tsx` — body 스타일 변경

`<body>`에 CSS 변수 기반 배경/텍스트 색상 적용:

```tsx
<body className={`${inter.className} h-full`}
  style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
```

---

## Step 5: `frontend/src/stores/chatStore.ts` — TOOL_LABELS에 이모지 추가

**변경 범위**: `TOOL_LABELS` 값에 `icon` 필드 추가, 각 `handleSSEEvent` case에서 label 문자열에 이모지 prefix 추가.

```ts
const TOOL_LABELS: Record<string, { progress: string; done: string; icon: string }> = {
  get_floating_population_tool: { progress: '유동인구 조회 중...', done: '유동인구 조회 완료', icon: '🔍' },
  get_estimated_sales_tool:     { progress: '추정매출 조회 중...', done: '추정매출 조회 완료', icon: '🔍' },
  get_store_info_tool:          { progress: '점포 현황 조회 중...', done: '점포 현황 조회 완료', icon: '🔍' },
  get_population_info_tool:     { progress: '인구 데이터 조회 중...', done: '인구 데이터 조회 완료', icon: '🔍' },
  get_district_summary_tool:    { progress: '상권 요약 생성 중...', done: '상권 요약 생성 완료', icon: '📋' },
  compare_districts_tool:       { progress: '상권 비교 분석 중...', done: '상권 비교 분석 완료', icon: '📊' },
  recommend_business_tool:      { progress: '업종 추천 분석 중...', done: '업종 추천 분석 완료', icon: '💡' },
  get_store_history_tool:       { progress: '점포 이력 분석 중...', done: '점포 이력 분석 완료', icon: '📋' },
};
```

**handleSSEEvent 라벨 변경 (문자열 값만):**
- thinking 초기: `'🧠 질문 분석 중...'`
- thinking 완료: `'🧠 질문 분석 완료'`
- response step: `'💬 응답 작성 중...'`
- tool step: `` `${icon} ${progress}` ``
- tool_end: `` `${icon} ${done}` ``
- final step: `'✅ 분석 완료'`
- card step: `` `📊 ${cardLabel} 생성 완료` ``

**초기 step (line 135-137):**
```ts
agentSteps: [{ id: 'thinking', label: '🧠 질문 분석 중...', status: 'in_progress' }]
```

> ChatState 인터페이스, AgentStep 타입, 스토어 메서드 시그니처는 변경 없음.

---

## Step 6: `frontend/src/components/chat/MessageBubble.tsx` — 마크다운 + 스트리밍 커서 + 다크 테마

**변경 사항:**
1. `react-markdown`/`remark-gfm` import 추가
2. props에 `isStreaming?: boolean` 추가
3. 유저 버블: `bg-primary-500` → `style={{ backgroundColor: 'var(--user-bubble)' }}`, `animate-msg-in` 클래스 추가
4. 어시스턴트 버블: `bg-gray-100` → `style={{ backgroundColor: 'var(--bot-bubble)' }}`, `animate-msg-in` 클래스 추가
5. 텍스트 렌더링: `<p>` → `<ReactMarkdown remarkPlugins={[remarkGfm]}>`를 `<div className="markdown-body">` 안에
6. 스트리밍 시 어시스턴트 버블 div에 `streaming` 클래스 추가 (CSS `::after` 커서)
7. 에러 버블: `bg-red-50` → `style={{ backgroundColor: 'rgba(239,68,68,0.1)', border: '1px solid var(--error)' }}`
8. 아이콘 원: `bg-primary-100` → `style={{ backgroundColor: 'var(--bg-tertiary)' }}`
9. Card fallback(JSON): `bg-gray-50` → `style={{ backgroundColor: 'var(--bg-secondary)' }}`

---

## Step 7: `frontend/src/components/chat/MessageList.tsx` — isStreaming 전달 + 다크 테마

**변경 사항:**
1. props에 `isLoading?: boolean` 추가
2. 마지막 assistant text 메시지 + isLoading일 때 `isStreaming={true}` 전달
3. 빈 상태: `bg-primary-100` → `var(--bg-tertiary)`, `text-gray-700` → `var(--text-primary)`, `text-gray-400` → `var(--text-muted)`
4. thinking dots: `bg-gray-100` → `var(--bot-bubble)`, `bg-gray-400` → `var(--text-muted)`
5. 아이콘 원: `bg-primary-100` → `var(--bg-tertiary)`

---

## Step 8: `frontend/src/components/chat/AgentProgressIndicator.tsx` — 접기/펼치기 + 슬라이드 애니메이션

**변경 사항:**
1. `useState(false)` 추가 → `collapsed` 상태
2. STATUS_ICON을 `{ pending: '⏳', in_progress: '⏳', completed: '✅' }`로 변경 (label에 이미 이모지 포함이므로)
3. 컨테이너: `bg-gray-100` → `style={{ backgroundColor: 'var(--thinking-bg)', border: '1px solid var(--thinking-border)' }}`
4. 헤더 영역 추가: "분석 진행" 텍스트 + ▶/▼ 토글 (클릭 시 collapsed 전환)
5. `animate-msg-in` 래퍼, 각 step에 `animate-step-in` + `animationDelay`
6. 텍스트 색상: `text-gray-400/800/300` → CSS 변수 (`var(--text-muted)`, `var(--text-primary)`)
7. 아이콘 원: `bg-primary-100` → `var(--bg-tertiary)`

---

## Step 9: `frontend/src/components/chat/ChatPanel.tsx` — 다크 테마

**변경 사항:**
1. `bg-white` → `style={{ backgroundColor: 'var(--bg-primary)' }}`
2. 헤더 `border-b border-gray-200` → `style={{ borderBottom: '1px solid var(--border-color)' }}`
3. 텍스트: `text-gray-800` → `var(--text-primary)`, `text-gray-400` → `var(--text-muted)`
4. `<MessageList>`에 `isLoading={isLoading}` prop 전달

---

## Step 10: `frontend/src/components/chat/ChatInput.tsx` — 다크 테마

**변경 사항:**
1. `border-t border-gray-200` → `style={{ borderTop: '1px solid var(--border-color)' }}`
2. textarea: `border-gray-300 disabled:bg-gray-50` → `style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}`
3. 버튼: `bg-primary-500 disabled:bg-gray-300` → `style={{ backgroundColor: disabled ? 'var(--bg-tertiary)' : 'var(--bg-accent)' }}`

---

## Step 11: `frontend/src/components/chat/SuggestionChips.tsx` — 다크 테마

**변경 사항:**
- `bg-primary-50 text-primary-600 border-primary-200 hover:bg-primary-100` → `style={{ backgroundColor: 'var(--thinking-bg)', color: 'var(--bg-accent)', border: '1px solid var(--border-color)' }}`

---

## Step 12: `frontend/src/components/layout/Toolbar.tsx` — 다크 테마

**변경 사항:**
1. 컨테이너: `bg-white border-b border-gray-200` → `style={{ backgroundColor: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)' }}`
2. 로고: `text-primary-600` → `style={{ color: 'var(--bg-accent)' }}`
3. 검색 input: `border-gray-300` → `style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}`
4. 검색 드롭다운: `bg-white border-gray-200` → `style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}`
5. 드롭다운 항목: `text-gray-900` → `var(--text-primary)`, `bg-gray-100` → `var(--bg-tertiary)`
6. 내 위치/비교모드 버튼: `text-gray-600` → `var(--text-secondary)`
7. 비교모드 활성: `bg-indigo-100 text-indigo-700 border-indigo-300` 유지 (시맨틱 색상이므로)

---

## Step 13: `server/server/agent/graph.py` — SSE 이벤트에 icon 필드 추가 (선택)

기존 SSE dict에 `icon` 필드 추가 (하위 호환):

```python
# line 268: thinking 이벤트
yield {"type": "thinking", "step": "분석 중...", "icon": "🧠"}

# line 274-278: tool 이벤트
_TOOL_EMOJI = {
    "get_floating_population_tool": "🔍",
    "get_estimated_sales_tool": "🔍",
    "get_store_info_tool": "🔍",
    "get_population_info_tool": "🔍",
    "get_district_summary_tool": "📋",
    "compare_districts_tool": "📊",
    "recommend_business_tool": "💡",
    "get_store_history_tool": "📋",
}
yield {"type": "tool", "name": tool_name, "input": tool_input, "icon": _TOOL_EMOJI.get(tool_name, "🔧")}

# line 284: tool_end 이벤트
yield {"type": "tool_end", "name": tool_name, "icon": _TOOL_EMOJI.get(tool_name, "🔧")}
```

> `SSEEvent` 타입이 `[key: string]: unknown`이므로 프론트엔드 호환성 문제 없음.

---

## 수정 파일 목록 (13개)

| # | 파일 | 변경 유형 |
|---|------|-----------|
| 1 | `frontend/package.json` | 의존성 추가 (npm install) |
| 2 | `frontend/src/app/globals.css` | CSS 변수, 애니메이션, 마크다운 스타일 |
| 3 | `frontend/tailwind.config.ts` | 키프레임/애니메이션 추가 |
| 4 | `frontend/src/app/layout.tsx` | body 스타일 변경 |
| 5 | `frontend/src/stores/chatStore.ts` | TOOL_LABELS 이모지, label 문자열 |
| 6 | `frontend/src/components/chat/MessageBubble.tsx` | 마크다운 렌더링, 스트리밍 커서, 다크 테마 |
| 7 | `frontend/src/components/chat/MessageList.tsx` | isStreaming 전달, 다크 테마 |
| 8 | `frontend/src/components/chat/AgentProgressIndicator.tsx` | 접기/펼치기, 이모지, 다크 테마 |
| 9 | `frontend/src/components/chat/ChatPanel.tsx` | isLoading 전달, 다크 테마 |
| 10 | `frontend/src/components/chat/ChatInput.tsx` | 다크 테마 |
| 11 | `frontend/src/components/chat/SuggestionChips.tsx` | 다크 테마 |
| 12 | `frontend/src/components/layout/Toolbar.tsx` | 다크 테마 |
| 13 | `server/server/agent/graph.py` | SSE icon 필드 추가 |

## 변경하지 않는 것

- 컴포넌트 트리 구조 (새 컴포넌트 없음, 기존 컴포넌트 이동 없음)
- SSE 이벤트 타입 (`types.ts`의 `SSEEvent` 유니온)
- Zustand `ChatState` 인터페이스
- `AgentStep` 타입 정의
- Card 컴포넌트 (SummaryCard, CompareCard, RecommendCard, RiskCard)
- 지도 관련 컴포넌트 (MapContainer, DistrictLayer, SplitPanel 등)
- useChat.ts, useMapSync.ts 훅
- api.ts, 백엔드 API 라우트

---

## 검증 방법

1. `cd frontend && npm run dev` → 빌드 에러 없이 기동
2. 브라우저에서 다크 테마 적용 확인 (Toolbar, ChatPanel, 빈 상태)
3. 메시지 전송 → fade-in 애니메이션 확인
4. Agent 응답 중 → 블링킹 커서 `▊` 확인
5. Agent 응답 중 → AgentProgressIndicator에 이모지 표시 + 클릭 접기/펼치기
6. 마크다운 응답 (볼드, 리스트, 코드블록 등) 렌더링 확인
7. Card 렌더링 정상 동작 (SummaryCard 등)
8. 기존 E2E 테스트 32개 통과 확인: `npx playwright test`
