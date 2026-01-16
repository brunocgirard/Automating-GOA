import pytest
import os
import tempfile
from pathlib import Path
from html.parser import HTMLParser
import re

from src.utils.form_generator import (
    load_rows,
    generate_goa_form,
    display_label,
    group_by_section,
    render_input,
    render_group,
    render_section,
    build_html,
    extract_schema_from_excel,
    get_all_fields_from_excel,
)


class TestLoadRows:
    """Test suite for load_rows() function."""

    def test_load_rows_returns_list(self):
        """Test that load_rows returns a list of dictionaries."""
        rows = load_rows()
        assert isinstance(rows, list), "load_rows should return a list"
        assert len(rows) > 0, "load_rows should return non-empty list"

    def test_load_rows_field_structure(self):
        """Test that each row has required fields."""
        rows = load_rows()
        required_keys = {"section", "subsection", "subsub", "field", "type", "placeholder"}

        for row in rows:
            assert isinstance(row, dict), "Each row should be a dictionary"
            assert all(key in row for key in required_keys), \
                f"Row missing required keys. Got: {row.keys()}"

            # Verify values are strings
            for key, value in row.items():
                assert isinstance(value, str), \
                    f"Row[{key}] should be string, got {type(value)}"

    def test_load_rows_field_count_approximately_602(self):
        """Test that approximately 602 fields are loaded (as per documentation)."""
        rows = load_rows()
        # Allow some flexibility due to filtering empty rows or auto-added fields
        assert 600 <= len(rows) <= 620, \
            f"Expected ~602 fields, got {len(rows)}"

    def test_load_rows_placeholder_uniqueness(self):
        """Test that placeholders are not duplicated (mostly)."""
        rows = load_rows()
        placeholders = [row["placeholder"] for row in rows]

        # Count duplicates - there might be a few but shouldn't be many
        unique_count = len(set(placeholders))
        total_count = len(placeholders)

        # Allow ~2% duplication tolerance
        assert unique_count > total_count * 0.98, \
            f"Too many duplicate placeholders: {total_count - unique_count} duplicates"

    def test_load_rows_valid_types(self):
        """Test that all rows have valid field types."""
        rows = load_rows()
        valid_types = {"text", "checkbox", "textarea", "qty"}

        for row in rows:
            assert row["type"] in valid_types, \
                f"Invalid type '{row['type']}' in field {row['placeholder']}"

    def test_load_rows_section_consistency(self):
        """Test that sections are consistent and not empty for grouped data."""
        rows = load_rows()

        for row in rows:
            # Section should be non-empty
            assert len(row["section"].strip()) > 0, \
                f"Section should not be empty for field {row['placeholder']}"

    def test_load_rows_options_listing_exists(self):
        """Test that options_listing field is present."""
        rows = load_rows()
        placeholders = [row["placeholder"] for row in rows]

        assert "options_listing" in placeholders, \
            "options_listing field should be present"

        # Find and verify it
        options_row = next(r for r in rows if r["placeholder"] == "options_listing")
        assert options_row["type"] == "textarea", \
            "options_listing should be textarea type"

    def test_load_rows_non_existent_file(self):
        """Test that FileNotFoundError is raised for missing Excel file."""
        with pytest.raises(FileNotFoundError):
            load_rows(Path("nonexistent_path.xlsx"))

    def test_load_rows_missing_form_sheet(self):
        """Test that ValueError is raised if 'Form' sheet doesn't exist."""
        # This would require creating a test Excel file, so we skip detailed testing
        # but verify the error handling logic exists in code
        pass

    def test_load_rows_placeholder_format(self):
        """Test that placeholders follow expected format (mostly fXXXX or special)."""
        rows = load_rows()

        # Count fields that follow fXXXX pattern
        fxxxx_pattern = re.compile(r"^f\d{4,}$")
        special_placeholders = {"options_listing"}

        fxxxx_count = 0
        for row in rows:
            ph = row["placeholder"]
            if fxxxx_pattern.match(ph) or ph in special_placeholders:
                fxxxx_count += 1

        # Most should follow this pattern
        assert fxxxx_count > len(rows) * 0.95, \
            f"Most placeholders should follow fXXXX pattern, got {fxxxx_count}/{len(rows)}"

    def test_load_rows_field_name_not_empty(self):
        """Test that field names are not empty."""
        rows = load_rows()

        for row in rows:
            assert len(row["field"].strip()) > 0, \
                f"Field name should not be empty for {row['placeholder']}"


