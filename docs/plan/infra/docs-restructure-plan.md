# MarketScope AI — `docs/` 폴더 재구조화 Plan

> 작성일: 2026-04-09
> 목적: 60개 .md 파일 + 8개 폴더의 docs를 스캔 가능하고 일관성 있게 정리
> 원칙: **코드와 상충하지 않는 문서 전용 작업**, git 이력 보존(rename 우선), 파괴적 삭제 최소화

---

## Context — 왜 이 작업이 필요한가

현재 `docs/`는 **60개 .md + 8개 폴더 + 64MB 스크린샷**으로 구성되어 있으며, 콘텐츠 자체는 풍부하고 최신(1주일 이내 갱신)이지만 다음 문제가 있습니다:

| 문제 | 현황 | 영향 |
|---|---|---|
| **명명 규칙 불일관** | snake_case(`data_preparation_plan.md`), kebab-case(`data-source-citation.md`), UPPER(`DATABASE_SETUP.md`) 혼재 | 파일 찾기 어렵고 새 문서 작성 시 매번 판단 필요 |
| **QA 문서 중복** | `qa/e2e-qa-test-plan.md`, `qa/qa-test-plan.md`, `plan/e2e-qa-plan.md` 3개가 범위 겹침 | 어느 것이 마스터인지 불명 |
| **상태 리포트 중복** | `status/` 4개 (`current_status`, `current_overall_status`, `e2e_test_report`, `e2e-qa-report`) | 단일 source of truth 부재 |
| **`plan/` 폴더 비대** | 31개 파일 한 폴더에 flat 배치 (agent_improvement/만 서브폴더) | 계획의 카테고리(phase / fix / infra / data) 불명 |
| **데이터 3개 문서** | `data_preparation_plan.md`, `data-source-migration.md`, `data-source-citation.md` 계층 관계 불명 | 상위/하위 구분 어려움 |
| **네비게이션 없음** | 루트 INDEX/README.md 없음, 각 폴더에 안내 문서 없음 | 신규 진입 시 어디부터 봐야 할지 모름 |
| **아카이브 미정리** | `a_drafts/merged_features.md` 여전히 "초기 설계 기준 문서"로 남음 | 구 정보와 현 정보 혼동 위험 |

**목표 상태**: (1) 파일명만 봐도 카테고리를 알 수 있고, (2) 각 폴더에 네비게이션 문서(README.md)가 있으며, (3) 중복이 제거되어 "한 주제 = 한 마스터 문서", (4) CLAUDE.md의 참조 경로가 여전히 유효.

---

## 1. 최종 목표 구조

