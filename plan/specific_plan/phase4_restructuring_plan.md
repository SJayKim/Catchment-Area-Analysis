# Phase 4 리팩토링 & 문서 보강 계획서

> 작성일: 2026-03-21
> 상태: 🟡 진행 중

---

## 개요

기존 설계 문서(`document/specs/`)와 실제 코드베이스 간 불일치를 해소하고,
누락된 문서를 전부 작성하는 종합 리팩토링 작업.

---

## Part 1: 코드 재구성 — 기존 스펙 문서 기준 정렬

### 1-1. Finance MCP 서버 구현 (스펙 #6)

스펙 문서 `05_mcp_servers.md` Section 6에 정의된 Finance MCP 서버가 코드에 없음.

- [ ] `app/mcp_servers/finance/__init__.py` 생성
- [ ] `app/mcp_servers/finance/server.py` — FastMCP 인스턴스
- [ ] `app/mcp_servers/finance/tools.py` — 6개 도구 구현
  - `search_startup_loans` (기업마당/K-Startup API)
  - `search_government_subsidies` (기업마당 API)
  - `calculate_loan_repayment` (내부 계산)
  - `get_franchise_disclosure` (공정위 API)
  - `get_minimum_wage` (내부 데이터)
  - `get_insurance_rates` (내부 데이터)
- [ ] `app/mcp_servers/finance/schemas.py` — Pydantic 모델
- [ ] `app/mcp_servers/finance/api_client.py` — httpx API 래퍼
- [ ] `docker-compose.yml`에 finance MCP 서비스 추가
- [ ] `tools/mcp_client.py` MCPClientRouter에 finance 서버 등록

### 1-2. Database MCP 서버 구현 (신규)

PostGIS 공간쿼리를 에이전트에게 제공하는 Database MCP 서버.

- [ ] `app/mcp_servers/database/__init__.py` 생성
- [ ] `app/mcp_servers/database/server.py` — FastMCP 인스턴스
- [ ] `app/mcp_servers/database/tools.py` — 도구 구현
  - `query_nearby_stores` — 반경 내 점포 조회 (PostGIS ST_DWithin)
  - `query_population_grid` — 격자별 인구 데이터
  - `query_revenue_by_area` — 지역별 매출 데이터
  - `query_commercial_district` — 상권 정보 조회
  - `execute_spatial_query` — 범용 공간 쿼리
- [ ] `app/mcp_servers/database/db_client.py` — asyncpg 연결 풀
- [ ] `app/mcp_servers/database/schemas.py` — 스키마
- [ ] `docker-compose.yml`에 database MCP 서비스 추가
- [ ] `tools/mcp_client.py` MCPClientRouter에 database 서버 등록

### 1-3. Google Maps MCP 서버 구현 (신규)

Google Places/Geocoding API 래퍼.

- [ ] `app/mcp_servers/google_maps/__init__.py` 생성
- [ ] `app/mcp_servers/google_maps/server.py` — FastMCP 인스턴스
- [ ] `app/mcp_servers/google_maps/tools.py` — 도구 구현
  - `google_geocode` — 주소 → 좌표 변환
  - `google_reverse_geocode` — 좌표 → 주소
  - `google_nearby_search` — 주변 장소 검색 (Places API)
  - `google_place_details` — 장소 상세 (리뷰, 영업시간)
  - `google_directions` — 경로 탐색
- [ ] `app/mcp_servers/google_maps/api_client.py` — Google API 래퍼
- [ ] `app/mcp_servers/google_maps/schemas.py` — 스키마
- [ ] `docker-compose.yml`에 google_maps MCP 서비스 추가
- [ ] `tools/mcp_client.py` MCPClientRouter에 google_maps 서버 등록

### 1-4. Naver Maps MCP 서버 구현 (신규)

네이버 지도/장소 API 래퍼.

- [ ] `app/mcp_servers/naver_maps/__init__.py` 생성
- [ ] `app/mcp_servers/naver_maps/server.py` — FastMCP 인스턴스
- [ ] `app/mcp_servers/naver_maps/tools.py` — 도구 구현
  - `naver_geocode` — 주소 → 좌표 (Geocoding API)
  - `naver_reverse_geocode` — 좌표 → 주소
  - `naver_local_search` — 장소 검색 (Search API)
  - `naver_directions` — 경로 탐색 (Directions API)
  - `naver_static_map` — 정적 지도 이미지 URL 생성
- [ ] `app/mcp_servers/naver_maps/api_client.py` — Naver API 래퍼
- [ ] `app/mcp_servers/naver_maps/schemas.py` — 스키마
- [ ] `docker-compose.yml`에 naver_maps MCP 서비스 추가
- [ ] `tools/mcp_client.py` MCPClientRouter에 naver_maps 서버 등록

### 1-5. LangGraph 노드 추가 — `user_input_node`

스펙 `01_orchestration_langgraph.md`에 정의된 `user_input` 노드가 코드에 없음.

