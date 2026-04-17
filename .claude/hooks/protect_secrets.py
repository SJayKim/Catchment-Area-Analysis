#!/usr/bin/env python
"""PreToolUse: Block edits to secret/protected files.

Reads stdin JSON ({tool_input: {file_path: ...}}). If file_path matches
a protected pattern, exits 2 with blocking reason on stderr.
.env.example and .env.template are explicitly allowed.
"""
import json
import re
import sys

PATTERNS = [
    r"(^|/)\.env(\.|$)",
    r"\.env\.local$",
    r"\.env\.production$",
    r"\.key$",
    r"\.pem$",
    r"credentials",
    r"secrets?\.",
]
ALLOWLIST_SUFFIXES = (".env.example", ".env.template")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = (data.get("tool_input") or {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    norm = file_path.replace("\\", "/").lower()
    if norm.endswith(ALLOWLIST_SUFFIXES):
        sys.exit(0)

    for pat in PATTERNS:
        if re.search(pat, norm):
            print(
                f"BLOCKED: {file_path} matches protected pattern ({pat}). "
                f"If intentional, adjust .claude/hooks/protect_secrets.py.",
                file=sys.stderr,
            )
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
