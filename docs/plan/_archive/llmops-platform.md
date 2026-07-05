# LLMOps 플랫폼 도입 제안 (MarketScope AI)

> **문서 성격**: 아이디어 제안 (Proposal-level). 원자적 구현 태스크는 각 Level 착수 시 별도 Plan 으로 분기.
> **목적**: 서비스 운영/관리 + LLM 품질 관리를 동시에 충족하는 LLMOps 파이프라인 설계.

---

## 1. Context

### 1.1 현재 스택 스냅샷 (2026-04-21 기준)

| 레이어 | 상태 | 근거 파일 |
|--------|------|-----------|
| Agent | LangGraph PAE (Planner→Actor→Evaluator→Respond, max 3 rounds) | `server/server/agent/graph.py` |
| LLM 라우팅 | Planner=Claude Sonnet 4, Evaluator=Gemini 2.5-flash, Respond=Gemini 2.5-pro (또는 Claude fallback) | `server/server/config.py` `llm_model_*` |
| 스트리밍 | 자체 SSE 포맷 (`data: {type,...}`) — 표준 `event:` 라인 없음 | `server/server/api/routes/chat.py` |
| Tools | **9종** 도메인 Tool + registry 기반 auto-discover (`benchmarks.py`는 헬퍼, Tool 아님) | `server/server/agent/tools/{compare_districts,district_summary,estimated_sales,floating_population,population_info,recommend_business,simulate_revenue,store_history,store_info}.py` |
| Prompts | `system.py` / `planner.py` / `evaluator.py` 3개 모듈 (sanitize 헬퍼 + 상수 혼재). `templates.py` 없음 | `server/server/agent/prompts/*.py` |
| 관측 | in-memory `metrics.py` (p50/95/99, SSE gauge), structured log | `server/server/middleware/metrics.py`, `server/server/logging_config.py` |
| 복구 | Circuit breaker + tenacity 재시도 + Anthropic 401 세션-레벨 fallback (`_anthropic_valid`) | `server/server/services/circuit_breaker.py`, `graph.py` |
| 테스트 | Playwright E2E Ring 0~3 (28 specs, Mock 39/39 + Real 24/24 그린) | `frontend/e2e/ring{0..3}-*/` |
| Langfuse | **의존성 + 설정값만 존재 (env 3개), CallbackHandler wiring 미완** | `pyproject.toml:27 langfuse>=2.0`, `config.py:39-42` |

### 1.2 LLMOps 관점의 Gap

| 범주 | 현재 | 결핍 |
|------|------|------|
| **Tracing** | 로그 + `metrics.py` 집계 | LLM 호출/Tool/세션 단위 분산 추적 없음 |
| **Evals** | Playwright E2E (UI 계약) | Golden query 회귀 / 품질 점수 / 응답 정합성 검증 없음 |
| **Prompt 관리** | `prompts/*.py` 상수·함수 혼재 | 버전/실험/롤백 단위 없음 |
| **Cost** | 없음 | 토큰/원가 추적, 예산 알림, 모델별 분해 없음 |
| **Feedback** | 없음 | 사용자 👍/👎 채널 없음 |
| **Incident** | Circuit breaker 기본, `docs/ops/runbook.md` 범용 | LLM 특화 런북 (공급자 장애, 프롬프트 회귀, 비용 폭주) 없음 |
| **Experiment** | 없음 | 모델/프롬프트 A/B, 카나리 배포 없음 |

### 1.3 이미 프로젝트에서 발견·기록된 LLM/운영 교훈 (Context)

> `memory/` 디렉토리는 현재 비어있으므로, 아래 항목은 **커밋 로그 + `docs/status/current-status.md`** 에서 확인 가능한 실제 인시던트만 정리. 향후 동일 교훈을 `memory/` 에 저장하여 재사용 가능하게 만드는 것이 L1 착수 조건 중 하나.

