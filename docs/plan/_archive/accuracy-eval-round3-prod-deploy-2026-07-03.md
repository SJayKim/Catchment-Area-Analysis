# Plan — Accuracy Eval Round 3 (v2 Real) → Gate → Prod 배포 + Redis Flush (2026-07-03)

## Context

`feat/agentic-loop-v2`(모델주도 루프 + Trust Kernel)가 main에 머지 완료(`ecfdf17`, 트리 = v2 tip byte-동일). checkpoint 잔여 2항목을 실행한다:

1. **Real accuracy eval S1~S8 v2 재실행** — Round 2(2026-06-10, PAE, 평균 9.4·S7=5.0 날조)를 baseline으로 v2 루프의 KPI 재측정
2. **prod 배포**(marketscope.robitlabs.co.kr) + **report 캐시 flush 필수** — `929885b` '일평균' 라벨 fix가 Redis 24h 캐시(`summary:*`)에 구 문구로 잔존하므로

**Gate (사용자 확정: 조건부 자동)**: eval gate 4항목(평균 ≥9.0 · 시나리오별 R2 점수 이상 · 날조 0 · S7 ≥9.3) **전부 통과 → 보고 없이 바로 배포 진행. 하나라도 미달 → 정지, verdict 보고 후 사용자 결정 대기.**

**메모리 교훈 인용**: `feedback_redis_cache_serves_old_card_text`(flush 선행) · `feedback_compose_env_block_overrides_env_file`(호스트 셸 env가 compose 오버라이드) · `feedback_env_convention_inverted`(.env=prod, .env.dev 빌드 전 격리) · `feedback_eval_district_code_hardcode`(message-only 전송) · `feedback_sse_hallucination_needs_db_gt`(DB GT 교차검증) · `feedback_anthropic_model_id_retired_404`(키/모델 사전 liveness) · `feedback_npx_playwright_global_cache`(로컬 바이너리 직접 호출) · `feedback_e2e_pgdata_stale_seed`(신선도 마커) · `feedback_stale_container_vs_source`(컨테이너 재시작 후 검증) · `feedback_marketscope_sse_format`(data: 임베드 type)

**환경 전제**: eval 타깃 = **e2e 스택 :8002** (이미 v2+anthropic+USE_MOCK=false로 17h 기동 중, `./server` bind-mount = 현 main 트리). `:8000`은 finance_agent(타 프로젝트)가 점유 — dev 스택 사용 불가. prod = 원격 Linux(`ssh prod`, `/opt/marketscope`).

**Step 0 (프로젝트 관례)**: 본 plan을 `docs/plan/qa/accuracy-eval-round3-prod-deploy-2026-07-03.md`에 표준 5섹션 형식으로 저장 후 실행 시작.

---

## Item 1 — Accuracy Eval Round 3 (e2e 스택 :8002, ~1.5~2h)

### Phase A — Preflight (~10분)

| # | Step → Verify |
|---|---|
| A1 | `docker ps --filter name=marketscope-e2e` → backend(8002)/db(15432)/redis(16379) 모두 Up healthy |
| A2 | `docker exec marketscope-e2e-backend-1 printenv \| grep -E 'USE_MOCK\|LLM_PROVIDER\|AGENT_LOOP\|LANGFUSE'` → `USE_MOCK=false`, `LLM_PROVIDER=anthropic`, `AGENT_LOOP_VERSION` 부재(→코드 기본 v2, `config.py:81`), Langfuse 키 공란(**의도됨** — e2e에선 `done.trace_id` 부재가 정상, 채점 항목 아님) |
| A3 | `curl -s localhost:8002/api/health/detail` → `use_mock:false, llm_provider:anthropic` |
| A4 | 데이터 신선도(06-25 재시드 마커): e2e db psql로 `SUM(population) WHERE pop_type='worker' AND quarter='2025Q4'` **>0** + `count(*) FROM category_metadata WHERE aliases IS NOT NULL` **=32** (psql 유저명은 compose 환경에서 확인) |
| A5 | 코드 드리프트 가드: e2e db에서 6개 GT 코드(3120189 강남역/3120043 서울역/3120103 홍대/3120052 성수역/3120053 건대/3120028 명동) name↔code 일치 확인. ※ `verify_district_codes.py`는 dev 컨테이너명 하드코딩이라 미사용 |
| A6 | `command -v python3` — Git Bash에 없으면 스크립트 실행 전 `python3() { python "$@"; }; export -f python3` shim (스크립트 수정 금지) |
| A7 | `git status -sb` → main == origin/main, drift 2건(settings.local.json, tech-stack-rationale.md)만 — **절대 add 금지** |

