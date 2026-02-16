import pytest
from bs4 import BeautifulSoup

import src.utils.html_doc_filler as html_doc_filler
from src.utils.html_doc_filler import fill_html_template


SAMPLE_TEMPLATE = """
<!doctype html>
<html>
  <head></head>
  <body>
    <section class="section" id="section-a">
      <div class="section-header"><h2>Section A</h2></div>
      <div class="group">
        <div class="field-grid">
          <label class="field" data-placeholder="{{f1}}">
            <span class="label">Field 1</span>
            <input type="text" name="f1" data-placeholder="{{f1}}" />
          </label>
          <label class="field checkbox" data-placeholder="{{f2}}">
            <span class="label">Flag</span>
            <input type="checkbox" name="f2" data-placeholder="{{f2}}" />
          </label>
        </div>
      </div>
    </section>
    <section class="section" id="section-b">
      <div class="section-header"><h2>Section B</h2></div>
      <div class="group">
        <div class="field-grid">
          <label class="field" data-placeholder="{{f3}}">
            <span class="label">Field 3</span>
            <input type="text" name="f3" data-placeholder="{{f3}}" />
          </label>
        </div>
      </div>
    </section>
  </body>
</html>
"""


OPTIONS_LISTING_TEMPLATE = """
<!doctype html>
<html>
  <head></head>
  <body>
    <section class="section" id="section-options">
      <div class="group">
        <div class="field-grid">
          <label class="field textarea" data-placeholder="{{options_listing}}">
            <span class="label">Options</span>
            <textarea name="options_listing" data-placeholder="{{options_listing}}" rows="5"></textarea>
          </label>
        </div>
      </div>
    </section>
  </body>
</html>
"""


def _parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def test_hide_empty_fields_removes_blank_fields_only() -> None:
    html = fill_html_template(
        SAMPLE_TEMPLATE,
        {"f1": "Project 123", "f2": "NO", "f3": ""},
        hide_empty_fields=True,
        hide_empty_sections=False,
    )
    soup = _parse(html)

    assert soup.find("input", {"name": "f1"}) is not None
    assert soup.find("label", {"data-placeholder": "{{f2}}"}) is None
    assert soup.find("label", {"data-placeholder": "{{f3}}"}) is None
    assert soup.find("section", {"id": "section-b"}) is not None


def test_hide_empty_sections_removes_sections_with_no_populated_fields() -> None:
    html = fill_html_template(
        SAMPLE_TEMPLATE,
        {"f1": "Project 123", "f2": "NO", "f3": ""},
        hide_empty_fields=False,
        hide_empty_sections=True,
    )
    soup = _parse(html)

    assert soup.find("section", {"id": "section-a"}) is not None
    assert soup.find("section", {"id": "section-b"}) is None


def test_hide_empty_sections_and_fields_combines_filters() -> None:
    html = fill_html_template(
        SAMPLE_TEMPLATE,
        {"f1": "Project 123", "f2": "NO", "f3": ""},
        hide_empty_fields=True,
        hide_empty_sections=True,
    )
    soup = _parse(html)

    assert soup.find("section", {"id": "section-a"}) is not None
    assert soup.find("section", {"id": "section-b"}) is None
    assert soup.find("label", {"data-placeholder": "{{f1}}"}) is not None
    assert soup.find("label", {"data-placeholder": "{{f2}}"}) is None


def test_hide_empty_fields_removes_empty_options_listing() -> None:
    html = fill_html_template(
        OPTIONS_LISTING_TEMPLATE,
        {"options_listing": ""},
        hide_empty_fields=True,
        hide_empty_sections=True,
    )
    soup = _parse(html)

    assert soup.find("section", {"id": "section-options"}) is None


def test_options_listing_nested_bullets_keep_multiline_structure() -> None:
    html = fill_html_template(
        OPTIONS_LISTING_TEMPLATE,
        {
            "options_listing": (
                "Selected Options:\n"
                "• Main option\n"
                "  - Nested detail A\n"
                "  - Nested detail B\n"
                "• Secondary option"
            )
        },
    )
    soup = _parse(html)

    nested_items = soup.select(".options-listing > ul > li ul li")
    assert len(nested_items) == 2
    assert nested_items[0].get_text(strip=True) == "Nested detail A"
    assert nested_items[1].get_text(strip=True) == "Nested detail B"


