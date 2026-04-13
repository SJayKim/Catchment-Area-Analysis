# 04. Actor 노드

> 계획대로 도구를 실행하는 순수 실행기 (LLM 호출 없음)

## 대상 파일

| 파일 | 작업 |
|------|------|
| `server/server/agent/nodes/actor.py` | **신규** — Actor 노드 구현 |

## 의존성

- 01-state-config (AgentState, ToolPlanStep)
- 기존 도구 함수: `server/server/agent/tools/*.py` (변경 없이 재사용)

## TODO

- [ ] `nodes/actor.py` 생성
- [ ] 도구 레지스트리 구현 (`TOOL_REGISTRY: dict[str, Callable]`)
- [ ] dependency layer 분리 함수 (`group_by_dependencies`)
- [ ] 개별 도구 실행 함수 (`execute_tool`)
- [ ] 카드 emission 매핑 (`TOOL_CARD_MAP`)
- [ ] SSE 이벤트 큐 연동 (tool/tool_end 실시간 emit용)
- [ ] `actor_node(state: AgentState) -> dict` 함수

## 상세 구현

### 도구 레지스트리

기존 `graph.py`의 `@tool` 래퍼 함수 내부에서 호출하는 실제 함수를 직접 사용:

```python
from server.agent.tools.floating_population import get_floating_population
from server.agent.tools.estimated_sales import get_estimated_sales
from server.agent.tools.store_info import get_store_info
from server.agent.tools.population_info import get_population_info
from server.agent.tools.district_summary import get_district_summary
from server.agent.tools.compare_districts import compare_districts
from server.agent.tools.recommend_business import recommend_business
from server.agent.tools.store_history import get_store_history

TOOL_REGISTRY: dict[str, Callable] = {
    "get_district_summary_tool": get_district_summary,
    "get_floating_population_tool": get_floating_population,
    "get_estimated_sales_tool": get_estimated_sales,
    "get_store_info_tool": get_store_info,
    "get_population_info_tool": get_population_info,
    "compare_districts_tool": compare_districts,
    "recommend_business_tool": recommend_business,
    "get_store_history_tool": get_store_history,
}

TOOL_CARD_MAP: dict[str, str] = {
    "get_district_summary_tool": "summary",
    "compare_districts_tool": "compare",
    "recommend_business_tool": "recommend",
    "get_store_history_tool": "risk",
}

TOOL_EMOJI: dict[str, str] = {
    "get_floating_population_tool": "🔍",
    "get_estimated_sales_tool": "🔍",
    "get_store_info_tool": "🔍",
    "get_population_info_tool": "🔍",
    "get_district_summary_tool": "📋",
    "compare_districts_tool": "📊",
    "recommend_business_tool": "💡",
    "get_store_history_tool": "📋",
}
```

### dependency layer 분리

```python
def group_by_dependencies(plan: list[ToolPlanStep]) -> list[list[ToolPlanStep]]:
    """depends_on 기준으로 병렬 실행 가능한 layer로 분리.

    Layer 0: depends_on이 비어있는 step들 (병렬 실행)
    Layer 1: Layer 0에 의존하는 step들 (Layer 0 완료 후 병렬 실행)
    ...
    """
    layers: list[list[ToolPlanStep]] = []
    resolved: set[int] = set()

    while len(resolved) < len(plan):
        current_layer = []
        for i, step in enumerate(plan):
            if i in resolved:
                continue
            if all(dep in resolved for dep in step["depends_on"]):
                current_layer.append(step)
        if not current_layer:
            # 순환 의존 방지: 남은 step 모두 현재 layer에 추가
            for i, step in enumerate(plan):
                if i not in resolved:
                    current_layer.append(step)
            resolved.update(range(len(plan)))
        else:
            for step in current_layer:
                resolved.add(plan.index(step))
        layers.append(current_layer)

    return layers
```

### 도구 실행

```python
async def execute_tool(step: ToolPlanStep) -> tuple[str, dict | None, str | None]:
    """단일 도구 실행. (tool_name, result, error) 반환."""
    tool_fn = TOOL_REGISTRY.get(step["tool_name"])
    if not tool_fn:
        return step["tool_name"], None, f"Unknown tool: {step['tool_name']}"

    try:
        result = await tool_fn(**step["args"])
        if isinstance(result, dict) and "error" in result:
            return step["tool_name"], result, result["error"]
        return step["tool_name"], result, None
    except Exception as e:
        return step["tool_name"], None, str(e)
```

### actor_node 함수

