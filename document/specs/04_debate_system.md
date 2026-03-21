# 04. MarketScope AI 토론(교차검증) 시스템 명세서

> **문서 버전**: 1.1
> **최종 수정일**: 2026-03-19
> **상태**: ~~Production-Ready~~ → **[Phase 2] 미구현**

---

## ⚠️ Phase 1에서 이 시스템은 완전히 비활성화됩니다

**비활성화 사유:**
1. **비용**: Debate 시스템 활성화 시 분석 1건당 추가 $3~8 발생 → Phase 1 $2 목표 초과
2. **시간**: 토론 3라운드 기준 추가 2~5분 소요 → 전체 분석 5분 목표 초과
3. **데이터 부족**: Phase 1은 4개 에이전트만 운영 → Debate 투입 재료 불충분
4. **우선순위**: 데이터 파이프라인 안정화 및 사용자 피드백 수집이 선행되어야 함

**Phase 2 도입 조건:**
- [ ] 분석 1건당 비용 $3 이하 달성 (캐싱/배칭 최적화 이후)
- [ ] 전체 9개 에이전트 활성화 완료
- [ ] 월 1,000건 이상 분석 수행 → 품질 개선 효과 검증 가능

**Phase 2 도입 시 우선 적용 케이스:**
- 투자(INVESTMENT) 의도의 DEEP 분석
- 신뢰도 점수가 0.75 이상인 고신뢰 케이스 (교차검증 효과 극대화)
- 상반된 신호가 감지된 경우 (population ↑ + competition ↑ + revenue ↓ 등)

