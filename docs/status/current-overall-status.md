# 설계 vs 구현 종합 검토 리포트

> 최종 검토일: 2026-04-05
> 검토 범위: 초기 설계서(overall-architecture.md), 기능 스펙(F01~F08, D01, B01), 체크리스트(checklist.md) 대비 실제 구현 상태

---

## 1. 전체 진행률 요약

| Phase | 계획 | 실제 | 달성률 |
|-------|------|------|--------|
| **Phase 1A** (Mock E2E) | M01, F01, F02, F03, F05, F07, F08 | 전부 완료 | **100%** |
| **Phase 1B** (Real Data + UX) | D03, D02, D01, Mock→Real 전환 | ETL 적재 완료, UX 개선 완료, Docker 통합 완료, QA P0+P1 수정 완료 | **~95%** |
| **Phase 2** (Premium) | F04, Tier 게이팅 | Tool 코드만 존재, 인증/결제 미착수 | **~15%** |
| **Phase 3** (확장) | F06, F09, F10 | 미착수 | **0%** |

---

## 2. 스펙 대비 구현 상세 검토

### 2.1 Backend — 아키텍처 정합성: **87%**

| 항목 | 스펙 | 실제 | 판정 |
|------|------|------|------|
| 디렉토리 구조 | `server/api/routes/`, `agent/`, `data/`, `models/`, `services/` | 거의 일치, `nodes/` 미분리, `repositories/` 없음 | ✅ 허용 범위 |
| Agent Tools | 9종 (spec) | **7종 구현**, `simulate_revenue`, `update_map_view` 미구현 | ⚠️ Phase 3 항목이라 OK |
| SSE 이벤트 | 7종 (thinking/tool/text/card/map_cmd/suggestion/done) | 7종 + `tool_end` 추가 | ✅ 스펙 초과 |
| ReAct 루프 | 최대 5회 | `MAX_ITERATIONS = 5`, `recursion_limit = 11` | ✅ 정확 |
| API 엔드포인트 | 6개 | **4개 구현**, `/api/map-data/heatmap`, `/api/reports/export` 없음 | ⚠️ Phase 3 |
| LLM 지원 | Claude API | Claude + Gemini 듀얼 지원 | ✅ 스펙 초과 |
| 캐시 | Redis TTL 24h | Redis + 메모리 fallback, TTL 24h | ✅ 정확 |
| Langfuse | 통합 필수 | config 설정만 존재, 실제 wiring 안 됨 | ⚠️ 미완 |

### 2.2 Frontend — 아키텍처 정합성: **95%**

| 항목 | 스펙 | 실제 | 판정 |
|------|------|------|------|
| SplitPanel | 60/40, resizable | 30~80% 범위 드래그 가능 | ✅ 개선 |
| Kakao Map | 폴리곤 오버레이 + 클릭/호버 | 프록시 로딩 + 폴리곤 인터랙션 완벽 | ✅ |
| Card UI 4종 | Summary, Compare, Recommend, Risk | 전부 구현 + InlineChart | ✅ |
| SSE 스트리밍 | EventSource | `Response.body.getReader()` (POST 지원) | ✅ 개선 |
| Zustand 3개 스토어 | map/chat/district | 전부 구현, 양방향 동기화 | ✅ |
| 다크 테마 | (추가 요구) | CSS 변수 12개+ 정의, 주요 컴포넌트 적용 | ✅ |
| `useDistrict` 훅 | 스펙에 명시 | 미구현 (store 직접 사용) | ✅ 실용적 판단 |
| Phase 3 컴포넌트 | HeatmapLayer, TimeSlider, SimulationCard, ReportExport | 미구현 (예정대로) | ⬜ 해당 없음 |

### 2.3 데이터 파이프라인 — 정합성: **80%**

