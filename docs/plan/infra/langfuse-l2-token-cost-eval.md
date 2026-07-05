# Langfuse L2+ — 토큰/비용/Prompt Version/Eval Harness

> 카테고리: infra
> 생성일: 2026-05-06
> 담당: sjkim
> 모델: 설계 opus / 구현 sonnet / 검증 haiku

## Context

### 문제
L1 (trace wiring + graceful degrade + 11차원 metadata + 6 score) 은 2026-04-28 완료. 다음 격차:

1. **토큰/비용 미측정** — Anthropic/Gemini 응답에 `usage.input_tokens`/`output_tokens` 가 있으나 generation observation 에 attach 되지 않음 → Langfuse Cost 대시보드 0원 표기
2. **Prompt version 누락** — system.py/respond.py/planner.py 프롬프트가 코드 inline. 변경 시 회귀 추적 불가
3. **Eval harness 부재** — Round 1/2 는 수동 SSE 캡처 + grading. Langfuse Datasets/Experiments 미사용 → 회귀 자동화 불가

목표: **토큰/비용 generation 단위 attach + prompt version 태깅 + Datasets/Experiments 기반 nightly eval** 3축으로 LLMOps 운영 자동화.

### 메모리 참조

> (2026-07-04 정정: 아래 auto-memory 파일 링크는 구 머신 경로라 현 리포에서 해석 불가 — 링크 제거, 교훈 요지만 보존.)

- [[feedback_langfuse_v2_langchain1_incompatible]] — v3 + langchain 1.x 조합 필수
- [[feedback_langfuse_sdk_drift_silent]] — 컨테이너 stale SDK silent fail
- [[feedback_langfuse_v3_no_update_trace]] — v3 update_trace 부재, score 는 trace_id 기반
- [[feedback_langfuse_otel_insecure_partial]] — REST 호출은 OTEL_INSECURE 미적용

### 관련 Plan
- [llmops-platform.md](./llmops-platform.md) — 전체 LLMOps 청사진
- [llmops-l1-verification.md](./llmops-l1-verification.md) — L1 trace wiring 검증
- [langfuse-aggregate-stats-2026-04-28.md](./langfuse-aggregate-stats-2026-04-28.md) — 11차원 metadata + 6 score
- [langfuse-cost-coverage-fix-2026-04-24.md](./langfuse-cost-coverage-fix-2026-04-24.md) — v3 SDK drift 가드

### 코드 스폿
- `server/server/services/langfuse_tracer.py` — v3 Client + CallbackHandler 싱글톤
- `server/server/agent/nodes/planner.py` — Claude Sonnet 4 호출 (`_run_llm_classify`)
- `server/server/agent/nodes/evaluator.py` — Gemini flash 호출
- `server/server/agent/nodes/respond.py` — Gemini pro 스트리밍 + system prompt
- `server/server/agent/prompts/{system,planner,evaluator}.py` — inline 프롬프트 상수
- `server/tests/test_langfuse_aggregate.py` — L1 회귀 16 testcase

---

## Scope

### In-scope
1. **L2-A 토큰/비용 attach**
   - `langfuse_tracer.py` 에 `attach_generation_usage(trace_id, model, input_tokens, output_tokens)` 헬퍼 추가
   - planner/evaluator/respond 노드에서 LLM 응답 직후 호출 (Anthropic `response.usage` / Gemini `usage_metadata`)
   - cost 는 Langfuse 가 model name 으로 자동 산출 (수동 단가 입력 X)
2. **L2-B Prompt version 태깅**
   - `prompts/` 모듈 상수에 `_VERSION = "v1.0.0-{sha7}"` 자동 주입 (build-time git rev-parse)
   - generation observation `prompt_name` + `prompt_version` 필드 세팅
   - 변경 시 `langfuse-promote-prompt.py` 스크립트로 production label 이동
3. **L2-C Eval Harness**
   - `server/scripts/langfuse_eval/` 신규 디렉토리
   - `dataset_manager.py` — Round 1/2 시나리오를 Langfuse Dataset 으로 동기화 (idempotent)
   - `run_experiment.py` — 데이터셋 N건 입력 → /api/chat 호출 → trace_id 회수 → Langfuse Experiment 생성
   - `grader.py` — 자동 grading (numeric_sanity + ground truth diff + clarification 회귀 4종)
