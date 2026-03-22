# MarketScope AI - 서비스 플로우 정의서

## 1. 서비스 개요

**MarketScope AI**는 대한민국 상권(Catchment Area)을 다차원으로 분석하여 창업·투자 의사결정을 지원하는 **멀티 에이전트 AI 분석 서비스**입니다.

- 11개 전문 에이전트가 LangGraph DAG(20개 노드)를 통해 협업
- 9개 MCP 서버를 통한 외부 데이터 수집
- 품질 검증을 위한 다자간 토론(Debate) 시스템 내장
- SSE 기반 실시간 진행률 스트리밍

---

## 2. 사용자 입력 (Input)

### API 엔드포인트

```
POST /api/v1/analysis
Content-Type: application/json
```

### 요청 파라미터

| 항목 | 필수 | 타입 | 설명 | 예시 |
|------|------|------|------|------|
| `query` | O | string (2-500자) | 자연어 분석 요청 | `"강남역 카페 창업 분석해줘"` |
| `location` | X | string | 위치 힌트 | `"강남역"` |
| `industry` | X | string | 업종 힌트 | `"카페"` |
| `depth` | X | enum | 분석 깊이 | `quick` / `standard` / `deep` |

### 요청 예시

```json
{
  "query": "강남역 근처 카페 창업 가능할까? 초기 투자금 5천만 원 이내로 생각 중이야",
  "location": "강남역",
  "industry": "카페",
  "depth": "standard"
}
```

### 응답 (202 Accepted)

```json
{
  "request_id": "uuid-string",
  "status": "queued",
  "estimated_duration_sec": 180,
  "stream_url": "/api/v1/analysis/{request_id}/stream",
  "created_at": "2026-03-22T10:30:00Z"
}
```

---

## 3. 서비스 플로우 (6단계)

### 전체 흐름도

```
[1] 요청 접수 ─────────────────────────────────────────────────
    POST /api/v1/analysis → 202 Accepted + request_id + stream_url

[2] Commander 기획 ─────────────────────────────────────────────
    자연어 쿼리 파싱 → 위치/업종/분석모드 추출
    예: "강남역" + "카페" + "standard" 모드 결정

[3] 병렬 데이터 수집 & 분석 (9개 에이전트) ─────────────────────
    ┌─ Group 1 (병렬) ──────────────────────────────┐
    │  인구 분석: 유동인구, 연령대, 피크시간대         │
    │  경쟁 분석: 경쟁업체 수, 포화지수, 개폐업률      │
    └───────────────────────────────────────────────┘
              ↓ (quick 모드면 여기서 → [5]로 점프)
    ┌─ Group 2 (병렬) ──────────────────────────────┐
    │  매출 분석: 예상 월매출, 계절 패턴              │
    │  입지 분석: 접근성, 가시성, 유동인구 품질        │
    └───────────────────────────────────────────────┘
    ┌─ Group 3 (병렬) ──────────────────────────────┐
    │  트렌드 분석: 검색량 추이, 라이프사이클 단계     │
    │  부동산 분석: 임대료, 권리금, 공실률             │
    │  규제 분석: 필요 허가, 용도지역, 영업시간 제한    │
    └───────────────────────────────────────────────┘
              ↓ (순차 실행 - 앞선 결과에 의존)
    재무 분석: 초기투자, 손익분기, ROI 시나리오
    리스크 분석: 종합 리스크 점수, 위험요인, 완화전략

[4] 품질 검증 (Debate - 조건부) ─────────────────────────────────
    트리거 조건: 에이전트 간 결론 충돌 / 신뢰도 낮음 / deep 모드
    ├─ Advocate (Gemini): 창업 찬성 논거
    ├─ Critic (Claude): 반대 논거 / 리스크 강조
    └─ Judge (Opus): 최종 판정, 점수 수정, 성공 조건 제시

[5] 종합 판단 ──────────────────────────────────────────────────
    Commander가 9개 분석 결과 + 토론 결과 종합
    → 종합점수(0-100) + 등급(S/A/B/C/D/F) + 추천의견 산출

[6] 리포트 생성 ────────────────────────────────────────────────
    ├─ 내러티브 에이전트: 구조화된 데이터 → 산문형 보고서
    ├─ 시각화 에이전트: 차트/지도 설정 생성
    └─ 리포트 조립: 최종 JSON 리포트 완성
```

