# 서빙 안정성 & 효율성 체크리스트

> MarketScope AI 서비스의 프로덕션 운용을 위한 안정성/효율성 점검 항목.
> ⚠ 본문 체크박스는 **관리되지 않는다** — 구현 여부와 무관하게 전부 미체크(`[ ]`)로 남아 있으므로
> 개별 항목의 완료 여부를 체크박스로 판단하지 말 것. 완료 현황은 하단 [체크리스트 요약](#체크리스트-요약)
> (2026-04-14 실사 스냅샷)과 `docs/status/current-status.md` 를 기준으로 한다.
> (2026-07-04 문서 정합성 감사 — 기존 범례가 완료/미완료를 동일 기호 `[ ]` 로 정의하던 모순 정정)

---

## 1. API 서버 (FastAPI) 안정성

### 1.1 프로세스 관리
- [ ] Uvicorn worker 수 설정 (CPU 코어 기반, `--workers` 또는 gunicorn+uvicorn)
- [ ] Worker 프로세스 자동 재시작 (gunicorn `--max-requests`, `--max-requests-jitter`)
- [ ] Graceful shutdown 구현 — 진행 중 요청 drain 대기 시간 설정 (`--graceful-timeout 30`)
- [ ] Lifespan 이벤트에서 DB engine / Redis 연결 정리
- [ ] SIGTERM 수신 시 새 요청 거부 + 기존 SSE 스트림 완료 대기
- [ ] PID 파일 또는 프로세스 매니저(systemd/supervisord) 연동

### 1.2 요청 타임아웃
- [ ] 전체 요청 타임아웃 설정 (Uvicorn `--timeout-keep-alive`, 리버스 프록시 레벨)
- [ ] LLM 호출 타임아웃 — fast: 15s, slow: 60s
- [ ] DB 쿼리 타임아웃 — `statement_timeout` (PostgreSQL) 또는 SQLAlchemy `execution_options`
- [ ] Redis 명령 타임아웃 — 현재 `socket_timeout=3s` (적절), `socket_connect_timeout=3s`
- [ ] SSE 스트림 전체 타임아웃 — 장시간 열린 연결 강제 종료 (예: 5분)
- [ ] 외부 API 호출 타임아웃 (공공데이터 API, ETL 시) — httpx timeout 명시

### 1.3 동시성 제어
- [ ] 채팅 동시 처리 제한 — `_MAX_CONCURRENT_CHATS = 20` (세마포어)
- [ ] 세마포어 획득 실패 시 사용자 피드백 (429 Too Many Requests + 재시도 안내)
- [ ] 세마포어 대기 타임아웃 설정 (무한 대기 방지)
- [ ] PDF 생성 등 heavy 작업 별도 세마포어 분리
- [ ] ETL 배치 작업과 API 서빙 리소스 격리 (별도 worker 또는 컨테이너)

### 1.4 CORS & 보안 미들웨어
- [ ] CORS origins 설정 (`cors_origins` 환경 변수)
- [ ] 프로덕션에서 와일드카드(`*`) CORS 금지 — 명시적 도메인만 허용
- [ ] Security headers 미들웨어 (X-Content-Type-Options, X-Frame-Options, CSP)
- [ ] Request body 크기 제한 (채팅 메시지 최대 길이)
- [ ] 요청 ID 미들웨어 — 모든 요청에 UUID 부여, 로그/응답 헤더에 포함

---

## 2. Rate Limiting & 남용 방지

### 2.1 IP 기반 제한
- [ ] Rate limiting 미들웨어 도입 (slowapi 또는 자체 구현)
- [ ] 글로벌 제한: IP당 분당 60회 (일반 API)
- [ ] 채팅 API 제한: IP당 분당 10회 (LLM 비용 고려)
- [ ] 히트맵/폴리곤 API: IP당 분당 30회
- [ ] Rate limit 초과 시 응답: `429 Too Many Requests` + `Retry-After` 헤더
- [ ] Rate limit 카운터 저장소: Redis (다중 worker 공유)

### 2.2 LLM 비용 제어
- [ ] Agent 루프 상한 — v2 agentic loop(현행): `agent_loop_max_iterations=6` / `agent_loop_max_tool_calls=12` / `agent_loop_wall_clock=90s` · 레거시 PAE: `agent_max_rounds=3`
- [ ] 대화 이력 제한 — `max_history_turns=10`, `history_content_limit=300`
- [ ] 세션당 총 LLM 호출 횟수 제한 (예: 50회/세션)
- [ ] 일일 총 LLM API 비용 상한 알림 (예: $50/day 초과 시 슬랙 알림)
- [ ] 비정상 토큰 사용 감지 — 단일 세션에서 과도한 토큰 소비 시 세션 종료
- [ ] Free tier 일일 5회 채팅 제한 구현 (현재 미구현)

### 2.3 악성 입력 방지
- [ ] 사용자 입력 길이 제한 (채팅 메시지 최대 500자)
- [ ] HTML/Script 태그 필터링 (XSS 방지)
- [ ] SQL Injection 방지 — SQLAlchemy ORM 사용 확인 (파라미터 바인딩)
- [ ] Prompt Injection 방어 — 시스템 프롬프트에 경계 지시 포함
- [ ] 반복 동일 메시지 탐지 및 차단 (봇 트래픽 방지)

---

## 3. 데이터베이스 (PostgreSQL + PostGIS)

### 3.1 커넥션 풀링
- [ ] SQLAlchemy async pool 설정 — `pool_size=10`, `max_overflow=20`
- [ ] 풀 소진 시 대기 타임아웃 설정 (`pool_timeout`, 기본 30s → 명시적 설정)
- [ ] 풀 연결 유효성 검사 (`pool_pre_ping=True` 설정 확인)
- [ ] 유휴 연결 재활용 (`pool_recycle` — 예: 1800s, DB 서버 idle timeout 이하)
- [ ] 프로덕션 풀 사이즈 튜닝 — worker 수 × pool_size < max_connections
- [ ] PgBouncer 도입 검토 (다중 worker 환경에서 커넥션 멀티플렉싱)

### 3.2 쿼리 성능
- [ ] PostGIS GIST 인덱스 — `districts.boundary`
- [ ] 복합 인덱스 — `floating_population(district_code, quarter)` 등
- [ ] Slow query 로깅 활성화 — PostgreSQL `log_min_duration_statement = 500` (ms)
- [ ] EXPLAIN ANALYZE로 주요 쿼리 실행 계획 검증
  - [ ] 뷰포트 기반 폴리곤 조회 (`ST_Intersects`)
  - [ ] 유동인구 시간대별 집계
  - [ ] 추정매출 업종별 조회
  - [ ] 점포 이력 조회
- [ ] 대용량 테이블 파티셔닝 검토 (quarter 기준 — floating_population, estimated_sales)
- [ ] 불필요한 N+1 쿼리 제거 — Agent Tool에서 일괄 조회 확인
- [ ] 집계 쿼리 결과 materialized view 또는 캐시 활용

### 3.3 데이터 정합성
- [ ] 외래키 제약 조건 동작 확인 (district_code 참조)
- [ ] NOT NULL 제약 조건 — 필수 필드 누락 방지
- [ ] UNIQUE 제약 조건 — 분기별 중복 데이터 방지 (`district_code + quarter + ...`)
- [ ] ETL 적재 시 트랜잭션 단위 처리 (실패 시 전체 롤백)
- [ ] 데이터 기준 분기 불일치 감지 — 테이블 간 quarter 값 교차 검증

### 3.4 백업 & 복구
- [ ] 자동 백업 스케줄 (pg_dump 또는 WAL 아카이빙, 일 1회)
- [ ] 백업 복원 테스트 (분기 1회)
- [ ] Point-in-Time Recovery (PITR) 설정 (WAL + 베이스 백업)
- [ ] 백업 보관 정책 (최소 30일)
- [ ] 테이블별 데이터 크기 모니터링 (분기별 적재로 지속 증가)

### 3.5 마이그레이션
- [ ] Alembic 마이그레이션 설정
- [ ] 마이그레이션 롤백 스크립트 (`downgrade`) 검증
- [ ] Zero-downtime 마이그레이션 전략 (ALTER TABLE 비차단 확인)
- [ ] 마이그레이션 전 백업 자동화

---

## 4. Redis 캐싱

### 4.1 연결 안정성
- [ ] 연결 실패 시 graceful degradation (캐시 우회, DB 직접 조회)
- [ ] 연결 타임아웃 설정 (`socket_connect_timeout=3s`)
- [ ] 재연결 전략 — 지수 백오프 (현재: 다음 호출 시 재시도, 빈번한 실패 시 과부하 가능)
- [ ] Redis Sentinel 또는 Cluster 구성 (HA 필요 시)
- [ ] 연결 풀링 (`max_connections` 설정, 기본 무제한 → 명시적 제한)

### 4.2 캐시 전략
- [ ] 상권 요약 캐시 TTL 24h (`summary:{district_code}` — quarter 미포함; `report:` 키는 존재하지 않음)
- [ ] 히트맵 캐시 TTL 24h (`heatmap:{time_slot}:{quarter}`)
- [ ] 캐시 히트율 모니터링 — Redis INFO 기반 메트릭 수집
- [ ] 캐시 워밍업 — 서비스 시작 시 인기 상권 top 20 프리로드
- [ ] 캐시 무효화 전략 — 새 분기 데이터 ETL 후 관련 키 flush
- [ ] 캐시 직렬화 크기 제한 — 대형 JSON 응답 압축 (gzip 또는 msgpack)
- [ ] Thundering herd 방지 — 캐시 미스 시 동시 DB 쿼리 singleflight 패턴

### 4.3 메모리 관리
- [ ] Redis `maxmemory` 설정 (예: 512MB)
- [ ] Eviction 정책 설정 (`allkeys-lru` — LRU 기반 만료)
- [ ] 메모리 사용량 알림 (80% 초과 시)
- [ ] 키 네임스페이스 분리 (캐시 vs 세션 vs Rate limit 카운터)

---

## 5. SSE 스트리밍 안정성

### 5.1 연결 관리
- [ ] 클라이언트 연결 해제 감지 (`request.is_disconnected()`)
- [ ] 연결 해제 시 Agent 태스크 취소 (`task.cancel()`)
- [ ] 바운디드 큐로 백프레셔 제어 (`sse_queue_maxsize=256`)
- [ ] SSE 연결 유지 heartbeat — 주기적 `:keep-alive\n\n` 전송 (30초 간격)
- [ ] Nginx/ALB SSE 프록시 설정 — `proxy_buffering off`, `X-Accel-Buffering: no`
- [ ] 리버스 프록시 SSE 타임아웃 — `proxy_read_timeout 300s` (기본 60s 부족)
- [ ] 최대 SSE 연결 수 모니터링 (파일 디스크립터 한계)

### 5.2 스트리밍 품질
- [ ] SSE 이벤트 순서 보장 (thinking → tool → card → text → suggestion → done)
- [ ] 이벤트 전송 실패 시 재시도 로직 (클라이언트 측)
- [ ] `done` 이벤트 미수신 타임아웃 — 클라이언트에서 60s 후 강제 종료
- [ ] 부분 응답이라도 사용자에게 표시 (중간 실패 시 이미 받은 내용 유지)
- [ ] SSE 이벤트 크기 제한 — 단일 `data:` 라인 최대 64KB

### 5.3 프론트엔드 SSE 처리
- [ ] 커스텀 SSE 파서 (표준 EventSource 우회, 내장 type 필드)
- [ ] AbortController 기반 스트림 취소
- [ ] 네트워크 에러 시 사용자 피드백 (연결 끊김 감지 + 재시도 버튼)
- [ ] 자동 재연결 로직 (일시적 네트워크 끊김 시)
- [ ] SSE 파서 에러 시 로깅 + 사용자 알림 (파싱 실패 무시 방지)

---

## 6. 세션 관리

### 6.1 현재 구현 (인메모리)
- [ ] 세션 TTL 30분 (`_SESSION_TTL = 1800`)
- [ ] 주기적 만료 세션 정리 (`_PRUNE_INTERVAL = 60s`)
- [ ] asyncio.Lock으로 동시 접근 보호

### 6.2 프로덕션 개선
- [ ] Redis 기반 세션 저장소로 전환 (서버 재시작 시 세션 유지)
- [ ] 다중 인스턴스 환경 세션 공유 (스케일 아웃 대비)
- [ ] 세션당 메모리 사용량 추정 및 상한 설정
- [ ] 활성 세션 수 메트릭 노출 (`/health/detail`에 이미 포함)
- [ ] 세션 ID 예측 불가능성 보장 (UUID v4 사용 확인)
- [ ] 세션 하이재킹 방지 — IP/User-Agent 바인딩 (선택적)

---

## 7. LLM / AI Agent 안정성

### 7.1 LLM 호출 회복성
- [ ] Anthropic 인증 실패 시 fallback (`_anthropic_valid` 플래그)
- [ ] LLM 파싱 에러 시 규칙 기반 분류 fallback
- [ ] LLM API 429 (Rate Limit) 시 지수 백오프 재시도 (tenacity 활용)
- [ ] LLM API 500/503 에러 시 재시도 (최대 2회, 전체 타임아웃 내)
- [ ] LLM 제공자 failover — Gemini 실패 시 Claude로 자동 전환 (또는 역방향)
- [ ] LLM 응답 유효성 검증 — JSON 파싱 실패, 빈 응답 처리
- [ ] Circuit breaker 패턴 — 연속 N회 실패 시 일시 차단 + 빠른 에러 반환

### 7.2 Tool 실행 안정성
- [ ] Tool별 에러 핸들링 — 실패 시 (tool_name, None, error_str) 반환
- [ ] Tool 병렬 실행 (의존성 레이어별)
- [ ] Tool 실행 개별 타임아웃 (DB 쿼리 기반 — 10s 상한)
- [ ] Tool 실패 시 부분 결과로 응답 생성 (전체 실패 아님)
- [ ] Tool 결과 크기 제한 — 대형 결과 truncation (LLM 컨텍스트 초과 방지)

### 7.3 프롬프트 관리
- [ ] 시스템 프롬프트 버전 관리 (Langfuse 또는 파일 기반)
- [ ] 프롬프트 변경 시 A/B 테스트 프레임워크
- [ ] 프롬프트 길이 모니터링 — 토큰 수 추적 (비용 예측)
- [ ] 할루시네이션 감지 로직 — Tool 결과와 응답 내 수치 교차 검증

---

## 8. 프론트엔드 서빙 효율성

### 8.1 번들 & 로딩 최적화
- [ ] Next.js bundle analyzer로 번들 크기 분석 (`@next/bundle-analyzer`)
- [ ] 코드 스플리팅 확인 — deck.gl, Recharts, react-pdf는 동적 import
- [ ] 지도 SDK 지연 로딩 (Kakao Map Script 비동기 로드)
- [ ] Tree shaking 확인 — 미사용 라이브러리 코드 제거
- [ ] 이미지 최적화 (Next.js `<Image>` 컴포넌트 활용)
- [ ] 폰트 최적화 — `next/font`로 FOUT/FOIT 방지, 서브셋 한글 폰트

### 8.2 지도 렌더링 성능
- [ ] 폴리곤 데이터 심플리파이 (줌 레벨별 LOD — Douglas-Peucker)
- [ ] 뷰포트 밖 폴리곤 언로드 (메모리 절약)
- [ ] 히트맵 데이터 프리로드 확인 (`/heatmap/all` → 클라이언트 캐시)
- [ ] 지도 이벤트 디바운싱 — 팬/줌 시 API 호출 쓰로틀링 (300ms)
- [ ] WebGL 컨텍스트 손실 복구 (deck.gl 장시간 사용 시)
- [ ] 모바일 터치 이벤트 최적화 (패시브 리스너)

### 8.3 클라이언트 캐싱
- [ ] API 응답 HTTP 캐시 헤더 설정
  - 폴리곤 GeoJSON: `Cache-Control: public, max-age=86400`
  - 상권 목록: `Cache-Control: public, max-age=3600`
  - 히트맵 데이터: `Cache-Control: public, max-age=86400`
  - 채팅 API: `Cache-Control: no-store`
- [ ] Service Worker 캐시 (정적 자산 오프라인 지원, 선택적)
- [ ] ETag 기반 조건부 요청 (변경 없으면 304)

### 8.4 렌더링 성능
- [ ] React DevTools Profiler로 불필요한 리렌더 감지
- [ ] Zustand selector 최적화 — 필요한 상태만 구독
- [ ] 대형 리스트 가상화 (채팅 메시지 100개 이상 시 — react-window)
- [ ] Chart 컴포넌트 메모이제이션 (`React.memo`, `useMemo`)
- [ ] Recharts lazy rendering — 뷰포트 진입 시 렌더링

---

## 9. 인프라 & 컨테이너

### 9.1 Docker 설정
- [ ] 멀티스테이지 빌드 (빌더 → 런너, 이미지 경량화)
- [ ] 헬스체크 설정 (DB: pg_isready, Redis: redis-cli ping)
- [ ] 컨테이너 리소스 제한 (`deploy.resources.limits` — CPU, 메모리)
  - Backend: `cpus: 2.0, memory: 2G`
  - Frontend: `cpus: 1.0, memory: 1G`
  - DB: `cpus: 2.0, memory: 4G`
  - Redis: `cpus: 0.5, memory: 512M`
- [ ] 컨테이너 OOM 발생 시 자동 재시작 (`restart: unless-stopped`)
- [ ] 로그 드라이버 설정 — `json-file` + `max-size: 50m` + `max-file: 5` (디스크 폭주 방지)
- [ ] Non-root 사용자로 컨테이너 실행 (`USER nobody`)
- [ ] `.dockerignore` 최적화 (node_modules, .git, __pycache__ 제외 확인)

### 9.2 오케스트레이션
- [ ] 컨테이너 오토 리스타트 정책 (`restart: always` or k8s restartPolicy)
- [ ] 수평 스케일링 준비 — 상태를 Redis로 외부화 (세션, Rate limit 카운터)
- [ ] Rolling update 전략 (무중단 배포)
- [ ] 롤백 자동화 — 배포 실패 시 이전 버전 자동 복원
- [ ] 서비스 디스커버리 — 컨테이너 IP 하드코딩 제거

### 9.3 리버스 프록시 (Nginx/Caddy/ALB)
- [ ] SSL/TLS 종료 (Let's Encrypt 자동 갱신 또는 ACM)
- [ ] HTTP/2 활성화 (멀티플렉싱으로 연결 효율 향상)
- [ ] SSE 프록시 설정: `proxy_buffering off`, `X-Accel-Buffering: no`
- [ ] 정적 파일 직접 서빙 (Next.js `_next/static` → CDN 또는 Nginx)
- [ ] Gzip/Brotli 압축 (JSON API 응답, 정적 자산)
- [ ] Connection keep-alive 설정
- [ ] 요청 크기 제한 (`client_max_body_size 10m`)

---

## 10. 모니터링 & 알림

### 10.1 헬스체크
- [ ] `GET /health` — 기본 상태 확인
- [ ] `GET /health/detail` — DB pool, Redis, 세마포어, 세션 수, Agent 모드
- [ ] 프론트엔드 헬스체크 엔드포인트 (`/api/health`)
- [ ] DB 연결 헬스체크 — 실제 쿼리 실행 (`SELECT 1`)
- [ ] Redis 헬스체크 — PING + 읽기/쓰기 테스트
- [ ] LLM API 헬스체크 — 경량 호출로 응답 가능 여부 확인 (주기적)
- [ ] 헬스체크 주기 및 타임아웃 (k8s: `livenessProbe`, `readinessProbe`, `startupProbe`)

### 10.2 메트릭 수집
- [ ] Prometheus 메트릭 엔드포인트 (`/metrics`) 또는 StatsD 연동
- [ ] **요청 메트릭**:
  - 요청 수 (endpoint별, status code별)
  - 응답 시간 p50/p95/p99
  - 동시 연결 수
  - 에러율 (4xx, 5xx)
- [ ] **SSE 메트릭**:
  - 활성 SSE 연결 수
  - 스트림 평균/최대 지속 시간
  - 첫 토큰 지연 시간 (TTFT) p50/p95
  - 클라이언트 연결 해제 비율
- [ ] **LLM 메트릭**:
  - API 호출 수 (제공자별, 모델별)
  - 토큰 사용량 (input/output)
  - 호출 비용 추정 (일/월 집계)
  - 응답 지연 시간 (제공자별)
  - 실패율 (429, 500, timeout)
- [ ] **DB 메트릭**:
  - 커넥션 풀 사용률 (checkedout / pool_size)
  - 쿼리 실행 시간 분포
  - Slow query 수 (>500ms)
  - 테이블 크기 추이
- [ ] **Redis 메트릭**:
  - 메모리 사용량
  - 캐시 히트율 (`keyspace_hits / (hits + misses)`)
  - 연결 수
  - Eviction 수
- [ ] **Agent 메트릭**:
  - 의도 분류 분포 (summary, compare, recommend 등)
  - Tool 호출 빈도/성공률
  - ReAct 루프 평균 라운드 수
  - Fallback 발동 횟수 (규칙 기반 전환)

### 10.3 로깅
- [ ] 구조화 로깅 (JSON 포맷) — `structlog` 또는 `python-json-logger`
- [ ] 로그 레벨 런타임 변경 가능 (환경 변수 또는 API)
- [ ] 요청별 correlation ID (request_id) 전파 — API → Agent → Tool → DB
- [ ] 민감 정보 마스킹 — API 키, 사용자 입력 중 개인정보
- [ ] 로그 보관 정책 (30일 온라인, 90일 콜드 스토리지)
- [ ] 중앙 로그 수집 (ELK, Datadog, CloudWatch Logs)
- [ ] 프론트엔드 에러 로깅 (Sentry 또는 자체 에러 리포팅)

### 10.4 알림 (Alerting)
- [ ] **P1 (즉시 대응)**:
  - 서비스 다운 (헬스체크 3회 연속 실패)
  - DB 연결 불가
  - 에러율 > 10% (5분 윈도우)
  - SSE 스트림 0건 (서비스 중 채팅 불가)
- [ ] **P2 (1시간 내 대응)**:
  - DB 커넥션 풀 80% 이상 사용
  - Redis 메모리 80% 이상
  - LLM API 실패율 > 20%
  - 응답 시간 p95 > 10초
- [ ] **P3 (일일 리뷰)**:
  - 일일 LLM 비용 임계치 초과
  - 캐시 히트율 < 50%
  - Slow query 일일 100건 이상
  - 디스크 사용률 > 70%
- [ ] 알림 채널: Slack, Email, PagerDuty (심각도별 분리)
- [ ] 알림 중복 제거 (동일 이슈 반복 알림 억제, 30분 cooldown)

---

## 11. 에러 핸들링 & 복구

### 11.1 API 에러 표준화
- [ ] 통일된 에러 응답 포맷:
  ```json
  {
    "error": { "code": "RATE_LIMITED", "message": "...", "request_id": "..." }
  }
  ```
- [ ] HTTP 상태 코드 일관성:
  - 400: 잘못된 입력 (district_code 형식 오류 등)
  - 404: 리소스 없음
  - 429: Rate limit 초과
  - 500: 서버 내부 오류
  - 503: 일시적 서비스 불가 (DB/LLM 장애)
- [ ] 에러 응답에 사용자 친화적 메시지 포함 (내부 스택트레이스 노출 금지)
- [ ] 글로벌 예외 핸들러 (FastAPI `@app.exception_handler`)

### 11.2 Graceful Degradation
- [ ] Redis 장애 시 캐시 우회 (DB 직접 조회)
- [ ] LLM 파싱 실패 시 규칙 기반 fallback
- [ ] DB 장애 시 캐시된 데이터로 읽기 전용 서빙 (가능한 범위)
- [ ] LLM 전체 장애 시 "현재 AI 분석 불가" 메시지 + 기본 데이터 조회만 제공
- [ ] 부분 Tool 실패 시 성공한 데이터로 부분 응답 생성
- [ ] 히트맵/폴리곤 API 독립 — 채팅 장애 시 지도 탐색은 정상 유지

### 11.3 데이터 파이프라인 복구
- [ ] ETL 실패 시 자동 재시도 (최대 3회, 지수 백오프)
- [ ] ETL 부분 실패 시 성공분 커밋 + 실패분 리포팅
- [ ] ETL 롤백 — 잘못된 데이터 적재 시 분기 단위 롤백
- [ ] 마지막 성공 ETL 시점 기록 (데이터 신선도 모니터링)
- [ ] 공공데이터 API 장애 시 이전 분기 데이터로 서빙 지속

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
- [ ] Locust 부하 테스트 시나리오 작성 (locust 이미 의존성에 포함)
  - [ ] 시나리오 1: 폴리곤/상권 조회 (동시 100명, 30초)
  - [ ] 시나리오 2: 채팅 SSE 스트리밍 (동시 20명, 60초)
  - [ ] 시나리오 3: 혼합 (폴리곤 80% + 채팅 20%, 동시 50명)
- [ ] 부하 테스트 결과 기록 및 병목 분석
- [ ] Mock 모드 부하 테스트 (LLM 비용 없이 서버 한계 측정)
- [ ] 점진적 부하 증가 테스트 (ramp-up) — 한계 지점 식별
- [ ] Soak 테스트 (24시간 지속) — 메모리 누수/연결 누수 감지

### 12.3 성능 회귀 방지
- [ ] CI에서 주요 API 응답 시간 벤치마크 자동 실행
- [ ] 성능 기준선 대비 20% 이상 저하 시 PR 경고
- [ ] 프론트엔드 Lighthouse CI (성능 점수 80 이상 유지)

---

## 13. 보안 강화

### 13.1 네트워크
- [ ] HTTPS 강제 (HTTP → HTTPS 301 리다이렉트)
- [ ] HSTS 헤더 (`Strict-Transport-Security: max-age=31536000`)
- [ ] 내부 서비스 포트 외부 노출 차단 (DB:5432, Redis:6379는 내부만)
- [ ] 컨테이너 네트워크 격리 (frontend ↔ backend만, DB ↔ backend만)

### 13.2 시크릿 관리
- [ ] API 키 환경 변수 관리 (.env)
- [ ] .env 파일 Git 커밋 방지 (.gitignore 확인)
- [ ] 프로덕션 시크릿 — AWS Secrets Manager / Vault 등 시크릿 매니저
- [ ] API 키 로테이션 절차 문서화
- [ ] 로그/에러 메시지에 시크릿 노출 방지 검증

### 13.3 의존성 보안
- [ ] `npm audit` / `pip audit` 정기 실행 (CI에 통합)
- [ ] Dependabot 또는 Renovate 활성화 (보안 패치 자동 PR)
- [ ] 컨테이너 이미지 취약점 스캔 (Trivy, Snyk)
- [ ] 라이센스 호환성 검증 (OSS 라이센스 충돌 방지)

---

## 14. CI/CD 파이프라인

### 14.1 빌드 & 테스트
- [ ] PR 머지 전 자동 실행:
  - [ ] Python lint (ruff check) + format (ruff format --check)
  - [ ] TypeScript lint (eslint) + format (prettier --check)
  - [ ] Python 단위 테스트 (pytest)
  - [ ] Frontend 단위 테스트 (vitest 또는 jest)
  - [ ] E2E 테스트 (Playwright — 핵심 시나리오)
  - [ ] Docker 이미지 빌드 검증
- [ ] 테스트 커버리지 임계치 (backend 70%, frontend 50%)
- [ ] 빌드 캐싱 (npm cache, pip cache, Docker layer cache)

### 14.2 배포
- [ ] 스테이징 환경 자동 배포 (main 브랜치 머지 시)
- [ ] 프로덕션 배포 수동 승인 (GitHub Environment protection)
- [ ] 배포 전 스모크 테스트 (헬스체크 + 핵심 API 호출)
- [ ] 배포 후 카나리 검증 (에러율, 응답 시간 5분 모니터링)
- [ ] 롤백 원클릭 자동화 (이전 Docker 이미지 태그로)

### 14.3 환경 관리
- [ ] 환경별 설정 분리 (dev / staging / production)
- [ ] Feature flag 시스템 (환경별 기능 ON/OFF)
- [ ] 데이터베이스 마이그레이션 CI 단계 포함

---

## 15. 재해 복구 & 가용성

### 15.1 RTO / RPO 정의
| 구분 | 목표 | 비고 |
|------|------|------|
| RTO (복구 시간 목표) | < 1시간 | 서비스 다운 → 복구까지 |
| RPO (복구 시점 목표) | < 24시간 | 데이터 손실 허용 범위 — 백업이 일 1회(pg_dump)이므로 24h 가 실현 가능한 목표. [disaster-recovery.md](disaster-recovery.md) 와 정합 |

### 15.2 장애 시나리오별 대응
- [ ] **DB 서버 장애**: 복구 절차 문서화 (백업 복원 → 마이그레이션 → 서비스 재시작)
- [ ] **Redis 장애**: 캐시 우회 모드 자동 전환 확인
- [ ] **LLM API 장애**: Gemini ↔ Claude failover 동작 확인
- [ ] **전체 서비스 장애**: Docker compose 원클릭 복원 (`docker compose up -d`)
- [ ] **데이터 오염**: 특정 분기 데이터 롤백 절차
- [ ] **시크릿 유출**: API 키 즉시 로테이션 + 영향 범위 확인 절차

### 15.3 운영 문서
- [ ] 인시던트 대응 절차서 (who/what/when/how)
- [ ] 온콜 로테이션 (해당 시)
- [ ] 장애 포스트모템 템플릿
- [ ] 서비스 의존성 맵 (장애 전파 경로 시각화)
- [ ] 운영 런북 (Runbook) — 주요 장애 유형별 복구 스텝

---

## 체크리스트 요약

> ⚠ 아래 수치는 **2026-04-14 Phase 1~10 구현 당시의 실사 스냅샷**이며, 본문 체크박스와 동기화되어 있지 않다
> (본문 체크박스는 전부 미체크 상태로 유지되지 않음 — 문서 헤더 참조). 또한 이후 구현분
> (backend pytest 확장, heatmap singleflight, loadtest/ 시나리오 8종, push 자동배포 파이프라인 등)은
> 미반영이라 실제 구현율은 아래보다 높다. 최신 상태는 `docs/status/current-status.md` 기준.

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
*최종 업데이트: 2026-07-04 — 문서 정합성 감사 (범례/요약표 모순 정정, RPO 24h 로 DR 문서와 정합, 캐시 키·Agent 루프 상한 현행화)*
*기준: 2026-04-14 코드베이스 실사 스냅샷 + 2026-07-04 부분 현행화*
