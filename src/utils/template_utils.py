import re
from typing import List, Set, Dict, Optional
from docx import Document
import os # Added for __main__ example

def extract_placeholders(template_path: str) -> List[str]:
    """Reads the template and extracts all unique, cleaned placeholder keys."""
    print(f"Extracting placeholders from: {template_path}")
    placeholders: Set[str] = set()
    try:
        doc = Document(template_path)
        regex = re.compile(r"{{\s*(.*?)\s*}}")

        for para in doc.paragraphs:
            for match in regex.findall(para.text):
                cleaned_key = match.strip()
                if cleaned_key:
                    placeholders.add(cleaned_key)
        
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for match in regex.findall(cell.text):
                        cleaned_key = match.strip()
                        if cleaned_key:
                            placeholders.add(cleaned_key)
                            
        if not placeholders:
             print(f"Warning: No placeholders found in {template_path}")
             return []

        print(f"Found {len(placeholders)} unique placeholders.")
        return sorted(list(placeholders))
    except Exception as e:
        print(f"Error reading placeholders from template '{template_path}': {e}")
        return []

def is_likely_section_header(paragraph) -> bool:
    """Heuristically determines if a paragraph is a section header."""
    text = paragraph.text.strip()
    if not text: # Empty paragraphs are not headers
        return False
    
    # Condition 1: All caps and relatively short
    if text.isupper() and len(text.split()) < 7:
        return True
        
    # Condition 2: Ends with a colon and is relatively short
    # if text.endswith(":") and len(text.split()) < 7:
    #     return True # This might be too broad, catching field labels

    # Condition 3: Bold text (check first run)
    if paragraph.runs and paragraph.runs[0].bold and len(text.split()) < 7:
        # Further check: not too many lowercase letters if it's mostly uppercase (e.g. avoids bolded sentences)
        if sum(1 for char in text if char.islower()) < len(text) / 2:
             return True
    
    # Condition 4: Check for specific heading styles if used consistently in template
    # for style_name_part in ["heading 1", "heading 2", "heading 3", "title"]:
    #     if paragraph.style and paragraph.style.name and style_name_part in paragraph.style.name.lower():
    #         return True
            
    # Add more heuristics as needed (e.g., font size significantly larger than body text)
    return False

