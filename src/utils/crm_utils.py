import sqlite3
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import re

# Import for document regeneration
from src.utils.doc_filler import fill_word_document_from_llm_data

# Define database connection
DB_PATH = os.path.join("data", "crm_data.db")
# Define base template path (ideally this would be passed or configured globally)
TEMPLATE_FILE_PATH = os.path.join("templates", "template.docx")

def init_db(db_path: str = DB_PATH):
    """
    Initializes the SQLite database. Creates 'clients' and 'priced_items' tables if they don't exist.
    """
    conn = None
    try:
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_ref TEXT UNIQUE NOT NULL, 
            customer_name TEXT,
            machine_model TEXT,          -- Comma-separated list of machine names from machines_data
            country_destination TEXT,    -- This seems to be missing from client_info, might need to add to extraction/form
            sold_to_address TEXT,        -- Maps to client_info.billing_address
            ship_to_address TEXT,        -- Maps to client_info.shipping_address
            telephone TEXT,              -- Maps to client_info.phone
            customer_contact_person TEXT, -- Maps to client_info.contact_person
            customer_po TEXT,            -- Maps to client_info.customer_po
            processing_date TEXT NOT NULL,
            incoterm TEXT,               -- Maps to client_info.incoterm
            quote_date TEXT              -- Maps to client_info.quote_date
        )
        """)

        # Create priced_items table with item_quantity
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS priced_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_quote_ref TEXT NOT NULL, 
            item_description TEXT,
            item_quantity TEXT,       -- Added: Store as TEXT to handle various formats (e.g., "1", "N/A", "As required")
            item_price_str TEXT,      
            item_price_numeric REAL,  
            FOREIGN KEY (client_quote_ref) REFERENCES clients (quote_ref) ON DELETE CASCADE
        )
        """)
        
        # Create machines table to store identified machines within a quote
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS machines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_quote_ref TEXT NOT NULL,
            machine_name TEXT NOT NULL,
            machine_data_json TEXT NOT NULL,   -- JSON string of machine details including main_item and add_ons
            processing_date TEXT NOT NULL,
            FOREIGN KEY (client_quote_ref) REFERENCES clients (quote_ref) ON DELETE CASCADE
        )
        """)
        
        # Create machine_templates table to store GOA outputs for specific machines
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS machine_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id INTEGER NOT NULL,
            template_type TEXT NOT NULL,       -- E.g., "GOA", "Packing Slip", etc.
            template_data_json TEXT NOT NULL,  -- JSON string of filled template data
            generated_file_path TEXT,          -- Path to the generated document
            processing_date TEXT NOT NULL,
            FOREIGN KEY (machine_id) REFERENCES machines (id) ON DELETE CASCADE
        )
        """)
        
        # Create document_content table to store PDF text for later chat functionality
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_quote_ref TEXT UNIQUE NOT NULL,
            full_pdf_text TEXT,           -- Full text extracted from the PDF
            pdf_filename TEXT,            -- Original filename
            upload_date TEXT NOT NULL,    -- When the document was uploaded
            FOREIGN KEY (client_quote_ref) REFERENCES clients (quote_ref) ON DELETE CASCADE
        )
        """)
        
        # Create goa_modifications table to track changes made to GOA templates after kickoff meetings
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS goa_modifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_template_id INTEGER NOT NULL,  -- Links to machine_templates table
            field_key TEXT NOT NULL,              -- The field/placeholder key that was modified
            original_value TEXT,                  -- Original value from LLM or previous modification
            modified_value TEXT NOT NULL,         -- New value after modification
            modification_reason TEXT,             -- Reason for the change (e.g., "Client request", "Kickoff meeting")
            modified_by TEXT,                     -- Who made the change
            modification_date TEXT NOT NULL,      -- When the modification was made
            FOREIGN KEY (machine_template_id) REFERENCES machine_templates (id) ON DELETE CASCADE
        )
        """)
        
        print(f"Database '{db_path}' initialized with all required tables.")
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during DB init: {e}")
    finally:
        if conn:
            conn.close()

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

def save_client_info(client_data: Dict[str, any], db_path: str = DB_PATH) -> bool:
    print("DEBUG: save_client_info called with:", client_data)
    required_fields = ['quote_ref'] 
    for field in required_fields:
        if field not in client_data or not client_data[field]:
            print(f"Error: Required field '{field}' is missing or empty.")
            return False
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        processing_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Map app's client_info keys to database columns
        # Note: machine_model is derived in app.py before calling this
        db_field_mapping = {
            "customer_name": client_data.get("customer_name"),
            "machine_model": client_data.get("machine_model"), # Passed directly now
            "country_destination": client_data.get("country_destination"), # Assuming it might be added to client_data
            "sold_to_address": client_data.get("sold_to_address"),
            "ship_to_address": client_data.get("ship_to_address"),
            "telephone": client_data.get("telephone"),
            "customer_contact_person": client_data.get("customer_contact_person"),
            "customer_po": client_data.get("customer_po"),
            "incoterm": client_data.get("incoterm"),
            "quote_date": client_data.get("quote_date")
        }
        
        cursor.execute("SELECT id FROM clients WHERE quote_ref = ?", (client_data['quote_ref'],))
        existing_record = cursor.fetchone()
        
        if existing_record:
            updates = []
            params = []
            for db_col, value in db_field_mapping.items():
                if value is not None: # Only update if value is provided
                    updates.append(f"{db_col} = ?")
                    params.append(value)
            
            if not updates: # No actual fields to update other than processing_date
                cursor.execute("UPDATE clients SET processing_date = ? WHERE quote_ref = ?", 
                               (processing_ts, client_data['quote_ref']))
            else:
                updates.append("processing_date = ?")
                params.append(processing_ts)
                params.append(client_data['quote_ref']) 
                sql = f"UPDATE clients SET {', '.join(updates)} WHERE quote_ref = ?"
                cursor.execute(sql, tuple(params))
            print(f"Updated record in 'clients' for quote: {client_data['quote_ref']}")
        else:
            columns = ['quote_ref', 'processing_date']
            values = [client_data['quote_ref'], processing_ts]
            placeholders = ['?', '?']
            
            for db_col, value in db_field_mapping.items():
                columns.append(db_col)
                values.append(value if value is not None else "") # Use empty string for missing optional fields
                placeholders.append('?')
            
            sql = f"INSERT INTO clients ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(sql, tuple(values))
            print(f"Inserted new record into 'clients' for quote: {client_data['quote_ref']}")
        conn.commit()
        return True
    except sqlite3.Error as e: 
        print(f"DB error in save_client_info (clients): {e}"); 
        print(f"Data attempted: {client_data}") # Print data on error
        return False
    finally: 
        if conn: conn.close()

