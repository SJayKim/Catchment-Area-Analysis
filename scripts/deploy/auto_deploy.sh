#!/usr/bin/env bash
# auto_deploy.sh — origin/main push 자동배포 (폴링 방식)
#
# systemd timer(2분)가 호출. 수동 단독 실행도 가능:
#   bash scripts/deploy/auto_deploy.sh            # 신규 커밋 없으면 no-op exit 0
#   bash scripts/deploy/auto_deploy.sh --force    # 현 origin/main tip 강제 재배포
#
# 흐름: flock → fetch → no-op 판정 → 가드(dirty/ahead/branch) → CI green 게이트
#      → prev-auto 재태그 → ff merge → 빌드(.env.dev 임시이동) → up -d → healthy 대기
#      → flush_cache → smoke 4항목 → 실패 시 prev-auto 자동 롤백
#
# 설계 근거: docs/plan/infra/auto-deploy-on-push.md
# golden path: docs/plan/infra/prod-deploy-2026-07-04.md (수동 런로그의 코드화)

# -E(errtrace): 함수 내부 실패도 ERR trap(→자동 롤백)으로 전파
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_DIR"

# ---------------------------------------------------------------- 상수/경로
COMPOSE_FILE="docker-compose.prod.yml"
IMAGE_PREFIX="catchment-area-analysis"          # prod compose project 이미지 prefix
IMAGES=(backend frontend migrate)
STATE_DIR="$REPO_DIR/data/deploy-logs"
LOCK_FILE="$STATE_DIR/.autodeploy.lock"
STATUS_FILE="$STATE_DIR/last-deploy.json"
DEPLOYED_SHA_FILE="$STATE_DIR/.last-deployed-sha"  # 마지막 SUCCESS 배포 SHA (no-op 기준)
BLOCKED_SHA_FILE="$STATE_DIR/blocked-shas.txt"  # CI failure / 배포실패 SHA — 재시도 방지
GITHUB_REPO="SJayKim/Catchment-Area-Analysis"
EXTERNAL_URL="https://marketscope.robitlabs.co.kr"
HEALTHY_TIMEOUT=180
# dirty 가드 허용목록 (tracked 변경이어도 배포를 막지 않는 파일)
DIRTY_ALLOWLIST=".claude/settings.local.json"

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

mkdir -p "$STATE_DIR"

# ---------------------------------------------------------------- 잠금 (동시 실행 차단)
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "[autodeploy] another run in progress — skip"
    exit 0
fi

log() { echo "[autodeploy $(date '+%F %T')] $*"; }

# ---------------------------------------------------------------- 상태 파일
write_status() { # $1=result $2=sha $3=detail
    jq -n --arg result "$1" --arg sha "$2" --arg detail "$3" \
        --arg ts "$(date -Is)" --arg log "${RUN_LOG:-}" \
        '{result:$result, sha:$sha, detail:$detail, ts:$ts, log:$log}' >"$STATUS_FILE"
}

# ---------------------------------------------------------------- env 위생
# 호스트 셸 env 가 compose 의 .env 값을 뒤집는 사고 차단
# (교훈: compose env 블록이 env_file 오버라이드 + 호스트 셸 env 흡수, 2026-07-02)
unset USE_MOCK AGENT_LOOP_VERSION AGENT_MODE LLM_PROVIDER \
    NEXT_PUBLIC_API_URL NEXT_PUBLIC_KAKAO_MAP_KEY BACKEND_INTERNAL_URL \
    ANTHROPIC_API_KEY GOOGLE_API_KEY DATABASE_URL DATABASE_URL_SYNC REDIS_URL \
    LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY LANGFUSE_HOST \
    LANGFUSE_TRACING_ENVIRONMENT LANGFUSE_SAMPLING_RATE LANGFUSE_SESSION_SALT \
    LANGFUSE_OTEL_INSECURE COMPOSE_PROJECT_NAME 2>/dev/null || true

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

# ---------------------------------------------------------------- 1) fetch + no-op 판정
if ! git fetch -q origin main; then
    log "git fetch failed (network?) — retry next tick"
    exit 0