| 항목 | 스펙 (D01) | 실제 | 판정 |
|------|-----------|------|------|
| 서울 열린데이터 | 4개 서비스 수집 | 4개 완료 (districts, floating_pop, sales, stores) | ✅ |
| data.go.kr | 점포 정보/이력 | **config만 존재, 코드 미구현** | ❌ 누락 |
| ETL Transform | 좌표변환, 시간대 unpivot, 성별/연령 변환 | 전부 구현 | ✅ |
| UPSERT | district_code + quarter 복합키 | `ON CONFLICT DO UPDATE` 구현 | ✅ |
| Celery 스케줄러 | 분기별 자동 실행 | CLI runner만 있음, **Celery 미구현** | ⚠️ |
| 적재 현황 | 5개 테이블 | districts 1,650 / fp 9,888 / sales 21,333 / stores 75,985 / res_pop 19,692 | ✅ |
| 미승인 API | 폴리곤(boundary), 상주인구, 점포상세 | 여전히 미승인 → **districts에 boundary NULL** | ⚠️ 블로커 |

### 2.4 비즈니스 모델 (B01) — 구현률: **0%**

| 항목 | 스펙 | 실제 | 판정 |
|------|------|------|------|
| OAuth2 (Google/Kakao) | 필수 | 미구현 | ❌ Phase 2 |
| users/subscriptions 테이블 | 필수 | 미구현 | ❌ Phase 2 |
| Free 일 5회 제한 | 필수 | 미구현 | ❌ Phase 2 |
| Tier 미들웨어 | 필수 | 미구현 | ❌ Phase 2 |
| 결제 연동 | Toss Payments | 미구현 | ❌ Phase 2 |

---

## 3. 스펙별 수용 기준(Acceptance Criteria) 충족도

### F01 지도 선택 — **6/7 충족**
- ✅ 카카오맵 초기화 (서울 중심)
- ✅ 폴리곤 렌더링 + 클릭 이벤트
- ✅ 검색 자동완성 (Mock)
- ✅ 선택 시 지도 중심 이동
- ✅ StatusBar 선택 상권 표시
- ⚠️ 서울 외 선택 안내 메시지 — **미확인**
- ❌ 뷰포트 기반 폴리곤 로딩 — **Real 모드에서 boundary NULL이라 불가**

### F02 AI 챗봇 — **7/8 충족**
- ✅ 자연어 → 적절한 Tool 선택
- ✅ SSE 스트리밍 실시간 표시
- ✅ thinking 상태 UI 표시
- ✅ 대화 컨텍스트 유지
- ✅ 상권 선택 시 자동 요약
- ✅ map_cmd → 지도 반영
- ✅ ReAct 5회 제한
- ⚠️ Langfuse 트레이싱 — **설정만 존재, 실동작 안 함**

### F03 기본 리포트 — **6/8 충족**
- ✅ 상권 선택 시 자동 생성
- ✅ 6개 지표 표시
- ✅ 미니 차트 렌더링
- ✅ 상태 뱃지 표시
- ⚠️ 데이터 기준 분기 — Mock에서는 "2025Q3 (샘플)" 표시
- ✅ 추천 질문 칩
- ⚠️ 첫 응답 3초 이내 — **E2E에서 타이밍 검증 안 함**
- ⚠️ 캐시된 상권 즉시 반환 — **Redis Mock fallback은 메모리 캐시**

### F05 상권 비교 — **4/6 충족**
- ✅ 챗봇 비교 동작
- ✅ CompareCard 비교표 렌더링
- ✅ AI 종합 의견 데이터 기반
- ✅ 최대 3개 제한
- ❌ 비교 모드 UI에서 지도 복수 하이라이트 — **미구현**
- ⚠️ 서로 다른 색상 — **미구현**

### F07 업종 추천 — **5/6 충족**
- ✅ "뭐 하면 좋을까?" → Top 5
- ✅ 점수 + 추천 근거
- ✅ 점수 공식 적용
- ⚠️ 예산 조건 필터 — **Mock에서만, Real DB 미검증**
- ✅ 면책 조항 표시
- ⚠️ "더 분석" → F04 연결 — **F04 미구현**

