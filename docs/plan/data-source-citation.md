# 데이터 출처 표시 기능 구현 계획

> 작성일: 2026-04-02
> 목적: 상권분석 Card에 데이터 출처(기관명, 데이터셋, 라이선스) 표시
> 원칙: 간결한 1줄 기본 표시 + 클릭 시 상세 펼침 (공간 최소 사용)

---

## Context

사용자가 상권분석 결과를 볼 때 데이터가 어디서 왔는지 전혀 알 수 없음. 현재 Card footer에 "데이터 기준: 2025Q4"만 표시.
출처 기관명, 데이터셋명, 라이선스 정보가 없어 **신뢰성 부족 + 공공데이터 이용 시 출처 표시 의무 미충족**.

### 현재 데이터 소스 (ETL 확인)

| 데이터 | 출처 기관 | API/데이터셋 | 서비스명 |
|--------|----------|-------------|---------|
| 유동인구 | 서울특별시 | VwsmTrdarFlpopQq | ��권분석서비스(��권-유동인구) |
| 추정매출 | 서울특별시 | VwsmTrdarSelngQq | 상권분석서비스(상권-추정매출) |
| 점포 현황 | 서울특별시 | VwsmTrdarStorW/Qq | 상권분석서비스(상권-점포) |
| 상주인구 | 서울특별시 | CSV OA-15584 | 상권분석서비스(상권-상주인구) |
| 직장인구 | 서울특별시 | VwsmTrdarWrcPopltnQq | 상권분석서비스(상권-직장인구) |
| 상권 폴리곤 | 서울특별시 | SHP OA-15560 | 상권분석서비스(상권영역) |

### 현재 상태: 출처 표시 없���

| Card | footer 내용 | 출처 표시 |
|------|------------|----------|
| SummaryCard | `데이터 기준: 2025Q4` | 없음 |
| CompareCard | `데이터 기준: 2025Q4` | 없음 |
| RecommendCard | `데이터 기준: 2025Q4 · 분석 업종 N개` + 면책 | 없음 |
| RiskCard | `데이터 기준: 2025Q4 · N분기 분석` | 없음 |

---

## UX 설계

### 원칙
- **간결함**: 기본 ��태에서 1줄만 사용 (현재 footer와 동일 공간)
- **신뢰감**: 출처 기���명이 한눈에 보여 "공공데이터 기반"임�� 바로 인지
- **상세 on-demand**: 클릭하면 ��이터셋 목록/라이선스/링�� 확인 가능
- **일관성**: 4개 Card 모두 동일한 SourcesCitation 컴포넌트 사용

### Collapsed (기본 - 1줄)
```
데이터 기준: 2025Q4  ·  출처: 서울 열린데이터광장 (3)  ▼
```
- `(3)` = 이 카드에 사용된 데이터셋 수
- `▼` = 클릭하면 상��� ���침

### Expanded (클릭 시)
```
데이터 기준: 2025Q4  ·  출처: 서울 열린데이터광장 (3)  ▲
  ├ 상권-유동인구 (VwsmTrdarFlpopQq)
  ├ 상권-추정매출 (VwsmTrdarSelngQq)
  └ 상권-점포 (VwsmTrdarStorW)
  서울특별시 · 공공누리 제1유형
  data.seoul.go.kr
```

### Mock 모드
```
데이터 기준: 2025Q3 (샘플)  ·  출처: 샘플 데이터
```
- 펼침 버튼 없음 (의미 없음)

---

## 파이프라인 설계

```
[data_sources.py]  정적 레지스트리: Tool명 -> DataSource 목록
        |
        |---> [district_summary.py]  result dict에 dataSources 필드 추가
        |
        +---> [graph.py on_tool_end]  card SSE 이벤트에 dataSources 주입
                    |
                    v
            [SSE card event]  { type:"card", card_type:"...", data: {..., dataSources:[...]} }
                    |
                    v
            [chatStore.ts]  cardData에 dataSources 포함하여 ChatMessage 저장
                    |
                    v
            [MessageBubble -> Card 컴포넌트]
                    |
                    v
            [SourcesCitation]  footer에서 출처 표시 (collapsed/expanded)
```

**핵심 설계 ��정: 정적 매핑**
- 각 Tool은 항상 동일한 데이터 테이블을 쿼리 -> 동일한 출처
- DB에 per-row source 컬럼 불필요 (오버엔지니어링)
- `data_sources.py`에서 Tool명 -> 출처 목록을 상수로 관리
- 새 데이터 소스 추가 시 이 파일만 수정

---

## 체크리스트

