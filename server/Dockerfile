FROM python:3.12-slim AS builder
WORKDIR /build
# pip SSL 우회용 build-arg (기본값은 HTTPS PyPI — 변경 없음).
# SSL CERTIFICATE_VERIFY_FAILED 발생 환경에서만:
#   docker compose build --build-arg PIP_INDEX_URL=http://pypi.org/simple \
#                        --build-arg PIP_TRUSTED_HOST=pypi.org backend
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}
# pip isolated build subprocess 는 env 를 상속하지 않으므로 pip.conf 로 고정
RUN mkdir -p /etc/pip && printf "[global]\nindex-url = %s\ntrusted-host = %s\n" \
    "${PIP_INDEX_URL}" "${PIP_TRUSTED_HOST}" > /etc/pip.conf
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc g++ && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runner
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
COPY . .
RUN adduser --disabled-password --no-create-home --gecos "" appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
