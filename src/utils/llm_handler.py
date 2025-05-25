import os
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional
import json
import traceback # For more detailed error logging

# Global variable for the model, initialized once
GENERATIVE_MODEL = None

def configure_gemini_client():
    """
    Loads the API key from .env and configures the Gemini client.
    Returns True if configuration is successful, False otherwise.
    """
    global GENERATIVE_MODEL
    if GENERATIVE_MODEL is not None:
        return True # Already configured

    try:
        load_dotenv() # Load environment variables from .env file
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Error: GOOGLE_API_KEY not found in .env file or environment variables.")
            return False
        
        genai.configure(api_key=api_key)
        GENERATIVE_MODEL = genai.GenerativeModel('gemini-1.5-flash-latest') # Or your preferred Gemini model
        print("Gemini client configured successfully.")
        return True
    except Exception as e:
        print(f"Error configuring Gemini client: {e}")
        GENERATIVE_MODEL = None
        return False

# Renamed and updated to handle all field types
def get_all_fields_via_llm(selected_pdf_descriptions: List[str], 
                             template_placeholder_contexts: Dict[str, str],
                             full_pdf_text: str) -> Dict[str, str]:
    """
    Constructs a comprehensive prompt for the LLM to fill all template fields
    (checkboxes and text fields) based on selected PDF items and full PDF text.
    """
    global GENERATIVE_MODEL
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client():
            print("LLM client not configured. Returning empty data for all fields.")
            return {key: ("NO" if key.endswith("_check") else "") for key in template_placeholder_contexts.keys()}

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
    
    prompt_parts.append("\nTEMPLATE FIELDS TO FILL (Placeholder Key: Description from template):")
    placeholder_list_for_prompt = []
    for key, context in template_placeholder_contexts.items():
        placeholder_list_for_prompt.append(f"  - '{key}': '{context}'")
    if not placeholder_list_for_prompt:
        prompt_parts.append("  (No template fields provided to evaluate.)")
        return {}
    for item_for_prompt in placeholder_list_for_prompt:
        prompt_parts.append(item_for_prompt)

    prompt_parts.append("\nYOUR TASK & RESPONSE FORMAT:")
    prompt_parts.append("Carefully analyze all provided information.")
    prompt_parts.append("For each TEMPLATE FIELD:")
    prompt_parts.append("  - If the field key ends with '_check' (a checkbox): Determine if it is confirmed as selected. Value must be \"YES\" or \"NO\". Prioritize SELECTED PDF ITEMS for these.")
    prompt_parts.append("  - If the field key does NOT end with '_check' (a text field): Extract the specific information from the FULL PDF TEXT using the field description as a guide. If the information cannot be found, the value should be an empty string (\"\").")
    prompt_parts.append("  - SPECIFIC INSTRUCTION for 'production_speed': Prioritize speed specifications mentioned *within the description of the primary selected machine* (e.g., a Monoblock) over general 'Projected Speed' sections if they differ. Look for phrases like 'up to X bottles/units per minute'.")
    prompt_parts.append("Pay attention to bundled features within SELECTED PDF ITEMS. For example, if 'Monoblock Model ABC' description says 'Including: Feature X, Feature Y', then template fields for Feature X and Feature Y (if they are _check fields) should be YES.")
    prompt_parts.append("If a PDF item is general (e.g., 'Three (X 3) colours status beacon light') and the template has specific sub-features (e.g., 'Status Beacon Light: Red', 'Status Beacon Light: Yellow', 'Status Beacon Light: Green'), mark ALL corresponding specific sub-feature placeholders as YES.")
    prompt_parts.append("Be accurate and conservative. For checkboxes, if unsure, default to \"NO\". If an entire category of options (e.g., 'Street Fighter Tablet Counter') is NOT MENTIONED AT ALL in the PDF text or selected items, all its related checkboxes should be \"NO\".")
    prompt_parts.append("For text fields, if not found, use an empty string.")
    prompt_parts.append("Respond with a single, valid JSON object. The keys in the JSON MUST be ALL the TEMPLATE PLACEHOLDER KEYS listed above, and the values must be their extracted text or \"YES\"/\"NO\".")
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
                for key, value in parsed_llm_output.items():
                    if key in llm_response_data: # Only update keys that were expected
                        if key.endswith("_check"):
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

    return llm_response_data

