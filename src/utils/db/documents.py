"""
Document content database operations - Store and retrieve full PDF text content.
"""

import sqlite3
from typing import Dict, Optional
from datetime import datetime

from .base import DB_PATH


def save_document_content(quote_ref: str, full_pdf_text: str, filename: str, db_path: str = DB_PATH) -> bool:
    """
    Saves the full text content of a PDF document for later retrieval.

    Args:
        quote_ref: The quote reference to link the document to
        full_pdf_text: The full extracted text from the PDF
        filename: Original filename of the PDF

    Returns:
        bool: True if successful, False otherwise
    """
    if not quote_ref or not full_pdf_text:
        print("Error: Missing quote reference or PDF text.")
        return False

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if entry already exists
        cursor.execute("SELECT id FROM document_content WHERE client_quote_ref = ?", (quote_ref,))
        existing = cursor.fetchone()

        upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if existing:
            # Update existing entry
            cursor.execute("""
            UPDATE document_content
            SET full_pdf_text = ?, pdf_filename = ?, upload_date = ?
            WHERE client_quote_ref = ?
            """, (full_pdf_text, filename, upload_date, quote_ref))
        else:
            # Insert new entry
            cursor.execute("""
            INSERT INTO document_content
            (client_quote_ref, full_pdf_text, pdf_filename, upload_date)
            VALUES (?, ?, ?, ?)
            """, (quote_ref, full_pdf_text, filename, upload_date))

        conn.commit()
        print(f"Saved document content for quote: {quote_ref}")
        return True
    except sqlite3.Error as e:
        print(f"Database error saving document content: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error saving document content: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

def load_document_content(quote_ref: str, db_path: str = DB_PATH) -> Optional[Dict]:
    """
    Loads the document content for a given quote reference.

    Args:
        quote_ref: The quote reference to load document content for

    Returns:
        Dictionary with full_pdf_text, pdf_filename, and upload_date if found, None otherwise
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
        SELECT full_pdf_text, pdf_filename, upload_date
        FROM document_content
        WHERE client_quote_ref = ?
        """, (quote_ref,))

        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"Database error loading document content for quote {quote_ref}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error loading document content for quote {quote_ref}: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if conn:
            conn.close()

# Function to delete document content when a client is deleted
def delete_document_content(quote_ref: str, db_path: str = DB_PATH) -> bool:
    """
    Deletes the document content for a given quote reference.
    Usually called when deleting a client record.

    Args:
        quote_ref: The quote reference to delete document content for

    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM document_content WHERE client_quote_ref = ?", (quote_ref,))
        conn.commit()

        print(f"Deleted document content for quote: {quote_ref}")
        return True
    except sqlite3.Error as e:
        print(f"Database error deleting document content: {e}")
        return False
    finally:
        if conn:
            conn.close()
