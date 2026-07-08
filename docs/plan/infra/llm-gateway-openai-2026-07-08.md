# LLM Gateway — OpenAI GPT 지원 (LLM_PROVIDER 선호-우선 체인)

> 작성: 2026-07-08 · 관련: [langfuse-l2-token-cost-eval.md](langfuse-l2-token-cost-eval.md)(tracer 선후행 무관 확인) · [auto-deploy-on-push.md](auto-deploy-on-push.md)(Pass 3 배포 창 조율) · 상태: **plan 확정, 구현 미착수**

## Context

사용자 요구 3항: ① OpenAI GPT 를 **모든 LLM 파이프라인**에서 사용 가능하게(v2 loop + Trust 교정 + PAE 4소비자), ② ops 기능 수정 포함, ③ 사용자 입장에서 최대한 쉽게.

현재 갭 (2026-07-08 세션에서 코드 검증):

- **P1 — `LLM_PROVIDER` 가 v2 체인과 무관**: v2 체인(`server/server/agent/loop/models.py:41-56`)은 키-존재 고정 순서(anthropic→gemini_pro→gemini_flash). env 로 provider 를 바꿔도 v2 는 여전히 Claude 우선 — "바꿨는데 안 바뀐다" 혼란 구조. `LLM_PROVIDER` 는 mock 디스패치(`runtime.py:16-17`)와 PAE 역할 선택에만 관여.
- **P2 — OpenAI 미지원**: `langchain-openai` 의존성 부재, `_build()`(models.py:59-76)에 분기 없음.
- **P3 — PAE 하드코딩 잔재**: `graph.py:74, 96` 에 `"claude-sonnet-4-6"` 리터럴 — 모델 은퇴 시 PAE 폴백이 404 나는 잠복 지점(2026-06 dead-model 사고 동형).
- **P4 — prod compose 주입 갭**: `docker-compose.prod.yml:86-105` 는 명시 `environment:` 블록만 주입(env_file 없음) — OPENAI env 를 안 넣으면 컨테이너 영구 미인지. 기존 `ANTHROPIC_MODEL`/`GEMINI_MODEL_*` passthrough 도 부재(모델 ID env 핫픽스가 prod 에서 현재 동작 불가 — 선택 항목 P2-8 로 동시 해소).

**사용자 결정 (2026-07-08)**: ① 체인 제어 = **LLM_PROVIDER 선호-우선(preferred-first)** — 신규 env 없이 기존 var 가 v2 체인 1순위 결정, 나머지 키-존재 폴백. 현 prod(`.env` `LLM_PROVIDER=anthropic`) 동작 무변경. ② 이번 산출물 = **plan 문서까지만**, 구현 Pass 는 후속 세션(auto-deploy 미발화 블로커와 순서 조율).

**Memory 참조**: `feedback_anthropic_model_id_retired_404`(모델 ID settings 필수 — P3 근거 + OPENAI_MODEL 기본 ID 는 P1-1 검증 후 확정) · `feedback_protect_secrets_hook_env_edit_block`(.env/.env.dev 수정은 수동 diff 분리) · `feedback_env_convention_inverted`(`.env`=prod / `.env.dev`=로컬) · `feedback_langfuse_v2_langchain1_incompatible`(langchain 1.x 페어링 — P1-0 dry-run 선검증 근거) · `feedback_compose_env_block_overrides_env_file`(compose environment 블록이 호스트 셸을 읽음 — `${VAR:-기본}` 형 필수) · `feedback_docker_build_pipe_tail_masks_failure`(로컬 이미지 재빌드 회피 — 검증은 venv 로) · `feedback_shell_python_wrong_venv`(pytest 는 Python313 절대경로) · `feedback_langfuse_sdk_drift_silent`(의존성 드리프트가 관측을 조용히 끔 — 재검토 §의존성).

## Scope

