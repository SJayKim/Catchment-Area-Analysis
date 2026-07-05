# 서비스 운영 부하 테스트 계획 — MarketScope AI

> 2026-07-04 문서 정합성 감사: Phase 1~3(인프라·계측·SSE 클라이언트) 및 시나리오 파일 8종(`loadtest/scenarios/a~h`)은 구현 완료 확인 — 의존성은 dev 가 아닌 `[loadtest]` extra(`server/pyproject.toml`)로, Locust User 클래스는 `SseUser` 대신 `ChatUser`/`GreetingFloodUser` 로 구현됨. Phase 4~7 부하 **실행**·리포트는 실행 기록 미확인(체크박스 미체크 유지).

## Context

MarketScope AI는 동시 다수 사용자가 AI 챗봇으로 상권 분석을 요청하는 서비스입니다.
현재 E2E 기능 테스트(42 시나리오)는 있지만, **다수 동시 사용자 환경에서의 운영 검증이 전무**합니다.

**현재 동시성 제어 현황**:
- `_chat_semaphore = Semaphore(20)` — 최대 20개 동시 채팅
- DB 커넥션 풀: 10 + overflow 20 = 최대 30
- PAE 모드: per-request 그래프 (격리 OK), ReAct 모드: singleton (LangChain 내부 격리)
- SSE 큐: bounded 256, LLM timeout: fast 15s / slow 60s
- 인메모리 세션 (서버 재시작 시 유실), Redis graceful degradation

> ⚠ 2026-07-04 정정: 위 "PAE 모드 / ReAct 모드" 서술은 작성 시점 기준. 현행 기본 실행 경로는 **v2 agentic loop + Trust Kernel**(`config.py` `agent_loop_version="v2"` → `agent/runtime.py` 가 비-mock 프로바이더에서 `agent/loop/engine.py` 로 디스패치)이며, PAE 그래프는 Mock 모드·`AGENT_LOOP_VERSION=pae` 롤백용 레거시 폴백이다. 'ReAct 모드'는 런타임에서 선택 불가(레거시 흔적만 잔존). v2 루프도 per-request 격리이고, 도구는 요청 내 **직렬** 실행이다.

**목표**: 동시 사용자 환경에서 정상 동작, 세션 격리, 장애 복구를 검증하는 부하 테스트 인프라 구축 + 실행

---

## 핵심 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `server/pyproject.toml` | `locust>=2.29`, `httpx>=0.27` dev 의존성 추가 |
| `server/server/config.py` | `llm_provider: "mock"` 옵션 추가 |
| `server/server/agent/graph.py` | `_create_llm()` 에 mock provider 분기 (`FakeListChatModel`) |
| `server/server/api/routes/chat.py` | `/api/health/detail` 엔드포인트 추가 (pool/semaphore/session 메트릭) |
| `server/server/main.py` | health detail에 engine pool status 노출 |

## 신규 파일

```
loadtest/
  README.md                         # 실행 가이드
  locustfile.py                     # 메인 Locust 시나리오 (SseUser 클래스)
  sse_client.py                     # 커스텀 SSE 클라이언트 (비표준 포맷 대응)
  scenarios/
    a_basic_summary.py              # 시나리오 A: 점진적 증가 (1→5→10→20명)
    b_mixed_intent.py               # 시나리오 B: 의도 혼합 (5종 랜덤)
    c_greeting_shortcut.py          # 시나리오 C: 인사 단축 (50명)
    d_semaphore_saturation.py       # 시나리오 D: 세마포어 포화 (25명)
    e_spike.py                      # 시나리오 E: 스파이크 (5→30→5명)
    f_session_isolation.py          # 시나리오 F: 세션 격리
    g_client_disconnect.py          # 시나리오 G: 중도 끊김
    h_redis_failure.py              # 시나리오 H: Redis 장애
  results/                          # 결과 저장 (gitignored)
docs/plan/infra/load-test-plan.md   # 이 계획 문서의 정식 저장본
```

---

## 구현 체크리스트

### Phase 1: 인프라 셋업

- [x] **1.1** `server/pyproject.toml` dev 의존성에 `locust>=2.29`, `httpx>=0.27` 추가 (2026-07-04 감사: `[loadtest]` extra 로 구현 확인)
- [x] **1.2** `loadtest/` 디렉토리 생성 + `README.md` (실행 가이드)
- [x] **1.3** `.gitignore`에 `loadtest/results/` 추가
- [x] **1.4** `config.py`에 `llm_provider: "mock"` 분기 추가
- [x] **1.5** `graph.py`의 `_create_llm()`에 mock provider → `FakeListChatModel` (토큰당 20ms sleep, 한국어 고정 텍스트 반환)
- [ ] **1.6** Mock LLM으로 PAE 전체 그래프 정상 동작 확인 (수동 1회)

