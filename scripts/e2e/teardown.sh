#!/usr/bin/env bash
# teardown.sh — E2E stack 정리 + 전용 volume 삭제
#
# 안전 가드:
#   - docker compose down --volumes 로 전용 volume 만 제거
#   - marketscope-e2e_ prefix 외 volume 은 절대 삭제하지 않음 (운영 보호)
#
# 사용: bash scripts/e2e/teardown.sh              # 일반 정리
#       bash scripts/e2e/teardown.sh --keep-data  # container 만 내리고 volume 유지
#
# 종료 코드: 0 — 정상 정리 / 1 — 안전 가드 위반 (운영 volume 감지 시)

set -euo pipefail

COMPOSE_PROJECT_NAME="marketscope-e2e"
COMPOSE_FILE="docker-compose.e2e.yml"
ALLOWED_VOLUME_PREFIX="marketscope-e2e_"

KEEP_DATA=0
if [ "${1:-}" = "--keep-data" ]; then
    KEEP_DATA=1
fi

log()  { printf "[teardown] %s\n" "$*"; }
fail() { printf "[teardown] ❌ %s\n" "$*" >&2; exit 1; }

[ -f "${COMPOSE_FILE}" ] || fail "${COMPOSE_FILE} missing"

export COMPOSE_PROJECT_NAME

if [ "${KEEP_DATA}" -eq 1 ]; then
    log "container 만 종료 (volume 유지)"
    docker compose -f "${COMPOSE_FILE}" down
    exit 0
fi

# --- 사전 안전 점검: 삭제 대상 volume 이 모두 허용 prefix 인지 ---
volumes_to_delete=$(docker volume ls --format '{{.Name}}' 2>/dev/null \
    | grep -E "^${COMPOSE_PROJECT_NAME}_" || true)

if [ -n "${volumes_to_delete}" ]; then
    log "삭제 예정 volume:"
    echo "${volumes_to_delete}" | sed 's/^/  - /'

    # prefix 가드: allowed prefix 외 이름이 한 개라도 있으면 중단
    while IFS= read -r v; do
        case "${v}" in
            ${ALLOWED_VOLUME_PREFIX}*) ;;
            *) fail "safety guard: '${v}' 이 허용 prefix (${ALLOWED_VOLUME_PREFIX}) 에 부합하지 않음. 수동 확인 필요." ;;
        esac
    done <<< "${volumes_to_delete}"
fi

log "docker compose down --volumes 실행"
docker compose -f "${COMPOSE_FILE}" down --volumes --remove-orphans

log "✅ teardown 완료"
