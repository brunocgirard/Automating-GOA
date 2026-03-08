"""Authentication database operations."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from .base import DB_PATH, get_connection


_ALLOWED_ROLES = {"admin", "standard"}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _as_row_dict(row: sqlite3.Row | tuple[Any, ...] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return None


def count_users(db_path: str = DB_PATH) -> int:
    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        row = cursor.fetchone()
        return int(row[0]) if row else 0
    except Exception as exc:
        print(f"Error counting users: {exc}")
        return 0
    finally:
        if conn:
            conn.close()


def create_user(
    username: str,
    display_name: str | None,
    password_hash: str,
    role: str = "standard",
    db_path: str = DB_PATH,
) -> dict[str, Any] | None:
    normalized_username = str(username or "").strip()
    normalized_role = str(role or "standard").strip().lower()
    if normalized_role not in _ALLOWED_ROLES:
        normalized_role = "standard"
    if not normalized_username or not password_hash:
        return None

    now = _now()
    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (
                username,
                display_name,
                password_hash,
                role,
                is_active,
                created_date,
                modified_date
            ) VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                normalized_username,
                str(display_name or "").strip() or None,
                password_hash,
                normalized_role,
                now,
                now,
            ),
        )
        user_id = int(cursor.lastrowid)
        conn.commit()
        return find_user_by_id(user_id, db_path=db_path)
    except sqlite3.IntegrityError:
        return None
    except Exception as exc:
        print(f"Error creating user '{normalized_username}': {exc}")
        return None
    finally:
        if conn:
            conn.close()


def find_user_by_username(username: str, db_path: str = DB_PATH) -> dict[str, Any] | None:
    normalized_username = str(username or "").strip()
    if not normalized_username:
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? LIMIT 1", (normalized_username,))
        return _as_row_dict(cursor.fetchone())
    except Exception as exc:
        print(f"Error finding user by username '{normalized_username}': {exc}")
        return None
    finally:
        if conn:
            conn.close()


def find_user_by_id(user_id: int, db_path: str = DB_PATH) -> dict[str, Any] | None:
    if not isinstance(user_id, int) or user_id <= 0:
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ? LIMIT 1", (user_id,))
        return _as_row_dict(cursor.fetchone())
    except Exception as exc:
        print(f"Error finding user by id '{user_id}': {exc}")
        return None
    finally:
        if conn:
            conn.close()


def list_users(db_path: str = DB_PATH) -> list[dict[str, Any]]:
    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM users
            ORDER BY role DESC, username ASC
            """
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as exc:
        print(f"Error listing users: {exc}")
        return []
    finally:
        if conn:
            conn.close()


def update_user_password(user_id: int, new_password_hash: str, db_path: str = DB_PATH) -> bool:
    if not isinstance(user_id, int) or user_id <= 0 or not new_password_hash:
        return False

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET password_hash = ?, modified_date = ?
            WHERE id = ?
            """,
            (new_password_hash, _now(), user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        print(f"Error updating password for user_id '{user_id}': {exc}")
        return False
    finally:
        if conn:
            conn.close()


def update_user_last_login(user_id: int, db_path: str = DB_PATH) -> bool:
    if not isinstance(user_id, int) or user_id <= 0:
        return False

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        now = _now()
        cursor.execute(
            """
            UPDATE users
            SET last_login_at = ?, modified_date = ?
            WHERE id = ?
            """,
            (now, now, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        print(f"Error updating last_login_at for user_id '{user_id}': {exc}")
        return False
    finally:
        if conn:
            conn.close()


def deactivate_user(user_id: int, db_path: str = DB_PATH) -> bool:
    if not isinstance(user_id, int) or user_id <= 0:
        return False

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET is_active = 0, modified_date = ?
            WHERE id = ?
            """,
            (_now(), user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        print(f"Error deactivating user_id '{user_id}': {exc}")
        return False
    finally:
        if conn:
            conn.close()


def create_session(
    user_id: int,
    token_hash: str,
    expires_at: str,
    ip_address: str | None,
    user_agent: str | None,
    db_path: str = DB_PATH,
) -> dict[str, Any] | None:
    if not isinstance(user_id, int) or user_id <= 0 or not token_hash or not expires_at:
        return None

    now = _now()
    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sessions (
                user_id,
                token_hash,
                created_at,
                expires_at,
                last_seen_at,
                ip_address,
                user_agent
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                token_hash,
                now,
                expires_at,
                now,
                str(ip_address or "").strip() or None,
                str(user_agent or "").strip() or None,
            ),
        )
        session_id = int(cursor.lastrowid)
        conn.commit()
        cursor.execute("SELECT * FROM sessions WHERE id = ? LIMIT 1", (session_id,))
        return _as_row_dict(cursor.fetchone())
    except Exception as exc:
        print(f"Error creating session for user_id '{user_id}': {exc}")
        return None
    finally:
        if conn:
            conn.close()


