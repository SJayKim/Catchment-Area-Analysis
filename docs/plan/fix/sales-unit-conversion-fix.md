# 분기→월 매출 단위 후속 수정 및 검증 Plan

## Context

보문역 상권 추천 응답에서 "슈퍼마켓 점포당 월매출 41,279만원 (≈4.13억/월)"이라는 비현실적 숫자가 노출된 것을 계기로, DB 컬럼 `estimated_sales.monthly_sales`(서울 열린데이터 `THSMON_SELNG_AMT`)가 **월 매출이 아니라 분기 누적(원)** 이라는 사실이 확인됐다. 서울 열린데이터 FAQ 원문: "분기당 매출 금액은 개인 매출액과 법인 매출액의 합산값...". 필드명(당월)과 DB 컬럼명(`monthly_sales`)이 오해를 유발한 케이스.

직전 세션에서 Real Repository 4곳(`estimated_sales.py`, `simulation.py`, `recommendation.py`, `comparison.py`)에 `// MONTHS_PER_QUARTER` 변환을 적용해 월 단위로 정규화했다 (커밋 전, 작업 트리 상태).

하지만 완전히 정리되지 않은 3가지 잔존 이슈가 있다:

1. **기존 `_enrich_sales` 키 불일치 버그 3곳** — `quarterly_sales` 배열의 실제 키는 `monthly_sales`인데 코드가 `.get("sales", 0)`로 조회해 항상 0을 리턴. `qoq_growth_pct` / `annual_growth_pct` / `qoqGrowth` / QoQ·연간 성장률 힌트가 전부 무효화되고 있다.
2. **Redis 캐시 TTL 24h** — 기존 과대 값이 캐시에 잔존. 배포 후 flush 필요.
3. **검증 자동화 부재** — pytest 없음, 단위 변환이 실제 DB 값에 대해 합리적 범위로 나오는지 확인할 스크립트 없음.

(프롬프트 예시 숫자 업데이트, DB 컬럼 rename은 이번 범위 밖 — 별도 이슈로 분리.)

**목표**: 잔존 버그를 제거하고, 분기→월 변환 + QoQ 힌트가 실제 DB 쿼리 결과에서 정상 동작함을 스크립트로 재현 가능하게 검증한다.

---

## Scope

### In Scope
- `_enrich_sales` / `district_summary` / `respond._compute_hints` 의 키 이름 버그 3곳 수정
- 캐시 flush 전용 스크립트 신설 (운영 재사용 목적)
- 단위 변환 검증 스크립트 신설 (보문역 + 대조 상권 1곳 샘플링)

### Out of Scope (별도 티켓)
- DB 컬럼 `monthly_sales` → `quarterly_sales_raw` rename (Alembic migration + 10+ 파일 수정, 장기 리팩터)
- `respond.py:96-98` 하드코딩 프롬프트 예시 숫자 업데이트 (LLM 응답 품질 튜닝 영역)
- 새로운 pytest 테스트 스위트 구축 (프로젝트 전반 인프라 작업)

---

## 핵심 변경 대상 파일

| 파일 | 변경 내용 |
|------|-----------|
| `server/server/agent/tools/estimated_sales.py` | `_enrich_sales()` 내 `.get("sales", 0)` → `.get("monthly_sales", 0)` (라인 29, 30, 34) |
| `server/server/agent/tools/district_summary.py` | 동일 버그 수정 (라인 140, 141) |
| `server/server/agent/nodes/respond.py` | `_compute_hints()` 내 동일 버그 수정 (라인 191, 192, 197) |
| `scripts/flush_cache.py` (신설) | `flush_by_prefix()`를 이용해 5개 prefix 일괄 삭제 |
| `scripts/verify_sales_units.py` (신설) | Real repository 4종을 직접 호출해 샘플 상권의 월매출 값이 상식 범위에 있는지 sanity check |

