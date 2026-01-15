"""
Client database operations - CRUD operations for client/quote records.
"""

import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime

from .base import DB_PATH, get_connection


def save_client_info(client_data: Dict[str, any], db_path: str = DB_PATH) -> bool:
    """
    Saves or updates client information to the database.

    Args:
        client_data: Dictionary containing client information. Required key: 'quote_ref'
        db_path: Path to the SQLite database file.

    Returns:
        bool: True if successful, False otherwise
    """
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
        db_field_mapping = {
            "customer_name": client_data.get("customer_name"),
            "machine_model": client_data.get("machine_model"),
            "sold_to_address": client_data.get("sold_to_address"),
            "ship_to_address": client_data.get("ship_to_address"),
            "telephone": client_data.get("telephone"),
            "customer_contact_person": client_data.get("customer_contact_person"),
            "customer_po": client_data.get("customer_po"),
            "incoterm": client_data.get("incoterm"),
            "company": client_data.get("company"),
            "serial_number": client_data.get("serial_number"),
            "ax": client_data.get("ax"),
            "ox": client_data.get("ox"),
            "via": client_data.get("via"),
            "tax_id": client_data.get("tax_id"),
            "hs_code": client_data.get("hs_code"),
            "customer_number": client_data.get("customer_number"),
            "order_date": client_data.get("order_date"),
        }

        cursor.execute("SELECT id FROM clients WHERE quote_ref = ?", (client_data['quote_ref'],))
        existing_record = cursor.fetchone()

        if existing_record:
            updates = []
            params = []
            for db_col, value in db_field_mapping.items():
                if value is not None:  # Only update if value is provided
                    updates.append(f"{db_col} = ?")
                    params.append(value)

            if not updates:  # No actual fields to update other than processing_date
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
                values.append(value if value is not None else "")  # Use empty string for missing optional fields
                placeholders.append('?')

            sql = f"INSERT INTO clients ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(sql, tuple(values))
            print(f"Inserted new record into 'clients' for quote: {client_data['quote_ref']}")
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"DB error in save_client_info (clients): {e}")
        print(f"Data attempted: {client_data}")  # Print data on error
        return False
    finally:
        if conn:
            conn.close()


def get_client_by_id(client_id: int, db_path: str = DB_PATH) -> Optional[Dict]:
    """
    Fetches a specific client record by its ID.

    Args:
        client_id: The database ID of the client record.
        db_path: Path to the SQLite database file.

    Returns:
        Dictionary containing client data if found, None otherwise
    """
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

    Only the following columns may be changed: customer_name, machine_model,
    sold_to_address, ship_to_address, telephone, customer_contact_person,
    customer_po, incoterm, company, serial_number, ax, ox, via, tax_id,
    hs_code, customer_number, order_date. The processing_date timestamp
    is always refreshed to the current time.

    Args:
        client_id: The database ID of the client record to update.
        data_to_update: Dictionary of field names and their new values.
        db_path: Path to the SQLite database file.

    Returns:
        bool: True if successful, False otherwise
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
            "customer_name", "machine_model",
            "sold_to_address", "ship_to_address", "telephone",
            "customer_contact_person", "customer_po", "incoterm",
            "company", "serial_number", "ax", "ox", "via", "tax_id",
            "hs_code", "customer_number", "order_date"
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
        SELECT id, quote_ref, customer_name, machine_model,
               sold_to_address, ship_to_address, telephone, customer_contact_person,
               customer_po, processing_date, incoterm, company, serial_number,
               ax, ox, via, tax_id, hs_code, customer_number, order_date
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


def delete_client_record(client_id: int, db_path: str = DB_PATH) -> bool:
    """
    Deletes a client record and its associated data from the database by client ID.

    This function deletes:
    - Priced items associated with the client's quote_ref
    - Document content associated with the client's quote_ref
    - The client record itself

    Args:
        client_id: The database ID of the client record to delete.
        db_path: Path to the SQLite database file.

    Returns:
        bool: True if successful, False otherwise
    """
    # Import here to avoid circular dependency
    from .documents import delete_document_content

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get quote_ref for the client_id to delete associated priced_items
        cursor.execute("SELECT quote_ref FROM clients WHERE id = ?", (client_id,))
        result = cursor.fetchone()
        if result:
            client_quote_ref_to_delete = result[0]
            cursor.execute("DELETE FROM priced_items WHERE client_quote_ref = ?", (client_quote_ref_to_delete,))
            print(f"Deleted priced items for quote_ref: {client_quote_ref_to_delete}")

            # Also explicitly delete document content
            delete_document_content(client_quote_ref_to_delete, db_path)
        else:
            print(f"Warning: Client ID {client_id} not found, cannot get quote_ref for deleting priced items.")

        # Delete from clients table
        cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()

        if cursor.rowcount > 0:
            print(f"Successfully deleted client record ID: {client_id}")
            return True
        else:
            print(f"Warning: No client record found with ID: {client_id} to delete.")
            return False

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
