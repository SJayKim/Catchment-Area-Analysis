# Docs Diet & Cleanup — 문서 다이어트/정리 (2026-07-07)

> **목표**: `docs/` **151파일·30,958줄** + `qa/runs` 비-md 아티팩트 **~2.66MB** 를 절반 이하로 감량한다.
> ① 전체 문서 diet(중복 단일화) ② 완료 plan·불필요 문서 삭제 ③ current-status 압축 ④ CLAUDE.md sub-dir 분할.

## 0. 결정사항 (사용자 승인 2026-07-07)

| # | 항목 | 결정 |
|---|---|---|
| D1 | 삭제 강도 | **공격적** — `plan/_archive/` 40개 + `qa/runs` 최신 2개 제외 전부 삭제 (git history 보존) |
| D2 | `docs/learning/` (8파일·2,718줄) | **그대로 유지** — 본 plan 무접촉 (라인수 불변이 검증조건) |
| D3 | `CLAUDE.md` (195줄) | **sub-dir 분할** — root 슬림화 + `frontend/CLAUDE.md`·`server/CLAUDE.md` 신설 |

---

## 1. Context

### 1.1 현황 인벤토리 (실측 2026-07-07)

| 트리 | 파일 | 줄 | 비고 |
|---|---:|---:|---|
| `docs/plan/` | 64 | 13,741 | 이 중 `_archive/` ~40개가 완료 이력 (spot-check 균일 COMPLETED 확인) |
| `docs/qa/` | 41 md | 8,316 | + `runs/` 비-md 아티팩트 다수. `user-journey-2026-04-24` = 105파일·1.4MB |
| `docs/spec/` | 17 | 2,751 | F02~F09 가 architecture/ 를 재서술 |
| `docs/learning/` | 8 | 2,718 | **D2: 무접촉** |
| `docs/ops/` | 7 | 1,797 | `serving-stability.md` 526 · `runbook.md` 346 · `quickstart.md` 305 |
| `docs/architecture/` | 8 | 1,372 | canonical 레이어 (dedup 목적지) |
| `docs/status/` | 2 | 168 | `current-status.md` 159 |
| 루트 | — | — | `README.md` 466 · `CLAUDE.md` 195 |

### 1.2 Memory 교훈 인용 (`memory/MEMORY.md` 매칭)

- **`feedback_verify_cited_path_before_read`** — ⭐ 본 작업 최대 리스크. 파일 삭제 후 이를 가리키는 참조(현재상태 "참고 문서"·"이력 요약" 테이블, README, architecture 링크)가 dead link 로 남는다. **삭제↔참조수정 원자화**가 핵심 게이트.
- **`feedback_git_mv_untracked`** — untracked 파일은 `git rm` 실패. 삭제 대상 중 untracked(doc-consistency-v2-sweep, eval-round3.1, S*-spotfix.sse)는 `Remove-Item`, tracked 는 `git rm -r`.
- **`feedback_read_large_doc_chunking`** / **`feedback_contains_check_use_grep`** — 대형 문서 diet 시 `limit` 청크 Read, "X 들어있나" 확인은 Grep.
- **`feedback_python_utf8_windows`** — 라인수/링크 검증 스크립트는 `encoding='utf-8'` + `PYTHONIOENCODING=utf-8`.
- **`feedback_ps51_git_commit_msg_quotes_split`** — 최종 커밋 메시지(한국어)는 UTF-8(no BOM) 파일 + `git commit -F`.

### 1.3 타 Plan 충돌 / 흡수

- **`fix/doc-consistency-v2-sweep-2026-07-03.md`** (untracked·ACTIVE, 문서 v2 사실 일관성) — 본 diet 와 **동일 파일 편집·목표 중첩**. 잔여 체크리스트(v2 사실 정합)를 **Pass 2 dedup 의 "canonical 단일화 = 자동 정합" 으로 흡수 후 원본 삭제**.
- **`fix/trust-fallback-redaction-2026-07-03.md`** (untracked·**코드** plan) — R4(2026-07-04) RC1~RC5 fix 로 **이미 반영된 것으로 보임**(should_fallback ≥3∧≥50% · mask_unbound · floor guard). 단 **코드 plan 이라 본 문서 diet 범위 밖** → §6 Notes 에서 별도 확인 대상으로만 남김(삭제 안 함).

