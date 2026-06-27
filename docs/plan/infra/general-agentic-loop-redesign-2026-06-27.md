# 범용 Agentic Loop 재설계 — 모델주도 + 구조적 grounded-answer 계약

> 유형: **Design Doc** (구현 계획 아님 — 코드 0). office-hours 2026-06-27 세션 산출물.
> 목표: 현재 고정 파이프라인 PAE 를 **Claude Code 류의 범용·안정 모델주도 루프**로 전환하는
> 아키텍처 비전. "현재 구현은 고려하지 말고 최종 목표(사용자에게 AI 로 가치 있는 서비스)
> 관점으로" 라는 사용자 지시에 따라 green-field 로 설계.

---

## 0. 결정 요약 (office-hours)

| 결정 | 값 | 근거 |
|---|---|---|
| 방향 (D1) | **범용성 우선 — 모델주도 루프로 전환** | 새 도구=새 능력. intent YAML 손대지 않고 질문 폭 확장 |
| 가치 축 (D2) | 대화연속성·기억 → 분석깊이·선제성 → 질문폭 → 신뢰 (사용자 우선순위 순) | 4축 모두. 단 **신뢰는 바닥 가드레일로 격상** |
| 루프 형태 (D3) | **B) 모델주도 + 구조적 grounded-answer 계약** | 범용성↑일수록 신뢰↓ 하는 근본 충돌을 *설계*로 해소 |
| 배포 형태 | C) fast-lane + deep-lane 로 B 를 감싸기 (현실적 구현 shape) | 모든 "안녕"에 전체 루프 비용 안 냄 |

### 도전된 전제 (Phase 3)

> **"모델 주도 = 자동으로 더 가치 있음"은 거짓.** 이 도메인의 사용자 가치는 *신뢰할 수 있는
> 데이터 해석*이다. 순수 ReAct 의 대표 실패모드 = 수치 날조. 이건 가상이 아니라 본 프로젝트가
> 이미 겪음 (2026-06-10 S7 coref: 도구 0건으로 유동인구 124,386/67,741 날조, "일평균>시간대최고"
> 물리 모순). **진짜 과제는 "모델주도 vs 고정"이 아니라 "오케스트레이션 자유는 최대로, 사실
> 주장에는 절대 안 깨지는 가드레일"이다.** Claude Code 가 범용이면서 안정적인 이유도 모델 자유가
> 아니라 *하네스 불변식* 때문. 이 도메인의 "컴파일러"는 도구가 반환한 DB 값이다.

---

## 1. 목표 아키텍처

```
USER MESSAGE
 │
 ├─[1. Context Assembly]   영속 메모리 recall + 세션 히스토리 + 선택 상권 + 토큰버짓 인지 조립
 │
 ├─[2. Agentic Loop]   ◀── 모델주도, budget-bounded. (고정 max_rounds=3 폐기)
 │     while not done and budget remains:
 │       모델 턴 → tool_use(들) 발행  OR  최종응답 신호
 │       도구결과 → fact store 에 typed fact 로 적재 (= ground truth)
 │     도구 표면: 도메인9 + resolve_district + list_categories + get_benchmark
 │                + compute + recall_memory + abstain + render_card
 │
 ├─[3. Trust Kernel]   ◀── 키스톤. 최종답의 모든 수치·사실 주장을 fact ref 에 바인딩
 │     → 검증(±tol) → 미바인딩 숫자: strip / correct / force-recall / abstain
 │     불변식: "숫자는 fact store 에서만 나온다. 모델 기억에서 originate 불가."
 │
 ├─[4. Proactive Reflection]   "안 물었지만 필요한 것?" → fact 기반 grounded 제안
 │
 ├─[5. Stream]   SSE: thinking / tool / tool_end / card / text / suggestion / warning / done
 │
 └─[6. Memory Write-back]   턴 영속화 + durable fact 추출 (장기기억)
```

핵심 전환: **Planner(intent분류+plan템플릿) 와 Evaluator(충분성판정) 노드를 삭제**한다.
그 두 책임은 루프 자체로 흡수된다 — 모델이 매 스텝 "무엇을 더 부를지/끝낼지"를 관찰 기반으로
결정하기 때문. 남는 명시적 단계는 컨텍스트 조립 / 루프 / **Trust Kernel** / reflection / 메모리.

---

## 2. 컴포넌트별 설계

### 2.1 Agentic Loop (PAE 그래프 대체)

- **네이티브 function-calling**. `intents.yaml` 정규식·plan 템플릿 전부 삭제. 모델이 도구를
  자유 조합 → 새 질문 유형마다 코드 수정 불필요 (= 질문 폭 가치축).
- **창발적 다단계 체이닝**으로 분석 깊이 확보: 모델이 요약을 보고 close_rate 가 높으면 스스로
  risk 도구를 부르고 종합 — 고정 plan 으론 불가능한 깊이.
- **Budget Governor** 가 max_rounds 를 대체:
  - 토큰 버짓 (입력+출력 누적 상한)
  - 도구 호출 횟수 상한 (예: 12)
  - wall-clock 상한 (예: 45s)
  - 루프 스텝 상한
  - 소진 시 → 모인 fact 로 grounded 최종 강제 + 공백은 abstain. (무한루프·폭주 백스톱)

