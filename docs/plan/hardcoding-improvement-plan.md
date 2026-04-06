# 하드코딩 개선 계획 (5개 항목)

> 작성일: 2026-04-06
> 상태: 계획 수립 완료, 구현 대기

## Context

프로젝트 전반에 키워드 매핑, regex 패턴, Tool 메타데이터, 프론트엔드 라벨, Mock 데이터가 하드코딩되어 있어 새 업종/Tool 추가 시 여러 파일을 동시에 수정해야 하는 문제가 있음. 이를 DB 동적 로딩, 설정 파일 분리, 자동 등록 패턴으로 개선하여 유지보수성을 높이고 단일 진실 소스(single source of truth)를 확보함.

## 구현 순서

```
5 (Mock JSON) → 2 (YAML 인텐트) → 1 (카테고리 DB) → 3 (Tool 레지스트리) → 4 (Frontend 라벨)
```

---

## 1. Mock 데이터 → JSON 파일 분리 (Improvement 5)

**목표**: `mock_data.py` 1,138줄의 Python dict → JSON 파일로 분리

### 파일 변경

| Action | File |
|--------|------|
| CREATE | `server/server/agent/tools/mock/__init__.py` — JSON 로더 (`@lru_cache` 기반) |
| CREATE | `server/server/agent/tools/mock/districts.json` |
| CREATE | `server/server/agent/tools/mock/floating_population.json` |
| CREATE | `server/server/agent/tools/mock/estimated_sales.json` |
| CREATE | `server/server/agent/tools/mock/store_info.json` |
| CREATE | `server/server/agent/tools/mock/population_info.json` |
| CREATE | `server/server/agent/tools/mock/store_history.json` |
| CREATE | `server/server/agent/tools/mock/recommendations.json` |
| MODIFY | `server/server/agent/tools/mock_data.py` — JSON import + helper 함수만 유지 |

### 핵심 설계

```python
# server/server/agent/tools/mock/__init__.py
import json
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent

@lru_cache(maxsize=1)
def _load(name: str) -> dict:
    return json.loads((_DIR / name).read_text("utf-8"))

def get_districts():       return _load("districts.json")
def get_floating_pop():    return _load("floating_population.json")
# ... 5개 더
```

```python
# mock_data.py — 슬림화 (helper 함수 + re-export)
from server.agent.tools.mock import get_districts, get_floating_pop, ...

MOCK_QUARTER = "2025Q3"
DISTRICTS = get_districts()
FLOATING_POPULATION = get_floating_pop()
# ... 기존 public API 유지 → 6개 mock repo 파일 수정 불필요

# Helper 함수들 유지
def get_compare_data(district_codes): ...
def get_recommendations(district_code, budget, preference): ...
def get_mock_geojson(): ...
def get_mock_district_list(search, district_type): ...
```

**리스크**: 낮음 — `mock_data.py`의 public API 불변, mock repo 파일 수정 없음

---

## 2. INTENT_PATTERNS → YAML 설정 파일 (Improvement 2)

**목표**: regex 패턴 + Tool 계획 매핑을 YAML로 분리

### 파일 변경

| Action | File |
|--------|------|
| CREATE | `server/server/agent/config/__init__.py` |
| CREATE | `server/server/agent/config/intents.yaml` — 패턴 + 계획 정의 |
| CREATE | `server/server/agent/config/intent_loader.py` — YAML 로더 + 컴파일 |
| MODIFY | `server/server/agent/nodes/planner.py` — 모듈 상수 → `load_intent_config()` 호출로 교체 |

### 핵심 설계

