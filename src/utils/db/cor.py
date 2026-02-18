"""COR document persistence utilities."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from .base import DB_PATH, get_connection


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_cor_document(client_quote_ref: str, db_path: str = DB_PATH) -> dict[str, Any] | None:
    """Load the latest saved COR state for a quote reference."""
    if not client_quote_ref:
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, client_quote_ref, cor_data_json, created_date, modified_date
            FROM cor_documents
            WHERE client_quote_ref = ?
            ORDER BY modified_date DESC, id DESC
            LIMIT 1
            """,
            (client_quote_ref,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        payload = dict(row)
        try:
            cor_data = json.loads(payload.get("cor_data_json") or "{}")
        except json.JSONDecodeError:
            cor_data = {}

        return {
            "id": payload.get("id"),
            "client_quote_ref": payload.get("client_quote_ref", ""),
            "cor_data": cor_data,
            "created_date": payload.get("created_date"),
            "modified_date": payload.get("modified_date"),
        }
    except Exception as exc:
        print(f"Error loading COR document for quote '{client_quote_ref}': {exc}")
        return None
    finally:
        if conn:
            conn.close()


def save_cor_document(
    client_quote_ref: str,
    cor_data: dict[str, Any],
    db_path: str = DB_PATH,
) -> dict[str, Any] | None:
    """Insert or update COR state for a quote reference."""
    if not client_quote_ref:
        print("Error: Missing quote reference for save_cor_document.")
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        now = _timestamp()
        serialized = json.dumps(cor_data or {})

        cursor.execute(
            """
            SELECT id
            FROM cor_documents
            WHERE client_quote_ref = ?
            ORDER BY modified_date DESC, id DESC
            LIMIT 1
            """,
            (client_quote_ref,),
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                """
                UPDATE cor_documents
                SET cor_data_json = ?, modified_date = ?
                WHERE id = ?
                """,
                (serialized, now, existing[0]),
            )
        else:
            cursor.execute(
                """
                INSERT INTO cor_documents (
                    client_quote_ref,
                    cor_data_json,
                    created_date,
                    modified_date
                ) VALUES (?, ?, ?, ?)
                """,
                (client_quote_ref, serialized, now, now),
            )

        conn.commit()
    except Exception as exc:
        print(f"Error saving COR document for quote '{client_quote_ref}': {exc}")
        return None
    finally:
        if conn:
            conn.close()

    return load_cor_document(client_quote_ref, db_path)
