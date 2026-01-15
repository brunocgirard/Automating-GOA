import pdfplumber
import re
import os
from typing import List, Tuple, Dict, Optional
import traceback

def find_table_headers(table: List[List[Optional[str]]]) -> Optional[Dict[str, int]]:
    """
    Identifies columns for 'description', 'quantity', and 'final_price'.
    Returns a dictionary mapping these conceptual names to their column indices.
    """
    if not table or not table[0]: return None
    header_row = table[0]
    headers = {}
    desc_keys = ["description", "item", "option", "feature", "article", "désignation"]
    qty_keys = ["qty", "quantity", "qté", "quant"]
    price_keys = ["selected item", "total", "amount", "price", "prix", "montant"] # Final price column

    # Find indices
    desc_idx = next((i for i, cell in enumerate(header_row) if cell and any(k in str(cell).lower() for k in desc_keys)), -1)
    qty_idx = next((i for i, cell in enumerate(header_row) if cell and any(k in str(cell).lower() for k in qty_keys)), -1)
    price_idx = next((i for i, cell in enumerate(header_row) if cell and any(k in str(cell).lower() for k in price_keys)), -1)

    if desc_idx != -1:
        headers["description"] = desc_idx
        # Determine the source for selection_text (either price or quantity if price is missing)
        if price_idx != -1:
            headers["selection_text_source"] = price_idx
        elif qty_idx != -1:
            headers["selection_text_source"] = qty_idx
            # print(f"Warning: Using Qty col (idx {qty_idx}) for selection text source, no explicit Price/Total col found.")
        else: # No price or qty column found for selection text, cannot determine selection or price text reliably
            return None 
        
        # Store quantity index if found, separately from selection_text_source
        if qty_idx != -1:
            headers["quantity"] = qty_idx
        else:
            headers["quantity"] = -1 # Indicate quantity column was not found
            
        return headers
    return None

def is_row_selected(row: List[Optional[str]], headers: Dict[str, int]) -> bool:
    """
    Checks if a row represents a selected item based on selection/price column content.
    """
    selection_idx = headers.get("selection")
    if selection_idx is None: # Should not happen if find_table_headers returned a dict
        return False 

    # These are the textual values we don't want to misinterpret as selected if they appear in data rows
    header_like_texts_in_selection_column = ["selected item", "price", "cost", "qty", "quantity", "montant", "prix", "total"]

    if len(row) > selection_idx and row[selection_idx] is not None:
        selection_value_str = str(row[selection_idx]).strip()
        selection_value_lower = selection_value_str.lower()

        if not selection_value_str: # Empty string is not selected
            return False

        # If the cell value is exactly one of the common header texts, it's not a selection
        if selection_value_lower in header_like_texts_in_selection_column:
            return False

        # Contains digits (likely a price or quantity)
        if re.search(r'\d', selection_value_str):
            return True
        
        # Explicit selection keywords
        if selection_value_lower in ['included', 'standard', 'yes']:
            return True
        
        # If it's not an explicit non-selection marker like 'no', 'none', '-', '0' (for numeric interpretation)
        # and it's not empty (already checked), consider it selected. This is a lenient catch-all.
        if selection_value_lower not in ['no', 'none', '-', '0']:
            return True
            
    return False

def get_description_from_row(row: List[Optional[str]], headers: Dict[str, int]) -> Optional[str]:
    """
    Extracts the description text from a row using the identified header index.
    """
    desc_idx = headers.get("description")
    if desc_idx is not None and len(row) > desc_idx and row[desc_idx]:
        return str(row[desc_idx]).strip()
    return None

