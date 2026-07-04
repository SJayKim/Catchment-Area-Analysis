# Deferred 백로그 처리 — daily_avg 필드명 정정 + recommend score100 정규화 + 스트리밍 재설계 게이팅

## Context
- 2026-07-04 v2 프로덕션 배포(GATE PASS 4/4)가 끝나며 status 의 "다음" 항목으로 deferred 3건이 남았다:
  스트리밍 재설계 · recommend score100 · daily_avg rename. 셋 다 전용 Plan 이 없어 본 Plan 으로 커버한다.
- **Item 1 — `daily_avg` 필드명 정정**: `get_floating_population` 이 반환하는 `daily_avg` 는 실제로
  **분기 시간대별 합계**(`repositories/real/floating_population.py:39` `sum(hourly_rows)`)인데 이름이
  daily_avg 라서 LLM 이 '일평균'으로 라벨·분할 날조(2026-06-26 S7 물리모순 3/5)했고, 지금은
  프롬프트 가드 3면(respond.py rule / loop/prompts.py / trust.py 라벨)으로 억누르는 상태.
  이름 자체를 `quarter_total` 로 바꿔 근본 해소한다(2026-06-26 status 가 명시한 follow-up).
- **Item 2 — recommend score100**: `repositories/real/recommendation.py:208-213` min-max 정규화가
  1위를 **항상 score 100.0, 꼴찌를 0.0 에 고정** — 실제 품질 격차와 무관하게 "만점 확신"으로 오독됨
  (p0-backlog-2026-06-09 L41 지적, ISSUE-003 플로어 fix 때 정규화 자체는 defer). 상대 순위는 유지하되
  100/0 핀 고정을 없앤 유계 밴드로 교체한다. 단일 카테고리(spread=0) 시 현재 score 0 이 되는 엣지도 함께 해소.
- **Item 3 — 스트리밍 재설계**: v2 루프는 최종 LLM 응답을 `ainvoke` 로 통으로 받고 Trust Kernel
  검증(unbound/scale 탐지 → 교정 → fallback) 후에야 `_chunks` 로 방출(`engine.py:301`). 진짜 토큰
  스트리밍은 **검증-후-방출이라는 Trust Kernel 설계와 정면 충돌**하며, respond 경로 변경은 프로젝트
  게이트 규정상 Accuracy Eval(S1~S8) 재실행 + GATE 재판정이 필수. 본 Plan 에서는 설계 옵션과 게이트
  조건만 확정하고 **구현은 착수 보류**(별도 eval-gated 사이클).
- **Memory 참조**:
  - `feedback_sse_done_staleness.md` — SSE 이벤트 핸들링 시 requestId staleness 가드 (Item 3 설계 제약)
  - `feedback_chat_inflight_guard.md` — sendMessage in-flight abort+restart 관례 (Item 3 설계 제약)
  - Item 1/2 직접 관련 memory 없음.

## Scope
- **In Scope**:
  - Item 1: repo 반환 키 `daily_avg`→`quarter_total`, card payload `dailyAvg`→`quarterTotal`,
    전 소비처(백엔드 8파일 + mock fixture + frontend 2파일 + 테스트 3파일 + eval/audit 스크립트) 일괄 rename,
    프론트 하위호환 fallback(`quarterTotal ?? dailyAvg` — prod Redis `report:*` 캐시 구버전 payload 방어)
  - Item 2: min-max → 유계 밴드(55~95) 매핑, spread=0 시 75 고정, mock fixture score 100.0 제거(95 캡),
    회귀 테스트 추가
  - Item 3: 설계 옵션 기록 + 착수 조건(게이트) 명시 — 코드 변경 없음
- **Out of Scope**:
  - 스트리밍 재설계 구현 (Item 3 — 별도 eval-gated Plan)
  - DB 컬럼/ETL 변경 (rename 은 응답 필드만 — DB `floating_population` 스키마 불변)
  - grounded_fallback 라벨링(OBS-007) — 별도 트랙 유지

## Design

### Item 1 — `daily_avg` → `quarter_total` rename
변경 파일 (grep 전수 기준):
- `server/server/repositories/real/floating_population.py`: 반환 키 rename (L39 로컬변수 + L82)
- `server/server/agent/tools/mock/floating_population.json`: fixture 키 5건 rename (mock parity)
- `server/server/agent/tools/mock_data.py:61`: `fp["daily_avg"]` 참조 수정
- `server/server/agent/tools/district_summary.py`: L87 읽기 + L154 + L167 card 키 `dailyAvg`→`quarterTotal`
- `server/server/api/routes/districts.py:159,166`: preview 소스 필드 참조 수정
- `server/server/agent/utils/abstention.py:27`: headline 필드 맵 수정
- `server/server/agent/utils/numeric_sanity.py:183`: sanity 튜플 수정
- `server/server/agent/loop/trust.py:169`: value_hints 튜플 수정 (라벨 "분기 유동인구" 유지)
- `server/server/agent/loop/prompts.py:31` + `server/server/agent/nodes/respond.py:294`:
  프롬프트 문구를 새 필드명 기준으로 갱신 (가드 룰 자체는 유지 — 과거 세대 모델 회귀 대비)
