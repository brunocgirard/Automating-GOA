import sqlite3
import json
import os

DB_PATH = os.path.join("data", "crm_data.db")

def diagnose_database():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("\n--- CHECKING MACHINE ID 3 TEMPLATES ---")
        cursor.execute("SELECT machine_name FROM machines WHERE id = 3")
        machine_name = cursor.fetchone()
        if machine_name:
            print(f"Machine name for ID 3: {machine_name['machine_name']}")
            
            # Check if there's a template for this machine
            cursor.execute("SELECT id, template_type, template_data_json FROM machine_templates WHERE machine_id = 3")
            templates = cursor.fetchall()
            if templates:
                print(f"Found {len(templates)} templates for machine ID 3:")
                for template in templates:
                    print(f"  Template ID: {template['id']}, Type: {template['template_type']}")
                    try:
                        if template['template_data_json']:
                            template_data = json.loads(template['template_data_json'])
                            print(f"  Template data has {len(template_data)} fields")
                            print(f"  Sample fields: {list(template_data.keys())[:5]}")
                        else:
                            print("  Template data JSON is empty")
                    except json.JSONDecodeError as e:
                        print(f"  Error decoding template data JSON: {e}")
            else:
                print("No templates found for machine ID 3!")
                
                # Check if there are other machine templates for reference
                cursor.execute("SELECT id, machine_id, template_type FROM machine_templates LIMIT 5")
                other_templates = cursor.fetchall()
                print("\nOther machine templates in database:")
                for template in other_templates:
                    print(f"  ID: {template['id']}, Machine ID: {template['machine_id']}, Type: {template['template_type']}")
        else:
            print("Machine with ID 3 not found in database!")
            
        # Check what's happening in the UI selection
        print("\n--- DIAGNOSING TEMPLATE SELECTOR ISSUE ---")
        cursor.execute("""
        SELECT m.id as machine_id, m.machine_name, 
               t.id as template_id, t.template_type 
        FROM machines m
        LEFT JOIN machine_templates t ON m.id = t.machine_id
        WHERE m.id = 3
        """)
        join_results = cursor.fetchall()
        if join_results:
            print(f"Join results for machine ID 3 (LEFT JOIN with templates):")
            for result in join_results:
                print(f"  Machine: {result['machine_id']} - {result['machine_name']}")
                print(f"  Template: {result['template_id']} - {result['template_type']}")
        else:
            print("No results from join query for machine ID 3")
        
        # Get database info
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"\nTables in database: {[t[0] for t in tables]}")
        
        print("\n--- TABLE STRUCTURE ---")
        for table in [t[0] for t in tables]:
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                print(f"Table '{table}' columns:")
                for col in columns:
                    print(f"  {col['name']} ({col['type']})")
            except sqlite3.OperationalError:
                print(f"Error getting columns for table '{table}'")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    diagnose_database() 