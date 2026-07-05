# Plan: MarketScope AI 학습 자료 제작 (`docs/learning/`)

## Context

현재 repo(`Catchment-Area-Analysis` = MarketScope AI)에 대한 **학습 자료**를 만든다. 목표 독자는 **비개발자를 포함한 신규 합류자**로, "이 서비스가 무엇을, 어떻게, 어떤 코드로 동작시키는가"를 처음부터 따라올 수 있어야 한다.

참고 모델은 `crypto_deep_research/docs/learning/`(6개 평문 .md). 그 자료의 검증된 패턴:
- **§0 큰 그림(비유) → §N 줄별 해설 → 마지막 §관통 설계 원칙** 의 고정 구조
- 사무실/팀 비유로 모든 전문 용어를 풀어 설명("프로세스 = 따로 돌아가는 프로그램")
- 설계 결정을 코드와 1:1로 추적

본 repo는 crypto 대비 표면이 크다(Frontend Next.js + Backend FastAPI + LangGraph PAE Agent + PostGIS/Redis 데이터 레이어). 따라서 자료를 **계층별 7개 문서 커리큘럼**으로 나누고, 각 문서를 **독립 컨텍스트의 작성 에이전트**가 자기 슬라이스만 읽고 쓰게 하여(= context bloat 방지) 문서 퀄리티를 유지한다.

> ⚠ 2026-07-04 정정 (문서 정합성 감사): 본 Plan 작성 시점(2026-06-21)과 달리 현행 기본 런타임은 **v2 agentic loop + Trust Kernel** (`config.py` `agent_loop_version="v2"` 기본값, `agent/runtime.py` 디스패치, `server/server/agent/loop/{engine,trust,tools_fc,prompts,models}.py`)이며, PAE 그래프(`agent/graph.py`)는 Mock 폴백·`AGENT_LOOP_VERSION=pae` 롤백 스위치용 legacy 다. 본 커리큘럼과 산출된 `docs/learning/` 문서 세트(§04 PAE 중심 · §05 도구 9종)는 v2 루프/Trust Kernel(수치 바인딩 검증, `trust_numeric_tolerance=0.05`)을 다루지 않는다 — 학습자료 개정 시 v2 문서 추가가 필요하다.

### 사용자 확정 사항
- **깊이**: 코드 줄별 해설 포함 (crypto 참고자료 수준) — 단, 비유를 앞세워 비개발자 진입장벽 제거
- **도식**: Mermaid 다이어그램으로 통일 (flowchart / sequenceDiagram / stateDiagram)
- **위치·언어**: `docs/learning/` · 한국어

### 참고 메모리
- `feedback_sse_buffering` — Chat SSE는 Next rewrite 프록시 미사용, 직접 백엔드 호출 (02/03 문서에 반영)
- `feedback_mock_real_pattern` — Repository 패턴, Mock에서 DB 연결 금지 (06 문서 핵심)
- `feedback_korean_particles` — 상권명 검색 시 조사 strip (04 entity_matching 줄별 해설에 반영)

---

## Goal & 제약

1. **비개발자 이해 최우선** — 모든 문서는 비유로 시작, 전문 용어는 첫 등장 시 괄호로 풀이.
2. **Mermaid 도식 적극 활용** — 문서당 최소 1개 이상의 핵심 다이어그램. 긴 산문 대신 그림으로 대체.
3. **Context bloat 방지** — (a) 문서 간 중복 금지·교차 링크로 해결, (b) `docs/architecture/*`에 이미 있는 내용은 재서술 대신 인용, (c) 작성 단계에서 문서 1개 = 에이전트 1개로 컨텍스트 격리.
4. 코드 스니펫은 **실제 파일에서 verbatim 인용** 후 줄별 해설 (paraphrase 금지).

---

## 산출물: 7개 문서 커리큘럼 (`docs/learning/`)

> 읽는 순서 = 파일 번호 순. 각 문서는 §0 큰그림(비유+Mermaid) → §N 줄별 해설 → §관통 원칙 으로 끝맺는다.

