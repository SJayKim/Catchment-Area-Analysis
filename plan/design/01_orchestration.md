# Phase 1: LangGraph Orchestration Checklist

## 1. 그래프 워크플로우
- [ ] `app/graph/workflow.py` - StateGraph 정의, 노드 등록, 엣지 연결
- [ ] `app/graph/nodes.py` - commander_plan, specialist agents, report 노드 함수
- [ ] `app/graph/edges.py` - 조건부 라우팅 (basic/quick/comparison)

## 2. 실행 흐름 (Phase 1 DAG)
- [ ] START → commander_plan → fan-out(population, competition) → fan-in → fan-out(revenue, location) → fan-in → report_generation → END
- [ ] comparison 모드 지원
- [ ] quick 모드 지원

## 3. 체크포인팅
- [ ] MemorySaver (개발용)
- [ ] 세션별 상태 복원