### Step 1: Backend - 출처 레지스트리 (신규 파일, 의존성 없음)

- [ ] `server/server/agent/tools/data_sources.py` 생성
  - [ ] `DataSource` dataclass 정의 (id, name, organization, platform, api_endpoint, url, license, collection_method)
  - [ ] `to_dict()` 메서드 (JSON 직렬화용)
  - [ ] 6개 Seoul Open Data 소스 상수 정의:
    - `SEOUL_FLOATING_POP` - VwsmTrdarFlpopQq
    - `SEOUL_ESTIMATED_SALES` - VwsmTrdarSelngQq
    - `SEOUL_STORE_INFO` - VwsmTrdarStorW
    - `SEOUL_RESIDENT_POP` - OA-15584 (CSV)
    - `SEOUL_WORKER_POP` - VwsmTrdarWrcPopltnQq
    - `SEOUL_DISTRICT_POLYGON` - OA-15560 (SHP)
  - [ ] `MOCK_SOURCE` 상수 (id="mock", name="샘플 데이터")
  - [ ] `TOOL_SOURCES` 매핑:
    ```python
    {
      "get_floating_population": [SEOUL_FLOATING_POP],
      "get_estimated_sales": [SEOUL_ESTIMATED_SALES],
      "get_store_info": [SEOUL_STORE_INFO],
      "get_population_info": [SEOUL_RESIDENT_POP, SEOUL_WORKER_POP],
      "get_store_history": [SEOUL_STORE_INFO],
      "get_district_summary": [SEOUL_FLOATING_POP, SEOUL_ESTIMATED_SALES, SEOUL_STORE_INFO],
      "compare_districts": [SEOUL_FLOATING_POP, SEOUL_ESTIMATED_SALES, SEOUL_STORE_INFO],
      "recommend_business": [SEOUL_ESTIMATED_SALES, SEOUL_STORE_INFO, SEOUL_FLOATING_POP],
    }
    ```
  - [ ] `get_sources_for_tool(tool_name) -> list[dict]` 함수 (use_mock 시 MOCK_SOURCE 반���)

**수정 파일**: 없음 (신규만)
**���증**: import 후 각 tool명으로 호출 -> 올바른 source list 반환 확인

### Step 2: Backend - Tool 응답에 출처 주입 (Step 1 의존)

- [ ] `server/server/agent/tools/district_summary.py` 수정
  - [ ] `get_sources_for_tool("get_district_summary")` import
  - [ ] result dict에 `"dataSources": get_sources_for_tool("get_district_summary")` 추가 (line ~148)
- [ ] `server/server/agent/graph.py` 수정
  - [ ] `on_tool_end` 블록 (lines 295-313)에서 card_data 생성 후 dataSources 주입:
    ```python
    base_name = tool_name.replace("_tool", "")
    card_data["dataSources"] = get_sources_for_tool(base_name)
    ```
  - [ ] 대상 카드: compare, recommend, risk (summary는 district_summary.py에서 직접)

**수정 파일**: `district_summary.py`, `graph.py`
**검증**: 채팅 요청 -> SSE card 이벤트 JSON에 dataSources 배열 포함 확인

### Step 3: Frontend - TypeScript ����� (의존성 없음)

- [ ] `frontend/src/lib/types.ts` 수정
  - [ ] `DataSourceInfo` 인터페이스 추가
  - [ ] `SummaryCardData`에 `dataSources?: DataSourceInfo[]` 추가
  - [ ] `CompareCardData`에 `dataSources?: DataSourceInfo[]` 추가
  - [ ] `RecommendCardData`에 `dataSources?: DataSourceInfo[]` 추가
  - [ ] `RiskCardData`에 `dataSources?: DataSourceInfo[]` 추가

**수정 파일**: `types.ts`

### Step 4: Frontend - SourcesCitation 컴포넌트 (Step 3 의존)

- [ ] `frontend/src/components/chat/cards/SourcesCitation.tsx` 생성
  - [ ] Props: `sources?: DataSourceInfo[]`, `quarter?: string`, `extraFooterText?: string`
  - [ ] `useState(false)` - expanded 상태 관리
  - [ ] Mock 감지: `sources?.length === 1 && sources[0].id === 'mock'`
  - [ ] Collapsed 렌더링: 기존 quarter + 출처 badge + 쉐브론
  - [ ] Expanded 렌더링: 트리 마커로 데이터셋 목록 + 기관/라이선스 + 링크
  - [ ] `extraFooterText` 렌더링 (면책/분석 수 등)
  - [ ] 스타일: 기존 CSS 변수만 사용

