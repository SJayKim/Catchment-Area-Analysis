# Plan — v2 Agentic Loop E2E 마무리 (S9-5 fix → baseline → 정리 → 문서화)

> 핸드오프 문서. `feat/agentic-loop-v2` 브랜치. 다음 컨텍스트가 이어받아 실행 가능하도록 작성.
> 작성 세션: 2026-06-28. 프로젝트 Plan 관례(`docs/plan/`) 미러는 §6 참조.

---

## Context (왜)

`feat/agentic-loop-v2`(모델주도 function-calling 루프 + Trust Kernel, PAE 대체)를 chromium full ring0~3 E2E로 검증한 결과 **130 passed / 26 failed / 8 skipped (164, 20.9m)**. 핵심 agent 테스트(f02-agent-chat H1~H4, f05-compare, preview-api, neg-prompt-injection, neg-no-district, ops-endpoints, stats-aggregate)는 전부 통과 → **v2 엔진 자체는 건강**.

26 실패 중 **v2가 유발한 것으로 분류된 건 S9-5(면책 문구) 1건뿐**, 나머지 25는 v2 무관(prod-smoke=prod전용·real-db spec을 Mock으로·Langfuse SDK 드리프트·순수 UI/perf·legacy spec 셀렉터)으로 1차 분류됨. 이 plan은 (1) 유일한 v2 finding을 고치고, (2) "25건 v2 무관" 분류를 PAE baseline으로 **실증**하고, (3~5) 세션 중 만든 임시 환경을 정리·문서화한다.

---

## 현재 환경 상태 (이미 완료된 것 — 다음 세션이 알아야 함)

- **LLM 키 교체 완료(영구, gitignore됨)**: 직전 키(`...rQAA`)는 `.env`/`.env.e2e` 동일 + **401 dead**였음. 교체 후:
  - `.env` → `ANTHROPIC_API_KEY` = **market-service** 키 (마스킹 `sk-ant-api03-z...9gAA`, live)
  - `.env.e2e` → `ANTHROPIC_API_KEY` = **market-test** 키 (마스킹 `sk-ant-api03-_...6gAA`, live)
- **compose 임시 변경**: `docker-compose.e2e.yml` backend `environment:` 에 `GEMINI_MODEL_PRO: ${GEMINI_MODEL_PRO:-gemini-2.5-flash}` 4줄 추가됨(죽은 gemini-2.5-pro 우회 fallback; pro free-tier quota=0·flash만 생존). **§4에서 되돌림 대상**.
- **e2e 스택**: `COMPOSE_PROJECT_NAME=marketscope-e2e`, `docker-compose.e2e.yml`, ports frontend 3001 / backend 8002 / db 15432 / redis 16379. USE_MOCK=true. backend는 market-test 키 + v2 loop. 세션 종료 시 내려갔을 수 있음 → 없으면 `bash scripts/e2e/preflight.sh` 로 재기동(.env.e2e 그대로 사용).
- v2 run 로그(참고): 본 세션 task 출력(휘발성). 실패 26건 목록은 §1.1.
- `.claude/settings.local.json` 의 `M` 은 **세션 이전부터의 drift**(이 작업과 무관, 건드리지 말 것).

> ⚠️ **시작 전 키 sanity**: backend 가 live 키를 들고 있는지 먼저 확인.
> `docker exec marketscope-e2e-backend-1 python -c "import os,json,urllib.request;k=os.environ['ANTHROPIC_API_KEY'];b=json.dumps({'model':'claude-sonnet-4-6','max_tokens':8,'messages':[{'role':'user','content':'hi'}]}).encode();r=urllib.request.Request('https://api.anthropic.com/v1/messages',data=b,headers={'x-api-key':k,'anthropic-version':'2023-06-01','content-type':'application/json'});print(urllib.request.urlopen(r,timeout=30).status)"` → `200` 기대.

---

## 실행 순서 & 의존성