def extract_placeholder_context_hierarchical(template_path: str) -> Dict[str, str]:
    """
    Parses the template to extract placeholders and attempts to build hierarchical context
    by identifying section headers.
    """
    print(f"Extracting hierarchical placeholder context from: {template_path}")
    context_map: Dict[str, str] = {}
    try:
        doc = Document(template_path)
        regex = re.compile(r"{{\s*(.*?)\s*}}")
        
        current_section_header = "General" # Default section
        current_subsection_header = ""

        # First pass: Identify all placeholders and their immediate cell/paragraph text
        # Store as: {placeholder: {"immediate": "text", "table_rc": (table_idx, r, c) or None, "para_idx": p_idx or None}}
        placeholder_details = {}

        for p_idx, para in enumerate(doc.paragraphs):
            para_text = para.text.strip()
            if is_likely_section_header(para):
                # Very basic subsection detection: if a new header is found while a section header is active
                # This doesn't handle deep nesting well without style checks.
                # For now, let's assume one level of sectioning for simplicity of header capture.
                # A more robust way would be to check styles (Heading 1, Heading 2, etc.)
                current_section_header = para_text.replace(":","").strip()
                current_subsection_header = "" # Reset subsection on new main section
                # print(f"DEBUG: New Section Header: {current_section_header}")
                continue # Don't look for placeholders in headers themselves
            
            # Heuristic for subsection: If text is bold and short but not ALL CAPS
            elif para.runs and para.runs[0].bold and len(para_text.split()) < 5 and not para_text.isupper() and para_text.endswith(":"):
                current_subsection_header = para_text.replace(":","").strip()
                # print(f"DEBUG: New Sub-Section Header: {current_subsection_header}")
                continue

            for r_match in regex.finditer(para_text):
                ph_key = r_match.group(1).strip()
                if ph_key and ph_key not in placeholder_details:
                    preceding_text = para_text[:r_match.start()].strip()
                    preceding_text = regex.sub("", preceding_text).strip().replace(":","").strip()
                    placeholder_details[ph_key] = {
                        "immediate_label": preceding_text if preceding_text else ph_key,
                        "section": current_section_header,
                        "subsection": current_subsection_header,
                        "type": "paragraph"
                    }

        for t_idx, table in enumerate(doc.tables):
            current_table_group_label = "" # For labels like HMI, PLC in the first column spanning rows
            for r_idx, row in enumerate(table.rows):
                # Try to detect a group label in the first column if it spans or is consistent
                if len(row.cells) > 0:
                    first_cell_text = row.cells[0].text.strip()
                    if first_cell_text and not regex.search(first_cell_text) and len(first_cell_text.split()) < 4:
                        # Heuristic: if this cell is different from the one above it in the same column, 
                        # or if it's the first row, it might be a new group label for subsequent rows.
                        if r_idx == 0 or (r_idx > 0 and table.cell(r_idx,0).text != table.cell(r_idx-1,0).text):
                            current_table_group_label = first_cell_text.replace(":","").strip()
                        elif not current_table_group_label: # If still no group label, take from first row, first cell
                            current_table_group_label = first_cell_text.replace(":","").strip()
                
                for c_idx, cell in enumerate(row.cells):
                    cell_text = cell.text.strip()
                    for r_match in regex.finditer(cell_text):
                        ph_key = r_match.group(1).strip()
                        if ph_key and ph_key not in placeholder_details: # Prioritize paragraph context if already found
                            immediate_label = ""
                            if c_idx > 0: # Label to the left
                                label_cell_text = row.cells[c_idx-1].text.strip().replace(":","").strip()
                                if label_cell_text and not regex.search(label_cell_text):
                                    immediate_label = label_cell_text
                            if not immediate_label: # Text before in current cell
                                immediate_label = cell_text[:r_match.start()].strip().replace(":","").strip()
                            
                            placeholder_details[ph_key] = {
                                "immediate_label": immediate_label if immediate_label else ph_key,
                                "section": current_section_header,
                                "subsection": current_subsection_header, # Could be overridden by table group
                                "table_group": current_table_group_label if current_table_group_label != immediate_label else "",
                                "type": "table"
                            }

        # Construct final context strings
        for ph_key, details in placeholder_details.items():
            parts = []
            if details.get("section") and details["section"] != "General": parts.append(details["section"])
            if details.get("subsection"): parts.append(details["subsection"])
            if details.get("table_group"): parts.append(details["table_group"])
            if details.get("immediate_label") and details["immediate_label"] != ph_key: parts.append(details["immediate_label"])
            
            if parts:
                context_map[ph_key] = " - ".join(filter(None, parts))
            else:
                context_map[ph_key] = ph_key # Fallback

        # Ensure all placeholders from extract_placeholders have some context
        all_phs = extract_placeholders(template_path)
        for ph in all_phs:
            if ph not in context_map:
                context_map[ph] = ph # Default if missed

        if not context_map: print(f"Warning: No placeholder context generated for {template_path}")
        else: print(f"Generated hierarchical context for {len(context_map)} placeholders.")
        return context_map

    except Exception as e:
        print(f"Error extracting hierarchical placeholder context from '{template_path}': {e}")
        import traceback
        traceback.print_exc()
        return {}

