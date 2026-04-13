# 09. 프론트엔드 연동

> SSE 신규 이벤트 핸들링 + AgentProgressIndicator 연동

## 대상 파일

| 파일 | 작업 |
|------|------|
| `frontend/src/lib/types.ts` | **수정** — SSEEvent에 `plan` 타입 추가 |
| `frontend/src/stores/chatStore.ts` | **수정** — `plan` 이벤트 핸들링 추가 |

## 의존성

- 07-graph-sse (SSE 이벤트 포맷)

## TODO

- [ ] `types.ts` SSEEvent union에 `'plan'` 추가
- [ ] `chatStore.ts` handleSSEEvent에 `plan` 케이스 추가
- [ ] `plan` 이벤트 → AgentProgressIndicator에 계획 단계 표시
- [ ] 동적 suggestion 반영 (기존 로직 유지, 데이터만 달라짐)
- [ ] 기존 이벤트(thinking, tool, tool_end, text, card, map_cmd, suggestion, done) 처리 변경 없음

## 상세 구현

### types.ts 변경

```typescript
export interface SSEEvent {
  type: 'thinking' | 'tool' | 'tool_end' | 'text' | 'card' | 'map_cmd'
      | 'suggestion' | 'done' | 'error' | 'plan';  // plan 추가
  [key: string]: unknown;
}
```

### chatStore.ts handleSSEEvent 추가

```typescript
case 'plan': {
  const intent = event.intent as string || '';
  const steps = (event.steps as string[]) || [];

  // 의도 표시 step 추가
  const intentLabels: Record<string, string> = {
    summary: '📋 상권 요약 분석',
    comparison: '📊 상권 비교 분석',
    recommendation: '💡 업종 추천 분석',
    risk: '⚠ 리스크 분석',
    category_analysis: '🔍 업종별 상세 분석',
    follow_up: '💬 추가 분석',
    general: '💬 일반 응답',
    ambiguous: '❓ 질문 확인',
  };

  // 기존 thinking step을 완료 처리
  const thinkingStep = get().agentSteps.find(s => s.status === 'in_progress');
  if (thinkingStep) {
    updateAgentStepStatus(thinkingStep.id, 'completed', intentLabels[intent] || '분석 계획 수립 완료');
  }

  // 계획 단계를 pending으로 추가
  steps.forEach((label, i) => {
    addAgentStep({
      id: `plan-step-${Date.now()}-${i}`,
      label,
      status: 'pending',
    });
  });
  break;
}
```

### 기존 이벤트 — 변경 불필요

| 이벤트 | 변경 | 이유 |
|--------|------|------|
| `thinking` | 없음 | PAE도 동일한 형태로 emit |
| `tool` | 없음 | Actor가 동일한 형태로 emit |
| `tool_end` | 없음 | Actor가 동일한 형태로 emit |
| `text` | 없음 | Respond가 동일한 형태로 emit |
| `card` | 없음 | Actor가 동일한 형태로 emit |
| `map_cmd` | 없음 | chat.py에서 동일하게 발행 |
| `suggestion` | 없음 | 데이터만 동적으로 변경 (처리 로직 동일) |
| `done` | 없음 | 동일 |

## Checklist

- [ ] `types.ts` SSEEvent type에 `'plan'` 추가
- [ ] `chatStore.ts` handleSSEEvent switch문에 `'plan'` case 추가
- [ ] `plan` 이벤트 수신 시 AgentProgressIndicator에 pending step 추가
- [ ] 기존 thinking step이 plan 수신 시 completed로 전환
- [ ] intent별 한국어 라벨 매핑 (8가지 의도)
- [ ] 기존 이벤트 핸들링 코드 변경 없음
- [ ] unknown 이벤트 타입 수신 시 에러 없이 무시 (기존 default 처리)
- [ ] TypeScript 컴파일 에러 없음
- [ ] ESLint + Prettier 통과

## 시나리오 테스트

### T09-01: plan 이벤트 → AgentProgressIndicator
```
조건: SSE로 {"type": "plan", "intent": "summary", "steps": ["상권 요약 조회"]} 수신
기대:
  1. 기존 thinking step → completed ("📋 상권 요약 분석")
  2. 새 pending step 추가 ("상권 요약 조회")
  3. AgentProgressIndicator에 2개 step 표시
검증: 브라우저에서 AgentProgressIndicator 렌더링 확인
판정: PASS — 계획 단계 표시 / FAIL — 미표시 또는 에러
```

### T09-02: plan 이벤트 없이도 정상 동작 (React 모드 호환)
```
조건: agent_mode="react" → plan 이벤트 미발생
기대: 기존 thinking → tool → tool_end → text 흐름 정상 동작
검증: chatStore에서 plan case가 실행되지 않음, 나머지 정상
판정: PASS — 기존 호환 / FAIL
```

### T09-03: 동적 suggestion 렌더링
```
조건: SSE로 {"type": "suggestion", "questions": ["카페 분석해줘", "리스크 확인"]} 수신
기대: SuggestionChips에 "카페 분석해줘", "리스크 확인" 표시
검증: 브라우저에서 chips 텍스트 확인 (기존 하드코딩과 다른 내용)
판정: PASS — 동적 내용 표시 / FAIL — 하드코딩 표시
```

### T09-04: 카드 정상 렌더링 (PAE 호환)
```
조건: PAE 모드에서 summary card 이벤트 수신
기대: SummaryCard 컴포넌트 정상 렌더링 (기존과 동일한 card_type + data 형태)
검증: 카드 UI 렌더링 확인
판정: PASS — 카드 정상 / FAIL — 렌더링 에러
```

### T09-05: TypeScript 빌드
```
조건: npm run build
기대: 컴파일 에러 없음
검증: 빌드 성공 확인
판정: PASS — 빌드 성공 / FAIL — 타입 에러
```

### T09-06: 다중 plan step 표시
```
조건: plan 이벤트에 steps=["매출 데이터 조회", "점포 현황 조회"] (2개)
기대: AgentProgressIndicator에 2개 pending step 순서대로 표시
검증: step 개수 + 순서 확인
판정: PASS / FAIL
```
