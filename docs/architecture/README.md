# Architecture

MarketScope AI 시스템 설계 문서. 레이어별로 분리되어 있으며, 전체 구조는 `overview.md` 에서 시작한다.

| 문서 | 다루는 범위 |
|---|---|
| [overview.md](overview.md) | 전체 시스템 요약 — 이 문서를 먼저 읽을 것 |
| [backend.md](backend.md) | FastAPI 앱 / API 라우트 / 서비스 / 미들웨어 |
| [frontend.md](frontend.md) | Next.js App Router / Zustand / SSE 파서 / Card UI |
| [agent.md](agent.md) | PAE 그래프 / Tool 11종 / 프롬프트 / 세션 히스토리 |
| [data.md](data.md) | DB 스키마 / Repository / PostGIS / ETL / 캐시 규약 |
| [deployment.md](deployment.md) | Docker Compose / Nginx / 환경변수 / 배포 순서 |

## 읽는 순서 권장

1. `overview.md` — 전체 그림 파악
2. 변경 대상 레이어의 상세 문서만 선택적으로 참조 (토큰 절감)
3. 기능 단위 스펙은 [../spec/features/](../spec/features/) 로 이동

## 문서 갱신 원칙

- 실제 코드 변경과 **같은 PR** 에서 갱신
- 한 레이어 변경은 해당 레이어 문서만 수정 (계층 분리 유지)
- 버전/수치 (TTL, pool size, timeout 등) 은 `config.py` · `docker-compose.yml` 이 단일 진실
- 다이어그램은 ASCII 유지 (렌더링 의존성 제거)
