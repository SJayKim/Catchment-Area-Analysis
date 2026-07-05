# 데이터 신뢰성 확보 — 적재 결손 3건 근본원인 수정 + 재발방지 검증 게이트

## Context

2026-06-25 데이터 정합성 감사(DB 직접 쿼리 + 서울 열린데이터 API 대조 + 워크플로우 적대검증)에서,
구조적 무결성(행수·FK·geometry·분기 균일·매출 단위)은 견고하나 **사용자 노출에 영향을 주는 적재 결손 3건**이
시드(2026-04-03) 이후 **약 3개월 잠복**해 있었음을 발견했다. 세 결손 모두 "행은 존재하나 컬럼 내용이
전부 0/NULL"이라, 기존 검증(행수·FK·boundary NULL%)을 통과하며 조용히 살아남았다.

**시스템적 근본원인:** ETL 사후검증(`runner.py::_validate_data`)이 *행 존재*만 확인하고
*컬럼 내용*(NULL 비율, all-zero/all-constant, 값 범위, 소스 대조)을 검사하지 않는다.
→ 신뢰성 확보 = **(A) 결손 3건 수정·재적재 + (B) 컬럼 내용 검증 게이트로 재발 차단**.

범위(사용자 합의): Part A+B 둘 다 · aliases 핵심 ~30종 큐레이션 + fallback · `avg_startup_cost` defer.

### 관련 메모리 교훈 (Plan Context 인용)
- `project_data_integrity_2026-06-25` — 본 결손을 surfaced 한 감사 결과(worker 0 / aliases·단가 NULL / 유동·점포 1분기 stale).
- `feedback_etl_api_column_rename` — **직접 근본원인**. 서울 API 컬럼명은 변경/지표별 상이(`MDW`→`MDWK` 등). ETL 전 API 1행 dump 로 key 직접 확인. worker = `MAG_{N}_WRC_POPLTN_CO`.
- `project_sales_quarterly_unit` — `estimated_sales.monthly_sales` 분기누적 → Repository read 시 ÷3. 검증 게이트의 값-범위 sanity 에 반영.
- `feedback_pg_stat_live_tup_stale_zero` — 재적재 후 행수 검증은 `pg_stat` 아닌 `COUNT(*)` 로(ANALYZE 전 추정치 0 위장).
- `feedback_psql_wrong_column_silent_empty` — 검증 쿼리 컬럼 오타가 빈 결과로 위장. `\d table` 로 컬럼명 확정 후 집계.
- `feedback_stale_container_vs_source` — 재적재/재시드 후 docker exec find/COUNT 로 live 검증. "반영 완료" 라벨 신뢰 금지.
- `feedback_python_utf8_windows` — ETL/검증 스크립트는 `encoding='utf-8'` + `PYTHONIOENCODING=utf-8`.
- `feedback_compose_force_recreate_cascade` — 단일 서비스 재생성 시 `--no-deps`(seed/migrate cascade 회피).

---

## Scope

| 포함 | 제외 |
|---|---|
| RC1 worker 필드 매핑 수정 + 재적재 | RC4 `avg_startup_cost` 채움 (Real 미사용 → defer) |
| RC2 `default_unit_price` 백필 (seed) | resident API transform 경로 수정 (CSV 사용, dormant — 주석만) |
| RC3 aliases 핵심 ~30종 + fallback | 폴리곤/StorW API 복구 (서울측 ERROR-500, out of scope) |
| Part B 컬럼 내용 검증 게이트 + pytest 회귀 + CI | 2026Q1 분기 갱신 (별도 사이클 — 전 테이블 동시 적재 필요) |
| 시드 덤프 재생성 | |

---

## Design — 근본원인 (코드 검증 완료)

### RC1 — 직장인구(worker) 19,692행 전량 0  [P1, F03/F07 노출]
`server/server/data/etl/transformers.py:277-313` (`transform_resident_pop`, worker 분기)
```python
else:  # worker
    male_suffix = "MAG_POPLTN_CO"      # ← resident 필드명 재사용 (틀림)
    female_suffix = "FAG_POPLTN_CO"
...
male_key = f"{age_prefix}_{male_suffix}"  # = "AGRDE_10_MAG_POPLTN_CO" (존재 안 함)
male_val = _safe_int(raw.get(male_key))   # None → 0
```
직장인구 API(`VwsmTrdarWrcPopltnQq`) **실제 필드**(2025Q4 행 확인):
남 `MAG_{N}_WRC_POPLTN_CO`, 여 `FAG_{N}_WRC_POPLTN_CO` (N ∈ 10/20/30/40/50/60_ABOVE).
→ **접미사 교체로는 불충분**(`AGRDE_10_MAG_WRC_POPLTN_CO`도 틀림). worker 전용 키 빌더로 분리.
resident 가 정상인 이유 = CSV 경로(`csv_collector.py::load_resident_pop_csv`), worker 만 API transform 경로.

**Fix**: worker 분기에서 `male_key = f"MAG_{n}_WRC_POPLTN_CO"`, `female_key = f"FAG_{n}_WRC_POPLTN_CO"`
(n = age_prefix 에서 `AGRDE_` 제거, 예 "10","60_ABOVE"). resident 분기 무변경 + "API path dormant(CSV 사용)" 주석.

