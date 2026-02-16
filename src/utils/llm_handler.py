"""
Compatibility shim for legacy ``src.utils.llm_handler`` imports.

Canonical LLM pipeline code now lives under ``src.llm``.
This module forwards attribute access so older imports continue working.
"""

from __future__ import annotations

import src.llm as _llm
from src.llm import __all__ as _llm_public
from src.llm import client as _client

__all__ = list(_llm_public)


def __getattr__(name: str):
    # Keep model/global lookups bound to live client state.
    if name == "GENERATIVE_MODEL":
        return _client.GENERATIVE_MODEL
    if name == "genai":
        return _client.genai

    if name in _llm_public:
        return getattr(_llm, name)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