- `frontend/src/lib/types.ts:36`: `dailyAvg`→`quarterTotal` + **optional 하위호환** `dailyAvg?`
- `frontend/src/components/chat/cards/SummaryCard.tsx:78`: `quarterTotal ?? dailyAvg` fallback 읽기
- 테스트: `server/tests/test_numeric_sanity.py` ×2, `server/tests/test_trust_kernel_regressions.py` ×1 fixture 키 갱신
- 스크립트: `scripts/eval/trust_scenarios.py`(변수명·라벨), `scripts/audit/p2_tool_vs_sql.py`(tool 필드 참조)
- 배포 주의: prod Redis `report:*`/preview 캐시에 구 `dailyAvg` payload 잔존 → **배포 시 flush_cache.py 필수**(기존 관례) + 프론트 fallback 이중 방어

### Item 2 — score 밴드 정규화
- `repositories/real/recommendation.py:208-213`:
  ```python
  SCORE_BAND_MIN, SCORE_BAND_MAX = 55.0, 95.0   # 모듈 상수
  # spread > 0: score = 55 + (raw-min)/spread * 40  → 1위 95.0, 꼴찌 55.0
  # spread == 0 (단일/동점): 전원 75.0 (현재는 0.0 이 되는 버그성 엣지)
  ```
  순수함수 `_band_score(raw_scores: list[float]) -> list[float]` 로 추출(테스트 용이).
- `server/server/agent/tools/mock/recommendations.json`: score 100.0 → 95.0 등 밴드 내 재배치 (mock parity)
- RecommendCard 색상 임계(≥80 green / ≥60 blue / ≥40 yellow)와 정합: 상위권 green~blue, 하위 55→yellow — 의도된 시각 완화
- 회귀 테스트: `test_recommendation_scoring.py` 에 `_band_score` 3건 추가 (1위≠100 / spread=0→75 / 순위 보존)

### Item 3 — 스트리밍 재설계 (설계만, 착수 보류)
- 현 구조: `engine.py` 가 final ainvoke → trust 검증/교정/fallback → `_chunks(90)` 방출. 침묵은
  thinking 진행 이벤트(`dcb5f8a`)로 완화된 상태.
- 옵션 A (문장 단위 검증 스트리밍): 토큰을 문장 경계 버퍼로 모아 문장별 `find_unbound_numbers` 통과분만
  방출, 미통과 문장은 `mask_unbound` 후 방출. **글로벌 교정 LLM 패스 상실** → R4 GATE 근거 붕괴 위험.
- 옵션 B (검증 유지 + 지각 지연 축소): final 호출을 `astream` 으로 받되 버퍼링, 수신 중 진행 이벤트를
  세분화(예: "응답 작성 중 n%"), 검증 후 일괄 방출. Trust 의미론 무변경 — 지각 개선만.
- 옵션 C (낙관 방출 + 교정 patch 이벤트): 스트리밍 후 위반 발견 시 교체 이벤트 — 클라이언트 프로토콜
  신설 필요, UX 리스크 큼.
- **권고: 옵션 B 를 1차로, A 는 eval 인프라 상시화 후**. 착수 게이트: (1) e2e 스택 + live LLM 키 가용,
  (2) 변경 후 S1~S8 재실행 평균 ≥9.0 & 날조 0 (R4 기준 유지), (3) `feedback_sse_done_staleness` /
  `feedback_chat_inflight_guard` 가드와 프론트 이벤트 순서 호환 검증.
- 의존성/선행: 없음(Item 1/2 는 상호 독립). Item 3 구현은 본 Plan 완료 후 별도 Plan.

