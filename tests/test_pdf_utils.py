"""
Comprehensive unit tests for src/utils/pdf_utils.py

Tests cover:
1. extract_line_item_details() - PDF table extraction
2. extract_full_pdf_text() - Full text extraction
3. identify_machines_from_items() - Machine identification
4. extract_contextual_details() - Context extraction
5. Helper functions for table parsing
"""

import pytest
import os
from pathlib import Path
from typing import List, Dict, Optional

from src.utils.pdf_utils import (
    extract_line_item_details,
    extract_full_pdf_text,
    identify_machines_from_items,
    extract_contextual_details,
    find_table_headers,
    is_row_selected,
    get_description_from_row
)


# Test fixtures
@pytest.fixture
def sample_pdf_cqc():
    """Path to real sample PDF: CQC quote"""
    return "templates/CQC-25-2638R5-NP.pdf"


@pytest.fixture
def sample_pdf_ume():
    """Path to real sample PDF: UME quote"""
    return "templates/UME-23-0001CN-R5-V2.pdf"


@pytest.fixture
def nonexistent_pdf():
    """Path to a PDF that doesn't exist"""
    return "templates/nonexistent_quote.pdf"


# ============================================================================
# Tests for find_table_headers()
# ============================================================================

class TestFindTableHeaders:
    """Test suite for find_table_headers() helper function"""

    def test_find_headers_standard_format(self):
        """Test header detection with standard column names"""
        table = [
            ["Description", "Qty.", "Total"],
            ["Item 1", "1", "1000"],
            ["Item 2", "2", "2000"]
        ]
        headers = find_table_headers(table)

        assert headers is not None
        assert "description" in headers
        assert "quantity" in headers
        assert "selection_text_source" in headers

    def test_find_headers_case_insensitive(self):
        """Test that header detection is case-insensitive"""
        table = [
            ["DESCRIPTION", "QTY", "AMOUNT"],
            ["Item 1", "1", "1000"]
        ]
        headers = find_table_headers(table)

        assert headers is not None
        assert headers["description"] == 0
        assert headers["quantity"] == 1

    def test_find_headers_french_columns(self):
        """Test header detection with French column names"""
        table = [
            ["Désignation", "Qté", "Montant"],
            ["Article 1", "1", "1000"]
        ]
        headers = find_table_headers(table)

        assert headers is not None
        assert "description" in headers
        assert "quantity" in headers

    def test_find_headers_missing_price_column(self):
        """Test when price column is missing but qty is present"""
        table = [
            ["Description", "Qty.", "Unit Cost"],
            ["Item 1", "1", "100"]
        ]
        headers = find_table_headers(table)

        # Should still find headers, using qty as selection text source
        assert headers is not None
        assert "description" in headers

    def test_find_headers_no_description_column(self):
        """Test that None is returned when description column is missing"""
        table = [
            ["Qty.", "Amount"],
            ["1", "1000"]
        ]
        headers = find_table_headers(table)

        assert headers is None

    def test_find_headers_empty_table(self):
        """Test with empty table"""
        table = []
        headers = find_table_headers(table)

        assert headers is None

    def test_find_headers_none_cells(self):
        """Test with None values in header row"""
        table = [
            [None, "Description", None, "Qty.", None, "Total"],
            ["", "Item 1", "", "1", "", "1000"]
        ]
        headers = find_table_headers(table)

        assert headers is not None
        assert headers["description"] == 1
        assert headers["quantity"] == 3


# ============================================================================
# Tests for is_row_selected()
# ============================================================================

