"""Validate the project .env file before docker compose up / build.

Checks that required keys exist and have the right shape. Runs on host
(no docker dependency) so failures surface before a 10-minute build burns.

Usage:
    python scripts/validate_env.py            # uses ./.env
    python scripts/validate_env.py path/to/.env

Exit codes:
    0 — all checks pass
    1 — one or more validations failed
    2 — .env file missing
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def _parse_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip("'\"")
    return out


REQUIRED = (
    "NEXT_PUBLIC_KAKAO_MAP_KEY",
    "NEXT_PUBLIC_API_URL",
)

# LLM 공급자에 따라 둘 중 하나만 있으면 됨.
LLM_ALTERNATIVES = ("GOOGLE_API_KEY", "ANTHROPIC_API_KEY")

PLACEHOLDER_PATTERN = re.compile(r"your_.*_(key|here)", re.IGNORECASE)


def main(argv: list[str]) -> int:
    env_path = Path(argv[1]) if len(argv) > 1 else Path(".env")
    if not env_path.exists():
        print(f"[validate_env] ❌ .env not found: {env_path.resolve()}", file=sys.stderr)
        return 2

    env = _parse_env(env_path)
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED:
        val = env.get(key, "")
        if not val:
            errors.append(f"{key} is missing or empty")
        elif PLACEHOLDER_PATTERN.search(val):
            errors.append(f"{key} still holds placeholder value: {val!r}")

    # NEXT_PUBLIC_API_URL must not end with /api
    api_url = env.get("NEXT_PUBLIC_API_URL", "")
    if api_url.rstrip("/").endswith("/api"):
        errors.append(
            f"NEXT_PUBLIC_API_URL must NOT end with /api (got {api_url!r}). "
            "Frontend auto-appends /api — keep the root domain only."
        )

    # LLM key: at least one alternative must be set
    if not any(env.get(k) and not PLACEHOLDER_PATTERN.search(env[k]) for k in LLM_ALTERNATIVES):
        errors.append(
            f"At least one of {', '.join(LLM_ALTERNATIVES)} must be set."
        )

    # USE_MOCK=false 이면 Seoul Opendata key 있어야 ETL 가능
    if env.get("USE_MOCK", "true").lower() == "false":
        key = env.get("SEOUL_OPENDATA_API_KEY", "")
        if not key or PLACEHOLDER_PATTERN.search(key):
            warnings.append(
                "USE_MOCK=false but SEOUL_OPENDATA_API_KEY is unset — "
                "pg_restore seed works, but Full ETL will fail."
            )

    for w in warnings:
        print(f"[validate_env] ⚠ {w}")
    if errors:
        for e in errors:
            print(f"[validate_env] ❌ {e}", file=sys.stderr)
        return 1
    print(f"[validate_env] ✅ {env_path} passes all checks")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
