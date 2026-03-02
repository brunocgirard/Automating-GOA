"""
Machine database operations - CRUD operations for identified machines within quotes.
"""

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List

from .base import (
    DB_PATH,
    get_connection,
    owner_scope_clause,
    row_to_dict,
    rows_to_dicts,
    safe_json_loads,
)


def save_machines_data(
    client_quote_ref: str,
    machines_data: Dict,
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
) -> bool:
    """
    Saves identified machines and their add-ons to the machines table.

    Args:
        client_quote_ref: The quote reference to link machines to.
        machines_data: Dictionary with "machines" list and "common_items" list.
            Each machine should have: machine_name, main_item, add_ons

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
        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, owner_user_id FROM clients WHERE quote_ref = ?", (client_quote_ref,))
        client_exists = cursor.fetchone()

        if not client_exists:
            # Create a basic client record if it doesn't exist
            print(f"Client with quote_ref {client_quote_ref} does not exist. Creating basic record.")
            processing_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Get a machine name for the client record if possible
            machine_name = ""
            if machines_data.get("machines") and len(machines_data["machines"]) > 0:
                machine_name = machines_data["machines"][0].get("machine_name", "")

            if isinstance(owner_user_id, int) and owner_user_id > 0:
                cursor.execute(
                    """
                    INSERT INTO clients (
                        quote_ref,
                        customer_name,
                        machine_model,
                        processing_date,
                        owner_user_id
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (client_quote_ref, "", machine_name, processing_ts, owner_user_id),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO clients (quote_ref, customer_name, machine_model, processing_date)
                    VALUES (?, ?, ?, ?)
                    """,
                    (client_quote_ref, "", machine_name, processing_ts),
                )
            conn.commit()
        else:
            existing_owner = client_exists[1] if len(client_exists) > 1 else None
            if isinstance(owner_user_id, int) and owner_user_id > 0:
                if existing_owner is not None and int(existing_owner) > 0 and int(existing_owner) != owner_user_id:
                    print(
                        "Permission denied in save_machines_data: "
                        f"quote_ref='{client_quote_ref}' is owned by another user."
                    )
                    return False
                if existing_owner is None:
                    cursor.execute(
                        "UPDATE clients SET owner_user_id = ? WHERE quote_ref = ?",
                        (owner_user_id, client_quote_ref),
                    )
                    conn.commit()

        # Delete any existing machines for this quote
        cursor.execute("DELETE FROM machines WHERE client_quote_ref = ?", (client_quote_ref,))

        # Prepare machines for insertion
        machines_to_insert = []
        processing_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def resolve_main_item(machine_payload: Dict[str, Any]) -> Dict[str, Any]:
            main_item = machine_payload.get("main_item")
            if isinstance(main_item, dict):
                return dict(main_item)
            return {}

        def resolve_description(machine_payload: Dict[str, Any], main_item: Dict[str, Any]) -> str:
            existing_description = machine_payload.get("description")
            if isinstance(existing_description, str) and existing_description.strip():
                return existing_description.strip()
            description = main_item.get("description")
            if isinstance(description, str):
                return description.strip()
            return ""

        def resolve_machine_type(machine_payload: Dict[str, Any], main_item: Dict[str, Any]) -> str:
            existing_type = machine_payload.get("machine_type")
            if isinstance(existing_type, str) and existing_type.strip():
                return existing_type.strip().lower()
            if main_item:
                return "main"
            return "option"

        # Process and validate each machine
        for machine in machines_data.get("machines", []):
            main_item = resolve_main_item(machine)
            machine_type = resolve_machine_type(machine, main_item)
            description = resolve_description(machine, main_item)

            # Ensure machine_name exists and is not empty
            if not machine.get("machine_name"):
                # Try to generate a name if missing
                if main_item and main_item.get("description"):
                    desc = main_item["description"]
                    # Use first line of description as machine name
                    machine["machine_name"] = desc.split('\n')[0] if '\n' in desc else desc
                else:
                    # Use a default name with timestamp
                    machine["machine_name"] = f"Unknown Machine {len(machines_to_insert) + 1}"
                print(f"Generated machine name: {machine['machine_name']}")

            # Make sure machine has client_quote_ref
            machine_copy = machine.copy()
            machine_copy["client_quote_ref"] = client_quote_ref
            machine_copy["machine_type"] = machine_type
            machine_copy["description"] = description
            machine_copy["main_item"] = main_item

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


def load_machines_for_quote(
    client_quote_ref: str,
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> List[Dict]:
    """
    Loads all identified machines for a given quote reference.

    Args:
        client_quote_ref: The quote reference to load machines for.
        db_path: Path to the SQLite database file.

    Returns:
        List of dictionaries containing machine data with keys:
        - id, machine_name, machine_data_json, processing_date, machine_data (parsed JSON)
    """
    conn = None
    machines = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        scope_sql, scope_params = owner_scope_clause(
            owner_user_id,
            include_all_for_admin,
            table_alias="c",
        )

        cursor.execute(f"""
        SELECT m.id, m.machine_name, m.machine_data_json, m.processing_date
        FROM machines m
        JOIN clients c ON c.quote_ref = m.client_quote_ref
        WHERE m.client_quote_ref = ?{scope_sql}
        ORDER BY m.id
        """, (client_quote_ref, *scope_params))

        rows = cursor.fetchall()
        for row in rows:
            machine_dict = row_to_dict(row) or {}
            machine_data = safe_json_loads(machine_dict["machine_data_json"], {})
            if isinstance(machine_data, dict):
                machine_dict["machine_data"] = machine_data
                machines.append(machine_dict)
            else:
                print(f"Error parsing JSON for machine ID {row['id']}")

        return machines
    except sqlite3.Error as e:
        print(f"Database error loading machines for quote {client_quote_ref}: {e}")
        return []
    finally:
        if conn:
            conn.close()


def find_machines_by_name(
    machine_name: str,
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> List[Dict]:
    """
    Finds machines by name across all quotes using partial matching.

    Args:
        machine_name: The name of the machine to search for.
        db_path: Path to the SQLite database file.

    Returns:
        List of dictionaries containing machine data and related client information
    """
    conn = None
    machines = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Use LIKE for partial matching with wildcards
        search_pattern = f"%{machine_name}%"
        scope_sql, scope_params = owner_scope_clause(
            owner_user_id,
            include_all_for_admin,
            table_alias="c",
        )

        cursor.execute(f"""
        SELECT m.id, m.machine_name, m.machine_data_json, m.client_quote_ref, m.processing_date,
               c.customer_name, c.id as client_id
        FROM machines m
        JOIN clients c ON m.client_quote_ref = c.quote_ref
        WHERE m.machine_name LIKE ?{scope_sql}
        ORDER BY m.processing_date DESC
        """, (search_pattern, *scope_params))

        rows = cursor.fetchall()
        for row in rows:
            machine_dict = row_to_dict(row) or {}
            machine_data = safe_json_loads(machine_dict["machine_data_json"], {})
            if isinstance(machine_data, dict):
                machine_dict["machine_data"] = machine_data
                machines.append(machine_dict)
            else:
                print(f"Error parsing JSON for machine ID {row['id']}")

        return machines
    except sqlite3.Error as e:
        print(f"Database error finding machines by name '{machine_name}': {e}")
        return []
    finally:
        if conn:
            conn.close()


def load_all_processed_machines(
    db_path: str = DB_PATH,
    owner_user_id: int | None = None,
    include_all_for_admin: bool = False,
) -> List[Dict]:
    """
    Loads all machines that have been processed with templates,
    including client information for better organization in the reports page.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        List of dictionaries containing machine information and related client data
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        scope_sql, scope_params = owner_scope_clause(
            owner_user_id,
            include_all_for_admin,
            table_alias="c",
        )

        # Join machines, machine_templates, and clients tables to get all necessary data
        cursor.execute(f"""
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
        WHERE 1 = 1{scope_sql}
        GROUP BY
            m.id
        ORDER BY
            c.customer_name, m.machine_name
        """, tuple(scope_params))

        return rows_to_dicts(cursor.fetchall())
    except sqlite3.Error as e:
        print(f"Error loading processed machines: {e}")
        return []
    finally:
        if conn:
            conn.close()


def group_items_by_confirmed_machines(all_items, main_machine_indices, common_option_indices):
    """
    Groups items into machines based on confirmed indices.

    Args:
        all_items: List of all item dictionaries.
        main_machine_indices: List of indices identifying main machine items.
        common_option_indices: List of indices identifying common/shared items.

    Returns:
        Dictionary with "machines" list and "common_items" list
    """
    machines = []
    common_items = []
    remaining_items = list(range(len(all_items)))
    sorted_machine_indices = sorted(set(main_machine_indices))
    sorted_common_indices = sorted(set(common_option_indices))

    for idx in sorted_common_indices:
        if idx in remaining_items:
            remaining_items.remove(idx)
            common_item = dict(all_items[idx])
            common_item["machine_type"] = "common"
            common_items.append(common_item)

    for machine_idx in sorted_machine_indices:
        if machine_idx in remaining_items:
            remaining_items.remove(machine_idx)
            next_machine_idx = float('inf')
            for next_idx in sorted_machine_indices:
                if next_idx > machine_idx and next_idx < next_machine_idx:
                    next_machine_idx = next_idx
            add_ons = []
            for idx in list(remaining_items):
                if idx > machine_idx and (idx < next_machine_idx or next_machine_idx == float('inf')):
                    add_on_item = dict(all_items[idx])
                    add_on_item["machine_type"] = "option"
                    add_ons.append(add_on_item)
                    remaining_items.remove(idx)
            main_item = dict(all_items[machine_idx])
            main_item["machine_type"] = "main"
            description = main_item.get("description", "")
            machine_name = description.split('\n')[0] if isinstance(description, str) else ""
            machines.append({
                "machine_name": machine_name,
                "description": description,
                "machine_type": "main",
                "main_item": main_item,
                "add_ons": add_ons,
            })

    for idx in remaining_items:
        common_item = dict(all_items[idx])
        common_item["machine_type"] = "common"
        common_items.append(common_item)

    return {"machines": machines, "common_items": common_items}


def calculate_machine_price(machine_data: Dict) -> float:
    """
    Calculates the total price for a machine including its add-ons.

    Args:
        machine_data: Dictionary containing machine data with 'main_item' and 'add_ons' keys.

    Returns:
        float: Total price of the machine and its add-ons
    """
    total_price = 0.0
    main_item = machine_data.get("main_item", {})
    main_price = main_item.get("item_price_numeric", 0)
    if main_price is not None:
        total_price += main_price
    for item in machine_data.get("add_ons", []):
        addon_price = item.get("item_price_numeric", 0)
        if addon_price is not None:
            total_price += addon_price
    return total_price
