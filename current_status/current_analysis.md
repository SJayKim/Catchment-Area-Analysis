# MarketScope AI - 문서 vs 구현 일치도 분석

> 분석 기준일: 2026-03-23

---

## 1. 완전 일치 (문서 = 코드)

| 컴포넌트 | 상태 | 비고 |
|----------|------|------|
| **에이전트 13종** (Commander, Population, Competition, Revenue, Location, Trend, Financial, Risk, Real Estate, Regulatory, Narrative, Visualization + Debate 4종) | 100% 구현 | LLM 호출 + MCP 도구 연동 실제 작동 |
| **MCP 서버 9개** (구조) | 100% 구현 | 9개 서버 FastAPI 엔드포인트, Docker 정의 완료 |
| **LangGraph DAG 워크플로우** | 100% 구현 | fan-out/fan-in 병렬 실행, 조건부 라우팅 |
| **핵심 API** (분석 생성/조회/SSE 스트리밍/비용) | 100% 구현 | POST/GET /analysis, /stream, /cost |
| **Health 엔드포인트** | 100% 구현 | /health, /live, /ready, /detailed |
| **DB 모델 10+ 테이블** | 100% 구현 | PostGIS, Alembic 마이그레이션 |
| **데이터 파이프라인** (수집기 3종, 전처리기 4종) | 100% 구현 | SEMAS, Seoul, KOSIS 수집기 |
| **스케줄러 10개 작업** | 100% 구현 | APScheduler 기반 cron |
| **Docker Compose 16 서비스** | 100% 구현 | infra + app + MCP + monitoring |
| **Prometheus/Grafana 모니터링** | 100% 구현 | 메트릭 정의, 스크래퍼, 대시보드 |
| **Redis Broker** (API↔Engine 비동기) | 100% 구현 | Stream, Pub/Sub, Hash |

---

## 2. 문서에는 있으나 미구현

| 컴포넌트 | 문서 내용 | 구현 상태 | 실현 가능성 판단 |
|----------|----------|----------|-----------------|
| **인증 API** (register, login, OAuth, JWT) | 6개 엔드포인트 정의 | **0%** - 파일 없음 | **후순위** - 내부 도구로 쓸 거면 불필요. 외부 공개 시에만 필요 |
| **채팅 API** (follow-up, history) | 2개 엔드포인트 정의 | **0%** - 파일 없음 | **가치 있음** - 분석 후 추가 질문은 UX 핵심. 구현 복잡도 중간 |
| **사용자 프로필 API** | profile CRUD | **0%** - 파일 없음 | **후순위** - 인증과 세트. 단독 구현 의미 없음 |
| **비교 분석 API** (compare) | POST /analysis/compare | **0%** - 라우트 없음 | **가치 있음** - 에이전트/워크플로우는 이미 comparison 모드 지원. 라우트만 추가하면 됨 |
| **지역/업종 검색 API** | districts/search, industries | **0%** - 라우트 없음 | **쉬움** - DB에 데이터 있으면 단순 쿼리. 우선 구현 추천 |
| **프론트엔드** (Next.js 15) | Phase 8 설계 | **0%** - 미착수 | **대규모 작업** - 별도 프로젝트 수준 |
| **LightRAG** (지식 그래프) | Phase 7 설계 | **스텁** - 인메모리 리스트 | **후순위** - 그래프 DB 필요, 실 데이터 충분히 쌓인 후에 의미 |
| **ReMe 메모리** | 사용자 선호 학습 | **스텁** - 최소 구현 | **후순위** - 반복 사용자 있을 때만 의미 |

---

## 3. 구현되어 있으나 실질적으로 작동 불가 (데이터/API 키 부재)

| MCP 서버 | 구현 상태 | 필요 API 키 | 실제 작동 여부 |
|----------|----------|------------|--------------|
| **Maps (Kakao)** | 실제 API 연동 | `DATA_API_KAKAO_REST_KEY` | 키 있으면 즉시 작동 |
| **Public Data** | 실제 API 연동 | `SEOUL_OPEN_DATA_KEY`, `KOSIS_KEY` | 키 있으면 즉시 작동 |
| **Google Maps** | 실제 API 연동 | `DATA_API_GOOGLE_MAPS_KEY` | 유료 API - 비용 발생 |
| **Naver Maps** | 실제 API 연동 | `NAVER_CLIENT_ID/SECRET` | 키 없으면 전면 실패 |
| **News** | 네이버 API 연동 | `NAVER_CLIENT_ID/SECRET` | 키 없으면 빈 결과 반환 (silent fail) |
| **Real Estate** | **대부분 스텁** | `DATA_API_PUBLIC_DATA_KEY` | 4개 중 3개가 `{"status": "estimated"}` 반환. 키 있어도 API URL 불완전 |
| **Regulatory** | 하드코딩 데이터 | 없음 | 즉시 작동 - 5개 업종만 지원 (음식점, 카페, 주점, 미용실, 학원) |
| **Finance** | 혼합 | 일부 `PUBLIC_DATA_KEY` | 4/6 즉시 작동 (대출 계산, 최저임금, 4대보험). 창업지원금 검색만 키 필요 |
| **Database** | PostgreSQL 직접 | 없음 | DB 구동 시 즉시 작동 |

---

## 4. 종합 판단

### 현재 상태 요약

| 영역 | 완성도 | 설명 |
|------|--------|------|
| 아키텍처/인프라 | **95%** | 문서와 거의 일치 |
| 핵심 분석 파이프라인 | **90%** | 에이전트, 워크플로우, 스트리밍 모두 구현 |
| 데이터 레이어 | **70%** | 구조는 있으나 실제 API 연동은 키 확보 필요 |
| 부가 API | **30%** | 핵심 분석만 구현, 인증/채팅/비교 미구현 |
| 프론트엔드 | **0%** | 미착수 |

### 즉시 실행 가능한 것 (API 키 없이)

1. Regulatory MCP (5개 업종 하드코딩)
2. Finance MCP 일부 (대출 계산, 최저임금, 보험료)
3. Database MCP (로컬 DB)
4. 전체 LangGraph 워크플로우 (MCP 호출 실패 시 LLM이 추정값으로 대체)

### 우선 해야 할 것 (가성비 높은 순)

1. **API 키 확보** - Kakao, Seoul Open Data, KOSIS 키만 확보하면 핵심 분석(유동인구, 매출, 경쟁, 입지)이 실제 데이터로 작동
2. **비교 분석 라우트 추가** - 워크플로우에 comparison 모드가 이미 있으므로 라우트만 추가 (소규모 작업)
3. **지역/업종 검색 API** - DB 쿼리만 하면 되므로 구현 간단
4. **Real Estate MCP 실제 연동** - 현재 스텁 상태, API URL 수정 및 실제 데이터 연동 필요

### 후순위 (현시점에서 불필요)

- **인증/사용자 관리** - 내부 도구로 사용 시 불필요
- **프론트엔드** - API가 안정화된 후 착수
- **LightRAG/ReMe** - 실 사용 데이터 쌓인 후에 의미
- **Naver Maps** - Kakao Maps와 기능 중복. 둘 다 유지할 필요 없음
