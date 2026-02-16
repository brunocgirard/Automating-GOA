"""Lightweight retrieval helpers for long PDF text prompts."""

from __future__ import annotations

import re
from typing import Iterable, Sequence

CHUNK_SEPARATOR = "\n\n==== CHUNK BREAK ====\n\n"

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def chunk_text(
    text: str,
    *,
    chunk_size: int = 1600,
    overlap: int = 220,
    max_chunks: int = 400,
) -> list[str]:
    """Split text into overlapping chunks with sentence/newline-aware boundaries."""
    if not text:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap cannot be negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len and len(chunks) < max_chunks:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            search_start = start + chunk_size // 2
            newline_pos = text.rfind("\n", search_start, end)
            period_pos = text.rfind(". ", search_start, end)
            if newline_pos != -1:
                end = newline_pos + 1
            elif period_pos != -1:
                end = period_pos + 2

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        # Always advance by at least one character to avoid loops.
        start = max(end - overlap, start + 1)

    return chunks if chunks else [text[:chunk_size]]


def build_retrieved_pdf_context(
    full_pdf_text: str,
    query_hints: Sequence[str] | None = None,
    *,
    max_context_chars: int = 50000,
    chunk_size: int = 1600,
    chunk_overlap: int = 220,
    max_chunks: int = 400,
    max_selected_chunks: int = 40,
    include_first_chunk: bool = True,
    include_last_chunk: bool = True,
    chunk_separator: str = CHUNK_SEPARATOR,
) -> tuple[str, str]:
    """
    Retrieve relevant PDF text chunks within a fixed character budget.

    Returns:
        tuple[str, str]:
            - Retrieved context text
            - Short metadata note describing retrieval behavior
    """
    if not full_pdf_text:
        return "", "[No PDF text provided.]"

    if max_context_chars <= 0:
        return "", "[PDF retrieval disabled because max_context_chars <= 0.]"

    if len(full_pdf_text) <= max_context_chars:
        return (
            full_pdf_text,
            f"[Full PDF text included ({len(full_pdf_text)} chars).]",
        )

    chunks = chunk_text(
        full_pdf_text,
        chunk_size=chunk_size,
        overlap=chunk_overlap,
        max_chunks=max_chunks,
    )
    if not chunks:
        fallback = full_pdf_text[:max_context_chars]
        return fallback, f"[Fallback context used ({len(fallback)} chars).]"

    normalized_hints = _normalize_hints(query_hints or [])
    terms = _extract_terms(normalized_hints)
    phrases = _extract_phrases(normalized_hints)

    scored_chunks = [
        (index, _score_chunk(chunk, terms, phrases, normalized_hints))
        for index, chunk in enumerate(chunks)
    ]
    scored_chunks.sort(key=lambda item: item[1], reverse=True)

    selected_indexes: list[int] = []
    selected_set: set[int] = set()
    total_chars = 0

    def add_chunk(index: int) -> bool:
        nonlocal total_chars
        if index in selected_set or index < 0 or index >= len(chunks):
            return False

        candidate = chunks[index]
        extra = len(candidate)
        if selected_indexes:
            extra += len(chunk_separator)
        if total_chars + extra > max_context_chars:
            return False

        selected_indexes.append(index)
        selected_set.add(index)
        total_chars += extra
        return True

    if include_first_chunk:
        add_chunk(0)
    if include_last_chunk and len(chunks) > 1:
        add_chunk(len(chunks) - 1)

    for index, score in scored_chunks:
        if len(selected_indexes) >= max_selected_chunks:
            break
        if score <= 0 and selected_indexes:
            continue
        add_chunk(index)

    # If scoring didn't pick useful chunks, fill from the start.
    if not selected_indexes:
        for index in range(len(chunks)):
            if not add_chunk(index):
                break

    selected_indexes.sort()
    context = chunk_separator.join(chunks[index] for index in selected_indexes)

    if not context:
        fallback = full_pdf_text[:max_context_chars]
        return fallback, f"[Fallback context used ({len(fallback)} chars).]"

    note = (
        f"[RAG context: selected {len(selected_indexes)}/{len(chunks)} chunks, "
        f"{len(context)} chars from {len(full_pdf_text)} total.]"
    )
    return context, note


def _normalize_hints(query_hints: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for hint in query_hints:
        if not hint:
            continue
        compact = re.sub(r"\s+", " ", hint).strip().lower()
        if compact:
            normalized.append(compact)
    return normalized


def _extract_terms(hints: Sequence[str]) -> list[str]:
    counts: dict[str, int] = {}
    for hint in hints:
        for term in re.findall(r"[a-z0-9][a-z0-9_\-/]{2,}", hint):
            if term in _STOPWORDS:
                continue
            counts[term] = counts.get(term, 0) + 1

    # Keep high-signal terms and cap total for speed.
    sorted_terms = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [term for term, _ in sorted_terms[:80]]


def _extract_phrases(hints: Sequence[str]) -> list[str]:
    phrases: list[str] = []
    for hint in hints:
        if len(hint) < 8:
            continue
        words = hint.split()
        if len(words) >= 2:
            phrases.append(" ".join(words[: min(6, len(words))]))
    return phrases[:30]


def _score_chunk(chunk: str, terms: Sequence[str], phrases: Sequence[str], hints: Sequence[str]) -> float:
    if not chunk:
        return 0.0

    chunk_lower = chunk.lower()
    score = 0.0

    for term in terms:
        term_count = chunk_lower.count(term)
        if term_count:
            score += min(term_count, 4) * 2.0

    for phrase in phrases:
        phrase_count = chunk_lower.count(phrase)
        if phrase_count:
            score += min(phrase_count, 3) * 4.0

    for hint in hints:
        if len(hint) >= 12 and hint in chunk_lower:
            score += 8.0

    # Slight preference for denser chunks.
    return score / (1.0 + (len(chunk) / 1000.0))