def extract_line_item_details(pdf_path: str) -> List[Dict[str, Optional[str]]]:
    """
    Extracts description, quantity text, and selection/price text for selected items.
    This enhanced version merges multi-line descriptions and uses flexible selection logic.
    """
    extracted_items: List[Dict[str, Optional[str]]] = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table_data in tables:
                    if not table_data: continue

                    headers = find_table_headers(table_data)
                    if not headers: continue

                    desc_col_idx = headers.get("description")
                    sel_text_col_idx = headers.get("selection_text_source")
                    qty_col_idx = headers.get("quantity", -1)
                    
                    # Also look for a 'unit cost' column for selection logic
                    unit_cost_keys = ["unit cost", "unit price"]
                    header_row = table_data[0]
                    unit_cost_col_idx = next((i for i, cell in enumerate(header_row) if cell and any(k in str(cell).lower() for k in unit_cost_keys)), -1)

                    merged_rows = []
                    current_item = None

                    for row in table_data[1:]: # Skip header row
                        # Determine if the row is a primary item row or a continuation
                        is_continuation = True
                        
                        # Check if essential columns (like qty or price) have content. If so, it's likely a new item.
                        has_essential_content = (qty_col_idx != -1 and len(row) > qty_col_idx and row[qty_col_idx] and str(row[qty_col_idx]).strip()) or \
                           (sel_text_col_idx is not None and len(row) > sel_text_col_idx and row[sel_text_col_idx] and str(row[sel_text_col_idx]).strip()) or \
                           (unit_cost_col_idx != -1 and len(row) > unit_cost_col_idx and row[unit_cost_col_idx] and str(row[unit_cost_col_idx]).strip())
                        
                        if has_essential_content:
                            is_continuation = False

                        # Description extraction
                        description_cell = str(row[desc_col_idx]).strip() if desc_col_idx is not None and len(row) > desc_col_idx and row[desc_col_idx] else ""
                        
                        # Fallback: If this is a NEW item (has content) but description is missing, look in other columns
                        # This handles cases where the description text is shifted to a different column
                        if has_essential_content and not description_cell:
                            forbidden_indices = {qty_col_idx, sel_text_col_idx, unit_cost_col_idx}
                            candidates = []
                            for i, cell in enumerate(row):
                                if i in forbidden_indices or i == desc_col_idx: continue
                                cell_text = str(cell).strip() if cell else ""
                                if cell_text:
                                    candidates.append(cell_text)
                            
                            if candidates:
                                # Pick the longest candidate as likely description
                                description_cell = max(candidates, key=len)

                        # If the description cell is empty, it's usually a continuation, UNLESS it has essential content (new item without desc)
                        if not description_cell and not has_essential_content:
                            is_continuation = True

                        # If it's a new item, save the previous one (if exists) and start a new one
                        if not is_continuation:
                            if current_item:
                                merged_rows.append(current_item)
                            current_item = list(row) # Make a copy
                        # If it's a continuation, append the description to the current item
                        elif current_item and description_cell:
                            # Safely append description
                            if desc_col_idx is not None and len(current_item) > desc_col_idx:
                                current_item[desc_col_idx] = (current_item[desc_col_idx] or "") + "\n" + description_cell
                    
                    # Add the last processed item
                    if current_item:
                        merged_rows.append(current_item)

                    # Now, process the merged rows to find selected items
                    unique_items_set = set()
                    for row in merged_rows:
                        # Enhanced selection logic
                        is_selected = False
                        selection_text = str(row[sel_text_col_idx]).strip() if sel_text_col_idx is not None and len(row) > sel_text_col_idx and row[sel_text_col_idx] else None
                        unit_cost_text = str(row[unit_cost_col_idx]).strip() if unit_cost_col_idx != -1 and len(row) > unit_cost_col_idx and row[unit_cost_col_idx] else None
                        quantity_text = str(row[qty_col_idx]).strip() if qty_col_idx != -1 and len(row) > qty_col_idx and row[qty_col_idx] else None
                        
                        # Helper to check inclusion keywords
                        def check_inclusion(text):
                            if not text: return False
                            t_lower = text.lower()
                            return any(k in t_lower for k in ['included', 'standard', 'yes', 'incl'])

                        # Primary check: Must have a valid quantity (contains a digit or is explicitly included)
                        # This filters out items that might have a price/keyword but no quantity (garbage rows)
                        has_digit_qty = quantity_text and re.search(r'\d', quantity_text)
                        is_qty_inclusion = check_inclusion(quantity_text)
                        
                        has_valid_qty = has_digit_qty or is_qty_inclusion

                        if has_valid_qty:
                            # Check for price in "Selected Item" or "Total" column
                            if selection_text and re.search(r'\d', selection_text):
                                is_selected = True
                            # Check for price in "Unit Cost" column
                            elif unit_cost_text and re.search(r'\d', unit_cost_text):
                                is_selected = True
                            # Check for keywords like "Included" in selection text
                            elif check_inclusion(selection_text):
                                is_selected = True
                            # If Quantity itself says "Included", it's considered selected
                            elif is_qty_inclusion:
                                is_selected = True

                        if is_selected:
                            description = str(row[desc_col_idx]).strip() if desc_col_idx is not None and len(row) > desc_col_idx and row[desc_col_idx] else None
                            
                            # Fallback if description is empty but item is selected (has valid qty/price)
                            if not description:
                                description = "(No Description Found)"

                            item_tuple = (description, quantity_text, selection_text)
                            if item_tuple not in unique_items_set:
                                extracted_items.append({
                                    "description": description,
                                    "quantity_text": quantity_text,
                                    "selection_text": selection_text or unit_cost_text # Prioritize selection_text, fallback to unit_cost
                                })
                                unique_items_set.add(item_tuple)
    except Exception as e:
        print(f"Error in extract_line_item_details for '{pdf_path}': {e}"); traceback.print_exc()
    return extracted_items

