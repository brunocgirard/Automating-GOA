"""
Confidence Estimation Module

This module handles confidence estimation for LLM field extractions from PDF documents.
It provides functions to assess the reliability of extracted values based on evidence
found in source documents, field types, and contextual information.

Confidence scores range from 0.0 (no confidence) to 1.0 (high confidence) and help
identify fields that may require manual review.
"""

import re
from typing import Dict, List, Any
from .constants import CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW


_UNIT_SYNONYMS: dict[str, str] = {
    "volt": "v", "volts": "v",
    "hertz": "hz",
    "millimeter": "mm", "millimeters": "mm", "millimetre": "mm", "millimetres": "mm",
    "centimeter": "cm", "centimeters": "cm", "centimetre": "cm", "centimetres": "cm",
    "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "inch": "in", "inches": "in",
    "pound": "lb", "pounds": "lb", "lbs": "lb",
    "kilogram": "kg", "kilograms": "kg",
    "gram": "g", "grams": "g",
    "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "gallon": "gal", "gallons": "gal",
    "minute": "min", "minutes": "min",
    "second": "sec", "seconds": "sec",
    "bottle": "btl", "bottles": "btl",
}


def _normalize_units(text: str) -> str:
    """Collapse common unit name variants to canonical abbreviations."""
    def _replace_unit(match: re.Match) -> str:
        word = match.group(0).lower()
        return _UNIT_SYNONYMS.get(word, word)

    pattern = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in _UNIT_SYNONYMS) + r")\b",
        re.IGNORECASE,
    )
    return pattern.sub(_replace_unit, text)


def _normalize_for_match(text: Any) -> str:
    raw = _normalize_units(str(text or "").lower())
    normalized = re.sub(r"[^a-z0-9]+", " ", raw)
    return re.sub(r"\s+", " ", normalized).strip()


def _token_overlap_ratio(needle: str, haystack_tokens: set[str]) -> float:
    tokens = [token for token in _normalize_for_match(needle).split() if len(token) > 2]
    if not tokens:
        return 0.0
    overlap = sum(1 for token in tokens if token in haystack_tokens)
    return overlap / len(tokens)


def _is_negated_mention(term: str, all_text: str) -> bool:
    term_norm = _normalize_for_match(term)
    if not term_norm:
        return False
    escaped_term = re.escape(term_norm)
    negation_patterns = (
        rf"\b(?:no|without|excluding|exclude|lacking|minus)\b(?:\s+\w+){{0,3}}\s+{escaped_term}\b",
        rf"\b{escaped_term}\b(?:\s+\w+){{0,3}}\s+\b(?:excluded|omitted|absent|not\s+included)\b",
    )
    return any(re.search(pattern, all_text) for pattern in negation_patterns)


def _term_in_text_fuzzy(term: str, raw_text: str, normalized_text: str, normalized_tokens: set[str]) -> bool:
    term_raw = str(term or "").strip().lower()
    if not term_raw:
        return False

    # Fast exact/normalized checks first.
    if term_raw in raw_text:
        return True

    term_norm = _normalize_for_match(term_raw)
    if not term_norm:
        return False
    if term_norm in normalized_text:
        return True

    overlap_ratio = _token_overlap_ratio(term_norm, normalized_tokens)
    if overlap_ratio >= 0.8:
        return True

    # Mild stemming-style fallback to catch singular/plural or minor punctuation drift.
    term_tokens = [token for token in term_norm.split() if len(token) > 4]
    if len(term_tokens) == 1:
        token = term_tokens[0]
        stem = token[:-1] if len(token) > 5 else token
        return any(candidate.startswith(stem) for candidate in normalized_tokens if len(candidate) >= 4)

    return False


def _resolve_semantic_tag(field_key: str, field_context: Dict[str, Any]) -> str:
    explicit = str(field_context.get("semantic_tag", "")).strip().lower()
    if explicit:
        return explicit

    description = str(field_context.get("description", "")).strip().lower()
    section = str(field_context.get("section", "")).strip().lower()
    if "direction" in description and "basic information" in section:
        return "direction"
    if "utility specifications" in section:
        if "voltage" in description:
            return "voltage"
        if "hz" in description or "hertz" in description:
            return "hz"
        if "phase" in description:
            return "phases"
    return ""