def test_options_listing_machine_block_keeps_indented_subbullets() -> None:
    html = fill_html_template(
        OPTIONS_LISTING_TEMPLATE,
        {
            "options_listing": (
                "MACHINE: SortStar 18ft3 configuration\n"
                "  - Left to right orientation\n"
                "  - Integrated orientor package\n"
                "• Operator platform"
            )
        },
    )
    soup = _parse(html)

    machine_sub_items = soup.select(".options-listing div ul li")
    assert len(machine_sub_items) == 2
    assert machine_sub_items[0].get_text(strip=True) == "Left to right orientation"
    assert machine_sub_items[1].get_text(strip=True) == "Integrated orientor package"
    assert "Operator platform" in soup.get_text(" ", strip=True)


def test_label_overrides_rename_section_and_field_labels() -> None:
    html = fill_html_template(
        SAMPLE_TEMPLATE,
        {"f1": "Project 123", "f2": "YES", "f3": "Detail"},
        label_overrides={"section_a": "Order Identification", "f1": "Work Order #"},
    )
    soup = _parse(html)

    section_heading = soup.select_one("#section-a .section-header h2")
    assert section_heading is not None
    assert section_heading.get_text(strip=True) == "Order Identification"

    field_label = soup.select_one("label[data-placeholder='{{f1}}'] .label")
    assert field_label is not None
    assert field_label.get_text(strip=True) == "Work Order #"


def test_included_sections_keeps_only_selected_sections() -> None:
    html = fill_html_template(
        SAMPLE_TEMPLATE,
        {"f1": "Project 123", "f2": "NO", "f3": "Detail"},
        included_sections=["section_b"],
        hide_empty_sections=False,
        hide_empty_fields=False,
    )
    soup = _parse(html)

    assert soup.find("section", {"id": "section-a"}) is None
    assert soup.find("section", {"id": "section-b"}) is not None


def test_fill_html_template_injects_preview_helpers_without_print_layout_overrides() -> None:
    html = fill_html_template(
        SAMPLE_TEMPLATE,
        {"f1": "Project 123", "f2": "YES", "f3": "Detail"},
    )
    soup = _parse(html)

    styles = "\n".join(style.get_text() for style in soup.find_all("style"))

    assert "body.print-preview .section.collapsed > .section-content" in styles
    assert ".field.checkbox input[type=\"checkbox\"]:checked" in styles
    assert "@media print" not in styles


def test_prepare_html_for_pdf_injects_cover_page_and_quality_style() -> None:
    prepared_html, metadata = html_doc_filler._prepare_html_for_pdf(
        fill_html_template(
            SAMPLE_TEMPLATE,
            {"f1": "Project 123", "f2": "YES", "f3": "Detail"},
        )
    )
    soup = _parse(prepared_html)

    assert soup.select_one(".pdf-cover-page") is not None
    assert soup.select_one("style[data-pdf-quality='v2']") is not None
    assert metadata["project_number"] == "N/A"
    assert metadata["customer_name"] == "N/A"
    assert metadata["machine_name"] == "N/A"
    assert metadata["report_date"]


def test_generate_pdf_passes_prepared_html_to_playwright(monkeypatch, tmp_path) -> None:
    captured_html: list[str] = []

    monkeypatch.setattr(html_doc_filler, "PLAYWRIGHT_AVAILABLE", True)
    monkeypatch.setattr(html_doc_filler, "PLAYWRIGHT_IMPORT_ERROR", None)
    monkeypatch.setattr(html_doc_filler, "WEASYPRINT_AVAILABLE", False)
    monkeypatch.setattr(html_doc_filler, "WEASYPRINT_IMPORT_ERROR", "weasy missing")
    monkeypatch.setattr(html_doc_filler, "_resolve_wkhtmltopdf_binary", lambda: None)

    def stub_playwright(html: str, output_path: str) -> None:
        captured_html.append(html)

    monkeypatch.setattr(html_doc_filler, "_generate_pdf_with_playwright", stub_playwright)

    html_doc_filler.generate_pdf("<html><head></head><body><div class='page'></div></body></html>", str(tmp_path / "out.pdf"))

    assert len(captured_html) == 1
    assert "pdf-cover-page" in captured_html[0]
    assert "data-pdf-quality=\"v2\"" in captured_html[0]


