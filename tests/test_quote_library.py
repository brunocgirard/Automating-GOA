"""Tests for QUOTE_LIBRARY parsing and context matching utilities."""

from __future__ import annotations

import os
from pathlib import Path

from src.utils.quote_library import get_quote_library_context, load_quote_library_sections


def _write_library(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    os.utime(path, None)


def test_load_quote_library_sections_ignores_table_of_contents_lines(tmp_path: Path) -> None:
    library_file = tmp_path / "QUOTE_LIBRARY.txt"
    _write_library(
        library_file,
        """
Quote Library
Table of Contents
Bottle Unscrambler Model SortStar XL\t16
LabelStar Model System 1 ECO\t31

Machine Technical Specifications

Bottle Unscrambler Model SortStar XL
Automatic bottle unscrambler with rotary feeder and indexing star wheel for high-speed lines.
Machine Specifications:
* Speed up to 150 BPM
* Bottle diameter 20 to 120 mm
* Main power 220 V / 60 Hz

LabelStar Model System 1 ECO
Automatic labeling machine for round containers with wrap-around pressure-sensitive labels.
Machine Specifications:
* Maximum dispensing speed of 40 meters per minute
* Label width up to 97 mm
* Main power 220 V single phase
""".strip(),
    )

    sections = load_quote_library_sections(str(library_file))
    titles = [section.title for section in sections]

    assert "Bottle Unscrambler Model SortStar XL" in titles
    assert "LabelStar Model System 1 ECO" in titles
    assert len(sections) == 2


def test_get_quote_library_context_returns_best_machine_match(tmp_path: Path) -> None:
    library_file = tmp_path / "QUOTE_LIBRARY.txt"
    _write_library(
        library_file,
        """
Bottle Unscrambler Model SortStar XL
Unscrambler details for sortstar family with servo control and orientor options.
Machine Specifications:
* Speed up to 160 BPM
* Hopper size 18 cubic feet

LabelStar Model System 1 ECO
Labeling machine details for round bottle labels and belt wrap applications.
Machine Specifications:
* Maximum dispensing speed of 40 meters per minute
* Core diameter between 38 and 76 mm
""".strip(),
    )

    context, matches = get_quote_library_context(
        machine_name="LabelStar Model System 1 ECO",
        quote_library_path=str(library_file),
        max_sections=1,
        max_chars=4000,
    )

    assert matches == ["LabelStar Model System 1 ECO"]
    assert "Maximum dispensing speed of 40 meters per minute" in context
    assert "SortStar XL" not in context


def test_get_quote_library_context_refreshes_when_library_changes(tmp_path: Path) -> None:
    library_file = tmp_path / "QUOTE_LIBRARY.txt"
    _write_library(
        library_file,
        """
LabelStar Model System 1 ECO
Labeling machine details.
Machine Specifications:
* Maximum dispensing speed of 40 meters per minute
""".strip(),
    )

    context_before, matches_before = get_quote_library_context(
        machine_name="Bottle Unscrambler Feeder Model RoboSort 2",
        quote_library_path=str(library_file),
        max_sections=1,
        max_chars=4000,
    )

    assert context_before == ""
    assert matches_before == []

    with library_file.open("a", encoding="utf-8") as file:
        file.write(
            """

Bottle Unscrambler Feeder Model RoboSort 2
Bottle unscrambler feeder details with integrated hopper and indexing logic.
Machine Specifications:
* Speed up to 100 BPM
* Bottle diameter 25 to 125 mm
* Bottle height 50 to 300 mm
""".rstrip()
        )
    os.utime(library_file, None)

    context_after, matches_after = get_quote_library_context(
        machine_name="Bottle Unscrambler Feeder Model RoboSort 2",
        quote_library_path=str(library_file),
        max_sections=1,
        max_chars=4000,
    )

    assert matches_after == ["Bottle Unscrambler Feeder Model RoboSort 2"]
    assert "Speed up to 100 BPM" in context_after


def test_explicit_machine_header_format_is_supported(tmp_path: Path) -> None:
    library_file = tmp_path / "QUOTE_LIBRARY.txt"
    _write_library(
        library_file,
        """
Machine: Synergy Patriot FPCL
Monoblock filler system for liquid products with servo pumps and synchronized conveyors.
Machine Specifications:
* Speed up to 120 BPM
* Main power 480 V, 3 phase
* Servo-controlled filling with recipe memory
""".strip(),
    )

    sections = load_quote_library_sections(str(library_file))
    assert sections[0].title == "Synergy Patriot FPCL"

    context, matches = get_quote_library_context(
        machine_name="Monoblock Model Synergy Patriot FPCL",
        quote_library_path=str(library_file),
        max_sections=1,
        max_chars=4000,
    )
    assert matches == ["Synergy Patriot FPCL"]
    assert "Speed up to 120 BPM" in context