## Checklist
- [x] I1-1 backend rename: repo·mock fixture·mock_data·district_summary·districts·abstention·numeric_sanity·trust·prompts·respond
- [x] I1-2 frontend rename: types.ts(`quarterTotal` + `dailyAvg?` 하위호환) + SummaryCard fallback 읽기
- [x] I1-3 테스트/스크립트 rename: test_numeric_sanity ×2 · test_trust_kernel_regressions ×1 · trust_scenarios.py · p2_tool_vs_sql.py
- [x] I1-4 잔존 검증: `grep -rn "daily_avg\|dailyAvg" server/ frontend/src/ scripts/` 가 의도된 하위호환 fallback 외 0건 (잔존 = trust.py/numeric_sanity.py legacy 매처 + frontend fallback — 전부 의도)
- [x] I2-1 `_band_scores` 순수함수 + 상수(55/95/75) + 정규화 블록 교체
- [x] I2-2 mock recommendations.json score 밴드 재배치 (100.0 제거, 4 리스트 55~95 재스케일)
- [x] I2-3 회귀 테스트 3건 추가 (1위≠100 / spread=0→75 / 순위 보존)
- [x] I3-1 설계 옵션 + 착수 게이트 본 문서 확정 (코드 변경 없음)
- [x] V-1 ruff check/format PASS (B905 zip strict 2건 수정 후 All checks passed, 145 files formatted)
- [x] V-2 pytest 전체 (prod 이미지 throwaway 컨테이너) **190 passed / 6 skipped(@real DB)** — 기존 187 + 신규 3, 회귀 0
- [x] V-3 tsc --noEmit 0 error
- [x] V-4 status-update + 배포 시 flush 필수 문구 기록

## 재검토 (Self-Review Gate)
- [ ] 엣지: prod Redis 구 payload(`dailyAvg`) → 프론트 fallback + 배포 flush 이중 방어 확인
- [ ] 엣지: spread=0(단일 카테고리) score — 기존 0.0 버그 → 75.0 개선 확인
- [ ] 엣지: mock/real parity — fixture JSON 과 real repo 반환 키 동일성 grep 검증
- [ ] Memory 교훈: SSE 관련 2건은 Item 3 설계 제약으로만 반영(Item 1/2 는 SSE 스키마 무변경 — card payload 키만 변경이며 이벤트 타입/순서 불변)
- [ ] 충돌: eval R4 산출물(`docs/qa/runs/`)의 과거 SSE 로그는 히스토리 — rename 대상 아님. e2e artifacts 로그 동일.
- [ ] 충돌: trust.py value_hints 는 07-04 RC5 fix 의 일부 — 키 rename 만 하고 로직(×10/×100 매칭) 불변 확인

## Scenario (E2E Ring Mapping)
- **Ring**: 1 (features) — 카드 payload 필드 변경이 F03 요약 카드·F07 추천 카드 렌더에 직접 영향
- **Scenario ID**: `R1-F03-QUARTERTOTAL-01` / `R1-F07-SCOREBAND-01`
- **사전조건**: USE_MOCK=true 스택 (mock fixture rename 반영 빌드)
- **실행 단계**: ① 강남역 요약 질의 → summary 카드 수신 ② 추천 질의 → recommend 카드 수신
- **기대 결과**: ① 카드 유동인구 수치 정상 렌더(NaN/undefined 없음, "분기 합계" 라벨) ② 1위 score ≤ 95, 전 항목 55~95 밴드, 순위 불변

## Pass 반복 (Iteration Plan)
- Pass 1: Item 1+2 기본 구현 + 단위 테스트 (I1-1~I2-3)
- Pass 2: 엣지 — 잔존 grep 0건(I1-4), spread=0, mock/real parity, 하위호환 fallback
- Pass 3: 회귀 — pytest 전체 + ruff + tsc, (스택 가용 시) Ring1 시나리오 2건
- Fail 시 수정 → 해당 Pass 재실행

## Agent 모델 선택
- **설계**: opus 불요 — 스코프가 grep 전수로 확정된 기계적 rename + 국소 수식 교체 (본 세션 직접)
- **구현**: sonnet 급 — 명확한 스펙 (본 세션 직접 수행)
- **검증**: haiku 급 판정 가능 — pytest/ruff/tsc exit code + grep 0건
- 근거: 파일 수는 많으나 판단 분기가 거의 없는 변경. Item 3 만 설계 난도가 있으나 본 Plan 에서 구현 제외.

## Validation
- `cd server && ruff check . && ruff format --check .` (또는 컨테이너)
- pytest: prod 이미지 throwaway 컨테이너 (2026-07-04 관례) — 전체 suite + 신규 테스트
- `cd frontend && npx tsc --noEmit`
- 수동: grep 잔존 0건 확인, mock 스택 기동 시 summary/recommend 카드 육안 확인
- `/e2e-run 1` (스택 가용 시, 수동 트리거)

## Metadata
- 작성일: 2026-07-04
- 작성자: Claude Code (plan-new skill)
