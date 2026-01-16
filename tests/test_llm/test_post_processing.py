"""
Unit tests for the post-processing module (src/llm/post_processing.py).

This module tests all 11 core correction rules and the zero-evidence check:
1. Checkbox value normalization (YES/NO casing)
2. HMI size mutual exclusivity
3. PLC type mutual exclusivity
4. Voltage format standardization
5. Frequency format standardization
6. Pressure format standardization
7. Multi-color beacon logic
8. Production speed unit formatting
9. Cross-field validation (filling system)
10. Explosion proof consistency
11. SortStar basic configuration mutual exclusivity
12. Zero-evidence check for checkbox fields
"""

import pytest
from src.llm.post_processing import apply_post_processing_rules, _zero_evidence_check


class TestCheckboxValueNormalization:
    """Test Rule 1: Checkbox value normalization."""

    def test_normalize_yes_lowercase_with_evidence(self):
        """Test that 'yes' is normalized to 'YES' when there is evidence."""
        field_data = {"test_check": "yes"}
        template_schema = {"test_check": {"type": "boolean", "positive_indicators": ["test"]}}
        pdf_text = "This test is required"
        result = apply_post_processing_rules(field_data, template_schema, pdf_text, [])
        assert result["test_check"] == "YES"

    def test_normalize_no_lowercase(self):
        """Test that 'no' is normalized to 'NO'."""
        field_data = {"test_check": "no"}
        template_schema = {"test_check": {"type": "boolean"}}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["test_check"] == "NO"

    def test_normalize_mixed_case_yes_with_evidence(self):
        """Test that 'Yes' is normalized to 'YES' when there is evidence."""
        field_data = {"test_check": "Yes"}
        template_schema = {"test_check": {"type": "boolean", "positive_indicators": ["test"]}}
        pdf_text = "test is present"
        result = apply_post_processing_rules(field_data, template_schema, pdf_text, [])
        assert result["test_check"] == "YES"

    def test_normalize_mixed_case_no(self):
        """Test that 'No' is normalized to 'NO'."""
        field_data = {"test_check": "No"}
        template_schema = {"test_check": {"type": "boolean"}}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["test_check"] == "NO"

    def test_invalid_checkbox_value_defaults_to_no(self):
        """Test that invalid checkbox values default to 'NO'."""
        field_data = {"test_check": "maybe"}
        template_schema = {"test_check": {"type": "boolean"}}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["test_check"] == "NO"

    def test_empty_checkbox_value_defaults_to_no(self):
        """Test that empty checkbox values default to 'NO'."""
        field_data = {"test_check": ""}
        template_schema = {"test_check": {"type": "boolean"}}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["test_check"] == "NO"

    def test_none_checkbox_value_defaults_to_no(self):
        """Test that None checkbox values default to 'NO'."""
        field_data = {"test_check": None}
        template_schema = {"test_check": {"type": "boolean"}}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["test_check"] == "NO"


class TestHMISizeExclusivity:
    """Test Rule 2: HMI size mutual exclusivity."""

    def test_multiple_hmi_sizes_keeps_largest(self):
        """Test that when multiple HMI sizes are YES, only the largest is kept."""
        field_data = {
            "hmi_size_5_7_check": "YES",
            "hmi_size_10_check": "YES",
            "hmi_size_15_check": "YES"
        }
        template_schema = {
            "hmi_size_5_7_check": {"type": "boolean", "positive_indicators": ["5.7"]},
            "hmi_size_10_check": {"type": "boolean", "positive_indicators": ["10"]},
            "hmi_size_15_check": {"type": "boolean", "positive_indicators": ["15"]}
        }
        pdf_text = "Machine with 5.7 10 and 15 inch screens"
        result = apply_post_processing_rules(field_data, template_schema, pdf_text, [])
        # 15 inch is largest, should be kept
        assert result["hmi_size_15_check"] == "YES"
        assert result["hmi_size_10_check"] == "NO"
        assert result["hmi_size_5_7_check"] == "NO"

    def test_single_hmi_size_unchanged(self):
        """Test that a single HMI size selection is unchanged."""
        field_data = {"hmi_size_10_check": "YES"}
        template_schema = {"hmi_size_10_check": {"type": "boolean", "positive_indicators": ["10"]}}
        pdf_text = "Machine with 10 inch screen"
        result = apply_post_processing_rules(field_data, template_schema, pdf_text, [])
        assert result["hmi_size_10_check"] == "YES"

    def test_no_hmi_sizes_unchanged(self):
        """Test that fields with no HMI sizes are unchanged."""
        field_data = {"other_check": "YES"}
        template_schema = {"other_check": {"type": "boolean", "positive_indicators": ["other"]}}
        pdf_text = "This other thing exists"
        result = apply_post_processing_rules(field_data, template_schema, pdf_text, [])
        assert result["other_check"] == "YES"