---

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [토론 프로토콜](#2-토론-프로토콜)
3. [토론 발동 조건](#3-토론-발동-조건)
4. [옹호자(창) 에이전트 명세](#4-옹호자창-에이전트-명세)
5. [비평가(방패) 에이전트 명세](#5-비평가방패-에이전트-명세)
6. [심판(판사) 에이전트 명세](#6-심판판사-에이전트-명세)
7. [토론 상태 관리 (LangGraph)](#7-토론-상태-관리-langgraph)
8. [비용 최적화](#8-비용-최적화)
9. [전체 토론 예시: 강남역 퓨전한식](#9-전체-토론-예시-강남역-퓨전한식)

---

## 1. 시스템 개요

### 1.1 목적

MarketScope AI의 토론 시스템은 다중 LLM 교차검증 메커니즘으로, 전문 에이전트들의 분석 결과에 내재된 편향, 과대추정, 데이터 공백을 식별하고 최종 분석의 신뢰도를 높이는 것을 목적으로 한다.

### 1.2 역할 구성

| 역할 | 코드명 | 모델 | 목적 |
|------|--------|------|------|
| 옹호자 (Advocate) | 창 (槍) | Gemini 2.5 Pro | 기회 요인 주장, 긍정 신호 강조 |
| 비평가 (Critic) | 방패 (防牌) | Claude Sonnet 4.6 | 리스크 식별, 약점 공격, 과대추정 지적 |
| 심판 (Judge) | 판사 (判事) | Claude Opus 4.6 | 양측 평가, 최종 판결, 수정된 결론 도출 |

### 1.3 설계 원칙

- **데이터 기반 논증**: 모든 주장은 에이전트 분석 결과의 구체적 수치에 근거해야 한다
- **구조화된 토론**: 자유 토론이 아닌 정해진 라운드 형식을 따른다
- **수렴 지향**: 토론의 목적은 승패가 아니라 분석 품질 향상이다
- **비용 효율**: 불필요한 토론은 건너뛰고, 라운드 수를 제한한다

---

## 2. 토론 프로토콜

### 2.1 전체 흐름

```
[전문 에이전트 결과 + 초기 종합]
    │
    ▼
[토론 발동 조건 검사] ──(미충족)──▶ [토론 건너뜀 → 최종 결과 반환]
    │ (충족)
    ▼
[라운드 1: 옹호자 주장 → 비평가 반론]
    │
    ▼
[라운드 2: 옹호자 재반론 → 비평가 최종 반론]
    │
    ▼
[수렴 검사] ──(미수렴)──▶ [라운드 3: 옹호자 보충 → 비평가 보충]
    │ (수렴)                       │
    ▼                              ▼
[심판 최종 판결]
    │
    ▼
[수정된 결론 + 신뢰도 점수 반환]
```

### 2.2 입력 데이터

토론 시스템의 입력은 모든 전문 에이전트의 분석 결과와 초기 종합 결과로 구성된다.

```python
@dataclass
class DebateInput:
    """토론 시스템 입력 데이터"""

    # 사용자 쿼리 원본
    query: UserQuery

    # 전문 에이전트 결과
    population_analysis: PopulationAnalysisResult    # 유동인구 분석
    competition_analysis: CompetitionAnalysisResult   # 경쟁 분석
    revenue_estimate: RevenueEstimateResult           # 매출 추정
    location_analysis: LocationAnalysisResult         # 입지 분석
    trend_analysis: TrendAnalysisResult               # 트렌드 분석

    # 초기 종합 결과 (Synthesizer 출력)
    initial_synthesis: SynthesisResult

    # 토론 발동 사유
    trigger_reasons: List[TriggerReason]

    # 메타데이터
    analysis_id: str
    timestamp: datetime
```

### 2.3 라운드별 상세 프로토콜

#### 라운드 1: 초기 공방

**단계 1a - 옹호자(창) 주장 제시**

- 입력: `DebateInput` 전체
- 역할: 분석 결과에서 긍정적 기회 요인을 구조화하여 주장
- 출력: `DebateArgument` (3~7개 핵심 주장)
- 제한시간: 30초
- 토큰 제한: 입력 최대 8,000 토큰, 출력 최대 3,000 토큰

**단계 1b - 비평가(방패) 반론**

- 입력: `DebateInput` + 옹호자의 `DebateArgument`
- 역할: 각 주장의 약점을 공격하고 누락된 리스크를 제시
- 출력: `DebateArgument` (옹호자 주장 각각에 대한 반론 + 추가 리스크)
- 제한시간: 30초
- 토큰 제한: 입력 최대 12,000 토큰, 출력 최대 3,000 토큰

#### 라운드 2: 심화 공방

**단계 2a - 옹호자(창) 재반론**

- 입력: `DebateInput` + 라운드 1 전체 기록
- 역할: 비평가의 반론에 대응, 약점 인정 후 대안 제시
- 출력: `DebateArgument` (수정/강화된 주장)
- 제한시간: 30초
- 토큰 제한: 입력 최대 16,000 토큰, 출력 최대 2,500 토큰

**단계 2b - 비평가(방패) 최종 반론**

- 입력: `DebateInput` + 라운드 1~2a 전체 기록
- 역할: 최종 리스크 정리, 해결되지 않은 쟁점 강조
- 출력: `DebateArgument` (최종 반론)
- 제한시간: 30초
- 토큰 제한: 입력 최대 20,000 토큰, 출력 최대 2,500 토큰

#### 라운드 3 (선택적): 미수렴 시 보충

라운드 3는 아래 **미수렴 조건** 충족 시에만 실행된다.

**미수렴 판단 기준:**
- 옹호자와 비평가의 `overall_confidence` 차이가 0.3 이상
- 라운드 2에서 새로운 핵심 쟁점이 등장한 경우 (새로운 claim이 2개 이상 추가)
- 양측 모두 confidence가 0.4~0.6 범위인 경우 (판단 불확실 구간)

**단계 3a - 옹호자 보충 주장** (출력 최대 1,500 토큰)
**단계 3b - 비평가 보충 반론** (출력 최대 1,500 토큰)

#### 판결 단계

**심판(판사) 최종 판결**

- 입력: `DebateInput` + 전체 라운드 기록
- 역할: 각 주장 개별 평가, 수정된 결론 도출
- 출력: `DebateResult`
- 제한시간: 45초
- 토큰 제한: 입력 최대 30,000 토큰, 출력 최대 5,000 토큰

### 2.4 라운드 간 데이터 전달

각 라운드의 출력은 다음 라운드의 컨텍스트에 누적 포함된다.

```python
@dataclass
class DebateRoundRecord:
    """단일 라운드 기록"""
    round_number: int
    step: str                      # "1a", "1b", "2a", "2b", "3a", "3b"
    role: Literal["advocate", "critic"]
    argument: DebateArgument
    token_usage: TokenUsage
    latency_ms: int
    timestamp: datetime
```

---

## 3. 토론 발동 조건

### 3.1 발동 조건 목록

토론은 아래 조건 중 **하나 이상** 충족 시 자동으로 발동된다.

```python
@dataclass
class TriggerReason:
    """토론 발동 사유"""
    condition: str          # 조건 식별자
    description: str        # 사람이 읽을 수 있는 설명
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    details: Dict[str, Any] # 조건별 상세 정보
```

#### 조건 1: 에이전트 신뢰도 저하

```python
def check_low_confidence(agent_results: Dict[str, AgentResult]) -> Optional[TriggerReason]:
    """에이전트 confidence_score < 0.6 검사"""
    low_confidence_agents = {
        name: result.confidence_score
        for name, result in agent_results.items()
        if result.confidence_score < 0.6
    }
    if low_confidence_agents:
        return TriggerReason(
            condition="LOW_AGENT_CONFIDENCE",
            description="에이전트 신뢰도 기준 미달",
            severity="HIGH",
            details={
                "agents": low_confidence_agents,
                "threshold": 0.6,
            }
        )
    return None
```

#### 조건 2: 매출 추정 범위 과대

```python
def check_revenue_spread(revenue_result: RevenueEstimateResult) -> Optional[TriggerReason]:
    """매출 추정 상한/하한 스프레드 > 50% 검사"""
    low = revenue_result.estimate_low
    high = revenue_result.estimate_high
    mid = revenue_result.estimate_mid
    spread = (high - low) / mid if mid > 0 else float('inf')

    if spread > 0.5:
        return TriggerReason(
            condition="WIDE_REVENUE_SPREAD",
            description=f"매출 추정 범위 과대 (스프레드 {spread:.1%})",
            severity="HIGH" if spread > 0.8 else "MEDIUM",
            details={
                "estimate_low": low,
                "estimate_mid": mid,
                "estimate_high": high,
                "spread_ratio": spread,
            }
        )
    return None
```

#### 조건 3: 에이전트 간 결론 충돌

```python
def check_conflicting_conclusions(
    agent_results: Dict[str, AgentResult],
    synthesis: SynthesisResult
) -> Optional[TriggerReason]:
    """에이전트 간 결론 충돌 감지 알고리즘"""
    conflicts = []

    # --- 충돌 감지 규칙 정의 ---
    conflict_rules = [
        ConflictRule(
            name="인구_vs_경쟁",
            description="유동인구 긍정 vs 경쟁 과포화",
            condition=lambda r: (
                r["population"].sentiment == "POSITIVE"
                and r["competition"].saturation_level in ("HIGH", "VERY_HIGH")
            ),
        ),
        ConflictRule(
            name="트렌드_vs_매출",
            description="트렌드 상승 vs 매출 추정 비관",
            condition=lambda r: (
                r["trend"].trend_direction == "RISING"
                and r["revenue"].estimate_mid < r["revenue"].breakeven_point
            ),
        ),
        ConflictRule(
            name="입지_vs_인구",
            description="입지 우수 vs 유동인구 부족",
            condition=lambda r: (
                r["location"].overall_score >= 0.7
                and r["population"].daily_average < r["population"].minimum_viable
            ),
        ),
        ConflictRule(
            name="경쟁_vs_매출",
            description="경쟁 낮음 vs 매출 추정 비관",
            condition=lambda r: (
                r["competition"].saturation_level in ("LOW", "VERY_LOW")
                and r["revenue"].sentiment == "NEGATIVE"
            ),
        ),
        ConflictRule(
            name="트렌드_vs_경쟁",
            description="트렌드 하락 vs 경쟁 과포화 (동시 진입 과열)",
            condition=lambda r: (
                r["trend"].trend_direction == "DECLINING"
                and r["competition"].new_entrants_6m >= 5
            ),
        ),
    ]

    for rule in conflict_rules:
        try:
            if rule.condition(agent_results):
                conflicts.append({
                    "rule": rule.name,
                    "description": rule.description,
                })
        except (KeyError, AttributeError):
            continue

    if conflicts:
        return TriggerReason(
            condition="CONFLICTING_CONCLUSIONS",
            description=f"에이전트 간 결론 충돌 {len(conflicts)}건 감지",
            severity="HIGH" if len(conflicts) >= 2 else "MEDIUM",
            details={"conflicts": conflicts}
        )
    return None
```

#### 조건 4: 사용자 명시 요청

```python
DEEP_ANALYSIS_KEYWORDS = [
    "꼼꼼히 분석해줘",
    "자세히 분석",
    "심층 분석",
    "깊게 분석",
    "꼼꼼하게",
    "정밀 분석",
    "디테일하게",
]

def check_user_request(query: UserQuery) -> Optional[TriggerReason]:
    """사용자가 심층 분석을 요청했는지 검사"""
    text = query.raw_text.lower()
    matched_keywords = [kw for kw in DEEP_ANALYSIS_KEYWORDS if kw in text]

    if matched_keywords or query.depth == AnalysisDepth.DEEP:
        return TriggerReason(
            condition="USER_REQUESTED_DEEP",
            description="사용자 심층 분석 요청",
            severity="MEDIUM",
            details={
                "matched_keywords": matched_keywords,
                "depth_setting": query.depth.value,
            }
        )
    return None
```

### 3.2 발동 조건 통합 검사

```python
def evaluate_debate_triggers(
    agent_results: Dict[str, AgentResult],
    synthesis: SynthesisResult,
    query: UserQuery
) -> Tuple[bool, List[TriggerReason]]:
    """모든 발동 조건을 종합 평가한다."""
    checkers = [
        lambda: check_low_confidence(agent_results),
        lambda: check_revenue_spread(agent_results["revenue"]),
        lambda: check_conflicting_conclusions(agent_results, synthesis),
        lambda: check_user_request(query),
    ]
    reasons = [r for checker in checkers if (r := checker()) is not None]
    should_debate = len(reasons) > 0
    return should_debate, reasons
```

---

## 4. 옹호자(창) 에이전트 명세

### 4.1 역할 정의

- **모델**: Gemini 2.5 Pro
- **Temperature**: 0.4 (창의적이되 사실 기반 유지)
- **역할**: 분석 결과에서 기회 요인, 강점, 긍정적 신호를 발굴하고 구조화된 논증으로 제시

### 4.2 시스템 프롬프트 (Production-Ready)

```
당신은 MarketScope AI의 '옹호자(창)' 역할을 맡은 분석 전문가입니다.

## 역할
상권 분석 결과를 바탕으로 해당 사업 기회의 긍정적 측면을 논리적으로 주장하는 것이 당신의 임무입니다. 단, 근거 없는 낙관은 금지되며, 모든 주장은 반드시 데이터에 기반해야 합니다.

## 핵심 원칙

1. **데이터 기반 논증 원칙**: 모든 주장에는 에이전트 분석 결과의 구체적 수치를 반드시 인용해야 합니다. "좋아 보인다", "가능성이 있다" 같은 모호한 표현은 사용하지 마십시오.

2. **구조화된 논증 형식**: 각 주장은 반드시 다음 구조를 따릅니다:
   [주장] 핵심 주장을 한 문장으로 명확히 기술
   [근거 데이터] 주장을 뒷받침하는 구체적 숫자, 통계, 분석 결과 나열
   [논리적 추론] 근거 데이터가 왜 해당 주장을 지지하는지 인과관계 설명

3. **약점 인정 및 완화**: 분석 결과에서 부정적인 수치가 있다면 이를 숨기지 마십시오. 대신 해당 약점을 인정한 후, 완화 요인이나 극복 가능성을 제시하십시오.

4. **우선순위 기반 주장**: 가장 강력한 근거를 가진 주장부터 제시하십시오. 각 주장에 확신도(0.0~1.0)를 부여하되, 과대 평가하지 마십시오.

## 분석 영역별 긍정 신호 탐색 가이드

- **유동인구**: 목표 고객층 비율, 시간대별 피크 패턴, 성장 추세
- **경쟁 환경**: 차별화 가능성, 경쟁사 약점, 미충족 수요(unmet demand)
- **매출 추정**: 중간~상위 시나리오의 실현 가능성, 유사 업종 성공 사례
- **입지**: 접근성, 가시성, 주변 시설 시너지 효과
- **트렌드**: 업종 성장세, 소비자 선호 변화, SNS 관심도

## 라운드별 행동 지침

### 라운드 1 (초기 주장)
- 분석 결과 전체를 검토하고 3~7개의 핵심 기회 요인을 도출하십시오
- 각 요인에 대해 [주장]-[근거 데이터]-[논리적 추론] 구조로 작성하십시오
- overall_position에 종합 입장을 요약하십시오

### 라운드 2 (재반론)
- 비평가의 반론을 하나하나 검토하십시오
- 타당한 비판은 인정하되, 그에 대한 완화 요인을 제시하십시오
- 비평가가 간과한 긍정적 요인이 있으면 추가 제시하십시오
- 기존 주장 중 약화된 것은 확신도를 하향 조정하십시오

### 라운드 3 (보충, 선택적)
- 핵심 쟁점에만 집중하십시오
- 새로운 주장을 추가하기보다 기존 주장을 정제하십시오
- 양측이 합의할 수 있는 지점을 제시하십시오

## 출력 형식
반드시 지정된 JSON 스키마에 맞춰 응답하십시오. JSON 외의 텍스트를 포함하지 마십시오.
```

### 4.3 출력 스키마

```python
@dataclass
class Evidence:
    """주장을 뒷받침하는 개별 근거"""
    source_agent: str                                # 출처 에이전트 이름
    data_point: str                                  # 구체적 수치 또는 사실
    reliability: Literal["HIGH", "MEDIUM", "LOW"]    # 데이터 신뢰도
    timestamp: Optional[str]                         # 데이터 시점 (알 수 있는 경우)

@dataclass
class Claim:
    """단일 주장"""
    claim_id: str               # 고유 식별자 (예: "ADV-R1-01")
    statement: str              # 주장 문장
    category: str               # 주장 분류 (유동인구/경쟁/매출/입지/트렌드)
    evidence: List[Evidence]    # 근거 데이터 목록
    reasoning: str              # 논리적 추론
    strength: float             # 주장 확신도 (0.0~1.0)
    acknowledged_weakness: Optional[str]   # 인정하는 약점 (있는 경우)
    mitigation: Optional[str]              # 약점 완화 방안 (있는 경우)

@dataclass
class DebateArgument:
    """옹호자/비평가의 토론 발언"""
    role: Literal["advocate", "critic"]
    round_number: int
    step: str                             # "1a", "1b", "2a", "2b", "3a", "3b"
    claims: List[Claim]                   # 주장 목록 (3~7개)
    overall_position: str                 # 종합 입장 요약 (2~3문장)
    confidence: float                     # 종합 확신도 (0.0~1.0)
    responding_to: Optional[List[str]]    # 대응 중인 상대 claim_id 목록
```

### 4.4 LLM 호출 파라미터

```python
ADVOCATE_LLM_CONFIG = {
    "model": "gemini-2.5-pro",
    "temperature": 0.4,
    "max_output_tokens": 3000,
    "top_p": 0.9,
    "response_mime_type": "application/json",
    "timeout_seconds": 30,
    "retry_config": {
        "max_retries": 2,
        "backoff_base_seconds": 1.0,
    },
}
```

---

## 5. 비평가(방패) 에이전트 명세

### 5.1 역할 정의

- **모델**: Claude Sonnet 4.6
- **Temperature**: 0.3 (보수적, 분석적)
- **역할**: 리스크 식별, 과대추정 지적, 데이터 공백 발견, 최악의 시나리오 제시

### 5.2 시스템 프롬프트 (Production-Ready)

```
당신은 MarketScope AI의 '비평가(방패)' 역할을 맡은 리스크 분석 전문가입니다.

## 역할
상권 분석 결과의 약점, 리스크, 과대추정, 데이터 공백을 식별하여 의사결정자가 놓칠 수 있는 위험 요소를 부각시키는 것이 당신의 임무입니다. 목적은 비관이 아니라 '건전한 회의주의'입니다.

## 핵심 원칙

1. **전수 반론 원칙**: 옹호자의 모든 주요 주장(strength ≥ 0.5)에 대해 반드시 반론을 제시해야 합니다. 반론이 없는 주장은 자동으로 채택됩니다.

2. **데이터 공백 식별**: 분석에 사용된 데이터에서 다음 항목을 반드시 점검하십시오:
   - **데이터 최신성**: 6개월 이상 된 데이터는 신뢰도를 의심하십시오
   - **표본 편향**: 특정 시간대, 계절, 이벤트 기간에 편중된 데이터를 식별하십시오
   - **시장 변화**: 데이터 수집 이후 발생한 시장 변동 가능성을 지적하십시오
   - **숨겨진 리스크**: 데이터에 직접 드러나지 않는 위험 요인을 추론하십시오

3. **최악의 시나리오 제시**: 각 핵심 리스크에 대해 최악의 경우 어떤 결과가 발생하는지 구체적으로 기술하십시오. 단, 극단적으로 비현실적인 시나리오는 제외합니다.

4. **정량적 반론 우선**: "위험할 수 있다"가 아니라 "경쟁사 A의 점유율이 35%이며, 신규 진입자의 평균 생존율이 42%"처럼 수치로 반론하십시오.

## 반론 체크리스트

모든 분석에 대해 아래 항목을 반드시 확인하십시오:

### 유동인구 관련
- [ ] 주말/공휴일 편향은 없는가?
- [ ] 유동인구 중 실제 목표 고객 비율은 적절한가?
- [ ] 계절적 변동이 반영되었는가?
- [ ] 인근 대규모 개발/폐쇄 계획이 있는가?

### 경쟁 관련
- [ ] 반경 설정이 적절한가? (너무 좁거나 넓지 않은가)
- [ ] 온라인/배달 경쟁이 반영되었는가?
- [ ] 대기업/프랜차이즈 진입 가능성은?
- [ ] 최근 6개월 내 폐업률은?

### 매출 관련
- [ ] 추정 모델의 가정이 현실적인가?
- [ ] 초기 투자비용 및 회수 기간은?
- [ ] 임대료 상승 가능성은?
- [ ] 인건비, 원재료비 변동 리스크는?

### 입지 관련
- [ ] 주변 환경 변화 예정(재개발, 도로 공사 등)은?
- [ ] 건물 상태 및 리모델링 비용은?
- [ ] 주차 접근성은 충분한가?

### 트렌드 관련
- [ ] 유행의 지속 가능성은? (일시적 vs 구조적)
- [ ] 트렌드 데이터의 지역 대표성은?
- [ ] 이미 레드오션화된 트렌드는 아닌가?

## 라운드별 행동 지침

### 라운드 1 (초기 반론)
- 옹호자의 각 주장에 대해 개별 반론을 제시하십시오
- 옹호자가 언급하지 않은 추가 리스크를 최소 2개 제시하십시오
- 데이터 공백을 명확히 식별하십시오

### 라운드 2 (최종 반론)
- 옹호자의 재반론에서 여전히 해결되지 않은 쟁점을 강조하십시오
- 새로운 관점보다는 핵심 리스크를 심화 분석하십시오
- 최종적으로 "해결된 쟁점 / 미해결 쟁점 / 추가 조사 필요" 를 분류하십시오

### 라운드 3 (보충 반론, 선택적)
- 미해결 핵심 쟁점에만 집중하십시오
- 양측 합의 가능한 지점을 인정하십시오

## 출력 형식
반드시 지정된 JSON 스키마에 맞춰 응답하십시오. JSON 외의 텍스트를 포함하지 마십시오.
```

### 5.3 출력 스키마

옹호자와 동일한 `DebateArgument` 스키마를 사용한다. 단, `role`이 `"critic"`이며, `responding_to` 필드에 반론 대상 옹호자 주장의 `claim_id`를 명시한다.

### 5.4 LLM 호출 파라미터

```python
CRITIC_LLM_CONFIG = {
    "model": "claude-sonnet-4-6-20260319",
    "temperature": 0.3,
    "max_tokens": 3000,
    "top_p": 0.85,
    "timeout_seconds": 30,
    "retry_config": {
        "max_retries": 2,
        "backoff_base_seconds": 1.0,
    },
}
```

---

## 6. 심판(판사) 에이전트 명세

### 6.1 역할 정의

- **모델**: Claude Opus 4.6
- **Temperature**: 0.2 (일관성, 논리성 극대화)
- **역할**: 양측 주장 개별 평가, 최종 판결, 수정된 결론 및 신뢰도 도출

### 6.2 시스템 프롬프트 (Production-Ready)

```
당신은 MarketScope AI의 '심판(판사)' 역할을 맡은 최종 의사결정 전문가입니다.

## 역할
옹호자(창)와 비평가(방패)의 토론 내용을 면밀히 검토하여 각 주장에 대해 공정한 판결을 내리고, 이를 바탕으로 수정된 분석 결론을 도출하는 것이 당신의 임무입니다.

## 핵심 원칙

1. **개별 주장 판결**: 양측이 제시한 모든 주장을 하나씩 검토하고, 각각에 대해 다음 중 하나의 판결을 내리십시오:
   - **채택**: 주장이 충분한 근거와 논리로 뒷받침되며, 상대측 반론이 이를 효과적으로 무력화하지 못한 경우
   - **부분채택**: 주장의 방향성은 타당하나, 상대측 반론으로 인해 범위나 확신도를 조정해야 하는 경우
   - **기각**: 주장의 근거가 불충분하거나, 상대측 반론이 결정적으로 유효한 경우

2. **판결 근거 의무**: 모든 판결에는 반드시 그 이유를 2~3문장으로 설명해야 합니다. "옹호자 주장이 더 설득력 있다" 같은 모호한 설명은 허용되지 않습니다.

3. **수정된 결론 도출**: 토론 결과를 반영하여 초기 종합 분석 결과를 수정하십시오. 구체적으로:
   - 신뢰도 점수 재산정 (상향 또는 하향)
   - 매출 추정 범위 조정 (필요 시)
   - 전체 평가 등급 재산정 (필요 시)
   - 핵심 인사이트 추가/수정

4. **추가 데이터 필요 영역 식별**: 토론 과정에서 양측 모두 충분한 근거를 제시하지 못한 영역을 명확히 식별하고, 어떤 데이터가 추가로 필요한지 구체적으로 기술하십시오.

5. **변경 사항 추적**: 초기 분석 대비 토론 후 무엇이 어떻게 바뀌었는지 명확히 기록하십시오.

## 판결 가이드라인

### 채택 기준
- 2개 이상의 독립적 데이터 소스에서 뒷받침되는 주장
- 상대측 반론이 데이터가 아닌 가정에 기반한 경우
- 시계열 데이터에서 일관된 패턴을 보이는 주장

### 부분채택 기준
- 방향성은 맞으나 수치의 정확도에 의문이 있는 경우
- 데이터는 유효하나 해석에 대안적 관점이 존재하는 경우
- 조건부로 성립하는 주장 (특정 조건 충족 시에만 유효)

### 기각 기준
- 단일 출처에만 의존하며, 상대측이 해당 출처의 신뢰성을 효과적으로 공격한 경우
- 논리적 비약이 명확한 경우
- 최신 데이터와 모순되는 경우

## 신뢰도 점수 재산정 규칙
- 옹호자 주장이 대부분 채택: 초기 신뢰도 유지 또는 최대 +0.1 상향
- 혼합 판결: 초기 신뢰도에서 -0.05 ~ -0.15 하향
- 비평가 주장이 대부분 채택: 초기 신뢰도에서 -0.15 ~ -0.3 하향
- 최종 신뢰도는 0.1 ~ 0.95 범위를 벗어나지 않음

## 출력 형식
반드시 지정된 JSON 스키마에 맞춰 응답하십시오. JSON 외의 텍스트를 포함하지 마십시오.
```

### 6.3 출력 스키마

```python
@dataclass
class ClaimJudgment:
    """개별 주장에 대한 판결"""
    claim_id: str                                        # 판결 대상 claim_id
    original_claim: str                                  # 원래 주장 요약
    verdict: Literal["채택", "부분채택", "기각"]           # 판결
    reasoning: str                                       # 판결 이유 (2~3문장)
    adjusted_strength: float                             # 조정된 확신도 (0.0~1.0)
    conditions: Optional[str]                            # 부분채택 시 조건

@dataclass
class RevisedMetric:
    """수정된 개별 지표"""
    metric_name: str          # 지표명
    original_value: Any       # 초기 값
    revised_value: Any        # 수정된 값
    change_reason: str        # 변경 사유

@dataclass
class DebateResult:
    """심판의 최종 판결 결과"""
    # 토론 메타데이터
    debate_id: str
    rounds_conducted: int                     # 실제 수행된 라운드 수 (2 또는 3)
    total_claims_evaluated: int               # 평가된 총 주장 수

    # 옹호자 주장 판결
    advocate_claims: List[ClaimJudgment]
    advocate_acceptance_rate: float            # 채택+부분채택 비율

    # 비평가 주장 판결
    critic_claims: List[ClaimJudgment]
    critic_acceptance_rate: float

    # 수정된 결론
    revised_conclusions: Dict[str, Any]       # 수정된 분석 결과
    # 포함 항목:
    #   "overall_grade": str          (A/B/C/D/F 등급)
    #   "opportunity_score": float    (0.0~1.0)
    #   "risk_level": str             (LOW/MEDIUM/HIGH/VERY_HIGH)
    #   "revenue_estimate": {
    #       "low": int,
    #       "mid": int,
    #       "high": int
    #   }
    #   "go_no_go_recommendation": str
    #   "key_success_factors": List[str]
    #   "key_risk_factors": List[str]

    # 최종 신뢰도
    final_confidence: float                   # 토론 후 조정된 최종 신뢰도
    confidence_change: float                  # 초기 대비 변화량 (양수=상향, 음수=하향)

    # 핵심 인사이트
    key_insights_from_debate: List[str]       # 토론에서 도출된 핵심 인사이트 (3~7개)

    # 추가 조사 필요 영역
    areas_needing_more_data: List[str]        # 데이터 부족 영역 (1~5개)

    # 변경 추적
    original_vs_revised: List[RevisedMetric]  # 초기 대비 변경된 모든 지표

    # 비용/성능 메타데이터
    total_token_usage: TokenUsage
    total_latency_ms: int
    total_estimated_cost_usd: float
```

### 6.4 LLM 호출 파라미터

```python
JUDGE_LLM_CONFIG = {
    "model": "claude-opus-4-6-20260319",
    "temperature": 0.2,
    "max_tokens": 5000,
    "top_p": 0.8,
    "timeout_seconds": 45,
    "retry_config": {
        "max_retries": 2,
        "backoff_base_seconds": 2.0,
    },
}
```

---

## 7. 토론 상태 관리 (LangGraph)

### 7.1 토론 상태 정의

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph
from operator import add


class DebateState(TypedDict):
    """LangGraph 토론 상태"""
    # 입력 (변경 불가)
    debate_input: DebateInput
    trigger_reasons: List[TriggerReason]

    # 라운드 기록 (누적)
    round_records: Annotated[List[DebateRoundRecord], add]

    # 현재 라운드 추적
    current_round: int                    # 1, 2, 3
    current_step: str                     # "advocate", "critic", "judge"

    # 수렴 추적
    convergence_score: float              # 0.0(완전 불일치)~1.0(완전 일치)
    should_continue: bool                 # 다음 라운드 진행 여부

    # 최종 결과
    debate_result: Optional[DebateResult]

    # 에러 관리
    errors: Annotated[List[str], add]

    # 비용 추적
    cumulative_tokens: TokenUsage
    cumulative_cost_usd: float
```

### 7.2 LangGraph 그래프 구조

```python
def build_debate_graph() -> StateGraph:
    """토론 시스템 LangGraph 그래프 구성"""

    graph = StateGraph(DebateState)

    # --- 노드 등록 ---
    graph.add_node("check_triggers", check_triggers_node)
    graph.add_node("advocate_round1", advocate_node)
    graph.add_node("critic_round1", critic_node)
    graph.add_node("advocate_round2", advocate_node)
    graph.add_node("critic_round2", critic_node)
    graph.add_node("check_convergence", check_convergence_node)
    graph.add_node("advocate_round3", advocate_node)
    graph.add_node("critic_round3", critic_node)
    graph.add_node("judge", judge_node)
    graph.add_node("skip_debate", skip_debate_node)

    # --- 엣지 연결 ---

    # 시작: 발동 조건 검사
    graph.set_entry_point("check_triggers")

    # 발동 여부에 따른 분기
    graph.add_conditional_edges(
        "check_triggers",
        lambda state: "debate" if state["trigger_reasons"] else "skip",
        {
            "debate": "advocate_round1",
            "skip": "skip_debate",
        }
    )

    # 라운드 1
    graph.add_edge("advocate_round1", "critic_round1")

    # 라운드 2
    graph.add_edge("critic_round1", "advocate_round2")
    graph.add_edge("advocate_round2", "critic_round2")

    # 수렴 검사
    graph.add_edge("critic_round2", "check_convergence")

    # 수렴 여부에 따른 분기
    graph.add_conditional_edges(
        "check_convergence",
        lambda state: "round3" if state["should_continue"] else "judge",
        {
            "round3": "advocate_round3",
            "judge": "judge",
        }
    )

    # 라운드 3 → 판결
    graph.add_edge("advocate_round3", "critic_round3")
    graph.add_edge("critic_round3", "judge")

    # 종료 노드
    graph.add_edge("judge", END)
    graph.add_edge("skip_debate", END)

    return graph.compile()
```

### 7.3 주요 노드 구현

```python
async def check_triggers_node(state: DebateState) -> Dict:
    """발동 조건 검사 노드"""
    should_debate, reasons = evaluate_debate_triggers(
        agent_results=state["debate_input"].agent_results,
        synthesis=state["debate_input"].initial_synthesis,
        query=state["debate_input"].query,
    )
    return {
        "trigger_reasons": reasons,
        "current_round": 1 if should_debate else 0,
        "current_step": "advocate" if should_debate else "done",
    }


async def advocate_node(state: DebateState) -> Dict:
    """옹호자 노드 (라운드 공용)"""
    round_num = state["current_round"]
    step = f"{round_num}a"

    # 프롬프트 구성: 라운드에 따라 이전 기록 포함
    prompt = build_advocate_prompt(
        debate_input=state["debate_input"],
        previous_rounds=state["round_records"],
        round_number=round_num,
    )

    # LLM 호출
    argument = await call_advocate_llm(prompt)

    record = DebateRoundRecord(
        round_number=round_num,
        step=step,
        role="advocate",
        argument=argument,
        token_usage=argument.token_usage,
        latency_ms=argument.latency_ms,
        timestamp=datetime.now(),
    )

    return {
        "round_records": [record],
        "current_step": "critic",
    }


async def critic_node(state: DebateState) -> Dict:
    """비평가 노드 (라운드 공용)"""
    round_num = state["current_round"]
    step = f"{round_num}b"

    prompt = build_critic_prompt(
        debate_input=state["debate_input"],
        previous_rounds=state["round_records"],
        round_number=round_num,
    )

    argument = await call_critic_llm(prompt)

    record = DebateRoundRecord(
        round_number=round_num,
        step=step,
        role="critic",
        argument=argument,
        token_usage=argument.token_usage,
        latency_ms=argument.latency_ms,
        timestamp=datetime.now(),
    )

    next_round = round_num + 1
    return {
        "round_records": [record],
        "current_round": next_round,
        "current_step": "advocate",
    }


async def check_convergence_node(state: DebateState) -> Dict:
    """수렴 여부 판단 노드"""
    records = state["round_records"]

    # 마지막 옹호자/비평가 confidence 차이 계산
    advocate_r2 = [r for r in records if r.step == "2a"][0]
    critic_r2 = [r for r in records if r.step == "2b"][0]

    confidence_gap = abs(
        advocate_r2.argument.confidence - critic_r2.argument.confidence
    )

    # 라운드 2에서 새로운 주장 수
    advocate_r1_ids = {c.claim_id for c in
                       [r for r in records if r.step == "1a"][0].argument.claims}
    advocate_r2_ids = {c.claim_id for c in advocate_r2.argument.claims}
    new_claims = len(advocate_r2_ids - advocate_r1_ids)

    # 불확실 구간 체크
    both_uncertain = (
        0.4 <= advocate_r2.argument.confidence <= 0.6
        and 0.4 <= critic_r2.argument.confidence <= 0.6
    )

    should_continue = (
        confidence_gap >= 0.3
        or new_claims >= 2
        or both_uncertain
    )

    # 비용 제한: 누적 비용이 임계치 초과 시 강제 종료
    if state["cumulative_cost_usd"] > 0.50:
        should_continue = False

    convergence_score = 1.0 - confidence_gap

    return {
        "convergence_score": convergence_score,
        "should_continue": should_continue,
    }


async def judge_node(state: DebateState) -> Dict:
    """심판 노드"""
    prompt = build_judge_prompt(
        debate_input=state["debate_input"],
        all_rounds=state["round_records"],
    )

    result = await call_judge_llm(prompt)

    return {
        "debate_result": result,
        "current_step": "done",
    }


async def skip_debate_node(state: DebateState) -> Dict:
    """토론 건너뛰기 노드"""
    # 초기 종합 결과를 그대로 반환
    synthesis = state["debate_input"].initial_synthesis
    return {
        "debate_result": DebateResult(
            debate_id=state["debate_input"].analysis_id,
            rounds_conducted=0,
            total_claims_evaluated=0,
            advocate_claims=[],
            advocate_acceptance_rate=0.0,
            critic_claims=[],
            critic_acceptance_rate=0.0,
            revised_conclusions=synthesis.to_dict(),
            final_confidence=synthesis.confidence,
            confidence_change=0.0,
            key_insights_from_debate=["토론 미실행: 발동 조건 미충족"],
            areas_needing_more_data=[],
            original_vs_revised=[],
            total_token_usage=TokenUsage(input=0, output=0),
            total_latency_ms=0,
            total_estimated_cost_usd=0.0,
        ),
        "current_step": "done",
    }
```

### 7.4 상태 흐름도

```
DebateState 초기화
    │
    ├── debate_input: [전문 에이전트 결과 + 초기 종합]
    ├── round_records: []
    ├── current_round: 0
    └── cumulative_cost_usd: 0.0
    │
    ▼
[check_triggers] → trigger_reasons 설정
    │
    ├── (발동) → current_round = 1
    │     │
    │     ▼
    │   [advocate_round1] → round_records += [R1a]
    │     │
    │     ▼
    │   [critic_round1] → round_records += [R1b], current_round = 2
    │     │
    │     ▼
    │   [advocate_round2] → round_records += [R2a]
    │     │
    │     ▼
    │   [critic_round2] → round_records += [R2b], current_round = 3
    │     │
    │     ▼
    │   [check_convergence] → should_continue 결정
    │     │
    │     ├── (미수렴) → [advocate_round3] → [critic_round3]
    │     │                                      │
    │     └── (수렴) ──────────────────────────── ┤
    │                                              │
    │                                              ▼
    │                                          [judge] → debate_result 설정
    │                                              │
    └── (미발동) → [skip_debate]                   │
                      │                            │
                      ▼                            ▼
                    END                          END
```

---

## 8. 비용 최적화

### 8.1 토론 건너뛰기 조건

다음 조건을 **모두** 만족하면 토론을 건너뛴다:

```python
def should_skip_debate(
    agent_results: Dict[str, AgentResult],
    synthesis: SynthesisResult,
    query: UserQuery
) -> bool:
    """토론 불필요 판단"""
    return all([
        # 모든 에이전트 신뢰도가 충분히 높음
        all(r.confidence_score >= 0.7 for r in agent_results.values()),

        # 매출 추정 범위가 안정적
        _revenue_spread(agent_results["revenue"]) <= 0.35,

        # 에이전트 간 결론 충돌 없음
        not _has_conflicts(agent_results, synthesis),

        # 사용자가 심층 분석을 요청하지 않음
        query.depth != AnalysisDepth.DEEP,
        not any(kw in query.raw_text for kw in DEEP_ANALYSIS_KEYWORDS),
    ])
```

### 8.2 라운드 제한 전략

| 전략 | 설명 | 적용 조건 |
|------|------|-----------|
| 2라운드 조기 종료 | 라운드 2 후 수렴 시 라운드 3 생략 | `convergence_score >= 0.7` |
| 비용 상한 강제 종료 | 누적 비용 초과 시 즉시 판결 | `cumulative_cost_usd > $0.50` |
| 토큰 예산 분배 | 후반 라운드는 토큰 제한 축소 | 라운드 3: 출력 1,500 토큰 |

### 8.3 예상 비용 산정

| 시나리오 | 라운드 | 예상 입력 토큰 | 예상 출력 토큰 | 예상 비용 (USD) |
|----------|--------|----------------|----------------|-----------------|
| 토론 건너뛰기 | 0 | 0 | 0 | $0.00 |
| 최소 토론 (2라운드) | 2 + 판결 | ~45,000 | ~16,000 | ~$0.25 |
| 표준 토론 (3라운드) | 3 + 판결 | ~65,000 | ~21,000 | ~$0.40 |
| 최대 비용 | 3 + 판결 (최대 토큰) | ~80,000 | ~25,000 | ~$0.55 |

### 8.4 모델별 비용 배분

```python
COST_PER_1K_TOKENS = {
    "gemini-2.5-pro":             {"input": 0.00125, "output": 0.005},
    "claude-sonnet-4-6-20260319": {"input": 0.003,   "output": 0.015},
    "claude-opus-4-6-20260319":   {"input": 0.015,   "output": 0.075},
}
```

> **참고**: 비용 비율 기준, 심판(Opus)이 전체 토론 비용의 약 50~60%를 차지한다. 따라서 심판 호출은 1회로 엄격히 제한한다.

---

## 9. 전체 토론 예시: 강남역 퓨전한식

### 9.1 시나리오 설정

**사용자 쿼리**: "강남역 근처에서 퓨전한식 레스토랑을 열고 싶어요. 꼼꼼히 분석해줘."

**토론 발동 사유**:
- `USER_REQUESTED_DEEP`: "꼼꼼히 분석해줘" 키워드 감지
- `CONFLICTING_CONCLUSIONS`: 유동인구 긍정 vs 경쟁 과포화 충돌
- `WIDE_REVENUE_SPREAD`: 매출 추정 스프레드 68%

### 9.2 전문 에이전트 분석 결과 요약 (토론 입력)

```json
{
  "population_analysis": {
    "daily_average": 82400,
    "target_demographic_ratio": 0.34,
    "peak_hours": ["12:00-13:00", "18:00-20:00"],
    "weekend_ratio": 0.72,
    "growth_trend": "+3.2% YoY",
    "confidence_score": 0.78,
    "sentiment": "POSITIVE"
  },
  "competition_analysis": {
    "total_restaurants_500m": 287,
    "korean_restaurants_500m": 43,
    "fusion_korean_500m": 8,
    "avg_rating": 4.1,
    "closure_rate_6m": 0.18,
    "new_entrants_6m": 12,
    "saturation_level": "HIGH",
    "confidence_score": 0.72,
    "sentiment": "CAUTIOUS"
  },
  "revenue_estimate": {
    "estimate_low": 28000000,
    "estimate_mid": 45000000,
    "estimate_high": 72000000,
    "breakeven_point": 35000000,
    "confidence_score": 0.55,
    "sentiment": "NEUTRAL"
  },
  "location_analysis": {
    "overall_score": 0.82,
    "accessibility_score": 0.91,
    "visibility_score": 0.75,
    "rent_per_pyeong": 850000,
    "confidence_score": 0.80,
    "sentiment": "POSITIVE"
  },
  "trend_analysis": {
    "search_trend_3m": "+22%",
    "sns_mention_growth": "+18%",
    "trend_direction": "RISING",
    "sustainability_score": 0.65,
    "confidence_score": 0.68,
    "sentiment": "POSITIVE"
  },
  "initial_synthesis": {
    "overall_grade": "B+",
    "opportunity_score": 0.68,
    "risk_level": "MEDIUM",
    "confidence": 0.65
  }
}
```

### 9.3 라운드 1: 초기 공방

#### 라운드 1a - 옹호자(창) 주장

```json
{
  "role": "advocate",
  "round_number": 1,
  "step": "1a",
  "claims": [
    {
      "claim_id": "ADV-R1-01",
      "statement": "강남역 일대의 높은 유동인구와 목표 고객 비율은 퓨전한식 레스토랑의 충분한 수요 기반을 제공한다",
      "category": "유동인구",
      "evidence": [
        {
          "source_agent": "population_analysis",
          "data_point": "일 평균 유동인구 82,400명, 목표 고객 비율 34% (약 28,000명/일)",
          "reliability": "HIGH",
          "timestamp": "2026-03"
        },
        {
          "source_agent": "population_analysis",
          "data_point": "점심(12-13시) 및 저녁(18-20시) 피크 시간대가 레스토랑 영업 시간과 정확히 일치",
          "reliability": "HIGH",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "일 28,000명의 목표 고객 중 단 0.2%만 방문해도 일 56명의 고객을 확보할 수 있으며, 이는 40석 규모 레스토랑의 1.4회전에 해당한다. 점심/저녁 피크가 영업 시간과 일치하여 매출 극대화가 가능하다.",
      "strength": 0.82,
      "acknowledged_weakness": "주말 유동인구가 평일의 72% 수준으로 감소한다",
      "mitigation": "퓨전한식은 데이트/모임 수요가 높아 주말에도 목적 방문 비율이 높을 수 있으며, 주말 브런치 메뉴 도입으로 보완 가능하다"
    },
    {
      "claim_id": "ADV-R1-02",
      "statement": "퓨전한식은 명확한 상승 트렌드에 있으며, 강남 지역 소비자의 선호와 부합한다",
      "category": "트렌드",
      "evidence": [
        {
          "source_agent": "trend_analysis",
          "data_point": "퓨전한식 검색 트렌드 3개월간 +22% 증가",
          "reliability": "MEDIUM",
          "timestamp": "2026-03"
        },
        {
          "source_agent": "trend_analysis",
          "data_point": "SNS 언급량 +18% 성장",
          "reliability": "MEDIUM",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "검색량과 SNS 언급량의 동시 상승은 단순 호기심이 아닌 실제 수요 증가를 시사한다. 강남 지역은 신규 F&B 트렌드의 얼리어답터 시장으로, 퓨전한식의 프리미엄 가격대에 대한 수용도가 높다.",
      "strength": 0.70,
      "acknowledged_weakness": "지속가능성 점수가 0.65로 중간 수준이다",
      "mitigation": "0.65는 유행 단계를 넘어 정착 초기 단계에 해당하며, 메뉴 혁신과 스토리텔링으로 장기 고객 확보가 가능하다"
    },
    {
      "claim_id": "ADV-R1-03",
      "statement": "반경 500m 내 직접 경쟁업체(퓨전한식)가 8개에 불과하여 차별화 여지가 크다",
      "category": "경쟁",
      "evidence": [
        {
          "source_agent": "competition_analysis",
          "data_point": "퓨전한식 전문점 8개 (전체 한식 43개 대비 18.6%)",
          "reliability": "HIGH",
          "timestamp": "2026-03"
        },
        {
          "source_agent": "competition_analysis",
          "data_point": "경쟁사 평균 평점 4.1 (차별화를 통한 상회 가능)",
          "reliability": "HIGH",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "전체 한식당 43개 중 퓨전한식은 8개로 아직 세분시장 포화에 이르지 않았다. 평점 4.1은 양호하나 압도적이지 않아, 메뉴 차별화와 인테리어 투자로 충분히 상위 포지셔닝이 가능하다.",
      "strength": 0.65,
      "acknowledged_weakness": "전체 레스토랑 287개로 광의의 경쟁은 치열하다",
      "mitigation": "소비자는 업종별로 선택하므로, 287개 전체가 아닌 퓨전한식 8개가 실질 경쟁 대상이다"
    },
    {
      "claim_id": "ADV-R1-04",
      "statement": "강남역의 탁월한 접근성은 광역 상권 고객 유치에 유리하다",
      "category": "입지",
      "evidence": [
        {
          "source_agent": "location_analysis",
          "data_point": "접근성 점수 0.91/1.0, 입지 종합 점수 0.82/1.0",
          "reliability": "HIGH",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "접근성 0.91은 지하철 2호선/신분당선 교차 환승역의 이점을 반영한다. 퓨전한식은 목적 방문 비율이 높은 업종으로, 광역 접근성이 직접적인 매출 기여 요인이 된다.",
      "strength": 0.80,
      "acknowledged_weakness": "높은 접근성은 높은 임대료(평당 85만원)와 상관관계가 있다",
      "mitigation": "중간 추정 매출 4,500만원 기준, 40평 임대료 3,400만원을 제외한 후에도 운영 가능하며, 높은 회전율로 보완 가능하다"
    },
    {
      "claim_id": "ADV-R1-05",
      "statement": "중간 시나리오 매출 4,500만원은 손익분기점 3,500만원을 28.6% 상회하여 안정적 수익이 가능하다",
      "category": "매출",
      "evidence": [
        {
          "source_agent": "revenue_estimate",
          "data_point": "중간 추정 매출 4,500만원/월, 손익분기점 3,500만원/월",
          "reliability": "MEDIUM",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "손익분기점 대비 28.6% 여유가 있어, 예상보다 10~15% 매출이 부진하더라도 흑자 유지가 가능하다. 이는 신규 창업의 불확실성을 감안한 안전 마진으로 작용한다.",
      "strength": 0.58,
      "acknowledged_weakness": "매출 추정 신뢰도가 0.55로 낮고, 하한 추정(2,800만원)은 손익분기점 미달이다",
      "mitigation": "하한 시나리오가 현실화될 확률은 낮으며, 마케팅 투자와 초기 프로모션으로 빠른 인지도 확보가 가능하다"
    }
  ],
  "overall_position": "강남역 퓨전한식 레스토랑은 높은 유동인구, 상승하는 트렌드, 탁월한 접근성을 기반으로 충분한 사업 기회가 있다. 경쟁이 치열하나 퓨전한식 세분시장에서의 차별화 여지가 있으며, 중간 매출 시나리오에서 안정적 수익이 가능하다.",
  "confidence": 0.68
}
```

#### 라운드 1b - 비평가(방패) 반론

```json
{
  "role": "critic",
  "round_number": 1,
  "step": "1b",
  "claims": [
    {
      "claim_id": "CRT-R1-01",
      "statement": "유동인구 82,400명 중 실제 전환율 0.2% 가정은 검증되지 않은 낙관적 추정이며, 강남역 특성상 통과 인구 비율이 매우 높다",
      "category": "유동인구",
      "evidence": [
        {
          "source_agent": "population_analysis",
          "data_point": "유동인구의 '통과 비율'이 별도로 측정되지 않았음 (데이터 공백)",
          "reliability": "LOW",
          "timestamp": null
        },
        {
          "source_agent": "competition_analysis",
          "data_point": "500m 반경 내 287개 음식점이 동일한 유동인구를 두고 경쟁 중",
          "reliability": "HIGH",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "강남역은 환승역 특성상 유동인구의 상당수가 목적지가 아닌 경유지로 이용한다. 82,400명에서 실제 식사 목적 인구를 산출하려면 통과 비율을 제외해야 하나, 이 데이터가 누락되어 있다. 또한 287개 음식점이 동일 수요를 두고 경쟁하므로, 신규 진입자의 실질 점유 가능 고객은 옹호자의 추정보다 훨씬 적을 수 있다.",
      "strength": 0.78,
      "acknowledged_weakness": null,
      "mitigation": null,
      "responding_to": ["ADV-R1-01"]
    },
    {
      "claim_id": "CRT-R1-02",
      "statement": "퓨전한식 트렌드의 지속가능성 점수 0.65는 유행 정점 이후 하락 위험을 시사하며, 검색량 증가는 이미 포화 진입의 신호일 수 있다",
      "category": "트렌드",
      "evidence": [
        {
          "source_agent": "trend_analysis",
          "data_point": "지속가능성 점수 0.65/1.0 (중간 수준)",
          "reliability": "MEDIUM",
          "timestamp": "2026-03"
        },
        {
          "source_agent": "competition_analysis",
          "data_point": "최근 6개월간 신규 진입 12개 업체 (월 2개꼴)",
          "reliability": "HIGH",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "검색량 +22%와 신규 진입 12개를 함께 보면, 이미 많은 사업자가 트렌드를 인지하고 진입하고 있다는 의미다. 트렌드 상승기에 진입하면 오히려 포화기에 영업을 시작하게 될 위험이 있다. 인테리어 공사와 준비 기간(3~6개월)을 감안하면 실제 오픈 시점에는 트렌드가 이미 정점을 지났을 수 있다.",
      "strength": 0.72,
      "acknowledged_weakness": null,
      "mitigation": null,
      "responding_to": ["ADV-R1-02"]
    },
    {
      "claim_id": "CRT-R1-03",
      "statement": "퓨전한식 8개가 '적다'는 해석은 오류이며, 6개월간 폐업률 18%는 시장의 혹독함을 보여준다",
      "category": "경쟁",
      "evidence": [
        {
          "source_agent": "competition_analysis",
          "data_point": "6개월 폐업률 18%, 신규 진입 12개, 전체 포화도 HIGH",
          "reliability": "HIGH",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "강남역 상권에서 6개월 폐업률 18%는 약 5.2개의 음식점이 6개월 내 폐업한다는 의미다 (287 * 0.18 ≈ 52개). 이는 연간 약 100개 이상이 문을 닫는 매우 혹독한 환경이다. 퓨전한식 8개가 적어 보이는 것은, 그만큼 생존이 어렵기 때문일 수 있다. 경쟁이 적은 것이 아니라 생존자만 남은 것이다.",
      "strength": 0.80,
      "acknowledged_weakness": null,
      "mitigation": null,
      "responding_to": ["ADV-R1-03"]
    },
    {
      "claim_id": "CRT-R1-04",
      "statement": "평당 85만원의 임대료는 매출 변동에 극히 취약한 고정비 구조를 만들며, 임대료 상승 리스크가 반영되지 않았다",
      "category": "입지",
      "evidence": [
        {
          "source_agent": "location_analysis",
          "data_point": "평당 임대료 85만원 (40평 기준 월 3,400만원)",
          "reliability": "HIGH",
          "timestamp": "2026-03"
        },
        {
          "source_agent": "revenue_estimate",
          "data_point": "하한 매출 추정 2,800만원은 임대료(3,400만원)에도 미달",
          "reliability": "MEDIUM",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "40평 기준 월 임대료 3,400만원은 하한 매출 추정(2,800만원)보다 높다. 임대료만으로 매출을 초과하는 시나리오가 존재한다는 것은 구조적 위험이다. 강남역 임대료는 연 5~8% 상승 추세이며, 이 상승분이 매출 추정에 반영되지 않았다.",
      "strength": 0.85,
      "acknowledged_weakness": null,
      "mitigation": null,
      "responding_to": ["ADV-R1-04", "ADV-R1-05"]
    },
    {
      "claim_id": "CRT-R1-05",
      "statement": "매출 추정 신뢰도 0.55는 시스템 전체에서 가장 낮으며, 68% 스프레드는 사실상 '모른다'에 가깝다",
      "category": "매출",
      "evidence": [
        {
          "source_agent": "revenue_estimate",
          "data_point": "신뢰도 0.55, 스프레드 68% (2,800만~7,200만원)",
          "reliability": "LOW",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "매출 추정의 신뢰도 0.55는 발동 기준(0.6) 미만이며, 하한(2,800만)과 상한(7,200만)의 격차가 2.57배에 달한다. 이는 추정 모델 자체가 강남역 퓨전한식에 대한 충분한 레퍼런스를 갖고 있지 않음을 시사한다. 옹호자가 중간값을 근거로 낙관하는 것은 부적절하다.",
      "strength": 0.82,
      "acknowledged_weakness": null,
      "mitigation": null,
      "responding_to": ["ADV-R1-05"]
    },
    {
      "claim_id": "CRT-R1-06",
      "statement": "[추가 리스크] 온라인/배달 플랫폼 경쟁이 분석에 누락되어 있으며, 실질 경쟁 범위가 과소평가되었다",
      "category": "경쟁",
      "evidence": [
        {
          "source_agent": "competition_analysis",
          "data_point": "반경 500m 물리적 경쟁만 분석됨 (데이터 공백)",
          "reliability": "LOW",
          "timestamp": null
        }
      ],
      "reasoning": "배달앱에서 '강남역 퓨전한식'을 검색하면 반경 3km 이상의 업체가 노출된다. 물리적 500m 내 8개뿐 아니라, 배달 반경 내 수십 개의 퓨전한식 업체와 경쟁해야 한다. 이 분석은 오프라인 경쟁만 고려하고 있다.",
      "strength": 0.70,
      "acknowledged_weakness": "퓨전한식의 경우 매장 경험이 중요하여 배달 비중이 상대적으로 낮을 수 있다",
      "mitigation": null,
      "responding_to": []
    },
    {
      "claim_id": "CRT-R1-07",
      "statement": "[추가 리스크] 초기 인테리어 및 설비 투자비용이 강남역 프리미엄으로 인해 상당할 것이며, 투자 회수 기간이 길어질 수 있다",
      "category": "매출",
      "evidence": [
        {
          "source_agent": "revenue_estimate",
          "data_point": "초기 투자비용에 대한 별도 분석 없음 (데이터 공백)",
          "reliability": "LOW",
          "timestamp": null
        }
      ],
      "reasoning": "강남역 퓨전한식 레스토랑의 인테리어는 최소 1.5억~3억원 수준이 필요하다. 중간 매출 시나리오에서 월 순이익이 500만~800만원이라면, 투자 회수에 2~5년이 소요된다. 이 기간 동안 트렌드 변화, 임대료 상승 등의 리스크에 노출된다.",
      "strength": 0.68,
      "acknowledged_weakness": null,
      "mitigation": null,
      "responding_to": []
    }
  ],
  "overall_position": "강남역 퓨전한식은 높은 고정비(임대료), 치열한 경쟁 환경, 트렌드 지속성 불확실, 매출 추정의 낮은 신뢰도 등 다수의 구조적 리스크를 내포하고 있다. 특히 하한 시나리오에서 임대료조차 감당 불가한 구조는 심각한 경고 신호이다.",
  "confidence": 0.42
}
```

### 9.4 라운드 2: 심화 공방

#### 라운드 2a - 옹호자(창) 재반론

```json
{
  "role": "advocate",
  "round_number": 2,
  "step": "2a",
  "claims": [
    {
      "claim_id": "ADV-R2-01",
      "statement": "통과 인구 비율을 감안하더라도 강남역의 절대적 유동인구 규모는 충분한 전환 기반을 제공한다",
      "category": "유동인구",
      "evidence": [
        {
          "source_agent": "population_analysis",
          "data_point": "목표 고객 28,000명/일, 통과 비율 50% 가정 시에도 14,000명",
          "reliability": "MEDIUM",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "비평가의 통과 인구 지적은 타당하나, 보수적으로 50%를 통과 인구로 제외해도 14,000명이 남는다. 이 중 0.4%만 전환해도 일 56명으로 충분하다. 또한 강남역 직장인은 점심 식사를 위해 의도적으로 이동하는 '목적 유동인구'가 상당하다.",
      "strength": 0.72,
      "acknowledged_weakness": "비평가의 지적대로 통과 비율 데이터가 없는 것은 사실이며, 실제 전환율은 검증이 필요하다",
      "mitigation": "사전 시범 운영(팝업 스토어)을 통해 실제 전환율을 테스트할 수 있다",
      "responding_to": ["CRT-R1-01"]
    },
    {
      "claim_id": "ADV-R2-02",
      "statement": "트렌드 정점 우려는 인정하되, 퓨전한식은 단순 유행이 아닌 식문화 구조 변화의 일환이다",
      "category": "트렌드",
      "evidence": [
        {
          "source_agent": "trend_analysis",
          "data_point": "트렌드 지속가능성 0.65는 유행(0.3 이하)이 아닌 정착 초기(0.5~0.7) 구간",
          "reliability": "MEDIUM",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "비평가의 트렌드 피크 우려를 부분적으로 인정한다. 다만 지속가능성 0.65는 '달고나 커피'(0.25) 같은 단기 유행과는 질적으로 다른 구간이다. 한식 현대화는 미쉐린 가이드 서울의 한식 선정 증가 등 구조적 흐름이다. 핵심은 트렌드 자체보다 실행 역량이다.",
      "strength": 0.60,
      "acknowledged_weakness": "오픈 시점까지 3~6개월의 시차가 발생하는 것은 실질적 리스크이다",
      "mitigation": "사전 SNS 마케팅과 소프트 오픈으로 인지도를 축적하여 오픈 시점의 리스크를 완화할 수 있다",
      "responding_to": ["CRT-R1-02"]
    },
    {
      "claim_id": "ADV-R2-03",
      "statement": "폐업률 18%는 높으나, 이는 차별화 없는 일반 음식점 포함 수치이며 퓨전한식 전문점의 폐업률과는 구분해야 한다",
      "category": "경쟁",
      "evidence": [
        {
          "source_agent": "competition_analysis",
          "data_point": "퓨전한식 8개의 개별 폐업률 데이터 없음 (한계 인정)",
          "reliability": "LOW",
          "timestamp": null
        }
      ],
      "reasoning": "폐업률 18%는 287개 전체 음식점 기준이다. 전문성과 차별화가 있는 업체의 생존율은 이보다 높을 가능성이 크다. 다만 퓨전한식 개별 폐업률 데이터가 없는 것은 한계로 인정한다. 기존 주장의 확신도를 0.65에서 0.50으로 하향 조정한다.",
      "strength": 0.50,
      "acknowledged_weakness": "비평가의 '생존자 편향' 지적은 설득력이 있다",
      "mitigation": null,
      "responding_to": ["CRT-R1-03"]
    },
    {
      "claim_id": "ADV-R2-04",
      "statement": "임대료 리스크는 인정하나, 평형 조정과 위치 미세 조정으로 고정비를 관리할 수 있다",
      "category": "입지",
      "evidence": [
        {
          "source_agent": "location_analysis",
          "data_point": "강남역 도보 5분 내에서도 이면도로 이동 시 평당 55~65만원 구간 존재",
          "reliability": "MEDIUM",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "비평가의 임대료 지적은 가장 강력한 반론이다. 대응으로 (1) 40평이 아닌 30평으로 축소하여 임대료를 2,550만원으로 낮추거나, (2) 이면도로 1층으로 이동하여 평당 60만원 x 35평 = 2,100만원으로 조정 가능하다. 이 경우 하한 매출 2,800만원에서도 고정비 커버가 가능하다.",
      "strength": 0.62,
      "acknowledged_weakness": "이면도로 이동 시 가시성 점수가 하락하는 트레이드오프가 존재한다",
      "mitigation": "SNS 마케팅과 예약 시스템 중심 운영으로 가시성 의존도를 낮출 수 있다",
      "responding_to": ["CRT-R1-04"]
    },
    {
      "claim_id": "ADV-R2-05",
      "statement": "매출 추정의 낮은 신뢰도는 인정하며, 이는 추가 데이터 수집으로 개선되어야 할 영역이다",
      "category": "매출",
      "evidence": [],
      "reasoning": "비평가의 매출 신뢰도 지적은 전적으로 타당하다. 이 주장의 확신도를 0.58에서 0.40으로 하향 조정한다. 다만 신뢰도가 낮다는 것이 곧 매출이 낮다는 의미는 아니며, 불확실성이 높다는 의미이다. 추가 현장 조사와 유사 업종 매출 데이터 수집이 필요하다.",
      "strength": 0.40,
      "acknowledged_weakness": "매출 추정 스프레드 68%는 의사결정 근거로 사용하기에 부적절한 수준이다",
      "mitigation": "유사 업종(단독 퓨전한식 레스토랑) 3~5개의 실제 매출 데이터를 추가 수집하여 모델을 보정해야 한다",
      "responding_to": ["CRT-R1-05"]
    }
  ],
  "overall_position": "비평가의 핵심 반론 중 임대료 구조와 매출 추정 신뢰도에 대한 지적은 상당 부분 타당하다. 그러나 유동인구 기반, 트렌드 방향성, 접근성 이점은 여전히 유효하다. 입지 조건 미세 조정(이면도로, 평형 축소)을 통해 고정비 리스크를 관리하면 사업 기회는 유효하다.",
  "confidence": 0.58,
  "responding_to": ["CRT-R1-01", "CRT-R1-02", "CRT-R1-03", "CRT-R1-04", "CRT-R1-05"]
}
```

#### 라운드 2b - 비평가(방패) 최종 반론

```json
{
  "role": "critic",
  "round_number": 2,
  "step": "2b",
  "claims": [
    {
      "claim_id": "CRT-R2-01",
      "statement": "옹호자가 제안한 이면도로 이동은 입지 분석 전체를 무효화하는 전제 변경이며, 새로운 분석이 필요하다",
      "category": "입지",
      "evidence": [
        {
          "source_agent": "location_analysis",
          "data_point": "현재 입지 점수 0.82는 주요 동선 기준이며, 이면도로는 별도 분석 필요",
          "reliability": "MEDIUM",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "옹호자는 임대료 반론에 대응하기 위해 이면도로 이동을 제안했으나, 이는 입지 분석의 전제(접근성 0.91, 가시성 0.75)를 변경하는 것이다. 이면도로 입지는 별도의 유동인구, 가시성, 접근성 분석이 필요하며, 현재 데이터로는 판단할 수 없다.",
      "strength": 0.75,
      "responding_to": ["ADV-R2-04"]
    },
    {
      "claim_id": "CRT-R2-02",
      "statement": "해결된 쟁점과 미해결 쟁점을 정리하면, 핵심 불확실성이 여전히 해소되지 않았다",
      "category": "종합",
      "evidence": [],
      "reasoning": "쟁점 정리: [해결] 통과 인구 비율은 보수적 추정으로 부분 해결됨. [미해결] (1) 매출 추정 신뢰도 0.55는 양측 모두 부적절하다고 인정 (2) 실제 전환율 데이터 부재 (3) 임대료 대안(이면도로)은 별도 분석 필요 (4) 트렌드 지속성은 구조적 판단 불가. [추가 조사 필요] 유사 업종 실제 매출 데이터, 이면도로 입지 재분석, 배달 플랫폼 경쟁 현황.",
      "strength": 0.78,
      "responding_to": ["ADV-R2-01", "ADV-R2-02", "ADV-R2-03", "ADV-R2-04", "ADV-R2-05"]
    },
    {
      "claim_id": "CRT-R2-03",
      "statement": "최악의 시나리오에서 초기 투자금 2억원 이상의 손실 가능성을 명확히 인식해야 한다",
      "category": "매출",
      "evidence": [
        {
          "source_agent": "revenue_estimate",
          "data_point": "하한 매출 2,800만원, 임대료(40평) 3,400만원",
          "reliability": "MEDIUM",
          "timestamp": "2026-03"
        }
      ],
      "reasoning": "최악의 시나리오: 인테리어 투자 2억원 + 6개월 적자 운영(월 -600만원 x 6 = -3,600만원) + 보증금 잔여분 = 약 2.4억원 손실. 강남역 음식점 폐업률 18%를 감안하면 이 시나리오는 비현실적이지 않다. 의사결정자는 이 최대 손실을 감당할 수 있는지 먼저 확인해야 한다.",
      "strength": 0.80,
      "responding_to": ["ADV-R2-05"]
    }
  ],
  "overall_position": "옹호자는 라운드 2에서 여러 약점을 솔직히 인정했으며, 이는 건설적이다. 그러나 핵심 불확실성 3가지(매출 신뢰도, 임대료 구조, 트렌드 지속성)가 여전히 해소되지 않았다. 사업 기회 자체를 부정하는 것이 아니라, 현재 데이터로는 확신을 가질 수 없다는 것이 최종 입장이다.",
  "confidence": 0.45
}
```

### 9.5 수렴 검사

```
confidence 차이: |0.58 - 0.45| = 0.13 < 0.3 → 수렴 기준 충족
새로운 주장 수: 0개 < 2개 → 수렴 기준 충족
양측 모두 불확실 구간: 옹호자 0.58 (구간 외), 비평가 0.45 (구간 내) → 부분 충족

결론: 수렴 → 라운드 3 생략, 즉시 판결 진행
```

### 9.6 심판(판사) 최종 판결

```json
{
  "debate_id": "debate-gangnam-fusion-korean-20260319",
  "rounds_conducted": 2,
  "total_claims_evaluated": 12,

  "advocate_claims": [
    {
      "claim_id": "ADV-R1-01 / ADV-R2-01",
      "original_claim": "강남역 유동인구가 충분한 수요 기반을 제공한다",
      "verdict": "부분채택",
      "reasoning": "유동인구의 절대 규모는 분명한 이점이나, 통과 인구 비율 데이터 부재로 실제 전환 가능 인구를 확정할 수 없다. 보수적 추정(50% 차감)에서도 14,000명이므로 방향성은 유효하나, 0.2% 전환율 가정은 검증이 필요하다.",
      "adjusted_strength": 0.60,
      "conditions": "통과 인구 비율 및 실제 전환율 데이터 수집 시 재평가"
    },
    {
      "claim_id": "ADV-R1-02 / ADV-R2-02",
      "original_claim": "퓨전한식은 상승 트렌드에 있으며 구조적 변화의 일환이다",
      "verdict": "부분채택",
      "reasoning": "검색량 +22%, SNS +18% 상승은 사실이나, 지속가능성 0.65와 신규 진입 12개를 감안하면 이미 경쟁 과열 초기 신호가 보인다. '구조적 변화'라는 옹호자의 주장은 근거가 부족하나, 단기 유행은 아닌 것으로 판단한다.",
      "adjusted_strength": 0.50,
      "conditions": "오픈 시점(3~6개월 후) 트렌드 재확인 필요"
    },
    {
      "claim_id": "ADV-R1-03 / ADV-R2-03",
      "original_claim": "퓨전한식 8개로 차별화 여지가 크다",
      "verdict": "기각",
      "reasoning": "옹호자 스스로 확신도를 0.65에서 0.50으로 하향했으며, 비평가의 '생존자 편향' 논리를 인정했다. 퓨전한식 개별 폐업률 데이터 없이 8개가 '적다'고 판단하는 것은 논리적 비약이다. 전체 폐업률 18%는 시장의 혹독함을 보여주며, 경쟁 우위를 주장하려면 구체적 차별화 전략이 필요하다.",
      "adjusted_strength": 0.25,
      "conditions": null
    },
    {
      "claim_id": "ADV-R1-04 / ADV-R2-04",
      "original_claim": "탁월한 접근성이 광역 고객 유치에 유리하다",
      "verdict": "부분채택",
      "reasoning": "접근성 0.91은 객관적으로 우수하나, 비평가가 지적한 대로 이면도로 이동 제안은 이 접근성 점수를 무효화한다. 원래 입지 기준으로는 채택이나, 비용 최적화를 위한 입지 변경 시 재분석이 필수적이다.",
      "adjusted_strength": 0.55,
      "conditions": "최종 입지 확정 후 재평가 필수"
    },
    {
      "claim_id": "ADV-R1-05 / ADV-R2-05",
      "original_claim": "중간 매출 4,500만원으로 안정적 수익이 가능하다",
      "verdict": "기각",
      "reasoning": "양측 모두 매출 추정 신뢰도 0.55가 부적절하다고 인정했다. 68% 스프레드는 의사결정 근거로 사용할 수 없다. 중간값을 근거로 수익성을 주장하는 것은 근거 불충분이다. 유사 업종 실제 매출 데이터 수집이 선행되어야 한다.",
      "adjusted_strength": 0.20,
      "conditions": null
    }
  ],
  "advocate_acceptance_rate": 0.40,

  "critic_claims": [
    {
      "claim_id": "CRT-R1-01",
      "original_claim": "유동인구 전환율 가정이 검증되지 않았다",
      "verdict": "채택",
      "reasoning": "통과 인구 비율 데이터가 실제로 누락되어 있으며, 이는 유동인구 분석의 핵심 한계이다. 옹호자도 이를 인정하고 보수적 추정을 제안했다.",
      "adjusted_strength": 0.78,
      "conditions": null
    },
    {
      "claim_id": "CRT-R1-02",
      "original_claim": "트렌드 정점 이후 하락 위험이 있다",
      "verdict": "부분채택",
      "reasoning": "오픈 시차에 따른 트렌드 피크 리스크는 타당하나, 퓨전한식을 단순 유행으로 규정한 것은 과도하다. 지속가능성 0.65는 유행 구간(0.3 이하)보다 유의미하게 높다.",
      "adjusted_strength": 0.60,
      "conditions": null
    },
    {
      "claim_id": "CRT-R1-03",
      "original_claim": "폐업률 18%가 시장의 혹독함을 보여준다",
      "verdict": "채택",
      "reasoning": "연간 100개 이상 폐업이라는 수치는 강력한 경고 신호이며, '생존자 편향' 논리가 설득력이 있다. 옹호자도 이를 인정했다.",
      "adjusted_strength": 0.80,
      "conditions": null
    },
    {
      "claim_id": "CRT-R1-04",
      "original_claim": "임대료가 매출 변동에 극히 취약한 구조를 만든다",
      "verdict": "채택",
      "reasoning": "하한 매출이 임대료에도 미달하는 구조는 객관적으로 고위험이다. 옹호자의 이면도로 대안은 별도 분석이 필요하며 현재로서는 해결되지 않은 핵심 쟁점이다.",
      "adjusted_strength": 0.85,
      "conditions": null
    },
    {
      "claim_id": "CRT-R1-05",
      "original_claim": "매출 추정 신뢰도가 의사결정에 부적절하다",
      "verdict": "채택",
      "reasoning": "양측 합의 사항이다. 신뢰도 0.55, 스프레드 68%는 사실상 추가 데이터 수집 없이 의사결정을 내릴 수 없는 수준이다.",
      "adjusted_strength": 0.82,
      "conditions": null
    },
    {
      "claim_id": "CRT-R1-06",
      "original_claim": "배달 플랫폼 경쟁이 누락되었다",
      "verdict": "부분채택",
      "reasoning": "데이터 공백 지적은 타당하나, 퓨전한식 프리미엄 다이닝의 경우 매장 방문 비중이 높아 배달 경쟁의 영향이 일반 음식점 대비 제한적일 수 있다.",
      "adjusted_strength": 0.50,
      "conditions": null
    },
    {
      "claim_id": "CRT-R1-07",
      "original_claim": "초기 투자비용과 회수 기간 리스크",
      "verdict": "채택",
      "reasoning": "초기 투자비 분석이 누락된 것은 명확한 데이터 공백이며, 최악 시나리오에서 2.4억원 손실 가능성은 의사결정자가 반드시 인지해야 할 정보이다.",
      "adjusted_strength": 0.72,
      "conditions": null
    },
    {
      "claim_id": "CRT-R2-01",
      "original_claim": "이면도로 이동은 입지 분석을 무효화한다",
      "verdict": "채택",
      "reasoning": "논리적으로 명확하다. 입지 조건 변경 시 기존 분석의 전제가 달라지므로, 재분석은 필수이다.",
      "adjusted_strength": 0.75,
      "conditions": null
    }
  ],
  "critic_acceptance_rate": 0.81,

  "revised_conclusions": {
    "overall_grade": "B-",
    "opportunity_score": 0.52,
    "risk_level": "HIGH",
    "revenue_estimate": {
      "low": 28000000,
      "mid": 42000000,
      "high": 65000000,
      "note": "신뢰도 부족으로 참고치로만 활용, 추가 데이터 수집 필수"
    },
    "go_no_go_recommendation": "조건부 보류 (CONDITIONAL HOLD)",
    "key_success_factors": [
      "강남역 유동인구의 절대적 규모 (보수적 추정에서도 양호)",
      "퓨전한식 트렌드의 현재 상승세",
      "2호선/신분당선 교차 환승의 광역 접근성"
    ],
    "key_risk_factors": [
      "하한 매출이 임대료에 미달하는 고정비 구조",
      "6개월 폐업률 18%의 혹독한 경쟁 환경",
      "매출 추정 신뢰도 0.55 (의사결정에 부적절한 수준)",
      "오픈 시점 트렌드 피크 경과 가능성",
      "초기 투자금 2억원 이상의 회수 기간 불확실"
    ]
  },

  "final_confidence": 0.52,
  "confidence_change": -0.13,

  "key_insights_from_debate": [
    "유동인구 규모는 긍정적이나, 통과 인구 비율 데이터 부재로 실제 전환 가능 인구를 확정할 수 없다",
    "매출 추정 신뢰도 0.55는 양측 모두 인정한 핵심 데이터 공백이며, 유사 업종 실매출 데이터 수집이 선행되어야 한다",
    "강남역 임대료 구조는 최대 리스크 요인이며, 입지 미세 조정(이면도로) 시 전체 분석 재수행이 필요하다",
    "퓨전한식은 단순 유행은 아니나 이미 경쟁 과열 초기 신호가 보이며, 오픈 시차 리스크를 관리해야 한다",
    "폐업률 18%는 차별화 전략 없는 진입의 위험성을 명확히 보여준다"
  ],

  "areas_needing_more_data": [
    "강남역 퓨전한식 유사 업종 3~5개의 실제 월 매출 데이터",
    "강남역 유동인구 중 통과 인구 vs 체류 인구 비율",
    "이면도로 후보지의 개별 입지 분석 (유동인구, 가시성, 임대료)",
    "강남역 퓨전한식 업체의 개별 폐업률 및 영업 기간",
    "초기 인테리어 및 설비 투자비용 상세 견적"
  ],

  "original_vs_revised": [
    {
      "metric_name": "overall_grade",
      "original_value": "B+",
      "revised_value": "B-",
      "change_reason": "매출 추정 신뢰도 문제, 임대료 구조 리스크, 경쟁 환경 재평가를 반영하여 1등급 하향"
    },
    {
      "metric_name": "opportunity_score",
      "original_value": 0.68,
      "revised_value": 0.52,
      "change_reason": "경쟁 차별화 주장 기각(-0.08), 매출 추정 근거 기각(-0.05), 전반적 불확실성 반영(-0.03)"
    },
    {
      "metric_name": "risk_level",
      "original_value": "MEDIUM",
      "revised_value": "HIGH",
      "change_reason": "하한 매출 < 임대료 구조, 18% 폐업률, 최대 2.4억원 손실 시나리오를 종합 반영"
    },
    {
      "metric_name": "confidence",
      "original_value": 0.65,
      "revised_value": 0.52,
      "change_reason": "데이터 공백 5건 확인(통과인구, 실매출, 개별폐업률, 이면도로입지, 투자비), 매출 추정 신뢰도 부적절 확인"
    },
    {
      "metric_name": "revenue_estimate_high",
      "original_value": 72000000,
      "revised_value": 65000000,
      "change_reason": "경쟁 과열 초기 신호, 트렌드 피크 리스크를 반영하여 상한 추정 보수적 조정"
    }
  ],

  "total_token_usage": {
    "input_tokens": 52000,
    "output_tokens": 18500
  },
  "total_latency_ms": 38200,
  "total_estimated_cost_usd": 0.34
}
```

### 9.7 최종 사용자 전달 요약

토론 결과는 사용자에게 다음과 같이 요약되어 전달된다:

```
📊 교차검증 결과 요약

[등급 조정] B+ → B- (1등급 하향)
[기회 점수] 0.68 → 0.52
[위험 수준] 중간 → 높음
[신뢰도] 0.65 → 0.52

💡 토론에서 도출된 핵심 인사이트:
1. 유동인구는 양호하나 실제 전환율 검증 필요
2. 임대료 구조가 최대 리스크 (하한 매출 < 임대료)
3. 매출 추정 데이터가 부족하여 추가 조사 권고
4. 퓨전한식 트렌드는 유효하나 경쟁 과열 초기 신호 감지
5. 최악의 경우 2.4억원 손실 가능성 인지 필요

📋 추가 조사 권고 항목:
- 유사 업종 실제 매출 데이터 (3~5개소)
- 이면도로 후보지 입지 재분석
- 초기 투자비용 상세 견적
```

---

## 부록 A: 에러 처리

### A.1 LLM 호출 실패 시

```python
async def handle_llm_failure(
    role: str,
    step: str,
    error: Exception,
    state: DebateState
) -> Dict:
    """LLM 호출 실패 시 처리"""
    if isinstance(error, TimeoutError):
        # 타임아웃: 1회 재시도 후 해당 라운드 건너뜀
        pass
    elif isinstance(error, RateLimitError):
        # 레이트 리밋: 지수 백오프 재시도
        pass
    else:
        # 기타 오류: 해당 라운드 건너뛰고 판결 진행
        pass

    # 어떤 경우든 이전 라운드 기록이 있으면 판결 가능
    if len(state["round_records"]) >= 2:
        return {"current_step": "judge", "errors": [str(error)]}
    else:
        # 라운드 1도 완료되지 않으면 토론 건너뛰기
        return {"current_step": "skip", "errors": [str(error)]}
```

### A.2 JSON 파싱 실패 시

LLM이 유효하지 않은 JSON을 반환한 경우, 1회 재시도 프롬프트를 전송한다:

```
이전 응답이 올바른 JSON 형식이 아닙니다. 반드시 지정된 스키마에 맞는 유효한 JSON으로 응답하십시오.
추가 설명이나 마크다운 없이 JSON만 출력하십시오.
```

재시도 후에도 실패 시 에러 처리 로직(A.1)을 따른다.

---

## 부록 B: 모니터링 및 로깅

### B.1 토론 로그 항목

모든 토론은 다음 항목을 로깅한다:

```python
@dataclass
class DebateLog:
    debate_id: str
    analysis_id: str
    trigger_reasons: List[str]
    rounds_conducted: int
    advocate_model: str
    critic_model: str
    judge_model: str
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    total_latency_ms: int
    grade_change: Optional[str]         # 예: "B+ → B-"
    confidence_change: float
    convergence_score: float
    errors: List[str]
    timestamp: datetime
```

### B.2 품질 추적 지표

- **토론 발동률**: 전체 분석 대비 토론이 발동된 비율 (목표: 30~50%)
- **평균 라운드 수**: 2.0~2.5 범위가 적정
- **등급 변경률**: 토론 후 등급이 변경된 비율 (목표: 60% 이상, 토론의 실효성 지표)
- **평균 비용**: 토론 건당 평균 비용 (목표: $0.30 이하)
- **평균 지연시간**: 토론 완료까지 소요 시간 (목표: 40초 이하)