**신규 파일**: `SourcesCitation.tsx`

### Step 5: Frontend - 4개 Card에 적용 (Step 4 의존)

- [ ] `SummaryCard.tsx` 수정 (lines 143-148): footer -> SourcesCitation
- [ ] `CompareCard.tsx` 수정 (lines 150-155): footer -> SourcesCitation
- [ ] `RecommendCard.tsx` 수정 (lines 99-107): footer -> SourcesCitation + extraFooterText
- [ ] `RiskCard.tsx` 수정 (lines 184-191): footer -> SourcesCitation + extraFooterText

**수정 파일**: 4개 Card 컴포넌트

### Step 6: E2E 검증

- [ ] Mock 모드: 4개 Card footer에 출처 표시 확인
- [ ] 펼침/접기 동작 확인 (각 Card 독립)
- [ ] 기존 E2E 테스트 (7 specs) 회귀 통과

---

## Scenario Tests (10점 만점, 10점만 통과)

### S1: SummaryCard 출처 정확성

| # | 체크 항목 | 배점 |
|---|----------|------|
| 1 | Collapsed에 "출처: 서울 열린데이터광장 (3)" 표시 | 1 |
| 2 | source count(3) = 유동인구+매출+점포 | 1 |
| 3 | Expanded 시 3개 데이터셋 항목 표시 | 1 |
| 4 | 각 항목 서비스 약칭 정확 (상권-유동인구, 상권-추정매출, 상권-점포) | 1 |
| 5 | 각 항목 API 엔드포인트 코드 정확 | 1 |
| 6 | 기관명 "서울특별시" 표시 | 1 |
| 7 | 라이선스 "공공누리 제1유형" 표시 | 1 |
| 8 | data.seoul.go.kr 링크 새 탭 열림 | 1 |
| 9 | 데이터 기준 분��� 텍스트 정확 유지 | 1 |
| 10 | 펼침/접힘 시 카드 리렌더/스크롤 이탈 없음 | 1 |

### S2: CompareCard 출처 정확성

| # | 체크 항목 | 배점 |
|---|----------|------|
| 1 | Footer에 출��� citation collapsed 표시 | 1 |
| 2 | Source count = 3 (유동인구+매출+점포) | 1 |
| 3 | 중복 소스 없음 (deduplicated) | 1 |
| 4 | 비교표 데이터 영향 없음 | 1 |
| 5 | quarter가 district 데이터에서 정확히 추출 | 1 |
| 6 | Expanded에 트리 마커 정렬 | 1 |
| 7 | AI 종합 의견 섹션 위치 밀림 없음 | 1 |
| 8 | Footer 영역 내 layout overflow 없음 | 1 |
| 9 | 접기 애니메이션 부드러움 | 1 |
| 10 | 동일 페이지 내 여러 Card 독립 펼침/접힘 | 1 |

### S3: RecommendCard 기존 footer 보존

| # | 체크 항목 | 배점 |
|---|----------|------|
| 1 | "분석 업종 N개" 텍스트 유지 | 1 |
| 2 | 면책 "추정치이며..." 텍스트 유지 | 1 |
| 3 | 출처 badge가 데이터 기준과 같은 줄에 표시 | 1 |
| 4 | Source count 정확 (3: 매출+점포+유동인구) | 1 |
| 5 | Expanded 소스가 면책 텍스트와 겹치지 않음 | 1 |
| 6 | extraFooterText가 소스 상세 아래에 렌더 | 1 |
| 7 | 점수바/추천 항목 영향 없음 | 1 |
| 8 | Footer 배경색 var(--bg-tertiary) 일치 | 1 |
| 9 | 폰트 크기 text-xs ��관 | 1 |
| 10 | 모바일 뷰포트(320px)에서 레이아웃 정상 | 1 |

### S4: RiskCard 기존 footer 보존

| # | 체크 항목 | 배점 |
|---|----------|------|
| 1 | "N분기 분석" 텍스트 유지 (quarters_analyzed > 0) | 1 |
| 2 | 출처 source가 점포 데이���셋 정확 | 1 |
| 3 | 안정��� 게이지 렌더링 영향 없음 | 1 |
| 4 | 생존기간 바 차트 영향 없음 | 1 |
| 5 | 분기별 추이 차트가 footer 위에 정상 렌더 | 1 |
| 6 | Expanded 소스가 quarter 라인 아래 표시 | 1 |
| 7 | Footer border-top 일관성 | 1 |
| 8 | quarters_analyzed=0일 때 extra text 미표시 | 1 |
| 9 | Collapsed로 돌아갈 때 1줄 높이 복귀 | 1 |
| 10 | 토글 시 layout shift/jump 없음 | 1 |

