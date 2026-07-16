# Pass 3 Live 활성화 — 통합 오케스트레이션 Plan (블로커 해소 + LLM Gateway live)

> 작성: 2026-07-16 · category: infra · 성격: **오케스트레이션 전용**(순서·의존성·실행 주체·검증만 정의, 원자적 체크리스트는 3개 기존 plan 인용 — 중복 서술 금지)

## Context

current-status.md 미결 3건 + Next Item 최상단(LLM Gateway Pass 3 live)을 **하나의 실행 순서**로 묶는다. 각 작업의 세부 체크리스트는 이미 아래 3개 plan 에 정의돼 있으므로, 본 문서는 **Stage A→D 순서·의존성·실행 주체(서버=사용자 수동)·종료 검증**만 정의하고 세부는 인용한다.

미결/잔여 (2026-07-09 current-status 기준):

1. **auto-deploy 미발화** — push·CI 5/5 green 완료됐으나 CI green 후 prod 미반영(07-06/07-07 동일 증상 = 배포 시도 자체 없음). prod 는 07-04 배포본에 머묾. 별건: prod `redis_connected=false` 지속 관측.
2. **`.env`/`.env.dev` 수동 diff 미적용** — `LANGFUSE_TRACING_ENVIRONMENT` / `SESSION_SALT` / OTEL 주석 (protect_secrets 훅이 Edit 차단 → 사용자 수동).
3. **auto-deploy Pass 3** — 2분 폴링 24h 관찰(no-op 부하·API rate·회귀 0).
4. **LLM Gateway Pass 3 (live)** — 실키 스모크·폴백 증명·Langfuse `provider:openai` cost·PAE 경로·prod 카나리아. **선행조건 = ① + ②**.

**의존성 사슬**: `A(서버 블로커 해소) → B(env 수동 적용) → C(로컬 live 검증) → D(prod 카나리아 + 24h 관찰)`. Pass 3(live)는 auto-deploy 발화 회복(A) + 실키 env 적용(B) 이후에만 착수 가능.

**실행 주체**: 서버 명령은 전부 **사용자가 프로덕션 서버에서 직접 실행**(리포에 로컬→서버 SSH 자동화 없음). Claude 는 복붙용 명령 블록을 제공하고 출력을 공유받아 해석한다. env 편집은 protect_secrets 훅 차단으로 **전부 사용자 수동** — Claude 는 diff 블록만 제시.

**인용 plan** (동일 디렉토리):
- [llm-gateway-openai-2026-07-08.md](llm-gateway-openai-2026-07-08.md) — Pass 3 체크리스트 P3-0~P3-6 (:162-171), 수동 적용 diff (:172-185), Scenario (:205-219)
- [auto-deploy-on-push.md](auto-deploy-on-push.md) — Validation/진단 명령 (:132-137) + no-op 판정 로직 (:44-52), Pass 3 24h 관찰 (:118-123)
- [langfuse-ops-hardening-2026-07-06.md](langfuse-ops-hardening-2026-07-06.md) — §수동 적용 diff (:53-68), `R1-LF-V2SMOKE` (:88)

> ⚠ auto-deploy 진단 명령은 melodic 초안이 `:9-11` 로 인용했으나 해당 범위는 폴링 방식 결정문이다. 실제 진단 명령은 current-status 미결 #1 + auto-deploy Validation(:132-137) — 본 문서는 정확 앵커로 교정(문서 rot 방지, `feedback_verify_cited_path_before_read`).

**Memory 참조** (파일명만 — 중복 저장 금지):
- `feedback_protect_secrets_hook_env_edit_block` — env 는 사용자 수동 편집, Bash 우회 금지 → **Stage B 전건**
- `feedback_env_convention_inverted` — `.env`=prod / `.env.dev`=로컬 → B1/B2 파일 결정 근거
- `feedback_deploy_detection_landing_blind` — 배포 반영은 backend health(SSE/`langfuse` 블록)로 판별, 랜딩 fingerprint 금지 → **A5**
- `feedback_prod_https_nonascii_body_mangled` — prod 카나리아 = Git Bash curl + `ensure_ascii` JSON (PS curl.exe·requests SSL fail) → **D2**
- `feedback_qa_browse_unstable_use_sse` — chat 검증은 `/api/chat` curl SSE 직접(browse 헤드리스 크래시) → **C1/C5**
- `feedback_langfuse_cli_stderr_json_pipe` — langfuse-cli JSON 파싱은 `2>/dev/null` 필수(`.env`=prod·`.env.dev`=dev 프로젝트) → **C4**

## Checklist