### 재사용할 기존 유틸/함수
- `server/server/services/cache.py:125-141` — `flush_by_prefix()` 이미 구현되어 있음. 새 스크립트는 얇게 감싸기만.
- `server/server/repositories/real/_units.py` — 직전 세션에서 추가한 `MONTHS_PER_QUARTER` 상수.
- `server/server/repositories/__init__.py::get_data_access()` — real/mock 분기 헬퍼. 검증 스크립트에서 그대로 사용.
- `server/server/config.py::settings` — DB URL, USE_MOCK 환경설정. 스크립트에서 직접 참조.
- `scripts/setup_db.py` — 기존 독립 실행 스크립트 패턴 참고 (async main, settings 주입 방식).

---

## 구현 체크리스트 (TODO)

### Phase A — 키 불일치 버그 수정 (P0, 기능 버그)
- [ ] `server/server/agent/tools/estimated_sales.py:29` — `quarterly[-2].get("sales", 0)` → `quarterly[-2].get("monthly_sales", 0)`
- [ ] `server/server/agent/tools/estimated_sales.py:30` — `quarterly[-1].get("sales", 0)` → `quarterly[-1].get("monthly_sales", 0)`
- [ ] `server/server/agent/tools/estimated_sales.py:34` — `quarterly[-5].get("sales", 0)` → `quarterly[-5].get("monthly_sales", 0)`
- [ ] `server/server/agent/tools/district_summary.py:140-141` — 동일한 2줄 치환
- [ ] `server/server/agent/nodes/respond.py:191, 192, 197` — 동일한 3줄 치환
- [ ] `grep -n 'quarterly.*\.get("sales"' server/` 로 추가 누락 없는지 최종 재확인

### Phase B — 캐시 flush 스크립트 신설 (P1, 운영)
- [ ] `scripts/flush_cache.py` 작성
  - `settings` 로드 → `set_cache_service(RedisCacheService(redis_url))` 또는 `MemoryCacheService`
  - `PREFIXES = ["sales:", "compare:", "recommend:", "simulation:", "summary:"]` 순회하며 `flush_by_prefix()` 호출
  - 각 prefix별 삭제 개수를 stdout에 출력
  - `if __name__ == "__main__": asyncio.run(main())` 엔트리포인트
- [ ] 로컬에서 `docker compose exec server python scripts/flush_cache.py` 로 동작 확인

### Phase C — 단위 변환 검증 스크립트 신설 (P1, 검증)
- [ ] `scripts/verify_sales_units.py` 작성
  - `get_data_access()` 경유로 real 리포지토리 획득 (USE_MOCK=false 가드)
  - 대상 상권: 보문역 포함 2~3곳 (DB 조회로 district_code 동적 획득 — `districts` 테이블에서 `district_name LIKE '%보문%'` 또는 `%강남%`)
  - 4개 시나리오 각각 실행하고 결과를 print + assertion:
    1. `sales.get_estimated_sales(bomun_code)` → `total_monthly_sales`가 1억~500억 원 범위 (상권 규모 대비 상식적 범위)
    2. `recommendation.recommend_business(bomun_code)` → Top5 각 항목의 `per_store_sales`를 원→만원 변환해 출력, 슈퍼마켓 카테고리의 경우 < 3억/월 경고
    3. `comparison.compare_districts([bomun_code, other_code])` → 두 상권의 `monthly_sales` 출력
    4. `simulation.get_sales_percentiles(supermarket_code)` → `seoul_avg_per_store`가 < 3억/월
  - 추가: Phase A에서 수정한 `computed.qoq_growth_pct` 또는 `insights.qoqGrowth` 키가 실제로 채워지는지 1곳 이상 확인
  - 실패 시 non-zero exit로 종료해 CI 사용 가능한 형태로

---

## 검증 계획 (How to test end-to-end)

### 사전 준비
1. `docker compose up -d db redis` 기동, seed 데이터 적재 확인 (`scripts/setup_db.py` → Full ETL 또는 `marketscope_seed.dump` 로드)
2. `SEOUL_OPENDATA_API_KEY` 필요 시 `.env` 설정
3. `USE_MOCK=false` 로 real 경로 진입 보장

