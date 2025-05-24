from typing import Dict, List, Optional
from datetime import datetime
import json

# We might need access to CRM loading functions if not passed all data directly
# from crm_utils import load_client_by_quote_ref, load_priced_items_for_quote 
# (Assuming client_data and priced_items are passed in for now)

def generate_packing_slip_data(client_data: Dict, priced_items: List[Dict]) -> Dict[str, str]:
    """
    Prepares the data dictionary for filling the Packing Slip template 
    based on CRM client data and their priced items.
    """
    output_data = {}

    # --- Direct Mappings from client_data (clients table) ---
    # Ensure placeholder keys here match your packing_slip_template.docx
    output_data["customer_name"] = client_data.get("customer_name", "")
    output_data["company_name"] = client_data.get("customer_name", "") # Often the same for packing slip
    output_data["quote_no"] = client_data.get("quote_ref", "")
    output_data["order_number"] = client_data.get("quote_ref", "") # Often same as quote no
    output_data["customer_po"] = client_data.get("customer_po", "")
    
    # Addresses need careful handling if stored as single block vs separate lines in CRM
    # Assuming sold_to_address and ship_to_address in CRM are multi-line strings or to be split
    # For template placeholders like sold_to_address_1, sold_to_address_2, etc.
    sold_to_addr_lines = client_data.get("sold_to_address", "").split('\n')
    output_data["sold_to_address_1"] = sold_to_addr_lines[0] if len(sold_to_addr_lines) > 0 else ""
    output_data["sold_to_address_2"] = sold_to_addr_lines[1] if len(sold_to_addr_lines) > 1 else ""
    output_data["sold_to_address_3"] = sold_to_addr_lines[2] if len(sold_to_addr_lines) > 2 else ""

    ship_to_addr_lines = client_data.get("ship_to_address", "").split('\n')
    output_data["ship_to_address_1"] = ship_to_addr_lines[0] if len(ship_to_addr_lines) > 0 else ""
    output_data["ship_to_address_2"] = ship_to_addr_lines[1] if len(ship_to_addr_lines) > 1 else ""
    output_data["ship_to_address_3"] = ship_to_addr_lines[2] if len(ship_to_addr_lines) > 2 else ""

    output_data["telephone"] = client_data.get("telephone", "")
    output_data["customer_contact"] = client_data.get("customer_contact_person", "")
    output_data["customer_number"] = client_data.get("customer_number_internal", "") # Assuming this key from CRM

    # --- Fields that might need specific logic or are usually new for a packing slip ---
    output_data["packing_slip_no"] = f"PS-{client_data.get('quote_ref', 'XXXX')}" # Example generation
    output_data["order_date"] = client_data.get("processing_date", datetime.now().strftime("%Y-%m-%d")) # Use CRM processing date or today
    output_data["ship_date"] = datetime.now().strftime("%Y-%m-%d") # Default to today, can be made editable
    output_data["ax_number"] = "AX-INTERNAL-123"  # Placeholder - How will this be generated/sourced?
    output_data["ox_number"] = "OX-INTERNAL-456"  # Placeholder
    output_data["serial_number"] = client_data.get("serial_number", "TBD")
    output_data["via"] = client_data.get("shipping_via", "TBD")
    output_data["incoterm"] = client_data.get("incoterm", "EXW") # Default or from CRM
    output_data["tax_id"] = client_data.get("tax_id", "")

    # --- Line Items from priced_items ---
    # Assuming your template has placeholders like item_1_desc, item_1_qty, item_2_desc, item_2_qty, etc.
    # And H.S codes are per item. For now, let's assume a fixed number of lines in template.
    MAX_PACKING_SLIP_LINES = 10 # Example: template supports up to 10 lines
    for i in range(MAX_PACKING_SLIP_LINES):
        if i < len(priced_items):
            item = priced_items[i]
            output_data[f"item_{i+1}_desc"] = item.get("item_description", "")
            output_data[f"item_{i+1}_qty"] = str(item.get("item_quantity", "")) # Ensure it's a string
            output_data[f"item_{i+1}_hs_code"] = item.get("hs_code", "") # Assuming hs_code is in priced_items
        else:
            output_data[f"item_{i+1}_desc"] = ""
            output_data[f"item_{i+1}_qty"] = ""
            output_data[f"item_{i+1}_hs_code"] = ""
    
    # Add any other calculated fields: total quantity, number of packages (may need user input or LLM)
    output_data["total_qty_items"] = str(sum(int(item.get("item_quantity", 0) or 0) for item in priced_items if str(item.get("item_quantity", "")).isdigit()))

    print("Prepared data for Packing Slip:", json.dumps(output_data, indent=2))
    return output_data

# We can add generate_commercial_invoice_data etc. here later 