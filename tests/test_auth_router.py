"""Authentication router behavior tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routers import auth as auth_router
from tests.helpers import login, unique_username

try:
    from cryptography.fernet import Fernet
    _CRYPTO_AVAILABLE = True
except Exception:
    Fernet = None  # type: ignore[assignment]
    _CRYPTO_AVAILABLE = False


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "test-admin-password"


def test_login_me_logout_cycle() -> None:
    client = TestClient(app)

    login(client, ADMIN_USERNAME, ADMIN_PASSWORD)

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    body = me_response.json()
    assert body["username"] == ADMIN_USERNAME
    assert body["role"] == "admin"

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200

    me_after_logout = client.get("/api/auth/me")
    assert me_after_logout.status_code == 401


def test_admin_can_create_user_and_reset_password() -> None:
    client = TestClient(app)
    login(client, ADMIN_USERNAME, ADMIN_PASSWORD)

    username = unique_username("std")
    create_response = client.post(
        "/api/auth/users",
        json={
            "username": username,
            "display_name": "Standard PM",
            "password": "initial-pass-123",
            "role": "standard",
        },
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    user_id = int(created["id"])

    client.post("/api/auth/logout")

    login(client, username, "initial-pass-123")
    client.post("/api/auth/logout")

    login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    reset_response = client.post(
        f"/api/auth/users/{user_id}/reset-password",
        json={"new_password": "updated-pass-456"},
    )
    assert reset_response.status_code == 200, reset_response.text

    client.post("/api/auth/logout")

    old_password_login = client.post(
        "/api/auth/login",
        json={"username": username, "password": "initial-pass-123"},
    )
    assert old_password_login.status_code == 401

    login(client, username, "updated-pass-456")


def test_public_user_can_register_and_is_signed_in_as_standard() -> None:
    client = TestClient(app)

    username = unique_username("self")
    register_response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": "Self Registered PM",
            "password": "register-pass-123",
        },
    )
    assert register_response.status_code == 201, register_response.text
    body = register_response.json()
    assert body["username"] == username
    assert body["role"] == "standard"

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["username"] == username

    admin_only_response = client.get("/api/auth/users")
    assert admin_only_response.status_code == 403


def test_register_rejects_duplicate_username() -> None:
    client = TestClient(app)

    username = unique_username("dup")
    first_response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": "First User",
            "password": "register-pass-123",
        },
    )
    assert first_response.status_code == 201, first_response.text
    client.post("/api/auth/logout")

    duplicate_response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": "Second User",
            "password": "register-pass-456",
        },
    )
    assert duplicate_response.status_code == 409


def test_standard_user_cannot_access_admin_users_endpoint() -> None:
    client = TestClient(app)
    login(client, ADMIN_USERNAME, ADMIN_PASSWORD)

    username = unique_username("pm")
    create_response = client.post(
        "/api/auth/users",
        json={
            "username": username,
            "display_name": "PM",
            "password": "standard-pass-123",
            "role": "standard",
        },
    )
    assert create_response.status_code == 201, create_response.text

    client.post("/api/auth/logout")
    login(client, username, "standard-pass-123")

    users_response = client.get("/api/auth/users")
    assert users_response.status_code == 403


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography is not installed")
def test_user_can_set_test_and_remove_gemini_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_KEY_ENCRYPTION_SECRET", Fernet.generate_key().decode("utf-8"))
    monkeypatch.setattr(auth_router, "test_gemini_api_key", lambda _api_key: (True, None))

    client = TestClient(app)
    login(client, ADMIN_USERNAME, ADMIN_PASSWORD)

    set_response = client.put(
        "/api/auth/me/gemini-key",
        json={"api_key": "fake-key-for-test"},
    )
    assert set_response.status_code == 200, set_response.text
    assert set_response.json()["has_gemini_key"] is True

    test_response = client.post("/api/auth/me/gemini-key/test")
    assert test_response.status_code == 200
    assert test_response.json()["valid"] is True

    delete_response = client.delete("/api/auth/me/gemini-key")
    assert delete_response.status_code == 200
    assert delete_response.json()["has_gemini_key"] is False
