# 서빙 안정성 & 효율성 체크리스트

> MarketScope AI 프로덕션 운용 안정성/효율성 점검. 체크박스는 관리되지 않으므로 완료 현황은 [체크리스트 요약](#체크리스트-요약)(2026-04-14 스냅샷)과 `docs/status/current-status.md` 기준.
> (2026-07-04 감사 — 범례/요약표 모순 정정)

---
## 1. API 서버 (FastAPI) 안정성
### 1.1 프로세스 관리
- [ ] Uvicorn worker 수 설정 (CPU 코어 기반, `--workers` 또는 gunicorn+uvicorn)
- [ ] Worker 자동 재시작 (gunicorn `--max-requests`, `--max-requests-jitter`)
- [ ] Graceful shutdown — 진행 중 요청 drain 대기 (`--graceful-timeout 30`)
- [ ] Lifespan 이벤트에서 DB engine / Redis 연결 정리
- [ ] SIGTERM 수신 시 새 요청 거부 + 기존 SSE 스트림 완료 대기
- [ ] PID 파일 또는 프로세스 매니저(systemd/supervisord) 연동

### 1.2 요청 타임아웃
- [ ] 전체 요청 타임아웃 (Uvicorn `--timeout-keep-alive`, 리버스 프록시 레벨)
- [ ] LLM 호출 타임아웃 — fast: 15s, slow: 60s
- [ ] DB 쿼리 타임아웃 — PostgreSQL `statement_timeout` 또는 SQLAlchemy `execution_options`
- [ ] Redis 명령 타임아웃 — `socket_timeout=3s`, `socket_connect_timeout=3s`
- [ ] SSE 스트림 전체 타임아웃 — 최대 5분 강제 종료
- [ ] 외부 API 호출 타임아웃 (공공데이터 ETL 시 httpx timeout 명시)

### 1.3 동시성 제어
- [ ] 채팅 동시 처리 제한 — `_MAX_CONCURRENT_CHATS = 20` (세마포어)
- [ ] 세마포어 획득 실패 시 429 + 재시도 안내, 세마포어 대기 타임아웃 설정
- [ ] PDF 등 heavy 작업 별도 세마포어 분리, ETL 배치와 API 서빙 리소스 격리

### 1.4 CORS & 보안 미들웨어
- [ ] CORS origins — `cors_origins` 환경 변수, 프로덕션 와일드카드 금지
- [ ] Security headers 미들웨어 (X-Content-Type-Options, X-Frame-Options, CSP)
- [ ] Request body 크기 제한 (채팅 최대 500자), 요청 ID 미들웨어 (UUID, 응답 헤더 포함)
---
## 2. Rate Limiting & 남용 방지
### 2.1 IP 기반 제한
- [ ] Rate limiting 미들웨어 (slowapi 또는 자체 구현)
- [ ] 글로벌: IP당 분당 60회 / 채팅 API: 분당 10회 / 히트맵·폴리곤: 분당 30회
- [ ] 초과 시 `429 Too Many Requests` + `Retry-After` 헤더, 카운터 저장소: Redis

### 2.2 LLM 비용 제어
- [ ] Agent 루프 상한 — v2: `agent_loop_max_iterations=6` / `agent_loop_max_tool_calls=12` / `agent_loop_wall_clock=90s` · PAE(legacy): `agent_max_rounds=3`
- [ ] 대화 이력 제한 — `max_history_turns=10`, `history_content_limit=300`
- [ ] 세션당 LLM 호출 횟수 제한 (예: 50회/세션), 일일 비용 상한 알림 ($50/day)
- [ ] 비정상 토큰 소비 감지 시 세션 종료, Free tier 일일 5회 제한 (현재 미구현)

### 2.3 악성 입력 방지
- [ ] 사용자 입력 길이 제한 (최대 500자), HTML/Script 태그 필터링 (XSS 방지)
- [ ] SQL Injection 방지 — SQLAlchemy ORM 파라미터 바인딩 확인
- [ ] Prompt Injection 방어 — 시스템 프롬프트에 경계 지시 포함, 반복 동일 메시지 탐지·차단
---
## 3. 데이터베이스 (PostgreSQL + PostGIS)
### 3.1 커넥션 풀링
- [ ] SQLAlchemy async pool — `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`, `pool_recycle=1800s`
- [ ] 풀 소진 대기 타임아웃 (`pool_timeout` 명시), worker 수 × pool_size < DB max_connections
- [ ] PgBouncer 도입 검토 (다중 worker 환경 커넥션 멀티플렉싱)

### 3.2 쿼리 성능
- [ ] PostGIS GIST 인덱스 — `districts.boundary`, 복합 인덱스 `floating_population(district_code, quarter)` 등
- [ ] Slow query 로깅 — `log_min_duration_statement = 500` ms
- [ ] EXPLAIN ANALYZE — `ST_Intersects` 폴리곤·유동인구 집계·추정매출·점포 이력
- [ ] 대용량 테이블 파티셔닝 검토 (floating_population, estimated_sales — quarter 기준)
- [ ] N+1 쿼리 제거, 집계 결과 materialized view/캐시 활용

### 3.3 데이터 정합성
- [ ] 외래키(district_code), NOT NULL, UNIQUE 제약 조건 확인
- [ ] ETL 트랜잭션 단위 처리 (실패 시 전체 롤백), 테이블 간 quarter 값 교차 검증

### 3.4 백업 & 복구
- [ ] 자동 백업 스케줄 (pg_dump 또는 WAL 아카이빙, 일 1회), 보관 최소 30일
- [ ] 백업 복원 테스트 (분기 1회), PITR 설정 (WAL + 베이스 백업)

### 3.5 마이그레이션
- [ ] Alembic 마이그레이션 + `downgrade` 롤백 검증
- [ ] Zero-downtime 마이그레이션 (ALTER TABLE 비차단 확인), 마이그레이션 전 백업 자동화
---
## 4. Redis 캐싱
### 4.1 연결 안정성
- [ ] Redis 실패 시 graceful degradation (캐시 우회, DB 직접 조회)
- [ ] 연결 타임아웃 `socket_connect_timeout=3s`, 지수 백오프 재연결 (1→2→4→60s)
- [ ] Redis Sentinel/Cluster (HA 필요 시), `max_connections` 명시적 제한

### 4.2 캐시 전략
- [ ] 상권 요약 TTL 24h (`summary:{district_code}`), 히트맵 TTL 24h (`heatmap:{time_slot}:{quarter}`)
- [ ] 캐시 히트율 모니터링 (Redis INFO), ETL 후 관련 키 flush, 대형 JSON 압축 (gzip/msgpack)
- [ ] 캐시 워밍업 (인기 상권 top 20 프리로드), Thundering herd 방지 — singleflight (heatmap 라우트 적용)

### 4.3 메모리 관리
- [ ] `maxmemory` 설정 (예: 512MB), Eviction 정책 `allkeys-lru`
- [ ] 메모리 80% 초과 시 알림, 키 네임스페이스 분리 (캐시/세션/Rate limit)
---
## 5. SSE 스트리밍 안정성
### 5.1 연결 관리
- [ ] 클라이언트 연결 해제 감지 (`request.is_disconnected()`) + Agent 태스크 취소
- [ ] 바운디드 큐 백프레셔 (`sse_queue_maxsize=256`), SSE heartbeat 25s 간격 `:keep-alive\n\n`
- [ ] Nginx SSE — `proxy_buffering off`, `X-Accel-Buffering: no`, `proxy_read_timeout 300s`
- [ ] 최대 SSE 연결 수 모니터링 (파일 디스크립터 한계)

### 5.2 스트리밍 품질
- [ ] SSE 이벤트 순서 보장 (v2: thinking→tool→tool_end→card→text→suggestion→done) — 이벤트 집합 상세: [../architecture/backend.md](../architecture/backend.md) §4
- [ ] `done` 미수신 시 클라이언트 120s idle 타임아웃 abort
- [ ] 부분 응답 표시 (중간 실패 시 이미 수신한 내용 유지), 단일 `data:` 라인 최대 64KB

### 5.3 프론트엔드 SSE 처리
커스텀 async generator 파서, AbortController 취소, 자동 재연결 상세 → [../architecture/frontend.md](../architecture/frontend.md) §5 참조.
---
## 6. 세션 관리
### 6.1 현재 구현 (인메모리)
- [ ] 세션 TTL 30분 (`_SESSION_TTL = 1800`), 만료 정리 주기 60s (`_PRUNE_INTERVAL`), asyncio.Lock 동시 보호

### 6.2 프로덕션 개선
- [ ] Redis 기반 세션 저장소 전환 (서버 재시작 시 유지, 스케일 아웃 대비)
- [ ] 세션당 메모리 상한 (`session_memory_limit_bytes=524288`), 활성 세션 수 `/health/detail` 노출
- [ ] 세션 ID UUID v4 보장, IP/User-Agent 바인딩 (선택적)
---
## 7. LLM / AI Agent 안정성
> Agent v2 루프 · Trust Kernel · PAE 폴백 구조 상세 → [../architecture/agent.md](../architecture/agent.md)
### 7.1 LLM 호출 회복성
- [ ] Anthropic 실패 시 Gemini fallback (`_anthropic_valid` 플래그)
- [ ] LLM 파싱 에러 시 규칙 기반 분류 fallback
- [ ] LLM API 429 — 지수 백오프 재시도 (tenacity), 500/503 — 최대 2회
- [ ] Circuit breaker — 연속 5회 실패 시 60s OPEN → HALF_OPEN
- [ ] LLM 응답 유효성 검증 (JSON 파싱 실패, 빈 응답 처리)

### 7.2 Tool 실행 안정성
- [ ] Tool별 에러 핸들링 — 실패 시 `(tool_name, None, error_str)` 반환
- [ ] Tool 타임아웃 15s (`tool_execution_timeout`), 결과 크기 제한 8000자 (`tool_result_max_chars`)
- [ ] Tool 실패 시 성공 데이터로 부분 응답 생성

### 7.3 프롬프트 관리
- [ ] 시스템 프롬프트 버전 관리 (Langfuse 또는 파일 기반), 토큰 수 추적 (비용 예측)
- [ ] 할루시네이션 감지 — Trust Kernel 수치 교차 검증 (`trust_numeric_tolerance=0.05`, ±5%)
---
## 8. 프론트엔드 서빙 효율성
### 8.1 번들 & 로딩 최적화
- [ ] Next.js bundle analyzer로 번들 크기 분석 (`@next/bundle-analyzer`)
- [ ] 코드 스플리팅 — deck.gl, Recharts, react-pdf 동적 import, Tree shaking 확인
- [ ] 지도 SDK 지연 로딩, `next/image`, `next/font` (서브셋 한글, FOUT 방지)

### 8.2 지도 렌더링 성능
- [ ] 폴리곤 심플리파이 (줌 레벨별 LOD), 뷰포트 밖 언로드
- [ ] 히트맵 프리로드 (`/heatmap/all` → 클라이언트 캐시), 지도 이벤트 디바운싱 300ms
- [ ] WebGL 컨텍스트 손실 복구 (deck.gl), 모바일 터치 패시브 리스너

### 8.3 클라이언트 캐싱
- [ ] API 캐시 헤더 — 폴리곤·히트맵 `Cache-Control: public, max-age=86400` / 상권 목록 `max-age=3600` / 채팅 `no-store`
- [ ] ETag 기반 조건부 요청 (304)

### 8.4 렌더링 성능
- [ ] Zustand selector 최적화, Chart `React.memo`/`useMemo`, Recharts lazy rendering
- [ ] 대형 메시지 리스트 가상화 (100개 이상 시 react-window)
---
## 9. 인프라 & 컨테이너
### 9.1 Docker 설정
- [ ] 멀티스테이지 빌드, Non-root 사용자 (`USER nobody`), `.dockerignore` 최적화
- [ ] 헬스체크 (DB: `pg_isready`, Redis: `redis-cli ping`)
- [ ] 컨테이너 리소스 제한: Backend(cpus:2.0/2G)·Frontend(cpus:1.0/1G)·DB(cpus:2.0/4G)·Redis(cpus:0.5/512M)
- [ ] 재시작 정책 `restart: unless-stopped`, 로그 드라이버 `json-file` + `max-size:50m` + `max-file:5`

### 9.2 오케스트레이션
- [ ] 수평 스케일링 준비 — 세션/Rate limit 카운터 Redis 외부화
- [ ] Rolling update 전략 (무중단 배포), 배포 실패 시 자동 롤백

### 9.3 리버스 프록시 (Nginx)
- [ ] SSL/TLS 종료 (Let's Encrypt 자동 갱신), HTTP/2 활성화
- [ ] SSE: `proxy_buffering off`, `X-Accel-Buffering: no`, `proxy_read_timeout 300s`
- [ ] 정적 파일 직접 서빙, Gzip/Brotli 압축, `client_max_body_size 10m`
---
## 10. 모니터링 & 알림
### 10.1 헬스체크
- [ ] `GET /health` (기본), `GET /health/detail` (DB pool·Redis·세션 수·agent_mode·langfuse 블록)
- [ ] DB `SELECT 1`, Redis PING+읽기/쓰기 테스트
- [ ] 헬스체크 주기/타임아웃 설정 (k8s: livenessProbe/readinessProbe/startupProbe)

### 10.2 메트릭 수집
- [ ] **요청**: endpoint·status 별 요청 수, p50/p95/p99 응답 시간, 동시 연결, 에러율(4xx/5xx)
- [ ] **SSE**: 활성 연결 수, TTFT p50/p95, 스트림 지속 시간, 클라이언트 해제 비율
- [ ] **LLM**: 제공자·모델별 API 호출 수, input/output 토큰, 비용 추정(일/월), 실패율(429/500/timeout)
- [ ] **DB**: 커넥션 풀 사용률, 쿼리 시간 분포, slow query 수(>500ms), 테이블 크기 추이
- [ ] **Redis**: 메모리 사용량, 캐시 히트율 (`keyspace_hits/(hits+misses)`), eviction 수
- [ ] **Agent**: 의도 분류 분포, Tool 호출 빈도/성공률, 루프 평균 이터레이션, fallback 횟수

### 10.3 로깅
- [ ] 구조화 로깅 JSON 포맷 (structlog), 요청별 correlation ID (request_id) — API→Agent→Tool→DB 전파
- [ ] 민감 정보 마스킹 (API 키, 개인정보), 로그 보관 30일 온라인/90일 콜드
- [ ] 중앙 로그 수집 (ELK/Datadog/CloudWatch), 프론트엔드 에러 로깅 (Sentry)

### 10.4 알림
- [ ] **P1 즉시**: 헬스체크 3회 연속 실패 · DB 연결 불가 · 에러율>10%(5분) · SSE 스트림 0건
- [ ] **P2 1시간**: DB 풀 80%+ · Redis 메모리 80%+ · LLM 실패율>20% · p95>10s
- [ ] **P3 일일**: LLM 비용 임계치 초과 · 캐시 히트율<50% · slow query 100건+ · 디스크>70%
- [ ] 알림 채널: Slack/Email/PagerDuty (심각도별), 30분 cooldown
---
## 11. 에러 핸들링 & 복구
### 11.1 API 에러 표준화
- [ ] 통일된 에러 응답: `{"error": {"code": "RATE_LIMITED", "message": "...", "request_id": "..."}}`
- [ ] HTTP 상태 코드 — 400 잘못된 입력 / 404 없음 / 429 Rate limit / 500 서버 오류 / 503 일시 불가
- [ ] 에러 응답에 사용자 친화적 메시지 (스택트레이스 미노출), 글로벌 예외 핸들러

### 11.2 Graceful Degradation
- [ ] Redis 장애 → 캐시 우회(DB 직접 조회)
- [ ] LLM 파싱 실패 → 규칙 기반 fallback, LLM 전체 장애 → "AI 분석 불가" + 기본 조회만
- [ ] 부분 Tool 실패 → 성공 데이터로 부분 응답
- [ ] 히트맵/폴리곤 API 독립 — 채팅 장애 시 지도 탐색 정상 유지

### 11.3 데이터 파이프라인 복구
- [ ] ETL 실패 시 자동 재시도 (최대 3회, 지수 백오프), 성공분 커밋+실패분 리포팅
- [ ] ETL 롤백 — 잘못된 데이터 분기 단위 롤백, 공공데이터 API 장애 시 이전 분기 데이터로 서빙 지속
---
## 12. 성능 벤치마크 & 부하 테스트
### 12.1 응답 시간 목표
| 엔드포인트 | 목표 p50 | 목표 p95 | 목표 p99 |
|-----------|---------|---------|---------|
| `GET /api/districts` | < 50ms | < 200ms | < 500ms |
| `GET /api/map-data/polygons` | < 100ms | < 500ms | < 1s |
| `GET /api/map-data/heatmap` | < 100ms | < 300ms | < 500ms |
| `POST /api/chat` (TTFT) | < 2s | < 4s | < 8s |
| `POST /api/chat` (전체) | < 10s | < 20s | < 30s |
| `GET /health` | < 10ms | < 50ms | < 100ms |

### 12.2 부하 테스트
- [ ] Locust 시나리오: 폴리곤/상권 조회(동시 100명·30s) · 채팅 SSE(동시 20명·60s) · 혼합(폴리곤 80%+채팅 20%·동시 50명)
- [ ] 부하 테스트 결과 기록·병목 분석, Mock 모드 부하 테스트 (LLM 비용 없이 한계 측정), Soak 테스트 24h — 메모리/연결 누수 감지

### 12.3 성능 회귀 방지
- [ ] CI에서 주요 API 응답 시간 벤치마크 자동 실행, 기준선 대비 20% 저하 시 PR 경고, Lighthouse CI (성능 점수 80 이상)
---
## 13. 보안 강화
### 13.1 네트워크
- [ ] HTTPS 강제 (HTTP→HTTPS 301), HSTS `Strict-Transport-Security: max-age=31536000`
- [ ] 내부 포트 외부 노출 차단 (DB:5432, Redis:6379), 컨테이너 네트워크 격리

### 13.2 시크릿 관리
- [ ] API 키 환경 변수 관리, .env Git 커밋 방지 (.gitignore)
- [ ] 프로덕션 시크릿 매니저 (AWS Secrets Manager/Vault), API 키 로테이션 절차 문서화
- [ ] 로그/에러 메시지 시크릿 노출 방지

### 13.3 의존성 보안
- [ ] `npm audit` / `pip audit` CI 통합, Dependabot/Renovate 활성화
- [ ] 컨테이너 이미지 취약점 스캔 (Trivy/Snyk), 라이센스 호환성 검증
---
## 14. CI/CD 파이프라인
### 14.1 빌드 & 테스트
- [ ] PR 자동 실행: ruff lint/format · ESLint+Prettier · pytest · Playwright E2E · Docker 빌드 검증
- [ ] 테스트 커버리지 임계치 (backend 70%, frontend 50%), 빌드 캐싱 (npm/pip/Docker layer)

### 14.2 배포
- [ ] 스테이징 자동 배포 (main 머지 시), 프로덕션 수동 승인 (GitHub Environment protection)
- [ ] 배포 전 스모크 테스트, 배포 후 카나리 검증 (에러율·응답 시간 5분)
- [ ] 롤백 원클릭 자동화 (이전 Docker 이미지 태그)

### 14.3 환경 관리
- [ ] 환경별 설정 분리 (dev/staging/production), Feature flag 시스템
- [ ] DB 마이그레이션 CI 단계 포함
---
## 15. 재해 복구 & 가용성
### 15.1 RTO / RPO 정의
| 구분 | 목표 | 비고 |
|------|------|------|
| RTO (복구 시간 목표) | < 1시간 | 서비스 다운 → 복구까지 |
| RPO (복구 시점 목표) | < 24시간 | pg_dump 일 1회 기준 — [disaster-recovery.md](disaster-recovery.md) 정합 |

### 15.2 장애 시나리오별 대응
- [ ] **DB 장애**: 백업 복원 → 마이그레이션 → 서비스 재시작 절차 문서화
- [ ] **Redis 장애**: 캐시 우회 모드 자동 전환 확인
- [ ] **LLM API 장애**: Gemini ↔ Claude failover 동작 확인
- [ ] **전체 장애**: `docker compose up -d` 원클릭 복원
- [ ] **데이터 오염**: 특정 분기 롤백 절차, **시크릿 유출**: 즉시 로테이션 + 영향 범위 확인

### 15.3 운영 문서
- [ ] 인시던트 대응 절차서, 장애 포스트모템 템플릿, 서비스 의존성 맵 (장애 전파 경로 시각화), 운영 런북 → [runbook.md](runbook.md)

---
## 체크리스트 요약

> ⚠ 2026-04-14 실사 스냅샷. 이후 추가 구현(backend pytest·heatmap singleflight·push 자동배포 등)은 미반영 — 실제 구현율은 아래보다 높다. 최신 현황: `docs/status/current-status.md`.

| 카테고리 | 전체 | 완료 | 미완료 | 구현율 |
|---------|------|------|--------|--------|
| 1. API 서버 | 16 | 12 | 4 | 75% |
| 2. Rate Limiting | 14 | 10 | 4 | 71% |
| 3. 데이터베이스 | 22 | 12 | 10 | 55% |
| 4. Redis | 13 | 8 | 5 | 62% |
| 5. SSE 스트리밍 | 14 | 11 | 3 | 79% |
| 6. 세션 관리 | 9 | 6 | 3 | 67% |
| 7. LLM/Agent | 14 | 12 | 2 | 86% |
| 8. 프론트엔드 | 19 | 13 | 6 | 68% |
| 9. 인프라/컨테이너 | 18 | 12 | 6 | 67% |
| 10. 모니터링/알림 | 37 | 8 | 29 | 22% |
| 11. 에러 핸들링 | 15 | 12 | 3 | 80% |
| 12. 성능 벤치마크 | 12 | 0 | 12 | 0% |
| 13. 보안 | 11 | 8 | 3 | 73% |
| 14. CI/CD | 15 | 7 | 8 | 47% |
| 15. 재해 복구 | 14 | 7 | 7 | 50% |
| **합계** | **243** | **148** | **95** | **61%** |

---

*작성일: 2026-04-14*
*최종 업데이트: 2026-07-04 — 범례/요약표 모순 정정, RPO 24h DR 정합, 캐시 키·Agent 루프 상한 현행화*
*기준: 2026-04-14 코드베이스 실사 스냅샷 + 2026-07-04 부분 현행화*