### Stage A — 서버 블로커 진단/해소 [서버 · 사용자 실행]

- [ ] **A1** timer 상태: `systemctl status marketscope-autodeploy.timer` → `active (waiting)` 여부 확인. `disabled/dead` 면 미발화 근본원인(수동 세션 전 disable 관례 미복구 가능성). *검증: Active 라인 + NextElapse*
- [ ] **A2** 서비스 로그: `journalctl -u marketscope-autodeploy.service -n 100 --no-pager` → `BLOCKED_DIRTY` / `BLOCKED_CI` / `BLOCKED_AHEAD` / freshness 판정 중 무엇인지. 로그 자체가 없으면 = timer 미발화(A1 로 회귀). *검증: 최근 tick 결과 문자열*
- [ ] **A3** 상태파일: `cat data/deploy-logs/last-deploy.json` + `cat data/deploy-logs/blocked-shas.txt` + 서버 `git status --short`. no-op 기준은 HEAD 아닌 `.last-deployed-sha`(auto-deploy :44-52) — 서버발 커밋이면 워킹트리 dirty 로 BLOCKED 가능. *검증: last SHA vs origin/main tip*
- [ ] **A4** 원인별 해소 → 강제 배포:
  - dirty → 허용목록(`.claude/settings.local.json`) 외 tracked 변경 커밋/스태시
  - blocked SHA → `blocked-shas.txt` 에서 해당 SHA 제거
  - timer disabled → `systemctl enable --now marketscope-autodeploy.timer`
  - 이후 `bash scripts/deploy/auto_deploy.sh --force`
  - *검증: `last-deploy.json` `result=SUCCESS` + 이미지 Created ≥ deploy start (stale-image 마커)*
- [ ] **A5** 배포 반영 검증(랜딩 fingerprint 금지, backend health 로만): `curl https://marketscope.robitlabs.co.kr/api/health/detail` → `langfuse` 블록 등장(07-06 ops-hardening 코드 증거) + `agent_mode`/`llm_provider` 최신값. *검증: `langfuse` 4키 블록 present*
- [ ] **A6** Redis 별건: `docker ps`(redis 상태) + `docker logs <redis> --tail 50` + `docker exec <redis> redis-cli ping` → 조치 후 health `redis_connected=true`. *검증: PONG + health redis_connected=true*

### Stage B — env 수동 diff [사용자 수동 편집 · protect_secrets 훅 차단]

> Claude 는 아래 블록 제시만. 사용자가 서버 `.env` / 로컬 `.env.dev` 를 직접 편집한다.

- [ ] **B1** `.env` (prod 프로파일) — ops-hardening(:56-63) + llm-gateway(:175-177) 병합. `LANGFUSE_OTEL_INSECURE` 는 prod 서버 복사 금지:

```dotenv
# --- Langfuse (ops-hardening §수동 diff) ---
LANGFUSE_TRACING_ENVIRONMENT=production
# 세션 해시 salt — 고정값이어야 재시작 후에도 같은 세션이 같은 해시로 묶임
LANGFUSE_SESSION_SALT=b229b91fc5d3575e4488c272eb9ed09a
# ⚠ LANGFUSE_OTEL_INSECURE=true 는 프로덕션 서버로 복사 금지 (TLS 검증이 꺼진 채 운영됨)

# --- OpenAI (llm-gateway 롤아웃 1단계 = 카나리아: 키만 → openai 2순위 폴백) ---
OPENAI_API_KEY=sk-proj-...(실키)
# 모델 핫픽스 필요 시: OPENAI_MODEL=gpt-5.4-mini (또는 후속 GPT-5.x ID)
# 롤아웃 2단계(승격, 별도 결정): LLM_PROVIDER=anthropic → openai
```

- [ ] **B2** `.env.dev` (로컬) — ops-hardening(:66-67) + llm-gateway(:184):

```dotenv
LANGFUSE_TRACING_ENVIRONMENT=development
LANGFUSE_SESSION_SALT=f967fecff0191c5d935e23642c47d131
OPENAI_API_KEY=sk-proj-...(dev키)
```

- [ ] **B3** 검증: 로컬에서 `settings.openai_api_key` 비어있지 않음 (Python313 절대경로 1줄 — `feedback_shell_python_wrong_venv`). *검증: `python -c "from server.config import settings; print(bool(settings.openai_api_key))"` → True*

### Stage C — LLM Gateway Pass 3 로컬 (P3-1~P3-5) [로컬 · Claude 실행 가능]

> 인용: llm-gateway P3-1~P3-5 (:165-169). prod 운영값 무변경 — 로컬 `.env.dev` 만 임시 조작.

