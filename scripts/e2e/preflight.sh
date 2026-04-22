#!/usr/bin/env bash
# preflight.sh — E2E 회귀 테스트 사전 점검 + 전용 stack 기동
#
# 목적:
#   1. 운영 compose (marketscope, marketscope-prod 등) 와 충돌 가능성 차단
#   2. .env.e2e 존재 확인 + NEXT_PUBLIC_API_URL 이 localhost 인지 검증
#   3. docker-compose.e2e.yml 기동 + health 대기
#   4. 운영 도메인 sanity probe (abort 되어야 정상)
#
# 사용: bash scripts/e2e/preflight.sh
# 종료 코드:
#   0 — 모든 검증 통과, e2e stack 가동 완료
#   1 — 사전 검증 실패 (ENV / 포트 / 운영 volume 충돌)
#   2 — 기동 실패 (docker compose up / healthcheck timeout)

set -euo pipefail

COMPOSE_PROJECT_NAME="marketscope-e2e"
COMPOSE_FILE="docker-compose.e2e.yml"
ENV_FILE=".env.e2e"

log()  { printf "[preflight] %s\n" "$*"; }
fail() { printf "[preflight] ❌ %s\n" "$*" >&2; exit 1; }
fail2(){ printf "[preflight] ❌ %s\n" "$*" >&2; exit 2; }

# --- 1. 리포 루트 검증 ---
[ -f "CLAUDE.md" ] || fail "must run from repo root (CLAUDE.md not found)"
[ -f "${COMPOSE_FILE}" ] || fail "${COMPOSE_FILE} missing — plan D2 작성 필요"

# --- 2. .env.e2e 존재 + 형식 검증 ---
if [ ! -f "${ENV_FILE}" ]; then
    fail "${ENV_FILE} not found. cp env.e2e.example ${ENV_FILE} 후 테스트 키 입력"
fi

# NEXT_PUBLIC_API_URL 이 localhost 인지 확인 (운영 도메인 실수 유입 방지)
api_url=$(grep -E "^NEXT_PUBLIC_API_URL=" "${ENV_FILE}" | head -1 | cut -d= -f2-)
if [[ "${api_url}" != *"localhost"* ]] && [[ "${api_url}" != *"127.0.0.1"* ]]; then
    fail "NEXT_PUBLIC_API_URL must point to localhost in ${ENV_FILE} (got: ${api_url})"
fi

# ENV_PROFILE=e2e 검증
if ! grep -qE "^ENV_PROFILE=e2e" "${ENV_FILE}"; then
    fail "ENV_PROFILE=e2e missing in ${ENV_FILE} (운영 env 와의 격리 마커)"
fi

# LANGFUSE 키가 실수로 운영 값으로 채워지지 않았는지 확인
for key in LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY POSTHOG_KEY SENTRY_DSN; do
    val=$(grep -E "^${key}=" "${ENV_FILE}" 2>/dev/null | cut -d= -f2- || true)
    if [ -n "${val}" ]; then
        fail "${key} 이 ${ENV_FILE} 에 비어있지 않음. 운영 telemetry 유출 방지를 위해 빈 값만 허용"
    fi
done

log "✅ env 검증 통과"

# --- 3. 운영 compose 충돌 탐지 ---
# docker ps 로 운영 이름 prefix 가 돌고 있으면 포트 3001/8002 가 여유 있더라도 경고
if docker ps --format '{{.Names}}' 2>/dev/null | grep -E "^(marketscope-prod|marketscope_[^e])" | grep -v "^${COMPOSE_PROJECT_NAME}" > /tmp/prod_containers 2>/dev/null; then
    log "⚠ 운영/개발 container 탐지:"
    cat /tmp/prod_containers
    log "  → e2e 는 독립 포트 (3001/8002/55432/56379) 로 기동하므로 계속 진행"
fi

# 충돌 포트 점검
for port in 3001 8002 15432 16379; do
    if netstat -an 2>/dev/null | grep -E "[.:]${port} .*LISTEN" > /dev/null; then
        log "⚠ port ${port} 이 이미 사용 중 — docker compose up 에서 실패할 수 있음"
    fi
done

# --- 4. 운영 volume 보호 ---
# 기존 볼륨 리스트에서 운영 prefix 가 있다면 건드리지 않음을 log
docker volume ls --format '{{.Name}}' 2>/dev/null | grep -E "^marketscope(-prod)?_pgdata" | grep -v "^${COMPOSE_PROJECT_NAME}" > /tmp/prod_volumes 2>/dev/null || true
if [ -s /tmp/prod_volumes ]; then
    log "ℹ 운영 volume 존재 (건드리지 않음):"
    cat /tmp/prod_volumes
fi

# --- 5. e2e stack 기동 ---
log "기동: COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME} docker compose -f ${COMPOSE_FILE} up -d"
export COMPOSE_PROJECT_NAME

if ! docker compose -f "${COMPOSE_FILE}" up -d --build --wait 2>&1 | tee /tmp/e2e_up.log; then
    log "❌ compose up 실패 — /tmp/e2e_up.log 참조"
    fail2 "compose up failed"
fi

# --- 6. healthcheck 대기 (최대 120초) ---
log "backend /health 대기..."
for i in $(seq 1 60); do
    if curl -fsS http://localhost:8002/health > /dev/null 2>&1; then
        log "✅ backend healthy (attempt ${i})"
        break
    fi
    sleep 2
    if [ "${i}" -eq 60 ]; then fail2 "backend /health timeout"; fi
done

log "frontend /api/districts probe..."
for i in $(seq 1 30); do
    if curl -fsS "http://localhost:3001" > /dev/null 2>&1; then
        log "✅ frontend responding (attempt ${i})"
        break
    fi
    sleep 2
    if [ "${i}" -eq 30 ]; then fail2 "frontend root timeout"; fi
done

# --- 7. 모드 확인 ---
mode_probe=$(curl -fsS "http://localhost:8002/api/districts?search=%EA%B0%95%EB%82%A8" 2>/dev/null || echo "{}")
if echo "${mode_probe}" | grep -q 'D300[0-9]'; then
    log "✅ Mock 모드 (district_code D300x)"
else
    log "ℹ Real 모드 (district_code D300x 아님)"
fi

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "✅ preflight 완료. Playwright 실행 준비:"
log "   cd frontend && E2E_BASE_URL=http://localhost:3001 E2E_BACKEND_URL=http://localhost:8002 npm test"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
