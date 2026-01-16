"""
Field Validation and Dependency Checking Module

This module handles validation of extracted field values and checking of cross-field
dependencies. It ensures data consistency across related fields (e.g., voltage-frequency
relationships) and provides suggestions for potential issues.

Functions:
    - validate_field_dependencies: Validates and adjusts field values based on cross-field rules
    - validate_llm_response: Validates LLM response against expected schema
"""

from typing import Dict, List, Any, Tuple
from .constants import FIELD_DEPENDENCIES


def validate_field_dependencies(
    extracted_data: Dict[str, str],
    confidence_scores: Dict[str, float]
) -> Tuple[Dict[str, str], Dict[str, float], List[Dict[str, Any]]]:
    """
    Validates and potentially adjusts field values based on cross-field dependencies.

    Args:
        extracted_data: Dictionary of extracted field values
        confidence_scores: Dictionary of confidence scores

    Returns:
        Tuple of:
        - Updated extracted data
        - Updated confidence scores
        - List of suggestions/warnings about field inconsistencies
    """
    suggestions = []
    updated_data = extracted_data.copy()
    updated_confidence = confidence_scores.copy()

    # Check voltage-frequency relationship
    voltage = extracted_data.get("voltage", "").upper()
    hz = extracted_data.get("hz", "")

    if voltage and not hz:
        # Suggest Hz based on voltage
        if any(v in voltage for v in ["480", "460", "440", "120", "110", "115"]):
            suggestions.append({
                "field": "hz",
                "current_value": hz,
                "suggested_value": "60 Hz",
                "reason": f"Based on voltage {voltage}, frequency should typically be 60 Hz (North American standard)",
                "type": "suggestion"
            })
        elif any(v in voltage for v in ["400", "380", "415", "230", "220", "240"]):
            suggestions.append({
                "field": "hz",
                "current_value": hz,
                "suggested_value": "50 Hz",
                "reason": f"Based on voltage {voltage}, frequency should typically be 50 Hz (European standard)",
                "type": "suggestion"
            })

    # Check Hz-Voltage consistency if both are filled
    if voltage and hz:
        hz_value = hz.replace("Hz", "").replace("hz", "").strip()
        is_consistent = True

        if hz_value == "60" and any(v in voltage for v in ["400", "380", "415"]):
            is_consistent = False
            suggestions.append({
                "field": "hz",
                "current_value": hz,
                "suggested_value": "50 Hz",
                "reason": f"Voltage {voltage} typically uses 50 Hz, not 60 Hz. Please verify.",
                "type": "warning"
            })
            updated_confidence["hz"] = min(updated_confidence.get("hz", 0.5), 0.4)

        if hz_value == "50" and any(v in voltage for v in ["480", "460", "440"]):
            is_consistent = False
            suggestions.append({
                "field": "hz",
                "current_value": hz,
                "suggested_value": "60 Hz",
                "reason": f"Voltage {voltage} typically uses 60 Hz, not 50 Hz. Please verify.",
                "type": "warning"
            })
            updated_confidence["hz"] = min(updated_confidence.get("hz", 0.5), 0.4)

    # Check PSI and CFM relationship
    psi = extracted_data.get("psi", "")
    cfm = extracted_data.get("cfm", "")

    if psi and not cfm:
        suggestions.append({
            "field": "cfm",
            "current_value": cfm,
            "suggested_value": None,
            "reason": "PSI is specified but CFM is missing. Consider checking pneumatic requirements.",
            "type": "info"
        })
        updated_confidence["cfm"] = min(updated_confidence.get("cfm", 0.5), 0.4)

    return updated_data, updated_confidence, suggestions


def validate_llm_response(response_data: Dict[str, Any], expected_schema: Dict[str, Dict]) -> Dict[str, List[str]]:
    """
    Validates the LLM response against the expected schema.

    Args:
        response_data: The LLM response data
        expected_schema: The template schema

    Returns:
        A dictionary of errors by field, empty if all valid
    """
    errors = {}

    # Check for missing fields
    for key, schema in expected_schema.items():
        if key not in response_data:
            if key not in errors:
                errors[key] = []
            errors[key].append("Missing field")
            continue

        value = response_data[key]

        # Validate by type
        if schema.get("type") == "boolean":
            if not isinstance(value, str) or value.upper() not in ["YES", "NO"]:
                if key not in errors:
                    errors[key] = []
                errors[key].append(f"Expected 'YES' or 'NO', got: {value}")
        elif schema.get("type") == "string":
            if not isinstance(value, str):
                if key not in errors:
                    errors[key] = []
                errors[key].append(f"Expected string, got: {type(value).__name__}")

    # Check for extra fields
    for key in response_data:
        if key not in expected_schema:
            if key not in errors:
                errors[key] = []
            errors[key].append("Unexpected field")

    return errors
