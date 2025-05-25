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

def generate_commercial_invoice_data(client_data: Dict, priced_items: List[Dict]) -> Dict[str, str]:
    """
    Prepares the data dictionary for filling the Commercial Invoice template
    based on CRM client data and their priced items.
    """
    output_data = {}
    
    # --- Direct Mappings from client_data ---
    output_data["customer_name"] = client_data.get("customer_name", "")
    output_data["company_name"] = client_data.get("customer_name", "")
    output_data["invoice_no"] = f"INV-{client_data.get('quote_ref', 'XXXX')}"
    output_data["quote_no"] = client_data.get("quote_ref", "")
    output_data["order_number"] = client_data.get("quote_ref", "")
    output_data["customer_po"] = client_data.get("customer_po", "")
    
    # Format addresses
    sold_to_addr_lines = client_data.get("sold_to_address", "").split('\n')
    output_data["sold_to_address_1"] = sold_to_addr_lines[0] if len(sold_to_addr_lines) > 0 else ""
    output_data["sold_to_address_2"] = sold_to_addr_lines[1] if len(sold_to_addr_lines) > 1 else ""
    output_data["sold_to_address_3"] = sold_to_addr_lines[2] if len(sold_to_addr_lines) > 2 else ""

    ship_to_addr_lines = client_data.get("ship_to_address", "").split('\n')
    output_data["ship_to_address_1"] = ship_to_addr_lines[0] if len(ship_to_addr_lines) > 0 else ""
    output_data["ship_to_address_2"] = ship_to_addr_lines[1] if len(ship_to_addr_lines) > 1 else ""
    output_data["ship_to_address_3"] = ship_to_addr_lines[2] if len(ship_to_addr_lines) > 2 else ""
    
    # Contact information
    output_data["telephone"] = client_data.get("telephone", "")
    output_data["customer_contact"] = client_data.get("customer_contact_person", "")
    output_data["tax_id"] = client_data.get("tax_id", "")
    
    # --- Invoice specific fields ---
    output_data["invoice_date"] = datetime.now().strftime("%Y-%m-%d")
    output_data["country_of_origin"] = "United States" # Default or from client_data
    output_data["country_of_destination"] = client_data.get("country_destination", "")
    output_data["incoterm"] = client_data.get("incoterm", "EXW")
    output_data["payment_terms"] = client_data.get("payment_terms", "Net 30 days")
    output_data["currency"] = client_data.get("currency", "USD")
    
    # --- Line Items with prices ---
    MAX_INVOICE_LINES = 10
    total_value = 0.0
    
    for i in range(MAX_INVOICE_LINES):
        if i < len(priced_items):
            item = priced_items[i]
            description = item.get("item_description", "")
            quantity = item.get("item_quantity", "1")
            # Try to extract numeric price from price string
            price_str = item.get("item_price_str", "")
            unit_price = 0.0
            
            # Extract numeric price if available
            if item.get("item_price") is not None:
                unit_price = float(item.get("item_price", 0.0))
            else:
                # Try to parse from price string
                import re
                price_match = re.search(r'[\d,]+\.\d+|\d+', price_str)
                if price_match:
                    unit_price = float(price_match.group().replace(',', ''))
            
            # Calculate line total
            try:
                qty_numeric = float(quantity) if isinstance(quantity, (int, float)) or (isinstance(quantity, str) and quantity.isdigit()) else 1
                line_total = unit_price * qty_numeric
                total_value += line_total
            except (ValueError, TypeError):
                line_total = unit_price  # Default to unit price if quantity can't be parsed
            
            output_data[f"item_{i+1}_desc"] = description
            output_data[f"item_{i+1}_qty"] = str(quantity)
            output_data[f"item_{i+1}_unit_price"] = f"{unit_price:.2f}"
            output_data[f"item_{i+1}_total"] = f"{line_total:.2f}"
            output_data[f"item_{i+1}_hs_code"] = item.get("hs_code", "")
        else:
            output_data[f"item_{i+1}_desc"] = ""
            output_data[f"item_{i+1}_qty"] = ""
            output_data[f"item_{i+1}_unit_price"] = ""
            output_data[f"item_{i+1}_total"] = ""
            output_data[f"item_{i+1}_hs_code"] = ""
    
    # --- Totals ---
    output_data["subtotal"] = f"{total_value:.2f}"
    
    # Calculate taxes if applicable
    tax_rate = client_data.get("tax_rate", 0.0)
    tax_amount = total_value * tax_rate / 100 if tax_rate else 0.0
    output_data["tax_rate"] = f"{tax_rate:.2f}%" if tax_rate else "0.00%"
    output_data["tax_amount"] = f"{tax_amount:.2f}"
    
    # Calculate shipping costs if available
    shipping_cost = client_data.get("shipping_cost", 0.0)
    output_data["shipping_cost"] = f"{shipping_cost:.2f}"
    
    # Calculate grand total
    grand_total = total_value + tax_amount + shipping_cost
    output_data["grand_total"] = f"{grand_total:.2f}"
    
    # Add any notes
    output_data["invoice_notes"] = client_data.get("invoice_notes", "")
    
    print("Prepared data for Commercial Invoice:", json.dumps(output_data, indent=2))
    return output_data

