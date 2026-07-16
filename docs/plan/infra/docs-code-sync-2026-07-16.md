# Docs–코드 동기화 + Learning 문서 전면 개정 (2026-07-16)

> **목표**: 07-05 이후 코드 구현 4건 — 스트리밍 옵션 B(`c44d0b6`, 07-06) · Langfuse ops-hardening(`d63a371`, 07-07) · e2e E02/E03 v3 재작성(`c98ea5d`, 07-07) · LLM Gateway openai(`9183f59`+`391ab58`, 07-08) — 의 문서 드리프트를 전수 해소하고, **learning 문서를 전면 리라이트 수준으로 개정 + 07-관측(Langfuse) 학습 문서를 신설**한다.

## 1. Context

- 4개 Explore 에이전트 전수 감사 + 직접 실측으로 드리프트 확정 (아래 §3.0 실측값 표 — 문서에 박을 근거, 재도출 불필요).
- 오늘(07-16) 다른 세션이 `current-status.md` + `plan/infra/pass3-live-activation-2026-07-16.md` 를 갱신 → **미결/Next Items 블록과 pass3 plan 파일은 불변경**. status 는 지표 1줄 교정 + 이력 row 추가만.
- 사용자 결정: learning 문서는 컨설팅 회사 비유 세계관·팔레트를 보존한 채 심혈을 기울여 개정.

### Memory 교훈 인용
- **`feedback_read_large_doc_chunking`** — status/plan/learning 대형 문서는 첫 Read 부터 limit 청크.
- **`feedback_verify_cited_path_before_read`** — 인용 경로는 Read 전 Glob 실존 확인 (전 경로 검증 완료).
- **`feedback_edit_needs_read_even_if_reminder_injected`** — 주입된 파일도 Read→Edit 순서.
- **`feedback_protect_secrets_hook_env_edit_block`** — `.env`/`.env.dev` 편집 차단 → env 반영은 `.env.example` 주석만.
- **`feedback_ps51_git_commit_msg_quotes_split`** — 한국어 커밋 메시지는 UTF-8(no BOM) 파일 + `git commit -F`.

## 2. Scope

**In**: `docs/architecture/`(agent·backend·frontend·overview·deployment·tech-stack-rationale) · `docs/spec/`(F02·D01) · `docs/ops/`(production-deployment·runbook) · `docs/qa/`(README·test-plan) · `server/CLAUDE.md` · `.env.example` · `docs/learning/` 전체(8개 개정 + 07 신설) · 완료 plan 2건 삭제 · status 지표 교정.

**Out (무접촉)**: 코드(`server/`·`frontend/` 소스) · `current-status.md` 미결/Next Items 블록 · `pass3-live-activation-2026-07-16.md` · `.env`/`.env.dev` 실파일 · `v2-stream-final-option-b-2026-07-06.md`(V7 미결 §1 계류로 삭제 보류).

## 3. Design

### 3.0 감사 확정 실측값 (문서 서술의 유일 근거)