### `00-시작하기.md` — 인덱스 & 전체 지도
- **역할**: 학습 경로 안내 + MarketScope 1문단 소개(서울 1,650개 상권 분석 AI 챗봇) + 읽는 순서 표.
- **핵심 Mermaid**: 전체 시스템 4계층 flowchart (브라우저 → FastAPI → PAE Agent → 데이터). 각 박스에서 해당 학습문서로 링크.
- **비유 앵커**: "상권 분석 컨설팅 회사" — 접수창구(프론트)·상담 분석팀(에이전트)·자료실(데이터).
- 작성 시점: **마지막** (나머지 6개 제목/링크 확정 후).

### `01-큰그림-한질문의여정.md` — End-to-End 흐름
- **역할**: 사용자가 "강남역 카페 어때?" 한 줄을 입력했을 때 화면→서버→AI→데이터→화면으로 **한 바퀴 도는 여정**을 추적. 전체를 꿰는 오리엔테이션.
- **핵심 Mermaid**: `sequenceDiagram` (사용자 / 브라우저 / FastAPI / Planner / Actor / Evaluator / Respond / DB). SSE 9 이벤트가 어느 단계에서 흐르는지 표기.
- **읽을 코드(포인터만, 줄별 해설은 후속 문서로 위임)**: `frontend/src/hooks/useChat.ts`, `server/server/api/routes/chat.py`, `server/server/agent/graph.py`.
- **비유**: 손님 주문서 한 장이 홀 → 주방 → 창고를 거쳐 완성된 요리로 돌아오는 길.

### `02-프론트엔드-화면.md` — 사용자가 보는 부분
- **역할**: 지도+챗 split 화면, Zustand 3 스토어, SSE 스트림을 화면으로 바꾸는 파서.
- **핵심 Mermaid**: `flowchart` — SSE 이벤트(type별) → eventHandlers → 어떤 store/컴포넌트가 갱신되는지.
- **줄별 해설 대상**:
  - `frontend/src/lib/sseParser.ts` (async generator, UTF-8 decode, 30s timeout)
  - `frontend/src/lib/eventHandlers.ts` (type → store action 매핑)
  - `frontend/src/stores/chatStore.ts` 의 `sendMessage` (직접 백엔드 호출 + 재시도 — 메모리 `feedback_sse_buffering` 인용)
- **참조**: 컴포넌트 전체 목록은 `docs/architecture/frontend.md` 인용(재서술 금지).
- **비유**: 홀 직원 — 주방에서 한 글자씩 나오는 응답(SSE)을 받아 손님 테이블(화면)에 실시간으로 차린다.

### `03-백엔드-접수창구.md` — 요청이 들어오는 문
- **역할**: FastAPI 앱 기동, `/api/chat` 라우트, 인메모리 세션(30분 TTL), SSE 응답(EventSourceResponse), 미들웨어 순서.
- **핵심 Mermaid**: `flowchart` — 미들웨어 파이프라인(CORS→Security→RequestId→예외→RateLimit→Metrics→핸들러).
- **줄별 해설 대상**:
  - `server/server/api/routes/chat.py` 의 `POST /api/chat` 핸들러 + 세션 조회/생성 + `run_agent` 호출 + SSE 스트리밍
  - `server/server/main.py` lifespan(캐시/DB/카테고리/그래프 초기화) 요약 해설
- **참조**: 환경설정 표·엔드포인트 표는 `docs/architecture/backend.md` 인용.
- **비유**: 접수창구 — 손님(요청)을 맞고, 단골 기록(세션)을 꺼내고, 분석팀에 넘긴 뒤 결과를 한 줄씩 손님에게 전달.

### `04-AI에이전트-분석팀.md` — 서비스의 심장 (PAE)

> ⚠ 2026-07-04 정정: PAE 그래프는 현행 legacy(Mock 모드·롤백 폴백) — 기본 경로는 v2 agentic loop(`agent/loop/engine.py`). SSE 방출 집합도 경로별로 다르다: v2 엔진 7종(thinking/tool/tool_end/card/text/suggestion/done), `plan`·`warning` 은 PAE 전용, `map_cmd` 는 `chat.py` 가 에이전트 밖에서 방출. "SSE 9 이벤트" 단일 서술은 PAE 기준.

