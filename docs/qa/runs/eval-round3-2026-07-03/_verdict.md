# Accuracy Eval Round 3 — Verdict (2026-07-03)

> Plan: [accuracy-eval-round3-prod-deploy-2026-07-03.md](../../../plan/qa/accuracy-eval-round3-prod-deploy-2026-07-03.md)
> Rubric: 6축(Depth/Context/Derived/Structure/Actionable/Accuracy) × 2점 = 12 → /1.2 = 10점 환산 (R2와 동일)
> 대상: **v2 agentic loop** (모델주도 function-calling + Trust Kernel, `ecfdf17` 머지 트리). e2e 스택 `:8002`, USE_MOCK=false, 1,650 상권, LLM_PROVIDER=anthropic, `agent_loop_version=v2` (B1 확인).
> 수집: message-only(WITH_CODES=0) — R2와 동일 entity-linking 포함 검증. Raw: `S{1..8}.sse` + `S7-{pre-,}run2.sse`(재현율) + `S{2,4}-run2-diag.sse`(진단, 공식 채점 외).
> GT: **현 e2e DB 스냅샷 기준**(06-25 데이터fix 반영 후). `done.trace_id=-` 는 expected(e2e Langfuse 키 공란, 채점 항목 아님).

## 종합 결과 — **GATE FAIL (2/4 미달) → 배포 정지**

| Gate 항목 | 기준 | 결과 | 판정 |
|---|---|---|---|
| 종합 평균 | ≥9.0 | **8.2** | ❌ |
| 시나리오별 R2 점수 이상 | S1~S6,S8=10.0 · S7≥5.0 | S2 3.3 · S4 3.3 · S8 9.2 | ❌ (3건 미달) |
| 수치 날조 | 0건 | **0건** | ✅ |
| S7 coref | ≥9.3 | **10.0** (재현 2/2) | ✅ |

**핵심**: R2 최대 결함이던 **S7 coref 날조는 구조적으로 해소**(2/2 tool 강제 호출·전 수치 DB 정확·참조 일관). 그러나 **v2 Trust Kernel의 deterministic fallback이 신규 회귀 축**으로 등장 — 카드·도구 데이터가 전부 정상인데 최종 텍스트를 abstention(S2) 또는 무라벨 숫자 나열(S4)로 대체해 분석 리포트 가치를 붕괴시킴. S8은 텍스트에서 점포당 월매출을 10배 축소 오기(카드값은 정확).

## KPI 추이 (R1 → R2 → R3)

| 지표 | R1 (04-13, PAE) | R2 (06-10, PAE) | R3 (07-03, v2) |
|---|---:|---:|---:|
| 종합 평균 | 8.0 | 9.4 | **8.2** |
| S7 coref | 8.9 | 5.0 (날조) | **10.0** (tool-backed 2/2) |
| tool-backed 수치 날조 | ~15% | 1/1 (tool-less) | **0** |
| 만점(10.0) 시나리오 | — | 7/8 | 5/8 |
| 신규 결함 축 | — | S7 tool-less 날조 | **Trust fallback 텍스트 붕괴 (S2·S4)** |

## 시나리오별 스코어