def extract_placeholder_schema(template_path: str) -> Dict[str, Dict]:
    """
    Creates a structured JSON schema from the template with rich metadata about each field.
    
    Returns a dictionary where:
    - Each key is a placeholder name
    - Each value is a dictionary with:
        - type: "string" or "boolean" (for _check fields)
        - section: The main section this field belongs to
        - subsection: The subsection if applicable
        - description: A human-readable description of the field
        - location: Where in the document the field appears (paragraph or table)
        - synonyms: List of alternative terms (for checkboxes)
        - positive_indicators: List of phrases that indicate the checkbox should be YES
        
    This schema is designed to be used by LLMs to better understand the template structure.
    """
    print(f"Extracting JSON schema from template: {template_path}")
    
    # First, use the existing function to get the placeholder details
    placeholder_details = {}
    schema = {}
    
    try:
        doc = Document(template_path)
        regex = re.compile(r"{{\s*(.*?)\s*}}")
        
        current_section_header = "General" # Default section
        current_subsection_header = ""

        # First pass: Identify all placeholders and their immediate cell/paragraph text
        for p_idx, para in enumerate(doc.paragraphs):
            para_text = para.text.strip()
            if is_likely_section_header(para):
                current_section_header = para_text.replace(":","").strip()
                current_subsection_header = "" # Reset subsection on new main section
                continue
            
            # Heuristic for subsection: If text is bold and short but not ALL CAPS
            elif para.runs and para.runs[0].bold and len(para_text.split()) < 5 and not para_text.isupper() and para_text.endswith(":"):
                current_subsection_header = para_text.replace(":","").strip()
                continue

            for r_match in regex.finditer(para_text):
                ph_key = r_match.group(1).strip()
                if ph_key and ph_key not in placeholder_details:
                    preceding_text = para_text[:r_match.start()].strip()
                    preceding_text = regex.sub("", preceding_text).strip().replace(":","").strip()
                    placeholder_details[ph_key] = {
                        "immediate_label": preceding_text if preceding_text else ph_key,
                        "section": current_section_header,
                        "subsection": current_subsection_header,
                        "type": "paragraph"
                    }

        for t_idx, table in enumerate(doc.tables):
            current_table_group_label = "" # For labels like HMI, PLC in the first column spanning rows
            for r_idx, row in enumerate(table.rows):
                # Try to detect a group label in the first column if it spans or is consistent
                if len(row.cells) > 0:
                    first_cell_text = row.cells[0].text.strip()
                    if first_cell_text and not regex.search(first_cell_text) and len(first_cell_text.split()) < 4:
                        # Heuristic: if this cell is different from the one above it in the same column, 
                        # or if it's the first row, it might be a new group label for subsequent rows.
                        if r_idx == 0 or (r_idx > 0 and table.cell(r_idx,0).text != table.cell(r_idx-1,0).text):
                            current_table_group_label = first_cell_text.replace(":","").strip()
                        elif not current_table_group_label: # If still no group label, take from first row, first cell
                            current_table_group_label = first_cell_text.replace(":","").strip()
                
                for c_idx, cell in enumerate(row.cells):
                    cell_text = cell.text.strip()
                    for r_match in regex.finditer(cell_text):
                        ph_key = r_match.group(1).strip()
                        if ph_key and ph_key not in placeholder_details: # Prioritize paragraph context if already found
                            immediate_label = ""
                            if c_idx > 0: # Label to the left
                                label_cell_text = row.cells[c_idx-1].text.strip().replace(":","").strip()
                                if label_cell_text and not regex.search(label_cell_text):
                                    immediate_label = label_cell_text
                            if not immediate_label: # Text before in current cell
                                immediate_label = cell_text[:r_match.start()].strip().replace(":","").strip()
                            
                            placeholder_details[ph_key] = {
                                "immediate_label": immediate_label if immediate_label else ph_key,
                                "section": current_section_header,
                                "subsection": current_subsection_header, # Could be overridden by table group
                                "table_group": current_table_group_label if current_table_group_label != immediate_label else "",
                                "type": "table"
                            }

        # Convert the details to a structured schema
        for ph_key, details in placeholder_details.items():
            field_type = "boolean" if ph_key.endswith("_check") else "string"
            
            # Build a descriptive label combining all context
            description_parts = []
            if details.get("immediate_label") and details["immediate_label"] != ph_key:
                description_parts.append(details["immediate_label"])
            if details.get("table_group"):
                description_parts.append(details["table_group"])
                
            description = " - ".join(filter(None, description_parts)) or ph_key
                
            # Create the schema entry
            schema[ph_key] = {
                "type": field_type,
                "section": details.get("section", "General"),
                "subsection": details.get("subsection", ""),
                "description": description,
                "location": details.get("type", "unknown")
            }
            
            # For checkboxes, add helpful metadata with synonyms and positive indicators
            if field_type == "boolean":
                # Generate common synonyms for this field based on the key and description
                synonyms = generate_synonyms_for_checkbox(ph_key, description)
                schema[ph_key]["synonyms"] = synonyms
                
                # Generate positive indicators based on the synonyms and key
                positive_indicators = generate_positive_indicators(ph_key, description, synonyms)
                schema[ph_key]["positive_indicators"] = positive_indicators
            
        # Ensure all placeholders have schema entries
        all_phs = extract_placeholders(template_path)
        for ph in all_phs:
            if ph not in schema:
                field_type = "boolean" if ph.endswith("_check") else "string"
                schema[ph] = {
                    "type": field_type,
                    "section": "General",
                    "subsection": "",
                    "description": ph,
                    "location": "unknown"
                }
                
                # For checkboxes, add helpful metadata
                if field_type == "boolean":
                    synonyms = generate_synonyms_for_checkbox(ph, ph)
                    schema[ph]["synonyms"] = synonyms
                    positive_indicators = generate_positive_indicators(ph, ph, synonyms)
                    schema[ph]["positive_indicators"] = positive_indicators

        print(f"Generated schema for {len(schema)} placeholders.")
        return schema

    except Exception as e:
        print(f"Error extracting placeholder schema from '{template_path}': {e}")
        import traceback
        traceback.print_exc()
        return {}

