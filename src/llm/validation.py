"""
Field Validation and Dependency Checking Module

This module handles validation of extracted field values and checking of cross-field
dependencies. It ensures data consistency across related fields (e.g., voltage-frequency
relationships) and provides suggestions for potential issues.

Functions:
    - validate_field_dependencies: Validates and adjusts field values based on cross-field rules
    - validate_llm_response: Validates LLM response against expected schema
    - sanitize_extracted_fields: Coerces extracted data into schema-safe template values
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


def _resolve_schema_type(field_key: str, field_schema: Any) -> str:
    """Resolve field type from schema metadata with a safe fallback."""
    if isinstance(field_schema, dict):
        schema_type = str(field_schema.get("type", "")).strip().lower()
        if schema_type in {"boolean", "string"}:
            return schema_type
    return "boolean" if field_key.endswith("_check") else "string"


def _coerce_checkbox_value(value: Any) -> str | None:
    """Convert common truthy/falsey forms to YES/NO; return None when invalid."""
    if isinstance(value, bool):
        return "YES" if value else "NO"

    if isinstance(value, (int, float)):
        if value == 1:
            return "YES"
        if value == 0:
            return "NO"
        return None

    if not isinstance(value, str):
        return None

    normalized = value.strip().upper()
    if normalized in {"YES", "TRUE", "1", "CHECKED", "ON", "Y"}:
        return "YES"
    if normalized in {"NO", "FALSE", "0", "OFF", "N"}:
        return "NO"
    return None


def sanitize_extracted_fields(
    extracted_data: Dict[str, Any],
    expected_schema: Dict[str, Any],
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Coerces extracted values to a schema-safe payload for template filling.

    Rules:
    - Include every schema field (missing values default to NO/empty string)
    - Normalize boolean fields to YES/NO
    - Keep string fields as strings (numbers are converted to strings)
    - Drop unexpected fields

    Returns:
        Tuple of:
        - Sanitized field dictionary
        - Field-level notes describing corrections/rejections
    """
    sanitized: Dict[str, str] = {}
    notes: Dict[str, List[str]] = {}
    input_data = extracted_data or {}
    schema = expected_schema or {}

    if not schema:
        for field_key, raw_value in input_data.items():
            if field_key.endswith("_check"):
                coerced = _coerce_checkbox_value(raw_value)
                sanitized[field_key] = coerced if coerced is not None else "NO"
            elif raw_value is None or isinstance(raw_value, bool):
                sanitized[field_key] = ""
            else:
                sanitized[field_key] = str(raw_value)
        return sanitized, notes

    for field_key, field_schema in schema.items():
        field_type = _resolve_schema_type(field_key, field_schema)
        has_value = field_key in input_data
        raw_value = input_data.get(field_key)

        if field_type == "boolean":
            coerced = _coerce_checkbox_value(raw_value) if has_value else None
            if coerced is None:
                sanitized[field_key] = "NO"
                if has_value:
                    notes.setdefault(field_key, []).append(
                        f"Invalid boolean value '{raw_value}' defaulted to 'NO'"
                    )
                else:
                    notes.setdefault(field_key, []).append("Missing field defaulted to 'NO'")
            else:
                sanitized[field_key] = coerced
            continue

        # string field
        if not has_value or raw_value is None:
            sanitized[field_key] = ""
            if not has_value:
                notes.setdefault(field_key, []).append("Missing field defaulted to empty string")
            continue

        if isinstance(raw_value, str):
            sanitized[field_key] = raw_value
        elif isinstance(raw_value, bool):
            sanitized[field_key] = ""
            notes.setdefault(field_key, []).append(
                f"Invalid string value type '{type(raw_value).__name__}' defaulted to empty string"
            )
        elif isinstance(raw_value, (int, float)):
            sanitized[field_key] = str(raw_value)
            notes.setdefault(field_key, []).append(
                f"Numeric value coerced to string: {raw_value}"
            )
        else:
            sanitized[field_key] = ""
            notes.setdefault(field_key, []).append(
                f"Invalid string value type '{type(raw_value).__name__}' defaulted to empty string"
            )

    for field_key in input_data:
        if field_key not in schema:
            notes.setdefault(field_key, []).append("Unexpected field ignored")

    return sanitized, notes