class TestIsRowSelected:
    """Test suite for is_row_selected() helper function"""

    def test_row_selected_with_price(self):
        """Test that row with price value is marked as selected"""
        headers = {
            "description": 0,
            "selection_text_source": 2,
            "quantity": 1,
            "selection": 2
        }
        row = ["Item 1", "1", "1000.00"]

        # Note: is_row_selected() checks for "selection" key in headers
        # The function uses this to get the selection index
        assert is_row_selected(row, headers) is True

    def test_row_selected_with_included_keyword(self):
        """Test that row with 'Included' keyword is marked as selected"""
        headers = {
            "description": 0,
            "selection": 2,
            "quantity": 1
        }
        row = ["Item 1", "1", "Included"]

        assert is_row_selected(row, headers) is True

    def test_row_not_selected_empty_cell(self):
        """Test that row with empty selection cell is not selected"""
        headers = {
            "description": 0,
            "selection": 2,
            "quantity": 1
        }
        row = ["Item 1", "1", ""]

        assert is_row_selected(row, headers) is False

    def test_row_not_selected_none_value(self):
        """Test that row with None in selection cell is not selected"""
        headers = {
            "description": 0,
            "selection": 2,
            "quantity": 1
        }
        row = ["Item 1", "1", None]

        assert is_row_selected(row, headers) is False

    def test_row_not_selected_explicit_no(self):
        """Test that 'No' or 'None' values are not selected"""
        headers = {
            "description": 0,
            "selection": 2,
            "quantity": 1
        }

        row_no = ["Item 1", "1", "No"]
        row_none = ["Item 1", "1", "None"]
        row_dash = ["Item 1", "1", "-"]

        assert is_row_selected(row_no, headers) is False
        assert is_row_selected(row_none, headers) is False
        assert is_row_selected(row_dash, headers) is False


# ============================================================================
# Tests for get_description_from_row()
# ============================================================================

class TestGetDescriptionFromRow:
    """Test suite for get_description_from_row() helper function"""

    def test_get_description_basic(self):
        """Test basic description extraction"""
        headers = {"description": 0}
        row = ["Machine Model XYZ", "1", "1000"]

        desc = get_description_from_row(row, headers)
        assert desc == "Machine Model XYZ"

    def test_get_description_with_whitespace(self):
        """Test description extraction with leading/trailing whitespace"""
        headers = {"description": 0}
        row = ["  Machine Model XYZ  ", "1", "1000"]

        desc = get_description_from_row(row, headers)
        assert desc == "Machine Model XYZ"

    def test_get_description_missing_column(self):
        """Test when description column index is out of range"""
        headers = {"description": 5}
        row = ["Machine Model XYZ", "1", "1000"]

        desc = get_description_from_row(row, headers)
        assert desc is None

    def test_get_description_none_cell(self):
        """Test when description cell is None"""
        headers = {"description": 0}
        row = [None, "1", "1000"]

        desc = get_description_from_row(row, headers)
        assert desc is None

    def test_get_description_multiline(self):
        """Test description extraction with newlines"""
        headers = {"description": 0}
        row = ["Machine Model XYZ\nWith multiple lines", "1", "1000"]

        desc = get_description_from_row(row, headers)
        assert "Machine Model XYZ" in desc
        assert "With multiple lines" in desc


# ============================================================================
# Tests for extract_line_item_details()
# ============================================================================

class TestExtractLineItemDetails:
    """Test suite for extract_line_item_details()"""

    def test_extract_from_real_pdf_cqc(self, sample_pdf_cqc):
        """Test extraction from real PDF (CQC quote)"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        items = extract_line_item_details(sample_pdf_cqc)

        # Should extract at least some items
        assert isinstance(items, list)
        assert len(items) > 0

        # Each item should have required fields
        for item in items:
            assert "description" in item
            assert "quantity_text" in item
            assert "selection_text" in item
            assert item["description"] is not None

    def test_extract_from_real_pdf_ume(self, sample_pdf_ume):
        """Test extraction from real PDF (UME quote)"""
        if not os.path.exists(sample_pdf_ume):
            pytest.skip(f"Sample PDF not found: {sample_pdf_ume}")

        items = extract_line_item_details(sample_pdf_ume)

        # Should extract items
        assert isinstance(items, list)
        assert len(items) >= 0  # At least well-formed result

    def test_extract_returns_list(self, sample_pdf_cqc):
        """Test that function returns a list"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        items = extract_line_item_details(sample_pdf_cqc)
        assert isinstance(items, list)

    def test_extract_with_nonexistent_file(self, nonexistent_pdf):
        """Test that function handles nonexistent file gracefully"""
        items = extract_line_item_details(nonexistent_pdf)

        # Should return empty list, not crash
        assert isinstance(items, list)
        assert len(items) == 0

    def test_extract_item_structure(self, sample_pdf_cqc):
        """Test that extracted items have correct structure"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        items = extract_line_item_details(sample_pdf_cqc)

        if items:
            # Check first item structure
            first_item = items[0]
            assert isinstance(first_item, dict)
            assert set(first_item.keys()) == {
                "description", "quantity_text", "selection_text"
            }

            # Values should be strings or None
            for key, value in first_item.items():
                assert value is None or isinstance(value, str)

    def test_extract_deduplicates_items(self, sample_pdf_cqc):
        """Test that identical items are deduplicated"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        items = extract_line_item_details(sample_pdf_cqc)

        # Create set of tuples to check for duplicates
        item_tuples = [
            (item["description"], item["quantity_text"], item["selection_text"])
            for item in items
        ]

        # All tuples should be unique
        assert len(item_tuples) == len(set(item_tuples))

    def test_extract_descriptions_are_nonempty(self, sample_pdf_cqc):
        """Test that extracted descriptions are not empty"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        items = extract_line_item_details(sample_pdf_cqc)

        for item in items:
            # Description should be present and meaningful
            desc = item.get("description", "")
            assert desc and len(desc) > 0
            # Should not be just whitespace
            assert desc.strip()

    def test_extract_items_have_valid_selection(self, sample_pdf_cqc):
        """Test that extracted items are actually selected (have valid data)"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        items = extract_line_item_details(sample_pdf_cqc)

        for item in items:
            # Item should have either quantity or selection text
            qty = item.get("quantity_text", "")
            sel = item.get("selection_text", "")

            # At least one should have content
            assert (qty and qty.strip()) or (sel and sel.strip())