### Phase B — Prep (~5분)

| # | Step → Verify |
|---|---|
| B1 | `docker restart marketscope-e2e-backend-1` (bind-mount + no-reload → 클린 재import 보험) → healthy 대기 후 `docker exec ... python -c "from server.config import settings; print(settings.agent_loop_version)"` = `v2` |
| B2 | **eval 전 e2e 캐시 flush**: `docker exec marketscope-e2e-backend-1 python scripts/flush_cache.py` (컨테이너 WORKDIR=/app, 실경로 `server/scripts/flush_cache.py`; 5 prefix: sales/compare/recommend/simulation/summary) → redis-cli scan `summary:*` 빈 결과 |
| B3 | **GT 스냅샷** (현 DB 기준 — R2 숫자 재사용 금지): 6개 코드 월매출(`SUM(monthly_sales)/3`, 2025Q4) + S7용 유동인구(`SUM(total_pop)`, 홍대/성수). ⚠ R2는 06-25 데이터fix(worker 0→472만·unit_price·aliases) **이전** 실행 → S1/S2/S6 수치 차이는 데이터 기인 delta로 주석, 회귀 아님 |

### Phase C — 실행 + 파싱 (~15분)

| # | Step → Verify |
|---|---|
| C1 | `BASE=http://localhost:8002 OUT=docs/qa/runs/eval-round3-2026-07-03 bash scripts/eval/run_accuracy_round2.sh` (WITH_CODES=0 기본 유지 — R2와 동일 message-only, entity-linking 검증) → 9개 `.sse` 생성, curl 에러 0 |
| C2 | 절단 체크(curl 90s == v2 wall_clock 90s 리스크): 각 `.sse`에 `done` 이벤트 존재 grep → 전부 존재 |
| C3 | (절단 시만) 해당 시나리오 수동 재실행 `curl -sN --max-time 180 ...` — **S7은 S7-pre부터 같은 fresh session으로 2턴 재실행** |
| C4 | `python scripts/eval/parse_sse.py docs/qa/runs/eval-round3-2026-07-03 > .../_parsed.md` → 9 섹션 생성 |
| C5 | **S7 재현율**: fresh session으로 S7-pre→S7 1회 추가 실행(총 2회) — R2 verdict 권고 반영 |

### Phase D — 채점 + Verdict (~60~90분, 수동)

| # | Step → Verify |
|---|---|
| D1 | S1~S8 채점: 6축(Depth/Context/Derived/Structure/Actionable/Accuracy) × 2pt → ×10/12. 모든 tool-backed 수치를 B3 GT와 교차검증(±10% + 출처 attribution) |
| D2 | **S7 정밀**: (a) 유동인구 tool 재호출 또는 (b) 직전 compare 카드 실값 충실 인용 확인. 날조·물리모순(파생값>peak) 발견 시 Accuracy=0 |
| D3 | `_verdict.md` 작성 — R2 verdict 구조 미러: R1/R2/R3 KPI 비교 테이블 + 시나리오별 6축 + DB 교차검증 + gate 판정. `done.trace_id` 부재는 "expected(e2e Langfuse 공란)" 명기 |

### GATE — 조건부 자동 (사용자 확정)

