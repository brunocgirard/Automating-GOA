"""COR document persistence utilities."""

from __future__ import annotations

import sqlite3
from typing import Any

import json

from .base import DB_PATH, get_connection, row_to_dict, safe_json_loads, timestamp, to_text


def _decode_cor_data(payload: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    parsed = safe_json_loads(payload.get("cor_data_json"), {})
    return parsed if isinstance(parsed, dict) else {}


def _next_cor_no(cursor: sqlite3.Cursor, client_quote_ref: str) -> str:
    cursor.execute(
        """
        SELECT cor_no, cor_data_json
        FROM cor_documents
        WHERE client_quote_ref = ?
        """,
        (client_quote_ref,),
    )
    highest = 0
    for row in cursor.fetchall():
        value = to_text(row[0])
        if not value:
            parsed = safe_json_loads(row[1], {})
            if not isinstance(parsed, dict):
                parsed = {}
            value = to_text(parsed.get("corNo"))
        if value.isdigit():
            highest = max(highest, int(value))
    return str(highest + 1 if highest > 0 else 1)


def list_cor_documents(client_quote_ref: str, db_path: str = DB_PATH) -> list[dict[str, Any]]:
    """List saved COR states for a quote reference."""
    if not client_quote_ref:
        return []

    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, client_quote_ref, cor_no, description, cor_data_json, created_date, modified_date
            FROM cor_documents
            WHERE client_quote_ref = ?
            ORDER BY modified_date DESC, id DESC
            """,
            (client_quote_ref,),
        )
        rows = cursor.fetchall()
        revisions: list[dict[str, Any]] = []
        for row in rows:
            payload = row_to_dict(row) or {}
            cor_data = _decode_cor_data(payload)
            revisions.append(
                {
                    "id": payload.get("id"),
                    "client_quote_ref": payload.get("client_quote_ref", ""),
                    "cor_no": to_text(payload.get("cor_no")) or to_text(cor_data.get("corNo")),
                    "description": to_text(payload.get("description"))
                    or to_text(cor_data.get("revisionDescription")),
                    "created_date": payload.get("created_date"),
                    "modified_date": payload.get("modified_date"),
                }
            )
        return revisions
    except Exception as exc:
        print(f"Error listing COR documents for quote '{client_quote_ref}': {exc}")
        return []
    finally:
        if conn:
            conn.close()


def load_cor_document(
    client_quote_ref: str,
    cor_document_id: int | None = None,
    db_path: str = DB_PATH,
) -> dict[str, Any] | None:
    """Load saved COR state for a quote reference."""
    if not client_quote_ref:
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if cor_document_id is None:
            cursor.execute(
                """
                SELECT id, client_quote_ref, cor_no, description, cor_data_json, created_date, modified_date
                FROM cor_documents
                WHERE client_quote_ref = ?
                ORDER BY modified_date DESC, id DESC
                LIMIT 1
                """,
                (client_quote_ref,),
            )
        else:
            cursor.execute(
                """
                SELECT id, client_quote_ref, cor_no, description, cor_data_json, created_date, modified_date
                FROM cor_documents
                WHERE client_quote_ref = ? AND id = ?
                LIMIT 1
                """,
                (client_quote_ref, cor_document_id),
            )
        row = cursor.fetchone()
        if not row:
            return None

        payload = row_to_dict(row) or {}
        cor_data = _decode_cor_data(payload)
        cor_no = to_text(payload.get("cor_no")) or to_text(cor_data.get("corNo"))
        description = to_text(payload.get("description")) or to_text(cor_data.get("revisionDescription"))
        if cor_no:
            cor_data["corNo"] = cor_no
        if description:
            cor_data["revisionDescription"] = description

        return {
            "id": payload.get("id"),
            "client_quote_ref": payload.get("client_quote_ref", ""),
            "cor_no": cor_no,
            "description": description,
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
    cor_document_id: int | None = None,
    create_new: bool = False,
    cor_no: str | None = None,
    description: str | None = None,
    db_path: str = DB_PATH,
) -> dict[str, Any] | None:
    """Insert or update COR state for a quote reference.

    Returns the stored row.
    """
    if not client_quote_ref:
        print("Error: Missing quote reference for save_cor_document.")
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        now = timestamp()
        payload = dict(cor_data or {})
        resolved_cor_no = to_text(cor_no) or to_text(payload.get("corNo"))
        if description is not None:
            resolved_description = to_text(description)
            description_provided = True
        elif "revisionDescription" in payload:
            resolved_description = to_text(payload.get("revisionDescription"))
            description_provided = True
        else:
            resolved_description = ""
            description_provided = False

        existing = None
        if not create_new:
            if cor_document_id is not None:
                cursor.execute(
                    """
                    SELECT id, cor_no, description
                    FROM cor_documents
                    WHERE client_quote_ref = ? AND id = ?
                    LIMIT 1
                    """,
                    (client_quote_ref, cor_document_id),
                )
                existing = cursor.fetchone()
            else:
                cursor.execute(
                    """
                    SELECT id, cor_no, description
                    FROM cor_documents
                    WHERE client_quote_ref = ?
                    ORDER BY modified_date DESC, id DESC
                    LIMIT 1
                    """,
                    (client_quote_ref,),
                )
                existing = cursor.fetchone()

        if existing:
            existing_id = int(existing[0])
            effective_cor_no = resolved_cor_no or to_text(existing[1]) or _next_cor_no(cursor, client_quote_ref)
            effective_description = (
                resolved_description if description_provided else to_text(existing[2])
            )
            payload["corNo"] = effective_cor_no
            payload["revisionDescription"] = effective_description
            serialized = json.dumps(payload)
            cursor.execute(
                """
                UPDATE cor_documents
                SET cor_no = ?, description = ?, cor_data_json = ?, modified_date = ?
                WHERE id = ?
                """,
                (effective_cor_no, effective_description, serialized, now, existing_id),
            )
            stored_id = existing_id
        else:
            effective_cor_no = resolved_cor_no or _next_cor_no(cursor, client_quote_ref)
            effective_description = resolved_description
            payload["corNo"] = effective_cor_no
            payload["revisionDescription"] = effective_description
            serialized = json.dumps(payload)
            cursor.execute(
                """
                INSERT INTO cor_documents (
                    client_quote_ref,
                    cor_no,
                    description,
                    cor_data_json,
                    created_date,
                    modified_date
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (client_quote_ref, effective_cor_no, effective_description, serialized, now, now),
            )
            stored_id = int(cursor.lastrowid)

        conn.commit()
    except Exception as exc:
        print(f"Error saving COR document for quote '{client_quote_ref}': {exc}")
        return None
    finally:
        if conn:
            conn.close()

    return load_cor_document(client_quote_ref, cor_document_id=stored_id, db_path=db_path)
