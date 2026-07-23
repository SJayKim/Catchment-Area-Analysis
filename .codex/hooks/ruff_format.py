#!/usr/bin/env python
"""PostToolUse: Run ruff format + check --fix on edited server/*.py files.

Triggered after Edit|Write|MultiEdit. Silently no-ops if file is not a
Python file under server/. Never blocks the edit (exit 0 regardless of
ruff outcome); warnings go to stderr for visibility.
"""
import json
import os
import subprocess
import sys


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = (data.get("tool_input") or {}).get("file_path", "")
    if not file_path or not file_path.endswith(".py"):
        sys.exit(0)

    norm = file_path.replace("\\", "/")
    if "/server/" not in norm and not norm.startswith("server/"):
        sys.exit(0)

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    server_dir = os.path.join(project_dir, "server")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    for args in (["ruff", "format", file_path], ["ruff", "check", "--fix", file_path]):
        try:
            result = subprocess.run(
                args,
                cwd=server_dir,
                env=env,
                timeout=30,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode != 0 and result.stderr:
                print(f"ruff {args[1]}: {result.stderr.strip()[:300]}", file=sys.stderr)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            print(f"ruff skipped ({args[1]}): {exc}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