def find_session_by_token_hash(token_hash: str, db_path: str = DB_PATH) -> dict[str, Any] | None:
    normalized_token_hash = str(token_hash or "").strip()
    if not normalized_token_hash:
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                s.id AS session_id,
                s.user_id AS session_user_id,
                s.token_hash,
                s.created_at,
                s.expires_at,
                s.last_seen_at,
                s.revoked_at,
                s.ip_address AS session_ip_address,
                s.user_agent AS session_user_agent,
                u.id AS user_id,
                u.username,
                u.display_name,
                u.password_hash,
                u.role,
                u.is_active,
                u.gemini_api_key_encrypted,
                u.created_date AS user_created_date,
                u.modified_date AS user_modified_date,
                u.last_login_at
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ?
              AND s.revoked_at IS NULL
            LIMIT 1
            """,
            (normalized_token_hash,),
        )
        return _as_row_dict(cursor.fetchone())
    except Exception as exc:
        print("Error finding session by token hash.")
        print(exc)
        return None
    finally:
        if conn:
            conn.close()


def revoke_session(session_id: int, db_path: str = DB_PATH) -> bool:
    if not isinstance(session_id, int) or session_id <= 0:
        return False

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE sessions
            SET revoked_at = ?
            WHERE id = ?
              AND revoked_at IS NULL
            """,
            (_now(), session_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        print(f"Error revoking session_id '{session_id}': {exc}")
        return False
    finally:
        if conn:
            conn.close()


def revoke_all_user_sessions(user_id: int, db_path: str = DB_PATH) -> int:
    if not isinstance(user_id, int) or user_id <= 0:
        return 0

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE sessions
            SET revoked_at = ?
            WHERE user_id = ?
              AND revoked_at IS NULL
            """,
            (_now(), user_id),
        )
        conn.commit()
        return int(cursor.rowcount)
    except Exception as exc:
        print(f"Error revoking all sessions for user_id '{user_id}': {exc}")
        return 0
    finally:
        if conn:
            conn.close()


def touch_session(session_id: int, db_path: str = DB_PATH) -> bool:
    if not isinstance(session_id, int) or session_id <= 0:
        return False

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE sessions
            SET last_seen_at = ?
            WHERE id = ?
              AND revoked_at IS NULL
            """,
            (_now(), session_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        print(f"Error touching session_id '{session_id}': {exc}")
        return False
    finally:
        if conn:
            conn.close()


def write_audit_event(
    user_id: int | None,
    event_type: str,
    metadata: dict[str, Any] | None,
    ip_address: str | None,
    user_agent: str | None,
    db_path: str = DB_PATH,
) -> bool:
    normalized_event_type = str(event_type or "").strip().lower()
    if not normalized_event_type:
        return False

    metadata_json = None
    if metadata is not None:
        try:
            metadata_json = json.dumps(metadata)
        except Exception:
            metadata_json = json.dumps({"raw": str(metadata)})

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO auth_audit_events (
                user_id,
                event_type,
                metadata_json,
                ip_address,
                user_agent,
                occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id if isinstance(user_id, int) and user_id > 0 else None,
                normalized_event_type,
                metadata_json,
                str(ip_address or "").strip() or None,
                str(user_agent or "").strip() or None,
                _now(),
            ),
        )
        conn.commit()
        return True
    except Exception as exc:
        print(f"Error writing auth audit event '{normalized_event_type}': {exc}")
        return False
    finally:
        if conn:
            conn.close()


def backfill_ownership(admin_user_id: int, db_path: str = DB_PATH) -> bool:
    if not isinstance(admin_user_id, int) or admin_user_id <= 0:
        return False

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE clients
            SET owner_user_id = ?
            WHERE owner_user_id IS NULL
            """,
            (admin_user_id,),
        )
        cursor.execute(
            """
            UPDATE projects
            SET owner_user_id = ?
            WHERE owner_user_id IS NULL
            """,
            (admin_user_id,),
        )
        conn.commit()
        return True
    except Exception as exc:
        print(f"Error backfilling ownership for admin_user_id '{admin_user_id}': {exc}")
        return False
    finally:
        if conn:
            conn.close()


def update_user_gemini_key(
    user_id: int,
    encrypted_key: str | None,
    db_path: str = DB_PATH,
) -> bool:
    if not isinstance(user_id, int) or user_id <= 0:
        return False

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET gemini_api_key_encrypted = ?, modified_date = ?
            WHERE id = ?
            """,
            (str(encrypted_key or "").strip() or None, _now(), user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        print(f"Error updating Gemini key for user_id '{user_id}': {exc}")
        return False
    finally:
        if conn:
            conn.close()


def get_user_gemini_key(user_id: int, db_path: str = DB_PATH) -> str | None:
    if not isinstance(user_id, int) or user_id <= 0:
        return None

    conn = None
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT gemini_api_key_encrypted
            FROM users
            WHERE id = ?
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        raw_value = row[0]
        if raw_value is None:
            return None
        return str(raw_value).strip() or None
    except Exception as exc:
        print(f"Error loading Gemini key for user_id '{user_id}': {exc}")
        return None
    finally:
        if conn:
            conn.close()
