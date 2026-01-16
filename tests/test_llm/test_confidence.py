"""
Unit tests for the confidence module (src/llm/confidence.py).

This module tests:
- Confidence level categorization
- Field-level confidence estimation
- Overall extraction confidence
- Evidence-based confidence scoring
"""

import pytest
from src.llm.confidence import (
    get_confidence_level,
    estimate_field_confidence,
    estimate_extraction_confidence
)
from src.llm.constants import CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW


class TestGetConfidenceLevel:
    """Test confidence level categorization."""

    def test_high_confidence_threshold(self):
        """Test that scores >= CONFIDENCE_HIGH are categorized as 'high'."""
        assert get_confidence_level(CONFIDENCE_HIGH) == 'high'
        assert get_confidence_level(0.85) == 'high'
        assert get_confidence_level(0.95) == 'high'
        assert get_confidence_level(1.0) == 'high'

    def test_medium_confidence_threshold(self):
        """Test that scores >= CONFIDENCE_MEDIUM but < CONFIDENCE_HIGH are 'medium'."""
        assert get_confidence_level(CONFIDENCE_MEDIUM) == 'medium'
        assert get_confidence_level(0.65) == 'medium'
        assert get_confidence_level(CONFIDENCE_HIGH - 0.01) == 'medium'

    def test_low_confidence_threshold(self):
        """Test that scores < CONFIDENCE_MEDIUM are categorized as 'low'."""
        assert get_confidence_level(CONFIDENCE_LOW) == 'low'
        assert get_confidence_level(0.2) == 'low'
        assert get_confidence_level(CONFIDENCE_MEDIUM - 0.01) == 'low'
        assert get_confidence_level(0.0) == 'low'

    def test_boundary_values(self):
        """Test confidence level at exact boundary values."""
        # Just below high threshold
        assert get_confidence_level(CONFIDENCE_HIGH - 0.001) == 'medium'
        # Just above high threshold
        assert get_confidence_level(CONFIDENCE_HIGH + 0.001) == 'high'
        # Just below medium threshold
        assert get_confidence_level(CONFIDENCE_MEDIUM - 0.001) == 'low'
        # Just above medium threshold
        assert get_confidence_level(CONFIDENCE_MEDIUM + 0.001) == 'medium'


class TestEstimateFieldConfidenceEmpty:
    """Test confidence estimation for empty/null values."""

    def test_none_value_low_confidence(self):
        """Test that None values get low confidence (0.3)."""
        confidence = estimate_field_confidence(
            field_key="test_field",
            field_value=None,
            template_contexts={},
            full_pdf_text="Some text",
            selected_descriptions=[]
        )
        assert confidence == 0.3

    def test_empty_string_low_confidence(self):
        """Test that empty strings get low confidence (0.3)."""
        confidence = estimate_field_confidence(
            field_key="test_field",
            field_value="",
            template_contexts={},
            full_pdf_text="Some text",
            selected_descriptions=[]
        )
        assert confidence == 0.3


class TestEstimateFieldConfidenceCheckboxYES:
    """Test confidence estimation for checkbox YES values."""

    def test_yes_with_multiple_evidence(self):
        """Test that YES with 3+ evidence points gets very high confidence."""
        confidence = estimate_field_confidence(
            field_key="cooling_system_check",
            field_value="YES",
            template_contexts={
                "cooling_system_check": {
                    "positive_indicators": ["cooling system", "chiller", "temperature control"],
                    "synonyms": ["cooling"]
                }
            },
            full_pdf_text="The machine includes a cooling system with a chiller for temperature control.",
            selected_descriptions=[]
        )
        assert confidence >= 0.95

    def test_yes_with_good_evidence(self):
        """Test that YES with 2 evidence points gets high confidence."""
        confidence = estimate_field_confidence(
            field_key="cooling_system_check",
            field_value="YES",
            template_contexts={
                "cooling_system_check": {
                    "positive_indicators": ["cooling system", "chiller"],
                    "synonyms": []
                }
            },
            full_pdf_text="The machine includes a cooling system with a chiller.",
            selected_descriptions=[]
        )
        assert confidence >= 0.85

    def test_yes_with_some_evidence(self):
        """Test that YES with 1 evidence point gets medium confidence."""
        confidence = estimate_field_confidence(
            field_key="cooling_system_check",
            field_value="YES",
            template_contexts={
                "cooling_system_check": {
                    "positive_indicators": ["cooling system"],
                    "synonyms": []
                }
            },
            full_pdf_text="The machine includes a cooling system.",
            selected_descriptions=[]
        )
        assert confidence >= 0.7

    def test_yes_without_evidence(self):
        """Test that YES without evidence gets low confidence."""
        confidence = estimate_field_confidence(
            field_key="cooling_system_check",
            field_value="YES",
            template_contexts={
                "cooling_system_check": {
                    "positive_indicators": ["cooling system", "chiller"],
                    "synonyms": []
                }
            },
            full_pdf_text="The machine is a basic model.",
            selected_descriptions=[]
        )
        assert confidence < 0.5