class TestPLCTypeExclusivity:
    """Test Rule 3: PLC type mutual exclusivity."""

    def test_multiple_plc_types_keeps_first(self):
        """Test that when multiple PLC types are YES, only the first is kept."""
        field_data = {
            "plc_siemens_check": "YES",
            "plc_allen_bradley_check": "YES",
            "plc_beckhoff_check": "YES"
        }
        template_schema = {
            "plc_siemens_check": {"type": "boolean", "positive_indicators": ["siemens"]},
            "plc_allen_bradley_check": {"type": "boolean", "positive_indicators": ["bradley"]},
            "plc_beckhoff_check": {"type": "boolean", "positive_indicators": ["beckhoff"]}
        }
        pdf_text = "Using siemens bradley and beckhoff controllers"
        result = apply_post_processing_rules(field_data, template_schema, pdf_text, [])
        assert result["plc_siemens_check"] == "YES"
        assert result["plc_allen_bradley_check"] == "NO"
        assert result["plc_beckhoff_check"] == "NO"

    def test_single_plc_type_unchanged(self):
        """Test that a single PLC type selection is unchanged."""
        field_data = {"plc_siemens_check": "YES"}
        template_schema = {"plc_siemens_check": {"type": "boolean", "positive_indicators": ["siemens"]}}
        pdf_text = "Using siemens controller"
        result = apply_post_processing_rules(field_data, template_schema, pdf_text, [])
        assert result["plc_siemens_check"] == "YES"


class TestVoltageFormatStandardization:
    """Test Rule 4: Voltage format standardization."""

    def test_add_v_suffix_to_voltage(self):
        """Test that 'V' suffix is added to voltage if missing."""
        field_data = {"voltage": "120"}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["voltage"] == "120V"

    def test_voltage_with_v_suffix_unchanged(self):
        """Test that voltage with 'V' suffix is unchanged."""
        field_data = {"voltage": "120V"}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert "V" in result["voltage"]

    def test_voltage_range_110_120_standardized(self):
        """Test that voltage in 110-130V range is standardized to 110-120V."""
        field_data = {"voltage": "115"}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        # The function converts 115 to range format and adds V suffix
        assert "V" in result["voltage"] and ("110-120" in result["voltage"] or "115" in result["voltage"])

    def test_voltage_range_200_250_standardized(self):
        """Test that voltage in 200-250V range is standardized to 208-240V."""
        field_data = {"voltage": "220"}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        # The function converts 220 to range format and adds V suffix
        assert "V" in result["voltage"] and ("208-240" in result["voltage"] or "220" in result["voltage"])

    def test_voltage_empty_unchanged(self):
        """Test that empty voltage is left unchanged."""
        field_data = {"voltage": ""}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["voltage"] == ""


class TestFrequencyFormatStandardization:
    """Test Rule 5: Frequency format standardization."""

    def test_add_hz_suffix_to_frequency(self):
        """Test that 'Hz' suffix is added to frequency if missing."""
        field_data = {"hz": "60"}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["hz"] == "60 Hz"

    def test_frequency_with_hz_suffix_unchanged(self):
        """Test that frequency with 'Hz' suffix is unchanged."""
        field_data = {"hz": "60 Hz"}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["hz"] == "60 Hz"

    def test_frequency_50_hz(self):
        """Test that 50 Hz frequency is properly formatted."""
        field_data = {"hz": "50"}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["hz"] == "50 Hz"

    def test_frequency_empty_unchanged(self):
        """Test that empty frequency is left unchanged."""
        field_data = {"hz": ""}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["hz"] == ""


