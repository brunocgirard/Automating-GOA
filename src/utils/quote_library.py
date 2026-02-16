"""Utilities for parsing and matching machine specs from QUOTE_LIBRARY.txt."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

DEFAULT_LIBRARY_FILENAME = "QUOTE_LIBRARY.txt"
DEFAULT_MAX_SECTIONS = 2
DEFAULT_MAX_CONTEXT_CHARS = 14000

_MODEL_HEADER_RE = re.compile(r"\bmodel\b", re.IGNORECASE)
_TABLE_OF_CONTENTS_RE = re.compile(r"\t+\d+\s*$")
_EXPLICIT_MACHINE_HEADER_RE = re.compile(r"^\s*(?:machine|model)\s*:\s*(.+)$", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_SPACES_RE = re.compile(r"\s+")

_MATCH_STOPWORDS = {
    "and",
    "at",
    "automatic",
    "base",
    "bottle",
    "by",
    "for",
    "from",
    "handling",
    "in",
    "label",
    "labeling",
    "line",
    "machine",
    "model",
    "of",
    "on",
    "system",
    "the",
    "to",
    "unit",
    "with",
}


@dataclass(frozen=True)
class QuoteLibrarySection:
    """Represents one machine-specific section from QUOTE_LIBRARY."""

    title: str
    content: str


def _safe_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _normalize_line(value: str) -> str:
    return _SPACES_RE.sub(" ", value).strip()


def _normalize_for_match(value: str) -> str:
    return " ".join(_NON_ALNUM_RE.sub(" ", value.lower()).split())


def _tokenize(value: str) -> set[str]:
    return {
        token
        for token in _normalize_for_match(value).split()
        if len(token) > 2 and token not in _MATCH_STOPWORDS
    }


def _resolve_quote_library_path(quote_library_path: str | None = None) -> Path | None:
    candidates: list[Path] = []

    if quote_library_path:
        candidates.append(Path(quote_library_path))

    env_path = os.getenv("QUOTE_LIBRARY_PATH")
    if env_path:
        candidates.append(Path(env_path))

    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / DEFAULT_LIBRARY_FILENAME)
    candidates.append(Path.cwd() / DEFAULT_LIBRARY_FILENAME)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    return None


def _is_machine_header(line: str) -> bool:
    cleaned = _normalize_line(line)
    if not cleaned or len(cleaned) < 10 or len(cleaned) > 140:
        return False

    if _TABLE_OF_CONTENTS_RE.search(line):
        return False

    lowered = cleaned.lower()
    if lowered.startswith(("quote library", "date:", "table of contents", "heading ")):
        return False
    if lowered.startswith(("*", "-", "?", "?:", "/")):
        return False
    if lowered.startswith("(") and lowered.endswith(")"):
        return False
    if lowered.startswith("change part"):
        return False

    if _EXPLICIT_MACHINE_HEADER_RE.match(cleaned):
        return True

    return bool(_MODEL_HEADER_RE.search(cleaned))


def _extract_machine_title(header_line: str) -> str:
    cleaned = _normalize_line(header_line)
    explicit_match = _EXPLICIT_MACHINE_HEADER_RE.match(cleaned)
    if explicit_match:
        return _normalize_line(explicit_match.group(1))
    return cleaned


def _extract_sections(text: str) -> list[QuoteLibrarySection]:
    lines = text.splitlines()
    header_indexes = [index for index, line in enumerate(lines) if _is_machine_header(line)]
    if not header_indexes:
        return []

    sections: dict[str, QuoteLibrarySection] = {}
    for idx, start in enumerate(header_indexes):
        end = header_indexes[idx + 1] if idx + 1 < len(header_indexes) else len(lines)
        title = _extract_machine_title(lines[start])
        content = "\n".join(line.rstrip() for line in lines[start:end]).strip()
        if len(content) < 120:
            continue

        dedupe_key = _normalize_for_match(title)
        existing = sections.get(dedupe_key)
        if existing is None or len(content) > len(existing.content):
            sections[dedupe_key] = QuoteLibrarySection(title=title, content=content)

    return list(sections.values())


@lru_cache(maxsize=8)
def _load_sections_cached(path_str: str, mtime_ns: int) -> tuple[QuoteLibrarySection, ...]:
    del mtime_ns  # Part of cache key so updates to the file invalidate cached parsing.
    text = Path(path_str).read_text(encoding="utf-8", errors="ignore")
    return tuple(_extract_sections(text))


def load_quote_library_sections(quote_library_path: str | None = None) -> list[QuoteLibrarySection]:
    """
    Parse machine sections from QUOTE_LIBRARY.

    Parsing is cached and auto-invalidated when file mtime changes so newly
    appended machine specs are picked up without code changes.
    """
    resolved_path = _resolve_quote_library_path(quote_library_path)
    if resolved_path is None:
        return []

    try:
        stat = resolved_path.stat()
    except OSError:
        return []

    return list(_load_sections_cached(str(resolved_path), stat.st_mtime_ns))


def _score_section(query: str, query_tokens: set[str], section: QuoteLibrarySection) -> float:
    title_norm = _normalize_for_match(section.title)
    title_tokens = _tokenize(section.title)

    snippet = section.content[:1600]
    snippet_tokens = _tokenize(snippet)

    overlap_title = len(query_tokens & title_tokens)
    overlap_snippet = len(query_tokens & snippet_tokens)

    containment = 0.0
    if query and title_norm:
        if query in title_norm or title_norm in query:
            containment = 1.0

    seq_ratio = SequenceMatcher(None, query, title_norm).ratio() if query and title_norm else 0.0

    score = 0.0
    score += containment * 0.55
    score += (overlap_title / max(1, len(query_tokens))) * 0.25
    score += (overlap_snippet / max(1, len(query_tokens))) * 0.15
    score += seq_ratio * 0.15

    return score


def _build_query(machine_name: str, main_item_desc: str, add_on_descs: str) -> str:
    parts: list[str] = []
    if machine_name:
        parts.append(machine_name)

    if main_item_desc:
        first_line = main_item_desc.splitlines()[0].strip()
        if first_line:
            parts.append(first_line)

    if add_on_descs:
        parts.append(add_on_descs[:500])

    return " ".join(parts).strip()


def get_quote_library_context(
    machine_name: str,
    main_item_desc: str = "",
    add_on_descs: str = "",
    *,
    quote_library_path: str | None = None,
    max_sections: int | None = None,
    max_chars: int | None = None,
) -> tuple[str, list[str]]:
    """
    Return matched QUOTE_LIBRARY context for the current machine extraction.

    Returns:
        tuple:
          - Context string with one or more matched machine sections.
          - List of matched section titles (in the same order as context).
    """
    sections = load_quote_library_sections(quote_library_path=quote_library_path)
    if not sections:
        return "", []

    query_text = _build_query(machine_name, main_item_desc, add_on_descs)
    if not query_text:
        return "", []

    query_norm = _normalize_for_match(query_text)
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return "", []

    candidate_scores = [
        (section, _score_section(query_norm, query_tokens, section))
        for section in sections
    ]
    candidate_scores.sort(key=lambda item: item[1], reverse=True)

    effective_max_sections = max_sections or _safe_int_env("QUOTE_LIBRARY_MAX_SECTIONS", DEFAULT_MAX_SECTIONS)
    effective_max_chars = max_chars or _safe_int_env("QUOTE_LIBRARY_MAX_CHARS", DEFAULT_MAX_CONTEXT_CHARS)

    selected: list[tuple[QuoteLibrarySection, float]] = []
    for section, score in candidate_scores:
        if len(selected) >= effective_max_sections:
            break
        if score < 0.32 and selected:
            break
        if score < 0.24 and not selected:
            continue
        selected.append((section, score))

    if not selected and candidate_scores and candidate_scores[0][1] >= 0.2:
        selected.append(candidate_scores[0])

    if not selected:
        return "", []

    context_parts: list[str] = []
    matched_titles: list[str] = []
    remaining_chars = effective_max_chars

    for section, _score in selected:
        heading = section.title
        section_lines = section.content.splitlines()
        if section_lines and _normalize_line(section_lines[0]) == _normalize_line(section.title):
            body = "\n".join(section_lines[1:]).strip()
        else:
            body = section.content.strip()

        if not body:
            continue

        block = f"[{heading}]\n{body}".strip()
        if len(block) > remaining_chars:
            truncated = block[:remaining_chars].strip()
            if not truncated:
                continue
            block = f"{truncated}\n... (truncated)".strip()

        context_parts.append(block)
        matched_titles.append(heading)
        remaining_chars -= len(block) + 6

        if remaining_chars <= 0:
            break

    return "\n\n---\n\n".join(context_parts), matched_titles
