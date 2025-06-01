import sqlite3
import json
import os
import sys
from src.utils.crm_utils import DB_PATH

def fix_machines():
    conn = None
    try:
        # Ensure the data directory exists
        if not os.path.exists(os.path.dirname(DB_PATH)):
            os.makedirs(os.path.dirname(DB_PATH))
            
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("\n==== MACHINE REPAIR UTILITY ====")
        
        # 1. Check if database exists
        if not os.path.exists(DB_PATH):
            print(f"Database file not found at {DB_PATH}!")
            return
            
        # 2. Get all machines for overview
        cursor.execute("SELECT id, machine_name, client_quote_ref FROM machines ORDER BY id")
        machines = cursor.fetchall()
        
        if not machines:
            print("No machines found in database.")
            return
            
        print(f"\nFound {len(machines)} machines in database.")
        print("\nMACHINE LIST:")
        for machine in machines:
            print(f"ID: {machine['id']}, Name: {machine['machine_name']}, Quote: {machine['client_quote_ref']}")
        
        # 3. Check for possible duplicate machines
        cursor.execute("""
        SELECT m1.id as id1, m2.id as id2, m1.machine_name, m1.client_quote_ref
        FROM machines m1
        JOIN machines m2 ON m1.machine_name = m2.machine_name AND m1.id < m2.id
        ORDER BY m1.machine_name
        """)
        
        duplicates = cursor.fetchall()
        
        if not duplicates:
            print("\nNo duplicate machines found by name.")
            return
            
        print(f"\nFound {len(duplicates)} potential duplicate pairs:")
        for dup in duplicates:
            print(f"Machine '{dup['machine_name']}' has IDs: {dup['id1']} and {dup['id2']}")
            
            # 4. Check which machine has templates
            cursor.execute("SELECT COUNT(*) FROM machine_templates WHERE machine_id=?", (dup['id1'],))
            templates1 = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM machine_templates WHERE machine_id=?", (dup['id2'],))
            templates2 = cursor.fetchone()[0]
            
            # List the actual templates
            print(f"\nTemplates for machine ID {dup['id1']}:")
            if templates1 > 0:
                cursor.execute("SELECT id, template_type FROM machine_templates WHERE machine_id=?", (dup['id1'],))
                for template in cursor.fetchall():
                    print(f"  - ID: {template['id']}, Type: {template['template_type']}")
            else:
                print("  None")
                
            print(f"\nTemplates for machine ID {dup['id2']}:")
            if templates2 > 0:
                cursor.execute("SELECT id, template_type FROM machine_templates WHERE machine_id=?", (dup['id2'],))
                for template in cursor.fetchall():
                    print(f"  - ID: {template['id']}, Type: {template['template_type']}")
            else:
                print("  None")
            
            # 5. Ask for confirmation to fix
            if templates1 == 0 and templates2 > 0:
                print(f"\nMachine ID {dup['id1']} has no templates but Machine ID {dup['id2']} has {templates2} templates.")
                print(f"RECOMMENDED ACTION: Move templates from machine ID {dup['id2']} to {dup['id1']} and delete ID {dup['id2']}")
                
                fix_choice = input("\nApply this fix? (y/n): ")
                if fix_choice.lower() == 'y':
                    # Move templates from id2 to id1
                    cursor.execute("UPDATE machine_templates SET machine_id=? WHERE machine_id=?", (dup['id1'], dup['id2']))
                    # Delete the duplicate machine
                    cursor.execute("DELETE FROM machines WHERE id=?", (dup['id2'],))
                    conn.commit()
                    print(f"Fixed! Moved templates from machine ID {dup['id2']} to {dup['id1']} and deleted machine ID {dup['id2']}")
            
            elif templates1 > 0 and templates2 == 0:
                print(f"\nMachine ID {dup['id2']} has no templates but Machine ID {dup['id1']} has {templates1} templates.")
                print(f"RECOMMENDED ACTION: Delete machine ID {dup['id2']} as it appears to be a duplicate without templates")
                
                fix_choice = input("\nApply this fix? (y/n): ")
                if fix_choice.lower() == 'y':
                    # Delete the duplicate machine
                    cursor.execute("DELETE FROM machines WHERE id=?", (dup['id2'],))
                    conn.commit()
                    print(f"Fixed! Deleted duplicate machine ID {dup['id2']}")
            
            elif templates1 > 0 and templates2 > 0:
                print("\nBoth machines have templates. This requires manual review.")
                print("Options:")
                print(f"1. Keep machine ID {dup['id1']} and move templates from {dup['id2']}")
                print(f"2. Keep machine ID {dup['id2']} and move templates from {dup['id1']}")
                print("3. Skip this pair")
                
                choice = input("\nChoose option (1/2/3): ")
                if choice == '1':
                    # Move templates from id2 to id1
                    cursor.execute("UPDATE machine_templates SET machine_id=? WHERE machine_id=?", (dup['id1'], dup['id2']))
                    # Delete the duplicate machine
                    cursor.execute("DELETE FROM machines WHERE id=?", (dup['id2'],))
                    conn.commit()
                    print(f"Fixed! Moved templates from machine ID {dup['id2']} to {dup['id1']} and deleted machine ID {dup['id2']}")
                elif choice == '2':
                    # Move templates from id1 to id2
                    cursor.execute("UPDATE machine_templates SET machine_id=? WHERE machine_id=?", (dup['id2'], dup['id1']))
                    # Delete the duplicate machine
                    cursor.execute("DELETE FROM machines WHERE id=?", (dup['id1'],))
                    conn.commit()
                    print(f"Fixed! Moved templates from machine ID {dup['id1']} to {dup['id2']} and deleted machine ID {dup['id1']}")
            
            else:
                print("\nNeither machine has templates. You can safely delete one of them.")
                print(f"RECOMMENDED ACTION: Delete machine ID {dup['id2']} (higher ID)")
                
                fix_choice = input("\nApply this fix? (y/n): ")
                if fix_choice.lower() == 'y':
                    # Delete the duplicate machine
                    cursor.execute("DELETE FROM machines WHERE id=?", (dup['id2'],))
                    conn.commit()
                    print(f"Fixed! Deleted duplicate machine ID {dup['id2']}")
        
        print("\nDatabase maintenance complete!")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