4. **L2-D 회귀 테스트**
   - `tests/test_langfuse_l2_usage.py` — usage attach 6 testcase (planner/evaluator/respond × 정상/실패)
   - `tests/test_langfuse_l2_prompt_version.py` — prompt_version 필드 셋팅 4 testcase

### Out-of-scope (별도 plan)
- Langfuse Self-Hosted 마이그레이션 (현재 Cloud 사용)
- Custom LLM-as-judge grader (Round 3 별도 Plan)
- Anthropic prompt caching billing 분리 (별도 plan, Anthropic SDK feature 안정화 후)

---

## Design

### L2-A 토큰/비용 흐름

```
planner_node → ChatAnthropic.ainvoke()
    │
    ├─ response.usage_metadata = {"input_tokens": 1024, "output_tokens": 256}
    │
    ▼
attach_generation_usage(
    trace_id=ctx.trace_id,
    model="claude-sonnet-4-20250514",
    input_tokens=1024,
    output_tokens=256,
    prompt_name="planner_intent_classify",
    prompt_version="v1.2.0-a3b9c8f",
)
    │
    ▼
client.start_observation(
    trace_context=TraceContext(trace_id=trace_id),
    as_type="generation",
    model=model,
    usage_details={"input": input_tokens, "output": output_tokens},
    metadata={"prompt_name": prompt_name, "prompt_version": prompt_version},
).end()
```

Langfuse Cloud 가 model name → 단가 자동 매핑 (claude-sonnet-4 = $3/MTok in, $15/MTok out, gemini-2.5-flash = $0.075/$0.30).

### L2-B Prompt Version

```python
# server/server/agent/prompts/system.py
import subprocess

def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=Path(__file__).parent, stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"

_BASE_PROMPT_VERSION = f"v1.0.0-{_git_sha()}"
_BASE_PROMPT = """..."""
```

generation observation 에 `metadata.prompt_version` 으로 attach. Langfuse UI 에서 version 별 score 분포 비교 가능.

### L2-C Eval Harness 구조

```
server/scripts/langfuse_eval/
├── __init__.py
├── dataset_manager.py      # YAML → Langfuse Dataset upsert
├── run_experiment.py       # CLI: --dataset accuracy-round-3 --backend localhost:8000
├── grader.py               # numeric_sanity + ground_truth_diff + clarification_check
├── datasets/
│   ├── accuracy-round-3.yaml   # 16 user-journey + 8 accuracy + 21 out-of-scope
│   └── regression-baseline.yaml # 회귀 차단용 best-of
└── README.md
```

CLI 사용:
```bash
USE_MOCK=false python server/scripts/langfuse_eval/run_experiment.py \
  --dataset accuracy-round-3 \
  --label "round-3-w1-hardened-2026-05-10" \
  --concurrency 4
# → Langfuse Experiment ID, 평균 score, 회귀 diff 출력
```

### Token/Cost 미적용 케이스
- Greeting short-circuit: LLM 0건 → token 0, cost 0 (정상)
- Circuit breaker OPEN: LLM 호출 skip → trace metadata `cb_state="OPEN"` 만 기록
- Streaming 도중 client abort: `try/finally` 에서 partial usage attach (output_tokens=0 가능)

---

## Checklist

