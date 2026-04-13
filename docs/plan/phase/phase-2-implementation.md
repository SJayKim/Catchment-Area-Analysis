# Phase 2 구현 계획

> 작성일: 2026-03-25

## 구현 범위

### F04. 업종별 심층 분석
- 기존 `get_estimated_sales`, `get_store_info` Tool에 category_code 필터 이미 지원
- Agent 시스템 프롬프트에 업종 지정 질문 가이드 추가
- 업종 코드 매핑은 Agent LLM이 자연어→category_code 변환 처리

### F05. 상권 비교
- **Backend**: `compare_districts` Tool 신규 구현 (2~3개 상권 병렬 조회)
- **Frontend**: CompareCard 컴포넌트, Toolbar 비교모드 토글, districtStore에 isCompareMode 추가

### F07. 업종 추천
- **Backend**: `recommend_business` Tool 신규 (추천 점수 공식: 점포당매출 × 연령매칭 × (1-폐업률) / 경쟁밀집도, 0~100 정규화)
- **Frontend**: RecommendCard 컴포넌트 (ScoreBar, reasons, 면책 안내)

### F08. 점포 이력/리스크
- **Backend**: `get_store_history` Tool 신규 (안정성 점수, 선형회귀 추세 분석, 위험 업종 식별)
- **Frontend**: RiskCard 컴포넌트 (StabilityGauge, SurvivalBar, 분기별 추이 차트)

### 통합
- Agent graph에 3개 새 Tool 등록 (총 7개)
- 시스템 프롬프트에 새 Tool 설명 및 질문 유형별 가이드 추가
- MessageBubble에 compare/recommend/risk 카드 렌더링 분기 추가
- types.ts에 CompareCardData, RecommendCardData, RiskCardData 타입 추가

## 변경 파일

### Backend (신규)
- `server/agent/tools/compare_districts.py`
- `server/agent/tools/store_history.py`
- `server/agent/tools/recommend_business.py`

### Backend (수정)
- `server/agent/graph.py` — 3개 Tool wrapper + TOOLS 배열 확장
- `server/agent/prompts/system.py` — 새 도구 설명 + 질문 가이드

### Frontend (신규)
- `frontend/src/components/chat/cards/CompareCard.tsx`
- `frontend/src/components/chat/cards/RecommendCard.tsx`
- `frontend/src/components/chat/cards/RiskCard.tsx`

### Frontend (수정)
- `frontend/src/lib/types.ts` — 3개 카드 데이터 인터페이스
- `frontend/src/components/chat/MessageBubble.tsx` — 새 카드 타입 렌더링
- `frontend/src/stores/districtStore.ts` — isCompareMode, toggleCompareMode
- `frontend/src/components/layout/Toolbar.tsx` — 비교모드 버튼

## 미포함 (추후 구현)
- Tier 게이팅 인프라 (인증/결제)
- category_aliases 퍼지 검색 테이블 (현재는 LLM이 직접 매핑)
