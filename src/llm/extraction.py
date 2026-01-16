"""
LLM Field Extraction Module

This module handles core LLM field extraction operations using structured prompts and chains.
It provides the main extraction functions for document field population, using both
comprehensive and machine-specific extraction strategies.

Key Features:
- Comprehensive field extraction for all document fields (get_all_fields_via_llm)
- Machine-specific field extraction with divide-and-conquer strategy (get_machine_specific_fields_via_llm)
- Interactive chat-based field updates (get_llm_chat_update)
- CRM-to-document mapping for secondary documents (map_crm_to_document_via_llm)
- Confidence-scored extraction with validation (get_machine_specific_fields_with_confidence)
- Few-shot learning integration for improved accuracy

Extraction Strategies:
1. Comprehensive Extraction: Processes all fields in a single LLM call with structured prompts
2. Divide and Conquer: Splits fields into logical groups for focused extraction
3. Chat Update: Allows interactive corrections based on user instructions
4. CRM Mapping: Maps existing CRM data to new document templates

The module integrates with:
- Few-shot learning (basic and enhanced semantic similarity)
- Post-processing rules for field correction
- Confidence estimation and dependency validation
- Template-specific extraction strategies (Standard vs SortStar)
"""

import re
import json
import traceback
from typing import Dict, List, Any, Optional, Tuple

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field, create_model

# Internal LLM module imports
from .client import get_generative_model, configure_gemini_client, genai
from .constants import FIELD_GROUPS, FieldWithConfidence
from .confidence import estimate_extraction_confidence
from .validation import validate_field_dependencies, validate_llm_response
from .post_processing import apply_post_processing_rules

# Few-shot learning imports (basic)
from src.utils.few_shot_learning import (
    determine_machine_type,
    save_successful_extraction_as_example,
    record_user_feedback_on_extraction,
    enhance_prompt_with_few_shot_examples,
)

# Try to import enhanced few-shot learning, fall back to basic if not available
try:
    from src.utils.few_shot_enhanced import (
        enhance_prompt_with_semantic_examples,
        FewShotManager,
        create_enhanced_few_shot_prompt,
        get_few_shot_manager,
    )
    # TEMPORARY FIX: Disable few-shot learning to prevent poisoned empty examples from influencing output
    # ENHANCED_FEW_SHOT_AVAILABLE = True
    ENHANCED_FEW_SHOT_AVAILABLE = False
    print("[WARN] Enhanced few-shot learning temporarily disabled to prevent data poisoning loop")
except ImportError as e:
    print(f"[WARN] Enhanced few-shot learning not available: {e}")
    print("  Falling back to basic few-shot learning")
    ENHANCED_FEW_SHOT_AVAILABLE = False
    FewShotManager = None  # type: ignore
    get_few_shot_manager = None  # type: ignore

# Template utilities imports (must NOT be moved - imported from template_utils)
from src.utils.template_utils import add_section_aware_instructions, select_sortstar_basic_system


