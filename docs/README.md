# MarketScope AI — Docs Index

지도 기반 AI 상권분석 서비스의 문서 루트. 주제별로 폴더가 나뉘며, 각 폴더의 `README.md`가 해당 폴더의 네비게이션 역할을 합니다.

## 폴더 구조

```
docs/
├── architecture/    시스템 전체 설계 (overall-architecture.md)
├── spec/            기능/업무/데이터 스펙 (F01~F10, B01, D01)
│   ├── features/    서비스 기능 스펙 F01~F10
│   ├── business/    B01 비즈니스 모델
│   └── data/        D01 데이터 파이프라인
├── plan/            구현 계획 (카테고리별)
│   ├── phase/       Phase 1/1B/2/3 로드맵
│   ├── fix/         버그/리팩토링 계획
│   ├── infra/       Docker/문서/E2E 인프라 계획
│   ├── data/        데이터 소스/마이그레이션
│   ├── ui/          카드 UI/다크 테마
│   ├── business/    커머셜라이제이션
│   └── agent-improvement/  Agent 고도화 단계별 계획
├── qa/              QA 테스트 플랜/리포트 (마스터: qa-test-plan.md)
│   └── runs/        실행 로그 (날짜별)
├── status/          개발 진행 상태 (마스터: current-status.md)
│   └── e2e/         E2E 테스트 리포트 이력
├── setup/           개발환경 셋업 가이드
├── archive/         구 버전 문서 + 완료된 plan/QA (⚠ 참고 금지, 이력 보존용)
│   ├── completed-plans/  완료된 구현 계획 12개
│   └── qa-history/       Phase 1B QA 히스토리 리포트 6개
├── screenshots/     UI 스크린샷 (dev/e2e-qa/real-mode/ux)
├── images/          README에서 참조하는 이미지
└── demo_video/      데모 영상
```

## 핵심 진입점

| 목적 | 문서 |
|---|---|
| 전체 아키텍처 이해 | [architecture/overall-architecture.md](architecture/overall-architecture.md) |
| 기능 목록 & Phase 계획 | [spec/feature-list.md](spec/feature-list.md) |
| 개발 체크리스트 | [spec/checklist.md](spec/checklist.md) |
| 현재 개발 상태 | [status/current-status.md](status/current-status.md) |
| QA 마스터 플랜 | [qa/qa-test-plan.md](qa/qa-test-plan.md) |
| Phase 2/3 구현 계획 | [plan/phase/](plan/phase/) |
| Agent 고도화 계획 | [plan/agent-improvement/00-overview.md](plan/agent-improvement/00-overview.md) |

## 명명 규칙

- 파일/폴더명은 **kebab-case** (예: `current-status.md`, `data-preparation.md`)
- 예외: `F01~F10`, `B01`, `D01`, `README.md` (스펙 코드/관례)
