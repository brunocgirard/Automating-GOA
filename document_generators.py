"""
Utility module for generating export document data from machine and client information.
Includes generators for Packing Slip, Commercial Invoice, and Certificate of Origin.
"""

import re
from typing import Dict, List, Any, Optional
import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_hs_code(description: str) -> str:
    """
    Extract HS (Harmonized System) code from item description if present.
    """
    # Common patterns for HS codes in descriptions
    patterns = [
        r'HS[:\s]+(\d{4,10})',  # HS: 12345678
        r'HTS[:\s]+(\d{4,10})',  # HTS: 12345678
        r'H\.S\.[:\s]+(\d{4,10})',  # H.S.: 12345678
        r'Harmonized\s+System[:\s]+(\d{4,10})',  # Harmonized System: 12345678
        r'Tariff[:\s]+(\d{4,10})'  # Tariff: 12345678
    ]
    
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # Default codes for common machinery types if not found
    if re.search(r'filler|filling machine', description, re.IGNORECASE):
        return "8422.30"
    elif re.search(r'capper|capping machine', description, re.IGNORECASE):
        return "8422.30"
    elif re.search(r'labeler|labelling machine', description, re.IGNORECASE):
        return "8422.30"
    elif re.search(r'wrapper|wrapping machine', description, re.IGNORECASE):
        return "8422.40"
    elif re.search(r'cartoner', description, re.IGNORECASE):
        return "8422.40"
    elif re.search(r'case\s+packer|packer', description, re.IGNORECASE):
        return "8422.40"
    elif re.search(r'palletizer', description, re.IGNORECASE):
        return "8422.30"
    elif re.search(r'conveyor', description, re.IGNORECASE):
        return "8428.33"
    elif re.search(r'spare\s+parts|parts', description, re.IGNORECASE):
        return "8431.90"
    
    # Default if nothing else matches
    return "8422.90"  # Parts for packaging machinery