def get_all_fields_via_llm(selected_pdf_descriptions: List[str],
                             template_placeholder_contexts: Dict[str, str],
                             full_pdf_text: str) -> Dict[str, str]:
    """
    Constructs a comprehensive prompt for the LLM to fill all template fields
    (checkboxes and text fields) based on selected PDF items and full PDF text.

    The function now better handles enhanced context from the outline file.

    Args:
        selected_pdf_descriptions: List of item descriptions selected from the PDF
        template_placeholder_contexts: Dictionary of field keys to descriptions/schema
        full_pdf_text: Full text content of the PDF document

    Returns:
        Dictionary mapping field keys to extracted values (YES/NO for checkboxes, text for fields)
    """
    GENERATIVE_MODEL = get_generative_model()
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client():
            print("LLM client not configured. Returning empty data for all fields.")
            return {key: ("NO" if key.endswith("_check") else "") for key in template_placeholder_contexts.keys()}

    # Determine if we're using the old format (string context) or new format (schema)
    using_schema_format = isinstance(next(iter(template_placeholder_contexts.values()), ""), dict)

    prompt_parts = [
        "You are an AI assistant tasked with accurately extracting information from a PDF quote to fill a structured Word template.",
        "You will be given:",
        "  1. A list of 'SELECTED PDF ITEMS' which are explicitly priced or marked as included in the quote.",
        "  2. The 'FULL PDF TEXT' of the entire quote document.",
        "  3. A list of 'TEMPLATE FIELDS' with their descriptions (contexts) from the Word template.",

        "\nFULL PDF TEXT (Use this for general information like customer name, project numbers, machine model, and for details related to selected items. Max 10,000 characters will be shown if very long - prioritize start of document.):",
        # Truncate very long full_pdf_text to avoid exceeding prompt limits, prioritizing the start.
        # A more sophisticated chunking and retrieval strategy (like RAG with vector DB) would be better for extremely long docs.
        (full_pdf_text[:10000] + "... (text truncated)") if len(full_pdf_text) > 10000 else full_pdf_text,

        "\nSELECTED PDF ITEMS (These are primary evidence for options being selected):"
    ]
    if not selected_pdf_descriptions:
        prompt_parts.append("  (No specific items were identified as selected from tables in the PDF quote.)")
    else:
        for i, desc in enumerate(selected_pdf_descriptions):
            prompt_parts.append(f"  - PDF Item {i+1}: {desc}")

    if using_schema_format:
        # Group fields by section when using schema format
        sections = {}
        for key, field_info in template_placeholder_contexts.items():
            section = field_info.get("section", "General")
            if section not in sections:
                sections[section] = []
            sections[section].append((key, field_info))

        prompt_parts.append("\nTEMPLATE FIELDS TO FILL (organized by section):")

        for section, fields in sorted(sections.items()):
            prompt_parts.append(f"\n## {section} SECTION:")

            # Group by field type within section
            text_fields = [f for f in fields if f[1].get("type") == "string"]
            checkbox_fields = [f for f in fields if f[1].get("type") == "boolean"]

            if text_fields:
                prompt_parts.append("TEXT FIELDS:")
                for key, field_info in text_fields:
                    desc = field_info.get("description", key)
                    subsection = field_info.get("subsection", "")
                    if subsection:
                        prompt_parts.append(f"  - '{key}': [{subsection}] {desc}")
                    else:
                        prompt_parts.append(f"  - '{key}': {desc}")

            if checkbox_fields:
                prompt_parts.append("CHECKBOX FIELDS (must be YES or NO):")
                for key, field_info in checkbox_fields:
                    desc = field_info.get("description", key)
                    subsection = field_info.get("subsection", "")

                    # Include synonyms and positive indicators for checkbox fields
                    synonyms = field_info.get("synonyms", [])
                    positive_indicators = field_info.get("positive_indicators", [])

                    # Format the synonyms and indicators for the prompt
                    synonym_text = ""
                    if synonyms:
                        synonym_text = f" [Alternative terms: {', '.join(synonyms[:5])}]" if synonyms else ""

                    # Add positive indicators only for the first few checkboxes to avoid making the prompt too long
                    indicator_text = ""
                    if positive_indicators and len(checkbox_fields) < 20:  # Only if not too many checkboxes
                        indicator_text = f" [Indicators: {', '.join(positive_indicators[:3])}]" if positive_indicators else ""

                    # Include negative indicators for checkbox fields
                    negative_indicators = field_info.get("negative_indicators", [])
                    negative_indicator_text = ""
                    if negative_indicators and len(checkbox_fields) < 20: # Only if not too many checkboxes
                        negative_indicator_text = f" [Negative Indicators: {', '.join(negative_indicators[:3])}]" if negative_indicators else ""

                    if subsection:
                        prompt_parts.append(f"  - '{key}': [{subsection}] {desc}{synonym_text}{indicator_text}{negative_indicator_text}")
                    else:
                        prompt_parts.append(f"  - '{key}': {desc}{synonym_text}{indicator_text}{negative_indicator_text}")

        # Add section-aware instructions
        prompt_parts = add_section_aware_instructions(template_placeholder_contexts, prompt_parts)
    else:
        # For hierarchical context format, organize by section/subsection structure
        # This better handles the enhanced context from the outline file

        # Extract sections from context values
        sections = {}
        for key, context in template_placeholder_contexts.items():
            # Split context into parts (assuming section - subsection - description format)
            parts = context.split(" - ")
            section = parts[0] if parts else "General"

            if section not in sections:
                sections[section] = {}

            # Get subsection if available
            subsection = parts[1] if len(parts) > 1 else "General"
            if subsection not in sections[section]:
                sections[section][subsection] = []

            # Add field to the appropriate subsection
            sections[section][subsection].append((key, context))

        prompt_parts.append("\nTEMPLATE FIELDS TO FILL (organized by section and subsection):")

        for section, subsections in sorted(sections.items()):
            prompt_parts.append(f"\n## {section} SECTION:")

            for subsection, fields in sorted(subsections.items()):
                if subsection != "General":
                    prompt_parts.append(f"\n### {subsection} Subsection:")

                # Split fields into checkboxes and text fields
                checkbox_fields = [(k, c) for k, c in fields if k.endswith('_check')]
                text_fields = [(k, c) for k, c in fields if not k.endswith('_check')]

                if text_fields:
                    prompt_parts.append("TEXT FIELDS:")
                    for key, context in text_fields:
                        # Extract just the field description part
                        description = context.split(" - ")[-1] if " - " in context else context
                        prompt_parts.append(f"  - '{key}': {description}")

                if checkbox_fields:
                    prompt_parts.append("CHECKBOX FIELDS (must be YES or NO):")
                    for key, context in checkbox_fields:
                        # Extract just the field description part
                        description = context.split(" - ")[-1] if " - " in context else context
                        prompt_parts.append(f"  - '{key}': {description}")

    prompt_parts.append("\nYOUR TASK & RESPONSE FORMAT:")
    prompt_parts.append("Carefully analyze all provided information.")
    prompt_parts.append("For each TEMPLATE FIELD:")
    prompt_parts.append("  - If the field key ends with '_check' (a checkbox): Determine if it is confirmed as selected. Value must be \"YES\" or \"NO\". Prioritize SELECTED PDF ITEMS for these.")
    prompt_parts.append("  - If the field key does NOT end with '_check' (a text field): Extract the specific information from the FULL PDF TEXT using the field description as a guide. If the information cannot be found, the value should be an empty string (\"\").")
    prompt_parts.append("  - SPECIFIC INSTRUCTION for 'production_speed': Prioritize speed specifications mentioned *within the description of the primary selected machine* (e.g., a Monoblock) over general 'Projected Speed' sections if they differ. Look for phrases like 'up to X bottles/units per minute'.")
    prompt_parts.append("  - NOTE: 'Projected Speed' and 'Production Speed' refer to the same information - the rate at which the machine processes bottles/units, typically expressed in units per minute.")
    prompt_parts.append("Pay attention to bundled features within SELECTED PDF ITEMS. For example, if 'Monoblock Model ABC' description says 'Including: Feature X, Feature Y', then template fields for Feature X and Feature Y (if they are _check fields) should be YES.")
    prompt_parts.append("If a PDF item is general (e.g., 'Three (X 3) colours status beacon light') and the template has specific sub-features (e.g., 'Status Beacon Light: Red', 'Status Beacon Light: Yellow', 'Status Beacon Light: Green'), mark ALL corresponding specific sub-feature placeholders as YES.")
    prompt_parts.append("Be accurate and conservative. For checkboxes, if unsure, default to \"NO\". If an entire category of options (e.g., 'Street Fighter Tablet Counter') is NOT MENTIONED AT ALL in the PDF text or selected items, all its related checkboxes should be \"NO\".")
    prompt_parts.append("For text fields, if not found, use an empty string.")
    prompt_parts.append("Respond with a single, valid JSON object. The keys in the JSON MUST be ALL the TEMPLATE PLACEHOLDER KEYS listed above, and the values must be their extracted text or \"YES\"/\"NO\".")

    # Add context about General Order Acknowledgement structure to help with understanding
    prompt_parts.append("\nADDITIONAL CONTEXT ABOUT THE GENERAL ORDER ACKNOWLEDGEMENT (GOA) FORM:")
    prompt_parts.append("The GOA form is used in the packaging manufacturing industry to capture all specifications for a machine build.")
    prompt_parts.append("1. It starts with basic customer and project information (Proj #, Customer name, Machine type).")
    prompt_parts.append("2. It includes utility specifications (voltage, conformity certifications, country of destination).")
    prompt_parts.append("3. Material specifications define what components contact the product (metal parts usually SS304/316).")
    prompt_parts.append("4. Control & Programming sections define the automation system (PLC type, HMI size, etc.).")
    prompt_parts.append("5. Different sections cover specific functional modules (Filling System, Capping, Labeling, etc.).")
    prompt_parts.append("Pay close attention to the hierarchical structure of fields when determining YES/NO values for checkboxes.")

    # Add example JSON response format
    prompt_parts.append("\nEXAMPLE JSON RESPONSE FORMAT:")
    prompt_parts.append("""```json
{
  "machine_model": "LabelStar Model System 1",
  "production_speed": "60 units per minute",
  "barcode_scanner_check": "YES",
  "extended_conveyor_check": "NO",
  "customer_name": "ACME Corp",
  ... (other fields)
}
```""")

    prompt_parts.append("\nYour JSON Response:")

    prompt = "\n".join(prompt_parts)

    # print("\n----- LLM PROMPT (get_all_fields_via_llm) -----")
    # print(prompt)
    # print("--------------------------------------------\n")

    # Initialize with default values based on all template placeholders provided
    llm_response_data = {key: ("NO" if key.endswith("_check") else "") for key in template_placeholder_contexts.keys()}

    try:
        print("Sending comprehensive prompt to Gemini API...")
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        response = GENERATIVE_MODEL.generate_content(prompt, safety_settings=safety_settings)

        cleaned_response_text = response.text.strip()
        if cleaned_response_text.startswith("```json"):
            cleaned_response_text = cleaned_response_text[7:]
            if cleaned_response_text.endswith("```"):
                cleaned_response_text = cleaned_response_text[:-3]
        cleaned_response_text = cleaned_response_text.strip()

        try:
            parsed_llm_output = json.loads(cleaned_response_text)
            if isinstance(parsed_llm_output, dict):
                # Validate the response if using schema format
                if using_schema_format:
                    validation_errors = validate_llm_response(parsed_llm_output, template_placeholder_contexts)
                    if validation_errors:
                        print("Validation errors found in LLM response:")
                        for field, errors in validation_errors.items():
                            print(f"  - '{field}': {', '.join(errors)}")
                        # Continue anyway - we'll use what we got

                # Update the response data with values
                for key, value in parsed_llm_output.items():
                    if key in llm_response_data: # Only update keys that were expected
                        is_checkbox = (using_schema_format and
                                      isinstance(template_placeholder_contexts.get(key), dict) and
                                      template_placeholder_contexts.get(key, {}).get("type") == "boolean") or \
                                      (not using_schema_format and key.endswith("_check"))

                        if is_checkbox:
                            if isinstance(value, str) and value.upper() in ["YES", "NO"]:
                                llm_response_data[key] = value.upper()
                            # else: keep default "NO"
                        else: # It's a text field
                            llm_response_data[key] = str(value) # Assign extracted text
            else:
                print(f"Warning: LLM response was not a JSON dictionary: {parsed_llm_output}")
        except json.JSONDecodeError as e:
            print(f"Error decoding LLM JSON response: {e}")
            print(f"LLM Response Text was: {repr(cleaned_response_text)}")
    except Exception as e:
        print(f"Error communicating with Gemini API or processing response: {e}")
        traceback.print_exc()

    # Apply post-processing rules to improve the data
    corrected_data = apply_post_processing_rules(llm_response_data, template_placeholder_contexts)
    return corrected_data