```python
async def actor_node(state: AgentState, event_queue: asyncio.Queue | None = None) -> dict:
    """계획대로 도구 실행. LLM 호출 없음."""
    tool_results = dict(state.get("tool_results", {}))
    tool_errors = dict(state.get("tool_errors", {}))
    card_emissions = list(state.get("card_emissions", []))

    layers = group_by_dependencies(state["plan"])

    for layer in layers:
        # 각 도구 실행 전 SSE 이벤트 emit
        for step in layer:
            if event_queue:
                await event_queue.put({
                    "type": "tool",
                    "name": step["tool_name"],
                    "input": step["args"],
                    "icon": TOOL_EMOJI.get(step["tool_name"], "🔧"),
                })

        # 병렬 실행
        results = await asyncio.gather(
            *[execute_tool(step) for step in layer],
            return_exceptions=True,
        )

        for step, result in zip(layer, results):
            if isinstance(result, Exception):
                tool_errors[step["tool_name"]] = str(result)
            else:
                name, data, error = result
                if error:
                    tool_errors[name] = error
                if data:
                    tool_results[name] = data

            # tool_end 이벤트
            if event_queue:
                await event_queue.put({
                    "type": "tool_end",
                    "name": step["tool_name"],
                    "icon": TOOL_EMOJI.get(step["tool_name"], "🔧"),
                })

            # 카드 emission
            card_type = TOOL_CARD_MAP.get(step["tool_name"])
            if card_type and step["tool_name"] in tool_results:
                card_emissions.append({
                    "card_type": card_type,
                    "data": tool_results[step["tool_name"]],
                })

    return {
        "tool_results": tool_results,
        "tool_errors": tool_errors,
        "card_emissions": card_emissions,
    }
```

## Checklist

- [ ] `TOOL_REGISTRY`에 8개 도구 모두 등록
- [ ] `TOOL_CARD_MAP`에 4개 카드 매핑 (summary, compare, recommend, risk)
- [ ] `group_by_dependencies` — depends_on=[] 인 step들이 같은 layer에 배치
- [ ] `group_by_dependencies` — 순환 의존 시 무한루프 방지
- [ ] `execute_tool` — 도구 함수를 `**step["args"]`로 호출
- [ ] `execute_tool` — 도구 내부 에러({"error": "..."}) 캐치
- [ ] `execute_tool` — 예외 발생 시 (name, None, error_msg) 반환
- [ ] `actor_node` — 이전 라운드의 tool_results 보존 (dict 복사 후 추가)
- [ ] `actor_node` — event_queue가 None이면 SSE 이벤트 미emit (단위 테스트용)
- [ ] LLM 호출 코드가 actor_node에 없음 (순수 실행기)
- [ ] 기존 도구 함수(`tools/*.py`)에 변경 없음

## 시나리오 테스트

### T04-01: 단일 도구 실행 — Summary
```
조건: plan=[{tool_name: "get_district_summary_tool", args: {district_code: "D3001"}, depends_on: []}]
기대: tool_results에 "get_district_summary_tool" 키로 요약 데이터 존재
      card_emissions에 {card_type: "summary", data: ...} 포함
검증: actor_node 직접 호출 (event_queue=None)
판정: PASS — 결과 + 카드 정확 / FAIL
```

### T04-02: 병렬 실행 — Category Analysis (2개 도구)
```
조건: plan=[
  {tool_name: "get_estimated_sales_tool", args: {district_code: "D3001"}, depends_on: []},
  {tool_name: "get_store_info_tool", args: {district_code: "D3001"}, depends_on: []}
]
기대: 두 도구가 같은 layer에서 병렬 실행, 둘 다 tool_results에 존재
검증: group_by_dependencies → 1개 layer, actor_node 결과에 2개 키
판정: PASS — 1 layer + 2 결과 / FAIL — 순차 실행 또는 결과 누락
```

### T04-03: 순차 실행 — 의존성 있는 계획
```
조건: plan=[
  {tool_name: "get_district_summary_tool", args: {...}, depends_on: []},      # step 0
  {tool_name: "get_floating_population_tool", args: {...}, depends_on: [0]},  # step 1
]
기대: layer 0에 step 0, layer 1에 step 1 → 순차 실행
검증: group_by_dependencies → 2개 layer
판정: PASS — 2 layers 정확 / FAIL
```

### T04-04: 도구 실패 처리
```
조건: plan에 존재하지 않는 도구명 "nonexistent_tool" 포함
기대: tool_errors에 해당 에러 기록, 다른 도구는 정상 실행
검증: actor_node 호출 후 tool_errors 키 확인
판정: PASS — 에러 기록 + 나머지 성공 / FAIL — 전체 중단
```

### T04-05: SSE 이벤트 큐
```
조건: event_queue=asyncio.Queue() 전달, 2개 도구 실행
기대: 큐에 tool → tool_end → tool → tool_end 순서로 4개 이벤트
검증: 큐에서 모든 이벤트 꺼내서 type과 순서 확인
판정: PASS — 이벤트 순서 정확 / FAIL — 순서 불일치 또는 누락
```

### T04-06: 이전 라운드 결과 보존
```
조건: state에 tool_results={"get_district_summary_tool": {...}} 이미 존재
      plan=[{tool_name: "get_floating_population_tool", ...}] 추가 실행
기대: 반환된 tool_results에 기존 summary + 새 floating_population 둘 다 존재
검증: 반환 dict의 키 수 확인
판정: PASS — 기존 결과 보존 + 새 결과 추가 / FAIL — 기존 결과 유실
```

### T04-07: 빈 계획
```
조건: plan=[] (도구 호출 불필요)
기대: tool_results 변경 없음, card_emissions 변경 없음
검증: actor_node 호출 후 상태 변화 없음
판정: PASS / FAIL
```