def test_generate_pdf_prefers_playwright(monkeypatch, tmp_path) -> None:
    calls: list[str] = []

    monkeypatch.setattr(html_doc_filler, "PLAYWRIGHT_AVAILABLE", True)
    monkeypatch.setattr(html_doc_filler, "PLAYWRIGHT_IMPORT_ERROR", None)
    monkeypatch.setattr(html_doc_filler, "WEASYPRINT_AVAILABLE", True)
    monkeypatch.setattr(html_doc_filler, "WEASYPRINT_IMPORT_ERROR", None)
    monkeypatch.setattr(
        html_doc_filler,
        "_generate_pdf_with_playwright",
        lambda html, output: calls.append("playwright"),
    )
    monkeypatch.setattr(html_doc_filler, "_resolve_wkhtmltopdf_binary", lambda: None)

    class StubHTML:
        def __init__(self, string: str) -> None:
            calls.append("weasy-init")

        def write_pdf(self, output_path: str) -> None:
            calls.append("weasy-write")

    monkeypatch.setattr(html_doc_filler, "HTML", StubHTML, raising=False)

    html_doc_filler.generate_pdf("<html><body>test</body></html>", str(tmp_path / "out.pdf"))

    assert calls == ["playwright"]


def test_generate_pdf_falls_back_to_weasyprint(monkeypatch, tmp_path) -> None:
    calls: list[str] = []

    monkeypatch.setattr(html_doc_filler, "PLAYWRIGHT_AVAILABLE", True)
    monkeypatch.setattr(html_doc_filler, "PLAYWRIGHT_IMPORT_ERROR", None)
    monkeypatch.setattr(html_doc_filler, "WEASYPRINT_AVAILABLE", True)
    monkeypatch.setattr(html_doc_filler, "WEASYPRINT_IMPORT_ERROR", None)

    def fail_playwright(html: str, output_path: str) -> None:
        calls.append("playwright")
        raise RuntimeError("missing chromium")

    monkeypatch.setattr(html_doc_filler, "_generate_pdf_with_playwright", fail_playwright)
    monkeypatch.setattr(html_doc_filler, "_resolve_wkhtmltopdf_binary", lambda: None)

    class StubHTML:
        def __init__(self, string: str) -> None:
            calls.append("weasy-init")

        def write_pdf(self, output_path: str) -> None:
            calls.append("weasy-write")

    monkeypatch.setattr(html_doc_filler, "HTML", StubHTML, raising=False)

    html_doc_filler.generate_pdf("<html><body>test</body></html>", str(tmp_path / "out.pdf"))

    assert calls == ["playwright", "weasy-init", "weasy-write"]


def test_generate_pdf_raises_clear_error_when_no_engine(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(html_doc_filler, "PLAYWRIGHT_AVAILABLE", False)
    monkeypatch.setattr(html_doc_filler, "PLAYWRIGHT_IMPORT_ERROR", "playwright missing")
    monkeypatch.setattr(html_doc_filler, "WEASYPRINT_AVAILABLE", False)
    monkeypatch.setattr(html_doc_filler, "WEASYPRINT_IMPORT_ERROR", "weasy missing")
    monkeypatch.setattr(html_doc_filler, "_resolve_wkhtmltopdf_binary", lambda: None)

    with pytest.raises(RuntimeError, match="playwright install chromium"):
        html_doc_filler.generate_pdf("<html><body>test</body></html>", str(tmp_path / "out.pdf"))
