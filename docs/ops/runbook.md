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

**Critical path**: db -> backend -> nginx (if db is down, backend health fails, nginx returns 502)

> ⚠ 위 맵은 **개발용 `docker-compose.yml`** 기준. 프로덕션(`docker-compose.prod.yml`)에는 nginx 서비스가 **없고**
> (db/redis/migrate/seed/backend/frontend 6개뿐) 호스트의 외부 nginx 가 리버스 프록시를 담당한다 — nginx 관련
> compose 명령은 dev 전용이며, prod 에서는 `sudo nginx -t && sudo systemctl reload nginx` 를 사용한다.

---

## Recovery Procedures

### Scenario 1: Database (PostgreSQL) Down

**Symptoms**: Backend health check fails, nginx returns 502, chat API returns errors.

**Diagnosis**:
```bash
docker compose ps db
docker compose logs --tail=50 db
docker compose exec db pg_isready -U marketscope
```

**Recovery**:
```bash
# 1. Restart the database
docker compose restart db

# 2. Wait for health check to pass
docker compose exec db pg_isready -U marketscope

# 3. Verify backend reconnects automatically
docker compose logs --tail=20 backend | grep -i "database\|connect"

# 4. If data corruption suspected, restore from backup
#    See disaster-recovery.md for full procedure
```

**If restart fails**:
```bash
# Check disk space
docker system df
docker compose exec db df -h /var/lib/postgresql/data

# Check PostgreSQL logs for corruption
docker compose logs db 2>&1 | grep -i "error\|fatal\|panic"

# Last resort: recreate with volume
docker compose down db
docker compose up -d db
docker compose up migrate seed  # re-run init containers
```

---

### Scenario 2: Redis Down

**Symptoms**: Cache misses (slower responses), but service still functional. (Redis is cache-only — rate limiting is not Redis-backed; `rate_limit_*` config values are defined but no route decorator applies them currently.)

**Diagnosis**:
```bash
docker compose ps redis
docker compose exec redis redis-cli ping
docker compose logs --tail=30 redis
```

**Recovery**:
```bash
# 1. Restart Redis
docker compose restart redis

# 2. Verify connectivity
docker compose exec redis redis-cli ping
# Expected: PONG

# 3. Backend auto-reconnects; verify cache is working
docker compose exec redis redis-cli info memory
```

**Note**: Redis is a cache layer. Data loss is acceptable -- cache rebuilds on next request. The backend has fallback logic for Redis unavailability.

---

### Scenario 3: LLM API Down (Anthropic / Google)

**Symptoms**: Chat responses fail or time out, backend logs show LLM API errors.

**Diagnosis**:
```bash
docker compose logs --tail=50 backend | grep -i "llm\|anthropic\|gemini\|claude\|timeout"

# Check if it's a network issue
docker compose exec backend python -c "import httpx; print(httpx.get('https://api.anthropic.com').status_code)"
```

**Recovery**:
```bash
# 1. Check API key validity
docker compose exec backend printenv ANTHROPIC_API_KEY | head -c 10
docker compose exec backend printenv GOOGLE_API_KEY | head -c 10

# 2. Switch LLM provider if one is down
#    Edit .env: LLM_PROVIDER=gemini (or anthropic)
docker compose up -d backend

# 3. If both providers are down, the agent returns a graceful error message
#    No action needed beyond monitoring for provider recovery
```

**Mitigation**: The agent has built-in timeout and retry logic. Users receive a friendly error message when LLM calls fail.

---

### Scenario 4: Full Outage (All Services Down)

**Diagnosis**:
```bash
docker compose ps
docker system df
docker info | grep -i "server version\|storage"
```

**Recovery**:
```bash
# 1. Check Docker daemon is running
docker info

# 2. Bring everything up in dependency order
docker compose up -d db redis
docker compose up migrate seed   # wait for completion
docker compose up -d backend frontend nginx

# 3. Verify health
curl -f http://localhost/health
curl -f http://localhost:8000/health
```

---

### Scenario 5: Data Corruption

**Symptoms**: Incorrect data in reports, SQL errors in logs, inconsistent query results.

**Diagnosis**:
```bash
# Check table integrity
docker compose exec db psql -U marketscope -d marketscope -c "
  SELECT schemaname, relname, n_dead_tup, last_autovacuum
  FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 10;
"

# Check for orphaned records
docker compose exec db psql -U marketscope -d marketscope -c "
  SELECT count(*) FROM floating_population fp
  LEFT JOIN districts d ON fp.district_code = d.district_code
  WHERE d.district_code IS NULL;
"
```

**Recovery**:
```bash
# Option A: Re-run ETL for affected data (Typer CLI — quarter is a positional arg)
docker compose exec backend python -m server.data.etl.runner run 2025Q4

# Only specific tables (valid: districts, floating_pop, estimated_sales, stores, resident_pop)
docker compose exec backend python -m server.data.etl.runner run 2025Q4 --table floating_pop

# Validate after reload (column-content gate, non-zero exit on failure)
docker compose exec backend python -m server.data.etl.runner validate 2025Q4

# Option B: Restore from backup (see disaster-recovery.md)
bash scripts/backup_db.sh                    # backup current state first
# Then restore from a known-good backup
```

