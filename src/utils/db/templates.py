import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

# Import for document regeneration
from src.utils.html_doc_filler import fill_and_generate_html
from src.utils.doc_filler import fill_word_document_from_llm_data
from src.utils.form_generator import OUTPUT_HTML_PATH

# Relative import from base module
from .base import DB_PATH

# Define base template paths
HTML_TEMPLATE_PATH = OUTPUT_HTML_PATH
DOCX_TEMPLATE_PATH = os.path.join("templates", "template.docx")


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