---

## 2. Scope

**In**
- 삭제: `plan/_archive/` 전체 · 완료 active plan 2개 · `qa/runs` 구증거(최신 2 eval 제외) · untracked WIP 정리.
- Diet: architecture/spec/ops/README 중복 단일화(canonical map) + 장황 산문 축소.
- `current-status.md` 압축(현재상태+Next Items 보존, 일자별 로그 → 이력 테이블).
- `CLAUDE.md` sub-dir 분할.

**Out (무접촉)**
- `docs/learning/` (D2) · 코드(`server/`·`frontend/` 소스) · **글로벌/부모 CLAUDE.md**(`~/.claude/*`, `OneDrive/Desktop/CLAUDE.md`) · **활성 plan 본문**(commercialization·apps-in-toss·langfuse-l2/ops-hardening·phase1-refactor·auto-deploy·v2-stream·ux-final-e2e) · `trust-fallback-redaction`(코드).

---

## 3. Design

### 3.1 삭제 대상 (공격적 purge)

**A. plan 완료 이력**
- `docs/plan/_archive/` **디렉토리 전체** (`git rm -r`).
- `docs/plan/infra/prod-deploy-2026-07-04.md` (COMPLETED — Phases 0~6 done).
- `docs/plan/fix/deferred-backlog-2026-07-04.md` (Item1~2 반영·Item3 는 `v2-stream-final-option-b` 로 대체됨).
- `docs/plan/fix/doc-consistency-v2-sweep-2026-07-03.md` (**untracked** — 본 plan 에 흡수 → `Remove-Item`).

**B. qa/runs 구증거 — 최신 2개만 KEEP**
- **KEEP**: `eval-round4-2026-07-04/` (GATE PASS 4/4 = 현행 정확도 기록) · `eval-stream-b-2026-07-06/` (최신) · `docs/qa/README.md` · `docs/qa/test-plan.md`.
- **DELETE**: `eval-round2-2026-06-10` · `eval-round2-raw` · `eval-round3-2026-07-03`(+ untracked `S*-spotfix.sse`) · `eval-round3.1-2026-07-03`(**untracked dir**) · `2026-04-22-ring1` · `e2e-run-2026-04-27` · `p0-hotfix-2026-04-24` · `quality-sweep-2026-04-24` · `s7-coref-pass3-2026-06-26` · `trust-eval-2026-04-24` · `user-journey-2026-04-24`(1.4MB) · `ux-final-e2e-2026-04-30` · `ux-phase-a-f-pass1` · 루스 md(`data-integrity-audit-2026-04-23`, `e2e-run-2026-04-07-mock/real`, `e2e-run-2026-04-19/22/23-full`).
- tracked → `git rm -r`, untracked → `Remove-Item -Recurse`.

**보호(삭제 금지) active plan**: commercialization · apps-in-toss · langfuse-l2-token-cost-eval · phase1-low-mid-risk · auto-deploy-on-push · langfuse-ops-hardening · v2-stream-final-option-b · ux-final-e2e-regression + **본 plan**. `architecture/tech-stack-rationale.md`(untracked) 는 KEEP(추후 `git add`).

### 3.2 중복 단일화 — Canonical Source Map

원칙: **각 사실은 한 곳에만 상세 서술**, 나머지는 1줄 요약 + 링크. (동시에 v2 사실 정합 자동 확보 → doc-consistency-v2-sweep 흡수)

| 반복 블록 | Canonical (상세 유지) | 링크로 축소할 곳 |
|---|---|---|
| SSE 이벤트(v2 7종/PAE 9종/프론트 10종) | `architecture/backend.md §4` | overview · agent.md(요약만) · README · spec/F02 · CLAUDE.md · qa/test-plan |
| v2 loop + Trust Kernel 상세 | `architecture/agent.md §2~3` | overview(1문단) · backend(1줄) · spec/F02 · CLAUDE.md |
| Tool 9종 레지스트리 표 | `architecture/agent.md §5` | overview · data.md · spec/F02 · README · CLAUDE.md |
| Budget governor 표 | `architecture/agent.md §2` | backend §3 · spec/F02 |
| 기술 스택 표 | `architecture/overview.md §3` | README(링크) · CLAUDE.md(간략) · tech-stack-rationale(why-not 만) |
| Repository 10 protocol | `architecture/data.md §1` | spec/D01 |
| Phase/로드맵 요약 | `spec/feature-list.md` | README · overview · status · CLAUDE.md(1줄) |
| 테스트 카운트 (28모듈·231·225 passed) | `architecture/backend.md §8` | overview · CLAUDE.md · status |

