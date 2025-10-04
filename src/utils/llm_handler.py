import os
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional
import json
import traceback # For more detailed error logging
import re
from src.utils.template_utils import add_section_aware_instructions, DEFAULT_EXPLICIT_MAPPINGS, SORTSTAR_EXPLICIT_MAPPINGS, select_sortstar_basic_system

# Global variable for the model, initialized once
GENERATIVE_MODEL = None

def check_model_usage():
    """
    Sends a minimal test request to check which model is actually being used.
    This can help verify if you're using the model you think you are.
    """
    global GENERATIVE_MODEL
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client():
            print("Error: Could not configure Gemini client to check model usage.")
            return
    
    try:
        # Send a minimal request to check model usage
        print("\n--- Checking Actual Model Usage ---")
        print("Sending test request to Gemini API...")
        
        # Get model info
        model_info = GENERATIVE_MODEL._model_name
        print(f"Model being used according to client: {model_info}")
        
        # Send a minimal request
        response = GENERATIVE_MODEL.generate_content("Say 'hello'")
        print(f"Response received successfully. Characters: {len(response.text)}")
        
        print("✅ Verification complete. If you're still being charged for Gemini 2.5 Pro,")
        print("   check your Google Cloud Console to see all usage under your API key.")
        print("   You may need to create a new API key if you can't identify the source.")
    except Exception as e:
        print(f"Error checking model usage: {e}")
        traceback.print_exc()

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
        
        # Choose model - 1.5 Flash is much cheaper than 2.5 Pro
        model_name = 'gemini-2.5-flash-lite'
        print(f"Initializing Gemini with model: {model_name}")
        
        genai.configure(api_key=api_key)
        GENERATIVE_MODEL = genai.GenerativeModel(model_name)
        
        # Print model details to verify
        print(f"Gemini client configured successfully with model: {model_name}")
        print("IMPORTANT: If you're being billed for Gemini 2.5 Pro, check your Google Cloud billing")
        print("           and make sure no other applications are using your API key.")
        
        return True
    except Exception as e:
        print(f"Error configuring Gemini client: {e}")
        GENERATIVE_MODEL = None
        return False