---

### 단계별 상세

#### [1] 요청 접수

- 사용자가 `POST /api/v1/analysis`로 분석 요청 제출
- 서버는 즉시 `202 Accepted` 응답 + `request_id` 반환
- 클라이언트는 `stream_url`을 통해 SSE 구독하여 실시간 진행 확인

#### [2] Commander 기획 (Progress: 5%)

- LLM이 자연어 쿼리를 분석하여 구조화된 정보 추출
  - `target_location`: 분석 대상 위치
  - `target_industry`: 분석 대상 업종
  - `analysis_mode`: quick / standard / deep
  - `user_constraints`: 사용자 제약조건 (예: 예산)
- 실행할 에이전트 목록 및 토론 강제 여부 결정
- 정보 부족 시 사용자에게 명확화 요청 반환

#### [3] 병렬 데이터 수집 & 분석

**Group 1 (Progress: 25%) - 핵심 지표**

| 에이전트 | 수집 데이터 | 데이터 소스 |
|----------|------------|------------|
| 인구 분석 | 유동/상주/직장 인구, 연령 분포, 피크 시간대, 추이 | KOSIS, 서울 열린데이터, Kakao Maps |
| 경쟁 분석 | 경쟁업체 수, 포화지수, 개업/폐업률, 시장 점유율 | 소상공인시장진흥공단, 서울 열린데이터 |

**Group 2 (Progress: 45%) - 수익성 지표**

| 에이전트 | 수집 데이터 | 데이터 소스 |
|----------|------------|------------|
| 매출 분석 | 총매출, 점포당 매출, 매출 추정, 계절 패턴 | 소상공인 매출 데이터, 서울 업종별 매출 |
| 입지 분석 | 접근성 점수, 지하철 근접도, 가시성, 주차, 유동인구 품질 | Kakao Maps, Naver Maps |

**Group 3 (Progress: 60%) - 환경 분석**

| 에이전트 | 수집 데이터 | 데이터 소스 |
|----------|------------|------------|
| 트렌드 분석 | 라이프사이클 단계, 검색량 추이, 신규 키워드, 계절 피크 | Google Trends, 뉴스 API |
| 부동산 분석 | 평당 임대료, 권리금 추정, 보증금, 공실률 | 네이버 부동산, 서울 부동산 통계 |
| 규제 분석 | 필요 인허가, 용도지역 현황, 영업시간 제한 | 규제 데이터베이스, 서울 용도지역 |

**순차 분석 (Progress: 65%) - 종합 판단 의존**

| 에이전트 | 수집 데이터 | 의존 관계 |
|----------|------------|-----------|
| 재무 분석 | 초기 투자비, 운영비, 손익분기 개월, ROI (12/24개월), 시나리오 | 매출 + 경쟁 결과 |
| 리스크 분석 | 리스크 점수, 등급, 위험 요인, 완화 전략 | 전체 Group 2-3 결과 |

#### [4] 품질 검증 - Debate 시스템 (Progress: 80%)

**트리거 조건** (4가지 중 하나 충족 시 발동):

1. Commander가 `force_debate` 플래그 설정
2. 에이전트 평균 신뢰도 < 0.6
3. 매출 추정 분산 > 30%
4. 에이전트 간 결론 충돌 (인구 vs 경쟁 점수 차이 > 0.3)

**토론 프로세스** (최대 3라운드):

| 역할 | 모델 | 임무 |
|------|------|------|
| Advocate | Gemini 2.5 Pro | 창업 찬성 논거 제시 |
| Critic | Claude Sonnet | 반대 논거, 리스크 강조 |
| Judge | Claude Opus | 최종 판정, 수렴 여부 결정, 점수 수정 |

