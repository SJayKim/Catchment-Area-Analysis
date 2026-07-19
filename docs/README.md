# MarketScope AI — Docs Index

지도 기반 AI 상권분석 서비스의 문서 루트. 토큰 효율을 위해 **계층형 구조**로 재편 (2026-04-19).
한 번에 전체를 읽지 말고, 필요한 계층/레이어만 선택적으로 읽을 것.

## 폴더 구조

```
docs/
├── architecture/   계층 1 — 시스템 설계 (overview / backend / frontend / agent / data / deployment)
├── spec/           계층 2 — 기능 스펙 (F01~F13, D01, B01)
├── ops/            운영 (quickstart, runbook, DR, deployment, database setup, serving stability)
├── plan/           진행 중/대기 구현 계획만 (완료분은 git history)
│   ├── business/   상용화 (commercialization-plan)
│   ├── fix/        버그 / 정확도 hotfix (현재 활성 없음)
│   ├── infra/      배포 / 안정성 / Langfuse / refactoring (auto-deploy · v2-stream · langfuse-* · phase1 · apps-in-toss)
│   └── qa/         QA / E2E 회귀 (ux-final-e2e-regression-plan)
├── qa/             E2E test plan + runs/
├── learning/       학습 자료 — 비개발자용 커리큘럼 00~07 + ARCHITECTURE-MAP.md
├── status/         현재 상태 단일 마스터 (current-status.md)
├── screenshots/    UI 스크린샷 (dev, e2e-qa, real-mode, ux)
├── images/         README 이미지
└── demo_video/     데모 영상
```

## 진입점

| 목적 | 문서 |
|---|---|
| 시스템 전체 그림 파악 | [architecture/overview.md](architecture/overview.md) |
| 특정 레이어만 상세 | [architecture/](architecture/) (backend / frontend / agent / data / deployment) |
| 기능별 요구사항 | [spec/feature-list.md](spec/feature-list.md) |
| 현재 개발 상태 | [status/current-status.md](status/current-status.md) |
| 빠른 시작 (개발) | [ops/quickstart.md](ops/quickstart.md) |
| 프로덕션 배포 | [ops/production-deployment.md](ops/production-deployment.md) |
| E2E 테스트 플랜 | [qa/test-plan.md](qa/test-plan.md) |
| 상용화 로드맵 | [plan/business/commercialization-plan.md](plan/business/commercialization-plan.md) |
| 학습 자료 (신규 합류자) | [learning/00-시작하기.md](learning/00-시작하기.md) |

## 읽는 순서 가이드

1. **처음 진입**: `architecture/overview.md` → `spec/feature-list.md`
2. **기능 작업**: `spec/features/F##-*.md` 해당 파일 → 필요 시 관련 레이어 architecture
3. **아키텍처 변경**: 해당 레이어 `architecture/*.md` 만 → 영향받는 기능 spec 갱신
4. **운영 작업**: `ops/runbook.md` → 상황별 세부 문서
5. **상태 확인**: `status/current-status.md` (단일 마스터)

## 명명 규칙

- 파일/폴더명은 **kebab-case**
- 예외: `F01~F10`, `B01`, `D01`, `README.md`
- 다이어그램은 ASCII 기반 (외부 도구 의존성 제거)

## 문서 삭제/정리 원칙

- **완료된 plan**: git history 로 이관 후 트리에서 제거 (2026-07-07 docs diet 정책). 이력은 `git log` + `status/current-status.md` "이력 요약"
- **구식 status 리포트**: 단일 `status/current-status.md` 만 유지
- **레이어별 중복 정보**: `architecture/` 가 단일 진실. spec 은 링크로 대체
- **수치/설정값**: `config.py` / `docker-compose.yml` 이 단일 진실