### RC2 — `default_unit_price` 100% NULL  [P2, F09 시뮬레이션]
`alembic/002_add_default_unit_price.py:27-40` 의 `UPDATE ... WHERE major_category=...` 백필이
`alembic upgrade head` 시점엔 **category_metadata 가 비어 있어**(seed 는 stores 적재 후 실행) **0행 no-op**.
이후 `seed_category_metadata.py:54-63` INSERT 가 컬럼 누락 → 영구 NULL.
값 출처 = `_UNIT_PRICES = {"외식":12000,"서비스":25000,"소매":15000}`.

**Fix**: `_UNIT_PRICES` 를 `seed_category_metadata.py` 로 공유, INSERT/`ON CONFLICT DO UPDATE` 에
`default_unit_price = :price`(major 기준, 기본 15000) 포함. 추가 방어선: `simulation.py:85
get_default_unit_price` 에 NULL→major 기본값 fallback.

### RC3 — `aliases` 100% NULL  [P2, Real 한국어 카테고리 매칭]
`alembic/003_add_category_aliases.py`(컬럼만) + seed INSERT 누락. **source of truth 자체가 부재**,
`category_aliases` 테이블도 없음. `category_resolver.py::load_from_db` 가 `metadata.aliases`(콤마분리)+
`learned_aliases`(1행) 로드 → NULL 시 Real 키워드 인덱스가 카테고리명만으로 구성.

**Fix**: `data/etl/category_aliases.json`(code→["별칭",...]) 신규 — **핵심 ~30종**(외식/소매/서비스 빈도 상위:
스벅·카공·편의점·약국 등 콜로키얼)만. seed INSERT 에 aliases(콤마조인, 없으면 NULL) 포함.
나머지 ~70종은 카테고리명 + learned_aliases 누적 + LLM fallback 위임.

### RC0 (시스템) — 컬럼 내용 검증 부재
`runner.py::_validate_data:212-272` = 행수 + FK(floating만) + boundary NULL%. Loader = NULL/값 제약 없음.
런타임 `numeric_sanity` = LLM 출력 vs tool 대조("데이터가 진짜 0" 미탐). Trust 하네스 = 5상권 주요지표만.

---

## Checklist (원자적·검증가능)

- [x] **C1** `transformers.py` worker 키 빌더 분리 → 단위테스트(worker raw 샘플 → population>0, 12행, 합=API TOT).
- [x] **C2** `seed_category_metadata.py` `_UNIT_PRICES` 공유 + INSERT/UPDATE 에 `default_unit_price` 포함.
- [x] **C3** `data/etl/category_aliases.json` 핵심 ~30종 작성 + seed INSERT 에 aliases 결합.
- [x] **C4** `simulation.py:85` NULL→major 기본단가 fallback (2차 방어선).
- [x] **C5** 라이브 2025Q4 DB 재적재: `runner run 2025Q4 --table resident_pop` + category 재시드.
- [x] **C6** `runner.py::_validate_data` 확장: per-column NULL 비율, all-zero/all-constant(`bool_and`,`count(distinct)=1`), 값범위 sanity(매출/인구 음수 0, percentile). 실패 시 비-0 exit.
- [x] **C7** `scripts/audit/p1_api_vs_db.py`(5상권×3서비스 대조) 를 validate/CI 흐름에 연결.
- [x] **C8** `server/tests/test_data_integrity.py` 신규: worker 비-0, aliases/default_unit_price NULL 임계, 분기 균일. (`avg_startup_cost` 는 의도된 NULL → 체크 제외)
- [x] **C9** `.github/workflows/ci.yml` 에 데이터 검증/회귀 job 연결(USE_MOCK 분기).
- [x] **C10** `scripts/generate_seed.py` 로 `data/seed/marketscope_seed.dump` 재생성 + fresh compose 복원 검증.
- [x] **C11** `docs/status/current-status.md` 갱신 + 본 플랜 진행 기록.

## 재검토 (Self-Review Gate)

- **엣지케이스**: ① 작은 골목상권은 worker 가 실제 0일 수 있음 → 게이트는 "**전량** 0(`bool_and`)"만 FAIL(개별 0 허용). ② `_UNIT_PRICES` 에 없는 major(NULL major)는 기본 15000 → 게이트에서 default_unit_price NULL 0건 보장. ③ aliases 핵심 30종 외 NULL 은 **의도** → 게이트는 "전량 NULL"만 FAIL, 부분 NULL 허용. ④ 재적재는 UPSERT(idempotent)라 중복 안전.
- **메모리 충돌**: `feedback_etl_api_column_rename` 와 정합(API key 직접 확인 후 수정). `feedback_compose_force_recreate_cascade` — 재적재 시 db 외 서비스 cascade 주의(`--no-deps` 또는 host uvicorn 경로).
- **타 Plan 충돌**: `accuracy-gap-fix.md` GAP-B(learned_aliases/LLM fallback) 와 **상보적**(본 플랜은 정적 큐레이션 별칭, GAP-B 는 동적 학습 — 둘 다 resolver 에 합류). `data-trust-reliability-2026-04-24.md` Layer 1~5 와 중복 없음(본 플랜은 *적재 시점* 검증, 기존은 *런타임/응답* 검증). RC2 fallback 은 ISSUE-003(`recommendation.py`) 와 무관 파일.
- **단위 함정**: 값범위 게이트는 `monthly_sales` 가 **분기누적**임을 전제(`project_sales_quarterly_unit`) — percentile 임계를 분기 스케일로.

