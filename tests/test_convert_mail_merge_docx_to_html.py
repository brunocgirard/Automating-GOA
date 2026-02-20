"""Tests for Mail_merge DOCX to HTML batch conversion script."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import convert_mail_merge_docx_to_html as converter


SAMPLE_FRAGMENT = (
    '<table class="layout" style="width:97%">'
    "<tr><td><p>\u00abCustomer_PO\u00bb</p></td></tr>"
    "</table>"
)


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _create_placeholder_docx(path: Path) -> None:
    path.write_bytes(b"placeholder")


def test_build_pandoc_command_includes_required_flags() -> None:
    command = converter._build_pandoc_command("pandoc", Path("Mail_merge/Paking Slip.docx"))

    assert command[0] == "pandoc"
    assert "--embed-resources" in command
    assert "--wrap=none" in command
    assert "-f" in command
    assert "-t" in command
    assert "docx" in command
    assert "html5" in command


def test_strip_class_attributes_keeps_inline_styles_and_tokens() -> None:
    cleaned = converter._strip_class_attributes(SAMPLE_FRAGMENT)

    assert "class=" not in cleaned
    assert 'style="width:97%"' in cleaned
    assert "\u00abCustomer_PO\u00bb" in cleaned


def test_convert_templates_generates_expected_files_and_wrapper(monkeypatch, tmp_path: Path) -> None:
    source_dir = tmp_path / "Mail_merge"
    output_dir = source_dir / "html_fragments"
    source_dir.mkdir(parents=True, exist_ok=True)
    for filename in converter.OUTPUT_FILE_NAMES:
        _create_placeholder_docx(source_dir / filename)

    observed_commands: list[list[str]] = []

    def fake_run(command, capture_output, text, encoding, check):  # noqa: ANN001
        assert capture_output is True
        assert text is True
        assert encoding == "utf-8"
        assert check is False
        observed_commands.append(command)
        return _FakeCompletedProcess(returncode=0, stdout=SAMPLE_FRAGMENT)

    monkeypatch.setattr(converter.shutil, "which", lambda _: "pandoc")
    monkeypatch.setattr(converter.subprocess, "run", fake_run)

    converted = converter.convert_templates(source_dir=source_dir, output_dir=output_dir)

    assert len(converted) == len(converter.OUTPUT_FILE_NAMES)
    assert {destination.name for _, destination in converted} == {
        "paking-slip.html",
        "commercial-invoice.html",
        "certification-of-origin-nafta.html",
        "customer-oxxxx-cor.html",
    }
    for command in observed_commands:
        assert "--embed-resources" in command
        assert "--wrap=none" in command

    html_content = (output_dir / "paking-slip.html").read_text(encoding="utf-8")
    assert html_content.startswith('<article data-source-docx="Paking Slip.docx">')
    assert "class=" not in html_content
    assert 'style="width:97%"' in html_content
    assert "\u00abCustomer_PO\u00bb" in html_content

    stylesheet_content = (output_dir / converter.STYLESHEET_NAME).read_text(encoding="utf-8")
    assert "max-width: 795px;" in stylesheet_content
    assert ".panel" not in stylesheet_content


def test_convert_templates_raises_when_pandoc_missing(monkeypatch, tmp_path: Path) -> None:
    source_dir = tmp_path / "Mail_merge"
    source_dir.mkdir(parents=True, exist_ok=True)
    _create_placeholder_docx(source_dir / "Paking Slip.docx")

    monkeypatch.setattr(converter.shutil, "which", lambda _: None)

    with pytest.raises(RuntimeError, match="Pandoc is required"):
        converter.convert_templates(source_dir=source_dir, output_dir=tmp_path / "out")