def get_llm_chat_update(current_data: Dict[str, str],
                        user_instruction: str,
                        selected_pdf_descriptions: List[str],
                        template_placeholder_contexts: Dict[str, str],
                        full_pdf_text: str) -> Dict[str, str]:
    """
    Takes current data, user instruction, and original contexts, then asks LLM for an updated data dictionary
    covering ALL fields (text and checkboxes).

    Args:
        current_data: Current field values before update
        user_instruction: User's instruction for what to change
        selected_pdf_descriptions: List of item descriptions from PDF
        template_placeholder_contexts: Template field contexts/descriptions
        full_pdf_text: Full PDF text for reference

    Returns:
        Updated dictionary with corrected field values
    """
    GENERATIVE_MODEL = get_generative_model()
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client():
            print("LLM client not configured for chat update. Returning current data.")
            return current_data

    prompt_parts = [
        "You are an AI assistant helping to correct a technical equipment order template that was previously filled (partially or fully).",
        "The user will provide an instruction to change one or more field values.",
        "\nPREVIOUSLY FILLED DATA (this is the data you need to update):",
        json.dumps(current_data, indent=2),
        "\nUSER'S CORRECTION INSTRUCTION:",
        f">>> {user_instruction}",
        "\nORIGINAL CONTEXT FOR YOUR REFERENCE (use this if the user's instruction is ambiguous or refers to original details):",
        "1. SELECTED PDF ITEMS (primary evidence for checkbox options):"
    ]
    if not selected_pdf_descriptions:
        prompt_parts.append("  (No specific items were identified as selected from tables.)")
    else:
        for i, desc in enumerate(selected_pdf_descriptions):
            prompt_parts.append(f"  - PDF Item {i+1}: {desc}")

    prompt_parts.append("\n2. FULL PDF TEXT (for general information and details - showing first 10000 chars if long):")
    prompt_parts.append((full_pdf_text[:10000] + "... (text truncated)") if len(full_pdf_text) > 10000 else full_pdf_text)

    prompt_parts.append("\n3. TEMPLATE FIELDS (Placeholder Key: Description from template that the user might refer to):")
    placeholder_list_for_prompt = []
    for key, context in template_placeholder_contexts.items():
        field_type = "Checkbox (YES/NO)" if key.endswith("_check") else "Text Field"
        placeholder_list_for_prompt.append(f"  - '{key}' (Type: {field_type}): '{context}'")
    if not placeholder_list_for_prompt:
        prompt_parts.append("  (No template fields provided for context.)")
    else:
        for item_for_prompt in placeholder_list_for_prompt:
            prompt_parts.append(item_for_prompt)

    prompt_parts.append("\nYOUR TASK:")
    prompt_parts.append("1. Understand the USER'S CORRECTION INSTRUCTION.")
    prompt_parts.append("2. If the instruction refers to a template field by its description, identify the corresponding Placeholder Key.")
    prompt_parts.append("3. Modify the PREVIOUSLY FILLED DATA according to the user's instruction. For text fields, extract the new value from the FULL PDF TEXT if the user implies it (e.g., 'Correct the customer name').")
    prompt_parts.append("4. IMPORTANT: Your response MUST be a single, valid JSON object.")
    prompt_parts.append("5. This JSON object MUST contain ALL the original placeholder keys listed in the TEMPLATE FIELDS section above.")
    prompt_parts.append("   - For keys ending with '_check', the value MUST be \"YES\" or \"NO\".")
    prompt_parts.append("   - For other keys (text fields), the value should be the extracted string, or an empty string if not found/applicable.")
    prompt_parts.append("   Do NOT omit any original keys. Do NOT add new keys.")
    prompt_parts.append("\nUpdated JSON Response:")

    prompt = "\n".join(prompt_parts)

    print("\n----- LLM CHAT PROMPT -----")
    print(prompt)
    print("-------------------------")

    updated_data = current_data.copy()

    try:
        print("Sending correction prompt to Gemini API...")
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        response = GENERATIVE_MODEL.generate_content(prompt, safety_settings=safety_settings)

        print("\n----- LLM CHAT RAW RESPONSE -----")
        print(response.text)
        print("----------------------------")

        cleaned_response_text = response.text.strip()
        if cleaned_response_text.startswith("```json"):
            cleaned_response_text = cleaned_response_text[7:]
            if cleaned_response_text.endswith("```"):
                cleaned_response_text = cleaned_response_text[:-3]
        cleaned_response_text = cleaned_response_text.strip()

        try:
            parsed_llm_update = json.loads(cleaned_response_text)
            if isinstance(parsed_llm_update, dict):
                for key, value in parsed_llm_update.items():
                    if key in updated_data and key.endswith("_check"):
                        if isinstance(value, str) and value.upper() in ["YES", "NO"]:
                            updated_data[key] = value.upper()
                        else:
                            print(f"Warning: LLM provided invalid value '{value}' for key '{key}'. Keeping previous: '{updated_data[key]}'.")
                    elif key in updated_data: # For text fields (not ending in _check)
                        updated_data[key] = str(value)
            else:
                print(f"Warning: LLM chat update response was not a JSON dictionary: {parsed_llm_update}")
        except json.JSONDecodeError as e:
            print(f"Error decoding LLM chat update JSON response: {e}")
            print(f"LLM Chat Update Response Text was: {repr(cleaned_response_text)}")

    except Exception as e:
        print(f"Error in get_llm_chat_update: {e}")
        traceback.print_exc()

    # Apply post-processing rules to improve the data
    corrected_data = apply_post_processing_rules(updated_data, template_placeholder_contexts)

    return corrected_data


