import sqlite3
import os
import json
from src.utils.crm_utils import DB_PATH

def fix_duplicate_machines():
    """
    Fix the specific issue with duplicate machines IDs 3 and 5.
    Machine ID 3 is correct with the proper quote reference.
    Machine ID 5 is a duplicate with a filename-like quote reference.
    
    We'll merge any template data from machine ID 5 into machine ID 3 and delete machine ID 5.
    """
    print("\n==== DUPLICATE MACHINE FIXER ====")
    print(f"Using database at: {os.path.abspath(DB_PATH)}")
    
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database file not found at {DB_PATH}")
        return
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # First, check if both machines exist
        cursor.execute("""
        SELECT id, machine_name, client_quote_ref 
        FROM machines 
        WHERE id IN (3, 5)
        """)
        machines = cursor.fetchall()
        
        if len(machines) != 2:
            print(f"Expected 2 machines with IDs 3 and 5, but found {len(machines)}")
            print("No fix applied")
            return
        
        print("Found both machines:")
        for machine in machines:
            print(f"  - ID: {machine['id']}, Name: {machine['machine_name']}, Quote: {machine['client_quote_ref']}")
        
        # Check templates for each machine
        template_data = {}
        for machine_id in [3, 5]:
            cursor.execute("""
            SELECT id, template_type, template_data_json, generated_file_path 
            FROM machine_templates 
            WHERE machine_id = ?
            """, (machine_id,))
            templates = cursor.fetchall()
            
            template_data[machine_id] = templates
            print(f"\nMachine ID {machine_id} has {len(templates)} templates:")
            for template in templates:
                print(f"  - ID: {template['id']}, Type: {template['template_type']}")
                # Check for modifications
                cursor.execute("""
                SELECT COUNT(*) as count 
                FROM goa_modifications 
                WHERE machine_template_id = ?
                """, (template['id'],))
                mod_count = cursor.fetchone()['count']
                if mod_count > 0:
                    print(f"    * Has {mod_count} modifications")
        
        # Decision: We'll keep machine ID 3 and its templates, and copy any data from machine ID 5
        # if it doesn't conflict with machine ID 3
        
        # First, check if machine ID 3 has a template of the same type as any template from machine ID 5
        template_types_3 = set(t['template_type'] for t in template_data[3])
        templates_to_copy = []
        
        for template in template_data[5]:
            if template['template_type'] not in template_types_3:
                # This is a unique template type in machine 5 - we should copy it to machine 3
                templates_to_copy.append(template)
            else:
                # Template type already exists in machine 3
                print(f"\nWARNING: Both machines have a template of type '{template['template_type']}'")
                print(f"Template from machine ID 3 will be kept, template ID {template['id']} from machine ID 5 will be discarded")
        
        if templates_to_copy:
            print(f"\nCopying {len(templates_to_copy)} unique templates from machine ID 5 to machine ID 3:")
            for template in templates_to_copy:
                # Copy this template to machine ID 3
                cursor.execute("""
                INSERT INTO machine_templates
                (machine_id, template_type, template_data_json, generated_file_path, processing_date)
                VALUES (?, ?, ?, ?, (SELECT processing_date FROM machine_templates WHERE id = ?))
                """, (3, template['template_type'], template['template_data_json'], 
                     template['generated_file_path'], template['id']))
                
                new_template_id = cursor.lastrowid
                print(f"  - Copied template ID {template['id']} to new template ID {new_template_id}")
                
                # Copy any modifications for this template
                cursor.execute("""
                SELECT * FROM goa_modifications WHERE machine_template_id = ?
                """, (template['id'],))
                mods = cursor.fetchall()
                
                if mods:
                    print(f"    * Copying {len(mods)} modifications")
                    for mod in mods:
                        cursor.execute("""
                        INSERT INTO goa_modifications
                        (machine_template_id, field_key, original_value, modified_value, 
                         modification_reason, modified_by, modification_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (new_template_id, mod['field_key'], mod['original_value'], 
                             mod['modified_value'], mod['modification_reason'], 
                             mod['modified_by'], mod['modification_date']))
        
        # Now delete machine ID 5 and all its templates (cascade should take care of modifications)
        cursor.execute("DELETE FROM machines WHERE id = 5")
        deleted_count = cursor.rowcount
        
        # Commit the changes
        conn.commit()
        
        if deleted_count > 0:
            print("\nSUCCESS: Duplicate machine ID 5 has been deleted")
            print("Any unique templates have been copied to machine ID 3")
            print("Please restart the application to see the changes")
        else:
            print("\nWARNING: Failed to delete machine ID 5")
    
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"Error: {e}")
        if conn:
            conn.rollback()
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    fix_duplicate_machines() 