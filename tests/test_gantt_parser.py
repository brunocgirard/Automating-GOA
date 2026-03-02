from __future__ import annotations

from datetime import date

import pytest

from src.utils import gantt_parser


class _FakePage:
    def __init__(self, tables: list[list[list[str]]], text: str = "") -> None:
        self._tables = tables
        self._text = text

    def extract_tables(self) -> list[list[list[str]]]:
        return self._tables

    def extract_text(self) -> str:
        return self._text


class _FakePdf:
    def __init__(self, pages: list[_FakePage]) -> None:
        self.pages = pages

    def __enter__(self) -> "_FakePdf":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_parse_gantt_pdf_uses_task_name_and_schedule_fallback(monkeypatch, tmp_path) -> None:
    pdf_path = tmp_path / "gantt.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    table = [
        ["ID", "Task Name", "Duration", "Start", "Finish"],
        ["1", "", "", "", ""],
        ["3", "Validation", "288.43 d", "Tue 25 Jun '24", "Thu 12 Jun '25"],
        ["4", "DQ", "60 d", "Mon 04 Nov '24", "Wed 15 Jan '25"],
    ]

    fake_pdf = _FakePdf([_FakePage([table])])
    monkeypatch.setattr(gantt_parser.pdfplumber, "open", lambda _path: fake_pdf)
    monkeypatch.setattr(gantt_parser, "_today", lambda: date(2025, 1, 1))

    parsed = gantt_parser.parse_gantt_pdf(str(pdf_path))
    machines = parsed["machines"]
    names = {machine["name"] for machine in machines}

    assert "Validation" in names
    assert "DQ" in names
    assert "1" not in names

    validation = next(machine for machine in machines if machine["name"] == "Validation")
    assert validation["overall_pct"] > 0


def test_parse_gantt_pdf_reads_plain_numbers_in_percent_column(monkeypatch, tmp_path) -> None:
    pdf_path = tmp_path / "gantt.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    table = [
        ["ID", "Task Name", "Machine", "Start", "Finish", "% Complete"],
        ["10", "Design", "CF-2P", "1/12/26", "7/2/26", "13"],
        ["11", "Build", "CF-2P", "7/3/26", "8/1/26", "0.5"],
    ]

    fake_pdf = _FakePdf([_FakePage([table])])
    monkeypatch.setattr(gantt_parser.pdfplumber, "open", lambda _path: fake_pdf)

    parsed = gantt_parser.parse_gantt_pdf(str(pdf_path))
    machines = parsed["machines"]
    assert len(machines) == 1
    assert machines[0]["name"] == "CF-2P"
    assert machines[0]["overall_pct"] == pytest.approx(31.5, abs=0.1)

