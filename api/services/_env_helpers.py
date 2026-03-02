"""Shared environment configuration helpers for service-layer workflows."""

from __future__ import annotations

import os


def env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def env_positive_int(name: str, default: int, *, min_value: int = 1) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return max(min_value, parsed)


def env_csv(name: str, default: list[str] | None = None) -> list[str]:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return list(default or [])
    values = [value.strip() for value in raw.split(",")]
    cleaned = [value for value in values if value]
    return cleaned or list(default or [])
