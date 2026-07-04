# Prod Deploy 2026-07-04 — v2 Agentic Loop + Trust Kernel P1/P2 fix + DB 복구 (런로그)

> 상태: ✅ **완료** (2026-07-04). Plan 원본: `~/.claude/plans/gleaming-juggling-yeti.md` (세션 플랜).
> 배포 커밋 기준: `2ad0d87` + 본 세션 P1/P2 fix. 게이트: [eval-round4 _verdict](../../qa/runs/eval-round4-2026-07-04/_verdict.md) **PASS 4/4**.

## Context

- R3 (07-03) GATE FAIL 2/4 로 배포 정지 → 사용자 결정: P1/P2 fix → S2/S4/S8 재측정 → 통과 시 v2 배포 + prod DB 결손 복구.
- 배포 전 라이브: 4/28 스냅샷 컨테이너 2개월 무배포, 죽은 모델 ID(`claude-sonnet-4-20250514`)+무효 키로 **전 트래픽 Gemini fallback**, prod DB 는 6/25 데이터 fix 미반영 (worker 전량 0 · category_metadata 0행).

## Phase 0 — P1/P2 fix (RC1~RC5)

| RC | 결함 | fix |
|---|---|---|
| RC1 | fact_pool `tool#N` 키 ↔ `_collect_tool_scalars` 완전일치 비교 → typed 매칭 전멸 → S2 abstention | `pool_key.split("#",1)[0]` 정규화 (`numeric_sanity.py`) |
| RC2 | `_COMPOUND_RE` lo_unit 에 `만` 미허용 → "3억 5,000만원"=300,005,000 오파싱 + 인접 숫자 오병합 | lo_unit 확장(천만~십)+**필수화**, `_SIMPLE_RE`/`_UNIT_SCALE` 천만·백만·십만·백·십 확장 (백/십은 TypeError 방지 겸용) |
| RC3 | fact_pool 은 truncate본·ToolMessage 는 전체본 → 11번째+ 값 인용 시 unbound (비결정) | `engine.py` fact_pool 원본 저장 (LLM 미전송 — 토큰 영향 0) |
| RC4 | still-unbound 1개에도 draft 전체를 무라벨 fallback 으로 대체 (가용성 손실) | `should_fallback`(≥3 AND ≥50%) + `mask_unbound`("[미확인]"+부기 1회) + `grounded_fallback` 라벨된 스칼라 재작성 + `cards_emitted` 시 abstention 금지, 빈 pool 만 기존 abstention 유지 (`trust.py`/`engine.py`) |
| RC5 | "145만 원"(1.45M)은 원화 채점 floor(10M) 미만 → 10배 축소 무검증 통과 | `find_scale_mismatches`(원 100K~10M·명 10K~100K 에서 ×10/×100 typed 매칭, face-value 매치 제외) + 교정 턴 value_hints + 시스템 프롬프트 자릿수 대조 1줄 |

- 변경: `numeric_sanity.py` · `loop/trust.py` · `loop/engine.py` · `loop/prompts.py` + 신규 `tests/test_trust_kernel_regressions.py`(7 클래스 19 테스트)
- 검증: 컨테이너 pytest **187 passed / 6 deselected(@real) / 0 fail** (기존 `test_numeric_sanity.py` 5건·v2 회귀 포함) · ruff check/format PASS

## Phase 1 — Eval Round 4 (게이트 재판정)

- e2e 스택 신규 기동 (`:8002`, fresh volume): `USE_MOCK=false` 호스트 export (compose env 블록 함정 회피), `.env.e2e` 새 Anthropic 키 반영, corrected seed 자동복원 (worker_sum=4,724,265 · aliases=32), 컨테이너 내 fix marker grep 확인. 함정 1건: fresh volume 의 PostGIS init 중 db healthcheck 가 선통과해 migrate 가 connection refused — init 완료 대기 후 재기동으로 해소.
- S2/S4/S8 ×2 + S7 smoke(2턴), message-only, done 8/8 절단 0. GT 는 현 DB 재쿼리.
- **결과**: S2/S4/S8 전부 10.0 (R3 3.3/3.3/9.2) · 평균 10.0 · 날조 0/8 · trust 로그 "still unbound → fallback" **0건** (교정 1회 발생·성공). 상세: [_verdict.md](../../qa/runs/eval-round4-2026-07-04/_verdict.md)

## Phase 2 — 프리플라이트