### F08 이력/리스크 — **5/6 충족**
- ✅ "이 자리 위험해?" → RiskCard
- ✅ 안정성 점수 0-100
- ✅ 업종별 생존기간 바 차트
- ✅ 위험 업종 경고
- ✅ 분기별 개폐업 추이
- ⚠️ "안전한 업종 추천" → F07 연결 — **UI 링크 미확인**

---

## 4. 발견된 주요 이슈

### 🔴 Critical (즉시 해결 필요)

| # | 이슈 | 영향 |
|---|------|------|
| C1 | **districts boundary NULL** — 폴리곤 API 미승인으로 Real 모드에서 지도에 상권 표시 불가 | Real 모드 F01 불가 |
| C2 | **`district_summary.py` Real DB 미지원** — Mock만 사용, 핵심 Tool인데 DB 분기 없음 | Real 모드 F03 불가 |
| C3 | **Card UI 다크 테마 미적용** — 4종 Card에 `bg-white`, `text-gray-700` 하드코딩 | 시각적 불일치 |

### 🟡 Medium (개선 필요)

| # | 이슈 | 영향 |
|---|------|------|
| M1 | **data.go.kr 미연동** — 점포 이력(store_history) 실데이터 없음 | F08 Real 모드 불완전 |
| M2 | **Backend 테스트 0개** — pytest 파일 없음 | 코드 품질/회귀 방지 부재 |
| M3 | **Langfuse 미연결** — config만 있고 agent 실행에 callback 주입 안 됨 | 운영 관측성 없음 |
| M4 | **Celery 미구현** — ETL CLI만 있고 자동 스케줄러 없음 | 수동 ETL만 가능 |
| M5 | **비교 모드 지도 하이라이트** — 복수 상권 색상 구분 미구현 | F05 UX 불완전 |

### 🟢 Low (Phase 2~3에서 해결)

| # | 이슈 | 비고 |
|---|------|------|
| L1 | `simulate_revenue` Tool 미구현 | Phase 3 (F09) |
| L2 | `update_map_view` Tool 미구현 | map_cmd로 대체 중 |
| L3 | Heatmap API/컴포넌트 없음 | Phase 3 (F06) |
| L4 | PDF export 없음 | Phase 3 (F10) |
| L5 | Rate Limiting 없음 | Phase 2 보안 |
| L6 | category_metadata 시드 데이터 없음 | F04/F07 정확도 |

---

## 5. 개선이 필요한 부분 및 해결책

### 5.1 Real 모드 전환이 "반쪽" 상태

**문제**: boundary NULL + district_summary Mock only → Real 모드에서 F01(지도), F03(요약) 불가

**해결책**:

**A) districts boundary NULL (C1)**
- **단기 (API 승인 전)**: 서울 열린데이터의 이미 승인된 `VwsmTrdarFlpopQq`에서 `XCNTS_VALUE`/`YDNTS_VALUE` 좌표를 활용하여 상권 중심점(center_point)만이라도 적재. 폴리곤 대신 원형 마커(Circle Overlay)로 상권 표시하는 대체 UI 구현
- **중기 (API 승인 후)**: `VwsmTrdarSelngW` 승인 → ETL에서 boundary POLYGON 적재 → DistrictLayer 폴리곤 렌더링 복원
- **실행 순서**:
  1. `seoul_opendata.py`에 중심점 추출 로직 추가 (1일)
  2. `DistrictLayer.tsx`에 Circle fallback 렌더링 추가 (0.5일)
  3. API 승인 신청 재요청 (외부 대기)

