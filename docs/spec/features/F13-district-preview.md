# F13 — 상권 프리뷰 (Zero-LLM)

> 지도 클릭 직후 **LLM 무호출** 로 핵심 지표를 요약 카드로 노출.
> `GET /api/districts/{code}/preview` · REST only · Agent 비경유.
> 2026-04-23 Plan `docs/plan/ui/landing-onboarding-feedback.md` §4.

## 1. 배경

2026-04-23 이전: 지도 클릭 → `useMapSync` 가 `"{name} 상권 요약해줘"` 를 즉시 `sendMessage` →
PAE 풀파이프 (6~8 Tool + 5~6 Card 스트림). 탐색 의도와 분석 의도를 구분하지 못해 모든 클릭이
LLM 토큰/비용 소모.

**해결**: 지도 클릭 → zero-LLM preview. 사용자가 chip 을 클릭하거나 `"AI 분석 보기"` 를 눌러야
PAE 풀파이프 진입.

## 2. API

### `GET /api/districts/{code}/preview`

**Query**: `role=owner|investor|founder` (optional, 그 외는 기본 세트)

**응답** (`DistrictPreview`):

```json
{
  "district_code": "D3001",
  "district_name": "강남역",
  "district_type": "발달상권",
  "data_quarter": "2025Q3",
  "center_lng": 127.0276,
  "center_lat": 37.4979,
  "top_categories": [
    {"category_code": "CS100", "category_name": "한식", "store_count": 245, "share_pct": 13.2}
  ],
  "floating_population": {
    "quarter": "2025Q3",
    "daily_total": 124350,
    "prev_quarter_total": 120000,
    "prev_quarter_delta_pct": 3.6,
    "peak_hour": 18
  },
  "suggested_questions": [
    "이 상권 유동인구 시간대별로 보여줘",
    "..."
  ]
}
```

**내부 구현** (`server/server/api/routes/districts.py`):

1. Redis `preview:{code}:{role|default}` → hit 시 즉시 반환
2. `DataAccess.districts.get_district_detail(code)` → 기본 메타 + center
3. `asyncio.gather(stores.get_store_info, floating_pop.get_floating_population(current),
   floating_pop.get_floating_population(prev_quarter))` 병렬 실행
4. `_build_top_categories` (top 3) + `_build_floating` (prev 대비 delta %) 집계
5. `_suggestions_for(role)` — 역할별 정적 프리셋 (`intents.yaml` 매핑 기반)
6. 결과 `cache.set(..., ttl=86400)` (24h)

**에러 처리**:

- 404 — `get_district_detail` 가 None
- 503 — `OperationalError` (DB 장애)
- 그 외 예외 — `suggested_questions` 만 담아 200 (UX degrade 원칙)

**LLM 호출 0**: Repository 직접 호출. Agent Tool · LLM 프로바이더 경유 없음.

## 3. 프론트엔드 흐름

```
지도 클릭 → districtStore.select(source='map')
           ↓
   useMapSync (hooks/useMapSync.ts)
           ↓
   chatStore.setPreview(code)
       └ fetchDistrictPreview(code, role) (lib/api.ts)
           ↓
   chatStore.preview 업데이트
           ↓
   ChatPanel → MessageList previewSlot 에 PreviewCard 렌더
     ├ 상권명 · 유형 · 분기
     ├ 주요 업종 Top 3 + share bar
     ├ 유동인구 전분기 대비 delta + peak hour
     ├ 예시 질문 chip (5개, 역할별)
     └ "AI 분석 보기" 풀파이프 CTA

사용자 chip 클릭 or CTA 클릭
           ↓
   chatStore.sendMessage(prompt)
           ↓
   preview=null (sendMessage 내에서 자동 클리어) + PAE 풀파이프 실행
```

## 4. `role` 별 suggested_questions

| Role | 대표 질문 (5개) |
|---|---|
| `owner` (소상공인) | 유동인구 시간대 / 경쟁 점포 수 / 비교 / 리스크 / 프랜차이즈 비중 |
| `investor` | 2~3 상권 비교 / 유망 업종 / 히트맵 / 안정성 점수 / 매출 시뮬 |
| `founder` (창업 준비) | 유망 업종 추천 / 매출 시뮬 / 예산 대비 업종 / 생존율 / 비교 |
| (기본) | 요약 / 비교 / 유망 업종 / 매출 시뮬 / 리스크 |

## 5. 캐시 키

`preview:{district_code}:{role|default}` · TTL 24h.

Redis 실패 시 `RedisCacheService` 가 graceful degrade → 매 요청 repo 재조회 (기능 정상).

## 6. 완료 조건 / E2E

- `1-PREVIEW-API` — 200 + shape (top_categories/floating/suggested) + role 별 suggestion 차이
- `1-PREVIEW-CACHE` — 동일 code 2회 호출 latency <20ms
- `1-F01-PREVIEW-FIRST` — 지도 클릭 시 `/api/chat` POST 0건 + `data-testid="district-preview"` 노출
- `1-F01-PREVIEW-CHIP` — chip 클릭 → SSE 발사
- `1-F01-PREVIEW-DEEP` — "AI 분석 보기" → 풀파이프 카드 수신
- `3-NEG-PREVIEW-BAD-CODE` — 404