### 2.2 Fact Store (ground truth 레이어)

- 도구는 free dict 가 아니라 **typed fact** 를 반환·등록한다. 각 fact 는 안정적 ref id 보유:
  - 예: `fact:get_floating_population:3120103:hourly_total = 4,106,209 (unit=people, quarter=2025Q4)`
- 한 턴의 모든 도구 결과가 fact store 에 누적 → Trust Kernel 의 검증 기준이자 모델 컨텍스트의
  ground truth.
- **단위·의미를 fact 에 명시** (현재 `daily_avg` 가 실제론 분기 시간대 합계인데 이름이 오해를
  부른 그 버그류를 구조적으로 차단 — fact 는 `hourly_total` 처럼 정직한 라벨 + unit 보유).

### 2.3 Trust Kernel — 구조적 grounded-answer 계약 (B 의 본체)

목표: **범용성을 키워도 수치 신뢰가 깨지지 않게 *구조적으로* 보장.** 사후 경고(현 numeric_sanity)
가 아니라 하드 게이트.

설계 (단계적 강도):

1. **숫자 바인딩 불변식 (필수)**: 최종 사용자 텍스트의 모든 수치 토큰은 fact store 의 어떤 fact
   와 ±tolerance 내 일치해야 한다. 미바인딩 숫자는 (a) strip, (b) 가장 가까운 fact 로 correct,
   (c) 해당 주장 abstain, (d) 도구 force re-call 중 정책에 따라 처리. **모델 기억발 숫자 = 통과 불가.**
2. **파생수치는 `compute` 도구로**: 비율·증감·월환산 등 산술을 모델 암산에 맡기지 않는다.
   (S7 의 "÷30 일평균" 날조 = 모델 암산이 근원). 화이트리스트 산술만 도구로 허용 → 결과도 fact.
3. **abstain 을 1급 도구로**: 데이터 부족·범위 밖(서울 외)일 때 모델이 `abstain` 호출 → 정직한
   "모름/범위 밖" 응답. 추측 금지를 거부가 아니라 *능동 선택지*로.
4. **구현 형태 (점진)**:
   - v1: prose 는 자유, **숫자만** 바인딩·검증 (가장 적은 UX 마찰).
   - v2: 핵심 주장에 출처 칩(어느 도구·필드) 노출 → 사용자 "이 숫자 믿고 투자" 수준.
   - v3: 완전 구조화 출력(segment+refs) → 렌더 시 인용 자동.
- 산출: trust-gate outcome 을 관측 지표로 (numbers_bound_rate / correction_rate / abstain_rate).

### 2.4 메모리·연속성 (가치축 1순위)

- **세션 영속화**: 현재 인메모리 10턴·30분 TTL·재시작 유실 → Redis(또는 PG) 영속. 세션 키 기준
  히스토리 복원. (백엔드 문서 §7 의 "프로덕션에서 Redis/Postgres 이관 고려" 를 본 설계에서 실행.)
- **장기 사용자 기억 (v2)**: durable fact 추출 ("이 사용자는 성수 관심, 카페 창업 검토중") →
  `recall_memory` 도구로 모델이 조회. "저번에 본 성수" 류 coref 를 세션 넘어 해소.
- **write-back**: 턴 종료 시 대화·durable fact 영속화. 모델주도 — 무엇을 기억할지 모델이 판단.

### 2.5 선제성·깊이 (가치축 2순위)

- 루프의 다단계 체이닝이 깊이의 1차 동력 (2.1).
- **Proactive Reflection 단계**: 최종 fact 확보 후 값싼 모델 패스 — "지금 결과 기준, 이 사용자가
  안 물었지만 실행할 다음 1~2 가지는?" → 템플릿 제안(현 evaluator 의 하드코딩 4종)이 아니라
  fact 기반 *맞춤* 선제 제안. 단, 제안도 Trust Kernel 적용 (날조 제안 금지).

### 2.6 질문 폭 (가치축 3순위)

- **엔티티 해석을 도구로 위임**: `resolve_district`(fuzzy + 후보 반환), `list_categories`,
  `get_benchmark`, `compute`. Planner 의 fuzzy 매칭("강남"vs"강남역" 트랩)·캐시부재 latency 를
  모델이 도구로 직접 해소. 모호하면 모델이 후보를 받아 사용자에게 되물음 (clarification 도 창발).
- **카드도 도구로**: `render_card(type, data)` — 모델이 카드가 도움될 때 호출. tool→card 자동매핑
  제거. (트레이드오프: 모델 부담↑. v1 은 자동매핑 유지 후 점진 이관 가능.)

### 2.7 안정성 하네스 (Claude Code 급 견고함)

도메인 무관, 범용 루프의 토대 — **전부 office-hours 매핑에서 실사실로 확인된 현 취약점 해소**:

- **모델 레지스트리**: 모델 ID 하드코딩(`graph.py:74,96` `claude-sonnet-4-6`) 제거 → config/DB
  기반 `role → ordered [(provider, model_id)]` + liveness + fallback 체인. (이번 달 죽은 ID 로
  전량 실패한 그 자리를 구조적으로 차단.)
