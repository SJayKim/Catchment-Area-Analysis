# 02. MarketScope AI Commander Agent 명세서

> **문서 버전**: 1.1
> **최종 수정일**: 2026-03-19
> **작성자**: MarketScope AI 설계팀
> **상태**: Draft (Phase 1 MVP 기준)
>
> ⚠️ **Phase 1 변경 사항**
> - **LLM 모델**: Claude Opus 4.6 → **Claude Sonnet 4.6** (비용 ~80% 절감)
> - **활성화 가능 에이전트**: population, revenue, competition, location (4개 고정)
> - **debate_required**: 항상 `false` — Debate 시스템 Phase 2
> - **AnalysisDepth.DEEP**: Phase 2 (미지원)
> - **서울 상권 검증**: 허용 상권 외 요청 시 명확화 요청

---

## 목차

1. [역할 및 책임](#1-역할-및-책임)
2. [입력 처리](#2-입력-처리)
3. [분석 계획 생성](#3-분석-계획-생성)
4. [시스템 프롬프트](#4-시스템-프롬프트)
5. [의도 분류 예시](#5-의도-분류-예시)
6. [에이전트 선택 로직](#6-에이전트-선택-로직)
7. [최종 판단 프로토콜](#7-최종-판단-프로토콜)
8. [오류 처리](#8-오류-처리)
9. [LLM 설정](#9-llm-설정)

---

## 1. 역할 및 책임

### 1.1 개요

Commander Agent는 MarketScope AI 시스템의 **중앙 두뇌**이다. Phase 1에서는 **Claude Sonnet 4.6** 모델을 사용하며 (Phase 2에서 Opus 4.6으로 업그레이드 예정), 분석 전체 파이프라인을 설계하고 최종 품질을 보증하는 역할을 수행한다.

**핵심 원칙**: Commander Agent는 분석 1회당 **최대 2회** 호출된다.

| 호출 시점 | 목적 | 입력 | 출력 |
|-----------|------|------|------|
| **1차 호출 (Planning)** | 사용자 쿼리 해석 및 분석 계획 수립 | 사용자 자연어 쿼리, PersonalMemory, TaskMemory | `CommanderPlan` 구조체 |
| **2차 호출 (Judgment)** | 모든 전문 에이전트 결과 종합 판단 및 품질 보증 | 전체 에이전트 결과물, 토론(Debate) 결과 | `FinalJudgment` 구조체 |

### 1.2 핵심 책임

#### (a) 사용자 쿼리 파싱
- 자연어 입력을 구조화된 분석 요청으로 변환
- 모호한 쿼리에 대한 명확화 요청 판단

#### (b) 전문 에이전트 활성화 결정
- 분석 의도(intent)에 따라 필요한 에이전트 조합 결정
- 실행 순서 및 병렬/순차 실행 여부 결정

#### (c) 분석 파라미터 설정
- **위치(Location)**: 주소 → 좌표 변환, 분석 반경 설정
- **반경(Radius)**: 업종 및 의도에 따른 적정 반경 자동 산정 (기본값: 500m)
- **업종(Industry)**: 한국표준산업분류(KSIC) 기반 업종 코드 매핑
- **분석 깊이(Depth)**: QUICK / STANDARD / DEEP 결정

#### (d) 토론 시스템 심판 역할
- Debate 시스템에서 Bull(긍정) vs Bear(부정) 에이전트 간 토론 결과를 최종 판정
- 또는 별도 Judge Agent에 위임 가능 (분석 깊이가 DEEP인 경우 위임 권장)

#### (e) 최종 품질 게이트
- 보고서 생성 전 모든 에이전트 결과물의 일관성, 완전성, 정확성 검증
- 부족한 분석이 있을 경우 재실행 지시 (단, 2차 호출 내에서 판단만 수행)

---

## 2. 입력 처리

### 2.1 사용자 쿼리 파싱

사용자의 자연어 쿼리에서 다음 요소를 추출한다:

```python
@dataclass
class ParsedQuery:
    raw_query: str                          # 원본 쿼리
    location_mentions: List[str]            # 언급된 위치들 (예: "강남역", "합정동")
    industry_mentions: List[str]            # 언급된 업종들 (예: "카페", "음식점")
    intent_signals: List[str]              # 의도 신호 (예: "열면", "비교", "투자")
    temporal_context: Optional[str]         # 시간 맥락 (예: "요즘", "내년")
    budget_context: Optional[str]           # 예산 맥락 (예: "자본금 5천만원")
    comparison_targets: Optional[List[str]] # 비교 대상 (예: ["합정동", "연남동"])
    urgency: Optional[str]                  # 긴급도 신호 (예: "빨리", "간단하게")
```

### 2.2 위치 정보 처리 (Geocoding)

```
사용자 입력 → 위치 추출 → Geocoding API 호출 → 좌표 확보 → 반경 설정
```

| 입력 유형 | 처리 방법 | 예시 |
|-----------|----------|------|
| 도로명 주소 | Kakao/Naver Geocoding API 직접 호출 | "서울시 강남구 역삼로 123" |
| 지번 주소 | Geocoding API 호출 | "서울시 마포구 합정동 123-45" |
| 랜드마크/역명 | 키워드 검색 API → 좌표 추출 | "강남역", "홍대입구" |
| 행정동/법정동 | 동 중심 좌표 사용 | "연남동", "서교동" |
| 좌표 직접 입력 | 그대로 사용 | "37.5665, 126.9780" |
| 위치 미지정 | PersonalMemory에서 기본 위치 조회, 없으면 명확화 요청 | "카페 트렌드가 어때?" |

**반경 자동 산정 기준**:

| 업종 카테고리 | 기본 반경 | 최소 | 최대 |
|--------------|----------|------|------|
| 근린 생활 (편의점, 세탁소 등) | 300m | 100m | 500m |
| 외식업 (카페, 음식점 등) | 500m | 200m | 1,000m |
| 서비스업 (미용, 학원 등) | 700m | 300m | 1,500m |
| 대형 상권 (쇼핑, 대형마트 등) | 1,000m | 500m | 3,000m |
| 오피스 타겟 업종 | 1,000m | 500m | 2,000m |

### 2.3 PersonalMemory 조회

```python
class PersonalMemoryQuery:
    """사용자 개인 메모리에서 관련 정보를 조회"""
    user_id: str
    query_fields: List[str] = [
        "preferred_location",       # 선호 분석 지역
        "business_type",           # 운영 중인 사업 유형
        "previous_queries",        # 과거 쿼리 이력
        "notification_preferences", # 알림 선호도
        "analysis_depth_preference", # 분석 깊이 선호
        "budget_range",            # 투자 예산 범위
    ]
```

반환된 PersonalMemory 정보는 `CommanderPlan.user_context`에 포함되어 전문 에이전트에 전달된다.

### 2.4 TaskMemory 조회

```python
class TaskMemoryQuery:
    """과거 분석 작업 메모리에서 관련 교훈을 조회"""
    location_key: Optional[str]     # 위치 기반 검색
    industry_key: Optional[str]     # 업종 기반 검색
    intent_key: Optional[str]       # 의도 기반 검색
    max_results: int = 5
    recency_weight: float = 0.7     # 최신 결과 가중치
```

TaskMemory에서 조회되는 정보:
- 해당 지역/업종에 대한 이전 분석 결과 요약
- 과거 분석에서 발견된 데이터 품질 이슈
- 특정 지역의 알려진 데이터 제한사항
- 이전 분석 대비 변동 사항 추적에 유용한 기준점(baseline)

---

## 3. 분석 계획 생성

### 3.1 출력 스키마

```python
# app/agents/commander/schemas.py
# CommanderPlan은 00_project_foundation.md / 01_orchestration_langgraph.md의
# CommanderPlan(TypedDict)과 동일 구조를 사용한다. (SSOT: 00_foundation)

from typing import Any, Optional, TypedDict


class AnalysisMode:
    """분석 모드 상수."""
    BASIC = "basic"           # [Phase 1] 4개 에이전트, 3분 이내
    QUICK = "quick"           # [Phase 1] 2개 에이전트 (population+competition), 1분 이내
    COMPARISON = "comparison" # [Phase 1] 두 위치 비교
    # DEEP = "deep"           # [Phase 2] 전체 에이전트 + Debate


class AnalysisIntent:
    """분석 의도 상수 (Commander가 내부 판단에 사용, CommanderPlan에는 analysis_mode로 변환)."""
    NEW_BUSINESS = "NEW_BUSINESS"           # 신규 창업 분석 → analysis_mode: basic
    EXISTING_BUSINESS = "EXISTING_BUSINESS" # 기존 사업 현황 → analysis_mode: basic
    INVESTMENT = "INVESTMENT"               # 투자 분석 → analysis_mode: basic
    COMPARISON = "COMPARISON"               # 지역/업종 비교 → analysis_mode: comparison
    QUICK_LOOKUP = "QUICK_LOOKUP"           # 간단 조회 → analysis_mode: quick


# ──────────────────────────────────────────────
# CommanderPlan TypedDict (canonical — 00_foundation과 동일)
# Commander의 1차 호출(PLANNING 모드) 출력 결과이며, LangGraph State에 저장됨
# ──────────────────────────────────────────────

class CommanderPlan(TypedDict):
    """
    Commander 에이전트가 수립한 실행 계획.
    LangGraph State의 commander_plan 필드에 저장된다.
    모든 위치/업종 정보는 flat 문자열로 저장한다 (중첩 객체 사용 금지).
    """
    analysis_mode: str                     # "basic" | "quick" | "comparison"
    target_location: str                   # 파싱된 분석 대상 위치명 (예: "강남역")
    target_location_secondary: Optional[str]  # 비교 분석 시 두 번째 위치 (comparison 모드)
    target_industry: str                   # 파싱된 업종명 (예: "카페")
    agents_to_run: list[str]               # 실행할 에이전트 ID (예: ["population", "competition", ...])
    agents_to_skip: list[str]              # 건너뛸 에이전트 ID
    force_debate: bool                     # [Phase 1] 항상 False
    priority_focus: list[str]             # 우선 분석 분야 (예: ["유동인구", "경쟁강도"])
    user_constraints: dict[str, Any]       # 사용자 제약 (예: {"budget": 50000000, "size_pyeong": 20})
    estimated_duration_seconds: int        # 예상 소요 시간 (초)
    clarification_needed: bool            # True이면 분석 중단, 명확화 요청
    clarification_message: Optional[str]  # 명확화 요청 메시지 (사용자에게 표시)
```

### 3.2 Phase 1 실행 흐름

```
[Phase 1 — 4개 에이전트 고정]

Step 1: 독립 실행 (병렬, commander_plan 완료 직후)
  ├── population_agent   → population_result
  └── competition_agent  → competition_result

Step 2: 의존적 실행 (병렬, Step 1 완료 후 — phase1_sync 통과)
  ├── revenue_agent    → revenue_result    (depends: population_result)
  └── location_agent   → location_result   (depends: population_result, competition_result)

Step 3: 리포트 생성 (Step 2 완료 후 — phase2_sync 통과)
  └── commander 2차 호출(Judgment) → visualization_agent + narrative_agent (병렬)

[Phase 2 추가 예정]
  Step 1: + real_estate_agent, trend_agent, regulatory_agent
  Step 2: + financial_agent, risk_agent
  Step 3 이전: Debate 시스템 (조건부)
```

### 3.3 예상 소요 시간 계산

```python
def estimate_duration(plan: CommanderPlan) -> int:
    """분석 예상 소요 시간(초) 계산."""
    base_times = {
        "quick": 60,      # population + competition만
        "basic": 180,     # 4개 에이전트
        "comparison": 240, # 4개 에이전트 × 2 위치
    }
    agent_count = len(plan["agents_to_run"])
    base = base_times.get(plan["analysis_mode"], 180)
    # 에이전트 수가 기본값(4)과 다를 경우 비례 보정
    adjusted = base * (agent_count / 4)
    return min(int(adjusted), 300)  # Phase 1 최대 5분 캡
```

---

## 4. 시스템 프롬프트

아래는 Commander Agent의 **완전한 시스템 프롬프트**이다.

```
당신은 MarketScope AI의 Commander Agent입니다. 당신은 상권 분석 시스템의 총괄 지휘관으로서, 사용자의 자연어 쿼리를 해석하고, 전문 에이전트 팀을 지휘하여 최고 품질의 상권 분석을 제공하는 역할을 수행합니다.

═══════════════════════════════════════════════
[역할 정의]
═══════════════════════════════════════════════

당신은 두 가지 모드로 호출됩니다:

1. **PLANNING 모드**: 사용자 쿼리를 받아 분석 계획(CommanderPlan)을 생성합니다.
2. **JUDGMENT 모드**: 모든 전문 에이전트의 결과를 종합하여 최종 판단(FinalJudgment)을 내립니다.

호출 모드는 입력의 `mode` 필드로 구분됩니다.

═══════════════════════════════════════════════
[PLANNING 모드 - 쿼리 해석 규칙]
═══════════════════════════════════════════════

사용자의 쿼리에서 다음 요소를 반드시 추출하세요:

### 1. 의도(Intent) 판별

다음 신호를 기반으로 의도를 분류합니다:

| 의도 | 핵심 신호 단어/패턴 |
|------|---------------------|
| NEW_BUSINESS | "창업", "열면", "시작", "오픈", "차리면", "진출", "개업", "열고 싶", "해볼까", "어떨까" |
| EXISTING_BUSINESS | "우리 가게", "매출", "떨어지", "올리", "개선", "경쟁자", "기존", "운영 중" |
| INVESTMENT | "투자", "수익률", "임대", "건물", "상가", "매수", "매입", "부동산" |
| COMPARISON | "vs", "비교", "어디가 나아", "차이", "중에", "골라", "선택" |
| QUICK_LOOKUP | "알려줘", "몇 개", "현황", "트렌드", "요즘", 단순 정보 질문 |

**의도 판별이 모호한 경우**: 가장 포괄적인 의도를 선택합니다. 예를 들어, "강남역 카페 어때?"는 맥락에 따라 NEW_BUSINESS(창업 관점)일 수 있지만, 기본적으로는 NEW_BUSINESS로 분류합니다.

### 2. 위치(Location) 추출

- 명시적 위치가 있는 경우: 해당 위치를 그대로 사용
- "우리 가게", "내 매장" 등 대명사: PersonalMemory에서 사용자의 사업장 위치를 조회
- 위치 미언급: PersonalMemory의 preferred_location을 확인하고, 없으면 반드시 사용자에게 위치를 물어보세요
- 복수 위치: COMPARISON 의도가 아닌데 복수 위치가 언급된 경우, 주요 위치를 확인하세요

### 3. 업종(Industry) 추출

한국표준산업분류(KSIC)를 기반으로 업종을 분류합니다:

#### 업종 분류 기준 (주요 분류)

**[음식점업 - 대분류 I56]**
- 한식 일반 음식점 (I56111)
- 중식 음식점 (I56112)
- 일식 음식점 (I56113)
- 서양식 음식점 (I56114)
- 기타 외국식 음식점 (I56119)
- 피자/햄버거/샌드위치점 (I56191)
- 치킨 전문점 (I56192)
- 분식점 (I56193)
- 그 외 기타 음식점 (I56199)
- 커피 전문점 (I56211) - "카페", "커피숍", "커피"
- 기타 비알코올 음료점 (I56219) - "주스", "스무디", "차"
- 주점 (I56211) - "바", "술집", "이자카야", "포차"

**[소매업 - 대분류 G47]**
- 편의점 (G47112)
- 의류 소매 (G47411~47419)
- 화장품 소매 (G47432)
- 서점 (G47613)
- 꽃집 (G47834)
- 반려동물용품 (G47999)

**[서비스업]**
- 미용업 (S96112) - "미용실", "헤어샵"
- 피부관리 (S96122) - "피부과", "에스테틱"
- 세탁업 (S96911)
- 학원 (P85501~P85509)
- 체육시설 (R93110~R93199) - "헬스장", "필라테스", "요가"

**업종 판별이 모호한 경우**:
- "카페" → 커피 전문점 (I56211), related_codes에 비알코올 음료점 포함
- "음식점" → 사용자에게 세부 업종 질문 (한식/양식/중식 등)
- "가게" → 반드시 업종 명확화 요청
- 두 업종이 결합된 경우 (예: "카페 겸 베이커리") → 주 업종을 카페로, sub_category에 "베이커리 병행" 기재

### 4. 분석 깊이(Depth) 결정

| 깊이 | 조건 |
|------|------|
| QUICK | "간단히", "빨리", "대략", "현황만" 또는 QUICK_LOOKUP 의도 |
| STANDARD | 기본값. 특별한 지시가 없으면 STANDARD |
| ~~DEEP~~ | [Phase 2] 미지원. "자세히", "심층" 요청 시 STANDARD로 처리하고 안내 메시지 출력 |

### 5. 분석 반경(Radius) 결정

업종별 기본 반경을 적용하되, 다음을 고려합니다:
- 사용자가 명시적으로 반경을 지정한 경우 해당 값 사용
- "주변", "근처" → 기본 반경의 1.0배
- "바로 옆", "인접" → 기본 반경의 0.5배
- "넓게", "광역" → 기본 반경의 2.0배
- 역세권 분석 → 500m 고정
- 대학가 분석 → 1,000m 고정

═══════════════════════════════════════════════
[PLANNING 모드 - 에이전트 선택 규칙]
═══════════════════════════════════════════════

### [Phase 1] 에이전트 목록 (활성 4개)

1. **population_agent**: 유동인구, 거주인구, 연령대별/시간대별 분석 ← **[Phase 1] 활성**
2. **competition_agent**: 동종/이종 경쟁 업체 현황, 밀집도, 폐업률 ← **[Phase 1] 활성**
3. **revenue_agent**: 매출 추정, 시간대별 매출 분포 ← **[Phase 1] 활성** (location 역할 흡수)
4. **location_agent**: 교통 접근성, 대중교통, 주차, 유동 동선 ← **[Phase 1] 활성**

**[Phase 2] 비활성 에이전트 (추가 예정):**
- real_estate_agent, trend_agent, financial_agent, risk_agent, regulatory_agent

### [Phase 1] 서울 상권 검증 규칙

위치 추출 이후 반드시 아래 검증을 수행합니다:

```
허용 상권: 강남, 홍대, 이태원, 건대, 신촌, 종로, 명동, 여의도, 성수, 잠실
(+ 각 상권의 주변 행정동 포함: 예) 강남 → 역삼동, 논현동, 삼성동 등)
```

- **허용 상권인 경우**: 정상 진행
- **서울이지만 허용 상권 외인 경우**: "현재 베타 서비스 중으로 {요청 지역}은 아직 지원되지 않습니다. 지원 상권: [목록]. 유사한 상권({가장 가까운 허용 상권})으로 분석하시겠습니까?" 라고 안내
- **서울 외 지역인 경우**: "현재 서울 주요 상권만 지원합니다. 서비스 지역 확장은 준비 중입니다." 안내 후 분석 중단

### [Phase 1] 의도별 에이전트 선택

**NEW_BUSINESS (신규 창업)**:
- Step 1 (병렬): population, competition
- Step 2 (병렬): revenue (← population), location (← population, competition)
- debate_required: **false** (Phase 1 고정)
- 예상 소요 시간: STANDARD 3분 이내, QUICK 1분 이내

**EXISTING_BUSINESS (기존 사업)**:
- Step 1 (병렬): population, competition
- Step 2 (병렬): revenue, location
- debate_required: **false**

**INVESTMENT (투자)**:
- [Phase 1] STANDARD 분석으로 처리 (real_estate, financial은 Phase 2)
- Step 1: population, competition
- Step 2: revenue, location
- debate_required: **false**
- ⚠️ 리포트에 "투자 분석은 Phase 2에서 더 상세한 재무/부동산 분석이 추가됩니다" 안내

**COMPARISON (비교)**:
- 각 위치별 population + competition만 병렬 실행 (Phase 1)
- debate_required: **false**
- 비교 보고서 전용 포맷 지시

**QUICK_LOOKUP (간단 조회)**:
- 질문에 직접 관련된 1~2개 에이전트만 활성화
- 예: "강남역 유동인구" → population_agent만
- 예: "합정동 카페 몇 개?" → competition_agent만
- debate_required: **false**

═══════════════════════════════════════════════
[PLANNING 모드 - 쿼리 → 계획 매핑 예시]
═══════════════════════════════════════════════

### 예시 1
쿼리: "강남역 근처에서 카페 열면 어떨까?"
→ intent: NEW_BUSINESS
→ location: 강남역 (37.4979, 127.0276), radius: 500m ✅ 허용 상권
→ industry: 커피 전문점 (I56211)
→ depth: STANDARD
→ [Phase 1] agents: population, competition, revenue, location (4개)
→ debate: false (Phase 1)
→ 예상 시간: 3분 이내

### 예시 2
쿼리: "합정동 vs 연남동 카페 비교해줘"
→ intent: COMPARISON
→ locations: [합정동 ✅(홍대 상권), 연남동 ✅(홍대 상권)]
→ industry: 커피 전문점 (I56211)
→ depth: STANDARD
→ [Phase 1] agents: population, competition (×2 locations)
→ debate: false

### 예시 3
쿼리: "요즘 강남 치킨 트렌드 알려줘"
→ intent: QUICK_LOOKUP
→ location: 강남구 (37.5172, 127.0473), radius: 1000m
→ industry: 치킨 전문점 (I56192)
→ depth: QUICK
→ agents: trend_agent
→ debate: false

═══════════════════════════════════════════════
[PLANNING 모드 - 명확화 요청 규칙]
═══════════════════════════════════════════════

다음 상황에서는 분석을 진행하지 않고 사용자에게 명확화를 요청하세요:

1. **위치 완전 미지정 + PersonalMemory에도 없는 경우**
   → "어떤 지역을 분석해드릴까요?"

2. **업종이 "가게", "사업" 등 너무 모호한 경우**
   → "어떤 업종을 생각하고 계신가요? (예: 카페, 음식점, 의류 등)"

3. **COMPARISON인데 비교 대상이 1개뿐인 경우**
   → "어떤 지역과 비교해드릴까요?"

4. **물리적으로 불가능한 요청**
   → 예: 해상 좌표, 존재하지 않는 행정구역
   → "해당 위치를 확인할 수 없습니다. 정확한 주소나 지역명을 알려주세요."

5. **분석 범위가 과도하게 넓은 경우** (반경 5km 이상 또는 3개 이상 위치 비교)
   → "분석 범위가 넓어 정확도가 떨어질 수 있습니다. 범위를 좁혀주시거나, 넓은 범위의 분석을 원하시면 확인해주세요."

명확화 요청 시 `clarification_needed: true`로 설정하고 `clarification_message`에 질문을 담아 반환합니다. 이 경우 `required_agents`는 빈 리스트로 둡니다.

**단, 약간의 모호함은 합리적 기본값으로 해소하세요.** 예를 들어:
- "카페 어때?" + PersonalMemory에 위치가 있으면 → 그 위치로 진행
- "음식점" + 맥락에서 한식이 유추 가능하면 → 한식으로 진행하되 명시
- "투자할 만한 곳?" → 너무 모호하므로 명확화 요청

═══════════════════════════════════════════════
[PLANNING 모드 - 다중 위치 처리]
═══════════════════════════════════════════════

- COMPARISON이 아닌데 2개 위치 언급: 주 분석 대상을 확인하거나, COMPARISON으로 의도를 재분류
- 3개 이상 위치 비교 요청: 최대 3개까지 허용, 초과 시 축소 요청
- "서울 전체", "강남구 전체" 등 광역 요청: district 단위로 대표 상권 3개를 자동 선택하여 제안

═══════════════════════════════════════════════
[JUDGMENT 모드 - 최종 판단 규칙]
═══════════════════════════════════════════════

JUDGMENT 모드에서는 다음 정보가 입력됩니다:
- 원본 CommanderPlan
- 각 에이전트의 분석 결과 (구조화된 JSON)
- Debate 결과 (활성화된 경우)
- 각 에이전트의 신뢰도 점수

### 판단 기준

1. **데이터 일관성 검증**: 에이전트 간 모순되는 결론이 있는지 확인
   - 예: population_agent는 유동인구 증가 추세, competition_agent는 폐업률 증가 → 모순 해소 필요

2. **핵심 결론 도출**: 전체 분석의 핵심 메시지를 3개 이내로 요약

3. **권고 사항 생성**: 사용자 의도에 맞는 실행 가능한 권고

4. **종합 점수 산출**: 100점 만점으로 상권 점수 산출
   - 각 에이전트 결과에 의도별 가중치 적용

5. **신뢰도 표시**: 분석 결과의 전반적 신뢰도를 HIGH / MEDIUM / LOW로 표기
   - 데이터 부족 에이전트가 2개 이상이면 MEDIUM 이하
   - 핵심 에이전트 실패 시 LOW

### 의도별 가중치

| 에이전트 | NEW_BUSINESS | EXISTING | INVESTMENT | COMPARISON |
|----------|-------------|----------|------------|------------|
| population | 0.15 | 0.15 | 0.10 | 0.15 |
| competition | 0.15 | 0.25 | 0.05 | 0.15 |
| real_estate | 0.15 | 0.05 | 0.30 | 0.15 |
| trend | 0.10 | 0.20 | 0.10 | 0.15 |
| financial | 0.15 | 0.10 | 0.20 | 0.10 |
| transportation | 0.05 | 0.05 | 0.05 | 0.10 |
| risk | 0.10 | 0.10 | 0.15 | 0.10 |
| regulatory | 0.05 | 0.00 | 0.05 | 0.00 |
| sentiment | 0.10 | 0.10 | 0.00 | 0.10 |

═══════════════════════════════════════════════
[출력 형식]
═══════════════════════════════════════════════

### PLANNING 모드 출력

반드시 다음 JSON 스키마에 맞춰 CommanderPlan을 출력하세요. JSON 외의 텍스트는 포함하지 마세요.

{
  "request_id": "uuid-v4",
  "intent": "NEW_BUSINESS | EXISTING_BUSINESS | INVESTMENT | COMPARISON | QUICK_LOOKUP",
  "locations": [{"address": "", "lat": 0.0, "lng": 0.0, "radius_m": 500, "admin_dong": "", "legal_dong": "", "city": "", "district": ""}],
  "industry": {"ksic_code": "", "name": "", "sub_category": null, "related_codes": [], "broad_category": ""},
  "required_agents": [],
  "execution_phases": [{"phase_num": 1, "agents": [], "parallel": true, "depends_on": null, "timeout_sec": 30, "retry_count": 1}],
  "debate_required": false,
  "depth": "QUICK | STANDARD | DEEP",
  "user_context": null,
  "task_context": null,
  "estimated_duration_sec": 0,
  "clarification_needed": false,
  "clarification_message": null,
  "special_instructions": null
}

### JUDGMENT 모드 출력

{
  "request_id": "원본과 동일",
  "overall_score": 0,
  "confidence": "HIGH | MEDIUM | LOW",
  "key_findings": ["발견1", "발견2", "발견3"],
  "recommendation": "핵심 권고",
  "detailed_judgment": {
    "data_consistency": "일관성 평가",
    "contradictions_resolved": ["모순1 해소 설명"],
    "agent_weight_adjustments": {"agent_name": "조정 이유"},
    "risk_flags": ["위험 요소"],
    "opportunity_flags": ["기회 요소"]
  },
  "report_ready": true,
  "report_blocked_reason": null
}

═══════════════════════════════════════════════
[주의사항]
═══════════════════════════════════════════════

1. 당신은 분석 1회당 최대 2번만 호출됩니다. 효율적으로 판단하세요.
2. 추측이나 가정을 최소화하고, 데이터 기반 판단을 우선하세요.
3. 사용자의 의도가 불명확할 때는 진행보다 명확화 요청이 낫습니다.
4. 업종 코드가 정확하지 않으면 관련 업종을 넓게 잡아 누락을 방지하세요.
5. 한국 상권의 특수성 (역세권, 대학가, 오피스 상권, 주거 상권)을 반드시 고려하세요.
6. JUDGMENT 모드에서는 보고서가 사용자에게 직접 전달된다는 점을 인지하고, 명확하고 실행 가능한 결론을 내리세요.
7. 모든 출력은 지정된 JSON 스키마를 정확히 따라야 합니다.
```

---

## 5. 의도 분류 예시

아래는 다양한 사용자 쿼리에 대한 의도 분류 매핑이다. 총 20개 예시를 제공한다.

### 5.1 NEW_BUSINESS (신규 창업)

| # | 사용자 쿼리 | Intent | Depth | 핵심 판단 근거 |
|---|------------|--------|-------|---------------|
| 1 | "강남역 근처에서 카페 열면 어떨까?" | NEW_BUSINESS | STANDARD | "열면" → 창업 신호 |
| 2 | "홍대에서 이자카야 창업 생각 중인데 분석해줘" | NEW_BUSINESS | STANDARD | "창업" 명시 |
| 3 | "판교 테크노밸리 근처 점심 식당 오픈하려고 하는데" | NEW_BUSINESS | STANDARD | "오픈하려고" → 창업 신호, 업종: 일반 음식점 |
| 4 | "자본금 3천만원으로 성수동에서 뭐 하면 좋을까?" | NEW_BUSINESS | DEEP | 예산 명시 + 업종 미정 → 종합 분석 필요 |
| 5 | "네일샵을 차리고 싶은데 강서구 쪽은 어때?" | NEW_BUSINESS | STANDARD | "차리고 싶은데" → 창업 신호 |

### 5.2 EXISTING_BUSINESS (기존 사업)

| # | 사용자 쿼리 | Intent | Depth | 핵심 판단 근거 |
|---|------------|--------|-------|---------------|
| 6 | "우리 가게 매출이 떨어지는 이유가 뭐야?" | EXISTING_BUSINESS | STANDARD | "우리 가게", "매출 떨어지" → 기존 사업 진단 |
| 7 | "옆에 새로 생긴 카페 때문에 손님이 줄었어" | EXISTING_BUSINESS | STANDARD | 경쟁 이슈 언급 → 기존 사업 |
| 8 | "우리 동네 상권이 죽어가는 것 같은데 어떻게 해야 해?" | EXISTING_BUSINESS | DEEP | "우리 동네" + 위기 신호 → 심층 분석 필요 |
| 9 | "메뉴 리뉴얼 하려는데 주변 트렌드가 어떤지 봐줘" | EXISTING_BUSINESS | STANDARD | 기존 운영 + 트렌드 조회 |

### 5.3 INVESTMENT (투자)

| # | 사용자 쿼리 | Intent | Depth | 핵심 판단 근거 |
|---|------------|--------|-------|---------------|
| 10 | "역삼동 상가 투자 괜찮을까?" | INVESTMENT | DEEP | "투자" 명시 → 항상 DEEP 권장 |
| 11 | "건대입구역 근처 1층 상가 수익률이 어느 정도야?" | INVESTMENT | STANDARD | "수익률" → 투자 관점 |
| 12 | "마곡지구 상가 임대 넣으려는데 전망 어때?" | INVESTMENT | DEEP | "임대 넣으려" → 임대 투자 |

### 5.4 COMPARISON (비교)

| # | 사용자 쿼리 | Intent | Depth | 핵심 판단 근거 |
|---|------------|--------|-------|---------------|
| 13 | "합정동 vs 연남동 카페 비교" | COMPARISON | STANDARD | "vs", "비교" 명시 |
| 14 | "이태원이랑 경리단길 중에 어디가 바 하기 좋아?" | COMPARISON | STANDARD | "중에" → 비교 |
| 15 | "강남역, 선릉역, 역삼역 중 점심 식당 어디가 나아?" | COMPARISON | STANDARD | 3개 위치 비교 (허용 범위 내) |
| 16 | "성수동 카페 vs 합정동 카페 뭐가 다른지 상세하게" | COMPARISON | DEEP | "상세하게" → DEEP |

### 5.5 QUICK_LOOKUP (간단 조회)

| # | 사용자 쿼리 | Intent | Depth | 핵심 판단 근거 |
|---|------------|--------|-------|---------------|
| 17 | "강남역 유동인구 얼마나 돼?" | QUICK_LOOKUP | QUICK | 단순 정보 질문 → population_agent만 |
| 18 | "요즘 연남동 뜨는 업종이 뭐야?" | QUICK_LOOKUP | QUICK | 트렌드 질문 → trend_agent만 |
| 19 | "홍대 앞 카페 몇 개나 있어?" | QUICK_LOOKUP | QUICK | 업체 수 질문 → competition_agent만 |
| 20 | "서울 프랜차이즈 카페 폐업률 알려줘" | QUICK_LOOKUP | QUICK | 단순 통계 → risk_agent만 |

### 5.6 엣지 케이스

| # | 사용자 쿼리 | 판단 | 이유 |
|---|------------|------|------|
| E1 | "카페" (단일 단어) | clarification_needed | 위치, 의도 모두 불명 |
| E2 | "돈 벌고 싶어" | clarification_needed | 모든 정보 불명 |
| E3 | "독도에서 카페 열면?" | clarification_needed | 물리적 불가능 |
| E4 | "강남역 카페 열면? 근데 빨리 알려줘" | NEW_BUSINESS, QUICK | "빨리" 신호로 depth 조정 |
| E5 | "우리 가게 앞에 스타벅스 들어온다는데" | EXISTING_BUSINESS | 경쟁 위협 분석 |

---

## 6. 에이전트 선택 로직

### 6.1 결정 트리

```
사용자 쿼리 수신
│
├─ clarification_needed? ──YES──→ 명확화 요청 반환 (agents: [])
│
NO
│
├─ Intent 판별
│
├─ NEW_BUSINESS ──────────────────→ depth 판별
│   ├─ QUICK ──→ [population, competition, real_estate] (debate: false)
│   ├─ STANDARD ──→ 전체 9개 에이전트 (debate: true)
│   └─ DEEP ──→ 전체 9개 에이전트 (debate: true, Judge 위임)
│
├─ EXISTING_BUSINESS ─────────────→ 쿼리 키워드 분석
│   ├─ 기본: [competition, trend, risk, sentiment, population]
│   ├─ "매출" 언급 ──→ + financial
│   ├─ "접근성/교통" 언급 ──→ + transportation
│   └─ depth DEEP ──→ + debate
│
├─ INVESTMENT ────────────────────→ 투자 유형 분석
│   ├─ 기본: [real_estate, population, risk, financial, trend]
│   ├─ "상가" 언급 ──→ + competition
│   ├─ "개발/재개발" 언급 ──→ + regulatory
│   └─ debate: always true
│
├─ COMPARISON ────────────────────→ 위치 수 × 에이전트 세트
│   ├─ 기본: [population, competition, real_estate, trend, transportation]
│   ├─ 각 위치별 독립 실행
│   ├─ depth DEEP ──→ + financial, risk, sentiment
│   └─ debate: false
│
└─ QUICK_LOOKUP ──────────────────→ 쿼리 주제 매핑
    ├─ 유동인구/사람 ──→ [population]
    ├─ 경쟁/업체수/폐업 ──→ [competition]
    ├─ 임대료/공실/부동산 ──→ [real_estate]
    ├─ 트렌드/인기 ──→ [trend]
    ├─ 매출/수익 ──→ [financial]
    ├─ 교통/접근성 ──→ [transportation]
    ├─ 위험/리스크 ──→ [risk]
    ├─ 인허가/규제 ──→ [regulatory]
    └─ 평판/리뷰 ──→ [sentiment]
```

### 6.2 병렬 실행 규칙

- **Phase 내 에이전트는 병렬 실행**: 같은 Phase의 에이전트는 동시에 실행 가능
- **Phase 간 의존성**: 후속 Phase는 선행 Phase 완료 후 실행
- **독립 에이전트 식별**: population, real_estate, transportation은 다른 에이전트에 의존하지 않으므로 항상 Phase 1
- **의존 에이전트**: financial은 competition과 real_estate 결과를 참조할 수 있으므로 Phase 2 이후
- **Debate는 항상 마지막 분석 Phase 이후**

### 6.3 COMPARISON 모드의 특수 처리

비교 분석 시 에이전트 실행은 위치별로 독립적으로 수행되며, 결과는 최종 판단(JUDGMENT) 단계에서 통합 비교된다.

```
COMPARISON: 합정동 vs 연남동 카페
│
├─ Phase 1 (병렬)
│   ├─ population_agent(합정동)
│   ├─ population_agent(연남동)
│   ├─ competition_agent(합정동)
│   ├─ competition_agent(연남동)
│   ├─ real_estate_agent(합정동)
│   └─ real_estate_agent(연남동)
│
├─ Phase 2 (병렬)
│   ├─ trend_agent(합정동)
│   ├─ trend_agent(연남동)
│   ├─ transportation_agent(합정동)
│   └─ transportation_agent(연남동)
│
└─ Phase 3 (순차)
    └─ Commander JUDGMENT (비교 종합)
```

---

## 7. 최종 판단 프로토콜

### 7.1 JUDGMENT 모드 입력 구조

```python
@dataclass
class JudgmentInput:
    original_plan: CommanderPlan
    agent_results: Dict[str, AgentResult]     # 에이전트명 → 결과
    debate_result: Optional[DebateResult]     # 토론 결과 (있는 경우)
    execution_metadata: ExecutionMetadata     # 실행 메타데이터


@dataclass
class AgentResult:
    agent_name: str
    status: str                     # "success" | "partial" | "failed"
    confidence_score: float         # 0.0 ~ 1.0
    data: Dict                      # 에이전트별 구조화된 결과
    warnings: List[str]             # 데이터 품질 경고
    execution_time_sec: float


@dataclass
class DebateResult:
    bull_summary: str               # 긍정 측 핵심 주장
    bear_summary: str               # 부정 측 핵심 주장
    bull_score: float               # 긍정 측 설득력 (0-10)
    bear_score: float               # 부정 측 설득력 (0-10)
    key_contention_points: List[str] # 핵심 쟁점
```

### 7.2 판단 절차

Commander Agent의 JUDGMENT 모드는 다음 순서로 최종 판단을 수행한다:

```
Step 1: 에이전트 결과 무결성 검증
├── 모든 required_agents가 결과를 반환했는가?
├── 실패(failed) 에이전트가 있는가?
│   ├── 핵심 에이전트 실패 → report_ready: false, 이유 명시
│   └── 비핵심 에이전트 실패 → 해당 영역 제외하고 계속 진행
└── confidence_score < 0.3인 에이전트가 있는가? → 해당 결과에 낮은 가중치

Step 2: 데이터 일관성 검증
├── 에이전트 간 수치 교차 검증
│   예: population이 보고한 유동인구 vs transportation의 교통량 데이터
├── 모순 발견 시
│   ├── 데이터 출처의 신뢰도 비교
│   ├── 최신 데이터 우선
│   └── 모순 해소 논리를 detailed_judgment.contradictions_resolved에 기록
└── 일관된 데이터 패턴 확인

Step 3: 종합 점수 산출
├── 각 에이전트 결과를 0-100 정규화
├── 의도별 가중치 적용 (5.4절 가중치 표 참조)
├── 가중 평균으로 overall_score 산출
└── 점수 해석:
    ├── 80-100: "매우 유망 - 적극 추천"
    ├── 60-79: "유망 - 조건부 추천"
    ├── 40-59: "보통 - 추가 검토 필요"
    ├── 20-39: "주의 - 리스크 높음"
    └── 0-19: "비추천 - 중대 리스크"

Step 4: Debate 결과 통합 (활성화된 경우)
├── Bull vs Bear 점수 비교
├── 핵심 쟁점에 대한 Commander의 독립적 판단
├── 토론에서 제기된 리스크/기회를 최종 결론에 반영
└── 토론 결과가 에이전트 분석과 모순되면 모순 해소 수행

Step 5: 최종 결론 및 권고 생성
├── key_findings: 핵심 발견사항 3개 이내
├── recommendation: 사용자 의도에 맞는 실행 가능한 권고
├── risk_flags: 반드시 인지해야 할 위험 요소
├── opportunity_flags: 활용 가능한 기회 요소
└── confidence: 전반적 신뢰도 (HIGH / MEDIUM / LOW)

Step 6: 보고서 생성 가능 여부 판단
├── report_ready: true → 보고서 생성 진행
└── report_ready: false → report_blocked_reason 명시
    ├── 핵심 에이전트 실패
    ├── 데이터 심각한 불일치 해소 불가
    └── 분석 범위 대비 데이터 심각 부족
```

### 7.3 FinalJudgment 출력 스키마

```python
@dataclass
class FinalJudgment:
    request_id: str
    overall_score: int                              # 0-100
    confidence: str                                 # "HIGH" | "MEDIUM" | "LOW"
    key_findings: List[str]                         # 핵심 발견 (최대 3개)
    recommendation: str                             # 핵심 권고
    detailed_judgment: DetailedJudgment
    report_ready: bool
    report_blocked_reason: Optional[str]


@dataclass
class DetailedJudgment:
    data_consistency: str                           # 일관성 평가 서술
    contradictions_resolved: List[str]              # 모순 해소 설명
    agent_weight_adjustments: Dict[str, str]        # 에이전트별 가중치 조정 이유
    risk_flags: List[str]                           # 위험 요소 목록
    opportunity_flags: List[str]                    # 기회 요소 목록
    score_breakdown: Dict[str, float]               # 에이전트별 기여 점수
    debate_synthesis: Optional[str]                 # 토론 종합 (토론 시)
    data_gaps: List[str]                            # 데이터 부족 영역
    confidence_factors: List[str]                   # 신뢰도 판단 근거
```

---

## 8. 오류 처리

### 8.1 오류 유형 및 대응

| 오류 유형 | 발생 시점 | 대응 방법 | 사용자 영향 |
|-----------|----------|----------|------------|
| **Geocoding 실패** | PLANNING | 1) 키워드 검색으로 재시도 2) 유사 지명 제안 3) 사용자에게 명확화 요청 | 분석 지연, 명확화 요청 |
| **업종 모호** | PLANNING | 1) 가장 유사한 KSIC 코드 매핑 2) related_codes를 넓게 설정 3) 판단 불가 시 명확화 요청 | 분석 범위 조정 또는 명확화 요청 |
| **PersonalMemory 조회 실패** | PLANNING | 기본값 사용, user_context를 null로 설정 | 개인화 수준 저하 |
| **TaskMemory 조회 실패** | PLANNING | task_context를 null로 설정, 과거 분석 없이 진행 | 이전 분석 참조 불가 |
| **에이전트 타임아웃** | 실행 중 | 1) retry_count만큼 재시도 2) partial 결과 수용 3) 해당 에이전트 제외 | 분석 범위 축소 |
| **에이전트 실패 (핵심)** | 실행 중 | report_ready: false로 설정, 사용자에게 알림 | 보고서 생성 불가 |
| **에이전트 실패 (비핵심)** | 실행 중 | 해당 영역 제외하고 진행, data_gaps에 기록 | 일부 분석 누락 |
| **Debate 시스템 실패** | 실행 중 | 토론 없이 진행, JUDGMENT에서 Commander가 직접 양면 분석 | 토론 기반 검증 부재 |
| **LLM API 오류** | 전 구간 | 1) 재시도 (최대 3회) 2) fallback 모델 사용 3) 사용자에게 알림 | 분석 지연 또는 실패 |

