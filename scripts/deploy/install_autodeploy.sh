#!/usr/bin/env bash
# 자동배포 systemd 유닛 설치 (sudo 필요 — 사용자가 직접 실행)
#   sudo bash scripts/deploy/install_autodeploy.sh
# 비활성화:
#   sudo systemctl disable --now marketscope-autodeploy.timer
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
UNIT_SRC="$REPO_DIR/deploy/systemd"

if [ "$(id -u)" -ne 0 ]; then
    echo "run with sudo: sudo bash scripts/deploy/install_autodeploy.sh" >&2
    exit 1
fi

install -m 644 "$UNIT_SRC/marketscope-autodeploy.service" /etc/systemd/system/
install -m 644 "$UNIT_SRC/marketscope-autodeploy.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now marketscope-autodeploy.timer

echo "installed. status:"
systemctl status marketscope-autodeploy.timer --no-pager || true
echo
echo "다음 발화 예정:"
systemctl list-timers marketscope-autodeploy.timer --no-pager || true