| 항목 | 실측값 | 근거 |
|---|---|---|
| 진행 이벤트 방출 형태 | **신규 SSE 타입 아님** — `{"type":"thinking","step":"응답 작성 중... {pct}%"}` 재사용 → "v2 7종" 유지 | engine.py:206-231 |
| 옵션 B 메커니즘 | `agent_loop_stream_final=true`(env `AGENT_LOOP_STREAM_FINAL`, 롤백 스위치)일 때 모델 턴을 `astream_with_fallback` 으로 수신·버퍼링, 본문은 Trust 검증 후 일괄 방출. pct = min(99, chars×100÷expected), `best_pct` 단조, tool_call 청크 등장 시 억제 | engine.py:206-233, `models.py::astream_with_fallback` |
| 옵션 B config 4종 | `agent_loop_stream_final: bool=true` / `agent_loop_progress_min_chars=120` / `agent_loop_progress_interval_chars=80` / `agent_loop_expected_answer_chars=2400` | config.py:93-96 |
| 프론트 처리 | `thinking` 케이스: 첫 이벤트→`thinking` step, 이후→`response` step 생성 후 라벨 실시간 갱신(`updateAgentStepStatus`) | `frontend/src/lib/eventHandlers.ts:64-81` |
| e2e 카운트 | spec 44파일 · test 선언 **188개** = ring0 4·18 / ring1 25·99 / ring2 6·13 / ring3 7·35 (소계 42·165) + prod-smoke 1·11(active 9+skip 2) + 레거시 phase3-scenario 1·12. 산정: `test(`/`test.skip(`/`test.fixme(` 선언 수 | 직접 실측 |
| l1-langfuse.spec.ts | 선언 11 = test 7 + test.skip 4 (status "7/7 green" 정합) | 직접 실측 |
| 서버 테스트 모듈 | **30개** · 수집 247 (신규: `test_loop_models_chain.py`(9) · `test_pae_create_llm.py`(4)) | ls + `pytest --collect-only` 실측 |
| prod compose passthrough | `AGENT_LOOP_STREAM_FINAL` 등 옵션 B 4종 **미정의** — prod 롤백은 compose environment 블록 추가 선행 | docker-compose.prod.yml:86-112 실측 |
| worker 4,724,265 | resident_population worker 인구 **합계**(행수 아님) — corrected seed 무결성 마커 | eval-round4 `_verdict.md` |
| auto_deploy 현행 3건 | `.last-deployed-sha` no-op 판정 · image freshness 마커(server/·frontend/ 변경 push 한정) · frontend cold-start 대기(:3200, 롤백 경로 포함) | auto_deploy.sh:29,84-85,217-228,268-283 |

에이전트 검증 OK(변경 불필요): data.md 전체 · agent.md §1/§3/§4체인/§5/§7/§8/§9 · backend.md 라우트/health/metrics · frontend CLAUDE.md · 루트 CLAUDE.md · feature-list · database-setup · disaster-recovery · serving-stability · quickstart · apps-in-toss plan.

### 3.1 Part 1 — 아키텍처/spec/ops/qa/CLAUDE/env sync (14항목)

| # | 파일 | 작업 |
|---|---|---|
| 1 | architecture/agent.md | §2 "최종 응답 스트리밍 — 옵션 B" subsection + config 4종 표 · 다이어그램 `ainvoke/astream_with_fallback` · §4 astream 1줄 · §6 thinking 현행화 |
| 2 | architecture/backend.md | 테스트 모듈 30·수집 247·신규 모듈 2 · e2e 44·188 breakdown+산정법 |
| 3 | architecture/frontend.md | §5 thinking 행 확장(response step 라벨 실시간 갱신) · §10 e2e 카운트 |
| 4 | architecture/overview.md | §4 v2 bullet 옵션 B 반문장 · §7 e2e 카운트 |
| 5 | architecture/deployment.md | env 표 `AGENT_LOOP_STREAM_FINAL`+progress 3종 행 (prod passthrough 부재 명시) |
| 6 | architecture/tech-stack-rationale.md | 체인 언급 2곳(:68·:156) openai 반영 |
| 7 | spec/features/F02 | §5 옵션 B 1줄 (체인 :17·:95 는 이미 openai 포함 — 무변경) |
| 8 | spec/data/D01 | 적재 현황에 worker 합계 4,724,265 (마커 의미 병기) |
| 9 | ops/production-deployment.md | 파이프라인 블록에 현행 로직 3건 + v2 롤백 스위치 note |
| 10 | ops/runbook.md | Scenario 3 뒤 rollback switches 1줄 |
| 11 | qa/README.md | Ring 인벤토리 실측 + runs/ 목록 + `npm run test:e2e` 교정 (전면 현행화) |
| 12 | qa/test-plan.md | :5 · :72 카운트 188 + l1-langfuse E02/E03 v3 주석 |
| 13 | server/CLAUDE.md | 테스트 모듈 28→30 |
| 14 | .env.example | 옵션 B 플래그 4종 주석 (protect_secrets 허용 파일) |

### 3.2 Part 2 — Learning 전면 개정 + 07-관측 신설 (핵심 워크스트림)

**집필은 메인 세션 직접** (서브에이전트 위임 금지 — 어조·비유 일관성). 문서당 사이클: 전체 Read → 개정 아웃라인 → 리라이트/패치 → 사실 grep 검증.