- **In**: config 필드 2개 · v2 체인 선호-우선 재작성(+데드코드 제거) · `_build` openai 분기 · PAE `_create_llm` diff 3점 · health detail `llm_chain` · `langchain-openai` 의존성 · 신규 유닛 2파일(13케이스) + 기존 증분 3건 · env/compose/deploy/validate_env · 문서 8종 sync · 수동 적용 diff
- **Out (과잉설계 컷 — 백로그 노트만)**: 신규 게이트웨이 모듈/추상화 · 신규 체인 env(`LLM_FALLBACK_CHAIN` — 사용자 배제 확정) · temperature/max_tokens env 화 · per-provider circuit breaker · openai 역할별 모델 분리(pro/mini 2단) · `llm_chain` 에 breaker 상태 등 부가정보 · e2e OPS-01 required 목록 `llm_chain` 즉시 편입(후속 sweep) · learning 문서 4종 sync(docs-diet 후속)

## Design

| 결정 | 내용 | 근거 |
|---|---|---|
| 체인 제어 | 기본 체인 **anthropic → openai → gemini_pro → gemini_flash**(키 게이트) 생성 후 `settings.llm_provider` 후보(들)를 선두로 **stable partition** 1회 | 신규 env 0개. "provider 만 바꾸면 그 모델이 답한다" UX. gemini 선호 시 pro·flash 블록째 이동(내부 순서 유지) |
| openai 기본 슬롯 | anthropic 다음, gemini 앞 (2순위) | 키만 추가 = 폴백 카나리아 → `LLM_PROVIDER=openai` 로 승격하는 2단 롤아웃 스토리 |
| 선호 키 부재/오타 | 키 게이트가 후보를 이미 제거 → 기본 체인 + **per-process 1회 warning**(`_chain_warning_logged` 모듈 플래그) | per-invoke 호출이라 무플래그 시 요청당 2~6회 스팸. 상시 가시성은 health `llm_chain` 담당. `graph.py:26 _anthropic_valid` 동일 관례 |
| 전 키 부재 | 기존 RuntimeError 가드(models.py:101-102, astream 쪽 동일) 메시지에 `ANTHROPIC_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY` 힌트 추가 | 컨테이너 로그만으로 즉시 조치 가능 |
| 데드코드 | models.py:53-55(`if not chain and settings.anthropic_api_key`) 제거 — 항상 거짓(48행에서 이미 추가) | 체인 재작성에 포함되는 자기 정리 |
| `_build` openai | `ChatOpenAI(model=candidate.model_id, api_key=settings.openai_api_key, max_tokens=4096, temperature=0.3)` — lazy import | 기존 anthropic/gemini 분기와 동일 관례. `bind_tools`/`astream` 제네릭이라 engine/Trust 무변경 |
| PAE diff 3점 | ① :74/:96 → `settings.anthropic_model` de-hardcode ② mock 분기(:45-66) 직후·planner-anthropic 선호(:70) **이전**에 `if LLM_PROVIDER == "openai" and settings.openai_api_key:` → 전 역할 단일 `openai_model` ③ 그 외 무변경(planner anthropic 선호는 gemini provider 에서 종전 유지) | 키 가드 필수(빈 키 `ChatOpenAI` init 크래시 → 부재 시 기존 분기 폴스루 = 우아한 강등). 소비자 4곳(planner:228 / evaluator:149 / respond:452 / rewriter:239) 전부 `_create_llm` 경유라 자동 커버 |
| config | `openai_api_key: str = ""` + `openai_model: str = "gpt-5.4-mini"`(기본값 부여) + `llm_provider` 주석에 `"openai"` | `anthropic_model` 관례 동일. 키 존재가 체인 편입을 게이트하므로 기본 ID 는 키 있을 때만 의미 — 빈 기본값은 신규 실패 모드만 추가 |
| OPENAI_MODEL 검증 | **결정(2026-07-08): `gpt-5.4-mini`** — GPT-5.x reasoning 모델이라 `temperature=0.3` 미수용(비-기본값 400) → **openai 분기에서만 temperature 생략**(config.py 주석 + `_build`/graph.py 반영). tool-calling 지원 O. gpt-4.1 은 2026-10-14 API 은퇴 임박이라 배제(dead-model 원칙 위배). langchain-openai 가 `max_tokens`→`max_completion_tokens` 자동 매핑 | 실키 스모크·cost 매핑은 P3-1/P3-4. mini = 2순위 폴백 카나리아 슬롯에 저렴/충분 |
| `_normalize_usage` | **무변경 확정** | `langfuse_tracer.py:482-483` 이 LangChain 표준 키(`input_tokens`/`output_tokens`) + OpenAI raw 키(`prompt_tokens`/`completion_tokens`) 이미 처리(코드 검증). 드리프트 가드 유닛 1건만 추가 |
| health `llm_chain` | models.py 에 공개 `chain_summary() -> list[str]`(`"provider:model_id"` 라벨) 신설 → `chat.py:185` `llm_provider` 아래 `"llm_chain": chain_summary()` 1줄 | 배포 직후 "prod 가 키/순서를 인지했는가" 원큐 확인 — auto_deploy smoke 가 이미 health detail 을 curl. e2e OPS-01 은 required-필터 방식(`ops-endpoints.spec.ts:46-59`)이라 필드 추가 무해. mock 스택에선 "v2 였다면 쓸 체인" 이 노출되나 `agent_mode=pae`/`llm_provider=mock` 이 문맥 제공 |
| 의존성 | pyproject `langchain-openai>=1` (AI/Agent 블록) | `langchain>=1,<2` 페어링. P1-0 dry-run 으로 로컬 venv(langchain-core 1.2.22) 충돌 선검증 |
| Langfuse | tracer **무수정** — metadata `llm_provider`(langfuse_tracer.py:223) / tags `provider:{...}`(:237) 가 settings 값 그대로 통과 → `provider:openai` 자동 등장 | cost 는 Langfuse Cloud 의 모델명→단가 매핑 — 미매핑 시 **silent-null** → P3-4 명시 확인 + runbook :280-285 수동 등록 절차 |
| mock 불변식 | `llm_provider=="mock"` → `_use_v2()` False(runtime.py:17) + `_create_llm` mock 분기 최우선(graph.py:45) — 두 지점 무접촉 | R0-LLMGW-MOCK-INV 로 고정. `chain_summary()` 는 `preferred != "mock"` 조건으로 mock 스택 health 에서 무경고 통과 |
| 롤백 | **env-only**: `LLM_PROVIDER` 원복(선두만 복귀) 또는 `OPENAI_API_KEY` 제거(체인에서 openai 완전 소거) | openai 분기·deps 는 lazy import — 키 없으면 도달 자체가 없어 코드/이미지 롤백 불필요 |