class TestEstimateFieldConfidenceCheckboxNO:
    """Test confidence estimation for checkbox NO values."""

    def test_no_value_medium_confidence(self):
        """Test that NO values get medium-high confidence (0.75)."""
        confidence = estimate_field_confidence(
            field_key="cooling_system_check",
            field_value="NO",
            template_contexts={},
            full_pdf_text="Basic machine without cooling system.",
            selected_descriptions=[]
        )
        assert confidence == 0.75

    def test_no_is_default(self):
        """Test that NO is the default value and gets reasonable confidence."""
        confidence = estimate_field_confidence(
            field_key="optional_feature_check",
            field_value="NO",
            template_contexts={},
            full_pdf_text="Text without mention of optional feature",
            selected_descriptions=[]
        )
        assert confidence >= 0.7


class TestEstimateFieldConfidenceTextFields:
    """Test confidence estimation for text fields."""

    def test_text_found_in_pdf(self):
        """Test that text found exactly in PDF gets high confidence."""
        confidence = estimate_field_confidence(
            field_key="machine_model",
            field_value="Model X-100",
            template_contexts={},
            full_pdf_text="The system includes a Model X-100 manufacturing unit.",
            selected_descriptions=[]
        )
        assert confidence >= 0.9

    def test_text_not_found_in_pdf(self):
        """Test that text not found in PDF gets lower confidence."""
        confidence = estimate_field_confidence(
            field_key="machine_model",
            field_value="Model X-100",
            template_contexts={},
            full_pdf_text="This is a basic machine specification.",
            selected_descriptions=[]
        )
        assert confidence < 0.6

    def test_partial_match_in_pdf(self):
        """Test that partial match gets medium confidence."""
        confidence = estimate_field_confidence(
            field_key="machine_model",
            field_value="Model X-100",
            template_contexts={},
            full_pdf_text="The system includes a Model with advanced features.",
            selected_descriptions=[]
        )
        assert confidence >= 0.7

    def test_suspicious_placeholder_values(self):
        """Test that suspicious placeholder values get very low confidence."""
        suspicious_values = [
            "n/a", "not applicable", "not specified", "not selected",
            "none selected", "to be determined", "tbd", "pending",
            "not available", "unknown", "not provided"
        ]
        for value in suspicious_values:
            confidence = estimate_field_confidence(
                field_key="test_field",
                field_value=value,
                template_contexts={},
                full_pdf_text="Some text",
                selected_descriptions=[]
            )
            assert confidence <= 0.2, f"Suspicious value '{value}' should have low confidence"

    def test_text_field_with_evidence_from_descriptions(self):
        """Test that text field evidence can come from selected descriptions."""
        confidence = estimate_field_confidence(
            field_key="line_item_description",
            field_value="Automatic bottle handler",
            template_contexts={},
            full_pdf_text="Order details for machine components.",
            selected_descriptions=["Automatic bottle handler with conveyor system"]
        )
        assert confidence >= 0.9