- Anthropic 키 liveness 200 + `claude-sonnet-4-6` 모델 존재 (`/v1/models`)
- `.env`: USE_MOCK=false · LLM_PROVIDER=anthropic · NEXT_PUBLIC_API_URL=루트 도메인 · **`AGENT_LOOP_VERSION=v2` 명시 추가**
- 호스트 셸 env 오염 0건 · 롤백 태그 `prev-2026-07-04` 3종 (backend/frontend/migrate — migrate 태그 갭 해소)

## Phase 3 — prod DB 복구 (targeted data-only)

- 사전 스냅샷: worker_sum=0 · catmeta=0 · rp_rows=39,288 · learned=0 · alembic=005 (플랜 예상 일치)
- 백업 2중: `data/backups/prod-full-2026-07-04.dump`(5.27MB) + `prod-tables-2026-07-04.dump` (gitignore 추가)
- 원자 복원: `psql --single-transaction -v ON_ERROR_STOP=1` — TRUNCATE(learned_aliases,category_metadata / resident_population) → seed dump 의 2테이블 data-only SQL → setval. 1차 시도는 dump 의 `search_path=''` 때문에 마지막 setval 이 실패해 **전체 자동 롤백** (원자성 실증) → `public.` 한정 후 재실행 COMMIT.
- 사후 검증 (COUNT 직접): worker_sum=**4,724,265** · allzero=f · rp_rows=39,288 · catmeta=**100** · unit_price_null=0 · aliases_set=**32** · orphans=0 · 무관 테이블 불변(75,985/21,333/9,888) · learned=0
- Step 5 (cutover 후): `runner validate 2025Q4` — **16/16 ALL PASS** (C6 게이트, 신규 이미지)

## Phase 4 — 빌드 + Cutover

- `.env.dev` 임시 이동 (bake-in 방지) → `docker compose -f docker-compose.prod.yml build` 3종 → 원복 → `up -d`
- migrate no-op (stale 0, head 005) · seed skip (districts>0) · backend healthy ~20s
- `flush_cache.py` 실행 — 0 keys (구 캐시는 24h TTL 로 기만료, 라벨 fix 구 캐시 포이즈닝 리스크 소멸 확인)

## Phase 5 — Live Smoke

| 항목 | 결과 |
|---|---|
| :3200 / :8000/health / 외부 도메인 ×5 / privacy·terms | 전부 200 |
| /api/health/detail | use_mock=false · anthropic · redis lazy-init 후 connected=true. (v2 는 detail 미노출 — 컨테이너 settings 로 `agent_loop_version=v2` 확인) |
| /api/districts | total=1650 · preview(3120189) 정상 — 복구 catmeta 업종명 노출 |
| SSE 실호출 3건 | ① 강남역 분석: done+카드2+**trace_id 동봉** ② 직장인구: **87,191명 = DB SUM 정확 일치** (복구 데이터 라이브) ③ 카페 시뮬: **카페→CS100010 resolve** (복구 aliases) · 평균 3,864만 = 기존 GT · 객단가 12,000 (복구 unit_price) |
| 백엔드 로그 | Anthropic 401/404 **0건** (배포 전 다수 → 소멸, Claude 실응답 확인) · ERROR/Traceback 0 · 10분 관찰 이상 없음 |
| 번들 스캔 | dev-URL(localhost:3000/8000) 0건 (컨테이너 .next + 서빙 HTML) |
| prod-smoke Playwright | **26 passed / 6 failed / 4 skipped** — 실패 6건 전부 로컬 WebKit 바이너리 부재 (mobile-iphone/tablet-ipad 프로젝트), 앱 결함 0. Chromium 계열(chromium+mobile-galaxy) 적용분 16/16 PASS (P5 카드 매출·P6 per_store·P8 실브라우저 SSE·P9 dev-URL 포함) |

- 비차단 관찰: prod-smoke 브라우저가 `/api/kakao-sdk` 404 프로브 (P7 지도 자체는 PASS — 프론트 `/proxy/kakao-sdk` 경로 사용) · `frontend/test-results/` root 소유 permission — follow-up 후보.

## Phase 6 — 정리

- stale `migrate-run-*` 2개 제거 · e2e 스택 down (볼륨 보존) · 미기동 nginx 현상 유지
- `docker-compose.yml`(dev) 에 `name: marketscope-dev` 추가 (dev/prod project-name 충돌 구조 해결, prod compose 는 무변경)
- `.gitignore` +`data/backups/`

## 롤백 경로 (현행화)

1. 이미지: `prev-2026-07-04` 3종 재태그 → `up -d --force-recreate` → flush 재실행
2. 스위치: `.env` `AGENT_LOOP_VERSION=pae` → backend 재생성
3. DB: `data/backups/prod-tables-2026-07-04.dump` 를 동일 단일 트랜잭션 패턴으로 원복
