# User-Journey 품질 개선 Plan — 2026-04-24

> 기존 107 시나리오 (intent-coverage 중심) 와 별도로, **실제 사용 패턴** (연쇄 질문 / 다중 상권 전환 / 3+ way 비교 / 상세 보고서) 에 집중한 16 journey × 45 turn 팩을 만들어 Pass 1→수정→Pass 2 를 돌린다.

## 1. Context

- Current baseline: Quality Sweep 2026-04-24 Pass 2 = 96.4% / 98 PASS · 9 FAIL (intent coverage 중심)
- Gap: `F-drill-*` (10), `E-coref-*` (12), `G-switch-*` (8) 이 multi-turn 을 다루지만 **journey 단위 서사**가 아니라 2-turn 스냅샷. 사용자의 실제 궤적(summary→category→risk→PDF 같은 4-step) 재현 부족.
- 참고 memory:
  - `feedback_respond_tool_use_xml_leak.md` — XML leak 금지 (현재 룰 적용됨)
  - `feedback_comparison_intent_halluc.md` — multi-district extract 실패 시 할루시
  - `feedback_sse_hallucination_needs_db_gt.md` — card data 일부만 노출, DB gt 대조 권장
  - `feedback_eval_district_code_hardcode.md` — district_code 주입 금지 · message 로만 entity linking 검증
  - `feedback_e2e_user_message_pollution.md` — body.innerText 매처는 user 쿼리 포함 주의

## 2. Scope

**In scope**
- `scripts/eval/user_journey_scenarios.py` 16 journey / 45 turn (UJ1~UJ4 × 4)
- live real-mode `/api/chat` (localhost:8000, USE_MOCK=false, Claude Sonnet 4) 대상 Pass 1 · Pass 2
- rubric 은 기존 `apply_rubric` 재활용 — final turn 채점
- Fail 발견 시 P0/P1 만 즉시 fix (P2+ 는 후속 plan 로 분리)

**Out of scope**
- Playwright UI 시나리오 (이미 ring0~3)
- Langfuse score / trace_id 정확성 (별도 LLMOps L2)
- 전체 eval round 3 KPI 재측정 (별도 `accuracy-gap-eval-round2-2026-04-24.md` 참조)

## 3. Design

### 3.1 Journey 축

| 축 | journey 수 | 대표 패턴 |
|---|---:|---|
| **UJ1** 단일 상권 심층 | 4 | summary → 세부 지표 (유동/업종) → 리스크/시뮬 (4-step) |
| **UJ2** 다중 상권 전환 | 4 | 상권 A → 상권 B → 비교/coref → back-to-A |
| **UJ3** 3+ way 비교 | 4 | 한 턴에 3 상권 + pick-best 질의 |
| **UJ4** 상세 보고서 | 4 | 3~4 step 누적 후 "PDF 로 저장" 또는 single-turn long synthesis |

### 3.2 평가 축 (final turn)

- `no_xml_leak` (필수, 전 시나리오)
- `min_text_chars`
- `intent_any` / `tool_names_include[_any]` / `compare_district_count_min`
- `coref_resolved_to` (UJ2 back-to-A 케이스)
- `pdf_trigger` (UJ4 PDF 요청 3건)
- `must_contain_any_in_text` (맥락 키워드)

### 3.3 Pass 1 → 분석 → Pass 2 싸이클

1. Pass 1 실행 → `docs/qa/runs/user-journey-2026-04-24/pass1/summary.md`
2. FAIL 을 원인별로 그룹: (a) Planner entity/coref (b) Rewriter (c) Respond leak/length (d) PDF ack
3. P0/P1 fix 구현 → ruff + unit smoke
4. Pass 2 실행 → delta 기록

## 4. Checklist

- [x] `scripts/eval/user_journey_scenarios.py` 작성 (16 journey / 45 turn)
- [x] `run_quality_sweep.py` 에 `SCENARIO_MODULE` env 추가
- [x] Pass 1 smoke 1 건 검증 (UJ1-cafe PASS 83%)
- [x] Pass 1 전체 실행 (16 journey, 71.3%)
- [x] FAIL 근본 원인 분류 + 이 문서 §5 업데이트
- [x] P0/P1/P2 fix 구현 (planner.py compare-coref history injection · intents 다중매치 우선순위 · UJ4 장문 synthesis)
- [x] Pass 2 실행 (97.5%) · Pass 3 실행 (**99.1% · 16/0**)
- [ ] `docs/status/current-status.md` 갱신
- [x] memory 신규 후보 저장: `feedback_bash_cwd_persists_between_calls.md`
- [ ] git commit + push origin main

## 5. Pass 1 결과

- Total **16** journey / 45 turn · Avg **71.3%** · **9 PASS / 7 FAIL**
- Dev compose override 환경이라 Langfuse OTel 비활성 → 전 scenario `trace_id` ✗ (회귀 아님, -1점 분만큼 실제 성능은 5–10%p 높음)