class TestEstimateExtractionConfidence:
    """Test overall extraction confidence estimation."""

    def test_extraction_with_mixed_fields(self):
        """Test extraction confidence with a mix of high and low confidence fields."""
        extracted_data = {
            "machine": "Model X",
            "cooling_system_check": "YES",
            "voltage": "480V",
            "optional_feature_check": "NO"
        }
        template_contexts = {
            "machine": {},
            "cooling_system_check": {
                "positive_indicators": ["cooling system", "chiller"],
                "synonyms": []
            },
            "voltage": {},
            "optional_feature_check": {}
        }
        full_pdf_text = "Model X with cooling system and chiller. Voltage: 480V."
        machine_data = {
            "main_item": {"description": "Model X base unit"},
            "add_ons": [{"description": "Cooling system"}]
        }
        common_items = []

        confidence_scores = estimate_extraction_confidence(
            extracted_data=extracted_data,
            template_contexts=template_contexts,
            full_pdf_text=full_pdf_text,
            machine_data=machine_data,
            common_items=common_items
        )

        # Should have scores for all fields
        assert len(confidence_scores) == 4
        assert "machine" in confidence_scores
        assert "cooling_system_check" in confidence_scores
        assert "voltage" in confidence_scores
        assert "optional_feature_check" in confidence_scores

    def test_extraction_high_confidence_fields(self):
        """Test extraction where all fields have high confidence."""
        extracted_data = {
            "machine": "Model X",
            "customer": "Customer A"
        }
        template_contexts = {
            "machine": {},
            "customer": {}
        }
        full_pdf_text = "Model X order for Customer A"
        machine_data = {
            "main_item": {"description": "Model X base unit"},
            "add_ons": []
        }
        common_items = []

        confidence_scores = estimate_extraction_confidence(
            extracted_data=extracted_data,
            template_contexts=template_contexts,
            full_pdf_text=full_pdf_text,
            machine_data=machine_data,
            common_items=common_items
        )

        # Both fields should have high confidence
        assert confidence_scores["machine"] >= 0.9
        assert confidence_scores["customer"] >= 0.9

    def test_extraction_low_confidence_fields(self):
        """Test extraction where fields have low confidence."""
        extracted_data = {
            "rare_feature_check": "YES",
            "unknown_param": "some value"
        }
        template_contexts = {
            "rare_feature_check": {
                "positive_indicators": ["rare feature"],
                "synonyms": []
            },
            "unknown_param": {}
        }
        full_pdf_text = "Basic machine without the rare feature or unknown param."
        machine_data = {
            "main_item": {"description": "Basic unit"},
            "add_ons": []
        }
        common_items = []

        confidence_scores = estimate_extraction_confidence(
            extracted_data=extracted_data,
            template_contexts=template_contexts,
            full_pdf_text=full_pdf_text,
            machine_data=machine_data,
            common_items=common_items
        )

        # Fields without evidence should have lower confidence
        assert confidence_scores["rare_feature_check"] < 0.5
        assert confidence_scores["unknown_param"] < 0.6

    def test_extraction_with_addon_evidence(self):
        """Test that evidence from add-ons is considered."""
        extracted_data = {
            "pneumatic_valve_check": "YES"
        }
        template_contexts = {
            "pneumatic_valve_check": {
                "positive_indicators": ["pneumatic valve"],
                "synonyms": ["pneumatic"]
            }
        }
        full_pdf_text = "Main unit specification."
        machine_data = {
            "main_item": {"description": "Main unit"},
            "add_ons": [{"description": "Pneumatic valve kit"}]
        }
        common_items = []

        confidence_scores = estimate_extraction_confidence(
            extracted_data=extracted_data,
            template_contexts=template_contexts,
            full_pdf_text=full_pdf_text,
            machine_data=machine_data,
            common_items=common_items
        )

        # Should find evidence in add-on description
        assert confidence_scores["pneumatic_valve_check"] >= 0.9

    def test_extraction_with_common_items_evidence(self):
        """Test that evidence from common items is considered."""
        extracted_data = {
            "label_printer_check": "YES"
        }
        template_contexts = {
            "label_printer_check": {
                "positive_indicators": ["label printer"],
                "synonyms": ["printer"]
            }
        }
        full_pdf_text = "Main unit without label printer."
        machine_data = {
            "main_item": {"description": "Main unit"},
            "add_ons": []
        }
        common_items = [
            {"description": "Thermal label printer"}
        ]

        confidence_scores = estimate_extraction_confidence(
            extracted_data=extracted_data,
            template_contexts=template_contexts,
            full_pdf_text=full_pdf_text,
            machine_data=machine_data,
            common_items=common_items
        )

        # Should find evidence in common items
        assert confidence_scores["label_printer_check"] >= 0.9

    def test_empty_extracted_data(self):
        """Test extraction confidence with no extracted data."""
        extracted_data = {}
        template_contexts = {}
        full_pdf_text = "Some text"
        machine_data = {
            "main_item": {"description": "Unit"},
            "add_ons": []
        }
        common_items = []

        confidence_scores = estimate_extraction_confidence(
            extracted_data=extracted_data,
            template_contexts=template_contexts,
            full_pdf_text=full_pdf_text,
            machine_data=machine_data,
            common_items=common_items
        )

        assert confidence_scores == {}

    def test_scores_are_normalized_0_to_1(self):
        """Test that all confidence scores are between 0.0 and 1.0."""
        extracted_data = {
            "field1": "YES",
            "field2": "text value",
            "field3": "NO"
        }
        template_contexts = {
            "field1": {"positive_indicators": ["field1"]},
            "field2": {},
            "field3": {}
        }
        full_pdf_text = "Some text"
        machine_data = {
            "main_item": {"description": "Unit"},
            "add_ons": []
        }
        common_items = []

        confidence_scores = estimate_extraction_confidence(
            extracted_data=extracted_data,
            template_contexts=template_contexts,
            full_pdf_text=full_pdf_text,
            machine_data=machine_data,
            common_items=common_items
        )

        # All scores should be between 0 and 1
        for score in confidence_scores.values():
            assert 0.0 <= score <= 1.0


