"""Authentication API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from api.dependencies.auth import require_admin_user, require_authenticated_user
from api.models.schemas import (
    CreateUserRequest,
    GeminiKeyTestResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SetGeminiKeyRequest,
    UserResponse,
)
from api.routers._helpers import user_id
from api.services.auth_service import (
    COOKIE_NAME,
    GeminiKeyError,
    bootstrap_admin_user,
    decrypt_gemini_key,
    encrypt_gemini_key,
    generate_session_token,
    get_session_expiry_str,
    hash_password,
    hash_session_token,
    session_cookie_options,
    test_gemini_api_key,
    user_to_response_payload,
    verify_password,
)
from src.llm.client import invalidate_user_client_cache
from src.utils.db import (
    create_session,
    create_user,
    find_session_by_token_hash,
    find_user_by_id,
    find_user_by_username,
    get_user_gemini_key,
    list_users,
    revoke_all_user_sessions,
    revoke_session,
    update_user_gemini_key,
    update_user_last_login,
    update_user_password,
    write_audit_event,
)

router = APIRouter()


def _request_ip_and_agent(request: Request) -> tuple[str | None, str | None]:
    forwarded_for = str(request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        ip_address = forwarded_for.split(",", 1)[0].strip() or None
    else:
        ip_address = request.client.host if request.client else None
    user_agent = str(request.headers.get("user-agent") or "").strip() or None
    return ip_address, user_agent


def _session_id_from_request(request: Request, fallback_cookie_value: str | None = None) -> int | None:
    token = fallback_cookie_value or request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    token_hash = hash_session_token(token)
    session_row = find_session_by_token_hash(token_hash)
    if not session_row:
        return None
    session_id = int(session_row.get("session_id") or 0)
    return session_id if session_id > 0 else None


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        bootstrap_admin_user()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication bootstrap failed: {exc}",
        ) from exc

    username = str(payload.username or "").strip()
    password = str(payload.password or "")
    ip_address, user_agent = _request_ip_and_agent(request)

    user_row = find_user_by_username(username)
    valid_credentials = (
        user_row is not None
        and bool(int(user_row.get("is_active") or 0))
        and verify_password(password, str(user_row.get("password_hash") or ""))
    )

    if not valid_credentials:
        write_audit_event(
            int(user_row["id"]) if user_row and user_row.get("id") else None,
            "login_failed",
            {"username": username},
            ip_address,
            user_agent,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    user_id = int(user_row["id"])
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)
    expires_at = get_session_expiry_str()

    session_row = create_session(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    if not session_row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create login session.",
        )

    update_user_last_login(user_id)
    write_audit_event(user_id, "login", None, ip_address, user_agent)

    cookie_kwargs = session_cookie_options()
    cookie_key = str(cookie_kwargs.pop("key"))
    response.set_cookie(cookie_key, raw_token, **cookie_kwargs)

    refreshed = find_user_by_id(user_id)
    if not refreshed:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load authenticated user.",
        )
    return user_to_response_payload(refreshed)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, response: Response) -> dict[str, Any]:
    username = str(payload.username or "").strip()
    display_name = str(payload.display_name or "").strip() or username
    password = str(payload.password or "")

    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is required.")
    if len(password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters.")
    if find_user_by_username(username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists.")

    created = create_user(
        username=username,
        display_name=display_name,
        password_hash=hash_password(password),
        role="standard",
    )
    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create account.",
        )

    user_id = int(created["id"])
    ip_address, user_agent = _request_ip_and_agent(request)
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)
    expires_at = get_session_expiry_str()

    session_row = create_session(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    if not session_row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create login session.",
        )

    update_user_last_login(user_id)
    write_audit_event(user_id, "register", None, ip_address, user_agent)
    write_audit_event(user_id, "login", {"source": "register"}, ip_address, user_agent)

    cookie_kwargs = session_cookie_options()
    cookie_key = str(cookie_kwargs.pop("key"))
    response.set_cookie(cookie_key, raw_token, **cookie_kwargs)

    refreshed = find_user_by_id(user_id)
    if not refreshed:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load authenticated user.",
        )
    return user_to_response_payload(refreshed)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, bool]:
    ip_address, user_agent = _request_ip_and_agent(request)

    session_id = None
    current_session = getattr(request.state, "current_session", None)
    if isinstance(current_session, dict):
        session_id = int(current_session.get("id") or 0) or None
    if session_id is None:
        session_id = _session_id_from_request(request)

    if session_id is not None:
        revoke_session(session_id)

    response.delete_cookie(key=COOKIE_NAME, path="/")

    write_audit_event(user_id(current_user), "logout", None, ip_address, user_agent)
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
def me(current_user: dict[str, Any] = Depends(require_authenticated_user)) -> dict[str, Any]:
    user_row = find_user_by_id(user_id(current_user))
    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authenticated user record not found.",
        )
    return user_to_response_payload(user_row)


@router.get("/users", response_model=list[UserResponse])
def get_users(_: dict[str, Any] = Depends(require_admin_user)) -> list[dict[str, Any]]:
    return [user_to_response_payload(row) for row in list_users()]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_account(
    payload: CreateUserRequest,
    request: Request,
    admin_user: dict[str, Any] = Depends(require_admin_user),
) -> dict[str, Any]:
    username = str(payload.username or "").strip()
    display_name = str(payload.display_name or "").strip() or username
    role = str(payload.role or "standard").strip().lower()
    password = str(payload.password or "")

    if role not in {"admin", "standard"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be 'admin' or 'standard'.")
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is required.")
    if len(password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters.")
    if find_user_by_username(username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists.")

    created = create_user(
        username=username,
        display_name=display_name,
        password_hash=hash_password(password),
        role=role,
    )
    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user.",
        )

    ip_address, user_agent = _request_ip_and_agent(request)
    write_audit_event(
        user_id(admin_user),
        "user_created",
        {"target_user_id": int(created["id"]), "target_username": username, "role": role},
        ip_address,
        user_agent,
    )
    return user_to_response_payload(created)


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: ResetPasswordRequest,
    request: Request,
    admin_user: dict[str, Any] = Depends(require_admin_user),
) -> dict[str, bool]:
    target_user = find_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    new_password = str(payload.new_password or "")
    if len(new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters.")

    if not update_user_password(user_id, hash_password(new_password)):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password.",
        )

    revoke_all_user_sessions(user_id)
    ip_address, user_agent = _request_ip_and_agent(request)
    write_audit_event(
        user_id(admin_user),
        "password_reset",
        {"target_user_id": user_id},
        ip_address,
        user_agent,
    )
    return {"ok": True}


@router.put("/me/gemini-key", response_model=UserResponse)
def set_my_gemini_key(
    payload: SetGeminiKeyRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    current_user_id = user_id(current_user)
    api_key = str(payload.api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API key is required.")

    try:
        encrypted_key = encrypt_gemini_key(api_key)
    except GeminiKeyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    if not update_user_gemini_key(current_user_id, encrypted_key):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store API key.",
        )

    invalidate_user_client_cache(current_user_id)

    ip_address, user_agent = _request_ip_and_agent(request)
    write_audit_event(current_user_id, "key_updated", {"action": "set"}, ip_address, user_agent)

    refreshed = find_user_by_id(current_user_id)
    if not refreshed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user_to_response_payload(refreshed)


@router.delete("/me/gemini-key", response_model=UserResponse)
def remove_my_gemini_key(
    request: Request,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    current_user_id = user_id(current_user)

    if not update_user_gemini_key(current_user_id, None):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove API key.",
        )

    invalidate_user_client_cache(current_user_id)

    ip_address, user_agent = _request_ip_and_agent(request)
    write_audit_event(current_user_id, "key_updated", {"action": "remove"}, ip_address, user_agent)

    refreshed = find_user_by_id(current_user_id)
    if not refreshed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user_to_response_payload(refreshed)


@router.post("/me/gemini-key/test", response_model=GeminiKeyTestResponse)
def test_my_gemini_key(
    request: Request,
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict[str, Any]:
    current_user_id = user_id(current_user)
    encrypted_key = get_user_gemini_key(current_user_id)
    if not encrypted_key:
        return {
            "valid": False,
            "error": "No API key configured. Add your key in settings first.",
        }

    try:
        plain_key = decrypt_gemini_key(encrypted_key)
    except GeminiKeyError as exc:
        return {
            "valid": False,
            "error": str(exc),
        }

    valid, error = test_gemini_api_key(plain_key)
    if valid:
        write_audit_event(
            current_user_id,
            "key_tested",
            {"valid": True},
            *_request_ip_and_agent(request),
        )

    return {
        "valid": bool(valid),
        "error": error if not valid else None,
    }