- [ ] **L2-A.1** `langfuse_tracer.py::attach_generation_usage` 추가 + graceful degrade
- [ ] **L2-A.2** `planner.py::_run_llm_classify` LLM 응답 후 attach 호출
- [ ] **L2-A.3** `evaluator.py::_run_llm_evaluate` 동일 패턴
- [ ] **L2-A.4** `respond.py::respond_node` 스트리밍 종료 finally 에서 attach
- [ ] **L2-A.5** Anthropic usage_metadata vs Gemini usage_metadata key 차이 흡수 (`_normalize_usage`)
- [ ] **L2-B.1** `prompts/system.py` + `planner.py` + `evaluator.py` 에 `_VERSION` 상수 + `_git_sha()` 헬퍼 (1회 import 시 캐시)
- [ ] **L2-B.2** generation observation 에 `prompt_name` + `prompt_version` metadata 셋팅
- [ ] **L2-B.3** `scripts/langfuse_promote_prompt.py` (라벨 이동 스크립트, optional)
- [ ] **L2-C.1** `server/scripts/langfuse_eval/dataset_manager.py` — YAML loader + Langfuse Dataset upsert (idempotent — name 동일 시 update)
- [ ] **L2-C.2** `datasets/accuracy-round-3.yaml` — 16 user-journey + 8 accuracy + 21 out-of-scope 통합
- [ ] **L2-C.3** `run_experiment.py` — POST /api/chat → SSE 수집 → trace_id 회수 → Experiment 생성
- [ ] **L2-C.4** `grader.py` — numeric_sanity + ground_truth_diff + clarification_check 4 axis
- [ ] **L2-D.1** `tests/test_langfuse_l2_usage.py` 6 testcase (planner/evaluator/respond × 성공/실패)
- [ ] **L2-D.2** `tests/test_langfuse_l2_prompt_version.py` 4 testcase
- [ ] **L2-D.3** `validate_env.py` 에 `LANGFUSE_HOST` + SDK 버전 ≥3.0 가드 추가

### 재검토 (Self-Review Gate)
- [ ] Anthropic SDK `response.usage` vs LangChain `response.usage_metadata` 키 차이 — `_normalize_usage` 로 흡수했는가
- [ ] streaming 응답에서 `output_tokens` 는 `on_llm_end` 콜백에서만 정확 — finally 에서 None 가능 → graceful skip
- [ ] git rev-parse 실패 환경 (Docker 내 .git 부재) → `_git_sha()` "unknown" fallback. ETL Dockerfile 에 ARG GIT_SHA 주입 고려
- [ ] Dataset upsert 시 동일 name 중복 → Langfuse 가 새 ID 생성. `dataset_manager.py` 에 by-name 검색 후 update 처리
- [ ] 메모리 교훈: SDK drift 회귀 — `validate_env.py` 에 `langfuse>=3` assert 보강
- [ ] 메모리 교훈: REST 호출 verify — dev MITM 환경에선 `LANGFUSE_HOST` HTTP 강제 또는 cert path 명시
- [ ] 다른 Plan 충돌: [accuracy-gap-eval-round2-2026-04-24.md](../fix/accuracy-gap-eval-round2-2026-04-24.md) 의 수동 grading 과 중복 — Round 3 부터는 본 harness 로 대체

### Scenario (E2E Ring Mapping)
| Ring | ID | 시나리오 |
|------|----|---------|
| 0 | Ring0-L2-USAGE-NORMAL | planner Anthropic 호출 후 generation usage 검증 (input/output tokens > 0) |
| 0 | Ring0-L2-USAGE-FAIL | Anthropic 503 → CB OPEN → usage attach skip + trace metadata cb_state |
| 0 | Ring0-L2-PROMPT-VER | system/planner/evaluator prompt_version 필드 셋팅 회귀 |
| 1 | Ring1-L2-EXPERIMENT | run_experiment.py 5건 dataset → Experiment 생성 + 평균 score |
| 1 | Ring1-L2-GRADER-NUM | numeric_sanity 자동 grading score 매핑 |
| 3 | Ring3-L2-DRIFT-GUARD | validate_env.py SDK<3.0 시 fail-fast 회귀 |

### Pass 반복
- **Pass 1 (기본)**: L2-A + L2-B 구현 → unit 10 testcase PASS
- **Pass 2 (엣지)**: streaming abort / CB OPEN / git sha unknown / dataset name 중복
- **Pass 3 (성능)**: 100 trace 동시 발행 시 attach overhead < 50ms p99, eval harness 30 testcase 5분 이내

---

## Validation

### 검증 명령
```bash
# Pass 1 — Backend pytest
cd server && pytest tests/test_langfuse_l2_*.py -v

# Pass 2 — Live trace 확인
USE_MOCK=false LANGFUSE_PUBLIC_KEY=... python -c "..."
# Langfuse UI 에서 trace_id 검색 → generation 의 usage_details 확인

# Pass 3 — Experiment harness
python server/scripts/langfuse_eval/run_experiment.py \
  --dataset accuracy-round-3 --label pass-3-validation
```