## Scenario (E2E Ring Mapping)

- `R0-DATA-WORKER` (Ring0 preflight) — 재적재 후 `resident_population` worker 전량0 아님 (DB 직접).
- `R0-DATA-CATMETA` (Ring0) — `category_metadata` default_unit_price/aliases(핵심30) NULL 0건.
- `R0-DATA-QUARTER` (Ring0) — 5 테이블 `count(distinct quarter)=1` = 2025Q4.
- `R1-F03-WORKERPOP` (Ring1) — 요약 카드 직장인구 > 0 노출(기존 0 회귀 차단).
- `R1-F09-UNITPRICE` (Ring1) — 시뮬레이션 기본단가 적용(NULL fallback 경로 무관히 값 존재).
- `R3-VALIDATE-GATE` (Ring3 negative) — 일부러 worker 0/aliases NULL 주입 → `runner validate` FAIL 재현(게이트 작동 증명).

## Pass 반복

- **Pass 1 (기본)**: C1~C5 수정·재적재 → 검증 쿼리 `worker bool_and=false` / `default_unit_price·aliases NULL=0,0` / 분기 균일. ruff + 단위테스트 green.
- **Pass 2 (엣지)**: C6~C9 게이트 + 회귀 → 결손 주입 FAIL 재현(R3-VALIDATE-GATE), 정상 데이터 PASS. `avg_startup_cost` defer 가 false alarm 안 내는지 확인.
- **Pass 3 (성능/마감)**: C10 시드 재생성 → fresh `docker compose up` 복원 후 전체 검증 재현. p1_api_vs_db 5상권 PASS. C11 문서 갱신.
- Fail → 수정 → 재실행.

## Agent 모델 선택
- 설계/근본원인: opus (완료). 구현(transformer/seed/validate): sonnet. 검증 쿼리/회귀 실행: haiku.

---

## Validation (E2E)
1. worker 단위테스트: 샘플 raw → population>0, 6연령×2성별=12행, Σ=API `TOT_WRC_POPLTN_CO`.
2. `runner run 2025Q4 --table resident_pop` 후 `SELECT bool_and(population=0) FROM resident_population WHERE pop_type='worker'` = `f`.
3. 재시드 후 `SELECT count(*) FILTER(WHERE default_unit_price IS NULL), count(*) FILTER(WHERE aliases IS NULL AND category_code IN (<핵심30>)) FROM category_metadata` = `0,0`.
4. `runner validate 2025Q4` 신규 게이트 ALL PASS. worker 0 주입 시 FAIL.
5. `pytest server/tests/test_data_integrity.py` green + CI 통과.
6. 시드 재생성 후 fresh compose → seed 복원 → 1~3 재확인 (`COUNT(*)`, not pg_stat).

## Verdict (2026-06-25)

✅ **완료 + 적대검증 통과.** Part A(RC1~RC3 수정·라이브 재적재) + Part B(검증 게이트·pytest·CI) 모두 구현·검증.
라이브 결과: worker total_pop 472만(was 0)·default_unit_price NULL 0·aliases 32 set. 게이트 `validate 2025Q4` PASS·`2026Q1`(빈분기) FAIL·worker=0 주입 FAIL 재현. pytest 132 passed/8 skip + data-integrity 13(gate FAIL-injection 포함). 시드 덤프 재생성(5.6MB, 아카이브 TOC 검증).

**적대검증 워크플로우**(5 lens·16 agent·11 finding 전건 confirmed) 후속 수정: P1 3건(alias `학원` 오라우팅·빈분기 false-pass·게이트 무테스트) + P2 3건. defer: GATE-3(all-constant↔단일분기 충돌)·SEED-2(도달불가)·PC-3(무관 drift).

**C10 단서**: 시드 재생성 + `pg_restore --list` 아카이브 검증까지 완료. fresh `docker compose up` end-to-end 복원 재검증은 live DB 파괴적이라 클린 세션으로 이월.

## Metadata
- 작성: 2026-06-25 · 카테고리: fix · 상태: ✅ 완료 (2026-06-25, 적대검증 통과)
- 선행 감사: `docs/qa/runs/eval-round2-2026-06-10/` + 2026-06-25 정합성 감사(메모리 `project_data_integrity_2026-06-25`)
- 영향 파일: `data/etl/transformers.py` · `data/etl/seed_category_metadata.py` · `data/etl/runner.py` · `repositories/real/simulation.py` · (신규) `data/etl/category_aliases.json` · `server/tests/test_data_integrity.py` · `.github/workflows/ci.yml` · (재생성) `data/seed/marketscope_seed.dump`