fi

LOCAL_SHA="$(git rev-parse HEAD)"
REMOTE_SHA="$(git rev-parse origin/main)"
SHORT_SHA="${REMOTE_SHA:0:7}"

# no-op 기준은 git HEAD 가 아닌 "마지막 배포 SHA" — 본 서버에서 직접 커밋→push 하면
# HEAD == origin/main 이라 HEAD 비교로는 영원히 no-op (이미지가 stale 하게 남는 원 문제 재발).
# 진짜 배포 상태는 워킹트리가 아니라 이미지이므로 SUCCESS 시 기록한 SHA 와 비교한다.
LAST_DEPLOYED="$(cat "$DEPLOYED_SHA_FILE" 2>/dev/null || echo "")"
if [ "$REMOTE_SHA" = "$LAST_DEPLOYED" ] && [ "$FORCE" -eq 0 ]; then
    # no-op: 로그 파일 미생성 (플랜 §흐름-3)
    exit 0
fi

# ---------------------------------------------------------------- 2) 안전 가드
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
    log "BLOCKED_BRANCH: HEAD is on '$BRANCH', not main"
    write_status "BLOCKED_BRANCH" "$REMOTE_SHA" "checked out branch=$BRANCH"
    exit 0
fi

# dirty: tracked 변경이 허용목록 외 존재 시 차단 (untracked 는 ff merge 에 무해 — 통과)
DIRTY="$(git status --porcelain --untracked-files=no | grep -vF "$DIRTY_ALLOWLIST" || true)"
if [ -n "$DIRTY" ]; then
    log "BLOCKED_DIRTY: uncommitted tracked changes — never reset, resolve manually"
    log "$DIRTY"
    write_status "BLOCKED_DIRTY" "$REMOTE_SHA" "$(echo "$DIRTY" | head -5 | tr '\n' ';')"
    exit 0
fi

# ahead: 서버 로컬 커밋 존재 → ff 불가. 자동 push 는 하지 않음 (사용자 판단)
AHEAD="$(git rev-list --count origin/main..main)"
if [ "$AHEAD" -gt 0 ]; then
    log "BLOCKED_AHEAD: local main is $AHEAD commit(s) ahead of origin — push manually first"
    write_status "BLOCKED_AHEAD" "$REMOTE_SHA" "local ahead by $AHEAD"
    exit 0
fi

# ---------------------------------------------------------------- 3) CI green 게이트
if [ "$FORCE" -eq 0 ] && [ -f "$BLOCKED_SHA_FILE" ] && grep -qF "$REMOTE_SHA" "$BLOCKED_SHA_FILE"; then
    # CI failure 로 이미 차단된 SHA — 매 tick 재조회하지 않음
    exit 0
fi

ci_gate() { # stdout: green | pending | failure | api-error
    local auth=() resp
    [ -n "${GITHUB_TOKEN:-}" ] && auth=(-H "Authorization: Bearer $GITHUB_TOKEN")
    resp="$(curl -fsS -m 20 "${auth[@]}" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/$GITHUB_REPO/commits/$REMOTE_SHA/check-runs?per_page=100" \
        2>/dev/null)" || { echo "api-error"; return 0; }
    echo "$resp" | jq -r '
        if .total_count == 0 then "pending"
        elif ([.check_runs[].conclusion] | map(select(. != null))
              | any(IN("failure","cancelled","timed_out","action_required"))) then "failure"
        elif ([.check_runs[].status] | any(. != "completed")) then "pending"
        else "green" end'
}

CI_RESULT="$(ci_gate)"
case "$CI_RESULT" in
green) log "CI green for $SHORT_SHA" ;;
pending | api-error)
    log "CI $CI_RESULT for $SHORT_SHA — wait next tick"
    exit 0
    ;;
failure)
    log "BLOCKED_CI: check-runs failure for $SHORT_SHA — will not retry this SHA"
    echo "$REMOTE_SHA" >>"$BLOCKED_SHA_FILE"
    write_status "BLOCKED_CI" "$REMOTE_SHA" "check-runs conclusion=failure"
    exit 0
    ;;