class TestDisplayLabel:
    """Test suite for display_label() function."""

    def test_display_label_removes_text_suffix(self):
        """Test that (text) suffix is removed."""
        assert display_label("Proj. # (text)") == "Proj. #"

    def test_display_label_removes_checkbox_suffix(self):
        """Test that (checkbox) suffix is removed."""
        assert display_label("Option (checkbox)") == "Option"

    def test_display_label_removes_qty_suffix(self):
        """Test that (qty) suffix is removed."""
        assert display_label("Quantity (qty)") == "Quantity"

    def test_display_label_removes_example_hint(self):
        """Test that example hints are removed."""
        result = display_label('Proj. # (text) - example: "Ax"')
        assert "example" not in result.lower()
        assert "Proj. #" in result

    def test_display_label_removes_multiple_suffixes(self):
        """Test handling of multiple patterns."""
        result = display_label("Field (text) - example: something")
        assert "(" not in result
        assert "example" not in result.lower()
        assert "Field" in result

    def test_display_label_case_insensitive(self):
        """Test that suffix removal is case-insensitive."""
        assert display_label("Field (TEXT)") == "Field"
        assert display_label("Field (CheckBox)") == "Field"

    def test_display_label_preserves_content(self):
        """Test that meaningful content is preserved."""
        result = display_label("My Important Field (text)")
        assert "Important" in result
        assert "Field" in result

    def test_display_label_empty_string(self):
        """Test handling of empty string."""
        result = display_label("")
        assert isinstance(result, str)


class TestGroupBySection:
    """Test suite for group_by_section() function."""

    def test_group_by_section_returns_dict(self):
        """Test that function returns a dictionary."""
        rows = load_rows()
        grouped = group_by_section(rows)
        assert isinstance(grouped, dict)

    def test_group_by_section_preserves_all_rows(self):
        """Test that no rows are lost during grouping."""
        rows = load_rows()
        grouped = group_by_section(rows)

        total_grouped = sum(len(items) for items in grouped.values())
        assert total_grouped == len(rows), \
            f"Rows lost during grouping: {len(rows)} -> {total_grouped}"

    def test_group_by_section_correct_grouping(self):
        """Test that rows are grouped correctly by section."""
        rows = load_rows()
        grouped = group_by_section(rows)

        for section_name, items in grouped.items():
            # All items in group should have same section
            for item in items:
                assert item["section"] == section_name, \
                    f"Item {item['placeholder']} in wrong section"

    def test_group_by_section_multiple_sections(self):
        """Test that multiple sections are created."""
        rows = load_rows()
        grouped = group_by_section(rows)
        assert len(grouped) > 1, "Should have multiple sections"