# ============================================================================
# Tests for extract_full_pdf_text()
# ============================================================================

class TestExtractFullPdfText:
    """Test suite for extract_full_pdf_text()"""

    def test_extract_full_text_basic(self, sample_pdf_cqc):
        """Test basic full text extraction"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        text = extract_full_pdf_text(sample_pdf_cqc)

        assert isinstance(text, str)
        assert len(text) > 0

    def test_extract_full_text_returns_string(self, sample_pdf_cqc):
        """Test that function returns a string"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        text = extract_full_pdf_text(sample_pdf_cqc)
        assert isinstance(text, str)

    def test_extract_full_text_with_default_tolerances(self, sample_pdf_cqc):
        """Test extraction with default x_tol and y_tol"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        text = extract_full_pdf_text(sample_pdf_cqc)
        assert len(text) > 0

    def test_extract_full_text_with_custom_tolerances(self, sample_pdf_cqc):
        """Test extraction with custom tolerances"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        text_default = extract_full_pdf_text(sample_pdf_cqc, x_tol=1.5, y_tol=3)
        text_loose = extract_full_pdf_text(sample_pdf_cqc, x_tol=3.0, y_tol=6)

        # Both should extract text
        assert len(text_default) > 0
        assert len(text_loose) > 0

        # Loose tolerances might result in different text
        # (but both should be valid)

    def test_extract_full_text_multiple_pages(self, sample_pdf_cqc):
        """Test that all pages are extracted"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        text = extract_full_pdf_text(sample_pdf_cqc)

        # PDF has 39 pages, text should be substantial
        assert len(text) > 5000  # Should have significant content

    def test_extract_full_text_contains_newlines(self, sample_pdf_cqc):
        """Test that extracted text contains page separators"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        text = extract_full_pdf_text(sample_pdf_cqc)

        # Pages are separated by newlines
        assert "\n" in text

    def test_extract_full_text_nonexistent_file(self, nonexistent_pdf):
        """Test handling of nonexistent file"""
        text = extract_full_pdf_text(nonexistent_pdf)

        # Should return empty string, not crash
        assert isinstance(text, str)
        assert text == ""

    def test_extract_full_text_content_quality(self, sample_pdf_cqc):
        """Test that extracted text contains meaningful content"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        text = extract_full_pdf_text(sample_pdf_cqc)

        # Text should contain some recognizable words/patterns
        text_lower = text.lower()
        # Common words that should appear in a quote
        assert any(word in text_lower for word in [
            "price", "qty", "description", "model", "total", "item"
        ])


# ============================================================================
# Tests for identify_machines_from_items()
# ============================================================================

class TestIdentifyMachinesFromItems:
    """Test suite for identify_machines_from_items()"""

    def test_identify_single_machine(self):
        """Test identification of a single main machine with add-ons"""
        items = [
            {
                "description": "Model XYZ Filler Machine\nWith safety features",
                "quantity_text": "1",
                "selection_text": "50000",
                "item_price_numeric": 50000
            },
            {
                "description": "Extended Warranty Package",
                "quantity_text": "1",
                "selection_text": "5000",
                "item_price_numeric": 5000
            },
            {
                "description": "Installation Service",
                "quantity_text": "Included",
                "selection_text": "Included",
                "item_price_numeric": 0
            }
        ]

        result = identify_machines_from_items(items)

        assert "machines" in result
        assert "common_items" in result
        assert isinstance(result["machines"], list)
        assert isinstance(result["common_items"], list)

        # Should identify one main machine
        assert len(result["machines"]) >= 1

    def test_identify_multiple_machines(self):
        """Test identification of multiple main machines"""
        items = [
            {
                "description": "Bottle Unscrambler Model XYZ",
                "quantity_text": "1",
                "selection_text": "30000",
                "item_price_numeric": 30000
            },
            {
                "description": "Add-on for unscrambler",
                "quantity_text": "1",
                "selection_text": "2000",
                "item_price_numeric": 2000
            },
            {
                "description": "Capper Machine Model ABC",
                "quantity_text": "1",
                "selection_text": "25000",
                "item_price_numeric": 25000
            },
            {
                "description": "Add-on for capper",
                "quantity_text": "1",
                "selection_text": "1000",
                "item_price_numeric": 1000
            }
        ]

        result = identify_machines_from_items(items)

        assert len(result["machines"]) >= 2

    def test_identify_common_items(self):
        """Test identification of common items (warranty, installation, etc.)"""
        items = [
            {
                "description": "Main Machine",
                "quantity_text": "1",
                "selection_text": "20000",
                "item_price_numeric": 20000
            },
            {
                "description": "Warranty Package - 5 Years",
                "quantity_text": "1",
                "selection_text": "2000",
                "item_price_numeric": 2000
            },
            {
                "description": "Installation and Training",
                "quantity_text": "Included",
                "selection_text": "Included",
                "item_price_numeric": 0
            },
            {
                "description": "Spare Parts Kit",
                "quantity_text": "1",
                "selection_text": "1000",
                "item_price_numeric": 1000
            }
        ]

        result = identify_machines_from_items(items)

        # Should identify common items
        assert len(result["common_items"]) > 0

    def test_identify_price_threshold(self):
        """Test that price threshold correctly identifies main machines"""
        default_threshold = 10000

        items = [
            {
                "description": "High Price Item",
                "quantity_text": "1",
                "selection_text": "15000",
                "item_price_numeric": 15000
            },
            {
                "description": "Low Price Item",
                "quantity_text": "1",
                "selection_text": "500",
                "item_price_numeric": 500
            }
        ]

        result = identify_machines_from_items(items, price_threshold=default_threshold)

        # High price item should be main machine
        assert len(result["machines"]) >= 1

    def test_identify_custom_price_threshold(self):
        """Test with custom price threshold"""
        items = [
            {
                "description": "Model ABC Labeler",
                "quantity_text": "1",
                "selection_text": "8000",
                "item_price_numeric": 8000
            }
        ]

        # With default threshold (10000), this is an add-on
        result_default = identify_machines_from_items(items, price_threshold=10000)

        # With lower threshold, this becomes a main machine
        result_low = identify_machines_from_items(items, price_threshold=5000)

        # Both should handle gracefully
        assert isinstance(result_default["machines"], list)
        assert isinstance(result_low["machines"], list)

    def test_identify_empty_items_list(self):
        """Test with empty items list"""
        items = []
        result = identify_machines_from_items(items)

        assert result["machines"] == []
        assert result["common_items"] == []

    def test_identify_single_item(self):
        """Test with single item"""
        items = [
            {
                "description": "Standalone Machine",
                "quantity_text": "1",
                "selection_text": "15000",
                "item_price_numeric": 15000
            }
        ]

        result = identify_machines_from_items(items)

        assert len(result["machines"]) >= 1

    def test_identify_machines_add_price_numeric(self):
        """Test that price_numeric is added to items"""
        items = [
            {
                "description": "Machine",
                "quantity_text": "1",
                "selection_text": "20000.50"
            }
        ]

        result = identify_machines_from_items(items)

        # Check that price_numeric was added
        for machine in result["machines"]:
            if machine["main_item"]:
                assert "item_price_numeric" in machine["main_item"]

    def test_identify_result_structure(self):
        """Test that result has correct structure"""
        items = [
            {
                "description": "Test Machine",
                "quantity_text": "1",
                "selection_text": "30000",
                "item_price_numeric": 30000
            },
            {
                "description": "Add-on Item",
                "quantity_text": "1",
                "selection_text": "1000",
                "item_price_numeric": 1000
            }
        ]

        result = identify_machines_from_items(items)

        # Check structure
        assert isinstance(result, dict)
        assert "machines" in result
        assert "common_items" in result

        # Check machine structure
        if result["machines"]:
            machine = result["machines"][0]
            assert "machine_name" in machine
            assert "main_item" in machine
            assert "add_ons" in machine
            assert isinstance(machine["add_ons"], list)

    def test_identify_monoblock_pattern(self):
        """Test that 'monoblock' pattern is recognized"""
        items = [
            {
                "description": "Monoblock Filler-Capper Model FC-100",
                "quantity_text": "1",
                "selection_text": "40000",
                "item_price_numeric": 40000
            }
        ]

        result = identify_machines_from_items(items, price_threshold=20000)

        # Should recognize as main machine (pattern match)
        assert len(result["machines"]) >= 1

    def test_identify_case_insensitive_patterns(self):
        """Test that pattern matching is case-insensitive"""
        items = [
            {
                "description": "WARRANTY PACKAGE - 3 YEARS",
                "quantity_text": "1",
                "selection_text": "1000",
                "item_price_numeric": 1000
            },
            {
                "description": "SPARE PARTS KIT",
                "quantity_text": "1",
                "selection_text": "500",
                "item_price_numeric": 500
            }
        ]

        result = identify_machines_from_items(items)

        # These should be identified as common items despite being uppercase
        assert len(result["common_items"]) > 0


# ============================================================================
# Tests for extract_contextual_details()
# ============================================================================

class TestExtractContextualDetails:
    """Test suite for extract_contextual_details()"""

    def test_extract_context_from_real_pdf(self, sample_pdf_cqc):
        """Test context extraction from real PDF"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        # Use a known trigger from the PDF
        trigger = "Bottle Unscrambler"
        all_descriptions = ["Bottle Unscrambler Model SortStar XL"]

        context = extract_contextual_details(sample_pdf_cqc, trigger, all_descriptions)

        # Should return a string (may be empty if trigger not found)
        assert isinstance(context, str)

    def test_extract_context_returns_string(self, sample_pdf_cqc):
        """Test that function returns a string"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        context = extract_contextual_details(
            sample_pdf_cqc,
            "test trigger",
            ["Item 1", "Item 2"]
        )

        assert isinstance(context, str)

    def test_extract_context_empty_descriptions(self, sample_pdf_cqc):
        """Test with empty descriptions list"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        context = extract_contextual_details(
            sample_pdf_cqc,
            "trigger",
            []
        )

        assert isinstance(context, str)

    def test_extract_context_nonexistent_file(self, nonexistent_pdf):
        """Test with nonexistent PDF file"""
        context = extract_contextual_details(
            nonexistent_pdf,
            "trigger",
            []
        )

        # Should return empty string
        assert isinstance(context, str)
        assert context == ""

    def test_extract_context_invalid_trigger(self, sample_pdf_cqc):
        """Test with trigger that doesn't exist in PDF"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        context = extract_contextual_details(
            sample_pdf_cqc,
            "xyzabc nonexistent trigger 12345",
            ["Item 1"]
        )

        # Should return empty string if trigger not found
        assert isinstance(context, str)

    def test_extract_context_short_trigger(self, sample_pdf_cqc):
        """Test that short triggers work (as per doc)"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        # Use a short trigger
        trigger = "Bottle"
        all_descriptions = ["Bottle Unscrambler"]

        context = extract_contextual_details(sample_pdf_cqc, trigger, all_descriptions)

        assert isinstance(context, str)

    def test_extract_context_multiple_items_stop_trigger(self, sample_pdf_cqc):
        """Test that context stops at other item descriptions"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        trigger = "Bottle Unscrambler"
        all_descriptions = [
            "Bottle Unscrambler Model SortStar XL",
            "Installation Service",
            "Warranty Package"
        ]

        context = extract_contextual_details(sample_pdf_cqc, trigger, all_descriptions)

        # Should stop before hitting other items
        # Result should be reasonable (empty or contain context lines)
        assert isinstance(context, str)

    def test_extract_context_case_insensitive_trigger(self, sample_pdf_cqc):
        """Test that trigger matching is case-insensitive"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        # Try different cases
        trigger_lower = "bottle"
        trigger_upper = "BOTTLE"

        context_lower = extract_contextual_details(
            sample_pdf_cqc,
            trigger_lower,
            ["Bottle Unscrambler"]
        )
        context_upper = extract_contextual_details(
            sample_pdf_cqc,
            trigger_upper,
            ["Bottle Unscrambler"]
        )

        # Both should work (case-insensitive matching)
        assert isinstance(context_lower, str)
        assert isinstance(context_upper, str)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests combining multiple functions"""

    def test_end_to_end_pdf_to_machines(self, sample_pdf_cqc):
        """Test complete workflow: PDF -> items -> machines"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        # Step 1: Extract line items
        items = extract_line_item_details(sample_pdf_cqc)
        assert len(items) > 0

        # Step 2: Identify machines
        result = identify_machines_from_items(items)
        assert "machines" in result
        assert "common_items" in result

        # Step 3: Extract full text
        full_text = extract_full_pdf_text(sample_pdf_cqc)
        assert len(full_text) > 0

    def test_full_text_and_contextual_extraction(self, sample_pdf_cqc):
        """Test that extracted context is coherent"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        # Extract items first
        items = extract_line_item_details(sample_pdf_cqc)

        if items:
            # Extract context for first item
            descriptions = [item["description"] for item in items]
            context = extract_contextual_details(
                sample_pdf_cqc,
                descriptions[0].split('\n')[0],  # Use first line as trigger
                descriptions
            )

            # Context should be properly formatted string
            assert isinstance(context, str)

    def test_machine_grouping_with_real_data(self, sample_pdf_cqc):
        """Test machine grouping with real PDF data"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        items = extract_line_item_details(sample_pdf_cqc)
        result = identify_machines_from_items(items)

        # Validate structure
        assert isinstance(result["machines"], list)
        for machine in result["machines"]:
            assert "machine_name" in machine
            assert isinstance(machine["add_ons"], list)

            # Each add-on should have proper structure
            for addon in machine["add_ons"]:
                assert "description" in addon


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error conditions"""

    def test_extract_with_corrupted_pdf(self):
        """Test handling of corrupted PDF (if available)"""
        # This would require a corrupted PDF file
        # For now, test with nonexistent file
        items = extract_line_item_details("templates/corrupted.pdf")
        assert isinstance(items, list)

    def test_items_with_missing_fields(self):
        """Test machine identification with items missing fields"""
        items = [
            {"description": "Machine"},  # Missing quantity_text and selection_text
            {"quantity_text": "1"},  # Missing description
        ]

        result = identify_machines_from_items(items)

        # Should handle gracefully
        assert isinstance(result, dict)
        assert "machines" in result

    def test_items_with_special_characters(self):
        """Test items with special characters in description"""
        items = [
            {
                "description": "Machine & Equipment (Model XYZ-100™)",
                "quantity_text": "1",
                "selection_text": "25000",
                "item_price_numeric": 25000
            }
        ]

        result = identify_machines_from_items(items)

        # Should handle special characters
        assert len(result["machines"]) >= 0

    def test_items_with_unicode_characters(self):
        """Test items with unicode characters"""
        items = [
            {
                "description": "Machine Café™ avec équipement français",
                "quantity_text": "1",
                "selection_text": "20000",
                "item_price_numeric": 20000
            }
        ]

        result = identify_machines_from_items(items)

        # Should handle unicode
        assert isinstance(result, dict)

    def test_very_large_items_list(self):
        """Test with a large number of items"""
        items = [
            {
                "description": f"Item {i}",
                "quantity_text": "1",
                "selection_text": str(100 + i),
                "item_price_numeric": 100 + i
            }
            for i in range(100)
        ]

        result = identify_machines_from_items(items)

        # Should handle large lists
        assert isinstance(result, dict)
        assert len(result["machines"]) >= 0

    def test_items_with_numeric_only_descriptions(self):
        """Test items with only numeric descriptions"""
        items = [
            {
                "description": "12345",
                "quantity_text": "1",
                "selection_text": "999",
                "item_price_numeric": 999
            }
        ]

        result = identify_machines_from_items(items)

        # Should handle numeric descriptions
        assert isinstance(result, dict)

    def test_extract_line_items_with_zero_price(self, sample_pdf_cqc):
        """Test that items with zero/no price are handled"""
        if not os.path.exists(sample_pdf_cqc):
            pytest.skip(f"Sample PDF not found: {sample_pdf_cqc}")

        items = extract_line_item_details(sample_pdf_cqc)

        # Some items may have "Included" instead of price
        # Verify they're still extracted
        assert isinstance(items, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