- **request-scoped DI**: 전역 가변 `_anthropic_valid`, 모듈 싱글톤 `_llm_circuit_breaker` 제거 →
  provider health 객체 + TTL 회복. 한 요청 실패가 전 사용자에 전파되지 않게.
- **에러 분류 체계**: top-level `except Exception` 하나 → `UserInputError / ToolError /
  ProviderError / TrustViolation / BudgetExceeded` 타입별 복구·SSE 이벤트.
- **컨텍스트 매니저**: Respond 의 13섹션 무한 조립 → 토큰 인지 truncation/summarization.
  fact store·히스토리가 윈도우 초과 시 요약·절단.
- **관측**: 루프 이터레이션·tool_use 마다 span. Trust-gate·budget·fallback 을 점수로
  (기존 Langfuse 11차원/6스코어 위에 확장).
- **취소·백프레셔**: 기존 per-session abort + bounded SSE queue 유지·일반화.

---

## 3. 대안 비교 (Phase 4 — 기록)

| | A) 순수 ReAct + 사후 신뢰게이트 | **B) 모델주도 + 구조적 계약 (채택)** | C) fast/deep 하이브리드 |
|---|---|---|---|
| 범용성 | 최대 | 최대 | 최대(deep), 고정(fast) |
| 신뢰 확보 | 사후 검출(반응적) | **생성 구조로 보장(능동)** | B 와 동일 + fast 결정성 |
| 비용·레이턴시 | 높음 | 중 | **최적** (흔한질문 fast) |
| 구현 난이도 | 낮음 | 중(계약·인용 UX) | 높음(2경로+라우터) |
| 리스크 | 날조 잔존 | 모델 compliance(eval 필요) | 라우터 오분류 |

**채택: B 를 엔진으로, C 를 배포 형태로.** B 가 4 아키텍처(A/B/C 및 D1 의 PAE-hardening) 중
유일하게 "범용성↑ ↔ 신뢰↓" 근본 충돌을 설계로 해소. C 는 별개 안이 아니라 B 를 비용 효율적으로
배포하는 wrapper (fast-lane = 인사·단일요약·프리뷰 = 트래픽 80%, 결정적·무비용·날조0).

---

## 4. 리스크 & 미해결 질문

| 리스크 | 완화 |
|---|---|
| 모델이 계약(숫자 바인딩) 비준수 | numbers_bound_rate eval 게이트 (기존 accuracy harness 확장). v1 은 숫자만 바인딩으로 마찰 최소화 |
| 구조화 출력·검증이 레이턴시 추가 | C 의 fast-lane 으로 흔한 질문 우회. 스트림 중 점진 검증 |
| 토큰 비용 증가 (다단계 루프) | Budget Governor + fast-lane + 도구결과 요약 |
| 메모리 영속화 = 새 인프라(Redis 세션) | 이미 Redis 운용중 — 캐시 옆 세션 store 추가 |
| 카드 도구화로 모델 부담↑ | v1 자동매핑 유지 → 점진 이관 |
| **미해결**: 인용 UX 의 시각 형태 (칩? 각주? 호버?) | design-consultation 트랙 분리 |
| **미해결**: fast/deep 라우터를 rule 로 vs 소형 모델로 | 측정 후 결정 (오분류율 vs 비용) |
| **미해결**: 장기기억의 프라이버시·보존 정책 | Phase 2(인증) 와 연동 필요 |

---

## 5. The Assignment (다음 실제 행동)

설계를 *증명*하려면 코드 대청소 전에 **Trust Kernel 의 핵심 불변식이 실제로 날조를 막는지**부터
1개 슬라이스로 검증한다. (office-hours 원칙: 전략이 아니라 행동 하나.)

> **1주 spike**: 모델주도 루프의 최소 슬라이스 하나 —
> "홍대랑 성수 비교 → 거기 중 유동인구 더 많은 곳?" (= S7 회귀 케이스) — 를
> ① 네이티브 function-calling 루프 + ② fact store + ③ **숫자 바인딩 하드게이트** 만으로 구현해,
> 도구 강제 없이도 **미바인딩 숫자가 구조적으로 못 나가는지** 5회 라이브로 확인.
> 성공 기준: 날조 0/5 (현 PAE 는 planner force-plan 패치로 해결 — B 는 *계약*만으로 해결되는지가 증명점).

이 spike 가 통과하면 B 의 핵심 베팅(범용 자유 + 구조적 신뢰)이 입증된 것 → 그때 메모리·하네스·
C 배포로 확장. 실패하면 계약 강도(v1→v2)나 force-recall 정책을 조정 후 재시도.

---

## 6. 메타데이터

- 세션: office-hours 2026-06-27
- 후속 트랙: design-consultation(인용 UX) · accuracy eval harness 확장(bound_rate) · Phase2(장기기억 프라이버시)
- 본 문서는 비전. 구현 착수 시 `/plan-new infra <slice>` 로 표준 5섹션 실행계획 분리 작성 권장.
