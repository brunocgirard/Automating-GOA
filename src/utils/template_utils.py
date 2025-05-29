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

def extract_placeholder_context_hierarchical(template_path: str, 
                                            enhance_with_outline: bool = True,
                                            outline_path: str = "full_fields_outline.md") -> Dict[str, str]:
    """
    Parses the template to extract placeholders and attempts to build hierarchical context
    by identifying section headers. Optionally enhances with outline file.
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
        
        # Enhance with outline file if requested
        if enhance_with_outline and os.path.exists(outline_path):
            context_map = enhance_placeholder_context_with_outline(context_map, outline_path)
        
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
    
    # Comprehensive dictionary of packaging industry terms and their synonyms
    word_synonyms = {
        # Safety and compliance terms
        "explosion_proof": ["explosion-proof", "explosion proof", "explosion protected", "exp", "exd", "class 1 div 2", 
                           "explosion protection", "hazardous area", "atex", "ex-proof", "explosion protected environment"],
        "stainless": ["ss", "s.s.", "stainless steel", "inox", "s/s", "316", "304", "316l", "ss316", "ss304", "aisi"],
        "certification": ["certified", "ce", "csa", "ul", "ansi", "asme", "iso", "iec", "din", "gmp", "fda", "3a"],
        "gmp": ["good manufacturing practice", "gmp-compliant", "cleanroom", "clean room", "pharmaceutical grade"],
        "fda": ["food grade", "fda approved", "fda-compliant", "pharma grade", "medical grade"],
        
        # Production parameters
        "production_speed": ["projected speed", "throughput", "bottles per minute", "units per minute", "parts per minute", 
                            "bpm", "upm", "ppm", "production rate", "processing speed", "output rate", "machine speed"],
        
        # Identification and coding systems
        "barcode": ["bar code", "barcode reader", "code reader", "scanner", "scan", "scanning", "2d code", "qr", 
                   "datamatrix", "data matrix", "upc", "ean", "barcode verification", "symbology"],
        "ocr": ["optical character recognition", "character reading", "text reading", "code reading", "character verification"],
        "ocv": ["optical character verification", "text verification", "character validation", "text validation"],
        "vision": ["machine vision", "camera", "imaging", "visual inspection", "vision system", "cognex", "keyence", "omron"],
        "laser": ["laser marking", "laser coding", "laser etching", "laser printing", "co2 laser", "fiber laser", "marking laser"],
        "inkjet": ["ink jet", "ink-jet", "cij", "continuous inkjet", "thermal inkjet", "ink printer", "coding", "printing"],
        
        # Labeling and packaging systems
        "label": ["label", "labelling", "labeling", "labeler", "labeller", "adhesive label", "pressure sensitive", 
                 "roll fed", "cut and stack", "label applicator", "front label", "back label"],
        "sleeve": ["shrink sleeve", "shrink label", "sleeve applicator", "full body sleeve", "neck sleeve", "tamper evident"],
        "wrap": ["wrap around", "wraparound", "wrap-around", "wrap label", "full wrap", "partial wrap"],
        "reel": ["label reel", "roll", "spool", "material reel", "unwinder", "rewinder", "roll holder"],
        
        # Control systems
        "hmi": ["hmi", "human machine interface", "touch screen", "touch panel", "operator interface", 
               "control panel", "display", "panel pc", "operator panel", "touchscreen", "monitor"],
        "plc": ["plc", "controller", "control system", "automation controller", "programmable logic", 
               "automation system", "control unit", "processor", "allen bradley", "siemens", "b&r", "omron"],
        "servo": ["servo motor", "servo drive", "servo system", "servo control", "brushless", "motion control", 
                 "precision motion", "servo-driven", "servo actuator", "stepper", "motor"],
        "pneumatic": ["air", "pneumatic cylinder", "pneumatic actuator", "pneumatic system", "compressed air", 
                     "air cylinder", "air pressure", "air operated", "air driven"],
        
        # Transport and handling systems
        "conveyor": ["conveying system", "transport system", "belt conveyor", "chain conveyor", "mat conveyor", 
                    "conveyor belt", "transport", "product transfer", "product handling"],
        "accumulation": ["accumulation table", "accumulator", "buffer", "buffer table", "accumulation conveyor", 
                        "bottle accumulator", "container buffer"],
        "elevator": ["product elevator", "vertical conveyor", "cap elevator", "bottle elevator", "vertical transport", 
                    "lifting system", "bucket elevator", "z-elevator"],
        "turntable": ["rotary table", "turn table", "rotating table", "accumulation table", "indexing table", 
                     "disc table", "disc turntable", "rotary buffer"],
        "starwheel": ["star wheel", "timing screw", "timing star", "infeed star", "discharge star", "transfer star", 
                     "pocket wheel", "container transfer"],
        
        # Filling and dispensing systems
        "filling": ["filler", "filling system", "liquid filling", "volumetric filling", "gravimetric filling", 
                   "level filling", "time pressure filling", "mass flow", "piston filler"],
        "pump": ["peristaltic pump", "gear pump", "lobe pump", "piston pump", "diaphragm pump", "centrifugal pump", 
                "rotary pump", "dosing pump", "metering pump", "dispensing pump"],
        "nozzle": ["filling nozzle", "dispensing nozzle", "fill head", "dosing nozzle", "spray nozzle", 
                  "injection nozzle", "applicator nozzle", "valve nozzle"],
        "valve": ["filling valve", "control valve", "check valve", "solenoid valve", "ball valve", "needle valve", 
                 "butterfly valve", "diaphragm valve", "pinch valve"],
        
        # Capping and sealing systems
        "capping": ["capper", "cap applicator", "cap tightener", "cap sealer", "screwing", "twist-off", 
                   "screw capper", "press-on capper", "snap-on capper", "ROPP", "roll-on pilfer-proof"],
        "torque": ["torque control", "cap torque", "torque monitoring", "torque verification", "torque check", 
                  "torque testing", "torque adjustment", "tightening torque"],
        "sealing": ["heat sealing", "induction sealing", "foil sealing", "ultrasonic sealing", "band sealing", 
                   "conduction sealing", "hermetic seal", "tamper evident"],
        "induction": ["induction sealer", "cap sealer", "foil sealer", "induction heating", "induction coil", 
                     "sealing head", "cap sealing"],
        
        # Detection and verification systems
        "sensor": ["detector", "sensing device", "photoelectric", "proximity", "ultrasonic", "capacitive", 
                  "inductive", "fiber optic", "vision sensor", "level sensor", "presence sensor"],
        "inspection": ["inspection system", "quality control", "verification", "checking", "monitoring", 
                      "detection", "visual inspection", "automated inspection", "100% inspection"],
        "reject": ["rejection system", "reject mechanism", "reject station", "rejection station", "ejector", 
                  "rejection device", "sort", "discard", "rejection arm"],
        "verification": ["check", "verification system", "monitoring", "quality assurance", "validation", 
                        "confirmation", "inspection", "testing", "quality check"],
        
        # Container handling terms
        "bottle": ["container", "vial", "jar", "flask", "ampoule", "bottle", "can", "packaging", "primary container"],
        "puck": ["carrier", "container carrier", "bottle puck", "vial carrier", "nest", "container holder", "pocket"],
        "unscrambler": ["bottle unscrambler", "container unscrambler", "container orienter", "bottle orienter", 
                       "unscrambling system", "bottle sorting", "bottle feed"],
        "accumulator": ["buffer", "accumulation", "accumulation table", "container buffer", "bottle buffer", 
                       "buffering system", "product queue"],
        
        # Machine features
        "clean_in_place": ["cip", "clean-in-place", "cip system", "automated cleaning", "washdown", "cleaning system",
                          "sanitization", "sterilization", "aseptic", "clean room"],
        "touchless": ["no-touch", "non-contact", "contactless", "touchless operation", "hands-free", "remote operation"],
        "remote_service": ["remote support", "remote access", "remote diagnostics", "remote monitoring", 
                          "teleservice", "remote maintenance", "remote connection"],
        "guarding": ["safety guarding", "machine guarding", "safety fence", "protective cover", "safety barrier", 
                    "safety shield", "protective enclosure", "lexan", "plexiglass", "safety door"],
        
        # Specialized add-ons
        "weighing": ["checkweigher", "weight verification", "weight control", "gravimetric", "scale", "balance", 
                    "load cell", "mass measurement", "weight check"],
        "coding": ["printer", "marking", "coding system", "date coder", "lot coder", "batch coder", 
                  "expiry date printer", "variable information"],
        "serialization": ["track and trace", "unique identification", "serial number", "unique code", 
                         "serialization system", "aggregation", "parent-child relationship"],
        "format_change": ["changeover", "format parts", "change parts", "size parts", "adjustment parts", 
                         "quick change", "tool-less changeover", "format conversion"]
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
        prompt_parts.append("Pay careful attention to these section-specific instructions when filling out the template:")
        
        # Domain-specific section guidance from the GOA filling guide
        section_guidance = {
            "Basic Information": "This section contains the fundamental project identifiers including project number (Ax), customer name, machine type, and flow direction (typically left-to-right or right-to-left).",
            
            "Order Identification": "This section includes customer PO number, quote number, internal order number (Ox), customer ID, and production speed. All information here should come directly from the quote/sales order document.",
            
            "Utility Specifications": "Look for electrical and pneumatic requirements: supply voltage (e.g., 208-240V), frequency (Hz), air pressure (PSI), certification standards (CSA, CE, etc.), and destination country. IMPORTANT: For explosion-proof environments, electrical components are replaced with pneumatic equivalents.",
            
            "Change Part Quantities and Construction Materials": "This section defines quantities and materials for components that may need to be changed for different product formats, including bottles, plugs, caps, and materials for seals and tubing.",
            
            "Material Specifications": "Identifies materials that come in contact with the product. Look for FDA-approved materials, product contact surfaces (usually SS 304 or SS 316L based on product compatibility), and options like 'Autoclavable' or 'Electropolished'.",
            
            "Control & Programming Specifications": "This critical section defines the machine's control system including explosion proof requirements, PLC type (B&R, Allen Bradley, CompactLogix, ControlLogix), HMI specifications (size, language, location), control panel configuration, beacon lights, E-stops, and data reporting capabilities.",
            
            "Bottle Handling System Specifications": "Defines how containers are fed into the machine, including tube handling systems, vial/bottle transport mechanisms, puck systems for unstable containers, turntables, and indexing mechanisms (starwheel, walking beam, etc.).",
            
            "Reject / Inspection System": "Specifies how rejected products are handled and what conditions trigger rejection. Look for reject methods (chute, tray, conveyor) and reject reasons (fill weight, cap presence, label position, etc.).",
            
            "Street Fighter Tablet Counter": "Specific to tablet counting systems. Identifies model version, number of funnels, hopper size, and features like dust extraction or load cells.",
            
            "Liquid Filling System Specifications": "For filling machines, identifies pump type (volumetric, peristaltic), filling mechanism, pump volume, valve type, nozzle configuration, and options like check weighing. Note that size-appropriate nozzles are typically 2-3mm smaller than the neck opening.",
            
            "Gas Purge": "For products requiring oxygen removal, specifies gas type (nitrogen, argon) and application points (before fill, at fill, after fill, tunnel).",
            
            "Desiccant": "For systems that insert desiccant, specifies type (roll/pouch, cannister) and feeding mechanism.",
            
            "Cottoner": "For systems that insert cotton, includes sensing options (presence, high) and cotton bin configuration.",
            
            "Plugging System Specifications": "For machines that insert plugs, defines insertion mechanism, sorting method, and bulk feeding system.",
            
            "Capping System Specifications": "For machines that apply caps, details cap placement method, torque mechanism and range, cap sorting, centering device, and bulk feeding system. NOTE: A servo with magnetic clutch is not standard and should be verified.",
            
            "BeltStar System Specifications": "For belt-driven capping systems, includes cap placement method, torque mechanism, cap sorting, and adjustment options.",
            
            "Labeling System Specifications": "For labeling machines, identifies label head model, reel diameter, arm type, application system (wrap around, multi-panel), and separator wheel configuration.",
            
            "Coding and Inspection System Specifications": "For printing batch codes and other variable information, includes coder type (hot stamp, thermal transfer, laser, inkjet), vision system configuration, and print content (lot, barcode, expiration date).",
            
            "Induction Specifications": "For induction sealing systems, specifies model, voltage, frequency, sealing head type, stand configuration, and cap inspection capabilities.",
            
            "Conveyor Specifications": "Details conveyor width, length, height, shape, chain type, bed type, and transfer guides.",
            
            "Euro Guarding": "Specifies machine guarding requirements including panel material, switch type, and covers.",
            
            "Validation Documents": "Identifies required documentation (FAT, SAT, DQ, IQ/OQ) and languages.",
            
            "Warranty & Install & Spares": "Specifies warranty period, spare parts kit requirements, and commissioning services."
        }
        
        # Add instructions for each section
        for section, fields in sorted(sections.items()):
            # Skip very small sections or generic sections
            if len(fields) < 2 or section in ["General"]:
                continue
            
            # Add domain-specific guidance from our dictionary if available
            if section in section_guidance:
                prompt_parts.append(f"\nFor the '{section}' section: {section_guidance[section]}")
            else:
                # Default guidance based on section name
                if "customer" in section.lower() or "client" in section.lower():
                    prompt_parts.append(f"For the '{section}' section: Focus on extracting customer/client details like company name, address, contact information, etc. Look for this information at the beginning of quotes or in header sections.")
                
                elif "machine" in section.lower() or "equipment" in section.lower():
                    prompt_parts.append(f"For the '{section}' section: Focus on the specific machine being quoted. The machine model and specifications are usually prominently featured in the quote's main description or line items.")
                
                elif "feature" in section.lower() or "option" in section.lower() or "accessory" in section.lower():
                    prompt_parts.append(f"For the '{section}' section: These are optional features or add-ons for the machine. Check each line item description carefully to determine which options are included in the quote.")
                
                elif "safety" in section.lower() or "compliance" in section.lower():
                    prompt_parts.append(f"For the '{section}' section: Look for safety features and compliance standards mentioned in the quote. These might be in dedicated sections or embedded within feature descriptions.")
                    
                elif "warranty" in section.lower() or "service" in section.lower():
                    prompt_parts.append(f"For the '{section}' section: Focus on warranty terms, service plans, and support offerings. These are often mentioned toward the end of quotes or in special sections.")
                    
                elif "delivery" in section.lower() or "shipping" in section.lower() or "transport" in section.lower():
                    prompt_parts.append(f"For the '{section}' section: Extract information about delivery timelines, shipping methods, and transportation details. Check both line items and any terms & conditions sections.")
                    
                elif "payment" in section.lower() or "financial" in section.lower() or "price" in section.lower():
                    prompt_parts.append(f"For the '{section}' section: Look for payment terms, financial arrangements, and pricing details. These may be in dedicated sections or near the end of the quote.")
                
                # If no specific rule matched but there are fields, create a generic one
                else:
                    prompt_parts.append(f"For the '{section}' section: Extract all relevant information about {section.lower()} from the quote document.")
            
            # Group fields by type within section
            text_fields = [f for f in fields if f[1].get("type") == "string"]
            checkbox_fields = [f for f in fields if f[1].get("type") == "boolean"]
            
            # Add field-type specific instructions if needed
            if checkbox_fields and len(checkbox_fields) > 5:
                checkbox_examples = ", ".join([f"'{f[1].get('description', f[0])}'" for f in checkbox_fields[:3]])
                prompt_parts.append(f"  - This section contains many checkbox fields (e.g., {checkbox_examples}). Only mark a checkbox 'YES' if there is explicit evidence in the quote that the feature is included.")
            
            if text_fields and len(text_fields) > 5:
                text_examples = ", ".join([f"'{f[1].get('description', f[0])}'" for f in text_fields[:3]])
                prompt_parts.append(f"  - This section contains text fields (e.g., {text_examples}) that need specific values extracted from the quote.")
            
            # Add special instructions for specific sections
            if "Control & Programming" in section:
                prompt_parts.append("  - When determining PLC type, look for keywords like 'Allen Bradley', 'CompactLogix', 'B&R', or 'ControlLogix'.")
                prompt_parts.append("  - For HMI size, common options are 5.7\", 10\", and 15\". The size is often specified directly with the HMI.")
                prompt_parts.append("  - For beacon lights, if a 'tri-color beacon' or 'three-color tower light' is mentioned, mark all three colors (Red, Green, Yellow) as 'YES'.")
            
            if "Filling" in section:
                prompt_parts.append("  - For pump volumes, look for specific capacity values like '50cc', '100cc', '250cc', etc.")
                prompt_parts.append("  - Nozzle sizes should be compatible with the container being filled. Typical size is 2-3mm smaller than the container opening.")
            
            if "Reject" in section:
                prompt_parts.append("  - Mark all the specific reject reasons mentioned in the quote. Common ones include cap presence, fill weight, and label position.")
                prompt_parts.append("  - If a vision system is mentioned for inspection, look for specific inspection parameters it will check.")
            
            if "Labeling" in section:
                prompt_parts.append("  - For label application type, determine if it's a wrap-around, front/back, or multi-panel system.")
                prompt_parts.append("  - Check if a specific label head model (like LS100 or LS200) is mentioned.")
    
    # Add some general packaging industry interpretation guidelines
    prompt_parts.append("\n## PACKAGING INDUSTRY INTERPRETATION GUIDELINES:")
    prompt_parts.append("1. When a line item includes the phrase 'Including:' followed by features, mark all those features as 'YES' in the template.")
    prompt_parts.append("2. If a feature is described as 'Standard' or 'STD', it should be marked as 'YES'.")
    prompt_parts.append("3. For HMI and PLC types, carefully check for brand names in the machine descriptions.")
    prompt_parts.append("4. When filling systems mention 'Bottom-up filling' or 'Diving nozzles', these are specialized fill methods.")
    prompt_parts.append("5. If a multi-color beacon light is mentioned without specifying colors, mark all standard colors (Red, Yellow, Green) as 'YES'.")
    prompt_parts.append("6. For servo-controlled systems, look for associated parameters like torque range or speed.")
    
    return prompt_parts

def enhance_placeholder_context_with_outline(context_map: Dict[str, str], outline_path: str = "full_fields_outline.md") -> Dict[str, str]:
    """
    Enhances the extracted placeholder context by cross-referencing with the structured outline file.
    
    Args:
        context_map: The existing context map from extract_placeholder_context_hierarchical
        outline_path: Path to the full_fields_outline.md file
        
    Returns:
        Enhanced context map with more accurate hierarchical information
    """
    print(f"Enhancing placeholder context using outline file: {outline_path}")
    
    try:
        if not os.path.exists(outline_path):
            print(f"Warning: Outline file not found at {outline_path}")
            return context_map
            
        # Load the outline file
        with open(outline_path, 'r', encoding='utf-8') as f:
            outline_lines = f.readlines()
            
        # Parse the outline structure
        outline_context = {}
        current_section = ""
        current_subsection = ""
        current_sub_subsection = ""
        
        # Process the outline file
        for line in outline_lines:
            line = line.strip()
            if not line:
                continue
                
            # Main sections (## headings)
            if line.startswith('## '):
                current_section = line[3:].strip()
                current_subsection = ""
                current_sub_subsection = ""
            
            # Subsections (- headings with no indentation)
            elif line.startswith('- ') and not line.startswith('  - '):
                # Extract the subsection name (remove any (text), (section), etc.)
                subsection_text = line[2:].strip()
                if '(' in subsection_text:
                    subsection_text = subsection_text.split('(')[0].strip()
                current_subsection = subsection_text
                current_sub_subsection = ""
                
                # Special case - create field entries for checkbox subsections
                if '(checkbox)' in line:
                    field_key = subsection_text.lower().replace(' ', '_').replace('/', '_').replace('-', '_')
                    field_key = field_key + "_check"
                    
                    context_str = f"{current_section} - {field_key.replace('_check', '')}"
                    outline_context[field_key] = context_str
            
            # Sub-subsections (indented items with checkbox)
            elif line.startswith('  - ') and '(checkbox)' in line:
                # This is a checkbox field
                field_text = line[4:].strip()
                if '(' in field_text:
                    field_text = field_text.split('(')[0].strip()
                
                # Create field key
                field_key = field_text.lower().replace(' ', '_').replace('/', '_').replace('-', '_').replace('&', 'and')
                field_key = field_key + "_check"
                
                # Build context
                if current_subsection:
                    context_str = f"{current_section} - {current_subsection} - {field_text}"
                else:
                    context_str = f"{current_section} - {field_text}"
                
                outline_context[field_key] = context_str
            
            # Text fields (indented items without checkbox)
            elif line.startswith('  - ') and '(text)' in line:
                # This is a text field
                field_text = line[4:].strip()
                if '(' in field_text:
                    field_text = field_text.split('(')[0].strip()
                
                # Create field key
                field_key = field_text.lower().replace(' ', '_').replace('/', '_').replace('-', '_').replace('&', 'and')
                
                # Build context
                if current_subsection:
                    context_str = f"{current_section} - {current_subsection} - {field_text}"
                else:
                    context_str = f"{current_section} - {field_text}"
                
                outline_context[field_key] = context_str
            
            # Field with any type indicator
            elif line.startswith('  - '):
                # Could be a field or subsection, treat as both for matching purposes
                field_text = line[4:].strip()
                if '(' in field_text:
                    field_text = field_text.split('(')[0].strip()
                
                # First, treat as a subsection
                current_sub_subsection = field_text
                
                # Also treat as a potential field
                field_key = field_text.lower().replace(' ', '_').replace('/', '_').replace('-', '_').replace('&', 'and')
                
                # Try both with and without _check suffix for better matching
                context_str = ""
                if current_subsection:
                    context_str = f"{current_section} - {current_subsection} - {field_text}"
                else:
                    context_str = f"{current_section} - {field_text}"
                
                outline_context[field_key] = context_str
                
                # Also add checkbox version if it's a feature that might be selectable
                if not any(term in line.lower() for term in ["qty", "file name", "capacity", "model", "comments"]):
                    outline_context[f"{field_key}_check"] = context_str
        
        print(f"Parsed {len(outline_context)} fields from outline file")
        
        # Add specific well-known fields that might not be captured by the outline parsing
        known_fields = {
            "plc_b&r_check": "Control & Programming Specifications - PLC - B & R",
            "plc_allen_bradley_check": "Control & Programming Specifications - PLC - Allen Bradley",
            "plc_compactlogix_check": "Control & Programming Specifications - PLC - CompactLogix",
            "plc_controllogix_check": "Control & Programming Specifications - PLC - ControlLogix",
            "explosion_proof_check": "Control & Programming Specifications - Explosion proof",
            "hmi_10_check": "Control & Programming Specifications - HMI - Size - 10\"",
            "hmi_15_check": "Control & Programming Specifications - HMI - Size - 15\"",
            "hmi_5_7_check": "Control & Programming Specifications - HMI - Size - 5.7\" n/a for vision",
            "cap_prs_check": "Reject / Inspection System - Reject Reasons - Cap Prs.",
            "voltage": "Utility Specifications - Voltage",
            "hz": "Utility Specifications - Hz",
            "psi": "Utility Specifications - PSI"
        }
        
        for field, context in known_fields.items():
            outline_context[field] = context
        
        # Enhance the context map with outline information
        enhanced_context_map = context_map.copy()
        enhanced_count = 0
        
        # Print some debug info about existing keys (reduced verbosity)
        print(f"Original context map has {len(context_map)} keys")
        
        # Create normalized versions of outline keys for better matching
        normalized_outline_keys = {}
        for key, value in outline_context.items():
            # Create multiple normalized versions
            norm_key1 = key.lower().replace('_', '')  # No underscores
            norm_key2 = key.lower()  # With underscores
            normalized_outline_keys[norm_key1] = key
            normalized_outline_keys[norm_key2] = key
        
        print(f"Created {len(normalized_outline_keys)} normalized outline keys")
        
        # First, try direct key matches
        for key in context_map.keys():
            # Try direct match first
            if key in outline_context:
                enhanced_context_map[key] = outline_context[key]
                enhanced_count += 1
                continue
                
            # Try normalized keys
            norm_key1 = key.lower().replace('_', '')
            norm_key2 = key.lower()
            
            if norm_key1 in normalized_outline_keys:
                outline_key = normalized_outline_keys[norm_key1]
                enhanced_context_map[key] = outline_context[outline_key]
                enhanced_count += 1
                continue
                
            if norm_key2 in normalized_outline_keys and norm_key2 != norm_key1:
                outline_key = normalized_outline_keys[norm_key2]
                enhanced_context_map[key] = outline_context[outline_key]
                enhanced_count += 1
                continue
                
            # Special case for PLC brands
            if 'plc' in key.lower() and 'check' in key.lower():
                if 'b&r' in key.lower() or 'br' in key.lower() or 'bandr' in key.lower():
                    enhanced_context_map[key] = "Control & Programming Specifications - PLC - B & R"
                    enhanced_count += 1
                    continue
                if 'allen' in key.lower() or 'bradley' in key.lower() or 'ab' in key.lower():
                    enhanced_context_map[key] = "Control & Programming Specifications - PLC - Allen Bradley"
                    enhanced_count += 1
                    continue
                if 'compact' in key.lower() or 'logix' in key.lower():
                    enhanced_context_map[key] = "Control & Programming Specifications - PLC - CompactLogix"
                    enhanced_count += 1
                    continue
            
            # Special case for HMI sizes
            if 'hmi' in key.lower() and 'check' in key.lower():
                if '10' in key.lower() or '10inch' in key.lower():
                    enhanced_context_map[key] = "Control & Programming Specifications - HMI - Size - 10\""
                    enhanced_count += 1
                    continue
                if '15' in key.lower() or '15inch' in key.lower():
                    enhanced_context_map[key] = "Control & Programming Specifications - HMI - Size - 15\""
                    enhanced_count += 1
                    continue
                if '5.7' in key.lower() or '5_7' in key.lower():
                    enhanced_context_map[key] = "Control & Programming Specifications - HMI - Size - 5.7\" n/a for vision"
                    enhanced_count += 1
                    continue
            
            # Try fuzzy matching against outline keys
            best_match = None
            best_score = 0
            
            for outline_key, outline_value in outline_context.items():
                # Check if this is a checkbox and the current key is a checkbox
                if key.endswith('_check') and outline_key.endswith('_check'):
                    # Remove _check for comparison
                    key_base = key[:-6]
                    outline_key_base = outline_key[:-6]
                    
                    # Simple word matching
                    key_words = set(key_base.split('_'))
                    outline_words = set(outline_key_base.split('_'))
                    common_words = key_words.intersection(outline_words)
                    
                    if common_words:
                        score = len(common_words) / max(len(key_words), len(outline_words))
                        if score > best_score:
                            best_score = score
                            best_match = outline_key
                
                # For non-checkbox fields
                elif not key.endswith('_check') and not outline_key.endswith('_check'):
                    # Simple word matching
                    key_words = set(key.split('_'))
                    outline_words = set(outline_key.split('_'))
                    common_words = key_words.intersection(outline_words)
                    
                    if common_words:
                        score = len(common_words) / max(len(key_words), len(outline_words))
                        if score > best_score:
                            best_score = score
                            best_match = outline_key
            
            # If we found a good match (threshold of 0.5)
            if best_match and best_score > 0.5:
                enhanced_context_map[key] = outline_context[best_match]
                enhanced_count += 1
        
        # Print some statistics
        print(f"Enhanced {enhanced_count} of {len(context_map)} placeholder contexts")
        
        return enhanced_context_map
    
    except Exception as e:
        print(f"Error enhancing placeholder context: {e}")
        import traceback
        traceback.print_exc()
        return context_map

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