**스타일 가드**: ① 컨설팅 회사 비유 체계 유지(접수창구=백엔드 · 수석컨설턴트=LLM · 팩트체크 데스크=Trust Kernel · 자료실=데이터 · 전문계측기=도구) ② 00 의 mermaid `classDef` 6색 정본 그대로 복사(변형 금지), sequenceDiagram 은 `box rgb(...)` ③ 코드 인용 `file:line`+함수명 병기 ④ "왜 필요한가 → 비유 → 실제 코드" 서사 + prev/next·목차 링크 정합 ⑤ 모든 수치·이름은 §3.0 실측값 표에서만.

| 문서 | 핵심 작업 |
|---|---|
| 00-시작하기 | 목차에 07-관측 추가, 코스 흐름 문장 갱신 |
| 01-큰그림 | sequenceDiagram 에 옵션 B 진행 이벤트 비트(주방 "요리 진행률" 안내방송 비유), 여정 서사에 "팩트체크 후 일괄 방출" 연결 |
| 02-프론트엔드 | thinking 케이스 서술 확장 — 'response' step 라벨 실시간 갱신 = "응답 작성 중 n%"의 정체(진행 안내판 비유) |
| 03-백엔드 | `conversation_history` ↔ 04 "최근 6턴" 연결 문장 |
| 04-AI에이전트 (최심층) | ① LLM 체인 4후보 교정(openai `gpt-5.4-mini`) + `LLM_PROVIDER` 승격 ② "옵션 B" 섹션 신설(팩트체크 끝난 원고만 배포 + 집필 진행률 실시간 공지 비유) ③ 07-관측 다리 문단 |
| 05-도구12종 | 메타 3종 실행 지점(`tools_fc.py::execute_fc_tool`) 링크 1줄 + 재검토 패스 |
| 06-데이터레이어 | 신뢰도 플래그 극성 오표기 fix(원문 확인 후) + 재검토 패스 |
| ARCHITECTURE-MAP | §6 "v2 스트리밍 옵션 B" 행 · §5-2 stale 라인번호→함수명 · 프론트 SSE 진행 이벤트 · 07-관측 참조 · 실측 날짜 2026-07-16 |
| **07-관측-품질기록실.md (신설)** | 비유: 모든 상담이 품질기록실에 기록·성적표. ① 무음사망 사고 교훈 서사 ② trace/observation/score 3개념 ③ v2 기록 — summary 19키·tool span·score 6종 ④ 샘플링 단일 게이트 + graceful degrade ⑤ 무음사망 가시화(health `langfuse`·`/metrics`) ⑥ F12 FeedbackRow→score proxy ⑦ 기술 참조(agent.md §9·runbook). mermaid 1~2개(팔레트 준수), 150~250줄 |

### 3.3 Part 3 — 삭제/정리 (게이트 통과 시에만)

- 삭제 후보: `plan/infra/docs-diet-cleanup-2026-07-07.md` · `plan/fix/trust-fallback-redaction-2026-07-03.md` (완료 plan → git history 관례, `56925b9` 선례). **게이트 3종**: ① 파일 내 미완 체크박스/잔여 Pass 실질 완료 확인 ② `grep -r` 인바운드 참조 0건(특히 pass3-live-activation 라인 앵커) ③ 잔여 항목 status Next Items 이관 확인.
- `v2-stream-final-option-b-2026-07-06.md`: **삭제 보류** — V7(prod 반영 확인)이 미결 §1 계류.
- status: 지표 라인 e2e 188 표기 교정 + `/status-update` 이력 row.

## 4. 실행 (Checklist · 재검토 · Scenario · Pass · Agent)

### Checklist
**Pass 1 — docs sync (§3.1)**
- [x] P1-1~6 architecture 6건 (agent/backend/frontend/overview/deployment/tech-stack)
- [x] P1-7~8 spec 2건 (F02/D01)
- [x] P1-9~12 ops·qa 4건 (production-deployment/runbook/qa README/test-plan)
- [x] P1-13~14 server CLAUDE + .env.example
- [x] 본 plan 을 repo 에 저장 → **commit ①**

**Pass 2 — learning (§3.2)**
- [x] P2-1 00/01/02/03 개정
- [x] P2-2 04 개정 (체인 4후보 + 옵션 B §6 신설 + 07 다리 §6-4)
- [x] P2-3 05/06 재검토 패스 (06 극성 오표기는 원문 대조 결과 **미재현** — 문서가 이미 정확, 라인 참조 1건만 교정)
- [x] P2-4 ARCHITECTURE-MAP 현행화 (§5-2 라인 2026-07-16 재실측)
- [x] P2-5 07-관측-품질기록실.md 신설 + 00/MAP 링크 → **commit ②**

