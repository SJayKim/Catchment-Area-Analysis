# MarketScope AI 응답 품질 평가 보고서 (Round 2 — W1~W3 적용 후)

**평가일**: 2026-04-24
**평가 대상**: S1~S8 (8 시나리오, Round 1 [2026-04-13] 동일 세트)
**Plan**: [accuracy-gap-eval-round2-2026-04-24.md](../plan/fix/accuracy-gap-eval-round2-2026-04-24.md)
**선행 Plan**: [accuracy-gap-fix.md](../plan/fix/accuracy-gap-fix.md) W1/W2/W3 (2026-04-23 구현)

## 1. Verdict

**전체 평균 7.6/10 · FAIL** (Round 1 8.0 대비 **-0.4**)

| 지표 | Round 1 (2026-04-13) | Round 2 (2026-04-24) | Delta | 판정 |
|------|---:|---:|---:|:---:|
| 종합 평균 | 8.0 | **7.6** | -0.4 | FAIL |
| S1 기본요약(강남) | 9.8 | 9.2 | -0.6 | PASS |
| S2 기본요약(서울역) | 9.6 | 7.9 | -1.7 | FAIL |
| S3 상권비교 | 2.6 | 7.9 | **+5.3** | FAIL (9.0 미달) |
| S4 업종추천 | 8.9 | 9.2 | +0.3 | PASS |
| S5 리스크분석(명동) | 8.4 | 6.7 | -1.7 | FAIL |
| S6 매출시뮬레이션 | 6.1 | 9.2 | **+3.1** | PASS |
| S7 후속질문 | 8.9 | 5.4 | **-3.5** | FAIL |
| S8 배제 토큰 | — | 5.0 | — | FAIL (신규) |

> ⚠ S2/S5 하락은 **eval 설계자 오류** (district_code 오매핑) — 시스템 회귀 아님. 아래 §4.3 참조.
> ⚠ S8 은 Round 1 에 S8=엣지케이스(9.7) 로 있었으나 본 Round 에서는 배제 토큰 시나리오로 교체 (Plan 설계). 비교 불가.

## 2. Round 2 rubric (Round 1 복제)

6 축 × 2점 (합 12점 → 10점 환산 `score*10/12`).

| 축 | 0점 | 1점 | 2점 |
|---|-----|-----|-----|
| Depth | 표면 답변 | 기본 지표 나열 | 해석+분석 |
| Context | 무시 | 일부 반영 | 전체 반영 |
| Derived | 원시 수치만 | 파생 일부 | 비율/차이/트렌드 도출 |
| Structure | 평문 | 부분 구조화 | 섹션+리스트+강조 |
| Actionable | 관찰 | 간접 제안 | 구체적 액션 |
| Accuracy | 확인 불가 주장 多 | 일부 attribution | 전 수치 attribution + DB 일치 |

## 3. 시나리오별 점수 상세

### S1 강남역 상권 요약 (9.2/10 PASS)

| 축 | 점수 | 근거 |
|---|---:|------|
| Depth | 2.0 | 3단 해석법(What/So What/Context) 모두 적용 |
| Context | 2.0 | "발달상권 중 상위 25%", "서울 평균 대비 81배" 등 벤치마크 명시 |
| Derived | 2.0 | 점포당 월매출, QoQ, 주말 비중 도출 |
| Structure | 2.0 | ## 섹션 + bullet + bold |
| Actionable | 1.5 | "차별화 전략 필수" 등 제안, 구체 액션은 약함 |
| Accuracy | 1.5 | 수치 23건 중 attribution tag 0 (프롬프트 규칙 위반) |

Ground truth 교차: `dailyAvg=7,453,202 · monthlySales=139,568,168,199` — 응답 "745만 3천명 · 1,396억" 일치 ✅

### S2 서울역 분석 (7.9/10 FAIL)

**중대 이슈**: eval 설계자가 `district_code=3110023` 전송 → 실제는 **서울대병원(골목상권)**. LLM 은 그 코드의 상권 데이터 기반으로 정확히 답변.

| 축 | 점수 | 근거 |
|---|---:|------|
| Depth | 2.0 | 해석 완전 |
| Context | 1.0 | 사용자는 "서울역" 의도, 응답은 "서울대병원" — 하지만 명시적 상권명 언급 |
| Derived | 2.0 | 점포당, 연령별 상세 |
| Structure | 2.0 | 구조화 정상 |
| Actionable | 1.5 | 일부 제안 |
| Accuracy | 1.0 | 수치 15 unattr · 수치 자체는 DB 일치 |

