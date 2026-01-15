import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List

# Import for document regeneration
from src.utils.html_doc_filler import fill_and_generate_html
from src.utils.doc_filler import fill_word_document_from_llm_data
from src.utils.form_generator import OUTPUT_HTML_PATH

# Import DB_PATH from base module
from .base import DB_PATH

# Define base template paths
HTML_TEMPLATE_PATH = OUTPUT_HTML_PATH
DOCX_TEMPLATE_PATH = os.path.join("templates", "template.docx")
# Legacy constant kept for compatibility if needed, but should rely on extension check
TEMPLATE_FILE_PATH = os.path.join("templates", "template.docx")


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

                    if generated_file_path.endswith('.html'):
                        print(f"Regenerating HTML document at: {generated_file_path}")
                        fill_and_generate_html(str(HTML_TEMPLATE_PATH), template_data, generated_file_path)
                        print(f"Successfully regenerated HTML document for machine template ID: {machine_template_id}")
                    elif generated_file_path.endswith('.docx'):
                        # Fallback for legacy DOCX or SortStar (assuming standard template for now, ideal would be to store template path)
                        # Note: This might pick the wrong template for SortStar if not handled, but sticking to previous logic for docx
                        template_source = DOCX_TEMPLATE_PATH
                        if "sortstar" in generated_file_path.lower():
                             template_source = os.path.join("templates", "goa_sortstar_temp.docx")

                        if os.path.exists(template_source):
                            print(f"Regenerating DOCX document at: {generated_file_path} using {template_source}")
                            fill_word_document_from_llm_data(template_source, template_data, generated_file_path)
                            print(f"Successfully regenerated DOCX document for machine template ID: {machine_template_id}")
                        else:
                            print(f"Warning: Template source {template_source} not found.")
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


def save_bulk_goa_modifications(
    machine_template_id: int,
    changes: Dict[str, Dict[str, str]],
    modification_reason: str = "Batch Manual Edit",
    modified_by: str = "User",
    db_path: str = DB_PATH
) -> bool:
    """
    Saves a batch of modifications to a GOA template field and updates the underlying template data.
    """
    if not machine_template_id or not changes:
        print("Error: Missing required parameters for save_bulk_goa_modifications.")
        return False

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("BEGIN TRANSACTION")

        cursor.execute("SELECT template_data_json, generated_file_path FROM machine_templates WHERE id = ?", (machine_template_id,))
        template_row = cursor.fetchone()
        if not template_row:
            print(f"Error: Machine template with ID {machine_template_id} not found.")
            conn.rollback()
            return False

        template_data_json, generated_file_path = template_row
        try:
            template_data = json.loads(template_data_json or '{}')
        except json.JSONDecodeError:
            print(f"Error parsing JSON for machine template ID {machine_template_id}")
            conn.rollback()
            return False

        modification_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for field_key, change_info in changes.items():
            original_value = change_info.get("original_value")
            modified_value = change_info.get("new_value")

            template_data[field_key] = modified_value

            cursor.execute("SELECT id FROM goa_modifications WHERE machine_template_id = ? AND field_key = ?", (machine_template_id, field_key))
            existing_mod = cursor.fetchone()

            if existing_mod:
                cursor.execute("""
                UPDATE goa_modifications
                SET original_value = ?, modified_value = ?, modification_reason = ?, modified_by = ?, modification_date = ?
                WHERE id = ?
                """, (original_value, modified_value, modification_reason, modified_by, modification_date, existing_mod[0]))
            else:
                cursor.execute("""
                INSERT INTO goa_modifications (machine_template_id, field_key, original_value, modified_value, modification_reason, modified_by, modification_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (machine_template_id, field_key, original_value, modified_value, modification_reason, modified_by, modification_date))

        cursor.execute("""
        UPDATE machine_templates SET template_data_json = ?, processing_date = ? WHERE id = ?
        """, (json.dumps(template_data), modification_date, machine_template_id))

        conn.commit()

        if generated_file_path:
            if generated_file_path.endswith('.html'):
                print(f"Regenerating HTML document at: {generated_file_path}")
                fill_and_generate_html(str(HTML_TEMPLATE_PATH), template_data, generated_file_path)
                print(f"Successfully regenerated HTML document for machine template ID: {machine_template_id}")
            elif generated_file_path.endswith('.docx') and os.path.exists(TEMPLATE_FILE_PATH):
                print(f"Regenerating DOCX document at: {generated_file_path}")
                fill_word_document_from_llm_data(TEMPLATE_FILE_PATH, template_data, generated_file_path)
                print(f"Successfully regenerated document for machine template ID: {machine_template_id}")

        print(f"Saved {len(changes)} GOA modifications for machine template ID: {machine_template_id}")
        return True

    except sqlite3.Error as e:
        print(f"Database error in save_bulk_goa_modifications: {e}")
        if conn: conn.rollback()
        return False
    except Exception as e:
        print(f"Unexpected error in save_bulk_goa_modifications: {e}")
        if conn: conn.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()