**장황 산문 축소 목표**: `ops/serving-stability.md` 526→≤300 · `ops/runbook.md` 346→≤250 · `ops/quickstart.md` 305→≤180("3줄 실행" TL;DR + architecture/deployment 링크) · `spec/F02` 223→≤130(agent.md 링크) · `README.md` 466→≤300(아키텍처 다이어그램/데이터플로우/기술스택 → 링크).

### 3.3 current-status 압축 (item 3)

- **보존(현재 context)**: `현재 실행 환경` 표 · `현재 서비스 지표` · `Next Items(우선순위)` · `참고 문서`.
- **신설 "미결/블로커" 3줄**(현재상태이므로 유지): ① v2-stream + langfuse-ops **prod push 대기(서버 접근 불가)** ② `.env`/`.env.dev` 수동 diff 미적용 ③ auto-deploy Pass 3 24h 관찰.
- **압축**: 일자별 `최근 작업`(07-07/07-06/07-04 상세) → `이력 요약` 테이블 1행씩. 삭제된 eval 참조는 KEEP 대상(round4/stream-b)으로 갱신.
- 목표 159 → **≤ 90줄**. (`/status-compress` 스킬 활용 가능)

### 3.4 CLAUDE.md sub-dir 분할 (item 4)

- **root `CLAUDE.md` (≤120줄)**: 프로젝트 개요 · 핵심 아키텍처 패턴(요약+@링크) · 공통 코딩 컨벤션 · 개발 워크플로우 · Reflection Loop · Plan 필수 구조 · 하네스 명령어 · **핵심 불변식**(매출=분기누적 / USE_MOCK / SSE=data:JSON) · Health Stack · `@docs` 참고링크. **제거**: 상세 기술스택 표·SSE 서술·DB 테이블 나열(→ architecture).
- **`frontend/CLAUDE.md` (신설)**: 빌드/`npm run test:e2e`(≠`npm test`) · Zustand 4스토어 · SSE 파서 gotcha · `NEXT_PUBLIC_API_URL` 함정 · React key 유일성 · tsc/lint. → `architecture/frontend.md` 링크.
- **`server/CLAUDE.md` (신설)**: 빌드/`pytest -m "not real"` · USE_MOCK 분기 · ruff · alembic · **매출 단위 warning** · v2/PAE dispatch 요약 · Python UTF-8(Windows). → `architecture/backend.md`+`agent.md` 링크.
- Claude Code 가 작업 디렉토리별로 sub-CLAUDE.md 를 자동 로드. root 의 `@`-ref 는 삭제 후에도 resolve 되어야 함(Ring0 검증).

### 3.5 감량 목표 (verifiable)

| 지표 | 현재 | 목표 |
|---|---:|---:|
| `docs/` md 총 줄 | 30,958 | **≤ ~15,000** |
| plan 파일 수 | 64 | **≤ 11** (active only, `_archive/` 부재) |
| qa/runs 아티팩트 | ~2.66MB 초과분 | 최신 2 eval 만 (**~2.66MB reclaim**) |
| README / CLAUDE(root) | 466 / 195 | ≤300 / **≤120** (+ sub 2개) |
| current-status | 159 | ≤90 |

---

## 4. 실행 (Checklist · 재검토 · Scenario · Pass · Agent)

### 실행 순서 요약
`Pass1(삭제+참조수정)` → `Pass2(dedup diet + status압축 + CLAUDE분할)` → `Pass3(검증+커밋)`.

### Checklist

