"""
Deterministic resolver for constrained text fields.

This module post-processes high-impact text fields (Direction and Utility values)
using explicit quote evidence so semantically wrong-but-non-empty LLM outputs can
be corrected before final sanitization/validation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Sequence, Tuple


_DIRECTION_PATTERNS = (
    re.compile(r"\bfrom\s+left\s+to\s+right\b", re.IGNORECASE),
    re.compile(r"\bfrom\s+right\s+to\s+left\b", re.IGNORECASE),
    re.compile(r"\bleft\s+to\s+right\b", re.IGNORECASE),
    re.compile(r"\bright\s+to\s+left\b", re.IGNORECASE),
)

_UTILITY_PATTERNS = {
    "voltage": (
        re.compile(r"\b\d{2,4}(?:\s*/\s*\d{2,4})?\s*(?:vac|vdc|v|volt(?:s)?)\b", re.IGNORECASE),
    ),
    "hz": (
        re.compile(r"\b\d{2,3}(?:\s*/\s*\d{2,3})?\s*(?:hz|hertz)\b", re.IGNORECASE),
    ),
    "phases": (
        re.compile(r"\b[123]\s*(?:phase|phases)\b", re.IGNORECASE),
    ),
}

_UTILITY_SCOPE_ANCHORS = (
    re.compile(r"line\s+direction", re.IGNORECASE),
    re.compile(r"utility", re.IGNORECASE),
    re.compile(r"conveyor", re.IGNORECASE),
)


def _normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _values_equivalent(left: str, right: str) -> bool:
    return _normalize_ws(left).lower() == _normalize_ws(right).lower()


def _iter_scopes(text: str) -> list[tuple[int, int, str]]:
    scopes: list[tuple[int, int, str]] = []
    normalized = str(text or "")
    for anchor in _UTILITY_SCOPE_ANCHORS:
        for match in anchor.finditer(normalized):
            start = max(0, match.start() - 220)
            end = min(len(normalized), match.end() + 420)
            scopes.append((start, end, normalized[start:end]))
    scopes.sort(key=lambda item: (item[0], item[1]))
    if normalized:
        scopes.append((0, len(normalized), normalized))
    return scopes


def _extract_first_match(patterns: Sequence[re.Pattern[str]], text: str) -> tuple[str, bool]:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return _normalize_ws(match.group(0)), True
    return "", False


def _extract_direction_value(full_pdf_text: str) -> tuple[str, bool]:
    text = str(full_pdf_text or "")
    if not text:
        return "", False

    # Prefer direction mentions close to "line direction".
    for anchor_match in re.finditer(r"line\s+direction", text, flags=re.IGNORECASE):
        start = max(0, anchor_match.start() - 160)
        end = min(len(text), anchor_match.end() + 260)
        scope = text[start:end]
        value, found = _extract_first_match(_DIRECTION_PATTERNS, scope)
        if found:
            return value, True

    return _extract_first_match(_DIRECTION_PATTERNS, text)


def _extract_utility_value(tag: str, full_pdf_text: str) -> tuple[str, bool]:
    patterns = _UTILITY_PATTERNS.get(tag, ())
    if not patterns:
        return "", False

    for _, _, scope in _iter_scopes(full_pdf_text):
        value, found = _extract_first_match(patterns, scope)
        if found:
            return value, True
    return "", False


def _resolve_semantic_tag(field_key: str, field_context: Any) -> str:
    if isinstance(field_context, dict):
        explicit = str(field_context.get("semantic_tag", "")).strip().lower()
        if explicit:
            return explicit
        description = str(field_context.get("description", "")).strip().lower()
        section = str(field_context.get("section", "")).strip().lower()
        if "direction" in description and "basic information" in section:
            return "direction"
        if "utility specifications" in section:
            if "voltage" in description:
                return "voltage"
            if "hz" in description or "hertz" in description:
                return "hz"
            if "phase" in description:
                return "phases"
    return ""


def resolve_critical_text_fields(
    extracted_data: Dict[str, str],
    template_contexts: Dict[str, Any],
    full_pdf_text: str,
    *,
    target_tags: Sequence[str] | None = None,
    blank_direction_without_evidence: bool = True,
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    Override constrained text fields with explicit quote evidence when available.

    Returns:
        tuple[dict, dict]:
            - resolved field payload
            - resolver metrics
    """
    targets = {
        str(tag).strip().lower()
        for tag in (target_tags or ("direction", "voltage", "hz", "phases"))
        if str(tag).strip()
    }

    resolved = dict(extracted_data or {})
    overrides_applied = 0
    no_evidence_blanked = 0
    overridden_fields: list[str] = []

    for field_key, field_context in (template_contexts or {}).items():
        if not isinstance(field_context, dict):
            continue
        if str(field_context.get("type", "string")).lower() != "string":
            continue

        semantic_tag = _resolve_semantic_tag(field_key, field_context)
        if not semantic_tag or semantic_tag not in targets:
            continue

        current_value = str(resolved.get(field_key, "") or "")

        if semantic_tag == "direction":
            detected_value, found = _extract_direction_value(full_pdf_text)
            if found and not _values_equivalent(current_value, detected_value):
                resolved[field_key] = detected_value
                overrides_applied += 1
                overridden_fields.append(field_key)
            elif not found and blank_direction_without_evidence and current_value.strip():
                resolved[field_key] = ""
                no_evidence_blanked += 1
                overridden_fields.append(field_key)
            continue

        detected_value, found = _extract_utility_value(semantic_tag, full_pdf_text)
        if found and not _values_equivalent(current_value, detected_value):
            resolved[field_key] = detected_value
            overrides_applied += 1
            overridden_fields.append(field_key)

    metrics = {
        "critical_text_targets": sorted(targets),
        "critical_text_overrides_applied": overrides_applied,
        "critical_text_no_evidence_blanked": no_evidence_blanked,
        "critical_text_override_fields": overridden_fields,
    }
    return resolved, metrics
