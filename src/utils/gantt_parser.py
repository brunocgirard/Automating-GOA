"""Helpers for parsing PM Gantt PDFs into structured JSON."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pdfplumber

_PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_DATE_RE = re.compile(r"\b(\d{1,4}[/-]\d{1,2}[/-]\d{1,4})\b")


def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\r", "\n").strip()


def _extract_pct(text: str) -> float | None:
    match = _PCT_RE.search(text)
    if not match:
        return None
    try:
        return max(0.0, min(100.0, float(match.group(1))))
    except ValueError:
        return None


def _extract_dates(text: str) -> list[str]:
    return [match.group(1).strip() for match in _DATE_RE.finditer(text)]


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
    project_code_match = re.search(r"\b([A-Z]{1,5}-\d{2,5}[A-Z]?)\b", row_text)

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

    machines: list[dict[str, Any]] = []
    milestones: list[str] = []

    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
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