def apply_post_processing_rules(field_data: Dict[str, str], template_schema: Dict[str, Dict]) -> Dict[str, str]:
    """
    Applies domain-specific rules to correct and improve LLM-generated field values.
    
    Args:
        field_data: Dictionary of field names to values from LLM
        template_schema: Schema information about the fields
        
    Returns:
        Corrected and improved field data
    """
    print("Applying post-processing rules to LLM output...")
    corrected_data = field_data.copy()
    
    # Quick early return if empty data
    if not corrected_data:
        return corrected_data
    
    # Create lookup maps for field types to avoid repetitive checks
    checkbox_fields = set()
    text_fields = set()
    
    # Pre-identify checkbox fields for faster processing
    for field_name in corrected_data.keys():
        # Determine if this is a checkbox field
        is_checkbox = False
        if field_name.endswith('_check'):
            is_checkbox = True
            checkbox_fields.add(field_name)
        elif field_name in template_schema and isinstance(template_schema[field_name], dict):
            is_checkbox = template_schema[field_name].get('type') == 'boolean'
            if is_checkbox:
                checkbox_fields.add(field_name)
        
        if not is_checkbox:
            text_fields.add(field_name)
    
    # Rule 1: Ensure all checkbox fields have correct YES/NO values (normalize casing)
    for field_name in checkbox_fields:
        value = corrected_data[field_name]
        if isinstance(value, str) and value.upper() in ["YES", "NO"]:
            corrected_data[field_name] = value.upper()
        else:
            # Default to NO for invalid values
            print(f"Correcting invalid checkbox value '{value}' to 'NO' for {field_name}")
            corrected_data[field_name] = "NO"
    
    # Extract field groups that we need for specific rules
    # This avoids repeated searches through all fields
    hmi_size_fields = [f for f in checkbox_fields if '_hmi_' in f.lower() and 'size' in f.lower()]
    alt_hmi_size_fields = [f for f in checkbox_fields 
                          if ('hmi' in f.lower() or 'touch' in f.lower() or 'screen' in f.lower()) 
                          and any(s in f.lower() for s in ['15', '10', '5.7', '5_7', '15inch', '10inch'])]
    plc_type_fields = [f for f in checkbox_fields if 'plc_' in f.lower()]
    beacon_fields = [f for f in checkbox_fields if any(term in f.lower() for term in ['beacon', 'light', 'signal'])]
    
    # Rule 2: HMI size constraints - only one HMI size should be YES
    if hmi_size_fields:
        yes_hmi_sizes = [f for f in hmi_size_fields if corrected_data[f] == "YES"]
        if len(yes_hmi_sizes) > 1:
            print(f"Multiple HMI sizes selected ({yes_hmi_sizes}), keeping only the largest/first")
            # Prioritize based on size (larger screens are usually more expensive/premium)
            size_priority = {"15": 1, "10": 2, "5.7": 3, "5_7": 3}
            
            # Find the highest priority (lowest number) size
            best_field = yes_hmi_sizes[0]
            best_priority = 99
            
            for field in yes_hmi_sizes:
                for size, priority in size_priority.items():
                    if size in field and priority < best_priority:
                        best_priority = priority
                        best_field = field
            
            # Set only the best one to YES, others to NO
            for field in hmi_size_fields:
                corrected_data[field] = "YES" if field == best_field else "NO"
    
    # Also look for alternative HMI size field patterns
    if alt_hmi_size_fields and alt_hmi_size_fields != hmi_size_fields:  # Skip if same as already processed
        yes_alt_sizes = [f for f in alt_hmi_size_fields if corrected_data[f] == "YES"]
        if len(yes_alt_sizes) > 1:
            print(f"Multiple alternative HMI sizes selected ({yes_alt_sizes}), keeping only the largest")
            # Determine the largest size
            size_indicators = {"15": 15, "15inch": 15, "10": 10, "10inch": 10, "5.7": 5.7, "5_7": 5.7}
            best_field = yes_alt_sizes[0]
            best_size = 0
            
            for field in yes_alt_sizes:
                for indicator, size in size_indicators.items():
                    if indicator in field.lower() and size > best_size:
                        best_size = size
                        best_field = field
            
            # Set only the best one to YES, others to NO
            for field in alt_hmi_size_fields:
                corrected_data[field] = "YES" if field == best_field else "NO"
    
    # Rule 3: PLC type constraints - only one PLC type should be YES
    if plc_type_fields:
        yes_plc_types = [f for f in plc_type_fields if corrected_data[f] == "YES"]
        if len(yes_plc_types) > 1:
            print(f"Multiple PLC types selected ({yes_plc_types}), keeping only one")
            # Keep only the first one as YES
            for i, field in enumerate(plc_type_fields):
                corrected_data[field] = "YES" if field == yes_plc_types[0] else "NO"
    
    # Rule 4-6: Format utility specifications
    # Process these rules together for better performance
    has_voltage = 'voltage' in corrected_data
    has_hz = 'hz' in corrected_data
    has_psi = 'psi' in corrected_data
    
    if has_voltage or has_hz or has_psi:
        # Rule 4: Standardize voltage format
        if has_voltage:
            voltage_value = corrected_data['voltage']
            if voltage_value:
                # Detect if it's likely a voltage range
                if '-' not in voltage_value and '/' not in voltage_value:
                    try:
                        # If it's a single number, try to determine common range
                        voltage_num = int(''.join(c for c in voltage_value if c.isdigit()))
                        if voltage_num > 100 and voltage_num < 130:
                            corrected_data['voltage'] = "110-120V"
                        elif voltage_num > 200 and voltage_num < 250:
                            corrected_data['voltage'] = "208-240V"
                        elif voltage_num > 380 and voltage_num < 420:
                            corrected_data['voltage'] = "380-400V"
                        elif voltage_num > 460 and voltage_num < 490:
                            corrected_data['voltage'] = "460-480V"
                    except (ValueError, TypeError):
                        # Keep original if conversion fails
                        pass
                
                # Ensure V suffix if missing
                if voltage_value and not voltage_value.upper().endswith('V') and any(c.isdigit() for c in voltage_value):
                    corrected_data['voltage'] = voltage_value + 'V'
        
        # Rule 5: Ensure frequency has Hz suffix
        if has_hz:
            hz_value = corrected_data['hz']
            if hz_value and hz_value.isdigit():
                corrected_data['hz'] = hz_value + ' Hz'
        
        # Rule 6: PSI format standardization
        if has_psi:
            psi_value = corrected_data['psi']
            if psi_value and not 'psi' in psi_value.lower() and any(c.isdigit() for c in psi_value):
                corrected_data['psi'] = psi_value + ' PSI'
    
    # Rule 7: If 'tri-color beacon' is mentioned anywhere, enable all three color beacons
    if beacon_fields:
        # Check if any field mentions multi-color beacon
        has_multicolor = False
        for field in beacon_fields:
            if corrected_data[field] == "YES" and any(term in field.lower() for term in ['tri', 'three', 'multi']):
                has_multicolor = True
                break
        
        # Find individual color beacon fields
        color_beacon_fields = ['beacon_red_check', 'beacon_amber_check', 'beacon_green_check', 'beacon_yellow_check']
        color_beacon_fields = [f for f in color_beacon_fields if f in corrected_data]
        
        if color_beacon_fields:
            # If at least one beacon is set to YES, check if others should be too
            yes_beacon_count = sum(1 for f in color_beacon_fields if corrected_data[f] == "YES")
            if yes_beacon_count >= 2 or has_multicolor:
                # If multiple colors are already YES or we detected a multi-color beacon reference,
                # set all standard colors to YES
                print("Setting all standard beacon colors to YES based on multi-color beacon detection")
                for field in color_beacon_fields:
                    corrected_data[field] = "YES"
    
    # Rule 8: Production speed formatting
    if 'production_speed' in corrected_data:
        speed = corrected_data['production_speed']
        if speed:
            # Try to ensure speed has units
            if all(not c.isalpha() for c in speed) and any(c.isdigit() for c in speed):
                # No letters but has numbers - add units
                if any('bottle' in field_name.lower() for field_name in corrected_data.keys()):
                    corrected_data['production_speed'] = speed + ' bottles per minute'
                else:
                    corrected_data['production_speed'] = speed + ' units per minute'
    
    # Rule 9: Cross-field validation - if filling system is selected, ensure appropriate filling type
    filling_system_field = next((f for f in checkbox_fields if 'filling_system' in f.lower() and corrected_data[f] == "YES"), None)
    if filling_system_field:
        filling_type_fields = [f for f in checkbox_fields if any(typ in f.lower() for typ in ['volumetric', 'peristaltic', 'time_pressure', 'mass_flow'])]
        if filling_type_fields and not any(corrected_data.get(f) == "YES" for f in filling_type_fields):
            # Default to volumetric if available (most common)
            volumetric_field = next((f for f in filling_type_fields if 'volumetric' in f.lower()), None)
            if volumetric_field:
                print(f"Setting {volumetric_field} to YES as default filling type")
                corrected_data[volumetric_field] = "YES"
    
    # Rule 10: Explosion proof consistency
    if 'explosion_proof_check' in corrected_data and corrected_data['explosion_proof_check'] == "YES":
        print("Explosion proof selected - ensuring consistent related fields")
        # In explosion proof environments, typically pneumatic components are used instead of electric
        pneumatic_fields = [f for f in checkbox_fields if 'pneumatic' in f.lower()]
        for field in pneumatic_fields:
            corrected_data[field] = "YES"  # Set pneumatic options to YES
            
        # Disable certain electric components that would be replaced in explosion proof environments
        electric_fields_to_disable = [
            f for f in checkbox_fields 
            if any(term in f.lower() for term in ['electric', 'servo', 'motor']) 
            and 'explosion' not in f.lower()
        ]
        for field in electric_fields_to_disable:
            if corrected_data[field] == "YES":
                print(f"Setting {field} to NO due to explosion proof environment")
                corrected_data[field] = "NO"
    
    # Rule 11: SortStar Basic Machine Configuration - ensure only one is YES
    sortstar_basic_config_fields = [
        "bs_984_check", "bs_1230_check", "bs_985_check", 
        "bs_1229_check", "bs_1264_check", "bs_1265_check"
    ]
    # Filter to only fields present in the current data
    active_sortstar_config_fields = [f for f in sortstar_basic_config_fields if f in corrected_data]
    
    if active_sortstar_config_fields: # Only run if any of these fields are actually in the data
        yes_sortstar_configs = [f for f in active_sortstar_config_fields if corrected_data.get(f) == "YES"]
        
        if len(yes_sortstar_configs) > 1:
            print(f"Warning: Multiple SortStar basic configurations selected: {yes_sortstar_configs}. Enforcing single selection.")
            # Keep the first one found as YES, set others to NO
            # A more sophisticated priority could be defined if needed, but for now, first encountered wins.
            first_yes_found = False
            for field_name in sortstar_basic_config_fields: # Iterate in defined order to ensure some consistency
                if field_name in corrected_data:
                    if corrected_data[field_name] == "YES":
                        if not first_yes_found:
                            first_yes_found = True
                            # This one stays YES
                        else:
                            corrected_data[field_name] = "NO" # Subsequent ones become NO
            print(f"Corrected SortStar basic configurations. Kept: {[f for f in active_sortstar_config_fields if corrected_data.get(f) == 'YES']}")
        elif not yes_sortstar_configs and any(f in corrected_data and corrected_data.get(f) is not None for f in active_sortstar_config_fields):
            # This case is tricky: if a sortstar machine is being processed, one of these *should* be yes.
            # However, this rule is for post-processing LLM output. If LLM says all are NO, this rule won't force one to YES.
            # That level of correction would require more context (knowing for sure it's a SortStar and which one).
            # For now, we just ensure there isn't *more than one* YES.
            pass

    return corrected_data

