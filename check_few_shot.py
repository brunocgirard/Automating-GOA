
import sqlite3
import os

DB_PATH = os.path.join("data", "crm_data.db")

def check_few_shot_table():
    if not os.path.exists(DB_PATH):
        print(f"Database file not found at: {DB_PATH}")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check if the table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='few_shot_examples'")
        if cursor.fetchone() is None:
            print("The 'few_shot_examples' table does not exist in the database.")
            return

        # Get the number of rows
        cursor.execute("SELECT COUNT(*) FROM few_shot_examples")
        count = cursor.fetchone()[0]
        print(f"The 'few_shot_examples' table contains {count} rows.")

        # Get a few sample rows
        if count > 0:
            print("\nSample rows:")
            cursor.execute("SELECT * FROM few_shot_examples LIMIT 5")
            rows = cursor.fetchall()
            # get column names
            column_names = [description[0] for description in cursor.description]
            print(column_names)
            for row in rows:
                print(row)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_few_shot_table()