```
docs/
├── README.md                               # ★ 신규 — docs 전체 네비게이션 (INDEX 역할)
│
├── architecture/
│   ├── README.md                           # ★ 신규 — 폴더 안내
│   └── overall-architecture.md             # (유지)
│
├── spec/
│   ├── README.md                           # ★ 신규 — Phase/기능 의존관계 + 인덱스
│   ├── feature-list.md                     # (유지) 마스터 인덱스 역할
│   ├── checklist.md                        # (유지)
│   ├── business/
│   │   └── B01-business-model.md           # ← spec/B01-business-model.md 이동
│   ├── data/
│   │   └── D01-data-pipeline.md            # ← spec/D01-data-pipeline.md 이동
│   └── features/
│       ├── F01-map-district-selection.md   # ← spec/F01-*.md 이동
│       ├── F02-ai-chatbot-agent.md
│       ├── F03-basic-report.md
│       ├── F04-industry-analysis.md
│       ├── F05-district-comparison.md
│       ├── F06-heatmap.md
│       ├── F07-business-recommendation.md
│       ├── F08-store-history-risk.md
│       ├── F09-revenue-simulation.md
│       └── F10-report-export.md
│
├── plan/
│   ├── README.md                           # ★ 신규 — 계획 카테고리별 인덱스
│   │
│   ├── phase/
│   │   ├── phase-1-implementation.md       # ← plan/phase1-implementation.md rename
│   │   ├── phase-1b-comprehensive-plan.md  # ← plan/phase1b-comprehensive-plan.md rename
│   │   ├── phase-2-implementation.md       # ← plan/phase2-implementation.md rename
│   │   └── phase-3-plan.md                 # ← plan/phase3-plan.md rename
│   │
│   ├── fix/
│   │   ├── p0-critical-fix-plan.md         # (유지, 이동)
│   │   ├── hardcoding-improvement-plan.md  # (이동)
│   │   ├── qa-bugfix-plan.md               # (이동)
│   │   ├── refactoring-plan.md             # (이동)
│   │   └── f05h1-realmode-plan.md          # (이동)
│   │
│   ├── infra/
│   │   ├── docker-integration-plan.md      # (이동)
│   │   ├── docs-restructure-plan.md        # (이동) — 본 문서
│   │   └── e2e-qa-plan.md                  # (이동) — e2e infra 계획
│   │
│   ├── data/
│   │   ├── data-preparation-plan.md        # ← data_preparation_plan.md rename (snake→kebab)
│   │   ├── data-source-migration.md        # (이동)
│   │   └── data-source-citation.md         # (이동)
│   │
│   ├── ui/
│   │   ├── card-ui-integration.md          # (이동)
│   │   ├── card-dark-theme-gitignore.md    # (이동)
│   │   └── streaming-ux-dark-theme.md      # (이동)
│   │
│   ├── business/
│   │   └── commercialization-plan.md       # (이동) — 직전 세션 산출물
│   │
│   └── agent-improvement/                  # ← agent_improvement/ rename (snake→kebab)
│       ├── 00-overview.md
│       ├── 01-state-config.md
│       ├── ... (10-ux-improvements.md까지)
│       └── (11개 파일 그대로)
│
├── qa/
│   ├── README.md                           # ★ 신규 — QA 문서 인덱스 + 최신 리포트 링크
│   ├── qa-test-plan.md                     # ★ 마스터 (유지, 194개 케이스)
│   ├── e2e-qa-test-plan.md                 # (유지) — E2E 특화
│   ├── qa-summary-report.md                # (유지)
│   ├── qa-detailed-results.md              # (유지)
│   ├── qa-bugfix-verification.md           # (유지)
│   ├── qa-improvements.md                  # (유지)
│   ├── issue-report.md                     # ← issue_report.md rename (snake→kebab)
│   ├── sub-agent-b-results.md              # (유지)
│   └── runs/
│       ├── e2e-run-2026-04-07-mock.md      # ← qa/e2e-run-2026-04-07.md rename + variant suffix
│       └── e2e-run-2026-04-07-real.md      # (이동)
│
├── status/
│   ├── README.md                           # ★ 신규 — 어느 것이 마스터인지 명시
│   ├── current-status.md                   # ← current_status.md rename (마스터, 48K)
│   ├── current-overall-status.md           # ← current_overall_status.md rename
│   └── e2e/
│       ├── e2e-test-report.md              # ← e2e_test_report.md rename + 이동
│       └── e2e-qa-report.md                # (이동)
│
├── setup/
│   ├── README.md                           # ★ 신규
│   └── database-setup.md                   # ← DATABASE_SETUP.md rename (UPPER→kebab)
│
├── archive/                                # ← a_drafts/ rename (의미 명확화)
│   ├── README.md                           # ★ 신규 — "참고 금지, 이력 보존용" 명시
│   └── merged-features.md                  # ← merged_features.md rename
│
├── screenshots/                            # (유지, 64MB 대용량이므로 손대지 않음)
│   ├── dev/ / e2e-qa/ / real-mode/ / ux/
│   └── README.md                           # ★ 신규 — 스크린샷 분류 설명
│
├── images/                                 # (유지)
│   └── README.md                           # ★ 신규
│
└── demo_video/                             # (유지, 80MB)
    └── README.md                           # ★ 신규
```

---

## 2. 변경 사항 요약

### 2.1 파일 rename (명명 규칙 통일: **kebab-case**)