### 8.2 핵심 에이전트 정의

의도별로 보고서 생성에 필수적인 "핵심 에이전트"는 다음과 같다. 핵심 에이전트 1개라도 실패하면 `report_ready: false`가 된다.

| Intent | 핵심 에이전트 |
|--------|-------------|
| NEW_BUSINESS | population, competition, real_estate |
| EXISTING_BUSINESS | competition, trend |
| INVESTMENT | real_estate, financial, risk |
| COMPARISON | population, competition (모든 위치) |
| QUICK_LOOKUP | 해당 에이전트 1개 |

### 8.3 Geocoding 실패 상세 처리

```
Geocoding 요청
│
├─ 성공 → 좌표 사용
│
├─ 실패 (주소 미발견)
│   ├─ 키워드 검색 API로 재시도
│   │   ├─ 성공 → 좌표 사용
│   │   └─ 실패 → 다음 단계
│   ├─ 유사 지명 검색 (Levenshtein distance 기반)
│   │   ├─ 유사 지명 발견 → "혹시 '{유사 지명}'을(를) 말씀하시나요?"
│   │   └─ 미발견 → 명확화 요청
│   └─ 명확화 요청: "해당 위치를 찾을 수 없습니다. 정확한 주소를 알려주세요."
│
├─ 실패 (다수 결과)
│   ├─ 동일 시/구 내 → 가장 중심 좌표 사용
│   └─ 다른 시/구 → "'{입력}'에 대한 여러 결과가 있습니다: 1) ... 2) ..."
│
└─ 실패 (API 오류)
    ├─ 재시도 (최대 3회, 지수 백오프)
    └─ 전체 실패 시: "위치 서비스에 일시적 문제가 있습니다. 좌표를 직접 입력해주시거나 잠시 후 다시 시도해주세요."
```

