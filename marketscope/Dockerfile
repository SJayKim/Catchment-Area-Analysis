FROM python:3.11-slim AS base

# 시스템 의존성 (PostGIS 클라이언트, proj)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev libproj-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 설치 (캐시 레이어)
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# 소스 복사
COPY . .

# 기본 환경변수
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV APP_ENV=production

EXPOSE 8000

# 기본 CMD: API 서버 (docker-compose에서 override 가능)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
