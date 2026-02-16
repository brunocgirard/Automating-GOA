#!/usr/bin/env python3
"""Block accidental credential commits in staged files."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from typing import Iterable

DISALLOWED_ENV_FILE_RE = re.compile(r"(^|/)\.env(\..+)?$", re.IGNORECASE)

TOKEN_PATTERNS: dict[str, re.Pattern[str]] = {
    "Google API key token": re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    "OpenAI API key token": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "Anthropic API key token": re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),
    "AWS Access Key ID": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub PAT": re.compile(r"(ghp|github_pat)_[A-Za-z0-9_]{20,}"),
}

SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"^\s*(GEMINI_API_KEY|GOOGLE_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|AWS_SECRET_ACCESS_KEY|SECRET_KEY|JWT_SECRET)\s*=\s*(.+?)\s*$",
    re.IGNORECASE,
)

SAFE_PLACEHOLDERS = {
    "",
    "changeme",
    "example",
    "none",
    "null",
    "replace_me",
    "replace-with-your-key",
    "test",
    "your_api_key_here",
    "your_key_here",
}


def _run_git(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *cmd], capture_output=True, text=True, check=False)


def _staged_files() -> list[str]:
    result = _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _load_staged_text(path: str) -> str:
    result = _run_git(["show", f":{path}"])
    if result.returncode != 0:
        return ""
    return result.stdout


def _normalize_value(raw: str) -> str:
    value = raw.split("#", 1)[0].strip().strip('"').strip("'").strip()
    return value


def _is_safe_placeholder(value: str) -> bool:
    lowered = value.lower()
    if lowered in SAFE_PLACEHOLDERS:
        return True
    if lowered.startswith("<") and lowered.endswith(">"):
        return True
    if lowered.startswith("${") and lowered.endswith("}"):
        return True
    if lowered.startswith("$") and len(lowered) > 1:
        return True
    return False


def scan_files(paths: Iterable[str]) -> list[str]:
    violations: list[str] = []
    for path in paths:
        normalized_path = path.replace("\\", "/")

        if DISALLOWED_ENV_FILE_RE.search(normalized_path) and not normalized_path.endswith(".example"):
            violations.append(
                f"{normalized_path}: environment file is blocked from commits (keep only *.example tracked)."
            )

        text = _load_staged_text(path)
        if not text:
            continue

        for label, pattern in TOKEN_PATTERNS.items():
            if pattern.search(text):
                violations.append(f"{normalized_path}: detected {label}.")

        for line_number, line in enumerate(text.splitlines(), start=1):
            match = SENSITIVE_ASSIGNMENT_RE.match(line)
            if not match:
                continue
            key_name = match.group(1).upper()
            value = _normalize_value(match.group(2))
            if value and not _is_safe_placeholder(value):
                violations.append(
                    f"{normalized_path}:{line_number}: {key_name} appears to contain a real secret value."
                )

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan staged files for likely secrets.")
    parser.add_argument("--staged", action="store_true", help="scan staged files (default behavior)")
    parser.add_argument("paths", nargs="*", help="optional explicit file paths to scan")
    args = parser.parse_args()

    paths = list(args.paths) if args.paths else _staged_files()
    if not paths:
        return 0

    violations = scan_files(paths)
    if not violations:
        return 0

    print("Credential safety check failed:")
    for issue in violations:
        print(f"  - {issue}")
    print("Remove secrets, rotate exposed keys, and recommit.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

