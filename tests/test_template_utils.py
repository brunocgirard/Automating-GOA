import pytest
import os
from src.utils.template_utils import extract_placeholders, generate_synonyms_for_checkbox

# Test functions will be added here 

def test_generate_synonyms_basic():
    key = "example_check"
    description = "Example Checkbox"
    synonyms = generate_synonyms_for_checkbox(key, description)
    assert "example" in synonyms
    assert "example checkbox" in synonyms
    assert "example_check" in synonyms
    # Check for some variations that should be generated
    assert "example checkbox" in synonyms # from description, lowercase, no punctuation
    assert "examplecheckbox" in synonyms # from description, lowercase, no space/punctuation

def test_generate_synonyms_with_common_terms():
    key = "plc_b_r_check"
    description = "PLC - B & R"
    synonyms = generate_synonyms_for_checkbox(key, description)
    assert "plc - b & r" in synonyms # direct from description
    assert "plc b & r" in synonyms   # normalized description
    assert "b & r plc" in synonyms   # reversed common term
    assert "plcbr" in synonyms      # concatenated
    assert "plc_b_r_check" in synonyms # original key
    assert "b&r plc" in synonyms

def test_generate_synonyms_empty_input():
    key = ""
    description = ""
    synonyms = generate_synonyms_for_checkbox(key, description)
    # Depending on implementation, it might return empty or minimal like ["_check"]
    # For robust behavior, it should ideally handle empty strings gracefully.
    # Let's assume it produces at least the key itself or a derivative.
    assert "_check" in synonyms or synonyms == []

    key = "test_check"
    description = ""
    synonyms = generate_synonyms_for_checkbox(key, description)
    assert "test_check" in synonyms
    assert "test" in synonyms

    key = ""
    description = "Only Description"
    synonyms = generate_synonyms_for_checkbox(key, description)
    assert "only description" in synonyms
    assert "onlydescription" in synonyms

def test_generate_synonyms_special_chars():
    key = "hmi_size5.7_check"
    description = "HMI Size 5.7\""
    synonyms = generate_synonyms_for_checkbox(key, description)
    # Check how special characters are handled (e.g., '.', '\"')
    assert "hmi size 5.7" in synonyms  # Assuming " is stripped, . might be kept or stripped
    assert "hmisize57" in synonyms # Concatenated version should strip the period
    assert "hmi_size5.7_check" in synonyms
    assert "5.7 hmi" in synonyms
    assert "5.7 inch hmi" in synonyms # common addition for size

def test_extract_placeholders_from_main_template():
    template_file = os.path.join("tests", "template.docx")
    # Ensure the test template actually exists where expected
    assert os.path.exists(template_file), f"Test template file not found: {template_file}"

    placeholders = extract_placeholders(template_file)
    
    assert isinstance(placeholders, list), "Function should return a list"
    # Assuming the main template has many placeholders
    assert len(placeholders) > 50, "Should extract a significant number of placeholders from the main template"

    # Check for a few specific, known placeholders (case-sensitive)
    # These are common ones from explicit_placeholder_mappings, assuming they are in the template
    expected_phs = ["customer", "machine", "quote", "production_speed", "amps", "voltage", "hz"]
    for ph in expected_phs:
        assert ph in placeholders, f"Expected placeholder '{ph}' not found in {template_file}"

    # Test if the list is sorted
    assert placeholders == sorted(placeholders), "Placeholder list should be sorted"

    # Example test for a placeholder that might have spaces in the template {{ example_spaced_key }}
    # If your template.docx has such a key, replace "example_spaced_key" with the actual cleaned key name.
    # If not, this can be commented out or removed.
    # assert "example_spaced_key" in placeholders, "Should find and clean placeholder with extra spaces"

def test_extract_placeholders_file_not_found():
    # This test assumes that the function handles FileNotFoundError by returning an empty list
    # as per the try-except block in extract_placeholders.
    placeholders = extract_placeholders("tests/non_existent_template.docx")
    assert placeholders == [], "Should return an empty list for a non-existent file"

# We can add this later if dummy_template_no_placeholders.docx is created
# def test_extract_placeholders_no_placeholders():
#     template_file = os.path.join("tests", "dummy_template_no_placeholders.docx")
#     assert os.path.exists(template_file), f"Test template file not found: {template_file}"
#     placeholders = extract_placeholders(template_file)
#     assert placeholders == [], "Should return an empty list for a document with no placeholders"

# Placeholder for extract_placeholders tests if we add dummy docx later
# def test_extract_placeholders_simple():
#     pass 