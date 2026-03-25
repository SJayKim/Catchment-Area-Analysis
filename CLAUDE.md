# CLAUDE.md — MarketScope AI (상권분석 AI 서비스)

## 프로젝트 개요

지도 기반 AI 챗봇으로 서울시 상권을 분석하는 Freemium SaaS.
소상공인/부동산 투자자가 "지도에서 상권 선택 → AI가 분석/추천" 하는 서비스.

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| Frontend | Next.js 14 (App Router, TypeScript), Kakao Map SDK, deck.gl, Recharts, Zustand, shadcn/ui + Tailwind |
| Backend | FastAPI (Python 3.12, async), LangGraph (ReAct Agent), Claude API |
| Database | PostgreSQL 16 + PostGIS, Redis 7 |
| Infra | Docker Compose (dev), GitHub Actions CI/CD |
| Observability | Langfuse (LLM tracing) |

## 프로젝트 구조

```
docs/
  architecture/overall-architecture.md   # 시스템 아키텍처 (필독)
  spec/feature-list.md                   # 기능 목록 + Phase 계획
  spec/checklist.md                      # 개발 체크리스트 (~150항목)
  spec/B01-business-model.md             # Freemium 수익 모델
  spec/D01-data-pipeline.md              # ETL 파이프라인 설계
  spec/F01~F10-*.md                      # 각 기능 상세 스펙
```

## 빌드 & 실행

```bash
# 개발 환경 기동
docker compose up -d

# Frontend
cd frontend && npm install && npm run dev

# Backend
cd backend && pip install -e ".[dev]" && uvicorn main:app --reload

# 테스트
cd frontend && npm test
cd backend && pytest

# 린트/포맷
npx prettier --write .          # TypeScript
ruff check --fix . && ruff format .  # Python
```

## 개발 Phase

- **Phase 0**: 인프라 — Docker, DB 스키마(PostGIS), 데이터 파이프라인(ETL)
- **Phase 1 (MVP)**: F01 지도 선택 → F02 AI 챗봇 → F03 기본 리포트
- **Phase 2 (Premium)**: F04 업종 심층, F05 상권 비교, F07 업종 추천, F08 리스크
- **Phase 3 (확장)**: F06 히트맵, F09 매출 시뮬레이션, F10 PDF 리포트

## 핵심 아키텍처 패턴

- **AI Agent**: LangGraph ReAct loop (Reason → Act → Observe), 최대 5회 반복
- **통신**: FastAPI → SSE 스트리밍 (thinking/tool/text/card/map_cmd/done 이벤트)
- **지도-챗봇 연동**: Zustand store로 상권 선택 ↔ 챗 컨텍스트 동기화
- **공간 쿼리**: PostGIS ST_Contains, ST_Within으로 상권 경계 처리
- **캐싱**: Redis (report:{code}:{quarter}, TTL 24h)

## 코딩 컨벤션

- TypeScript: strict mode, 2-space indent, ESLint + Prettier
- Python: type hints 필수, ruff (lint + format), async/await 우선
- 컴포넌트: shadcn/ui 기반, Tailwind 유틸리티 클래스
- API: RESTful, snake_case (Python), camelCase (TypeScript)
- DB: Alembic 마이그레이션, 테이블명 복수형 snake_case

## 데이터 소스

- 서울 열린데이터 (data.seoul.go.kr): 상권 폴리곤, 유동인구, 추정매출, 상주/직장인구
- 공공데이터포털 (data.go.kr): 점포 정보, 점포 이력

## 주요 DB 테이블

districts, floating_population, estimated_sales, stores, store_history,
resident_population, chat_sessions, chat_messages, category_metadata

## 개발 워크플로우

코드 구현 시 반드시 아래 순서를 따를 것:

1. **스펙 확인**: `docs/spec/` 폴더의 해당 기능 정의서를 먼저 읽고 요구사항 파악
   - 기능별 스펙: `docs/spec/F01~F10-*.md`, `docs/spec/D01-*.md`, `docs/spec/B01-*.md`
   - 체크리스트: `docs/spec/checklist.md`
2. **계획 작성**: `docs/plan/` 폴더에 구현 계획 문서 작성 (접근 방식, 변경 범위, 의존성 정리)
3. **구현**: 스펙과 계획에 따라 코드 작성
4. **상태 업데이트**: 구현 완료 후 `docs/status/current_status.md`에 진행 상황 반영

## 참고 문서

새 기능 구현 전 반드시 해당 스펙 문서를 먼저 읽을 것:
- 전체 구조: @docs/architecture/overall-architecture.md
- 기능 목록: @docs/spec/feature-list.md
- 체크리스트: @docs/spec/checklist.md
