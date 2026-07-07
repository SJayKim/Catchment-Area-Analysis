# Operations Runbook - MarketScope AI

> Per-scenario recovery procedures and quick reference commands.

---

## Service Dependency Map

```
                     [nginx :80]
                      /       \
                     v         v
            [backend :8000]   [frontend :3000]
              /       \
             v         v
      [db :5432]   [redis :6379]
        (PostGIS)    (cache)
             ^
             |
      [migrate] --> [seed]
      (init containers, run once)
```

**Startup order**: db -> redis -> migrate -> seed -> backend -> frontend -> nginx

**Critical path**: db -> backend -> nginx (db down → backend health fails → nginx 502)

> ⚠ 위 맵은 **개발용 `docker-compose.yml`** 기준. 프로덕션(`docker-compose.prod.yml`)에는 nginx 서비스가 없고 (db/redis/migrate/seed/backend/frontend 6개뿐) 호스트의 외부 nginx 가 리버스 프록시를 담당한다 — nginx 관련 compose 명령은 dev 전용, prod 에서는 `sudo nginx -t && sudo systemctl reload nginx` 를 사용한다.

---

## Recovery Procedures

### Scenario 1: Database (PostgreSQL) Down

**Symptoms**: Backend health check fails, nginx returns 502, chat API returns errors.

```bash
# Diagnose
docker compose ps db
docker compose logs --tail=50 db
docker compose exec db pg_isready -U marketscope

# Recovery
docker compose restart db
docker compose exec db pg_isready -U marketscope
docker compose logs --tail=20 backend | grep -i "database\|connect"

# If restart fails — check disk / logs
docker system df
docker compose exec db df -h /var/lib/postgresql/data
docker compose logs db 2>&1 | grep -i "error\|fatal\|panic"

# Last resort: recreate
docker compose down db
docker compose up -d db
docker compose up migrate seed
```

See disaster-recovery.md for full backup/restore procedure.

---

### Scenario 2: Redis Down

**Symptoms**: Cache misses (slower responses), service still functional. Redis is cache-only — no route decorator applies rate limiting currently.

```bash
# Diagnose
docker compose ps redis
docker compose exec redis redis-cli ping
docker compose logs --tail=30 redis

# Recovery
docker compose restart redis
docker compose exec redis redis-cli ping  # Expected: PONG
docker compose exec redis redis-cli info memory
```

Redis data loss is acceptable — cache rebuilds on next request. Backend degrades gracefully.

---

### Scenario 3: LLM API Down (Anthropic / Google)

**Symptoms**: Chat responses fail or time out, backend logs show LLM API errors.

```bash
# Diagnose
docker compose logs --tail=50 backend | grep -i "llm\|anthropic\|gemini\|claude\|timeout"
docker compose exec backend python -c "import httpx; print(httpx.get('https://api.anthropic.com').status_code)"

# Recovery
# 1. Check API key validity
docker compose exec backend printenv ANTHROPIC_API_KEY | head -c 10
docker compose exec backend printenv GOOGLE_API_KEY | head -c 10

# 2. Switch provider if one is down — edit .env: LLM_PROVIDER=gemini (or anthropic)
docker compose up -d backend
```

Agent has built-in timeout and fallback chain (anthropic → gemini-pro → gemini-flash). Users receive a friendly error when all providers fail.

---

### Scenario 4: Full Outage (All Services Down)

```bash
# Diagnose
docker compose ps
docker system df
docker info | grep -i "server version\|storage"

# Recovery — bring up in dependency order
docker compose up -d db redis
docker compose up migrate seed
docker compose up -d backend frontend nginx

# Verify
curl -f http://localhost/health
curl -f http://localhost:8000/health
```

---

### Scenario 5: Data Corruption

**Symptoms**: Incorrect data in reports, SQL errors in logs, inconsistent query results.

```bash
# Diagnose
docker compose exec db psql -U marketscope -d marketscope -c "
  SELECT schemaname, relname, n_dead_tup, last_autovacuum
  FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 10;
"
docker compose exec db psql -U marketscope -d marketscope -c "
  SELECT count(*) FROM floating_population fp
  LEFT JOIN districts d ON fp.district_code = d.district_code
  WHERE d.district_code IS NULL;
"

# Option A: Re-run ETL (quarter is a positional arg)
docker compose exec backend python -m server.data.etl.runner run 2025Q4
# specific table only (districts/floating_pop/estimated_sales/stores/resident_pop)
docker compose exec backend python -m server.data.etl.runner run 2025Q4 --table floating_pop
# Validate after reload (non-zero exit on failure)
docker compose exec backend python -m server.data.etl.runner validate 2025Q4

# Option B: Restore from backup (see disaster-recovery.md)
bash scripts/backup_db.sh
```

---

### Scenario 6: Secret/API Key Leak

```bash
# 1. Rotate immediately
#    - Anthropic: https://console.anthropic.com/settings/keys
#    - Google: https://console.cloud.google.com/apis/credentials

# 2. Update .env and restart backend
nano .env
docker compose up -d backend

# 3. Check git history for accidental commits
git log --all --diff-filter=A -- '*.env' '.env*'
git log -p --all -S 'sk-ant-' -- .

# 4. If key was committed, rewrite history (git filter-repo or BFG)

# 5. Review access logs during exposure window
docker compose logs --since="2h" backend | grep -i "401\|403\|api_key"
```

---

## Quick Reference Commands

### Service Management
```bash
docker compose ps                          # Check all service status
docker compose logs -f backend             # Follow backend logs
docker compose logs --tail=100 nginx       # Last 100 nginx log lines
docker compose restart backend             # Restart single service
docker compose up -d                       # Start all services
docker compose down                        # Stop all (preserve volumes)
docker compose down -v                     # Stop all + delete volumes (DATA LOSS)
```