def get_llm_chat_update(current_data: Dict[str, str], 
                        user_instruction: str, 
                        selected_pdf_descriptions: List[str], 
                        template_placeholder_contexts: Dict[str, str],
                        full_pdf_text: str) -> Dict[str, str]:
    """
    Takes current data, user instruction, and original contexts, then asks LLM for an updated data dictionary
    covering ALL fields (text and checkboxes).
    """
    global GENERATIVE_MODEL
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
    return updated_data

def answer_pdf_question(user_question: str, 
                        selected_pdf_descriptions: List[str], 
                        full_pdf_text: str, 
                        template_placeholder_contexts: Optional[Dict[str, str]] = None) -> str:
    """
    Answers a user's question based on the provided PDF content (selected items and full text).
    Optionally uses template contexts if questions might refer to template field names.
    """
    global GENERATIVE_MODEL
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client():
            return "Error: LLM client not configured. Please check API key."

    prompt_parts = [
        "You are an AI assistant designed to answer questions about a technical equipment PDF quote.",
        "Base your answers SOLELY on the information provided below from the PDF.",
        "If the information to answer the question is not present in the provided text, clearly state that you cannot find the answer in the document.",
        "Be concise and direct.",
        
        "\nUSER'S QUESTION:",
        user_question,
        
        "\nRELEVANT INFORMATION FROM PDF:",
        "\n1. SELECTED PDF ITEMS (items confirmed as selected from the PDF quote):"
    ]
    if not selected_pdf_descriptions:
        prompt_parts.append("  (No specific items were identified as selected from tables.)")
    else:
        for i, desc in enumerate(selected_pdf_descriptions):
            prompt_parts.append(f"  - PDF Item {i+1}: {desc}")
    
    prompt_parts.append("\n2. FULL PDF TEXT (for general information or details not in selected items - showing first 10,000 chars if long to save tokens. Prioritize start of document if truncated.):")
    prompt_parts.append((full_pdf_text[:10000] + "... (text truncated if longer)") if len(full_pdf_text) > 10000 else full_pdf_text)

    # Optionally add template contexts if questions might refer to template field names
    if template_placeholder_contexts:
        prompt_parts.append("\n3. TEMPLATE FIELDS (Context for potential questions referring to template field names - Placeholder Key: Description from template):")
        placeholder_list_for_prompt = []
        for key, context in template_placeholder_contexts.items():
            placeholder_list_for_prompt.append(f"  - '{key}': '{context}'")
        if not placeholder_list_for_prompt:
            prompt_parts.append("  (No template fields context provided.)")
        else:
            for item_for_prompt in placeholder_list_for_prompt:
                prompt_parts.append(item_for_prompt)

    prompt_parts.append("\nYOUR ANSWER TO THE USER'S QUESTION:")
    
    prompt = "\n".join(prompt_parts)

    # print("\n----- LLM Q&A PROMPT -----") # Uncomment for debugging
    # print(prompt)
    # print("------------------------")

    try:
        print("Sending Q&A prompt to Gemini API...")
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        response = GENERATIVE_MODEL.generate_content(prompt, safety_settings=safety_settings)
        
        # print("\n----- LLM Q&A RAW RESPONSE -----") # Uncomment for debugging
        # print(response.text)
        # print("----------------------------")
        return response.text.strip()
    
    except Exception as e:
        print(f"Error in answer_pdf_question: {e}")
        traceback.print_exc()
        return "Sorry, I encountered an error trying to answer your question."

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
    global GENERATIVE_MODEL
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
                                       template_placeholder_contexts: Dict[str, str],
                                       full_pdf_text: str) -> Dict[str, str]:
    """
    Constructs a prompt for the LLM focused on a specific machine and its add-ons,
    plus common items that apply to all machines.
    
    Args:
        machine_data: Dictionary containing machine_name, main_item, and add_ons
        common_items: List of items common to all machines (warranty, etc.)
        template_placeholder_contexts: Dictionary of template field contexts
        full_pdf_text: Full text of the PDF document
        
    Returns:
        Dictionary mapping template placeholders to values from LLM
    """
    global GENERATIVE_MODEL
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client():
            print("LLM client not configured. Returning empty data for machine fields.")
            return {key: ("NO" if key.endswith("_check") else "") for key in template_placeholder_contexts.keys()}

    # Extract descriptions for the prompt
    machine_name = machine_data.get("machine_name", "Unknown Machine")
    main_item_desc = machine_data.get("main_item", {}).get("description", "")
    addon_descs = [item.get("description", "") for item in machine_data.get("add_ons", [])]
    common_item_descs = [item.get("description", "") for item in common_items]
    
    prompt_parts = [
        f"You are an AI assistant tasked with accurately extracting information about a SPECIFIC MACHINE from a PDF quote to fill a structured Word template.",
        "You will be given:",
        "  1. A main machine description",
        "  2. Add-on items specifically for this machine",
        "  3. Common items that apply to all machines (warranty, shipping, etc.)",
        "  4. The full PDF text for context",
        "  5. A list of template fields to fill",
        
        f"\nMAIN MACHINE: {machine_name}",
        main_item_desc,
        
        "\nADD-ON ITEMS SPECIFIC TO THIS MACHINE:"
    ]
    
    if not addon_descs:
        prompt_parts.append("  (No specific add-on items for this machine)")
    else:
        for i, desc in enumerate(addon_descs):
            prompt_parts.append(f"  - Add-on {i+1}: {desc}")
    
    prompt_parts.append("\nCOMMON ITEMS (apply to all machines):")
    if not common_item_descs:
        prompt_parts.append("  (No common items identified)")
    else:
        for i, desc in enumerate(common_item_descs):
            prompt_parts.append(f"  - Common Item {i+1}: {desc}")
    
    prompt_parts.append("\nFULL PDF TEXT (for additional context):")
    prompt_parts.append((full_pdf_text[:10000] + "... (text truncated)") if len(full_pdf_text) > 10000 else full_pdf_text)
    
    prompt_parts.append("\nTEMPLATE FIELDS TO FILL (Placeholder Key: Description from template):")
    placeholder_list_for_prompt = []
    for key, context in template_placeholder_contexts.items():
        placeholder_list_for_prompt.append(f"  - '{key}': '{context}'")
    
    if not placeholder_list_for_prompt:
        prompt_parts.append("  (No template fields provided to evaluate.)")
        return {}
    
    for item_for_prompt in placeholder_list_for_prompt:
        prompt_parts.append(item_for_prompt)

    prompt_parts.append("\nYOUR TASK & RESPONSE FORMAT:")
    prompt_parts.append(f"Focus ONLY on the specified machine '{machine_name}' and its add-ons, plus common items.")
    prompt_parts.append("Carefully analyze all provided information.")
    prompt_parts.append("For each TEMPLATE FIELD:")
    prompt_parts.append("  - If the field key ends with '_check' (a checkbox): Determine if it is confirmed as selected for THIS SPECIFIC MACHINE. Value must be \"YES\" or \"NO\".")
    prompt_parts.append("  - If the field key does NOT end with '_check' (a text field): Extract the specific information relevant to THIS MACHINE.")
    prompt_parts.append("Be accurate and conservative. For checkboxes, if unsure, default to \"NO\".")
    prompt_parts.append("For text fields, if not found, use an empty string.")
    prompt_parts.append("Respond with a single, valid JSON object. The keys in the JSON MUST be ALL the TEMPLATE PLACEHOLDER KEYS listed above.")
    prompt_parts.append("\nYour JSON Response:")
    
    prompt = "\n".join(prompt_parts)
    
    # Initialize with default values
    llm_response_data = {key: ("NO" if key.endswith("_check") else "") for key in template_placeholder_contexts.keys()}

    try:
        print(f"Sending machine-specific prompt for '{machine_name}' to Gemini API...")
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
                    if key in llm_response_data: # Only update keys that were expected
                        if key.endswith("_check"):
                            if isinstance(value, str) and value.upper() in ["YES", "NO"]:
                                llm_response_data[key] = value.upper()
                            # else: keep default "NO"
                        else: # It's a text field
                            llm_response_data[key] = str(value) # Assign extracted text
            else:
                print(f"Warning: LLM response for machine '{machine_name}' was not a JSON dictionary: {parsed_llm_output}")
        except json.JSONDecodeError as e:
            print(f"Error decoding LLM JSON response for machine '{machine_name}': {e}")
            print(f"LLM Response Text was: {repr(cleaned_response_text)}")
    except Exception as e:
        print(f"Error communicating with Gemini API or processing response for machine '{machine_name}': {e}")
        traceback.print_exc()

    return llm_response_data

