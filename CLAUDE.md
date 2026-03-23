# MarketScope AI — 상권 분석 멀티 에이전트 시스템

한국 소매업 창업을 위한 상권 타당성 분석 플랫폼. Claude/Gemini LLM + LangGraph + MCP 서버 기반.

## 패키지 구조

```
marketscope/
├── agent/    # LangGraph DAG, 13 에이전트, LLM(LiteLLM), 메모리
├── api/      # FastAPI REST (port 8000), SSE 스트리밍
├── common/   # 공유: config, DB(PostGIS), models, monitoring, Redis broker
├── mcp/      # MCP 도구 서버 9개 (port 5100-5108)
├── pipeline/ # 데이터 수집기 3종, 전처리기 4종, APScheduler
├── alembic/  # DB 마이그레이션
└── tests/    # unit + integration
```

import 경로: `from marketscope_agent.agents.base import ...`, `from marketscope_common.config import ...` 등 패키지명 기준.
`marketscope/app/`은 폐기된 레거시 경로 — 절대 참조하지 말 것.

## 데이터 흐름

```
Client → POST /api/v1/analysis
           ↓
      API (Redis Stream publish)
           ↓
      Engine Worker (LangGraph DAG 실행)
           ↓
      Agent → MCP Server(HTTP) → 외부 API / DB
           ↓
      Redis Pub/Sub (진행 상황)
           ↓
      Client ← GET /stream (SSE)
      Client ← GET /analysis/{id} (결과)
```

## 빌드 & 테스트

```bash
cd marketscope
docker compose up -d                    # 전체 16 서비스 기동
docker compose up postgres redis -d     # 인프라만
pytest tests/ -v                        # 테스트
alembic upgrade head                    # DB 마이그레이션
```

## MCP 서버

| 서버 | 포트 | API 키 | 상태 |
|------|------|--------|------|
| public-data | 5100 | `SEOUL_OPEN_DATA_KEY`, `KOSIS_KEY` | 실제 API |
| maps (Kakao) | 5101 | `KAKAO_REST_KEY` | 실제 API |
| real-estate | 5102 | `PUBLIC_DATA_KEY` | 대부분 스텁 |
| news | 5103 | `NAVER_CLIENT_ID/SECRET` | 실제 API |
| regulatory | 5104 | 없음 | 하드코딩 (5개 업종) |
| finance | 5105 | 일부 `PUBLIC_DATA_KEY` | 혼합 (4/6 즉시 작동) |
| database | 5106 | 없음 | PostGIS 직접 |
| google-maps | 5107 | `GOOGLE_MAPS_KEY` | 실제 API (유료) |
| naver-maps | 5108 | `NAVER_CLIENT_ID/SECRET` | 실제 API |

## 에이전트 DAG

```
user_input → commander_plan
  ├─ population ──┐
  ├─ competition ─┤ (병렬 Group 1)
  │               ↓
  ├─ revenue ─────┐ (population 의존)
  ├─ location ────┤ (population+competition 의존, 병렬 Group 2)
  │               ↓
  ├─ trend ───────┐
  ├─ real_estate ─┤ (병렬 Group 3, Phase 2)
  ├─ regulatory ──┘
  │               ↓
  ├─ financial    (revenue+competition 의존)
  ├─ risk         (전체 의존)
  ├─ debate?      (조건부: deep 모드)
  ↓
  commander_judgment → narrative → visualization → report_assembly
```

분석 모드: `basic` | `quick` | `standard` | `deep` | `comparison`

## 현재 상태 (2026-03-23)

**작동**: 에이전트 13종, DAG, API(분석/health/SSE), Docker 16서비스, 모니터링, 스케줄러, Redis broker
**스텁**: LightRAG(인메모리), ReMe(최소), Real Estate MCP(3/4 추정값 반환)
**미구현**: 인증 API, 채팅 API, 비교 분석 라우트, 프론트엔드, 지역/업종 검색 API

## 주의사항

- LLM 호출: LiteLLM 경유. 에이전트별 모델 설정은 `common/config.py`의 Settings
- 외부 API 실패 시 LLM이 추정값으로 대체 (silent fail 주의)
- DB: PostgreSQL 15 + PostGIS, GeoAlchemy2 사용
- 테스트 시 외부 API mock 필수 — 실제 키 없이 CI 가능해야 함
- Langfuse 모니터링은 기본 비활성 (`LANGFUSE_ENABLED=false`)
