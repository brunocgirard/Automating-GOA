#!/usr/bin/env python
"""
Test script to examine database tables and verify that machines and templates are properly saved.
"""

import os
import sqlite3
import json
from src.utils.crm_utils import DB_PATH, init_db
from datetime import datetime

def check_database_tables():
    """Check database tables and their contents."""
    print(f"Checking database at {os.path.abspath(DB_PATH)}...")
    
    # Make sure the database exists
    if not os.path.exists(DB_PATH):
        print(f"Database file not found at {DB_PATH}")
        return False
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Found {len(tables)} tables in the database:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Check for goa_modifications table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='goa_modifications'")
        if not cursor.fetchone():
            print("❌ goa_modifications table NOT found!")
            return False
        else:
            print("✅ goa_modifications table found")
            
        # Check clients
        cursor.execute("SELECT COUNT(*) FROM clients")
        client_count = cursor.fetchone()[0]
        print(f"\nFound {client_count} clients in the database")
        
        if client_count > 0:
            cursor.execute("SELECT id, quote_ref, customer_name FROM clients LIMIT 5")
            clients = cursor.fetchall()
            print("Sample clients:")
            for client in clients:
                print(f"  - ID: {client[0]}, Quote: {client[1]}, Name: {client[2]}")
        
        # Check machines
        cursor.execute("SELECT COUNT(*) FROM machines")
        machine_count = cursor.fetchone()[0]
        print(f"\nFound {machine_count} machines in the database")
        
        if machine_count > 0:
            cursor.execute("SELECT id, client_quote_ref, machine_name FROM machines LIMIT 5")
            machines = cursor.fetchall()
            print("Sample machines:")
            for machine in machines:
                print(f"  - ID: {machine[0]}, Quote: {machine[1]}, Name: {machine[2]}")
                
            # Check machine_templates
            cursor.execute("SELECT COUNT(*) FROM machine_templates")
            template_count = cursor.fetchone()[0]
            print(f"\nFound {template_count} machine templates in the database")
            
            if template_count > 0:
                cursor.execute("""
                SELECT mt.id, m.machine_name, mt.template_type, mt.generated_file_path 
                FROM machine_templates mt
                JOIN machines m ON mt.machine_id = m.id
                LIMIT 5
                """)
                templates = cursor.fetchall()
                print("Sample templates:")
                for template in templates:
                    print(f"  - ID: {template[0]}, Machine: {template[1]}, Type: {template[2]}, File: {template[3]}")
                
                # Check modifications
                cursor.execute("SELECT COUNT(*) FROM goa_modifications")
                mod_count = cursor.fetchone()[0]
                print(f"\nFound {mod_count} GOA modifications in the database")
                
                if mod_count > 0:
                    cursor.execute("""
                    SELECT gm.id, mt.template_type, m.machine_name, gm.field_key, gm.original_value, gm.modified_value
                    FROM goa_modifications gm
                    JOIN machine_templates mt ON gm.machine_template_id = mt.id
                    JOIN machines m ON mt.machine_id = m.id
                    LIMIT 5
                    """)
                    mods = cursor.fetchall()
                    print("Sample modifications:")
                    for mod in mods:
                        print(f"  - ID: {mod[0]}, Template: {mod[1]}, Machine: {mod[2]}")
                        print(f"    Field: {mod[3]}, Original: {mod[4]}, Modified: {mod[5]}")
            else:
                print("❌ No machine templates found in the database")
                
                # Insert a test template for diagnosis
                if machine_count > 0:
                    # Get the first machine ID
                    cursor.execute("SELECT id FROM machines LIMIT 1")
                    first_machine_id = cursor.fetchone()[0]
                    
                    print(f"\nAttempting to create a test template for machine ID {first_machine_id}...")
                    template_data = {
                        "test_field": "Test Value",
                        "test_check": "YES"
                    }
                    
                    try:
                        cursor.execute("""
                        INSERT INTO machine_templates 
                        (machine_id, template_type, template_data_json, processing_date)
                        VALUES (?, ?, ?, ?)
                        """, (
                            first_machine_id,
                            "Test Template",
                            json.dumps(template_data),
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ))
                        conn.commit()
                        
                        template_id = cursor.lastrowid
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
                            "Test Script",
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ))
                        conn.commit()
                        
                        print(f"✅ Added test modification for template ID {template_id}")
                    except Exception as e:
                        print(f"❌ Error creating test data: {e}")
        else:
            print("❌ No machines found in the database")
        
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

