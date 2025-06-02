import sqlite3
import json
import os

# Connect to the database
conn = sqlite3.connect('data/crm_data.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all templates
cursor.execute("SELECT id, machine_id, template_type, template_data_json FROM machine_templates")
templates = cursor.fetchall()

print(f"Found {len(templates)} templates in database")

# Check each template for valid JSON data
fixed_count = 0
for template in templates:
    template_id = template['id']
    machine_id = template['machine_id']
    template_type = template['template_type']
    template_data_json = template['template_data_json']
    
    print(f"\nTemplate ID: {template_id}, Machine ID: {machine_id}, Type: {template_type}")
    
    # Check if template_data_json is empty or invalid
    is_valid = True
    template_data = None
    
    try:
        if template_data_json:
            template_data = json.loads(template_data_json)
            if template_data:
                print(f"  Template data valid with {len(template_data)} fields")
                # Print first few fields
                fields = list(template_data.keys())[:5]
                print(f"  Sample fields: {fields}")
            else:
                print("  Template data JSON parsed to empty object/array")
                is_valid = False
        else:
            print("  Template data JSON is empty or None")
            is_valid = False
    except json.JSONDecodeError:
        print(f"  Error decoding template data JSON")
        is_valid = False
    
    # Fix invalid templates
    if not is_valid:
        print("  Fixing invalid template...")
        
        # Get machine name for this template
        cursor.execute("SELECT machine_name FROM machines WHERE id = ?", (machine_id,))
        machine_row = cursor.fetchone()
        machine_name = machine_row['machine_name'] if machine_row else f"Machine {machine_id}"
        
        # Create a simple default template
        default_data = {
            "machine_name": machine_name,
            "customer_name": "Default Customer",
            "quote_ref": "Default Reference",
            "description": f"Default template for {machine_name}",
            "capacity": "Standard",
            "direction": "Left to Right",
            "machine_type": template_type
        }
        
        # Update the template
        cursor.execute("""
        UPDATE machine_templates 
        SET template_data_json = ?, processing_date = datetime('now')
        WHERE id = ?
        """, (json.dumps(default_data), template_id))
        
        fixed_count += 1
        print(f"  Updated template with default data")

if fixed_count > 0:
    conn.commit()
    print(f"\nFixed {fixed_count} templates")
else:
    print("\nNo templates needed fixing")

# Close the connection
conn.close()

print("\nTemplate fix complete. Please restart the app to see the changes.") 