esac

# ================================================================ 배포 시작
DEPLOY_START_EPOCH="$(date +%s)"
RUN_LOG="$STATE_DIR/deploy-$(date +%Y%m%d-%H%M%S)-$SHORT_SHA.log"
exec > >(tee -a "$RUN_LOG") 2>&1
log "deploying $LOCAL_SHA -> $REMOTE_SHA (force=$FORCE)"
write_status "DEPLOYING" "$REMOTE_SHA" "started"

# --- .env.dev 임시 이동 (빌드 bake-in 방지, trap 으로 원복 보장) ---
ENV_DEV="$REPO_DIR/.env.dev"
ENV_DEV_BAK="$REPO_DIR/.env.dev.autodeploy-moved"
ENV_DEV_MOVED=0
restore_env_dev() {
    if [ "$ENV_DEV_MOVED" -eq 1 ] && [ -f "$ENV_DEV_BAK" ]; then
        mv "$ENV_DEV_BAK" "$ENV_DEV"
        ENV_DEV_MOVED=0
        log ".env.dev restored"
    fi
}
trap restore_env_dev EXIT

rollback() {
    log "ROLLBACK: retagging prev-auto -> latest and recreating"
    local img
    for img in "${IMAGES[@]}"; do
        if docker image inspect "$IMAGE_PREFIX-$img:prev-auto" >/dev/null 2>&1; then
            docker tag "$IMAGE_PREFIX-$img:prev-auto" "$IMAGE_PREFIX-$img:latest"
        else
            log "WARN: $IMAGE_PREFIX-$img:prev-auto missing — cannot roll back this image"
        fi
    done
    compose up -d --force-recreate backend frontend || true
    # 실패 SHA 재시도 방지 — no-op 기준이 deployed-sha 라 이게 없으면 매 tick 재배포 루프
    echo "$REMOTE_SHA" >>"$BLOCKED_SHA_FILE"
    if wait_healthy && wait_frontend && smoke; then
        log "rollback smoke OK — service restored on prev-auto"
        write_status "ROLLED_BACK" "$REMOTE_SHA" "deploy failed at: ${FAILED_STEP:-unknown}; prev-auto restored, smoke OK"
    else
        log "CRITICAL: rollback smoke FAILED — manual intervention required"
        write_status "ROLLBACK_FAILED" "$REMOTE_SHA" "deploy failed at: ${FAILED_STEP:-unknown}; prev-auto smoke also failed"
    fi
}

on_error() {
    trap - ERR # 롤백 중 재귀 방지
    local step="${FAILED_STEP:-unknown}"
    log "deploy step failed: $step"
    restore_env_dev
    rollback
    exit 1
}
trap on_error ERR

wait_healthy() {
    local cid status waited=0
    cid="$(compose ps -q backend)"
    [ -n "$cid" ] || { log "backend container not found"; return 1; }
    while [ "$waited" -lt "$HEALTHY_TIMEOUT" ]; do
        status="$(docker inspect --format '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo missing)"
        [ "$status" = "healthy" ] && return 0
        sleep 5
        waited=$((waited + 5))
    done
    log "backend not healthy after ${HEALTHY_TIMEOUT}s (last=$status)"
    return 1
}

# frontend 는 compose healthcheck 이 없어 recreate 직후 cold start(~10-20s) 동안 :3200 거부
# — smoke 는 검증 전용으로 유지하고 준비 대기는 여기서 (C10 리허설에서 가짜 ROLLBACK_FAILED 실증)
wait_frontend() {
    local waited=0
    while [ "$waited" -lt 90 ]; do
        curl -fsS -m 5 -o /dev/null http://localhost:3200 2>/dev/null && return 0
        sleep 5
        waited=$((waited + 5))
    done
    log "frontend not responding on :3200 after 90s"
    return 1
}

