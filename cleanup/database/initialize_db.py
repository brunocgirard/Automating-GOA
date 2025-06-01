#!/usr/bin/env python
"""
Script to initialize the database with the goa_modifications table.
Run this to ensure the database schema is up-to-date.
"""

from src.utils.crm_utils import init_db, DB_PATH
import os

if __name__ == "__main__":
    print(f"Initializing database at {os.path.abspath(DB_PATH)}...")
    init_db()
    print("Database initialization complete. The goa_modifications table is now available.")
    print("\nYou can now track modifications made to GOA templates after kickoff meetings.")
    print("Use the 'Template Modifications' tab in the Quote Processing workflow to:")
    print("  - View existing modifications")
    print("  - Add new modifications with reasons")
    print("  - Regenerate documents with applied modifications") 