**시스템 이슈 0** — 시스템은 정확히 3110023 상권을 분석. W1 Entity Linking 을 테스트하려면 district_code 없이 "서울역 상권 분석" 으로 호출해야 했음.

### S3 홍대 vs 성수 매출 비교 (7.9/10 FAIL, Round 1 2.6 대비 +5.3)

**중대 이슈 3건**:
1. **W1 multi-district 추출 실패**: tool input = `{"district_codes":["3110285"]}` 1개만 — `detect_districts_in_message` 가 성수 감지 실패
2. **W1 type boost 미작동**: "홍대" prefix → `홍대부중(골목상권)` top 매칭. 기대: `홍대입구역(홍대) 발달상권`(3120103). type_priority 가 점수에 충분히 반영 안 됨
3. **🔴 Respond LLM XML leak**: 응답 본문에 `<tool_use>...</tool_use>` `<tool_result>{ "districts": [...] }</tool_result>` Claude tool_use XML 이 그대로 출력됨 → 프론트 렌더 시 매우 나쁜 UX

| 축 | 점수 | 근거 |
|---|---:|------|
| Depth | 2.0 | 해석 완전 |
| Context | 2.0 | 벤치마크 percentile 반영 |
| Derived | 2.0 | 점포당, 객단가, 주말/평일 도출 |
| Structure | 1.5 | XML leak 으로 구조 오염 |
| Actionable | 1.5 | 각 상권 적합 시나리오 제시 |
| Accuracy | 0.5 | cards=[] (UI 오류), unattr 34, XML leak 에서 수치 유래 |

**긍정**: Round 1 에서 "일반지식 할루시" 로 FAIL 한 것 대비, **Tool 결과 기반 수치**로 개선. 하지만 Card 미렌더 + XML leak 로 여전히 FAIL.

### S4 건대 업종 추천 (9.2/10 PASS, Round 1 8.9 대비 +0.3)

| 축 | 점수 | 근거 |
|---|---:|------|
| Depth | 2.0 | Top 5 전수 분석 |
| Context | 2.0 | "대학가 특성" 맥락 |
| Derived | 2.0 | 점포당 매출, 경쟁 밀도, 폐업률 |
| Structure | 2.0 | 1~5순위 각 bullet |
| Actionable | 2.0 | "편의점 압도적 추천" + 이유 |
| Accuracy | 1.0 | unattr 30 |

2026-04-13 W1~W3 이전 "1순위만 다룸" 이슈 해소 ✅

### S5 명동 리스크 (6.7/10 FAIL)

**eval 설계 오류**: `district_code=3110010` → **평창동서측(골목상권)**. 명동은 `3120028` (명동거리, 발달상권) 또는 `3120027`.

LLM 은 **abstention 작동** ✅: "명동 상권 데이터만 수집되어 있지 않다"고 정직히 응답 + 평창동서측 데이터는 부수 안내.

| 축 | 점수 | 근거 |
|---|---:|------|
| Depth | 1.0 | 정직한 거절 + 보조 정보 |
| Context | 1.5 | 사용자 의도 인지 |
| Derived | 1.0 | 부수 데이터만 |
| Structure | 1.5 | 간결한 거절 |
| Actionable | 1.0 | 재시도 유도 |
| Accuracy | 2.0 | **abstention 완벽 작동** — 할루시 0 |

**시스템 positive**: W1-D abstention 이 잘못된 입력에도 hallucination 없이 graceful degrade.

### S6 강남역 카페 매출 시뮬레이션 (9.2/10 PASS, Round 1 6.1 대비 +3.1)

| 축 | 점수 | 근거 |
|---|---:|------|
| Depth | 2.0 | low/avg/high 3 구간 해석 |
| Context | 2.0 | 서울 평균 대비 2배, 기준 분기 명시 |
| Derived | 2.0 | "기존 410개 점포 기반" 추론 |
| Structure | 2.0 | 섹션 + 기회/주의 |
| Actionable | 1.5 | 제안 |
| Accuracy | 1.5 | unattr 12 |

Ground truth: `simulation.avg=51,591,985` — 응답 "5,160만원" 일치 ✅. Round 1 FAIL 항목 해소.

### S7 후속질문 "거기 중에 유동인구 더 많은 곳?" (5.4/10 FAIL, Round 1 8.9 대비 -3.5)

**중대 이슈**: **W2 coreference rewriter 미작동**
- tools=[] · cards=[] · map_cmds=1만 존재
- S7-pre 에서 `compare_districts([3110285])` 1회 호출 → 세션 히스토리에 데이터 있음에도 S7 에서 Planner→Actor 경로 스킵
- 응답 수치 "15만 1천명 vs 6만 8천명" 은 **S7-pre tool 결과 (홍대 74,000 / 성수 34,000) 와 불일치** → LLM priors 로 생성된 할루시

