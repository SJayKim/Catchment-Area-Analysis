# server/ — MarketScope AI 백엔드

FastAPI (Python 3.12, async). 실제 패키지는 `server/server/*`.
상세: [../docs/architecture/backend.md](../docs/architecture/backend.md) · Agent: [../docs/architecture/agent.md](../docs/architecture/agent.md).

## 빌드 & 테스트

```bash
cd server
pip install -e ".[dev]"
uvicorn server.main:app --reload --port 8000
ruff check --fix . && ruff format .
pytest                      # 전체 (테스트 모듈 28)
pytest -m "not real"        # CI 게이트 (@real DB 통합 6케이스 제외 — 로컬 opt-in)
```

> Windows: Python `open()`/print 는 cp949 기본 → `encoding='utf-8'` + 환경변수 `PYTHONIOENCODING=utf-8` 명시. 셸 python 이 타 프로젝트 venv 일 수 있으니 pytest 는 Python 절대경로로.

## 핵심 불변식

- **매출 단위**: `estimated_sales.monthly_sales` = `THSMON_SELNG_AMT` = **분기 누적(원)**. Repository 에서 `// MONTHS_PER_QUARTER` 로 월 환산 후 응답. 유동인구 집계는 `quarter_total` ('일평균' 아님).
- **USE_MOCK 분기**: `true` → Memory 캐시 + JSON fixture repo + **Agent PAE 폴백**(mock LLM tool-call 불가). `false` → Redis + SQLAlchemy async + v2 loop.
- **env 관례**: `.env`=prod, `.env.dev`=로컬 (config.py 가 `.env.dev` 우선 로드). prod 서버엔 `.env.dev` 없어야 함. `.env`/`.env.dev` 수정은 `protect_secrets.py` 훅이 차단 → 수동 diff 적용.

## Agent 디스패치 (`agent/runtime.py::run_agent`)

- `agent_loop_version=="v2"` && `llm_provider!="mock"` → **v2 loop** (`agent/loop/engine.py`, 모델주도 function-calling + Trust Kernel). 그 외(특히 Mock) → legacy **PAE** (`agent/graph.py`, Planner-Actor-Evaluator).
- **LLM fallback chain** (키 존재 기준): anthropic `claude-sonnet-4-6` → gemini-2.5-pro → flash. 모델 ID 는 전부 settings(env-overridable) — 하드코딩 은퇴사고(dead model 404) 방지.
- Tool 9종 도메인 + 메타 3종(resolve_district/compute/abstain) = 스키마 12. Card 발행 5종. 새 Tool 은 `@register_tool` + `loop/tools_fc.py::tool_schemas()` 등록.

## DB / 마이그레이션

- alembic 001~005. FK 작성 전 `psql \d <table>` 로 참조 컬럼명 확인 (오타는 빈 결과로 위장). 배포 시 문구/템플릿 fix 는 `flush_cache.py` 로 Redis 캐시 flush (24h TTL).
- 주요 테이블: districts · floating_population · estimated_sales · stores · store_history · resident_population · category_metadata · learned_aliases · chat_sessions · chat_messages (세션은 인메모리).