| ID | Score | 판정 | 근본 원인 |
|---|---:|---|---|
| UJ1-pub-건대 | 50% | FAIL | "안전한 창업 업종 추천" → risk 분류 (원래 recommendation 기대) |
| UJ2-switch-강남-종로 | 71% | FAIL | recommend card 에 `district_name` 노출 안됨 (rubric noise; trace_id 제외 시 83% PASS) |
| UJ2-switch-홍대-성수 | 33% | FAIL | **"이 두 곳 비교" coref → planner clarification**. history 의 districts 미주입 |
| UJ2-switch-명동-남대문 | 75% | FAIL (noise) | trace_id 외 전부 PASS |
| UJ2-switch-잠실-신촌 | 50% | FAIL | **"대학가 vs 번화가"** 에 district 없고 coref 도 미감지 → clarification. min_text=71 |
| UJ4-report-from-compare | 50% | FAIL | **"이 비교+추천 내용 PDF"** 3rd turn 이 clarification (comparison coref 동일 버그) |
| UJ4-long-synthesis | 67% | FAIL | 단일 턴 장문 요청 → "리스크" 키워드 선점 → `get_store_history` 단일 도구 (종합 fan-out 필요) |

## 6. Fix 설계

### P0 — Comparison coref history injection  (rewriter 또는 planner)
영향 scenario: UJ2-홍대-성수, UJ2-잠실-신촌, UJ4-report-from-compare (×3)

- `planner.py` comparison intent 분기에서 `detect_districts_in_message` 가 0~1 반환 & message 에 compare-coref 패턴 ("이 두 곳", "두 곳 다", "둘 다", "둘 중", "위 비교", "위 두", "이 상권들", "이것들", "양쪽") 검출 시 → history 의 user 턴 content 를 최근부터 `detect_districts_in_message` 로 추출해 3개까지 주입
- 비용: compare-coref 이 실제 매치된 경우에만 최대 3회 추가 lookup (대부분 캐시 히트)

### P1 — "안전/리스크 + 추천" 충돌  (`_classify_by_rules` post-fix)
영향 scenario: UJ1-pub-건대 (×1)

- rule classifier 반환 intent 가 `risk` 이고 message 에 "추천|업종.*뭐|어떤.*업종|가장.*좋은.*업종" 이 동시 존재 → `recommendation` 로 교체 (confidence 0.85)

### P2 — 장문 상세 보고서 single-turn → summary fan-out  (`_classify_by_rules` 특수 경로)
영향 scenario: UJ4-long-synthesis (×1)

- message 에 "상세.*분석|종합.*분석|전체.*분석|분석.*보고서|보고서.*형태" 중 하나 매치 & 토픽 키워드 (유동/매출/점포/추천/리스크/시뮬/폐업) 3개 이상 병렬 매치 → `summary` (0.9) 로 분류 → `get_district_summary` 가 4 tool 내부 fan-out

### Non-fix (rubric/infra)
- trace_id 부재: 컨테이너 volume-mount 환경의 Langfuse OTel 미활성. 프로덕션 이미지 재빌드 전까지 유지. Pass 2 채점 시 per-scenario max 에서 -1 유지.
- UJ2-switch-강남-종로 의 `card_district_name_any` 미충족: recommend card 의 `district_name` 노출은 frontend 스키마 변경 요구 (deferred)

## 7. Pass 2 / Pass 3 결과

### Pass 2 (P0+P1+P2 fix 반영)
- Avg **97.5%** · 15 PASS / 1 FAIL (from Pass 1 71.3% · 9/7). Delta **+26.2%p**.
- 남은 1 FAIL = UJ2-잠실-신촌 (75%) — "대학가 상권이랑 번화가 상권 차이점 알려줘" 의 compare-coref 패턴 미매치 + 다중매치 시 summary 로 넘어감.

### Pass 3 (rule classifier 다중매치 우선순위 + history fallback guard 완화)
- Avg **99.1%** · **16 PASS / 0 FAIL**. Delta vs Pass 1 **+27.8%p**, vs Pass 2 **+1.6%p**.
- 추가 fix:
  - `_classify_by_rules` 다중매치 시 `(comparison, simulation, risk, recommendation, category_analysis)` 우선 반환 → "차이" + "알려줘" 가 comparison 으로 확정
  - Comparison 분기의 history fallback 을 `len(referenced_districts) < 2` 단일 가드로 완화 (compare-coref 패턴 guard 제거) — elif 에서 district_code 1개 들어간 뒤에도 history 추가 주입 가능

### Per-scenario Δ

| ID | Pass 1 | Pass 2 | Pass 3 |
|---|---:|---:|---:|
| UJ1-cafe-startup-강남 | 83% | 100% | 100% |
| UJ1-restaurant-홍대 | 83% | 100% | 100% |
| UJ1-retail-성수 | 80% | 100% | 100% |
| UJ1-pub-건대 | 50% | 100% | 100% |
| UJ2-switch-강남-종로 | 71% | 86% | 86% |
| UJ2-switch-홍대-성수 | 33% | 100% | 100% |
| UJ2-switch-명동-남대문 | 75% | 100% | 100% |
| UJ2-switch-잠실-신촌 | 50% | 75% | 100% |
| UJ3-3way-major | 86% | 100% | 100% |
| UJ3-3way-retail-hubs | 83% | 100% | 100% |
| UJ3-3way-young-picks | 83% | 100% | 100% |
| UJ3-3way-cafe-best | 86% | 100% | 100% |
| UJ4-full-report-강남 | 80% | 100% | 100% |
| UJ4-report-from-recommend | 80% | 100% | 100% |
| UJ4-report-from-compare | 50% | 100% | 100% |
| UJ4-long-synthesis | 67% | 100% | 100% |

## 8. Metadata

- Author: Claude (Opus 4.7)
- Plan type: qa
- Related plans: `docs/plan/qa/e2e-quality-improvement-2026-04-24.md` (intent-coverage 선행)
- Scenarios: `scripts/eval/user_journey_scenarios.py`
- Runs: `docs/qa/runs/user-journey-2026-04-24/pass{1,2}/`
