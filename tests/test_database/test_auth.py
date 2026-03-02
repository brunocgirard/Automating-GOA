"""Auth database layer tests."""

from __future__ import annotations

import hashlib

from src.utils.db import create_project, get_connection, save_client_info
from src.utils.db.auth import (
    backfill_ownership,
    create_session,
    create_user,
    find_session_by_token_hash,
    find_user_by_id,
    find_user_by_username,
    revoke_all_user_sessions,
    revoke_session,
    touch_session,
    update_user_gemini_key,
    update_user_password,
    get_user_gemini_key,
)


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_user_and_session_crud(temp_db_path) -> None:
    db_path = str(temp_db_path)

    user = create_user(
        username="tester",
        display_name="Test User",
        password_hash="hashed-password",
        role="standard",
        db_path=db_path,
    )
    assert user is not None
    user_id = int(user["id"])

    by_username = find_user_by_username("tester", db_path=db_path)
    assert by_username is not None
    assert int(by_username["id"]) == user_id

    assert update_user_password(user_id, "new-hash", db_path=db_path) is True

    session = create_session(
        user_id=user_id,
        token_hash=_token_hash("token-1"),
        expires_at="2099-01-01 00:00:00",
        ip_address="127.0.0.1",
        user_agent="pytest",
        db_path=db_path,
    )
    assert session is not None
    session_id = int(session["id"])

    looked_up = find_session_by_token_hash(_token_hash("token-1"), db_path=db_path)
    assert looked_up is not None
    assert int(looked_up["session_id"]) == session_id
    assert int(looked_up["user_id"]) == user_id

    assert touch_session(session_id, db_path=db_path) is True
    assert revoke_session(session_id, db_path=db_path) is True
    assert find_session_by_token_hash(_token_hash("token-1"), db_path=db_path) is None

    second_session = create_session(
        user_id=user_id,
        token_hash=_token_hash("token-2"),
        expires_at="2099-01-01 00:00:00",
        ip_address=None,
        user_agent=None,
        db_path=db_path,
    )
    assert second_session is not None
    assert revoke_all_user_sessions(user_id, db_path=db_path) >= 1


def test_ownership_backfill_and_gemini_key_storage(temp_db_path) -> None:
    db_path = str(temp_db_path)

    admin = create_user(
        username="admin_temp",
        display_name="Admin Temp",
        password_hash="hash",
        role="admin",
        db_path=db_path,
    )
    assert admin is not None
    admin_id = int(admin["id"])

    assert save_client_info({"quote_ref": "Q-100"}, db_path=db_path) is True
    project = create_project(
        {
            "project_name": "Project 100",
            "customer_name": "Customer 100",
            "quote_ref": "Q-100",
        },
        db_path=db_path,
    )
    assert project is not None

    assert backfill_ownership(admin_id, db_path=db_path) is True

    conn = get_connection(db_path)
    conn.row_factory = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT owner_user_id FROM clients WHERE quote_ref = ?", ("Q-100",))
        client_owner = cursor.fetchone()
        cursor.execute("SELECT owner_user_id FROM projects WHERE quote_ref = ?", ("Q-100",))
        project_owner = cursor.fetchone()
    finally:
        conn.close()

    assert client_owner is not None
    assert int(client_owner[0]) == admin_id
    assert project_owner is not None
    assert int(project_owner[0]) == admin_id

    assert update_user_gemini_key(admin_id, "encrypted-key", db_path=db_path) is True
    assert get_user_gemini_key(admin_id, db_path=db_path) == "encrypted-key"

    updated_admin = find_user_by_id(admin_id, db_path=db_path)
    assert updated_admin is not None
    assert str(updated_admin.get("gemini_api_key_encrypted")) == "encrypted-key"
