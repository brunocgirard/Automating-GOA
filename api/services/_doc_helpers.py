"""Shared document helper utilities for service-layer workflows."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Callable
from datetime import datetime
from typing import Any


TOKEN_PATTERN = re.compile(r"\u00ab[^\u00bb]+\u00bb")
DOUBLE_BRACE_TOKEN_PATTERN = re.compile(r"\{\{\s*[^{}]+\s*\}\}")


def to_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if not cleaned:
        return default
    try:
        return float(cleaned)
    except ValueError:
        return default


def current_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-")
    return normalized.lower()


def replace_tokens_in_container(
    container: Any,
    token_replacements: dict[str, str],
    literal_replacements: dict[str, str] | None = None,
    *,
    preprocess_text: Callable[[str], str] | None = None,
    postprocess_text: Callable[[str], str] | None = None,
    recurse_nested_tables: bool = True,
) -> None:
    for paragraph in container.paragraphs:
        replace_tokens_in_paragraph(
            paragraph,
            token_replacements,
            literal_replacements,
            preprocess_text=preprocess_text,
            postprocess_text=postprocess_text,
        )

    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                replace_tokens_in_cell(
                    cell,
                    token_replacements,
                    literal_replacements,
                    preprocess_text=preprocess_text,
                    postprocess_text=postprocess_text,
                    recurse_nested_tables=recurse_nested_tables,
                )


def replace_tokens_in_cell(
    cell: Any,
    token_replacements: dict[str, str],
    literal_replacements: dict[str, str] | None = None,
    *,
    preprocess_text: Callable[[str], str] | None = None,
    postprocess_text: Callable[[str], str] | None = None,
    recurse_nested_tables: bool = True,
) -> None:
    for paragraph in cell.paragraphs:
        replace_tokens_in_paragraph(
            paragraph,
            token_replacements,
            literal_replacements,
            preprocess_text=preprocess_text,
            postprocess_text=postprocess_text,
        )

    if not recurse_nested_tables:
        return

    for nested_table in cell.tables:
        for row in nested_table.rows:
            for nested_cell in row.cells:
                replace_tokens_in_cell(
                    nested_cell,
                    token_replacements,
                    literal_replacements,
                    preprocess_text=preprocess_text,
                    postprocess_text=postprocess_text,
                    recurse_nested_tables=True,
                )


def replace_tokens_in_paragraph(
    paragraph: Any,
    token_replacements: dict[str, str],
    literal_replacements: dict[str, str] | None = None,
    *,
    preprocess_text: Callable[[str], str] | None = None,
    postprocess_text: Callable[[str], str] | None = None,
) -> None:
    raw_text = "".join(run.text for run in paragraph.runs)
    if not raw_text:
        raw_text = paragraph.text or ""
    if not raw_text:
        return

    updated_text = preprocess_text(raw_text) if preprocess_text else raw_text

    for token, value in token_replacements.items():
        updated_text = updated_text.replace(f"\u00ab{token}\u00bb", value)
        updated_text = re.sub(r"\{\{\s*" + re.escape(token) + r"\s*\}\}", value, updated_text)

    for source, target in (literal_replacements or {}).items():
        if source:
            updated_text = updated_text.replace(source, target)

    updated_text = TOKEN_PATTERN.sub("", updated_text)
    updated_text = DOUBLE_BRACE_TOKEN_PATTERN.sub("", updated_text)

    if postprocess_text:
        updated_text = postprocess_text(updated_text)

    if updated_text == raw_text:
        return

    if paragraph.runs:
        paragraph.runs[0].text = updated_text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.text = updated_text


def write_temp_file(suffix: str, data: bytes) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as temp_file:
            temp_file.write(data)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    return path