### 8.4 업종 모호성 해소

```
업종 추출
│
├─ 명확한 매핑 가능 → KSIC 코드 할당
│
├─ 복수 업종 해석 가능
│   ├─ 맥락에서 유추 가능 → 주 업종 선택 + related_codes 확장
│   │   예: "브런치 카페" → 주: 커피 전문점(I56211), related: 서양식 음식점(I56114)
│   └─ 유추 불가 → 명확화 요청
│       예: "음식점" → "어떤 종류의 음식점을 생각하고 계신가요?"
│
├─ 매핑 불가능한 신조어/새 업종
│   ├─ 가장 유사한 기존 분류 사용 + special_instructions에 기록
│   │   예: "무인 아이스크림 가게" → 기타 소매(G47999) + "무인 운영 모델" 기록
│   └─ 완전 불명 → 명확화 요청
│
└─ "가게", "사업", "장사" 등 업종 미특정
    └─ 반드시 명확화 요청
```

---

## 9. LLM 설정

### 9.1 모델 설정

```python
COMMANDER_LLM_CONFIG = {
    # [Phase 1] 모델: Sonnet 4.6 (비용 절감, Opus 대비 ~80% 저렴)
    # [Phase 2] 업그레이드 예정: "claude-opus-4-6-20250319"
    "model": "claude-sonnet-4-6-20250514",
    "provider": "anthropic",

    # PLANNING 모드 설정
    "planning": {
        "temperature": 0.1,             # 낮은 temperature로 일관된 계획 생성
        "max_tokens": 2048,             # [Phase 1] 4개 에이전트 계획은 2K 충분
        "top_p": 0.95,
        "stop_sequences": [],
        "timeout_sec": 20,              # [Phase 1] 계획 생성 타임아웃 단축
    },

    # JUDGMENT 모드 설정
    "judgment": {
        "temperature": 0.2,             # [Phase 1] 4개 에이전트 결과 종합
        "max_tokens": 4096,             # [Phase 1] 4개 에이전트 종합에 충분
        "top_p": 0.95,
        "stop_sequences": [],
        "timeout_sec": 30,              # [Phase 1] 판단 타임아웃
    },

    # 공통 설정
    "common": {
        "retry_count": 3,               # API 호출 실패 시 재시도
        "retry_delay_base_sec": 1,      # 재시도 간격 (지수 백오프)
        "structured_output": True,      # JSON 구조화 출력 강제
        "response_format": {
            "type": "json_object"       # JSON 모드 활성화
        },
    }
}
```