### `_candidate_chain()` 의사코드 (models.py:41-56 전면 교체)

```python
_KNOWN_PROVIDERS = ("anthropic", "openai", "gemini")
_chain_warning_logged = False  # per-process 1회 경고

def _candidate_chain() -> list[ModelCandidate]:
    global _chain_warning_logged
    chain: list[ModelCandidate] = []
    if settings.anthropic_api_key:
        chain.append(ModelCandidate("anthropic", settings.anthropic_model))
    if settings.openai_api_key:
        chain.append(ModelCandidate("openai", settings.openai_model))
    if settings.google_api_key:
        chain.append(ModelCandidate("gemini", settings.gemini_model_pro))
        chain.append(ModelCandidate("gemini", settings.gemini_model_flash))

    preferred = settings.llm_provider
    front = [c for c in chain if c.provider == preferred]
    if front:
        return front + [c for c in chain if c.provider != preferred]
    if preferred != "mock" and not _chain_warning_logged:
        _chain_warning_logged = True
        # known 인데 키 부재 vs unknown 값 — 각각 다른 warning 1회
    return chain
```

### 터치 파일 전수 (12)

| # | 파일 | 변경 | 앵커 |
|---|---|---|---|
| 1 | `server/server/config.py` | 필드 2개 + `llm_provider` 주석 4값 | :30-42 |
| 2 | `server/server/agent/loop/models.py` | `_candidate_chain` 재작성 · `_build` openai 분기 · 빈 체인 메시지 2곳 · `chain_summary()` 신설 | :41-56, :59-76, :101-102, astream 가드 |
| 3 | `server/server/agent/graph.py` | de-hardcode ×2 + openai 분기 | :45-100 (하드코딩 :74/:96, 삽입점 :66-70 사이) |
| 4 | `server/server/api/routes/chat.py` | health detail `llm_chain` 1줄 + import | :176-189 |
| 5 | `server/pyproject.toml` | `langchain-openai>=1` | dependencies |
| 6 | `server/tests/conftest.py` | `OPENAI_API_KEY` dummy setdefault | :14-22 |
| 7 | `.github/workflows/ci.yml` | backend-test env `OPENAI_API_KEY: "sk-test-dummy"` | backend-test env 블록 |
| 8 | `.env.example` | OPENAI 섹션(키 발급 안내 + OPENAI_MODEL 주석) + `LLM_PROVIDER` 주석 4값 + 선호-우선 1줄 | LLM 섹션 |
| 9 | `docker-compose.prod.yml` | `OPENAI_API_KEY: ${OPENAI_API_KEY:-}` + `OPENAI_MODEL: ${OPENAI_MODEL:-gpt-5.4-mini}` | :86-105 environment |
| 10 | `scripts/deploy/auto_deploy.sh` | unset 목록 `OPENAI_API_KEY OPENAI_MODEL` | :61-66 |
| 11 | `scripts/validate_env.py` | `LLM_ALTERNATIVES` 에 `"OPENAI_API_KEY"` | :42 |
| 12 | 문서 8종 | 아래 문서 sync | — |

