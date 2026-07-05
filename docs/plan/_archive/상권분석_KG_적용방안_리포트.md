# 상권 분석을 위한 Knowledge Graph 적용 방안 리포트

> Tabular 기반 상권 데이터(매출, 유동인구, 임대료, 상가업소 정보 등)를 Knowledge Graph로 변환하고 KG-RAG 시스템을 구축하기 위한 설계 및 실행 가이드

---

## 1. 배경 및 목적

### 1.1 문제 정의

상권분석 업무는 본질적으로 **관계 기반 추론**을 요구합니다.

- "강남역 상권과 매출 패턴이 유사한 다른 상권은?"
- "치킨집 창업 시 경쟁 밀도가 낮고 유동인구가 많은 상권은?"
- "최근 6개월간 매출이 감소한 상권과 그 주변의 변화 요인은?"

이러한 질문은 **여러 엔티티(점포 / 상권 / 업종 / 시간 / 인구 세그먼트) 간의 관계를 연결하고 다단계로 추론**해야 답할 수 있습니다. 기존 Vector RAG는 텍스트 유사도 기반이라 이러한 관계형 질의에 취약합니다.

### 1.2 왜 KG인가

| 요구사항 | Vector RAG | KG 기반 RAG |
|---|---|---|
| 매출/인구 수치의 **정확성** | 환각 위험 | 스키마 강제로 안전 |
| **멀티홉 추론** ("근처 경쟁점의 매출") | 약함 | 트래버설로 자연스럽게 해결 |
| **시계열 집계** (월별/연도별 추이) | 불가능 수준 | 팩트 노드로 구조화 |
| **계층 집계** (동 → 구 → 시) | 불가능 | 계층 엣지로 즉시 풀림 |
| **설명 가능성** (왜 이 답이 나왔는가) | 블랙박스 | 추론 경로 추적 가능 |

---

## 2. Tabular → Knowledge Graph 변환 원칙

### 2.1 기본 매핑 규칙

| 테이블 요소 | KG 요소 | 예시 |
|---|---|---|
| **Row (행)** | Entity (노드) | 상가업소 테이블의 각 행 = `(Store)` 노드 |
| **Column (컬럼)** | Attribute 또는 Relation | `district_id` → `(Store)-[LOCATED_IN]->(District)` |
| **Cell (값)** | Property 또는 Fact 노드 | 매출액 → `SalesFact` 노드의 속성 |

### 2.2 핵심 원칙

1. **식별자가 있는 값은 엔티티로**: `district_id`, `category_code`처럼 고유 식별자를 가진 값은 별도 노드로 분리
2. **시계열 수치는 팩트 노드로**: 매출/유동인구는 절대 관계 속성에 넣지 말고 별도 팩트 노드 생성
3. **계층 구조는 명시적 엣지로**: 구 → 동 → 상권 → 점포 계층을 `PART_OF` 엣지로 연결
4. **도출 가능한 관계는 추론으로 추가**: 근접성, 경쟁관계 등은 좌표/업종으로 계산해 엣지 생성

---

## 3. 도메인 스키마 설계

### 3.1 엔티티(노드) 설계

```
핵심 엔티티
├─ Store            점포 (개별 매장)
├─ Brand            브랜드/프랜차이즈
├─ Category         업종 (계층 구조)
├─ TradeArea        상권 (골목/발달/전통시장)
├─ AdminDistrict    행정구역 (동/구/시)
├─ Building         건물
├─ Location         지리 좌표 포인트
├─ TimeSlot         시간대 (평일점심, 주말저녁 등)
└─ DemographicSegment  인구 세그먼트 (20대여성 등)

팩트 노드 (시계열/측정값)
├─ SalesFact        월별 매출 팩트
├─ FootTrafficFact  유동인구 팩트
├─ RentFact         임대료 팩트
└─ EventFact        점포 개폐업 이벤트
```

### 3.2 관계(엣지) 설계

#### 구조적 관계 (테이블에서 직접 추출)

| 관계 | 방향 | 의미 |
|---|---|---|
| `BELONGS_TO` | Store → Brand | 프랜차이즈 소속 |
| `OF_CATEGORY` | Store → Category | 업종 분류 |
| `SUBCATEGORY_OF` | Category → Category | 업종 계층 (커피전문점 ⊂ 카페 ⊂ 외식) |
| `LOCATED_IN` | Store → TradeArea | 상권 귀속 |
| `PART_OF` | TradeArea → AdminDistrict | 행정구역 귀속 |
| `HAS_LOCATION` | Store → Location | 좌표 연결 |