def map_crm_to_document_via_llm(crm_client_data: Dict[str, Any],
                                crm_priced_items: List[Dict[str, Any]],
                                document_template_contexts: Dict[str, str],
                                document_type_hint: str,
                                # full_original_pdf_text: Optional[str] = None # For future LLM calls if CRM data is not enough
                               ) -> Dict[str, str]:
    """
    Uses an LLM to map CRM data (client details and priced items) to the placeholders
    of a specified document template (e.g., Packing Slip, Commercial Invoice).

    Args:
        crm_client_data: Dictionary of the client's main details from the CRM.
        crm_priced_items: List of dictionaries for their priced items from the CRM.
        document_template_contexts: Dict of {{placeholder}} -> "context string" for the target document.
        document_type_hint: String like "Packing Slip" or "Commercial Invoice" to guide the LLM.
        # full_original_pdf_text: Optional full text of the original quote if LLM needs to refer back.

    Returns:
        A dictionary ready to be used by doc_filler.py for the target document.
    """
    GENERATIVE_MODEL = get_generative_model()
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client():
            print(f"LLM client not configured for {document_type_hint} generation. Returning empty data.")
            return {key: "" for key in document_template_contexts.keys()} # Default all to empty

    prompt_parts = [
        f"You are an AI assistant preparing data to fill a '{document_type_hint}' document.",
        "You will be given data from a CRM (Customer Relationship Management) system and a list of fields from the target document template.",

        "\nCRM DATA:",
        "1. Client Details:",
        json.dumps(crm_client_data, indent=2),
        "\n2. Priced Line Items from Original Quote:"
    ]
    if not crm_priced_items:
        prompt_parts.append("  (No priced line items found in CRM for this client/quote.)")
    else:
        for i, item in enumerate(crm_priced_items):
            prompt_parts.append(f"  - Item {i+1}: Description='{item.get('item_description')}', Quantity='{item.get('item_quantity')}', Price String='{item.get('item_price_str')}', Numeric Price='{item.get('item_price_numeric')}'") # Add H.S. Code later if available

    prompt_parts.append(f"\nTARGET DOCUMENT TEMPLATE FIELDS ('{document_type_hint}' - Placeholder Key: Description from template):")
    placeholder_list_for_prompt = []
    for key, context in document_template_contexts.items():
        placeholder_list_for_prompt.append(f"  - '{key}': '{context}'")
    if not placeholder_list_for_prompt:
        prompt_parts.append("  (No template fields provided for the target document.)")
        return {}
    for item_for_prompt in placeholder_list_for_prompt:
        prompt_parts.append(item_for_prompt)

    prompt_parts.append("\nYOUR TASK:")
    prompt_parts.append(f"Based on the provided CRM DATA, determine the correct value for each TARGET DOCUMENT TEMPLATE FIELD.")
    prompt_parts.append("  - Directly map CRM fields (like customer_name, quote_ref, addresses, customer_po) to corresponding template fields.")
    prompt_parts.append("  - For line items in the template (e.g., item_1_desc, item_1_qty), populate them sequentially from the CRM Priced Line Items. If the template has more line item placeholders than available items, leave the extra ones as empty strings.")
    prompt_parts.append("  - For fields specific to the new document that are not directly in the CRM (e.g., '{document_type_hint} Number', 'Ship Date', 'AX Number', 'OX Number', 'Incoterm', 'Via', 'Serial Number'):")
    prompt_parts.append("    - If a sensible default is obvious (like today's date for 'Ship Date', or deriving '{document_type_hint} Number' from quote_ref like 'PS-[quote_ref]'), generate it.")
    prompt_parts.append("    - Otherwise, use \"TBD\" or an empty string for such fields if the information isn't in the CRM.")
    prompt_parts.append("  - Ensure dates are formatted as YYYY-MM-DD if applicable.")
    prompt_parts.append("  - For any checkbox fields (ending in '_check'), determine their YES/NO value based on CRM data or common sense for the document type.")

    prompt_parts.append("RESPONSE FORMAT:")
    prompt_parts.append("Respond with a single, valid JSON object. The keys in the JSON MUST be ALL the TARGET DOCUMENT TEMPLATE PLACEHOLDER KEYS, and the values should be the data to fill them with.")
    prompt_parts.append("\nYour JSON Response:")

    prompt = "\n".join(prompt_parts)

    # print(f"\n----- LLM PROMPT ({document_type_hint} Data Mapping) -----")
    # print(prompt)
    # print("----------------------------------------------------\n")

    # Initialize with default values based on all target template placeholders
    output_data_for_document = {key: ("NO" if key.endswith("_check") else "") for key in document_template_contexts.keys()}

    try:
        print(f"Sending '{document_type_hint}' data mapping prompt to Gemini API...")
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        response = GENERATIVE_MODEL.generate_content(prompt, safety_settings=safety_settings)

        cleaned_response_text = response.text.strip()
        if cleaned_response_text.startswith("```json"):
            cleaned_response_text = cleaned_response_text[7:]
            if cleaned_response_text.endswith("```"):
                cleaned_response_text = cleaned_response_text[:-3]
        cleaned_response_text = cleaned_response_text.strip()

        try:
            parsed_llm_output = json.loads(cleaned_response_text)
            if isinstance(parsed_llm_output, dict):
                for key, value in parsed_llm_output.items():
                    if key in output_data_for_document: # Only update keys that were expected from the target template
                        if key.endswith("_check"):
                            if isinstance(value, str) and value.upper() in ["YES", "NO"]:
                                output_data_for_document[key] = value.upper()
                        else: # It's a text field
                            output_data_for_document[key] = str(value) # Assign extracted/generated text
            else:
                print(f"Warning: LLM response for {document_type_hint} was not a JSON dictionary.")
        except json.JSONDecodeError as e:
            print(f"Error decoding LLM JSON response for {document_type_hint}: {e}")
            print(f"LLM Response Text was: {repr(cleaned_response_text)}")
    except Exception as e:
        print(f"Error generating data for {document_type_hint}: {e}")
        traceback.print_exc()

    print(f"Prepared data for {document_type_hint}:", json.dumps(output_data_for_document, indent=2))
    return output_data_for_document