def fix_database_if_needed():
    """Initialize the database if needed."""
    print("Initializing database with latest schema...")
    init_db()
    print("Database initialization complete.")

def test_load_all_processed_machines():
    """
    Tests loading all machines that have been processed with templates.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("\n=== TESTING LOAD_ALL_PROCESSED_MACHINES FUNCTION ===")
        print(f"Database file exists: {os.path.exists(DB_PATH)}")
        
        # Check if required tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        table_names = [t[0] for t in tables]
        print(f"Tables in database: {table_names}")
        
        # Check counts in each table
        print("\nTable record counts:")
        for table in ["machines", "machine_templates", "clients"]:
            if table in table_names:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  - {table}: {count} records")
            else:
                print(f"  - {table}: TABLE NOT FOUND")
        
        # Test the SQL query
        try:
            print("\nTesting the query for load_all_processed_machines:")
            cursor.execute("""
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
            GROUP BY 
                m.id
            ORDER BY 
                c.customer_name, m.machine_name
            """)
            
            rows = cursor.fetchall()
            
            if rows:
                print(f"\nFound {len(rows)} processed machines")
                print("\nSample machine data:")
                for i, row in enumerate(rows[:3]):  # Show first 3 rows
                    print(f"\nMachine {i+1}:")
                    row_dict = dict(row)
                    for key, value in row_dict.items():
                        print(f"  {key}: {value}")
            else:
                print("No processed machines found in the database")
                
                # Let's check each part of the join separately
                print("\nChecking machines with templates:")
                cursor.execute("""
                SELECT m.id, m.machine_name, mt.id as template_id, mt.template_type
                FROM machines m
                JOIN machine_templates mt ON m.id = mt.machine_id
                LIMIT 5
                """)
                template_join_rows = cursor.fetchall()
                
                if template_join_rows:
                    print(f"Found {len(template_join_rows)} machines with templates")
                    for row in template_join_rows:
                        print(f"  Machine ID: {row['id']}, Name: {row['machine_name']}, Template ID: {row['template_id']}, Type: {row['template_type']}")
                else:
                    print("No machines found with templates")
                
                # Check clients connection
                print("\nChecking machines with client connections:")
                cursor.execute("""
                SELECT m.id, m.machine_name, m.client_quote_ref, c.id as client_id, c.customer_name
                FROM machines m
                JOIN clients c ON m.client_quote_ref = c.quote_ref
                LIMIT 5
                """)
                client_join_rows = cursor.fetchall()
                
                if client_join_rows:
                    print(f"Found {len(client_join_rows)} machines with client connections")
                    for row in client_join_rows:
                        print(f"  Machine ID: {row['id']}, Name: {row['machine_name']}, Client ID: {row['client_id']}, Client: {row['customer_name']}")
                else:
                    print("No machines found with client connections")
        except sqlite3.Error as e:
            print(f"SQL Error: {e}")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Testing database setup for GOA modifications feature")
    print("=" * 50)
    
    # Check database
    if not check_database_tables():
        print("\nTrying to fix database issues...")
        fix_database_if_needed()
        
        # Check again after fixing
        if check_database_tables():
            print("\n✅ Database issues fixed successfully!")
        else:
            print("\n❌ Still having issues with the database")
    else:
        print("\n✅ Database looks good!")

    test_load_all_processed_machines() 