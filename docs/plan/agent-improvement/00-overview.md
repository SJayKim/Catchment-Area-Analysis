# Agent Improvement Plan — Overview

> Planner-Actor-Evaluator 멀티턴 Agent 전환 마스터 플랜

## 배경

현재 `create_react_agent`(langgraph.prebuilt) 블랙박스를 **Planner → Actor → Evaluator** 커스텀 그래프로 전환.

**현재 문제점**:
1. 멀티턴 대화 불가 (매 요청 SystemMessage + HumanMessage 1개만 전달)
2. 비효율적 도구 호출 (ReAct가 매 도구마다 LLM 추론)
3. 평가 부재 (도구 결과 충분성 검증 없이 바로 응답)
4. Follow-up 불가 ("거기서 카페는?", "아까 그 상권" 등 맥락 참조 불가)

## 아키텍처

```
START → PLANNER → ACTOR → EVALUATOR → RESPOND → END
              ↑                  │
              └── insufficient ──┘ (max 3회)

        PLANNER → RESPOND (direct, 도구 불필요 시)
```

## 기능 모듈 분리

| # | 모듈 | 파일 | 의존성 |
|---|------|------|--------|
| 01 | [State 확장 + Config](./01-state-config.md) | state.py, config.py | 없음 |
| 02 | [대화 이력 관리](./02-conversation-history.md) | history.py, chat.py | 01 |
| 03 | [Planner 노드](./03-planner-node.md) | nodes/planner.py, prompts/planner.py | 01, 02 |
| 04 | [Actor 노드](./04-actor-node.md) | nodes/actor.py | 01 |
| 05 | [Evaluator 노드](./05-evaluator-node.md) | nodes/evaluator.py, prompts/evaluator.py | 01 |
| 06 | [Respond 노드](./06-respond-node.md) | nodes/respond.py, prompts/system.py | 01, 02 |
| 07 | [Graph 조립 + SSE 스트리밍](./07-graph-sse.md) | graph.py | 01~06 |
| 08 | [Chat API 통합](./08-chat-api-integration.md) | chat.py | 02, 07 |
| 09 | [프론트엔드 연동](./09-frontend-integration.md) | types.ts, chatStore.ts | 07 |
| 10 | [UX 개선 (동적 제안/맥락 해석)](./10-ux-improvements.md) | 03, 05, 06 통합 | 03~08 |

## 구현 순서

```
Phase A (인프라, 기존 동작 유지):  01 → 02
Phase B (노드 구현, 병렬 존재):    03 → 04 → 05 → 06 → 07
Phase C (통합 + 전환):            08 → 09
Phase D (UX 강화):                10
```

## 롤백 전략

- `config.py`의 `agent_mode = "react" | "pae"` 플래그로 전환
- Phase C까지 `agent_mode = "react"`로 즉시 복원 가능
- Phase D 완료 후 legacy 코드 제거

## 전체 완료 기준

모든 모듈의 시나리오 테스트가 **PASS** 해야 최종 완료:
- 01~06: 각 모듈 단위 테스트 PASS
- 07~08: 통합 테스트 PASS (SSE 이벤트 순서, 에러 핸들링)
- 09: 프론트엔드 호환성 테스트 PASS
- 10: UX 시나리오 테스트 PASS