def get_machine_specific_fields_via_llm(machine_data: Dict,
                                       common_items: List[Dict],
                                       template_placeholder_contexts: Dict[str, Any], # Can be Dict[str, str] or Dict[str, Dict]
                                       full_pdf_text: str,
                                       template_metadata: Optional[Dict] = None) -> Dict[str, str]:
    """
    Uses LangChain to create robust, schema-driven extraction chains to fill
    fields based on machine data, common items, and full PDF text.

    Implements a 'Divide and Conquer' strategy by splitting fields into logical groups
    and running multiple smaller LLM calls to improve accuracy and focus.

    Args:
        machine_data: Dictionary containing machine information (name, main_item, add_ons)
        common_items: List of common/shared items for this quote
        template_placeholder_contexts: Template field contexts (string or dict schema)
        full_pdf_text: Full text of the PDF document
        template_metadata: Optional metadata about the template

    Returns:
        Dictionary mapping field keys to extracted values
    """
    GENERATIVE_MODEL = get_generative_model()
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client():
            print("LLM client not configured. Returning empty data.")
            return {key: ("NO" if key.endswith("_check") else "") for key in template_placeholder_contexts.keys()}

    # 1. Categorize fields into groups
    grouped_contexts = {group: {} for group in FIELD_GROUPS.keys()}

    # Helper to find group
    def find_group(key, context=None):
        # Strategy 1: Use section name from schema context if available
        if isinstance(context, dict) and "section" in context:
            section = context["section"].lower()
            
            # Map sections to groups
            if any(x in section for x in ["control", "electrical", "program", "guard", "code", "coding", "inspect"]):
                return "Controls & Electrical"
            
            if any(x in section for x in ["liquid", "fill", "bottle", "handling", "tablet", "cotton", "desiccant", "gas"]):
                return "Liquid Filling & Handling"
            
            if any(x in section for x in ["cap", "label", "induction", "sleeve", "conveyor", "plug", "belt", "shrink", "retorquer"]):
                return "Capping, Labeling & Other"
                
            # Default for other sections (Basic Info, Utility, Warranty, etc.)
            return "General & Utility"

        # Strategy 2: Fallback to key prefixes (backward compatibility)
        for group_name, rules in FIELD_GROUPS.items():
            if key in rules["exact"]:
                return group_name
            for prefix in rules["prefixes"]:
                if key.startswith(prefix):
                    return group_name
        return "General & Utility" # Default fallback

    for key, context in template_placeholder_contexts.items():
        group = find_group(key, context)
        grouped_contexts[group][key] = context

    # Remove empty groups to avoid unnecessary calls
    active_groups = {k: v for k, v in grouped_contexts.items() if v}

    all_extracted_data = {}

    # Determine machine type once for few-shot learning
    machine_name = machine_data.get("machine_name", "")
    machine_type = determine_machine_type(machine_name)

    # Prepare input data common to all groups
    main_item_desc = machine_data.get("main_item", {}).get("description", "")
    add_on_descs = "; ".join([item.get("description", "") for item in machine_data.get("add_ons", [])])
    common_item_descs = "; ".join([item.get("description", "") for item in common_items])

    # 2. Iterate through each group and run extraction
    BATCH_SIZE = 40  # Process max 40 fields at a time to prevent hangs
    
    for group_name, group_contexts in active_groups.items():
        print(f"\n--- Processing Group: {group_name} ({len(group_contexts)} fields) ---")
        
        # Split contexts into batches
        context_items = list(group_contexts.items())
        batches = [context_items[i:i + BATCH_SIZE] for i in range(0, len(context_items), BATCH_SIZE)]
        
        for batch_idx, batch_items in enumerate(batches):
            batch_contexts = dict(batch_items)
            print(f"  Batch {batch_idx + 1}/{len(batches)} ({len(batch_contexts)} fields)...")

            # --- Dynamic Pydantic Model Creation for this Batch ---
            using_schema_format = isinstance(next(iter(batch_contexts.values()), {}), dict)

            fields = {}
            name_mapping = {}
            for name, context in batch_contexts.items():
                description = ""
                if using_schema_format and isinstance(context, dict):
                    description = context.get("description", f"Field for {name}")
                elif isinstance(context, str):
                    description = context

                # Sanitize field name for Pydantic
                sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
                if sanitized_name != name:
                    name_mapping[sanitized_name] = name

                fields[sanitized_name] = (Optional[str], Field(default=None, description=description))

            # Create unique model name to avoid conflicts
            model_name = f"DynamicGOA_{group_name.replace(' ', '').replace('&', '')}_{batch_idx}"
            DynamicGroupModel = create_model(model_name, **fields)

            # Initialize LLM with timeout to prevent infinite hangs
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash-lite", 
                temperature=0.1,
                request_timeout=60, # 60 seconds timeout per batch
                max_retries=2
            )
            parser = PydanticOutputParser(pydantic_object=DynamicGroupModel)

            base_prompt_template = f"""
            You are an AI assistant specializing in extracting information from packaging machinery quotes.
            Your task is to populate a structured data model for the '{group_name}' section (Batch {batch_idx + 1}) based on the provided context.

            INSTRUCTIONS:
            - For checkbox fields (ending in '_check'):
              - You MUST find direct evidence in the context. The 'positive indicators' provided in the field descriptions are REQUIRED keywords. If none of these indicators are present, you MUST output "NO".
              - Conversely, if any 'negative indicators' (keywords that explicitly negate the feature) are present in the context, you MUST output "NO", even if some positive indicators are also present. Negative indicators override positive ones.
            - For text fields, extract the information as requested. If not found, leave it null.
            - Be precise and do not guess. Your accuracy is critical.

            CONTEXT:
            - Machine Name: {{{{machine_name}}}}
            - Main Machine Item: {{{{main_item_desc}}}}
            - Machine Add-ons: {{{{add_on_descs}}}}
            - Common/Shared Items: {{{{common_item_descs}}}}
            - Full PDF Text (for context and details): {{{{full_pdf_text}}}}

            Based on the context above, extract the information for the following fields.
            Pay close attention to the descriptions and positive indicators for each field to guide your extraction.

            {{{{format_instructions}}}}
            """

            # Enhance prompt with few-shot examples specific to this group/fields if possible
            if ENHANCED_FEW_SHOT_AVAILABLE:
                try:
                    enhanced_prompt_parts = enhance_prompt_with_semantic_examples(
                        prompt_parts=[base_prompt_template],
                        machine_data=machine_data,
                        template_placeholder_contexts=batch_contexts, # Pass only batch contexts
                        common_items=common_items,
                        full_pdf_text=full_pdf_text,
                        max_examples_per_field=1 
                    )
                except Exception as semantic_error:
                    print(f"Semantic few-shot enhancement failed for {group_name} batch {batch_idx}: {semantic_error}")
                    enhanced_prompt_parts = [base_prompt_template]
            else:
                # Fallback to basic few-shot examples
                try:
                    enhanced_prompt_parts = enhance_prompt_with_few_shot_examples(
                        prompt_parts=[base_prompt_template],
                        machine_data=machine_data,
                        template_placeholder_contexts=batch_contexts,
                        common_items=common_items,
                        full_pdf_text=full_pdf_text,
                        max_examples_per_field=1
                    )
                except Exception as basic_error:
                    print(f"Basic few-shot enhancement failed for {group_name} batch {batch_idx}: {basic_error}")
                    enhanced_prompt_parts = [base_prompt_template]

            prompt_template = "\n".join(enhanced_prompt_parts)

            prompt = PromptTemplate(
                template=prompt_template,
                input_variables=["machine_name", "full_pdf_text", "main_item_desc", "add_on_descs", "common_item_descs"],
                partial_variables={"format_instructions": parser.get_format_instructions()},
            )

            chain = prompt | llm | parser

            # Reduced context size to prevent server disconnection with Flash Lite model
            # 20000 chars is approx 5k tokens - this matches the pre-refactoring limit that worked reliably
            input_data = {
                "machine_name": machine_name,
                "full_pdf_text": full_pdf_text[:20000],
                "main_item_desc": main_item_desc,
                "add_on_descs": add_on_descs,
                "common_item_descs": common_item_descs,
            }

            try:
                print(f"    Invoking LLM chain...")
                result = chain.invoke(input_data)
                result_dict = result.dict()
                print(f"    Received response")

                # Process results for this batch
                for sanitized_name, value in result_dict.items():
                    original_name = name_mapping.get(sanitized_name, sanitized_name)

                    is_checkbox = original_name.endswith("_check") or (
                        using_schema_format and
                        isinstance(template_placeholder_contexts.get(original_name), dict) and
                        template_placeholder_contexts[original_name].get('type') == 'boolean'
                    )

                    if value is None:
                        all_extracted_data[original_name] = "NO" if is_checkbox else ""
                    elif is_checkbox:
                        if isinstance(value, str) and value.upper() in ["YES", "TRUE", "1"]:
                            all_extracted_data[original_name] = "YES"
                        elif isinstance(value, bool) and value:
                            all_extracted_data[original_name] = "YES"
                        else:
                            all_extracted_data[original_name] = "NO"
                    else:
                        all_extracted_data[original_name] = str(value)

            except Exception as e:
                print(f"Error during extraction for group {group_name} batch {batch_idx}: {e}")
                # Fill missing fields with defaults for this batch only
                for key in batch_contexts:
                    if key not in all_extracted_data:
                         all_extracted_data[key] = "NO" if key.endswith("_check") else ""

    # 3. Apply post-processing rules to the combined data
    print("\nApplying post-processing rules to combined data...")

    # Construct selected_pdf_descriptions for post-processing
    selected_pdf_descriptions = []
    if main_item_desc: # Add main item description
        selected_pdf_descriptions.append(main_item_desc)
    selected_pdf_descriptions.extend([item.get("description", "") for item in machine_data.get("add_ons", []) if item.get("description")])
    selected_pdf_descriptions.extend([item.get("description", "") for item in common_items if item.get("description")])

    final_data = apply_post_processing_rules(all_extracted_data, template_placeholder_contexts, full_pdf_text, selected_pdf_descriptions)

    # If this is a SortStar machine, enforce the basic system selection
    if machine_type == "sortstar":
        print("Enforcing SortStar basic system selection...")
        basic_system_selection = select_sortstar_basic_system(machine_data, full_pdf_text)
        final_data.update(basic_system_selection)
        print("SortStar basic system selection applied.")

    # Store confident outputs so future runs benefit from richer few-shot data
    _persist_machine_few_shot_examples(
        machine_data=machine_data,
        common_items=common_items,
        full_pdf_text=full_pdf_text,
        extracted_fields=final_data,
        machine_type=machine_type,
    )

    return final_data


