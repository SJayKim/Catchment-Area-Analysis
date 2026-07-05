---
name: plan-new
description: docs/plan/<category>/<name>.md 를 MarketScope 표준 5섹션 구조(Context/Scope/Design/Checklist+재검토+Scenario+Pass반복+Agent모델/Validation/Metadata)로 생성.
user-invocable: true
allowed-tools: Read, Write, Grep, Glob, Bash
---

## 입력

`$ARGUMENTS = <category> <kebab-case-name>`

- category: `business | docs | fix | infra | qa | ui` (docs/plan/ 실존 디렉토리 기준)
- 예: `/plan-new fix sales-unit-conversion-fix`

## 절차

### 1. 카테고리 검증
`$1` 이 `docs/plan/` 하위 실존 디렉토리(현재 business/docs/fix/infra/qa/ui) 중 하나인지 확인. 아니면 에러.

### 2. 중복 방지
`docs/plan/$1/$2.md` 가 이미 존재하면 abort.

### 3. Memory 훑기
```bash
# 환경변수 우선. fallback 은 현 머신의 프로젝트 memory 슬러그를 자동 탐색 (머신별 절대경로 하드코딩 금지)
MEM_DIR="${CLAUDE_MEMORY_DIR:-$(ls -d "${HOME}"/.claude/projects/*Catchment-Area-Analysis*/memory 2>/dev/null | head -1)}"
[ -n "$MEM_DIR" ] && grep -l "<키워드>" "${MEM_DIR}"/feedback_*.md 2>/dev/null
```

디렉토리가 없거나 `feedback_*.md` 가 없으면(무매치) 참조 없이 진행 — 무음 실패로 취급하지 말 것.
`$2` 에서 핵심 키워드 추출(예: sse, mock, sales, utf-8, react, playwright) 후 feedback 파일 최대 3건 수집.

### 4. 오늘 날짜
```bash
date +%Y-%m-%d
```

### 5. 템플릿 작성

```markdown
# <Title (한국어)>

## Context
- 배경 / 문제 / 동기
- **Memory 참조**: <수집한 feedback 파일명 bullet 리스트 - 해당 작업에 영향 있는 것만>

## Scope
- **In Scope**:
  -
- **Out of Scope**:
  -

## Design
- 접근 방식
- 변경 파일 목록 (`path:변경 요지`)
- 의존성 / 선행 Plan

## Checklist
- [ ] 원자적 TODO (단일 책임, 완료 조건 명확)
- [ ] ...

## 재검토 (Self-Review Gate)
- [ ] 엣지 케이스 점검
- [ ] Memory 교훈 반영 여부
- [ ] 타 Plan / 기존 코드 충돌 여부

## Scenario (E2E Ring Mapping)
- **Ring**: 0(infra) / 1(features) / 2(journeys) / 3(regression) 중 선택 + 이유
- **Scenario ID**: `<RING>-<FEATURE>-<CASE>`
- **사전조건**:
- **실행 단계**:
- **기대 결과**:

## Pass 반복 (Iteration Plan)
- Pass 1: 기본 구현
- Pass 2: 엣지 케이스 보강
- Pass 3: 성능 / 회귀 검증
- 각 Pass 후 Scenario 재실행, Fail 시 수정→재실행 루프

## Agent 모델 선택
- **설계**: opus (심층 추론 필요 여부)
- **구현**: sonnet (명확한 스펙 따라 작성)
- **검증**: haiku (Pass/Fail 판정)
- 근거:

## Validation
- 수동 검증 스텝
- `/e2e-run <ring>` 명령으로 자동 검증

## Metadata
- 작성일: <YYYY-MM-DD>
- 작성자: Claude Code (plan-new skill)
```

## 완료 기준
- 파일 생성 완료 + 절대 경로 한 줄 출력.
- Memory 참조 0건이면 "참조 없음" 명시.
