"""
Machine family detection helpers.

Centralizes machine type classification logic so template routing and few-shot
selection use the same hardened rules.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Machine family lookup table
# Each entry maps a family name to a tuple of compiled regex patterns.
# All patterns use re.IGNORECASE so detection is case-insensitive.
# ---------------------------------------------------------------------------
_MACHINE_FAMILIES: dict[str, tuple[re.Pattern[str], ...]] = {
    "sortstar": (
        re.compile(r"\bsort[\s_-]*star\b", re.IGNORECASE),
        re.compile(r"\brobo[\s_-]*sort\b", re.IGNORECASE),
        re.compile(r"\bthunder[\s_-]*star\b", re.IGNORECASE),
        re.compile(r"\bbottle[\s_-]*unscrambler\b", re.IGNORECASE),
        re.compile(r"\bunscrambler\b", re.IGNORECASE),
    ),
    "labeling": (
        re.compile(r"\blabel[\s_-]*star\b", re.IGNORECASE),
        re.compile(r"\blabel(er|ing)?\b", re.IGNORECASE),
        re.compile(r"\blabel\s+applicator\b", re.IGNORECASE),
    ),
    "filling": (
        re.compile(r"\bfiller\b", re.IGNORECASE),
        re.compile(r"\bfilling\b", re.IGNORECASE),
        re.compile(r"\bliquid\s+fill(ing)?\b", re.IGNORECASE),
        re.compile(r"\bmonoblock\b", re.IGNORECASE),
        re.compile(r"\bbottling\b", re.IGNORECASE),
    ),
    "capping": (
        re.compile(r"\bcapper\b", re.IGNORECASE),
        re.compile(r"\bcapping\b", re.IGNORECASE),
        re.compile(r"\bcap\s+tighten(er|ing)?\b", re.IGNORECASE),
    ),
}

# Convenience aliases kept for internal helpers that still reference them.
_SORTSTAR_PATTERN = _MACHINE_FAMILIES["sortstar"][0]
_BOTTLE_UNSCRAMBLER_PATTERN = _MACHINE_FAMILIES["sortstar"][3]
_UNSCRAMBLER_PATTERN = _MACHINE_FAMILIES["sortstar"][4]

_LABELING_PATTERNS = _MACHINE_FAMILIES["labeling"]
_FILLING_PATTERNS = _MACHINE_FAMILIES["filling"]
_CAPPING_PATTERNS = _MACHINE_FAMILIES["capping"]


def _normalize_machine_name(machine_name: str) -> str:
    normalized = str(machine_name or "").strip().lower()
    normalized = re.sub(r"[_/]+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9\s-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _count_hits(text: str, patterns: tuple[re.Pattern[str], ...]) -> int:
    return sum(1 for pattern in patterns if pattern.search(text))


def determine_machine_type(machine_name: str) -> str:
    """
    Determine the machine family for routing and few-shot selection.

    Categories:
    - sortstar
    - labeling
    - filling
    - capping
    - general
    """
    normalized_name = _normalize_machine_name(machine_name)
    if not normalized_name:
        return "general"

    # Check all sortstar-family patterns (SortStar, RoboSort, ThunderStar).
    _sortstar_hard = _MACHINE_FAMILIES["sortstar"][:3]  # sort-star, robo-sort, thunder-star
    has_sortstar = any(p.search(normalized_name) for p in _sortstar_hard)
    has_bottle_unscrambler = bool(_BOTTLE_UNSCRAMBLER_PATTERN.search(normalized_name))
    has_unscrambler = bool(_UNSCRAMBLER_PATTERN.search(normalized_name))

    labeling_score = _count_hits(normalized_name, _LABELING_PATTERNS)
    filling_score = _count_hits(normalized_name, _FILLING_PATTERNS)
    capping_score = _count_hits(normalized_name, _CAPPING_PATTERNS)

    # Hard signal for SortStar family.
    if has_sortstar:
        return "sortstar"

    # Hardened unscrambler handling:
    # do not route to SortStar when machine name strongly signals another family.
    strongest_non_sortstar = max(labeling_score, filling_score, capping_score)
    if has_bottle_unscrambler and strongest_non_sortstar <= 1:
        return "sortstar"
    if has_unscrambler and strongest_non_sortstar == 0:
        return "sortstar"

    if labeling_score >= filling_score and labeling_score >= capping_score and labeling_score > 0:
        return "labeling"
    if filling_score >= capping_score and filling_score > 0:
        return "filling"
    if capping_score > 0:
        return "capping"

    # Fall back to SortStar only if no clear competing family was detected.
    if has_bottle_unscrambler or has_unscrambler:
        return "sortstar"

    return "general"


def is_sortstar_machine(machine_name: str) -> bool:
    """Return True when the machine should use SortStar routing/templates."""
    return determine_machine_type(machine_name) == "sortstar"

