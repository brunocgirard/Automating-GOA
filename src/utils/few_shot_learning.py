"""
Few-Shot Learning Module for GOA Document Generation

This module provides functionality to enhance LLM prompts with high-quality examples
from previous successful extractions, improving accuracy over time.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from src.utils.db.few_shot import (
    save_few_shot_example, get_few_shot_examples, get_similar_examples,
    add_few_shot_feedback
)

def determine_machine_type(machine_name: str) -> str:
    """
    Determines the machine type based on the machine name.
    
    Args:
        machine_name: Name of the machine
    
    Returns:
        str: Machine type category
    """
    machine_name_lower = machine_name.lower()
    
    if any(keyword in machine_name_lower for keyword in ["sortstar", "unscrambler", "bottle unscrambler"]):
        return "sortstar"
    elif any(keyword in machine_name_lower for keyword in ["label", "labeling", "labelstar"]):
        return "labeling"
    elif any(keyword in machine_name_lower for keyword in ["fill", "filler", "filling"]):
        return "filling"
    elif any(keyword in machine_name_lower for keyword in ["cap", "capper", "capping"]):
        return "capping"
    else:
        return "general"

def extract_field_context_for_example(field_name: str, machine_data: Dict, 
                                    common_items: List[Dict], full_pdf_text: str) -> str:
    """
    Extracts relevant context for a specific field to create training examples.
    
    Args:
        field_name: Name of the field being extracted
        machine_data: Machine data dictionary
        common_items: List of common items
        full_pdf_text: Full PDF text
    
    Returns:
        str: Relevant context for the field
    """
    # Start with machine-specific context
    context_parts = []
    
    # Add main item description
    main_item = machine_data.get("main_item", {})
    if main_item.get("description"):
        context_parts.append(f"Main Item: {main_item['description']}")
    
    # Add add-on descriptions
    add_ons = machine_data.get("add_ons", [])
    if add_ons:
        context_parts.append("Add-ons:")
        for i, addon in enumerate(add_ons[:5]):  # Limit to first 5 add-ons
            if addon.get("description"):
                context_parts.append(f"  - {addon['description']}")
    
    # Add relevant common items (limit to avoid too much context)
    if common_items:
        context_parts.append("Common Items:")
        for i, item in enumerate(common_items[:3]):  # Limit to first 3 common items
            if item.get("description"):
                context_parts.append(f"  - {item['description']}")
    
    # Add relevant portion of PDF text (first 2000 chars for context)
    if full_pdf_text:
        pdf_context = full_pdf_text[:2000]
        context_parts.append(f"PDF Context: {pdf_context}")
    
    return "\n".join(context_parts)

def create_few_shot_examples_for_field(field_name: str, machine_type: str, 
                                     template_type: str, limit: int = 2) -> List[Dict]:
    """
    Retrieves few-shot examples for a specific field.
    
    Args:
        field_name: Name of the field
        machine_type: Type of machine
        template_type: Type of template
        limit: Maximum number of examples to retrieve
    
    Returns:
        List of example dictionaries
    """
    examples = get_few_shot_examples(machine_type, template_type, field_name, limit)
    return examples

def format_few_shot_examples_for_prompt(examples: List[Dict], field_name: str) -> str:
    """
    Formats few-shot examples for inclusion in LLM prompts.
    
    Args:
        examples: List of example dictionaries
        field_name: Name of the field these examples are for
    
    Returns:
        str: Formatted examples for the prompt
    """
    if not examples:
        return ""
    
    formatted_examples = [f"EXAMPLES FOR {field_name.upper()}:"]
    
    for i, example in enumerate(examples, 1):
        input_context = example.get("input_context", "")
        expected_output = example.get("expected_output", "")
        
        # Truncate context if too long
        if len(input_context) > 500:
            input_context = input_context[:500] + "..."
        
        formatted_examples.append(f"Example {i}:")
        formatted_examples.append(f"Input: {input_context}")
        formatted_examples.append(f"Expected Output: {expected_output}")
        formatted_examples.append("")  # Empty line for readability
    
    return "\n".join(formatted_examples)

def save_successful_extraction_as_example(field_name: str, field_value: str,
                                        machine_data: Dict, common_items: List[Dict],
                                        full_pdf_text: str, machine_type: str,
                                        template_type: str, source_machine_id: Optional[int] = None,
                                        confidence_score: float = 1.0) -> bool:
    """
    Saves a successful field extraction as a few-shot example.
    
    Args:
        field_name: Name of the field
        field_value: Successfully extracted value
        machine_data: Machine data dictionary
        common_items: List of common items
        full_pdf_text: Full PDF text
        machine_type: Type of machine
        template_type: Type of template
        source_machine_id: ID of the source machine
        confidence_score: Confidence in this example
    
    Returns:
        bool: True if saved successfully
    """
    # Extract relevant context for this field
    input_context = extract_field_context_for_example(
        field_name, machine_data, common_items, full_pdf_text
    )
    
    # Save the example
    return save_few_shot_example(
        machine_type=machine_type,
        template_type=template_type,
        field_name=field_name,
        input_context=input_context,
        expected_output=field_value,
        source_machine_id=source_machine_id,
        confidence_score=confidence_score
    )

def enhance_prompt_with_few_shot_examples(prompt_parts: List[str], 
                                        machine_data: Dict,
                                        template_placeholder_contexts: Dict[str, str],
                                        common_items: List[Dict],
                                        full_pdf_text: str,
                                        max_examples_per_field: int = 2) -> List[str]:
    """
    Enhances LLM prompts with few-shot examples for better field extraction.
    
    Args:
        prompt_parts: Existing prompt parts
        machine_data: Machine data dictionary
        template_placeholder_contexts: Template field contexts
        common_items: List of common items
        full_pdf_text: Full PDF text
        max_examples_per_field: Maximum examples per field
    
    Returns:
        List of enhanced prompt parts
    """
    machine_name = machine_data.get("machine_name", "")
    machine_type = determine_machine_type(machine_name)
    
    # Determine template type
    template_type = "sortstar" if "sortstar" in machine_type else "default"
    
    # Get few-shot examples for key fields
    # Note: Limit removed to support Divide and Conquer strategy where contexts are already grouped/limited
    key_fields = list(template_placeholder_contexts.keys())
    
    few_shot_section = ["\nFEW-SHOT EXAMPLES FROM PREVIOUS SUCCESSFUL EXTRACTIONS:"]
    
    for field_name in key_fields:
        examples = create_few_shot_examples_for_field(
            field_name, machine_type, template_type, max_examples_per_field
        )
        
        if examples:
            formatted_examples = format_few_shot_examples_for_prompt(examples, field_name)
            few_shot_section.append(formatted_examples)
    
    if len(few_shot_section) > 1:  # More than just the header
        # Insert few-shot examples before the final instruction
        prompt_parts.extend(few_shot_section)
        prompt_parts.append("\nBased on the above examples, extract the field values for the current machine.")
    
    return prompt_parts

def record_user_feedback_on_extraction(field_name: str, original_value: str,
                                     corrected_value: str, feedback_type: str,
                                     machine_type: str, template_type: str,
                                     user_context: str = None) -> bool:
    """
    Records user feedback on a field extraction to improve future performance.
    
    Args:
        field_name: Name of the field
        original_value: Original LLM prediction
        corrected_value: User's correction
        feedback_type: Type of feedback ("correction", "confirmation", "rejection")
        machine_type: Type of machine
        template_type: Type of template
        user_context: Additional context from user
    
    Returns:
        bool: True if feedback recorded successfully
    """
    # Find the most relevant example that might have influenced this prediction
    # This is a simplified approach - in practice, you might want to track
    # which specific examples were used in each prediction
    
    # For now, we'll find examples for this field and record feedback
    examples = get_few_shot_examples(machine_type, template_type, field_name, limit=5)
    
    if examples:
        # Record feedback on the most recent/confident example
        example_id = examples[0]['id']
        return add_few_shot_feedback(
            example_id=example_id,
            feedback_type=feedback_type,
            original_prediction=original_value,
            corrected_value=corrected_value,
            user_context=user_context
        )
    
    return False

def get_field_similarity_score(field_name: str, input_text: str, 
                             machine_type: str, template_type: str) -> float:
    """
    Calculates similarity score between input text and existing examples for a field.
    
    Args:
        field_name: Name of the field
        input_text: Input text to compare
        machine_type: Type of machine
        template_type: Type of template
    
    Returns:
        float: Similarity score (0.0-1.0)
    """
    examples = get_similar_examples(input_text, machine_type, template_type, limit=10)
    
    if not examples:
        return 0.0
    
    # Find examples for this specific field
    field_examples = [ex for ex in examples if ex.get('field_name') == field_name]
    
    if not field_examples:
        return 0.0
    
    # Return the highest similarity score for this field
    return max(ex.get('similarity', 0.0) for ex in field_examples)

def suggest_field_value_from_examples(field_name: str, input_text: str,
                                    machine_type: str, template_type: str) -> Optional[str]:
    """
    Suggests a field value based on similar examples.
    
    Args:
        field_name: Name of the field
        input_text: Input text
        machine_type: Type of machine
        template_type: Type of template
    
    Returns:
        str or None: Suggested value based on examples
    """
    examples = get_similar_examples(input_text, machine_type, template_type, limit=5)
    
    # Find examples for this specific field
    field_examples = [ex for ex in examples if ex.get('field_name') == field_name]
    
    if not field_examples:
        return None
    
    # Return the most confident example's output
    best_example = max(field_examples, key=lambda x: x.get('confidence_score', 0.0))
    return best_example.get('expected_output')