### S5: Mock 모드 출처 표시

| # | 체크 항목 | 배점 |
|---|----------|------|
| 1 | USE_MOCK=true: dataSources에 MOCK_SOURCE 1건 | 1 |
| 2 | "출처: 샘플 데이터" 렌더링 | 1 |
| 3 | 펼침 쉐브론 버튼 미표시 | 1 |
| 4 | quarter에 "(샘플)" 접미사 표시 | 1 |
| 5 | USE_MOCK=false: 실제 소스 엔트리 표시 | 1 |
| 6 | mock source id="mock" 프로그래밍 감지 가능 | 1 |
| 7 | 4개 Card 모두 mock source 정상 ���시 | 1 |
| 8 | 콘솔 에�� 없음 | 1 |
| 9 | Mock footer 크기 = Real footer 크기 (collapsed) | 1 |
| 10 | dataSources 미존재(undefined) 시 기존 footer 그대로 렌더 (하위 호환) | 1 |

### S6: 펼침/접힘 인터랙션

| # | 체크 항목 | 배점 |
|---|----------|------|
| 1 | 쉐브론 클릭으로 toggle 동작 | 1 |
| 2 | 쉐브론 방향 전환 (▼/▲) | 1 |
| 3 | Expanded 영역 animate-step-in 적용 | 1 |
| 4 | Collapsed 시 부드럽게 숨김 | 1 |
| 5 | 쉐브론/버튼 외 영역 클릭 시 toggle 안 됨 | 1 |
| 6 | 여러 Card 독립 expand/collapse | 1 |
| 7 | 채팅 하단 Card 펼침 시 스크롤 유지 | 1 |
| 8 | 키보드 접근성: Tab->Enter로 토글 가능 | 1 |
| 9 | 새 Card 메시지 도착 시 기존 Card 상태 유지 | 1 |
| 10 | 토글 시 부모 Card 불필�� 리렌더 없음 | 1 |

### S7: SSE 파이프라인 무결성

| # | 체크 항목 | 배점 |
|---|----------|------|
| 1 | SSE card 이벤트 JSON에 dataSources 필드 포함 | 1 |
| 2 | dataSources가 올바른 shape의 객체 배열 | 1 |
| 3 | 각 source 객체에 필수 6개 필드 존재 (id, name, organization, platform, url, license) | 1 |
| 4 | chatStore가 cardData(dataSources 포함)를 ChatMessage에 정확히 전달 | 1 |
| 5 | MessageBubble이 cardData를 Card 컴포넌트에 전달 | 1 |
| 6 | Card 컴포넌트가 dataSources를 props에서 읽음 | 1 |
| 7 | dataSources 없는 기존 캐시 데이터에서도 footer 정상 렌더 (하위 호환) | 1 |
| 8 | SSE 직렬화 시 한국어 정상 처리 (ensure_ascii=False) | 1 |
| 9 | dataSources 추가로 인한 SSE 이벤트 크기 증��� < 500 bytes | 1 |
| 10 | district_summary (chat.py 직접 emit)와 graph.py (on_tool_end) 모두 dataSources 포함 | 1 |

### S8: 하위 호환성

| # | 체크 항목 | 배점 |
|---|----------|------|
| 1 | dataSources 없는 Card (구 캐시) footer 정상 렌더 | 1 |
| 2 | TypeScript에서 dataSources는 optional(?) | 1 |
| 3 | SourcesCitation에 sources=undefined -> 출처 없이 기존 footer만 표시 | 1 |
| 4 | SourcesCitation에 sources=[] -> 출처 없이 기존 footer만 표시 | 1 |
| 5 | 기존 E2E 테스트 7 specs 전부 통과 | 1 |
| 6 | TypeScript 컴파일 에러 0건 (tsc --noEmit) | 1 |
| 7 | 기존 SSE 이벤트 타입 변경 없음 | 1 |
| 8 | chatStore가 dataSources 유무 모두 처리 | 1 |
| 9 | Redis 캐시 무효화 불필요 (additive field) | 1 |
| 10 | `npm run build` 성��� | 1 |

### S9: 법적 준수 (공공데이터 출처 표시 의무)