#### 추론 관계 (계산으로 생성)

| 관계 | 계산 방식 | 용도 |
|---|---|---|
| `NEAR` | 두 점포의 좌표 거리 < 임계값 | 근접 분석 |
| `COMPETES_WITH` | 동일 업종 + 근접 | 경쟁 구도 분석 |
| `COMPLEMENTS` | 보완재 업종 룰 + 근접 | 시너지 분석 |
| `ADJACENT_TO` | 상권 경계 맞닿음 | 상권 클러스터링 |
| `SIMILAR_PROFILE` | 매출/인구 벡터 코사인 유사도 > 0.85 | 유사 상권 탐색 |

### 3.3 팩트 노드 설계 (시계열 처리의 핵심)

**Bad Practice (관계 속성):**
```
(Store)-[HAS_SALES {year:2024, month:3, amount:1억}]->(Store)
```
→ 시간 필터링/집계 시 쿼리가 극도로 복잡해짐

**Good Practice (팩트 노드):**
```
(f:SalesFact {
   period: '2024-03',
   amount: 100000000,
   transaction_count: 3200,
   avg_ticket: 31250
})
(f)-[:OF_STORE]->(Store)
(f)-[:AT_TIME]->(TimeSlot)
```
→ 시간 범위 쿼리, 집계, 시계열 비교가 자연스럽게 해결됨

---

## 4. 주요 테이블별 변환 예시

### 4.1 상가업소 정보 테이블

**원본:**

| store_id | 상호 | 업종코드 | 업종명 | 주소 | 위도 | 경도 | 상권코드 |
|---|---|---|---|---|---|---|---|
| S001 | 스타벅스 강남점 | Q01A01 | 커피전문점 | 서울시 강남구... | 37.49 | 127.03 | TA_GN01 |

**KG 변환:**
```cypher
CREATE (s:Store {id:'S001', name:'스타벅스 강남점'})
CREATE (c:Category {code:'Q01A01', name:'커피전문점'})
CREATE (t:TradeArea {code:'TA_GN01'})
CREATE (l:Location {lat:37.49, lng:127.03})
CREATE (b:Brand {name:'스타벅스'})

CREATE (s)-[:OF_CATEGORY]->(c)
CREATE (s)-[:LOCATED_IN]->(t)
CREATE (s)-[:HAS_LOCATION]->(l)
CREATE (s)-[:BELONGS_TO]->(b)
```

### 4.2 월별 매출 추정 테이블

**원본:**

| 상권코드 | 업종코드 | 년월 | 추정매출 | 건당단가 | 주중매출비중 |
|---|---|---|---|---|---|
| TA_GN01 | Q01A01 | 2024-03 | 50억 | 6,500 | 72% |

**KG 변환:**
```cypher
CREATE (f:SalesFact {
   period: '2024-03',
   estimated_sales: 5000000000,
   avg_ticket: 6500,
   weekday_ratio: 0.72
})
CREATE (f)-[:IN_TRADE_AREA]->(t:TradeArea {code:'TA_GN01'})
CREATE (f)-[:OF_CATEGORY]->(c:Category {code:'Q01A01'})
```

### 4.3 유동인구 테이블

**원본:**

| 상권코드 | 년월 | 시간대 | 연령대 | 성별 | 유동인구수 |
|---|---|---|---|---|---|
| TA_GN01 | 2024-03 | 점심 | 20대 | 여 | 12,500 |

**KG 변환:**
```cypher
CREATE (fp:FootTrafficFact {period:'2024-03', count:12500})
CREATE (fp)-[:IN_TRADE_AREA]->(t:TradeArea {code:'TA_GN01'})
CREATE (fp)-[:AT_TIME]->(ts:TimeSlot {name:'점심'})
CREATE (fp)-[:OF_SEGMENT]->(seg:DemographicSegment {age:'20대', gender:'여'})
```

### 4.4 임대료 테이블

**원본:**

| 상권코드 | 년월 | 평균임대료 | 평당단가 |
|---|---|---|---|
| TA_GN01 | 2024-03 | 350만원 | 25만원 |

**KG 변환:** `RentFact` 팩트 노드 생성 후 상권과 연결.

---

## 5. 추론 관계(Derived Edges) 생성

**테이블에 명시적으로 없지만 계산으로 도출 가능한 관계**를 배치 잡으로 생성하는 것이 KG의 핵심 가치입니다.

### 5.1 근접성 관계

```python
for s1, s2 in store_pairs:
    dist = haversine(s1.location, s2.location)
    if dist < 200:  # 200m 이내
        add_edge(s1, 'NEAR', s2, distance_m=dist)
```