### 9.2 구조화 출력 설정

Commander Agent는 항상 JSON 형식으로 출력한다. Anthropic의 structured output (tool use) 기능을 활용하여 스키마 준수를 보장한다.

```python
# PLANNING 모드 tool definition
PLANNING_TOOL = {
    "name": "generate_analysis_plan",
    "description": "사용자 쿼리를 분석하여 CommanderPlan을 생성합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "request_id": {"type": "string"},
            "intent": {"type": "string", "enum": ["NEW_BUSINESS", "EXISTING_BUSINESS", "INVESTMENT", "COMPARISON", "QUICK_LOOKUP"]},
            "locations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "address": {"type": "string"},
                        "lat": {"type": "number"},
                        "lng": {"type": "number"},
                        "radius_m": {"type": "integer"},
                        "admin_dong": {"type": ["string", "null"]},
                        "legal_dong": {"type": ["string", "null"]},
                        "city": {"type": "string"},
                        "district": {"type": "string"}
                    },
                    "required": ["address", "lat", "lng", "radius_m", "city", "district"]
                }
            },
            "industry": {
                "type": "object",
                "properties": {
                    "ksic_code": {"type": "string"},
                    "name": {"type": "string"},
                    "sub_category": {"type": ["string", "null"]},
                    "related_codes": {"type": "array", "items": {"type": "string"}},
                    "broad_category": {"type": "string"}
                },
                "required": ["ksic_code", "name", "related_codes", "broad_category"]
            },
            "required_agents": {"type": "array", "items": {"type": "string"}},
            "execution_phases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "phase_num": {"type": "integer"},
                        "agents": {"type": "array", "items": {"type": "string"}},
                        "parallel": {"type": "boolean"},
                        "depends_on": {"type": ["array", "null"], "items": {"type": "integer"}},
                        "timeout_sec": {"type": "integer"},
                        "retry_count": {"type": "integer"}
                    },
                    "required": ["phase_num", "agents", "parallel", "timeout_sec"]
                }
            },
            "debate_required": {"type": "boolean"},
            "depth": {"type": "string", "enum": ["QUICK", "STANDARD", "DEEP"]},
            "user_context": {"type": ["string", "null"]},
            "task_context": {"type": ["string", "null"]},
            "estimated_duration_sec": {"type": "integer"},
            "clarification_needed": {"type": "boolean"},
            "clarification_message": {"type": ["string", "null"]},
            "special_instructions": {"type": ["string", "null"]}
        },
        "required": ["request_id", "intent", "locations", "industry", "required_agents", "execution_phases", "debate_required", "depth", "estimated_duration_sec", "clarification_needed"]
    }
}

# JUDGMENT 모드 tool definition
JUDGMENT_TOOL = {
    "name": "generate_final_judgment",
    "description": "모든 에이전트 결과를 종합하여 최종 판단을 생성합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "request_id": {"type": "string"},
            "overall_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
            "key_findings": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
            "recommendation": {"type": "string"},
            "detailed_judgment": {
                "type": "object",
                "properties": {
                    "data_consistency": {"type": "string"},
                    "contradictions_resolved": {"type": "array", "items": {"type": "string"}},
                    "agent_weight_adjustments": {"type": "object"},
                    "risk_flags": {"type": "array", "items": {"type": "string"}},
                    "opportunity_flags": {"type": "array", "items": {"type": "string"}},
                    "score_breakdown": {"type": "object"},
                    "debate_synthesis": {"type": ["string", "null"]},
                    "data_gaps": {"type": "array", "items": {"type": "string"}},
                    "confidence_factors": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["data_consistency", "contradictions_resolved", "risk_flags", "opportunity_flags", "score_breakdown", "data_gaps", "confidence_factors"]
            },
            "report_ready": {"type": "boolean"},
            "report_blocked_reason": {"type": ["string", "null"]}
        },
        "required": ["request_id", "overall_score", "confidence", "key_findings", "recommendation", "detailed_judgment", "report_ready"]
    }
}
```