**Pass 3 — 정리 (§3.3)**
- [ ] P3-1 완료 plan 2건 게이트 검증 → 삭제
- [ ] P3-2 status 지표 교정 + 이력 row → **commit ③**
- [ ] P3-3 메모리 저장(learning 취급 기준) + 역검증 Explore 1회

### 재검토
- **엣지1 — 다른 세션 산출물 충돌**: status 미결 블록·pass3 plan 은 불변경 (Out 명시).
- **엣지2 — l1-langfuse 카운트 이중 표기**: "7/7 green"(active 실행 결과) vs "선언 11"(skip 포함) — 문서에 산정법 병기로 해소.
- **엣지3 — worker 수치 오분류**: 행수 아닌 합계 — D01 에 마커 의미 병기.
- **엣지4 — prod 롤백 스위치 과대 서술**: compose passthrough 부재 실측 → "선행 필요" 명시 (compose 수정은 본 plan 범위 밖).
- **엣지5 — learning 비유 훼손**: 스타일 가드 §3.2 준수, 리라이트여도 팔레트/비유 diff 0.

### Scenario (docs 적응형 Ring)
| Case | Ring | 검증 |
|---|---|---|
| R0-GREP-01 | 0 | `test 선언 164`·`모듈 28` docs 내 0건 (qa/runs 아티팩트·본 plan 제외) |
| R0-LINK-02 | 0 | 신설 07 문서가 00 목차·ARCHITECTURE-MAP 에서 링크, 내부 링크 Glob 실존 |
| R1-FACT-03 | 1 | `AGENT_LOOP_STREAM_FINAL` 이 agent.md·deployment.md·production-deployment.md 존재 · `gpt-5.4-mini` learning/04 존재 · `응답 작성 중` 이 agent.md·frontend.md·learning 01/02/04·MAP 존재 |
| R1-NUM-04 | 1 | 문서 기재 120/80/2400/99% = config.py:93-96·engine.py:228 실값 |
| R2-MERMAID-05 | 2 | 각 learning 문서 mermaid 백틱 짝·classDef 00 정본 diff 0 |
| R3-ADV-06 | 3 | 역검증 Explore 1회 — 변경 문서의 신규 주장만 코드 재대조, 발견 시 수정 후 재실행 |

### Pass 반복
- Pass 1 Fail(grep 잔존) → 해당 문서 재수정 후 R0 재검. Pass 2 Fail(mermaid/링크) → 수정 후 R2 재검. Pass 3 게이트 Fail → 삭제 보류·사유 기록.

### Agent 모델
- 설계: opus(사전 감사·본 plan). 구현: 메인 세션 직접(learning 은 위임 금지). 검증: Explore 서브에이전트(역검증 R3-ADV-06).

## 5. Validation

- **grep 게이트**: R0-GREP-01 · R1-FACT-03 · R1-NUM-04 전부 green.
- **learning 품질 게이트**: mermaid 구문(백틱 짝·classDef 정본 diff 0) · 내부 링크 Glob 실존 · 00 목차 ↔ 실제 파일 1:1 · 07 이 00·MAP 에서 링크됨.
- **역검증**: 신규 주장 코드 재대조 Explore 1회 (적대적 fact-check).
- **git diff 셀프리뷰**: 변경 줄 전부가 본 plan 항목에 매핑(Surgical).

## 6. Metadata & Notes
- **카테고리**: `infra`. **경로**: `docs/plan/infra/docs-code-sync-2026-07-16.md`.
- **커밋 3개**: ① `docs: 코드-문서 동기화 2026-07-16 — 옵션 B/e2e 카운트/auto-deploy 현행화` ② `docs(learning): 학습 문서 전면 개정 + 07-관측 신설 — 옵션 B·openai 체인·Langfuse` ③ Part 3 정리 + status.
- **push 는 사용자 확인 후** — main push = auto_deploy 트리거 (미결 §1 상황 고려).
- **롤백**: 전부 git 추적 → `git revert`.