# Add non-interactive version to execute automatically for machine IDs 3 and 5
def auto_fix_machines_3_and_5():
    conn = None
    try:
        # Check if database file exists
        if not os.path.exists(DB_PATH):
            print(f"ERROR: Database file not found at {DB_PATH}")
            print(f"Please run 'python initialize_db.py' first to create the database.")
            return
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("\n==== AUTOMATIC MACHINE REPAIR UTILITY ====")
        print(f"Using database at: {os.path.abspath(DB_PATH)}")
        
        # First check if the tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='machines'")
        if not cursor.fetchone():
            print("ERROR: 'machines' table does not exist in the database.")
            print("The database schema may not be properly initialized.")
            return
            
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='machine_templates'")
        if not cursor.fetchone():
            print("ERROR: 'machine_templates' table does not exist in the database.")
            print("The database schema may not be properly initialized.")
            return
        
        # Get all machines to see if we have duplicates
        cursor.execute("SELECT id, machine_name, client_quote_ref FROM machines ORDER BY machine_name")
        all_machines = cursor.fetchall()
        
        if not all_machines:
            print("No machines found in the database.")
            return
            
        print(f"Found {len(all_machines)} total machines in database.")
        
        # Look for duplicate machine names
        machine_names = {}
        duplicates = []
        
        for machine in all_machines:
            name = machine['machine_name']
            if name in machine_names:
                duplicates.append((machine_names[name], machine['id'], name))
            else:
                machine_names[name] = machine['id']
        
        if not duplicates:
            print("No duplicate machine names found.")
            return
            
        print(f"Found {len(duplicates)} duplicate machine pairs:")
        for id1, id2, name in duplicates:
            print(f"Machine '{name}': IDs {id1} and {id2}")
            
        # Look specifically for IDs 3 and 5
        for id1, id2, name in duplicates:
            if (id1 == 3 and id2 == 5) or (id1 == 5 and id2 == 3):
                print(f"\nFound duplicate of interest: Machine '{name}' with IDs 3 and 5")
                
                # Fix this specific duplicate
                fix_specific_duplicate(3, 5, name)
                return
                
        print("\nNo duplicate with IDs 3 and 5 found.")
        
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