**Pass 1 — Purge & 참조 원자수정**
- [ ] P1-1 `git rm -r docs/plan/_archive` + 완료 plan 2개(`prod-deploy-2026-07-04`, `deferred-backlog-2026-07-04`)
- [ ] P1-2 untracked 삭제: `Remove-Item` — `doc-consistency-v2-sweep`(흡수됨) · `eval-round3.1-2026-07-03/` · eval-round3 내 `S*-spotfix.sse`
- [ ] P1-3 qa/runs 구증거 `git rm -r` (§3.1 B DELETE 목록) — 최신 2개·README·test-plan 만 잔존
- [ ] P1-4 **참조 수정**: `git grep` 로 삭제 경로 링크(`](...)`) 전수 검색 → current-status "참고 문서/이력 요약", README, architecture 링크 수리 (dead link 0)

**Pass 2 — Diet & 재구성**
- [ ] P2-1 Canonical dedup(§3.2 표): 각 반복 블록을 canonical 1곳 유지, 나머지 요약+링크. **동시에 v2 사실 정합 확보**(테스트카운트·SSE 종수·tools 9 통일)
- [ ] P2-2 장황 산문 축소: ops(serving-stability/runbook/quickstart) · spec/F02 · README (§3.2 목표치)
- [ ] P2-3 `current-status.md` 압축 → ≤90줄 (§3.3, 블로커 3줄 보존)
- [ ] P2-4 CLAUDE.md 분할: root 슬림 + `frontend/CLAUDE.md` + `server/CLAUDE.md` 신설 (§3.4)

**Pass 3 — 검증 & 커밋**
- [ ] P3-1 링크/트리 무결성(Ring0) · 사실 정합(Ring1) · 빌드 무영향(Ring2) · 사용성 스모크(Ring3)
- [ ] P3-2 감량 목표(§3.5) 실측 달성 확인
- [ ] P3-3 커밋 (`git commit -F` UTF-8 메시지) — **push 는 사용자 확인 후**(main push=auto_deploy 트리거)

### 재검토 (Self-Review Gate)

- **엣지1 — 삭제 plan 이 자기 자신을 참조**: 본 plan 이 삭제 파일명을 나열 → 무결성 grep 이 self-hit. 검증은 **본 plan 파일 제외** + `](경로)` 링크 문법 한정.
- **엣지2 — 활성 plan 오삭제**: §3.1 보호목록 대조. 특히 `apps-in-toss`·`langfuse-l2` 는 미완이나 오래돼 archive 로 오인 금지.
- **엣지3 — CLAUDE.md `@`-ref 붕괴**: root 에서 `@docs/...` 링크가 분할 후에도 resolve 되는지, sub-CLAUDE.md 가 실제 로드되는지 확인.
- **엣지4 — learning/ 오염**: D2=무접촉. dedup 시 learning/ 은 canonical/링크 대상에서 제외(라인수 불변 검증).
- **엣지5 — 정보 손실**: current-status 압축 시 "prod push 대기·서버 접근불가·수동 env diff" 는 **미래 세션 필수 context** → 반드시 보존(과압축 금지).
- **엣지6 — Redis/formatter 잡음**: 순수 문서 작업이라 [[feedback_redis_cache_serves_old_card_text]] 무관. 단, 저장 시 markdown auto-formatter 가 표 훼손하지 않는지 1개 파일로 확인.

### Scenario (검증 Ring 매핑 — docs 적응형)

> 런타임 행위 변경이 없으므로 Ring 을 **문서 무결성 축**으로 재정의.

| Case | Ring | 검증 |
|---|---|---|
| R0-LINK-01 | 0 트리/링크 | `git grep -nE "]\(.*(_archive\|eval-round2\|eval-round3\|user-journey-2026-04-24\|prod-deploy-2026-07-04\|deferred-backlog)"` (본 plan 제외) = **0 hit** |
| R0-REF-02 | 0 참조 | root CLAUDE.md `@docs/...` 전 경로 존재(Glob) · sub-CLAUDE.md 2개 존재 |
| R1-FACT-03 | 1 정합 | SSE(7/9/10)·tools(9)·districts(1650)·tests(28/231/225) 가 canonical 1곳 + 링크, 상충 서술 0 |
| R2-BUILD-04 | 2 빌드 | 코드 파일 diff 0 → `ruff check .` · `tsc --noEmit` · `pytest -m "not real"` 무영향(green) |
| R3-USE-05 | 3 사용성 | 신규 세션 관점: root+sub CLAUDE.md 로 build/test/agent 사실을 1~2 hop 내 도달 |
| R3-DIET-06 | 3 목표 | §3.5 실측: docs md ≤~15k · plan ≤11 · README≤300 · CLAUDE≤120 · status≤90 · learning 불변 |