def generate_synonyms_for_checkbox(key: str, description: str) -> List[str]:
    """
    Generates synonyms for a checkbox field based on its key and description.
    
    Args:
        key: The placeholder key (e.g. "explosion_proof_check")
        description: The human-readable description
        
    Returns:
        A list of synonyms for this concept
    """
    # Remove _check suffix for cleaner key
    clean_key = key.replace("_check", "")
    
    # Common replacements for parts of keys
    word_synonyms = {
        "explosion_proof": ["explosion-proof", "explosion proof", "explosion protected", "exp", "exd", "class 1 div 2"],
        "stainless": ["ss", "s.s.", "stainless steel", "inox", "s/s"],
        "barcode": ["bar code", "barcode reader", "code reader", "scanner"],
        "label": ["label", "labelling", "labeling", "labeler"],
        "hmi": ["hmi", "human machine interface", "touch screen", "touch panel", "operator interface"],
        "plc": ["plc", "controller", "control system", "automation controller"],
        "conveyor": ["conveyor", "conveying system", "transport system"],
        "sensor": ["sensor", "detector", "sensing device"],
    }
    
    # Extract potential key parts by splitting on underscores
    key_parts = clean_key.split("_")
    
    # Get synonyms from description
    desc_words = description.lower().split()
    
    # Start with the key itself and the description
    synonyms = [clean_key.replace("_", " "), description]
    
    # Add synonyms for each key part if available
    for part in key_parts:
        if part in word_synonyms:
            synonyms.extend(word_synonyms[part])
    
    # Look for known phrases in the description and add their synonyms
    for phrase, syn_list in word_synonyms.items():
        if phrase in description.lower() or phrase.replace("_", " ") in description.lower():
            synonyms.extend(syn_list)
    
    # Clean up and return unique values
    cleaned_synonyms = [s.strip().lower() for s in synonyms if s.strip()]
    return list(set(cleaned_synonyms))

def generate_positive_indicators(key: str, description: str, synonyms: List[str]) -> List[str]:
    """
    Generates phrases that would indicate this checkbox should be marked YES.
    
    Args:
        key: The placeholder key
        description: The human-readable description
        synonyms: List of synonyms for this concept
        
    Returns:
        A list of phrases that would indicate this is selected
    """
    # Start with basic indicators
    indicators = ["included", "standard", "included as standard", "yes", "selected"]
    
    # Create phrases like "with <synonym>"
    for synonym in synonyms:
        if synonym:
            indicators.append(f"with {synonym}")
            indicators.append(f"includes {synonym}")
            indicators.append(f"{synonym} included")
            indicators.append(f"{synonym} is selected")
    
    # Clean up the description to use as an indicator
    if description:
        clean_desc = description.strip().lower()
        indicators.append(clean_desc)
        indicators.append(f"with {clean_desc}")
        indicators.append(f"includes {clean_desc}")
    
    # Clean up and return unique values
    cleaned_indicators = [i.strip().lower() for i in indicators if i.strip()]
    return list(set(cleaned_indicators))