| 현재 | 변경 후 | 이유 |
|---|---|---|
| `docs/plan/data_preparation_plan.md` | `docs/plan/data/data-preparation-plan.md` | snake → kebab + 이동 |
| `docs/plan/phase1-implementation.md` | `docs/plan/phase/phase-1-implementation.md` | 가독성 + 이동 |
| `docs/plan/phase1b-comprehensive-plan.md` | `docs/plan/phase/phase-1b-comprehensive-plan.md` | 이동 |
| `docs/plan/phase2-implementation.md` | `docs/plan/phase/phase-2-implementation.md` | 이동 |
| `docs/plan/phase3-plan.md` | `docs/plan/phase/phase-3-plan.md` | 이동 |
| `docs/plan/agent_improvement/` | `docs/plan/agent-improvement/` | snake → kebab (폴더) |
| `docs/setup/DATABASE_SETUP.md` | `docs/setup/database-setup.md` | UPPER → kebab |
| `docs/status/current_status.md` | `docs/status/current-status.md` | snake → kebab |
| `docs/status/current_overall_status.md` | `docs/status/current-overall-status.md` | snake → kebab |
| `docs/status/e2e_test_report.md` | `docs/status/e2e/e2e-test-report.md` | snake → kebab + 서브폴더 |
| `docs/status/e2e-qa-report.md` | `docs/status/e2e/e2e-qa-report.md` | 이동 |
| `docs/qa/issue_report.md` | `docs/qa/issue-report.md` | snake → kebab |
| `docs/qa/e2e-run-2026-04-07.md` | `docs/qa/runs/e2e-run-2026-04-07-mock.md` | variant 명시 + 이동 |
| `docs/qa/e2e-run-2026-04-07-real.md` | `docs/qa/runs/e2e-run-2026-04-07-real.md` | 이동 |
| `docs/a_drafts/` | `docs/archive/` | 의미 명확화 |
| `docs/a_drafts/merged_features.md` | `docs/archive/merged-features.md` | snake → kebab |

### 2.2 폴더 신설

```
docs/spec/business/     # B01 전용
docs/spec/data/         # D01 전용
docs/spec/features/     # F01~F10 그룹화
docs/plan/phase/        # phase-* 4개
docs/plan/fix/          # p0, hardcoding, qa-bugfix, refactoring, f05h1
docs/plan/infra/        # docker, docs-restructure, e2e infra
docs/plan/data/         # data-* 3개
docs/plan/ui/           # card-ui, dark-theme 3개
docs/plan/business/     # commercialization
docs/qa/runs/           # e2e-run-* 실행 리포트
docs/status/e2e/        # e2e 리포트 2개
docs/archive/           # 구 a_drafts
```

### 2.3 신규 문서 (README.md 10개)

각 폴더에 **10줄 내외의 네비게이션 README.md**를 추가합니다. 목적: 폴더에 진입한 사람이 "이게 뭐 모아놓은 건지" 즉시 파악.

| 경로 | 내용 (뼈대) |
|---|---|
| `docs/README.md` | 전체 docs 맵 (ASCII tree + 주요 문서 핵심 링크 5~10개) |
| `docs/architecture/README.md` | "시스템 전체 설계 문서. 시작은 overall-architecture.md" |
| `docs/spec/README.md` | "Phase/기능 의존관계 + features/business/data 3분할 안내" |
| `docs/plan/README.md` | "phase/fix/infra/data/ui/business/agent-improvement 7개 카테고리 안내" |
| `docs/qa/README.md` | "**마스터: qa-test-plan.md**. runs/에 날짜별 실행 리포트" |
| `docs/status/README.md` | "**마스터: current-status.md**. current-overall-status는 설계 vs 구현 검토" |
| `docs/setup/README.md` | "개발환경 셋업 가이드" |
| `docs/archive/README.md` | "⚠️ 참고 금지. 초기 설계 병합본 이력 보존용" |
| `docs/screenshots/README.md` | "dev/e2e-qa/real-mode/ux 4개 카테고리 구분" |
| `docs/images/README.md` | "README.md에서 참조하는 UI 이미지" |

### 2.4 중복/노후 문서 처리