def extract_country_of_origin(description: str, client_data: Dict[str, Any]) -> str:
    """
    Extract country of origin from item description or client data.
    """
    # Common patterns for country of origin in descriptions
    patterns = [
        r'Made in ([A-Za-z\s]+)',
        r'Origin[:\s]+([A-Za-z\s]+)',
        r'Country of Origin[:\s]+([A-Za-z\s]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Check client data for default country
    if "manufacturer_country" in client_data and client_data["manufacturer_country"]:
        return client_data["manufacturer_country"]
    
    # Default to a common value for machinery
    return "USA"  # Default, change as needed

def extract_net_weight(description: str, default_weight: float = 100.0) -> float:
    """
    Extract net weight from item description or provide a default.
    """
    # Patterns for weight in descriptions
    patterns = [
        r'Net Weight[:\s]+([\d,.]+)\s*kg',
        r'Weight[:\s]+([\d,.]+)\s*kg',
        r'([\d,.]+)\s*kg'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            weight_str = match.group(1).replace(',', '.')
            try:
                return float(weight_str)
            except ValueError:
                pass
    
    # Estimate weight based on machine type if not found
    if re.search(r'filler|filling machine', description, re.IGNORECASE):
        return 1200.0
    elif re.search(r'capper', description, re.IGNORECASE):
        return 800.0
    elif re.search(r'labeler', description, re.IGNORECASE):
        return 600.0
    elif re.search(r'cartoner', description, re.IGNORECASE):
        return 1500.0
    elif re.search(r'case\s+packer', description, re.IGNORECASE):
        return 2000.0
    elif re.search(r'palletizer', description, re.IGNORECASE):
        return 3000.0
    elif re.search(r'conveyor', description, re.IGNORECASE):
        return 500.0
    elif re.search(r'spare\s+parts|parts', description, re.IGNORECASE):
        return 50.0
    
    # Default if nothing else matches
    return default_weight

def extract_dimensions(description: str) -> Dict[str, float]:
    """
    Extract dimensions from item description or provide defaults.
    """
    # Default dimensions (in cm)
    default_dims = {"length": 150.0, "width": 120.0, "height": 180.0}
    
    # Pattern for dimensions in descriptions
    # Example: "Dimensions: 150 x 120 x 180 cm"
    pattern = r'Dimensions?[:\s]+([\d,.]+)\s*[xX]\s*([\d,.]+)\s*[xX]\s*([\d,.]+)\s*cm'
    
    match = re.search(pattern, description, re.IGNORECASE)
    if match:
        try:
            return {
                "length": float(match.group(1).replace(',', '.')),
                "width": float(match.group(2).replace(',', '.')),
                "height": float(match.group(3).replace(',', '.'))
            }
        except ValueError:
            pass
    
    # Estimate dimensions based on machine type if not found
    if re.search(r'filler|filling machine', description, re.IGNORECASE):
        return {"length": 200.0, "width": 150.0, "height": 180.0}
    elif re.search(r'capper', description, re.IGNORECASE):
        return {"length": 150.0, "width": 120.0, "height": 160.0}
    elif re.search(r'labeler', description, re.IGNORECASE):
        return {"length": 130.0, "width": 110.0, "height": 150.0}
    elif re.search(r'cartoner', description, re.IGNORECASE):
        return {"length": 250.0, "width": 180.0, "height": 200.0}
    elif re.search(r'case\s+packer', description, re.IGNORECASE):
        return {"length": 300.0, "width": 200.0, "height": 220.0}
    elif re.search(r'palletizer', description, re.IGNORECASE):
        return {"length": 350.0, "width": 250.0, "height": 300.0}
    elif re.search(r'conveyor', description, re.IGNORECASE):
        return {"length": 400.0, "width": 80.0, "height": 100.0}
    elif re.search(r'spare\s+parts|parts', description, re.IGNORECASE):
        return {"length": 80.0, "width": 60.0, "height": 40.0}
    
    return default_dims

def estimate_package_count(machines: List[Dict[str, Any]], common_items: List[Dict[str, Any]]) -> int:
    """
    Estimate the number of packages needed to ship the equipment.
    """
    # Start with base count for main machines (each machine typically requires multiple packages)
    package_count = 0
    
    for machine in machines:
        machine_name = machine.get("machine_name", "").lower()
        
        # Estimate based on machine type
        if re.search(r'filler|filling machine', machine_name, re.IGNORECASE):
            package_count += 4  # Filler typically ships in multiple crates
        elif re.search(r'capper', machine_name, re.IGNORECASE):
            package_count += 2
        elif re.search(r'labeler', machine_name, re.IGNORECASE):
            package_count += 2
        elif re.search(r'cartoner', machine_name, re.IGNORECASE):
            package_count += 3
        elif re.search(r'case\s+packer', machine_name, re.IGNORECASE):
            package_count += 3
        elif re.search(r'palletizer', machine_name, re.IGNORECASE):
            package_count += 5
        elif re.search(r'conveyor', machine_name, re.IGNORECASE):
            package_count += 2
        else:
            package_count += 2  # Default for unrecognized machines
        
        # Add for add-ons
        add_ons = machine.get("add_ons", [])
        if add_ons:
            # Group similar add-ons into one package where possible
            package_count += max(1, len(add_ons) // 3)
    
    # Add for common items
    if common_items:
        package_count += max(1, len(common_items) // 5)
    
    # Ensure minimum of 1 package
    return max(1, package_count)

def generate_packing_slip_data(client_data: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate data for a packing slip document.
    
    Args:
        client_data: Dictionary containing client information
        items: List of items to include in the packing slip
        
    Returns:
        Dictionary with data for packing slip fields
    """
    # Get today's date for packing slip
    today = datetime.datetime.now()
    
    # Extract customer information
    customer_name = client_data.get("customer_name", "")
    quote_ref = client_data.get("quote_ref", "")
    country_destination = client_data.get("country_destination", "")
    ship_to_address = client_data.get("ship_to_address", "")
    
    # Generate packing slip number
    packing_slip_no = f"PS-{quote_ref}-{today.strftime('%Y%m%d')}"
    
    # Separate machine items from common items for better estimation
    machine_items = []
    common_items = []
    
    for item in items:
        desc = item.get("description", "").lower()
        if any(kw in desc for kw in ["warranty", "installation", "training", "shipping", "documentation"]):
            common_items.append(item)
        else:
            machine_items.append(item)
    
    # Estimate package count
    package_count = estimate_package_count(
        [{"machine_name": i.get("description", ""), "add_ons": []} for i in machine_items], 
        common_items
    )
    
    # Calculate total weight and dimensions
    total_net_weight = sum(extract_net_weight(item.get("description", ""), 100.0) for item in items)
    total_gross_weight = total_net_weight * 1.15  # Add 15% for packaging
    
    # Prepare item list with details
    item_details = []
    for i, item in enumerate(items):
        description = item.get("description", "").split('\n')[0]  # Use only first line
        quantity = item.get("quantity_text", "1")
        # Clean quantity text to get numeric value if possible
        try:
            qty_numeric = int(re.sub(r'[^\d]', '', quantity))
        except ValueError:
            qty_numeric = 1
            
        net_weight = extract_net_weight(item.get("description", ""))
        dimensions = extract_dimensions(item.get("description", ""))
        
        item_details.append({
            "item_no": i + 1,
            "description": description,
            "quantity": qty_numeric,
            "net_weight": net_weight,
            "dimensions": dimensions
        })
    
    # Build packing slip data dictionary
    packing_slip_data = {
        "packing_slip_no": packing_slip_no,
        "date": today.strftime("%B %d, %Y"),
        "customer_name": customer_name,
        "quote_ref": quote_ref,
        "destination_country": country_destination,
        "ship_to_address": ship_to_address,
        "package_count": str(package_count),
        "total_net_weight": f"{total_net_weight:.2f} kg",
        "total_gross_weight": f"{total_gross_weight:.2f} kg",
        "shipping_terms": client_data.get("shipping_terms", "EXW"),
        "carrier": client_data.get("carrier", "To Be Determined"),
        "item_list": "\n".join([f"{item['item_no']}. {item['description']} - Qty: {item['quantity']}" for item in item_details])
    }
    
    # Add additional fields that might be in the template
    packing_slip_data.update({
        "shipper_name": "Your Company Name",
        "shipper_address": "Your Company Address",
        "tracking_number": "TBD",
        "special_instructions": client_data.get("special_instructions", "")
    })
    
    return packing_slip_data

def generate_commercial_invoice_data(client_data: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate data for a commercial invoice document.
    
    Args:
        client_data: Dictionary containing client information
        items: List of items to include in the commercial invoice
        
    Returns:
        Dictionary with data for commercial invoice fields
    """
    # Get today's date for invoice
    today = datetime.datetime.now()
    
    # Extract customer information
    customer_name = client_data.get("customer_name", "")
    quote_ref = client_data.get("quote_ref", "")
    country_destination = client_data.get("country_destination", "")
    ship_to_address = client_data.get("ship_to_address", "")
    sold_to_address = client_data.get("sold_to_address", ship_to_address)
    
    # Generate invoice number
    invoice_no = f"INV-{quote_ref}-{today.strftime('%Y%m%d')}"
    
    # Calculate total price
    total_price = 0.0
    for item in items:
        price_text = item.get("selection_text", "0.00")
        try:
            # Extract numeric value from price text
            price_str = re.sub(r'[^\d.]', '', price_text.replace(',', '.'))
            if price_str:
                price = float(price_str)
                total_price += price
        except ValueError:
            pass
    
    # Prepare item list with details
    item_details = []
    for i, item in enumerate(items):
        description = item.get("description", "").split('\n')[0]  # Use only first line
        quantity = item.get("quantity_text", "1")
        # Clean quantity text to get numeric value if possible
        try:
            qty_numeric = int(re.sub(r'[^\d]', '', quantity))
        except ValueError:
            qty_numeric = 1
            
        # Extract price
        price_text = item.get("selection_text", "0.00")
        try:
            price_str = re.sub(r'[^\d.]', '', price_text.replace(',', '.'))
            price = float(price_str) if price_str else 0.0
        except ValueError:
            price = 0.0
            
        # Extract other commercial details
        hs_code = extract_hs_code(item.get("description", ""))
        country_of_origin = extract_country_of_origin(item.get("description", ""), client_data)
        
        item_details.append({
            "item_no": i + 1,
            "description": description,
            "quantity": qty_numeric,
            "unit_price": price / qty_numeric if qty_numeric > 0 else price,
            "total_price": price,
            "hs_code": hs_code,
            "country_of_origin": country_of_origin
        })
    
    # Build commercial invoice data dictionary
    commercial_invoice_data = {
        "invoice_no": invoice_no,
        "invoice_date": today.strftime("%B %d, %Y"),
        "customer_name": customer_name,
        "quote_ref": quote_ref,
        "destination_country": country_destination,
        "ship_to_address": ship_to_address,
        "sold_to_address": sold_to_address,
        "total_price": f"{total_price:.2f}",
        "currency": "USD",  # Default currency
        "incoterms": client_data.get("incoterms", "EXW"),
        "payment_terms": client_data.get("payment_terms", "Net 30 days"),
        "item_list": "\n".join([
            f"{item['item_no']}. {item['description']} - "
            f"Qty: {item['quantity']} - "
            f"Unit: ${item['unit_price']:.2f} - "
            f"Total: ${item['total_price']:.2f} - "
            f"HS: {item['hs_code']} - "
            f"Origin: {item['country_of_origin']}"
            for item in item_details
        ])
    }
    
    # Add additional fields that might be in the template
    commercial_invoice_data.update({
        "exporter_name": "Your Company Name",
        "exporter_address": "Your Company Address",
        "exporter_tax_id": "Your Tax ID",
        "customer_po": client_data.get("customer_po", ""),
        "shipping_method": client_data.get("shipping_method", "Ocean Freight"),
        "notes": "This is a commercial invoice for customs purposes only."
    })
    
    return commercial_invoice_data

def generate_certificate_of_origin_data(client_data: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate data for a certificate of origin document.
    
    Args:
        client_data: Dictionary containing client information
        items: List of items to include in the certificate of origin
        
    Returns:
        Dictionary with data for certificate of origin fields
    """
    # Get today's date for certificate
    today = datetime.datetime.now()
    
    # Extract customer information
    customer_name = client_data.get("customer_name", "")
    quote_ref = client_data.get("quote_ref", "")
    country_destination = client_data.get("country_destination", "")
    ship_to_address = client_data.get("ship_to_address", "")
    
    # Generate certificate number
    certificate_no = f"COO-{quote_ref}-{today.strftime('%Y%m%d')}"
    
    # Determine primary country of origin (most common one)
    origin_countries = {}
    for item in items:
        country = extract_country_of_origin(item.get("description", ""), client_data)
        origin_countries[country] = origin_countries.get(country, 0) + 1
    
    primary_origin = max(origin_countries.items(), key=lambda x: x[1])[0] if origin_countries else "USA"
    
    # Prepare item list with details
    item_details = []
    for i, item in enumerate(items):
        description = item.get("description", "").split('\n')[0]  # Use only first line
        quantity = item.get("quantity_text", "1")
        # Clean quantity text to get numeric value if possible
        try:
            qty_numeric = int(re.sub(r'[^\d]', '', quantity))
        except ValueError:
            qty_numeric = 1
            
        # Extract commercial details
        hs_code = extract_hs_code(item.get("description", ""))
        country_of_origin = extract_country_of_origin(item.get("description", ""), client_data)
        
        item_details.append({
            "item_no": i + 1,
            "description": description,
            "quantity": qty_numeric,
            "hs_code": hs_code,
            "country_of_origin": country_of_origin,
            "origin_criteria": "Wholly Obtained" if country_of_origin == primary_origin else "Not Wholly Obtained"
        })
    
    # Build certificate of origin data dictionary
    certificate_data = {
        "certificate_no": certificate_no,
        "certificate_date": today.strftime("%B %d, %Y"),
        "exporter_name": "Your Company Name",
        "exporter_address": "Your Company Address",
        "producer_name": "Your Company Name",  # Often the same as exporter
        "producer_address": "Your Company Address",
        "importer_name": customer_name,
        "importer_address": ship_to_address,
        "destination_country": country_destination,
        "primary_origin": primary_origin,
        "transport_details": client_data.get("transport_details", "Ocean Freight"),
        "remarks": "Certificate of Origin for customs purposes.",
        "item_list": "\n".join([
            f"{item['item_no']}. {item['description']} - "
            f"Qty: {item['quantity']} - "
            f"HS: {item['hs_code']} - "
            f"Origin: {item['country_of_origin']} - "
            f"Criteria: {item['origin_criteria']}"
            for item in item_details
        ])
    }
    
    # Add additional fields that might be in the template
    certificate_data.update({
        "authorized_signature": "________________________",
        "authorized_name": "Authorized Signatory",
        "authorized_title": "Export Manager",
        "declaration": f"I hereby declare that the information contained herein is true and correct and all the goods were produced in {primary_origin}."
    })
    
    return certificate_data