def extract_full_pdf_text(pdf_path: str,
                          x_tol: float = 1.5,
                          y_tol: float = 3) -> str:
    """
    Extract all text from every page of a PDF.

    The ``x_tol`` and ``y_tol`` parameters control the horizontal and vertical
    tolerance values passed to ``page.extract_text`` for cleaner text flow.
    """
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(x_tolerance=x_tol,
                                             y_tolerance=y_tol)
                if page_text:
                    full_text += page_text + "\n"
    except Exception as e:
        print(f"Error extracting full text from PDF '{pdf_path}': {e}")
    return full_text

def extract_contextual_details(pdf_path: str, 
                               main_item_short_trigger: str, # Changed to short trigger
                               all_selected_descriptions: List[str]) -> str:
    """
    Extracts contextual details that follow a main selected item's description.
    Uses a short trigger to start, captures more aggressively, relies on stop conditions.
    """
    contextual_text_lines = []
    capturing = False
    trigger_start_text_lower = main_item_short_trigger.lower()

    # Create stop triggers from other selected items (use their first line / ~70 chars)
    other_selected_item_start_lines = []
    for desc in all_selected_descriptions:
        # Ensure the main_item_short_trigger (which is now short) isn't preventing its own context capture
        # by checking if the full description of the current item starts with the short trigger.
        # This is a bit heuristic to avoid stopping if the short trigger appears in another item's *full* description.
        current_item_is_being_processed = False
        if desc.lower().startswith(trigger_start_text_lower):
            current_item_is_being_processed = True
        
        if not current_item_is_being_processed:
            first_line = desc.splitlines()[0].strip() if desc else ""
            if first_line:
                other_selected_item_start_lines.append(first_line.lower()[:70]) 
    
    stop_capture_keywords_general = [
        "equipment configuration and price", "total price", "terms and conditions",
        "payment terms", "lead time", "validity", "optional accessories", 
        "spare parts kit", "extended warranty", "start up and commissioning", "validation package",
        # Consider adding very common section headers that might follow details
        "technical specifications", "general specifications", "machine specifications"
    ]
    # Combine general stop keywords with dynamic ones from other selected items
    all_stop_triggers = stop_capture_keywords_general + other_selected_item_start_lines

    try:
        with pdfplumber.open(pdf_path) as pdf:
            main_item_found_on_page = -1
            start_line_of_trigger = -1

            for page_num, page in enumerate(pdf.pages):
                if capturing and page_num > main_item_found_on_page + 2: # Stop after 2 pages of context
                    # print(f"DEBUG: Context capture for '{trigger_start_text_lower}' stopped by page limit.")
                    break

                page_text_elements = page.extract_text_lines(return_chars=False, strip=True)
                
                for line_idx, line_info in enumerate(page_text_elements):
                    line_text = line_info["text"]
                    if not line_text: continue
                    line_text_lower = line_text.lower()

                    if not capturing and trigger_start_text_lower in line_text_lower:
                        capturing = True
                        main_item_found_on_page = page_num
                        start_line_of_trigger = line_idx # Remember the line where trigger was found
                        # print(f"DEBUG: Started context capture for '{trigger_start_text_lower}' on page {page_num + 1}, line {line_idx}")
                        # Don't add the trigger line itself to the context, start from next line
                        continue 

                    if capturing:
                        # If we are on the same page and same line as trigger, skip (already continued)
                        if page_num == main_item_found_on_page and line_idx == start_line_of_trigger:
                            continue

                        # Check for stop conditions
                        for stop_keyword in all_stop_triggers:
                            if stop_keyword in line_text_lower:
                                # print(f"DEBUG: Context for '{trigger_start_text_lower}' stopped by: '{stop_keyword}' in line: '{line_text}'")
                                capturing = False; break
                        if not capturing: break
                        
                        contextual_text_lines.append(line_text)
                
                if not capturing and len(contextual_text_lines) > 0: 
                    break 
            
    except Exception as e:
        print(f"Error extracting contextual details for trigger '{trigger_start_text_lower}': {e}")
    
    return "\n".join(contextual_text_lines)