smoke() {
    local total
    curl -fsS -m 10 -o /dev/null http://localhost:8000/health || { log "smoke FAIL: :8000/health"; return 1; }
    curl -fsS -m 10 -o /dev/null http://localhost:3200 || { log "smoke FAIL: :3200"; return 1; }
    # 외부 nginx 라우팅 양방향: / → frontend, /api/ → backend (backend 루트 /health 는 외부 미노출)
    curl -fsS -m 15 -o /dev/null "$EXTERNAL_URL/" || { log "smoke FAIL: $EXTERNAL_URL/"; return 1; }
    curl -fsS -m 15 -o /dev/null "$EXTERNAL_URL/api/health/detail" || { log "smoke FAIL: $EXTERNAL_URL/api/health/detail"; return 1; }
    total="$(curl -fsS -m 15 "http://localhost:8000/api/districts?limit=1" | jq -r '.total // 0')" \
        || { log "smoke FAIL: /api/districts unreachable"; return 1; }
    [ "$total" -gt 0 ] || { log "smoke FAIL: districts total=$total"; return 1; }
    log "smoke OK (districts total=$total)"
    return 0
}

# --- 5) 롤백 준비: 현행 이미지 prev-auto 재태그 ---
FAILED_STEP="retag prev-auto"
for img in "${IMAGES[@]}"; do
    if docker image inspect "$IMAGE_PREFIX-$img:latest" >/dev/null 2>&1; then
        docker tag "$IMAGE_PREFIX-$img:latest" "$IMAGE_PREFIX-$img:prev-auto"
    fi
done
log "prev-auto tags updated"

# --- 6) ff merge ---
FAILED_STEP="git merge --ff-only"
git merge --ff-only origin/main
log "merged to $(git rev-parse --short HEAD)"

# --- 7) 빌드 (.env.dev 임시 이동) ---
FAILED_STEP="docker build"
if [ -f "$ENV_DEV" ]; then
    mv "$ENV_DEV" "$ENV_DEV_BAK"
    ENV_DEV_MOVED=1
    log ".env.dev moved aside for build"
fi
compose build backend frontend migrate
restore_env_dev

# stale-image 마커: 빌드 산출물이 이번 run 에서 생성됐는지 확인 (교훈: 6주 stale 이미지).
# 단, 소스 컨텍스트(server/·frontend/)가 변하지 않은 push 는 전체 캐시 히트로
# Created 가 갱신되지 않는 게 정상 (C10 리허설 실증) — 소스 변경 push 에만 적용.
FAILED_STEP="image freshness check"
if [ -z "$LAST_DEPLOYED" ]; then
    log "freshness check skipped — no last-deployed sha (bootstrap)"
elif git diff --quiet "$LAST_DEPLOYED" "$REMOTE_SHA" -- server frontend 2>/dev/null; then
    log "freshness check skipped — server/·frontend/ unchanged since ${LAST_DEPLOYED:0:7} (cache-hit build OK)"
else
    IMG_CREATED="$(docker inspect --format '{{.Created}}' "$IMAGE_PREFIX-backend:latest")"
    IMG_EPOCH="$(date -d "$IMG_CREATED" +%s)"
    if [ "$IMG_EPOCH" -lt "$DEPLOY_START_EPOCH" ]; then
        log "backend image Created=$IMG_CREATED predates deploy start despite source changes — stale build"
        false # ERR trap → rollback
    fi
fi

# --- 8) 기동 + healthy 대기 ---
FAILED_STEP="compose up"
compose up -d
FAILED_STEP="backend healthy wait"
wait_healthy
FAILED_STEP="frontend ready wait"
wait_frontend

# --- 9) 캐시 flush (report 계열 포이즈닝 방지 — 배포 필수 스텝) ---
FAILED_STEP="flush_cache"
compose exec -T backend python scripts/flush_cache.py

# --- 10) smoke ---
FAILED_STEP="smoke"
smoke

# --- 12) 성공 기록 ---
trap - ERR
echo "$REMOTE_SHA" >"$DEPLOYED_SHA_FILE"
write_status "SUCCESS" "$REMOTE_SHA" "deployed and smoke passed"
log "deploy SUCCESS: $REMOTE_SHA"