### Database
```bash
docker compose exec db psql -U marketscope -d marketscope
docker compose exec db pg_isready -U marketscope
docker compose exec db pg_dump -U marketscope marketscope > backup.sql
```

### Redis
```bash
docker compose exec redis redis-cli ping
docker compose exec redis redis-cli info memory
docker compose exec redis redis-cli dbsize
docker compose exec redis redis-cli flushdb   # Clear cache (safe)
```

### Nginx (dev 전용 — prod 는 외부 호스트 nginx)
```bash
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload
docker compose logs nginx | grep " 5[0-9][0-9] "

# prod (호스트 nginx)
sudo nginx -t && sudo systemctl reload nginx
sudo tail -f /var/log/nginx/error.log
```

### Monitoring
```bash
curl -s http://localhost/health | python -m json.tool
curl -s http://localhost:8000/health
docker stats --no-stream
```

---

## Langfuse (LLMOps) 진단

### Tracing sanity
```bash
# 1) SDK 버전 확인 (3.x 필수)
docker compose exec -T backend pip show langfuse | grep Version
docker compose exec -T backend python -c "from langfuse.langchain import CallbackHandler; from langfuse.types import TraceContext; print('ok')"

# 2) /api/chat done 이벤트에 trace_id 포함 여부
curl -s -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"message":"강남역 요약"}' --max-time 90 | grep -o '"trace_id":"[^"]*"'

# 3) 백엔드 로그의 실제 hex 값 확인
docker compose logs backend --tail 100 | grep agent_done | tail -3
# trace_id=- 이면 tracing OFF. docs/plan/infra/langfuse-ops-hardening-2026-07-06.md 참조.
```

### 무음사망(silent death) 3단 진단

tracing 이 조용히 꺼지는 사고(SDK 드리프트·auth 실패 등)는 LLM 과금은 계속되는데 Langfuse 만 0건이 된다.

```bash
# 1단 — 배선 상태
curl -s http://localhost:8000/api/health/detail | python -c "import sys,json; print(json.load(sys.stdin)['langfuse'])"
# 정상: {'enabled': True, 'tracer_valid': True, 'client_initialized': True, 'sampling_rate': 1.0}

# 2단 — 누적 카운터 (0 이 정상, 증가 추세면 사고)
curl -s http://localhost:8000/metrics | python -c "import sys,json; print(json.load(sys.stdin)['langfuse_trace_missing_total'])"

# 3단 — 개별 요청 trace_id 확인 (위 Tracing sanity #3 과 동일)
docker compose logs backend --tail 100 | grep agent_done | tail -3
```

**판정**: ① `enabled=false` = 키 미설정(의도된 off) ② `enabled=true, tracer_valid=false` = SDK import/초기화 사망 → 컨테이너 SDK 버전 확인 후 재빌드/재기동 ③ `tracer_valid=true` 인데 카운터 증가 = handler 생성 실패·auth 오류 반복 → backend 로그에서 `langfuse` 경고 grep.

**샘플링 semantics** — `LANGFUSE_SAMPLING_RATE` 는 `should_sample()` 한 곳에서만 적용 (SDK `sample_rate` 는 이중 샘플링 문제로 2026-07-06 제거). rate<1.0 운용 시 `langfuse_trace_missing_total` 이 (1-rate) 비율만큼 자연 증가하는 기준선을 감안하고 추세로 판단할 것 (rate=1.0 에서는 0 이 정상).

### score-config 등록 (user_feedback) — Langfuse Cloud UI 1회 수작업

1. 프로젝트 → Settings → Scores → `+ New score config`
2. Name: `user_feedback` / Data type: NUMERIC / Min -1, Max 1
3. v2 자동 score 6종(`numeric_match`/`tool_error_rate`/`abstention_triggered`/`trust_corrective_applied`/`trust_fallback_triggered`/`trust_masked_count`)은 SDK 가 직접 생성 — config 등록 불필요.

### Langfuse Cloud — Models pricing 체크리스트

토큰이 있어도 Models 테이블에 가격이 없으면 `cost = 0`. Anthropic 대시보드 대조 전 필수 확인.

| 모델 ID | 역할 |
|---|---|
| `claude-sonnet-4-6` | v2 루프 1순위 / PAE planner·respond (anthropic mode) |
| `gemini-2.5-pro` | v2 fallback 2순위 / PAE respond (gemini mode) |
| `gemini-2.5-flash` | v2 fallback 3순위 / PAE planner·evaluator (gemini mode) |

> 구 모델 ID `claude-sonnet-4-20250514` 는 은퇴(404) — 2026-06-26 에 `claude-sonnet-4-6` 으로 교체됨.

**등록 방법** (Langfuse Cloud UI):
1. Organization → Settings → Models → `+ Add model`
2. Match pattern: 모델 ID prefix (예: `claude-sonnet-4-`)
3. Tokenizer: `openai` 기본 (근사치, 정확 cost 는 provider 청구 기반)
4. Input/Output price per 1K tokens: Anthropic pricing page 참조
5. 저장 후 신규 trace 부터 적용 (과거 trace backfill 없음)

### Eval harness preflight
```bash
# REQUIRE_TRACE=1 기본 — tracing OFF 면 자동 abort
python3 scripts/eval/run_quality_sweep.py
python3 scripts/eval/trust_scenarios.py
REQUIRE_TRACE=0 python3 scripts/eval/...   # 강제 bypass (load-test 전용)
```