- **전부 충족 → Item 2 즉시 진행**: 평균 ≥9.0 AND 시나리오별 R2 점수 이상 AND 날조 0 AND S7 ≥9.3
- **하나라도 미달 → 정지**: verdict + status 기록 후 사용자 보고 (S7이 날조 0인데 9.3 미만인 케이스 포함 — 배포 여부는 사용자 결정)

---

## Item 2 — Prod 배포 + Redis Flush (~1.5h, cutover 다운타임 ~15초)

### Phase E — Dev측 사전 (~15분)

| # | Step → Verify |
|---|---|
| E1 | eval 산출물 + plan 문서 + status 커밋/푸시: `git add docs/qa/runs/eval-round3-2026-07-03 docs/plan/qa/... docs/status/current-status.md` → commit → `git push origin main`. drift 2건 제외 확인. `NEW_HEAD` 기록 |
| E2 | `ssh prod 'echo ok && df -h / \| tail -1'` → 접속 ok + 디스크 ≥10GB |

### Phase F — Prod preflight (~10분)

| # | Step → Verify |
|---|---|
| F1 | `ssh prod 'cd /opt/marketscope && git fetch && git status -sb && git rev-parse --short HEAD'` → 클린 트리, 현 HEAD를 롤백 ref로 기록 |
| F2 | `.env`(=prod 관례) 키 확인(값 비노출): `LLM_PROVIDER=anthropic`(⚠ compose 기본값 gemini — .env 누락 시 조용히 오배포), `USE_MOCK=false`, `NEXT_PUBLIC_API_URL=https://marketscope.robitlabs.co.kr`(루트, /api 금지), `ANTHROPIC_API_KEY`/`NEXT_PUBLIC_KAKAO_MAP_KEY`/`LANGFUSE_*` 존재 |
| F3 | **키 liveness**(死키 사고 재발 방지): prod .env의 키로 `curl https://api.anthropic.com/v1/models` → 200 (401 → 빌드 전 STOP) |
| F4 | `.env.dev` 존재 여부 확인 → G3/G5 분기 |
| F5 | 배포 셸 env 오염 체크: `env \| grep -E 'USE_MOCK\|AGENT_LOOP\|LLM_PROVIDER\|LANGFUSE'` → 비면 OK, 있으면 unset (호스트 셸이 .env를 이김) |

### Phase G — Pull·스냅샷·빌드·마이그레이션 (~20~25분, 무중단)

| # | Step → Verify |
|---|---|
| G1 | `git pull --ff-only origin main` → HEAD == `NEW_HEAD`, `git merge-base --is-ancestor ecfdf17 HEAD` OK |
| G2 | 롤백 태그: `docker tag catchment-area-analysis-{backend,frontend}:latest ...:prev-2026-07-03` (태깅 전 `docker images`로 실제 이미지명 확인) |
| G3 | `.env.dev` 존재 시 `mv .env.dev .env.dev.predeploy-2026-07-03.bak` (next.config.mjs가 .env.dev 우선 → dev값 번들 bake-in 방지) |
| G4 | `docker compose -f docker-compose.prod.yml build backend frontend migrate seed` (**모든 명령에 -f 필수** — dev compose와 project명 충돌 이력) → exit 0, 새 이미지 ID ≠ prev |
| G5 | `.env.dev` 원복 |
| G6 | `docker compose -f docker-compose.prod.yml run --rm migrate` → v2 머지엔 alembic 없음 = no-op 확인 (version_num 불변) |

### Phase H — Cutover + Flush (~5분)

| # | Step → Verify |
|---|---|
| H1 | (F5 재확인 후) `docker compose -f docker-compose.prod.yml up -d backend frontend` → 둘 다 Up |
| H2 | `localhost:8000/health` 200 (≤60s 폴링) + `localhost:3200/` 200 |
| H3 | `docker compose ... exec backend python -c "...print(settings.agent_loop_version, settings.llm_provider, settings.use_mock)"` → `v2 anthropic False` |
| H4 | **필수 flush**: `docker compose -f docker-compose.prod.yml exec backend python scripts/flush_cache.py` → 5 prefix flush + redis scan `summary:*` 빈 결과. 범위 결정: 기본 5-prefix로 충분(머지 diff의 캐시 접점 = district_summary.py → `summary:*`). heatmap/preview는 diff 무접점 — I단계서 stale 발견 시에만 `--prefix` 추가 |

