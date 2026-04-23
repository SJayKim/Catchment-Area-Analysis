---
name: status-update
description: docs/status/current-status.md 에 오늘 날짜 진행 기록을 추가. Phase 섹션 구조/이모지 관례 보존. 400줄 초과 시 status-compress 자동 선행.
user-invocable: true
allowed-tools: Read, Edit, Bash, Skill
---

## 입력

`$ARGUMENTS` = 진행 요약 문장 (선택). 비어 있으면 최근 git log 로 자동 생성.

## 절차

### 0. 줄 수 프리체크 (400줄 가드)

```bash
wc -l docs/status/current-status.md
```

- **> 400** → `/status-compress` 먼저 호출 (Skill 로 체이닝). 압축 완료 후 본 절차 1 부터 재개.
- ≤ 400 → 바로 1 번으로.

### 1. 파일 읽기
```
Read docs/status/current-status.md
```
큰 파일이므로 `limit=150` 으로 청크 분할 (memory/feedback_read_large_doc_chunking.md 관례).

### 2. 오늘 날짜
```bash
date +%Y-%m-%d
```

### 3. 요약 확보
- `$ARGUMENTS` 가 있으면 그대로 사용
- 비어 있으면:
```bash
git log --oneline -5
```
으로 최근 5개 커밋 요약

### 4. 헤더 업데이트
```
> 최종 갱신: <YYYY-MM-DD>
```
라인을 오늘 날짜로 Edit.

### 5. Phase 섹션에 블록 삽입

가장 최근 Phase 섹션 바로 아래에:

```markdown
### <YYYY-MM-DD>
- ✅ <완료 항목>
- 🔧 <진행 중>
- ⚠️ <블로커>
```

### 6. 이모지 규약

| 이모지 | 의미 |
|--------|------|
| ✅ | 완료 |
| 🔧 | 진행 중 |
| ⚠️ | 이슈 / 블로커 |
| 🆕 | 신규 |
| ⭐ | 주목 |

## 완료 기준
- 파일 수정 + diff 한 줄 요약 출력.
- 같은 날짜 블록이 이미 있으면 append (새 블록 만들지 말 것).
