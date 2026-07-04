# Accuracy Eval Round 4 — Verdict (2026-07-04)

> **GATE PASS 4/4 → v2 prod 배포 진행.**
> Rubric: 6축(Depth/Context/Derived/Structure/Actionable/Accuracy) × 2점 = 12 → /1.2 = 10점 환산 (R2/R3 동일).
> 수집: e2e 스택 `:8002` (USE_MOCK=false · 1,650 상권 · anthropic · `agent_loop_version=v2` + **P1/P2 fix 반영 이미지** 컨테이너 내 grep 확인). fresh volume(corrected seed: worker_sum=4,724,265 · aliases=32) + 캐시 flush + GT 현 DB 재쿼리. message-only(WITH_CODES=0), `curl -sN --max-time 180`, 8런 전부 done=1 절단 0.

## 대상

Round 3 (2026-07-03) GATE FAIL 2/4 의 재측정 3건 + S7 smoke. 선행 fix (Phase 0, 이 세션):

- **P1 (Trust Kernel fallback 붕괴)**: RC1 `#N` 접미키 매칭 전멸 → `_collect_tool_scalars` split 정규화 / RC2 `_COMPOUND_RE` "3억 5,000만원"→300,005,000 오파싱 → lo_unit 확장+필수화 / RC3 fact_pool truncate본 vs ToolMessage 전체본 불일치 → 원본 저장 / RC4 still-unbound 1개에도 전체 대체 → `should_fallback`(≥3 AND ≥50%) + 마스킹 보존 + 라벨된 fallback + 카드 존재 시 abstention 금지
- **P2 (S8 스케일 오기)**: RC5 원화 floor(10M) 미만 무검증 → `find_scale_mismatches`(×10/×100 typed 매칭) + 교정 힌트 + 프롬프트 자릿수 규칙
- 회귀 가드: `test_trust_kernel_regressions.py` 19케이스 (전체 pytest 187 passed)

## 게이트 재판정

| 기준 | 결과 | 판정 |
|---|---|---|
| ① 평균 ≥ 9.0 | (이월 50.0 + S2 10.0 + S4 10.0 + S8 10.0) / 8 = **10.0** | ✅ |
| ② S2·S4·S8 각각 R2(=10.0) 이상 | 3건 전부 10.0 | ✅ |
| ③ 재측정 .sse 전건 날조 0 | 0/8 (전 수치 tool/카드-bound, GT 교차검증 일치) | ✅ |
| ④ S7 ≥ 9.3 (이월 + smoke 재확인) | smoke PASS — tool 강제 발화 유지 · 4,106,209/1,092,973 GT 정확 · 참조 일관 | ✅ |

## 시나리오별 스코어 (R2 → R3 → R4)

| 시나리오 | R2 | R3 | **R4** | 근거 |
|---|---:|---:|---:|---|
| S2 서울역 상권 분석 | 10.0 | 3.3 | **10.0** (×2) | 6 tool + compute×3~4, 카드 2장(summary+risk). 분기 fp 1,022,060 · 월매출 200.6억 · 점포당 2,287만 · 877개 · 객단가 23,551원 전부 GT 정확. 6섹션 라벨링 분석 + 별점 시사점. **abstention 유출 0/2** (R3 1/2) |
| S4 건대 창업 추천 | 10.0 | 3.3 | **10.0** (×2) | recommend 카드 + 라벨된 TOP5 표. 편의점 per_store 184,053,847=GT(1,472,430,777/8) 정확, 2~5위 매출·점포수 전부 카드/GT 일치. **무라벨 나열 0/2** (R3 2/2 결정론 재현이던 것 소멸) |
| S8 성수역·건대 비교 | 10.0 | 9.2 | **10.0** (×2) | resolve×2→compare→fp×2→compute×4. fp 1,412,369/2,771,403 · 매출 221억/260억 · **점포당 "약 1,450만/1,683만 원" = 14,503,839/16,829,233 스케일 정확** (R3 "145만/168만" 10배 축소 해소). 파생(1.96배/+17.5%/+16%/1.4%p) 전부 compute-bound |
| S7 coref smoke | 5.0 | 10.0 | **10.0 (이월+smoke)** | 2턴 동일 세션: get_floating_population×2 + resolve + compute 강제 발화, 직전 비교와 참조 상권 일관(성수동카페거리 3110131), 날조 0 |
| S1/S3/S5/S6 | — | 10.0 | 10.0 (이월) | R3 만점 고정 (plan 규정) |

**종합 평균: 10.0** (R2 9.4 → R3 8.2 → R4 10.0)

## P1 fix 라이브 실증 (trust 로그)

backend 로그 grep(`trust|unbound|fallback|mask`) 전체 결과 **단 1줄**:

```
trust: 1 unbound / 0 scale-suspect numbers, corrective pass   (S2 run1 진행 중)
```

- `still unbound → deterministic fallback` **0건** · 마스킹 0건 — 교정 패스 1회로 해결, 응답 대체(붕괴) 미발생. 해당 런(S2 run1)의 최종 text 는 완전한 라벨링 분석 → **교정 성공 시 fallback 미진입 경로 실증**.
- 나머지 7런은 trust 개입 자체 0회 (초안부터 전 수치 bound — RC1/RC2 파싱·매칭 fix 로 오탐 소멸).

## 관찰 (비차단)

1. S2 run1 "서울 평균 폐업률 6.5%" vs run2 "5.9%" — **둘 다 tool 반환값** (summary 카드 `closeRate.average=6.5` / benchmarks `seoulAvg.close_rate=5.9`, 카드 payload 에서 직접 확인). 날조 아님. 모델이 '서울 평균' 라벨로 어느 필드를 집는지가 런 간 비결정 — 라벨 정합성 follow-up 후보.
2. done 이벤트 `trace_id` 미동봉 — e2e 스택 Langfuse 미설정(키 없음) 기인, prod 무관.
3. S7 "성수" → 성수동카페거리(3110131) resolve — R3 run1 과 동일 선택, 2턴 참조 일관이므로 정합.

## 결론

R3 의 P1(가용성 손실)·P2(스케일 오기) 모두 **재현 0** — 근본원인 5건(RC1~RC5) fix 가 라이브에서 유효함을 실증. 게이트 4/4 PASS 로 plan 규정에 따라 **v2 prod 배포 진행** (배포 시 `flush_cache.py` 필수).

산출물: `S{2,4,8}[-run2].sse` + `S7[-pre].sse` 8개 + `_parsed.md` + 본 verdict.