def identify_machines_from_items(line_items: List[Dict[str, Optional[str]]], price_threshold: float = 10000) -> Dict:
    """
    Groups line items by machine, identifying main machines and their add-ons.
    
    Args:
        line_items: List of dictionaries containing line item details
        price_threshold: Price threshold for determining main machines (default 10000)
        
    Returns:
        Dictionary with "machines" list and "common_items" list:
        {
            "machines": [
                {
                    "machine_name": "Machine Name",
                    "main_item": {...},  # Dict with the main machine's details
                    "add_ons": [...]     # List of dicts with add-on items
                },
                ...
            ],
            "common_items": [...]  # List of items common to all machines
        }
    """
    machines = []
    current_machine = None
    common_items = []
    
    # Keywords that typically indicate a main machine
    main_machine_indicators = [
        r"model.*[A-Z0-9]{2,}",     # Model followed by alphanumeric
        r".*\bmonoblock\b.*",        # Contains "monoblock"
        r".*\bunscrambler\b.*",      # Contains "unscrambler"
        r".*\bfiller\b.*",           # Contains "filler" 
        r".*\bcapper\b.*",           # Contains "capper"
        r".*\blabeler\b.*",          # Contains "labeler"
        r".*\bcartoner\b.*",         # Contains "cartoner"
        r".*\bcase\s*packer\b.*"     # Contains "case packer"
    ]
    
    # Keywords that typically indicate common items (not specific to one machine)
    common_item_indicators = [
        r"warranty",
        r"installation",
        r"documentation",
        r"training",
        r"spare\s*parts\s*kit",
        r"service",
        r"maintenance",
        r"validation",
        r"shipping",
        r"delivery"
    ]

    # Extract numeric price from item if available
    def extract_price(item):
        # Try to get numeric price if it exists
        if item.get("item_price_numeric") is not None:
            return float(item.get("item_price_numeric", 0))
        
        # Try to extract from price string
        price_str = item.get("selection_text", "") or item.get("item_price_str", "")
        if price_str:
            # Extract numbers from string
            import re
            matches = re.findall(r'[\d,]+\.\d+|\d+', price_str.replace(',', ''))
            if matches:
                try:
                    return float(matches[0])
                except ValueError:
                    pass
        return 0.0
    
    # Check if an item matches main machine patterns
    def is_main_machine(item):
        desc = item.get("description", "")
        if not desc:
            return False
            
        desc_lower = desc.lower()
        
        # Skip items that are clearly not main machines
        if desc_lower.startswith(("each", "option", "accessory", "optional")):
            return False
            
        # Check if price is above threshold (strong indicator of main machine)
        price = extract_price(item)
        if price >= price_threshold:
            return True
            
        # Check for main machine indicator patterns
        for pattern in main_machine_indicators:
            if re.search(pattern, desc_lower):
                return True
                
        return False
    
    # Check if an item is common to all machines
    def is_common_item(item):
        desc = item.get("description", "")
        if not desc:
            return False
        desc_lower = desc.lower()
        for pattern in common_item_indicators:
            if re.search(pattern, desc_lower):
                return True
        return False
    
    # Process all line items
    for item in line_items:
        # Add price calculations
        item["item_price_numeric"] = extract_price(item)
        
        if is_main_machine(item):
            # If we already have a machine, save it before starting a new one
            if current_machine:
                machines.append(current_machine)
                
            # Start a new machine
            desc = item.get("description", "")
            machine_name = desc.split('\n')[0] if '\n' in desc else desc
            current_machine = {
                "machine_name": machine_name,
                "main_item": item,
                "add_ons": []
            }
        elif is_common_item(item):
            # Item applies to all machines
            common_items.append(item)
        elif current_machine:
            # This is an add-on for the current machine
            current_machine["add_ons"].append(item)
        else:
            # If no current machine yet, this might be a standalone accessory
            # Add it to common items for now
            common_items.append(item)
    
    # Add the last machine if there is one
    if current_machine:
        machines.append(current_machine)
    
    # If no machines were found, create a default "Unknown Machine" group
    if not machines and line_items:
        machines.append({
            "machine_name": "Complete System",
            "main_item": line_items[0] if line_items else None,
            "add_ons": line_items[1:] if len(line_items) > 1 else []
        })
        # Clear common items as we've put everything in one machine
        common_items = []
    
    # Return machines and common items
    return {
        "machines": machines,
        "common_items": common_items
    }