**B) district_summary.py Real DB 미지원 (C2)**
- 다른 7개 Tool과 동일한 패턴으로 `settings.use_mock` 분기 추가
- Real 경로에서 `floating_population`, `estimated_sales`, `stores`, `resident_population` 4개 테이블을 집계 쿼리로 조합
- **실행**: 기존 Tool(`floating_population.py` 등)의 Real DB 쿼리를 참조하여 동일 패턴 적용 (0.5일)

---

### 5.2 Backend 테스트 부재

**문제**: pytest 파일 0개 — Tool 로직, API 엔드포인트, ETL 변환에 대한 자동 검증 없음

**해결책**:

```
server/tests/
├── conftest.py                  # DB fixture (mock session), test client
├── test_tools/
│   ├── test_floating_population.py   # Mock/Real 분기 각각 테스트
│   ├── test_estimated_sales.py
│   ├── test_store_info.py
│   ├── test_compare_districts.py
│   ├── test_recommend_business.py
│   └── test_store_history.py
├── test_api/
│   ├── test_chat.py             # SSE 이벤트 순서/포맷 검증
│   ├── test_districts.py        # 검색, 필터, GeoJSON 반환
│   └── test_map_data.py         # 폴리곤 엔드포인트
└── test_etl/
    ├── test_transformers.py     # 좌표변환, unpivot 순수함수 테스트
    └── test_loader.py           # UPSERT 멱등성 검증
```

- **우선순위**: `test_tools/` → `test_api/` → `test_etl/` 순서
- Mock 모드 테스트는 DB 불필요하므로 CI에서도 즉시 실행 가능
- **목표 커버리지**: Tool 함수 80%+, API 엔드포인트 100%
- **실행**: conftest.py + Tool 테스트 6개 작성 (1~2일)

---

### 5.3 Langfuse 미연결

**문제**: config에 키만 설정, agent 실행 시 callback 주입 안 됨 → LLM 호출 트레이싱/비용 추적 불가

**해결책**:

- `graph.py`의 `create_agent()` 또는 `astream_events()` 호출부에 Langfuse callback 주입:
  ```python
  from langfuse.callback import CallbackHandler as LangfuseHandler

  langfuse_handler = LangfuseHandler(
      public_key=settings.langfuse_public_key,
      secret_key=settings.langfuse_secret_key,
      host=settings.langfuse_host,
  )
  # agent.astream_events(..., config={"callbacks": [langfuse_handler]})
  ```
- Docker Compose의 Langfuse 서비스는 이미 정의되어 있으므로 `docker compose up langfuse` 후 연결
- **조건부 활성화**: `LANGFUSE_PUBLIC_KEY`가 비어있으면 callback 생략 (개발 환경 호환)
- **실행**: graph.py 수정 1곳 + 환경변수 확인 (0.5일)

---

### 5.4 Celery 스케줄러 미구현

**문제**: ETL이 CLI 수동 실행만 가능, 분기별 자동 갱신 불가

**해결책**:

- **단기**: 현재 CLI runner(`python -m server.data.etl.runner run 2025Q4`)를 cron job 또는 GitHub Actions scheduled workflow로 감싸기
  ```yaml
  # .github/workflows/etl-quarterly.yml
  on:
    schedule:
      - cron: '0 3 1 1,4,7,10 *'  # 1/1, 4/1, 7/1, 10/1 새벽 3시
    workflow_dispatch:              # 수동 트리거도 가능
  ```
- **중기**: Celery Beat + Redis broker 구성 (D01 스펙 원안)
  - `docker-compose.yml`에 celery worker/beat 서비스 추가
  - `server/data/etl/tasks.py`에 `@shared_task` 래핑
- **판단**: MVP 단계에서는 GitHub Actions cron이 더 실용적 (인프라 추가 없음)
- **실행**: GitHub Actions workflow 작성 (0.5일) 또는 Celery 구성 (1~2일)

---

### 5.5 data.go.kr 미연동

**문제**: `store_history` 테이블에 실데이터 없음 → F08 리스크 분석이 Real 모드에서 빈 결과