### 5.2 경쟁 관계

```python
if s1.category == s2.category and distance(s1, s2) < 500:
    add_edge(s1, 'COMPETES_WITH', s2)
```

### 5.3 보완 관계

```python
COMPLEMENT_RULES = {
    '카페': ['서점', '학원', '코워킹스페이스'],
    '치킨집': ['호프집', '편의점'],
    '미용실': ['네일샵', '피부관리'],
}

if s2.category in COMPLEMENT_RULES.get(s1.category, []):
    add_edge(s1, 'COMPLEMENTS', s2)
```

### 5.4 상권 유사도

```python
# 각 상권을 매출 벡터 + 인구 벡터로 표현
for ta1, ta2 in trade_area_pairs:
    sim = cosine_similarity(ta1.profile_vector, ta2.profile_vector)
    if sim > 0.85:
        add_edge(ta1, 'SIMILAR_PROFILE', ta2, similarity=sim)
```

### 5.5 실행 주기

| 엣지 종류 | 갱신 주기 | 비고 |
|---|---|---|
| `NEAR`, `COMPETES_WITH` | 월 1회 | 점포 개폐업 반영 |
| `COMPLEMENTS` | 분기 1회 | 룰 기반이라 변화 느림 |
| `SIMILAR_PROFILE` | 월 1회 | 매출 데이터 갱신 주기 맞춤 |

---

## 6. 계층 구조 활용

상권분석의 강력한 기능은 **계층 집계**입니다. KG에서는 경로 트래버설로 자연스럽게 풀립니다.

### 6.1 지리 계층

```
전국
  └ 서울시
      └ 강남구
          └ 역삼1동
              └ TA_GN01 (강남역 상권)
                  └ 개별 점포들
```

### 6.2 업종 계층

```
외식업
  └ 한식
      └ 한정식
          └ 개별 점포
```

### 6.3 계층 쿼리 예시

```cypher
// 강남구 전체 카페 매출 합계
MATCH (d:AdminDistrict {name:'강남구'})<-[:PART_OF*]-(t:TradeArea)
      <-[:IN_TRADE_AREA]-(f:SalesFact)-[:OF_CATEGORY]->(c:Category)
WHERE c.name CONTAINS '카페'
  AND f.period STARTS WITH '2024'
RETURN t.name, SUM(f.estimated_sales) AS total_sales
ORDER BY total_sales DESC
```

---

## 7. KG-RAG 방식 선택

상권분석 데이터 특성을 고려한 RAG 아키텍처 선택:

### 7.1 추천: OG-RAG / KAG (1순위)

**선택 이유**
- 상권/업종/시간 도메인 개념이 명확 → 온톨로지 정의 용이
- 숫자 정확성이 핵심 → 스키마 제약이 환각을 원천 차단
- 논리식 기반 쿼리로 **"역삼동 카페 평균매출"** 같은 질문이 정확히 실행됨

### 7.2 차선: Dual-channel KG-RAG (2순위)

**선택 이유**
- 정형 데이터(매출 KG) + 비정형 데이터(상권 리포트, 뉴스 기사)를 함께 활용
- 예: "강남역 팝업스토어 트렌드" 같은 질문에 뉴스 벡터 검색 + KG 집계를 결합

### 7.3 비추천

| 방식 | 비추천 이유 |
|---|---|
| MS GraphRAG (Community-based) | Tabular 데이터는 구조가 이미 명확 → LLM 엔티티 추출이 불필요하고 인덱싱 비용만 폭증 |
| 순수 Vector RAG | 수치 집계/멀티홉 추론 불가 |
| RAPTOR | 관계형 질의 지원 부재 |

---

## 8. 실무 파이프라인 아키텍처

```
┌──────────────────────┐
│   Raw Tables         │  상가업소 / 매출 / 유동인구 / 임대료
│   (공공데이터 / 내부)  │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│  스키마 설계 / 온톨로지 │  도메인 전문가 + 분석 목적 기반
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│  ETL 파이프라인       │  각 테이블 → Cypher INSERT
│  (Airflow / dbt)     │  단계별 멱등성 보장
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│  Enrichment 배치 잡  │  근접/경쟁/보완/유사도 엣지 생성
│  (월 1회 주기)        │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│  Graph DB            │  Neo4j / TigerGraph / ArangoDB
│  + Vector Index      │  점포명/리뷰 등은 별도 벡터 인덱스
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│  KG-RAG 레이어       │  Text-to-Cypher LLM + 답변 생성
│                      │  스키마 프롬프트 주입
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│  사용자 인터페이스     │  자연어 질의 → 정형 분석 결과
└──────────────────────┘
```