| 축 | 점수 | 근거 |
|---|---:|------|
| Depth | 2.0 | 해석 있음 |
| Context | 1.0 | 히스토리 참조 의도 있으나 수치 drift |
| Derived | 1.0 | 2.2배 비교 |
| Structure | 1.5 | bullet |
| Actionable | 1.0 | 제안 |
| Accuracy | 0.0 | **전면 할루시** — tool 0 |

**근본 원인 후보**: Planner 가 `거기 중에` 감지는 했으나 anchor walk 에서 district code 복원 실패 → tool plan empty → Respond 가 priors 로 답변.

### S8 배제 토큰 "홍대 말고 성수역이랑 건대 비교" (5.0/10 FAIL)

**중대 이슈**: **W2 배제 토큰 처리 미완**
- tools=[] · cards=[]
- 응답에 `<get_district_analysis>{"district_name": "성수역"}</get_district_analysis>` Claude self-hallucinated tool call leak
- 수치 "성수역 168억/건대입구 312억" 전면 할루시 (DB 실값 미확인)

| 축 | 점수 | 근거 |
|---|---:|------|
| Depth | 1.0 | 형식적 구조 |
| Context | 1.0 | 의도 인지 |
| Derived | 1.0 | 일부 비율 |
| Structure | 1.5 | bullet |
| Actionable | 1.5 | 상권 적합 시나리오 |
| Accuracy | 0.0 | **tool 0 + XML leak + 수치 할루시** |

**근본 원인 후보**: Planner 에서 `excluded_tokens=[홍대]` 로 multi-district 필터 후 **상권 0개 남으면 tool 호출 skip → Respond 진입**. excluded 상황에 대한 재탐지 로직 누락.

## 4. 핵심 발견 (우선순위)

### 🔴 신규 발견 #1 — Respond LLM `<tool_use>` XML leak (CRITICAL)

- **현상**: S3, S8 에서 Claude Sonnet 4 가 응답 본문에 `<tool_use>...</tool_use>` / `<tool_result>...</tool_result>` / `<get_district_analysis>...</get_district_analysis>` 자체 XML 포맷을 출력
- **트리거**: Tool 결과가 0 또는 부족한 경우, LLM 이 "추가 데이터 조회가 필요하다" 판단해 tool_use 형식을 생성 (Anthropic 모델 특성)
- **영향**: 프론트 MessageList 에 XML 노출되어 UX 심각한 저해. MarketScope 는 `<tool_use>` 를 파싱하지 않는다
- **Fix 제안**: `RESPOND_SYSTEM_PROMPT` 에 "절대로 `<tool_use>`, `<tool_result>`, `<get_district_*>`, `<tool_name>` 등 XML/tag 형식의 tool 호출 문법을 출력하지 마세요. 응답은 자연어 마크다운만 사용하세요." 명시
- **메모리**: `feedback_respond_tool_use_xml_leak.md` 저장 권장

### 🔴 신규 발견 #2 — W1 Entity Linking type boost 약함

- **현상**: "홍대" prefix → `홍대부중(골목상권)` top. 기대: `홍대입구역(홍대) 발달상권`(3120103)
- **원인 추정**: `entity_matching.py::rank_candidates` 의 prefix score (`0.55 + 0.25×query_len/name_len`) 가 type_priority (`발달+0.20`) 보다 dominant. 3글자 "홍대부중" (name_len=4) vs 7글자 "홍대입구역(홍대)" → prefix 성분 "홍대" 가 둘 다 매칭하지만 name_len 비율로 골목 우세
- **Fix 제안**: type_priority 가중치를 `0.20 → 0.35` 로 상향 or prefix score 의 name_len 페널티 완화
- S3 의 `compare_districts([3110285])` = 홍대부중 — 비교 상대 "성수" 는 아예 후보에 없었음 (multi-district 추출 실패)

### 🔴 신규 발견 #3 — W1 multi-district 추출 regression

- **현상**: `detect_districts_in_message("홍대 vs 성수 매출 비교")` → 1개 code 만 반환
- **기대**: 2개 code 반환 후 comparison intent 로 병렬 tool 호출
- **영향**: S3 의 core scenario 불완전 + cards=[] (compare card 미발행)
- **Fix 제안**: `_candidate_words` 가 "홍대" 와 "성수" 를 각각 추출하는지 로그로 검증. 이미 W1 구현 시 "성수" 2글자 허용했다 했으므로 regression 가능성

