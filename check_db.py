import sqlite3
import os
import json
from src.utils.db import DB_PATH

def check_database():
    """Check the database for machines and templates."""
    print(f"\n==== DATABASE CHECK UTILITY ====")
    print(f"Looking for database at: {os.path.abspath(DB_PATH)}")
    
    # Check if database file exists
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database file not found at {DB_PATH}")
        print(f"Please run 'python initialize_db.py' first to create the database.")
        return
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"\nTables in database: {', '.join([t['name'] for t in tables])}")
        
        # Check clients
        cursor.execute("SELECT COUNT(*) as count FROM clients")
        client_count = cursor.fetchone()['count']
        print(f"\nFound {client_count} clients in database")
        
        if client_count > 0:
            cursor.execute("SELECT id, quote_ref, customer_name FROM clients LIMIT 3")
            clients = cursor.fetchall()
            print("Sample clients:")
            for client in clients:
                print(f"  - ID: {client['id']}, Quote: {client['quote_ref']}, Name: {client['customer_name']}")
        
        # Check machines
        cursor.execute("SELECT COUNT(*) as count FROM machines")
        machine_count = cursor.fetchone()['count']
        print(f"\nFound {machine_count} machines in database")
        
        if machine_count > 0:
            cursor.execute("SELECT id, machine_name, client_quote_ref FROM machines ORDER BY id")
            machines = cursor.fetchall()
            print("All machines:")
            for machine in machines:
                print(f"  - ID: {machine['id']}, Name: {machine['machine_name']}, Quote: {machine['client_quote_ref']}")
        
        # Check templates
        cursor.execute("SELECT COUNT(*) as count FROM machine_templates")
        template_count = cursor.fetchone()['count']
        print(f"\nFound {template_count} templates in database")
        
        if template_count > 0:
            cursor.execute("""
            SELECT mt.id, mt.machine_id, mt.template_type, m.machine_name 
            FROM machine_templates mt
            JOIN machines m ON mt.machine_id = m.id
            ORDER BY mt.machine_id
            """)
            templates = cursor.fetchall()
            print("All templates:")
            for template in templates:
                print(f"  - ID: {template['id']}, Machine ID: {template['machine_id']}, " +
                     f"Type: {template['template_type']}, Machine: {template['machine_name']}")
        
        # Check duplicate machine names
        cursor.execute("""
        SELECT m1.machine_name, COUNT(*) as count
        FROM machines m1
        GROUP BY m1.machine_name
        HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        
        if duplicates:
            print(f"\nFound {len(duplicates)} duplicate machine names:")
            for dup in duplicates:
                print(f"  - '{dup['machine_name']}' appears {dup['count']} times")
                
                # Show the specific machine records
                cursor.execute("""
                SELECT id, machine_name, client_quote_ref
                FROM machines
                WHERE machine_name = ?
                ORDER BY id
                """, (dup['machine_name'],))
                
                dup_machines = cursor.fetchall()
                for m in dup_machines:
                    print(f"    * ID: {m['id']}, Quote: {m['client_quote_ref']}")
                    
                    # Check for templates for this machine
                    cursor.execute("""
                    SELECT id, template_type
                    FROM machine_templates
                    WHERE machine_id = ?
                    """, (m['id'],))
                    
                    templates = cursor.fetchall()
                    if templates:
                        print(f"      Templates:")
                        for t in templates:
                            print(f"        - ID: {t['id']}, Type: {t['template_type']}")
                    else:
                        print(f"      No templates for this machine.")
        else:
            print("\nNo duplicate machine names found.")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_database() 