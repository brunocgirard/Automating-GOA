"""
LLM Integration Module for GOA Document Assistant.

This module provides a comprehensive interface for LLM-based document processing,
field extraction, validation, and question answering using Google's Gemini API.

Architecture:
    The module is organized into focused submodules:
    - client: Gemini API client configuration and model access
    - constants: Shared constants, confidence levels, field metadata
    - confidence: Confidence estimation for extracted fields
    - validation: Field dependency and response validation
    - post_processing: Post-extraction field normalization and cleanup
    - extraction: Core LLM extraction functions for GOA documents
    - qa: Question-answering over PDF documents

Usage:
    Basic setup:
        >>> from src.llm import configure_gemini_client
        >>> configure_gemini_client()

    Extract fields from a machine:
        >>> from src.llm import get_machine_specific_fields_via_llm
        >>> fields = get_machine_specific_fields_via_llm(
        ...     machine_data, common_items, template_contexts, pdf_text
        ... )

    Extract with confidence scores:
        >>> from src.llm import get_machine_specific_fields_with_confidence
        >>> result = get_machine_specific_fields_with_confidence(
        ...     machine_data, common_items, template_contexts, pdf_text
        ... )
        >>> fields = result['fields']
        >>> confidence = result['confidence']

    Answer questions about PDF:
        >>> from src.llm import answer_pdf_question
        >>> answer = answer_pdf_question(pdf_text, "What is the delivery date?")

Integration Points:
    - Pipeline 1 (PDF → Database): Uses extraction functions to parse PDF data
    - Pipeline 2 (GOA Generation): Core field extraction with validation
    - Pipeline 3 (Few-Shot Learning): Confidence scoring for example selection

Key Features:
    - Type-safe Pydantic model generation from Excel schemas
    - Semantic few-shot example retrieval via ChromaDB
    - Confidence scoring for extracted fields
    - Field dependency validation
    - Post-processing rules for data normalization
    - Context-aware Q&A over PDF documents

Model Configuration:
    - Provider: Google Gemini
    - Model: gemini-2.5-flash-lite (default)
    - Frameworks: google.generativeai + langchain_google_genai
    - Output: Structured JSON via PydanticOutputParser

Modification Guidelines:
    1. Client changes: Update .client module for API configuration
    2. New fields: Add to constants.py field metadata
    3. Validation rules: Extend .validation module
    4. Post-processing: Add rules to .post_processing module
    5. Extraction logic: Modify .extraction module functions

See Also:
    - CLAUDE.md: Complete application architecture
    - templates/GOA_template.xlsx: Field schema source of truth
    - src/utils/few_shot_enhanced.py: Few-shot learning integration
"""

# Client configuration and model access
from .client import (
    configure_gemini_client,
    check_model_usage,
    get_generative_model,
    GENERATIVE_MODEL,
    genai,
)

# Constants and field metadata
from .constants import (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
    FieldWithConfidence,
    FIELD_DEPENDENCIES,
    FIELD_GROUPS,
)

# Confidence estimation
from .confidence import (
    get_confidence_level,
    estimate_field_confidence,
    estimate_extraction_confidence,
)

# Validation
from .validation import (
    validate_field_dependencies,
    validate_llm_response,
)

# Post-processing
from .post_processing import (
    apply_post_processing_rules,
)

# Extraction
from .extraction import (
    get_all_fields_via_llm,
    get_llm_chat_update,
    map_crm_to_document_via_llm,
    get_machine_specific_fields_via_llm,
    get_machine_specific_fields_with_confidence,
)

# Question answering
from .qa import (
    answer_pdf_question,
)

# Public API - organized by category
__all__ = [
    # Client configuration and model access
    "configure_gemini_client",
    "check_model_usage",
    "get_generative_model",
    "GENERATIVE_MODEL",
    "genai",

    # Constants and field metadata
    "CONFIDENCE_HIGH",
    "CONFIDENCE_MEDIUM",
    "CONFIDENCE_LOW",
    "FieldWithConfidence",
    "FIELD_DEPENDENCIES",
    "FIELD_GROUPS",

    # Confidence estimation
    "get_confidence_level",
    "estimate_field_confidence",
    "estimate_extraction_confidence",

    # Validation
    "validate_field_dependencies",
    "validate_llm_response",

    # Post-processing
    "apply_post_processing_rules",

    # Extraction (core functions)
    "get_all_fields_via_llm",
    "get_llm_chat_update",
    "map_crm_to_document_via_llm",
    "get_machine_specific_fields_via_llm",
    "get_machine_specific_fields_with_confidence",

    # Question answering
    "answer_pdf_question",
]