def _matches_semantic_value(tag: str, value: str) -> bool:
    value_norm = str(value or "").strip().lower()
    if not value_norm:
        return False

    if tag == "direction":
        return bool(
            re.search(r"\b(from\s+)?left\s+to\s+right\b", value_norm)
            or re.search(r"\b(from\s+)?right\s+to\s+left\b", value_norm)
        )
    if tag == "voltage":
        return bool(re.search(r"\b\d{2,4}(?:\s*/\s*\d{2,4})?\s*(?:v|vac|volt|volts)\b", value_norm))
    if tag == "hz":
        return bool(re.search(r"\b\d{2,3}(?:\s*/\s*\d{2,3})?\s*(?:hz|hertz)\b", value_norm))
    if tag == "phases":
        return bool(re.search(r"\b[123]\s*(?:phase|phases)\b", value_norm))
    return True


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

    pdf_text = str(full_pdf_text or "").lower()
    selected_text = " ".join(str(desc or "") for desc in selected_descriptions).lower()

    # Combine all text for evidence search
    all_text = f"{pdf_text} {selected_text}".strip()
    normalized_all_text = _normalize_for_match(all_text)
    normalized_tokens = set(normalized_all_text.split())
    normalized_pdf_text = _normalize_for_match(pdf_text)
    normalized_selected_text = _normalize_for_match(selected_text)
    selected_tokens = set(normalized_selected_text.split())
    pdf_tokens = set(normalized_pdf_text.split())

    # Check for checkbox fields
    is_checkbox = field_key.endswith("_check")

    if is_checkbox:
        if str(field_value).upper() == "YES":
            # For YES values, check if we have evidence
            positive_indicators = field_context.get("positive_indicators", [])
            synonyms = field_context.get("synonyms", [])
            evidence_terms = [str(term) for term in (positive_indicators + synonyms) if str(term).strip()]

            # Also check field name parts as potential evidence
            field_parts = field_key.replace("_check", "").replace("_", " ").split()
            evidence_terms.extend([p.lower() for p in field_parts if len(p) > 2])
            evidence_terms = list(dict.fromkeys(evidence_terms))

            # Count how many evidence terms are found
            evidence_found = 0
            for term in evidence_terms:
                found_in_selected = _term_in_text_fuzzy(
                    term,
                    selected_text,
                    normalized_selected_text,
                    selected_tokens,
                )
                found_in_pdf = _term_in_text_fuzzy(
                    term,
                    pdf_text,
                    normalized_pdf_text,
                    pdf_tokens,
                )
                if not found_in_selected and _is_negated_mention(term, normalized_pdf_text):
                    continue
                if found_in_selected or found_in_pdf:
                    evidence_found += 1

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
        elif _normalize_for_match(value_lower) in normalized_all_text:
            # Match found after punctuation/spacing normalization.
            confidence = 0.85
        elif any(word in all_text for word in value_lower.split() if len(word) > 3):
            # Partial exact token match found
            confidence = 0.7
        else:
            overlap_ratio = _token_overlap_ratio(value_lower, normalized_tokens)
            if overlap_ratio >= 0.8:
                confidence = 0.8
            elif overlap_ratio >= 0.5:
                confidence = 0.65
            else:
                # Value not found in text - might be inferred
                confidence = 0.5

        semantic_tag = _resolve_semantic_tag(field_key, field_context if isinstance(field_context, dict) else {})
        if semantic_tag:
            if not _matches_semantic_value(semantic_tag, value_lower):
                confidence = min(confidence, 0.45)
            elif _normalize_for_match(value_lower) not in normalized_all_text:
                # Constrained values that are not found in evidence should not remain high.
                confidence = min(confidence, 0.65)

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
