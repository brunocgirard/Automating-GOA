"""
Priced items database operations - CRUD operations for line items from PDF quotes.
"""

import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime

from .base import DB_PATH
from .utils import parse_price_string


def save_priced_items(client_quote_ref: str, line_items_data: List[Dict[str, Optional[str]]], db_path: str = DB_PATH) -> bool:
    """
    Saves parsed line item details (description, quantity, price) to the priced_items table.
    Extracts a main title from the full description before saving.

    Args:
        client_quote_ref: The quote reference to link items to.
        line_items_data: List of dictionaries containing item data with keys:
            - description: Full item description
            - quantity_text: Quantity as text
            - selection_text: Price/selection text
        db_path: Path to the SQLite database file.

    Returns:
        bool: True if successful, False otherwise
    """
    if not client_quote_ref or not line_items_data:
        return False

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM priced_items WHERE client_quote_ref = ?", (client_quote_ref,))

        items_to_insert = []
        for item_dict in line_items_data:
            full_description = item_dict.get("description")
            quantity_text = item_dict.get("quantity_text")
            selection_cell_content = item_dict.get("selection_text")

            parsed_price_info = parse_price_string(selection_cell_content)

            main_item_title = full_description  # Default to full description
            if full_description:
                lines = full_description.splitlines()
                title_buffer = []
                for line_num, line_content in enumerate(lines):
                    stripped_line = line_content.strip()
                    # Stop if we hit common delimiters for sub-items or if the line is clearly a sub-item
                    if (stripped_line.lower().startswith("including:") or
                        stripped_line.lower().startswith("includes:") or
                        stripped_line.startswith("*") or
                        stripped_line.startswith("-") or
                        (line_num > 0 and (stripped_line.lower().startswith("one ") or
                                           stripped_line.lower().startswith("each ")))):
                        break
                    title_buffer.append(stripped_line)
                if title_buffer:
                    main_item_title = " ".join(title_buffer).strip()
                else:  # Fallback if all lines looked like sub-items
                    main_item_title = lines[0].strip() if lines else full_description

            if main_item_title:  # Only save if we have a title/description
                items_to_insert.append((
                    client_quote_ref,
                    main_item_title,  # Use the extracted main title
                    quantity_text,
                    parsed_price_info["price_str"],
                    parsed_price_info["price_numeric"]
                ))

        if items_to_insert:
            cursor.executemany(
                "INSERT INTO priced_items (client_quote_ref, item_description, item_quantity, item_price_str, item_price_numeric) VALUES (?, ?, ?, ?, ?)",
                items_to_insert
            )
            conn.commit()
            print(f"Saved/Updated {len(items_to_insert)} priced items for quote: {client_quote_ref}")
        else:
            print(f"No valid items to insert for priced_items for quote: {client_quote_ref}")
        return True
    except sqlite3.Error as e:
        print(f"Database error in save_priced_items for quote {client_quote_ref}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error in save_priced_items for quote {client_quote_ref}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()


def load_priced_items_for_quote(client_quote_ref: str, db_path: str = DB_PATH) -> List[Dict]:
    """
    Loads all priced items for a given client_quote_ref, including quantity.

    Args:
        client_quote_ref: The quote reference to load items for.
        db_path: Path to the SQLite database file.

    Returns:
        List of dictionaries containing item data with keys:
        - id, item_description, item_quantity, item_price_str, item_price_numeric
    """
    conn = None
    items = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, item_description, item_quantity, item_price_str, item_price_numeric
        FROM priced_items
        WHERE client_quote_ref = ?
        ORDER BY id
        """, (client_quote_ref,))
        rows = cursor.fetchall()
        for row in rows:
            items.append(dict(row))
    except sqlite3.Error as e:
        print(f"Database error loading priced items for quote {client_quote_ref}: {e}")
    finally:
        if conn:
            conn.close()
    return items


def update_single_priced_item(item_id: int, new_data: Dict[str, Any], db_path: str = DB_PATH) -> bool:
    """
    Updates a specific priced item in the database by its ID.

    Args:
        item_id: The database ID of the priced item to update.
        new_data: Dictionary with expected keys:
            - item_description: New description
            - item_quantity: New quantity
            - item_price_str: New price string (will be re-parsed)
        db_path: Path to the SQLite database file.

    Returns:
        bool: True if successful, False otherwise
    """
    if not new_data or item_id is None:
        print("Error: Item ID or new_data missing for priced item update.")
        return False

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Re-parse the price_str to ensure price_numeric is consistent
        parsed_price = parse_price_string(new_data.get('item_price_str'))

        sql = """
        UPDATE priced_items
        SET item_description = ?,
            item_quantity = ?,
            item_price_str = ?,
            item_price_numeric = ?
        WHERE id = ?
        """
        params = (
            new_data.get('item_description'),
            new_data.get('item_quantity'),
            parsed_price['price_str'],
            parsed_price['price_numeric'],
            item_id
        )
        cursor.execute(sql, params)
        conn.commit()
        if cursor.rowcount > 0:
            print(f"Successfully updated priced_item ID: {item_id}")
            return True
        else:
            print(f"Warning: No priced_item found with ID: {item_id} to update.")
            return False

    except sqlite3.Error as e:
        print(f"Database error updating priced_item ID {item_id}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error updating priced_item ID {item_id}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()


def calculate_common_items_price(common_items: List[Dict]) -> float:
    """
    Calculates the total price of common items.

    Args:
        common_items: List of item dictionaries with 'item_price_numeric' key.

    Returns:
        float: Total price of all common items
    """
    total_price = 0.0
    for item in common_items:
        item_price = item.get("item_price_numeric", 0)
        if item_price is not None:
            total_price += item_price
    return total_price
