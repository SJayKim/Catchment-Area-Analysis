# MarketScope AI — 프로젝트 로드맵

> **마지막 업데이트**: 2026-03-22

---

## Phase 요약

| Phase | 목표 | 상태 | 완료일 |
|-------|------|------|--------|
| Phase 1 | 핵심 에이전트 MVP + 데이터 파이프라인 | ✅ 완료 | 2026-03-21 |
| Phase 2 | MCP 라우팅 해소 + 에이전트 확장 + 토론 시스템 | ✅ 완료 | 2026-03-21 |
| Phase 3 | 로깅 & 모니터링 시스템 (structlog, Langfuse, Prometheus) | ✅ 완료 | 2026-03-21 |
| Phase 4 | 리팩토링 & 문서 보강 + MCP 서버 4종 추가 | ✅ 완료 | 2026-03-21 |
| Phase 5 | 기능 테스트 & 버그 수정 (71개 테스트) | ✅ 완료 | 2026-03-21 |
| Phase 6 | 버그 수정 + 서비스 분리 + E2E 테스트 | 🔄 S2 완료 | - |
| Phase 7+ | 향후 계획 (아래 참조) | ⬜ 미착수 | - |

---

## Phase 1: 핵심 에이전트 MVP ✅ (2026-03-21)

프로젝트 기반(FastAPI, LangGraph, LiteLLM, Docker Compose) 구축 + 7개 에이전트(Commander, Population, Competition, Revenue, Location, Narrative, Visualization) 구현 + 2개 MCP 서버(public_data, maps) + 데이터 파이프라인(DB 스키마 10테이블, Collector 3종, Preprocessor 4종, Redis 캐시, APScheduler 8개 job) 완료. 총 ~45파일, ~7,150 LOC.

**주요 산출물:** 9노드 LangGraph DAG, REST API(POST/GET/SSE), PostgreSQL+PostGIS ORM, MCP Client

## Phase 2: 에이전트 확장 + 토론 시스템 ✅ (2026-03-21)

MCP 멀티서버 라우팅 블로커 해소(MCPClientRouter 구현) + 5개 Specialist Agent 추가(Trend, Financial, Risk, RealEstate, Regulatory) + 3개 MCP 서버 추가(real_estate, news, regulatory) + Debate 시스템(Advocate/Critic/Judge/Orchestrator) + Memory 시스템(Task/Personal/LightRAG) 구현. DAG 18노드로 확장.

**주요 산출물:** 15개 에이전트, 5개 MCP 서버, 토론 시스템, 메모리 3계층

## Phase 3: 로깅 & 모니터링 ✅ (2026-03-21)

structlog JSON 파이프라인 전환 + Langfuse LLM 트레이싱 활성화 + MCP 모니터링 미들웨어(MCPMonitoringMiddleware) + LangGraph DAG 관측성(@trace_node 18노드 적용) + Prometheus 메트릭 11종 + 헬스체크 확장(/health/live, /ready, /detailed) + Docker Compose 모니터링 스택(Prometheus+Grafana+Loki).

**주요 산출물:** 구조화 로깅, LLM 트레이싱, 메트릭 엔드포인트, Grafana 대시보드

## Phase 4: 리팩토링 & 문서 보강 ✅ (2026-03-21)

`user_input_node` + `debate_check_node` 추가로 DAG 20노드 완성 + MCP 서버 4종 추가(finance:6도구, database:5도구, google_maps:5도구, naver_maps:5도구) + 설계 문서 11건 작성(배포, 테스트, CI/CD, 보안, 운영, 성능, 개발자 가이드 등) + Grafana 대시보드 프로비저닝.

**주요 산출물:** 20노드 DAG, 9개 MCP 서버(총 46도구), 설계 문서 21개

## Phase 5: 기능 테스트 & 버그 수정 ✅ (2026-03-21)