### Pass 반복
- Pass 1(기본 삭제) Fail(dead link 잔존) → 참조수정 재실행 후 R0 재검.
- Pass 2(dedup) Fail(R1 상충) → canonical 재지정 후 재검.
- Pass 3 Fail(목표 미달) → 해당 파일 추가 축소.

### Agent 모델 선택
- **설계**: opus (본 plan).
- **구현**: sonnet — P1 삭제는 mechanical(main), **P1-4 참조 grep+수리는 Explore/Grep 서브에이전트**로 dead-link 목록 회수. P2 dedup 은 canonical 일관성 위해 순차.
- **검증**: haiku 또는 `code-reviewer`/Explore 서브에이전트 — R0~R3 링크·라인수 자동 집계(대량 출력 격리).

---

## 5. Validation

### 성공 기준 (goal-driven, 전부 통과 시 완료)
1. `docs/plan/_archive/` 부재 · plan 파일 ≤ 11.
2. `docs/qa/runs/` = `eval-round4-2026-07-04` + `eval-stream-b-2026-07-06` 만 (~2.66MB reclaim).
3. 삭제경로 링크 grep = 0 (본 plan 제외).
4. `README.md` ≤300 · root `CLAUDE.md` ≤120 · `frontend/CLAUDE.md`·`server/CLAUDE.md` 존재.
5. `current-status.md` ≤90 + 블로커 3줄 보존.
6. ops/spec 목표치 달성(§3.2).
7. `docs/` md 총 줄 ≤ ~15,000.
8. 중복 블록 각 canonical 1곳 + 링크(R1 green).
9. 코드 무접촉 → ruff/tsc/pytest green.
10. `docs/learning/` 8파일 라인수 불변(2,718).

### 검증 명령 (PowerShell, UTF-8)
```powershell
$root="C:\Users\cyon1\OneDrive\Desktop\Catchment-Area-Analysis"
# 총 라인/파일 수
$md = Get-ChildItem "$root\docs" -Recurse -File -Filter *.md
"md files: $($md.Count) / lines: $((($md|%{(Get-Content -LiteralPath $_.FullName).Count})|Measure-Object -Sum).Sum)"
# 개별 목표
(Get-Content "$root\README.md").Count; (Get-Content "$root\CLAUDE.md").Count
(Get-Content "$root\docs\status\current-status.md").Count
Test-Path "$root\frontend\CLAUDE.md","$root\server\CLAUDE.md"
# dead-link (본 plan 제외)
Push-Location $root; git grep -nE "]\(.*(_archive|eval-round2|eval-round3|user-journey-2026-04-24|prod-deploy-2026-07-04|deferred-backlog)" -- docs ":(exclude)docs/plan/infra/docs-diet-cleanup-2026-07-07.md"; Pop-Location
```

---

## 6. Metadata & Notes
- **카테고리**: `infra` (문서 구조 refactoring). **경로**: `docs/plan/infra/docs-diet-cleanup-2026-07-07.md`.
- **선행/흡수**: `fix/doc-consistency-v2-sweep-2026-07-03.md`(흡수→삭제).
- **별도 확인(본 plan 밖)**: `fix/trust-fallback-redaction-2026-07-03.md`(untracked **코드** plan) — R4 RC1~RC5 로 반영됐는지 코드 대조 후 별도 처리. 삭제 보류.
- **커밋만·push 보류**: main push = auto_deploy 트리거 + prod 서버 현재 접근 불가. 문서 변경은 배포 무관하나 관례상 사용자 확인 후 push.
- **롤백**: 전부 git 추적 → `git revert` / 삭제분은 history 복원. 파괴적 조작 전 branch 권장.