# Example Usage (for testing this module directly)
if __name__ == '__main__':
    test_pdf_path = 'Importfab - CQC-22-2268R10-NP.pdf' 
    if os.path.exists(test_pdf_path):
        print(f"Testing with PDF: {test_pdf_path}")
        line_items = extract_line_item_details(test_pdf_path)
        print("\n--- Extracted Line Item Details ---")
        if line_items:
            for item in line_items:
                print(f"- Desc: '{item['description'][:60]}...', Qty: '{item['quantity_text']}', Selection: '{item['selection_text']}'")
        else:
            print("No line items found.")

        print("\n--- Testing Contextual Detail Extraction (Option B Style) ---")
        
        # Test with a short, unique trigger for the Monoblock
        monoblock_short_trigger = "Monoblock Model: Patriot FC 11"
        # Find the full description to ensure we pass it for context-aware stop word generation
        actual_monoblock_full_desc = next((d for d in line_items if monoblock_short_trigger.lower() in d['description'].lower()), None)
        
        if actual_monoblock_full_desc: # Check if found
            monoblock_context = extract_contextual_details(test_pdf_path, monoblock_short_trigger, [d['description'] for d in line_items])
            if monoblock_context:
                print(f"\nContext for '{monoblock_short_trigger}':")
                print(monoblock_context)
            else:
                print(f"No context found for '{monoblock_short_trigger}'.")
        else:
             print(f"Trigger '{monoblock_short_trigger}' not found in selected descriptions list.")

        fat_sat_short_trigger = "FAT / SAT Protocol Package"
        actual_fat_sat_full_desc = next((d for d in line_items if fat_sat_short_trigger.lower() in d['description'].lower()), None)
        if actual_fat_sat_full_desc:
            fat_sat_context = extract_contextual_details(test_pdf_path, fat_sat_short_trigger, [d['description'] for d in line_items])
            if fat_sat_context:
                print(f"\nContext for '{fat_sat_short_trigger}':")
                print(fat_sat_context)
            else:
                print(f"No context found for '{fat_sat_short_trigger}'.")
        else:
            print(f"Trigger '{fat_sat_short_trigger}' not found in selected descriptions list.")
    else:
        print(f"Test PDF not found: {test_pdf_path}")