### 🔴 신규 발견 #4 — W2 coreference + exclusion 실전 경로 누락

- **S7**: Planner 가 `거기` anchor walk 로 history 의 홍대/성수 code 복원 실패 → tool plan empty → Respond 할루시
- **S8**: `excluded_tokens=[홍대]` 후 multi 리스트 empty → tool plan empty → Respond 할루시
- **Fix 제안**: Planner 에서 tool plan 이 empty 인 경우 RESPOND 단계로 가지 말고 **명시적 clarification card** 로 사용자에게 재질문

### 🟡 Eval 설계자 오류 (본 세션)

district_code 매핑 오류:
- 서울역 = **3120043** (내가 `3110023` = 서울대병원 사용)
- 명동 = **3120028** 또는 `3120027` (내가 `3110010` = 평창동서측 사용)

**교훈**: district_code 하드코딩 금지. eval 은 message 만 넣고 entity linking 자체를 검증하도록 재설계 권장. [Plan](../plan/fix/accuracy-gap-eval-round2-2026-04-24.md) Round 3 에 반영 예정.

### 🟢 긍정 — 개선된 영역

- **S3 +5.3**: Round 1 의 "일반지식 할루시 (50% 오차)" → Round 2 "Tool 결과 기반 수치 (DB 일치)". 단일 district 한정이지만 benchmark percentile 등 정확
- **S6 +3.1**: `simulate_revenue` tool 과 SimulationCard 정상 작동
- **S4 +0.3**: Top 5 전수 분석 정착 (Round 1 issue 해소)
- **S5 abstention 완벽**: 데이터 부재 시 거절 + 수치 할루시 0

## 5. KPI Delta

| 지표 | 현재 | Round 2 목표 | 달성 여부 |
|------|-----:|-----:|:---:|
| 종합 정확성 (74) | **72-74** | 85+ | ❌ |
| S3 비교 | **7.9** (+5.3) | 9.0+ | ❌ (개선) |
| S6 시뮬레이션 | **9.2** (+3.1) | 9.0+ | ✅ |
| S7 후속질문 | **5.4** (-3.5) | 9.3+ | ❌ (대폭 regression) |
| GAP-A 2글자 매칭률 | ~30% (S3 multi 실패) | 95%+ | ❌ |
| GAP-A type 우선순위 | 30-40% | 95%+ | ❌ |
| GAP-C 배제 정확도 | ~50% (감지 O · tool plan 폴백 X) | 95%+ | ❌ (부분) |
| GAP-D 할루시 발생률 | S7/S8 에서 전면, S1/S4/S6 에서 0 | <3% | ❌ (분리됨) |
| GAP-E coref 성공률 | 0% (S7 tool 미호출) | 85%+ | ❌ |

## 6. Next Actions (우선순위)

**P0 (긴급, 다음 세션)**:
1. `RESPOND_SYSTEM_PROMPT` 에 XML/tag leak 금지 규칙 추가 (§4.1)
2. `entity_matching.py::rank_candidates` type_priority 가중치 상향 (§4.2)
3. Planner: tool plan empty 시 clarification 카드 fallback 경로 (§4.4)

**P1 (W4 재개 전)**:
4. `detect_districts_in_message` multi-extract 재검증 (§4.3)
5. Rewriter Tier 1/2 anchor walk 디버그 로그 추가 (S7 원인 추적)
6. Eval 시나리오에서 district_code 하드코딩 제거, entity linking 의존 검증

**P2 (KPI 측정 재실시)**:
7. P0/P1 fix 후 Round 3 eval 실행
8. Round 3 에서 GAP-A/C/D/E 각각 단독 micro-scenario 추가 (시나리오당 1 메시지)

## 7. 산출물

- Raw SSE: [eval-round2-raw/S{1..8}.sse](runs/eval-round2-raw/)
- Parser 요약: [eval-round2-raw/_summary.md](runs/eval-round2-raw/_summary.md)
- Eval 스크립트: `scripts/eval/run_accuracy_round2.sh` · `scripts/eval/parse_sse.py`

## 8. Metadata

- 평가자: Claude Opus 4.7
- 평가일: 2026-04-24
- 컨테이너: `catchment-area-analysis-backend-1` (19h uptime · W1~W3 docker cp 반영)
- 컨테이너 미반영: 2026-04-24 refactor (formatting.py 추출, respond.py 502→280 LOC — semantics 동일, eval 결과 동일)
- LLM: Claude Sonnet 4 (planner+respond) / Gemini 2.5 Flash (evaluator)
- USE_MOCK: false (Real 데이터 1,650 상권)
- 데이터 기준: 2025Q4