### Phase I — 라이브 smoke (~15~20분)

| # | Step → Verify |
|---|---|
| I1 | curl P-체크: 도메인 200 / `search=강남역`→3120189 / preview / health detail(`use_mock:false, llm_provider:anthropic`) |
| I2 | chat SSE(도메인 직접): "강남역 상권 요약해줘" → thinking→tool→card→text→`done`(**trace_id 존재** — prod는 Langfuse 라이브) + summary 카드에 교정된 라벨('일평균' 아닌 '분기') 확인 |
| I3 | prod-smoke Playwright(dev 머신, **로컬 바이너리**): `cd frontend && ./node_modules/.bin/playwright test prod-smoke --project=chromium --project=mobile-iphone --project=mobile-galaxy --project=tablet-ipad --reporter=line` → P1~P9 green (번들 dev-URL 스캔 0건 포함) |
| I4 | 10분 관찰: prod backend 로그 error/traceback 0 + Langfuse에 production trace 유입 |

### Phase J — 기록 (~15분)

| # | Step → Verify |
|---|---|
| J1 | `docs/qa/runs/prod-deploy-2026-07-03.md` 배포 런로그(P-체크 결과·이미지 ID·타이밍) + status-update(eval R3 + 배포) |
| J2 | 커밋/푸시 → porcelain에 drift 2건만 잔존 |

---

## Rollback (prod)

1. `docker tag ...:prev-2026-07-03 ...:latest` (backend+frontend) → `up -d --force-recreate backend frontend`
2. health 200 + chat SSE 확인 → **flush 재실행** (v2가 쓴 캐시를 구 이미지가 서빙하지 않도록)
3. DB 롤백 불필요(migrate no-op). `AGENT_LOOP_VERSION=pae` env 스위치는 보조 수단일 뿐 — **prev-* 이미지 태그가 1차 롤백**

## 리스크 요약

| 리스크 | 완화 |
|---|---|
| curl 90s == v2 wall_clock 90s → SSE 절단 | C2 done-grep → C3 개별 재실행(--max-time 180), 스크립트 수정 금지 |
| 캐시 poisoning('일평균' 구 문구) | eval 전 e2e flush(B2) + 배포 후 prod flush(H4) + I2 라벨 육안 확인 |
| 호스트 셸 env가 compose 오버라이드 | F5/H1에서 배포 셸 직접 grep·unset |
| 死 ANTHROPIC_API_KEY | F3 빌드 전 liveness 200 게이트 |
| .env.dev bake-in | G3 격리 → 빌드 → G5 원복 + I3 번들 스캔 |
| compose project명 충돌 | prod의 모든 compose 명령에 `-f docker-compose.prod.yml` |
| S7 v2 미검증(R2=5.0) | D2 정밀채점 + C5 2회 재현율 + gate에 S7 ≥9.3 명시(미달 시 정지·보고) |
| R2 대비 GT 변동(06-25 데이터fix) | B3 현 DB 스냅샷 기준 채점, delta 주석 |

## 산출물

- `docs/qa/runs/eval-round3-2026-07-03/` — S*.sse(+S7 2회차) · `_parsed.md` · `_verdict.md`(R1/R2/R3 비교)
- `docs/plan/qa/accuracy-eval-round3-prod-deploy-2026-07-03.md` — 본 plan 프로젝트 표준형 저장
- `docs/qa/runs/prod-deploy-2026-07-03.md` — 배포 런로그
- `docs/status/current-status.md` 2026-07-03 항목 갱신
- prod에 `prev-2026-07-03` 롤백 태그 2종

## 총 소요 추정: ~3~3.5h (수동 채점 60~90분이 지배)
