"""Helpers for parsing PM Gantt PDFs into structured JSON."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pdfplumber

_PCT_RE = re.compile(r"(-?\d{1,3}(?:[.,]\d+)?)\s*%")
_NUMBER_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)")
_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,4}[/-]\d{1,2}[/-]\d{1,4})\b")
_TEXT_DATE_RE = re.compile(
    r"\b(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+)?\d{1,2}\s+[A-Za-z]{3,9}\s+'?\d{2,4}\b",
    flags=re.IGNORECASE,
)
_PROJECT_CODE_RE = re.compile(r"\b([A-Z]{1,5}-\d{2,5}[A-Z]?)\b")
_DIGITS_ONLY_RE = re.compile(r"^\d+$")
_PAGE_LABEL_RE = re.compile(r"^page\s+\d+$", flags=re.IGNORECASE)
_ROW_NAME_BLACKLIST = {"machine", "project", "projects", "description", "task", "task name", "id"}


def _today() -> date:
    return date.today()


def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\r", "\n").strip()


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _to_float(value: str) -> float | None:
    try:
        return float(value.replace(",", ".").strip())
    except (TypeError, ValueError, AttributeError):
        return None


def _extract_pct(text: str, *, allow_plain_number: bool = False) -> float | None:
    match = _PCT_RE.search(text)
    if match:
        value = _to_float(match.group(1))
        if value is not None:
            return max(0.0, min(100.0, value))

    if not allow_plain_number:
        return None

    number_match = _NUMBER_RE.search(text or "")
    if not number_match:
        return None

    value = _to_float(number_match.group(1))
    if value is None:
        return None
    raw_token = number_match.group(1)
    # In some exports `% Complete` is emitted as 0-1 decimals instead of 0-100.
    if 0.0 <= value <= 1.0 and ("." in raw_token or "," in raw_token):
        value *= 100.0
    if not 0.0 <= value <= 100.0:
        return None
    return round(value, 1)


def _extract_dates(text: str) -> list[str]:
    dates: list[str] = []
    for match in _NUMERIC_DATE_RE.finditer(text or ""):
        dates.append(_normalize_spaces(match.group(1)))
    for match in _TEXT_DATE_RE.finditer(text or ""):
        dates.append(_normalize_spaces(match.group(0)))
    return dates


def _parse_date(value: str) -> date | None:
    token = _normalize_spaces((value or "").replace("’", "'"))
    if not token:
        return None

    formats = (
        "%m/%d/%Y",
        "%m/%d/%y",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d",
        "%m-%d-%Y",
        "%m-%d-%y",
        "%d-%m-%Y",
        "%d-%m-%y",
        "%a %d %b '%y",
        "%a %d %b %Y",
        "%a %d %B '%y",
        "%a %d %B %Y",
        "%d %b '%y",
        "%d %b %Y",
        "%d %B '%y",
        "%d %B %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue

    # OCR/noisy rows often include extra text around the actual date token.
    numeric_match = _NUMERIC_DATE_RE.search(token)
    if numeric_match:
        numeric_parsed = _parse_date(numeric_match.group(1))
        if numeric_parsed:
            return numeric_parsed

    text_match = _TEXT_DATE_RE.search(token)
    if text_match:
        text_parsed = _parse_date(text_match.group(0))
        if text_parsed:
            return text_parsed

    return None


def _estimate_pct_from_schedule(start_date: date | None, end_date: date | None) -> float | None:
    if not start_date or not end_date:
        return None
    if end_date <= start_date:
        return 100.0 if _today() >= end_date else 0.0

    today = _today()
    if today <= start_date:
        return 0.0
    if today >= end_date:
        return 100.0

    elapsed_days = (today - start_date).days
    total_days = max((end_date - start_date).days, 1)
    return round((elapsed_days / total_days) * 100.0, 1)


def _header_tokens(cells: list[str]) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    for cell in cells:
        raw = _normalize_spaces(cell).lower()
        simplified = re.sub(r"[^a-z%]+", "", raw)
        tokens.append((raw, simplified))
    return tokens


def _looks_like_header_row(cells: list[str]) -> bool:
    tokens = _header_tokens(cells)
    simplified_values = [item[1] for item in tokens if item[1]]
    if not simplified_values:
        return False

    has_task = any(("task" in token) or ("name" in token) or token == "activity" for token in simplified_values)
    has_schedule = any(
        any(marker in token for marker in ("start", "finish", "duration", "complete", "progress", "end"))
        for token in simplified_values
    )
    return has_task and has_schedule


def _build_column_map(cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, (_raw, simplified) in enumerate(_header_tokens(cells)):
        if not simplified:
            continue

        if (
            "taskname" in simplified
            or ("task" in simplified and "name" in simplified)
            or simplified == "task"
            or (
                "name" in simplified
                and "customer" not in simplified
                and "machine" not in simplified
                and "project" not in simplified
            )
        ):
            mapping.setdefault("task_name", index)
            continue
        if "machine" in simplified:
            mapping.setdefault("machine", index)
            continue
        if "project" in simplified:
            mapping.setdefault("project", index)
            continue
        if "%complete" in simplified or "percentcomplete" in simplified or "progress" in simplified or simplified == "complete":
            mapping.setdefault("progress", index)
            continue
        if simplified.startswith("start"):
            mapping.setdefault("start", index)
            continue
        if simplified.startswith("finish") or simplified.startswith("end"):
            mapping.setdefault("finish", index)
            continue
        if "duration" in simplified:
            mapping.setdefault("duration", index)
            continue
        if simplified in {"id", "wbs", "uid"}:
            mapping.setdefault("id", index)
            continue
        if "department" in simplified or "phase" in simplified or simplified.endswith("mode"):
            mapping.setdefault("phase", index)
    return mapping


def _cell(cells: list[str], column_map: dict[str, int], key: str) -> str:
    index = column_map.get(key)
    if index is None or index >= len(cells):
        return ""
    return (cells[index] or "").strip()


def _row_display_name(cells: list[str], column_map: dict[str, int]) -> str:
    machine_name = _cell(cells, column_map, "machine")
    task_name = _cell(cells, column_map, "task_name")
    id_value = _cell(cells, column_map, "id") or (cells[0].strip() if cells else "")

    if machine_name and not _DIGITS_ONLY_RE.fullmatch(machine_name):
        return machine_name
    if task_name and not _DIGITS_ONLY_RE.fullmatch(task_name):
        return task_name

    fallback = machine_name or task_name or id_value
    if _DIGITS_ONLY_RE.fullmatch(fallback):
        return ""
    return fallback


def _parse_row_from_columns(cells: list[str], column_map: dict[str, int]) -> dict[str, Any] | None:
    row_text = " | ".join(cell for cell in cells if cell)
    if not row_text:
        return None

    non_empty_cells = [cell for cell in cells if cell]
    if len(non_empty_cells) <= 1 and _DIGITS_ONLY_RE.fullmatch(non_empty_cells[0]):
        return None

    display_name = _row_display_name(cells, column_map).strip()
    if not display_name:
        return None
    if display_name.lower() in _ROW_NAME_BLACKLIST:
        return None
    if _PAGE_LABEL_RE.fullmatch(display_name):
        return None

    task_name = _cell(cells, column_map, "task_name")
    phase_name = _cell(cells, column_map, "phase") or task_name
    project_cell = _cell(cells, column_map, "project")
    project_code_match = _PROJECT_CODE_RE.search(project_cell or row_text)

    start_cell = _cell(cells, column_map, "start")
    finish_cell = _cell(cells, column_map, "finish")
    parsed_dates_from_row = _extract_dates(row_text)
    if not start_cell and parsed_dates_from_row:
        start_cell = parsed_dates_from_row[0]
    if not finish_cell and len(parsed_dates_from_row) >= 2:
        finish_cell = parsed_dates_from_row[1]

    start_dt = _parse_date(start_cell)
    finish_dt = _parse_date(finish_cell)

    progress_cell = _cell(cells, column_map, "progress")
    progress_pct = _extract_pct(progress_cell, allow_plain_number=True) if progress_cell else None
    if progress_pct is None:
        progress_pct = _extract_pct(row_text)
    if progress_pct is None:
        progress_pct = _estimate_pct_from_schedule(start_dt, finish_dt)

    return {
        "name": display_name[:200],
        "task_name": task_name[:200] if task_name else display_name[:200],
        "phase_name": phase_name[:120] if phase_name else "",
        "project_code": project_code_match.group(1) if project_code_match else None,
        "progress_pct": progress_pct,
        "start_date": start_cell or None,
        "end_date": finish_cell or None,
        "start_dt": start_dt,
        "end_dt": finish_dt,
        "raw": row_text[:2000],
    }


def _parse_structured_table(table: list[list[Any]]) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    column_map: dict[str, int] | None = None

    for raw_row in table or []:
        cells = [_clean_cell(cell) for cell in raw_row]
        if not any(cells):
            continue

        if column_map is None:
            if _looks_like_header_row(cells):
                column_map = _build_column_map(cells)
                continue
            continue

        parsed = _parse_row_from_columns(cells, column_map)
        if parsed:
            rows.append(parsed)

    return rows, column_map is not None


def _aggregate_structured_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get("name") or "").strip().lower()
        if not key:
            continue
        grouped.setdefault(key, []).append(row)

    machines: list[dict[str, Any]] = []
    for machine_rows in grouped.values():
        base = machine_rows[0]
        progress_values = [
            float(row["progress_pct"])
            for row in machine_rows
            if isinstance(row.get("progress_pct"), (int, float))
        ]
        overall_pct = round(sum(progress_values) / len(progress_values), 1) if progress_values else 0.0

        project_code = next((row.get("project_code") for row in machine_rows if row.get("project_code")), None)
        start_date = next((row.get("start_date") for row in machine_rows if row.get("start_date")), None)
        end_date = next((row.get("end_date") for row in machine_rows if row.get("end_date")), None)

        start_candidates = [row.get("start_dt") for row in machine_rows if isinstance(row.get("start_dt"), date)]
        end_candidates = [row.get("end_dt") for row in machine_rows if isinstance(row.get("end_dt"), date)]
        if start_candidates:
            start_date = min(start_candidates).isoformat()
        if end_candidates:
            end_date = max(end_candidates).isoformat()

        phases: list[dict[str, Any]] = []
        seen_phase_names: set[str] = set()
        for row in machine_rows:
            phase_name = str(row.get("task_name") or row.get("phase_name") or "").strip()
            if not phase_name:
                continue
            phase_key = phase_name.lower()
            if phase_key in seen_phase_names:
                continue
            seen_phase_names.add(phase_key)

            phase_dates: list[str] = []
            if row.get("start_date"):
                phase_dates.append(str(row["start_date"]))
            if row.get("end_date"):
                phase_dates.append(str(row["end_date"]))

            phases.append(
                {
                    "name": phase_name[:80],
                    "progress_pct": row.get("progress_pct"),
                    "dates": phase_dates,
                    "raw": str(row.get("raw") or "")[:500],
                }
            )

        raw_parts = [str(row.get("raw") or "") for row in machine_rows if row.get("raw")]
        machines.append(
            {
                "name": str(base.get("name") or "Machine")[:200],
                "project_code": project_code,
                "overall_pct": overall_pct,
                "start_date": start_date,
                "end_date": end_date,
                "phases": phases,
                "raw": " || ".join(raw_parts[:3])[:2000],
            }
        )
    return machines


def _phase_entries_from_row(cells: list[str]) -> list[dict[str, Any]]:
    phases: list[dict[str, Any]] = []
    for index, cell in enumerate(cells[1:], start=2):
        content = cell.strip()
        if not content:
            continue
        pct = _extract_pct(content)
        dates = _extract_dates(content)
        phase_name = f"column_{index}"
        line_1 = content.splitlines()[0].strip()
        if line_1 and not _PCT_RE.fullmatch(line_1):
            phase_name = line_1[:80]
        phases.append(
            {
                "name": phase_name,
                "progress_pct": pct,
                "dates": dates,
                "raw": content,
            }
        )
    return phases


def _machine_from_row(cells: list[str]) -> dict[str, Any] | None:
    if not cells:
        return None

    machine_name = cells[0].strip()
    if not machine_name or machine_name.lower() in {"machine", "project", "description"}:
        return None

    row_text = " | ".join(cell for cell in cells if cell)
    overall_pct = _extract_pct(row_text)
    dates = _extract_dates(row_text)
    project_code_match = _PROJECT_CODE_RE.search(row_text)

    phases = _phase_entries_from_row(cells)
    if overall_pct is None and phases:
        phase_pcts = [phase["progress_pct"] for phase in phases if isinstance(phase.get("progress_pct"), (int, float))]
        if phase_pcts:
            overall_pct = round(sum(phase_pcts) / len(phase_pcts), 1)

    return {
        "name": machine_name[:200],
        "project_code": project_code_match.group(1) if project_code_match else None,
        "overall_pct": overall_pct if overall_pct is not None else 0.0,
        "start_date": dates[0] if len(dates) >= 1 else None,
        "end_date": dates[1] if len(dates) >= 2 else None,
        "phases": phases,
        "raw": row_text[:2000],
    }


def parse_gantt_pdf(pdf_path: str) -> dict[str, Any]:
    """Parse a Gantt PDF into a structured dict safe for JSON storage."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Gantt PDF not found: {pdf_path}")

    structured_rows: list[dict[str, Any]] = []
    machines: list[dict[str, Any]] = []
    milestones: list[str] = []

    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                parsed_rows, has_header = _parse_structured_table(table)
                if has_header:
                    structured_rows.extend(parsed_rows)
                    continue

                for raw_row in table or []:
                    cells = [_clean_cell(cell) for cell in raw_row]
                    if not any(cells):
                        continue
                    machine = _machine_from_row(cells)
                    if machine:
                        machines.append(machine)

            page_text = page.extract_text() or ""
            for line in page_text.splitlines():
                clean_line = line.strip()
                if not clean_line:
                    continue
                lower_line = clean_line.lower()
                if "fat" in lower_line or "milestone" in lower_line:
                    milestones.append(clean_line[:200])

    if structured_rows:
        machines = _aggregate_structured_rows(structured_rows)

    deduped_machines: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for machine in machines:
        key = str(machine.get("name") or "").strip().lower()
        if not key:
            continue
        if key in seen_names:
            continue
        seen_names.add(key)
        deduped_machines.append(machine)

    return {
        "machines": deduped_machines,
        "fat": {
            "milestones": milestones[:50],
        },
    }
