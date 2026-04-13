# 분석 리포트 품질 개선 계획

## Context

현재 MarketScope AI의 분석 품질은 **3.2/5** — 데이터는 풍부하지만 해석이 얕습니다.
오픈업 같은 서비스는 대시보드로 "raw data"만 보여주는 반면, MarketScope의 차별점은 **AI가 데이터를 해석**하는 것인데, 현재 Respond 프롬프트에 해석 가이드가 없고 Tool이 raw 값만 반환합니다.

**목표**: 3.2/5 → 4.5/5 (데이터 → 인사이트 전환)

**핵심 문제**:
1. Respond 프롬프트에 "데이터 해석하세요"만 있고 HOW가 없음
2. Tool이 raw DB 값만 반환 — 파생 지표(점포당 매출, 주말 비중 등) 미계산
3. 벤치마킹 전무 — "유동인구 12만"이 높은 건지 낮은 건지 맥락 없음
4. DB에 있는 데이터 20%가 미활용 (성별, 거래건수, 프랜차이즈 수 등)

---

## Phase 1: Respond 프롬프트 업그레이드 (백엔드 변경 없음, 최고 ROI)

### 1.1 RESPOND_SYSTEM_PROMPT 분석 프레임워크 추가
**파일**: `server/server/agent/nodes/respond.py` (lines 21-40)

현재 10개 규칙에 아래를 추가:
- [ ] **수치 해석 원칙**: "무엇(what) + 의미(so what) + 맥락(context)" 3단 해석
- [ ] **인사이트 도출 규칙 4가지**:
  - "왜(Why)" 설명 (폐업률이 높은 이유까지)
  - 비교 맥락 (서울 평균, 같은 유형 상권 대비)
  - 위험 신호 명확화 (폐업률 >8%, 매출 하락 >5% 등 임계값)
  - 기회도 함께 제시 (단점만 나열하지 말 것)
- [ ] **응답 구조 템플릿**: 핵심 한줄 → 지표 해석 → 시사점 → 후속 유도
- [ ] **좋은 분석 예시** 1개 (few-shot)
- [ ] **파생 지표 직접 계산 지시**: 점포당 매출, 주말 비중, 건당 결제액 등

### 1.2 Tool 결과 truncation 한도 상향
**파일**: `server/server/agent/nodes/respond.py` line 62

- [ ] `[:2000]` → `[:4000]` (비교 분석 시 3개 상권 데이터가 잘리는 문제 해결)

### 1.3 파생 지표 힌트 자동 생성 (`_compute_hints`)
**파일**: `server/server/agent/nodes/respond.py`

`_format_tool_results()` 내에서 tool result JSON 아래에 파생 지표를 자동 계산하여 LLM에 제공:
- [ ] floating_pop → 주요 성별, 주요 연령층, 피크 유형(출근/점심/퇴근/야간), 주간/야간 비율
- [ ] estimated_sales → 건당 평균 결제액, 주말 매출 비중%, QoQ 성장률, 피크 시간대
- [ ] store_info → 프랜차이즈 비율, 순유입(개업-폐업), 상위 업종 집중도
- [ ] comparison → 지표별 우위 상권, 점포당 매출 효율 순위

### 검증
- "강남역 분석해줘" → 응답에 비교 맥락, 계산된 비율, 구조화된 섹션 포함 확인
- "홍대랑 비교해줘" → 텍스트에 winner 분석 포함 확인

---

## Phase 2: Tool 데이터 보강 (기존 데이터로 파생 지표 계산)

### 2.1 district_summary 보강
**파일**: `server/server/agent/tools/district_summary.py`

반환 dict에 `insights` 블록 추가 (기존 필드 유지):
- [ ] `genderInsight`: 성별 비중 (남/녀 5%p 이상 차이 시)
- [ ] `ageInsight`: 주요 연령층 + 비중%
- [ ] `perStoreSales`: 점포당 월 매출 (total_sales ÷ store_count)
- [ ] `franchiseRatio`: 프랜차이즈 비율% (franchise_count ÷ total_stores)
- [ ] `weekendUplift`: 주말 매출 증감률% (weekend_sales vs weekday_sales)
- [ ] `qoqGrowth`: 전분기 대비 매출 성장률%

