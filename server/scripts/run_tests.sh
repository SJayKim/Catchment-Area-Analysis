#!/usr/bin/env bash
# Backend pytest + coverage runner.
#
# Plan: docs/plan/infra/backend-pytest-coverage-expansion.md (C1).
#
# Usage:
#   ./scripts/run_tests.sh            # full suite, no coverage gate
#   COV_FAIL_UNDER=70 ./scripts/run_tests.sh   # enforce 70% line coverage
set -euo pipefail

cd "$(dirname "$0")/.."

export USE_MOCK="${USE_MOCK:-true}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"
# Mock mode skips external services; dummy keys keep config.py happy.
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-sk-ant-test-dummy}"
export GOOGLE_API_KEY="${GOOGLE_API_KEY:-test-dummy}"

cov_args=()
if [[ -n "${COV_FAIL_UNDER:-}" ]]; then
    cov_args=(--cov=server --cov-report=term-missing "--cov-fail-under=${COV_FAIL_UNDER}")
fi

exec python -m pytest tests/ -v "${cov_args[@]}" "$@"
