# Card UI 다크 테마 + .gitignore 정리 구현 계획

> 작성일: 2026-03-31
> 대상: Next Items #1 (Card UI 다크 테마), #2 (.gitignore 정리)

## Context

Phase 1B 완료 후 Dark Theme이 ChatPanel, MessageBubble, Toolbar 등에 적용되었으나, **Card UI 4종**(SummaryCard, CompareCard, RecommendCard, RiskCard)과 **InlineChart**에는 `bg-white`, `text-gray-700` 등 라이트 모드 색상이 하드코딩되어 있어 다크 테마와 불일치. `.gitignore`에도 test-results, .playwright-mcp 디렉토리가 누락.

## 적용 패턴

기존 다크 테마 적용 컴포넌트(ChatPanel, MessageBubble)와 동일하게 **inline style + CSS 변수** 패턴 사용:
```tsx
style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
```

### CSS 변수 매핑 (globals.css에 이미 정의됨)

| 용도 | 기존 (라이트 하드코딩) | 변경 (CSS 변수) |
|------|----------------------|----------------|
| 카드 배경 | `bg-white` | `var(--bg-secondary)` (#1e293b) |
| 서브 섹션 배경 | `bg-gray-50`, `bg-gray-100` | `var(--bg-tertiary)` (#283548) |
| 주요 텍스트 | `text-gray-800`, `text-gray-700` | `var(--text-primary)` (#f8fafc) |
| 보조 텍스트 | `text-gray-500`, `text-gray-600` | `var(--text-secondary)` (#94a3b8) |
| 약한 텍스트 | `text-gray-400` | `var(--text-muted)` (#64748b) |
| 테두리 | `border-gray-200`, `border-gray-100` | `var(--border-color)` (#334155) |
| 그라디언트 헤더 | 유지 (각 카드 고유 색상) | **변경 없음** |
| 상태 뱃지 | `bg-green-100 text-green-700` 등 | 반투명 배경으로 변경 (e.g., `rgba(16,185,129,0.15)`) |

## 수정 대상 파일 (6개)

### 1. SummaryCard.tsx
`frontend/src/components/chat/cards/SummaryCard.tsx`
- 카드 외곽: `bg-white border-gray-200` → CSS 변수
- 요약 섹션: `bg-gray-50` → `var(--bg-tertiary)`
- 텍스트: `text-gray-700/600/500` → CSS 변수
- 푸터: `bg-gray-50 text-gray-400` → CSS 변수
- 상태 뱃지: 반투명 배경으로 변경

### 2. CompareCard.tsx
`frontend/src/components/chat/cards/CompareCard.tsx`
- 카드 외곽: `bg-white border-gray-200` → CSS 변수
- 테이블 행: `bg-gray-50` (홀수행) → `var(--bg-tertiary)`
- 텍스트: `text-gray-800/700/500` → CSS 변수
- Winner 뱃지: `bg-green-50 text-green-600` → 반투명
- 푸터: `bg-gray-50 text-gray-400` → CSS 변수

### 3. RecommendCard.tsx
`frontend/src/components/chat/cards/RecommendCard.tsx`
- 카드 외곽: `bg-white border-gray-200` → CSS 변수
- 알림 배너: `bg-amber-50 border-amber-200` → 반투명 amber
- 추천 항목 배경: `bg-gray-50` → `var(--bg-tertiary)`
- 점수 바 배경: `bg-gray-200` → `var(--border-color)`
- 텍스트: `text-gray-700/600/500/400` → CSS 변수
- 푸터: 동일 패턴

### 4. RiskCard.tsx
`frontend/src/components/chat/cards/RiskCard.tsx`
- 카드 외곽: `bg-white border-gray-200` → CSS 변수
- 게이지/바 배경: `bg-gray-200` → `var(--border-color)`
- 생존 바 배경: `bg-gray-100` → `var(--bg-tertiary)`
- 리스크 항목: `bg-gray-50` → `var(--bg-tertiary)`
- 텍스트 전체: CSS 변수로 교체
- 푸터: 동일 패턴

### 5. InlineChart.tsx
`frontend/src/components/chat/cards/InlineChart.tsx`
- CartesianGrid stroke: `#f0f0f0` → `var(--border-color)`
- Axis line stroke: `#e5e7eb` → `var(--border-color)`
- Tooltip: 배경/테두리 다크 테마 적용

### 6. .gitignore
`.gitignore`
- `frontend/test-results/` 추가
- `.playwright-mcp/` 추가 (현재 `*.log`만 제외 중 → 디렉토리 전체 제외)

## 구현 순서

1. `.gitignore` 수정
2. InlineChart.tsx 다크 테마 (차트가 Card 안에 쓰이므로 먼저)
3. SummaryCard.tsx 다크 테마
4. CompareCard.tsx 다크 테마
5. RecommendCard.tsx 다크 테마
6. RiskCard.tsx 다크 테마

## 주의사항

- **그라디언트 헤더는 유지**: 각 카드의 고유 색상 (primary, indigo, amber, red)은 다크 테마에서도 잘 어울림
- **상태 뱃지 색상**: `bg-green-100` 같은 라이트 뱃지는 다크 배경에서 부자연스러우므로 `rgba()` 반투명으로 변경
- **InlineChart Recharts**: CSS 변수를 직접 사용 불가 (SVG prop) → 하드코딩된 다크 색상값 사용
- **Tailwind 클래스 → inline style**: 기존 패턴(ChatPanel)을 따라 `className`의 라이트 색상을 제거하고 `style={{}}` 추가

## 검증 방법

1. `cd frontend && npm run dev` 로 개발 서버 실행
2. 브라우저에서 각 Card가 다크 테마로 표시되는지 확인:
   - 상권 클릭 → SummaryCard
   - "홍대랑 비교해줘" → CompareCard
   - "뭐하면 좋을까?" → RecommendCard
   - "위험해?" → RiskCard
3. InlineChart 차트 색상이 다크 배경에서 가독성 확인
4. `git status`로 .gitignore 반영 확인 (test-results, .playwright-mcp 제외)