### 2.2 estimated_sales 보강
**파일**: `server/server/agent/tools/estimated_sales.py`

`_enrich_sales(result)` 후처리 함수 추가:
- [ ] `avg_transaction`: 건당 평균 결제액 (sales ÷ sales_count)
- [ ] `weekend_uplift_pct`: 주말 매출 증감%
- [ ] `weekend_share_pct`: 주말 매출 비중%
- [ ] `qoq_growth_pct`: 전분기 대비 성장률
- [ ] `annual_growth_pct`: 연간 성장률 (4분기 기준)
- [ ] `peak_daypart`: 매출 최고 시간대 + 비중%
- [ ] `dominant_age`: 매출 최다 연령층 + 비중%

### 2.3 compare_districts 보강
**파일**: `server/server/agent/tools/comparison.py` (또는 관련 mock/real)

- [ ] 각 상권에 `sales_per_store`, `pop_per_store` 효율 지표 추가
- [ ] `winners` 블록: 지표별 1위 상권 (highest_pop, highest_sales, lowest_close_rate, best_efficiency)

### 2.4 recommend_business 보강
**파일**: `server/server/agent/tools/recommendation.py` (또는 관련 mock/real)

- [ ] `saturation`: 시장 포화도 (점포 수 기반: 여유/포화/과포화)
- [ ] `risk_flag`: 폐업률 8% 초과 시 경고
- [ ] `cost_category`: 창업비용 등급 (소자본/중간/대자본)

### 2.5 Mock JSON 파일 업데이트
**파일**: `server/server/agent/tools/mock/*.json` (7개)

- [ ] 각 JSON에 `computed` / `insights` 필드 추가하여 Mock↔Real 형태 일치

### 검증
- Mock/Real 양쪽에서 각 tool의 enriched 결과 확인
- 기존 Card 컴포넌트가 새 필드 무시하고 정상 렌더링 확인 (하위 호환)
- JSON 직렬화 4000자 이내 확인

---

## Phase 3: 벤치마킹 레이어 (상권 유형별 순위)

### 3.1 벤치마크 데이터 모듈
**신규 파일**: `server/server/agent/tools/benchmarks.py`

- [ ] Mock 모드: 상권 유형별(발달상권/골목상권/전통시장) 하드코딩 통계 (p25/p50/p75/mean)
  - 유동인구, 월매출, 폐업률, 점포수, 점포당 매출
- [ ] Real 모드: DB `percentile_cont()` 쿼리 + 24h 캐시
- [ ] `get_percentile_rank(value, benchmarks)` → "상위 25%" 등 텍스트 반환

### 3.2 district_summary에 벤치마크 주입
**파일**: `server/server/agent/tools/district_summary.py`

- [ ] `benchmarks` 블록 추가:
  ```
  benchmarks: {
    districtType: "발달상권",
    rankings: { floatingPop: "상위 25%", monthlySales: "상위 50%", ... },
    seoulAvg: { floating_pop: 92000, monthly_sales: 6000000000, close_rate: 6.5 }
  }
  ```

### 3.3 Respond 프롬프트에 벤치마크 활용 지시 추가
**파일**: `server/server/agent/nodes/respond.py`

- [ ] "benchmarks 데이터가 있으면 반드시 순위/백분위를 언급" 규칙 추가

### 3.4 Real 모드 벤치마크 Repository
**파일**: `server/server/repositories/protocols.py` + `real/benchmarks.py` + `mock/benchmarks.py`

- [ ] `BenchmarkRepository` protocol 정의
- [ ] Real: `percentile_cont()` SQL 집계 (district_type별)
- [ ] Mock: 하드코딩 통계
- [ ] DataAccess 파사드에 등록

### 검증
- "강남역 분석해줘" → "발달상권 중 상위 X%" 표현 포함 확인
- "홍대랑 비교해줘" → 각 상권의 순위 비교 포함 확인
- Real 모드에서 벤치마크 쿼리 <100ms 확인

---

## 핵심 수정 파일 요약

