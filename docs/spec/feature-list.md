# 개발 기능 목록

> 개발 관점의 기능 인덱스. 각 기능의 상세 스펙은 개별 문서 참조.

## 인프라 / 데이터

| ID | 기능명 | Phase | 상태 | 참조 |
|---|---|---|---|---|
| D01 | 데이터 파이프라인 (ETL) | 1B | ✅ 완료 (2025Q4) | [data/D01-data-pipeline.md](data/D01-data-pipeline.md) |
| D02 | DB 스키마 + PostGIS | 1B | ✅ 완료 (Alembic 001~003) | [../architecture/data.md](../architecture/data.md) |
| D03 | Docker 개발환경 | 1B | ✅ 완료 (compose dev + prod) | [../architecture/deployment.md](../architecture/deployment.md) |
| M01 | Mock 데이터 레이어 | 1A | ✅ 완료 | [../architecture/data.md §1](../architecture/data.md) |

## 서비스 기능

| ID | 기능명 | Phase | 상태 | Tier | 스펙 |
|---|---|---|---|---|---|
| F01 | 지도 기반 상권 선택 | 1A · 1B | ✅ 완료 | Free | [features/F01-map-district-selection.md](features/F01-map-district-selection.md) |
| F02 | AI 챗봇 (PAE Agent) | 1A · 1B | ✅ 완료 | Free (Phase 2 에서 일 5회 제한 예정) | [features/F02-ai-chatbot-agent.md](features/F02-ai-chatbot-agent.md) |
| F03 | 상권 기본 리포트 | 1A · 1B | ✅ 완료 | Free | [features/F03-basic-report.md](features/F03-basic-report.md) |
| F04 | 업종별 심층 분석 | 2 | ⏳ Tool 부분 구현 / UI 미구현 | Premium | [features/F04-industry-analysis.md](features/F04-industry-analysis.md) |
| F05 | 상권 비교 | 1A · 1B | ✅ 완료 (다색 하이라이트) | Free (Phase 2 에서 Premium) | [features/F05-district-comparison.md](features/F05-district-comparison.md) |
| F06 | 시간대별 히트맵 | 3 | ✅ 완료 (평일/주말 토글 제외) | Premium | [features/F06-heatmap.md](features/F06-heatmap.md) |
| F07 | 업종 추천 | 1A · 1B | ✅ 완료 | Free (Phase 2 에서 Premium) | [features/F07-business-recommendation.md](features/F07-business-recommendation.md) |
| F08 | 점포 이력 / 리스크 | 1A · 1B | ✅ 완료 (store_history 실데이터 미적재) | Free (Phase 2 에서 Premium) | [features/F08-store-history-risk.md](features/F08-store-history-risk.md) |
| F09 | 매출 시뮬레이션 | 3 | ✅ 완료 (What-If UI 버튼 제외) | Premium | [features/F09-revenue-simulation.md](features/F09-revenue-simulation.md) |
| F10 | PDF 리포트 저장 | 3 | ✅ 완료 | Premium | [features/F10-report-export.md](features/F10-report-export.md) |
| F11 | 랜딩 + 역할 온보딩 | UX | ✅ 구현 (Phase A) | Free | [features/F11-landing.md](features/F11-landing.md) |
| F12 | 피드백 수집 3-layer | UX | ✅ 구현 (Phase C) | Free | [features/F12-feedback.md](features/F12-feedback.md) |
| F13 | 상권 프리뷰 (Zero-LLM) | UX | ✅ 구현 (Phase B) | Free | [features/F13-district-preview.md](features/F13-district-preview.md) |

## Phase 요약

- **Phase 1A — Mock E2E** ✅ 완료. DB 없이 Agent 전체 흐름 검증.
- **Phase 1B — Real Data** ✅ 완료. 1,650개 상권 ETL 적재 + PAE 전환 + 프로덕션 배포.
- **Phase 3 — 확장** ✅ 완료. F06 / F09 / F10 구현.
- **Phase 2 — Premium** ⏳ 미착수. OAuth2 / 결제 / Tier 게이팅 / F04 카드 UI.

> Phase 2 는 기능 순서가 아닌 **상용화 순서**로 [plan/business/commercialization-plan.md](../plan/business/commercialization-plan.md) 에서 관리.

## Freemium 수익 모델 (계획)

> 현재 모든 기능이 Free. Phase 2 에서 게이팅 도입.

| 기능 | Free | Premium |
|---|---|---|
| 지도 상권 탐색 (F01) | O | O |
| AI 챗봇 (F02) | 일 5회 | 무제한 |
| 기본 리포트 (F03) | O | O |
| 업종 심층 (F04) | X | O |
| 상권 비교 (F05) | X | O |
| 업종 추천 (F07) | X | O |
| 리스크 (F08) | X | O |
| 히트맵 (F06) | X | O |
| 매출 시뮬레이션 (F09) | X | O |
| PDF 리포트 (F10) | X | O |

세부 정책은 [business/B01-business-model.md](business/B01-business-model.md) 참조.

## 기능 의존 관계

```
M01 (Mock) ──┐
             ▼
 F01 (지도) ──┐
             ▼
 F02 (Agent) ──┬──→ F03 (요약) ──┬──→ F04 (업종 심층, Phase 2)
              │                ├──→ F05 (비교, 다색 하이라이트)
              │                ├──→ F07 (추천)
              │                └──→ F09 (시뮬레이션)
              ├──→ F08 (리스크)
              └──→ F10 (PDF, chatStore 활용)

F06 (히트맵) — F01 에 의존, deck.gl 레이어
```