def add_section_aware_instructions(template_schema: Dict[str, Dict], prompt_parts: List[str]) -> List[str]:
    """
    Enhances the prompt with section-specific instructions to improve the LLM's understanding
    of each template section's purpose and meaning.
    
    Args:
        template_schema: The JSON schema generated by extract_placeholder_schema
        prompt_parts: The current prompt parts list to enhance
        
    Returns:
        Enhanced prompt parts list with section-specific instructions
    """
    if not template_schema:
        return prompt_parts  # No schema to work with
    
    # Group fields by section
    sections = {}
    for key, field_info in template_schema.items():
        section = field_info.get("section", "General")
        if section not in sections:
            sections[section] = []
        sections[section].append((key, field_info))
    
    # Add section-specific instructions
    if sections:
        prompt_parts.append("\n## SECTION-SPECIFIC GUIDANCE:")
        prompt_parts.append("Pay attention to these section-specific instructions when filling out the template:")
        
        # Add instructions for each section
        for section, fields in sorted(sections.items()):
            # Skip very small sections or generic sections
            if len(fields) < 2 or section in ["General"]:
                continue
            
            # Group fields by type within section
            text_fields = [f for f in fields if f[1].get("type") == "string"]
            checkbox_fields = [f for f in fields if f[1].get("type") == "boolean"]
            
            # Create section-specific instructions based on section name and field types
            section_instructions = []
            
            # General rules based on section name
            if "customer" in section.lower() or "client" in section.lower():
                section_instructions.append(f"For the '{section}' section: Focus on extracting customer/client details like company name, address, contact information, etc. Look for this information at the beginning of quotes or in header sections.")
            
            elif "machine" in section.lower() or "equipment" in section.lower():
                section_instructions.append(f"For the '{section}' section: Focus on the specific machine being quoted. The machine model and specifications are usually prominently featured in the quote's main description or line items.")
            
            elif "feature" in section.lower() or "option" in section.lower() or "accessory" in section.lower():
                section_instructions.append(f"For the '{section}' section: These are optional features or add-ons for the machine. Check each line item description carefully to determine which options are included in the quote.")
            
            elif "safety" in section.lower() or "compliance" in section.lower():
                section_instructions.append(f"For the '{section}' section: Look for safety features and compliance standards mentioned in the quote. These might be in dedicated sections or embedded within feature descriptions.")
                
            elif "warranty" in section.lower() or "service" in section.lower():
                section_instructions.append(f"For the '{section}' section: Focus on warranty terms, service plans, and support offerings. These are often mentioned toward the end of quotes or in special sections.")
                
            elif "delivery" in section.lower() or "shipping" in section.lower() or "transport" in section.lower():
                section_instructions.append(f"For the '{section}' section: Extract information about delivery timelines, shipping methods, and transportation details. Check both line items and any terms & conditions sections.")
                
            elif "payment" in section.lower() or "financial" in section.lower() or "price" in section.lower():
                section_instructions.append(f"For the '{section}' section: Look for payment terms, financial arrangements, and pricing details. These may be in dedicated sections or near the end of the quote.")
            
            # If no specific rule matched but there are fields, create a generic one
            if not section_instructions:
                section_instructions.append(f"For the '{section}' section: Extract all relevant information about {section.lower()} from the quote document.")
            
            # Add field-type specific instructions if needed
            if checkbox_fields and len(checkbox_fields) > 5:
                checkbox_examples = ", ".join([f"'{f[1].get('description', f[0])}'" for f in checkbox_fields[:3]])
                section_instructions.append(f"  - This section contains many checkbox fields (e.g., {checkbox_examples}). Only mark a checkbox 'YES' if there is explicit evidence in the quote that the feature is included.")
            
            if text_fields and len(text_fields) > 5:
                text_examples = ", ".join([f"'{f[1].get('description', f[0])}'" for f in text_fields[:3]])
                section_instructions.append(f"  - This section contains text fields (e.g., {text_examples}) that need specific values extracted from the quote.")
            
            # Add the section instructions to the prompt
            for instruction in section_instructions:
                prompt_parts.append(instruction)
    
    return prompt_parts

if __name__ == '__main__':
    test_template_path = 'template.docx' 
    if os.path.exists(test_template_path):
        print(f"Testing with template: {test_template_path}")
        
        placeholders = extract_placeholders(test_template_path)
        print("\n--- Unique Placeholders Found ---")
        if placeholders:
            for p_holder in placeholders:
                print(f"- {p_holder}")
        else:
            print("No placeholders found.")

        print("\n--- Placeholder Context (Hierarchical Test) ---")
        context = extract_placeholder_context_hierarchical(test_template_path)
        if context:
            count = 0
            for p_holder, desc in sorted(context.items()): 
                print(f"- '{p_holder}': '{desc}'")
                count += 1
                if count >= 50 and len(context) > 50: 
                    print("... and more.")
                    break
        else:
            print("No placeholder context generated.")
            
    else:
        print(f"Test template file not found at: {test_template_path}. Please provide a valid path.") 