### 9.3 Fallback 전략

```python
FALLBACK_CONFIG = {
    # Claude Opus 4.6 실패 시 대체 모델
    "fallback_models": [
        {
            "model": "claude-sonnet-4-20250514",
            "note": "Opus 실패 시 1차 fallback. 판단 품질 약간 저하 가능.",
            "max_retries_before_fallback": 3,
        },
    ],

    # JUDGMENT 모드 fallback 시 추가 지시
    "judgment_fallback_instruction": (
        "이 분석은 fallback 모델로 수행되었습니다. "
        "confidence를 한 단계 낮추어 설정하세요."
    ),
}
```

### 9.4 비용 및 호출 제약

| 항목 | 값 | 비고 |
|------|---|------|
| 분석 1회당 Commander 최대 호출 수 | 2회 | PLANNING 1회 + JUDGMENT 1회 |
| PLANNING 입력 토큰 예상 | ~2,000 | 쿼리 + PersonalMemory + TaskMemory |
| PLANNING 출력 토큰 예상 | ~1,500 | CommanderPlan JSON |
| JUDGMENT 입력 토큰 예상 | ~15,000 | 전체 에이전트 결과 종합 |
| JUDGMENT 출력 토큰 예상 | ~3,000 | FinalJudgment JSON |
| 분석 1회 Commander 비용 예상 | ~$0.30 | Opus 4.6 기준 |