### Phase 2: 계측 코드 추가

- [x] **2.1** `chat.py`에 `/api/health/detail` GET 엔드포인트 추가 (2026-07-04 감사에서 구현 확인):
  ```json
  {
    "semaphore_available": 18,
    "semaphore_max": 20,
    "active_sessions": 5,
    "db_pool_checkedout": 3,
    "db_pool_size": 10,
    "db_pool_overflow": 0,
    "redis_connected": true
  }
  ```
- [x] **2.2** `main.py`에서 engine pool status를 health detail에 노출하는 헬퍼 등록 (`app.state.db_engine` 보관으로 구현)

### Phase 3: SSE 클라이언트 + Locust User 클래스

- [x] **3.1** `loadtest/sse_client.py` 작성 (2026-07-04 감사에서 구현 확인)
  - `httpx.AsyncClient`로 `POST /api/chat` (stream=True)
  - `data:` 접두사 파싱 → JSON 내부 `type` 필드 추출 (비표준 SSE 포맷)
  - 이벤트 카운터: thinking/tool/tool_end/text/card/suggestion/done
  - 타이밍: TTFB, 첫 text 이벤트, done 시각
  - 60초 타임아웃 (done 미수신 시 에러)
- [x] **3.2** `loadtest/locustfile.py` — `SseUser(User)` 클래스 (2026-07-04 감사: `ChatUser`/`GreetingFloodUser` 클래스명으로 구현 확인)
  - `on_start`: httpx 클라이언트 초기화, 고유 session_id 생성
  - SSE 응답 시간을 Locust `request_meta` 이벤트로 보고
  - TTFB / 전체 응답 시간 / 이벤트 수 태그 구분

### Phase 4: Mock 모드 부하 테스트 시나리오

#### 시나리오 A — 기본 요약 (점진적 증가)
- [ ] **4A.1** 요청: `"강남역 상권 분석해줘"` (D3001)
- [ ] **4A.2** 설정: 1→5→10→20명, 각 60초, ramp-up 30초
- [ ] **4A.3** 합격 기준:
  - 10명 동시: p95 TTFB < 3초, p95 전체 < 30초
  - 20명 동시: p95 TTFB < 5초, 에러율 < 5%
  - 모든 응답에 `done` 이벤트 포함

#### 시나리오 B — 의도 혼합
- [ ] **4B.1** 5종 의도 랜덤 (요약 30% / 비교 20% / 추천 20% / 리스크 15% / 시뮬레이션 15%)
- [ ] **4B.2** 10명 동시, 120초 지속
- [ ] **4B.3** 합격 기준: 에러율 < 3%, 카드 타입이 의도와 일치

#### 시나리오 C — 인사 단축 경로
- [ ] **4C.1** 요청: `"안녕하세요"` (Agent 스킵)
- [ ] **4C.2** 50명 동시, 30초
- [ ] **4C.3** 합격 기준: p99 전체 < 500ms, 에러율 0%

#### 시나리오 D — 세마포어 포화
- [ ] **4D.1** Mock LLM sleep 5초로 설정, 25명 동시
- [ ] **4D.2** 합격 기준:
  - 20명까지 정상, 21~25번째는 대기 후 처리
  - HTTP 5xx 0건
  - 클라이언트 disconnect 시 세마포어 정상 해제

#### 시나리오 E — 스파이크
- [ ] **4E.1** 5명 안정 → 30초 후 30명 급증 → 30초 유지 → 5명 복귀
- [ ] **4E.2** 합격 기준: 스파이크 중 에러율 < 10%, 복귀 후 p95 TTFB 정상화

### Phase 5: 동시성/격리 검증

#### 시나리오 F — 세션 격리
- [ ] **5F.1** 10명이 각각 다른 상권코드(D3001~D3005 반복)로 동시 요청
- [ ] **5F.2** 합격 기준:
  - User 1(강남역) 응답에 "홍대" 미포함 (다른 세션 데이터 누수 0)
  - 각 `map_cmd`에 올바른 district_code

#### 시나리오 G — PAE/ReAct 격리
- [ ] **5G.1** PAE 모드에서 5명 × 5종 의도 동시 → 카드 타입 일치 확인
- [ ] **5G.2** ReAct 모드에서 5명 동시 → 상태 오염 없음 확인

