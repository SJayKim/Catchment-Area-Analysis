# Spec — 기능 · 업무 · 데이터 스펙

서비스 기능(F01~F13), 비즈니스 모델(B01), 데이터 파이프라인(D01) 스펙 모음.

## 진입점

| 문서 | 역할 |
|---|---|
| [feature-list.md](feature-list.md) | 전체 기능 인덱스 + Phase/상태/Tier 매핑 (**먼저 읽을 것**) |

## 폴더 구성

```
spec/
├── features/    F01~F13 서비스 기능 스펙
├── business/    B01 Freemium 비즈니스 모델
└── data/        D01 데이터 파이프라인
```

## 기능 스펙

| ID | 기능 | Phase | 상태 |
|---|---|---|---|
| [F01](features/F01-map-district-selection.md) | 지도 기반 상권 선택 | 1A · 1B | ✅ |
| [F02](features/F02-ai-chatbot-agent.md) | AI 챗봇 (Agent — 현행 v2 agentic loop, PAE 는 legacy) | 1A · 1B | ✅ |
| [F03](features/F03-basic-report.md) | 상권 기본 리포트 | 1A · 1B | ✅ |
| [F04](features/F04-industry-analysis.md) | 업종별 심층 분석 | 2 | ⏳ 부분 |
| [F05](features/F05-district-comparison.md) | 상권 비교 | 1A · 1B | ✅ |
| [F06](features/F06-heatmap.md) | 시간대별 히트맵 | 3 | ✅ |
| [F07](features/F07-business-recommendation.md) | 업종 추천 | 1A · 1B | ✅ |
| [F08](features/F08-store-history-risk.md) | 점포 이력 / 리스크 | 1A · 1B | ✅ |
| [F09](features/F09-revenue-simulation.md) | 매출 시뮬레이션 | 3 | ✅ |
| [F10](features/F10-report-export.md) | PDF 리포트 | 3 | ✅ |
| [F11](features/F11-landing.md) | 랜딩 + 역할 온보딩 | UX | ✅ |
| [F12](features/F12-feedback.md) | 피드백 수집 3-layer | UX | ✅ |
| [F13](features/F13-district-preview.md) | 상권 프리뷰 (Zero-LLM) | UX | ✅ |

## 기타 스펙

- [business/B01-business-model.md](business/B01-business-model.md) — Freemium 수익 모델 (Phase 2 계획)
- [data/D01-data-pipeline.md](data/D01-data-pipeline.md) — 공공데이터 ETL 파이프라인

## 읽는 순서

1. `feature-list.md` — 전체 Phase/상태 파악
2. 변경 대상 기능의 `features/F##-*.md` 만 선택적으로 읽기
3. 레이어 전체 영향이 있으면 [../architecture/](../architecture/) 참조
4. 구현 계획은 [../plan/](../plan/) (현재 진행 중인 것만 보관)