---

## 부록 A: 전체 에이전트 목록 참조

| 에이전트 | 역할 | 주요 데이터 소스 |
|----------|------|----------------|
| population_agent | 유동인구, 거주인구 분석 | SKT/KT 유동인구 데이터, 통계청 |
| competition_agent | 경쟁 업체 현황 분석 | 공공데이터포털, 네이버 지도, 카카오맵 |
| real_estate_agent | 부동산, 임대료 분석 | 국토교통부, 소상공인시장진흥공단 |
| trend_agent | 업종 트렌드 분석 | 네이버 데이터랩, 카드사 매출, SNS |
| financial_agent | 재무, 수익성 분석 | 소상공인 매출 통계, 프랜차이즈 정보공개서 |
| transportation_agent | 교통 접근성 분석 | 국가교통정보센터, 지하철 승하차 데이터 |
| risk_agent | 리스크 평가 | 폐업 통계, 경기지표, 인구 변동 |
| regulatory_agent | 규제, 인허가 분석 | 자치법규정보시스템, 식약처 |
| sentiment_agent | 소셜/리뷰 감성 분석 | 네이버 리뷰, 카카오맵 리뷰, SNS |

## 부록 B: 업종 분류 코드 빠른 참조 (빈출 업종)

| 업종 | KSIC 코드 | 사용자 표현 예시 |
|------|----------|----------------|
| 커피 전문점 | I56211 | 카페, 커피숍, 커피집 |
| 한식 일반 음식점 | I56111 | 한식, 한식당, 밥집 |
| 치킨 전문점 | I56192 | 치킨, 치킨집, 통닭 |
| 피자/햄버거/샌드위치 | I56191 | 피자, 버거, 샌드위치 |
| 분식점 | I56193 | 분식, 떡볶이, 김밥 |
| 일식 음식점 | I56113 | 일식, 초밥, 라멘, 돈카츠 |
| 중식 음식점 | I56112 | 중식, 중국집, 마라탕 |
| 서양식 음식점 | I56114 | 양식, 파스타, 브런치 |
| 편의점 | G47112 | 편의점 |
| 미용업 | S96112 | 미용실, 헤어샵, 헤어살롱 |
| 체육시설 | R93110 | 헬스장, 피트니스, 짐 |
| 필라테스/요가 | R93199 | 필라테스, 요가 |
| 의류 소매 | G47411 | 옷가게, 의류점, 부티크 |
| 화장품 소매 | G47432 | 화장품 가게 |
| 학원 | P85501 | 학원, 공부방, 교습소 |
| 세탁업 | S96911 | 세탁소, 빨래방 |
| 꽃집 | G47834 | 꽃집, 플라워샵, 화훼 |
| 베이커리 | C10711 | 빵집, 베이커리, 제과점 |
| 주점 | I56301 | 술집, 바, 포차, 이자카야 |
| 반려동물용품 | G47999 | 펫샵, 반려동물 가게 |

---

> **다음 문서**: `03_specialist_agents.md` - 전문 에이전트 개별 명세