**해결책**:

- `server/data/etl/data_go_kr.py` 수집 모듈 신규 작성
  - API: 소상공인시장진흥공단 상가(상권)정보 조회 서비스
  - 필요 데이터: 개업일, 폐업일, 업종코드, 주소 → `store_history` 매핑
- **대안 (API 승인 대기 중)**: 서울 열린데이터 `VwsmTrdarStorQq`에서 분기별 개폐업 수를 `store_history`에 집계 형태로 적재 (개별 점포 이력은 아니지만 리스크 분석은 가능)
- **실행**: 대안 적재 로직 (1일) 또는 data.go.kr 신규 모듈 (2~3일)

---

### 5.6 Card UI 다크 테마 미적용

**문제**: SummaryCard, CompareCard, RecommendCard, RiskCard에 `bg-white`, `text-gray-700` 등 하드코딩

**해결책**:

- 4개 Card 컴포넌트에서 라이트 모드 색상을 CSS 변수로 교체:
  | 기존 | 교체 |
  |------|------|
  | `bg-white` | `style={{ background: 'var(--bg-secondary)' }}` |
  | `text-gray-700` | `style={{ color: 'var(--text-primary)' }}` |
  | `text-gray-500` | `style={{ color: 'var(--text-secondary)' }}` |
  | `border-gray-200` | `style={{ borderColor: 'var(--border-color)' }}` |
  | `bg-gray-50` | `style={{ background: 'var(--bg-tertiary)' }}` |
- 각 컴포넌트 ~20줄 수정, 기존 `globals.css`의 `:root` 변수 활용
- **실행**: 4개 파일 일괄 수정 (0.5일)

---

### 5.7 비교 모드 복수 하이라이트 미구현

**문제**: F05 비교 시 지도에 2~3개 상권을 서로 다른 색상으로 하이라이트해야 하지만 미구현

**해결책**:

- `DistrictLayer.tsx`에서 `districtStore.compareList` 참조
- 비교 목록 상권에 색상 배열 적용: `['#3B82F6', '#EF4444', '#10B981']` (파랑/빨강/초록)
- 비교 모드 진입 시 `map_cmd`로 `fitBounds` 호출하여 모든 비교 상권이 뷰포트에 보이도록 조정
- `CompareCard`의 각 상권명 옆에 동일 색상 인디케이터 표시 (일관성)
- **실행**: DistrictLayer 수정 + CompareCard 색상 매칭 (1일)

---

## 6. 실행 우선순위 로드맵

### Phase 1B 마무리 (즉시 ~ 1주)

| 순서 | 작업 | 이슈 ID | 예상 소요 | 의존성 |
|------|------|---------|-----------|--------|
| 1 | Card UI 다크 테마 교체 | C3 | 0.5일 | 없음 |
| 2 | .gitignore 정리 | - | 5분 | 없음 |
| 3 | `district_summary.py` Real DB 지원 | C2 | 0.5일 | 없음 |
| 4 | 중심점 기반 대체 UI (Circle fallback) | C1 단기 | 1.5일 | 없음 |
| 5 | Backend pytest 기본 테스트 | M2 | 1~2일 | 없음 |
| 6 | Langfuse callback 주입 | M3 | 0.5일 | Docker langfuse up |

### Phase 1B+ 보강 (1~2주)

| 순서 | 작업 | 이슈 ID | 예상 소요 | 의존성 |
|------|------|---------|-----------|--------|
| 7 | 비교 모드 복수 하이라이트 | M5 | 1일 | 없음 |
| 8 | store_history 집계 적재 (대안) | M1 | 1일 | DB 접근 |
| 9 | GitHub Actions ETL cron | M4 | 0.5일 | ETL runner 동작 확인 |
| 10 | 미승인 API 재신청 + boundary ETL | C1 중기 | 외부 대기 | API 승인 |

### Phase 2 착수 (2주~)

