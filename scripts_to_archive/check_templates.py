import sqlite3
import json

# Connect to the database
conn = sqlite3.connect('data/crm_data.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check for machine with ID 3
cursor.execute("SELECT * FROM machines WHERE id = 3")
machine = cursor.fetchone()
if machine:
    print(f"Machine found: ID {machine['id']}, Name: {machine['machine_name']}")
    
    # Check for templates for this machine
    cursor.execute("SELECT * FROM machine_templates WHERE machine_id = 3")
    templates = cursor.fetchall()
    if templates:
        print(f"Found {len(templates)} templates:")
        for template in templates:
            print(f"  Template ID: {template['id']}, Type: {template['template_type']}")
    else:
        print("No templates found for this machine!")
        
    # Insert a test template if none exists
    if not templates:
        print("\nInserting a test GOA template for this machine...")
        
        # Simple test template data
        test_data = {
            "machine_name": machine['machine_name'],
            "customer_name": "Test Customer",
            "description": "This is a test template"
        }
        
        # Insert the template
        cursor.execute("""
        INSERT INTO machine_templates 
        (machine_id, template_type, template_data_json, generated_file_path, processing_date)
        VALUES (?, ?, ?, ?, datetime('now'))
        """, (3, "GOA", json.dumps(test_data), ""))
        
        conn.commit()
        
        # Get the newly created template
        cursor.execute("SELECT * FROM machine_templates WHERE machine_id = 3")
        new_template = cursor.fetchone()
        if new_template:
            print(f"Successfully created template with ID {new_template['id']}")
        else:
            print("Failed to create template!")
else:
    print("Machine with ID 3 not found!")
    
# Close the connection
conn.close() 