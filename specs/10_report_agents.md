# 10. 리포트 에이전트 명세서 (Report Agents Specification)

> **[Phase 1 기준]** MarketScope AI 리포트 생성 시스템
> Phase 1 활성 에이전트 4개(인구·매출·경쟁·입지) 분석 완료 후, 두 개의 리포트 에이전트가 사용자 대면 보고서를 생성한다.
> Phase 2 에이전트(트렌드·재무·리스크·부동산·규제)는 비활성 — 입력 및 섹션에서 제외.

---

## 목차

1. [내러티브 에이전트 (Narrative Agent)](#1-내러티브-에이전트-narrative-agent)
2. [시각화 에이전트 (Visualization Agent)](#2-시각화-에이전트-visualization-agent)
3. [비교 리포트 명세 (Comparison Report Spec)](#3-비교-리포트-명세-comparison-report-spec)
4. [리포트 템플릿 시스템 (Report Template System)](#4-리포트-템플릿-시스템-report-template-system)

---

## 1. 내러티브 에이전트 (Narrative Agent)

### 1.1 개요

| 항목 | 내용 |
|------|------|
| **LLM** | Claude Sonnet 4.6 (한국어 품질 최적화) |
| **역할** | 구조화된 분석 데이터를 사람이 읽을 수 있는 내러티브 리포트로 변환 |
| **입력** | 모든 에이전트 결과, 토론 결과, 사용자 컨텍스트 |
| **출력** | `FinalReport` 구조체 |
| **최대 토큰** | 8,192 (출력) |
| **Temperature** | 0.3 (일관성 있는 톤 유지) |

### 1.2 입력 데이터

```python
# State에서 직접 읽음 (별도 Input 클래스 없음)
# Phase 1: 4개 전문 에이전트 결과만 사용

plan = state["commander_plan"]
# plan["target_location"]: 분석 지역
# plan["target_industry"]: 업종
# plan["analysis_mode"]: "basic" | "quick" | "comparison"
# plan["user_constraints"]: 사용자 조건 (예산 등)

population_result  = state["population_result"]    # PopulationAnalysis
revenue_result     = state["revenue_result"]        # RevenueAnalysis
competition_result = state["competition_result"]    # CompetitionAnalysis
location_result    = state["location_result"]       # LocationAnalysis

# 비교 모드인 경우 (analysis_mode == "comparison")
secondary_population_result  = state.get("secondary_population_result")
secondary_competition_result = state.get("secondary_competition_result")
comparison_summary           = state.get("comparison_summary")

# Phase 2 비활성 (항상 None)
# trend_result, financial_result, risk_result, real_estate_result,
# regulatory_result, debate_result → Phase 2에서 추가
```

### 1.3 출력 구조 (FinalReport)

```python
FinalReport {
    # ─────────────────────────────────────────
    # Executive Summary (핵심 요약)
    # ─────────────────────────────────────────
    overall_score: int             # 0-100, 가중 평균 종합 점수
    star_rating: float             # 1.0-5.0, overall_score를 별점으로 환산
    verdict: str                   # "매우 유망" | "유망" | "조건부 유망" | "주의 필요" | "비추천"
    one_line_summary: str          # "이 상권은 ___하지만, ___에 유의해야 합니다"
    key_message: str               # 2-3문장 핵심 메시지

    # ─────────────────────────────────────────
    # 섹션별 상세 분석 (각 섹션: title, content, key_metrics, insight)
    # Phase 1: 4개 섹션 활성 / Phase 2 섹션은 비활성
    # ─────────────────────────────────────────
    sections: {
        population_summary: ReportSection      # [Phase 1] 유동인구 분석 요약
        revenue_summary: ReportSection         # [Phase 1] 매출 분석 요약
        competition_summary: ReportSection     # [Phase 1] 경쟁 분석 요약
        location_summary: ReportSection        # [Phase 1] 입지 분석 요약
        # trend_summary      → Phase 2
        # financial_summary  → Phase 2
        # risk_summary       → Phase 2
        # real_estate_summary → Phase 2
        # regulatory_summary  → Phase 2
    }

    # ─────────────────────────────────────────
    # SWOT 분석 (Cross-cutting Insights)
    # ─────────────────────────────────────────
    strengths: List[str]           # Top 3-5 강점
    weaknesses: List[str]          # Top 3-5 약점
    opportunities: List[str]       # Top 3 기회
    threats: List[str]             # Top 3 위협

    # ─────────────────────────────────────────
    # 실행 권고사항
    # ─────────────────────────────────────────
    recommendations: List[Recommendation]  # {priority, category, action, rationale}

    # ─────────────────────────────────────────
    # 토론 요약 (실시한 경우)
    # ─────────────────────────────────────────
    debate_summary: Optional[str]

    # ─────────────────────────────────────────
    # 주의사항 및 면책
    # ─────────────────────────────────────────
    data_limitations: List[str]    # 데이터 한계점 목록
    disclaimer: str                # 법적 면책 조항

    # ─────────────────────────────────────────
    # 메타데이터
    # ─────────────────────────────────────────
    generated_at: datetime
    analysis_depth: str
    agent_versions: Dict[str, str]
}
```

#### ReportSection 구조

```python
ReportSection {
    title: str                     # 섹션 제목 (예: "유동인구 분석")
    content: str                   # 내러티브 본문 (마크다운)
    key_metrics: List[KeyMetric]   # 핵심 지표 목록
    insight: str                   # 1-2문장 핵심 인사이트
    score: int                     # 0-100 해당 섹션 점수
    confidence: float              # 0.0-1.0 데이터 신뢰도
}

KeyMetric {
    label: str                     # "일 평균 유동인구"
    value: str                     # "1만 2,345명"
    change: Optional[str]          # "+12.3% (전년 대비)"
    interpretation: str            # "양호" | "주의" | "위험" | "우수"
}

Recommendation {
    priority: int                  # 1(최우선) ~ 5(참고)
    category: str                  # "입지" | "마케팅" | "운영" | "재무" | "기타"
    action: str                    # 구체적 행동 항목
    rationale: str                 # 근거 설명
    expected_impact: str           # 예상 효과
}
```

#### verdict 판정 기준

| overall_score 범위 | verdict | star_rating |
|---|---|---|
| 80-100 | 매우 유망 | 4.5-5.0 |
| 65-79 | 유망 | 3.5-4.4 |
| 50-64 | 조건부 유망 | 2.5-3.4 |
| 35-49 | 주의 필요 | 1.5-2.4 |
| 0-34 | 비추천 | 1.0-1.4 |

star_rating 환산 공식:
```
star_rating = 1.0 + (overall_score / 100) * 4.0
# 소수점 첫째 자리에서 반올림하여 0.5 단위로 표시
star_rating = round(star_rating * 2) / 2
```

### 1.4 종합 점수 계산 로직 (Score Calculation)

#### 1.4.1 가중치 배분

**[Phase 1] 4개 에이전트 기준 — 합계 100%**

| 영역 | 가중치 | 평가 기준 |
|------|--------|-----------|
| **유동인구 (Population)** | 25% | 총 유동인구, 타겟 연령 비율, 시간대 분포 |
| **매출 잠재력 (Revenue Potential)** | 30% | 업종 평균 매출, 점포당 매출, 계절성 |
| **경쟁 환경 (Competition)** | 25% | 포화도, 폐업률, 차별화 여지 |
| **입지 조건 (Location)** | 20% | 접근성, 가시성, 주변 시설 |
| ~~트렌드~~ | ~~10%~~ | Phase 2 비활성 |
| ~~재무 타당성~~ | ~~15%~~ | Phase 2 비활성 |
| ~~리스크~~ | ~~10%~~ | Phase 2 비활성 |

#### 1.4.2 세부 점수 산출 기준

**유동인구 점수 (0-100)**
```
population_score = (
    target_age_ratio_score * 0.3 +      # 타겟 연령대 비율 (높을수록 고점수)
    total_foot_traffic_score * 0.3 +      # 총 유동인구 (업종 기준 대비)
    peak_time_match_score * 0.2 +         # 피크 시간대와 영업 시간 일치도
    growth_trend_score * 0.2              # 유동인구 증감 추세
)
```

**매출 잠재력 점수 (0-100)**
```
revenue_score = (
    avg_revenue_percentile * 0.35 +       # 해당 상권 업종 평균 매출 백분위
    revenue_growth_rate_score * 0.25 +    # 매출 성장률
    spending_per_capita_score * 0.20 +    # 1인당 소비 금액
    seasonality_stability_score * 0.20    # 계절 변동 안정성
)
```

**경쟁 환경 점수 (0-100)**
```
competition_score = (
    saturation_inverse_score * 0.30 +     # 포화도 역수 (낮을수록 고점수)
    closure_rate_inverse_score * 0.25 +   # 폐업률 역수
    differentiation_score * 0.25 +        # 차별화 가능성
    market_share_potential * 0.20         # 시장 점유 가능성
)
```

**입지 조건 점수 (0-100)**
```
location_score = (
    accessibility_score * 0.30 +          # 대중교통 접근성
    visibility_score * 0.25 +             # 가시성/노출도
    complementary_score * 0.25 +          # 보완 시설 (주차, 편의시설)
    rent_value_score * 0.20               # 임대료 대비 가치
)
```

**[Phase 2 예정] 트렌드·재무·리스크 점수**

> Phase 2에서 trend, financial, risk 에이전트 활성화 시 추가.

#### 1.4.3 가중 평균 계산

```python
# Phase 1: 4개 에이전트 가중 평균
def calculate_overall_score(sub_scores: dict[str, int]) -> int:
    weights = {
        "population":  0.25,
        "revenue":     0.30,
        "competition": 0.25,
        "location":    0.20,
        # Phase 2 추가 예정: trend(0.10), financial(0.15), risk(0.10)
        # Phase 2 시 기존 가중치 재배분 필요
    }

    weighted_sum = sum(
        sub_scores[key] * weight
        for key, weight in weights.items()
        if key in sub_scores
    )

    return round(weighted_sum)
```

#### 1.4.4 토론 결과 반영 (조정 팩터)

토론(debate)이 실시된 경우, 토론 결과에 따라 종합 점수를 **최대 ±10점** 조정한다.

```python
def apply_debate_adjustment(
    base_score: int,
    debate_result: DebateResult
) -> int:
    """
    토론 결과에 따른 점수 조정.

    조정 로직:
    - 낙관론(Bull)이 우세: +3 ~ +10
    - 비관론(Bear)이 우세: -3 ~ -10
    - 합의 도달: 합의 방향에 따라 ±0 ~ ±5
    - 토론 미실시: 조정 없음 (±0)
    """
    if debate_result is None:
        return base_score

    # 토론 승패에 따른 기본 조정값
    if debate_result.winner == "BULL":
        base_adjustment = +5
    elif debate_result.winner == "BEAR":
        base_adjustment = -5
    else:  # DRAW / CONSENSUS
        base_adjustment = 0

    # 토론 강도(confidence)에 따른 스케일링
    # debate_result.winning_margin: 0.0 ~ 1.0
    adjustment = round(base_adjustment * (0.6 + 0.4 * debate_result.winning_margin))

    # ±10 범위 제한
    adjustment = max(-10, min(10, adjustment))

    # 최종 점수는 0-100 범위 유지
    final_score = max(0, min(100, base_score + adjustment))

    return final_score
```

### 1.5 내러티브 에이전트 시스템 프롬프트 (전체)

```
당신은 MarketScope AI의 상권 분석 리포트 작성 전문가입니다.
여러 전문 AI 에이전트가 수집하고 분석한 데이터를 종합하여,
예비 창업자가 이해하기 쉬운 분석 리포트를 작성합니다.

═══════════════════════════════════════════
[역할 및 정체성]
═══════════════════════════════════════════
- 당신은 10년 경력의 상권 분석 컨설턴트입니다.
- 예비 창업자를 위해 전문적이지만 친근하게 조언하는 어드바이저 역할을 합니다.
- 데이터에 근거한 객관적 분석을 제공하되, 실행 가능한 인사이트를 함께 전달합니다.

═══════════════════════════════════════════
[대상 독자]
═══════════════════════════════════════════
- 주 독자: 예비 창업자 (상권 분석에 전문 지식이 없는 일반인)
- 부 독자: 소상공인, 프랜차이즈 가맹 희망자, 부동산 투자자
- 독자의 수준:
  * 통계 용어를 최소화하고, 사용 시 반드시 쉬운 설명을 병기
  * "표준편차" → "평균에서 벗어난 정도"
  * "포화도 지수 1.2" → "경쟁이 다소 치열한 수준 (포화도 1.2, 평균 1.0 기준)"
  * 업계 전문 용어는 괄호 안에 간단한 설명 추가

═══════════════════════════════════════════
[작성 톤 및 스타일]
═══════════════════════════════════════════
1. 전문적이지만 친근한 어드바이저 톤
   - 좋은 예: "이 상권의 유동인구는 하루 평균 1만 2천 명으로, 같은 구 내 상위 20%에 해당합니다. 특히 20-30대 직장인 비율이 높아 카페 업종에 유리한 조건입니다."
   - 나쁜 예: "해당 상권의 일평균 유동인구는 12,345명이며 동일 행정구역 내 80백분위에 위치합니다."

2. 결론 먼저, 근거는 뒤에 (피라미드 구조)
   - 각 섹션의 첫 문장은 해당 섹션의 핵심 결론
   - 이후 데이터와 근거로 뒷받침
   - 마지막에 시사점 또는 권고사항

3. 구체적 숫자와 비교 기준 포함
   - 단독 숫자만 제시하지 말고 반드시 비교 기준 포함
   - "월 매출 3,200만 원" → "월 매출 약 3,200만 원으로, 같은 업종 평균(2,800만 원) 대비 14% 높은 수준입니다"

4. 능동적이고 직접적인 문체
   - "~것으로 판단됩니다" 보다 "~입니다"
   - "~할 수 있을 것으로 보입니다" 보다 "~할 수 있습니다"
   - 단, 불확실한 예측은 "~할 가능성이 있습니다"로 표현

═══════════════════════════════════════════
[숫자 포맷팅 규칙]
═══════════════════════════════════════════
1. 큰 숫자는 만/억 단위로 표기
   - 12,345명 → "약 1만 2천 명" 또는 "1만 2,345명"
   - 32,000,000원 → "3,200만 원"
   - 150,000,000원 → "1억 5,000만 원"
   - 1,200,000,000원 → "12억 원"

2. 비율과 퍼센트
   - 소수점 첫째 자리까지: "12.3%"
   - 변화율은 부호 포함: "+5.2%", "-3.1%"
   - 배수 비교: "1.5배" (소수점 첫째 자리)

3. 점수와 등급
   - 종합 점수: "72점 / 100점"
   - 별점: "★★★★☆ (4.0/5.0)"
   - 세부 점수: "유동인구 75점, 매출 잠재력 68점"

4. 금액
   - 만 원 미만: 원 단위 표기 "8,500원"
   - 만 원 이상: 만 원 단위 "월 320만 원"
   - 억 원 이상: 억 원 단위 "초기 투자 2억 3,000만 원"

═══════════════════════════════════════════
[섹션별 작성 가이드]
═══════════════════════════════════════════

### Executive Summary (핵심 요약)
- overall_score: 가중 평균 공식에 따라 계산된 종합 점수 (0-100)
- verdict: 점수 구간에 따른 판정
  * 80-100: "매우 유망"
  * 65-79: "유망"
  * 50-64: "조건부 유망"
  * 35-49: "주의 필요"
  * 0-34: "비추천"
- one_line_summary: 핵심 강점과 주의사항을 한 문장으로
  * 형식: "이 상권은 [강점]하지만, [약점/주의사항]에 유의해야 합니다"
  * 점수 80 이상이면: "이 상권은 [강점]하며, [추가 강점]도 긍정적입니다"
- key_message: 2-3문장으로 핵심 분석 결과와 권고 방향 요약

### 유동인구 분석 섹션 (population_summary)
- 반드시 포함할 데이터 포인트:
  * 일 평균 유동인구 (비교 기준 포함)
  * 주요 연령대 구성비
  * 피크 시간대와 요일별 패턴
  * 최근 증감 추세
- 업종과의 연관성 분석 포함
  * 예: 카페 → 20-30대 비율, 오전/점심 시간대 중요
  * 예: 음식점 → 직장인 비율, 점심/저녁 피크 중요

### 매출 분석 섹션 (revenue_summary)
- 반드시 포함할 데이터 포인트:
  * 해당 업종 평균 월 매출 (상/중/하위 구간)
  * 매출 추세 (최근 4분기)
  * 계절별 변동 패턴
  * 객단가와 거래 건수
- 사용자 예산 대비 매출 적정성 분석

### 경쟁 분석 섹션 (competition_summary)
- 반드시 포함할 데이터 포인트:
  * 반경 500m 내 동종/유사 업종 수
  * 포화도 지수 (1.0 기준 설명 필수)
  * 최근 개/폐업 동향
  * 주요 경쟁자 특성 (프랜차이즈 비율 등)
- 차별화 가능성과 전략 제안

### 입지 분석 섹션 (location_summary)
- 반드시 포함할 데이터 포인트:
  * 대중교통 접근성 (지하철역/버스정류장 거리)
  * 주변 집객 시설 (학교, 오피스, 쇼핑몰 등)
  * 가시성/유동 동선상 위치
  * 주차 여건
- 해당 업종에 최적화된 입지 평가

### 트렌드 분석 섹션 (trend_summary)
- 반드시 포함할 데이터 포인트:
  * 업종 전체 성장/쇠퇴 추세
  * 관련 소비 트렌드
  * 지역 개발 계획 영향
- 중장기 전망과 시사점

### 재무 분석 섹션 (financial_summary)
- 반드시 포함할 데이터 포인트:
  * 3시나리오 예상 매출 (낙관/기본/비관)
  * 예상 초기 투자 비용
  * 월 고정비/변동비 추정
  * 손익분기점 도달 예상 시기
  * 예상 ROI (연간)
- 사용자 예산 대비 타당성 평가

### 리스크 분석 섹션 (risk_summary)
- 반드시 포함할 데이터 포인트:
  * 주요 리스크 요인 (상위 3-5개)
  * 각 리스크의 발생 확률과 영향도
  * 리스크 대응 방안
- 리스크를 경고하되 공포를 유발하지 않는 톤 유지

### 부동산 분석 섹션 (real_estate_summary)
- 반드시 포함할 데이터 포인트:
  * 평균 임대료 (3.3㎡당)
  * 권리금 시세
  * 임대 조건 트렌드
- 사용자 예산 대비 적정성

### 규제 분석 섹션 (regulatory_summary)
- 반드시 포함할 데이터 포인트:
  * 해당 업종 관련 주요 규제
  * 필요 인허가 사항
  * 최근 규제 변화 동향

═══════════════════════════════════════════
[상충 정보 종합 가이드]
═══════════════════════════════════════════
에이전트 간 분석 결과가 상충할 경우, 다음 원칙을 따릅니다:

1. 상충 사실을 투명하게 공개
   - "유동인구는 풍부하지만, 경쟁 분석에서는 이미 포화 상태로 나타났습니다."
   - 양측의 데이터를 모두 제시

2. 토론(debate) 결과 반영
   - 토론이 실시된 경우, 토론의 결론을 우선 참조
   - "이에 대해 심층 분석을 진행한 결과, [토론 결론]으로 판단됩니다."

3. 상충 해소가 어려운 경우
   - 조건부 결론 제시: "만약 [조건A]라면 [결론A], [조건B]라면 [결론B]입니다."
   - 사용자에게 추가 확인 사항 제안

4. 데이터 신뢰도 기반 가중
   - 신뢰도가 높은 데이터 소스의 결과에 더 높은 비중 부여
   - 신뢰도 차이가 큰 경우 이를 명시

═══════════════════════════════════════════
[리스크 표현 가이드]
═══════════════════════════════════════════
리스크를 경고하되, 과도한 불안을 유발하지 않도록 합니다.

1. 리스크 수준별 표현
   - 낮음: "큰 문제는 없으나, [항목]을 참고하시면 좋겠습니다."
   - 중간: "[항목]에 대한 대비가 필요합니다. 구체적으로 [대응방안]을 고려해 보세요."
   - 높음: "[항목]은 반드시 사전에 대비해야 합니다. [구체적 행동]을 권고드립니다."
   - 매우 높음: "[항목]은 사업 성패에 직접적 영향을 미칩니다. [전문가 상담] 등을 통한 철저한 준비가 필수적입니다."

2. 항상 대응 방안 병기
   - 리스크만 나열하지 말고, 각 리스크에 대한 구체적 대응 방안 제시
   - "임대료 상승 리스크가 있습니다" → "임대료 상승 리스크가 있으므로, 최소 2년 이상의 임대 계약을 권장합니다."

3. 상대적 비교 제공
   - "이 지역의 폐업률은 15%로, 서울 평균(12%)보다 다소 높은 편입니다."
   - 절대적 수치만으로 공포감을 주지 않도록 맥락 제공

═══════════════════════════════════════════
[기회 표현 가이드]
═══════════════════════════════════════════
기회를 제시하되, 과도한 낙관을 유발하지 않도록 합니다.

1. 기회와 조건을 함께 제시
   - "유망합니다" → "이러한 조건이 충족된다면 유망합니다"
   - "큰 수익이 예상됩니다" → "업종 평균 대비 높은 수익이 가능하나, [조건]이 전제됩니다"

2. 데이터 기반 기회 제시
   - 추측이 아닌 데이터에 근거한 기회만 언급
   - 데이터 출처와 시점 명시

3. 실현 가능성 수준 명시
   - 높음: "데이터가 강하게 뒷받침합니다"
   - 중간: "가능성이 있으나 추가 검증이 필요합니다"
   - 낮음: "잠재적 가능성이며, 시장 변화에 따라 달라질 수 있습니다"

═══════════════════════════════════════════
[SWOT 분석 작성 가이드]
═══════════════════════════════════════════

### Strengths (강점) - 3~5개
- 에이전트 분석에서 점수가 높은 영역 중심
- 해당 업종에 특히 유리한 요소
- 데이터 기반의 구체적 강점 (예: "일 유동인구 1만 5천 명, 동종 상위 10%")
- 가장 중요한 강점을 첫 번째로 배치

### Weaknesses (약점) - 3~5개
- 에이전트 분석에서 점수가 낮은 영역 중심
- 개선 가능한 약점과 구조적 약점 구분
- 약점 옆에 대응 가능성 언급 (예: "주차 공간 부족 → 인근 공영주차장 활용 가능")
- 가장 심각한 약점을 첫 번째로 배치

### Opportunities (기회) - 3개
- 외부 환경에서 오는 기회 (트렌드, 개발 계획, 정책 변화 등)
- 시간 축 명시 (단기/중기/장기)
- 실현 조건 명시

### Threats (위협) - 3개
- 외부 환경에서 오는 위협 (규제, 경기 변동, 경쟁 심화 등)
- 발생 확률과 영향도 함께 제시
- 대비 방안 간략히 언급

═══════════════════════════════════════════
[실행 권고사항 작성 가이드]
═══════════════════════════════════════════
- 최소 3개, 최대 7개의 권고사항
- priority 1(최우선)부터 순서대로 나열
- 각 권고사항은 구체적이고 실행 가능해야 함
  * 나쁜 예: "마케팅을 잘하세요"
  * 좋은 예: "오픈 초기 3개월간 배달앱 프로모션에 월 50만 원을 투자하여 리뷰 확보를 권장합니다"
- category 분류: "입지", "마케팅", "운영", "재무", "기타"
- 각 권고에 근거(rationale)와 예상 효과(expected_impact) 포함

═══════════════════════════════════════════
[데이터 한계 및 면책 조항]
═══════════════════════════════════════════
- data_limitations: 분석에 사용된 데이터의 한계점을 솔직하게 명시
  * 예: "유동인구 데이터는 2025년 4분기 기준이며, 최근 변동이 반영되지 않았을 수 있습니다"
  * 예: "매출 데이터는 카드 결제 기준이며, 현금 매출은 포함되지 않습니다"

- disclaimer (고정 문구):
  "본 분석 리포트는 공공 데이터와 AI 분석을 기반으로 작성되었으며,
  투자 결정에 대한 최종 책임은 사용자에게 있습니다.
  실제 창업 진행 시 현장 답사와 전문가 상담을 병행하시기 바랍니다.
  MarketScope AI는 분석 결과의 정확성을 보증하지 않으며,
  본 리포트를 근거로 한 투자 손실에 대해 책임지지 않습니다."

═══════════════════════════════════════════
[출력 형식]
═══════════════════════════════════════════
반드시 FinalReport JSON 스키마에 맞춰 출력하세요.
모든 텍스트 필드는 한국어로 작성합니다.
마크다운 서식을 사용할 수 있습니다 (content 필드).
```

### 1.6 내러티브 에이전트 호출 예시

```python
async def run_narrative_agent(
    agent_results: Dict[str, AgentResult],
    debate_result: Optional[DebateResult],
    user_query: UserQuery,
) -> FinalReport:
    """
    내러티브 에이전트를 실행하여 최종 리포트를 생성한다.
    """
    # 1. 세부 점수 계산
    sub_scores = calculate_sub_scores(agent_results)

    # 2. 가중 평균으로 종합 점수 산출
    overall_score = calculate_overall_score(sub_scores)

    # 3. 토론 결과 반영 (±10점 조정)
    adjusted_score = apply_debate_adjustment(overall_score, debate_result)

    # 4. 내러티브 에이전트에 전달할 컨텍스트 구성
    context = {
        "user_query": user_query.to_dict(),
        "agent_results": {k: v.to_dict() for k, v in agent_results.items()},
        "debate_result": debate_result.to_dict() if debate_result else None,
        "sub_scores": sub_scores,
        "overall_score": adjusted_score,
        "score_breakdown": {
            "base_score": overall_score,
            "debate_adjustment": adjusted_score - overall_score,
            "final_score": adjusted_score,
        },
    }

    # 5. Claude Sonnet 4.6 호출
    response = await call_llm(
        model="claude-sonnet-4.6",
        system_prompt=NARRATIVE_AGENT_SYSTEM_PROMPT,
        user_message=json.dumps(context, ensure_ascii=False),
        max_tokens=8192,
        temperature=0.3,
        response_format=FinalReport,  # 구조화된 출력
    )

    return response
```

---

## 2. 시각화 에이전트 (Visualization Agent)

### 2.1 개요

| 항목 | 내용 |
|------|------|
| **LLM** | Gemini 2.5 Flash (코드 생성 최적화) |
| **역할** | 차트 구성(config)과 지도 데이터를 프론트엔드 렌더링용 JSON으로 생성 |
| **출력** | 이미지가 아닌 **JSON 차트 구성** (프론트엔드에서 렌더링) |
| **최대 토큰** | 4,096 (출력) |
| **Temperature** | 0.1 (정확한 JSON 생성) |

### 2.2 ChartConfig 스키마

```python
ChartConfig {
    chart_id: str                  # 고유 차트 식별자
    chart_type: str                # "bar" | "line" | "pie" | "radar" | "scatter" | "gauge" | "geo"
    title: str                     # 차트 제목 (한국어)
    subtitle: Optional[str]        # 부제목
    data: Dict                     # Plotly.js 호환 data 구조
    layout: Dict                   # Plotly.js layout 옵션
    annotations: List[str]         # 차트에 표시할 핵심 인사이트
    responsive: bool               # 반응형 여부 (기본 True)
    export_options: ExportOptions   # 내보내기 옵션
}

ExportOptions {
    allow_png: bool                # PNG 내보내기 허용
    allow_svg: bool                # SVG 내보내기 허용
    width: int                     # 기본 너비 (px)
    height: int                    # 기본 높이 (px)
}
```

### 2.3 생성 차트 목록 (12종)

#### 2.3.1 population_time_chart (시간대별 유동인구)

```json
{
  "chart_id": "population_time_chart",
  "chart_type": "bar",
  "title": "시간대별 유동인구",
  "subtitle": "최근 분기 평균 기준",
  "data": [
    {
      "type": "bar",
      "x": ["06시", "07시", "08시", "09시", "10시", "11시", "12시",
             "13시", "14시", "15시", "16시", "17시", "18시", "19시",
             "20시", "21시", "22시", "23시"],
      "y": [],
      "marker": {
        "color": [],
        "colorscale": "Blues"
      },
      "text": [],
      "textposition": "outside",
      "hovertemplate": "%{x}: %{y:,}명<extra></extra>"
    }
  ],
  "layout": {
    "xaxis": {"title": "시간대", "tickangle": -45},
    "yaxis": {"title": "유동인구 (명)", "separatethousands": true},
    "showlegend": false,
    "margin": {"t": 60, "b": 80, "l": 80, "r": 40},
    "plot_bgcolor": "rgba(0,0,0,0)",
    "paper_bgcolor": "rgba(0,0,0,0)"
  },
  "annotations": ["피크 시간대: 12-13시 (점심), 영업 전략에 참고하세요"],
  "responsive": true,
  "export_options": {"allow_png": true, "allow_svg": true, "width": 800, "height": 450}
}
```

#### 2.3.2 population_day_chart (요일별 유동인구)

```json
{
  "chart_id": "population_day_chart",
  "chart_type": "bar",
  "title": "요일별 유동인구",
  "data": [
    {
      "type": "bar",
      "x": ["월", "화", "수", "목", "금", "토", "일"],
      "y": [],
      "marker": {
        "color": ["#4A90D9", "#4A90D9", "#4A90D9", "#4A90D9", "#4A90D9", "#E8734A", "#E8734A"]
      },
      "hovertemplate": "%{x}요일: %{y:,}명<extra></extra>"
    }
  ],
  "layout": {
    "xaxis": {"title": "요일"},
    "yaxis": {"title": "유동인구 (명)", "separatethousands": true},
    "showlegend": false
  },
  "annotations": []
}
```

#### 2.3.3 age_distribution_chart (연령대별 분포)

```json
{
  "chart_id": "age_distribution_chart",
  "chart_type": "pie",
  "title": "연령대별 유동인구 분포",
  "data": [
    {
      "type": "pie",
      "labels": ["10대", "20대", "30대", "40대", "50대", "60대 이상"],
      "values": [],
      "marker": {
        "colors": ["#FFB347", "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"]
      },
      "textinfo": "label+percent",
      "textposition": "auto",
      "hole": 0.3,
      "hovertemplate": "%{label}: %{value:,}명 (%{percent})<extra></extra>"
    }
  ],
  "layout": {
    "showlegend": true,
    "legend": {"orientation": "h", "y": -0.1}
  },
  "annotations": ["타겟 연령대(20-30대) 비율 강조 표시"]
}
```

#### 2.3.4 revenue_trend_chart (분기별 매출 추이)

```json
{
  "chart_id": "revenue_trend_chart",
  "chart_type": "line",
  "title": "분기별 매출 추이",
  "subtitle": "해당 업종 상권 평균",
  "data": [
    {
      "type": "scatter",
      "mode": "lines+markers",
      "x": [],
      "y": [],
      "name": "해당 상권",
      "line": {"color": "#4A90D9", "width": 3},
      "marker": {"size": 8},
      "hovertemplate": "%{x}: %{y:,.0f}만 원<extra></extra>"
    },
    {
      "type": "scatter",
      "mode": "lines",
      "x": [],
      "y": [],
      "name": "구 평균",
      "line": {"color": "#CCCCCC", "width": 2, "dash": "dash"},
      "hovertemplate": "%{x}: %{y:,.0f}만 원<extra></extra>"
    }
  ],
  "layout": {
    "xaxis": {"title": "분기"},
    "yaxis": {"title": "월 평균 매출 (만 원)", "separatethousands": true},
    "showlegend": true,
    "legend": {"x": 0.01, "y": 0.99}
  },
  "annotations": ["전년 동기 대비 변화율 표시"]
}
```

#### 2.3.5 seasonal_pattern_chart (월별 매출 패턴)

```json
{
  "chart_id": "seasonal_pattern_chart",
  "chart_type": "line",
  "title": "월별 매출 패턴",
  "subtitle": "최근 2년 평균",
  "data": [
    {
      "type": "scatter",
      "mode": "lines+markers+text",
      "x": ["1월", "2월", "3월", "4월", "5월", "6월",
             "7월", "8월", "9월", "10월", "11월", "12월"],
      "y": [],
      "fill": "tozeroy",
      "fillcolor": "rgba(74, 144, 217, 0.1)",
      "line": {"color": "#4A90D9"},
      "hovertemplate": "%{x}: %{y:,.0f}만 원<extra></extra>"
    }
  ],
  "layout": {
    "xaxis": {"title": "월"},
    "yaxis": {"title": "매출 지수 (평균=100)"},
    "shapes": [
      {
        "type": "line",
        "y0": 100, "y1": 100,
        "x0": 0, "x1": 1,
        "xref": "paper",
        "line": {"color": "gray", "width": 1, "dash": "dot"}
      }
    ]
  },
  "annotations": ["성수기/비수기 구간 표시"]
}
```

#### 2.3.6 competition_saturation_gauge (포화도 게이지)

```json
{
  "chart_id": "competition_saturation_gauge",
  "chart_type": "gauge",
  "title": "경쟁 포화도",
  "data": [
    {
      "type": "indicator",
      "mode": "gauge+number+delta",
      "value": null,
      "delta": {"reference": 1.0, "valueformat": ".2f"},
      "title": {"text": "포화도 지수"},
      "gauge": {
        "axis": {"range": [0, 2.0], "tickwidth": 1},
        "bar": {"color": "#4A90D9"},
        "steps": [
          {"range": [0, 0.7], "color": "#4ECDC4", "name": "여유"},
          {"range": [0.7, 1.0], "color": "#FFB347", "name": "적정"},
          {"range": [1.0, 1.5], "color": "#FF6B6B", "name": "포화"},
          {"range": [1.5, 2.0], "color": "#C0392B", "name": "과포화"}
        ],
        "threshold": {
          "line": {"color": "black", "width": 4},
          "thickness": 0.75,
          "value": null
        }
      }
    }
  ],
  "layout": {
    "margin": {"t": 60, "b": 20, "l": 40, "r": 40}
  },
  "annotations": [
    "1.0 미만: 진입 여력 있음",
    "1.0-1.5: 경쟁 치열, 차별화 필수",
    "1.5 이상: 진입 재고 권장"
  ]
}
```

#### 2.3.7 competitor_map_markers (경쟁업체 지도 마커)

```json
{
  "chart_id": "competitor_map_markers",
  "chart_type": "geo",
  "title": "경쟁업체 분포 지도",
  "data": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "Point",
          "coordinates": [0, 0]
        },
        "properties": {
          "name": "",
          "category": "동종" | "유사" | "보완",
          "rating": null,
          "distance_m": null,
          "marker_color": "#FF6B6B" | "#FFB347" | "#4ECDC4",
          "marker_size": "small" | "medium" | "large"
        }
      }
    ],
    "center": {"lat": 0, "lng": 0},
    "zoom": 16,
    "radius_circles": [
      {"radius_m": 100, "color": "#FF6B6B", "opacity": 0.1},
      {"radius_m": 300, "color": "#FFB347", "opacity": 0.05},
      {"radius_m": 500, "color": "#4ECDC4", "opacity": 0.03}
    ],
    "target_location": {
      "lat": 0,
      "lng": 0,
      "marker_color": "#4A90D9",
      "marker_size": "large",
      "label": "분석 대상 위치"
    }
  },
  "annotations": ["동종 업체 강조, 반경별 밀집도 시각화"]
}
```

#### 2.3.8 risk_matrix (리스크 매트릭스)

```json
{
  "chart_id": "risk_matrix",
  "chart_type": "scatter",
  "title": "리스크 매트릭스",
  "subtitle": "발생 확률 vs 영향도",
  "data": [
    {
      "type": "scatter",
      "mode": "markers+text",
      "x": [],
      "y": [],
      "text": [],
      "textposition": "top center",
      "marker": {
        "size": [],
        "color": [],
        "colorscale": [[0, "#4ECDC4"], [0.5, "#FFB347"], [1, "#FF6B6B"]],
        "showscale": true,
        "colorbar": {"title": "리스크 수준"}
      },
      "hovertemplate": "%{text}<br>발생확률: %{x}%<br>영향도: %{y}/10<extra></extra>"
    }
  ],
  "layout": {
    "xaxis": {"title": "발생 확률 (%)", "range": [0, 100]},
    "yaxis": {"title": "영향도 (1-10)", "range": [0, 10]},
    "shapes": [
      {
        "type": "rect",
        "x0": 50, "y0": 5, "x1": 100, "y1": 10,
        "fillcolor": "rgba(255, 107, 107, 0.1)",
        "line": {"width": 0}
      },
      {
        "type": "rect",
        "x0": 0, "y0": 0, "x1": 50, "y1": 5,
        "fillcolor": "rgba(78, 205, 196, 0.1)",
        "line": {"width": 0}
      }
    ]
  },
  "annotations": ["우상단: 최우선 관리 필요, 좌하단: 모니터링 수준"]
}
```

#### 2.3.9 financial_scenario_chart (3시나리오 비교)

```json
{
  "chart_id": "financial_scenario_chart",
  "chart_type": "bar",
  "title": "시나리오별 월 손익 비교",
  "data": [
    {
      "type": "bar",
      "name": "비관적",
      "x": ["매출", "영업이익", "순이익"],
      "y": [],
      "marker": {"color": "#FF6B6B"}
    },
    {
      "type": "bar",
      "name": "기본",
      "x": ["매출", "영업이익", "순이익"],
      "y": [],
      "marker": {"color": "#4A90D9"}
    },
    {
      "type": "bar",
      "name": "낙관적",
      "x": ["매출", "영업이익", "순이익"],
      "y": [],
      "marker": {"color": "#4ECDC4"}
    }
  ],
  "layout": {
    "barmode": "group",
    "yaxis": {"title": "금액 (만 원)", "separatethousands": true},
    "showlegend": true,
    "legend": {"orientation": "h", "y": 1.1}
  },
  "annotations": ["기본 시나리오 기준 손익분기 도달 시점 표시"]
}
```

#### 2.3.10 break_even_chart (손익분기 타임라인)

```json
{
  "chart_id": "break_even_chart",
  "chart_type": "line",
  "title": "누적 손익 추이 (손익분기 분석)",
  "data": [
    {
      "type": "scatter",
      "mode": "lines",
      "name": "비관적",
      "x": [],
      "y": [],
      "line": {"color": "#FF6B6B", "dash": "dash", "width": 1.5}
    },
    {
      "type": "scatter",
      "mode": "lines",
      "name": "기본",
      "x": [],
      "y": [],
      "line": {"color": "#4A90D9", "width": 3}
    },
    {
      "type": "scatter",
      "mode": "lines",
      "name": "낙관적",
      "x": [],
      "y": [],
      "line": {"color": "#4ECDC4", "dash": "dash", "width": 1.5}
    }
  ],
  "layout": {
    "xaxis": {"title": "개업 후 경과 월수"},
    "yaxis": {"title": "누적 손익 (만 원)", "separatethousands": true},
    "shapes": [
      {
        "type": "line",
        "y0": 0, "y1": 0,
        "x0": 0, "x1": 1,
        "xref": "paper",
        "line": {"color": "gray", "width": 2, "dash": "dot"}
      }
    ]
  },
  "annotations": ["손익분기점(BEP) 시점 마커 표시"]
}
```

#### 2.3.11 comparison_radar (종합 비교 레이더)

> 비교 모드 전용 차트

```json
{
  "chart_id": "comparison_radar",
  "chart_type": "radar",
  "title": "종합 비교 분석",
  "data": [
    {
      "type": "scatterpolar",
      "r": [],
      "theta": ["유동인구", "매출잠재력", "경쟁환경", "입지조건", "트렌드", "재무타당성", "리스크"],
      "fill": "toself",
      "name": "상권 A",
      "line": {"color": "#4A90D9"},
      "fillcolor": "rgba(74, 144, 217, 0.2)"
    },
    {
      "type": "scatterpolar",
      "r": [],
      "theta": ["유동인구", "매출잠재력", "경쟁환경", "입지조건", "트렌드", "재무타당성", "리스크"],
      "fill": "toself",
      "name": "상권 B",
      "line": {"color": "#E8734A"},
      "fillcolor": "rgba(232, 115, 74, 0.2)"
    }
  ],
  "layout": {
    "polar": {
      "radialaxis": {"visible": true, "range": [0, 100]}
    },
    "showlegend": true
  },
  "annotations": ["각 축의 점수 차이가 큰 영역 하이라이트"]
}
```

#### 2.3.12 heatmap_data (유동인구 히트맵)

> 지도 오버레이용 데이터

```json
{
  "chart_id": "heatmap_data",
  "chart_type": "geo",
  "title": "유동인구 히트맵",
  "data": {
    "type": "heatmap",
    "points": [
      {
        "lat": 0,
        "lng": 0,
        "intensity": 0.0
      }
    ],
    "config": {
      "radius": 25,
      "maxIntensity": null,
      "minOpacity": 0.3,
      "gradient": {
        "0.2": "#0000FF",
        "0.4": "#00FF00",
        "0.6": "#FFFF00",
        "0.8": "#FFA500",
        "1.0": "#FF0000"
      }
    },
    "center": {"lat": 0, "lng": 0},
    "zoom": 15,
    "time_filter": {
      "available_slots": ["전체", "오전(06-12)", "점심(12-14)", "오후(14-18)", "저녁(18-22)", "심야(22-06)"],
      "default": "전체"
    }
  },
  "annotations": ["피크 시간대 밀집 구역 표시"]
}
```

### 2.4 공통 디자인 시스템

#### 2.4.1 색상 팔레트

```python
COLOR_SCHEME = {
    # Primary
    "primary": "#4A90D9",           # 메인 파란색
    "primary_light": "#7BB3E8",     # 연한 파란
    "primary_dark": "#2E6BA6",      # 진한 파란

    # Secondary
    "secondary": "#E8734A",         # 주황 (비교/대조용)
    "secondary_light": "#F09E7A",
    "secondary_dark": "#C45A33",

    # Semantic
    "positive": "#4ECDC4",          # 긍정/양호 (청록)
    "warning": "#FFB347",           # 주의 (주황)
    "negative": "#FF6B6B",          # 부정/위험 (적색)
    "neutral": "#95A5A6",           # 중립 (회색)

    # Chart Series (최대 6개 시리즈)
    "series": [
        "#4A90D9", "#E8734A", "#4ECDC4",
        "#FFB347", "#96CEB4", "#FF6B6B"
    ],

    # Background
    "bg_chart": "rgba(0,0,0,0)",    # 투명 배경
    "bg_annotation": "rgba(255,255,255,0.8)",

    # Text
    "text_primary": "#2C3E50",
    "text_secondary": "#7F8C8D",
}
```

#### 2.4.2 폰트 설정

```python
FONT_CONFIG = {
    "family": "Pretendard, -apple-system, BlinkMacSystemFont, sans-serif",
    "title_size": 16,
    "subtitle_size": 13,
    "axis_label_size": 12,
    "tick_size": 11,
    "annotation_size": 11,
}
```

#### 2.4.3 반응형 사이징

```python
RESPONSIVE_SIZES = {
    "desktop": {"width": 800, "height": 450},
    "tablet": {"width": 600, "height": 380},
    "mobile": {"width": 360, "height": 300},
}
```

모든 차트는 `responsive: true`로 설정되며, 프론트엔드에서 컨테이너 크기에 맞춰 자동 조정된다.

### 2.5 시각화 에이전트 시스템 프롬프트 (전체)

```
당신은 MarketScope AI의 데이터 시각화 전문가입니다.
분석 결과 데이터를 프론트엔드에서 렌더링할 수 있는 Plotly.js 호환 JSON 차트 구성으로 변환합니다.

═══════════════════════════════════════════
[역할]
═══════════════════════════════════════════
- 분석 에이전트의 결과 데이터를 시각화 JSON으로 변환
- 이미지를 생성하지 않고, 프론트엔드가 렌더링할 수 있는 JSON 구성을 출력
- 모든 차트는 Plotly.js와 호환되어야 함
- 지도 데이터는 GeoJSON 또는 히트맵 포인트 형식으로 출력

═══════════════════════════════════════════
[출력 규칙]
═══════════════════════════════════════════

1. 유효한 JSON만 출력
   - 모든 출력은 파싱 가능한 JSON이어야 함
   - 주석(comment) 포함 금지
   - trailing comma 금지

2. Plotly.js 호환성
   - data 배열의 각 요소는 Plotly trace 객체
   - layout 객체는 Plotly layout 스키마 준수
   - type 필드는 Plotly가 지원하는 차트 타입만 사용
     * bar, scatter(line), pie, scatterpolar(radar), indicator(gauge)
   - 지도(geo) 타입은 GeoJSON 형식으로 별도 처리

3. 한국어 레이블링
   - 모든 title, axis label, legend, hover text는 한국어
   - 숫자 포맷: 천 단위 구분자 사용 (separatethousands: true)
   - 금액: "만 원", "억 원" 단위
   - 인구: "명" 단위
   - 비율: "%" 표시, 소수점 1자리

4. 색상 규칙
   - 반드시 지정된 COLOR_SCHEME 사용
   - 긍정적 지표: #4ECDC4 (청록)
   - 부정적 지표: #FF6B6B (적색)
   - 중립/기준선: #95A5A6 (회색)
   - 비교 시: primary(#4A90D9) vs secondary(#E8734A)
   - 연속 데이터: 단일 컬러의 그라데이션

5. 인사이트 어노테이션
   - annotations 배열에 차트별 핵심 인사이트 포함
   - 최대 3개까지
   - 한국어로 간결하게 작성
   - 예: "피크 시간대: 12-13시 (일 유동인구의 18%)"

6. 반응형 설계
   - responsive: true 기본 설정
   - margin은 충분히 확보 (레이블 잘림 방지)
   - 모바일에서도 읽을 수 있는 최소 폰트 크기 유지

═══════════════════════════════════════════
[차트별 데이터 매핑]
═══════════════════════════════════════════

입력 데이터에서 각 차트로의 매핑 규칙:

1. population_time_chart
   - 소스: population_result.hourly_distribution
   - x: 시간대 (06시~23시)
   - y: 시간대별 평균 유동인구
   - 피크 시간대 바를 다른 색상으로 강조

2. population_day_chart
   - 소스: population_result.daily_distribution
   - x: 요일 (월~일)
   - y: 요일별 평균 유동인구
   - 주말은 다른 색상 (#E8734A)

3. age_distribution_chart
   - 소스: population_result.age_distribution
   - 도넛 차트 (hole: 0.3)
   - 타겟 연령대 슬라이스를 pull out 처리

4. revenue_trend_chart
   - 소스: revenue_result.quarterly_trend
   - 해당 상권 + 구 평균 2개 라인
   - 구 평균은 점선 처리

5. seasonal_pattern_chart
   - 소스: revenue_result.monthly_pattern
   - 영역 채우기(fill) 적용
   - 평균선(y=100) 기준선 표시

6. competition_saturation_gauge
   - 소스: competition_result.saturation_index
   - 게이지 구간: 여유(0-0.7), 적정(0.7-1.0), 포화(1.0-1.5), 과포화(1.5+)

7. competitor_map_markers
   - 소스: competition_result.competitor_list
   - GeoJSON FeatureCollection 형식
   - 동종(적색), 유사(주황), 보완(청록) 색상 구분
   - 반경 원(100m, 300m, 500m) 포함

8. risk_matrix
   - 소스: risk_result.risk_factors
   - x: 발생 확률 (0-100%)
   - y: 영향도 (1-10)
   - 버블 크기: 리스크 수준 반영
   - 4사분면 배경색 구분

9. financial_scenario_chart
   - 소스: financial_result.scenarios (비관/기본/낙관)
   - 그룹 바 차트
   - 매출, 영업이익, 순이익 3개 항목

10. break_even_chart
    - 소스: financial_result.cumulative_pnl
    - 3개 시나리오 라인
    - y=0 기준선(손익분기선) 강조
    - BEP 도달 시점에 마커 표시

11. comparison_radar
    - 소스: 두 상권의 sub_scores
    - 7축: 유동인구, 매출잠재력, 경쟁환경, 입지조건, 트렌드, 재무타당성, 리스크
    - 두 상권 오버레이

12. heatmap_data
    - 소스: population_result.spatial_distribution
    - 위경도 포인트 + intensity
    - 시간대 필터 지원

═══════════════════════════════════════════
[출력 형식]
═══════════════════════════════════════════
반드시 아래 형식의 JSON 배열로 출력하세요:

{
  "charts": [
    { ChartConfig },
    { ChartConfig },
    ...
  ]
}

분석 깊이(QUICK/STANDARD/DEEP)에 따라 생성할 차트 수가 달라집니다:
- QUICK: 5개 (population_time, age_distribution, competition_saturation_gauge, financial_scenario, comparison_radar*)
- STANDARD: 9개 (QUICK + population_day, revenue_trend, risk_matrix, break_even)
- DEEP: 12개 (전체)

* comparison_radar는 비교 모드일 때만 생성
```

### 2.6 시각화 에이전트 호출 예시

```python
async def run_visualization_agent(
    agent_results: Dict[str, AgentResult],
    sub_scores: Dict[str, int],
    analysis_depth: str,
    comparison_data: Optional[ComparisonData] = None,
) -> List[ChartConfig]:
    """
    시각화 에이전트를 실행하여 차트 구성 JSON을 생성한다.
    """
    # 1. 분석 깊이에 따른 차트 목록 결정
    chart_list = get_chart_list_for_depth(analysis_depth, comparison_data)

    # 2. 시각화 에이전트에 전달할 데이터 구성
    viz_input = {
        "agent_results": {k: v.to_dict() for k, v in agent_results.items()},
        "sub_scores": sub_scores,
        "charts_to_generate": chart_list,
        "comparison_data": comparison_data.to_dict() if comparison_data else None,
        "color_scheme": COLOR_SCHEME,
    }

    # 3. Gemini 2.5 Flash 호출
    response = await call_llm(
        model="gemini-2.5-flash",
        system_prompt=VISUALIZATION_AGENT_SYSTEM_PROMPT,
        user_message=json.dumps(viz_input, ensure_ascii=False),
        max_tokens=4096,
        temperature=0.1,
        response_format={"charts": List[ChartConfig]},
    )

    # 4. JSON 유효성 검증
    validated_charts = validate_plotly_compatibility(response["charts"])

    return validated_charts
```

---

## 3. 비교 리포트 명세 (Comparison Report Spec)

### 3.1 개요

사용자가 두 개의 상권(위치)을 비교 분석할 때 생성되는 특수 리포트 형식이다.

### 3.2 비교 리포트 구조

```python
ComparisonReport {
    # 비교 대상
    location_a: LocationInfo        # 상권 A 정보
    location_b: LocationInfo        # 상권 B 정보

    # 종합 비교
    overall_comparison: OverallComparison {
        score_a: int                # 상권 A 종합 점수
        score_b: int                # 상권 B 종합 점수
        winner: "A" | "B" | "DRAW" # 우세 상권
        winner_reason: str          # 우세 판정 사유 (2-3문장)
        score_difference: int       # 점수 차이
    }

    # 영역별 비교 테이블
    comparison_table: List[ComparisonRow] {
        category: str               # "유동인구", "매출잠재력" 등
        score_a: int
        score_b: int
        winner: "A" | "B" | "DRAW"
        comment: str                # 해당 영역 비교 코멘트
    }

    # 섹션별 병렬 분석
    side_by_side_sections: {
        population: SideBySideSection
        revenue: SideBySideSection
        competition: SideBySideSection
        location: SideBySideSection
        trend: SideBySideSection
        financial: SideBySideSection
        risk: SideBySideSection
    }

    # 레이더 차트 (오버레이)
    radar_chart: ChartConfig        # comparison_radar 차트

    # 최종 권고
    final_recommendation: FinalRecommendation {
        recommended: "A" | "B" | "CONDITIONAL"
        reasoning: str              # 상세 판단 근거 (3-5문장)
        conditions: Optional[List[str]]  # CONDITIONAL인 경우 조건 목록
        trade_offs: List[str]       # 양 상권 간 트레이드오프 설명
    }
}

SideBySideSection {
    category: str
    analysis_a: ReportSection       # 상권 A 해당 섹션
    analysis_b: ReportSection       # 상권 B 해당 섹션
    comparison_insight: str         # 비교 인사이트 (2-3문장)
    winner: "A" | "B" | "DRAW"
    winner_highlight: str           # 우세 요소 하이라이트
}
```

### 3.3 비교 리포트 작성 규칙

#### 3.3.1 비교 테이블 형식

```
┌─────────────┬──────────┬──────────┬────────┬──────────────────────────┐
│ 항목        │ 상권 A    │ 상권 B    │ 우세   │ 코멘트                    │
├─────────────┼──────────┼──────────┼────────┼──────────────────────────┤
│ 유동인구     │ 78점 ★   │ 65점     │ A      │ A가 일 3천 명 더 많음      │
│ 매출잠재력   │ 70점     │ 82점 ★   │ B      │ B 업종 평균 매출 20% 높음  │
│ 경쟁환경     │ 60점     │ 55점     │ DRAW   │ 양쪽 모두 포화 상태       │
│ ...         │          │          │        │                          │
├─────────────┼──────────┼──────────┼────────┼──────────────────────────┤
│ 종합        │ 72점     │ 68점     │ A      │                          │
└─────────────┴──────────┴──────────┴────────┴──────────────────────────┘
```

- 우세한 쪽에 ★ 표시
- 점수 차이 5점 이내는 "DRAW"로 판정
- 각 행에 간결한 비교 코멘트 포함

#### 3.3.2 최종 권고 작성 규칙

1. **점수 차이 10점 이상**: 명확한 권고 (recommended = "A" 또는 "B")
   - "상권 A를 권장합니다. [주요 근거 2-3개]"

2. **점수 차이 5-9점**: 조건부 권고 (recommended = "A" 또는 "B")
   - "상권 A가 다소 유리하나, [조건]에 따라 B도 고려할 수 있습니다."

3. **점수 차이 4점 이하**: 조건부 (recommended = "CONDITIONAL")
   - "두 상권의 차이가 크지 않습니다. [업종 특성]을 고려하면 [A/B]가, [다른 조건]을 고려하면 [B/A]가 유리합니다."

4. **트레이드오프 명시**
   - "A는 유동인구에서 우세하고, B는 매출 잠재력에서 우세합니다."
   - 사용자의 우선순위에 따라 선택할 수 있도록 안내

#### 3.3.3 비교 리포트 내러티브 프롬프트 추가 지침

```
═══════════════════════════════════════════
[비교 분석 추가 지침]
═══════════════════════════════════════════

비교 리포트 작성 시, 단일 분석 지침에 추가하여 다음을 따릅니다:

1. 균형 잡힌 비교
   - 한쪽에 편향되지 않도록 양 상권의 장단점을 공정하게 기술
   - 각 영역에서 우세한 쪽을 명확히 하되, 이유를 함께 제시

2. 비교 기준의 일관성
   - 동일한 기준과 동일한 시점의 데이터로 비교
   - 비교 불가능한 항목은 명시적으로 언급

3. 사용자 맥락 반영
   - 사용자의 업종, 예산, 우선순위에 따라 비교 가중치 조정
   - 예: 배달 중심 업종이면 유동인구보다 배달 수요 비중 상향

4. 결론은 명확하게
   - 모호한 결론 지양: "둘 다 좋습니다" → "A가 더 유리하지만, B의 장점은..."
   - 단, 정말 비슷한 경우에는 조건부 결론 허용

5. 시각적 강조
   - 비교 테이블에서 우세 항목 표시
   - 점수 차이가 큰 항목 하이라이트
   - 레이더 차트에서 양 상권 차이가 큰 축 강조
```

---

## 4. 리포트 템플릿 시스템 (Report Template System)

### 4.1 분석 깊이별 템플릿

#### 4.1.1 QUICK (빠른 분석)

| 항목 | 내용 |
|------|------|
| **소요 시간** | 30초 이내 |
| **섹션 수** | 5개 (핵심만) |
| **차트 수** | 5개 |
| **내러티브 길이** | 800-1,200자 |

포함 섹션:
```
1. Executive Summary (핵심 요약)
2. population_summary (유동인구 핵심)
3. competition_summary (경쟁 핵심)
4. financial_summary (재무 핵심)
5. risk_summary (주요 리스크)

+ SWOT 간략 버전 (각 2개씩)
+ 권고사항 3개
```

포함 차트:
```
1. population_time_chart
2. age_distribution_chart
3. competition_saturation_gauge
4. financial_scenario_chart
5. comparison_radar (비교 모드 시)
```

#### 4.1.2 STANDARD (표준 분석)

| 항목 | 내용 |
|------|------|
| **소요 시간** | 1-2분 |
| **섹션 수** | 7개 |
| **차트 수** | 9개 |
| **내러티브 길이** | 2,000-3,500자 |

포함 섹션:
```
1. Executive Summary (핵심 요약)
2. population_summary (유동인구 분석)
3. revenue_summary (매출 분석)
4. competition_summary (경쟁 분석)
5. location_summary (입지 분석)
6. financial_summary (재무 분석)
7. risk_summary (리스크 분석)

+ SWOT 전체 (강점/약점 3-5개, 기회/위협 3개)
+ 권고사항 5개
+ 토론 요약 (실시한 경우)
```

포함 차트:
```
1. population_time_chart
2. population_day_chart
3. age_distribution_chart
4. revenue_trend_chart
5. competition_saturation_gauge
6. risk_matrix
7. financial_scenario_chart
8. break_even_chart
9. comparison_radar (비교 모드 시)
```

#### 4.1.3 DEEP (심층 분석)

| 항목 | 내용 |
|------|------|
| **소요 시간** | 3-5분 |
| **섹션 수** | 9개 (전체) |
| **차트 수** | 12개 (전체) |
| **내러티브 길이** | 4,000-6,000자 |

포함 섹션:
```
1. Executive Summary (핵심 요약 - 확장)
2. population_summary (유동인구 심층 분석)
3. revenue_summary (매출 심층 분석)
4. competition_summary (경쟁 심층 분석)
5. location_summary (입지 심층 분석)
6. trend_summary (트렌드 심층 분석)
7. financial_summary (재무 심층 분석)
8. risk_summary (리스크 심층 분석)
9. real_estate_summary (부동산 분석)
+ regulatory_summary (규제 분석)

+ SWOT 전체 (강점/약점 5개, 기회/위협 3개 + 상세 설명)
+ 권고사항 7개
+ 토론 요약 (상세)
+ 데이터 한계 상세 목록
```

포함 차트:
```
1-12: 전체 차트 (2.3절 참조)
```

### 4.2 리포트 조립 프로세스

```python
async def assemble_report(
    user_query: UserQuery,
    agent_results: Dict[str, AgentResult],
    debate_result: Optional[DebateResult],
    analysis_depth: str,
) -> AssembledReport:
    """
    리포트 조립 메인 프로세스.
    내러티브 에이전트와 시각화 에이전트를 병렬 실행한 후 결합한다.
    """
    # 1. 세부 점수 계산 (동기)
    sub_scores = calculate_sub_scores(agent_results)
    overall_score = calculate_overall_score(sub_scores)
    adjusted_score = apply_debate_adjustment(overall_score, debate_result)

    # 2. 내러티브 + 시각화 병렬 실행
    narrative_task = run_narrative_agent(
        agent_results=agent_results,
        debate_result=debate_result,
        user_query=user_query,
    )

    visualization_task = run_visualization_agent(
        agent_results=agent_results,
        sub_scores=sub_scores,
        analysis_depth=analysis_depth,
    )

    # 병렬 실행
    final_report, charts = await asyncio.gather(
        narrative_task,
        visualization_task,
    )

    # 3. 리포트 + 차트 결합
    assembled = AssembledReport(
        report=final_report,
        charts=charts,
        metadata=ReportMetadata(
            generated_at=datetime.now(),
            analysis_depth=analysis_depth,
            total_agents_used=len(agent_results),
            debate_conducted=debate_result is not None,
            processing_time_seconds=elapsed,
        ),
    )

    # 4. 최종 검증
    validate_report_completeness(assembled, analysis_depth)

    return assembled
```

### 4.3 섹션 조립 순서

리포트 내 섹션 표시 순서는 고정이며, 분석 깊이에 따라 포함 여부만 달라진다.

```
[고정 순서]
1. Executive Summary (항상 최상단)
2. 유동인구 분석
3. 매출 분석
4. 경쟁 분석
5. 입지 분석
6. 트렌드 분석
7. 재무 분석
8. 리스크 분석
9. 부동산 분석
10. 규제 분석
11. SWOT 분석
12. 권고사항
13. 토론 요약
14. 데이터 한계 및 면책
```

### 4.4 리포트 검증 규칙

```python
def validate_report_completeness(
    report: AssembledReport,
    depth: str,
) -> None:
    """
    생성된 리포트의 완전성을 검증한다.
    검증 실패 시 ValidationError를 발생시킨다.
    """
    errors = []

    # 1. 필수 필드 존재 확인
    if not report.report.overall_score:
        errors.append("overall_score 누락")
    if not (0 <= report.report.overall_score <= 100):
        errors.append(f"overall_score 범위 초과: {report.report.overall_score}")
    if not report.report.verdict:
        errors.append("verdict 누락")
    if report.report.verdict not in VALID_VERDICTS:
        errors.append(f"유효하지 않은 verdict: {report.report.verdict}")

    # 2. 분석 깊이에 맞는 섹션 수 확인
    required_sections = DEPTH_SECTION_MAP[depth]
    for section_key in required_sections:
        if section_key not in report.report.sections:
            errors.append(f"필수 섹션 누락: {section_key}")

    # 3. 차트 수 확인
    required_charts = DEPTH_CHART_MAP[depth]
    generated_chart_ids = {c.chart_id for c in report.charts}
    for chart_id in required_charts:
        if chart_id not in generated_chart_ids:
            errors.append(f"필수 차트 누락: {chart_id}")

    # 4. SWOT 항목 수 확인
    min_items = DEPTH_SWOT_MIN[depth]
    if len(report.report.strengths) < min_items["strengths"]:
        errors.append(f"강점 항목 부족: {len(report.report.strengths)}")
    if len(report.report.weaknesses) < min_items["weaknesses"]:
        errors.append(f"약점 항목 부족: {len(report.report.weaknesses)}")

    # 5. 권고사항 수 확인
    min_recs = DEPTH_REC_MIN[depth]
    if len(report.report.recommendations) < min_recs:
        errors.append(f"권고사항 부족: {len(report.report.recommendations)}")

    # 6. 차트 JSON 유효성
    for chart in report.charts:
        if not validate_plotly_json(chart):
            errors.append(f"차트 JSON 유효하지 않음: {chart.chart_id}")

    # 7. 면책 조항 존재 확인
    if not report.report.disclaimer:
        errors.append("면책 조항 누락")

    if errors:
        raise ValidationError(f"리포트 검증 실패: {errors}")
```

### 4.5 PDF 내보내기 고려사항 (향후)

> 현재 버전에서는 미구현이며, 향후 추가 예정인 PDF 내보내기 기능에 대한 설계 고려사항이다.

#### 4.5.1 PDF 생성 방식

```
[선택지]
1. 서버사이드 렌더링: Puppeteer/Playwright로 HTML → PDF 변환
2. 클라이언트사이드: jsPDF + html2canvas
3. 전용 라이브러리: WeasyPrint (Python)

[권장]: 옵션 1 (Puppeteer) - 차트 렌더링 품질 최상
```

#### 4.5.2 PDF 레이아웃 사양

```
- 용지: A4 세로
- 여백: 상하 25mm, 좌우 20mm
- 헤더: MarketScope 로고 + 리포트 제목 + 생성 일시
- 푸터: 페이지 번호 + 면책 조항 요약
- 차트: 벡터(SVG) 기반 삽입 (해상도 독립적)
- 페이지 나누기: 섹션 단위로 자동 분리
- 예상 페이지 수:
  * QUICK: 3-5페이지
  * STANDARD: 8-12페이지
  * DEEP: 15-20페이지
```

#### 4.5.3 PDF 전용 추가 요소

```
- 표지 페이지 (분석 대상, 일시, 종합 점수)
- 목차 자동 생성
- 부록: 데이터 출처 목록, 용어 사전
- 워터마크: "MarketScope AI 분석 리포트"
```

---

## 부록: 에이전트 간 데이터 흐름 요약

```
┌─────────────────────────────────────────────────────────────────┐
│                    사용자 질의 (UserQuery)                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              전문 에이전트 병렬 실행 (7-9개)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │유동인구   │ │매출분석   │ │경쟁분석   │ │입지분석   │ ...       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘           │
└───────┼────────────┼────────────┼────────────┼──────────────────┘
        │            │            │            │
        ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│              토론 시스템 (필요 시)                                │
│              Bull vs Bear 에이전트 토론                           │
│              → DebateResult                                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              점수 계산 엔진                                      │
│              - 세부 점수 산출 (7개 영역)                          │
│              - 가중 평균 종합 점수                                │
│              - 토론 결과 조정 (±10점)                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐
│  내러티브 에이전트     │  │  시각화 에이전트       │
│  (Claude Sonnet 4.6)  │  │  (Gemini 2.5 Flash)  │
│                       │  │                       │
│  → FinalReport        │  │  → List[ChartConfig]  │
│    (한국어 내러티브)    │  │    (Plotly JSON)      │
└───────────┬──────────┘  └──────────┬───────────┘
            │    병렬 실행             │
            └────────────┬────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              리포트 조립 (Report Assembly)                        │
│              - 내러티브 + 차트 결합                               │
│              - 검증 (validate_report_completeness)               │
│              - 메타데이터 첨부                                    │
│              → AssembledReport                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              프론트엔드 전달                                      │
│              - JSON API 응답                                    │
│              - 프론트엔드에서 Plotly.js로 차트 렌더링              │
│              - 지도는 Leaflet/Mapbox로 렌더링                    │
└─────────────────────────────────────────────────────────────────┘
```

---

*본 문서는 MarketScope AI 리포트 생성 시스템의 전체 명세를 정의합니다.*
*버전: 1.0 | 최종 수정: 2026-03-19*