def generate_certificate_of_origin_data(client_data: Dict, priced_items: List[Dict]) -> Dict[str, str]:
    """
    Prepares the data dictionary for filling the Certificate of Origin template
    based on CRM client data and their priced items.
    """
    output_data = {}
    
    # --- Exporter Information ---
    output_data["exporter_name"] = "Your Company Name"  # Company issuing the certificate
    output_data["exporter_address_1"] = "123 Main Street"
    output_data["exporter_address_2"] = "City, State, ZIP"
    output_data["exporter_address_3"] = "United States"
    output_data["tax_id"] = "12-3456789"  # Company tax ID
    
    # --- Importer Information (from client data) ---
    output_data["importer_name"] = client_data.get("customer_name", "")
    
    ship_to_addr_lines = client_data.get("ship_to_address", "").split('\n')
    output_data["importer_address_1"] = ship_to_addr_lines[0] if len(ship_to_addr_lines) > 0 else ""
    output_data["importer_address_2"] = ship_to_addr_lines[1] if len(ship_to_addr_lines) > 1 else ""
    output_data["importer_address_3"] = ship_to_addr_lines[2] if len(ship_to_addr_lines) > 2 else ""
    
    # --- Certificate Information ---
    output_data["certificate_no"] = f"COO-{client_data.get('quote_ref', 'XXXX')}"
    output_data["issue_date"] = datetime.now().strftime("%Y-%m-%d")
    output_data["country_of_origin"] = "United States"  # Or from configuration
    output_data["country_of_destination"] = client_data.get("country_destination", "")
    
    # --- Transport Information ---
    output_data["transport_method"] = client_data.get("transport_method", "Sea Freight")
    output_data["vessel_name"] = client_data.get("vessel_name", "")
    output_data["port_of_loading"] = "Los Angeles, CA"  # Default or from configuration
    output_data["port_of_discharge"] = client_data.get("port_of_discharge", "")
    
    # --- Reference Numbers ---
    output_data["invoice_no"] = f"INV-{client_data.get('quote_ref', 'XXXX')}"
    output_data["order_number"] = client_data.get("quote_ref", "")
    output_data["customer_po"] = client_data.get("customer_po", "")
    
    # --- Item Details ---
    MAX_ITEMS = 10
    
    for i in range(MAX_ITEMS):
        if i < len(priced_items):
            item = priced_items[i]
            description = item.get("item_description", "")
            quantity = item.get("item_quantity", "1")
            hs_code = item.get("hs_code", "")
            
            output_data[f"item_{i+1}_desc"] = description
            output_data[f"item_{i+1}_qty"] = str(quantity)
            output_data[f"item_{i+1}_hs_code"] = hs_code
            output_data[f"item_{i+1}_origin_criterion"] = "A"  # Default or from item data
            output_data[f"item_{i+1}_producer"] = "YES"  # Default or from configuration
        else:
            output_data[f"item_{i+1}_desc"] = ""
            output_data[f"item_{i+1}_qty"] = ""
            output_data[f"item_{i+1}_hs_code"] = ""
            output_data[f"item_{i+1}_origin_criterion"] = ""
            output_data[f"item_{i+1}_producer"] = ""
    
    # --- Certification ---
    output_data["authorized_signature"] = "Authorized Signatory"
    output_data["signatory_company"] = "Your Company Name"
    output_data["signatory_title"] = "Export Manager"
    output_data["signatory_date"] = datetime.now().strftime("%Y-%m-%d")
    output_data["certification_text"] = "I certify that the goods described above originate in the United States and that the information given is true and correct."
    
    print("Prepared data for Certificate of Origin:", json.dumps(output_data, indent=2))
    return output_data

# We can add generate_commercial_invoice_data etc. here later 