| ID | 입력 | tool → card | R2 | R3 | 비고 |
|---|---|---|---:|---:|---|
| S1 | 강남역 요약 | get_district_summary → summary | 10.0 | **10.0** | 분기 745.3만·1,396억·폐업 2.3%·peak 165만 전부 GT 일치. **'분기 유동인구' 라벨 정확(929885b fix 작동)** |
| S2 | 서울역 분석 | summary+risk 카드 2장 + tool 6회 + compute 3회 | 10.0 | **3.3** | 카드 데이터 전부 정확(fp 1,022,060 GT)·최종 텍스트가 **trust fallback abstention**("확인된 데이터를 가져오지 못했습니다") — 재현 1/2 (diag 2회차는 정상 풀리포트) |
| S3 | 홍대 vs 성수 매출 비교 | resolve→sales×2→compute×2 | 10.0 | **10.0** | "성수"→성수동카페거리(3110131) 명시 resolve. 532억/177억·192만/32.8만 건·객단가 27,641/54,082·주말 35.4/31.0% 전부 DB 정확 |
| S4 | 건대 추천 | recommend_business → recommend | 10.0 | **3.3** | 카드 정상(편의점 8점포 #1 — ISSUE-003 floor 유지)·최종 텍스트가 **trust fallback 무라벨 숫자 나열** — **재현 2/2 결정론적** (diag byte-동일) |
| S5 | 명동 리스크 | store_info+store_history → risk | 10.0 | **10.0** | 1,712점포·개 64/폐 44·2.6%·프랜차이즈 237(13.8%)·일반의류 335/한식 176/화장품 162 전부 DB 정확 |
| S6 | 강남역 카페 매출 | simulate_revenue("카페"→CS100010) → simulation | 10.0 | **10.0** | avg 3,864만 = GT(45.98억/119) 정확(c5aee3c fix 작동)·p25 1,615만/p75 9,095만·객단가 12,000(RC2 fix)·서울대비 +254.9% |
| S7 | (비교 후) 거기 중 유동인구 많은 곳? | **get_floating_population×2 + resolve + compute** | 5.0 | **10.0** | run1: 성수동카페거리 1,092,973 GT 정확·3.8배. run2: 성수역 1,412,369 GT 정확·2.9배·야간 5배(564,539/109,821 DB 정확). **양 run 모두 직전 비교와 참조 일관·날조 0·물리모순 0** |
| S8 | 홍대 말고 성수역·건대 비교 | resolve×2→compare→fp×2→compute×4 | 10.0 | **9.2** | 배제토큰 정확. fp 1,412,369/2,771,403·심야 136,547/465,878·매출 221억/260억 전부 DB 정확. **단 텍스트 점포당 월매출 "145만/168만" — 카드 실값 1,450만/1,683만의 10배 축소 오기** (Accuracy 1/2) |

**6축 상세 (미달 3건)**
- S2 = Depth 0 · Context 1 · Derived 0 · Structure 1(카드) · Actionable 0 · Accuracy 2(노출 수치 전부 정확·날조 0) = 4/12 → 3.3
- S4 = Depth 0 · Context 1 · Derived 0 · Structure 1(카드) · Actionable 0 · Accuracy 2(나열 8수치 전부 카드 일치) = 4/12 → 3.3
- S8 = Depth 2 · Context 2 · Derived 2(1.96배·+17.5%·+16.0%·1.4%p compute 정확) · Structure 2 · Actionable 2 · Accuracy 1(10배 오기 1건) = 11/12 → 9.2

## DB 교차검증 (GT = 현 e2e DB 2025Q4 스냅샷)

| 항목 | 응답 | DB GT | 판정 |
|---|---:|---:|---|
| 강남역 월매출 | 1,396억 | 139,568,168,200 | ✅ |
| 강남역 분기 유동인구 | 745만 3천 | 7,453,202 | ✅ (라벨 '분기' 정확) |
| 강남역 peak(17시) | 165만 | 1,653,367 | ✅ |
| 서울역 분기 유동인구(카드) | 102만 2천 | 1,022,060 | ✅ |
| 홍대 월매출 | 532억 | 53,200,280,285 | ✅ |
| 성수동카페거리 월매출 | 177억 | 17,737,244,309 | ✅ |
| 홍대/성수동 결제건수 | 192만/32.8만 | 1,924,711/327,970 | ✅ |
| 홍대/성수동 주말비중 | 35.4%/31.0% | 35.4/31.0 | ✅ |
| 건대 추천 #1 편의점 | 월 14.7억/8점포 | 1,472,430,777/8 | ✅ (store floor ≥3 유지) |
| 명동 점포/개/폐 | 1,712/64/44 | 1,712/64/44 | ✅ |
| 강남 카페 시뮬 avg | 3,864만 | 45.98억/119 = 38,636,376 | ✅ |
| S7 유동인구 (run1/run2) | 4,106,209 vs 1,092,973 / 1,412,369 | 동일 | ✅ |
| S8 심야(0시) | 136,547/465,878 | 동일 | ✅ |
| S8 점포당 월매출 (텍스트) | **145만/168만** | 14,503,839/16,829,233 | ❌ **10배 축소** (카드값은 정확) |

⚠ R2 대비 delta 주석: "성수" resolve가 R2 성수역(3120052) → R3 성수동카페거리(3110131)로 변경(S3·S7 run1). 06-25 aliases 시드 + v2 자유 resolve 결과이며 응답이 상권명을 명시 표기하고 수치가 해당 상권 GT와 정확 일치하므로 **오매핑 아님**. S7 run2는 성수역 resolve — 세션별 비결정 범위.

## 신규 P1 — Trust Kernel deterministic fallback의 응답 붕괴 (S2·S4)

- **증상**: draft 생성 → Trust Kernel이 unbound number 검출 → 교정 패스 → **여전히 unbound → deterministic fallback이 전체 답변 대체**.
  - S2: "죄송합니다. 요청하신 내용을 뒷받침할 확인된 데이터를 가져오지 못했습니다" (카드 2장이 실데이터로 이미 발행된 상태에서)
  - S4: "확인된 데이터 기준으로만 정리하면 다음과 같습니다: - 약 14.7억원 - 8개 …" (업종명 없는 숫자 나열)
- **로그 증거** (`engine.py:238/257`): S2 = `trust: 1 unbound → corrective → 1 still unbound → deterministic fallback` · S4 = `4 unbound → 2 still → fallback`. 두 건 모두 해당 `agent_done` 직전 발생, 나머지 6 시나리오는 trust 이벤트 0.
- **재현성**: S2 **1/2 (비결정)** — diag 재실행은 trust 미발동·정상 풀리포트. S4 **2/2 (결정론)** — diag가 byte-동일 fallback + 동일 trust 로그(4→2).
- **분류**: 날조 아님(fallback 수치는 전부 tool-bound 정확). **과잉 방어에 의한 가용성 손실** — 07-02 fix(7cae440)가 메타발화 유출은 막았으나, 교정 실패 시 fallback 산출물 품질(무라벨 나열/불필요 abstention)이 리포트 수준에 못 미침.
- **권고(fix 방향, 사용자 결정 대기)**: ⓐ fallback 렌더러에 tool 결과의 라벨(업종명·지표명) 바인딩 ⓑ unbound number만 제거·마스킹하고 나머지 draft 보존 ⓒ 교정 패스에 unbound 목록 명시 전달(현재 교정이 무엇을 고칠지 모른 채 재작성하는 것으로 추정) ⓓ 카드 발행 완료 시 abstention 대신 카드 참조 응답. S4가 결정론적이므로 회귀 테스트 작성 용이.

## 신규 P2 — S8 텍스트 단위 축소 오기

- sales_per_store 14,503,839 → 텍스트 "145만 원"(만 단위 환산에서 10배 축소). 비교 방향·백분율(+16.0%)은 정확. 억/만 환산 가드(respond 규칙 또는 trust 바인더의 스케일 검증)에 케이스 추가 권장.

## 결론

- ✅ **S7 coref 구조 해소 실증** — R2 유일 P1이 v2에서 만점 전환(재현 2/2). Trust Kernel의 도구 강제·수치 바인딩이 의도대로 작동.
- ✅ **날조 0 유지** — 노출된 모든 수치가 tool/카드 기원. 06-25 데이터fix + 07-02 5fix(라벨·시뮬 resolve) 라이브 검증 완료.
- ❌ **GATE FAIL** — 평균 8.2(<9.0), S2·S4·S8이 R2 미달. **prod 배포 정지** (plan gate 규정). Trust fallback P1 fix 후 R3 재실행(S2·S4·S8만 재측정도 가능) 권장.
