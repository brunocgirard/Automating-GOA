"""Personal task board persistence utilities."""

from __future__ import annotations

import sqlite3
from typing import Any

from .base import DB_PATH, get_connection, row_to_dict, rows_to_dicts, timestamp

USER_TASK_PRIORITIES: tuple[str, ...] = ("low", "normal", "high", "urgent")
USER_TASK_STATUSES: tuple[str, ...] = ("pending", "done")


def _normalize_priority(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in USER_TASK_PRIORITIES:
        return normalized
    return "normal"


def _normalize_status(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in USER_TASK_STATUSES:
        return normalized
    return "pending"


def _normalize_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _load_user_task(
    cursor: sqlite3.Cursor,
    task_id: int,
    owner_user_id: int,
) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT
            id,
            owner_user_id,
            title,
            description,
            client_tag,
            priority,
            status,
            due_date,
            completed_at,
            created_at,
            modified_at
        FROM user_tasks
        WHERE id = ?
          AND owner_user_id = ?
        LIMIT 1
        """,
        (task_id, owner_user_id),
    )
    return row_to_dict(cursor.fetchone())


def create_user_task(
    owner_user_id: int,
    title: str,
    description: str | None = None,
    client_tag: str | None = None,
    priority: str | None = "normal",
    due_date: str | None = None,
    db_path: str = DB_PATH,
) -> dict[str, Any] | None:
    """Create a personal task row."""
    if not isinstance(owner_user_id, int) or owner_user_id <= 0:
        return None

    normalized_title = str(title or "").strip()
    if not normalized_title:
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = timestamp()
        cursor.execute(
            """
            INSERT INTO user_tasks (
                owner_user_id,
                title,
                description,
                client_tag,
                priority,
                status,
                due_date,
                completed_at,
                created_at,
                modified_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL, ?, ?)
            """,
            (
                owner_user_id,
                normalized_title,
                _normalize_text(description),
                _normalize_text(client_tag),
                _normalize_priority(priority),
                _normalize_text(due_date),
                now,
                now,
            ),
        )
        task_id = int(cursor.lastrowid)
        conn.commit()
        return _load_user_task(cursor, task_id, owner_user_id)
    except Exception as exc:
        print(f"Error creating user task: {exc}")
        return None
    finally:
        if conn:
            conn.close()


def list_user_tasks(
    owner_user_id: int,
    status_filter: str | None = None,
    client_tag_filter: str | None = None,
    db_path: str = DB_PATH,
) -> list[dict[str, Any]]:
    """List personal tasks for a user with optional filters."""
    if not isinstance(owner_user_id, int) or owner_user_id <= 0:
        return []

    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = """
            SELECT
                id,
                owner_user_id,
                title,
                description,
                client_tag,
                priority,
                status,
                due_date,
                completed_at,
                created_at,
                modified_at
            FROM user_tasks
            WHERE owner_user_id = ?
        """
        params: list[Any] = [owner_user_id]

        normalized_status = str(status_filter or "").strip().lower()
        if normalized_status in USER_TASK_STATUSES:
            query += " AND status = ?"
            params.append(normalized_status)

        normalized_client_tag = _normalize_text(client_tag_filter)
        if normalized_client_tag:
            query += " AND LOWER(client_tag) = LOWER(?)"
            params.append(normalized_client_tag)

        query += """
            ORDER BY
                CASE WHEN status = 'pending' THEN 0 ELSE 1 END ASC,
                CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END ASC,
                due_date ASC,
                created_at DESC,
                id DESC
        """
        cursor.execute(query, tuple(params))
        return rows_to_dicts(cursor.fetchall())
    except Exception as exc:
        print(f"Error listing user tasks: {exc}")
        return []
    finally:
        if conn:
            conn.close()


def update_user_task(
    task_id: int,
    owner_user_id: int,
    db_path: str = DB_PATH,
    **fields: Any,
) -> dict[str, Any] | None:
    """Update editable task fields for the owner."""
    if not isinstance(task_id, int) or task_id <= 0:
        return None
    if not isinstance(owner_user_id, int) or owner_user_id <= 0:
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        existing = _load_user_task(cursor, task_id, owner_user_id)
        if not existing:
            return None

        updates: list[str] = []
        params: list[Any] = []

        if "title" in fields:
            normalized_title = str(fields.get("title") or "").strip()
            if not normalized_title:
                return None
            updates.append("title = ?")
            params.append(normalized_title)

        if "description" in fields:
            updates.append("description = ?")
            params.append(_normalize_text(fields.get("description")))

        if "client_tag" in fields:
            updates.append("client_tag = ?")
            params.append(_normalize_text(fields.get("client_tag")))

        if "priority" in fields:
            updates.append("priority = ?")
            params.append(_normalize_priority(str(fields.get("priority") or "")))

        if "due_date" in fields:
            updates.append("due_date = ?")
            params.append(_normalize_text(fields.get("due_date")))

        if "status" in fields:
            normalized_status = _normalize_status(str(fields.get("status") or ""))
            updates.append("status = ?")
            params.append(normalized_status)
            if normalized_status == "done":
                updates.append("completed_at = ?")
                params.append(timestamp())
            else:
                updates.append("completed_at = NULL")

        if not updates:
            return existing

        updates.append("modified_at = ?")
        params.append(timestamp())
        params.extend([task_id, owner_user_id])
        cursor.execute(
            f"""
            UPDATE user_tasks
            SET {", ".join(updates)}
            WHERE id = ?
              AND owner_user_id = ?
            """,
            tuple(params),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        return _load_user_task(cursor, task_id, owner_user_id)
    except Exception as exc:
        print(f"Error updating user task {task_id}: {exc}")
        return None
    finally:
        if conn:
            conn.close()


def toggle_user_task(
    task_id: int,
    owner_user_id: int,
    db_path: str = DB_PATH,
) -> dict[str, Any] | None:
    """Toggle task status between pending and done."""
    if not isinstance(task_id, int) or task_id <= 0:
        return None
    if not isinstance(owner_user_id, int) or owner_user_id <= 0:
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        existing = _load_user_task(cursor, task_id, owner_user_id)
        if not existing:
            return None

        current_status = _normalize_status(existing.get("status"))
        next_status = "pending" if current_status == "done" else "done"
        now = timestamp()

        if next_status == "done":
            cursor.execute(
                """
                UPDATE user_tasks
                SET status = 'done',
                    completed_at = ?,
                    modified_at = ?
                WHERE id = ?
                  AND owner_user_id = ?
                """,
                (now, now, task_id, owner_user_id),
            )
        else:
            cursor.execute(
                """
                UPDATE user_tasks
                SET status = 'pending',
                    completed_at = NULL,
                    modified_at = ?
                WHERE id = ?
                  AND owner_user_id = ?
                """,
                (now, task_id, owner_user_id),
            )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        return _load_user_task(cursor, task_id, owner_user_id)
    except Exception as exc:
        print(f"Error toggling user task {task_id}: {exc}")
        return None
    finally:
        if conn:
            conn.close()


def delete_user_task(
    task_id: int,
    owner_user_id: int,
    db_path: str = DB_PATH,
) -> bool:
    """Delete a task owned by the requesting user."""
    if not isinstance(task_id, int) or task_id <= 0:
        return False
    if not isinstance(owner_user_id, int) or owner_user_id <= 0:
        return False

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM user_tasks
            WHERE id = ?
              AND owner_user_id = ?
            """,
            (task_id, owner_user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        print(f"Error deleting user task {task_id}: {exc}")
        return False
    finally:
        if conn:
            conn.close()


def list_client_tags(
    owner_user_id: int,
    db_path: str = DB_PATH,
) -> list[str]:
    """Return distinct client tags from the user's personal task board."""
    if not isinstance(owner_user_id, int) or owner_user_id <= 0:
        return []

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT TRIM(client_tag)
            FROM user_tasks
            WHERE owner_user_id = ?
              AND client_tag IS NOT NULL
              AND TRIM(client_tag) <> ''
            ORDER BY LOWER(TRIM(client_tag)) ASC
            """,
            (owner_user_id,),
        )
        return [str(row[0]).strip() for row in cursor.fetchall() if row and str(row[0]).strip()]
    except Exception as exc:
        print(f"Error listing client tags for user {owner_user_id}: {exc}")
        return []
    finally:
        if conn:
            conn.close()