- [ ] `graph/nodes.py` — `user_input_node()` 함수 추가
  - 사용자 입력 파싱 & 기본 검증
  - 빈 입력 시 `has_critical_failure=True` 반환
  - 정상 시 `current_phase=0, progress_pct=2.0` 설정
  - `@trace_node` 데코레이터 적용
- [ ] `graph/workflow.py` — 엔트리포인트 변경
  - `user_input` 노드 등록
  - `set_entry_point("user_input")`
  - `user_input → commander_plan` 엣지 추가
- [ ] 기존 `commander_plan` 엔트리포인트 제거 (→ user_input 뒤로 이동)

### 1-6. LangGraph 노드 추가 — `debate_check_node`

스펙에 정의된 `debate_check` 전용 노드가 코드에서 엣지 함수로만 존재.

- [ ] `graph/nodes.py` — `debate_check_node()` 함수 추가
  - 4가지 트리거 조건 평가:
    1. 에이전트 confidence 평균 < 0.6
    2. 매출 추정치 분산 > 30%
    3. 에이전트 간 결론 충돌
    4. `force_debate=True`
  - `debate_decision` (TRIGGER/SKIP) + `debate_trigger_reasons` 반환
  - `@trace_node` 데코레이터 적용
- [ ] `graph/edges.py` — `route_after_debate_check()` 추가
  - `state["debate_decision"]` 기반 라우팅
  - 기존 `should_run_debate()` 로직은 `debate_check_node`로 이전
- [ ] `graph/workflow.py` — 워크플로우 수정
  - `debate_check` 노드 등록
  - `risk → debate_check` 엣지
  - `debate_check → conditional_edge(debate | commander_judgment)`
  - 기존 `risk → should_run_debate → debate/judgment` 패턴 제거
- [ ] `models/state.py` — 필드 추가 (필요시)
  - `debate_decision: str | None`
  - `debate_trigger_reasons: list[str]`

### 1-7. 파이프라인 정합성 검증

- [ ] `graph/workflow.py` import 정리 (새 노드/엣지 반영)
- [ ] `graph/nodes.py` export 목록 갱신
- [ ] MCP 서버 라우팅 동작 확인 (새 서버 3개 + finance)
- [ ] `main.py` lifespan 흐름 확인
- [ ] Python import 오류 없는지 검증 (`python -c "from app.graph.workflow import build_workflow"`)

---

## Part 2: 누락 MCP 서버 문서 작성

### 2-1. Database MCP 서버 스펙

- [ ] `document/specs/05_mcp_servers_database.md` 작성
  - 서버 프로필 (서버명, 목적, 래핑 대상)
  - 도구 목록 (5개: query_nearby_stores, query_population_grid 등)
  - 각 도구별 파라미터, SQL 쿼리 패턴, 반환 스키마
  - PostGIS 함수 활용 사항 (ST_DWithin, ST_MakePoint 등)
  - 에러 처리 & 커넥션 풀 전략
  - 기존 `05_mcp_servers.md` 포맷 준수

### 2-2. Google Maps MCP 서버 스펙

- [ ] `document/specs/05_mcp_servers_google_maps.md` 작성
  - 서버 프로필
  - 도구 목록 (5개: google_geocode, google_nearby_search 등)
  - Google API 키 관리 & 할당량
  - 요청/응답 스키마
  - Rate Limiting 전략
  - 에러 처리

### 2-3. Naver Maps MCP 서버 스펙

- [ ] `document/specs/05_mcp_servers_naver_maps.md` 작성
  - 서버 프로필
  - 도구 목록 (5개: naver_geocode, naver_local_search 등)
  - Naver Cloud Platform 인증 (Client ID/Secret)
  - 요청/응답 스키마
  - Rate Limiting 전략
  - 에러 처리

---

## Part 3: 누락 문서 전체 작성

### 3-1. 배포 & 인프라 가이드

- [ ] `document/specs/11_deployment.md` 작성
  - Dockerfile 설계 (Python 3.11-slim 기반)
  - docker-compose.yml 서비스 구성 상세
  - docker-compose.monitoring.yml 모니터링 스택
  - 환경변수 목록 (.env 필수/선택 항목)
  - 로컬 개발 환경 셋업 절차
  - GCP Cloud Run 프로덕션 배포 절차
  - Alembic 마이그레이션 전략
  - 볼륨 & 네트워크 구성

### 3-2. 테스트 전략

- [ ] `document/specs/12_testing.md` 작성
  - 테스트 아키텍처 (단위/통합/E2E 3-tier)
  - pytest + pytest-asyncio 설정
  - 에이전트 단위 테스트 패턴 (LLM 모킹)
  - MCP 서버 단위 테스트 패턴
  - LangGraph 워크플로우 통합 테스트
  - API 엔드포인트 테스트 (httpx AsyncClient)
  - 테스트 픽스처 & 팩토리
  - 커버리지 목표 (>80%)
  - 테스트 데이터 관리 전략

