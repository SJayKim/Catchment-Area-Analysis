# 13. CI/CD 파이프라인 명세서

> MarketScope AI 프로젝트의 지속적 통합(CI) 및 지속적 배포(CD) 파이프라인 설계 명세

---

## 목차

1. [CI/CD 파이프라인 개요](#1-cicd-파이프라인-개요)
2. [GitHub Actions 워크플로우 설계](#2-github-actions-워크플로우-설계)
3. [빌드 스테이지](#3-빌드-스테이지)
4. [배포 스테이지](#4-배포-스테이지)
5. [환경별 배포 전략](#5-환경별-배포-전략)
6. [Alembic 자동 마이그레이션](#6-alembic-자동-마이그레이션)
7. [롤백 절차](#7-롤백-절차)
8. [시크릿 관리](#8-시크릿-관리)
9. [PR 자동 검증](#9-pr-자동-검증)
10. [브랜치 전략](#10-브랜치-전략)

---

## 1. CI/CD 파이프라인 개요

### 1.1 목적

MarketScope AI 프로젝트의 코드 품질 보장, 자동화된 테스트 실행, 안정적인 배포 프로세스를 구축하여 개발 생산성과 서비스 안정성을 동시에 확보한다.

### 1.2 파이프라인 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CI/CD Pipeline                               │
│                                                                     │
│  Developer                                                          │
│     │                                                               │
│     ├─── feature/* branch push ──► PR 생성                          │
│     │                                │                              │
│     │                         ┌──────▼──────┐                       │
│     │                         │  PR 검증 CI  │                      │
│     │                         │  ┌────────┐  │                      │
│     │                         │  │  Lint   │  │                      │
│     │                         │  └───┬────┘  │                      │
│     │                         │  ┌───▼────┐  │                      │
│     │                         │  │  Test   │  │                      │
│     │                         │  └───┬────┘  │                      │
│     │                         │  ┌───▼────┐  │                      │
│     │                         │  │Coverage │  │                      │
│     │                         │  └────────┘  │                      │
│     │                         └──────┬──────┘                       │
│     │                                │ ✅ All Passed                │
│     │                         ┌──────▼──────┐                       │
│     │                         │  Merge to    │                      │
│     │                         │  main branch │                      │
│     │                         └──────┬──────┘                       │
│     │                                │                              │
│     │                         ┌──────▼──────┐                       │
│     │                         │  배포 CD     │                      │
│     │                         │  ┌────────┐  │                      │
│     │                         │  │ Build   │  │                      │
│     │                         │  └───┬────┘  │                      │
│     │                         │  ┌───▼────┐  │                      │
│     │                         │  │ Push    │  │                      │
│     │                         │  └───┬────┘  │                      │
│     │                         │  ┌───▼────┐  │                      │
│     │                         │  │Staging  │  │                      │
│     │                         │  └───┬────┘  │                      │
│     │                         │  ┌───▼────┐  │                      │
│     │                         │  │  Prod   │  │                      │
│     │                         │  │(수동승인)│  │                      │
│     │                         │  └────────┘  │                      │
│     │                         └─────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 기술 스택

| 구성 요소 | 기술 |
|-----------|------|
| CI/CD 플랫폼 | GitHub Actions |
| 컨테이너 레지스트리 | Google Artifact Registry |
| 배포 대상 | Google Cloud Run |
| 린터/포매터 | Ruff |
| 테스트 프레임워크 | pytest |
| DB 마이그레이션 | Alembic |
| 컨테이너 빌드 | Docker (multi-stage) |
| 시크릿 관리 | GitHub Secrets + GCP Secret Manager |

### 1.4 핵심 원칙

- **자동화 우선**: 수동 개입 최소화, 모든 검증 및 배포 자동화
- **Fast Feedback**: PR 제출 후 10분 이내 CI 결과 피드백
- **환경 격리**: dev / staging / prod 환경 완전 분리
- **불변 배포(Immutable Deployment)**: 동일 이미지를 staging → prod로 프로모션
- **롤백 가능성**: 모든 배포는 즉시 롤백 가능한 구조

---

## 2. GitHub Actions 워크플로우 설계

### 2.1 PR 검증 워크플로우 (CI)

> 트리거: `on: pull_request` (대상 브랜치: `main`, `develop`)

#### 2.1.1 워크플로우 정의

```yaml
# .github/workflows/ci.yml
name: CI - PR Validation

on:
  pull_request:
    branches: [main, develop]
    paths-ignore:
      - "docs/**"
      - "*.md"
      - ".gitignore"

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

env:
  PYTHON_VERSION: "3.11"
  POETRY_VERSION: "1.7.1"

jobs:
  lint:
    name: "Lint & Format Check"
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: |
          pip install ruff

      - name: Run Ruff linter
        run: |
          ruff check . --output-format=github

      - name: Run Ruff format check
        run: |
          ruff format --check .

  unit-tests:
    name: "Unit Tests"
    runs-on: ubuntu-latest
    needs: [lint]
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run unit tests
        run: |
          pytest tests/unit/ \
            -v \
            --tb=short \
            --cov=app \
            --cov-report=xml:coverage-unit.xml \
            --cov-report=term-missing \
            --junitxml=junit-unit.xml
        env:
          ENVIRONMENT: test
          DATABASE_URL: "sqlite:///./test.db"

      - name: Upload unit test coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-unit
          path: coverage-unit.xml

  integration-tests:
    name: "Integration Tests"
    runs-on: ubuntu-latest
    needs: [lint]
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: marketscope_test
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: marketscope_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run database migrations
        run: |
          alembic upgrade head
        env:
          DATABASE_URL: "postgresql://marketscope_test:test_password@localhost:5432/marketscope_test"

      - name: Run integration tests
        run: |
          pytest tests/integration/ \
            -v \
            --tb=short \
            --cov=app \
            --cov-report=xml:coverage-integration.xml \
            --junitxml=junit-integration.xml \
            --timeout=120
        env:
          ENVIRONMENT: test
          DATABASE_URL: "postgresql://marketscope_test:test_password@localhost:5432/marketscope_test"
          REDIS_URL: "redis://localhost:6379/0"

      - name: Upload integration test coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-integration
          path: coverage-integration.xml

  coverage-report:
    name: "Coverage Report"
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Download unit test coverage
        uses: actions/download-artifact@v4
        with:
          name: coverage-unit

      - name: Download integration test coverage
        uses: actions/download-artifact@v4
        with:
          name: coverage-integration

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install coverage tools
        run: pip install coverage

      - name: Merge coverage reports
        run: |
          coverage combine coverage-unit.xml coverage-integration.xml || true
          coverage report --fail-under=80
          coverage xml -o coverage-total.xml

      - name: Post coverage comment on PR
        uses: orgoro/coverage@v3.2
        with:
          coverageFile: coverage-total.xml
          token: ${{ secrets.GITHUB_TOKEN }}
          thresholdAll: 0.80
          thresholdNew: 0.90
```

#### 2.1.2 Lint 상세 설정

```toml
# pyproject.toml - Ruff 설정
[tool.ruff]
target-version = "py311"
line-length = 120
src = ["app", "tests"]

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "S",    # flake8-bandit (보안)
    "T20",  # flake8-print
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
]
ignore = [
    "S101",  # assert 사용 허용 (테스트 코드)
    "B008",  # Depends() 패턴 허용 (FastAPI)
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101", "S106"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

#### 2.1.3 테스트 구성

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --strict-markers
    --tb=short
markers =
    unit: Unit tests (빠른 실행, 외부 의존성 없음)
    integration: Integration tests (외부 서비스 필요)
    slow: Slow tests (실행 시간 > 30초)
    e2e: End-to-end tests
```

### 2.2 배포 워크플로우 (CD)

> 트리거: `on: push` (대상 브랜치: `main`)

```yaml
# .github/workflows/cd.yml
name: CD - Build & Deploy

on:
  push:
    branches: [main]
    paths-ignore:
      - "docs/**"
      - "*.md"

env:
  PROJECT_ID: marketscope-ai
  REGION: asia-northeast3
  REGISTRY: asia-northeast3-docker.pkg.dev
  REPOSITORY: marketscope-repo
  SERVICE_NAME: marketscope-api
  PYTHON_VERSION: "3.11"

jobs:
  # ──────────────────────────────────────────────
  # Stage 1: Build & Push Docker Image
  # ──────────────────────────────────────────────
  build-and-push:
    name: "Build & Push Docker Image"
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}
      image_digest: ${{ steps.build.outputs.digest }}
      short_sha: ${{ steps.vars.outputs.short_sha }}
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set variables
        id: vars
        run: |
          echo "short_sha=$(git rev-parse --short HEAD)" >> $GITHUB_OUTPUT
          echo "build_date=$(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> $GITHUB_OUTPUT

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}

      - name: Configure Docker for Artifact Registry
        run: |
          gcloud auth configure-docker ${{ env.REGISTRY }} --quiet

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: |
            ${{ env.REGISTRY }}/${{ env.PROJECT_ID }}/${{ env.REPOSITORY }}/${{ env.SERVICE_NAME }}
          tags: |
            type=sha,prefix=
            type=raw,value=latest
            type=raw,value=${{ steps.vars.outputs.short_sha }}

      - name: Build and push Docker image
        id: build
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            BUILD_DATE=${{ steps.vars.outputs.build_date }}
            GIT_SHA=${{ github.sha }}

  # ──────────────────────────────────────────────
  # Stage 2: Deploy to Staging
  # ──────────────────────────────────────────────
  deploy-staging:
    name: "Deploy to Staging"
    runs-on: ubuntu-latest
    needs: [build-and-push]
    environment:
      name: staging
      url: https://staging-marketscope-api-${{ env.PROJECT_ID }}.run.app
    permissions:
      contents: read
      id-token: write
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2

      - name: Run Alembic migrations (Staging)
        run: |
          gcloud run jobs execute marketscope-migrate \
            --region=${{ env.REGION }} \
            --wait \
            --args="upgrade,head" \
            --set-env-vars="DATABASE_URL=${{ secrets.STAGING_DATABASE_URL }}"

      - name: Deploy to Cloud Run (Staging)
        uses: google-github-actions/deploy-cloudrun@v2
        with:
          service: ${{ env.SERVICE_NAME }}-staging
          region: ${{ env.REGION }}
          image: "${{ env.REGISTRY }}/${{ env.PROJECT_ID }}/${{ env.REPOSITORY }}/${{ env.SERVICE_NAME }}:${{ needs.build-and-push.outputs.short_sha }}"
          flags: |
            --cpu=2
            --memory=2Gi
            --min-instances=0
            --max-instances=5
            --concurrency=80
            --timeout=300
            --set-env-vars=ENVIRONMENT=staging
          secrets: |
            DATABASE_URL=staging-database-url:latest
            REDIS_URL=staging-redis-url:latest
            OPENAI_API_KEY=openai-api-key:latest
            GOOGLE_MAPS_API_KEY=google-maps-api-key:latest

      - name: Run smoke tests (Staging)
        run: |
          STAGING_URL=$(gcloud run services describe ${{ env.SERVICE_NAME }}-staging \
            --region=${{ env.REGION }} \
            --format='value(status.url)')

          echo "Staging URL: $STAGING_URL"

          # Health check
          HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$STAGING_URL/health")
          if [ "$HTTP_STATUS" != "200" ]; then
            echo "Health check failed with status: $HTTP_STATUS"
            exit 1
          fi

          # API readiness check
          HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$STAGING_URL/api/v1/ready")
          if [ "$HTTP_STATUS" != "200" ]; then
            echo "Readiness check failed with status: $HTTP_STATUS"
            exit 1
          fi

          echo "Smoke tests passed"

  # ──────────────────────────────────────────────
  # Stage 3: Deploy to Production (수동 승인 필요)
  # ──────────────────────────────────────────────
  deploy-production:
    name: "Deploy to Production"
    runs-on: ubuntu-latest
    needs: [build-and-push, deploy-staging]
    environment:
      name: production
      url: https://marketscope-api-${{ env.PROJECT_ID }}.run.app
    permissions:
      contents: read
      id-token: write
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2

      - name: Run Alembic migrations (Production)
        run: |
          gcloud run jobs execute marketscope-migrate-prod \
            --region=${{ env.REGION }} \
            --wait \
            --args="upgrade,head" \
            --set-env-vars="DATABASE_URL=${{ secrets.PROD_DATABASE_URL }}"

      - name: Deploy to Cloud Run (Production)
        uses: google-github-actions/deploy-cloudrun@v2
        with:
          service: ${{ env.SERVICE_NAME }}
          region: ${{ env.REGION }}
          image: "${{ env.REGISTRY }}/${{ env.PROJECT_ID }}/${{ env.REPOSITORY }}/${{ env.SERVICE_NAME }}:${{ needs.build-and-push.outputs.short_sha }}"
          flags: |
            --cpu=4
            --memory=4Gi
            --min-instances=1
            --max-instances=20
            --concurrency=100
            --timeout=300
            --set-env-vars=ENVIRONMENT=production
            --cpu-boost
          secrets: |
            DATABASE_URL=prod-database-url:latest
            REDIS_URL=prod-redis-url:latest
            OPENAI_API_KEY=openai-api-key:latest
            GOOGLE_MAPS_API_KEY=google-maps-api-key:latest
            NAVER_CLIENT_ID=naver-client-id:latest
            NAVER_CLIENT_SECRET=naver-client-secret:latest

      - name: Verify production deployment
        run: |
          PROD_URL=$(gcloud run services describe ${{ env.SERVICE_NAME }} \
            --region=${{ env.REGION }} \
            --format='value(status.url)')

          echo "Production URL: $PROD_URL"

          # Health check with retries
          for i in {1..5}; do
            HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$PROD_URL/health")
            if [ "$HTTP_STATUS" == "200" ]; then
              echo "Production health check passed (attempt $i)"
              break
            fi
            echo "Attempt $i failed with status $HTTP_STATUS, retrying..."
            sleep 10
          done

          if [ "$HTTP_STATUS" != "200" ]; then
            echo "Production health check failed"
            exit 1
          fi

      - name: Tag release
        run: |
          git tag "release-$(date +'%Y%m%d-%H%M%S')-${{ needs.build-and-push.outputs.short_sha }}"
          git push origin --tags
```

---

## 3. 빌드 스테이지

### 3.1 빌드 파이프라인 흐름

```
lint ──► test (unit + integration) ──► Docker build ──► push
  │              │                           │             │
  │              │                           │             │
  ▼              ▼                           ▼             ▼
 Ruff         pytest                   multi-stage    Artifact
 check     + coverage                    build        Registry
```

### 3.2 스테이지별 상세

#### 3.2.1 Lint 스테이지

| 항목 | 설명 |
|------|------|
| 도구 | Ruff |
| 린팅 명령 | `ruff check . --output-format=github` |
| 포맷 검증 | `ruff format --check .` |
| 실패 조건 | 린팅 오류 또는 포맷 불일치 존재 시 |
| 예상 실행 시간 | < 30초 |

#### 3.2.2 Test 스테이지

| 항목 | Unit Tests | Integration Tests |
|------|-----------|-------------------|
| 경로 | `tests/unit/` | `tests/integration/` |
| 외부 서비스 | 없음 (mock 사용) | PostgreSQL, Redis (GitHub Services) |
| 실행 명령 | `pytest tests/unit/ --cov` | `pytest tests/integration/ --cov` |
| 커버리지 임계값 | 80% 이상 | 70% 이상 |
| 타임아웃 | 60초/테스트 | 120초/테스트 |
| 병렬 실행 | lint 완료 후 unit/integration 병렬 | lint 완료 후 unit/integration 병렬 |

#### 3.2.3 Docker Build 스테이지

**Dockerfile (Multi-stage Build)**:

```dockerfile
# ─── Stage 1: Builder ───
FROM python:3.11-slim AS builder

WORKDIR /build

# 시스템 의존성 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 2: Runtime ───
FROM python:3.11-slim AS runtime

ARG BUILD_DATE
ARG GIT_SHA

LABEL maintainer="MarketScope AI Team"
LABEL build.date=${BUILD_DATE}
LABEL git.sha=${GIT_SHA}

WORKDIR /app

# 런타임 시스템 의존성만 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libpq5 \
      curl && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r appuser && \
    useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Builder에서 Python 패키지 복사
COPY --from=builder /install /usr/local

# 애플리케이션 코드 복사
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY entrypoint.sh .

RUN chmod +x entrypoint.sh && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**entrypoint.sh**:

```bash
#!/bin/bash
set -e

echo "=== MarketScope AI Server Starting ==="
echo "Environment: ${ENVIRONMENT:-unknown}"
echo "Git SHA: ${GIT_SHA:-unknown}"
echo "Build Date: ${BUILD_DATE:-unknown}"

# 자동 마이그레이션 실행 (ENABLE_AUTO_MIGRATE=true 인 경우)
if [ "${ENABLE_AUTO_MIGRATE}" = "true" ]; then
    echo "Running database migrations..."
    alembic upgrade head
    echo "Migrations completed."
fi

exec "$@"
```

#### 3.2.4 Push 스테이지

| 항목 | 설명 |
|------|------|
| 레지스트리 | Google Artifact Registry (`asia-northeast3-docker.pkg.dev`) |
| 이미지 태그 규칙 | `<short-sha>`, `latest` |
| 캐시 전략 | GitHub Actions Cache (`type=gha`) |
| 인증 방식 | Workload Identity Federation (OIDC) |

---

## 4. 배포 스테이지

### 4.1 배포 파이프라인 흐름

```
Docker Image Push
       │
       ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Alembic    │     │   Deploy     │     │    Smoke     │
│  Migration   │────►│   Staging    │────►│    Tests     │
│  (Staging)   │     │  Cloud Run   │     │   (Staging)  │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │ ✅ Pass
                                          ┌───────▼───────┐
                                          │   수동 승인    │
                                          │  (Reviewers)   │
                                          └───────┬───────┘
                                                  │ ✅ Approved
                                          ┌───────▼───────┐
                                          │   Alembic     │
                                          │  Migration    │
                                          │  (Prod)       │
                                          └───────┬───────┘
                                          ┌───────▼───────┐
                                          │   Deploy      │
                                          │  Production   │
                                          │  Cloud Run    │
                                          └───────┬───────┘
                                          ┌───────▼───────┐
                                          │   Verify &    │
                                          │   Tag Release │
                                          └───────────────┘
```

### 4.2 Staging 배포

| 항목 | 설정 |
|------|------|
| 트리거 | `main` 브랜치 push (자동) |
| 승인 | 불필요 |
| 인스턴스 | min=0, max=5 |
| CPU/메모리 | 2 vCPU / 2Gi |
| 스모크 테스트 | `/health`, `/api/v1/ready` 엔드포인트 확인 |

### 4.3 Production 배포

| 항목 | 설정 |
|------|------|
| 트리거 | Staging 배포 성공 후 |
| 승인 | **수동 승인 필수** (GitHub Environment Protection Rules) |
| 승인 권한자 | 프로젝트 리드 또는 시니어 개발자 (최소 1명) |
| 승인 대기 | 최대 72시간 (이후 자동 취소) |
| 인스턴스 | min=1, max=20 |
| CPU/메모리 | 4 vCPU / 4Gi |
| 배포 후 검증 | Health check (5회 재시도, 10초 간격) |

### 4.4 GitHub Environment 설정

```yaml
# GitHub Repository Settings → Environments

# Staging Environment
staging:
  protection_rules:
    required_reviewers: []          # 승인 불필요
    wait_timer: 0                   # 대기 시간 없음
  deployment_branch_policy:
    protected_branches: true        # main 브랜치만 허용

# Production Environment
production:
  protection_rules:
    required_reviewers:             # 수동 승인 필요
      - team/senior-developers
      - team/tech-leads
    wait_timer: 5                   # 5분 대기 (쿨다운)
  deployment_branch_policy:
    protected_branches: true        # main 브랜치만 허용
```

---

## 5. 환경별 배포 전략

### 5.1 환경 구성 개요

| 구분 | Development | Staging | Production |
|------|-------------|---------|------------|
| 목적 | 개발/테스트 | QA/통합 검증 | 실서비스 운영 |
| 배포 트리거 | feature/* push | main push (자동) | 수동 승인 |
| 인프라 | 로컬 Docker Compose | Cloud Run (축소) | Cloud Run (확장) |
| DB | 로컬 PostgreSQL | Cloud SQL (소형) | Cloud SQL (고가용성) |
| 도메인 | localhost:8000 | staging-api.marketscope.ai | api.marketscope.ai |
| 로그 레벨 | DEBUG | INFO | WARNING |
| 모니터링 | 없음 | 기본 메트릭 | 전체 모니터링 + 알림 |
| 데이터 | 시드 데이터 | 샘플 데이터 | 실제 운영 데이터 |

### 5.2 환경별 설정 파일

```python
# app/core/config.py
from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"

    # Database
    DATABASE_URL: str = "postgresql://localhost:5432/marketscope"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # API Keys
    OPENAI_API_KEY: str = ""
    GOOGLE_MAPS_API_KEY: str = ""

    # Application
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    class Config:
        env_file = ".env"
        case_sensitive = True
```

### 5.3 Development 환경 (로컬)

```yaml
# docker-compose.dev.yml
version: "3.8"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - DATABASE_URL=postgresql://marketscope:devpass@postgres:5432/marketscope
      - REDIS_URL=redis://redis:6379/0
      - ENABLE_AUTO_MIGRATE=true
      - LOG_LEVEL=DEBUG
    volumes:
      - ./app:/app/app:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: marketscope
      POSTGRES_PASSWORD: devpass
      POSTGRES_DB: marketscope
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U marketscope"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  postgres_data:
```

### 5.4 환경 전환 매트릭스

```
feature/* branch
    │
    ├── 로컬 개발 (docker-compose.dev.yml)
    │
    └── PR 생성 ──► CI 파이프라인 (lint + test)
                        │
                        ▼
                    main merge ──► Staging 자동 배포
                                       │
                                       ▼
                                  수동 승인 ──► Production 배포
```

---

## 6. Alembic 자동 마이그레이션

### 6.1 마이그레이션 전략

배포 시 Alembic 마이그레이션을 자동으로 실행하여 데이터베이스 스키마를 애플리케이션 코드와 동기화한다.

### 6.2 마이그레이션 실행 방식

#### 6.2.1 Cloud Run Job 기반 실행

마이그레이션은 별도의 Cloud Run Job으로 실행하여 애플리케이션 배포와 분리한다.

```yaml
# Cloud Run Job 정의 (Terraform)
resource "google_cloud_run_v2_job" "migrate" {
  name     = "marketscope-migrate"
  location = var.region

  template {
    template {
      containers {
        image = var.image_url
        command = ["alembic"]
        args    = ["upgrade", "head"]

        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.database_url.secret_id
              version = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }

      timeout     = "300s"
      max_retries = 1

      vpc_access {
        connector = var.vpc_connector_id
        egress    = "PRIVATE_RANGES_ONLY"
      }
    }
  }
}
```

#### 6.2.2 마이그레이션 안전 규칙

| 규칙 | 설명 |
|------|------|
| 하위 호환성 | 모든 마이그레이션은 이전 버전 코드와 호환되어야 함 |
| 단일 방향 | `upgrade`만 자동 실행, `downgrade`는 수동으로만 실행 |
| 타임아웃 | 최대 300초 (5분) |
| 재시도 | 최대 1회 재시도 |
| 락 획득 | Advisory Lock을 사용하여 동시 마이그레이션 방지 |

#### 6.2.3 마이그레이션 파일 관리

```python
# alembic/env.py (핵심 설정)
from alembic import context
from sqlalchemy import engine_from_config, pool, text
from app.models import Base
import os

target_metadata = Base.metadata


def run_migrations_online():
    """온라인 마이그레이션 실행 (Advisory Lock 사용)"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Advisory Lock 획득 (동시 마이그레이션 방지)
        lock_id = 123456789  # 고유 락 ID
        connection.execute(text(f"SELECT pg_advisory_lock({lock_id})"))

        try:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )

            with context.begin_transaction():
                context.run_migrations()
        finally:
            connection.execute(text(f"SELECT pg_advisory_unlock({lock_id})"))
```

#### 6.2.4 마이그레이션 생성 가이드

```bash
# 마이그레이션 생성 (자동 감지)
alembic revision --autogenerate -m "add_user_preferences_table"

# 마이그레이션 이력 확인
alembic history --verbose

# 현재 리비전 확인
alembic current

# 특정 리비전까지 업그레이드
alembic upgrade <revision>

# 특정 리비전으로 다운그레이드 (수동 전용)
alembic downgrade <revision>
```

### 6.3 마이그레이션 CI 검증

```yaml
# CI에서 마이그레이션 검증 (ci.yml 내 추가 job)
migration-check:
  name: "Migration Validation"
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:15
      env:
        POSTGRES_USER: test
        POSTGRES_PASSWORD: test
        POSTGRES_DB: test
      ports:
        - 5432:5432
  steps:
    - uses: actions/checkout@v4

    - name: Install dependencies
      run: pip install -r requirements.txt

    - name: Check migration heads
      run: |
        # 단일 head 확인 (분기된 마이그레이션 방지)
        HEADS=$(alembic heads | wc -l)
        if [ "$HEADS" -gt 1 ]; then
          echo "ERROR: Multiple migration heads detected"
          alembic heads
          exit 1
        fi

    - name: Test upgrade from empty
      run: |
        alembic upgrade head
      env:
        DATABASE_URL: "postgresql://test:test@localhost:5432/test"

    - name: Test downgrade to base
      run: |
        alembic downgrade base
      env:
        DATABASE_URL: "postgresql://test:test@localhost:5432/test"
```

---

## 7. 롤백 절차

### 7.1 롤백 전략 개요

MarketScope AI는 **이전 리비전 재배포** 방식으로 롤백을 수행한다. Cloud Run의 리비전 관리 기능을 활용하여 즉시 롤백이 가능하다.

### 7.2 롤백 시나리오별 절차

#### 7.2.1 즉시 롤백 (애플리케이션 이슈)

데이터베이스 스키마 변경이 없는 경우, Cloud Run 리비전 트래픽 전환으로 즉시 롤백한다.

```bash
# 1. 현재 리비전 목록 확인
gcloud run revisions list \
  --service=marketscope-api \
  --region=asia-northeast3 \
  --limit=5

# 2. 이전 리비전으로 트래픽 전환 (즉시 롤백)
gcloud run services update-traffic marketscope-api \
  --region=asia-northeast3 \
  --to-revisions=marketscope-api-<previous-revision>=100

# 3. 롤백 확인
gcloud run services describe marketscope-api \
  --region=asia-northeast3 \
  --format='value(status.traffic)'
```

**예상 소요 시간**: 30초 ~ 1분

#### 7.2.2 마이그레이션 포함 롤백

데이터베이스 스키마 변경이 포함된 경우, 마이그레이션 다운그레이드 후 애플리케이션을 롤백한다.

```bash
# 1. 현재 마이그레이션 리비전 확인
alembic current

# 2. 다운그레이드 (수동 실행)
alembic downgrade -1  # 한 단계 롤백

# 3. 이전 Docker 이미지로 재배포
gcloud run deploy marketscope-api \
  --image=asia-northeast3-docker.pkg.dev/marketscope-ai/marketscope-repo/marketscope-api:<previous-sha> \
  --region=asia-northeast3
```

**예상 소요 시간**: 5분 ~ 10분

#### 7.2.3 자동 롤백 워크플로우

```yaml
# .github/workflows/rollback.yml
name: Emergency Rollback

on:
  workflow_dispatch:
    inputs:
      environment:
        description: "Target environment"
        required: true
        type: choice
        options:
          - staging
          - production
      revision_tag:
        description: "Docker image tag to rollback to"
        required: true
        type: string
      run_downgrade:
        description: "Run Alembic downgrade"
        required: false
        type: boolean
        default: false
      downgrade_revision:
        description: "Alembic revision to downgrade to"
        required: false
        type: string

jobs:
  rollback:
    name: "Rollback to ${{ inputs.revision_tag }}"
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    steps:
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}

      - name: Alembic downgrade (if requested)
        if: inputs.run_downgrade == true
        run: |
          gcloud run jobs execute marketscope-migrate \
            --region=asia-northeast3 \
            --wait \
            --args="downgrade,${{ inputs.downgrade_revision }}"

      - name: Deploy previous revision
        run: |
          SERVICE_SUFFIX=""
          if [ "${{ inputs.environment }}" == "staging" ]; then
            SERVICE_SUFFIX="-staging"
          fi

          gcloud run deploy marketscope-api${SERVICE_SUFFIX} \
            --image=asia-northeast3-docker.pkg.dev/marketscope-ai/marketscope-repo/marketscope-api:${{ inputs.revision_tag }} \
            --region=asia-northeast3

      - name: Verify rollback
        run: |
          SERVICE_SUFFIX=""
          if [ "${{ inputs.environment }}" == "staging" ]; then
            SERVICE_SUFFIX="-staging"
          fi

          URL=$(gcloud run services describe marketscope-api${SERVICE_SUFFIX} \
            --region=asia-northeast3 \
            --format='value(status.url)')

          HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL/health")
          echo "Health check status: $HTTP_STATUS"
          [ "$HTTP_STATUS" == "200" ] || exit 1

      - name: Notify rollback completion
        uses: slackapi/slack-github-action@v1.25.0
        with:
          payload: |
            {
              "text": "🔄 Rollback completed: ${{ inputs.environment }} → ${{ inputs.revision_tag }}"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### 7.3 롤백 판단 기준

| 지표 | 임계값 | 판단 |
|------|--------|------|
| HTTP 5xx 에러율 | > 5% | 즉시 롤백 |
| 응답 시간 (P99) | > 5초 | 모니터링 후 롤백 판단 |
| Health check 실패 | 연속 3회 | 즉시 롤백 |
| 배포 후 에러 로그 급증 | 10배 이상 증가 | 모니터링 후 롤백 판단 |

---

## 8. 시크릿 관리

### 8.1 시크릿 관리 전략

2단계 시크릿 관리 구조를 사용한다:
- **GitHub Secrets**: CI/CD 파이프라인 실행에 필요한 시크릿
- **GCP Secret Manager**: 런타임 애플리케이션에 필요한 시크릿

### 8.2 GitHub Secrets 구성

#### 8.2.1 Repository Secrets

| 시크릿 이름 | 용도 | 사용 위치 |
|-------------|------|-----------|
| `WIF_PROVIDER` | Workload Identity Federation Provider | 모든 GCP 인증 |
| `WIF_SERVICE_ACCOUNT` | GCP 서비스 계정 | 모든 GCP 인증 |
| `SLACK_WEBHOOK_URL` | Slack 알림 | 배포/롤백 알림 |

#### 8.2.2 Environment Secrets

**Staging Environment**:

| 시크릿 이름 | 용도 |
|-------------|------|
| `STAGING_DATABASE_URL` | Staging DB 연결 문자열 |
| `STAGING_REDIS_URL` | Staging Redis 연결 문자열 |

**Production Environment**:

| 시크릿 이름 | 용도 |
|-------------|------|
| `PROD_DATABASE_URL` | Production DB 연결 문자열 |
| `PROD_REDIS_URL` | Production Redis 연결 문자열 |

### 8.3 GCP Secret Manager 구성

```bash
# 시크릿 생성 예시
gcloud secrets create openai-api-key \
  --replication-policy="user-managed" \
  --locations="asia-northeast3"

# 시크릿 값 설정
echo -n "sk-xxxx" | gcloud secrets versions add openai-api-key --data-file=-

# Cloud Run 서비스 계정에 접근 권한 부여
gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:marketscope-api@marketscope-ai.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**런타임 시크릿 목록**:

| GCP Secret 이름 | 설명 |
|-----------------|------|
| `prod-database-url` | PostgreSQL 연결 문자열 |
| `prod-redis-url` | Redis 연결 문자열 |
| `openai-api-key` | OpenAI API 키 |
| `google-maps-api-key` | Google Maps API 키 |
| `naver-client-id` | Naver API Client ID |
| `naver-client-secret` | Naver API Client Secret |
| `jwt-secret-key` | JWT 서명 키 |

### 8.4 시크릿 보안 원칙

1. **최소 권한 원칙**: 각 환경의 서비스 계정은 해당 환경의 시크릿만 접근 가능
2. **자동 로테이션**: API 키는 90일 주기로 로테이션 권장
3. **감사 로깅**: 모든 시크릿 접근은 Cloud Audit Logs에 기록
4. **코드 내 하드코딩 금지**: `.env` 파일은 `.gitignore`에 반드시 포함
5. **PR 검증**: `git-secrets` 또는 `trufflehog`를 CI에 통합하여 시크릿 유출 방지

```yaml
# CI에 시크릿 스캔 추가
secret-scan:
  name: "Secret Scan"
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0

    - name: TruffleHog scan
      uses: trufflesecurity/trufflehog@main
      with:
        extra_args: --only-verified
```

---

## 9. PR 자동 검증

### 9.1 Required Status Checks

GitHub Branch Protection Rules를 통해 PR 병합 전 필수 검증 항목을 설정한다.

#### 9.1.1 필수 검증 항목 (Required Checks)

| Check 이름 | 설명 | 실패 시 |
|------------|------|---------|
| `Lint & Format Check` | Ruff 린팅 및 포맷 검증 | PR 병합 차단 |
| `Unit Tests` | 단위 테스트 통과 | PR 병합 차단 |
| `Integration Tests` | 통합 테스트 통과 | PR 병합 차단 |
| `Coverage Report` | 커버리지 80% 이상 | PR 병합 차단 |
| `Secret Scan` | 시크릿 유출 검사 | PR 병합 차단 |

#### 9.1.2 Branch Protection 설정

```yaml
# GitHub Repository Settings → Branches → Branch protection rules

main:
  required_status_checks:
    strict: true                    # 최신 base branch와 동기화 필수
    contexts:
      - "Lint & Format Check"
      - "Unit Tests"
      - "Integration Tests"
      - "Coverage Report"
      - "Secret Scan"
  required_pull_request_reviews:
    required_approving_review_count: 1
    dismiss_stale_reviews: true     # 새 커밋 push 시 기존 리뷰 무효화
    require_code_owner_reviews: true
  restrictions:
    users: []
    teams: [tech-leads]            # tech-leads 팀만 직접 push 가능
  enforce_admins: true              # 관리자에게도 규칙 적용
  required_linear_history: true     # Squash merge 강제
  allow_force_pushes: false
  allow_deletions: false

develop:
  required_status_checks:
    strict: false
    contexts:
      - "Lint & Format Check"
      - "Unit Tests"
  required_pull_request_reviews:
    required_approving_review_count: 1
    dismiss_stale_reviews: false
```

### 9.2 PR 자동화 봇

```yaml
# .github/workflows/pr-automation.yml
name: PR Automation

on:
  pull_request:
    types: [opened, synchronize, ready_for_review]

jobs:
  auto-label:
    name: "Auto Label PR"
    runs-on: ubuntu-latest
    steps:
      - uses: actions/labeler@v5
        with:
          repo-token: ${{ secrets.GITHUB_TOKEN }}

  size-label:
    name: "PR Size Label"
    runs-on: ubuntu-latest
    steps:
      - uses: codelytv/pr-size-labeler@v1
        with:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          xs_label: "size/XS"
          xs_max_size: 10
          s_label: "size/S"
          s_max_size: 50
          m_label: "size/M"
          m_max_size: 200
          l_label: "size/L"
          l_max_size: 500
          xl_label: "size/XL"
          fail_if_xl: true          # XL PR은 경고
```

### 9.3 CODEOWNERS 설정

```
# .github/CODEOWNERS

# 전체 프로젝트
*                           @marketscope/backend-team

# 인프라 및 배포 설정
.github/                    @marketscope/devops-team
Dockerfile                  @marketscope/devops-team
docker-compose*.yml         @marketscope/devops-team

# 데이터베이스 마이그레이션
alembic/                    @marketscope/backend-team @marketscope/tech-leads

# API 엔드포인트
app/api/                    @marketscope/backend-team

# AI 에이전트
app/agents/                 @marketscope/ai-team

# 프론트엔드
frontend/                   @marketscope/frontend-team

# 보안 관련 설정
app/core/security.py        @marketscope/tech-leads
app/core/config.py          @marketscope/tech-leads
```

---

## 10. 브랜치 전략

### 10.1 브랜치 모델

MarketScope AI는 **GitHub Flow** 기반의 간소화된 브랜치 전략을 채택한다.

```
main (production-ready)
  │
  ├── develop (통합 브랜치, 선택적)
  │     │
  │     ├── feature/add-user-auth
  │     ├── feature/implement-debate-system
  │     ├── feature/mcp-naver-maps
  │     │
  │     ├── fix/api-timeout-error
  │     ├── fix/memory-leak-agent
  │     │
  │     └── chore/update-dependencies
  │
  ├── hotfix/critical-security-patch  (main에서 직접 분기)
  │
  └── release/v1.2.0  (선택적, 릴리스 준비 시)
```

### 10.2 브랜치 명명 규칙

| 접두사 | 용도 | 예시 |
|--------|------|------|
| `feature/` | 새 기능 개발 | `feature/add-catchment-analysis` |
| `fix/` | 버그 수정 | `fix/api-response-timeout` |
| `hotfix/` | 긴급 프로덕션 수정 | `hotfix/security-vulnerability` |
| `chore/` | 유지보수, 의존성 업데이트 | `chore/update-ruff-config` |
| `refactor/` | 코드 리팩토링 | `refactor/agent-base-class` |
| `docs/` | 문서 작업 | `docs/api-endpoint-guide` |
| `release/` | 릴리스 준비 | `release/v1.2.0` |

### 10.3 브랜치별 워크플로우

#### 10.3.1 Feature 브랜치

```bash
# 1. develop에서 feature 브랜치 생성
git checkout develop
git pull origin develop
git checkout -b feature/add-catchment-analysis

# 2. 개발 작업 수행 및 커밋
git add .
git commit -m "feat: 상권 분석 기능 추가"

# 3. 원격에 push
git push -u origin feature/add-catchment-analysis

# 4. PR 생성 (develop → main)
# GitHub UI 또는 gh CLI 사용
gh pr create --base develop --title "feat: 상권 분석 기능 추가"

# 5. CI 통과 + 코드 리뷰 후 Squash Merge
```

#### 10.3.2 Hotfix 브랜치

```bash
# 1. main에서 직접 hotfix 브랜치 생성
git checkout main
git pull origin main
git checkout -b hotfix/critical-security-patch

# 2. 긴급 수정 작업
git add .
git commit -m "fix: 인증 우회 취약점 수정"

# 3. main으로 PR 생성 (긴급 리뷰)
gh pr create --base main --title "hotfix: 인증 우회 취약점 긴급 수정"

# 4. 빠른 리뷰 후 병합 → 자동 배포
# 5. develop 브랜치에도 변경사항 반영
git checkout develop
git merge main
git push origin develop
```

### 10.4 커밋 메시지 규칙

[Conventional Commits](https://www.conventionalcommits.org/) 규칙을 따른다.

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Type 목록**:

| Type | 설명 |
|------|------|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `docs` | 문서 변경 |
| `style` | 코드 스타일 (포맷팅, 세미콜론 등) |
| `refactor` | 리팩토링 |
| `test` | 테스트 추가/수정 |
| `chore` | 빌드, CI, 의존성 등 기타 |
| `perf` | 성능 개선 |

**예시**:

```
feat(agents): Commander Agent 토론 시스템 통합

- LangGraph 기반 멀티 에이전트 토론 플로우 구현
- 3라운드 토론 후 최종 결론 도출 로직 추가
- 토론 결과 메모리 저장 기능 연동

Closes #42
```

### 10.5 Merge 전략

| 대상 브랜치 | Merge 방식 | 이유 |
|------------|-----------|------|
| feature/* → develop | Squash Merge | 깔끔한 커밋 히스토리 유지 |
| develop → main | Merge Commit | 기능 단위 이력 보존 |
| hotfix/* → main | Squash Merge | 빠른 병합 |
| release/* → main | Merge Commit | 릴리스 이력 보존 |

---

## 부록

### A. CI/CD 파이프라인 체크리스트

**PR 생성 전 로컬 검증**:

```bash
# 린팅
ruff check .
ruff format --check .

# 단위 테스트
pytest tests/unit/ -v --cov=app

# 통합 테스트 (docker-compose 필요)
docker compose -f docker-compose.dev.yml up -d postgres redis
pytest tests/integration/ -v

# 마이그레이션 확인
alembic check  # 미적용 마이그레이션 확인
```

**배포 전 검증 체크리스트**:

- [ ] 모든 CI 검사 통과
- [ ] 코드 리뷰 승인 완료
- [ ] 마이그레이션 하위 호환성 확인
- [ ] Staging 스모크 테스트 통과
- [ ] (Production) 수동 승인 완료

### B. 트러블슈팅 가이드

| 문제 | 원인 | 해결 |
|------|------|------|
| CI 테스트 타임아웃 | 서비스 컨테이너 시작 지연 | `health-check` 옵션의 `retries` 증가 |
| Docker 빌드 캐시 미스 | `requirements.txt` 변경 | 의존성 변경 최소화, 레이어 캐시 활용 |
| 마이그레이션 충돌 | 동시 마이그레이션 생성 | `alembic merge heads` 실행 |
| Staging 배포 실패 | GCP 인증 만료 | WIF 설정 확인, 서비스 계정 권한 검증 |
| 롤백 후 데이터 불일치 | 마이그레이션 비가역적 변경 | 마이그레이션 작성 시 `downgrade` 함수 필수 구현 |

### C. 참고 문서

- [GitHub Actions 공식 문서](https://docs.github.com/en/actions)
- [Google Cloud Run 배포 가이드](https://cloud.google.com/run/docs/deploying)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Ruff 공식 문서](https://docs.astral.sh/ruff/)
- [Conventional Commits](https://www.conventionalcommits.org/)