| 파일 | Phase | 변경 |
|------|-------|------|
| `server/server/agent/nodes/respond.py` | 1 | 프롬프트 확장 + truncation + _compute_hints |
| `server/server/agent/tools/district_summary.py` | 2,3 | insights + benchmarks 블록 |
| `server/server/agent/tools/estimated_sales.py` | 2 | _enrich_sales 후처리 |
| `server/server/agent/tools/comparison.py` | 2 | winner + efficiency 지표 |
| `server/server/agent/tools/recommendation.py` | 2 | saturation + risk_flag |
| `server/server/agent/tools/mock/*.json` | 2 | Mock 데이터 형태 동기화 |
| `server/server/agent/tools/benchmarks.py` | 3 | **신규** — 벤치마크 모듈 |
| `server/server/repositories/protocols.py` | 3 | BenchmarkRepository 추가 |
| `server/server/repositories/mock/benchmarks.py` | 3 | **신규** — Mock 벤치마크 |
| `server/server/repositories/real/benchmarks.py` | 3 | **신규** — Real 벤치마크 쿼리 |

## 예상 품질 변화

| Phase | 변경 | 예상 품질 |
|-------|------|-----------|
| 현재 | — | 3.2/5 |
| Phase 1 완료 | 프롬프트만 개선 | 3.8/5 |
| Phase 2 완료 | Tool 데이터 보강 | 4.2/5 |
| Phase 3 완료 | 벤치마킹 추가 | 4.5/5 |

---

## Phase 4: E2E 분석 품질 테스트 (10점 척도, 9점 이상 합격)

### 평가 원칙

- **척도**: 0~10점 (9점 이상 = 합격)
- **객관성**: 별도 세션의 fresh agent가 평가 (구현자 편향 제거)
- **평가 기준 6개 축**:

| 축 | 설명 | 배점 |
|----|------|------|
| **해석 깊이** (Depth) | raw 수치 나열이 아니라 "왜/어떻게"가 있는가 | 2점 |
| **비교 맥락** (Context) | 서울 평균, 상권 유형 내 순위 등 맥락이 있는가 | 2점 |
| **파생 지표** (Derived) | 점포당 매출, 주말 비중 등 계산된 지표가 있는가 | 2점 |
| **구조/가독성** (Structure) | 핵심 요약 → 상세 → 시사점 순서로 구조화됐는가 | 1.5점 |
| **실행 가능성** (Actionable) | 창업자가 의사결정에 활용할 수 있는 구체적 인사이트가 있는가 | 1.5점 |
| **정확성** (Accuracy) | 수치가 Tool 데이터와 일치하고, 허구/환각이 없는가 | 1점 |

### 테스트 시나리오 (8개)

#### S1. 기본 요약 — 강남역
```
입력: "강남역 상권 분석해줘"
district_code: D3001 (Mock) / 3110031 (Real)
```
**합격 기준**:
- [ ] 유동인구 수치 + "서울 상위 X%" 또는 유사 맥락
- [ ] 피크 시간대 + 왜 그런지 해석 (퇴근형/점심형 등)
- [ ] 점포당 매출 또는 매출 효율 파생 지표 1개+
- [ ] 핵심 한줄 요약으로 시작
- [ ] 위험 요소 또는 강점 1개+ 명시

#### S2. 기본 요약 — 골목상권 (건대입구)
```
입력: "건대입구 상권 분석해줘"
district_code: D3003 (Mock)
```
**합격 기준**:
- [ ] 발달상권과 다른 톤 (골목상권 특성 반영)
- [ ] 소규모 상권에 적합한 인사이트 (소자본 기회 등)
- [ ] 상권 유형별 맥락 차이 표현

#### S3. 상권 비교
```
입력: "강남역이랑 홍대 비교해줘"
```
**합격 기준**:
- [ ] 지표별 우위 분석 (유동인구는 A가 높고, 폐업률은 B가 낮고)
- [ ] 효율 지표 비교 (점포당 매출, 유동인구 대비 점포 밀도)
- [ ] "어떤 상권이 더 적합한가"에 대한 판단/시사점
- [ ] 단순 숫자 나열이 아닌 해석

#### S4. 업종 추천
```
입력: "강남역에서 뭐하면 좋을까?"
district_code: D3001
```
**합격 기준**:
- [ ] 추천 근거에 데이터 기반 설명 (매출, 경쟁, 고객층)
- [ ] 포화도/리스크 경고 포함 (해당 시)
- [ ] 1순위 추천의 장단점 균형 있게 설명
- [ ] "이 업종은 이런 이유로 유망" 형태의 actionable 인사이트