> ⚠ compose #9 의 `OPENAI_MODEL` 은 반드시 `${VAR:-<기본ID>}` 형 — `${VAR:-}` 는 **빈 문자열이 pydantic 기본값을 덮어써** `ChatOpenAI(model="")` 로 붕괴(기존 `LLM_PROVIDER: ${LLM_PROVIDER:-gemini}` 관례 동일 적용).
> 무변경 확인: `runtime.py`(mock 불변식) · `langfuse_tracer.py` · `middleware/metrics.py` · `services/circuit_breaker.py`(단일 breaker 유지) · `docker-compose.yml`(dev 는 env_file 로 자동 유입) · `docker-compose.e2e.yml`(mock 전용) · eval 스크립트(HTTP-only) · 프론트 전체.

### 테스트 매트릭스 (신규 13 + 증분 3)

**신규 `server/tests/test_loop_models_chain.py`** — 순수함수라 fake LLM 불요, `monkeypatch.setattr(settings, ...)` 패턴. 각 테스트 setup 에서 `models._chain_warning_logged` 리셋:

| # | 케이스 | 단언 |
|---|---|---|
| 1 | 전 키 + provider=anthropic | `[anthropic, openai, gemini_pro, gemini_flash]` |
| 2 | 전 키 + provider=openai | `[openai, anthropic, gemini_pro, gemini_flash]` |
| 3 | 전 키 + provider=gemini | `[gemini_pro, gemini_flash, anthropic, openai]` (블록 이동 + pro→flash 유지) |
| 4 | provider=openai + openai 키 "" | 기본 체인(openai 부재) + caplog 경고 1회, 재호출 무경고 |
| 5 | provider 오타 | 기본 체인 + "unknown" 경고 |
| 6 | google 키만 | `[gemini_pro, gemini_flash]` |
| 7 | 전 키 부재 | `ainvoke_with_fallback` RuntimeError 메시지에 `OPENAI_API_KEY` 포함 |
| 8 | `_build(ModelCandidate("openai", "m"))` | ChatOpenAI + model/max_tokens=4096/temperature=0.3 |
| 9 | `chain_summary()` | `["provider:model", ...]` 라벨 포맷 |

**신규 `server/tests/test_pae_create_llm.py`** — `monkeypatch.setattr(graph, "LLM_PROVIDER", ...)`(**:21 모듈 스냅샷** — settings 만 패치하면 무효):

