import sqlite3
import json

def check_machines():
    conn = None
    try:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check machines table
        print("\n---- CHECKING MACHINES ----")
        cursor.execute("SELECT id, machine_name, client_quote_ref FROM machines ORDER BY id")
        machines = cursor.fetchall()
        
        print(f"Total machines: {len(machines)}")
        print("\nMACHINE LIST:")
        print("ID | MACHINE NAME | CLIENT QUOTE REF")
        print("-" * 50)
        for machine in machines:
            print(f"{machine['id']} | {machine['machine_name']} | {machine['client_quote_ref']}")
        
        # Check for machines with IDs 3 and 5
        print("\n---- CHECKING SPECIFIC MACHINES ----")
        cursor.execute("SELECT * FROM machines WHERE id=3 OR id=5")
        specific_machines = cursor.fetchall()
        
        print(f"Found {len(specific_machines)} machines with IDs 3 or 5")
        for machine in specific_machines:
            print(f"\nMachine ID: {machine['id']}")
            print(f"Name: {machine['machine_name']}")
            print(f"Quote Ref: {machine['client_quote_ref']}")
            
            # Check machine_data_json
            try:
                machine_data = json.loads(machine['machine_data_json'])
                print(f"Machine data contains: {list(machine_data.keys())}")
                print(f"Main item description: {machine_data.get('main_item', {}).get('description', 'N/A')[:50]}...")
            except:
                print("Error parsing machine data JSON")
            
            # Check for templates
            cursor.execute("SELECT id, template_type, processing_date FROM machine_templates WHERE machine_id=?", 
                          (machine['id'],))
            templates = cursor.fetchall()
            
            if templates:
                print(f"Templates for machine ID {machine['id']}:")
                for template in templates:
                    print(f"  - ID: {template['id']}, Type: {template['template_type']}, Date: {template['processing_date']}")
            else:
                print(f"No templates found for machine ID {machine['id']}")
        
        # Suggestion for fix if needed
        if len(specific_machines) == 2:
            machine3 = next((m for m in specific_machines if m['id'] == 3), None)
            machine5 = next((m for m in specific_machines if m['id'] == 5), None)
            
            if machine3 and machine5 and machine3['machine_name'] == machine5['machine_name']:
                print("\n---- SUGGESTED FIX ----")
                
                # Check which machine has templates
                cursor.execute("SELECT COUNT(*) FROM machine_templates WHERE machine_id=3")
                templates3 = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM machine_templates WHERE machine_id=5")
                templates5 = cursor.fetchone()[0]
                
                if templates3 == 0 and templates5 > 0:
                    print("Machine ID 3 has no templates but Machine ID 5 has templates.")
                    print("Suggested action: Update machine_templates to use machine_id=3 instead of machine_id=5")
                    print("\nTo fix, run this SQL:")
                    print("UPDATE machine_templates SET machine_id=3 WHERE machine_id=5;")
                    print("DELETE FROM machines WHERE id=5;")
                elif templates3 > 0 and templates5 == 0:
                    print("Machine ID 5 has no templates but Machine ID 3 has templates.")
                    print("Suggested action: Delete machine ID 5 as it appears to be a duplicate")
                    print("\nTo fix, run this SQL:")
                    print("DELETE FROM machines WHERE id=5;")
                elif templates3 > 0 and templates5 > 0:
                    print("Both machines have templates. This requires manual review.")
                    print("Suggested action: Compare the templates and decide which to keep")
                else:
                    print("Neither machine has templates. You can safely delete one of them.")
                    print("\nTo fix, run this SQL:")
                    print("DELETE FROM machines WHERE id=5;")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_machines() 