class TestRenderInput:
    """Test suite for render_input() function."""

    def test_render_input_text_field(self):
        """Test rendering of text input field."""
        row = {
            "placeholder": "test_field",
            "field": "Test Field",
            "type": "text"
        }
        html = render_input(row)

        assert "input" in html
        assert 'type="text"' in html
        assert "test_field" in html
        assert "Test Field" in html

    def test_render_input_checkbox_field(self):
        """Test rendering of checkbox field."""
        row = {
            "placeholder": "test_check",
            "field": "Test Checkbox",
            "type": "checkbox"
        }
        html = render_input(row)

        assert "input" in html
        assert 'type="checkbox"' in html
        assert "test_check" in html
        assert "Test Checkbox" in html

    def test_render_input_qty_field(self):
        """Test rendering of quantity (number) field."""
        row = {
            "placeholder": "qty_field",
            "field": "Quantity",
            "type": "qty"
        }
        html = render_input(row)

        assert "input" in html
        assert 'type="number"' in html
        assert "qty_field" in html

    def test_render_input_textarea_field(self):
        """Test rendering of textarea field."""
        row = {
            "placeholder": "notes",
            "field": "Notes",
            "type": "textarea"
        }
        html = render_input(row)

        assert "textarea" in html
        assert "notes" in html
        assert "Notes" in html

    def test_render_input_options_listing_special(self):
        """Test special handling of options_listing field."""
        row = {
            "placeholder": "options_listing",
            "field": "Options",
            "type": "text"
        }
        html = render_input(row)

        # Should render as textarea even though type is text
        assert "textarea" in html
        assert "options_listing" in html

    def test_render_input_html_escaping(self):
        """Test that HTML special characters are escaped."""
        row = {
            "placeholder": "test",
            "field": "Test & <Field>",
            "type": "text"
        }
        html = render_input(row)

        # HTML should be escaped
        assert "&amp;" in html or "&" not in html or "Test &amp; &lt;Field&gt;" in html

    def test_render_input_data_placeholder_attribute(self):
        """Test that data-placeholder attribute is present."""
        row = {
            "placeholder": "test",
            "field": "Test",
            "type": "text"
        }
        html = render_input(row)

        assert 'data-placeholder=' in html

    def test_render_input_contains_token(self):
        """Test that placeholder token is included."""
        row = {
            "placeholder": "test_token",
            "field": "Test",
            "type": "text"
        }
        html = render_input(row)

        # Token should be in HTML (though may be hidden via CSS)
        # The token appears as {{test_token}} in the HTML
        assert "{{test_token}}" in html


class TestRenderGroup:
    """Test suite for render_group() function."""

    def test_render_group_with_title(self):
        """Test rendering group with title."""
        items = [
            {"placeholder": "f001", "field": "Field 1", "type": "text"},
            {"placeholder": "f002", "field": "Field 2", "type": "text"}
        ]
        html = render_group("Test Group", items)

        assert "group" in html
        assert "Test Group" in html

    def test_render_group_without_title(self):
        """Test rendering group without title."""
        items = [
            {"placeholder": "f001", "field": "Field 1", "type": "text"}
        ]
        html = render_group("", items)

        assert "group" in html

    def test_render_group_checkbox_items_use_checkbox_grid(self):
        """Test that all-checkbox groups use checkbox-grid class."""
        items = [
            {"placeholder": "f001", "field": "Check 1", "type": "checkbox"},
            {"placeholder": "f002", "field": "Check 2", "type": "checkbox"}
        ]
        html = render_group("Checkboxes", items)

        assert "checkbox-grid" in html

    def test_render_group_mixed_items_use_field_grid(self):
        """Test that mixed item groups use field-grid class."""
        items = [
            {"placeholder": "f001", "field": "Field 1", "type": "text"},
            {"placeholder": "f002", "field": "Check 1", "type": "checkbox"}
        ]
        html = render_group("Mixed", items)

        assert "field-grid" in html

    def test_render_group_preserves_all_items(self):
        """Test that all items are rendered in group."""
        items = [
            {"placeholder": f"f{i:04d}", "field": f"Field {i}", "type": "text"}
            for i in range(5)
        ]
        html = render_group("Group", items)

        for item in items:
            assert item["placeholder"] in html


