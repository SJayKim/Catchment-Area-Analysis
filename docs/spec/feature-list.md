# 개발 기능 목록

> 개발 관점에서 정리한 기능 목록. 각 기능의 세부 spec은 개별 문서 참조.

---

## 인프라/데이터 기능

| ID | 기능명 | 설명 | Phase |
|----|--------|------|-------|
| D01 | 데이터 파이프라인 | 공공데이터 수집 → ETL → PostgreSQL 적재 | 1B |
| D02 | DB 스키마 & 초기화 | PostGIS 테이블 생성, 인덱스, 시드 데이터 | 1B |
| D03 | Docker 개발환경 | docker-compose (DB, Redis, Backend, Frontend) | 1B |
| M01 | Mock 데이터 레이어 | DB 없이 Agent Tool이 동작하는 Mock 데이터셋 | 1A |

## 서비스 기능

| ID | 기능명 | 핵심 컴포넌트 | Phase | Tier | 의존성 |
|----|--------|---------------|-------|------|--------|
| F01 | 지도 기반 상권 선택 | Kakao Map + DistrictLayer + Zustand | 1A | Free | M01 |
| F02 | AI 챗봇 에이전트 | LangGraph ReAct + FastAPI SSE + ChatPanel | 1A | Free (일 5회) | M01 |
| F03 | 상권 기본 리포트 | Agent Tools (4종) + SummaryCard | 1A | Free | F02 |
| F04 | 업종별 심층 분석 | get_estimated_sales + get_store_info | 2 | **Premium** | F02, F03 |
| F05 | 상권 비교 | compare_districts Tool + CompareCard | 1A | Free (데모) | F03 |
| F07 | 업종 추천 | recommend_business Tool + RecommendCard | 1A | Free (데모) | F03 |
| F08 | 점포 이력/리스크 분석 | store_history 테이블 + RiskCard | 1A | Free (데모) | F02 |
| F06 | 시간대별 히트맵 | deck.gl HeatmapLayer + TimeSlider | 3 | **Premium** | F01 |
| F09 | 간이 매출 시뮬레이션 | simulate_revenue Tool + SimulationCard | 3 | **Premium** | F04 |
| F10 | 리포트 저장 (PDF) | @react-pdf/renderer + S3 | 3 | **Premium** | F03 |

> **변경사항 (2026-03-25)**: F05, F07, F08을 Phase 1A로 이동 — Mock 데이터로 E2E 흐름 검증 우선. 실제 데이터 연결은 Phase 1B에서.

## 수익 모델 (Freemium)

> 상세 정책은 `docs/spec/business/B01-business-model.md` 참조

| 구분 | Free | Premium |
|------|------|---------|
| 지도 상권 탐색 | O | O |
| AI 챗봇 질의 | 일 5회 | 무제한 |
| 기본 리포트 (F03) | O | O |
| 업종 심층 분석 (F04) | X | O |
| 상권 비교 (F05) | X | O |
| 업종 추천 (F07) | X | O |
| 리스크 분석 (F08) | X | O |
| 히트맵 (F06) | X | O |
| 매출 시뮬레이션 (F09) | X | O |
| PDF 리포트 (F10) | X | O |

## Phase별 개발 순서

### Phase 1A — E2E Mock (DB 없이 Agent + Chat UI 동작)
```
M01 Mock 데이터 → F01 지도 선택 → F02 AI 챗봇 → F03 기본 리포트
                                                  → F05 상권 비교
                                                  → F07 업종 추천
                                                  → F08 리스크 분석
```
- 목표: **데이터 없이도** "지도에서 상권 선택 → AI가 분석" 전체 흐름 동작 확인
- Mock 데이터 기반, FastAPI + Next.js만으로 실행 (Docker/DB/Redis 불필요)
- Agent 로직, SSE 스트리밍, Card UI 렌더링 E2E 검증

### Phase 1B — Real Data 연결
```
D03 Docker 환경 → D02 DB 스키마 → D01 데이터 수집/적재
→ Mock Tool을 Real DB 쿼리로 교체
```
- 목표: Mock 데이터를 실제 공공데이터로 교체
- DB/Redis 연결, ETL 파이프라인, 캐싱 활성화

### Phase 2 — 프리미엄 차별화 기능
```
F04 업종 심층 | Tier 게이팅 인프라 (인증/결제)
```
- 목표: 유료 전환을 유도하는 고부가 기능
- Phase 1A에서 검증한 F05/F07/F08에 Tier 게이팅 적용

### Phase 3 — 확장
```
F06 히트맵 | F09 매출 시뮬레이션 | F10 리포트 저장
```
- 목표: 시각적 임팩트 + 실용 기능 (Premium 전용)

## 기능 의존관계 다이어그램

```
M01 (Mock 데이터) ─────────────────────────────────── Phase 1A
        │
        ▼
 F01 (지도 선택, Mock 폴리곤) ─────────────────────── Phase 1A
        │
        ▼
 F02 (AI 챗봇, Mock Tools) ──────────────┐
        │                                │
        ▼                                ▼
 F03 (기본 리포트) ── Mock          F08 (리스크) ── Mock
   │         │
   ▼         ▼
F05 (비교)  F07 (추천) ── Mock
                                        ─────────── Phase 1A 여기까지

D03 → D02 → D01 (인프라/데이터)
        │
        ▼
 Mock → Real DB 전환                    ─────────── Phase 1B

F04 (업종 심층) + Tier 게이팅           ─────────── Phase 2

F06 (히트맵) / F09 (시뮬레이션) / F10 (PDF) ─────── Phase 3
```

---

*작성일: 2026-03-24*
*수정일: 2026-03-25 — Mock-first E2E 전략으로 Phase 재구성*