# Example Usage:
if __name__ == '__main__':
    if configure_gemini_client():
        mock_selected_descs_init = [
            "Monoblock Model: FC 11 including 10 inch HMI and B&R PLC, with automatic bottle sorting.",
            "Factory Acceptance Test Protocol",
            "Optional Upgrade: High-speed capping turret."
        ]
        mock_template_contexts_init = {
            "plc_b&r_check": "PLC Controller is B&R",
            "plc_allenb_check": "PLC Controller is Allen Bradley",
            "hmi_size10_check": "HMI Screen Size 10 inches",
            "hmi_size15_check": "HMI Screen Size 15 inches",
            "vd_f_check": "Factory Acceptance Test (FAT)",
            "vd_s_check": "Site Acceptance Test (SAT)",
            "capping_turret_high_speed_check": "High-speed capping turret option",
            "bottle_sorting_auto_check": "Automatic bottle sorting system",
            "other_field_value": "Some other textual value field"
        }
        mock_full_text_init = "The Monoblock has a 10 inch HMI and B&R PLC. Customer: ACME Corp. Quote: Q-123. FAT Protocol is selected. High-speed capping turret is an option."
        
        print("\n--- Mock Test for get_all_fields_via_llm ---")
        initial_results = get_all_fields_via_llm(mock_selected_descs_init, mock_template_contexts_init, mock_full_text_init)
        print("\n--- LLM Processed Data (All Fields) ---")
        for key, value in sorted(initial_results.items()):
            print(f"'{key}': '{value}'")
        
        print("\n---------------------------------------")
        # Test chat update
        current_data_for_chat = initial_results.copy()
        user_instruction_chat = "The customer name is actually 'Beta Corp' and turn off the FAT."

        print("\n--- Mock Test for LLM Chat Update (All Fields) ---")
        updated_results = get_llm_chat_update(current_data_for_chat, user_instruction_chat, mock_selected_descs_init, mock_template_contexts_init, mock_full_text_init)
        print("\n--- LLM Corrected Data (All Fields) ---")
        for key, value in sorted(updated_results.items()):
            print(f"'{key}': '{value}'")

        print("\n---------------------------------------")
        print("\n--- Mock Test for Q&A ---")
        mock_user_q = "What is the HMI screen size?"
        # Use the same full text and contexts for Q&A test for simplicity
        answer = answer_pdf_question(mock_user_q, mock_selected_descs_init, mock_full_text_init, mock_template_contexts_init)
        print(f"Q: {mock_user_q}\nA: {answer}") # Corrected f-string

        mock_user_q_2 = "What is the project number?"
        answer_2 = answer_pdf_question(mock_user_q_2, mock_selected_descs_init, mock_full_text_init, mock_template_contexts_init)
        print(f"\nQ: {mock_user_q_2}\nA: {answer_2}") # Corrected f-string

        print("\n---------------------------------------")
        print("\n--- Mock Test for map_crm_to_document_via_llm (Packing Slip) ---")
        mock_client_crm = {
            "id": 1, "quote_ref": "Q-CRM-PS-001", "customer_name": "PackSlip Customer",
            "machine_model": "Packer 3000", "country_destination": "USA",
            "sold_to_address": "123 Main St\nAnytown, CA 90210", 
            "ship_to_address": "456 Shipping Ln\nOtherville, CA 90211",
            "telephone": "555-1234", "customer_contact_person": "John Doe", "customer_po": "PO-789"
        }
        mock_priced_items_crm = [
            {"id": 10, "client_quote_ref": "Q-CRM-PS-001", "item_description": "Main Packing Unit", "item_quantity": "1", "item_price_str": "5000", "item_price_numeric": 5000.0, "hs_code": "842240"},
            {"id": 11, "client_quote_ref": "Q-CRM-PS-001", "item_description": "Accessory Kit A", "item_quantity": "2", "item_price_str": "250", "item_price_numeric": 250.0, "hs_code": "842290"}
        ]
        # Assume these are placeholders from Paking Slip.docx with their contexts
        mock_packing_slip_template_contexts = {
            "ps_customer_name": "Customer Name for Packing Slip",
            "ps_ship_to_addr1": "Shipping Address Line 1",
            "ps_order_no": "Order Number",
            "ps_item_1_desc": "Line Item 1 Description",
            "ps_item_1_qty": "Line Item 1 Quantity",
            "ps_item_1_hs": "Line Item 1 HS Code",
            "ps_ship_date": "Date of Shipment",
            "ps_packing_slip_no": "Packing Slip ID"
        }

        packing_slip_data = map_crm_to_document_via_llm(
            mock_client_crm, 
            mock_priced_items_crm, 
            mock_packing_slip_template_contexts,
            "Packing Slip"
        )
        # The full output_data_for_document will be printed by the function itself
        # print("\n--- Generated Packing Slip Data ---")
        # for key, value in sorted(packing_slip_data.items()):
        #     print(f"'{key}': '{value}'")
    else:
        print("Failed to configure Gemini client for tests.") 