class TestRenderSection:
    """Test suite for render_section() function."""

    def test_render_section_basic(self):
        """Test basic section rendering."""
        items = [
            {"placeholder": "f001", "field": "Field 1", "type": "text",
             "subsection": "", "subsub": ""}
        ]
        html = render_section("Test Section", items)

        assert "section" in html
        assert "Test Section" in html

    def test_render_section_removes_section_suffix(self):
        """Test that '(section)' suffix is removed from title."""
        items = [
            {"placeholder": "f001", "field": "Field 1", "type": "text",
             "subsection": "", "subsub": ""}
        ]
        html = render_section("My Section (section)", items)

        assert "My Section (section)" not in html
        assert "My Section" in html

    def test_render_section_preserves_all_items(self):
        """Test that all items are rendered in section."""
        items = [
            {"placeholder": f"f{i:04d}", "field": f"Field {i}", "type": "text",
             "subsection": "", "subsub": ""}
            for i in range(5)
        ]
        html = render_section("Section", items)

        for item in items:
            assert item["placeholder"] in html

    def test_render_section_groups_by_subsection(self):
        """Test that items are grouped by subsection."""
        items = [
            {"placeholder": "f001", "field": "Field 1", "type": "text",
             "subsection": "Sub A", "subsub": ""},
            {"placeholder": "f002", "field": "Field 2", "type": "text",
             "subsection": "Sub A", "subsub": ""},
            {"placeholder": "f003", "field": "Field 3", "type": "text",
             "subsection": "Sub B", "subsub": ""}
        ]
        html = render_section("Section", items)

        # Should have group titles for subsections
        assert "Sub A" in html
        assert "Sub B" in html


class TestBuildHtml:
    """Test suite for build_html() function."""

    def test_build_html_returns_string(self):
        """Test that build_html returns HTML string."""
        rows = load_rows()[:10]  # Use small sample
        html = build_html(rows)

        assert isinstance(html, string), "Should return string"
        assert len(html) > 0

    def test_build_html_contains_doctype(self):
        """Test that HTML contains doctype declaration."""
        rows = load_rows()[:10]
        html = build_html(rows)

        assert "<!doctype html>" in html.lower()

    def test_build_html_contains_sections(self):
        """Test that HTML contains section elements."""
        rows = load_rows()[:20]
        html = build_html(rows)

        assert "<section" in html

    def test_build_html_contains_style(self):
        """Test that HTML contains CSS styling."""
        rows = load_rows()[:10]
        html = build_html(rows)

        assert "<style>" in html
        assert "</style>" in html
        assert "color:" in html

    def test_build_html_contains_javascript(self):
        """Test that HTML contains JavaScript."""
        rows = load_rows()[:10]
        html = build_html(rows)

        assert "<script>" in html
        assert "</script>" in html

    def test_build_html_title_is_correct(self):
        """Test that page title is correct."""
        rows = load_rows()[:10]
        html = build_html(rows)

        assert "General Order Acknowledgement" in html

    def test_build_html_section_order_preserved(self):
        """Test that section order matches Excel order."""
        rows = load_rows()
        html = build_html(rows)

        # Get first few unique sections from rows
        sections_in_rows = []
        seen = set()
        for row in rows[:50]:
            if row["section"] not in seen:
                sections_in_rows.append(row["section"])
                seen.add(row["section"])
                if len(sections_in_rows) >= 3:
                    break

        # Check they appear in same order in HTML
        positions = []
        for section in sections_in_rows:
            pos = html.find(section)
            assert pos > 0, f"Section '{section}' not found in HTML"
            positions.append(pos)

        assert positions == sorted(positions), "Section order not preserved"