| 파일 | 처리 | 이유 |
|---|---|---|
| `docs/plan/e2e-qa-plan.md` (8K) | **유지** (plan/infra/로 이동) — 초기에는 삭제하려 했으나 `qa/e2e-qa-test-plan.md`(34K)와 작성 시점·관점 다름 | 안전 보수적 유지, archive 후보는 2차 작업에서 |
| `docs/status/e2e_test_report.md`, `e2e-qa-report.md` | **유지** (status/e2e/ 서브폴더로 이동) | 이력 자료로 보존 |
| `docs/a_drafts/merged_features.md` | **유지** (archive/로 이동 + README로 참조 금지 명시) | 초기 설계 history |
| **파괴적 삭제** | **0건** | git 이력 훼손 방지, 판단 보류 시 archive가 더 안전 |

### 2.5 CLAUDE.md 참조 경로 업데이트 (필수)

`CLAUDE.md`는 다음 경로를 참조 중이며, rename/이동 후 업데이트 필요:

| 현재 참조 | 변경 후 |
|---|---|
| `docs/architecture/overall-architecture.md` | (변경 없음) |
| `docs/spec/feature-list.md` | (변경 없음) |
| `docs/spec/checklist.md` | (변경 없음) |
| `docs/spec/F01~F10-*.md` | `docs/spec/features/F01~F10-*.md` |
| `docs/spec/B01-business-model.md` | `docs/spec/business/B01-business-model.md` |
| `docs/spec/D01-data-pipeline.md` | `docs/spec/data/D01-data-pipeline.md` |
| `docs/plan/` (일반) | (변경 없음, 서브 구조만 바뀜) |
| `docs/status/current_status.md` | `docs/status/current-status.md` |

또한 **README.md는 `docs/images/`, `docs/screenshots/` 경로만 참조**하고 있어 수정 불필요.

---

## 3. 실행 순서 (5단계, 파괴적 작업 없음)

### Step 1 — 신규 폴더 생성 + README.md 10개 작성 (가장 안전)
- `docs/spec/{business,data,features}/`
- `docs/plan/{phase,fix,infra,data,ui,business}/`
- `docs/qa/runs/`
- `docs/status/e2e/`
- `docs/archive/`
- 각 신규 폴더 + 기존 8개 폴더에 README.md 작성 (총 10~12개)
- `docs/README.md` (루트 인덱스) 작성

**검증**: `ls docs/*/README.md` → 모두 존재 확인

### Step 2 — `git mv`로 파일 이동/rename (이력 보존)
```bash
# rename (snake → kebab)
git mv docs/plan/data_preparation_plan.md docs/plan/data/data-preparation-plan.md
git mv docs/plan/agent_improvement docs/plan/agent-improvement
git mv docs/setup/DATABASE_SETUP.md docs/setup/database-setup.md
git mv docs/status/current_status.md docs/status/current-status.md
git mv docs/status/current_overall_status.md docs/status/current-overall-status.md
git mv docs/status/e2e_test_report.md docs/status/e2e/e2e-test-report.md
git mv docs/qa/issue_report.md docs/qa/issue-report.md
git mv docs/a_drafts docs/archive
git mv docs/archive/merged_features.md docs/archive/merged-features.md

# 이동 (F01~F10)
git mv docs/spec/F01-map-district-selection.md docs/spec/features/
git mv docs/spec/F02-ai-chatbot-agent.md docs/spec/features/
# ... F03~F10 동일

# 이동 (spec business/data)
git mv docs/spec/B01-business-model.md docs/spec/business/
git mv docs/spec/D01-data-pipeline.md docs/spec/data/

# 이동 (plan 서브폴더)
git mv docs/plan/phase1-implementation.md docs/plan/phase/phase-1-implementation.md
git mv docs/plan/phase1b-comprehensive-plan.md docs/plan/phase/phase-1b-comprehensive-plan.md
git mv docs/plan/phase2-implementation.md docs/plan/phase/phase-2-implementation.md
git mv docs/plan/phase3-plan.md docs/plan/phase/phase-3-plan.md

git mv docs/plan/p0-critical-fix-plan.md docs/plan/fix/
git mv docs/plan/hardcoding-improvement-plan.md docs/plan/fix/
git mv docs/plan/qa-bugfix-plan.md docs/plan/fix/
git mv docs/plan/refactoring-plan.md docs/plan/fix/
git mv docs/plan/f05h1-realmode-plan.md docs/plan/fix/

git mv docs/plan/docker-integration-plan.md docs/plan/infra/
git mv docs/plan/docs-restructure-plan.md docs/plan/infra/   # 본 문서
git mv docs/plan/e2e-qa-plan.md docs/plan/infra/

git mv docs/plan/data-source-migration.md docs/plan/data/
git mv docs/plan/data-source-citation.md docs/plan/data/

git mv docs/plan/card-ui-integration.md docs/plan/ui/
git mv docs/plan/card-dark-theme-gitignore.md docs/plan/ui/
git mv docs/plan/streaming-ux-dark-theme.md docs/plan/ui/

git mv docs/plan/commercialization-plan.md docs/plan/business/

# qa runs
git mv docs/qa/e2e-run-2026-04-07.md docs/qa/runs/e2e-run-2026-04-07-mock.md
git mv docs/qa/e2e-run-2026-04-07-real.md docs/qa/runs/

# status e2e
git mv docs/status/e2e-qa-report.md docs/status/e2e/
```