```
[1] S9-5 fix (코드) ──┐
                      ├─▶ [2] PAE baseline (분류 실증, flash-pin 필요) ──▶ [1-verify] v2 재실행(전체) ──▶ [3] compose 되돌리기 ──▶ [4] 스택 teardown ──▶ [5] 문서화
```
- [2]는 [3]보다 **먼저** (PAE도 gemini fallback flash-pin 의존). [3] compose 되돌리기는 baseline·재실행 **끝난 뒤**.
- 키 교체(.env/.env.e2e)는 **유지**(되돌리지 않음). 사용자 요청 반영분.

---

## [1] S9-5 면책 문구 — v2 prose 프롬프트에 PAE 표준 disclaimer 상속

**근본원인**: 테스트 `frontend/e2e/phase3-scenario.spec.ts:41-47` 는 SSE 전체 텍스트에 `추정치` OR `실제와 다를` OR `실제 매출과 다를` 중 하나를 요구. `simulate_revenue.py:145` 가 `"추정치...실제 매출과 다를 수 있습니다"` disclaimer를 카드에 담으므로 **simulate 카드가 발행되면 통과**한다. v2는 "카페 매출 얼마나?"(D3001)에서 simulate 카드를 **매번 발행하진 않음**(모델주도라 때때로 clarification/prose) → 카드 미발행 시 disclaimer 부재 → fail. PAE는 rule plan 으로 simulate 를 강제 + `respond.py:240`/`system.py:18` 에 면책 문구 보유라 항상 통과.

**수정 (대상 1파일)**: `server/server/agent/loop/prompts.py:28`
- 현재: `- 마지막에 '추정 데이터 기반 참고용' 임을 한 줄로 밝히세요.`
- 변경: PAE 표준 문구를 상속 — 매출·추천·리스크 응답에 **"추정치이며 실제와 다를 수 있습니다"** 를 한 줄 면책으로 포함하도록 지시. (system.py:18 / respond.py:240 와 동일 표현 → 카드 미발행·prose-only 경우에도 `추정치`+`실제와 다를` 문자열이 본문에 실려 S9-5 통과.)
- 예시 문구: `- 매출·추천·리스크 등 분석 결과의 마지막엔 면책을 한 줄로 붙이세요: "추정치이며 실제와 다를 수 있습니다(참고용)".`

**대안(비권장)**: 테스트를 v2 문구("추정 데이터 기반")도 허용하도록 완화. → v2를 PAE 관례에 맞추는 게 더 일관적이므로 prompt-fix 채택.

**부차(별건, 이 plan 범위 밖)**: v2가 명백한 시뮬레이션 의도에서 `simulate_revenue` 를 더 안정적으로 호출하도록 프롬프트 튜닝(카드 발행률↑) — S9-1/S9-6 안정성과도 연결. 본 plan은 disclaimer 상속까지만.

**검증**:
- ruff: `cd server && ruff check server/agent/loop/prompts.py`
- 단발 probe(빠름): backend 재빌드/재기동 불필요 — `prompts.py` 는 bind-mount 아니면 **이미지 재빌드 필요**. e2e backend 는 이미지 빌드본이므로 `docker compose -f docker-compose.e2e.yml build backend && docker compose -f docker-compose.e2e.yml up -d --force-recreate --no-deps backend` 후:
  `curl`/python SSE probe 로 `{"message":"카페 매출 얼마나?","district_code":"D3001"}` → 응답에 `추정치` 또는 `실제와 다를` 포함 확인. (probe 패턴: 본 세션 `scratchpad/v2_probe.py` 와 동일 — 새 세션은 동등 스크립트 재작성; SSE 는 `data: {json}` 임베드, 표준 파서 금지.)
- 최종은 [1-verify] 전체 재실행에서 S9-5 PASS 확인.

---

## [2] PAE baseline — "25건 v2 무관" 실증