### 합격 기준
- [ ] usage attach 성공률 ≥ 99% (정상 호출 기준)
- [ ] Langfuse Cost 대시보드에 일자별 비용 표기 (claude/gemini 분리)
- [ ] prompt_version 미설정 generation 0건
- [ ] Eval harness Round 3 자동 실행 < 10분 / 30 testcase

### 결과 (2026-05-07 Pass 1 — Foundation)

**구현 완료 (L2-A.1 + L2-A.5 + L2-B.1)**:
- `server/server/services/langfuse_tracer.py` —
  - `_normalize_usage(response | dict)` 헬퍼: LangChain `usage_metadata` / Anthropic native `usage.input_tokens` / Gemini `prompt_token_count`+`candidates_token_count` / OpenAI `prompt_tokens`+`completion_tokens` 4 가지 shape 흡수.
  - `attach_generation_usage(trace_id, *, model, input_tokens, output_tokens, prompt_name?, prompt_version?, name?)` — Langfuse v3 `start_observation(as_type="generation", model=..., usage_details={input,output}, metadata={prompt_name, prompt_version})` 발행. Trace 비활성/disabled/예외 모두 silent.
  - `_git_sha()` 헬퍼: `git rev-parse --short=7 HEAD` 실패 시 `"unknown"` fallback.
  - `prompt_version("v1.0.0")` → `"v1.0.0-<sha7>"` 빌드.
- `server/tests/test_langfuse_l2.py` — 12 testcase: shape 흡수 6 (LangChain/Anthropic/Gemini/OpenAI/empty/partial) + attach 가드 3 (no trace_id / 0 tokens / disabled) + prompt_version 3.

**Pass 1 검증** (PYTHONIOENCODING=utf-8 pytest server/tests/test_langfuse_l2.py):
- 12/12 PASS · 0.23s
- ruff PASS (langfuse_tracer.py + test_langfuse_l2.py)
- 전체 backend pytest 120 passed (108 + 12 신규) / 8 skipped (route deps), 회귀 0.

**Pass 1 미진 (후속 sweep 필수)**:
- **L2-A.2 / L2-A.3 / L2-A.4** — `planner.py` / `evaluator.py` / `respond.py` 노드에서 LLM 호출 직후 `attach_generation_usage` 호출. 각 노드의 LLM 응답 객체 (`AIMessage` / `LangChainCallback` / streaming chunk) 가 어떤 usage shape 인지 확인 후 통합 — 실 backend stack 검증 필요. 본 Pass 1 에서는 헬퍼 + 테스트만 우선 정착.
- **L2-B.2** — `prompts/system.py` / `planner.py` / `evaluator.py` 모듈에 `_VERSION = prompt_version("v1.0.0")` 상수 + generation observation 의 `metadata.prompt_version` 셋팅. 노드 통합과 함께 진행.
- **L2-C (Eval Harness)** — `server/scripts/langfuse_eval/` 디렉토리, `dataset_manager.py` + `run_experiment.py` + `grader.py` + `datasets/accuracy-round-3.yaml`. 별도 Pass 로 분리 (M, 2~3d).
- **L2-D.1 / L2-D.2** — usage attach + prompt_version 노드 회귀 6+4 testcase. L2-A.2~4 와 L2-B.2 와 함께 추가.
- **validate_env.py SDK ≥ 3.0 가드** — 본 Pass 1 에서는 미적용. CI 환경에 langfuse SDK drift 차단 추가는 후속.

**다음 P0 (후속)**:
1. planner/evaluator/respond 노드 wiring (Pass 2) — attach + prompt_version 셋팅 + L2-D 회귀 10 testcase.
2. L2-C eval harness — Round 3 자동화 단계.
3. live trace 검증 — Langfuse Cloud UI 에서 generation observation cost 표기 확인.

---

## Metadata
- 우선순위: 🟠 P1
- 난이도: M (3~5d)
- Phase 2 의존성: 없음 (LLMOps 운영 향상, 독립 진행)
- 후속: Round 3 eval (W1 type boost 약화 측정 Plan 과 결합)