class TestConfidenceEdgeCases:
    """Test edge cases in confidence estimation."""

    def test_field_with_context_as_string(self):
        """Test field context that is a string instead of dict."""
        confidence = estimate_field_confidence(
            field_key="test_field",
            field_value="value",
            template_contexts={
                "test_field": "This is a description string"
            },
            full_pdf_text="Some text",
            selected_descriptions=[]
        )
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_checkbox_field_name_inference(self):
        """Test that checkbox status is inferred from field name."""
        # Field ending in _check
        confidence = estimate_field_confidence(
            field_key="option_check",
            field_value="YES",
            template_contexts={},
            full_pdf_text="Random text without option",
            selected_descriptions=[]
        )
        # Should be treated as checkbox with no evidence
        assert confidence < 0.5

    def test_case_insensitive_evidence_matching(self):
        """Test that evidence matching is case-insensitive."""
        confidence = estimate_field_confidence(
            field_key="cooling_system_check",
            field_value="YES",
            template_contexts={
                "cooling_system_check": {
                    "positive_indicators": ["cooling system"],
                    "synonyms": []
                }
            },
            full_pdf_text="The machine has a COOLING SYSTEM for temperature control.",
            selected_descriptions=[]
        )
        assert confidence >= 0.9

    def test_multipart_field_name_inference(self):
        """Test evidence inference from multi-part field names."""
        confidence = estimate_field_confidence(
            field_key="pneumatic_valve_check",
            field_value="YES",
            template_contexts={
                "pneumatic_valve_check": {
                    "positive_indicators": [],
                    "synonyms": []
                }
            },
            full_pdf_text="System with pneumatic and valve components.",
            selected_descriptions=[]
        )
        # Should find evidence from field name parts
        assert confidence >= 0.7

    def test_very_long_pdf_text(self):
        """Test handling of very long PDF text."""
        long_text = "Some content. " * 1000  # Very long text
        confidence = estimate_field_confidence(
            field_key="feature_check",
            field_value="YES",
            template_contexts={
                "feature_check": {
                    "positive_indicators": ["feature"],
                    "synonyms": []
                }
            },
            full_pdf_text=long_text,
            selected_descriptions=[]
        )
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_special_characters_in_text(self):
        """Test handling of special characters in field values and text."""
        confidence = estimate_field_confidence(
            field_key="model_field",
            field_value="Model X-100/R2",
            template_contexts={},
            full_pdf_text="Order for Model X-100/R2 unit with special chars.",
            selected_descriptions=[]
        )
        assert confidence >= 0.9

    def test_numeric_string_field(self):
        """Test confidence for numeric string values."""
        confidence = estimate_field_confidence(
            field_key="serial_number",
            field_value="SN12345",
            template_contexts={},
            full_pdf_text="Serial number: SN12345",
            selected_descriptions=[]
        )
        assert confidence >= 0.9

    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is handled correctly."""
        confidence = estimate_field_confidence(
            field_key="model",
            field_value="  Model X  ",
            template_contexts={},
            full_pdf_text="Model X specification",
            selected_descriptions=[]
        )
        # Should strip whitespace and find match
        assert confidence >= 0.9