> ⚠ 2026-07-04 정정: 'ReAct 모드'는 현행 코드에서 선택 불가 — 본 시나리오를 실행한다면 **v2 루프(기본) vs PAE(Mock 폴백)** 격리 검증으로 대체해야 한다. 참고로 구현된 `loadtest/scenarios/g_client_disconnect.py`/`h_redis_failure.py` 는 본 계획의 I/J 시나리오에 대응하며, 계획의 G/H/K/L 전용 시나리오 파일은 없다.

#### 시나리오 H — 동일 세션 경합
- [ ] **5H.1** 같은 session_id로 3명 동시 요청
- [ ] **5H.2** 합격 기준: 서버 크래시 없음, lock이 race condition 방지

### Phase 6: 장애 복구 시나리오

#### 시나리오 I — 클라이언트 중도 Disconnect
- [ ] **6I.1** SSE 수신 2초 후 연결 강제 끊기, 10명 동시
- [ ] **6I.2** 합격 기준: 로그에 disconnect 감지, 세마포어 해제, 메모리 누수 없음

#### 시나리오 J — Redis 장애
- [ ] **6J.1** (Real 모드) `docker compose pause redis` → 5명 요청 → `unpause`
- [ ] **6J.2** 합격 기준: 서비스 미중단, DB fallback 동작, Redis 복구 후 캐시 자동 복원

#### 시나리오 K — DB 커넥션 풀 포화
- [ ] **6K.1** (Real 모드) 15명 동시 요약 (60 DB 쿼리 vs 풀 30)
- [ ] **6K.2** 합격 기준: pool overflow 대기로 처리, 5xx 없음

#### 시나리오 L — SSE 큐 백프레셔
- [ ] **6L.1** 느린 클라이언트 (이벤트 수신 후 1초 sleep), 5명 동시
- [ ] **6L.2** 합격 기준: Queue(256) 가득 차도 OOM 없음, 최종 완료됨

### Phase 7: 결과 리포트

- [ ] **7.1** `loadtest/results/run-{date}/` 디렉토리에 Locust CSV + HTML 저장
- [ ] **7.2** 시나리오별 Pass/Fail 요약 테이블 작성
- [ ] **7.3** `docs/qa/load-test-report-{date}.md` 리포트 문서 생성

---

## 종합 SLA (합격 기준 요약)

| 메트릭 | 10명 동시 | 20명 동시 | 비고 |
|--------|-----------|-----------|------|
| TTFB p95 | < 3초 | < 5초 | Mock LLM 기준 |
| 전체 응답 p95 | < 30초 | < 45초 | LLM 스트리밍 포함 |
| 에러율 | < 1% | < 5% | 5xx + done 미수신 |
| 세션 격리 위반 | **0건** | **0건** | 절대 불가 |
| 메모리 누수 | 0 | 0 | RSS 복귀 확인 |

---

## 실행 순서

```
Phase 1 (인프라) → Phase 2 (계측) → Phase 3 (SSE 클라이언트)
    → Phase 4 (Mock 부하 A~E) → Phase 5 (격리 F~H)
    → Phase 6 (장애 I~L) → Phase 7 (리포트)
```

- Phase 4~5는 Mock 모드 (`USE_MOCK=true`, `LLM_PROVIDER=mock`)
- Phase 6의 J, K는 Real 모드 (`USE_MOCK=false`, Docker DB+Redis 필요)
- 총 예상 시나리오: **12개** (A~L)

---

## 검증 방법

1. **Mock LLM 동작 확인**: `LLM_PROVIDER=mock`으로 backend 기동 → curl로 `/api/chat` SSE 응답 확인
2. **Locust 실행**: `cd loadtest && locust -f locustfile.py --host=http://localhost:8002`
3. **Health detail 모니터링**: 부하 중 `GET /api/health/detail` 로 pool/semaphore 상태 실시간 확인
4. **Docker logs**: `docker compose logs -f backend` 로 에러/경고 실시간 모니터링
5. **결과 수집**: Locust `--csv=results/run --html=results/report.html`

## 알려진 제약 사항

- 인메모리 세션: 서버 재시작 시 유실 (향후 Redis 세션 저장 필요)
- LLM API rate limit: per-provider semaphore 미구현 (Real 모드에서 과도 호출 시 429 가능)
- Uvicorn 단일 워커: 프로덕션에서는 `--workers 4` 이상 필요
- DB 풀(30) < PAE 병렬 Tool(20×4=80): 대기 발생 가능 (graceful)

> ⚠ 2026-07-04 정정: 병렬 4-Tool 산식은 PAE 기준. 현행 v2 루프는 도구를 요청 내 직렬 실행하므로 순간 동시 DB 쿼리 압력은 이보다 낮다 (PAE 는 Mock 폴백 경로에서만 유효).