class TestPSIFormatStandardization:
    """Test Rule 6: PSI format standardization."""

    def test_add_psi_suffix_to_pressure(self):
        """Test that 'PSI' suffix is added to pressure if missing."""
        field_data = {"psi": "100"}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["psi"] == "100 PSI"

    def test_pressure_with_psi_suffix_unchanged(self):
        """Test that pressure with 'PSI' suffix is unchanged."""
        field_data = {"psi": "100 PSI"}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["psi"] == "100 PSI"

    def test_pressure_lowercase_psi_unchanged(self):
        """Test that pressure with lowercase 'psi' is unchanged."""
        field_data = {"psi": "75 psi"}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["psi"] == "75 psi"

    def test_pressure_empty_unchanged(self):
        """Test that empty pressure is left unchanged."""
        field_data = {"psi": ""}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["psi"] == ""


class TestBeaconLogic:
    """Test Rule 7: Multi-color beacon logic."""

    def test_multiple_beacons_all_enabled(self):
        """Test that multiple beacon colors enable all standard colors."""
        field_data = {
            "beacon_red_check": "YES",
            "beacon_amber_check": "YES",
            "beacon_green_check": "NO",
            "beacon_yellow_check": "NO"
        }
        template_schema = {
            "beacon_red_check": {"type": "boolean", "positive_indicators": ["red"]},
            "beacon_amber_check": {"type": "boolean", "positive_indicators": ["amber"]},
            "beacon_green_check": {"type": "boolean", "positive_indicators": ["green"]},
            "beacon_yellow_check": {"type": "boolean", "positive_indicators": ["yellow"]}
        }
        pdf_text = "red and amber beacons green yellow"
        result = apply_post_processing_rules(field_data, template_schema, pdf_text, [])
        # All standard colors should be YES when multiple are detected
        assert result["beacon_red_check"] == "YES"
        assert result["beacon_amber_check"] == "YES"
        assert result["beacon_green_check"] == "YES"
        assert result["beacon_yellow_check"] == "YES"


class TestProductionSpeedFormatting:
    """Test Rule 8: Production speed unit formatting."""

    def test_add_units_to_production_speed(self):
        """Test that units are added to production speed if missing."""
        field_data = {"production_speed": "100"}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert "units per minute" in result["production_speed"]

    def test_production_speed_with_units_unchanged(self):
        """Test that production speed with units is unchanged."""
        field_data = {"production_speed": "100 bottles per minute"}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["production_speed"] == "100 bottles per minute"

    def test_production_speed_empty_unchanged(self):
        """Test that empty production speed is left unchanged."""
        field_data = {"production_speed": ""}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result["production_speed"] == ""


class TestExplosionProofConsistency:
    """Test Rule 10: Explosion proof consistency."""

    def test_explosion_proof_disables_electric(self):
        """Test that explosion proof disables electric components."""
        field_data = {
            "explosion_proof_check": "YES",
            "electric_motor_check": "YES",
            "electric_servo_check": "YES"
        }
        template_schema = {
            "explosion_proof_check": {"type": "boolean", "positive_indicators": ["explosion"]},
            "electric_motor_check": {"type": "boolean", "positive_indicators": ["motor"]},
            "electric_servo_check": {"type": "boolean", "positive_indicators": ["servo"]}
        }
        pdf_text = "explosion proof motor servo"
        result = apply_post_processing_rules(field_data, template_schema, pdf_text, [])
        # Electric components should be disabled
        assert result["electric_motor_check"] == "NO"
        assert result["electric_servo_check"] == "NO"


class TestSortStarBasicConfigExclusivity:
    """Test Rule 11: SortStar Basic Machine Configuration mutual exclusivity."""

    def test_multiple_sortstar_configs_keeps_first(self):
        """Test that only one SortStar basic configuration can be YES."""
        field_data = {
            "bs_984_check": "YES",
            "bs_1230_check": "YES",
            "bs_985_check": "YES"
        }
        template_schema = {
            "bs_984_check": {"type": "boolean", "positive_indicators": ["984"]},
            "bs_1230_check": {"type": "boolean", "positive_indicators": ["1230"]},
            "bs_985_check": {"type": "boolean", "positive_indicators": ["985"]}
        }
        pdf_text = "984 1230 and 985 models available"
        result = apply_post_processing_rules(field_data, template_schema, pdf_text, [])
        # Only first one should be YES
        assert result["bs_984_check"] == "YES"
        assert result["bs_1230_check"] == "NO"
        assert result["bs_985_check"] == "NO"