- **역할**: LangGraph **Planner→Actor→Evaluator→Respond** 그래프를 "분석팀"으로 설명. 가장 깊은 문서.
- **핵심 Mermaid**: `stateDiagram-v2` — agent.md의 ASCII 그래프를 Mermaid로 (greeting/fast-respond 분기, Evaluator↔Planner 최대 3회 루프 포함).
- **줄별 해설 대상**:
  - `server/server/agent/state.py` (AgentState TypedDict — 팀이 공유하는 업무 양식)
  - `server/server/agent/graph.py` 의 그래프 조립 + 노드 라우팅
  - `nodes/planner.py` 핵심: 규칙 우선 intent 분류 + entity 추출 (+ `utils/entity_matching.py`의 조사 strip — 메모리 `feedback_korean_particles` 인용, out_of_scope 가드)
  - `nodes/actor.py` 핵심: 의존성 layer 병렬 실행(`asyncio.gather`) + card 발행
  - `nodes/evaluator.py` 핵심: fast/slow path 충분성 판정
  - `nodes/respond.py` 핵심: 스트리밍 응답 + 시스템 프롬프트 역할
- **비유**: 기획자(Planner: 무엇을 조사할지 계획)→실무자(Actor: 자료 수집)→검토자(Evaluator: 충분한가)→작성자(Respond: 보고서 작성). 부족하면 검토자가 기획자에게 반려(최대 3회).

### `05-도구9종-전문계측기.md` — Agent가 쓰는 도구
- **역할**: `@register_tool` 자기등록 패턴 + Tool 9종 한눈에 + 대표 도구 1개 줄별 추적.
- **핵심 Mermaid**: `flowchart` — Planner의 plan → Actor가 tool 호출 → registry로 card_type 매핑 → card 이벤트.
- **줄별 해설 대상**:
  - `server/server/agent/tools/registry.py` (`@register_tool` 데코레이터 동작)
  - 대표 도구 1개 `tools/district_summary.py` (입력→repo 호출→카드 payload)
  - **Tool 9종 표** (이름/입력/출력/Card/사용 기능) — registry.py에서 실제 등록분만 추출, 내부 헬퍼(`benchmarks`) 구분 명시
- **비유**: 실무자의 연장통 — 9개의 전문 계측기. 각 계측기는 이름표(`@register_tool`)를 스스로 붙여 팀에 등록.

### `06-데이터레이어-자료실.md` — 숫자는 어디서 오나
- **역할**: Repository 패턴(protocols + mock/real), `USE_MOCK` 토글, PostGIS 공간쿼리, Redis 캐시, 매출 월환산 단위 주의.
- **핵심 Mermaid**: `flowchart` — Tool → DataAccess 파사드 → (USE_MOCK 분기) → Mock fixture **또는** Real(SQLAlchemy→PostGIS). 캐시 히트/미스 경로.
- **줄별 해설 대상**:
  - `server/server/repositories/protocols.py` 일부 (인터페이스 = 약속)
  - `repositories/real/recommendation.py` 의 `_apply_store_floor`/점수식 (ISSUE-003 fix — 저점포수 아티팩트 방어, 실제 정확성 사례로 활용)
  - 매출 단위 주의: `monthly_sales` = 분기누적 → 월 환산 (`repositories/real/_units.py` 또는 enrich 지점)
  - `services/cache.py` 의 Memory/Redis graceful degradation 요약
- **참조**: DB 스키마·ETL은 `docs/architecture/data.md` 인용. 메모리 `feedback_mock_real_pattern` 인용.
- **비유**: 자료실 — 같은 청구서식(protocols)에 두 종류 캐비닛(mock=연습용 견본, real=진짜 PostGIS). 사서(캐시)가 자주 찾는 자료는 책상에 미리 꺼내둠.

---

## 공통 스타일 가이드 (모든 작성 에이전트에 주입)

각 문서 헤더 3줄:
```markdown
# 학습 자료: <한국어 제목>

> 대상: <다루는 파일/모듈>
> 목적: <한 문장>
> 선행 문서: <이전 번호 문서 링크> · 다음: <다음 번호 문서 링크>
```

문서 골격:
1. **§0 큰 그림** — 비유 2~3문단 + 핵심 Mermaid 1개. (반드시 맨 처음)
2. **§1..N 줄별 해설** — 단위마다: ```실제 코드 verbatim``` → `이 코드는 …` → `왜? …` → `주의: …`. 전문용어 첫 등장 시 괄호 풀이.
3. **§마지막 — 이 문서가 가르치는 핵심 원칙** — 번호 목록으로 코드를 시스템 설계(USE_MOCK 토글 / Repository 패턴 / SSE 9 이벤트 / Circuit Breaker / out_of_scope 가드 등)에 연결.

