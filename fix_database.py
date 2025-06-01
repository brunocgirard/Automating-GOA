#!/usr/bin/env python
"""
Script to fix database issues with machine data and templates.
This script will:
1. Ensure the database schema is up-to-date
2. Fix client records with missing quote references
3. Fix machine records with missing client references
4. Ensure template data is properly saved
"""

import os
import sqlite3
import json
from datetime import datetime
import traceback
from src.utils.crm_utils import (
    DB_PATH, init_db, load_all_clients, load_machines_for_quote,
    save_machines_data, save_client_info, save_machine_template_data
)

def ensure_database_schema():
    """Initialize the database with the latest schema."""
    print(f"Ensuring database schema is up-to-date at {os.path.abspath(DB_PATH)}...")
    init_db()
    print("Database schema initialization complete.")
    
def fix_missing_client_records():
    """Find and fix machines with missing client records."""
    print("\nChecking for machines with missing client records...")
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Find machines with client_quote_refs that don't exist in clients table
        cursor.execute("""
        SELECT m.id, m.client_quote_ref, m.machine_name
        FROM machines m
        LEFT JOIN clients c ON m.client_quote_ref = c.quote_ref
        WHERE c.id IS NULL
        """)
        
        orphaned_machines = cursor.fetchall()
        if not orphaned_machines:
            print("✅ No orphaned machines found.")
            return
            
        print(f"Found {len(orphaned_machines)} machines with missing client records.")
        
        for machine_id, quote_ref, machine_name in orphaned_machines:
            print(f"Creating client record for machine ID {machine_id}, quote_ref: {quote_ref}")
            
            client_info = {
                "quote_ref": quote_ref,
                "customer_name": f"Auto-created for {machine_name}",
                "machine_model": machine_name,
                "processing_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            cursor.execute("""
            INSERT INTO clients (quote_ref, customer_name, machine_model, processing_date)
            VALUES (?, ?, ?, ?)
            """, (
                quote_ref,
                client_info["customer_name"],
                client_info["machine_model"],
                client_info["processing_date"]
            ))
        
        conn.commit()
        print(f"Created {len(orphaned_machines)} missing client records.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

def fix_machine_template_data():
    """Find and fix template records with missing data."""
    print("\nChecking for template records with issues...")
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Find templates with empty or invalid JSON data
        cursor.execute("""
        SELECT mt.id, mt.machine_id, mt.template_type, mt.template_data_json
        FROM machine_templates mt
        """)
        
        templates = cursor.fetchall()
        if not templates:
            print("No template records found.")
            return
            
        print(f"Checking {len(templates)} template records...")
        
        invalid_templates = []
        for template_id, machine_id, template_type, template_data_json in templates:
            try:
                # Try to parse JSON
                if not template_data_json or template_data_json.strip() in ('{}', '[]', ''):
                    invalid_templates.append((template_id, machine_id, template_type, "Empty JSON"))
                    continue
                    
                data = json.loads(template_data_json)
                if not isinstance(data, dict) or not data:
                    invalid_templates.append((template_id, machine_id, template_type, "Invalid data structure"))
            except json.JSONDecodeError:
                invalid_templates.append((template_id, machine_id, template_type, "Invalid JSON"))
        
        if not invalid_templates:
            print("✅ All templates have valid data.")
            return
            
        print(f"Found {len(invalid_templates)} templates with issues:")
        for template_id, machine_id, template_type, issue in invalid_templates:
            print(f"  - Template ID {template_id}, Machine ID {machine_id}, Type: {template_type}, Issue: {issue}")
            
            # Delete invalid template
            cursor.execute("DELETE FROM machine_templates WHERE id = ?", (template_id,))
            print(f"    Deleted invalid template ID {template_id}")
        
        conn.commit()
        print(f"Cleaned up {len(invalid_templates)} invalid templates.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

def check_client_machine_consistency():
    """Check consistency between clients and machines tables."""
    print("\nChecking consistency between clients and machines...")
    
    clients = load_all_clients()
    if not clients:
        print("No clients found in database.")
        return
        
    print(f"Found {len(clients)} clients in database.")
    
    for client in clients:
        quote_ref = client.get("quote_ref")
        if not quote_ref:
            print(f"Client ID {client.get('id')} has no quote_ref!")
            continue
            
        machines = load_machines_for_quote(quote_ref)
        print(f"Client {quote_ref}: {len(machines)} machines")
        
        # Check for machine_model consistency
        machine_names = [m.get("machine_name", "") for m in machines]
        if machine_names and not client.get("machine_model"):
            # Update client record with machine names
            machine_model = ", ".join(machine_names)
            print(f"Updating client {quote_ref} with machine model: {machine_model}")
            
            conn = None
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                
                cursor.execute("""
                UPDATE clients 
                SET machine_model = ?
                WHERE quote_ref = ?
                """, (machine_model[:200] if len(machine_model) > 200 else machine_model, quote_ref))
                
                conn.commit()
            except sqlite3.Error as e:
                print(f"Error updating client {quote_ref}: {e}")
            finally:
                if conn:
                    conn.close()
            
def create_test_template_if_needed():
    """Create a test template if none exist."""
    print("\nChecking if we need to create a test template...")
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if any templates exist
        cursor.execute("SELECT COUNT(*) FROM machine_templates")
        template_count = cursor.fetchone()[0]
        
        if template_count > 0:
            print(f"✅ {template_count} templates already exist.")
            return
            
        # Check if any machines exist
        cursor.execute("SELECT COUNT(*) FROM machines")
        machine_count = cursor.fetchone()[0]
        
        if machine_count == 0:
            print("No machines found. Cannot create test template.")
            return
            
        # Get the first machine
        cursor.execute("SELECT id, machine_name FROM machines LIMIT 1")
        first_machine = cursor.fetchone()
        
        if not first_machine:
            print("No machines found. Cannot create test template.")
            return
            
        machine_id, machine_name = first_machine
        print(f"Creating test template for machine ID {machine_id} ({machine_name})...")
        
        # Create a simple test template data
        template_data = {
            "test_field": "Test Value",
            "test_check": "YES",
            "plc_b&r_check": "YES",
            "hmi_size10_check": "YES"
        }
        
        # Insert the template
        processing_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        INSERT INTO machine_templates 
        (machine_id, template_type, template_data_json, processing_date)
        VALUES (?, ?, ?, ?)
        """, (
            machine_id,
            "GOA",
            json.dumps(template_data),
            processing_ts
        ))
        
        conn.commit()
        template_id = cursor.lastrowid
        
        if template_id:
            print(f"✅ Created test template with ID {template_id}")
            
            # Add a test modification
            cursor.execute("""
            INSERT INTO goa_modifications
            (machine_template_id, field_key, original_value, modified_value, modification_reason, modified_by, modification_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                template_id,
                "test_field",
                "Test Value",
                "Modified Test Value",
                "Test modification",
                "Fix Script",
                processing_ts
            ))
            
            conn.commit()
            print(f"✅ Added test modification for template ID {template_id}")
        else:
            print("Failed to create test template.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("🔧 Database Fix Tool for GOA Template Modifications 🔧")
    print("=" * 60)
    
    # Run all the fix functions
    ensure_database_schema()
    fix_missing_client_records()
    fix_machine_template_data()
    check_client_machine_consistency()
    create_test_template_if_needed()
    
    print("\n✅ Database fixes completed!")
    print("You can now run the application and test the template modifications feature.")
    print("If you're still experiencing issues, run test_db.py for detailed diagnostics.") 