**검증**:
- `git status` — 모든 변경이 "renamed"로 표시되는지 확인 (git이 rename을 감지하는지)
- `find docs -name "*.md" | wc -l` — 파일 수 (README 추가분 + 60 = ~72) 확인
- `ls docs/spec/` → README.md, feature-list.md, checklist.md, business/, data/, features/ 6개

### Step 3 — CLAUDE.md 참조 경로 업데이트
- `docs/spec/F01~F10-*.md` → `docs/spec/features/F01~F10-*.md`
- `docs/spec/B01-business-model.md` → `docs/spec/business/B01-business-model.md`
- `docs/spec/D01-data-pipeline.md` → `docs/spec/data/D01-data-pipeline.md`
- `docs/status/current_status.md` → `docs/status/current-status.md`

**검증**: `grep -n "docs/spec\|docs/status" CLAUDE.md` → 모든 경로가 신규 경로와 일치

### Step 4 — 문서 간 상호 링크 점검
- `grep -rn "docs/plan/phase1\|docs/plan/phase2\|data_preparation_plan\|current_status\.md\|DATABASE_SETUP\|F01-\|F02-\|F03-\|F04-\|F05-\|F06-\|F07-\|F08-\|F09-\|F10-\|B01-\|D01-" docs/ README.md` 로 상호 참조 깨진 링크 찾기
- 검색 결과 나오는 파일들의 링크만 신경 써서 일괄 수정
- **범위 한정**: docs/ 내부 + 루트 README.md + CLAUDE.md 만 검사 (소스 코드는 문서 경로 언급 거의 없음)

**검증**: 다시 grep → 구 경로 참조 0건

### Step 5 — 최종 검증
```bash
# 1. 파일 수 확인 (원본 60 + README 10~12 = 70~72)
find docs -name "*.md" -not -path "*/screenshots/*" | wc -l

# 2. 빈 폴더 없는지 확인
find docs -type d -empty

# 3. 모든 폴더에 README 있는지 확인
for dir in docs docs/architecture docs/spec docs/plan docs/qa docs/status docs/setup docs/archive docs/screenshots docs/images; do
  test -f "$dir/README.md" || echo "MISSING: $dir/README.md"
done

# 4. git status — renamed만 보이고 modified(CLAUDE.md 1건) 외에는 깨끗
git status

# 5. CLAUDE.md의 참조 경로가 실제 파일과 일치하는지
grep -oP 'docs/[^ )]+\.md' CLAUDE.md | xargs -I{} test -f {} && echo "OK"
```

---

## 4. 영향 범위 분석

### 4.1 수정 대상 파일

| 파일 | 작업 | 변경 줄 수 추정 |
|---|---|---|
| `docs/` 내 60개 .md 파일 | `git mv`로 이동/rename (내용 수정 0) | 0 (경로만) |
| `docs/**/README.md` × 10~12개 | 신규 작성 (각 10~30줄) | +200~300 |
| `docs/README.md` (루트 인덱스) | 신규 작성 (50~80줄) | +80 |
| `CLAUDE.md` | 참조 경로 5~7곳 업데이트 | ~10 |
| `README.md` (루트) | 변경 없음 (images/, screenshots/만 참조) | 0 |
| 소스 코드 | 변경 없음 | 0 |

