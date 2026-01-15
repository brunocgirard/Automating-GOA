"""
Database base module - contains DB path constants and initialization.
This module provides the foundation for all database operations.
"""

import sqlite3
import os
from typing import Optional
from datetime import datetime

# Define database connection path
DB_PATH = os.path.join("data", "crm_data.db")

# Define base template paths
HTML_TEMPLATE_PATH = os.path.join("templates", "goa_form.html")
DOCX_TEMPLATE_PATH = os.path.join("templates", "template.docx")
# Legacy constant kept for compatibility
TEMPLATE_FILE_PATH = os.path.join("templates", "template.docx")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """
    Creates and returns a database connection.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        sqlite3.Connection: Database connection object
    """
    conn = sqlite3.connect(db_path)
    return conn


def init_db(db_path: str = DB_PATH):
    """
    Initializes the SQLite database. Creates all required tables if they don't exist.

    Tables created:
    - clients: Customer information
    - priced_items: Line items from PDF quotes
    - machines: Identified machines within quotes
    - machine_templates: GOA outputs for specific machines
    - few_shot_examples: High-quality examples for LLM learning
    - few_shot_feedback: User corrections and improvements
    - document_content: Full PDF text for chat functionality
    - goa_modifications: Changes made to GOA templates
    """
    conn = None
    try:
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_ref TEXT UNIQUE NOT NULL,
            customer_name TEXT,
            machine_model TEXT,
            sold_to_address TEXT,
            ship_to_address TEXT,
            telephone TEXT,
            customer_contact_person TEXT,
            customer_po TEXT,
            processing_date TEXT NOT NULL,
            incoterm TEXT,
            company TEXT,
            serial_number TEXT,
            ax TEXT,
            ox TEXT,
            via TEXT,
            tax_id TEXT,
            hs_code TEXT,
            customer_number TEXT,
            order_date TEXT
        )
        """)

        # Schema migration for existing databases
        cursor.execute("PRAGMA table_info(clients)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        new_columns = {
            "company": "TEXT", "serial_number": "TEXT", "ax": "TEXT",
            "ox": "TEXT", "via": "TEXT", "tax_id": "TEXT", "hs_code": "TEXT",
            "customer_number": "TEXT", "order_date": "TEXT"
        }

        for col_name, col_type in new_columns.items():
            if col_name not in existing_columns:
                cursor.execute(f"ALTER TABLE clients ADD COLUMN {col_name} {col_type}")
                print(f"Added column '{col_name}' to 'clients' table.")

        # Create priced_items table with item_quantity
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS priced_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_quote_ref TEXT NOT NULL,
            item_description TEXT,
            item_quantity TEXT,       -- Store as TEXT to handle various formats
            item_price_str TEXT,
            item_price_numeric REAL,
            FOREIGN KEY (client_quote_ref) REFERENCES clients (quote_ref) ON DELETE CASCADE
        )
        """)

        # Create machines table to store identified machines within a quote
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS machines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_quote_ref TEXT NOT NULL,
            machine_name TEXT NOT NULL,
            machine_data_json TEXT NOT NULL,
            processing_date TEXT NOT NULL,
            FOREIGN KEY (client_quote_ref) REFERENCES clients (quote_ref) ON DELETE CASCADE
        )
        """)

        # Create machine_templates table to store GOA outputs for specific machines
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS machine_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id INTEGER NOT NULL,
            template_type TEXT NOT NULL,
            template_data_json TEXT NOT NULL,
            generated_file_path TEXT,
            processing_date TEXT NOT NULL,
            FOREIGN KEY (machine_id) REFERENCES machines (id) ON DELETE CASCADE
        )
        """)

        # Create few_shot_examples table to store high-quality examples for LLM learning
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS few_shot_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_type TEXT NOT NULL,
            template_type TEXT NOT NULL,
            field_name TEXT NOT NULL,
            input_context TEXT NOT NULL,
            expected_output TEXT NOT NULL,
            confidence_score REAL DEFAULT 1.0,
            usage_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            created_date TEXT NOT NULL,
            last_used_date TEXT,
            source_machine_id INTEGER,
            FOREIGN KEY (source_machine_id) REFERENCES machines (id) ON DELETE SET NULL
        )
        """)

        # Create few_shot_feedback table to track user corrections and improvements
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS few_shot_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            example_id INTEGER NOT NULL,
            feedback_type TEXT NOT NULL,
            original_prediction TEXT,
            corrected_value TEXT,
            feedback_date TEXT NOT NULL,
            user_context TEXT,
            FOREIGN KEY (example_id) REFERENCES few_shot_examples (id) ON DELETE CASCADE
        )
        """)

        # Create document_content table to store PDF text for later chat functionality
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_quote_ref TEXT UNIQUE NOT NULL,
            full_pdf_text TEXT,
            pdf_filename TEXT,
            upload_date TEXT NOT NULL,
            FOREIGN KEY (client_quote_ref) REFERENCES clients (quote_ref) ON DELETE CASCADE
        )
        """)

        # Create goa_modifications table to track changes made to GOA templates
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS goa_modifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_template_id INTEGER NOT NULL,
            field_key TEXT NOT NULL,
            original_value TEXT,
            modified_value TEXT NOT NULL,
            modification_reason TEXT,
            modified_by TEXT,
            modification_date TEXT NOT NULL,
            FOREIGN KEY (machine_template_id) REFERENCES machine_templates (id) ON DELETE CASCADE
        )
        """)

        print(f"Database '{db_path}' initialized with all required tables.")
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during DB init: {e}")
    finally:
        if conn:
            conn.close()