def get_client_by_id(client_id: int, db_path: str = DB_PATH) -> Optional[Dict]:
    """Fetches a specific client record by its ID."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"Database error loading client by ID '{client_id}': {e}")
        return None
    finally:
        if conn:
            conn.close()

def update_client_record(client_id: int, data_to_update: Dict[str, str], db_path: str = DB_PATH) -> bool:
    """
    Updates specific fields of an existing client record identified by ID.
    Does not update quote_ref, full_llm_data_json, or selected_pdf_items_json.
    Processing_date is updated.
    """
    if not data_to_update:
        print("No data provided to update.")
        return False

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        fields = []
        params = []
        allowed_fields = [
            "customer_name", "machine_model", "country_destination", 
            "sold_to_address", "ship_to_address", "telephone", 
            "customer_contact_person", "customer_po", "incoterm", "quote_date"
        ]
        for key, value in data_to_update.items():
            if key in allowed_fields:
                fields.append(f"{key} = ?")
                params.append(value)
        
        if not fields: 
            cursor.execute("UPDATE clients SET processing_date = ? WHERE id = ?", 
                           (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), client_id))
            print(f"Only updated processing_date for client ID: {client_id}")
        else:
            fields.append("processing_date = ?")
            params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            params.append(client_id) 
            
            sql = f"UPDATE clients SET {', '.join(fields)} WHERE id = ?"
            cursor.execute(sql, tuple(params))
            print(f"Successfully updated client ID: {client_id}")
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error updating client ID {client_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def load_all_clients(db_path: str = DB_PATH) -> List[Dict]:
    """
    Loads all client/quote records from the database.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        A list of dictionaries, where each dictionary represents a client record.
        Returns an empty list if an error occurs or no data is found.
    """
    conn = None
    clients = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        # Select all relevant fields for client list display
        cursor.execute("""
        SELECT id, quote_ref, customer_name, machine_model, country_destination, 
               sold_to_address, ship_to_address, telephone, customer_contact_person, 
               customer_po, processing_date, incoterm, quote_date 
        FROM clients ORDER BY processing_date DESC
        """)
        rows = cursor.fetchall()
        for row in rows:
            clients.append(dict(row))
    except sqlite3.Error as e:
        print(f"Database error while loading clients: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while loading clients: {e}")
    finally:
        if conn:
            conn.close()
    return clients

# --- Functions for priced_items table ---
def save_priced_items(client_quote_ref: str, line_items_data: List[Dict[str, Optional[str]]], db_path: str = DB_PATH) -> bool:
    """
    Saves parsed line item details (description, quantity, price) to the priced_items table.
    Extracts a main title from the full description before saving.
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
            
            main_item_title = full_description # Default to full description
            if full_description:
                lines = full_description.splitlines()
                title_buffer = []
                for line_num, line_content in enumerate(lines):
                    stripped_line = line_content.strip()
                    # Stop if we hit common delimiters for sub-items or if the line is clearly a sub-item
                    if (stripped_line.lower().startswith("including:") or 
                        stripped_line.lower().startswith("includes:") or 
                        stripped_line.startswith("●") or 
                        stripped_line.startswith("*") or 
                        stripped_line.startswith("-") or 
                        (line_num > 0 and (stripped_line.lower().startswith("one ") or stripped_line.lower().startswith("each ")))
                       ):
                        break
                    title_buffer.append(stripped_line)
                if title_buffer:
                    main_item_title = " ".join(title_buffer).strip()
                else: # Fallback if all lines looked like sub-items (e.g. starts with 'Each...')
                    main_item_title = lines[0].strip() if lines else full_description

            if main_item_title: # Only save if we have a title/description
                items_to_insert.append((
                    client_quote_ref,
                    main_item_title, # Use the extracted main title
                    quantity_text, 
                    parsed_price_info["price_str"],
                    parsed_price_info["price_numeric"]
                ))
        
        if items_to_insert:
            cursor.executemany("INSERT INTO priced_items (client_quote_ref, item_description, item_quantity, item_price_str, item_price_numeric) VALUES (?, ?, ?, ?, ?)", items_to_insert)
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
    """Loads all priced items for a given client_quote_ref, including quantity."""
    conn = None
    items = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Added item_quantity to the SELECT statement
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
    Expected keys in new_data: 'item_description', 'item_quantity', 'item_price_str'.
    It will re-parse price_str to get price_numeric.
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
            return False # Or True if no update needed is not an error

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

