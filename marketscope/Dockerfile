FROM python:3.11-slim AS base

# 시스템 의존성 (PostGIS 클라이언트, proj)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev libproj-dev gcc tzdata curl \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Seoul

WORKDIR /app

# 의존성 설치 (캐시 레이어) — workspace 패키지 pyproject.toml 먼저 복사
COPY pyproject.toml ./
COPY common/pyproject.toml common/pyproject.toml
COPY mcp/pyproject.toml mcp/pyproject.toml
COPY agent/pyproject.toml agent/pyproject.toml
COPY api/pyproject.toml api/pyproject.toml
COPY pipeline/pyproject.toml pipeline/pyproject.toml

# 빈 패키지 구조만 생성하여 pip resolve 통과
RUN mkdir -p common/src/marketscope_common \
    && touch common/src/marketscope_common/__init__.py \
    && mkdir -p mcp/src/marketscope_mcp \
    && touch mcp/src/marketscope_mcp/__init__.py \
    && mkdir -p agent/src/marketscope_agent \
    && touch agent/src/marketscope_agent/__init__.py \
    && mkdir -p api/src/marketscope_api \
    && touch api/src/marketscope_api/__init__.py \
    && mkdir -p pipeline/src/marketscope_pipeline \
    && touch pipeline/src/marketscope_pipeline/__init__.py

RUN pip install --no-cache-dir -e common/ -e mcp/ -e agent/ -e api/ -e pipeline/ .

# 소스 복사 (캐시 무효화 최소화를 위해 마지막에)
COPY . .

# 패키지 재설치 (editable 모드로 실제 소스 반영)
RUN pip install --no-cache-dir --no-deps -e common/ -e mcp/ -e agent/ -e api/ -e pipeline/

# 기본 환경변수
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV APP_ENV=production

EXPOSE 8000

# 기본 CMD: API 서버 (docker-compose에서 override 가능)
CMD ["uvicorn", "marketscope_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