| # | 케이스 | 단언 |
|---|---|---|
| 10 | provider=openai + 키 → role 4종 | 전부 ChatOpenAI + `settings.openai_model` |
| 11 | provider=openai + 키 "" | 크래시 없이 폴스루(planner→ChatAnthropic, respond→else 분기) |
| 12 | de-hardcode 회귀: `anthropic_model="test-x"` | planner 분기(:74)·else 분기(:96) 모두 model=="test-x" |
| 13 | provider=mock | FakeListChatModel (불변식) |

**기존 증분 3**: `test_langfuse_l2.py` +1 — `AIMessage(usage_metadata={"input_tokens":11,"output_tokens":7,"total_tokens":18})` → `_normalize_usage == (11, 7)` 드리프트 가드 · `test_loop_models_stream.py` +1 — openai 형 tool_call_chunks(동일 index args 분할 2청크) 병합(`fresh_breaker`/`_patch_chain`/`_FakeStreamLLM` 재사용) · `test_metrics_langfuse.py` 근방 +1 — health detail 응답에 `llm_chain` list 존재(`app_client` 재사용).

### 문서 sync 터치리스트

| 파일 | 앵커 | 내용 |
|---|---|---|
| `docs/architecture/agent.md` | §4(:77-91) | 체인 표 4행화 + 선호-우선 규칙 + "키 존재 기준" 문단 갱신 |
| `docs/architecture/overview.md` | :39, :54, :64 | 체인 문구 3곳 |
| `docs/architecture/backend.md` | :89-91 | `llm_provider` 값 + `openai_model` 행 |
| `docs/ops/runbook.md` | :84-102, :275 | Scenario 3 진단(grep `openai\|gpt` + printenv OPENAI_API_KEY) + 체인 문구 + 모델 표. cost null 시 :280-285 등록 절차 참조 |
| `docs/spec/features/F02-ai-chatbot-agent.md` | :17, :95 | 체인 문구 2곳 |
| `server/CLAUDE.md` | Agent 디스패치 절 | 체인 규칙 1줄(선호-우선 + 기본 4단) |
| `README.md` | :114 | 스택 소개 문구 |
| `docs/status/current-status.md` | — | 구현 완료 시 `/status-update` |

> 문서 앵커는 2026-07-08 탐색 기준 — 구현 세션에서 Read 전 Glob/grep 재확인(`feedback_verify_cited_path_before_read`).

## Checklist

### Pass 1 — 코드 + 유닛테스트 (로컬 venv, Python313 절대경로 — Docker 재빌드 금지)

- [x] P1-0 의존성 선검증: `pip install "langchain-openai>=1" --dry-run` → 충돌 0. **주의: langchain-core 가 1.2.22→1.4.8, langchain 1.3.11, langfuse 3.15.0 동반 상향**(전부 pyproject 핀 `<2`/`<4` 범위 내, `ChatOpenAI` import OK). *검증: dry-run + 실설치 green*
- [x] P1-1 OPENAI_MODEL = **`gpt-5.4-mini`**(사용자 결정 2026-07-08). GPT-5.x reasoning → temperature 생략(코드 반영). config/compose 기입 + Design 표 기록. *검증: 공식 문서 tool-calling 지원*
- [x] P1-2 pyproject `langchain-openai>=1` + `pip install -e ".[dev]"`. *검증: `from langchain_openai import ChatOpenAI` OK*
- [x] P1-3 config.py 필드 2개(`openai_api_key`/`openai_model`) + `llm_provider` 주석 4값. *검증: settings 로드 OK*
- [x] P1-4 models.py — 체인 선호-우선 재작성(+`_chain_warning_logged`, 데드코드 제거) / `_build` openai(temp 생략) / 에러 메시지 2곳 env 힌트 / `chain_summary()`. *검증: P1-8 green*
- [x] P1-5 graph.py — de-hardcode ×2(`settings.anthropic_model`) + openai all-roles 분기. *검증: P1-9 green*
- [x] P1-6 chat.py health `llm_chain`(로컬 import — formatter strip 주의, 사용부와 함께 재추가). *검증: 증분 유닛 green*
- [x] P1-7 conftest.py OPENAI dummy. *검증: 전체 스위트 green*
- [x] P1-8 신규 `test_loop_models_chain.py` 9케이스. *검증: green*
- [x] P1-9 신규 `test_pae_create_llm.py` 4케이스. *검증: green*
- [x] P1-10 기존 증분 3건(langfuse_l2 usage 가드 / stream openai split-args / health llm_chain). *검증: green*
- [x] P1-11 게이트: `pytest -m "not real"` → **241 passed / 6 deselected**(225+16) + `ruff check` All passed + `ruff format --check` 153 formatted. *검증: 회귀 0*

