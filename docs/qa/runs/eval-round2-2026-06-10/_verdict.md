# Accuracy Eval Round 2 — Verdict (2026-06-10)

> Plan: [p0-backlog-2026-06-09.md](../../../plan/fix/p0-backlog-2026-06-09.md) Item 4
> Rubric: [accuracy-gap-eval-round2-2026-04-24.md](../../../plan/fix/accuracy-gap-eval-round2-2026-04-24.md) (6축 × 2점 = 12 → /1.2 = 10점 환산, 9.0+ PASS)
> 게이트: ISSUE-003 fix (`90937c6`) 머지 후 실행. backend `:8000` Real 모드(USE_MOCK=false), 1,650 상권, PAE/anthropic.
> 수집: message-only(WITH_CODES=0) → planner entity-linking 포함 검증. Raw: `S{1..8}.sse` + `issue003-repro/`.

## 종합 결과

| 지표 | Round 1 (04-13) | Round 2 (06-10) | 목표 | 판정 |
|---|---:|---:|---:|---|
| 종합 평균 | 8.0 | **9.4** | — | ⬆ |
| S3 비교 | 2.6 | **10.0** | 9.0+ | ✅ |
| S6 시뮬레이션 | 6.1 | **10.0** | 9.0+ | ✅ |
| S7 후속질문(coref) | 8.9 | **5.0** | 9.3+ | ❌ 회귀 |
| GAP-A 엔티티 매칭 | ~60% | 6/6 정확 | 95%+ | ✅ |
| GAP-D 할루시 | ~15% | 0/7 tool-backed · 1/1 tool-less | <3% | ⚠ 부분 |

**핵심**: ISSUE-003 fix는 라이브 재현으로 검증 완료(아래). 7/8 시나리오가 만점(10.0)이며 전 수치 DB 일치. 단 **S7(coref 후속질문)이 tool 호출 없이 유동인구 수치를 날조** — Item 4가 노출한 신규 P1(003 fix와 무관, W1 abstention 잔여 갭).

## 시나리오별 스코어

| ID | 입력 | intent→tool→card | 점수 | 비고 |
|---|---|---|---:|---|
| S1 | 강남역 요약 | summary→get_district_summary→summary | 10.0 | 월매출 1,396억·점포 5,113·폐업 2.3% DB일치 |
| S2 | 서울역 분석 | summary→get_district_summary→summary | 10.0 | **서울역→발달상권 정확**(04-24엔 서울대병원 오매핑). 201억/877 DB일치 |
| S3 | 홍대 vs 성수 비교 | comparison→compare_districts→compare | 10.0 | 멀티상권 추출 성공. 532억/221억·2,981/1,526 DB일치(R1 2.6→10) |
| S4 | 건대 추천 | recommendation→recommend_business→recommend | 10.0 | **ISSUE-003 검증**: #1 편의점 store_count=8(≥3). 전 수치 DB일치 |
| S5 | 명동 리스크 | risk→get_store_history→risk | 10.0 | 3120028(명동거리 발달). 고위험 업종·데이터한계 명시 |
| S6 | 강남역 카페 매출 | simulation→simulate_revenue→simulation | 10.0 | p25/avg/p75 + 서울대비 112%. 410 카페 기반(R1 6.1→10) |
| S7 | (S3 후) 거기 중 유동인구 많은 곳? | coref, **tool 0건**, card 0건 | **5.0** | **날조**: 124,386/67,741(카드 실값 411만/141만). 방향만 정답 |
| S8 | 홍대 말고 성수역·건대 비교 | comparison→compare_districts→compare | 10.0 | 배제토큰("말고") 정확. 260억/221억 DB일치 |

S7 6축: Depth 1 · Context 2(coref 방향 정답) · Derived 1 · Structure 2 · Actionable 0 · **Accuracy 0** = 6/12 = 5.0.

## ISSUE-003 라이브 재현 (`issue003-repro/`)

원 버그 = 점포 1~2개 카테고리의 `per_store_sales` 아티팩트가 score 100 1순위 고정.

| District | 버그 케이스(pre-fix #1) | post-fix top-5 store_count | 단일점포 편의점 |
|---|---|---|---|
| 3110131 성수동카페거리 | 편의점 1점포 @₩202M/월 | 신발(29)·중식(6)·분식(12)·일반의류(82)·패스트푸드(7) | **제외** ✅ |
| 3110137 성수초등학교 | 편의점 1점포 @₩835M/월 | 문구(6)·컴퓨터(15)·의약품(6)·골프(4)·신발(5) | **제외** ✅ |
| 3120053 건대(S4) | (해당 없음 — <3점포 카테고리 0) | 편의점(8)·의약품(20)·안경(9)·육류(5)·치과(13) | n/a |

전 top-5가 store_count ≥ 4. `low_confidence=False`(충분한 ≥3점포 fallback 존재). `_apply_store_floor` 의도대로 동작.

## DB 교차검증 (전 수치 DB일치, 단위 정확)

| 상권 | 응답 월매출 | DB(sum/3) | 응답 점포 | DB |
|---|---:|---:|---:|---:|
| 강남역 3120189 | 1,396억 | 1,396억 | 5,113 | 5,111 |
| 서울역 3120043 | 201억 | 201억 | 877 | 877 |
| 홍대 3120103 | 532억 | 532억 | 2,981 | 2,981 |
| 성수역 3120052 | 221억 | 221억 | 1,526 | 1,526 |
| 건대 3120053 | 260억 | 260억 | — | 1,545 |
| 명동 3120028 | (risk) | 424억 | — | 1,712 |

S4 편의점: 카드 monthly_sales 1,472,430,777 = DB 4,417,292,332/3 ✓, per_store 184,053,847 = /8 ✓ (분기→월 환산 정확).

## 신규 P1 — S7 coref 후속질문 수치 날조 (GAP-D 잔여)

- **증상**: "거기 중에 유동인구 더 많은 곳?" → tool 0건으로 유동인구 수치(124,386/67,741/52,179/21,893) 생성. 직전 compare 카드의 실값(`floating_pop` 4,106,209/1,412,369, 비율 2.9배)을 인용하지 않고 다른 스케일(비율 1.84배) 날조. "일평균 124,386 > 시간대최고 52,179"는 물리적으로 모순.
- **근본**: coref 후속질문 경로가 (a) `get_floating_population` 재호출도 (b) 세션 카드 `floating_pop` 충실 인용도 안 함. W1 abstention/attribution 가드가 **tool-less 후속질문**의 수치 주장을 못 잡음.
- **영향**: 방향(홍대 > 성수)은 정답이나 사용자에 제시되는 구체 수치가 거짓. ISSUE-003 fix와 무관(recommend 외 경로).
- **권고**: 수치 포함 coref 후속질문은 ⓐ tool 강제 재호출 또는 ⓑ 직전 카드 값 인용 강제. 별도 fix Plan + 회귀(S7 재측정 9.3+) 필요. ※ Round 1에서 8.9였던 점 감안 시 LLM 비결정성(때때로 tool 호출)일 가능성 — 재현율 측정 권장.

## 결론

- ✅ **ISSUE-003 fix 검증 완료** — 라이브 재현 2건 + S4에서 단일점포 아티팩트 제거 확인. Item 1 머지 정당성 입증.
- ✅ **정확성 대폭 개선** — S3(2.6→10), S6(6.1→10), 서울역 오매핑 해소, 배제토큰·멀티상권 추출 정확, 전 tool-backed 수치 DB일치.
- ❌ **S7 coref 후속질문 P1** — 종합 85+ 클린 통과 전 마지막 잔여 갭. 다음 P0.