| 교훈 | 근거 | 본 Plan 적용 |
|------|------|--------------|
| **SSE 이벤트 타입이 `data: {type:...}` JSON 안에 임베드**. `event:` 라인 없음 | `api/routes/chat.py`, current-status.md 2026-04-13 | trace_id 도 **JSON 안에 추가**, `event:` 라인 신설 금지 |
| **Gemini preview 모델 TTFT 16~45s → Claude Sonnet 4 로 전환 후 1.5~2s (17× 개선)** | current-status.md 2026-04-13 "SSE 스트리밍 성능 최적화" | 모델별 TTFT 히스토그램을 **관측 1순위** 지표로 |
| **Anthropic API 키 만료 시 매 요청 401 → `_anthropic_valid` 세션 플래그로 우회** | `graph.py`, current-status.md 2026-04-13 | 동일 패턴을 Langfuse 전송 실패에도 적용 (best-effort) |
| **Mock D3001~D3005 ↔ Real `3120189` district_code 불일치** → F02-H1 / F03-H4 테스트가 하드코딩 시 깨짐 | 커밋 `ff9909c` "런타임 resolve" | Eval runner 도 `USE_MOCK` preflight + district_code 런타임 resolve |
| **`estimated_sales.monthly_sales` = 분기 누적**. `//3` 월환산 필요 | current-status.md 2026-04-17 매출 단위 fix · `repositories/real/_units.py::MONTHS_PER_QUARTER` (2026-07-04 정정: 구 인용처 `docs/plan/fix/sales-unit-conversion-fix.md` 는 리포에 부재) | Golden query 의 매출 assertion 은 월 단위 범위로 |
| **Next.js `_` prefix = private folder → 라우트 안됨**. `/api/kakao-sdk` ↔ `/proxy/kakao-sdk` rename | 커밋 `3c5f884` | Langfuse 가 프론트에 노출되는 API 루트 신설 시 동일 함정 주의 |
| **Windows UTF-8 인코딩**: Python 파일 입출력 `encoding='utf-8'` 명시 누락 시 깨짐 | 반복된 ruff/pytest 환경 이슈 | Eval 리포트 저장 시 `encoding='utf-8'` 강제 |
| **E2E 검증 시 user 메시지 자체가 키워드 오염** → assistant 메시지만 assertion | `frontend/e2e/helpers/evalPacket.ts` | LLM-as-Judge 입력도 `role=='assistant'` 필터 |

---

## 2. Scope

### 2.1 In-Scope

1. **Observability Layer** — Langfuse wiring, LLM/Tool/세션 trace, 모델별 latency·TTFT 분해, cost 기록.
2. **Quality Layer** — Prompt registry(YAML 본문 + Python 헬퍼), golden-query eval harness, LLM-as-Judge, regression gate.
3. **Ops Layer** — Cost dashboard + budget alert, 사용자 feedback 파이프라인, LLM 특화 런북.
4. **Release Layer** — 프롬프트/모델 A/B, shadow traffic, 카나리 롤아웃.

### 2.2 Out-of-Scope (본 문서)

- RAG / 벡터 DB 구축 (별도 plan: `docs/plan/data/`)
- Fine-tuning / 모델 학습 인프라
- 결제/구독 (`docs/plan/business/commercialization-plan.md`)
- PII 마스킹 정책 전면 (별도 Security plan, 본 Plan 은 session_id 해시만 규정)
- `docs/plan/marketscope_improvement.md` 가 다루는 비-LLM 영역 (DB·캐시·인프라)

---

## 3. Design

### 3.1 4-Layer 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     Release Layer                           │
│  Prompt A/B · Model Canary · Shadow Traffic · Rollback      │
└────────────────────────┬────────────────────────────────────┘
                         │ config/flag
┌────────────────────────┴────────────────────────────────────┐
│                     Ops Layer                               │
│  Cost Tracker · Budget Alert · Feedback Pipeline · Runbook  │
└────────────────────────┬────────────────────────────────────┘
                         │ metrics/events
┌────────────────────────┴────────────────────────────────────┐
│                     Quality Layer                           │
│  Prompt Registry(YAML+py) · Eval Harness · LLM-as-Judge ·   │
│  Regression Gate (CI)                                       │
└────────────────────────┬────────────────────────────────────┘
                         │ trace/score