### 4.2 Critical Files (작업 시 열람/수정)

- `CLAUDE.md` — Step 3에서 참조 경로 업데이트
- `README.md` — 검토만 (수정 불필요)
- `docs/spec/feature-list.md` — 내부 링크 점검
- `docs/spec/checklist.md` — 내부 링크 점검
- `docs/architecture/overall-architecture.md` — 내부 링크 점검
- `docs/status/current_status.md` (→ current-status.md) — 다른 문서 참조가 많아 링크 점검 필요

### 4.3 하지 않을 것 (의도적 배제)

- **문서 내용 수정 금지**: rename/이동 외에 본문을 손대지 않음 (Step 4의 링크 수정만 예외)
- **파괴적 삭제 0건**: 중복 의심 문서도 archive 또는 그대로 유지 (2차 작업에서 판단)
- **screenshots/images/demo_video 내부 재구성 금지**: 대용량이고 README에서 참조 중
- **CLAUDE.md/README.md 본문 재작성 금지**: 최소 참조 경로 갱신만
- **commit/push 금지**: plan이 승인되면 rename만 수행, 사용자 확인 후 git commit은 별도 요청

---

## 5. Verification — 작업 완료 검증

### 5.1 파일 시스템 검증

```bash
# 파일 수 확인: 원본 60 + README ~12 = ~72
find docs -name "*.md" -not -path "*/screenshots/*" -not -path "*/images/*" -not -path "*/demo_video/*" | wc -l

# 빈 폴더 없음 확인
find docs -type d -empty

# 각 주요 폴더의 README.md 존재 확인
ls docs/README.md \
   docs/architecture/README.md \
   docs/spec/README.md \
   docs/plan/README.md \
   docs/qa/README.md \
   docs/status/README.md \
   docs/setup/README.md \
   docs/archive/README.md

# 신규 서브폴더 구조 확인
ls docs/spec/features/ docs/spec/business/ docs/spec/data/
ls docs/plan/phase/ docs/plan/fix/ docs/plan/infra/ docs/plan/data/ docs/plan/ui/ docs/plan/business/
ls docs/qa/runs/ docs/status/e2e/
```

### 5.2 명명 규칙 검증 (snake_case / UPPER 잔존 없음)

```bash
# snake_case .md 파일 잔존 검사 — 결과 0건이어야 함
find docs -name "*_*.md"

# UPPER_CASE .md 파일 잔존 검사 — 결과 0건이어야 함
find docs -name "*.md" | grep -E '[A-Z_]+\.md$' | grep -v 'F[0-9]\{2\}-' | grep -v 'B01-' | grep -v 'D01-' | grep -v 'README\.md$'
```
(F01~F10, B01, D01, README.md는 의도적으로 대문자 허용)

### 5.3 링크 무결성 검증

```bash
# 구 경로 참조 잔존 검사 — 결과 0건이어야 함
grep -rn "data_preparation_plan\|current_status\.md\|DATABASE_SETUP\|a_drafts\|agent_improvement\|phase1-impl\|phase2-impl\|phase3-plan" docs/ CLAUDE.md README.md

# spec/F01~F10 구 경로 참조 — 루트의 "docs/spec/F01-" 형태 0건이어야 함 (docs/spec/features/F01-로 전환)
grep -rn "docs/spec/F0[0-9]\|docs/spec/F10\|docs/spec/B01\|docs/spec/D01" CLAUDE.md README.md
```

### 5.4 Git 이력 보존 검증

```bash
# 모든 변경이 "renamed"로 표시되어야 함 (copy + delete가 아닌)
git status | grep -E "renamed|new file" | wc -l  # ~72 (rename ~60 + new README ~12)
git status | grep "deleted" | wc -l  # 0이어야 함

# 특정 파일의 이력이 보존되는지 (sample)
git log --follow docs/status/current-status.md | head  # current_status.md 이전 이력이 보여야 함
```

### 5.5 CLAUDE.md 워크플로우 호환 검증