**목적**: v2 run 에서 실패한 26건을 **동일 스택에서 PAE 로만 바꿔** 재실행 → 양쪽 다 실패=사전결함 확정, v2만 실패=회귀. v2는 서버측 agent 만 바꾸므로 비-agent 실패(아래 대부분)는 PAE 에서도 동일 실패할 것.

**방법(브랜치 전환 없이 loop 버전만 토글 — 가장 깨끗한 격리)**:
- `runtime.py::_use_v2()` = `agent_loop_version=="v2" and llm_provider!="mock"`. config 필드 `agent_loop_version`(`config.py`) ← env `AGENT_LOOP_VERSION`(pydantic 기본 매핑, env_prefix 없음).
- compose backend `environment:` 에 한 줄 임시 추가: `AGENT_LOOP_VERSION: ${AGENT_LOOP_VERSION:-v2}` (GEMINI_MODEL_PRO 패턴과 동일).
- PAE 로 재기동: `export COMPOSE_PROJECT_NAME=marketscope-e2e AGENT_LOOP_VERSION=pae; docker compose -f docker-compose.e2e.yml up -d --force-recreate --no-deps backend` → health 대기 → `docker exec ... printenv AGENT_LOOP_VERSION` = `pae` 확인. (PAE 는 anthropic live 키 + flash-pin fallback 으로 동작.)
- **실패 26건이 속한 10개 spec 파일만** PAE 로 실행(전체 164 불필요):
  `cd frontend && E2E_BASE_URL=http://localhost:3001 E2E_BACKEND_URL=http://localhost:8002 npx playwright test --project=chromium phase3-scenario prod-smoke d-perf f01-preview-real-db f01-rapid-switch f11-landing phase-b-ux-sweep phase-c-ux-sweep j06-ux-a2f-integration l1-langfuse`
- 복원: `AGENT_LOOP_VERSION=v2` 로(또는 unset 후 default v2) backend 재기동.

**판정 기준 & 사전 분류(§1.1)**:
| spec | 실패수 | 1차 분류 | PAE 예상 |
|---|---:|---|---|
| prod-smoke P4/P5/P8/P9 | 4 | prod/Real 전용 spec ↔ local Mock | 동일 실패(무관 확정) |
| f01-preview-real-db | 3 | "real DB" spec ↔ Mock | 동일 실패 |
| f01-rapid-switch | 2 | `district-preview`(zero-LLM REST) | 동일 실패 |
| phase-c-ux-sweep | 5 | TimeSlider/opacity/CTA UI·perf | 동일 실패 |
| heatmap UI S6-1/S6-5 | 2 | `button[title]` 셀렉터 | 동일 실패 |
| j06 J02/J04 | 2 | 멀티스텝 UX 집계(passCount) | 동일/유사 |
| l1-langfuse E02/E03 | 2 | Langfuse SDK 버전 드리프트 | 동일 실패 |
| phase3 S9-1/S10-1 | 2 | legacy chat-input 셀렉터 fill timeout | 동일 실패(or 양쪽 flaky) |
| d-perf D7 / f11 배너 / phase-b B1 | 3 | brittle regex(미변경 파일)/localStorage/재클릭 UI | 동일 실패 |
| **phase3 S9-5** | 1 | **v2 회귀** | **PAE PASS** (← 회귀 입증) |
- 기대 결과: **S9-5만 PAE에서 PASS**(= v2-유일 회귀 확정), 나머지 25는 PAE에서도 FAIL(= 사전결함 확정).
- 예상 밖(PAE에서도 PASS 인데 v2 FAIL)인 spec 발견 시 → 추가 v2 회귀로 분류·조사(별건).

---

## [1-verify] S9-5 fix 후 v2 전체 재실행