┌────────────────────────┴────────────────────────────────────┐
│                     Observability Layer                     │
│  Langfuse (trace/span) · metrics.py 집계 · structlog        │
│  (request_id 상관) · 모델/intent 별 대시보드                 │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
              server/server/agent/graph.py (PAE)
```

### 3.2 Maturity Level 로드맵 (점진 도입)

| Level | 기간 | 목표 | 산출물 |
|-------|------|------|--------|
| **L1 — Trace 활성화** | 1~2주 | Langfuse 연결, 모든 LLM/Tool 호출 span 기록 | `graph.py` CallbackHandler, Langfuse Cloud 연동 또는 `docker-compose.observe.yml` |
| **L2 — Prompt 자산화** | 1주 | 본문 YAML 추출 + hash 버저닝, Python 헬퍼(`sanitize_prompt_value` 등) 유지 | `server/server/agent/prompts/registry/*.yaml` + `loader.py` |
| **L3 — Eval 하네스** | 2~3주 | Golden query 30~50개, LLM-as-Judge, CI regression gate | `server/tests/evals/`, GitHub Actions `eval-gate` job |
| **L4 — Cost + Feedback** | 1~2주 | 토큰/원가 기록, 프론트 👍/👎, budget alert | 미들웨어, `MessageBubble` 버튼, Langfuse score |
| **L5 — Experiment** | 2주+ | 프롬프트 A/B, 모델 카나리 (10%→50%→100%) | feature flag, Langfuse dataset 분리 |

### 3.3 컴포넌트별 진입점

#### 3.3.1 Observability (L1)

**Hosting 선택**:

| 옵션 | 장점 | 단점 | 권장 |
|------|------|------|------|
| Langfuse **Cloud** | 15분 내 연동, 의존성 추가 0 | 외부 SaaS (PII 정책), 월 요금 | **초기 L1 권장** |
| Langfuse **Self-host** (v2) | 데이터 주권, postgres 1개만 필요 | 운영 부담, 스키마 업그레이드 이슈 | L4 이후 PII 요구 생기면 전환 |
| v3 Self-host | 최신 기능 | postgres + **clickhouse + redis + minio** 4종 스택 | 현 compose 부담 ↑, 비권장 |

**진입점**: `server/server/agent/graph.py` `_build_pae_graph()` 직후, graph 실행 시 `config={"callbacks": [handler]}` 주입.

```python
# 의사 코드 — 실제 구현 시 별도 plan 에서 정교화
from langfuse.callback import CallbackHandler

def get_langfuse_handler(session_id: str, request_id: str) -> CallbackHandler | None:
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    return CallbackHandler(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        session_id=_hash_session(session_id),     # PII 해시 (3.1.3 교훈)
        trace_name="marketscope.pae",
        metadata={
            "request_id": request_id,
            "llm_provider": settings.llm_provider,
            "agent_mode": settings.agent_mode,
            "use_mock": settings.use_mock,        # Mock/Real 필터링용
        },
    )
```

**추적 대상 span**:
- `planner.classify` — intent, confidence, 모델명, latency, input/output 토큰
- `actor.tool.<name>` — tool 입력/출력, DB 쿼리 시간, truncation 여부, `card_type`
- `evaluator.judge` — sufficient 판정, missing 필드, fast-path vs slow-path
- `respond.stream` — **TTFT (첫 토큰)**, 총 출력 토큰, SSE 이벤트 수, `_anthropic_valid` 상태

**Metrics 병행**: 기존 `server/server/middleware/metrics.py` 유지하되, Langfuse = raw trace / `metrics.py` = 집계 지표 (SLO 대시보드·Prometheus 익스포트 후보) 로 분업.

#### 3.3.2 Prompt Registry (L2)

**현재 구조**: `server/server/agent/prompts/{system,planner,evaluator}.py` — 함수·상수 혼재.

- `system.py` — `RESPOND_SYSTEM_PROMPT` (문자열) + `sanitize_prompt_value(val)` (함수) + Mock/Real 분기 로직
- `planner.py` / `evaluator.py` — intent·judge 프롬프트 문자열 + JSON 스키마 설명

**제안 구조** (기능별 분리, 함수는 유지):

```
server/server/agent/prompts/
├── registry/
│   ├── system.v1.yaml            # {version, template, input_vars, description, owner, hash}
│   ├── system.v2.yaml            # 실험 중 (예: 해석 가이드 강화)
│   ├── planner.v1.yaml
│   └── evaluator.v1.yaml
├── loader.py                     # YAML load + Langfuse tag 주입 + hash 검증
├── system.py                     # sanitize_prompt_value 등 헬퍼 유지, 문자열 상수만 제거
├── planner.py                    # JSON 스키마 Pydantic 모델 유지, 본문 문자열만 제거
└── evaluator.py                  # 상동
```

**효과**:
- Trace 에 `prompt_version=system.v2` 태그 → Langfuse 에서 버전별 품질 비교
- 롤백 = env 변경 (`PROMPT_SYSTEM_VERSION=v1`) + 재시작, 코드 재배포 불필요
- PR diff 에서 프롬프트 변경 가시화 (`*.yaml` 만 바뀐 PR 은 eval-gate 자동 엄격화)

#### 3.3.3 Eval Harness (L3)

**구조**:

```
server/tests/evals/
├── datasets/
│   ├── golden_queries.yaml       # 30~50개: {query, mode(mock|real|both), district_code?, intent,
│   │                             #          expect.cards[], expect.tools[], must_include[], must_not_include[]}
│   ├── prompt_injection.yaml     # 시스템 프롬프트 우회 시도 (현 `system.py` 가드레일 9·10 검증)
│   └── edge_cases.yaml           # 매출 분기→월 환산 / Korean particles / Mock-Real code mismatch
├── scorers/
│   ├── rule_based.py             # must_include / 카드 타입 / 도구 호출 포함 여부 / SSE 이벤트 순서
│   └── llm_judge.py              # Claude Haiku 로 품질 스코어(1~5) + 근거 코멘트
├── runner.py                     # USE_MOCK preflight 강제, district_code 런타임 resolve, assistant 메시지만 assert
└── reports/                      # HTML + JSON 결과 (encoding='utf-8' 강제)
```

**실행 모드**:
1. **PR Gate** — 핵심 20개 쿼리 (Mock) GitHub Actions 에서 실행. 점수 하락 >5% 시 fail.
2. **Nightly** — 전체 셋 + LLM-as-Judge (Mock+Real). 결과 Langfuse dataset 에 업로드.
3. **Pre-release** — 프로덕션 배포 전 수동 트리거 (`scripts/run_evals.py`).

**프로젝트 교훈 반영** (Context §1.3):
- runner.py 가 `USE_MOCK` 강제 + `scripts/e2e/preflight.sh` 와 동일한 env 검증 재사용
- district_code 하드코딩 금지 → 이름 기반 `detect_districts_in_message` 런타임 resolve
- assertion 은 `role=='assistant'` 필터 (user 키워드 오염 방지)
- 매출 assertion 은 **월 단위 범위** (예: 보문역 슈퍼마켓 ≈ 1.38억/월 ± 30%)

#### 3.3.4 Cost Tracking (L4)

- Langfuse 가 기본으로 token/cost 기록 → 커스텀 작업은 **가격표 등록** (Claude Sonnet 4, Gemini 2.5-pro/flash, Claude Haiku LLM-judge) 만.
- Budget alert: Langfuse Cloud 의 Slack webhook (일일 $X 초과 시) — 자체 구현 시 `scripts/cost_alert.py` + GitHub Actions cron (Windows 개발 환경 고려, UTC 기준).
- 대시보드: 모델별 · intent별 · 세션별 (해시된 session_id) top spender.

#### 3.3.5 Feedback UI (L4)

**진입점**: `frontend/src/components/chat/MessageBubble.tsx` (assistant 메시지).

```
MessageBubble
  └ [👍 👎 🔗공유] 버튼 → POST /api/feedback {session_id, trace_id, score, comment?}
                            └→ Langfuse score API 전달 (trace 에 귀속)
```

**신규 라우트**: `server/server/api/routes/feedback.py` — slowapi 10/min 동일 정책.

**효과**: Langfuse 에서 "👎 받은 trace" 드릴다운 → 프롬프트/Tool 결함 역추적 루프.

#### 3.3.6 Incident & Runbook (L4)

기존 `docs/ops/runbook.md` 와 `docs/ops/disaster-recovery.md` 에 **LLM 특화 섹션** 추가 (신규 디렉토리 생성 X):

| 섹션 | 위치 | 내용 |
|------|------|------|
| LLM 공급자 장애 | `docs/ops/runbook.md` §새 섹션 | Claude/Gemini 장애 시 대응 — circuit breaker 수동 open, `LLM_PROVIDER` 강제 전환 |
| 비용 폭주 | `docs/ops/runbook.md` §새 섹션 | 예산 초과 감지 시 rate limit 긴급 축소 (`chat_rate_limit=3/min`), feature flag off |
| 프롬프트 회귀 | `docs/ops/runbook.md` §새 섹션 | Eval 회귀 감지 후 롤백 — `PROMPT_SYSTEM_VERSION=v(n-1)` + compose restart |
| 데이터 인시던트 | `docs/ops/disaster-recovery.md` 확장 | Mock/Real 불일치, Alembic 마이그레이션 실패 (기존 `cleanup_alembic.py` 참조) |

#### 3.3.7 Experiment (L5)

- **Prompt A/B**: 세션 hash 기반 50:50 라우팅 → Langfuse metadata `variant` 태그.
- **Model canary**: env flag `LLM_RESPOND_CANARY_RATIO=0.1` → 10% 트래픽을 신모델로.
- **Shadow traffic**: 프로덕션 쿼리를 백그라운드로 신 프롬프트에도 전송 (사용자 노출 X), 점수만 수집. `asyncio.create_task` + 전용 SSE 큐 제외.

### 3.4 기존 구조와의 정합성 체크

| 기존 | 정합 여부 | 비고 |
|------|-----------|------|
| `server/server/services/circuit_breaker.py` | ✅ | Langfuse 독립. circuit state 를 span metadata 로만 노출. |
| `server/server/middleware/metrics.py` | ✅ | 집계 지표 유지. Langfuse 는 raw trace. 중복 아님. |
| SSE 자체 포맷 (`data: {type,...}`) | ⚠️ | `event:` 라인 신설 금지. trace_id 는 **기존 done 이벤트 JSON 필드에만 추가**. |
| `USE_MOCK` 분기 | ✅ | Eval runner 가 preflight 강제. Mock 응답에도 `use_mock=true` metadata 로 trace 기록. |
| Playwright Ring 0~3 | ✅ | L3 Eval 은 별도 트랙. Ring 은 UI 계약 검증 유지. Ring 3 은 eval-gate 결과까지 부분 반영. |
| `_anthropic_valid` 세션 플래그 | ✅ | Langfuse 전송 실패도 동일 패턴 적용 (best-effort, 세션 재시도 스킵). |
| `docs/ops/runbook.md` / `disaster-recovery.md` | ✅ | 신규 디렉토리 없이 섹션 추가만. |

---

## 4. Checklist · 재검토 · Scenario · Pass · Agent 모델

### 4.1 Checklist (Level 단위, 세부 Plan 분기 전제)

#### L1 — Trace 활성화
- [ ] Langfuse **Cloud 계정 vs self-host** 의사결정 기록 (ADR 짧게)
- [ ] `server/server/config.py` Langfuse 3개 env 유효성 검증 (빈 값 허용, 로그만)
- [ ] `graph.py` PAE 컴파일 지점에 `CallbackHandler` 의존성 주입 훅 추가
- [ ] `session_id` 해시 함수 (`hashlib.sha256`, salt = 배포 고유값) 추가
- [ ] SSE **`done`** 이벤트 payload 에 `trace_id` 추가 (기존 type/필드 불변)
- [ ] 5개 대표 쿼리 (summary/compare/recommend/risk/simulate) 로 trace 생성 확인 — planner/actor/evaluator/respond span 모두 존재
- [ ] Langfuse 장애 시 graceful degrade 검증 (엔드포인트 차단 상태에서 /api/chat 정상)

#### L2 — Prompt Registry
- [ ] YAML 스키마 정의 (`version`, `template`, `input_vars`, `owner`, `hash_sha256`)
- [ ] `loader.py` 작성 (YAML → string, 기동 시 hash 검증, Langfuse tag 주입)
- [ ] `system.v1.yaml` / `planner.v1.yaml` / `evaluator.v1.yaml` 이관 (본문만 이동, 함수 유지)
- [ ] `sanitize_prompt_value` / Mock·Real 분기 등 **함수는 `.py` 유지** 명시
- [ ] env `PROMPT_SYSTEM_VERSION=v1` 기반 스왑 동작 (기본값 v1)
- [ ] YAML 변경만 포함된 PR 을 eval-gate 가 자동 엄격화 (threshold -3%→-1%)

#### L3 — Eval Harness
- [ ] `server/tests/evals/datasets/golden_queries.yaml` 초안 30개 (summary/compare/recommend/risk/simulate 각 6개)
- [ ] `runner.py` + `scorers/rule_based.py` (assistant 메시지만, UTF-8 고정)
- [ ] `scorers/llm_judge.py` (Claude Haiku, 1~5 점 + 근거)
- [ ] GitHub Actions `eval-gate` job (PR trigger, 20개 quick set, Mock 모드, ≤4분)
- [ ] Nightly 워크플로우 + Langfuse dataset 업로드 (Mock+Real 둘 다)
- [ ] Real eval 은 `scripts/e2e/preflight.sh` 를 재활용해 `USE_MOCK=false` 컨테이너 기동

#### L4 — Cost + Feedback
- [ ] Langfuse 가격표 커스터마이즈 (Sonnet 4, Gemini 2.5-pro/flash, Haiku)
- [ ] 일일 비용 Slack webhook (cron 또는 Langfuse Cloud 내장)
- [ ] `MessageBubble` 👍/👎 버튼 + optimistic update
- [ ] `POST /api/feedback` + slowapi 10/min → Langfuse score 연계
- [ ] `docs/ops/runbook.md` 에 3개 섹션 추가 (LLM 장애 / 비용 폭주 / 프롬프트 회귀)

#### L5 — Experiment
- [ ] Feature flag 로더 (세션 hash → variant, deterministic)
- [ ] Prompt A/B 2개 variant 동시 Registry 유지 + trace 태그 분리
- [ ] Canary ratio env flag + Langfuse `variant` 태그
- [ ] 주간 실험 리포트 템플릿 (`docs/status/experiments/YYYY-MM-DD.md`)

### 4.2 재검토 (Self-Review Gate)

구현 착수 전 확인:

1. **엣지케이스**
   - Langfuse 엔드포인트 다운 시 서비스 정상 동작? → handler 는 best-effort, 예외 무시 (`_anthropic_valid` 패턴 재사용).
   - USE_MOCK=true 인 PR eval 결과를 production 품질로 오해 가능? → Langfuse UI / 리포트에 `[MOCK]` 배지 + dataset 분리 필수.
   - SSE stream 중단 후 Langfuse trace 는 `incomplete` 로 닫혀야 함 → `graph.py` `finally` 블록 + `handler.flush()` 호출.
   - 프롬프트 YAML 의 hash 가 기동 시 불일치하면? → fail-fast, 기동 거부.

2. **프로젝트 교훈 충돌** (Context §1.3)
   - SSE 포맷 변경 금지: trace_id 는 **추가만**, `event:` 라인 신설 X, type/필드 이름 불변.
   - Python 파일 입출력 `encoding='utf-8'` 강제 (Windows CI ·로컬 둘 다).
   - Eval runner 는 `USE_MOCK` preflight 실패 시 즉시 abort, district_code 런타임 resolve.
   - assertion 은 `role=='assistant'` 메시지만.

3. **타 Plan 충돌**
   - `docs/plan/infra/load-test-plan.md` — 부하 테스트 중 Langfuse 플러싱이 지연 유발 가능. `LANGFUSE_SAMPLING_RATE=0.1` env 도입.
   - `docs/plan/marketscope_improvement.md` — DB/캐시 개선과 별도 트랙. 본 Plan 은 LLM 계층에만 집중.
   - `docs/plan/business/commercialization-plan.md` — 결제 도입 시 사용자 ID 가 trace 에 포함되어 PII 이슈. session_id 는 **해시 필수**, 원본 저장 금지.
   - PAE 구조 재변경 없음: `graph.py` 에 handler 파라미터만 추가, 노드 시그니처 불변 → `current-status.md` 2026-04-03 PAE 전환 결과와 호환.

### 4.3 Scenario (E2E Ring Mapping)

| Scenario ID | Ring | 사전조건 | 실행단계 | 기대결과 |
|-------------|------|----------|----------|----------|
| `R1-TRACE-BASIC` | 1 | Langfuse 기동 (Cloud 또는 local), `USE_MOCK=true` | "강남역 요약해줘" 질의 | Langfuse UI 에 planner/actor/respond 3개 이상 span, SSE `done` 의 trace_id 가 Langfuse trace 와 매칭 |
| `R1-TRACE-DOWN` | 1 | Langfuse 호스트 차단 (방화벽 규칙) | 동일 질의 | /api/chat 정상, 서버 로그에 best-effort warn 1건, trace 미생성 |
| `R2-EVAL-GATE` | 2 | PR 생성 | GitHub Actions `eval-gate` 실행 | 20 쿼리 중 통과율 ≥95%, 실패 1건 이상 → PR block |
| `R2-PROMPT-SWAP` | 2 | `system.v1` 배포 상태 | `PROMPT_SYSTEM_VERSION=v2` 재기동 | trace metadata `prompt_version=system.v2`, YAML hash 검증 통과 |
| `R3-FEEDBACK-LOOP` | 3 | L4 배포 후 실 사용자 | 👎 클릭 | `POST /api/feedback` 200 + Langfuse trace score=-1, 주간 리포트에 집계 |
| `R3-COST-ALERT` | 3 | 일일 예산 $10 설정 | Mock 스크립트로 $12 발생 시뮬 | Slack webhook 메시지 수신 (Langfuse Cloud 또는 cron) |
| `R3-CANARY` | 3 | canary_ratio=0.1 | 100회 호출 | 신 variant 호출 8~12회 (통계 허용 범위), variant 태그 분리 확인 |

### 4.4 Pass 반복

- **Pass 1 (기본)**: L1 → L2 각 Scenario 통과. Mock 환경에서 전 단계 trace 확인.
- **Pass 2 (엣지)**: Langfuse 다운 / SSE 중단 / 잘못된 prompt version / USE_MOCK mismatch / Windows UTF-8 파일 입출력 주입 시 graceful degrade.
- **Pass 3 (성능)**: Langfuse handler 추가 후 **TTFT 증가 <50ms, p95 응답시간 증가 <5%**. `load-test-plan.md` 와 병행 실행. 샘플링 10% 하에서도 주요 span 커버리지 ≥90%.

### 4.5 Agent 모델 선택

| 단계 | 모델 | 근거 |
|------|------|------|
| 아키텍처 설계 (본 문서, L5 실험 설계) | **Opus** | 다층 trade-off, 교훈 상관, Scope 경계 판단 필요 |
| L1/L2/L4 구현 (CallbackHandler, YAML loader, FE 버튼) | **Sonnet** | 정형화 작업 + 파일 경로 정합성 |
| L3 golden query 초안, runner 구현 | **Sonnet** | 도메인 지식 필요 (상권/매출 단위) |
| L3 LLM-as-Judge 스코어러 | **Haiku** (런타임 모델) | 대량 평가 비용 최소화, 근거 코멘트만 수집 |
| 런북 섹션 추가, 문서화 | **Haiku** | 템플릿 기반 |

---

## 5. Validation

### 5.1 도입 성공 기준 (Level 완료 시점)

| Level | KPI | 목표 |
|-------|-----|------|
| L1 | Trace 커버리지 | 모든 `/api/chat` 호출의 95%+ trace 존재 (샘플링 미적용 기준) |
| L1 | Span 완결성 | planner+actor+respond 3 span 동시 존재율 ≥98% |
| L1 | Overhead | 평균 latency 증가 ≤50ms, p95 증가 ≤5% |
| L2 | Prompt 스왑 | env 변경 1회 + 재시작으로 완전 롤백, 코드 배포 없이 가능 |
| L3 | Eval 통과율 | 회귀 gate 20쿼리 ≥95% pass, nightly LLM-judge 평균 ≥4.2/5 |
| L3 | CI 시간 | eval-gate job ≤4분 |
| L4 | 비용 정확도 | Langfuse 집계 vs 공급자 청구액 오차 ≤3% |
| L4 | 피드백 수집률 | 응답 중 👍/👎 수신 ≥5% |
| L5 | 실험 유효성 | 주간 A/B 리포트 자동 생성, p-value 포함 |

### 5.2 지속 운영 지표 (도입 후 상시)

- **Reliability**: LLM 호출 성공률 ≥99%, circuit open 발생 주 ≤1회
- **Latency**: TTFT p95 ≤3s (Context §1.3 Claude 기준 유지), 전체 응답 p95 ≤15s
- **Quality**: Golden eval 주간 점수 ±2% 이내 안정, 👎 비율 ≤10%
- **Cost**: 쿼리당 평균 비용 목표 범위 ($0.01~0.03) 유지, 주간 예산 편차 ±15%
- **Experiment**: 진행 중 실험 ≤2개 (과도한 동시 변수 방지)

### 5.3 회귀 방지 루프

```
[사용자 👎]
     ↓
[Langfuse trace 수집 (trace_id 로 SSE ↔ Langfuse 매칭)]
     ↓
[주간 리뷰 — 저점수 trace 상위 10개 → Golden query 후보]
     ↓
[Eval dataset 갱신 → 프롬프트 YAML 수정 → PR eval-gate]
     ↓
[프롬프트 v(n+1) 배포 (canary 10%)]
     ↓
[24h 점수 모니터링 → 전면 배포 or 롤백 (env 한 줄)]
```

---

## Metadata

- **작성일**: 2026-04-21 (v2 — 현 프로젝트 상태 반영 개선본)
- **작성자**: Claude (Opus)
- **상태**: Proposal (idea-level)
- **분기 Plan 예정**:
  - `docs/plan/infra/llmops-l1-langfuse-wiring.md` (L1)
  - `docs/plan/infra/llmops-l2-prompt-registry.md` (L2)
  - `docs/plan/infra/llmops-l3-eval-harness.md` (L3)
  - `docs/plan/infra/llmops-l4-cost-feedback.md` (L4)
  - `docs/plan/infra/llmops-l5-experiment.md` (L5)
- **관련 문서**:
  - `docs/architecture/overview.md` — 전체 구조 (§4 Circuit Breaker/Singleflight)
  - `docs/architecture/agent.md` — PAE 그래프 · Tool 레지스트리 · §7 Langfuse wiring 계획
  - `docs/architecture/backend.md` — §5 Services (cache/circuit_breaker/category_resolver)
  - `docs/plan/infra/load-test-plan.md` — L1 도입 후 회귀 테스트 대상
  - `docs/plan/marketscope_improvement.md` — 비-LLM 인프라 개선 (별도 트랙)
  - `docs/ops/runbook.md` / `docs/ops/disaster-recovery.md` — L4 에서 섹션 추가
  - `docs/status/current-status.md` — 2026-04-13 LLM 전환, 2026-04-17 매출 단위 fix, 2026-04-21 E2E 그린
- **프로젝트 내 근거 (memory 대체)**:
  - SSE 포맷 — `server/server/api/routes/chat.py`
  - TTFT 모델 벤치마크 — `current-status.md` 2026-04-13
  - district_code Mock/Real 런타임 resolve — 커밋 `ff9909c`
  - 매출 분기→월 환산 — `repositories/real/_units.py::MONTHS_PER_QUARTER` + current-status.md 2026-04-17 (2026-07-04 정정: 구 인용처 `docs/plan/fix/sales-unit-conversion-fix.md` 는 리포에 부재)
  - Next.js `_` prefix rule — 커밋 `3c5f884`
  - Anthropic 401 세션 플래그 — `server/server/agent/graph.py` `_anthropic_valid`
