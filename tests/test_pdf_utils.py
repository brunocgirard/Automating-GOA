import pytest
pytest.importorskip("pdfplumber")
from src.utils.pdf_utils import is_row_selected


def test_is_row_selected_with_quantity_only():
    headers = {"selection": 2, "quantity": 1}
    row = ["FAT / SAT Protocol Package", "1", ""]
    assert is_row_selected(row, headers)


def test_is_row_selected_empty():
    headers = {"selection": 2, "quantity": 1}
    row = ["Unselected Item", "", ""]
    assert not is_row_selected(row, headers)