```yaml
# intents.yaml
intents:
  greeting:
    pattern: "^(안녕|하이|헬로|hi|hello|반갑|감사|고마워|ㅎㅇ)"
    flags: IGNORECASE
    plan: []
  simulation:
    pattern: "(시뮬레이션|매출.*예상|매출.*얼마|매출.*시뮬|얼마.*벌|수익.*예상|장사.*되|매출.*전망|열면.*매출|하면.*매출)"
    plan:
      - tool: simulate_revenue
        args: {district_code: "{district_code}", category_code: "{category_code}"}
        reason: "매출 시뮬레이션"
  comparison:
    pattern: "(비교|vs|대비|차이)"
    plan:
      - tool: compare_districts
        args: {district_codes: "{referenced_districts}"}
        reason: "상권 비교 분석"
  recommendation:
    pattern: "(추천|뭐.*하면|어떤.*업종|창업|아이템)"
    plan:
      - tool: recommend_business
        args: {district_code: "{district_code}"}
        reason: "업종 추천 분석"
  risk:
    pattern: "(위험|리스크|폐업|안전|생존|실패)"
    plan:
      - tool: get_store_history
        args: {district_code: "{district_code}"}
        reason: "점포 이력/리스크 분석"
  category_analysis:
    pattern: "(카페|한식|커피|치킨|편의점|음식점|미용|병원|약국|중식|일식|양식|분식|주점|제과)"
    plan:
      - tool: get_estimated_sales
        args: {district_code: "{district_code}", category_code: "{category_code}"}
        reason: "업종별 매출 조회"
      - tool: get_store_info
        args: {district_code: "{district_code}", category_code: "{category_code}"}
        reason: "업종별 점포 현황 조회"
  summary:
    pattern: "(요약|분석|알려줘|어때|보여줘|정보|현황|상권을?\\s*선택)"
    plan:
      - tool: get_district_summary
        args: {district_code: "{district_code}"}
        reason: "상권 종합 요약 조회"

non_summary_overrides: "(비교|추천|뭐.*하면|위험|리스크|폐업|히트맵|시뮬|매출.*예상|매출.*얼마|얼마.*벌|카페|한식|커피|치킨|편의점)"
follow_up_markers: "(그러면|그럼|그래서|그리고|또|거기|아까|방금|그\\s*상권|그\\s*지역|그곳)"
```

```python
# intent_loader.py
@dataclass
class IntentConfig:
    patterns: dict[str, re.Pattern]
    plans: dict[str, list[dict]]
    non_summary_overrides: re.Pattern
    follow_up_markers: re.Pattern

@lru_cache(maxsize=1)
def load_intent_config() -> IntentConfig:
    path = Path(__file__).parent / "intents.yaml"
    raw = yaml.safe_load(path.read_text("utf-8"))
    # compile patterns, build plans
    return IntentConfig(...)
```

```python
# planner.py 변경
# Before: INTENT_PATTERNS = { ... }
# After:
from server.agent.config.intent_loader import load_intent_config

def _classify_by_rules(message: str) -> tuple[str | None, float]:
    config = load_intent_config()
    if config.follow_up_markers.search(message):
        return "follow_up", 0.5
    # ... 동일 로직, config.patterns 사용
```

**리스크**: 낮음 — 동일 regex, 동일 결과. YAML은 사람이 읽기 쉬움.

---

## 3. _CATEGORY_KEYWORDS → DB 동적 로딩 (Improvement 1)

**목표**: 12개 하드코딩 키워드를 DB `category_metadata`에서 동적 로딩 + aliases 컬럼 지원

### 파일 변경

| Action | File |
|--------|------|
| CREATE | `server/server/services/category_resolver.py` — 싱글턴 서비스 |
| CREATE | `server/alembic/versions/003_add_category_aliases.py` — aliases 컬럼 추가 |
| MODIFY | `server/server/models/category.py` — `aliases` 컬럼 추가 |
| MODIFY | `server/server/agent/nodes/planner.py` — `_CATEGORY_KEYWORDS` 제거, resolver 사용 |
| MODIFY | `server/server/main.py` — lifespan에서 resolver 초기화 |

### 핵심 설계

```python
# category_resolver.py
class CategoryResolver:
    def __init__(self):
        self._keywords: dict[str, str] = {}  # keyword → code

    def load_defaults(self):
        """Mock 모드용 기본 키워드 (기존 12개)"""
        self._keywords = {"카페": "CS100001", "커피": "CS100001", ...}

    async def load_from_db(self, session_factory):
        """DB에서 category_name + aliases 파싱하여 키워드 매핑 생성"""
        async with session_factory() as session:
            rows = await session.execute(select(
                CategoryMetadata.category_code,
                CategoryMetadata.category_name,
                CategoryMetadata.aliases,
            ))
            for row in rows.all():
                # "커피전문점/카페" → ["커피전문점", "카페"]
                for part in row.category_name.split("/"):
                    keyword = part.strip()
                    if len(keyword) >= 2:
                        self._keywords[keyword] = row.category_code
                # aliases: "스벅,투썸,카공" → 개별 등록
                if row.aliases:
                    for alias in row.aliases.split(","):
                        alias = alias.strip()
                        if alias:
                            self._keywords[alias] = row.category_code

    def resolve(self, message: str) -> str | None:
        for kw, code in self._keywords.items():
            if kw in message:
                return code
        return None

    def resolve_name(self, message: str) -> str | None:
        for kw in self._keywords:
            if kw in message:
                return kw
        return None

# 모듈 레벨 접근자
_resolver: CategoryResolver | None = None
def get_category_resolver() -> CategoryResolver: ...
def set_category_resolver(r: CategoryResolver): ...
```