### 단위 변환 검증
```bash
docker compose exec server python scripts/verify_sales_units.py
```
기대값: 보문역 슈퍼마켓 점포당 월매출이 대략 **1.2~1.5억/월** (직전 세션 예측치 ≈1.38억) 근처로 표시. 과거 버그 시점 값(4.13억/월) 대비 ≈1/3로 줄어 있어야 함.

### 캐시 flush 검증
```bash
docker compose exec redis redis-cli KEYS 'sales:*' | wc -l   # 기존 키 개수
docker compose exec server python scripts/flush_cache.py      # 실행
docker compose exec redis redis-cli KEYS 'sales:*' | wc -l   # 0 이어야 함
```

### `_enrich_sales` 키 버그 수정 검증
- `get_estimated_sales` 결과의 `computed.qoq_growth_pct`가 0이 아닌 값으로 채워짐을 확인 (4분기 이상 trend rows가 있는 상권 기준). `verify_sales_units.py` 마지막 섹션에 포함.

### 엔드투엔드 (UI/에이전트 경로)
1. 캐시 flush 후 `docker compose up -d` 전체 기동
2. 브라우저에서 "보문역" 상권 클릭 → 챗봇에 "여기서 가장 추천하는 업종이 뭐야?" 입력
3. RecommendCard 렌더링 시 슈퍼마켓 점포당 월매출이 **약 1억대 후반 이하**로 표시되는지 확인 (기존 41,279만원 → 약 13,760만원)
4. "분기 대비 매출 성장률은?" 식으로 물어보면 QoQ 숫자가 응답에 포함되는지 확인 (Phase A 수정 효과)

### Rollback
- 코드 변경은 전부 최소 범위 치환. 문제 발생 시 각 파일을 직전 커밋으로 되돌리고 캐시 재생성 대기 (24h TTL 이후 자연 치유, 또는 재-flush 후 구 바이너리로 재배포).
- DB 변경 없음, 스키마 변경 없음 → 데이터 손실 위험 0.

---

## 이미 적용된 선행 수정 (직전 세션, 커밋 전)

이 plan이 전제로 하는 직전 세션 변경 사항 — Real repository 분기→월 변환:

| 파일 | 변경 |
|------|------|
| `server/server/repositories/real/_units.py` (신규) | `MONTHS_PER_QUARTER = 3` 상수 + 배경 주석 |
| `server/server/repositories/real/estimated_sales.py` | total/weekday/weekend/gender/age/time/quarterly 모든 매출 값 `//3` |
| `server/server/repositories/real/simulation.py` | `seoul_avg_per_store` `/3` (p25/p75는 비율이라 불변) |
| `server/server/repositories/real/recommendation.py` | `monthly_sales` `//3` (하위 `per_store_sales`/reasons/score 자동 보정) |
| `server/server/repositories/real/comparison.py` | `monthly_sales` `//3` (trend 비율은 불변) |
| `server/server/models/sales.py` | 클래스 docstring 추가 (컬럼 단위 경고) |
| `server/server/data/etl/transformers.py` | `transform_estimated_sales` docstring 보강 |

Mock 데이터는 원래부터 월 단위로 작성되어 있어 변경 불필요. 다운스트림 tool(`simulate_revenue`, `district_summary`, `compare_districts`, `recommend_business`)은 이미 변환된 값을 사용하므로 이중 분할 위험 없음 확인.

---

## 후속 과제 (이번 범위 밖, 별도 티켓으로)

- `respond.py:96-98` 시스템 프롬프트 예시 숫자를 새 월 단위 현실 값으로 업데이트 (LLM 응답 품질)
- DB 컬럼 `estimated_sales.monthly_sales` → `quarterly_sales_raw` rename + 읽기 레이어 리팩터 (장기)
- pytest 프로젝트 인프라 (conftest, fixtures, CI 통합)
- 관리용 HTTP 엔드포인트 `/admin/cache/flush` 도입 여부 결정

---

*작성일: 2026-04-16*
