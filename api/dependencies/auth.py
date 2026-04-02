"""Authentication dependencies for FastAPI routes."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status

from api.services.auth_service import (
    COOKIE_NAME,
    get_sign_in_disabled_user,
    hash_session_token,
    is_session_expired,
    is_sign_in_disabled,
)
from src.utils.db import find_session_by_token_hash, revoke_session, touch_session


def is_admin_user(user: dict[str, Any] | None) -> bool:
    """Return True when payload represents an admin user."""
    if not isinstance(user, dict):
        return False
    return str(user.get("role") or "").strip().lower() == "admin"


async def get_current_user(request: Request) -> dict[str, Any] | None:
    """Extract session cookie, validate session, and return user payload or None."""
    if is_sign_in_disabled():
        user_row = get_sign_in_disabled_user()
        user_payload = {
            "id": int(user_row.get("id") or 0),
            "username": str(user_row.get("username") or ""),
            "display_name": str(user_row.get("display_name") or "").strip() or None,
            "role": str(user_row.get("role") or "admin").strip().lower() or "admin",
            "is_active": bool(int(user_row.get("is_active") or 0)),
            "gemini_api_key_encrypted": user_row.get("gemini_api_key_encrypted"),
        }
        request.state.current_user = user_payload
        request.state.current_session = None
        return user_payload

    raw_token = request.cookies.get(COOKIE_NAME)
    if not raw_token:
        request.state.current_user = None
        request.state.current_session = None
        return None

    token_hash = hash_session_token(raw_token)
    session_row = find_session_by_token_hash(token_hash)
    if not session_row:
        request.state.current_user = None
        request.state.current_session = None
        return None

    session_id = int(session_row.get("session_id") or 0)
    if is_session_expired(str(session_row.get("expires_at") or "")):
        if session_id > 0:
            revoke_session(session_id)
        request.state.current_user = None
        request.state.current_session = None
        return None

    is_active = bool(int(session_row.get("is_active") or 0))
    if not is_active:
        if session_id > 0:
            revoke_session(session_id)
        request.state.current_user = None
        request.state.current_session = None
        return None

    if session_id > 0:
        touch_session(session_id)

    user_payload = {
        "id": int(session_row.get("user_id") or 0),
        "username": str(session_row.get("username") or ""),
        "display_name": str(session_row.get("display_name") or "").strip() or None,
        "role": str(session_row.get("role") or "standard").strip().lower() or "standard",
        "is_active": is_active,
        "gemini_api_key_encrypted": session_row.get("gemini_api_key_encrypted"),
    }

    request.state.current_user = user_payload
    request.state.current_session = {
        "id": session_id,
        "user_id": int(session_row.get("session_user_id") or 0),
        "expires_at": str(session_row.get("expires_at") or ""),
        "token_hash": str(session_row.get("token_hash") or ""),
    }
    return user_payload


async def require_authenticated_user(
    user: dict[str, Any] | None = Depends(get_current_user),
) -> dict[str, Any]:
    """Raise 401 when no valid authenticated user session exists."""
    if user is None or int(user.get("id") or 0) <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user


async def require_admin_user(
    user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    """Raise 403 when authenticated user is not an admin."""
    if str(user.get("role") or "").strip().lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return user