```python
# main.py lifespan 추가
resolver = CategoryResolver()
if settings.use_mock:
    resolver.load_defaults()
else:
    await resolver.load_from_db(session_factory)
set_category_resolver(resolver)
```

```python
# planner.py 변경
# Before: _CATEGORY_KEYWORDS dict + _extract_category() 함수
# After:
from server.services.category_resolver import get_category_resolver

def _extract_category(message: str) -> str | None:
    return get_category_resolver().resolve(message)

def _extract_category_name(message: str) -> str | None:
    return get_category_resolver().resolve_name(message)
```

**DB 마이그레이션**:
```python
# 003_add_category_aliases.py
op.add_column("category_metadata", sa.Column("aliases", sa.String(500), nullable=True))
```

**리스크**: 낮음 — Mock 모드는 `load_defaults()`로 기존 12개 키워드 그대로. Real 모드는 DB에서 로드하되, 테이블이 비어있으면 defaults 사용.

---

## 4. Tool 레지스트리 자동 등록 (Improvement 3)

**목표**: 9개 Tool의 메타데이터를 각 파일에서 데코레이터로 선언, actor/graph에서 자동 수집

### 파일 변경

| Action | File |
|--------|------|
| CREATE | `server/server/agent/tools/registry.py` — ToolMeta + @register_tool 데코레이터 |
| MODIFY | `server/server/agent/tools/floating_population.py` — `@register_tool` 추가 |
| MODIFY | `server/server/agent/tools/estimated_sales.py` — `@register_tool` 추가 |
| MODIFY | `server/server/agent/tools/store_info.py` — `@register_tool` 추가 |
| MODIFY | `server/server/agent/tools/population_info.py` — `@register_tool` 추가 |
| MODIFY | `server/server/agent/tools/district_summary.py` — `@register_tool` 추가 |
| MODIFY | `server/server/agent/tools/compare_districts.py` — `@register_tool` 추가 |
| MODIFY | `server/server/agent/tools/recommend_business.py` — `@register_tool` 추가 |
| MODIFY | `server/server/agent/tools/store_history.py` — `@register_tool` 추가 |
| MODIFY | `server/server/agent/tools/simulate_revenue.py` — `@register_tool` 추가 |
| MODIFY | `server/server/agent/nodes/actor.py` — TOOL_REGISTRY/CARD_MAP/EMOJI 제거, registry 사용 |
| MODIFY | `server/server/agent/graph.py` — TOOLS 리스트 + 중복 emoji/card map 제거, registry 사용 |
| MODIFY | `server/server/agent/tools/data_sources.py` — TOOL_SOURCES를 registry로 통합 |

### 핵심 설계

```python
# registry.py
@dataclass
class ToolMeta:
    name: str
    fn: Callable
    emoji: str
    card_type: str | None
    progress_label: str
    done_label: str
    description: str          # LangChain @tool docstring용

_REGISTRY: dict[str, ToolMeta] = {}

def register_tool(name, *, emoji="🔧", card_type=None,
                  progress_label="", done_label=""):
    def decorator(fn):
        _REGISTRY[name] = ToolMeta(
            name=name, fn=fn, emoji=emoji, card_type=card_type,
            progress_label=progress_label or f"{name} 실행 중...",
            done_label=done_label or f"{name} 완료",
            description=fn.__doc__ or "",
        )
        return fn
    return decorator

def get_tool_registry() -> dict[str, ToolMeta]:
    if not _REGISTRY:
        _discover_tools()
    return _REGISTRY

def _discover_tools():
    """모든 tool 모듈을 import하여 @register_tool 실행"""
    from server.agent.tools import (
        floating_population, estimated_sales, store_info,
        population_info, district_summary, compare_districts,
        recommend_business, store_history, simulate_revenue,
    )
```