def get_all_fields_via_llm(selected_pdf_descriptions: List[str], 
                             template_placeholder_contexts: Dict[str, str],
                             full_pdf_text: str) -> Dict[str, str]:
    """
    Constructs a comprehensive prompt for the LLM to fill all template fields
    (checkboxes and text fields) based on selected PDF items and full PDF text.
    
    The function now better handles enhanced context from the outline file.
    """
    global GENERATIVE_MODEL
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
                    
                    if subsection:
                        prompt_parts.append(f"  - '{key}': [{subsection}] {desc}{synonym_text}{indicator_text}")
                    else:
                        prompt_parts.append(f"  - '{key}': {desc}{synonym_text}{indicator_text}")
        
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
    
    # Apply post-processing rules to improve the data
    corrected_data = apply_post_processing_rules(updated_data, template_placeholder_contexts)
    
    # Record user feedback for few-shot learning improvement
    try:
        from src.utils.few_shot_learning import record_user_feedback_on_extraction
        from src.utils.few_shot_learning import determine_machine_type
        
        # Try to determine machine type from context (this might not always be available in chat)
        machine_name = "Unknown"  # Default fallback
        if selected_pdf_descriptions:
            # Try to extract machine name from first description
            first_desc = selected_pdf_descriptions[0]
            if "machine" in first_desc.lower() or "system" in first_desc.lower():
                machine_name = first_desc.split('\n')[0] if '\n' in first_desc else first_desc[:50]
        
        machine_type = determine_machine_type(machine_name)
        
        # Record feedback for fields that were changed
        for field_name in corrected_data:
            original_value = current_data.get(field_name, "")
            new_value = corrected_data.get(field_name, "")
            
            # If the value changed due to user instruction, record it as feedback
            if original_value != new_value:
                record_user_feedback_on_extraction(
                    field_name=field_name,
                    original_value=original_value,
                    corrected_value=new_value,
                    feedback_type="correction",
                    machine_type=machine_type,
                    template_type="default",  # Could be enhanced to detect template type
                    user_context=user_instruction
                )
                print(f"Recorded feedback for field '{field_name}': '{original_value}' -> '{new_value}'")
        
    except Exception as e:
        print(f"Error recording user feedback: {e}")
    
    return corrected_data

