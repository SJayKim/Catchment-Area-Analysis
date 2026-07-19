"""Validate the project .env file before docker compose up / build.

Checks that required keys exist and have the right shape. Runs on host
(no docker dependency) so failures surface before a 10-minute build burns.

Usage:
    python scripts/validate_env.py            # .env.dev 우선, 없으면 .env
    python scripts/validate_env.py path/to/.env

Exit codes:
    0 — all checks pass
    1 — one or more validations failed
    2 — env file missing
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
LLM_ALTERNATIVES = ("GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")

PLACEHOLDER_PATTERN = re.compile(r"your_.*_(key|here)", re.IGNORECASE)


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        env_path = Path(argv[1])
    else:
        # .env.dev 가 있으면 우선 (로컬 개발용), 없으면 .env (prod 배포용)
        dev = Path(".env.dev")
        env_path = dev if dev.exists() else Path(".env")
    if not env_path.exists():
        print(f"[validate_env] ❌ env file not found: {env_path.resolve()}", file=sys.stderr)
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

    # NEXT_PUBLIC_API_URL must not point at the frontend's own port.
    # chat SSE 는 Next.js rewrite 프록시를 통하면 버퍼링되므로 backend 로 direct 호출해야 함.
    # 이 값이 localhost:3000 / :3001 처럼 frontend 포트로 잘못 설정되면 SSE 가 무응답처럼 보임.
    # (2026-04-22 재발 이력 — feedback_next_public_api_url_frontend_port.md)
    FRONTEND_PORTS = ("3000", "3001")
    for port in FRONTEND_PORTS:
        if f"localhost:{port}" in api_url or f"127.0.0.1:{port}" in api_url:
            errors.append(
                f"NEXT_PUBLIC_API_URL points at frontend port :{port} (got {api_url!r}). "
                "This routes chat SSE through Next.js rewrite and buffers the stream. "
                "Use the backend URL (e.g. http://localhost:8000) or production API origin."
            )
            break

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

    # Langfuse SDK drift guard — code paths import `langfuse.langchain.CallbackHandler`
    # (v3). If a stale v2 (2.x) is installed in the runtime env, the import silently
    # fails, `_tracer_valid=False`, and every LLM call burns cost without a trace.
    # See docs/plan/infra/langfuse-cost-coverage-fix-2026-04-24.md.
    if env.get("LANGFUSE_PUBLIC_KEY") and env.get("LANGFUSE_SECRET_KEY"):
        try:
            import importlib.util

            if importlib.util.find_spec("langfuse.langchain") is None:
                warnings.append(
                    "Langfuse keys are set but `langfuse.langchain` module is missing. "
                    "Likely stale v2 SDK — run `pip install --upgrade 'langfuse>=3,<4'` "
                    "or rebuild the backend image. Otherwise every LLM call is billed by "
                    "Anthropic/Google but invisible in Langfuse."
                )
        except Exception:
            # Import failure here is non-fatal; worst case we fall through with no
            # extra warning. The runtime tracer module has its own guards.
            pass

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