- [ ] **C1** (P3-1) `.env.dev` 에 `LLM_PROVIDER=openai` 임시 + backend venv 기동 → `/api/chat` 1問 **curl SSE 직접**(browse 금지) → `tool`/`card`/`text`/`done` + Trust 통과. TTFT 실측 — 60s 근접 시 `LLM_TIMEOUT_SLOW` 상향(무코드 env). *검증: SSE 이벤트 순서 + 컨테이너 로그 openai 성공*
- [ ] **C2** (P3-2) `OPENAI_MODEL=존재하지-않는-ID` 1問 → warning 후 **anthropic 폴백 완결**. *검증: 로그 폴백 흔적 + 응답 정상*
- [ ] **C3** (P3-3) `curl :8000/api/health/detail` → `llm_chain` 선두 `openai:gpt-5.4-mini`. *검증: 라벨 순서*
- [ ] **C4** (P3-4) Langfuse trace: `provider:openai` 태그 + usage>0 + **cost 비-null**(null 시 runbook :280-285 수동 등록 후 재확인). langfuse-cli JSON 은 `2>/dev/null`. **ops-hardening Pass 3 `R1-LF-V2SMOKE` 와 합승 — 중복 실행 금지**(이 Plan 이 실행 주체, 양쪽 체크박스 동시 갱신). *검증: Langfuse Cloud dev 프로젝트 trace*
- [ ] **C5** (P3-5) PAE 경로: `AGENT_LOOP_VERSION=pae` + `LLM_PROVIDER=openai` 1問 + 후속질문 1건(rewriter 경로). *검증: 완결 + 로그에 anthropic/gemini 호출 부재*
- [ ] **C6** 로컬 env 원복: `LLM_PROVIDER=anthropic` (+ C2 의 가짜 `OPENAI_MODEL` 제거). *검증: `.env.dev` diff = OPENAI_API_KEY/SALT 만 잔존*

### Stage D — prod 카나리아 + 관찰 [서버 · 사용자 실행]

- [ ] **D1** (P3-6) B1 적용 + backend 재기동(A4 auto_deploy 또는 수동) → prod health `llm_chain` 에 `openai:` 라벨 **2순위** 포함(`LLM_PROVIDER=anthropic` 유지 = 카나리아 1단계, 키만). *검증: prod `/api/health/detail` llm_chain*
- [ ] **D2** prod 카나리아 1問 — **Git Bash curl + `ensure_ascii` JSON**(PS curl.exe exit 35 · requests SSL fail). GET 도 revocation 에러 시 `-k --ssl-no-revoke`. *검증: SSE 정상 완결 + Trust 통과*
- [ ] **D3** (auto-deploy Pass 3) 24h 관찰: no-op tick 2s 내 종료·로그 무증가 · GitHub API rate(무인증 60req/h, 30/h 사용) 여유 · `prod-smoke` 재실행 회귀 0. *검증: `npx playwright test prod-smoke --project=chromium` green*
- [ ] **D4** `/status-update "Pass 3 live 활성화 완료"` → current-status 미결 3건 해소 반영 + 기존 3개 plan(llm-gateway P3-*, auto-deploy Pass 3, ops-hardening Pass 3) 체크박스 갱신. *검증: current-status 미결 섹션에서 3건 제거*

## 재검토 (Self-Review Gate)

- [ ] **env 편집 훅 차단** — protect_secrets PreToolUse 가 `.env`/`.env.dev` Edit 을 exit 2 차단. Stage B 전 항목 사용자 수동, Claude 는 diff 블록 제시만 (Bash `echo >>` 우회도 훅 정책 위반 — 금지).
- [ ] **타 Plan 합승 (중복 실행 방지)** — C4(P3-4)는 ops-hardening Pass 3 `R1-LF-V2SMOKE` live smoke 와 동일 trace 를 검증한다. 한 번만 실행하고 양쪽 체크박스 동시 갱신 — 이 Plan 이 실행 주체.
- [ ] **gpt-5.4-mini temperature 생략 분기** — models.py `_build` 의 openai 분기는 `temperature` 를 생략한다(GPT-5.x reasoning 이 비-기본값 400 거부). C1 스모크에서 400 에러가 나오면 이 분기 회귀를 우선 의심.
- [ ] **A6 redis 분기** — 컨테이너가 healthy 인데 `redis_connected=false` 면 앱↔redis 네트워크/컨테이너명 분기 문제 → 별도 진단(compose service name·REDIS_URL 호스트 대조).
- [ ] **docs push CI** — 본 문서 push 시 CI 5잡 재실행되나 docs-only 라 green 유지 예상. auto-deploy freshness 마커는 server/·frontend/ diff 없는 push 를 stale 오판정하지 않음(auto-deploy :107).
- [ ] **선행조건 게이트** — Stage C/D 는 A(발화 회복) + B(실키 적용) 완료가 전제. A 미회복 시 D 착수 금지(llm-gateway P3-0), C 는 B 없이는 실키 부재로 무의미.
- [ ] **prod 운영값 무변경 원칙** — 카나리아 1단계는 "키만"(`LLM_PROVIDER=anthropic` 유지). GPT 1순위 승격(2단계)은 D 이후 별도 결정.