def answer_pdf_question(user_question: str, 
                        selected_pdf_descriptions: List[str], 
                        full_pdf_text: str, 
                        template_placeholder_contexts: Optional[Dict[str, str]] = None) -> str:
    """
    Answers a user's question based on the provided PDF content (selected items and full text).
    Optionally uses template contexts if questions might refer to template field names.
    Uses retrieval-augmented prompting to handle long PDFs more effectively.
    """
    global GENERATIVE_MODEL
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client():
            return "Error: LLM client not configured. Please check API key."

    # Performance tracking
    import time
    start_time = time.time()

    # Implement retrieval-augmented prompting for long PDFs
    def chunk_pdf_text(text, chunk_size=800, overlap=150, max_chunks=50):
        """Split text into overlapping chunks for better context preservation."""
        chunks = []
        if not text or len(text) <= chunk_size:
            return [text] if text else []
            
        start = 0
        while start < len(text) and len(chunks) < max_chunks:
            end = min(start + chunk_size, len(text))
            # Try to find a sensible break point (newline or period)
            if end < len(text):
                # Look for newline first
                newline_pos = text.rfind('\n', start, end)
                period_pos = text.rfind('. ', start, end)
                if newline_pos > start + chunk_size // 2:
                    end = newline_pos + 1  # Include the newline
                elif period_pos > start + chunk_size // 2:
                    end = period_pos + 2  # Include the period and space
            
            chunks.append(text[start:end])
            start = end - overlap  # Create overlap with previous chunk
        
        print(f"Created {len(chunks)} chunks from {len(text)} characters of text")
        return chunks
    
    def score_chunk_relevance(query, chunk):
        """
        Score chunk relevance to the query using simple keyword matching.
        A more sophisticated approach would use embeddings and semantic similarity.
        """
        query_terms = query.lower().split()
        # Remove common words
        stopwords = {'the', 'and', 'is', 'of', 'in', 'to', 'a', 'for', 'with', 'on', 'what', 'how', 'why', 'can', 'does', 'do'}
        query_terms = [term for term in query_terms if term not in stopwords and len(term) > 2]
        
        if not query_terms:
            return 0  # No meaningful terms to match
            
        score = 0
        chunk_lower = chunk.lower()
        
        # Score based on term frequency
        for term in query_terms:
            term_count = chunk_lower.count(term)
            score += term_count * 2  # Weight term matches
            
        # Score based on phrase matches (more weight)
        query_phrases = [' '.join(query_terms[i:i+2]) for i in range(len(query_terms)-1)]
        for phrase in query_phrases:
            if len(phrase.split()) > 1:  # Only count actual phrases
                phrase_count = chunk_lower.count(phrase)
                score += phrase_count * 5  # Higher weight for phrase matches
                
        # Normalize by chunk length to avoid bias toward longer chunks
        return score / (len(chunk) / 100) if chunk else 0
    
    # Process the PDF text
    if len(full_pdf_text) > 8000:
        print(f"PDF text is long ({len(full_pdf_text)} chars). Using retrieval-augmented prompting.")
        
        # Chunking phase
        chunk_time_start = time.time()
        chunks = chunk_pdf_text(full_pdf_text, max_chunks=40)  # Limit to 40 chunks maximum
        chunk_time = time.time() - chunk_time_start
        print(f"Chunking completed in {chunk_time:.2f} seconds")
        
        # Scoring phase
        scoring_time_start = time.time()
        scored_chunks = [(chunk, score_chunk_relevance(user_question, chunk)) for chunk in chunks]
        scoring_time = time.time() - scoring_time_start
        print(f"Scoring completed in {scoring_time:.2f} seconds")
        
        # Sort chunks by relevance score in descending order
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        # Select the top relevant chunks (up to a token limit)
        top_chunks = []
        total_chars = 0
        max_chars = 8000  # Reduced token limit for better performance
        max_top_chunks = 10  # Limit the number of top chunks
        
        for chunk, score in scored_chunks:
            if score > 0 and total_chars + len(chunk) <= max_chars and len(top_chunks) < max_top_chunks:
                top_chunks.append(chunk)
                total_chars += len(chunk)
                print(f"Added chunk with score {score:.2f}, length {len(chunk)}")
                
        # Always include the beginning of the document (first chunk) for context
        if chunks and chunks[0] not in top_chunks and total_chars + len(chunks[0]) <= max_chars:
            top_chunks.insert(0, chunks[0])
            print(f"Added first chunk for context, length {len(chunks[0])}")
            
        # Create a context summary with metadata
        relevant_text = "\n\n==== CHUNK BREAK ====\n\n".join(top_chunks)
        context_note = f"[PDF document chunked for retrieval. Showing {len(top_chunks)} most relevant chunks out of {len(chunks)} total.]"
        
        print(f"Final content for LLM: {len(relevant_text)} characters")
    else:
        relevant_text = full_pdf_text
        context_note = "[Full PDF text included - document is within token limits]"
        print(f"Using full PDF text: {len(relevant_text)} characters")

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
    
    prompt_parts.append(f"\n2. PDF TEXT CONTEXT: {context_note}")
    prompt_parts.append(relevant_text)

    # Optionally add template contexts if questions might refer to template field names
    if template_placeholder_contexts:
        prompt_parts.append("\n3. TEMPLATE FIELDS (Context for potential questions referring to template field names - Placeholder Key: Description from template):")
        placeholder_list_for_prompt = []
        for key, context in template_placeholder_contexts.items():
            # Limit the number of template fields to include to avoid token limits
            if len(placeholder_list_for_prompt) < 50:  # Only include up to 50 fields
                placeholder_list_for_prompt.append(f"  - '{key}': '{context}'")
        if not placeholder_list_for_prompt:
            prompt_parts.append("  (No template fields context provided.)")
        else:
            prompt_parts.append(f"  (Showing {len(placeholder_list_for_prompt)} template fields)")
            for item_for_prompt in placeholder_list_for_prompt:
                prompt_parts.append(item_for_prompt)

    prompt_parts.append("\nYOUR ANSWER TO THE USER'S QUESTION:")
    
    prompt = "\n".join(prompt_parts)

    # print("\n----- LLM Q&A PROMPT -----") # Uncomment for debugging
    # print(prompt)
    # print("------------------------")

    try:
        print(f"RAG processing completed in {time.time() - start_time:.2f} seconds")
        print("Sending Q&A prompt to Gemini API...")
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        llm_start_time = time.time()
        response = GENERATIVE_MODEL.generate_content(prompt, safety_settings=safety_settings)
        print(f"LLM response received in {time.time() - llm_start_time:.2f} seconds")
        
        # print("\n----- LLM Q&A RAW RESPONSE -----") # Uncomment for debugging
        # print(response.text)
        # print("----------------------------")
        
        total_time = time.time() - start_time
        print(f"Total answer_pdf_question processing time: {total_time:.2f} seconds")
        
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