Settings 로드 검증 + 37개 모듈 import 검증 + 단위 테스트 작성(에이전트 11개, MCPClientRouter 13개, 그래프 노드 11개, Edge 함수 14개, MCP 도구 14개) + 통합 테스트(워크플로우 구조 6개) + 발견 결함 2건 수정(.env 포맷, debate_check_node 방어코드). **71개 테스트 전체 PASS.**

**주요 산출물:** 71개 테스트, 결함 2건 수정

## Phase 6: 서비스 분리 + E2E 테스트 🔄 (진행 중)

S1: Critical 버그 4건 수정 완료. S2: 모놀리식 앱을 3개 서비스로 분리(API/Engine/Pipeline) + Dockerfile + docker-compose 14개 서비스 구성 + Redis 기반 서비스 간 통신(Stream/Pub/Sub/Hash) + 검증 테스트 27개 추가. **총 98개 테스트 PASS.** S3(서비스별 테스트)·S4(E2E 테스트)는 Docker 환경에서 실행 대기.

**주요 산출물:** 서비스 분리 아키텍처, Docker 인프라, 98개 테스트

---

## 데이터 처리 핵심 결정 사항

> 출처: `plan/specific_plan/data_process_plan.md`

### 데이터 파이프라인 구조
```
외부 API → Collector → Preprocessor → DB/Cache → MCP Server → Agent
```

### 구현 Phase (D0~D5, 모두 완료)
- **D0**: DB 스키마 10테이블 + PostGIS + Alembic 마이그레이션
- **D1**: Collector 3종 (Seoul, KOSIS, SEMAS) — 재시도 3회, Rate Limit 처리
- **D2**: Preprocessor 4종 (좌표변환 TM→WGS84, 코드매핑, 결측치 Forward Fill, IQR 이상치)
- **D3**: Public Data MCP Server — 8도구 + 3리소스, Redis 캐시 (TTL 7~30일)
- **D4**: Maps MCP Server — 카카오 API 기반 7도구, Redis 캐시
- **D5**: Redis 캐시 + APScheduler 8 job + 품질 모니터링

### API 키 현황

| API | 상태 | 용도 |
|-----|------|------|
| GOOGLE_API_KEY (Gemini) | ✅ | LLM |
| DATA_API_KAKAO_REST_KEY | ✅ | 카카오 지도 |
| DATA_API_SEOUL_OPEN_DATA_KEY | ✅ | 서울 열린데이터 |
| DATA_API_KOSIS_KEY | ✅ | 통계청 |
| DATA_API_PUBLIC_DATA_KEY (SEMAS) | ❌ 미발급 | data.go.kr |
| DATA_API_SMALL_BIZ_KEY | ❌ 미발급 | 소상공인진흥공단 |
| Naver API | ❌ 미발급 | 뉴스/지도 |

---

## Phase 7+: 향후 방향 (미확정)

### Phase 7: LightRAG DB 구축 + 지식 베이스
- LightRAG 메모리 시스템 실구현 (현재 인메모리 stub)
- 상권 지식 그래프 구축 (업종별 인사이트, 지역 특성)
- 분석 결과 축적 → 유사 상권 추천

### Phase 8: 프론트엔드 MVP
- Next.js 15 + Tailwind CSS + shadcn/ui
- SSE 실시간 진행률 대시보드
- 카카오맵 연동 분석 결과 시각화
- 비교 분석 기능

### Phase 9: 프로덕션 준비
- 전체 API 키 확보 (SEMAS, Naver 등)
- 성능 최적화 (MCP 캐시 히트 시 < 30초 목표)
- Circuit Breaker, Token Bucket Rate Limiting
- CI/CD 파이프라인 구축
- 보안 강화 (CORS, 인증, 환경변수 분리)

### Phase 10: 고도화
- 멀티 지역 동시 분석 / 비교 분석
- 시계열 트렌드 예측
- 사용자 맞춤 추천 (PersonalMemory 활용)
- 리포트 PDF 내보내기
