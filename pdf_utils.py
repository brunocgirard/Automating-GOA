import pdfplumber
import re
import os
from typing import List, Tuple, Dict, Optional, Any
import traceback
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_table_headers(table: List[List[Optional[str]]]) -> Optional[Dict[str, int]]:
    """
    Identifies columns for 'description', 'quantity', and 'final_price'.
    Returns a dictionary mapping these conceptual names to their column indices.
    """
    if not table or not table[0]: return None
    header_row = table[0]
    headers = {}
    desc_keys = ["description", "item", "option", "feature", "article", "désignation"]
    qty_keys = ["qty", "quantity", "qté"]
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

def extract_line_item_details(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extracts description, quantity text, and selection/price text for selected items.
    Returns: List of dicts, e.g., 
    [{'description': 'Item A', 'quantity_text': '1', 'selection_text': '1,250.00'}, ...]
    """
    extracted_items: List[Dict[str, Any]] = []
    unique_items_set = set() # To avoid duplicate entries
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table_data in tables:
                    if not table_data: continue
                    headers = find_table_headers(table_data)
                    if not headers: continue

                    desc_col_idx = headers["description"]
                    sel_text_col_idx = headers["selection_text_source"]
                    qty_col_idx = headers.get("quantity", -1) # Get quantity index, default to -1 if not found
                    
                    headers_for_selection_check = {"description": desc_col_idx, "selection": sel_text_col_idx}

                    for row in table_data[1:]: # Skip header row
                        if is_row_selected(row, headers_for_selection_check):
                            description = str(row[desc_col_idx]).strip() if len(row) > desc_col_idx and row[desc_col_idx] else None
                            selection_text = str(row[sel_text_col_idx]).strip() if len(row) > sel_text_col_idx and row[sel_text_col_idx] else None
                            quantity_text = str(row[qty_col_idx]).strip() if qty_col_idx != -1 and len(row) > qty_col_idx and row[qty_col_idx] else None
                            
                            if description: # Must have a description
                                item_tuple = (description, quantity_text, selection_text)
                                if item_tuple not in unique_items_set:
                                    extracted_items.append({
                                        "description": description,
                                        "quantity_text": quantity_text,
                                        "selection_text": selection_text
                                    })
                                    unique_items_set.add(item_tuple)
    except Exception as e:
        logger.error(f"Error in extract_line_item_details for '{pdf_path}': {e}"); traceback.print_exc()
    return extracted_items

def extract_full_pdf_text(pdf_path: str) -> str:
    """
    Extracts all text content from all pages of the PDF.
    """
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n" 
    except Exception as e:
        logger.error(f"Error extracting full text from PDF '{pdf_path}': {e}")
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
        logger.error(f"Error extracting contextual details for trigger '{trigger_start_text_lower}': {e}")
    
    return "\n".join(contextual_text_lines)

def identify_machines_from_items(items: List[Dict[str, Any]], price_threshold: float = 10000) -> List[Dict[str, Any]]:
    """
    Identify potential machines from a list of line items.
    Returns a list of dictionaries representing identified machines with their items.
    
    Args:
        items: List of line item dictionaries from PDF extraction
        price_threshold: Price threshold for identifying machines (default: 10000)
                         Higher = more conservative (fewer machines)
                         Lower = more aggressive (more machines)
    
    Returns:
        List of dictionaries, each containing:
        - name: The machine name/model
        - items: List of items that belong to this machine
        - is_main_machine: Boolean flag (default True)
    """
    if not items:
        return []
    
    # Keywords that might indicate a main machine
    machine_indicators = [
        "machine", "system", "unit", "model", "equipment", "device",
        # Industrial machinery types
        "press", "brake", "shear", "laser", "cutter", "welder", "robot",
        "mill", "lathe", "grinder", "drill", "saw", "bender",
        # Packaging/processing machinery
        "filler", "capper", "labeler", "cartoner", "case packer", "palletizer",
        "unscrambler", "blister", "thermoformer", "wrapper", "sealer",
        # Terminology commonly used in quotes
        "monoblock", "monobloc", "rotary", "linear", "inline", "form fill seal", "checkweigher",
        # Model indicators
        "series", "type", "line", "platform"
    ]
    
    # Terms that typically indicate add-ons rather than main machines
    addon_indicators = [
        "option", "accessory", "kit", "package", "module", "attachment",
        "upgrade", "spare", "part", "add-on", "addon", "additional",
        "enhancement", "feature", "optional", "bundle"
    ]
    
    # Terms that typically indicate common items not specific to one machine
    common_item_indicators = [
        "warranty", "installation", "documentation", "manual", "training",
        "service", "maintenance", "validation", "shipping", "delivery",
        "travel", "commissioning", "startup", "certification", "compliance",
        "packaging", "iqoqpq", "iq/oq/pq", "fat", "sat", "protocol"
    ]
    
    # Helper function to extract price as numeric value
    def extract_price(item):
        price_text = item.get('selection_text', '')
        if not price_text:
            return 0
        
        # Try to extract numeric price from text
        numeric_chars = re.sub(r'[^\d.]', '', price_text.replace(',', '.'))
        try:
            return float(numeric_chars) if numeric_chars else 0
        except ValueError:
            return 0
    
    # Add numeric price field to items for easier processing
    for item in items:
        item['item_price_numeric'] = extract_price(item)
    
    # Helper function to determine if an item might be a main machine
    def is_potential_machine(item):
        desc = item.get('description', '').lower()
        
        # Check for add-on indicators first (these override machine detection)
        for indicator in addon_indicators:
            if indicator in desc and desc.startswith(indicator):
                return False
                
        # Check for common item indicators
        for indicator in common_item_indicators:
            if indicator in desc and (desc.startswith(indicator) or f" {indicator} " in f" {desc} "):
                return False
        
        # Check for machine indicators in description
        for indicator in machine_indicators:
            if indicator in desc:
                return True
                
        # Check for price - machines are usually expensive
        price = item.get('item_price_numeric', 0)
        if price > price_threshold:
            return True
            
        # Check for quantity - machines usually have qty 1
        qty_text = item.get('quantity_text', '')
        try:
            qty = int(re.sub(r'[^\d]', '', qty_text)) if qty_text else 0
            if qty == 1 and price > price_threshold/2:  # Half the threshold for qty=1 items
                return True
        except ValueError:
            pass
            
        # Check for model numbers in description (e.g., "Model ABC-123")
        if re.search(r'model\s+[a-z0-9]+-?[a-z0-9]+', desc) or re.search(r'series\s+[a-z0-9]+', desc):
            return True
            
        return False
    
    # First pass: identify potential machines and common items
    machines = []
    potential_addons = []
    common_items = []
    
    for item in items:
        desc = item.get('description', '').lower()
        
        # Check for common items first
        is_common = False
        for indicator in common_item_indicators:
            if indicator in desc and (desc.startswith(indicator) or f" {indicator} " in f" {desc} "):
                common_items.append(item)
                is_common = True
                break
                
        if is_common:
            continue
        
        # Then check if it's a machine
        if is_potential_machine(item):
            # Create a new machine entry
            machines.append({
                "name": item.get('description', 'Unknown Machine').split('\n')[0],  # Use only the first line
                "items": [item],
                "is_main_machine": True
            })
        else:
            # If not a machine or common item, it's a potential addon
            potential_addons.append(item)
    
    # If no machines found, use price-based heuristic
    if not machines and items:
        # Sort by price if available
        sorted_items = sorted(items, 
                             key=lambda x: x.get('item_price_numeric', 0),
                             reverse=True)
        
        # Take the highest priced item as a machine if it's above threshold
        if sorted_items[0].get('item_price_numeric', 0) > 1000:
            machines.append({
                "name": sorted_items[0].get('description', 'Unknown Machine').split('\n')[0],
                "items": [sorted_items[0]],
                "is_main_machine": True
            })
            
            # Remove the selected item from sorted items
            potential_addons = sorted_items[1:]
        else:
            # No clear machine found, put all items in common
            common_items.extend(items)
            potential_addons = []
    
    # Second pass: Assign potential add-ons to machines
    if machines and potential_addons:
        # Sort machines by their position in the original list
        # This assumes that add-ons usually follow their main machine in the quote
        machine_indices = []
        for i, machine in enumerate(machines):
            main_item = machine["items"][0]
            machine_indices.append((i, items.index(main_item)))
        machine_indices.sort(key=lambda x: x[1])
        
        # For each potential addon, assign to the nearest preceding machine
        for addon in potential_addons:
            addon_index = items.index(addon)
            assigned = False
            
            # Find the last machine that appears before this addon
            prev_machine_idx = -1
            for i, (machine_list_idx, machine_item_idx) in enumerate(machine_indices):
                if machine_item_idx < addon_index:
                    prev_machine_idx = machine_list_idx
                else:
                    # We've passed the addon position, so use the previous machine
                    break
            
            if prev_machine_idx >= 0:
                # Assign to the previous machine
                machines[prev_machine_idx]["items"].append(addon)
                assigned = True
            
            if not assigned:
                # If couldn't assign to a machine, add to common items
                common_items.append(addon)
    
    # Add common items as a separate group if any exist
    if common_items:
        machines.append({
            "name": "Common Items",
            "items": common_items,
            "is_main_machine": False
        })
    
    return machines

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