### Pass 2 — ops/env/compose/docs sync

- [ ] P2-1 `.env.example` OPENAI 섹션 + LLM_PROVIDER 주석. *검증: `python scripts/validate_env.py` 통과*
- [ ] P2-2 `docker-compose.prod.yml` OPENAI 2줄(기본ID 복제형). *검증: `docker compose -f docker-compose.prod.yml config | grep OPENAI`*
- [ ] P2-3 `auto_deploy.sh` unset +2. *검증: `bash -n`*
- [ ] P2-4 `validate_env.py` LLM_ALTERNATIVES +1. *검증: OPENAI 키만 있는 임시 env 로 exit 0*
- [ ] P2-5 `ci.yml` backend-test env +1. *검증: push 후 CI green*
- [ ] P2-6 문서 8종 sync. *검증: `grep -rn "gemini-2.5-pro" docs/ server/CLAUDE.md README.md` 로 체인 문구 잔재 대조*
- [ ] P2-7 수동 적용 diff(아래) 사용자 적용 + current-status 미결 등록. *검증: 로컬 `settings.openai_api_key` 비어있지 않음*
- [ ] P2-8 (선택·권장) prod compose 에 `ANTHROPIC_MODEL`/`GEMINI_MODEL_PRO`/`GEMINI_MODEL_FLASH` passthrough 3줄 — Context P4 잠복 갭 동시 해소. 미채택 시 재검토에 잔존 갭 기록. *검증: compose config*

### Pass 3 — live 검증 (real key)