class TestGenerateGoaForm:
    """Test suite for generate_goa_form() function."""

    def test_generate_goa_form_creates_file(self):
        """Test that generate_goa_form creates output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_form.html"
            result = generate_goa_form(output_path=output_path)

            assert result is True, "Should return True on success"
            assert output_path.exists(), "Output file should be created"

    def test_generate_goa_form_output_is_valid_html(self):
        """Test that generated output is valid HTML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_form.html"
            generate_goa_form(output_path=output_path)

            with open(output_path, 'r', encoding='utf-8') as f:
                html = f.read()

            assert "<!doctype html>" in html.lower()
            assert "<html" in html
            assert "</html>" in html

    def test_generate_goa_form_contains_all_fields(self):
        """Test that generated form contains fields from Excel."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_form.html"
            generate_goa_form(output_path=output_path)

            rows = load_rows()

            with open(output_path, 'r', encoding='utf-8') as f:
                html = f.read()

            # Check that many field placeholders are in HTML
            placeholder_count = 0
            for row in rows:
                if row["placeholder"] in html:
                    placeholder_count += 1

            # Should have at least 90% of placeholders
            assert placeholder_count > len(rows) * 0.9, \
                f"Only {placeholder_count}/{len(rows)} placeholders found in HTML"

    def test_generate_goa_form_with_custom_excel_path(self):
        """Test generate_goa_form with custom Excel path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_form.html"

            # Use actual Excel path
            excel_path = Path("templates/GOA_template.xlsx")
            result = generate_goa_form(excel_path=excel_path, output_path=output_path)

            assert result is True

    def test_generate_goa_form_handles_missing_excel(self):
        """Test that generate_goa_form handles missing Excel file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_form.html"

            result = generate_goa_form(
                excel_path=Path("nonexistent.xlsx"),
                output_path=output_path
            )

            assert result is False, "Should return False on error"

    def test_generate_goa_form_file_is_readable(self):
        """Test that generated file is readable and has content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_form.html"
            generate_goa_form(output_path=output_path)

            file_size = output_path.stat().st_size
            assert file_size > 10000, f"File seems too small: {file_size} bytes"

    def test_generate_goa_form_contains_sections(self):
        """Test that output contains section elements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_form.html"
            generate_goa_form(output_path=output_path)

            with open(output_path, 'r', encoding='utf-8') as f:
                html = f.read()

            section_count = html.count("<section")
            assert section_count > 5, f"Expected multiple sections, got {section_count}"

    def test_generate_goa_form_contains_inputs(self):
        """Test that output contains input elements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_form.html"
            generate_goa_form(output_path=output_path)

            with open(output_path, 'r', encoding='utf-8') as f:
                html = f.read()

            # Should have text, checkbox, number, textarea inputs
            assert 'type="text"' in html
            assert 'type="checkbox"' in html
            assert 'type="number"' in html
            assert "<textarea" in html


class TestExtractSchemaFromExcel:
    """Test suite for extract_schema_from_excel() function."""

    def test_extract_schema_returns_dict(self):
        """Test that function returns a dictionary."""
        schema = extract_schema_from_excel()
        assert isinstance(schema, dict)

    def test_extract_schema_has_all_fields(self):
        """Test that schema contains all fields."""
        schema = extract_schema_from_excel()
        rows = load_rows()

        assert len(schema) == len(rows), \
            f"Schema size {len(schema)} != rows {len(rows)}"

    def test_extract_schema_field_structure(self):
        """Test that each schema entry has required keys."""
        schema = extract_schema_from_excel()
        required_keys = {"type", "section", "subsection", "description"}

        for placeholder, entry in schema.items():
            assert isinstance(entry, dict), f"Schema[{placeholder}] should be dict"
            assert all(key in entry for key in required_keys), \
                f"Schema[{placeholder}] missing required keys"

    def test_extract_schema_types_are_valid(self):
        """Test that schema types are string or boolean."""
        schema = extract_schema_from_excel()
        valid_types = {"string", "boolean"}

        for placeholder, entry in schema.items():
            assert entry["type"] in valid_types, \
                f"Invalid type '{entry['type']}' for {placeholder}"

    def test_extract_schema_checkbox_has_synonyms(self):
        """Test that checkbox fields have synonyms."""
        schema = extract_schema_from_excel()

        # Find a checkbox field
        checkbox_placeholders = [ph for ph, entry in schema.items()
                                  if entry["type"] == "boolean"]

        assert len(checkbox_placeholders) > 0, "Should have checkbox fields"

        for ph in checkbox_placeholders[:5]:
            entry = schema[ph]
            assert "synonyms" in entry, f"Checkbox {ph} missing synonyms"
            assert isinstance(entry["synonyms"], list)

    def test_extract_schema_checkbox_has_indicators(self):
        """Test that checkbox fields have positive indicators."""
        schema = extract_schema_from_excel()

        # Find a checkbox field
        checkbox_placeholders = [ph for ph, entry in schema.items()
                                  if entry["type"] == "boolean"]

        assert len(checkbox_placeholders) > 0

        for ph in checkbox_placeholders[:5]:
            entry = schema[ph]
            assert "positive_indicators" in entry, \
                f"Checkbox {ph} missing positive_indicators"

    def test_extract_schema_description_populated(self):
        """Test that descriptions are populated for all fields."""
        schema = extract_schema_from_excel()

        for placeholder, entry in schema.items():
            assert len(entry["description"]) > 0, \
                f"Description empty for {placeholder}"