#### [5] 종합 판단 (Progress: 85%)

- Commander가 9개 에이전트 결과 + 토론 결과 종합
- 산출물:
  - **종합 점수**: 0-100점
  - **등급**: S / A / B / C / D / F
  - **추천 의견**: 강력추천 / 추천 / 조건부추천 / 보류 / 비추천
  - **핵심 발견**: 5-7개 인사이트
  - **핵심 실행사항**: 3-5개 액션 아이템

#### [6] 리포트 생성 (Progress: 100%)

- **내러티브 에이전트**: 구조화된 데이터를 산문형 보고서로 변환
- **시각화 에이전트**: 차트/지도 설정 JSON 생성
- **리포트 조립 노드**: 모든 결과를 단일 `FinalReport` JSON으로 병합

---

## 4. 사용자 결과물 (Output)

### 4.1 실시간 진행률 (SSE Stream)

```
GET /api/v1/analysis/{request_id}/stream
```

```
data: {"type":"status","status":"processing","message":"분석을 시작합니다..."}
data: {"type":"progress","node":"commander_plan","progress_pct":5}
data: {"type":"progress","node":"population","progress_pct":15}
...
data: {"type":"status","status":"completed","message":"분석이 완료되었습니다."}
```

### 4.2 최종 리포트

```
GET /api/v1/analysis/{request_id}
```

#### 리포트 구성요소

| 카테고리 | 내용 |
|----------|------|
| **종합 점수/등급** | 0~100점 + S/A/B/C/D/F 등급 |
| **추천 의견** | 강력추천 / 추천 / 조건부추천 / 보류 / 비추천 |
| **핵심 발견** | 5~7개 핵심 인사이트 |
| **핵심 실행사항** | 3~5개 우선 실행 항목 |
| **9개 상세 분석** | 인구·경쟁·매출·입지·트렌드·부동산·재무·리스크·규제 |
| **내러티브 보고서** | 요약(3-5문장) + 상세 분석문 + 권장사항 + 리스크 경고 |
| **시각화 설정** | 차트/지도 렌더링용 JSON 설정 |
| **토론 결과** | 찬반 논거 + 판정 결과 + 성공 조건 (deep 모드) |

#### 시각화 항목

| 차트 유형 | 내용 |
|-----------|------|
| 레이더 차트 | 9개 항목별 분석 점수 |
| 바 차트 | 시간대별 유동인구 |
| 게이지 차트 | 예상 월매출 |
| 게이지 차트 | 시장 포화 지수 |
| 지도 | 대상 위치 + 주변 마커 |
| 요약 카드 | 핵심 지표 수치 |

#### 리포트 응답 예시 (일부)

```json
{
  "report_id": "abc-123",
  "overall_score": 75.0,
  "overall_grade": "B",
  "recommendation": "조건부추천",
  "executive_summary": "강남역 상권은 일평균 15,000명의 유동인구로 높은 접근성을 보이고...",
  "key_findings": [
    "유동인구: 일 15,000명 (상위 25%)",
    "카페 포화 지수: 1.8 (중간 수준)",
    "예상 월 매출: 4,200만 원",
    "권리금: 3,000~5,000만 원",
    "ROI: 12개월 15%, 24개월 45%"
  ],
  "population_result": {
    "total_floating_population": 15000,
    "peak_times": ["08:00-09:00", "12:00-14:00", "17:30-19:00"],
    "trend_rate": 2.3,
    "confidence_score": 0.85
  },
  "revenue_result": {
    "estimated_monthly_revenue": 42000000,
    "revenue_range": {"min_value": 35000000, "max_value": 52000000},
    "confidence_score": 0.72
  },
  "visualization_config": {
    "chart_configs": [
      {"type": "radar", "title": "항목별 분석 점수"},
      {"type": "bar", "title": "시간대별 유동인구"}
    ],
    "map_config": {
      "center": {"lat": 37.4979, "lng": 127.0276},
      "zoom": 16
    }
  },
  "debate_result": null
}
```