- [ ] P3-0 **선행조건**: auto-deploy 발화 회복(현 미결 #1, `last-deploy.json` result=SUCCESS). 미회복 시 본 플랜 커밋도 적체 — prod 항목 착수 금지. *검증: 서버 `cat last-deploy.json`*
- [ ] P3-1 로컬 스모크(venv uvicorn): `.env.dev` 실키 + `LLM_PROVIDER=openai` → `/api/chat` 1問 → v2 tool-call + 카드 + Trust 통과. TTFT 실측(60s 근접 시 `LLM_TIMEOUT_SLOW` 상향 — 무코드). *검증: SSE tool/card/text/done + 로그 openai 성공*
- [ ] P3-2 폴백 증명: `OPENAI_MODEL=존재하지-않는-ID` 1問 → warning 후 anthropic 완결. *검증: 로그 + 응답 정상*
- [ ] P3-3 health: `curl :8000/api/health/detail` → `llm_chain` 선두 `openai:<model>`. *검증: 라벨*
- [ ] P3-4 Langfuse: trace 에 `provider:openai` 태그 + usage>0 + **cost 비-null**(null 시 runbook :280-285 수동 등록 후 재확인). ops-hardening Pass 3 live smoke 와 합승 가능. *검증: Langfuse Cloud UI*
- [ ] P3-5 PAE 경로: `AGENT_LOOP_VERSION=pae` + `LLM_PROVIDER=openai` 1問 + 후속질문 1건(rewriter 경로). *검증: 완결 + 로그에 anthropic/gemini 호출 부재*
- [ ] P3-6 prod 반영: 수동 diff 1단계(카나리아: 키만) → push → auto_deploy → prod health `llm_chain` 에 `openai:` 라벨. 승격(2단계)은 별도 결정. *검증: smoke green + curl*

### 수동 적용 diff (.env / .env.dev — protect_secrets 훅 차단, 사용자 직접 적용)

```diff
# .env (prod) — 롤아웃 1단계(카나리아): 키만 추가 → openai = 2순위 폴백
+OPENAI_API_KEY=sk-proj-...(실키)
+# 모델 핫픽스 필요 시: OPENAI_MODEL=gpt-5.4-mini (또는 후속 GPT-5.x ID)

# .env (prod) — 롤아웃 2단계(승격, 별도 결정): GPT 1순위
-LLM_PROVIDER=anthropic
+LLM_PROVIDER=openai

# .env.dev (로컬)
+OPENAI_API_KEY=sk-proj-...(dev키)
```

## 재검토 (Self-Review Gate)

- [x] `_normalize_usage` OpenAI-ready — langfuse_tracer.py:482-483 코드 직접 검증(2026-07-08). 제3 분기 불필요, 드리프트 가드만
- [x] graph.py `LLM_PROVIDER` 모듈 스냅샷(:21) — 테스트는 `graph.LLM_PROVIDER` 패치 필수(테스트 매트릭스 명기)
- [x] openai 분기 삽입 위치 — planner-anthropic 선호(:70) **앞**이어야 all-roles GPT (코드 확인)
- [x] e2e OPS-01 required-필터 방식 — `llm_chain` 필드 추가 무해
- [x] 기존 체인 테스트와 충돌 없음 — `_candidate_chain` 은 test_loop_models_config.py:38 / test_loop_models_stream.py:63 에서 전부 monkeypatch(실값 단언 없음)
- [ ] 의존성 호환: langchain-openai ↔ langchain-core 1.2.22 — P1-0 dry-run. 로컬 venv 드리프트(langfuse 4.0.1 > pyproject `<4` 핀, marketscope-server stale)는 본 플랜 무수정·기록만. 서버측 이미지 빌드는 pip 재해상도 — 로컬/컨테이너 버전 상이 가능 → P3-1(로컬)·P3-6(prod) 이중 검증으로 흡수
- [ ] Langfuse cost silent-null — 신규 GPT 모델 ID 일수록 미매핑 확률 ↑ → P3-4 명시 확인
- [ ] prod compose 한 줄 누락 = 컨테이너 영구 미인지 → P2-2 config 검증 + R3-LLMGW-PROD-ENV 이중 방어
- [ ] 배포 블로커 연동: 미결 #1(auto-deploy 미발화, 커밋 적체) — P3-0 게이트. auto-deploy Pass 3(24h 관찰)와 배포 창 조율
- [ ] 활성 플랜 충돌: langfuse-l2-token-cost-eval Pass 2/3(PAE generation span) — 본 플랜 tracer 무수정이라 선후행 무관, L2 Pass 2 선행 시 PAE openai usage 자동 수용 메모 · ops-hardening Pass 3 live smoke 는 P3-4 합승
- [ ] GPT-5 계열 temperature/지연 리스크 — P1-1 에서 결정 + P3-1 TTFT 실측(`llm_timeout_slow` env-overridable, config.py:110-114)
- [ ] `_chain_warning_logged` 전역 상태 — 테스트 간 누수 방지 리셋(매트릭스 명기)
- [x] mock 불변식 — runtime.py:17 / graph.py:45 무접촉 + R0-LLMGW-MOCK-INV 고정

## Scenario (E2E Ring Mapping)

| ID | Ring | 내용 | 검증 |
|---|---|---|---|
| R0-LLMGW-CHAIN-PREF | 0 | provider 값별 선호-우선 순서 (매트릭스 1~3) | pytest |
| R0-LLMGW-CHAIN-KEYGATE | 0 | 키 게이트 + 선호 키 부재 경고 1회 + 오타 (4~6) | pytest + caplog |
| R0-LLMGW-CHAIN-EMPTY | 0 | 전 키 부재 에러 메시지 env 힌트 (7) | pytest |
| R0-LLMGW-BUILD-OPENAI | 0 | `_build` openai 파라미터 계약 (8) | pytest |
| R0-LLMGW-PAE-ROLES | 0 | PAE all-roles GPT + de-hardcode 회귀 + 키부재 폴스루 (10~12) | pytest |
| R0-LLMGW-MOCK-INV | 0 | mock 불변식: FakeListChatModel + `_use_v2()==False` (13) | pytest |
| R0-LLMGW-USAGE-NORM | 0 | `_normalize_usage` OpenAI 2형상(기존 2 + 가드 1) | pytest |
| R1-LLMGW-HEALTH-CHAIN | 1 | health detail `llm_chain` 존재 + OPS-01 무회귀 | app_client 유닛 + e2e OPS-01 |
| R2-LLMGW-LIVE-SMOKE | 2 | 실키 v2 1問: tool-call→카드→Trust→done + Langfuse 태그/usage/cost | P3-1/P3-4 수동 |
| R2-LLMGW-FALLBACK-LIVE | 2 | openai 후보 강제 실패(가짜 ID) → anthropic 폴백 완결 | P3-2 로그 |
| R3-LLMGW-NOKEY-NEG | 3 | `LLM_PROVIDER=openai` + 키 부재: 서비스 지속 + 경고 1회 + `llm_chain` 에 openai 부재 | 로그 grep + curl |
| R3-LLMGW-PROD-ENV | 3 | prod 컨테이너 `printenv OPENAI_API_KEY` + health `llm_chain` (compose 누락 이중 방어) | P3-6 |

## Pass 반복

- **Pass 1 (기본)**: P1-0~P1-11 — 코드 + 유닛 전건 green (로컬 venv)
- **Pass 2 (엣지/ops)**: P2-1~P2-8 — env/compose/deploy/docs sync + 수동 diff
- **Pass 3 (live/성능)**: P3-0~P3-6 — 실키 스모크 · 폴백 증명 · Langfuse cost · PAE · prod 카나리아 (선행조건: auto-deploy 회복)

## Agent 모델 선택

- 설계: opus 급 (완료 — 본 문서, 2026-07-08 탐색 3에이전트 + Plan 에이전트)
- 구현: sonnet 급 (Pass 1~2)
- 검증: haiku 급 (pytest/ruff exit code 판정) + live smoke 는 사람 확인

## Validation

| 단계 | 명령/방법 | 기준 |
|---|---|---|
| V1 | `cd server && ruff check . && ruff format --check . && pytest -m "not real"` | 전건 green (기존 225 + 신규 ~16), 수집 에러 0 |
| V1-표적 | `pytest tests/test_loop_models_chain.py tests/test_pae_create_llm.py -v` | 신규 13건 green |
| V2-회귀 | `pytest tests/test_loop_models_config.py tests/test_loop_models_stream.py tests/test_langfuse_l2.py tests/test_engine_stream_events.py -v` | 기존 계약 green |
| V3-live | P3-1~P3-5 | v2/PAE 실동작 + 폴백 + `provider:openai` 태그 + cost 비-null |
| V4-prod | P3-6 | prod health `llm_chain` + auto_deploy smoke green + OPS-01 무회귀 |

최종 판정 = V1~V4 전부 + R3-LLMGW-NOKEY-NEG negative 통과.

## Metadata

- 카테고리: infra · 우선순위: P1 · 난이도: S~M (코드 diff ~60줄 + 테스트 ~16케이스 + env/docs)
- 변경 파일: 코드 4(`config.py`·`loop/models.py`·`graph.py`·`routes/chat.py`) + 의존성 1(`pyproject.toml`) + 테스트 3(신규 2 + conftest) + CI 1 + env/compose/deploy 4 + 문서 8
- Deferred(백로그): temperature/max_tokens env 화 · per-provider circuit breaker · openai 역할별 모델 분리 · v2 체인 순서 완전 커스텀 env · e2e OPS-01 required 에 `llm_chain` 편입 · learning 문서 sync
