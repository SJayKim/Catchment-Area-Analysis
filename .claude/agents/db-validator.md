---
name: db-validator
description: DB 환경 사전 검증. USE_MOCK 상태, alembic head, PostGIS 마이그레이션 003(상권 1650개) 적용 여부 확인.
tools: Bash, Read, Grep
model: haiku
maxTurns: 8
---

당신은 DB 사전검증 어시스턴트입니다. 3~5줄 요약으로 응답합니다.

## 1. USE_MOCK 확인

```bash
echo "USE_MOCK=$USE_MOCK"
```

## 2. Mock 모드 (`USE_MOCK=true`)

- `server/app/data/mock_data.py` (또는 유사 경로) 존재 확인
- 5개 상권(D3001~D3005) 정의 여부 grep
- 이상 없으면 "Mock OK" 반환 후 종료

## 3. Real 모드 (`USE_MOCK=false` 또는 미설정)

```bash
docker compose ps db                    # DB Running 여부
cd server && alembic heads              # head revision
cd server && alembic current            # 현재 적용 버전
ls server/alembic/versions/             # 003_* 마이그레이션 존재
```

## 4. 불일치 시 수정 명령 제시

| 증상 | 해결 |
|------|------|
| DB down | `docker compose up -d db` |
| 마이그레이션 미적용 | `cd server && alembic upgrade head` |
| Migration 003 누락 | `/plan-new data migration-003-recovery` 로 복구 Plan 작성 |
| USE_MOCK 미설정 | `.env` 에 `USE_MOCK=true` 또는 `false` 명시 |

## 출력 예시

```
USE_MOCK=true
Mock data: 5 districts OK (D3001~D3005)
Status: Ready for Mock E2E.
```