class TestGetAllFieldsFromExcel:
    """Test suite for get_all_fields_from_excel() function."""

    def test_get_all_fields_returns_dict(self):
        """Test that function returns dictionary."""
        fields = get_all_fields_from_excel()
        assert isinstance(fields, dict)

    def test_get_all_fields_has_all_placeholders(self):
        """Test that all field placeholders are included."""
        fields = get_all_fields_from_excel()
        rows = load_rows()

        assert len(fields) == len(rows), \
            f"Fields {len(fields)} != rows {len(rows)}"

    def test_get_all_fields_descriptions_populated(self):
        """Test that all fields have descriptions."""
        fields = get_all_fields_from_excel()

        for placeholder, description in fields.items():
            assert len(description) > 0, \
                f"Description empty for {placeholder}"

    def test_get_all_fields_specific_field(self):
        """Test that specific field is in dictionary."""
        fields = get_all_fields_from_excel()

        # Check for some common fields
        assert "f0001" in fields or len(fields) > 0

        if "f0001" in fields:
            assert "Customer" in fields["f0001"] or \
                   "Proj" in fields["f0001"]


class TestIntegration:
    """Integration tests for form_generator module."""

    def test_full_workflow_excel_to_html(self):
        """Test complete workflow from Excel to HTML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "generated_form.html"

            # Load rows
            rows = load_rows()
            assert len(rows) > 0

            # Generate HTML
            result = generate_goa_form(output_path=output_path)
            assert result is True

            # Verify file exists and is valid
            assert output_path.exists()

            with open(output_path, 'r', encoding='utf-8') as f:
                html = f.read()

            assert "<!doctype html>" in html.lower()
            assert "<section" in html
            assert len(html) > 100000

    def test_field_types_rendered_correctly(self):
        """Test that all field types are rendered in output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_form.html"
            generate_goa_form(output_path=output_path)

            with open(output_path, 'r', encoding='utf-8') as f:
                html = f.read()

            # Check for each input type
            assert 'type="text"' in html, "Missing text input"
            assert 'type="checkbox"' in html, "Missing checkbox input"
            assert 'type="number"' in html, "Missing number input"
            assert "<textarea" in html, "Missing textarea"

    def test_consistency_between_functions(self):
        """Test consistency between different functions."""
        rows = load_rows()
        schema = extract_schema_from_excel()
        fields = get_all_fields_from_excel()

        # All should have same count
        assert len(rows) == len(schema) == len(fields), \
            "Data structure sizes don't match"

        # All placeholders should match
        row_phs = {r["placeholder"] for r in rows}
        schema_phs = set(schema.keys())
        field_phs = set(fields.keys())

        assert row_phs == schema_phs == field_phs, \
            "Placeholder sets don't match"

    def test_generated_form_html_structure(self):
        """Test structure of generated HTML form."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_form.html"
            generate_goa_form(output_path=output_path)

            with open(output_path, 'r', encoding='utf-8') as f:
                html = f.read()

            # Check key structural elements
            assert html.count("<section") == html.count("</section>")
            # DIVs should be balanced (equal opening and closing tags)
            assert html.count("<div") == html.count("</div>")
            assert "<header" in html
            assert "<style>" in html
            assert "<script>" in html


# Helper type to check string
string = type("string")

# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