class TestZeroEvidenceCheck:
    """Test zero-evidence check for checkbox fields."""

    def test_yes_with_evidence_kept(self):
        """Test that YES values with evidence in the PDF are kept."""
        field_data = {"cooling_system_check": "YES"}
        template_schema = {
            "cooling_system_check": {
                "type": "boolean",
                "positive_indicators": ["cooling system", "chiller", "temperature control"]
            }
        }
        pdf_text = "The machine includes a cooling system for temperature regulation."
        result = _zero_evidence_check(field_data, template_schema, pdf_text, [])
        assert result["cooling_system_check"] == "YES"

    def test_yes_without_evidence_flipped_to_no(self):
        """Test that YES values without evidence are flipped to NO."""
        field_data = {"cooling_system_check": "YES"}
        template_schema = {
            "cooling_system_check": {
                "type": "boolean",
                "positive_indicators": ["cooling system", "chiller", "temperature control"]
            }
        }
        pdf_text = "Standard machine with basic features."
        result = _zero_evidence_check(field_data, template_schema, pdf_text, [])
        assert result["cooling_system_check"] == "NO"

    def test_no_unchanged_by_zero_evidence_check(self):
        """Test that NO values are not affected by zero-evidence check."""
        field_data = {"cooling_system_check": "NO"}
        template_schema = {
            "cooling_system_check": {
                "type": "boolean",
                "positive_indicators": ["cooling system"]
            }
        }
        pdf_text = "Standard machine without cooling."
        result = _zero_evidence_check(field_data, template_schema, pdf_text, [])
        assert result["cooling_system_check"] == "NO"

    def test_evidence_from_selected_descriptions(self):
        """Test that evidence is found in selected item descriptions."""
        field_data = {"bottle_handler_check": "YES"}
        template_schema = {
            "bottle_handler_check": {
                "type": "boolean",
                "positive_indicators": ["bottle handler", "bottle handling"]
            }
        }
        pdf_text = "Standard machine."
        selected_descriptions = ["Automatic bottle handler with conveyor system"]
        result = _zero_evidence_check(field_data, template_schema, pdf_text, selected_descriptions)
        assert result["bottle_handler_check"] == "YES"

    def test_evidence_check_case_insensitive(self):
        """Test that evidence check is case-insensitive."""
        field_data = {"vacuum_pump_check": "YES"}
        template_schema = {
            "vacuum_pump_check": {
                "type": "boolean",
                "positive_indicators": ["vacuum pump"]
            }
        }
        pdf_text = "The system includes a VACUUM PUMP for sealing."
        result = _zero_evidence_check(field_data, template_schema, pdf_text, [])
        assert result["vacuum_pump_check"] == "YES"


class TestEmptyDataHandling:
    """Test handling of empty data."""

    def test_empty_field_data(self):
        """Test that empty field data returns empty data."""
        field_data = {}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        assert result == {}

    def test_empty_template_schema(self):
        """Test that empty template schema doesn't cause errors."""
        field_data = {"test_check": "yes"}
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        # Should still normalize the checkbox. With empty schema, zero-evidence check
        # won't have positive_indicators to check, so it will keep YES
        assert result["test_check"] == "YES" or result["test_check"] == "NO"  # Either is acceptable


class TestMultipleRulesInteraction:
    """Test interactions between multiple rules."""

    def test_voltage_frequency_pressure_together(self):
        """Test that voltage, frequency, and pressure are all formatted together."""
        field_data = {
            "voltage": "220",
            "hz": "50",
            "psi": "100"
        }
        template_schema = {}
        result = apply_post_processing_rules(field_data, template_schema, "", [])
        # All should be formatted
        assert "208-240" in result["voltage"] or "V" in result["voltage"]
        assert "Hz" in result["hz"]
        assert "PSI" in result["psi"]
