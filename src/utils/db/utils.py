import re
from typing import Dict, Optional, Any

def parse_price_string(price_input_str: Optional[str]) -> Dict[str, Optional[Any]]:
    """
    Parses a string that is expected to be a price or a status like "Included".
    Returns a dict: {"price_str": "original_string", "price_numeric": 1234.50 or 0.0 or None}
    """
    price_str_cleaned = None
    price_numeric = None

    if price_input_str is None or not str(price_input_str).strip():
        return {"price_str": None, "price_numeric": None}

    original_price_str = str(price_input_str).strip()
    price_str_lower = original_price_str.lower()

    if price_str_lower in ["included", "standard", "inclus"]:
        price_str_cleaned = original_price_str # Keep original casing like "Included"
        price_numeric = 0.0
    elif price_str_lower in ["n/a", "-", ""]:
        price_str_cleaned = original_price_str # Keep original like "N/A"
        price_numeric = None
    else:
        # Attempt to extract numeric value from potentially complex price string
        price_str_cleaned = original_price_str # Store the original as the price_str
        
        # Remove currency symbols, then handle commas/dots for float conversion
        # Keep only digits, decimal separators (.), and potentially group separators (,)
        # This regex also handles cases with currency symbols at the start or end
        numeric_part = re.sub(r"[^\d.,]", "", original_price_str)
        
        if numeric_part:
            # Standardize to use dot as decimal separator for float conversion
            if ',' in numeric_part and '.' in numeric_part: # Handles 1,234.56 or 1.234,56
                if numeric_part.rfind('.') > numeric_part.rfind(','): # Decimal is dot
                    numeric_part = numeric_part.replace(',', '')
                else: # Decimal is comma
                    numeric_part = numeric_part.replace('.', '').replace(',', '.')
            elif ',' in numeric_part: # Only comma present
                # If comma is likely a decimal separator (e.g., common in Europe for some formats like X,XX)
                if re.search(r',\d{2}$', numeric_part) and not re.search(r',\d{3}', numeric_part):
                    numeric_part = numeric_part.replace(',', '.')
                else: # Assume comma is a thousands separator
                    numeric_part = numeric_part.replace(',', '')
            
            try:
                price_numeric = float(numeric_part)
            except ValueError:
                # print(f"Warning: Could not convert '{numeric_part}' to float from original '{original_price_str}'.")
                price_numeric = None
        else:
            price_numeric = None # No numeric part found after stripping currency etc.

    return {"price_str": price_str_cleaned, "price_numeric": price_numeric}