### 3-3. CI/CD 파이프라인

- [ ] `document/specs/13_cicd.md` 작성
  - GitHub Actions 워크플로우 설계
  - 빌드 스테이지: lint (ruff) → test (pytest) → Docker build
  - 배포 스테이지: staging → production
  - 환경별 배포 전략
  - Alembic 자동 마이그레이션
  - 롤백 절차
  - 시크릿 관리 (GitHub Secrets)
  - PR 자동 검증 워크플로우

### 3-4. 보안 & 컴플라이언스

- [ ] `document/specs/14_security.md` 작성
  - 인증 아키텍처 (JWT RS256, 토큰 수명주기)
  - OAuth2 소셜 로그인 (Google, Kakao)
  - API 키 관리 & 로테이션
  - 데이터 암호화 (at-rest: PostgreSQL, in-transit: TLS)
  - 시크릿 관리 (환경변수, Docker secrets)
  - 입력 검증 & 새니타이징
  - Rate Limiting 구현 상세
  - GDPR/PIPA 개인정보 보호 매핑
  - OWASP Top 10 대응 전략
  - 취약점 스캔 (Trivy, Bandit)

### 3-5. 운영 & 트러블슈팅

- [ ] `document/specs/15_operations.md` 작성
  - 로깅 전략 (structlog → Loki → Grafana)
  - 모니터링 대시보드 구성 (Prometheus 메트릭 11종)
  - 알림 규칙 (AlertManager 연동)
  - 일반적인 장애 유형 & 디버깅 절차
  - DB 백업 & 복구 절차 (pg_dump/pg_restore)
  - Redis 장애 대응
  - MCP 서버 장애 대응 (Circuit Breaker 동작)
  - 성능 튜닝 (DB 인덱스, 캐시 전략, 커넥션 풀)
  - 수평 확장 전략 (Celery workers)
  - 인시던트 대응 런북

### 3-6. Grafana 대시보드

- [ ] `monitoring/grafana/dashboards/marketscope_overview.json` 생성
  - HTTP 요청 레이턴시 & 처리량
  - 에이전트 실행 시간 & 에러율
  - LLM 토큰 사용량 & 비용
  - MCP 서버 상태 & 레이턴시
  - 토론 시스템 통계
  - 파이프라인 노드별 소요시간

### 3-7. 성능 벤치마크 & SLA

- [ ] `document/specs/16_performance.md` 작성
  - 분석 모드별 목표 응답 시간 (Quick: 30s, Basic: 90s, Deep: 180s)
  - API 엔드포인트별 SLA (p50/p95/p99 레이턴시)
  - LLM 호출 비용 목표 ($2/분석)
  - 동시 분석 처리 용량
  - DB 쿼리 성능 기준
  - 부하 테스트 시나리오

### 3-8. 개발자 온보딩 가이드

- [ ] `document/specs/17_developer_guide.md` 작성
  - 퀵스타트 (clone → docker-compose up → 테스트)
  - 개발 환경 설정 (Python 3.11+, Docker, IDE)
  - 프로젝트 구조 설명
  - 새 에이전트 추가 방법
  - 새 MCP 서버 추가 방법
  - Git 워크플로우 & 커밋 컨벤션
  - 디버깅 가이드
  - 코드 리뷰 가이드라인

---

## 실행 순서

```
Step 1: Part 1-5 → user_input_node 추가
Step 2: Part 1-6 → debate_check_node 추가
Step 3: Part 1-7 → 워크플로우 재연결 & 검증
Step 4: Part 1-1 → Finance MCP 서버
Step 5: Part 1-2 → Database MCP 서버
Step 6: Part 1-3 → Google Maps MCP 서버
Step 7: Part 1-4 → Naver Maps MCP 서버
Step 8: Part 1-7 → MCP 라우팅 통합 검증
Step 9: Part 2 → MCP 문서 3건
Step 10: Part 3-1 → 배포 문서
Step 11: Part 3-2 → 테스트 문서
Step 12: Part 3-3 → CI/CD 문서
Step 13: Part 3-4 → 보안 문서
Step 14: Part 3-5 → 운영 문서
Step 15: Part 3-6 → Grafana 대시보드
Step 16: Part 3-7 → 성능 문서
Step 17: Part 3-8 → 온보딩 문서
Step 18: 최종 검증
```

---

## 고려사항

1. **파이프라인 안전성**: 코드 수정 시 기존 import, 워크플로우 흐름이 깨지지 않도록 단계별 검증
2. **기존 패턴 준수**: 새 MCP 서버는 기존 `public_data/`, `maps/` 패턴을 동일하게 따름
3. **불필요 코드 정리**: 리팩토링 과정에서 중복/미사용 코드 발견 시 삭제
4. **문서 포맷 일관성**: 모든 새 문서는 기존 specs/ 문서의 한국어 포맷, 구조 준수