| 순서 | 작업 | 이슈 ID | 예상 소요 | 의존성 |
|------|------|---------|-----------|--------|
| 11 | OAuth2 (Google/Kakao) + users 테이블 | B01 | 3~4일 | 없음 |
| 12 | Tier 미들웨어 + Free 5회 제한 | B01 | 2일 | #11 |
| 13 | category_metadata 시드 데이터 | L6 | 1일 | 없음 |
| 14 | F04 업종 심층 분석 완성 | - | 2일 | #13 |
| 15 | Rate Limiting 미들웨어 | L5 | 0.5일 | 없음 |

---

## 7. 종합 평가

### 잘 진행된 부분
- **Phase 1A Mock E2E가 완벽하게 동작** — 설계 의도대로 DB 없이 전체 흐름 검증 완료
- **SSE 스트리밍 + Agent Progress UX** — 스펙보다 우수한 UX (tool_end 이벤트, 이모지 단계 표시)
- **E2E 테스트 32개 PASS** — 핵심 시나리오 자동화 검증 확보
- **ETL 파이프라인** — 서울 열린데이터 4개 서비스 12만+ 행 적재 성공
- **Mock/Real 전환 메커니즘** — `USE_MOCK` 플래그로 깔끔한 분기
- **듀얼 LLM 지원** — 스펙에 없던 Gemini fallback까지 구현

### 개선이 필요한 부분 (위 5장에서 해결책 포함)
- **Real 모드 전환이 "반쪽"** — boundary NULL + district_summary Mock only → 5.1에서 단기/중기 해결책 제시
- **Backend 테스트 부재** — pytest 0개 → 5.2에서 테스트 구조 및 우선순위 제시
- **Langfuse/Celery 등 운영 인프라 미완** — 5.3, 5.4에서 각각 해결책 제시
- **data.go.kr 미연동** — 5.5에서 대안 적재 방안 제시
- **UI 일관성 (다크 테마, 비교 하이라이트)** — 5.6, 5.7에서 구체적 수정 방안 제시

### 결론

전체적으로 **설계 대비 Phase 1A/1B 수준에서 잘 진행**되고 있습니다. 핵심 아키텍처(ReAct Agent + SSE + Card UI + Mock/Real 전환)가 안정적으로 동작하며, E2E 테스트로 회귀 방지도 확보되어 있습니다.

다음 관건은:
1. **Real 모드 완성** (boundary + district_summary) — 1B 마무리의 핵심
2. **Backend 테스트 확보** — 안정적 확장의 기반
3. **Phase 2 Tier 게이팅** — 수익화 경로 확보

6장의 실행 로드맵 순서대로 진행하면 약 2~3주 내에 Phase 1B 완전 마무리 + Phase 2 착수가 가능합니다.

---

## 참고 문서

| 문서 | 경로 |
|------|------|
| 전체 아키텍처 | `docs/architecture/overall-architecture.md` |
| 기능 목록 | `docs/spec/feature-list.md` |
| 체크리스트 | `docs/spec/checklist.md` |
| F01 지도 선택 | `docs/spec/features/F01-map-district-selection.md` |
| F02 AI 챗봇 | `docs/spec/features/F02-ai-chatbot-agent.md` |
| F03 기본 리포트 | `docs/spec/features/F03-basic-report.md` |
| F05 상권 비교 | `docs/spec/features/F05-district-comparison.md` |
| F07 업종 추천 | `docs/spec/features/F07-business-recommendation.md` |
| F08 이력/리스크 | `docs/spec/features/F08-store-history-risk.md` |
| D01 데이터 파이프라인 | `docs/spec/data/D01-data-pipeline.md` |
| B01 비즈니스 모델 | `docs/spec/business/B01-business-model.md` |
| Phase 1B 계획 | `docs/plan/phase/phase-1b-implementation.md` |
| 진행 상황 (운영) | `docs/status/current-status.md` |
