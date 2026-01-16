"""
Confidence Estimation Module

This module handles confidence estimation for LLM field extractions from PDF documents.
It provides functions to assess the reliability of extracted values based on evidence
found in source documents, field types, and contextual information.

Confidence scores range from 0.0 (no confidence) to 1.0 (high confidence) and help
identify fields that may require manual review.
"""

from typing import Dict, List, Any, Optional
from .constants import CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW


def get_confidence_level(confidence: float) -> str:
    """
    Returns the confidence level category based on score.

    Args:
        confidence: Float between 0.0 and 1.0

    Returns:
        str: 'high', 'medium', or 'low'
    """
    if confidence >= CONFIDENCE_HIGH:
        return 'high'
    elif confidence >= CONFIDENCE_MEDIUM:
        return 'medium'
    else:
        return 'low'


def estimate_field_confidence(
    field_key: str,
    field_value: Any,
    template_contexts: Dict[str, Any],
    full_pdf_text: str,
    selected_descriptions: List[str]
) -> float:
    """
    Estimates confidence score for a single extracted field based on evidence quality.

    Args:
        field_key: The field key
        field_value: The extracted value
        template_contexts: Template field context/schema
        full_pdf_text: Full PDF text for evidence checking
        selected_descriptions: List of selected item descriptions

    Returns:
        float: Confidence score between 0.0 and 1.0
    """
    # Base confidence
    confidence = 0.5

    # Get field context if available
    field_context = template_contexts.get(field_key, {})
    if isinstance(field_context, str):
        field_context = {"description": field_context}

    # Empty or None values get low confidence (they are defaults)
    if field_value is None or field_value == "":
        return 0.3  # Low confidence - we just defaulted to empty

    # Combine all text for evidence search
    all_text = (full_pdf_text + " " + " ".join(selected_descriptions)).lower()

    # Check for checkbox fields
    is_checkbox = field_key.endswith("_check")

    if is_checkbox:
        if str(field_value).upper() == "YES":
            # For YES values, check if we have evidence
            positive_indicators = field_context.get("positive_indicators", [])
            synonyms = field_context.get("synonyms", [])
            evidence_terms = positive_indicators + synonyms

            # Also check field name parts as potential evidence
            field_parts = field_key.replace("_check", "").replace("_", " ").split()
            evidence_terms.extend([p.lower() for p in field_parts if len(p) > 2])

            # Count how many evidence terms are found
            evidence_found = sum(1 for term in evidence_terms if term.lower() in all_text)

            if evidence_found >= 3:
                confidence = 0.95  # Very high - multiple evidence points
            elif evidence_found >= 2:
                confidence = 0.85  # High - good evidence
            elif evidence_found >= 1:
                confidence = 0.7   # Medium-high - some evidence
            else:
                confidence = 0.4   # Low - no direct evidence for YES
        else:
            # NO is the default, usually more confident if we found nothing
            confidence = 0.75
    else:
        # Text field - check if value appears in the text
        value_lower = str(field_value).lower().strip()

        # Check for suspicious placeholder values
        suspicious_phrases = [
            "n/a", "not applicable", "not specified", "not selected",
            "none selected", "to be determined", "tbd", "pending",
            "not available", "unknown", "not provided"
        ]

        if value_lower in suspicious_phrases:
            confidence = 0.2  # Very low - suspicious value

        elif value_lower in all_text:
            # Exact match found in text
            confidence = 0.9
        elif any(word in all_text for word in value_lower.split() if len(word) > 3):
            # Partial match found
            confidence = 0.7
        else:
            # Value not found in text - might be inferred
            confidence = 0.5

    return round(confidence, 2)


def estimate_extraction_confidence(
    extracted_data: Dict[str, str],
    template_contexts: Dict[str, Any],
    full_pdf_text: str,
    machine_data: Dict,
    common_items: List[Dict]
) -> Dict[str, float]:
    """
    Estimates confidence scores for all extracted fields.

    Args:
        extracted_data: Dictionary of extracted field values
        template_contexts: Template field contexts/schema
        full_pdf_text: Full PDF text
        machine_data: Machine data with main item and add-ons
        common_items: List of common items

    Returns:
        Dict[str, float]: Dictionary mapping field keys to confidence scores (0.0-1.0)
    """
    # Build selected descriptions list
    selected_descriptions = []

    main_item_desc = machine_data.get("main_item", {}).get("description", "")
    if main_item_desc:
        selected_descriptions.append(main_item_desc)

    for addon in machine_data.get("add_ons", []):
        desc = addon.get("description", "")
        if desc:
            selected_descriptions.append(desc)

    for common in common_items:
        desc = common.get("description", "")
        if desc:
            selected_descriptions.append(desc)

    # Estimate confidence for each field
    confidence_scores = {}

    for field_key, field_value in extracted_data.items():
        confidence = estimate_field_confidence(
            field_key=field_key,
            field_value=field_value,
            template_contexts=template_contexts,
            full_pdf_text=full_pdf_text,
            selected_descriptions=selected_descriptions
        )
        confidence_scores[field_key] = confidence

    print(f"Estimated confidence for {len(confidence_scores)} fields")

    # Log summary statistics
    high_conf = sum(1 for c in confidence_scores.values() if c >= CONFIDENCE_HIGH)
    med_conf = sum(1 for c in confidence_scores.values() if CONFIDENCE_MEDIUM <= c < CONFIDENCE_HIGH)
    low_conf = sum(1 for c in confidence_scores.values() if c < CONFIDENCE_MEDIUM)

    print(f"  High confidence: {high_conf} fields")
    print(f"  Medium confidence: {med_conf} fields")
    print(f"  Low confidence (needs review): {low_conf} fields")

    return confidence_scores