규칙:
- 한국어. Mermaid 코드펜스(` ```mermaid `) 사용. ASCII 도식 지양(Mermaid로 대체).
- `docs/architecture/*`·`docs/spec/*`에 이미 있는 표/스키마는 **링크로 인용**, 재서술 금지.
- 코드는 paraphrase 금지 — 해당 파일을 직접 Read 후 verbatim 인용.
- 문서 길이 목표 ~200–400줄(참고자료와 동급). 초과 시 줄별 해설 대상 축소(대표 1~2개만).

---

## 구현 전략 (context bloat 방지의 핵심)

1. **`docs/learning/` 디렉토리 생성.**
2. **문서 1개 = 작성 에이전트 1개** (01~06, 6개를 병렬 또는 순차 spawn). 각 에이전트에 전달:
   - 위 "공통 스타일 가이드" 전문
   - 그 문서의 scope + **읽어야 할 정확한 소스 파일 목록**(위에 명시) — 그 외 파일은 읽지 말 것
   - Mermaid·한국어·줄별 해설·비유 요구사항
   → 각 에이전트가 자기 슬라이스만 컨텍스트에 올리므로 단일 컨텍스트 과적 방지.
3. **`00-시작하기.md`는 마지막**에 작성 (6개 문서 제목·앵커 확정 후 링크 정합성 보장).
4. 작성 후 메인에서 교차 링크·중복 점검 1회 패스.

> 모델 선택(프로젝트 관례): 본 문서들은 설명 정확도가 중요 → 작성 sonnet, 큰그림/링크정합 검수 메인(opus).

---

## Scenario (E2E Ring Mapping)

> 본 작업은 코드 변경이 없는 **문서 산출물**이라 런타임 E2E Ring(0~3)에 해당하지 않는다. 대신 문서 품질 게이트를 Ring 유사 단계로 매핑한다.

| 유사 Ring | 검증 항목 | 통과 기준 |
|---|---|---|
| Ring 0 (preflight) | 7개 파일 생성 + 3구조(§0/줄별/원칙) 존재 | 파일 7개 · 구조 누락 0 |
| Ring 1 (단위) | Mermaid 문법 렌더 · 코드 인용 정합성 | 문법 에러 0 · 표본 인용 일치 |
| Ring 2 (여정) | 교차 링크 · 학습 경로 통독 | 깨진 링크 0 · 00→06 흐름 자연스러움 |
| Ring 3 (네거티브) | 중복 재서술 · 비개발자 난해도 | architecture 재서술 0 · 미풀이 전문용어 0 |

---

## Validation

1. **파일 존재·구조**: `docs/learning/` 에 `00`~`06` 7개 .md 생성 확인. 각 문서가 §0 큰그림 / 줄별 해설 / 핵심 원칙 3구조를 갖는지.
2. **Mermaid 문법**: 각 ` ```mermaid ` 블록을 [mermaid.live](https://mermaid.live) 또는 VS Code Markdown Preview Mermaid 확장으로 렌더 확인 (문법 에러 0). GitHub에서도 렌더되는지 1개 이상 확인.
3. **코드 인용 정합성**: 인용한 스니펫이 실제 파일과 일치하는지 표본 점검 (예: `sseParser.ts`, `registry.py`, `recommendation.py::_apply_store_floor`).
4. **교차 링크**: `00`의 학습경로 링크와 각 문서의 선행/다음 링크가 깨지지 않는지 (상대경로).
5. **비개발자 검증(스모크)**: 임의 1개 문서를 비개발자 관점에서 통독 — 전문용어가 첫 등장 시 풀이됐는지, 비유만으로 §0이 이해되는지.
6. **중복 점검**: `docs/architecture/*`와 내용이 재서술되지 않고 링크로 처리됐는지.

---

## Metadata
- 작성일: 2026-06-21
- 카테고리: docs (학습 자료)
- 영향 범위: `docs/learning/` 신규 생성만. 소스 코드·기존 docs 변경 없음 (read-only 참조).
- 커밋: 프로젝트 관례상 main 직접 가능하나, 사용자 지시 시에만 커밋.
- 비고: 작성 중 코드와 문서 불일치 발견 시 문서는 **현재 코드 기준**으로 작성하고, 불일치 사항은 별도 노트로 사용자에게 보고(코드 수정은 본 작업 범위 밖).
