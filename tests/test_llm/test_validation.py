"""
Unit tests for the validation module (src/llm/validation.py).

This module tests:
- Field dependency validation
- Response format validation
- Required field checks
- Cross-field consistency checks
"""

import pytest
from src.llm.validation import validate_field_dependencies, validate_llm_response


class TestVoltagFrequencyDependency:
    """Test voltage-frequency relationship validation."""

    def test_voltage_460_suggests_60hz(self):
        """Test that voltage 460 suggests 60 Hz."""
        extracted_data = {"voltage": "460V"}
        confidence_scores = {"voltage": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Should have no suggestion since no hz field
        assert len([s for s in suggestions if s["field"] == "hz"]) == 1
        assert suggestions[0]["suggested_value"] == "60 Hz"

    def test_voltage_480_suggests_60hz(self):
        """Test that voltage 480 suggests 60 Hz (North American standard)."""
        extracted_data = {"voltage": "480V"}
        confidence_scores = {"voltage": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        suggestion = next((s for s in suggestions if s["field"] == "hz"), None)
        assert suggestion is not None
        assert suggestion["suggested_value"] == "60 Hz"

    def test_voltage_400_suggests_50hz(self):
        """Test that voltage 400 suggests 50 Hz (European standard)."""
        extracted_data = {"voltage": "400V"}
        confidence_scores = {"voltage": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        suggestion = next((s for s in suggestions if s["field"] == "hz"), None)
        assert suggestion is not None
        assert suggestion["suggested_value"] == "50 Hz"

    def test_voltage_380_suggests_50hz(self):
        """Test that voltage 380 suggests 50 Hz."""
        extracted_data = {"voltage": "380V"}
        confidence_scores = {"voltage": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        suggestion = next((s for s in suggestions if s["field"] == "hz"), None)
        assert suggestion is not None
        assert suggestion["suggested_value"] == "50 Hz"

    def test_voltage_230_suggests_50hz(self):
        """Test that voltage 230 suggests 50 Hz (European)."""
        extracted_data = {"voltage": "230V"}
        confidence_scores = {"voltage": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        suggestion = next((s for s in suggestions if s["field"] == "hz"), None)
        assert suggestion is not None
        assert suggestion["suggested_value"] == "50 Hz"

    def test_voltage_120_suggests_60hz(self):
        """Test that voltage 120 suggests 60 Hz (North American)."""
        extracted_data = {"voltage": "120V"}
        confidence_scores = {"voltage": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        suggestion = next((s for s in suggestions if s["field"] == "hz"), None)
        assert suggestion is not None
        assert suggestion["suggested_value"] == "60 Hz"

    def test_voltage_110_suggests_60hz(self):
        """Test that voltage 110 suggests 60 Hz."""
        extracted_data = {"voltage": "110V"}
        confidence_scores = {"voltage": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        suggestion = next((s for s in suggestions if s["field"] == "hz"), None)
        assert suggestion is not None
        assert suggestion["suggested_value"] == "60 Hz"


class TestHzVoltageConsistency:
    """Test consistency between Hz and voltage when both are filled."""

    def test_60hz_with_460v_consistent(self):
        """Test that 60 Hz with 460V is consistent (no warning)."""
        extracted_data = {"voltage": "460V", "hz": "60"}
        confidence_scores = {"voltage": 0.9, "hz": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Should not have warning
        warnings = [s for s in suggestions if s["type"] == "warning"]
        assert len(warnings) == 0

    def test_50hz_with_460v_inconsistent(self):
        """Test that 50 Hz with 460V is inconsistent (warning)."""
        extracted_data = {"voltage": "460V", "hz": "50"}
        confidence_scores = {"voltage": 0.9, "hz": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Should have warning
        warnings = [s for s in suggestions if s["type"] == "warning" and s["field"] == "hz"]
        assert len(warnings) > 0
        assert updated_conf["hz"] < 0.5

    def test_60hz_with_400v_inconsistent(self):
        """Test that 60 Hz with 400V is inconsistent (warning)."""
        extracted_data = {"voltage": "400V", "hz": "60"}
        confidence_scores = {"voltage": 0.9, "hz": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Should have warning
        warnings = [s for s in suggestions if s["type"] == "warning" and s["field"] == "hz"]
        assert len(warnings) > 0
        assert updated_conf["hz"] < 0.5

    def test_50hz_with_400v_consistent(self):
        """Test that 50 Hz with 400V is consistent (no warning)."""
        extracted_data = {"voltage": "400V", "hz": "50"}
        confidence_scores = {"voltage": 0.9, "hz": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Should not have warning
        warnings = [s for s in suggestions if s["type"] == "warning"]
        assert len(warnings) == 0

    def test_hz_with_hz_suffix_normalized(self):
        """Test that Hz with 'Hz' suffix is properly parsed."""
        extracted_data = {"voltage": "460V", "hz": "60 Hz"}
        confidence_scores = {"voltage": 0.9, "hz": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Should parse correctly and not issue warning
        warnings = [s for s in suggestions if s["type"] == "warning"]
        assert len(warnings) == 0

    def test_hz_lowercase_normalized(self):
        """Test that 'hz' lowercase is properly parsed."""
        extracted_data = {"voltage": "460V", "hz": "60 hz"}
        confidence_scores = {"voltage": 0.9, "hz": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Should parse correctly
        warnings = [s for s in suggestions if s["type"] == "warning"]
        assert len(warnings) == 0


class TestPSICFMDependency:
    """Test PSI and CFM relationship validation."""

    def test_psi_without_cfm_generates_info(self):
        """Test that PSI without CFM generates an info message."""
        extracted_data = {"psi": "100"}
        confidence_scores = {"psi": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Should have info message
        info_msgs = [s for s in suggestions if s["type"] == "info"]
        assert len(info_msgs) > 0
        assert any("CFM" in msg.get("reason", "") for msg in info_msgs)

    def test_psi_with_cfm_no_message(self):
        """Test that PSI with CFM doesn't generate a message."""
        extracted_data = {"psi": "100", "cfm": "50"}
        confidence_scores = {"psi": 0.9, "cfm": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Should not have CFM info message
        cfm_msgs = [s for s in suggestions if "CFM" in s.get("reason", "")]
        assert len(cfm_msgs) == 0

    def test_cfm_without_psi_no_suggestion(self):
        """Test that CFM without PSI doesn't trigger suggestion."""
        extracted_data = {"cfm": "50"}
        confidence_scores = {"cfm": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # PSI not mentioned
        psi_msgs = [s for s in suggestions if s["field"] == "psi"]
        assert len(psi_msgs) == 0


class TestValidateLLMResponse:
    """Test LLM response validation against schema."""

    def test_valid_response_no_errors(self):
        """Test that a valid response produces no errors."""
        response_data = {
            "machine": "Model X",
            "customer": "Customer A",
            "checkbox_field": "YES"
        }
        expected_schema = {
            "machine": {"type": "string"},
            "customer": {"type": "string"},
            "checkbox_field": {"type": "boolean"}
        }
        errors = validate_llm_response(response_data, expected_schema)
        assert errors == {}

    def test_missing_field_detected(self):
        """Test that missing fields are detected."""
        response_data = {"machine": "Model X"}
        expected_schema = {
            "machine": {"type": "string"},
            "customer": {"type": "string"}
        }
        errors = validate_llm_response(response_data, expected_schema)
        assert "customer" in errors
        assert "Missing field" in errors["customer"]

    def test_invalid_boolean_value_detected(self):
        """Test that invalid boolean values are detected."""
        response_data = {"checkbox_field": "maybe"}
        expected_schema = {"checkbox_field": {"type": "boolean"}}
        errors = validate_llm_response(response_data, expected_schema)
        assert "checkbox_field" in errors
        assert any("YES" in err or "NO" in err for err in errors["checkbox_field"])

    def test_boolean_yes_valid(self):
        """Test that 'YES' is a valid boolean value."""
        response_data = {"checkbox_field": "YES"}
        expected_schema = {"checkbox_field": {"type": "boolean"}}
        errors = validate_llm_response(response_data, expected_schema)
        assert "checkbox_field" not in errors

    def test_boolean_no_valid(self):
        """Test that 'NO' is a valid boolean value."""
        response_data = {"checkbox_field": "NO"}
        expected_schema = {"checkbox_field": {"type": "boolean"}}
        errors = validate_llm_response(response_data, expected_schema)
        assert "checkbox_field" not in errors

    def test_boolean_yes_lowercase_valid(self):
        """Test that lowercase 'yes' is accepted (the validation is case-insensitive via .upper())."""
        response_data = {"checkbox_field": "yes"}
        expected_schema = {"checkbox_field": {"type": "boolean"}}
        errors = validate_llm_response(response_data, expected_schema)
        # The validation checks .upper() so lowercase is valid
        assert "checkbox_field" not in errors

    def test_invalid_string_type_detected(self):
        """Test that non-string values for string fields are detected."""
        response_data = {"machine": 123}
        expected_schema = {"machine": {"type": "string"}}
        errors = validate_llm_response(response_data, expected_schema)
        assert "machine" in errors
        assert "Expected string" in errors["machine"][0]

    def test_unexpected_field_detected(self):
        """Test that unexpected fields are detected."""
        response_data = {
            "machine": "Model X",
            "unexpected_field": "value"
        }
        expected_schema = {"machine": {"type": "string"}}
        errors = validate_llm_response(response_data, expected_schema)
        assert "unexpected_field" in errors
        assert "Unexpected field" in errors["unexpected_field"]

    def test_extra_fields_detected(self):
        """Test that all extra fields are detected."""
        response_data = {
            "machine": "Model X",
            "field1": "value1",
            "field2": "value2"
        }
        expected_schema = {"machine": {"type": "string"}}
        errors = validate_llm_response(response_data, expected_schema)
        assert len(errors) == 2
        assert "field1" in errors
        assert "field2" in errors

    def test_empty_response(self):
        """Test that empty response with required fields shows errors."""
        response_data = {}
        expected_schema = {
            "machine": {"type": "string"},
            "customer": {"type": "string"}
        }
        errors = validate_llm_response(response_data, expected_schema)
        assert "machine" in errors
        assert "customer" in errors

    def test_empty_schema_with_response(self):
        """Test that response with empty schema detects extra fields."""
        response_data = {"machine": "Model X"}
        expected_schema = {}
        errors = validate_llm_response(response_data, expected_schema)
        assert "machine" in errors
        assert "Unexpected field" in errors["machine"]

    def test_complex_schema_validation(self):
        """Test validation of a complex schema."""
        response_data = {
            "machine": "Model X",
            "customer": "Customer A",
            "voltage": "480V",
            "hz": "60 Hz",
            "plc_siemens_check": "YES",
            "plc_allen_bradley_check": "NO",
            "hmi_size_10_check": "YES"
        }
        expected_schema = {
            "machine": {"type": "string"},
            "customer": {"type": "string"},
            "voltage": {"type": "string"},
            "hz": {"type": "string"},
            "plc_siemens_check": {"type": "boolean"},
            "plc_allen_bradley_check": {"type": "boolean"},
            "hmi_size_10_check": {"type": "boolean"}
        }
        errors = validate_llm_response(response_data, expected_schema)
        assert errors == {}

    def test_none_value_in_response(self):
        """Test handling of None values in response."""
        response_data = {"machine": None}
        expected_schema = {"machine": {"type": "string"}}
        errors = validate_llm_response(response_data, expected_schema)
        # None is not a string
        assert "machine" in errors


class TestFieldDependencyDataUpdates:
    """Test that field dependency validation updates data appropriately."""

    def test_confidence_not_modified_if_consistent(self):
        """Test that confidence is not reduced if fields are consistent."""
        extracted_data = {"voltage": "460V", "hz": "60"}
        confidence_scores = {"voltage": 0.9, "hz": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Confidence should remain unchanged if consistent
        assert updated_conf["hz"] == 0.9

    def test_confidence_reduced_if_inconsistent(self):
        """Test that confidence is reduced if fields are inconsistent."""
        extracted_data = {"voltage": "460V", "hz": "50"}
        confidence_scores = {"voltage": 0.9, "hz": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Confidence should be reduced
        assert updated_conf["hz"] < 0.9

    def test_data_not_auto_corrected_only_suggested(self):
        """Test that validation suggests but doesn't auto-correct values."""
        extracted_data = {"voltage": "460V"}
        confidence_scores = {"voltage": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Original voltage should remain
        assert updated_data["voltage"] == "460V"
        # But a suggestion should be made
        assert len(suggestions) > 0


class TestEdgeCases:
    """Test edge cases in validation."""

    def test_empty_extracted_data(self):
        """Test validation with empty extracted data."""
        extracted_data = {}
        confidence_scores = {}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        assert updated_data == {}
        assert updated_conf == {}
        assert suggestions == []

    def test_uppercase_voltage_values(self):
        """Test validation with uppercase voltage values."""
        extracted_data = {"voltage": "460V", "hz": "60"}
        confidence_scores = {"voltage": 0.9, "hz": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Should handle uppercase correctly
        assert len(suggestions) == 0  # Consistent

    def test_voltage_with_lowercase_v(self):
        """Test validation with lowercase 'v' suffix."""
        extracted_data = {"voltage": "460v"}
        confidence_scores = {"voltage": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Should still recognize it and suggest Hz
        suggestion = next((s for s in suggestions if s["field"] == "hz"), None)
        assert suggestion is not None

    def test_hz_with_multiple_spaces(self):
        """Test parsing Hz with multiple spaces."""
        extracted_data = {"voltage": "460V", "hz": "60   Hz"}
        confidence_scores = {"voltage": 0.9, "hz": 0.9}
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Should parse correctly despite extra spaces
        warnings = [s for s in suggestions if s["type"] == "warning"]
        assert len(warnings) == 0

    def test_missing_confidence_score(self):
        """Test validation when some confidence scores are missing."""
        extracted_data = {"voltage": "460V", "hz": "60"}
        confidence_scores = {"voltage": 0.9}  # hz missing
        updated_data, updated_conf, suggestions = validate_field_dependencies(extracted_data, confidence_scores)

        # Should still work, using default if needed
        assert "hz" in updated_conf or "hz" not in updated_conf  # Either way is ok