---

## 9. 질문 유형별 동작 예시

| 사용자 질문 | KG 해결 방식 |
|---|---|
| "강남역 상권의 30대 여성 타깃 카페 매출 추이" | `TradeArea → SalesFact + FootTrafficFact` 조인 후 시계열 정렬 |
| "스타벅스 근처 200m 내 경쟁 카페의 매출 비교" | `Store -[NEAR]-> Store -[COMPETES_WITH]->` 트래버설 후 매출 팩트 조회 |
| "강남역 상권과 매출 패턴이 비슷한 다른 상권" | `TradeArea -[SIMILAR_PROFILE]-> TradeArea` (사전 계산 엣지) |
| "치킨집 창업하려는데 좋은 상권 추천" | 업종 매출 상위 + 경쟁 밀도 낮은 + 타깃 인구 많은 상권 복합 필터링 |
| "최근 6개월간 매출 감소 상권과 주변 변화 요인" | 시계열 팩트 정렬 + 주변 `Store`의 `EventFact` (폐업/신규) 조회 |

마지막 질문의 **"왜 매출이 줄었나?"** 류 인과적 질의는 벡터 RAG에서 거의 불가능하지만, KG에서는 주변 이벤트 노드를 함께 꺼내오면 자연스럽게 설명이 가능합니다.

---

## 10. 실전 팁 & 권장사항

### 10.1 시작 규모

처음부터 완벽한 스키마를 만들지 말 것. 핵심 5-6개 엔티티로 시작:
- `Store`, `Category`, `TradeArea`, `SalesFact`, `FootTrafficFact`, `AdminDistrict`

질문이 안 풀리는 지점에서 스키마를 점진적으로 확장하는 것이 실패 확률을 줄입니다.

### 10.2 시계열 처리 철칙

매출/유동인구는 **반드시 팩트 노드**로. 관계 속성에 넣으면 나중에 시간축 집계에서 쿼리가 지옥이 됩니다.

### 10.3 Text-to-Cypher 체인

사용자 자연어 질문을 Cypher로 변환하는 LLM 체인을 구축하면 분석가가 아니어도 KG를 활용할 수 있습니다. **스키마 정보를 프롬프트에 명시**하는 것이 핵심.

```
[System Prompt]
당신은 상권분석 KG 전문가입니다.
아래 스키마를 기반으로 사용자 질문을 Cypher 쿼리로 변환하세요.

엔티티: Store, TradeArea, Category, SalesFact, FootTrafficFact, ...
관계: LOCATED_IN, OF_CATEGORY, IN_TRADE_AREA, NEAR, COMPETES_WITH, ...

[User Query]
"강남역 근처 경쟁 카페 중 매출 상위 3곳"
```

### 10.4 벡터 인덱스 병행

점포명, 리뷰, 상권 설명 같은 **텍스트 속성은 별도 벡터 인덱스**로 관리하고, "힙한 카페" "핫한 상권" 같은 모호한 쿼리는 **벡터 → KG 조인** 패턴으로 해결.

### 10.5 갱신 주기 관리

| 데이터 종류 | 갱신 주기 | 갱신 방식 |
|---|---|---|
| 점포 개폐업 | 월 1회 | Incremental UPSERT |
| 매출/유동인구 팩트 | 월 1회 | 팩트 노드 추가 (append-only) |
| 추론 엣지 | 월 1회 | 배치 재계산 |
| 상권/행정구역 | 연 1회 | 정부 고시 반영 |

---

## 11. 요약

1. Tabular 상권 데이터는 **엔티티(점포/상권/업종) + 팩트(매출/인구) + 관계(위치/경쟁/보완)** 구조로 KG 변환 가능
2. **팩트 노드 분리**와 **추론 엣지 생성**이 KG 가치의 핵심
3. **OG-RAG / KAG** 방식이 수치 정확성과 스키마 강제 때문에 가장 적합
4. 계층 구조(지리·업종)를 명시적 엣지로 모델링하면 집계 질의가 한 줄 쿼리로 해결
5. 작게 시작해서 질문이 막히는 지점에서 스키마를 확장하는 **점진적 접근**이 실패 확률을 최소화

KG 기반 상권분석 시스템은 초기 설계 비용이 들지만, 일단 구축되면 **멀티홉 추론·인과 분석·유사 상권 탐색** 같은 고부가가치 분석을 자연어로 수행할 수 있는 강력한 자산이 됩니다.