- backend 를 **v2 로 복원**(AGENT_LOOP_VERSION=v2 / unset) + S9-5 fix 반영 이미지로 재기동.
- 전체 재실행: `cd frontend && E2E_BASE_URL=http://localhost:3001 E2E_BACKEND_URL=http://localhost:8002 npx playwright test --project=chromium --reporter=line`
- **성공 기준**: S9-5 PASS. 전체는 **≥131 passed** 기대(S9-5 회복; 나머지 25 사전결함은 그대로 red). v2-유발 신규 실패 0.
- (선택) S9-1/S9-6/S10-1 안정성은 nondeterministic — flaky 면 §1 부차 항목으로 별도 트래킹.

---

## [3] compose flash-pin 되돌리기

- baseline([2]) + 재실행([1-verify]) 완료 후 수행(그 전엔 fallback 으로 필요).
- `git checkout docker-compose.e2e.yml` (GEMINI_MODEL_PRO + [2]에서 추가한 AGENT_LOOP_VERSION 라인 모두 제거). 
- 대안: gemini 유료 tier 전환 예정이면 flash-pin 유지도 무방 — 그 경우 라인 보존 + 주석만 정리.
- 확인: `git diff docker-compose.e2e.yml` → 변경 없음(또는 의도한 주석만).

---

## [4] e2e 스택 teardown

- 모든 실행 종료 후: `export COMPOSE_PROJECT_NAME=marketscope-e2e; docker compose -f docker-compose.e2e.yml down` (volume `marketscope-e2e_pgdata` 는 보존 — `down -v` 금지, 재시드 비용).
- 운영/개발 compose(`marketscope`, `marketscope-prod`)와 포트·프로젝트명 격리되어 있으므로 안전.
- 확인: `docker ps | grep e2e` → 없음.

---

## [5] status 문서 갱신

- `/status-update "<요약>"` 스킬 사용(오늘 날짜 섹션 추가, 이모지/구조 관례 보존; 400줄 초과 시 status-compress 선행).
- 기록 내용: `feat/agentic-loop-v2` E2E 검증(130/164 → S9-5 fix 후 131), v2-유일 회귀 S9-5(면책 문구 상속) + PAE baseline 으로 25 사전결함 실증, e2e LLM 키 교체(.env=market-service/.env.e2e=market-test, 직전 401 dead), gemini free-tier pro quota=0(flash-pin). 메모리 `project_v2_loop_e2e.md` 와 교차 링크.
- (선택) 본 plan 을 프로젝트 관례 위치 `docs/plan/qa/v2-loop-e2e-verification-2026-06-28.md` 로 미러(§6).

---

## §6 프로젝트 Plan 관례 메모

CLAUDE.md 는 plan 을 `docs/plan/<category>/` 에 5섹션(Checklist/재검토/Scenario/Pass반복/Agent모델)으로 둘 것을 권장(`/plan-new qa <name>`). 본 핸드오프는 plan-mode 파일이 1차 산출물이며, 실행 착수 시 `docs/plan/qa/` 또는 `docs/plan/fix/` 로 옮겨 관례 정렬 권장. 관련 메모리: `memory/project_v2_loop_e2e.md`, `feedback_stale_container_vs_source`(이미지 재빌드 필수), `feedback_sse_buffering`(SSE `data:` 임베드).

## Agent 모델 선택(관례)
- [1] 구현(prompt 1줄) — sonnet. [2]/[1-verify] 실행·판정 — sonnet(또는 qa-scenario-runner subagent 로 대량 출력 격리). [5] 문서 — haiku/sonnet.

## 검증 종합 (이 plan 전체의 done 기준)
1. `ruff check` PASS (`server/agent/loop/prompts.py`).
2. v2 전체 재실행에서 **S9-5 PASS**, v2-유발 신규 실패 0 (≥131 passed).
3. PAE baseline 에서 S9-5 외 25건 동일 FAIL(사전결함 실증), S9-5 는 PAE PASS.
4. `git diff docker-compose.e2e.yml` 클린(또는 의도 주석만), `.env`/`.env.e2e` 키 유지(gitignore).
5. status 문서에 오늘자 섹션 추가, 스택 teardown 완료.