## Scenario (E2E Ring Mapping)

**기존 재사용** (실행 주체만 본 Plan 으로 이관 — 시나리오 정의는 원 plan):

| ID | Ring | 출처 | 매핑 |
|---|---|---|---|
| `R2-LLMGW-LIVE-SMOKE` | 2 | llm-gateway :215 | C1 + C4 |
| `R2-LLMGW-FALLBACK-LIVE` | 2 | llm-gateway :216 | C2 |
| `R3-LLMGW-NOKEY-NEG` | 3 | llm-gateway :217 | (negative — 키 부재 서비스 지속) |
| `R3-LLMGW-PROD-ENV` | 3 | llm-gateway :218 | D1 |
| `R1-LF-V2SMOKE` | 1 | ops-hardening :88 | C4 합승 |

**신규** (본 오케스트레이션 고유):

| ID | Ring | 내용 | 검증 |
|---|---|---|---|
| `R0-DEPLOY-FORCE-FIRE` | 0 | A4 — `--force` 후 `last-deploy.json` SUCCESS + health 반영 | last-deploy.json + curl health |
| `R0-REDIS-RECONNECT` | 0 | A6 — redis 재연결 후 `redis_connected=true` | redis-cli ping + health |

## Pass 반복

- **Pass 1 (기본)**: Stage A + B — 서버 블로커 해소 + env 실키 적용. 게이트 = `last-deploy.json` SUCCESS + `settings.openai_api_key` 비어있지 않음.
- **Pass 2 (엣지)**: Stage C — 로컬 스모크(C1) / 폴백 증명(C2) / health(C3) / Langfuse cost(C4) / PAE(C5). 게이트 = C1~C5 전건 + env 원복(C6).
- **Pass 3 (성능/회귀)**: Stage D — prod 카나리아(D1/D2) + auto-deploy 24h 관찰(D3) + status/plan 갱신(D4). 게이트 = prod health `llm_chain` openai 포함 + prod-smoke 회귀 0.

## Agent 모델 선택

- **설계**: opus (완료 — melodic 초안 + 본 오케스트레이션 문서)
- **구현/실행**: sonnet (Stage A~D 명령 실행 · diff 제시 · 로그 해석)
- **검증**: haiku (last-deploy.json/health/SSE exit 판정) + live smoke 는 사람 확인(서버 명령·Langfuse UI)

## Validation

| 종료 조건 | 확인 방법 |
|---|---|
| auto-deploy 발화 회복 | `cat data/deploy-logs/last-deploy.json` → `result=SUCCESS` |
| prod 배포 반영 | prod `/api/health/detail` 에 `langfuse` 블록 present |
| Redis 정상 | prod health `redis_connected=true` |
| env 실키 적용 | 로컬 `settings.openai_api_key` truthy |
| LLM Gateway live | prod health `llm_chain` 에 `openai:` 라벨 포함 |
| Langfuse cost | dev 프로젝트 trace `provider:openai` 태그 + cost 비-null |
| 미결 정리 | current-status 미결 3건 제거 (D4) |

최종 판정 = 위 7행 전부 + 신규 시나리오 2건(`R0-DEPLOY-FORCE-FIRE` / `R0-REDIS-RECONNECT`) PASS.

## Metadata

- 작성일: 2026-07-16 · 카테고리: infra · 우선순위: P1 (Next Item 최상단) · 성격: 오케스트레이션(코드 변경 0)
- 관련 Plan: [llm-gateway-openai-2026-07-08.md](llm-gateway-openai-2026-07-08.md) · [auto-deploy-on-push.md](auto-deploy-on-push.md) · [langfuse-ops-hardening-2026-07-06.md](langfuse-ops-hardening-2026-07-06.md)
- 실행 주체: 서버 명령·env = 사용자 수동 / 로컬 Stage C = Claude 가능
- Deferred: GPT 1순위 승격(카나리아 2단계) — Stage D 이후 별도 결정
