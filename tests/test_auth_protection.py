"""Authentication protection coverage for existing API routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_public_routes_remain_accessible() -> None:
    client = TestClient(app)

    health_response = client.get("/health")
    assert health_response.status_code == 200

    invalid_login = client.post(
        "/api/auth/login",
        json={"username": "missing", "password": "bad-password"},
    )
    assert invalid_login.status_code == 401


def test_existing_routes_return_401_when_unauthenticated() -> None:
    client = TestClient(app)

    assert client.get("/api/quotes").status_code == 401
    assert client.get("/api/machines").status_code == 401
    assert client.get("/api/cor/1/prefill").status_code == 401
    assert client.get("/api/shipping/1/prefill").status_code == 401


def test_existing_routes_work_with_authenticated_session(auth_client) -> None:
    quotes_response = auth_client.get("/api/quotes")
    assert quotes_response.status_code == 200