def get_machine_specific_fields_with_confidence(
    machine_data: Dict,
    common_items: List[Dict],
    template_placeholder_contexts: Dict[str, Any],
    full_pdf_text: str,
    template_metadata: Optional[Dict] = None
) -> Tuple[Dict[str, str], Dict[str, float], List[Dict[str, Any]]]:
    """
    Enhanced version of get_machine_specific_fields_via_llm that also returns
    confidence scores and field dependency suggestions.

    Args:
        machine_data: Dictionary containing machine information
        common_items: List of common items
        template_placeholder_contexts: Template field contexts
        full_pdf_text: Full PDF text
        template_metadata: Optional template metadata

    Returns:
        Tuple containing:
        - Dict[str, str]: Extracted field values
        - Dict[str, float]: Confidence scores for each field (0.0-1.0)
        - List[Dict]: Field dependency suggestions/warnings
    """
    # First, run the standard extraction
    extracted_data = get_machine_specific_fields_via_llm(
        machine_data=machine_data,
        common_items=common_items,
        template_placeholder_contexts=template_placeholder_contexts,
        full_pdf_text=full_pdf_text,
        template_metadata=template_metadata
    )

    # Estimate confidence for each field
    print("\n--- Estimating field confidence scores ---")
    confidence_scores = estimate_extraction_confidence(
        extracted_data=extracted_data,
        template_contexts=template_placeholder_contexts,
        full_pdf_text=full_pdf_text,
        machine_data=machine_data,
        common_items=common_items
    )

    # Validate field dependencies and get suggestions
    print("\n--- Validating field dependencies ---")
    updated_data, updated_confidence, suggestions = validate_field_dependencies(
        extracted_data=extracted_data,
        confidence_scores=confidence_scores
    )

    if suggestions:
        print(f"Field dependency validation found {len(suggestions)} suggestion(s)/warning(s):")
        for s in suggestions:
            print(f"  [{s['type'].upper()}] {s['field']}: {s['reason']}")

    return updated_data, updated_confidence, suggestions