#### S5. 리스크 분석
```
입력: "명동 이 자리 위험하지 않아?"
district_code: D3004
```
**합격 기준**:
- [ ] 안정성 등급 + 구체적 근거
- [ ] 위험 업종 명시 + 왜 위험한지
- [ ] 생존 기간 데이터 활용
- [ ] 단순 "위험합니다/안전합니다"가 아닌 조건부 판단

#### S6. 매출 시뮬레이션
```
입력: "강남역에서 카페 하면 매출 얼마나?"
district_code: D3001
```
**합격 기준**:
- [ ] 예상 매출 범위 (하한~상한)
- [ ] 산출 근거 (점포당 매출, 경쟁 점포 수 등)
- [ ] 서울 평균 대비 위치
- [ ] 면책 안내 포함

#### S7. 후속 질문 (멀티턴)
```
턴1: "강남역 분석해줘"
턴2: "거기서 카페는 어때?"
```
**합격 기준**:
- [ ] 턴2에서 "강남역" 컨텍스트 유지
- [ ] 턴1 분석 내용을 반복하지 않고 심화
- [ ] 업종 특화 인사이트 (카페 경쟁, 커피 매출 비중 등)

#### S8. 엣지 케이스 — 상권 미선택
```
입력: "상권 분석해줘" (district_code 없음)
```
**합격 기준**:
- [ ] 상권 선택 안내 (에러 아닌 가이드)
- [ ] 추천 상권 또는 사용법 안내
- [ ] 친절한 톤 유지

### 평가 프로세스

```
Phase 1~3 구현 완료
    │
    ▼
각 시나리오(S1~S8)별로:
    │
    ├─ 1. Backend에 실제 요청 (curl POST /api/chat)
    ├─ 2. SSE 응답 텍스트 전체 수집
    ├─ 3. Tool 결과 JSON + 최종 텍스트를 evaluation packet으로 묶기
    │
    ▼
Fresh Agent 세션 (별도 general-purpose subagent)에 전달:
    │
    ├─ "당신은 상권분석 보고서 품질 평가자입니다"
    ├─ evaluation packet (tool data + LLM 응답 텍스트)
    ├─ 평가 기준 6축 + 배점표
    ├─ 합격 기준 체크리스트
    │
    ▼
시나리오별 결과:
    {
      "scenario": "S1",
      "scores": { "depth": 1.8, "context": 1.5, "derived": 2.0, ... },
      "total": 8.8,
      "pass": false,
      "feedback": "비교 맥락에서 상권 유형 내 순위 누락"
    }
    │
    ▼
9점 미만 시나리오 → 피드백 기반 프롬프트/Tool 수정 → 재평가
```

### 합격 조건

| 조건 | 기준 |
|------|------|
| **개별 시나리오** | 8개 모두 **9.0/10 이상** |
| **평균** | 전체 평균 **9.0/10 이상** |
| **정확성** | 모든 시나리오에서 정확성 축 **0.8/1.0 이상** (환각 0) |
| **최저점** | 어떤 축도 배점의 50% 미만이면 불합격 |

### 재시도 정책

- 9점 미만 시나리오의 `feedback`에서 부족한 축 확인
- 해당 축에 대응하는 Phase(1/2/3) 코드 수정
- **최대 3회 반복** (구현 → 평가 → 수정)
- 3회 후에도 미달 시 평가 기준 또는 구현 범위 재조정

### 결과 저장

- [ ] `docs/qa/analysis-quality-eval-{date}.md` — 시나리오별 점수 + 피드백
- [ ] `docs/qa/analysis-quality-criteria.md` — 평가 기준 문서 (재사용)

---

## 실행 순서 종합

```
Phase 1 (프롬프트)  →  Phase 2 (Tool 보강)  →  Phase 3 (벤치마킹)
                                                        │
                                                        ▼
                                              Phase 4: E2E 품질 평가
                                              S1~S8 × Fresh Agent
                                                        │
                                              ┌─────────┴─────────┐
                                              │                   │
                                          9점 이상              9점 미만
                                          → PASS               → 피드백 기반 수정
                                                               → 재평가 (최대 3회)
```