---

## 5. 분석 깊이별 비교

| 항목 | Quick | Standard | Deep |
|------|-------|----------|------|
| **소요 시간** | ~60초 | ~180초 | ~420초 |
| **실행 에이전트** | 인구 + 경쟁 (2개) | 전체 9개 | 전체 9개 |
| **토론 시스템** | 미실행 | 조건부 실행 | 강제 실행 (3라운드) |
| **재무 분석** | 미포함 | 포함 | 포함 (심층) |
| **리스크 분석** | 미포함 | 포함 | 포함 (심층) |
| **내러티브 보고서** | 간략 요약 | 전체 보고서 | 전체 보고서 + 토론 결과 |
| **적합 용도** | 빠른 사전 검토 | 일반 창업 분석 | 고액 투자 의사결정 |

---

## 6. API 엔드포인트 요약

| Method | Endpoint | 설명 | 응답 |
|--------|----------|------|------|
| `POST` | `/api/v1/analysis` | 분석 요청 생성 | `202 + {request_id, stream_url}` |
| `GET` | `/api/v1/analysis/{id}` | 분석 결과 조회 | `200 + FinalReport JSON` |
| `GET` | `/api/v1/analysis/{id}/stream` | 실시간 진행률 스트림 | `200 text/event-stream (SSE)` |
| `GET` | `/api/v1/health` | 기본 헬스체크 | `{status, app_name, version}` |
| `GET` | `/api/v1/health/live` | 라이브니스 프로브 (K8s) | `{status: "ok"}` |
| `GET` | `/api/v1/health/ready` | 레디니스 프로브 (K8s) | `{status, checks}` |
| `GET` | `/api/v1/health/detailed` | 상세 컴포넌트 상태 | `{status, checks, mcp_stats}` |
| `GET` | `/metrics` | Prometheus 메트릭 | `text/plain` |

---

## 7. LangGraph DAG 노드 실행 순서

```
START
  ↓
user_input (검증)
  ↓ (에러 시: END)
commander_plan (쿼리 파싱, 분석 계획)
  ↓ (명확화 필요 시: END)
population ↔ competition       [병렬, fan-in]
  ↓
group1_complete
  ↓ (quick 모드: → commander_judgment)
revenue ↔ location             [병렬, fan-in]
  ↓
group2_complete
  ↓
trend ↔ real_estate ↔ regulatory  [3-way 병렬, fan-in]
  ↓
group3_complete
  ↓
financial                      [순차, revenue + competition 의존]
  ↓
risk                           [순차, 전체 결과 의존]
  ↓
debate_check                   [4가지 트리거 조건 평가]
  ↓ (trigger: 토론 실행 / skip: 건너뛰기)
[debate]                       [3라운드: advocate → critic → judge]
  ↓
commander_judgment             [전체 결과 종합]
  ↓ (critical_failure: 리포트 건너뛰기)
narrative ↔ visualization      [병렬]
  ↓
report_assembly                [최종 리포트 조립]
  ↓
END
```

---

## 8. 데이터 소스 (MCP 서버)

| 포트 | 서버 | 주요 도구 | 데이터 소스 |
|------|------|-----------|------------|
| 5100 | `public_data` | `kosis.*`, `seoul_api.*` | KOSIS (통계청), 서울 열린데이터 |
| 5101 | `maps` | `maps.*` | Kakao Maps API |
| 5102 | `real_estate` | `real_estate.*` | 부동산 마켓플레이스 API |
| 5103 | `news` | `news.*` | 뉴스 집계, 트렌드 API |
| 5104 | `regulatory` | `regulatory.*` | 규제 데이터베이스 |
| 5105 | `finance` | `finance.*` | 금융 데이터 API |
| 5106 | `database` | `database.*` | PostgreSQL (상권/업체 데이터) |
| 5107 | `google_maps` | `google_maps.*` | Google Maps API |
| 5108 | `naver_maps` | `naver_maps.*` | Naver Maps API |