def delete_client_record(client_id: int, db_path: str = DB_PATH) -> bool:
    """
    Deletes a client record and its associated priced items from the database by client ID.
    Relies on ON DELETE CASCADE for priced_items if the foreign key was set up with it.
    If not, priced_items for the client's quote_ref would need to be deleted first.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # If ON DELETE CASCADE is not reliably working or not set, delete priced_items first.
        # Get quote_ref for the client_id to delete associated priced_items.
        cursor.execute("SELECT quote_ref FROM clients WHERE id = ?", (client_id,))
        result = cursor.fetchone()
        if result:
            client_quote_ref_to_delete = result[0]
            cursor.execute("DELETE FROM priced_items WHERE client_quote_ref = ?", (client_quote_ref_to_delete,))
            print(f"Deleted priced items for quote_ref: {client_quote_ref_to_delete}")
            
            # Also explicitly delete document content
            delete_document_content(client_quote_ref_to_delete)
        else:
            print(f"Warning: Client ID {client_id} not found, cannot get quote_ref for deleting priced items.")
            # Still proceed to try deleting from clients table in case of orphaned ID somehow.

        # Delete from clients table
        cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()

        if cursor.rowcount > 0:
            print(f"Successfully deleted client record ID: {client_id}")
            return True
        else:
            print(f"Warning: No client record found with ID: {client_id} to delete.")
            return False # No rows were deleted from clients table

    except sqlite3.Error as e:
        print(f"Database error deleting client record ID {client_id}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error deleting client record ID {client_id}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

def save_machines_data(client_quote_ref: str, machines_data: Dict, db_path: str = DB_PATH) -> bool:
    """
    Saves identified machines and their add-ons to the machines table.
    
    Args:
        client_quote_ref: The quote reference to link machines to
        machines_data: Dictionary with "machines" list and "common_items" list
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not client_quote_ref:
        print("Error: Missing quote reference for save_machines_data.")
        return False
        
    if not machines_data:
        print("Error: Missing machines data for save_machines_data.")
        return False
    
    # Validate machines_data structure
    if "machines" not in machines_data:
        print("Error: No 'machines' key in machines_data.")
        print(f"Available keys: {list(machines_data.keys())}")
        return False
        
    # Make sure we have at least one machine
    if not machines_data.get("machines"):
        print("Error: Empty machines list in machines_data.")
        return False
        
    conn = None
    try:
        # First check if the client exists
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM clients WHERE quote_ref = ?", (client_quote_ref,))
        client_exists = cursor.fetchone()
        
        if not client_exists:
            # Create a basic client record if it doesn't exist
            print(f"Client with quote_ref {client_quote_ref} does not exist. Creating basic record.")
            processing_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Get a machine name for the client record if possible
            machine_name = ""
            if machines_data.get("machines") and len(machines_data["machines"]) > 0:
                machine_name = machines_data["machines"][0].get("machine_name", "")
                
            cursor.execute("""
            INSERT INTO clients (quote_ref, customer_name, machine_model, processing_date)
            VALUES (?, ?, ?, ?)
            """, (client_quote_ref, "", machine_name, processing_ts))
            conn.commit()
        
        # Delete any existing machines for this quote
        cursor.execute("DELETE FROM machines WHERE client_quote_ref = ?", (client_quote_ref,))
        
        # Prepare machines for insertion
        machines_to_insert = []
        processing_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Process and validate each machine
        for machine in machines_data.get("machines", []):
            # Ensure machine_name exists and is not empty
            if not machine.get("machine_name"):
                # Try to generate a name if missing
                if machine.get("main_item") and machine["main_item"].get("description"):
                    desc = machine["main_item"]["description"]
                    # Use first line of description as machine name
                    machine["machine_name"] = desc.split('\n')[0] if '\n' in desc else desc
                else:
                    # Use a default name with timestamp
                    machine["machine_name"] = f"Unknown Machine {len(machines_to_insert) + 1}"
                print(f"Generated machine name: {machine['machine_name']}")
            
            # Make sure machine has client_quote_ref
            machine_copy = machine.copy()
            machine_copy["client_quote_ref"] = client_quote_ref
            
            # Add common items to each machine for storage
            machine_with_common = machine_copy.copy()
            machine_with_common["common_items"] = machines_data.get("common_items", [])
            
            # Convert machine to JSON and validate
            try:
                machine_json = json.dumps(machine_with_common)
                machines_to_insert.append((
                    client_quote_ref,
                    machine_copy.get("machine_name", "Unknown Machine"),
                    machine_json,
                    processing_ts
                ))
            except (TypeError, ValueError) as e:
                print(f"Error serializing machine to JSON: {e}")
                print(f"Problem machine: {machine_copy.get('machine_name', 'Unknown')}")
                # Continue with other machines
                continue
        
        if machines_to_insert:
            try:
                cursor.executemany("""
                INSERT INTO machines (client_quote_ref, machine_name, machine_data_json, processing_date)
                VALUES (?, ?, ?, ?)
                """, machines_to_insert)
                
                conn.commit()
                print(f"Saved {len(machines_to_insert)} machines for quote: {client_quote_ref}")
                return True
            except sqlite3.Error as e:
                print(f"SQLite error while inserting machines: {e}")
                return False
        else:
            print(f"No machines to save for quote: {client_quote_ref}")
            return False
            
    except sqlite3.Error as e:
        print(f"Database error in save_machines_data for quote {client_quote_ref}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error in save_machines_data for quote {client_quote_ref}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

def load_machines_for_quote(client_quote_ref: str, db_path: str = DB_PATH) -> List[Dict]:
    """
    Loads all identified machines for a given quote reference.
    
    Args:
        client_quote_ref: The quote reference to load machines for
        
    Returns:
        List of dictionaries containing machine data
    """
    conn = None
    machines = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, machine_name, machine_data_json, processing_date
        FROM machines
        WHERE client_quote_ref = ?
        ORDER BY id
        """, (client_quote_ref,))
        
        rows = cursor.fetchall()
        for row in rows:
            machine_dict = dict(row)
            try:
                # Parse the JSON string back to a dictionary
                machine_dict["machine_data"] = json.loads(machine_dict["machine_data_json"])
                # Keep the original JSON string in case it's needed
                machines.append(machine_dict)
            except json.JSONDecodeError:
                print(f"Error parsing JSON for machine ID {row['id']}")
                
        return machines
    except sqlite3.Error as e:
        print(f"Database error loading machines for quote {client_quote_ref}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def save_machine_template_data(machine_id: int, template_type: str, template_data: Dict, 
                              generated_file_path: Optional[str] = None, 
                              db_path: str = DB_PATH) -> bool:
    """
    Saves template data (GOA, Packing Slip, etc.) for a specific machine.
    
    Args:
        machine_id: ID of the machine in the machines table
        template_type: Type of template (e.g., "GOA", "Packing Slip")
        template_data: Dictionary of filled template fields
        generated_file_path: Optional path to the generated document
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not machine_id or not template_type or not template_data:
        print("Error: Missing required parameters for save_machine_template_data.")
        return False
        
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the machine exists
        cursor.execute("SELECT id FROM machines WHERE id = ?", (machine_id,))
        if not cursor.fetchone():
            print(f"Error: Machine with ID {machine_id} not found.")
            return False
            
        # Check if a template of this type already exists for this machine
        cursor.execute("""
        SELECT id FROM machine_templates 
        WHERE machine_id = ? AND template_type = ?
        """, (machine_id, template_type))
        
        existing_template = cursor.fetchone()
        processing_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if existing_template:
            # Update existing template
            cursor.execute("""
            UPDATE machine_templates
            SET template_data_json = ?, 
                generated_file_path = ?,
                processing_date = ?
            WHERE id = ?
            """, (
                json.dumps(template_data),
                generated_file_path or "",
                processing_ts,
                existing_template[0]
            ))
        else:
            # Insert new template
            cursor.execute("""
            INSERT INTO machine_templates
            (machine_id, template_type, template_data_json, generated_file_path, processing_date)
            VALUES (?, ?, ?, ?, ?)
            """, (
                machine_id,
                template_type,
                json.dumps(template_data),
                generated_file_path or "",
                processing_ts
            ))
            
        conn.commit()
        print(f"Saved {template_type} template data for machine ID: {machine_id}")
        return True
            
    except sqlite3.Error as e:
        print(f"Database error in save_machine_template_data: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error in save_machine_template_data: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

def load_machine_template_data(machine_id: int, template_type: str, db_path: str = DB_PATH) -> Optional[Dict]:
    """
    Loads template data for a specific machine and template type.
    
    Args:
        machine_id: ID of the machine
        template_type: Type of template to load
        
    Returns:
        Dictionary of template data if found, None otherwise
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, template_data_json, generated_file_path, processing_date
        FROM machine_templates
        WHERE machine_id = ? AND template_type = ?
        """, (machine_id, template_type))
        
        row = cursor.fetchone()
        if row:
            template_dict = dict(row)
            try:
                template_dict["template_data"] = json.loads(template_dict["template_data_json"])
                return template_dict
            except json.JSONDecodeError:
                print(f"Error parsing JSON for template ID {row['id']}")
                return None
        return None
    except sqlite3.Error as e:
        print(f"Database error loading template for machine {machine_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def save_document_content(quote_ref: str, full_pdf_text: str, filename: str, db_path: str = DB_PATH) -> bool:
    """
    Saves the full text content of a PDF document for later retrieval.
    
    Args:
        quote_ref: The quote reference to link the document to
        full_pdf_text: The full extracted text from the PDF
        filename: Original filename of the PDF
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not quote_ref or not full_pdf_text:
        print("Error: Missing quote reference or PDF text.")
        return False
        
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if entry already exists
        cursor.execute("SELECT id FROM document_content WHERE client_quote_ref = ?", (quote_ref,))
        existing = cursor.fetchone()
        
        upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if existing:
            # Update existing entry
            cursor.execute("""
            UPDATE document_content 
            SET full_pdf_text = ?, pdf_filename = ?, upload_date = ?
            WHERE client_quote_ref = ?
            """, (full_pdf_text, filename, upload_date, quote_ref))
        else:
            # Insert new entry
            cursor.execute("""
            INSERT INTO document_content 
            (client_quote_ref, full_pdf_text, pdf_filename, upload_date)
            VALUES (?, ?, ?, ?)
            """, (quote_ref, full_pdf_text, filename, upload_date))
        
        conn.commit()
        print(f"Saved document content for quote: {quote_ref}")
        return True
    except sqlite3.Error as e:
        print(f"Database error saving document content: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error saving document content: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

def load_document_content(quote_ref: str, db_path: str = DB_PATH) -> Optional[Dict]:
    """
    Loads the document content for a given quote reference.
    
    Args:
        quote_ref: The quote reference to load document content for
        
    Returns:
        Dictionary with full_pdf_text, pdf_filename, and upload_date if found, None otherwise
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT full_pdf_text, pdf_filename, upload_date
        FROM document_content
        WHERE client_quote_ref = ?
        """, (quote_ref,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"Database error loading document content for quote {quote_ref}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error loading document content for quote {quote_ref}: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if conn:
            conn.close()

# Function to delete document content when a client is deleted
def delete_document_content(quote_ref: str, db_path: str = DB_PATH) -> bool:
    """
    Deletes the document content for a given quote reference.
    Usually called when deleting a client record.
    
    Args:
        quote_ref: The quote reference to delete document content for
        
    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM document_content WHERE client_quote_ref = ?", (quote_ref,))
        conn.commit()
        
        print(f"Deleted document content for quote: {quote_ref}")
        return True
    except sqlite3.Error as e:
        print(f"Database error deleting document content: {e}")
        return False
    finally:
        if conn:
            conn.close()

# --- Functions for GOA modifications tracking ---

def save_goa_modification(
    machine_template_id: int, 
    field_key: str, 
    original_value: str, 
    modified_value: str,
    modification_reason: str = "",
    modified_by: str = "",
    db_path: str = DB_PATH
) -> bool:
    """
    Saves a modification made to a GOA template field.
    
    Args:
        machine_template_id: ID of the machine template being modified
        field_key: The field/placeholder key that was modified
        original_value: Original value before modification
        modified_value: New value after modification
        modification_reason: Optional reason for the change
        modified_by: Optional name of who made the change
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not machine_template_id or not field_key or not modified_value:
        print("Error: Missing required parameters for save_goa_modification.")
        return False
        
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the machine template exists
        cursor.execute("SELECT id FROM machine_templates WHERE id = ?", (machine_template_id,))
        if not cursor.fetchone():
            print(f"Error: Machine template with ID {machine_template_id} not found.")
            return False
            
        # Check if a modification for this field already exists
        cursor.execute("""
        SELECT id FROM goa_modifications 
        WHERE machine_template_id = ? AND field_key = ?
        """, (machine_template_id, field_key))
        
        existing_modification = cursor.fetchone()
        modification_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if existing_modification:
            # Update existing modification
            cursor.execute("""
            UPDATE goa_modifications
            SET original_value = ?,
                modified_value = ?,
                modification_reason = ?,
                modified_by = ?,
                modification_date = ?
            WHERE id = ?
            """, (
                original_value,
                modified_value,
                modification_reason,
                modified_by,
                modification_date,
                existing_modification[0]
            ))
        else:
            # Insert new modification
            cursor.execute("""
            INSERT INTO goa_modifications
            (machine_template_id, field_key, original_value, modified_value, 
             modification_reason, modified_by, modification_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                machine_template_id,
                field_key,
                original_value,
                modified_value,
                modification_reason,
                modified_by,
                modification_date
            ))
            
        conn.commit()
        print(f"Saved GOA modification for field '{field_key}' on machine template ID: {machine_template_id}")
        
        # Update the template_data_json in machine_templates to reflect this change
        cursor.execute("SELECT template_data_json FROM machine_templates WHERE id = ?", (machine_template_id,))
        template_data_row = cursor.fetchone()
        if template_data_row:
            try:
                template_data = json.loads(template_data_row[0])
                # This will add the field if it's new, or update it if it exists.
                template_data[field_key] = modified_value 
                cursor.execute("""
                UPDATE machine_templates 
                SET template_data_json = ?, processing_date = ? 
                WHERE id = ?
                """, (json.dumps(template_data), modification_date, machine_template_id))
                conn.commit()
                print(f"Updated template data (added/modified field '{field_key}') for machine template ID: {machine_template_id}")

                # Regenerate the document
                cursor.execute("SELECT generated_file_path FROM machine_templates WHERE id = ?", (machine_template_id,))
                file_path_row = cursor.fetchone()
                if file_path_row and file_path_row[0]:
                    generated_file_path = file_path_row[0]
                    if os.path.exists(TEMPLATE_FILE_PATH): # Check if base template exists
                        if generated_file_path: # Check if a file path exists to overwrite
                            print(f"Regenerating document at: {generated_file_path}")
                            fill_word_document_from_llm_data(TEMPLATE_FILE_PATH, template_data, generated_file_path)
                            print(f"Successfully regenerated document for machine template ID: {machine_template_id}")
                        else:
                            print(f"Warning: No generated_file_path found for template ID {machine_template_id}. Document not regenerated.")
                    else:
                        print(f"Warning: Base template file {TEMPLATE_FILE_PATH} not found. Document not regenerated.")
                else:
                    print(f"Warning: Could not retrieve generated_file_path for template ID {machine_template_id}. Document not regenerated.")

            except json.JSONDecodeError:
                print(f"Error parsing JSON for machine template ID {machine_template_id} during document regeneration step.")
        
        return True
            
    except sqlite3.Error as e:
        print(f"Database error in save_goa_modification: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error in save_goa_modification: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

def load_goa_modifications(machine_template_id: int, db_path: str = DB_PATH) -> List[Dict]:
    """
    Loads all modifications for a specific machine template.
    
    Args:
        machine_template_id: ID of the machine template
        
    Returns:
        List of dictionaries containing modification data
    """
    conn = None
    modifications = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, field_key, original_value, modified_value, 
               modification_reason, modified_by, modification_date
        FROM goa_modifications
        WHERE machine_template_id = ?
        ORDER BY modification_date DESC
        """, (machine_template_id,))
        
        rows = cursor.fetchall()
        for row in rows:
            modifications.append(dict(row))
                
        return modifications
    except sqlite3.Error as e:
        print(f"Database error loading GOA modifications for template {machine_template_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def load_machine_templates_with_modifications(machine_id: int, db_path: str = DB_PATH) -> Dict:
    """
    Loads machine template data along with any modifications for a specific machine.
    
    Args:
        machine_id: ID of the machine
        
    Returns:
        Dictionary containing template data and modifications
    """
    conn = None
    result = {"templates": [], "has_modifications": False}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all templates for this machine
        cursor.execute("""
        SELECT id, template_type, template_data_json, generated_file_path, processing_date
        FROM machine_templates
        WHERE machine_id = ?
        ORDER BY processing_date DESC
        """, (machine_id,))
        
        template_rows = cursor.fetchall()
        for template_row in template_rows:
            template_dict = dict(template_row)
            template_id = template_dict["id"]
            
            # Get modifications for this template
            cursor.execute("""
            SELECT id, field_key, original_value, modified_value, 
                   modification_reason, modified_by, modification_date
            FROM goa_modifications
            WHERE machine_template_id = ?
            ORDER BY field_key
            """, (template_id,))
            
            modification_rows = cursor.fetchall()
            modifications = [dict(row) for row in modification_rows]
            
            # Parse template data
            try:
                # Ensure template_data is always a dictionary, even if JSON is null/empty
                template_json_str = template_dict.get("template_data_json")
                if template_json_str:
                    template_dict["template_data"] = json.loads(template_json_str)
                else:
                    template_dict["template_data"] = {} # Initialize as empty dict if no JSON
            except json.JSONDecodeError:
                template_dict["template_data"] = {} # Initialize as empty dict on error
                print(f"Error parsing JSON for template ID {template_id}, initializing as empty.")
            
            template_dict["modifications"] = modifications
            if modifications:
                result["has_modifications"] = True
                
            result["templates"].append(template_dict)
                
        return result
    except sqlite3.Error as e:
        print(f"Database error loading templates with modifications for machine {machine_id}: {e}")
        return result
    finally:
        if conn:
            conn.close()

def update_template_after_modifications(machine_template_id: int, db_path: str = DB_PATH) -> bool:
    """
    Updates the template_data_json in machine_templates to reflect all modifications.
    Used to consolidate changes after multiple modifications.
    
    Args:
        machine_template_id: ID of the machine template
        
    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get the template data
        cursor.execute("SELECT template_data_json FROM machine_templates WHERE id = ?", (machine_template_id,))
        template_data_row = cursor.fetchone()
        if not template_data_row:
            print(f"Error: Machine template with ID {machine_template_id} not found.")
            return False
            
        try:
            template_data = json.loads(template_data_row[0])
        except json.JSONDecodeError:
            print(f"Error parsing JSON for machine template ID {machine_template_id}")
            return False
            
        # Get all modifications for this template
        cursor.execute("""
        SELECT field_key, modified_value FROM goa_modifications
        WHERE machine_template_id = ?
        """, (machine_template_id,))
        
        modifications = cursor.fetchall()
        if not modifications:
            print(f"No modifications found for machine template ID {machine_template_id}")
            return True  # Not an error, just no modifications to apply
            
        # Apply all modifications to the template data
        for field_key, modified_value in modifications:
            if field_key in template_data:
                template_data[field_key] = modified_value
                
        # Update the template data
        processing_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        UPDATE machine_templates 
        SET template_data_json = ?, processing_date = ? 
        WHERE id = ?
        """, (json.dumps(template_data), processing_date, machine_template_id))
        
        conn.commit()
        print(f"Updated template data for machine template ID: {machine_template_id}")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error updating template after modifications: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error updating template after modifications: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

def find_machines_by_name(machine_name: str, db_path: str = DB_PATH) -> List[Dict]:
    """
    Finds machines by name across all quotes.
    This is useful when looking for machines that might have been processed in different quotes.
    
    Args:
        machine_name: The name of the machine to search for
        
    Returns:
        List of dictionaries containing machine data
    """
    conn = None
    machines = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Use LIKE for partial matching with wildcards
        search_pattern = f"%{machine_name}%"
        
        cursor.execute("""
        SELECT m.id, m.machine_name, m.machine_data_json, m.client_quote_ref, m.processing_date, 
               c.customer_name, c.id as client_id
        FROM machines m
        LEFT JOIN clients c ON m.client_quote_ref = c.quote_ref
        WHERE m.machine_name LIKE ?
        ORDER BY m.processing_date DESC
        """, (search_pattern,))
        
        rows = cursor.fetchall()
        for row in rows:
            machine_dict = dict(row)
            try:
                # Parse the JSON string back to a dictionary
                machine_dict["machine_data"] = json.loads(machine_dict["machine_data_json"])
                # Keep the original JSON string in case it's needed
                machines.append(machine_dict)
            except json.JSONDecodeError:
                print(f"Error parsing JSON for machine ID {row['id']}")
                
        return machines
    except sqlite3.Error as e:
        print(f"Database error finding machines by name '{machine_name}': {e}")
        return []
    finally:
        if conn:
            conn.close()

def load_all_processed_machines(db_path: str = DB_PATH) -> List[Dict]:
    """
    Loads all machines that have been processed with templates,
    including client information for better organization in the reports page.
    
    Returns:
        List of dictionaries containing machine information and related client data
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Join machines, machine_templates, and clients tables to get all necessary data
        cursor.execute("""
        SELECT 
            m.id, 
            m.machine_name, 
            m.client_quote_ref, 
            c.id as client_id,
            c.customer_name as client_name,
            c.quote_ref,
            mt.template_type,
            mt.processing_date
        FROM 
            machines m
        JOIN 
            clients c ON m.client_quote_ref = c.quote_ref
        JOIN 
            machine_templates mt ON m.id = mt.machine_id
        GROUP BY 
            m.id
        ORDER BY 
            c.customer_name, m.machine_name
        """)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"Error loading processed machines: {e}")
        return []
    finally:
        if conn:
            conn.close()

# Example usage (can be run once to create the DB)
if __name__ == '__main__':
    print(f"Attempting to initialize database at: {os.path.abspath(DB_PATH)}")
    init_db()
    print("If no errors, database and tables should be ready.")
    # Test save_client_info (main client details)
    mock_main_client_data = {
        "quote_ref": "Q-MAIN-003",
        "customer_name": "Main Client Corp 3",
        "machine_model": "Monoblock Supreme 3",
        "country_destination": "UK"
    }
    if save_client_info(mock_main_client_data):
        print("Mock main client data saved.")
    # We will test save_priced_items once it's implemented 

    print("\nTesting parse_price_string:")
    test_prices = [
        "165,000.00", "24,550", "$1,234.56", "Included", "EUR1.234,56", "N/A", "  ", None, "USD 750", "500.75", "1.250,80"
    ]
    for t_price in test_prices:
        parsed = parse_price_string(t_price)
        print(f"Original Price String: '{t_price}' -> Parsed: {parsed}")

    print("\nTesting save_priced_items with new structure...")
    mock_items_for_saving = [
        {"description": "Monoblock Model: Patriot FC 11 Including...", "selection_text": "439,950"},
        {"description": "Antistatic for nozzle and hopper", "selection_text": "19,950"},
        {"description": "Warranty Two Year", "selection_text": "Included"},
        {"description": "Consulting Services", "selection_text": "N/A"},
        {"description": "Shipping International", "selection_text": "EUR 1.250,50"}
    ]
    test_quote_ref = "Q-CRM-SAVE-001"
    # Mock save main client info for this quote_ref first
    save_client_info({"quote_ref": test_quote_ref, "customer_name": "CRM Save Test Customer"})

    if save_priced_items(test_quote_ref, mock_items_for_saving):
        print(f"Mock priced items saved for {test_quote_ref}.")
        loaded_items = load_priced_items_for_quote(test_quote_ref)
        if loaded_items:
            print(f"Loaded {len(loaded_items)} items for {test_quote_ref}:")
            for item in loaded_items:
                print(f"  - {item}")
        else:
            print(f"Could not load items for {test_quote_ref} after saving.")
    else:
        print(f"Failed to save mock priced items for {test_quote_ref}.") 

    print(f"Attempting to initialize database at: {os.path.abspath(DB_PATH)}")
    init_db()
    mock_main_client_data = {
        "quote_ref": "Q-CRM-SAVE-002", "customer_name": "CRM Save Test Customer 2",
        "machine_model": "Monoblock Supreme 2", "country_destination": "FR"
    }
    if save_client_info(mock_main_client_data):
        print("Mock main client data saved for Q-CRM-SAVE-002.")

    print("\nTesting save_priced_items with quantity...")
    mock_items_for_saving_with_qty = [
        {"description": "Monoblock Model: Patriot FC 11 Including...", "quantity_text": "1", "selection_text": "439,950"},
        {"description": "Antistatic for nozzle and hopper", "quantity_text": "1", "selection_text": "19,950"},
        {"description": "Change Parts - 5 sets", "quantity_text": "5", "selection_text": "25,000"},
        {"description": "Warranty Two Year", "quantity_text": "1", "selection_text": "Included"},
        {"description": "Total Summary Line", "quantity_text": None, "selection_text": "$500,000.00"}
    ]
    test_quote_ref_qty = "Q-CRM-SAVE-002"

    if save_priced_items(test_quote_ref_qty, mock_items_for_saving_with_qty):
        print(f"Mock priced items with quantity saved for {test_quote_ref_qty}.")
        # load_priced_items_for_quote will be tested after its update
    else:
        print(f"Failed to save mock priced items with quantity for {test_quote_ref_qty}.") 

    print(f"Attempting to initialize database at: {os.path.abspath(DB_PATH)}") # Ensure this is called if running standalone
    init_db()
    mock_main_client_data = {
        "quote_ref": "Q-CRM-SAVE-002", "customer_name": "CRM Save Test Customer 2",
        "machine_model": "Monoblock Supreme 2", "country_destination": "FR"
    }
    if save_client_info(mock_main_client_data): # Make sure main client record exists for FK
        print("Mock main client data saved for Q-CRM-SAVE-002 for load test.")

    mock_items_for_saving_with_qty = [
        {"description": "Monoblock Model: Patriot FC 11 Including...", "quantity_text": "1", "selection_text": "439,950"},
        {"description": "Antistatic for nozzle and hopper", "quantity_text": "1", "selection_text": "19,950"},
        {"description": "Change Parts - 5 sets", "quantity_text": "5", "selection_text": "25,000"}
    ]
    test_quote_ref_qty = "Q-CRM-SAVE-002"
    if save_priced_items(test_quote_ref_qty, mock_items_for_saving_with_qty):
        print(f"Mock priced items with quantity saved for {test_quote_ref_qty} (for load test).")
        loaded_items = load_priced_items_for_quote(test_quote_ref_qty)
        if loaded_items:
            print(f"Loaded {len(loaded_items)} items for {test_quote_ref_qty} (including quantity):")
            for item in loaded_items:
                print(f"  - {item}") # Will now show quantity
        else:
            print(f"Could not load items for {test_quote_ref_qty} after saving for load test.")
    else:
        print(f"Failed to save mock priced items with quantity for {test_quote_ref_qty} (for load test).") 

    print(f"Attempting to initialize database at: {os.path.abspath(DB_PATH)}")
    init_db()
    # Ensure a client and some priced items exist for testing update
    test_quote_ref_for_edit = "Q-EDIT-ITEMS-001"
    save_client_info({"quote_ref": test_quote_ref_for_edit, "customer_name": "Edit Priced Items Test Cust"})
    initial_items_for_edit = [
        {"description": "Editable Item A", "quantity_text": "1", "selection_text": "100.00"},
        {"description": "Editable Item B", "quantity_text": "2", "selection_text": "Included"}
    ]
    save_priced_items(test_quote_ref_for_edit, initial_items_for_edit)
    
    print(f"\n--- Testing update_single_priced_item for quote {test_quote_ref_for_edit} ---")
    items_to_edit = load_priced_items_for_quote(test_quote_ref_for_edit)
    if items_to_edit:
        item_id_to_update = items_to_edit[0]['id']
        print(f"Original item ID {item_id_to_update}: {items_to_edit[0]}")
        update_payload = {
            "item_description": "Editable Item A - MODIFIED",
            "item_quantity": "3",
            "item_price_str": "150.99"
        }
        if update_single_priced_item(item_id_to_update, update_payload):
            print("Item update successful.")
            updated_item_check = get_client_by_id(item_id_to_update) # This is wrong, need to get item by id
            # For now, just reload all items for the quote to check
            reloaded_items = load_priced_items_for_quote(test_quote_ref_for_edit)
            print("Items after update:")
            for item in reloaded_items:
                print(f"  - {item}")
        else:
            print("Item update failed.")
    else:
        print(f"No items found for quote {test_quote_ref_for_edit} to test update.") 

    print(f"Attempting to initialize database at: {os.path.abspath(DB_PATH)}")
    init_db()
    test_quote_ref_title = "Q-TITLE-TEST-001"
    save_client_info({"quote_ref": test_quote_ref_title, "customer_name": "Title Test Customer"})
    
    mock_items_for_title_test = [
        {"description": "Monoblock Model: Patriot FC 11\nIncluding:\n● Automatic Bottle Sorting...\n● Single index star wheel...", "quantity_text": "1", "selection_text": "439,950"},
        {"description": "Each Bottle Change Parts (Bowl)", "quantity_text": "1", "selection_text": "19,950"},
        {"description": "LabelStar System 1\nFeatures:\n- High speed application\n- Stainless Steel Body", "quantity_text": "1", "selection_text": "50,000"}
    ]

    print(f"\n--- Testing save_priced_items with title extraction for quote {test_quote_ref_title} ---")
    if save_priced_items(test_quote_ref_title, mock_items_for_title_test):
        print(f"Priced items saved for {test_quote_ref_title}.")
        loaded_items = load_priced_items_for_quote(test_quote_ref_title)
        if loaded_items:
            print(f"Loaded items for {test_quote_ref_title}:")
            for item in loaded_items:
                print(f"  - ID: {item['id']}, Desc: '{item['item_description']}', Qty: {item['item_quantity']}, Price: {item['item_price_str']}")
        else:
            print(f"Could not load items for {test_quote_ref_title}.")
    else:
        print(f"Failed to save priced items for {test_quote_ref_title}.") 

    print(f"Attempting to initialize database at: {os.path.abspath(DB_PATH)}")
    init_db()
    # Create a test client specifically for deletion test
    del_quote_ref = "Q-TO-DELETE-001"
    del_client_data = {"quote_ref": del_quote_ref, "customer_name": "Delete Me Customer"}
    if save_client_info(del_client_data):
        print(f"Saved test client for deletion: {del_quote_ref}")
        # Optionally add some priced items for this client
        del_items = [
            {"description": "Item on quote to delete", "quantity_text": "1", "selection_text": "50.00"}
        ]
        save_priced_items(del_quote_ref, del_items)
        
        clients_before_delete = load_all_clients()
        client_to_delete = next((c for c in clients_before_delete if c['quote_ref'] == del_quote_ref), None)

        if client_to_delete:
            client_id_to_delete = client_to_delete['id']
            print(f"\n--- Testing delete_client_record for ID: {client_id_to_delete} (Quote: {del_quote_ref}) ---")
            items_before_delete = load_priced_items_for_quote(del_quote_ref)
            print(f"Priced items BEFORE delete for {del_quote_ref}: {len(items_before_delete)}")
            
            if delete_client_record(client_id_to_delete):
                print(f"Deletion reported successful for client ID: {client_id_to_delete}")
                clients_after_delete = load_all_clients()
                items_after_delete = load_priced_items_for_quote(del_quote_ref)
                deleted_client_check = get_client_by_id(client_id_to_delete)
                print(f"Client record exists after delete: {deleted_client_check is not None}")
                print(f"Priced items count AFTER delete for {del_quote_ref}: {len(items_after_delete)}")
                if not deleted_client_check and not items_after_delete:
                    print("Deletion fully successful (client and priced items gone).")
                else:
                    print("Problem with full deletion verification.")
            else:
                print(f"Deletion reported failed for client ID: {client_id_to_delete}")
        else:
            print(f"Could not find client {del_quote_ref} to test deletion.")
    else:
        print(f"Failed to save test client {del_quote_ref} for deletion test.") 