def fix_specific_duplicate(id1, id2, machine_name):
    """Fix a specific duplicate by moving templates from id2 to id1 and deleting id2"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check which machine has templates
        cursor.execute("SELECT COUNT(*) FROM machine_templates WHERE machine_id=?", (id1,))
        templates1 = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM machine_templates WHERE machine_id=?", (id2,))
        templates2 = cursor.fetchone()[0]
        
        print(f"Machine ID {id1} has {templates1} templates")
        print(f"Machine ID {id2} has {templates2} templates")
        
        # List the templates
        if templates1 > 0:
            cursor.execute("SELECT id, template_type FROM machine_templates WHERE machine_id=?", (id1,))
            print(f"\nTemplates for machine ID {id1}:")
            for template in cursor.fetchall():
                print(f"  - ID: {template[0]}, Type: {template[1]}")
                
        if templates2 > 0:
            cursor.execute("SELECT id, template_type FROM machine_templates WHERE machine_id=?", (id2,))
            print(f"\nTemplates for machine ID {id2}:")
            for template in cursor.fetchall():
                print(f"  - ID: {template[0]}, Type: {template[1]}")
        
        # Implement the fix logic
        if templates1 == 0 and templates2 > 0:
            # Move templates from id2 to id1
            cursor.execute("UPDATE machine_templates SET machine_id=? WHERE machine_id=?", (id1, id2))
            # Delete machine id2
            cursor.execute("DELETE FROM machines WHERE id=?", (id2,))
            conn.commit()
            print(f"\nFIX APPLIED: Moved {templates2} templates from machine ID {id2} to {id1} and deleted machine ID {id2}")
            print("Please restart the application to see the changes.")
        elif templates1 > 0 and templates2 == 0:
            # Delete machine id2
            cursor.execute("DELETE FROM machines WHERE id=?", (id2,))
            conn.commit()
            print(f"\nFIX APPLIED: Deleted duplicate machine ID {id2} (it had no templates)")
            print("Please restart the application to see the changes.")
        elif templates1 > 0 and templates2 > 0:
            print("\nBoth machines have templates. This requires manual review.")
            print(f"Please review the templates for machine IDs {id1} and {id2} before applying a fix.")
            # If you want to force a fix uncomment these lines:
            # cursor.execute("UPDATE machine_templates SET machine_id=? WHERE machine_id=?", (id1, id2))
            # cursor.execute("DELETE FROM machines WHERE id=?", (id2,))
            # conn.commit()
            # print(f"FIX APPLIED: Moved templates from machine ID {id2} to {id1} and deleted machine ID {id2}")
        else:
            # Neither has templates
            cursor.execute("DELETE FROM machines WHERE id=?", (id2,))
            conn.commit()
            print(f"\nFIX APPLIED: Deleted duplicate machine ID {id2} (neither had templates)")
            print("Please restart the application to see the changes.")
            
    except sqlite3.Error as e:
        print(f"Database error during fix: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"Error during fix: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Run the automatic fix for machines 3 and 5
    auto_fix_machines_3_and_5()
    
    # Uncomment the line below if you want to run the interactive version
    # fix_machines() 