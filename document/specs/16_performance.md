# 16. 성능 벤치마크 & SLA 명세서

> MarketScope AI 성능 목표 및 벤치마크 기준
> 작성일: 2026-03-21

---

## 목차

1. [분석 모드별 응답 시간 목표](#1-분석-모드별-응답-시간-목표)
2. [API 엔드포인트 SLA](#2-api-엔드포인트-sla)
3. [LLM 비용 목표](#3-llm-비용-목표)
4. [동시 처리 용량](#4-동시-처리-용량)
5. [DB 쿼리 성능](#5-db-쿼리-성능)
6. [MCP 서버 성능](#6-mcp-서버-성능)
7. [부하 테스트 시나리오](#7-부하-테스트-시나리오)

---

## 1. 분석 모드별 응답 시간 목표

| 분석 모드 | 노드 수 | 목표 (p50) | 목표 (p95) | 최대 허용 |
|-----------|---------|-----------|-----------|-----------|
| **Quick** | ~6 (user_input → commander → pop+comp → judgment → report) | 15초 | 30초 | 45초 |
| **Basic** | ~12 (Quick + rev+loc + financial + risk) | 45초 | 90초 | 120초 |
| **Deep** | ~20 (Basic + trend+re+reg + debate_check + debate) | 90초 | 180초 | 300초 |
| **Comparison** | ~18 (Basic × 2 locations + comparison) | 60초 | 120초 | 180초 |

### 1.1 노드별 예상 소요시간

| 노드 | 예상 시간 (초) | LLM 호출 수 | 비고 |
|------|---------------|-------------|------|
| `user_input` | < 0.1 | 0 | 입력 파싱만 |
| `commander_plan` | 3-5 | 1 | Sonnet 4.6 |
| `population` | 5-10 | 1 | Gemini 2.5 Flash + MCP |
| `competition` | 5-10 | 1 | Gemini 2.5 Flash + MCP |
| `revenue` | 5-10 | 1 | Gemini 2.5 Flash + MCP |
| `location` | 5-10 | 1 | Gemini 2.5 Flash + MCP |
| `trend` | 5-10 | 1 | Gemini 2.5 Flash + MCP |
| `real_estate` | 5-10 | 1 | Gemini 2.5 Flash + MCP |
| `regulatory` | 5-10 | 1 | Gemini 2.5 Flash + MCP |
| `financial` | 5-8 | 1 | Gemini 2.5 Flash |
| `risk` | 5-8 | 1 | Gemini 2.5 Flash |
| `debate_check` | < 0.1 | 0 | 조건 평가만 |
| `debate` (3라운드) | 15-30 | 9 | Advocate+Critic+Judge × 3 |
| `commander_judgment` | 3-5 | 1 | Sonnet 4.6 |
| `narrative` | 3-5 | 1 | Sonnet 4.6 |
| `visualization` | 2-3 | 1 | Gemini Flash |
| `report_assembly` | < 0.5 | 0 | dict 조합만 |

### 1.2 병렬 실행 이점

```
순차 실행 (9개 에이전트): ~70초
병렬 실행 (3그룹 fan-out):
  Group 1: pop + comp = ~10초 (최대값)
  Group 2: rev + loc = ~10초
  Group 3: trend + re + reg = ~10초
  → 실제: ~30초 + sequential(financial + risk + judgment + report) ~20초
  → 총: ~50초 (28% 절약)
```

---

## 2. API 엔드포인트 SLA

| 엔드포인트 | p50 | p95 | p99 | 가용성 목표 |
|-----------|-----|-----|-----|-----------|
| `POST /analyze` (응답 시작) | 200ms | 500ms | 1s | 99.5% |
| `GET /analyze/{id}` | 50ms | 200ms | 500ms | 99.9% |
| `GET /analyze/{id}/stream` (첫 이벤트) | 1s | 3s | 5s | 99.5% |
| `GET /health` | 10ms | 50ms | 100ms | 99.99% |
| `GET /health/ready` | 100ms | 500ms | 1s | 99.9% |
| `GET /metrics` | 50ms | 200ms | 500ms | 99.9% |

---

## 3. LLM 비용 목표

### 3.1 분석당 비용

| 분석 모드 | 예상 비용 | LLM 호출 수 | 총 토큰 수 |
|-----------|-----------|-------------|-----------|
| Quick | $0.50-1.00 | 5-6 | ~15K |
| Basic | $1.00-2.00 | 10-12 | ~30K |
| Deep (토론 포함) | $3.00-8.00 | 20-25 | ~60K |
| Comparison | $2.00-4.00 | 18-20 | ~50K |

### 3.2 모델별 비용

| 모델 | Input ($/1M tokens) | Output ($/1M tokens) | 용도 |
|------|---------------------|----------------------|------|
| Gemini 2.5 Flash | $0.15 | $0.60 | 전문 에이전트 (9개) |
| Claude Sonnet 4.6 | $3.00 | $15.00 | Commander, Narrative |
| Claude Opus 4.6 | $15.00 | $75.00 | Judge (토론 시에만) |

### 3.3 월간 비용 예측

| 일일 분석 수 | 월간 예상 비용 | 모드 혼합 (Quick:Basic:Deep = 3:5:2) |
|-------------|---------------|-------------------------------------|
| 10건 | $45-90 | 소규모 운영 |
| 50건 | $225-450 | 중규모 운영 |
| 200건 | $900-1,800 | 대규모 운영 |

---

## 4. 동시 처리 용량

### 4.1 단일 인스턴스

| 항목 | 값 | 제약 요인 |
|------|-----|-----------|
| 동시 분석 | 4건 | `analysis_max_parallel_agents=4` |
| 동시 MCP 호출 | 5건 | `mcp_max_concurrent_tools=5` |
| DB 커넥션 | 20개 | asyncpg pool max_size |
| Redis 커넥션 | 10개 | ConnectionPool max |
| HTTP 커넥션 (MCP) | 10개 | httpx Limits |

### 4.2 수평 확장 시

| 인스턴스 수 | 동시 분석 | 일일 처리량 (예상) |
|------------|----------|------------------|
| 1 | 4건 | ~200건/일 |
| 3 | 12건 | ~600건/일 |
| 5 | 20건 | ~1,000건/일 |

---

## 5. DB 쿼리 성능

| 쿼리 유형 | 목표 (p95) | 인덱스 | 비고 |
|-----------|-----------|--------|------|
| 반경 내 점포 조회 (PostGIS) | < 100ms | GiST (geom) | ST_DWithin |
| 격자별 인구 조회 | < 50ms | B-tree (area_code) | |
| 지역별 매출 조회 | < 50ms | B-tree (area_code, industry) | |
| 상권 정보 공간 조회 | < 100ms | GiST (center_geom) | ST_DWithin |
| 분석 결과 저장 | < 200ms | — | INSERT |
| 분석 결과 조회 | < 50ms | B-tree (session_id) | SELECT |

---

## 6. MCP 서버 성능

| MCP 서버 | 목표 응답 시간 | 외부 API 의존 | Rate Limit |
|----------|--------------|--------------|-----------|
| public_data | < 2s | data.go.kr, 서울 열린데이터 | 1,000건/일 |
| maps (Kakao) | < 1s | 카카오 로컬 API | QPS 10 |
| real_estate | < 2s | 한국부동산원 | 1,000건/일 |
| news | < 2s | 네이버 뉴스 API | 25,000건/일 |
| regulatory | < 2s | data.go.kr | 1,000건/일 |
| finance | < 2s | 기업마당, K-Startup | 1,000건/일 |
| database | < 500ms | 내부 PostgreSQL | 없음 |
| google_maps | < 1s | Google Maps API | QPS 50 |
| naver_maps | < 1s | 네이버 지도 API | 3,000건/일 |

---

## 7. 부하 테스트 시나리오

### 7.1 도구

- **k6** (Grafana k6) 또는 **locust** (Python 기반)
- Prometheus + Grafana로 실시간 모니터링

### 7.2 시나리오

| 시나리오 | VU (가상 사용자) | 지속 시간 | 목표 |
|---------|----------------|-----------|------|
| Smoke Test | 1 | 1분 | 기본 동작 확인 |
| Load Test | 10 | 10분 | 정상 부하 (p95 < SLA) |
| Stress Test | 50 | 5분 | 한계 부하 (에러율 < 1%) |
| Soak Test | 5 | 1시간 | 메모리 누수 확인 |

### 7.3 k6 스크립트 예시

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 10 },  // ramp up
    { duration: '5m', target: 10 },  // steady
    { duration: '2m', target: 0 },   // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<5000'],
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const res = http.post('http://localhost:8000/analyze', JSON.stringify({
    query: '합정동 카페 창업 분석',
    mode: 'quick',
  }), { headers: { 'Content-Type': 'application/json' } });

  check(res, {
    'status is 200 or 202': (r) => r.status === 200 || r.status === 202,
  });

  sleep(3);
}
```