| # | 체크 항목 | 배점 |
|---|----------|------|
| 1 | 제공기관 "서울특별시" 표시 | 1 |
| 2 | 데이터셋 서비스명 식별 ���능 | 1 |
| 3 | 이용허락 유형 "공공누리 제1유형" 표시 | 1 |
| 4 | 출처 플랫폼 URL 접근 가능 | 1 |
| 5 | 기본 상태(collapsed)에서 출처 기관 확인 가능 | 1 |
| 6 | 상세 정보 on-demand 확인 가능 (expanded) | 1 |
| 7 | 공공데이터 사용하는 모든 Card에 출처 부착 | 1 |
| 8 | 실데이터 표시 시 출처 누�� 불가 (tool이 항상 주입) | 1 |
| 9 | 출처 정보가 실제 API 엔드포인트와 정확히 일치 | 1 |
| 10 | Phase 2 새 데이터 소스 추가 시 data_sources.py만 수정하면 됨 | 1 |

### S10: 확장성 (Phase 2 data.go.kr 대비)

| # | 체크 항목 | 배점 |
|---|----------|------|
| 1 | DataSource가 data.go.kr 소스도 표현 가능 | 1 |
| 2 | TOOL_SOURCES에 기존 tool에 새 소스 추가 가능 | 1 |
| 3 | SourcesCitation이 복수 플랫폼 처리 (서울+공공데이터포털) | 1 |
| 4 | Collapsed에 주 플랫폼 + "(외 1개)" 표시 | 1 |
| 5 | Expanded에서 플랫폼별 그룹핑 | 1 |
| 6 | 새 DataSource 추가 시 data_sources.py만 수정 | 1 |
| 7 | 멀티플랫폼 tool의 get_sources_for_tool이 합산 목록 반환 | 1 |
| 8 | 프론트엔드 변경 불필요 (새 소스 추가 시) | 1 |
| 9 | DataSource.url이 서울/공공데이터포털 URL 모두 지원 | 1 |
| 10 | 타입 시스템이 불완전한 source 정의 방지 (필수 필드) | 1 |

---

## 테스트 실행 워크플로

```
1. Step 1-5 구현
2. 독립 subagent 세션으로 시나리오 평가:

   [Phase A] 정적 분석 (S5-mock, S8-하위호환, S10-확장)
     - grep, tsc --noEmit, 코드 구조 확인

   [Phase B] SSE 파이프라인 검증 (S7)
     - 백엔드 기동 -> chat API 호출 -> SSE 이벤트 JSON 검증

   [Phase C] Card별 출처 표시 (S1-S4)
     - 각 Card footer 확인

   [Phase D] 인터랙션 (S6)
     - 펼침/접힘 동작, 키보드 접근성, 애니메이션

   [Phase E] 법적 준수 (S9)
     - 출처 표시 의무 항목 전수 검사

3. 그레이딩 리포트 (10점 만점)
4. 10점 미만 항목 수정 -> 해당 시나리오만 재평가
5. 전체 10/10 -> 완료
```

---

## 전체 구현 순서

| # | 단계 | 신규 | 수정 | 위험도 |
|---|------|------|------|--------|
| 1 | data_sources.py 레지스트리 | 1 | 0 | 낮음 |
| 2 | district_summary + graph.py 출처 ��입 | 0 | 2 | 중간 |
| 3 | types.ts DataSourceInfo 추가 | 0 | 1 | 낮음 |
| 4 | SourcesCitation 컴포넌트 | 1 | 0 | 낮음 |
| 5 | 4개 Card footer 교체 | 0 | 4 | 중간 |
| 6 | E2E 검증 + 시나리오 테스트 | 0 | 0 | - |

**총계**: 신규 2개, 수정 7개

## 핵심 파일

| 파일 | 역할 |
|------|------|
| `server/server/agent/tools/data_sources.py` | 신규: 출처 레지스트리 (단일 진실 원천) |
| `server/server/agent/graph.py` | 수정: on_tool_end에서 card에 dataSources 주입 (lines 295-313) |
| `server/server/agent/tools/district_summary.py` | 수정: result dict에 dataSources 추가 (line ~148) |
| `frontend/src/lib/types.ts` | 수정: DataSourceInfo 인터페이스 + Card 타입 확장 |
| `frontend/src/components/chat/cards/SourcesCitation.tsx` | 신규: 재사용 출처 표시 컴포넌트 |
| `frontend/src/components/chat/cards/SummaryCard.tsx` | 수정: footer -> SourcesCitation (lines 143-148) |
| `frontend/src/components/chat/cards/CompareCard.tsx` | 수정: footer -> SourcesCitation (lines 150-155) |
| `frontend/src/components/chat/cards/RecommendCard.tsx` | 수정: footer -> SourcesCitation (lines 99-107) |
| `frontend/src/components/chat/cards/RiskCard.tsx` | 수정: footer -> SourcesCitation (lines 184-191) |