---

### Scenario 6: Secret/API Key Leak

**Immediate actions** (within 15 minutes):
```bash
# 1. Rotate the leaked key immediately
#    - Anthropic: https://console.anthropic.com/settings/keys
#    - Google: https://console.cloud.google.com/apis/credentials

# 2. Update .env with new key
nano .env

# 3. Restart backend with new credentials
docker compose up -d backend

# 4. Check git history for accidental commits
git log --all --diff-filter=A -- '*.env' '.env*'
git log -p --all -S 'sk-ant-' -- .  # search for API key patterns

# 5. If key was committed to git, consider repo history rewrite
#    (coordinate with team, use git filter-repo or BFG)

# 6. Review access logs for unauthorized usage during exposure window
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
docker compose down                        # Stop all services (preserve volumes)
docker compose down -v                     # Stop all + delete volumes (DATA LOSS)
```

### Database
```bash
docker compose exec db psql -U marketscope -d marketscope   # SQL shell
docker compose exec db pg_isready -U marketscope             # Health check
docker compose exec db pg_dump -U marketscope marketscope > backup.sql  # Manual backup
```

### Redis
```bash
docker compose exec redis redis-cli ping           # Health check
docker compose exec redis redis-cli info memory     # Memory usage
docker compose exec redis redis-cli dbsize          # Key count
docker compose exec redis redis-cli flushdb         # Clear cache (safe)
```

### Nginx (dev 전용 — prod 는 외부 호스트 nginx)
```bash
docker compose exec nginx nginx -t                  # Test config syntax
docker compose exec nginx nginx -s reload           # Reload config (no downtime)
docker compose logs nginx | grep " 5[0-9][0-9] "    # Find 5xx errors

# prod (호스트 nginx)
sudo nginx -t && sudo systemctl reload nginx
sudo tail -f /var/log/nginx/error.log
```

### Monitoring
```bash
curl -s http://localhost/health | python -m json.tool   # Health check via nginx
curl -s http://localhost:8000/health                     # Direct backend health
docker stats --no-stream                                 # Resource usage snapshot
```

### Langfuse (LLMOps L1)

**Tracing sanity**
```bash
# 1) Container SDK version (compose project 이름 무관하게 서비스명으로 exec —
#    dev project 는 marketscope-dev, prod 는 catchment-area-analysis)
docker compose exec -T backend pip show langfuse | grep Version   # Must be 3.x
docker compose exec -T backend python -c "from langfuse.langchain import CallbackHandler; from langfuse.types import TraceContext; print('ok')"

# 2) /api/chat must return done.trace_id
curl -s -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"message":"강남역 요약"}' --max-time 90 | grep -o '"trace_id":"[^"]*"'

# 3) Backend log must carry real hex
docker compose logs backend --tail 100 | grep agent_done | tail -3
# → trace_id=- 이면 tracing OFF. docs/plan/infra/langfuse-cost-coverage-fix-2026-04-24.md 참조.
```

**Langfuse Cloud — Models pricing 체크리스트**
(집계된 토큰이 있어도 Models 테이블에 모델 가격이 없으면 `cost = 0`. Anthropic 대시보드와 대조 전 필수 확인.)

| 모델 ID | 역할 | 확인 위치 |
|---|---|---|
| `claude-sonnet-4-6` | v2 루프 1순위 (tool-calling) / PAE planner·respond (anthropic mode) | Langfuse Cloud → Settings → Models |
| `gemini-2.5-pro` | v2 fallback 2순위 / PAE respond (gemini mode) | 동일 |
| `gemini-2.5-flash` | v2 fallback 3순위 / PAE planner·evaluator (gemini mode) | 동일 |

> 구 모델 ID `claude-sonnet-4-20250514` 는 은퇴(404) — 2026-06-26 에 `claude-sonnet-4-6` 으로 교체됨. 과거 trace 가격 대조 시에만 참고.

**등록 방법** (Langfuse Cloud UI):
1. Organization → Settings → Models → `+ Add model`
2. Match pattern: 모델 ID 의 prefix (예: `claude-sonnet-4-`)
3. Tokenizer: `openai` 기본 (Anthropic/Gemini 는 근사치, 정확 cost 는 provider 청구 기반)
4. Input/Output price per 1K tokens: Anthropic pricing page 에서 당시 단가 입력
5. 저장 후 신규 trace 부터 cost 계산 반영. 과거 trace 는 자동 backfill 되지 않음.

**Eval harness preflight**
```bash
# 기본 REQUIRE_TRACE=1 — tracing OFF 상태면 자동 abort
python3 scripts/eval/run_quality_sweep.py            # preflight 후 진행
python3 scripts/eval/trust_scenarios.py              # preflight 후 진행
REQUIRE_TRACE=0 python3 scripts/eval/...             # 강제 bypass (load-test 전용)
```