def _persist_machine_few_shot_examples(
    machine_data: Dict[str, Any],
    common_items: List[Dict[str, Any]],
    full_pdf_text: str,
    extracted_fields: Dict[str, str],
    machine_type: str,
) -> None:
    """
    Save high-confidence model outputs so they can serve as future few-shot examples.

    Args:
        machine_data: Dictionary containing machine information
        common_items: List of common/shared items
        full_pdf_text: Full PDF text content
        extracted_fields: Dictionary of extracted field values
        machine_type: Type of machine (e.g., "sortstar", "default")
    """
    if not extracted_fields or not full_pdf_text:
        return

    template_type = "sortstar" if "sortstar" in machine_type else "default"
    machine_name = machine_data.get("machine_name", "machine")
    saved_count = 0

    manager = None
    if ENHANCED_FEW_SHOT_AVAILABLE and get_few_shot_manager is not None:
        try:
            manager = get_few_shot_manager()  # type: ignore[misc]
        except Exception as manager_error:
            print(f"Unable to initialize FewShotManager cache: {manager_error}")
            manager = None

    for field_name, raw_value in extracted_fields.items():
        value = raw_value.strip() if isinstance(raw_value, str) else ""
        if not value:
            continue

        # Only persist checkbox fields when we detected a positive assertion.
        if field_name.endswith("_check"):
            normalized_checkbox = value.upper()
            if normalized_checkbox != "YES":
                continue
            value_to_store = normalized_checkbox
        else:
            # Avoid polluting the example base with extremely short strings
            if len(value) < 3:
                continue
            value_to_store = value

        success = save_successful_extraction_as_example(
            field_name=field_name,
            field_value=value_to_store,
            machine_data=machine_data,
            common_items=common_items,
            full_pdf_text=full_pdf_text,
            machine_type=machine_type,
            template_type=template_type,
            confidence_score=0.75,
        )

        if success:
            saved_count += 1
            if manager:
                try:
                    manager.invalidate_cache(machine_type, template_type, field_name)
                except Exception as cache_error:
                    print(f"Unable to refresh semantic cache for {field_name}: {cache_error}")

    if saved_count:
        print(f"Saved {saved_count} automatic few-shot example(s) for {machine_name}.")