`CLAUDE.md`에 다음 지시사항이 있음:
> 1. 스펙 확인: `docs/spec/` 폴더의 해당 기능 정의서를 먼저 읽고 요구사항 파악
> 2. 계획 작성: `docs/plan/` 폴더에 구현 계획 문서 작성
> 3. 상태 업데이트: `docs/status/current_status.md`에 진행 상황 반영

→ `current_status.md` 경로를 `current-status.md`로 업데이트했는지 확인

```bash
grep "current_status\.md\|current-status\.md" CLAUDE.md
# 결과: current-status.md만 나와야 함
```

---

## 6. 대안 및 트레이드오프 (왜 이 설계인가)

| 결정 | 대안 | 선택 이유 |
|---|---|---|
| **kebab-case 통일** | snake_case / 현 상태 유지 | 기존 docs의 다수가 이미 kebab(spec/F01-..., plan/*-plan.md), snake는 소수파(4개). kebab이 웹/링크 친화적 |
| **git mv 사용** | 파일 복사 후 구 파일 삭제 | `git mv`는 git rename 감지를 강제하여 `git log --follow` 이력 보존. 문서 변경 이력 추적 중요 |
| **파괴적 삭제 0건** | 중복 의심 3개 바로 삭제 | 판단 리스크 회피. archive 후 2차 작업에서 사용자 확인 후 삭제 |
| **README.md 10~12개 추가** | 단일 docs/INDEX.md만 | 각 폴더에 자기소개가 있어야 IDE/GitHub 탐색 시 한 번에 파악. 유지비용 낮음(10줄 내외) |
| **서브폴더 분할 (plan/phase/, plan/fix/)** | flat 유지 + prefix로만 구분 | 31개 flat은 스캔 불가. agent-improvement/가 이미 서브폴더 선례 |
| **screenshots/ 손대지 않음** | 스크린샷도 카테고리 재구성 | 64MB + README에서 참조 중 → 링크 깨짐 리스크. 본 작업 범위 외 |
| **CLAUDE.md만 업데이트, 내용 재작성 X** | 전면 재작성 | 본 plan은 문서 **위치 정리**, CLAUDE.md 콘텐츠 품질은 별개 작업 |

---

## 7. 후속 작업 (이번 plan 범위 아님)

다음은 명시적으로 **이번 plan에서 다루지 않는** 후속 과제이며, 별도 plan으로 분리:

1. **중복 문서 최종 정리** — `plan/infra/e2e-qa-plan.md` vs `qa/e2e-qa-test-plan.md` 실질 병합 여부 판단 (둘 다 읽고 내용 비교 필요)
2. **status 문서 통합** — `current-status.md` vs `current-overall-status.md`를 단일 문서로 합칠지
3. **데이터 문서 계층화** — `plan/data/` 3개 파일의 상위-하위 관계 정리
4. **문서 내 cross-reference 표준화** — 상대 경로 vs 절대 경로 통일
5. **CLAUDE.md 전면 점검** — workflow 지시사항을 신규 구조에 맞춰 재작성
6. **아카이브 정책 수립** — 구 버전 문서의 보관 기간, 삭제 기준
7. **자동 생성 문서** — spec/features/에서 feature-list.md 자동 생성 스크립트

---

## 8. 요약 (한눈에)

| 항목 | 수치 |
|---|---|
| **대상** | `docs/` 60개 .md + 8개 폴더 |
| **이동/rename** | ~40건 (`git mv`로 이력 보존) |
| **신규 서브폴더** | 13개 (`spec/{business,data,features}/`, `plan/{phase,fix,infra,data,ui,business}/`, `plan/agent-improvement/` (rename), `qa/runs/`, `status/e2e/`, `archive/`) |
| **신규 문서** | README.md 10~12개 (각 10~30줄) |
| **기존 문서 내용 수정** | 0건 (rename 외) |
| **파괴적 삭제** | 0건 |
| **CLAUDE.md 업데이트** | 참조 경로 5~7줄 |
| **Git commit** | 본 작업에선 수행 X (사용자 요청 시 수행) |
| **예상 작업 시간** | README 작성 ~1시간 + git mv 스크립트 ~30분 + 검증 ~20분 |

**핵심 원칙**: "이동만, 내용 변경 최소, 이력 보존, 되돌리기 쉬움."
