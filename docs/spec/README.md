# Spec — 기능/업무/데이터 스펙

서비스 기능(F01~F10), 비즈니스 모델(B01), 데이터 파이프라인(D01) 스펙을 모아둔 폴더.

## 핵심 인덱스

| 문서 | 역할 |
|---|---|
| [feature-list.md](feature-list.md) | 전체 기능 목록 + Phase 계획 + 의존관계 (**마스터 인덱스**) |
| [checklist.md](checklist.md) | ~150항목 개발 체크리스트 |

## 폴더 구성

```
spec/
├── features/    F01~F10 서비스 기능 스펙
├── business/    B01 Freemium 비즈니스 모델
└── data/        D01 데이터 파이프라인/ETL
```

## 기능 스펙 (features/)

| ID | 기능 | Phase | Tier |
|---|---|---|---|
| [F01](features/F01-map-district-selection.md) | 지도 기반 상권 선택 | 1A | Free |
| [F02](features/F02-ai-chatbot-agent.md) | AI 챗봇 에이전트 | 1A | Free |
| [F03](features/F03-basic-report.md) | 상권 기본 리포트 | 1A | Free |
| [F04](features/F04-industry-analysis.md) | 업종별 심층 분석 | 2 | Premium |
| [F05](features/F05-district-comparison.md) | 상권 비교 | 1A | Free(데모) |
| [F06](features/F06-heatmap.md) | 시간대별 히트맵 | 3 | Premium |
| [F07](features/F07-business-recommendation.md) | 업종 추천 | 1A | Free(데모) |
| [F08](features/F08-store-history-risk.md) | 점포 이력/리스크 | 1A | Free(데모) |
| [F09](features/F09-revenue-simulation.md) | 매출 시뮬레이션 | 3 | Premium |
| [F10](features/F10-report-export.md) | 리포트 저장(PDF) | 3 | Premium |

## 기타 스펙

- [business/B01-business-model.md](business/B01-business-model.md) — Freemium 수익 모델
- [data/D01-data-pipeline.md](data/D01-data-pipeline.md) — 공공데이터 ETL 파이프라인