def get_machine_specific_fields_via_llm(machine_data: Dict, 
                                       common_items: List[Dict],
                                       template_placeholder_contexts: Dict[str, str],
                                       full_pdf_text: str) -> Dict[str, str]:
    """
    Identifies relevant fields for a specific machine and its add-ons,
    then uses LLM to fill only those fields based on the machine data,
    common items, and the full PDF text.
    """
    global GENERATIVE_MODEL
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client():
            print("LLM client not configured. Returning empty data for machine-specific fields.")
            return {key: ("NO" if key.endswith("_check") else "") for key in template_placeholder_contexts.keys()}

    machine_name = machine_data.get("machine_name", "Unknown Machine")
    main_item_desc = machine_data.get("main_item", {}).get("description", "")
    add_on_descs = [item.get("description", "") for item in machine_data.get("add_ons", [])]
    common_item_descs = [item.get("description", "") for item in common_items]

    # Determine if this is a SortStar machine
    is_sortstar_machine = False
    # Use regex for whole-word matching to avoid matching "monostar"
    sortstar_pattern = r'\b(sortstar|unscrambler|bottle unscrambler)\b'
    if re.search(sortstar_pattern, machine_name.lower()):
        is_sortstar_machine = True

    # Import few-shot learning module
    try:
        from src.utils.few_shot_learning import enhance_prompt_with_few_shot_examples
        few_shot_available = True
    except ImportError:
        few_shot_available = False
        print("Few-shot learning module not available, using standard prompts")

    # Simplified prompt focusing on the specific machine and its direct context
    prompt_parts = [
        "You are an AI assistant specializing in extracting information from packaging machinery quotes.",
        f"You are focusing on a specific machine: '{machine_name}'.",
        "You will be given:",
        "  1. The 'MAIN ITEM DESCRIPTION' for this machine.",
        "  2. A list of 'ADD-ON ITEMS' specifically associated with this machine.",
        "  3. A list of 'COMMON/SHARED ITEMS' that might apply to multiple machines in the quote.",
        "  4. The 'FULL PDF TEXT' of the entire quote for broader context.",
        "  5. A list of 'TEMPLATE FIELDS' with their descriptions/contexts that need to be filled for this machine.",
        
        "\nFULL PDF TEXT (Refer to this for general project details or if item descriptions are brief. Prioritize the start of document. Max 10,000 chars shown):",
        (full_pdf_text[:10000] + "... (text truncated)") if len(full_pdf_text) > 10000 else full_pdf_text,
        
        f"\nMAIN ITEM DESCRIPTION for {machine_name}:",
        main_item_desc if main_item_desc else "(No main item description provided for this machine)",
        
        "\nADD-ON ITEMS for this machine:"
    ]
    if not add_on_descs:
        prompt_parts.append("  (No specific add-on items listed for this machine)")
    else:
        for i, desc in enumerate(add_on_descs):
            prompt_parts.append(f"  - Add-on {i+1}: {desc}")
            
    prompt_parts.append("\nCOMMON/SHARED ITEMS (Consider if relevant to this machine):")
    if not common_item_descs:
        prompt_parts.append("  (No common/shared items listed)")
    else:
        for i, desc in enumerate(common_item_descs):
            prompt_parts.append(f"  - Common Item {i+1}: {desc}")

    # Field listing (similar to get_all_fields_via_llm but could be tailored further if needed)
    # For now, using the same comprehensive listing method
    using_schema_format = isinstance(next(iter(template_placeholder_contexts.values()), ""), dict)
    if using_schema_format:
        sections = {}
        for key, field_info in template_placeholder_contexts.items():
            section = field_info.get("section", "General")
            if section not in sections: sections[section] = []
            sections[section].append((key, field_info))
        
        prompt_parts.append("\nTEMPLATE FIELDS TO FILL (organized by section):")
        for section, fields in sorted(sections.items()):
            prompt_parts.append(f"\n## {section} SECTION:")
            text_fields = [f for f in fields if f[1].get("type") == "string"]
            checkbox_fields = [f for f in fields if f[1].get("type") == "boolean"]
            if text_fields:
                prompt_parts.append("TEXT FIELDS:")
                for key, field_info in text_fields:
                    desc = field_info.get("description", key)
                    subsection = field_info.get("subsection", "")
                    prompt_parts.append(f"  - '{key}': [{subsection if subsection else section}] {desc}")
            if checkbox_fields:
                prompt_parts.append("CHECKBOX FIELDS (must be YES or NO):")
                for key, field_info in checkbox_fields:
                    desc = field_info.get("description", key)
                    subsection = field_info.get("subsection", "")
                    prompt_parts.append(f"  - '{key}': [{subsection if subsection else section}] {desc}")
    else: # Hierarchical context format
        sections = {}
        for key, context in template_placeholder_contexts.items():
            parts = context.split(" - "); section = parts[0] if parts else "General"
            if section not in sections: sections[section] = {}
            subsection = parts[1] if len(parts) > 1 else "General"
            if subsection not in sections[section]: sections[section][subsection] = []
            sections[section][subsection].append((key, context))
        prompt_parts.append("\nTEMPLATE FIELDS TO FILL (organized by section and subsection):")
        for section, subsections in sorted(sections.items()):
            prompt_parts.append(f"\n## {section} SECTION:")
            for subsection, fields in sorted(subsections.items()):
                if subsection != "General": prompt_parts.append(f"\n### {subsection} Subsection:")
                checkbox_fields = [(k, c) for k, c in fields if k.endswith('_check')]
                text_fields = [(k, c) for k, c in fields if not k.endswith('_check')]
                if text_fields: prompt_parts.append("TEXT FIELDS:"); [prompt_parts.append(f"  - '{k}': {c.split(' - ')[-1]}") for k,c in text_fields]
                if checkbox_fields: prompt_parts.append("CHECKBOX FIELDS (must be YES or NO):"); [prompt_parts.append(f"  - '{k}': {c.split(' - ')[-1]}") for k,c in checkbox_fields]

    prompt_parts.extend([
        "\nYOUR TASK & RESPONSE FORMAT:",
        "Carefully analyze the MAIN ITEM DESCRIPTION, ADD-ON ITEMS, COMMON/SHARED ITEMS, and FULL PDF TEXT.",
        "For each TEMPLATE FIELD:",
        "  - If it's a CHECKBOX (_check): Determine if confirmed (YES/NO). Prioritize specific mentions in item descriptions.",
        "  - If it's a TEXT field: Extract information. If not found, use an empty string (\"\").",
        "  - Production Speed: Prioritize speeds mentioned in the MAIN ITEM DESCRIPTION over general project speeds.",
        "Bundled features (e.g., 'Including: Feature X') mean corresponding _check fields are YES.",
        "If unsure for a checkbox, default to NO. If a category (e.g., 'Validation Documents') is entirely unmentioned, set its checkboxes to NO.",
    ])

    if is_sortstar_machine:
        prompt_parts.extend([
            "\nIMPORTANT FOR SORTSTAR BASIC SYSTEMS CONFIGURATION:",
            "The template contains several checkboxes for 'BASIC SYSTEMS > Mechanical Basic Machine configuration' like:",
            "  - 'bs_984_check': Sortstar 18ft3 220VAC 3 Phases LEFT TO RIGHT",
            "  - 'bs_1230_check': Sortstar 18ft3 220VAC 3 Phases RIGHT TO LEFT",
            "  - 'bs_985_check': Sortstar 18ft3 480VAC & 380VAC 3 Phases LEFT TO RIGHT",
            "  - 'bs_1229_check': Sortstar 18ft3 480VAC & 380VAC 3 Phases RIGHT TO LEFT",
            "  - 'bs_1264_check': Sortstar 24ft3 220VAC 3 Phases LEFT TO RIGHT",
            "  - 'bs_1265_check': Sortstar 24ft3 480VAC & 380VAC 3 Phases LEFT TO RIGHT",
            "These options are MUTUALLY EXCLUSIVE. Only ONE of these 'bs_XXXX_check' fields should be YES.",
            "Determine the correct configuration (size, voltage, and direction) for THIS SPECIFIC SORTSTAR from the quote details (especially the MAIN ITEM DESCRIPTION) and set only the corresponding checkbox to YES. All other 'bs_XXXX_check' fields in this group must be NO.",
            "For example, if the quote specifies a 'Sortstar 24ft3 220VAC Left to Right', then 'bs_1264_check' should be YES and all other bs_..._check for basic configuration should be NO."
        ])

    # Enhance prompt with few-shot examples if available
    if few_shot_available:
        try:
            prompt_parts = enhance_prompt_with_few_shot_examples(
                prompt_parts=prompt_parts,
                machine_data=machine_data,
                template_placeholder_contexts=template_placeholder_contexts,
                common_items=common_items,
                full_pdf_text=full_pdf_text,
                max_examples_per_field=2
            )
            print("Enhanced prompt with few-shot examples")
        except Exception as e:
            print(f"Error enhancing prompt with few-shot examples: {e}")

    prompt_parts.extend([
        "Respond with a single, valid JSON object. Keys MUST be ALL the TEMPLATE PLACEHOLDER KEYS, values their extracted text or YES/NO.",
        "\nEXAMPLE JSON RESPONSE FORMAT:",
        '''{
  "machine_model": "SortStar 18ft3", 
  "production_speed": "Not Specified for this item",
  "bs_984_check": "YES",
  "bs_1230_check": "NO",
  "op_2409_check": "NO",
  ... (all other fields listed in TEMPLATE FIELDS section)
}
''',
        "\nYour JSON Response:"
    ])
    
    prompt = "\n".join(prompt_parts)

    # print("\n----- LLM PROMPT (machine-specific fields) -----") 
    # print(prompt)
    # print("--------------------------------------------\n")

    # Initialize with default values based on all template placeholders
    llm_response_data = {key: ("NO" if key.endswith("_check") else "") for key in template_placeholder_contexts.keys()}

    try:
        print("Sending machine-specific prompt to Gemini API...")
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
    
    # For SortStar machines, use our specialized function to select the correct basic system
    if is_sortstar_machine:
        print("Detected SortStar machine - applying specialized basic system selection logic")
        basic_systems = select_sortstar_basic_system(machine_data, full_pdf_text)
        
        # Add these selections to the response data
        for key, value in basic_systems.items():
            corrected_data[key] = value
            print(f"SortStar basic system selection: {key} = {value}")
    
    # Save successful extractions as few-shot examples for future learning
    if few_shot_available:
        try:
            from src.utils.few_shot_learning import (
                save_successful_extraction_as_example, determine_machine_type
            )
            
            machine_type = determine_machine_type(machine_name)
            template_type = "sortstar" if is_sortstar_machine else "default"
            source_machine_id = machine_data.get("id")  # If available from database
            
            # Save examples for fields that have meaningful values
            for field_name, field_value in corrected_data.items():
                # Only save examples for fields with meaningful values
                if field_value and field_value not in ["", "NO", "Not Specified", "None"]:
                    # For checkboxes, only save "YES" values as examples
                    if field_name.endswith("_check") and field_value == "YES":
                        save_successful_extraction_as_example(
                            field_name=field_name,
                            field_value=field_value,
                            machine_data=machine_data,
                            common_items=common_items,
                            full_pdf_text=full_pdf_text,
                            machine_type=machine_type,
                            template_type=template_type,
                            source_machine_id=source_machine_id,
                            confidence_score=0.9  # High confidence for successful extractions
                        )
                    # For text fields, save if they have meaningful content
                    elif not field_name.endswith("_check") and len(str(field_value).strip()) > 3:
                        save_successful_extraction_as_example(
                            field_name=field_name,
                            field_value=str(field_value),
                            machine_data=machine_data,
                            common_items=common_items,
                            full_pdf_text=full_pdf_text,
                            machine_type=machine_type,
                            template_type=template_type,
                            source_machine_id=source_machine_id,
                            confidence_score=0.8  # Good confidence for text fields
                        )
            
            print(f"Saved few-shot examples for {machine_type} {template_type} template")
            
        except Exception as e:
            print(f"Error saving few-shot examples: {e}")
    
    return corrected_data

# Example Usage:
if __name__ == '__main__':
    # First run the model check to verify which model we're using
    check_model_usage()
    
    print("\n--- Running additional tests if needed ---")
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