```python
# 각 tool 파일 — 예시: simulate_revenue.py
from server.agent.tools.registry import register_tool

@register_tool(
    "simulate_revenue",
    emoji="💰",
    card_type="simulation",
    progress_label="매출 시뮬레이션 중...",
    done_label="매출 시뮬레이션 완료",
)
async def simulate_revenue(district_code, category_code, ...):
    """상권에서 특정 업종 매출을 시뮬레이션합니다."""
    ...
```

```python
# actor.py — 교체
# Before: TOOL_REGISTRY, TOOL_CARD_MAP, TOOL_EMOJI, _ensure_registry()
# After:
from server.agent.tools.registry import get_tool_registry

async def execute_tool(step):
    reg = get_tool_registry()
    meta = reg.get(step["tool_name"])
    if not meta:
        return step["tool_name"], None, f"Unknown tool"
    result = await meta.fn(**args)
    ...
```

**리스크**: 중간 — 9개 tool 파일 + actor.py + graph.py 수정. 각 변경은 기계적이지만 import 순서 주의 필요.

---

## 5. Frontend 라벨 → Backend SSE 전달 (Improvement 4)

**목표**: Backend SSE 이벤트에 라벨 포함, Frontend는 backend 값 우선 + 로컬 fallback

### 파일 변경

| Action | File |
|--------|------|
| MODIFY | `server/server/agent/nodes/actor.py` — tool/tool_end 이벤트에 `progress_label`, `done_label` 추가 |
| MODIFY | `server/server/agent/graph.py` — ReAct 모드 tool 이벤트에도 라벨 추가 |
| MODIFY | `frontend/src/lib/types.ts` — SSEEvent에 optional label 필드 추가 |
| MODIFY | `frontend/src/lib/eventHandlers.ts` — backend label 우선 사용, TOOL_LABELS는 fallback 유지 |

### 핵심 설계

```python
# actor.py — tool start 이벤트 보강
meta = reg.get(step["tool_name"])
await event_queue.put({
    "type": "tool",
    "name": step["tool_name"],
    "input": step["args"],
    "icon": meta.emoji,
    "progress_label": meta.progress_label,   # NEW
})

# tool_end 이벤트
await event_queue.put({
    "type": "tool_end",
    "name": step["tool_name"],
    "icon": meta.emoji,
    "done_label": meta.done_label,           # NEW
})
```

```typescript
// types.ts — SSEEvent 확장
| { type: 'tool'; name: string; input?: Record<string, unknown>;
    icon?: string; progress_label?: string }     // progress_label 추가
| { type: 'tool_end'; name: string;
    icon?: string; done_label?: string }         // done_label 추가
```

```typescript
// eventHandlers.ts — backend 우선, fallback 유지
case 'tool': {
  const toolLabel = TOOL_LABELS[event.name];
  const icon = event.icon || toolLabel?.icon || '🔧';
  const label = event.progress_label              // backend 우선
    || toolLabel?.progress
    || `${event.name} 실행 중...`;                 // 최종 fallback
  // ...
}
```

**TOOL_LABELS / CARD_LABELS 유지** — 삭제하지 않음. Backend 미응답 시 fallback으로 동작.

**리스크**: 낮음 — SSE에 optional 필드 추가만.

---

## 검증 방법

각 개선 완료 후:
1. `tsc --noEmit` — 0 errors
2. `npm run build` — 성공
3. Mock 모드 backend 기동 → 기존 chat 시나리오 테스트
4. `npx playwright test e2e/phase3-scenario.spec.ts` — 12/12 PASS
5. 기존 E2E 32/32 회귀 테스트 (가능 시)

전체 완료 후 추가 검증:
- 새 업종 키워드를 aliases에 추가 → 코드 수정 없이 인식 확인
- YAML 패턴 추가 → 서버 재시작만으로 적용 확인
- 새 Tool 추가 시 `@register_tool` 데코레이터만으로 전체 동작 확인

---

## 파일 변경 총괄

| # | 개선 | 신규 | 수정 | 리스크 |
|---|------|------|------|--------|
| 5 | Mock JSON | 8 | 1 | 낮음 |
| 2 | YAML 인텐트 | 3 | 1 | 낮음 |
| 1 | 카테고리 DB | 2 | 3 | 낮음 |
| 3 | Tool 레지스트리 | 1 | 12 | 중간 |
| 4 | Frontend 라벨 | 0 | 4 | 낮음 |
| **합계** | | **14** | **21** | |
